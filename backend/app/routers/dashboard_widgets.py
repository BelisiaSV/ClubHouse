import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user, require_module
from app.models import ClubModule, User
from app.models import CoachDashboardPreferences as DbCoachDashboardPreferences
from app.schemas_dashboards import (
    DashboardPreferencesSchema,
    DashboardWidgetSchema,
    ReorderDashboardWidgetsRequest,
    ToggleDashboardWidgetRequest,
)
from app.services.platform_admin import (
    CORE_MODULES,
    CoachDashboardPreferences,
    DashboardWidgetKey,
    ModuleKey,
    get_available_widgets_for_club,
    get_default_dashboard_widgets,
    reorder_dashboard_widgets,
    toggle_dashboard_widget,
)

router = APIRouter(
    prefix="/api/dashboard-widgets",
    tags=["dashboard-widgets"],
    dependencies=[Depends(require_module(ModuleKey.DASHBOARD))],
)


def _enabled_modules_for_club(club_id: uuid.UUID, db: Session) -> set:
    """Same computation as app.routers.clubs._to_club_out's enabled_modules:
    club_modules rows with enabled=True, plus CORE_MODULES unconditionally."""
    enabled_rows = db.query(ClubModule).filter_by(club_id=club_id, enabled=True).all()
    return {row.module_key for row in enabled_rows} | set(CORE_MODULES)


def _get_or_create_prefs(current_user: User, db: Session) -> DbCoachDashboardPreferences:
    """Lazily creates a coach's dashboard-preferences row on first access,
    seeded with get_default_dashboard_widgets() — this is what makes 'new
    coaches get the standard layout' true without needing a signup-time
    side effect."""
    row = db.scalar(
        select(DbCoachDashboardPreferences).where(DbCoachDashboardPreferences.user_id == current_user.id)
    )
    if row is None:
        enabled_modules = _enabled_modules_for_club(current_user.club_id, db)
        defaults = get_default_dashboard_widgets(enabled_modules)
        row = DbCoachDashboardPreferences(
            user_id=current_user.id, enabled_widgets=[w.value for w in defaults]
        )
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


@router.get("/available", response_model=list[DashboardWidgetSchema])
def available_widgets(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Feeds the 'Toevoegen aan dashboard'-knop: every widget the coach
    COULD add, filtered to what the club has activated via the module
    system (bv. de MAS-widgets enkel als ModuleKey.MAS_TEST actief is)."""
    enabled_modules = _enabled_modules_for_club(current_user.club_id, db)
    widgets = get_available_widgets_for_club(enabled_modules)
    return [
        DashboardWidgetSchema(
            key=w.key.value,
            label=w.label,
            description=w.description,
            requires_module=w.requires_module.value if w.requires_module else None,
            default_enabled=w.default_enabled,
        )
        for w in widgets
    ]


@router.get("/preferences", response_model=DashboardPreferencesSchema)
def get_preferences(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    row = _get_or_create_prefs(current_user, db)
    return DashboardPreferencesSchema(enabled_widgets=row.enabled_widgets)


@router.patch("/preferences/toggle", response_model=DashboardPreferencesSchema)
def toggle_widget(
    payload: ToggleDashboardWidgetRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = _get_or_create_prefs(current_user, db)
    try:
        widget_key = DashboardWidgetKey(payload.widget_key)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Onbekende widget: {payload.widget_key}")

    prefs = CoachDashboardPreferences(
        coach_id=str(current_user.id),
        enabled_widgets=[DashboardWidgetKey(k) for k in row.enabled_widgets],
    )
    try:
        toggle_dashboard_widget(prefs, widget_key, payload.enabled, payload.position)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    row.enabled_widgets = [w.value for w in prefs.enabled_widgets]
    db.commit()
    return DashboardPreferencesSchema(enabled_widgets=row.enabled_widgets)


@router.patch("/preferences/reorder", response_model=DashboardPreferencesSchema)
def reorder_widgets(
    payload: ReorderDashboardWidgetsRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = _get_or_create_prefs(current_user, db)
    prefs = CoachDashboardPreferences(
        coach_id=str(current_user.id),
        enabled_widgets=[DashboardWidgetKey(k) for k in row.enabled_widgets],
    )
    try:
        new_order = [DashboardWidgetKey(k) for k in payload.new_order]
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Onbekende widget-sleutel in nieuwe volgorde.") from exc

    try:
        reorder_dashboard_widgets(prefs, new_order)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    row.enabled_widgets = [w.value for w in prefs.enabled_widgets]
    db.commit()
    return DashboardPreferencesSchema(enabled_widgets=row.enabled_widgets)
