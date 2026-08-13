"""Club logo storage: Supabase Storage in production (Vercel's serverless
filesystem is read-only outside of a non-persistent /tmp, so writing to
local disk there would silently lose every upload on the next cold start),
local disk in dev (no Supabase project needed to run the app locally).

Which mode is active is decided purely by whether SUPABASE_URL and
SUPABASE_SERVICE_ROLE_KEY are set — see .env.example.
"""

import os
import time
from pathlib import Path

import httpx

SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
SUPABASE_STORAGE_BUCKET = os.getenv("SUPABASE_STORAGE_BUCKET", "club-logos")

LOCAL_LOGO_STORAGE_DIR = Path(__file__).resolve().parent.parent.parent / "static" / "logos"

USING_SUPABASE_STORAGE = bool(SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY)


def store_club_logo(club_id, contents: bytes, content_type: str, extension: str) -> str:
    """Persists the logo and returns the club.logo_url value to store —
    either an absolute Supabase public-bucket URL, or a path served by the
    local /static mount (see app/main.py). Object path is stable per club
    (just the id + extension) so a re-upload overwrites the previous file;
    the caller adds a cache-busting query param either way."""
    object_path = f"{club_id}{extension}"

    if USING_SUPABASE_STORAGE:
        upload_url = f"{SUPABASE_URL}/storage/v1/object/{SUPABASE_STORAGE_BUCKET}/{object_path}"
        response = httpx.post(
            upload_url,
            headers={
                "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
                "Content-Type": content_type,
                "x-upsert": "true",  # overwrite on re-upload instead of erroring on a name clash
            },
            content=contents,
            timeout=15.0,
        )
        if response.status_code >= 400:
            raise RuntimeError(f"Supabase Storage upload failed ({response.status_code}): {response.text}")
        base_url = f"{SUPABASE_URL}/storage/v1/object/public/{SUPABASE_STORAGE_BUCKET}/{object_path}"
    else:
        LOCAL_LOGO_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        for existing in LOCAL_LOGO_STORAGE_DIR.glob(f"{club_id}.*"):
            existing.unlink(missing_ok=True)
        (LOCAL_LOGO_STORAGE_DIR / object_path).write_bytes(contents)
        base_url = f"/static/logos/{object_path}"

    return f"{base_url}?v={int(time.time())}"
