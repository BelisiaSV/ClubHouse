import logging
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.core.storage import USING_SUPABASE_STORAGE
from app.routers import (
    admin,
    auth,
    calendar,
    clubs,
    dashboard_widgets,
    makeup_programs,
    mas,
    mas_testing,
    matches,
    periodization,
    players,
    rpe_wellness,
    team_readiness,
    training_sessions,
    volume_planning,
)

logging.getLogger("clubhouse.email").setLevel(logging.INFO)
if not logging.getLogger("clubhouse.email").handlers:
    logging.getLogger("clubhouse.email").addHandler(logging.StreamHandler())

app = FastAPI(title="ClubHouse Football SaaS API", version="0.6.0")

logger = logging.getLogger("clubhouse.errors")


# An UNHANDLED exception's default 500 response is normally sent by
# Starlette's ServerErrorMiddleware, which — because @app.exception_handler
# for the base Exception class gets special-cased straight to that same
# outermost middleware — sits OUTSIDE CORSMiddleware (added below) no matter
# which of the two you use. That response never passes back through
# CORSMiddleware, so it never gets Access-Control-* headers, and the browser
# blocks it as a CORS failure — which axios can't tell apart from a dropped
# connection, so it just reports "Network Error" with the real cause (and
# any useful detail message) invisible. Registering this as ordinary HTTP
# middleware INSTEAD, and doing so before CORSMiddleware is added (Starlette
# wraps middleware in reverse add-order, so whatever's added first ends up
# innermost, closer to the routes), catches the exception on the inside —
# the resulting response then passes back out through CORSMiddleware like
# any other, and gets real CORS headers plus a readable error.
@app.middleware("http")
async def catch_unhandled_exceptions(request, call_next):
    try:
        return await call_next(request)
    except Exception:
        logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
        return JSONResponse(status_code=500, content={"detail": "Er ging iets mis. Probeer het opnieuw."})


# Comma-separated, e.g. "https://clubhouse.vercel.app,https://clubhouse-staging.vercel.app" —
# defaults to just the local Vite dev server so nothing extra needs configuring locally.
ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("ALLOWED_ORIGINS", "http://localhost:5173").split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(clubs.router)
app.include_router(players.router)
app.include_router(rpe_wellness.router)
app.include_router(matches.router)
app.include_router(mas.router)
app.include_router(periodization.router)
app.include_router(mas_testing.router)
app.include_router(makeup_programs.router)
app.include_router(team_readiness.router)
app.include_router(volume_planning.router)
app.include_router(calendar.router)
app.include_router(training_sessions.router)
app.include_router(dashboard_widgets.router)
app.include_router(admin.router)

if not USING_SUPABASE_STORAGE:
    # Local-disk logo storage mode only (see app/core/storage.py) — skipped
    # entirely when Supabase Storage is configured, since Vercel's deployment
    # filesystem is read-only and this mkdir would raise on cold start there.
    STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
    STATIC_DIR.mkdir(exist_ok=True)
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/api/health")
def health():
    return {"status": "ok"}
