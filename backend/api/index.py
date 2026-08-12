"""Vercel serverless entrypoint. The Python runtime's ASGI support picks up
the `app` object here directly — no handler boilerplate needed. Kept as a
one-line re-export so app/main.py stays the single source of truth for the
actual FastAPI app (also what `uvicorn app.main:app` runs locally).
"""

from app.main import app  # noqa: F401
