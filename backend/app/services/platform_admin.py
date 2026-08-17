"""
platform_admin.py

Entitlements-systeem voor het platform-adminpaneel (enkel voor Jordy,
niet voor trainers). Laat toe om per club een basispakket te activeren
en individuele modules (tabbladen) aan/uit te zetten — inclusief betaalde
add-ons zoals de toekomstige video-analyse.

Dit is bewust een LOS bestand van de sportwetenschap-services (periodization,
mas_testing, ...): dit is platform-/business-logica (wie mag wat zien).

BELANGRIJKE ARCHITECTUURNOTITIE
--------------------------------
Het bestaande datamodel (Users met verplichte club_id) veronderstelt dat
elke gebruiker bij precies één club hoort. Een platformeigenaar (Jordy) is
niet clubgebonden. Dit vraagt een van de volgende oplossingen:

  (A) users.club_id nullable maken, en een aparte rol 'platform_owner'
      toevoegen aan de user_role-enum die geen club_id heeft.
  (B) Een volledig aparte tabel 'platform_admins' (los van users/clubs),
      met eigen authenticatie, die geen deel uitmaakt van de multi-tenant
      structuur.

Optie (B) is gekozen (app.models.PlatformAdmin): het houdt elke rij in
'users' gegarandeerd club-gebonden (geen uitzondering, geen nullable
club_id), en een platformadmin-account heeft sowieso andere
beveiligingseisen dan een coach-account — eigen JWT-scope
(app.core.security.create_platform_admin_token), eigen dependency
(app.deps.get_current_platform_admin), nooit bereikbaar via een
club-gebonden rol.

Zuiver en side-effect-vrij: geen databasetoegang. app/routers/admin.py
haalt/schrijft de club_modules-rijen en roept deze bouwstenen aan.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


# =============================================================
# MODULE-REGISTER: het "menu" van alles wat aan/uit te zetten is
# =============================================================

class ModuleKey(str, Enum):
    DASHBOARD = "dashboard"                  # kernmodule, altijd aan
    SQUAD_OVERVIEW = "squad_overview"
    MAS_COMPENSATIE = "mas_compensatie"
    NEXT_TRAINING = "next_training"
    KALENDER = "kalender"
    MAS_TEST = "mas_test"
    RETURN_TO_PLAY = "return_to_play"
    RPE_WELLNESS = "rpe_wellness"             # optionele laag bovenop de km-gebaseerde fitheid
    VIDEO_ANALYSE = "video_analyse"          # betaalde add-on


@dataclass
class ModuleDefinition:
    key: ModuleKey
    label: str
    description: str
    in_base_package: bool          # zit dit standaard in het basispakket?
    is_core: bool                  # kan dit UITGEZET worden, of altijd aan?
    is_addon: bool                 # betaalde uitbreiding buiten het basispakket?
    monthly_price_eur: Optional[float] = None   # enkel ingevuld voor add-ons


MODULE_REGISTRY = {
    ModuleKey.DASHBOARD: ModuleDefinition(
        key=ModuleKey.DASHBOARD, label="Dashboard",
        description="Overzichtsscherm bij het inloggen.",
        in_base_package=True, is_core=True, is_addon=False,
    ),
    ModuleKey.SQUAD_OVERVIEW: ModuleDefinition(
        key=ModuleKey.SQUAD_OVERVIEW, label="Squad Overview",
        description="Spelersoverzicht met filters, blessurestatus en cyclusgrafiek per speler.",
        in_base_package=True, is_core=False, is_addon=False,
    ),
    ModuleKey.MAS_COMPENSATIE: ModuleDefinition(
        key=ModuleKey.MAS_COMPENSATIE, label="MAS & Compensatie",
        description="Wedstrijdminuten ingeven en automatische inhaalprogramma's genereren.",
        in_base_package=True, is_core=False, is_addon=False,
    ),
    ModuleKey.NEXT_TRAINING: ModuleDefinition(
        key=ModuleKey.NEXT_TRAINING, label="Next Training",
        description="AI-voorstel voor de trainingsweek, inclusief oefenvormen.",
        in_base_package=True, is_core=False, is_addon=False,
    ),
    ModuleKey.KALENDER: ModuleDefinition(
        key=ModuleKey.KALENDER, label="Kalender",
        description="Seizoensoverzicht met cyclussen, trainingen, wedstrijden en MAS-testen.",
        in_base_package=True, is_core=False, is_addon=False,
    ),
    ModuleKey.MAS_TEST: ModuleDefinition(
        key=ModuleKey.MAS_TEST, label="MAS-test",
        description="Testprotocollen kiezen en resultaten ingeven.",
        in_base_package=True, is_core=False, is_addon=False,
    ),
    ModuleKey.RETURN_TO_PLAY: ModuleDefinition(
        key=ModuleKey.RETURN_TO_PLAY, label="Return-to-play",
        description="Gefaseerd terugkeerprogramma na blessure.",
        in_base_package=True, is_core=False, is_addon=False,
    ),
    ModuleKey.RPE_WELLNESS: ModuleDefinition(
        key=ModuleKey.RPE_WELLNESS, label="RPE & Wellness",
        description=(
            "Optionele extra laag bovenop de km-gebaseerde fitheidsbepaling: RPE na elke "
            "sessie en dagelijkse wellness-vragen (slaap, vermoeidheid, spierpijn, stress, "
            "humeur). Uitgeschakeld -> het platform toont de spelerstoestand puur op basis "
            "van afgelegde kilometers, zonder dat de coach dit moet invullen."
        ),
        in_base_package=True, is_core=False, is_addon=False,
    ),
    ModuleKey.VIDEO_ANALYSE: ModuleDefinition(
        key=ModuleKey.VIDEO_ANALYSE, label="Video Analyse",
        description="Klikbare AI-highlights uit wedstrijdvideo's.",
        in_base_package=False, is_core=False, is_addon=True,
        monthly_price_eur=39.0,   # placeholder — pas aan naar je eigen prijszetting
    ),
}

BASE_PACKAGE_MODULES = {m.key for m in MODULE_REGISTRY.values() if m.in_base_package}
CORE_MODULES = {m.key for m in MODULE_REGISTRY.values() if m.is_core}


# =============================================================
# PER-CLUB MODULE-INSTELLINGEN
# =============================================================

@dataclass
class ClubModuleSettings:
    club_id: str
    enabled_modules: set = field(default_factory=set)
    last_changed_at: Optional[datetime] = None
    last_changed_by: Optional[str] = None   # naam/id van de platformadmin


def activate_base_package(club_id: str, changed_by: str) -> ClubModuleSettings:
    """Activeert het volledige basispakket voor een nieuwe club — de
    eerste actie bij het onboarden van een pilotclub."""
    return ClubModuleSettings(
        club_id=club_id, enabled_modules=set(BASE_PACKAGE_MODULES),
        last_changed_at=datetime.now(), last_changed_by=changed_by,
    )


def toggle_module(settings: ClubModuleSettings, module_key: ModuleKey,
                   enabled: bool, changed_by: str) -> ClubModuleSettings:
    """
    Zet één module aan/uit voor een club. Kernmodules (bv. Dashboard)
    kunnen nooit uitgezet worden — dat is een bewuste bescherming tegen
    een club zonder toegang tot het platform.
    """
    if module_key not in MODULE_REGISTRY:
        raise ValueError(f"Onbekende module: {module_key}")
    if module_key in CORE_MODULES and not enabled:
        raise ValueError(f"'{MODULE_REGISTRY[module_key].label}' is een kernmodule en kan niet uitgezet worden.")

    if enabled:
        settings.enabled_modules.add(module_key)
    else:
        settings.enabled_modules.discard(module_key)

    settings.last_changed_at = datetime.now()
    settings.last_changed_by = changed_by
    return settings


def get_visible_modules_for_club(settings: ClubModuleSettings) -> list:
    """
    Geeft de modules die de FRONTEND mag tonen voor deze club, in de
    volgorde van MODULE_REGISTRY. Dit is wat de navigatiebalk van de coach
    rechtstreeks aanstuurt — een module die hier niet in zit, mag noch in
    de nav, noch via een directe URL bereikbaar zijn (dus ook backend-side
    afdwingen, niet enkel de nav verbergen — zie app.deps.require_module).
    """
    return [MODULE_REGISTRY[key] for key in MODULE_REGISTRY if key in settings.enabled_modules]


def calculate_monthly_addon_price(settings: ClubModuleSettings) -> float:
    """Som van de add-on-prijzen die deze club actief heeft — het basispakket
    zelf heeft geen prijs hier (dat is een apart abonnementsgegeven,
    geen per-module-prijs)."""
    return round(sum(
        MODULE_REGISTRY[key].monthly_price_eur or 0.0
        for key in settings.enabled_modules
        if MODULE_REGISTRY[key].is_addon
    ), 2)


# =============================================================
# PERSOONLIJK DASHBOARD-WIDGET-REGISTER (per coach, niet per club)
# =============================================================
# Losstaand van MODULE_REGISTRY: modules bepalen WAT een club mag zien
# (door de platformadmin ingesteld), widgets bepalen HOE een individuele
# coach zijn eigen dashboard indeelt (door de coach zelf ingesteld,
# 'Toevoegen aan dashboard'-knop). Een widget is enkel beschikbaar als de
# onderliggende module actief is voor die club — zo blijft alles
# consistent met het entitlements-systeem.

class DashboardWidgetKey(str, Enum):
    SQUAD_COUNT = "squad_count"                        # 'Spelersgroep': aantal spelers
    ATTENTION_PLAYERS = "attention_players"             # belast/overbelast/geblesseerd
    SESSIONS_THIS_WEEK = "sessions_this_week"
    NEXT_SESSION = "next_session"
    NEXT_MATCH = "next_match"
    RECENT_SESSIONS = "recent_sessions"
    NEXT_TRAINING_BUILDER = "next_training_builder"     # 'Volgende training samenstellen'
    CURRENT_MAS_RESULTS = "current_mas_results"
    UPCOMING_MAS_TEST = "upcoming_mas_test"              # met datum
    MAKE_SCHEDULES_SHORTCUT = "make_schedules_shortcut"
    CYCLE_WEEK_STATUS = "cycle_week_status"              # bv. 'Cyclus 1 · Week 2 · Accumulatie'


@dataclass
class DashboardWidgetDefinition:
    key: DashboardWidgetKey
    label: str
    description: str
    requires_module: Optional[ModuleKey]   # None = altijd beschikbaar, geen moduleafhankelijkheid
    default_enabled: bool                   # standaard aan bij een nieuw coach-account


DASHBOARD_WIDGET_REGISTRY = {
    DashboardWidgetKey.SQUAD_COUNT: DashboardWidgetDefinition(
        key=DashboardWidgetKey.SQUAD_COUNT, label="Spelersgroep",
        description="Aantal spelers in de actieve kern.",
        requires_module=ModuleKey.SQUAD_OVERVIEW, default_enabled=True,
    ),
    DashboardWidgetKey.ATTENTION_PLAYERS: DashboardWidgetDefinition(
        key=DashboardWidgetKey.ATTENTION_PLAYERS, label="Belast / overbelast / geblesseerd",
        description="Aantal spelers met een actieve aandachtsvlag (km- of RPE-gebaseerd).",
        requires_module=None, default_enabled=True,
    ),
    DashboardWidgetKey.SESSIONS_THIS_WEEK: DashboardWidgetDefinition(
        key=DashboardWidgetKey.SESSIONS_THIS_WEEK, label="Sessies deze week",
        description="Aantal trainingen + wedstrijden in de actieve cyclusweek.",
        requires_module=ModuleKey.KALENDER, default_enabled=True,
    ),
    DashboardWidgetKey.NEXT_SESSION: DashboardWidgetDefinition(
        key=DashboardWidgetKey.NEXT_SESSION, label="Volgende sessie",
        description="Eerstvolgende training of wedstrijd.",
        requires_module=ModuleKey.KALENDER, default_enabled=True,
    ),
    DashboardWidgetKey.NEXT_MATCH: DashboardWidgetDefinition(
        key=DashboardWidgetKey.NEXT_MATCH, label="Volgende wedstrijd",
        description="Eerstvolgende wedstrijd met datum en tegenstander.",
        requires_module=ModuleKey.MAS_COMPENSATIE, default_enabled=False,
    ),
    DashboardWidgetKey.RECENT_SESSIONS: DashboardWidgetDefinition(
        key=DashboardWidgetKey.RECENT_SESSIONS, label="Recente sessies",
        description="Laatst afgewerkte trainingen/wedstrijden met belasting en teamgemiddelde RPE.",
        requires_module=ModuleKey.KALENDER, default_enabled=True,
    ),
    DashboardWidgetKey.NEXT_TRAINING_BUILDER: DashboardWidgetDefinition(
        key=DashboardWidgetKey.NEXT_TRAINING_BUILDER, label="Volgende training samenstellen",
        description="Snelkoppeling naar het samenstellen van de eerstvolgende sessie.",
        requires_module=ModuleKey.NEXT_TRAINING, default_enabled=True,
    ),
    DashboardWidgetKey.CURRENT_MAS_RESULTS: DashboardWidgetDefinition(
        key=DashboardWidgetKey.CURRENT_MAS_RESULTS, label="Huidige MAS-resultaten",
        description="Meest recente MAS-score per speler.",
        requires_module=ModuleKey.MAS_TEST, default_enabled=False,
    ),
    DashboardWidgetKey.UPCOMING_MAS_TEST: DashboardWidgetDefinition(
        key=DashboardWidgetKey.UPCOMING_MAS_TEST, label="Aankomende MAS-test",
        description="Eerstvolgende geplande teamtestdatum.",
        requires_module=ModuleKey.MAS_TEST, default_enabled=True,
    ),
    DashboardWidgetKey.MAKE_SCHEDULES_SHORTCUT: DashboardWidgetDefinition(
        key=DashboardWidgetKey.MAKE_SCHEDULES_SHORTCUT, label="Schema's maken",
        description="Snelkoppeling naar de 'Maak schema's'-actie.",
        requires_module=ModuleKey.MAS_COMPENSATIE, default_enabled=False,
    ),
    DashboardWidgetKey.CYCLE_WEEK_STATUS: DashboardWidgetDefinition(
        key=DashboardWidgetKey.CYCLE_WEEK_STATUS, label="Cyclusweek-status",
        description="Bv. 'Cyclus 1 · Week 2 · Accumulatie', afhankelijk van de actieve cyclus.",
        requires_module=ModuleKey.KALENDER, default_enabled=True,
    ),
}


@dataclass
class CoachDashboardPreferences:
    coach_id: str
    enabled_widgets: list = field(default_factory=list)   # geordende lijst DashboardWidgetKey — volgorde = layout


def get_default_dashboard_widgets(enabled_club_modules: set) -> list:
    """Standaardindeling bij een nieuw coach-account: alle widgets met
    default_enabled=True waarvan de vereiste module actief is voor de club."""
    return [
        key for key, definition in DASHBOARD_WIDGET_REGISTRY.items()
        if definition.default_enabled
        and (definition.requires_module is None or definition.requires_module in enabled_club_modules)
    ]


def get_available_widgets_for_club(enabled_club_modules: set) -> list:
    """Alle widgets die de coach ZOU KUNNEN toevoegen — gefilterd op wat
    de club effectief geactiveerd heeft. Dit voedt de 'Toevoegen aan
    dashboard'-keuzelijst."""
    return [
        definition for definition in DASHBOARD_WIDGET_REGISTRY.values()
        if definition.requires_module is None or definition.requires_module in enabled_club_modules
    ]


def toggle_dashboard_widget(prefs: CoachDashboardPreferences, widget_key: DashboardWidgetKey,
                             enabled: bool, position: Optional[int] = None) -> CoachDashboardPreferences:
    """Voegt een widget toe/verwijdert hem uit de persoonlijke lay-out van
    de coach. 'position' laat toe een widget op een specifieke plek in te
    voegen (voor de eenvoudige aan/uit-toggle volstaat None — komt dan
    achteraan)."""
    if widget_key not in DASHBOARD_WIDGET_REGISTRY:
        raise ValueError(f"Onbekende widget: {widget_key}")

    if enabled:
        if widget_key not in prefs.enabled_widgets:
            if position is not None:
                prefs.enabled_widgets.insert(position, widget_key)
            else:
                prefs.enabled_widgets.append(widget_key)
    else:
        if widget_key in prefs.enabled_widgets:
            prefs.enabled_widgets.remove(widget_key)
    return prefs


def reorder_dashboard_widgets(prefs: CoachDashboardPreferences, new_order: list) -> CoachDashboardPreferences:
    """Herschikt de widgets (drag-and-drop op het dashboard zelf, zelfde
    principe als het herschikken van oefenvorm-blokken in een sessie).
    Valideert dat de nieuwe volgorde exact dezelfde set widgets bevat —
    geen widgets erbij of kwijt tijdens het herschikken."""
    if set(new_order) != set(prefs.enabled_widgets):
        raise ValueError("De nieuwe volgorde moet exact dezelfde widgets bevatten als voorheen.")
    prefs.enabled_widgets = new_order
    return prefs
