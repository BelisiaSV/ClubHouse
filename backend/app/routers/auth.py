from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.core.email import send_password_reset_email
from app.core.security import (
    PASSWORD_RESET_TOKEN_EXPIRE_MINUTES,
    create_access_token,
    generate_password_reset_token,
    hash_password,
    hash_reset_token,
    verify_password,
)
from app.database import get_db
from app.deps import get_current_user
from app.models import Club, ClubModule
from app.models import ModuleKey as DbModuleKey
from app.models import PasswordResetAttempt, PasswordResetToken, User, UserRole
from app.schemas import (
    ForgotPasswordRequest,
    MessageResponse,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
    UserOut,
)
from app.services.platform_admin import BASE_PACKAGE_MODULES

router = APIRouter(prefix="/api/auth", tags=["auth"])

GENERIC_FORGOT_PASSWORD_MESSAGE = (
    "Als dit e-mailadres bij ons bekend is, hebben we een link om je wachtwoord te "
    "resetten verstuurd."
)

# Rate limit: max requests per email within a rolling 24h window (not calendar day,
# so it can't be gamed by sending 3 just before and 3 just after midnight).
MAX_FORGOT_PASSWORD_ATTEMPTS_PER_DAY = 3
FORGOT_PASSWORD_WINDOW = timedelta(hours=24)
RATE_LIMIT_MESSAGE = (
    "Je hebt het maximum van 3 aanvragen voor dit e-mailadres vandaag al bereikt. "
    "Probeer het morgen opnieuw."
)


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

    # Self-service signup gets the free base package immediately (same
    # modules services.platform_admin.activate_base_package() would turn
    # on) — only paid add-ons like video_analyse stay gated behind a
    # platform admin actually enabling them. Without this, module-gating
    # (app.deps.require_module) would default-deny a brand new club out of
    # every feature the moment they finish registering.
    for module_key in BASE_PACKAGE_MODULES:
        db.add(ClubModule(club_id=club.id, module_key=DbModuleKey(module_key.value), enabled=True, changed_by="self-service registration"))

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


@router.post("/forgot-password", response_model=MessageResponse)
def forgot_password(payload: ForgotPasswordRequest, db: Session = Depends(get_db)):
    """Always returns the same generic message, whether or not the email is known,
    so this endpoint can't be used to enumerate registered accounts.

    Rate-limited to MAX_FORGOT_PASSWORD_ATTEMPTS_PER_DAY per email, tracked by the
    raw email string rather than by user_id, so the rate-limit response itself
    doesn't leak whether the account exists."""
    normalized_email = payload.email.strip().lower()
    now = datetime.now(timezone.utc)

    recent_attempts = db.query(PasswordResetAttempt).filter(
        PasswordResetAttempt.email == normalized_email,
        PasswordResetAttempt.requested_at >= now - FORGOT_PASSWORD_WINDOW,
    ).count()
    if recent_attempts >= MAX_FORGOT_PASSWORD_ATTEMPTS_PER_DAY:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=RATE_LIMIT_MESSAGE)

    db.add(PasswordResetAttempt(email=normalized_email))

    user = db.query(User).filter_by(email=payload.email).first()
    raw_token = None
    if user is not None and user.is_active:
        raw_token, token_hash = generate_password_reset_token()
        db.add(
            PasswordResetToken(
                user_id=user.id,
                token_hash=token_hash,
                expires_at=now + timedelta(minutes=PASSWORD_RESET_TOKEN_EXPIRE_MINUTES),
            )
        )

    db.commit()

    if raw_token is not None:
        send_password_reset_email(user.email, raw_token)

    return MessageResponse(message=GENERIC_FORGOT_PASSWORD_MESSAGE)


@router.post("/reset-password", response_model=MessageResponse)
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)):
    token_hash = hash_reset_token(payload.token)
    reset_token = db.query(PasswordResetToken).filter_by(token_hash=token_hash).first()

    now = datetime.now(timezone.utc)
    if reset_token is None or reset_token.used_at is not None or reset_token.expires_at < now:
        raise HTTPException(status_code=400, detail="Ongeldige of verlopen resetlink")

    user = db.get(User, reset_token.user_id)
    user.hashed_password = hash_password(payload.new_password)
    reset_token.used_at = now

    # Invalidate any other outstanding reset tokens for this user.
    db.query(PasswordResetToken).filter(
        PasswordResetToken.user_id == user.id,
        PasswordResetToken.used_at.is_(None),
    ).update({"used_at": now})

    db.commit()
    return MessageResponse(message="Wachtwoord succesvol gewijzigd.")
