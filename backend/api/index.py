"""Vercel serverless entrypoint. The Python runtime's ASGI support picks up
the `app` object here directly — no handler boilerplate needed. Re-exports
app/main.py's FastAPI app so that stays the single source of truth (also
what `uvicorn app.main:app` runs locally).

The sys.path insert below is required: Vercel's Python runtime doesn't
reliably put this file's parent directory (backend/, which is where the
`app` package actually lives) on sys.path before importing this module,
so a bare `from app.main import app` fails with "could not import
api/index.py" at cold start without it.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.main import app  # noqa: E402,F401
