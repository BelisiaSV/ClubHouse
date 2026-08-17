import { useEffect, useState } from "react";
import { getRpeWellnessShouldPrompt, listPlayers, recordRpeWellness } from "../api/client";
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

function initials(firstName, lastName) {
  return `${firstName?.[0] ?? ""}${lastName?.[0] ?? ""}`.toUpperCase();
}

export default function Rpe() {
  const { club } = useAuth();
  const rpeModuleActive = Boolean(club?.enabled_modules?.includes("rpe_wellness"));

  const [players, setPlayers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [shouldPrompt, setShouldPrompt] = useState(null);

  const [rpePlayerId, setRpePlayerId] = useState(null);
  const [rpeForm, setRpeForm] = useState(emptyRpeForm());
  const [rpeSubmitting, setRpeSubmitting] = useState(false);
  const [rpeError, setRpeError] = useState(null);
  const [rpeConfirmation, setRpeConfirmation] = useState(null);

  useEffect(() => {
    if (!rpeModuleActive) {
      setLoading(false);
      return;
    }
    setLoading(true);
    listPlayers()
      .then(setPlayers)
      .catch((err) => setError(err.response?.data?.detail ?? err.message))
      .finally(() => setLoading(false));
    getRpeWellnessShouldPrompt()
      .then(setShouldPrompt)
      .catch(() => {});
  }, [rpeModuleActive]);

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
    } catch (err) {
      setRpeError(err.response?.data?.detail ?? err.message);
    } finally {
      setRpeSubmitting(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto py-12 px-4 space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-white tracking-tight mb-1">RPE &amp; Wellness</h1>
        <p className="text-sm text-gray-400">
          Dagelijkse belastings- en herstelinvoer per speler — voedt de km-ACWR-status op Squad Overview
          aan met een subjectieve laag.
        </p>
      </div>

      {!rpeModuleActive && (
        <div className="bg-gray-900/60 border border-white/10 rounded-2xl p-8 text-center text-gray-500 shadow-xl shadow-black/20">
          De RPE-module is niet actief voor deze club. Vraag een platformbeheerder om deze te activeren
          via het adminpaneel.
        </div>
      )}

      {rpeModuleActive && shouldPrompt?.is_session_day && (
        <div className="bg-amber-500/10 border border-amber-500/30 text-amber-300 rounded-2xl px-5 py-3.5 text-sm">
          Vandaag is een {shouldPrompt.reason === "match" ? "wedstrijddag" : "trainingsdag"} — vergeet niet RPE
          en wellness in te vullen bij de spelers die trainen of spelen.
        </div>
      )}

      {rpeModuleActive && loading && <p className="text-gray-400">Laden…</p>}
      {rpeModuleActive && error && <p className="text-red-400">{error}</p>}

      {rpeModuleActive && !loading && !error && players.length === 0 && (
        <div className="bg-gray-900/60 border border-white/10 rounded-2xl p-8 text-center text-gray-500 shadow-xl shadow-black/20">
          Nog geen spelers. Voeg er eerst een toe via Squad.
        </div>
      )}

      {rpeModuleActive && !loading && !error && players.length > 0 && (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {players.map((p) => {
            const isOpen = rpePlayerId === p.id;
            return (
              <div key={p.id} className="bg-gray-900/60 border border-white/10 rounded-2xl p-4 shadow-xl shadow-black/20">
                <div className="flex items-center justify-between gap-3">
                  <div className="flex items-center gap-3 min-w-0">
                    <div className="h-10 w-10 shrink-0 rounded-full flex items-center justify-center text-sm font-bold bg-white/5 text-gray-300">
                      {initials(p.first_name, p.last_name)}
                    </div>
                    <p className="text-white font-semibold truncate">
                      {p.first_name} {p.last_name}
                    </p>
                  </div>
                  <button
                    onClick={() => (isOpen ? setRpePlayerId(null) : openRpeForm(p.id))}
                    className="text-brand hover:opacity-80 text-xs font-medium shrink-0"
                  >
                    {isOpen ? "Sluiten" : "Invullen"}
                  </button>
                </div>

                {isOpen && (
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
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
