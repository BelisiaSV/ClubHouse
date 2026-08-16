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
