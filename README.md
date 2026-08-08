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
- **matches** / **match_minutes** — matches and the per-player minutes/GPS junction table
- **rpe_wellness_data** — daily session-RPE + wellness monitoring; `session_load` is a Postgres
  generated column (`rpe_score * session_duration_min`, Foster's sRPE)
- **training_cycles** / **training_cycle_weeks** — periodization cycles and their weekly focus

Migrations live in `alembic/versions/`. The initial migration also creates the `uuid-ossp`
extension and the `current_mas` view (not auto-detected by `--autogenerate`).

### Auth (`/api/auth`)

JWT-based, scoped by `club_id` on every request via `app/deps.get_current_user`:

- `POST /api/auth/register` — self-service whitelabel signup: creates a new club (tenant) +
  its first `head_coach` user in one step, returns an access token
- `POST /api/auth/login` — OAuth2 password flow (`username` = email), returns an access token
- `GET /api/auth/me` — current user
- `POST /api/auth/forgot-password` — always returns the same generic message (no account
  enumeration); if the email matches an active user, generates a single-use token (30 min
  expiry, only its SHA-256 hash is stored) and emails a `/reset-password?token=...` link
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
`/forgot-password`, `/reset-password?token=...`, and behind `ProtectedRoute`: `/`
(Compensation, with a player picker), `/players` (list, single add, template download/upload),
`/settings` (whitelabel branding). `AuthContext` holds the JWT (localStorage) and the current
user/club; the navbar re-colors itself from the club's `primary_color`.

## Running both

Start Postgres, then the backend (port 8000) with migrations applied, then the frontend (port
5173). Register a new club at `/register`, or log in with the seeded demo account
(`coach@demo-fc.be` / `changeme123`).
