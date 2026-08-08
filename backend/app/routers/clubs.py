from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import Club, User
from app.schemas import ClubOut, ClubUpdateRequest

router = APIRouter(prefix="/api/clubs", tags=["clubs"])


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
