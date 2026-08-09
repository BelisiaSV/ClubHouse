import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import (
    auth,
    clubs,
    makeup_programs,
    mas,
    mas_testing,
    periodization,
    players,
    team_readiness,
    volume_planning,
)

logging.getLogger("clubhouse.email").setLevel(logging.INFO)
if not logging.getLogger("clubhouse.email").handlers:
    logging.getLogger("clubhouse.email").addHandler(logging.StreamHandler())

app = FastAPI(title="ClubHouse Football SaaS API", version="0.5.0")

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
app.include_router(mas.router)
app.include_router(periodization.router)
app.include_router(mas_testing.router)
app.include_router(makeup_programs.router)
app.include_router(team_readiness.router)
app.include_router(volume_planning.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}
