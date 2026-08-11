# ClubHouse — Whitelabel Voetbal-SaaS Platform

Monorepo: FastAPI + SQLAlchemy + Alembic backend (PostgreSQL), React + Tailwind frontend.
Multi-tenant: each club registers its own coach login and gets a fully whitelabeled
environment (name, logo, colors) with its own players, isolated from every other club.

## Backend

Requires a running PostgreSQL instance.

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env               # adjust DATABASE_URL / JWT_SECRET_KEY if needed
export $(cat .env | xargs)         # or use python-dotenv / your shell's env loading
alembic upgrade head               # creates schema, enums, current_mas view
python seed.py                     # optional: demo club + coach login + player + MAS test
uvicorn app.main:app --reload --port 8000
```

API docs at http://localhost:8000/docs.

### Data model (`app/models.py`, migrated via Alembic)

Implements the multi-tenant schema from the architecture doc 1:1, plus auth/contact fields
added on top (`alembic/versions/2255d9e9e637_*.py`):

- **clubs** — tenant root (whitelabel branding: `name`, `logo_url`, `primary_color`,
  `secondary_color`, `slug`)
- **users** — role-based (`admin`, `head_coach`, `assistant_coach`, `physio`, `analyst`,
  `player`), now with `hashed_password` for self-service login
- **players** — separate from `users` (a player may not have an account yet); `email` and
  `phone_number` were added so a coach can capture player contact details without an account,
  and `date_of_birth`/`position` were relaxed to nullable so bulk import doesn't require them
- **mas_tests** — time-series MAS (Maximal Aerobic Speed) tests per player; `current_mas` is a
  DB view exposing the latest test per player
- **matches** / **match_minutes** — matches and the per-player minutes/GPS junction table;
  `match_minutes.selection_status` (`basis`/`bank`/`niet_geselecteerd`) drives the quick-select
  dropdown on the MAS compensation panel, while `minutes_played` stays the source of truth for
  compensation math
- **rpe_wellness_data** — daily session-RPE + wellness monitoring; `session_load` is a Postgres
  generated column (`rpe_score * session_duration_min`, Foster's sRPE)
- **training_cycles** / **training_cycle_weeks** — periodization cycles and their weekly focus
- **player_weekly_distance_log** — one row per `(match_id, player_id)`, auto-populated when
  match minutes are saved (see `PATCH /api/matches/{id}/players/{player_id}` above); pinned to
  a `training_cycle_id` so `week_number` stays unambiguous across cycles
- **calendar_events** / **calendar_event_players** — club calendar items; only `event_type =
  'mas_test'` is populated so far, kept in sync with the season's MAS-test projection (see
  "MAS-test calendar projection" below). `training_cycles.target_match_date` was added so a DB
  cycle round-trips cleanly into the `services.periodization.TrainingCycle` dataclass (needed to
  reconstruct a club's `Season`); the one pre-existing cycle was backfilled with its `end_date`
  as a synthetic default.
- **training_sessions** — one row per training proposal from `POST /api/team-readiness/
  propose-training` (`week_focus` + the readiness-adjusted duration/distance target), so a coach's
  later oefenvormen choices (see "Oefenvormen" below) can reference it by id instead of the
  frontend re-sending the whole proposal.

Migrations live in `alembic/versions/`. The initial migration also creates the `uuid-ossp`
extension and the `current_mas` view (not auto-detected by `--autogenerate`).

### Auth (`/api/auth`)

JWT-based, scoped by `club_id` on every request via `app/deps.get_current_user`:

- `POST /api/auth/register` — self-service whitelabel signup: creates a new club (tenant) +
  its first `head_coach` user in one step, returns an access token
- `POST /api/auth/login` — OAuth2 password flow (`username` = email), returns an access token
- `GET /api/auth/me` — current user
- `POST /api/auth/forgot-password` — rate-limited to **3 requests per email per rolling 24h**
  (tracked by the normalized email itself, not by user, so the rate-limit response can't be
  used to distinguish real from unregistered accounts either); returns HTTP 429 with a Dutch
  notification once exceeded. Under the limit, always returns the same generic message (no
  account enumeration); if the email matches an active user, generates a single-use token
  (30 min expiry, only its SHA-256 hash is stored) and emails a `/reset-password?token=...` link
- `POST /api/auth/reset-password` — sets a new password given a valid, unused, unexpired
  token; the token and any other outstanding tokens for that user are invalidated afterwards

Emailing goes through `app/core/email.py`: if `SMTP_HOST` is set it sends real SMTP mail,
otherwise it logs the message (including the reset link) to the server console — so the whole
flow works out of the box in dev without mail credentials, and picks up real delivery the
moment SMTP env vars are set.

All `/api/players/*`, `/api/clubs/me`, and `/mas/compensation` requests require
`Authorization: Bearer <token>` and are scoped to the caller's club — a coach can only ever
see or modify their own club's data.

### Whitelabel branding (`/api/clubs`)

- `GET /api/clubs/me` / `PATCH /api/clubs/me` — each coach can customize their club's name,
  logo URL, and primary/secondary colors; the frontend applies these live (navbar color, logo).

### Players + bulk import (`/api/players`)

- `POST /api/players`, `GET /api/players`, `GET/PATCH/DELETE /api/players/{id}` — manage
  players one at a time
- `GET /api/players/import-template` — downloads a `.xlsx` template with columns
  **Rugnummer, Naam, Voornaam, E-mailadres, Telefoonnummer** (plus one example row)
- `POST /api/players/import` — upload the filled-in `.xlsx` to bulk-create players in one go;
  returns `{created, skipped, errors: [{row, message}]}` so invalid rows are reported without
  failing the whole batch

### Matches (`/api/matches`)

- `GET /api/matches` — club's matches, most recent first
- `POST /api/matches` — create a match (opponent, date, home/away, competition)
- `GET /api/matches/{id}/players` — every active club player merged with their `match_minutes`
  row for that match (defaulting to `basis`/90' for anyone without one yet) and their latest
  MAS score
- `PATCH /api/matches/{id}/players/{player_id}` — upsert a player's status/minutes for that
  match; `minutes_played` is derived from `selection_status` (basis→90, bank/niet
  geselecteerd→0) when not explicitly overridden. As a background step of this same save (no
  separate coach action), it also auto-populates that player's estimated match distance for the
  cycle week the match falls in — `calculate_player_match_distance()` /
  `populate_match_distance_for_week()` in `app/services/volume_planning.py`, upserted into
  `player_weekly_distance_log` keyed by `(match_id, player_id)` so re-saving minutes corrects
  the same row instead of accumulating duplicates. Silently skipped (never blocks the minutes
  save) if the player has no position set, or the club has no active cycle/no cycle week covers
  the match date.
- `GET /api/players/{id}/weekly-distance?week_number=N` — that player's summed
  `match_distance_km` (from the log above) + `training_distance_km` (reserved for a future
  "actually completed training" log — there's no such tracking yet, so always 0) for one week of
  the club's active cycle, for showing next to a position's km target on the frontend.

### `POST /mas/compensation`

Exposes `calculate_hit_compensation()` (`app/services/mas_compensation.py`, ported from the
architecture doc's reference implementation) as an endpoint. Given a `player_id` and
`minutes_played`, it looks up the player's most recent MAS test (within the caller's own club)
and returns a fully specified 15s/15s HIT compensation protocol at the requested
`intensity_pct` (default 110% MAS): target speed, total reps/blocks, distance, and a
human-readable protocol description.

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login \
  -d 'username=coach@demo-fc.be&password=changeme123' | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

curl -X POST http://localhost:8000/mas/compensation \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"player_id": "<uuid>", "minutes_played": 32, "intensity_pct": 1.10}'
```

### Periodization / MAS dashboard panels

`app/services/` also holds a pure, DB-free service layer split out of the club's
`football_periodization_services.py` — one module per dashboard panel, all built on the same
shared `WeekFocus` / `CycleWeek` / `TrainingCycle` dataclasses (defined once, in
`periodization.py`, and imported by the other four):

| Service module | Router (`app/routers/`) | Prefix | What it does |
|---|---|---|---|
| `periodization.py` | `periodization.py` | `/api/periodization` | Build a training cycle (`build_cycle`); reschedule it when the target match is postponed (`handle_match_cancellation`) — shifts the remaining weeks and injects recovery weeks so there's no training gap |
| `mas_testing.py` | `mas_testing.py` | `/api/mas-testing` | When a player's next MAS (re)test is due, and the training-zone speeds (% MAS) derived from a MAS score |
| `makeup_programs.py` | `makeup_programs.py` | `/api/makeup-programs` | The "Maak schema's" button: generates individual catch-up running programs for missed match minutes and/or missed trainings |
| `team_readiness.py` | `team_readiness.py` | `/api/team-readiness` | ACWR + wellness-based player flags (overload/underload/poor recovery/injured), and a team training proposal (duration + km) scaled to squad readiness |
| `volume_planning.py` | `volume_planning.py` | `/api/volume-planning` | Weekly km target per cycle phase, split between match load and training load |
| `session_composition.py` | `training_sessions.py` | `/api/training-sessions` | "AI physical coach" for session content: translates a session's abstract duration/distance target into concrete, recognizable oefenvormen (`propose_session_composition`), or lets the coach price out one specific oefenvorm they pick from a menu (`calculate_vorm_target`) |

Because the services are pure functions with no database access, every router endpoint takes
the full input it needs in the request body (e.g. the whole `TrainingCycle`, not just an id) and
returns the computed result — nothing is persisted. `app/schemas_dashboards.py` holds the
Pydantic request/response contracts, with `CycleWeekSchema`/`TrainingCycleSchema` shared across
all five routers the same way the dataclasses are shared across the five services. All
endpoints require `Authorization: Bearer <token>` like the rest of the API. See `/docs` for the
full request/response shape of each endpoint.

Several endpoints add a DB-backed layer on top of that pure-calculator design, for the MAS
compensation panel:

- `POST /api/periodization/cycles` also persists its result as the club's one active cycle
  (`training_cycles`/`training_cycle_weeks`, deactivating any previous one) so it can be looked
  up later without the frontend re-sending it.
- `POST /api/makeup-programs/generate-for-match` — the panel's "Maak schema's" button. Takes
  only `match_id`; server-side it resolves the club's active cycle and the week covering today,
  builds candidates from every player under the 60' threshold (using their latest MAS test and
  `match_minutes` for that match), and calls the same `generate_makeup_schedules()` used by the
  plain `/generate` endpoint. Returns `400` with a clear message if there's no active cycle or
  no week covering today, and lists any under-threshold players skipped for lacking a MAS test.
- `POST /api/periodization/cycles/queue-next` — the Settings "Cyclusplanning" weekselector. Sets
  the club's *next* cycle without ever touching the currently active, running one. Calling it
  again while that active cycle is still running **overwrites the already-queued (not yet
  started) next cycle in place** — same start date, new length/target/name — instead of
  returning a `400`; this lets a coach change their mind about a cycle before it starts. Server-
  side, `app/routers/periodization.py::load_season_from_db()` reconstructs a full `Season` from
  the club's `training_cycles` rows (ordered by `start_date`, DB `is_active` flag deliberately
  ignored — see `Season.get_active_cycle_and_week`'s docstring on never trusting a static
  activeness column) before calling `services.periodization.queue_next_cycle()`; whether that
  call appended a new cycle or overwrote the season's last one decides an `INSERT` vs `UPDATE`
  against `training_cycles`/`training_cycle_weeks`. Newly queued cycles are stored with
  `is_active=False`, so this never interferes with the `is_active=True` lookups the rest of the
  app still uses for "the" active cycle.
- `GET /api/mas-testing/protocols` — the four MAS field-test protocols a coach can choose from
  (VAMEVAL, 30-15 IFT, UMTT, 20m shuttle run), each with equipment, how-to-administer notes, and
  the `correction_factor` used to convert a raw result into a MAS score.
- `POST /api/mas-testing/record` — the "MAS-test invoeren" action on `/players`. Takes a
  `player_id`, `protocol_key`, raw result, and test date; converts it to a MAS score via
  `services.mas_testing.record_mas_test()` and stores it as a new `mas_tests` row. Immediately
  re-syncs the MAS-test calendar (see below) so any projected test dates depending on this
  player's new baseline update right away, and returns how many calendar events were
  (re)written.
- `POST /api/mas-testing/sync-calendar` — standalone trigger for the same calendar (re)sync, in
  case it ever needs to be run outside of recording a result.
- `GET /api/calendar/events?event_type=mas_test&from_date=…` — reads the club's calendar items
  (`app/routers/calendar.py`); currently only `mas_test` is populated. Powers the "Aankomende
  MAS-testen" list on `/matches`.

### MAS-test calendar projection

`services.mas_testing.project_season_mas_test_events()` projects **every** MAS test a club's
players will need for the rest of the season — not just the next one — grouping players whose
required dates fall within `group_window_days` of each other into a single calendar event
(fewer separate team test sessions to organize). It's explicitly a re-runnable *projection*, not
a one-time schedule: if a coach tests later or earlier than planned, the remaining projected
dates need to shift too. `app/routers/mas_testing.py::_sync_mas_test_calendar()` is the DB-backed
wrapper that makes that automatic — it rebuilds the projection from the club's current cycles and
every active player's latest `mas_tests` row, then wholesale-replaces the club's not-yet-past
`calendar_events` rows of type `mas_test` (`is_projected=True` and `event_date >= today`) with
the fresh set; past rows are left untouched as history. It runs both on demand
(`POST /sync-calendar`) and automatically after every `POST /record`, which is what keeps the
calendar showing the current projection instead of a stale one once a real result changes a
player's baseline.

### Oefenvormen (`/api/training-sessions`)

`POST /api/team-readiness/propose-training` now also persists its result as a `training_sessions`
row (`week_focus` + the readiness-adjusted `target_duration_min`/`target_distance_km`) and
returns its id as `session_id` — "the already-existing session" the endpoints below act on, so a
coach's later choices don't need to re-send the whole proposal.

The **km target is the leading number, not the session duration**: `propose_session_composition()`
builds a baseline block breakdown from the cycle phase's template, then rescales every block's
duration by the same factor so the total distance lands as close as possible to the km goal
(bounded to a 0.3-2.5x scale factor to avoid degenerate cases). Small/medium/large-sided games and
transition vormen are never proposed as one continuous block — they're structured into repeated
bouts with rest between them (SSG 3'/2' rest, MSG 5.5'/2.5' rest, LSG 9'/3.5' rest; each vorm's
own bout/rest timing lives on its `OefenvormProfile` in `OEFENVORM_LIBRARY`), matching
small-sided-games injury-prevention literature — so `total_clock_time_min` (work + rest) can run
well past `target_duration_min`; that's expected, not an error. `format_hint` tells the coach the
suggested sub-format (e.g. "7v7, rouleer groepen") and pitch size for player-count-sensitive
vormen, deliberately in plain pitch-size/player-count language — no RPA/m² jargon.

- `GET/POST /api/training-sessions/{session_id}/composition-proposal` — the session's stored
  `week_focus`/duration/distance target plus a coach-supplied `num_players` (`?num_players=` query
  param on `GET`, `{"num_players", "team_avg_mas_kmh", "player_flags"}` body on `POST` — both
  routes share one handler; `player_flags` is POST-only since a list of objects doesn't fit a
  query string). Returns the full block breakdown plus `optional_dry_run_topup`: if scaling still
  leaves a meaningful shortfall (>150m) after rounding partijvormen to whole bouts, and
  `team_avg_mas_kmh` was given, a supplementary ball-less running block is suggested to close the
  gap (`null` otherwise).
- `POST /api/training-sessions/{session_id}/vorm-target` — body: `{vorm, duration_min,
  num_players}`. Calls `calculate_vorm_target()` for that one oefenvorm and returns its expected
  duration/distance/intensity band/bout structure. Meant to be called every time a coach picks a
  vorm from the dropdown and types a duration, e.g. while building out a session block by block.
- `POST /api/training-sessions/{session_id}/recalculate` — body: `{blocks, target_distance_km,
  player_flags}`. Re-sums a (possibly coach-edited) block list — e.g. after swapping in a
  `vorm-target` result for one block — against the given km goal via
  `services.session_composition.summarize_composition()`, the same function
  `propose_session_composition()` itself calls internally. Its `deviation_note` adds an explicit
  overload warning when the total is clearly above target AND `player_flags` already lists an
  `overload`/`poor_recovery` player, so a coach doesn't accidentally push extra volume onto
  someone already flagged.
- `POST /api/training-sessions/dry-run-topup` — body: `{remaining_distance_km,
  team_avg_mas_kmh}`. A standalone (not session-scoped, since `propose_optional_dry_running_topup()`
  needs no session context) way to ask for the same supplementary running block on demand, for
  when a coach wants one after the fact rather than only seeing it inline on the initial proposal.

`{session_id}`-scoped endpoints validate session ownership (404 for another club's session) but
`vorm-target`/`recalculate` compute purely from their request body, not the session's stored
values — mirroring how `POST /api/makeup-programs/generate-for-match` already separates "which
club resource is this for" from "what to compute with". All four endpoints return a clear `400`
(never FastAPI's generic `422`) for an unknown oefenvorm key or `num_players <= 0` — `vorm` and
`num_players` are accepted as plain, unconstrained types in the request schemas specifically so
every rejection routes through `services.session_composition`'s own `ValueError`s (plus one
explicit `num_players` check in the router for `vorm-target`, since `calculate_vorm_target()`
doesn't validate that itself) instead of Pydantic's request validation.

`backend/tests/test_session_composition.py` (run via `pytest` from `backend/`, now in
`requirements.txt`) pins a regression scenario — 18 players, an intensification week, a 68'/6.3km
target — asserting the proposal's total distance stays within 10% of the km goal despite the
longer partijvorm bout/rest structure above (currently lands at 5.99 km, ~5% under).

## Frontend

```bash
cd frontend
npm install
npm run dev
```

Runs on http://localhost:5173, proxying `/mas/*` and `/api/*` to `http://localhost:8000` (see
`vite.config.js` — kept to just those two prefixes on purpose, since a broader proxy rule like
`/players` would shadow the frontend's own `/players` route on direct navigation/refresh).

Pages: `/login` (with a "wachtwoord vergeten?" link), `/register` (club + coach signup),
`/forgot-password`, `/reset-password?token=...`, and behind `ProtectedRoute`: `/` (the MAS
compensation panel), `/matches` (match calendar plus an "Aankomende MAS-testen" list from
`GET /api/calendar/events`), `/players` (list, single add, template download/upload, and a
per-player "MAS-test invoeren" action that calls `POST /api/mas-testing/record`), `/settings`
(whitelabel branding plus a "Cyclusplanning" weekselector calling
`POST /api/periodization/cycles/queue-next` — a repeat submission while the active cycle is
still running just re-confirms the update, it's never rendered as an error, since the backend
overwrites the queued cycle instead of rejecting the call). `AuthContext` holds the JWT
(localStorage) and the current user/club; the navbar re-colors itself from the club's
`primary_color`.

`/` is the MAS compensation panel (ported from a Claude Design mockup, wired to the endpoints
above through `src/api/client.js` — no direct `fetch()` calls in the component): a match
selector populated from `GET /api/matches`; a per-player table (status + exact-minutes
dropdowns, each saving on change via `PATCH /api/matches/{id}/players/{player_id}` with a
per-row ✓/error+retry indicator — a native `<select>`'s `onChange` only fires once per choice,
which already gives "save on close, not per keystroke" for free); and a "Maak schema's" button
that calls `POST /api/makeup-programs/generate-for-match` with just the match id. A `400` (no
active cycle) renders as an inline explanation, not a silent failure; a `401` is handled
globally by an axios response interceptor that clears the token and redirects to `/login`. No
matches yet → an empty state links to `/matches` to add one.

## Running both

Start Postgres, then the backend (port 8000) with migrations applied, then the frontend (port
5173). Register a new club at `/register`, or log in with the seeded demo account
(`coach@demo-fc.be` / `changeme123`).
