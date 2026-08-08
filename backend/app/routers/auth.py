from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password, verify_password
from app.database import get_db
from app.deps import get_current_user
from app.models import Club, User, UserRole
from app.schemas import RegisterRequest, TokenResponse, UserOut

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    """Self-service whitelabel signup: creates a new club (tenant) and its first
    head coach account in one step."""
    if db.query(Club).filter_by(slug=payload.club_slug).first() is not None:
        raise HTTPException(status_code=409, detail="Club slug already in use")
    if db.query(User).filter_by(email=payload.email).first() is not None:
        raise HTTPException(status_code=409, detail="Email already registered")

    club = Club(name=payload.club_name, slug=payload.club_slug)
    db.add(club)
    db.flush()

    user = User(
        club_id=club.id,
        email=payload.email,
        hashed_password=hash_password(payload.password),
        full_name=payload.coach_full_name,
        role=UserRole.HEAD_COACH,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(subject=str(user.id), club_id=str(club.id))
    return TokenResponse(access_token=token)


@router.post("/login", response_model=TokenResponse)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter_by(email=form_data.username).first()
    if user is None or user.hashed_password is None or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is deactivated")

    token = create_access_token(subject=str(user.id), club_id=str(user.club_id))
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)):
    return current_user
