from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.storage import store_club_logo
from app.database import get_db
from app.deps import get_current_user
from app.models import Club, User
from app.schemas import ClubOut, ClubUpdateRequest

router = APIRouter(prefix="/api/clubs", tags=["clubs"])

ALLOWED_LOGO_CONTENT_TYPES = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/svg+xml": ".svg",
    "image/webp": ".webp",
}
MAX_LOGO_SIZE_BYTES = 4 * 1024 * 1024  # 4 MB — stays under Vercel serverless functions'
# hard 4.5 MB request body ceiling once multipart overhead is added; not raisable further
# on the current hosting without switching the upload off the request body entirely.


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
    """Coaches upload their own logo (no external URL needed); stored under a
    path keyed by club_id — a re-upload overwrites the same object, so
    club.logo_url stays stable except for a cache-busting query param.
    app.core.storage.store_club_logo() picks Supabase Storage vs. local disk
    depending on which env vars are set — see that module's docstring.
    Shown everywhere as a low-opacity background watermark (frontend
    Layout)."""
    extension = ALLOWED_LOGO_CONTENT_TYPES.get(file.content_type)
    if extension is None:
        raise HTTPException(
            status_code=400,
            detail="Enkel PNG, JPEG, SVG of WebP-afbeeldingen zijn toegestaan voor het logo.",
        )

    contents = file.file.read()
    if len(contents) > MAX_LOGO_SIZE_BYTES:
        raise HTTPException(status_code=400, detail="Logo mag maximaal 4 MB groot zijn.")

    club = db.get(Club, current_user.club_id)
    try:
        club.logo_url = store_club_logo(club.id, contents, file.content_type, extension)
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail="Kon het logo niet opslaan. Probeer opnieuw.") from exc

    db.commit()
    db.refresh(club)
    return club
