import time
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import Club, User
from app.schemas import ClubOut, ClubUpdateRequest

router = APIRouter(prefix="/api/clubs", tags=["clubs"])

LOGO_STORAGE_DIR = Path(__file__).resolve().parent.parent.parent / "static" / "logos"
ALLOWED_LOGO_CONTENT_TYPES = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/svg+xml": ".svg",
    "image/webp": ".webp",
}
MAX_LOGO_SIZE_BYTES = 2 * 1024 * 1024  # 2 MB


@router.get("/me", response_model=ClubOut)
def get_my_club(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.get(Club, current_user.club_id)


@router.patch("/me", response_model=ClubOut)
def update_my_club(
    payload: ClubUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    club = db.get(Club, current_user.club_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(club, field, value)
    db.commit()
    db.refresh(club)
    return club


@router.post("/me/logo", response_model=ClubOut)
def upload_my_club_logo(
    file: UploadFile,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Coaches upload their own logo (no external URL needed); it's stored
    under a filename keyed by club_id — a re-upload overwrites the same
    file, so club.logo_url stays stable except for a cache-busting query
    param. Served back via the /static mount (see app/main.py) and shown
    everywhere as a low-opacity background watermark (frontend Layout)."""
    extension = ALLOWED_LOGO_CONTENT_TYPES.get(file.content_type)
    if extension is None:
        raise HTTPException(
            status_code=400,
            detail="Enkel PNG, JPEG, SVG of WebP-afbeeldingen zijn toegestaan voor het logo.",
        )

    contents = file.file.read()
    if len(contents) > MAX_LOGO_SIZE_BYTES:
        raise HTTPException(status_code=400, detail="Logo mag maximaal 2 MB groot zijn.")

    club = db.get(Club, current_user.club_id)
    LOGO_STORAGE_DIR.mkdir(parents=True, exist_ok=True)

    # Remove any previous logo for this club under a different extension, so
    # switching from e.g. .png to .svg doesn't leave the old file lingering.
    for existing in LOGO_STORAGE_DIR.glob(f"{club.id}.*"):
        existing.unlink(missing_ok=True)

    destination = LOGO_STORAGE_DIR / f"{club.id}{extension}"
    destination.write_bytes(contents)

    # Cache-busting query param: the filename is stable per club, so without
    # this the browser would keep showing a cached old logo after a re-upload.
    club.logo_url = f"/static/logos/{club.id}{extension}?v={int(time.time())}"
    db.commit()
    db.refresh(club)
    return club
