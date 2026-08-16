import { useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import {
  createPlayer,
  downloadImportTemplate,
  getMasTestProtocols,
  getRpeWellnessShouldPrompt,
  getSquadOverview,
  importPlayers,
  recordMasTest,
  recordRpeWellness,
} from "../api/client";
import { useAuth } from "../context/AuthContext.jsx";

const EXTERNAL_LOAD_LABELS = {
  none: "Geen",
  light: "Licht (school/bureauwerk)",
  physical: "Fysiek zwaar (bv. bouw, horeca-shift)",
};

const emptyRpeForm = () => ({
  entry_date: new Date().toISOString().slice(0, 10),
  rpe_score: "",
  session_duration_min: "",
  sleep_quality: "3",
  fatigue_level: "3",
  muscle_soreness: "3",
  stress_level: "3",
  mood: "3",
  injury_flag: false,
  injury_note: "",
  external_load_category: "none",
  extra_activity_today: false,
  extra_activity_note: "",
});

const POSITION_LABELS = {
  GK: "Doelman",
  CB: "Centrale verdediger",
  FB: "Flankverdediger",
  DM: "Verdedigende middenvelder",
  CM: "Centrale middenvelder",
  AM: "Aanvallende middenvelder",
  WNG: "Vleugelspeler",
  ST: "Spits",
};
const POSITION_ORDER = ["GK", "CB", "FB", "DM", "CM", "AM", "WNG", "ST"];

// Mirrors app/routers/team_readiness.py's ATTENTION_FLAG_TYPES — the exact
// flag set the Next Training "Belast/overbelast/geblesseerd" tile counts,
// so its ?filter=flagged link shows exactly that set here (deliberately
// excludes "underload", a Squad Overview 'reductie' signal, not a
// load-management concern for that tile).
const ATTENTION_FLAG_TYPES = new Set(["overload", "poor_recovery", "acwr_trending_up", "injured"]);

const STATUS_META = {
  fit: { label: "Fit", dot: "bg-emerald-500", badge: "bg-emerald-500/15 text-emerald-400", ring: "ring-emerald-500/30" },
  reductie: { label: "Reductie", dot: "bg-amber-500", badge: "bg-amber-500/15 text-amber-400", ring: "ring-amber-500/30" },
  overbelast: { label: "Overbelast", dot: "bg-red-500", badge: "bg-red-500/15 text-red-400", ring: "ring-red-500/30" },
  geen_data: { label: "Geen data", dot: "bg-gray-500", badge: "bg-gray-500/15 text-gray-400", ring: "ring-white/10" },
};

function initials(firstName, lastName) {
  return `${firstName?.[0] ?? ""}${lastName?.[0] ?? ""}`.toUpperCase();
}

export default function Players() {
  const { club } = useAuth();
  const rpeModuleActive = Boolean(club?.enabled_modules?.includes("rpe_wellness"));
  const [searchParams, setSearchParams] = useSearchParams();
  const flaggedOnly = searchParams.get("filter") === "flagged";

  const [squad, setSquad] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [positionFilter, setPositionFilter] = useState("ALL");

  const [protocols, setProtocols] = useState([]);
  const [testPlayerId, setTestPlayerId] = useState(null);
  const [testProtocolKey, setTestProtocolKey] = useState("");
  const [testRawResult, setTestRawResult] = useState("");
  const [testDate, setTestDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [testSubmitting, setTestSubmitting] = useState(false);
  const [testError, setTestError] = useState(null);
  const [testConfirmation, setTestConfirmation] = useState(null);

  const [showAddForm, setShowAddForm] = useState(false);
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [jerseyNumber, setJerseyNumber] = useState("");
  const [email, setEmail] = useState("");
  const [phoneNumber, setPhoneNumber] = useState("");
  const [addSubmitting, setAddSubmitting] = useState(false);
  const [addError, setAddError] = useState(null);

  const [importResult, setImportResult] = useState(null);
  const [importError, setImportError] = useState(null);
  const [importing, setImporting] = useState(false);
  const fileInputRef = useRef(null);

  const [shouldPrompt, setShouldPrompt] = useState(null);
  const [rpePlayerId, setRpePlayerId] = useState(null);
  const [rpeForm, setRpeForm] = useState(emptyRpeForm());
  const [rpeSubmitting, setRpeSubmitting] = useState(false);
  const [rpeError, setRpeError] = useState(null);
  const [rpeConfirmation, setRpeConfirmation] = useState(null);

  const refresh = async () => {
    setLoading(true);
    try {
      setSquad(await getSquadOverview());
      setError(null);
    } catch (err) {
      setError(err.response?.data?.detail ?? err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refresh();
    getMasTestProtocols()
      .then((result) => {
        setProtocols(result);
        if (result.length > 0) setTestProtocolKey(result[0].key);
      })
      .catch(() => {});
    if (rpeModuleActive) {
      getRpeWellnessShouldPrompt()
        .then(setShouldPrompt)
        .catch(() => {});
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rpeModuleActive]);

  const statusCounts = useMemo(() => {
    const counts = { fit: 0, reductie: 0, overbelast: 0, geen_data: 0 };
    for (const p of squad) counts[p.status] += 1;
    return counts;
  }, [squad]);

  const availablePositions = useMemo(() => {
    const present = new Set(squad.map((p) => p.position).filter(Boolean));
    return POSITION_ORDER.filter((pos) => present.has(pos));
  }, [squad]);

  const filteredSquad = useMemo(() => {
    let result = positionFilter === "ALL" ? squad : squad.filter((p) => p.position === positionFilter);
    if (flaggedOnly) {
      result = result.filter((p) => (p.flag_types ?? []).some((t) => ATTENTION_FLAG_TYPES.has(t)));
    }
    return result;
  }, [squad, positionFilter, flaggedOnly]);

  const clearFlaggedFilter = () => {
    const next = new URLSearchParams(searchParams);
    next.delete("filter");
    setSearchParams(next);
  };

  const openTestForm = (playerId) => {
    setTestPlayerId(playerId);
    setTestRawResult("");
    setTestDate(new Date().toISOString().slice(0, 10));
    setTestError(null);
    setTestConfirmation(null);
  };

  const handleRecordMasTest = async (e) => {
    e.preventDefault();
    setTestSubmitting(true);
    setTestError(null);
    try {
      const result = await recordMasTest({
        player_id: testPlayerId,
        protocol_key: testProtocolKey,
        raw_result_kmh: Number(testRawResult),
        test_date: testDate,
      });
      setTestConfirmation(
        `MAS-score ${result.mas_kmh} km/u opgeslagen. Kalender bijgewerkt (${result.calendar_events_synced} testmoment(en)).`
      );
    } catch (err) {
      setTestError(err.response?.data?.detail ?? err.message);
    } finally {
      setTestSubmitting(false);
    }
  };

  const openRpeForm = (playerId) => {
    setRpePlayerId(playerId);
    setRpeForm(emptyRpeForm());
    setRpeError(null);
    setRpeConfirmation(null);
  };

  const handleRecordRpeWellness = async (e) => {
    e.preventDefault();
    setRpeSubmitting(true);
    setRpeError(null);
    try {
      await recordRpeWellness({
        player_id: rpePlayerId,
        entry_date: rpeForm.entry_date,
        session_type: "training",
        rpe_score: rpeForm.rpe_score === "" ? null : Number(rpeForm.rpe_score),
        session_duration_min: rpeForm.session_duration_min === "" ? null : Number(rpeForm.session_duration_min),
        sleep_quality: Number(rpeForm.sleep_quality),
        fatigue_level: Number(rpeForm.fatigue_level),
        muscle_soreness: Number(rpeForm.muscle_soreness),
        stress_level: Number(rpeForm.stress_level),
        mood: Number(rpeForm.mood),
        injury_flag: rpeForm.injury_flag,
        injury_note: rpeForm.injury_flag && rpeForm.injury_note ? rpeForm.injury_note : null,
        external_load_category: rpeForm.external_load_category,
        extra_activity_today: rpeForm.extra_activity_today,
        extra_activity_note:
          rpeForm.extra_activity_today && rpeForm.extra_activity_note ? rpeForm.extra_activity_note : null,
      });
      setRpeConfirmation("Opgeslagen.");
      await refresh();
    } catch (err) {
      setRpeError(err.response?.data?.detail ?? err.message);
    } finally {
      setRpeSubmitting(false);
    }
  };

  const handleAddPlayer = async (e) => {
    e.preventDefault();
    setAddSubmitting(true);
    setAddError(null);
    try {
      await createPlayer({
        first_name: firstName,
        last_name: lastName,
        jersey_number: jerseyNumber === "" ? null : Number(jerseyNumber),
        email: email || null,
        phone_number: phoneNumber || null,
      });
      setFirstName("");
      setLastName("");
      setJerseyNumber("");
      setEmail("");
      setPhoneNumber("");
      setShowAddForm(false);
      await refresh();
    } catch (err) {
      setAddError(err.response?.data?.detail ?? err.message);
    } finally {
      setAddSubmitting(false);
    }
  };

  const handleDownloadTemplate = async () => {
    const blob = await downloadImportTemplate();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "spelers_import_sjabloon.xlsx";
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(url);
  };

  const handleImportFile = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setImporting(true);
    setImportError(null);
    setImportResult(null);
    try {
      const result = await importPlayers(file);
      setImportResult(result);
      await refresh();
    } catch (err) {
      setImportError(err.response?.data?.detail ?? err.message);
    } finally {
      setImporting(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  return (
    <div className="max-w-6xl mx-auto py-12 px-4">
      <div className="flex flex-wrap items-center justify-between gap-3 mb-6">
        <div>
          <h1 className="text-3xl font-bold text-white tracking-tight mb-1">Squad Overview</h1>
          <p className="text-sm text-gray-400">
            Statusoverzicht per speler op basis van afgelegde kilometers uit de voorbije 28 dagen
            {rpeModuleActive ? ", aangevuld met RPE en wellness-gegevens." : "."}
          </p>
        </div>
        <button
          onClick={() => setShowAddForm((v) => !v)}
          className="btn-brand text-white px-5 py-2.5 rounded-lg text-sm font-medium shrink-0"
        >
          {showAddForm ? "Annuleren" : "+ Speler toevoegen"}
        </button>
      </div>

      {flaggedOnly && (
        <div className="bg-amber-500/10 border border-amber-500/30 text-amber-300 rounded-2xl px-5 py-3.5 mb-6 text-sm flex items-center justify-between gap-3 flex-wrap">
          <span>
            Gefilterd op belast / overbelast / geblesseerd spelers (vanuit de Next Training-tegel).
          </span>
          <button onClick={clearFlaggedFilter} className="underline hover:opacity-80 shrink-0">
            Filter wissen
          </button>
        </div>
      )}

      {rpeModuleActive && shouldPrompt?.is_session_day && (
        <div className="bg-amber-500/10 border border-amber-500/30 text-amber-300 rounded-2xl px-5 py-3.5 mb-6 text-sm">
          Vandaag is een {shouldPrompt.reason === "match" ? "wedstrijddag" : "trainingsdag"} — vergeet niet RPE
          en wellness in te vullen bij de spelers die trainen of spelen.
        </div>
      )}

      {showAddForm && (
        <form onSubmit={handleAddPlayer} className="bg-gray-900/60 border border-white/10 rounded-2xl p-6 mb-6 space-y-4 shadow-xl shadow-black/20">
          <div className="grid grid-cols-2 gap-3">
            <input
              required
              placeholder="Voornaam"
              value={firstName}
              onChange={(e) => setFirstName(e.target.value)}
              className="bg-gray-950 border border-white/10 text-white rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 ring-brand"
            />
            <input
              required
              placeholder="Naam"
              value={lastName}
              onChange={(e) => setLastName(e.target.value)}
              className="bg-gray-950 border border-white/10 text-white rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 ring-brand"
            />
            <input
              type="number"
              min="0"
              max="99"
              placeholder="Rugnummer"
              value={jerseyNumber}
              onChange={(e) => setJerseyNumber(e.target.value)}
              className="bg-gray-950 border border-white/10 text-white rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 ring-brand"
            />
            <input
              type="email"
              placeholder="E-mailadres"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="bg-gray-950 border border-white/10 text-white rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 ring-brand"
            />
            <input
              placeholder="Telefoonnummer"
              value={phoneNumber}
              onChange={(e) => setPhoneNumber(e.target.value)}
              className="bg-gray-950 border border-white/10 text-white rounded-lg px-3 py-2.5 text-sm col-span-2 focus:outline-none focus:ring-2 ring-brand"
            />
          </div>
          {addError && <p className="text-red-400 text-sm">{addError}</p>}
          <button
            type="submit"
            disabled={addSubmitting}
            className="btn-brand text-white px-5 py-2.5 rounded-lg text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {addSubmitting ? "Bezig…" : "Toevoegen"}
          </button>
        </form>
      )}

      <div className="bg-gray-900/60 border border-white/10 rounded-2xl p-6 mb-6 shadow-xl shadow-black/20">
        <h2 className="text-white font-semibold mb-1">Bulk import</h2>
        <p className="text-sm text-gray-400 mb-3">
          Download het sjabloon, vul de gegevens in (rugnummer, naam, voornaam, e-mailadres,
          telefoonnummer) en upload het opnieuw om alle spelers in één keer in te laden.
        </p>
        <div className="flex flex-wrap items-center gap-3">
          <button
            onClick={handleDownloadTemplate}
            className="bg-white/5 hover:bg-white/10 border border-white/10 text-white px-4 py-2.5 rounded-lg text-sm font-medium transition-colors"
          >
            Download sjabloon (.xlsx)
          </button>
          <label className="btn-brand text-white px-5 py-2.5 rounded-lg text-sm font-medium cursor-pointer">
            {importing ? "Bezig met importeren…" : "Upload ingevuld sjabloon"}
            <input
              ref={fileInputRef}
              type="file"
              accept=".xlsx,.xlsm"
              onChange={handleImportFile}
              disabled={importing}
              className="hidden"
            />
          </label>
        </div>
        {importError && <p className="text-red-400 text-sm mt-3">{importError}</p>}
        {importResult && (
          <div className="text-sm mt-3 text-gray-300">
            <p>
              {importResult.created} speler(s) aangemaakt, {importResult.skipped} rij(en) overgeslagen.
            </p>
            {importResult.errors.length > 0 && (
              <ul className="list-disc list-inside text-red-400 mt-1">
                {importResult.errors.map((err) => (
                  <li key={err.row}>
                    Rij {err.row}: {err.message}
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </div>

      {loading && <p className="text-gray-400">Laden…</p>}
      {error && <p className="text-red-400">{error}</p>}

      {!loading && !error && squad.length === 0 && (
        <div className="bg-gray-900/60 border border-white/10 rounded-2xl p-8 text-center text-gray-500 shadow-xl shadow-black/20">
          Nog geen spelers. Voeg er een toe of importeer het sjabloon.
        </div>
      )}

      {!loading && !error && squad.length > 0 && (
        <>
          <div className="flex flex-wrap items-center gap-2 mb-4">
            {["fit", "reductie", "overbelast"].map((status) => (
              <span
                key={status}
                className={`inline-flex items-center gap-1.5 ${STATUS_META[status].badge} px-3 py-1.5 rounded-full text-xs font-semibold`}
              >
                <span className={`h-1.5 w-1.5 rounded-full ${STATUS_META[status].dot}`} />
                {statusCounts[status]} {STATUS_META[status].label}
              </span>
            ))}
          </div>

          <div className="flex flex-wrap items-center gap-2 mb-6">
            <span className="text-[10px] uppercase tracking-wider text-gray-500 font-medium mr-1">Positie</span>
            <button
              onClick={() => setPositionFilter("ALL")}
              className={`px-3 py-1.5 rounded-full text-xs font-semibold border transition-colors ${
                positionFilter === "ALL"
                  ? "nav-active-brand border-transparent"
                  : "border-white/10 text-gray-400 hover:bg-white/5"
              }`}
            >
              Alle
            </button>
            {availablePositions.map((pos) => (
              <button
                key={pos}
                onClick={() => setPositionFilter(pos)}
                title={POSITION_LABELS[pos]}
                className={`px-3 py-1.5 rounded-full text-xs font-semibold border transition-colors ${
                  positionFilter === pos
                    ? "nav-active-brand border-transparent"
                    : "border-white/10 text-gray-400 hover:bg-white/5"
                }`}
              >
                {pos}
              </button>
            ))}
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {filteredSquad.map((p) => {
              const meta = STATUS_META[p.status];
              const isTestOpen = testPlayerId === p.id;
              const isRpeOpen = rpePlayerId === p.id;
              return (
                <div
                  key={p.id}
                  className={`bg-gray-900/60 border border-white/10 rounded-2xl p-4 shadow-xl shadow-black/20 ring-1 ${meta.ring}`}
                >
                  <div className="flex items-start justify-between gap-2 mb-3">
                    <div className="flex items-center gap-3 min-w-0">
                      <div className={`h-10 w-10 shrink-0 rounded-full flex items-center justify-center text-sm font-bold ${meta.badge}`}>
                        {initials(p.first_name, p.last_name)}
                      </div>
                      <div className="min-w-0">
                        <p className="text-white font-semibold truncate">
                          {p.first_name} {p.last_name}
                        </p>
                        <p className="text-xs text-gray-500 truncate" title={p.position ? POSITION_LABELS[p.position] : undefined}>
                          {p.jersey_number != null ? `#${p.jersey_number}` : "—"}
                          {p.position ? ` · ${p.position}` : ""}
                        </p>
                      </div>
                    </div>
                    <span className={`shrink-0 px-2.5 py-1 rounded-full text-[11px] font-semibold ${meta.badge}`}>
                      {meta.label}
                    </span>
                  </div>

                  <div className="text-xs text-gray-400 mb-3">
                    {p.status === "geen_data" ? (
                      "Nog geen belastingsgegevens."
                    ) : (
                      <>
                        {p.acwr != null && <span>Km-ACWR {p.acwr}</span>}
                        {rpeModuleActive && p.acwr != null && (p.latest_rpe != null || p.latest_wellness != null) && (
                          <span> · </span>
                        )}
                        {rpeModuleActive && p.latest_rpe != null && <span>RPE {p.latest_rpe}</span>}
                        {rpeModuleActive && p.latest_rpe != null && p.latest_wellness != null && <span> · </span>}
                        {rpeModuleActive && p.latest_wellness != null && <span>Wellness {p.latest_wellness}/5</span>}
                      </>
                    )}
                    {p.flags.length > 0 && (
                      <ul className="mt-1.5 space-y-0.5">
                        {p.flags.map((detail, i) => (
                          <li key={i} className="text-[11px] text-gray-500">
                            {detail}
                            {rpeModuleActive && p.flag_sources?.[i] && (
                              <span className="text-gray-600"> ({p.flag_sources[i]})</span>
                            )}
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>

                  <div className="flex items-center gap-3">
                    <button
                      onClick={() => (isTestOpen ? setTestPlayerId(null) : openTestForm(p.id))}
                      className="text-brand hover:opacity-80 text-xs font-medium"
                    >
                      {isTestOpen ? "Sluiten" : "MAS-test invoeren"}
                    </button>
                    {rpeModuleActive && (
                      <button
                        onClick={() => (isRpeOpen ? setRpePlayerId(null) : openRpeForm(p.id))}
                        className="text-brand hover:opacity-80 text-xs font-medium"
                      >
                        {isRpeOpen ? "Sluiten" : "RPE & wellness invullen"}
                      </button>
                    )}
                  </div>

                  {rpeModuleActive && isRpeOpen && (
                    <form onSubmit={handleRecordRpeWellness} className="mt-3 pt-3 border-t border-white/10 space-y-2.5 text-sm">
                      <div className="grid grid-cols-2 gap-2.5">
                        <label className="flex flex-col text-gray-300 text-xs gap-1">
                          Datum
                          <input
                            type="date"
                            required
                            value={rpeForm.entry_date}
                            onChange={(e) => setRpeForm((f) => ({ ...f, entry_date: e.target.value }))}
                            className="bg-gray-950 border border-white/10 text-white rounded-lg px-2.5 py-2 text-xs focus:outline-none focus:ring-2 ring-brand"
                          />
                        </label>
                        <label className="flex flex-col text-gray-300 text-xs gap-1">
                          RPE (1-10)
                          <input
                            type="number"
                            min="1"
                            max="10"
                            value={rpeForm.rpe_score}
                            onChange={(e) => setRpeForm((f) => ({ ...f, rpe_score: e.target.value }))}
                            className="bg-gray-950 border border-white/10 text-white rounded-lg px-2.5 py-2 text-xs focus:outline-none focus:ring-2 ring-brand"
                          />
                        </label>
                        <label className="flex flex-col text-gray-300 text-xs gap-1 col-span-2">
                          Sessieduur (min)
                          <input
                            type="number"
                            min="1"
                            value={rpeForm.session_duration_min}
                            onChange={(e) => setRpeForm((f) => ({ ...f, session_duration_min: e.target.value }))}
                            className="bg-gray-950 border border-white/10 text-white rounded-lg px-2.5 py-2 text-xs focus:outline-none focus:ring-2 ring-brand"
                          />
                        </label>
                      </div>

                      <div className="grid grid-cols-5 gap-1.5">
                        {[
                          { key: "sleep_quality", label: "Slaap", title: "1 = zeer slecht … 5 = zeer goed" },
                          { key: "fatigue_level", label: "Vermoeid", title: "1 = heel fris … 5 = heel vermoeid" },
                          { key: "muscle_soreness", label: "Spierpijn", title: "1 = geen … 5 = veel" },
                          { key: "stress_level", label: "Stress", title: "1 = ontspannen … 5 = gestrest" },
                          { key: "mood", label: "Humeur", title: "1 = slecht … 5 = heel goed" },
                        ].map(({ key, label, title }) => (
                          <label key={key} className="flex flex-col text-gray-300 text-[10px] gap-1" title={title}>
                            {label}
                            <select
                              value={rpeForm[key]}
                              onChange={(e) => setRpeForm((f) => ({ ...f, [key]: e.target.value }))}
                              className="bg-gray-950 border border-white/10 text-white rounded-lg px-1 py-1.5 text-xs focus:outline-none focus:ring-2 ring-brand"
                            >
                              {[1, 2, 3, 4, 5].map((n) => (
                                <option key={n} value={n}>
                                  {n}
                                </option>
                              ))}
                            </select>
                          </label>
                        ))}
                      </div>

                      <label className="flex flex-col text-gray-300 text-xs gap-1">
                        Externe belasting vandaag (school/werk)
                        <select
                          value={rpeForm.external_load_category}
                          onChange={(e) => setRpeForm((f) => ({ ...f, external_load_category: e.target.value }))}
                          className="bg-gray-950 border border-white/10 text-white rounded-lg px-2.5 py-2 text-xs focus:outline-none focus:ring-2 ring-brand"
                        >
                          {Object.entries(EXTERNAL_LOAD_LABELS).map(([value, label]) => (
                            <option key={value} value={value}>
                              {label}
                            </option>
                          ))}
                        </select>
                      </label>

                      <label className="flex items-center gap-2 text-gray-300 text-xs">
                        <input
                          type="checkbox"
                          checked={rpeForm.extra_activity_today}
                          onChange={(e) => setRpeForm((f) => ({ ...f, extra_activity_today: e.target.checked }))}
                          className="rounded border-white/20 bg-gray-950"
                        />
                        Nog een andere sportieve inspanning gehad vandaag?
                      </label>
                      {rpeForm.extra_activity_today && (
                        <input
                          type="text"
                          placeholder="Korte omschrijving (optioneel)"
                          value={rpeForm.extra_activity_note}
                          onChange={(e) => setRpeForm((f) => ({ ...f, extra_activity_note: e.target.value }))}
                          className="w-full bg-gray-950 border border-white/10 text-white rounded-lg px-2.5 py-2 text-xs focus:outline-none focus:ring-2 ring-brand"
                        />
                      )}

                      <label className="flex items-center gap-2 text-gray-300 text-xs">
                        <input
                          type="checkbox"
                          checked={rpeForm.injury_flag}
                          onChange={(e) => setRpeForm((f) => ({ ...f, injury_flag: e.target.checked }))}
                          className="rounded border-white/20 bg-gray-950"
                        />
                        Actief blessure- of pijnsignaal
                      </label>
                      {rpeForm.injury_flag && (
                        <input
                          type="text"
                          placeholder="Korte notitie (optioneel)"
                          value={rpeForm.injury_note}
                          onChange={(e) => setRpeForm((f) => ({ ...f, injury_note: e.target.value }))}
                          className="w-full bg-gray-950 border border-white/10 text-white rounded-lg px-2.5 py-2 text-xs focus:outline-none focus:ring-2 ring-brand"
                        />
                      )}

                      <button
                        type="submit"
                        disabled={rpeSubmitting}
                        className="btn-brand text-white px-4 py-2 rounded-lg text-sm font-medium w-full disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        {rpeSubmitting ? "Bezig…" : "Opslaan"}
                      </button>
                      {rpeError && <p className="text-red-400 text-xs">{rpeError}</p>}
                      {rpeConfirmation && <p className="text-emerald-400 text-xs">{rpeConfirmation}</p>}
                    </form>
                  )}

                  {isTestOpen && (
                    <form onSubmit={handleRecordMasTest} className="mt-3 pt-3 border-t border-white/10 space-y-2.5 text-sm">
                      <label className="flex flex-col text-gray-300 text-xs gap-1">
                        Protocol
                        <select
                          value={testProtocolKey}
                          onChange={(e) => setTestProtocolKey(e.target.value)}
                          className="bg-gray-950 border border-white/10 text-white rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 ring-brand"
                        >
                          {protocols.map((protocol) => (
                            <option key={protocol.key} value={protocol.key}>
                              {protocol.name}
                            </option>
                          ))}
                        </select>
                      </label>
                      <label className="flex flex-col text-gray-300 text-xs gap-1">
                        Resultaat (km/u)
                        <input
                          type="number"
                          step="0.1"
                          min="0.1"
                          required
                          value={testRawResult}
                          onChange={(e) => setTestRawResult(e.target.value)}
                          className="bg-gray-950 border border-white/10 text-white rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 ring-brand"
                        />
                      </label>
                      <label className="flex flex-col text-gray-300 text-xs gap-1">
                        Testdatum
                        <input
                          type="date"
                          required
                          value={testDate}
                          onChange={(e) => setTestDate(e.target.value)}
                          className="bg-gray-950 border border-white/10 text-white rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 ring-brand"
                        />
                      </label>
                      <button
                        type="submit"
                        disabled={testSubmitting}
                        className="btn-brand text-white px-4 py-2 rounded-lg text-sm font-medium w-full disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        {testSubmitting ? "Bezig…" : "Opslaan"}
                      </button>
                      {testError && <p className="text-red-400 text-xs">{testError}</p>}
                      {testConfirmation && <p className="text-emerald-400 text-xs">{testConfirmation}</p>}
                    </form>
                  )}
                </div>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}
