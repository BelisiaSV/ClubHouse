"""Bootstraps the platform admin account (Jordy) — deliberately NOT a public
API endpoint, since platform admins are never self-registered (see
app/services/platform_admin.py's architecture note: they're not club-bound
and have no place in the open club-signup flow at POST /api/auth/register).
Run this once per environment.

Usage:
    PLATFORM_ADMIN_EMAIL=jordy@... PLATFORM_ADMIN_PASSWORD=... python seed_platform_admin.py
Falls back to dev defaults if the env vars aren't set — fine for local dev,
but always set them explicitly outside of local dev.
"""
import os

from app.core.security import hash_password
from app.database import SessionLocal
from app.models import PlatformAdmin

ADMIN_EMAIL = os.getenv("PLATFORM_ADMIN_EMAIL", "jordy@clubhouse.local")
ADMIN_PASSWORD = os.getenv("PLATFORM_ADMIN_PASSWORD", "changeme123")
ADMIN_FULL_NAME = os.getenv("PLATFORM_ADMIN_FULL_NAME", "Jordy")

db = SessionLocal()
try:
    admin = db.query(PlatformAdmin).filter_by(email=ADMIN_EMAIL).first()
    if admin is None:
        admin = PlatformAdmin(
            email=ADMIN_EMAIL,
            hashed_password=hash_password(ADMIN_PASSWORD),
            full_name=ADMIN_FULL_NAME,
        )
        db.add(admin)
        db.commit()
        db.refresh(admin)
        print(f"Created platform admin login=({ADMIN_EMAIL} / {ADMIN_PASSWORD}) id={admin.id}")
    else:
        print(f"Platform admin already exists: {ADMIN_EMAIL} (id={admin.id})")
finally:
    db.close()
