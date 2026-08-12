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
python seed_platform_admin.py      # optional: platform admin login (see "Platform admin" below)
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
- **platform_admins** — completely separate from `clubs`/`users` (no `club_id`, no relationship);
  see "Platform admin" below for why.
- **club_modules** — `(club_id, module_key)` → `enabled`/`changed_at`/`changed_by`, one row per
  module a platform admin has ever touched for that club; see "Platform admin" below.

Migrations live in `alembic/versions/`. The initial migration also creates the `uuid-ossp`
extension and the `current_mas` view (not auto-detected by `--autogenerate`).

### Auth (`/api/auth`)

JWT-based, scoped by `club_id` on every request via `app/deps.get_current_user`:

- `POST /api/auth/register` — self-service whitelabel signup: creates a new club (tenant) +
  its first `head_coach` user in one step, activates the free base package for it (see "Platform
  admin" below — otherwise module-gating's default-deny would lock a brand new club out of
  everything), and returns an access token
- `POST /api/auth/login` — OAuth2 password flow (`username` = email), returns an access token.
  The JWT carries `scope: "club_user"` (a separate `scope: "platform_admin"` token type exists
  for `POST /admin/auth/login` — see "Platform admin" below — and each is rejected by the other's
  auth dependency)
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

- `GET /api/clubs/me` / `PATCH /api/clubs/me` — each coach can customize their club's name and
  primary/secondary colors; the frontend applies these live everywhere (navbar, buttons, focus
  rings — see "Design system" under Frontend below) via CSS custom properties, not just the
  navbar color it used to.
- `POST /api/clubs/me/logo` — multipart upload (PNG/JPEG/SVG/WebP, max 2 MB); replaces
  `logo_url` with the free-form text field it used to be. Stored under `backend/static/logos/
  {club_id}.{ext}` (served via the `/static` mount in `app/main.py`, gitignored — this is
  uploaded content, not source) and served back with a cache-busting `?v=` query param so a
  re-upload shows immediately instead of the browser's cached old logo.

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
- `GET /api/periodization/cycles/current` — both the active cycle and the queued one (if any),
  each with its DB `id`, for the Settings page's two cycle sections: an "Actieve cyclus" editor
  and the existing Cyclusplanning form, now pre-filled with the queued cycle's current values
  when one exists instead of always starting blank.
- `PATCH /api/periodization/cycles/active` — edits the *running* cycle in place: name, target
  match date, target peak weekly km. Deliberately **not** length/start date — the active cycle's
  weeks already have real dates baked in and `player_weekly_distance_log` rows already reference
  them by `training_cycle_id`/`week_number`, so a structural change here could silently corrupt
  that history. Use `POST /cycles` to replace the active cycle outright if a structural change is
  genuinely needed. `404` if the club has no active cycle right now.
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
- `POST /api/training-sessions/{session_id}/vorm-target` — body: `{vorm, num_players}` plus
  **either** `duration_min` **or** `num_bouts`, never both, decided by which of the two the vorm
  actually is: partijvormen (SSG/MSG/LSG/transitie) only take `num_bouts` — the bout length itself
  (e.g. 3' for SSG) is scientifically fixed and was never meant to be coach-adjustable, so
  `calculate_vorm_target_by_reps()` is now the only way to manually resize one, letting the coach
  pick a rep count while the block length stays put; continuous vormen (pass-en-trap, balbezit,
  patroon, afwerking) are unchanged, still sized via `duration_min` through `calculate_vorm_target()`.
  Sending `duration_min` to a partijvorm, `num_bouts` to a continuous vorm, or omitting the one
  the vorm needs all return `400`. Both underlying functions clamp their input to a safety
  ceiling derived from the vorm's `typical_duration_min` upper bound (a requested `duration_min`
  is capped directly; a requested `num_bouts` is capped to `typical_duration_min[1] //
  bout_duration_min`) and append an explanatory note to the returned `notes` field whenever that
  ceiling is actually hit, so a coach who asks for an unrealistic amount (e.g. 40' of continuous
  small-sided games) gets a safe result plus a visible explanation instead of a silent clamp or a
  rejected request.
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
(never FastAPI's generic `422`) for an unknown oefenvorm key or `num_players <= 0` — `vorm`,
`duration_min`/`num_bouts`, and `num_players` are all accepted as plain, unconstrained/optional
types in the request schemas specifically so every rejection (unknown vorm, wrong field for the
vorm, missing required field, non-positive count) routes through
`services.session_composition`'s own `ValueError`s plus the router's own vorm/field-shape checks,
instead of Pydantic's request validation.

`backend/tests/test_session_composition.py` (run via `pytest` from `backend/`, now in
`requirements.txt`) pins a regression scenario — 18 players, an intensification week, a 68'/6.3km
target — asserting the proposal's total distance stays within 10% of the km goal despite the
longer partijvorm bout/rest structure above (currently lands at 5.99 km, ~5% under).

## Platform admin (`/admin`) — Jordy only, never a club role

`app/services/platform_admin.py` is the entitlements system behind a future admin panel: which
modules (tabs) each club can see, including a paid `video_analyse` add-on. Ported straight from
the uploaded reference file, including its architecture note:

> Option (B) — a fully separate `platform_admins` table, with its own auth, no part of the
> multi-tenant club/user structure — over (A) making `users.club_id` nullable with a
> `platform_owner` role, because it keeps every `users` row guaranteed club-scoped (no exception
> to carve out elsewhere) and a platform-owner account has different security requirements than a
> coach account anyway.

That's what's implemented:

- **`platform_admins`** (`app/models.py`) — id/email/hashed_password/full_name/is_active, no
  `club_id`, no relationship to `Club`/`User`. Bootstrapped via `python seed_platform_admin.py`
  (env vars `PLATFORM_ADMIN_EMAIL`/`PLATFORM_ADMIN_PASSWORD`/`PLATFORM_ADMIN_FULL_NAME`, dev
  defaults `jordy@clubhouse.local` / `changeme123`) — deliberately **not** a public API endpoint,
  since platform admins are never self-registered.
- **`POST /admin/auth/login`** — its own OAuth2-password login, entirely separate from
  `/api/auth/login`. The resulting JWT carries `scope: "platform_admin"` and no `club_id` claim
  (club-user tokens now carry `scope: "club_user"`); `app/deps.py::get_current_user` and
  `get_current_platform_admin` each check the other's scope is absent/wrong and reject it, so a
  token minted by one login can never be replayed against the other's endpoints — verified both
  directions with curl (a coach token 401s on every `/admin/*` route; an admin token 401s on
  every `/api/*` club route).
- **`club_modules`** (`club_id`, `module_key`, `enabled`, `changed_at`, `changed_by`) — one row
  per (club, module) ever touched, mirroring `ClubModuleSettings` but as an explicit boolean per
  row (an audited update) rather than presence-in-a-set. The migration backfills every
  pre-existing club with the base package enabled, matching `activate_base_package()`.
- **`app/deps.py::require_module(module_key)`** — a dependency factory attached at the
  `APIRouter(dependencies=[...])` level (not per-endpoint) for every club-facing router: players
  → Squad Overview, matches/periodization/calendar → Kalender, mas.py/makeup_programs → MAS &
  Compensatie, mas_testing → MAS-test, team_readiness/volume_planning/training_sessions → Next
  Training. This runs the check for *every* route on that router automatically, including ones a
  future developer adds without remembering to annotate — a disabled module returns `403` even
  when the coach knows the exact URL, not just a hidden nav link. Core modules (currently just
  Dashboard, which has no dedicated route in this app yet) are always enabled; anything else with
  no `club_modules` row is default-deny. Verified with curl: disabling `mas_test` for a club 403s
  `GET /api/mas-testing/protocols` immediately, while `MAS & Compensatie` (a different module)
  stays reachable; re-enabling restores it.
- **Admin API** (`app/routers/admin.py`, all behind `get_current_platform_admin` only):
  - `POST /admin/clubs/{club_id}/activate-base-package` — turns on every `BASE_PACKAGE_MODULES`
    entry. Deliberately leaves any already-enabled add-on (e.g. `video_analyse`) untouched rather
    than replacing the club's whole module set the way the bare dataclass constructor would —
    otherwise re-running this on an already-configured club would silently cancel a paid add-on.
  - `POST /admin/clubs/{club_id}/modules/{module_key}/toggle` — body `{enabled}`, wraps
    `services.platform_admin.toggle_module()` including its core-module protection (`400` trying
    to disable Dashboard).
  - `GET /admin/clubs/{club_id}/modules` — full overview: every module's enabled state,
    `changed_at`/`changed_by`, and `calculate_monthly_addon_price()`.
  - All three `404` on an unknown `club_id`; `toggle` `400`s on an unknown `module_key`.

**Side effect worth calling out**: module-gating defaults to deny, so it would otherwise lock a
brand-new self-registered club out of the entire app (`POST /api/auth/register`'s club starts
with zero `club_modules` rows). `register()` now also activates the base package inline —
free-tier signup keeps working exactly as before; only paid add-ons stay behind a platform admin
actually turning them on.

No admin frontend was built this round (not asked for) — everything above is API-only, reachable
via `/docs` or curl with a `POST /admin/auth/login` token.

## Frontend

```bash
cd frontend
npm install
npm run dev
```

Runs on http://localhost:5173, proxying `/mas/*`, `/api/*`, `/admin/*`, and `/static/*` to
`http://localhost:8000` (see `vite.config.js` — kept to just those prefixes on purpose, since a
broader proxy rule like `/players` would shadow the frontend's own `/players` route on direct
navigation/refresh).

### Design system

A club's own branding now reaches the whole app, not just the navbar. `src/hooks/useClubTheme.js`
writes the logged-in club's `primary_color`/`secondary_color` onto `document.documentElement` as
CSS custom properties (`--club-primary`, `--club-primary-hover` — a darkened shade computed by
`src/utils/color.js`, no color library needed — and `--club-secondary`) whenever `club` changes;
`src/index.css` defines `.btn-brand`/`.text-brand`/`.ring-brand` helper classes on top of them, so
any primary button, link, or focus ring across every page picks up the club's colors automatically
just by using those classes. Semantic colors (red for errors, green for success/confirmation) stay
fixed system colors rather than being themed, for legibility. Pages share a consistent card/input
language (`rounded-2xl` panels on a translucent `bg-gray-900/60` with a `border-white/10` hairline,
`Inter` typeface) instead of each page's own ad hoc Tailwind classes.

`src/components/Layout.jsx` wraps every route (auth pages included, though they have no club
context yet so nothing renders there) with the navbar plus — when the club has uploaded a logo — a
centered, fixed-position watermark behind the page content at 5% opacity and `grayscale`, so it
reads as a subtle brand mark rather than competing with the text on top of it. It's `pointer-events-
none` and `z-0` under a `z-10` content layer, so it never intercepts clicks.

### Whitelabel branding UI (`/settings`)

The old free-text "Logo URL" field is gone — coaches upload an image file directly (PNG/JPEG/SVG/
WebP) via `POST /api/clubs/me/logo`, see it applied immediately (navbar + watermark, since
`refreshClub()` re-reads `club.logo_url` after the upload resolves), with its own inline error for
a rejected file type/size. Name and colors keep their explicit "Opslaan" button (`PATCH
/api/clubs/me`), unchanged apart from the styling pass above.

Below that, two cycle sections: **"Actieve cyclus"** — new, loads `GET /api/periodization/cycles/
current` and lets the coach edit the running cycle's name/target match date via its own "Opslaan"
button (`PATCH /api/periodization/cycles/active`) at any time, not just when queuing the next one.
**"Cyclusplanning"** — the existing weekselector, now pre-filled from the same `GET .../current`
call when a queued (not-yet-started) cycle already exists, so adjusting it reads as an edit instead
of always looking like a blind create; still calls `POST /api/periodization/cycles/queue-next`,
still never shows an error on a repeat submission since the backend overwrites in place.

### Pages

`/login` (with a "wachtwoord vergeten?" link), `/register` (club + coach signup),
`/forgot-password`, `/reset-password?token=...`, and behind `ProtectedRoute`: `/` (the MAS
compensation panel), `/matches` (match calendar plus an "Aankomende MAS-testen" list from
`GET /api/calendar/events`), `/players` (list, single add, template download/upload, and a
per-player "MAS-test invoeren" action that calls `POST /api/mas-testing/record`), `/settings` (see
above). `AuthContext` holds the JWT (localStorage) and the current user/club.

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
