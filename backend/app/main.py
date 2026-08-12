import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.routers import (
    admin,
    auth,
    calendar,
    clubs,
    makeup_programs,
    mas,
    mas_testing,
    matches,
    periodization,
    players,
    team_readiness,
    training_sessions,
    volume_planning,
)

logging.getLogger("clubhouse.email").setLevel(logging.INFO)
if not logging.getLogger("clubhouse.email").handlers:
    logging.getLogger("clubhouse.email").addHandler(logging.StreamHandler())

app = FastAPI(title="ClubHouse Football SaaS API", version="0.6.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(clubs.router)
app.include_router(players.router)
app.include_router(matches.router)
app.include_router(mas.router)
app.include_router(periodization.router)
app.include_router(mas_testing.router)
app.include_router(makeup_programs.router)
app.include_router(team_readiness.router)
app.include_router(volume_planning.router)
app.include_router(calendar.router)
app.include_router(training_sessions.router)
app.include_router(admin.router)

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
STATIC_DIR.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/api/health")
def health():
    return {"status": "ok"}
