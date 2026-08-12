import uuid

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.database import get_db
from app.models import ClubModule, PlatformAdmin, User
from app.services.platform_admin import CORE_MODULES, MODULE_REGISTRY, ModuleKey

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")
platform_admin_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/admin/auth/login", auto_error=False)


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(token)
        user_id = payload.get("sub")
        # Tokens minted before "scope" existed have no claim at all — treated as
        # club_user for backwards compatibility. A platform_admin token, which
        # always carries the claim, is explicitly rejected here so it can never
        # be replayed against a club-scoped endpoint.
        if user_id is None or payload.get("scope") == "platform_admin":
            raise credentials_error
    except jwt.PyJWTError:
        raise credentials_error

    user = db.get(User, uuid.UUID(user_id))
    if user is None or not user.is_active:
        raise credentials_error
    return user


def get_current_platform_admin(
    token: str | None = Depends(platform_admin_oauth2_scheme), db: Session = Depends(get_db)
) -> PlatformAdmin:
    """Completely separate from get_current_user: decodes the same JWT
    secret/algorithm but requires scope='platform_admin' and looks the
    subject up in platform_admins, never users — a club-user token is
    structurally incapable of satisfying this (no matching scope claim,
    and even a forged one wouldn't resolve to a platform_admins row)."""
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if token is None:
        raise credentials_error
    try:
        payload = decode_access_token(token)
        admin_id = payload.get("sub")
        if admin_id is None or payload.get("scope") != "platform_admin":
            raise credentials_error
    except jwt.PyJWTError:
        raise credentials_error

    admin = db.get(PlatformAdmin, uuid.UUID(admin_id))
    if admin is None or not admin.is_active:
        raise credentials_error
    return admin


def is_module_enabled_for_club(club_id: uuid.UUID, module_key: ModuleKey, db: Session) -> bool:
    """Core modules (currently just Dashboard) are always enabled regardless
    of club_modules — see services.platform_admin.CORE_MODULES. Anything
    else with no row for this club is treated as disabled (default-deny),
    which is why the club_modules migration backfills the base package for
    every pre-existing club instead of leaving them with an empty table."""
    if module_key in CORE_MODULES:
        return True
    row = (
        db.query(ClubModule)
        .filter_by(club_id=club_id, module_key=module_key)
        .first()
    )
    return row is not None and row.enabled


def require_module(module_key: ModuleKey):
    """Dependency factory — attach via APIRouter(dependencies=[Depends(require_
    module(...))]) so it runs for every route on that router, not just the ones
    that remember to declare it, and not just what the nav happens to hide.
    A disabled module 403s even when the coach knows/guesses the URL directly."""

    def _dependency(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> None:
        if not is_module_enabled_for_club(current_user.club_id, module_key, db):
            label = MODULE_REGISTRY[module_key].label
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"De module '{label}' is niet actief voor jouw club.",
            )

    return _dependency
