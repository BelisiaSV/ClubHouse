import { useEffect, useState } from "react";
import {
  editFirstCycle,
  getCurrentCycles,
  patchActiveCycle,
  queueNextCycle,
  startSeason,
  updateMyClub,
  uploadClubLogo,
} from "../api/client";
import { useAuth } from "../context/AuthContext.jsx";

const cardClass = "bg-gray-900/60 border border-white/10 rounded-2xl p-6 shadow-xl shadow-black/20";
const labelClass = "flex flex-col text-sm font-medium text-gray-300 gap-1.5";
const inputClass =
  "bg-gray-950 border border-white/10 text-white rounded-lg px-3 py-2.5 focus:outline-none focus:ring-2 ring-brand placeholder:text-gray-600";
const primaryButtonClass =
  "btn-brand text-white px-5 py-2.5 rounded-lg font-medium disabled:opacity-50 disabled:cursor-not-allowed";
// Kept in sync with backend/app/routers/clubs.py's MAX_LOGO_SIZE_BYTES.
const MAX_LOGO_SIZE_BYTES = 4 * 1024 * 1024;
// 0=maandag .. 6=zondag, matching Python's date.weekday() (backend/app/services/rpe_wellness.py).
const WEEKDAY_LABELS = [
  { value: 0, label: "Ma" },
  { value: 1, label: "Di" },
  { value: 2, label: "Wo" },
  { value: 3, label: "Do" },
  { value: 4, label: "Vr" },
  { value: 5, label: "Za" },
  { value: 6, label: "Zo" },
];

export default function Settings() {
  const { club, refreshClub } = useAuth();
  const [name, setName] = useState(club?.name ?? "");
  const [primaryColor, setPrimaryColor] = useState(club?.primary_color ?? "#059669");
  const [secondaryColor, setSecondaryColor] = useState(club?.secondary_color ?? "#111827");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [saved, setSaved] = useState(false);

  const [logoUploading, setLogoUploading] = useState(false);
  const [logoError, setLogoError] = useState(null);

  const [trainingWeekdays, setTrainingWeekdays] = useState(club?.training_weekdays ?? []);
  const [savingWeekdays, setSavingWeekdays] = useState(false);
  const [weekdaysError, setWeekdaysError] = useState(null);
  const [weekdaysSaved, setWeekdaysSaved] = useState(false);

  const [activeCycle, setActiveCycle] = useState(null);
  const [activeCycleForm, setActiveCycleForm] = useState({ name: "", target_peak_weekly_km: "" });
  const [savingActiveCycle, setSavingActiveCycle] = useState(false);
  const [activeCycleError, setActiveCycleError] = useState(null);
  const [activeCycleSaved, setActiveCycleSaved] = useState(false);
  const [cyclesLoading, setCyclesLoading] = useState(true);
  const [canEditFirstCycle, setCanEditFirstCycle] = useState(false);
  const [hasAnyCycle, setHasAnyCycle] = useState(true); // avoid a flash of the "start season" form while loading

  // "Seizoen starten" — only shown before any cycle exists at all. The
  // coach picks ONE explicit start date here (services.periodization.
  // start_new_season); every cycle after this is chosen via "Cyclusplanning"
  // below, which never asks for a date again.
  const [seasonName, setSeasonName] = useState("");
  const [seasonStartDate, setSeasonStartDate] = useState("");
  const [seasonLengthWeeks, setSeasonLengthWeeks] = useState(4);
  const [startingSeason, setStartingSeason] = useState(false);
  const [startSeasonError, setStartSeasonError] = useState(null);

  // "Eerste cyclus aanpassen" — only shown while canEditFirstCycle holds
  // (season has exactly 1 cycle so far), for correcting a mistake.
  const [firstCycleForm, setFirstCycleForm] = useState({ start_date: "", length_weeks: 4 });
  const [savingFirstCycle, setSavingFirstCycle] = useState(false);
  const [firstCycleError, setFirstCycleError] = useState(null);
  const [firstCycleSaved, setFirstCycleSaved] = useState(false);

  const [queuedCycleId, setQueuedCycleId] = useState(null);
  const [cycleName, setCycleName] = useState("");
  const [cycleLengthWeeks, setCycleLengthWeeks] = useState(4);
  const [queueing, setQueueing] = useState(false);
  const [queueError, setQueueError] = useState(null);
  const [queueConfirmation, setQueueConfirmation] = useState(null);

  const loadCycles = async () => {
    setCyclesLoading(true);
    try {
      const { active, queued, can_edit_first_cycle } = await getCurrentCycles();
      setActiveCycle(active);
      setCanEditFirstCycle(can_edit_first_cycle);
      setHasAnyCycle(Boolean(active || queued || can_edit_first_cycle));
      if (active) {
        setActiveCycleForm({ name: active.name, target_peak_weekly_km: active.target_peak_weekly_km });
        setFirstCycleForm({ start_date: active.start_date, length_weeks: active.length_weeks });
      }
      if (queued) {
        setQueuedCycleId(queued.id);
        setCycleName(queued.name);
        setCycleLengthWeeks(queued.length_weeks);
      } else {
        setQueuedCycleId(null);
      }
    } catch {
      // No active/queued cycle yet is a normal state, not an error to surface.
      setHasAnyCycle(false);
    } finally {
      setCyclesLoading(false);
    }
  };

  useEffect(() => {
    loadCycles();
  }, []);

  const handleStartSeason = async (e) => {
    e.preventDefault();
    setStartingSeason(true);
    setStartSeasonError(null);
    try {
      await startSeason({
        name: seasonName || `${club?.name ?? "Seizoen"}`,
        start_date: seasonStartDate,
        length_weeks: Number(seasonLengthWeeks),
      });
      await loadCycles();
    } catch (err) {
      setStartSeasonError(err.response?.data?.detail ?? err.message);
    } finally {
      setStartingSeason(false);
    }
  };

  const handleSaveFirstCycle = async (e) => {
    e.preventDefault();
    setSavingFirstCycle(true);
    setFirstCycleError(null);
    setFirstCycleSaved(false);
    try {
      await editFirstCycle(club.id, {
        start_date: firstCycleForm.start_date,
        length_weeks: Number(firstCycleForm.length_weeks),
      });
      await loadCycles();
      setFirstCycleSaved(true);
    } catch (err) {
      setFirstCycleError(err.response?.data?.detail ?? err.message);
    } finally {
      setSavingFirstCycle(false);
    }
  };

  const handleLogoChange = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (file.size > MAX_LOGO_SIZE_BYTES) {
      setLogoError(
        `Dit bestand is ${(file.size / 1024 / 1024).toFixed(1)} MB — logo's mogen maximaal 4 MB zijn. Tip: verklein de afbeelding (bv. via squoosh.app) en probeer opnieuw.`
      );
      e.target.value = "";
      return;
    }
    setLogoUploading(true);
    setLogoError(null);
    try {
      await uploadClubLogo(file);
      await refreshClub();
    } catch (err) {
      setLogoError(err.response?.data?.detail ?? err.message);
    } finally {
      setLogoUploading(false);
      e.target.value = "";
    }
  };

  const toggleWeekday = (value) => {
    setTrainingWeekdays((days) =>
      days.includes(value) ? days.filter((d) => d !== value) : [...days, value].sort()
    );
  };

  const handleSaveWeekdays = async (e) => {
    e.preventDefault();
    setSavingWeekdays(true);
    setWeekdaysError(null);
    setWeekdaysSaved(false);
    try {
      await updateMyClub({ training_weekdays: trainingWeekdays });
      await refreshClub();
      setWeekdaysSaved(true);
    } catch (err) {
      setWeekdaysError(err.response?.data?.detail ?? err.message);
    } finally {
      setSavingWeekdays(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSaving(true);
    setError(null);
    setSaved(false);
    try {
      await updateMyClub({ name, primary_color: primaryColor, secondary_color: secondaryColor });
      await refreshClub();
      setSaved(true);
    } catch (err) {
      setError(err.response?.data?.detail ?? err.message);
    } finally {
      setSaving(false);
    }
  };

  const handleSaveActiveCycle = async (e) => {
    e.preventDefault();
    setSavingActiveCycle(true);
    setActiveCycleError(null);
    setActiveCycleSaved(false);
    try {
      const updated = await patchActiveCycle({
        name: activeCycleForm.name,
        target_peak_weekly_km: Number(activeCycleForm.target_peak_weekly_km),
      });
      setActiveCycle(updated);
      setActiveCycleSaved(true);
    } catch (err) {
      setActiveCycleError(err.response?.data?.detail ?? err.message);
    } finally {
      setSavingActiveCycle(false);
    }
  };

  const handleQueueNextCycle = async (e) => {
    e.preventDefault();
    setQueueing(true);
    setQueueError(null);
    setQueueConfirmation(null);
    try {
      const cycle = await queueNextCycle({
        length_weeks: Number(cycleLengthWeeks),
        name: cycleName || null,
      });
      // A repeat call while the active cycle is still running overwrites the
      // already-queued (not yet started) next cycle instead of erroring — so
      // this is always a confirmation, never an error state on retry.
      setQueueConfirmation(
        `Instelling bijgewerkt: '${cycle.name}' (${cycle.length_weeks}w) staat klaar vanaf ${cycle.start_date}.`
      );
      loadCycles();
    } catch (err) {
      setQueueError(err.response?.data?.detail ?? err.message);
    } finally {
      setQueueing(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto py-12 px-4 space-y-10">
      <div>
        <h1 className="text-3xl font-bold text-white tracking-tight mb-1">Instellingen</h1>
        <p className="text-sm text-gray-400">Maak het platform helemaal van jouw club.</p>
      </div>

      <section>
        <h2 className="text-lg font-semibold text-white mb-4">Whitelabel branding</h2>
        <form onSubmit={handleSubmit} className={`${cardClass} space-y-5`}>
          <label className={labelClass}>
            Clubnaam
            <input type="text" value={name} onChange={(e) => setName(e.target.value)} className={inputClass} />
          </label>

          <div className={labelClass}>
            Logo
            <div className="flex items-center gap-4 mt-1">
              <div className="h-16 w-16 rounded-xl bg-white flex items-center justify-center overflow-hidden shrink-0 border border-white/10">
                {club?.logo_url ? (
                  <img src={club.logo_url} alt="Clublogo" className="h-full w-full object-contain p-1.5" />
                ) : (
                  <span className="text-gray-400 text-xs">Geen logo</span>
                )}
              </div>
              <label className="btn-brand text-white px-4 py-2 rounded-lg font-medium text-sm cursor-pointer">
                {logoUploading ? "Bezig met uploaden…" : "Logo uploaden"}
                <input
                  type="file"
                  accept="image/png,image/jpeg,image/svg+xml,image/webp"
                  onChange={handleLogoChange}
                  disabled={logoUploading}
                  className="hidden"
                />
              </label>
            </div>
            <p className="text-xs text-gray-500 font-normal mt-1">
              PNG, JPEG, SVG of WebP, max 4 MB. Verschijnt automatisch als watermerk op elk scherm.
            </p>
            {logoError && <p className="text-red-400 text-sm font-normal">{logoError}</p>}
          </div>

          <div className="flex gap-4">
            <label className={`${labelClass} flex-1`}>
              Primaire kleur
              <input
                type="color"
                value={primaryColor ?? "#059669"}
                onChange={(e) => setPrimaryColor(e.target.value)}
                className="mt-1 h-11 w-full bg-gray-950 border border-white/10 rounded-lg cursor-pointer"
              />
            </label>
            <label className={`${labelClass} flex-1`}>
              Secundaire kleur
              <input
                type="color"
                value={secondaryColor ?? "#111827"}
                onChange={(e) => setSecondaryColor(e.target.value)}
                className="mt-1 h-11 w-full bg-gray-950 border border-white/10 rounded-lg cursor-pointer"
              />
            </label>
          </div>

          {error && <p className="text-red-400 text-sm">{error}</p>}
          {saved && <p className="text-emerald-400 text-sm">Opgeslagen.</p>}

          <button type="submit" disabled={saving} className={primaryButtonClass}>
            {saving ? "Bezig…" : "Opslaan"}
          </button>
        </form>
      </section>

      <section>
        <h2 className="text-lg font-semibold text-white mb-1">Trainingsdagen</h2>
        <p className="text-sm text-gray-400 mb-4">
          Op welke dagen traint de ploeg standaard? Dit bepaalt op welke dagen spelers gevraagd
          worden om RPE en wellness in te vullen (samen met wedstrijddagen — die worden altijd
          automatisch herkend).
        </p>
        <form onSubmit={handleSaveWeekdays} className={`${cardClass} space-y-5`}>
          <div className="flex flex-wrap gap-2">
            {WEEKDAY_LABELS.map(({ value, label }) => (
              <button
                key={value}
                type="button"
                onClick={() => toggleWeekday(value)}
                className={`px-4 py-2 rounded-lg text-sm font-medium border transition-colors ${
                  trainingWeekdays.includes(value)
                    ? "nav-active-brand border-transparent"
                    : "border-white/10 text-gray-400 hover:bg-white/5"
                }`}
              >
                {label}
              </button>
            ))}
          </div>

          {weekdaysError && <p className="text-red-400 text-sm">{weekdaysError}</p>}
          {weekdaysSaved && <p className="text-emerald-400 text-sm">Opgeslagen.</p>}

          <button type="submit" disabled={savingWeekdays} className={primaryButtonClass}>
            {savingWeekdays ? "Bezig…" : "Opslaan"}
          </button>
        </form>
      </section>

      {cyclesLoading && (
        <section>
          <p className="text-gray-500 text-sm">Cyclusgegevens laden…</p>
        </section>
      )}

      {!cyclesLoading && !hasAnyCycle && (
        <section>
          <h2 className="text-lg font-semibold text-white mb-1">Seizoen starten</h2>
          <p className="text-sm text-gray-400 mb-4">
            Kies enkel een startdatum en de lengte van je eerste cyclus. Geen doelwedstrijddatum
            nodig — die wordt automatisch bepaald zodra je wedstrijden ingeeft in de kalender.
          </p>
          <form onSubmit={handleStartSeason} className={`${cardClass} space-y-5`}>
            <label className={labelClass}>
              Seizoensnaam (optioneel)
              <input
                type="text"
                value={seasonName}
                onChange={(e) => setSeasonName(e.target.value)}
                placeholder={`bv. Seizoen ${new Date().getFullYear()}-${new Date().getFullYear() + 1}`}
                className={inputClass}
              />
            </label>
            <label className={labelClass}>
              Startdatum eerste cyclus
              <input
                type="date"
                required
                value={seasonStartDate}
                onChange={(e) => setSeasonStartDate(e.target.value)}
                className={inputClass}
              />
            </label>
            <label className={labelClass}>
              Lengte
              <select
                value={seasonLengthWeeks}
                onChange={(e) => setSeasonLengthWeeks(e.target.value)}
                className={inputClass}
              >
                <option value={4}>4 weken</option>
                <option value={6}>6 weken</option>
                <option value={8}>8 weken</option>
              </select>
            </label>

            {startSeasonError && <p className="text-red-400 text-sm">{startSeasonError}</p>}

            <button type="submit" disabled={startingSeason} className={primaryButtonClass}>
              {startingSeason ? "Bezig…" : "Seizoen starten"}
            </button>
          </form>
        </section>
      )}

      {!cyclesLoading && hasAnyCycle && (
        <section>
          <h2 className="text-lg font-semibold text-white mb-1">Actieve cyclus</h2>
          <p className="text-sm text-gray-400 mb-4">
            De lopende trainingscyclus kan op elk moment aangepast worden — lengte en startdatum
            liggen vast omdat de weken er al op afgestemd zijn, maar naam en piekvolume zijn
            altijd wijzigbaar. De doelwedstrijd wordt automatisch bepaald zodra er wedstrijden in
            de kalender staan.
          </p>

          {!activeCycle && (
            <div className={`${cardClass} text-sm text-gray-400`}>
              Geen actieve cyclus op dit moment — de klaargezette cyclus hieronder start nog.
            </div>
          )}

          {activeCycle && (
            <form onSubmit={handleSaveActiveCycle} className={`${cardClass} space-y-5`}>
              <label className={labelClass}>
                Naam
                <input
                  type="text"
                  value={activeCycleForm.name}
                  onChange={(e) => setActiveCycleForm((f) => ({ ...f, name: e.target.value }))}
                  className={inputClass}
                />
              </label>
              <label className={labelClass}>
                Piekvolume (km, 100%-week)
                <input
                  type="number"
                  step="0.5"
                  min="0"
                  value={activeCycleForm.target_peak_weekly_km}
                  onChange={(e) =>
                    setActiveCycleForm((f) => ({ ...f, target_peak_weekly_km: e.target.value }))
                  }
                  className={inputClass}
                />
              </label>
              <p className="text-xs text-gray-500">
                {activeCycle.length_weeks} weken, gestart op {activeCycle.start_date}
                {" · "}
                Doelwedstrijd:{" "}
                {activeCycle.target_match_date
                  ? activeCycle.target_match_date
                  : "nog niet bepaald (automatisch zodra er een wedstrijd in de kalender staat)"}
              </p>

              {activeCycleError && <p className="text-red-400 text-sm">{activeCycleError}</p>}
              {activeCycleSaved && <p className="text-emerald-400 text-sm">Opgeslagen.</p>}

              <button type="submit" disabled={savingActiveCycle} className={primaryButtonClass}>
                {savingActiveCycle ? "Bezig…" : "Opslaan"}
              </button>
            </form>
          )}

          {canEditFirstCycle && (
            <details className="mt-3">
              <summary className="text-sm text-gray-400 cursor-pointer hover:text-gray-300">
                Vergissing bij de start? Cyclus aanpassen
              </summary>
              <form onSubmit={handleSaveFirstCycle} className={`${cardClass} space-y-5 mt-3`}>
                <p className="text-xs text-gray-500">
                  Enkel mogelijk zolang er nog geen volgende cyclus is gestart.
                </p>
                <label className={labelClass}>
                  Startdatum
                  <input
                    type="date"
                    value={firstCycleForm.start_date}
                    onChange={(e) => setFirstCycleForm((f) => ({ ...f, start_date: e.target.value }))}
                    className={inputClass}
                  />
                </label>
                <label className={labelClass}>
                  Lengte
                  <select
                    value={firstCycleForm.length_weeks}
                    onChange={(e) => setFirstCycleForm((f) => ({ ...f, length_weeks: e.target.value }))}
                    className={inputClass}
                  >
                    <option value={4}>4 weken</option>
                    <option value={6}>6 weken</option>
                    <option value={8}>8 weken</option>
                  </select>
                </label>

                {firstCycleError && <p className="text-red-400 text-sm">{firstCycleError}</p>}
                {firstCycleSaved && <p className="text-emerald-400 text-sm">Opgeslagen.</p>}

                <button type="submit" disabled={savingFirstCycle} className={primaryButtonClass}>
                  {savingFirstCycle ? "Bezig…" : "Cyclus corrigeren"}
                </button>
              </form>
            </details>
          )}
        </section>
      )}

      {!cyclesLoading && hasAnyCycle && (
        <section>
          <h2 className="text-lg font-semibold text-white mb-1">
            {queuedCycleId ? "Klaargezette volgende cyclus" : "Cyclusplanning"}
          </h2>
          <p className="text-sm text-gray-400 mb-4">
            Stel de eerstvolgende trainingscyclus in. De actieve, lopende cyclus wordt hier nooit
            door aangeraakt — je kan van gedachte veranderen over de klaargezette volgende cyclus
            zolang die nog niet gestart is. Geen datum nodig — die sluit automatisch aan op het
            einde van de huidige cyclus.
          </p>

          <form onSubmit={handleQueueNextCycle} className={`${cardClass} space-y-5`}>
            <label className={labelClass}>
              Naam (optioneel)
              <input
                type="text"
                value={cycleName}
                onChange={(e) => setCycleName(e.target.value)}
                placeholder="bv. Competitieblok 2"
                className={inputClass}
              />
            </label>
            <label className={labelClass}>
              Lengte
              <select
                value={cycleLengthWeeks}
                onChange={(e) => setCycleLengthWeeks(e.target.value)}
                className={inputClass}
              >
                <option value={4}>4 weken</option>
                <option value={6}>6 weken</option>
                <option value={8}>8 weken</option>
              </select>
            </label>

            {queueError && <p className="text-red-400 text-sm">{queueError}</p>}
            {queueConfirmation && <p className="text-emerald-400 text-sm">{queueConfirmation}</p>}

            <button type="submit" disabled={queueing} className={primaryButtonClass}>
              {queueing ? "Bezig…" : queuedCycleId ? "Wijzigingen opslaan" : "Volgende cyclus instellen"}
            </button>
          </form>
        </section>
      )}
    </div>
  );
}
