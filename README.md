# ClubHouse — Football SaaS Platform

Full-stack scaffold: FastAPI + SQLAlchemy backend, React + Tailwind frontend.

## Backend

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python seed.py          # optional: creates a demo player with match/RPE history
uvicorn app.main:app --reload --port 8000
```

API docs at http://localhost:8000/docs.

### Data model

- **Player** — name, position, `mas_score` (Maximal Aerobic Speed, m/s)
- **Match** — player, date, minutes played, opponent, competition
- **RPE** — session-RPE entry (`rpe_value` 0-10 × `duration_minutes` = training load)
- **Cycle** — periodization cycle (macro/meso/microcycle), optionally player-specific

### Key endpoints

- `POST /api/calculate-compensation` — given `playerId` + `matchMinutes`, prescribes HIT
  compensation running (110% MAS, 15s/15s intervals) sized to the minutes missed from a
  full 90-minute match. Protocol constants live at the top of
  `app/routers/compensation.py` and are meant to be tuned by coaching staff.
- `GET /api/wellness-status?playerId=` — computes the acute (7-day) : chronic (28-day,
  weekly-averaged) workload ratio from RPE load and returns a green/orange/red flag using
  the standard 0.8–1.3 sweet-spot bands.
- `POST /api/players`, `GET /api/players`, `POST /api/matches`, `POST /api/rpe` — minimal
  CRUD to populate data for the two endpoints above.

## Frontend

```bash
cd frontend
npm install
npm run dev
```

Runs on http://localhost:5173 and proxies `/api/*` to `http://localhost:8000` (see
`vite.config.js`). Routing is via `react-router-dom` (Dashboard / Compensation / Wellness
pages); a `PlayerContext` holds the selected player and player list fetched from the
backend.

## Running both

Start the backend on port 8000, then the frontend on port 5173. Select a player in the
navbar, then use the Compensation and Wellness pages to hit the two core endpoints.
