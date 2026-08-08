# ClubHouse — Whitelabel Voetbal-SaaS Platform

Monorepo: FastAPI + SQLAlchemy + Alembic backend (PostgreSQL), React + Tailwind frontend.

## Backend

Requires a running PostgreSQL instance.

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env               # adjust DATABASE_URL if needed
export $(cat .env | xargs)         # or use python-dotenv / your shell's env loading
alembic upgrade head               # creates schema, enums, current_mas view
python seed.py                     # optional: demo club + player + MAS test
uvicorn app.main:app --reload --port 8000
```

API docs at http://localhost:8000/docs.

### Data model (`app/models.py`, migrated via Alembic)

Implements the multi-tenant schema from the architecture doc 1:1:

- **clubs** — tenant root (whitelabel branding, slug)
- **users** — role-based (`admin`, `head_coach`, `assistant_coach`, `physio`, `analyst`, `player`)
- **players** — separate from `users` (a player may not have an account yet)
- **mas_tests** — time-series MAS (Maximal Aerobic Speed) tests per player; `current_mas` is a
  DB view exposing the latest test per player
- **matches** / **match_minutes** — matches and the per-player minutes/GPS junction table
- **rpe_wellness_data** — daily session-RPE + wellness monitoring; `session_load` is a Postgres
  generated column (`rpe_score * session_duration_min`, Foster's sRPE)
- **training_cycles** / **training_cycle_weeks** — periodization cycles and their weekly focus

Migrations live in `alembic/versions/`. The initial migration also creates the `uuid-ossp`
extension and the `current_mas` view (not auto-detected by `--autogenerate`).

### `POST /mas/compensation`

Exposes `calculate_hit_compensation()` (`app/services/mas_compensation.py`, ported from the
architecture doc's reference implementation) as an endpoint. Given a `player_id` and
`minutes_played`, it looks up the player's most recent MAS test and returns a fully specified
15s/15s HIT compensation protocol at the requested `intensity_pct` (default 110% MAS):
target speed, total reps/blocks, distance, and a human-readable protocol description.

```bash
curl -X POST http://localhost:8000/mas/compensation \
  -H 'Content-Type: application/json' \
  -d '{"player_id": "<uuid>", "minutes_played": 32, "intensity_pct": 1.10}'
```

## Frontend

```bash
cd frontend
npm install
npm run dev
```

Runs on http://localhost:5173, proxying `/mas/*` and `/api/*` to `http://localhost:8000` (see
`vite.config.js`). The single Compensation page takes a player UUID + minutes played and calls
`/mas/compensation`.

## Running both

Start Postgres, then the backend (port 8000) with migrations applied, then the frontend (port
5173). Grab a player id from `psql` or the seed script's output and paste it into the form.
