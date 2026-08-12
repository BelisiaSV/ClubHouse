import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.core.security import create_platform_admin_token, verify_password
from app.database import get_db
from app.deps import get_current_platform_admin
from app.models import Club
from app.models import ClubModule as DbClubModule
from app.models import ModuleKey as DbModuleKey
from app.models import PlatformAdmin
from app.schemas import TokenResponse
from app.schemas_admin import (
    ClubModulesOverviewResponse,
    ClubModuleStatusSchema,
    ModuleDefinitionSchema,
    ToggleModuleRequest,
)
from app.services.platform_admin import (
    BASE_PACKAGE_MODULES,
    CORE_MODULES,
    MODULE_REGISTRY,
    ClubModuleSettings,
    ModuleKey,
    calculate_monthly_addon_price,
)
from app.services.platform_admin import toggle_module as svc_toggle_module

router = APIRouter(prefix="/admin", tags=["platform-admin"])


@router.post("/auth/login", response_model=TokenResponse)
def admin_login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """Entirely separate login path from /api/auth/login — platform admins
    aren't rows in `users` (see services.platform_admin's architecture
    note), so this can't share that endpoint's query/verification logic
    even though the shape looks similar."""
    admin = db.query(PlatformAdmin).filter_by(email=form_data.username).first()
    if admin is None or not verify_password(form_data.password, admin.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")
    if not admin.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is deactivated")
    token = create_platform_admin_token(subject=str(admin.id))
    return TokenResponse(access_token=token)


def _get_club_or_404(club_id: uuid.UUID, db: Session) -> Club:
    club = db.get(Club, club_id)
    if club is None:
        raise HTTPException(status_code=404, detail="Club not found")
    return club


def _load_club_module_settings(club_id: uuid.UUID, db: Session) -> ClubModuleSettings:
    rows = db.query(DbClubModule).filter_by(club_id=club_id).all()
    enabled = {ModuleKey(r.module_key.value) for r in rows if r.enabled}
    return ClubModuleSettings(club_id=str(club_id), enabled_modules=enabled)


def _build_overview(club: Club, db: Session) -> ClubModulesOverviewResponse:
    settings = _load_club_module_settings(club.id, db)
    rows_by_key = {r.module_key.value: r for r in db.query(DbClubModule).filter_by(club_id=club.id).all()}

    modules = []
    for key, definition in MODULE_REGISTRY.items():
        row = rows_by_key.get(key.value)
        # Core modules (Dashboard) are always enabled regardless of the table,
        # mirroring app.deps.is_module_enabled_for_club's default-on-for-core rule.
        is_enabled = key in CORE_MODULES or (row is not None and row.enabled)
        modules.append(
            ClubModuleStatusSchema(
                module=ModuleDefinitionSchema.model_validate(definition),
                enabled=is_enabled,
                changed_at=row.changed_at if row else None,
                changed_by=row.changed_by if row else None,
            )
        )

    return ClubModulesOverviewResponse(
        club_id=club.id,
        club_name=club.name,
        modules=modules,
        monthly_addon_price_eur=calculate_monthly_addon_price(settings),
    )


@router.post("/clubs/{club_id}/activate-base-package", response_model=ClubModulesOverviewResponse)
def activate_base_package_endpoint(
    club_id: uuid.UUID,
    admin: PlatformAdmin = Depends(get_current_platform_admin),
    db: Session = Depends(get_db),
):
    """De eerste actie bij het onboarden van een pilotclub — activeert elke
    module uit BASE_PACKAGE_MODULES. Raakt bewust GEEN reeds actieve add-on
    (bv. video_analyse) aan: dat is prima voor de bedoelde onboarding-van-
    een-nieuwe-club-flow (die heeft nog geen add-ons), en voorkomt dat een
    herhaalde aanroep op een reeds ingerichte club per ongeluk een betaalde
    add-on uitschakelt."""
    club = _get_club_or_404(club_id, db)
    now = datetime.now(timezone.utc)

    existing = {r.module_key.value: r for r in db.query(DbClubModule).filter_by(club_id=club_id).all()}
    for key in BASE_PACKAGE_MODULES:
        row = existing.get(key.value)
        if row is None:
            db.add(
                DbClubModule(
                    club_id=club_id, module_key=DbModuleKey(key.value), enabled=True, changed_by=admin.full_name
                )
            )
        else:
            row.enabled = True
            row.changed_at = now
            row.changed_by = admin.full_name
    db.commit()

    return _build_overview(club, db)


@router.post("/clubs/{club_id}/modules/{module_key}/toggle", response_model=ClubModulesOverviewResponse)
def toggle_module_endpoint(
    club_id: uuid.UUID,
    module_key: str,
    payload: ToggleModuleRequest,
    admin: PlatformAdmin = Depends(get_current_platform_admin),
    db: Session = Depends(get_db),
):
    club = _get_club_or_404(club_id, db)
    settings = _load_club_module_settings(club_id, db)

    try:
        svc_toggle_module(settings, ModuleKey(module_key), payload.enabled, changed_by=admin.full_name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    is_enabled = ModuleKey(module_key) in settings.enabled_modules
    row = db.query(DbClubModule).filter_by(club_id=club_id, module_key=DbModuleKey(module_key)).first()
    if row is None:
        db.add(
            DbClubModule(
                club_id=club_id, module_key=DbModuleKey(module_key), enabled=is_enabled, changed_by=admin.full_name
            )
        )
    else:
        row.enabled = is_enabled
        row.changed_at = settings.last_changed_at
        row.changed_by = admin.full_name
    db.commit()

    return _build_overview(club, db)


@router.get("/clubs/{club_id}/modules", response_model=ClubModulesOverviewResponse)
def get_club_modules(
    club_id: uuid.UUID,
    admin: PlatformAdmin = Depends(get_current_platform_admin),
    db: Session = Depends(get_db),
):
    club = _get_club_or_404(club_id, db)
    return _build_overview(club, db)
