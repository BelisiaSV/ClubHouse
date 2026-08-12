import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { createMatch, getCalendarEvents, listMatches, listPlayers } from "../api/client";

export default function Matches() {
  const navigate = useNavigate();
  const [matches, setMatches] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [masTestEvents, setMasTestEvents] = useState([]);
  const [playersById, setPlayersById] = useState({});

  const [showForm, setShowForm] = useState(false);
  const [opponent, setOpponent] = useState("");
  const [matchDate, setMatchDate] = useState("");
  const [isHome, setIsHome] = useState(true);
  const [competition, setCompetition] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const refresh = async () => {
    setLoading(true);
    try {
      setMatches(await listMatches());
      setError(null);
    } catch (err) {
      setError(err.response?.data?.detail ?? err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refresh();
    getCalendarEvents("mas_test")
      .then(setMasTestEvents)
      .catch(() => {});
    listPlayers()
      .then((players) => setPlayersById(Object.fromEntries(players.map((p) => [p.id, p]))))
      .catch(() => {});
  }, []);

  const playerLabel = (playerId) => {
    const player = playersById[playerId];
    return player ? `${player.first_name} ${player.last_name}` : "onbekende speler";
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      await createMatch({
        opponent,
        match_date: new Date(matchDate).toISOString(),
        is_home: isHome,
        competition: competition || null,
      });
      setOpponent("");
      setMatchDate("");
      setIsHome(true);
      setCompetition("");
      setShowForm(false);
      await refresh();
    } catch (err) {
      setError(err.response?.data?.detail ?? err.message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto py-12 px-4">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-3xl font-bold text-white tracking-tight mb-1">Wedstrijden</h1>
          <p className="text-sm text-gray-400">Kalender van wedstrijden — nodig voor het MAS-compensatiepaneel.</p>
        </div>
        <button
          onClick={() => setShowForm((v) => !v)}
          className="btn-brand text-white px-5 py-2.5 rounded-lg text-sm font-medium"
        >
          {showForm ? "Annuleren" : "+ Wedstrijd toevoegen"}
        </button>
      </div>

      {showForm && (
        <form onSubmit={handleSubmit} className="bg-gray-900/60 border border-white/10 rounded-2xl p-6 mb-6 space-y-4 shadow-xl shadow-black/20">
          <div className="grid grid-cols-2 gap-3">
            <input
              required
              placeholder="Tegenstander"
              value={opponent}
              onChange={(e) => setOpponent(e.target.value)}
              className="bg-gray-950 border border-white/10 text-white rounded-lg px-3 py-2.5 text-sm col-span-2 focus:outline-none focus:ring-2 ring-brand"
            />
            <input
              type="datetime-local"
              required
              value={matchDate}
              onChange={(e) => setMatchDate(e.target.value)}
              className="bg-gray-950 border border-white/10 text-white rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 ring-brand"
            />
            <select
              value={isHome ? "thuis" : "uit"}
              onChange={(e) => setIsHome(e.target.value === "thuis")}
              className="bg-gray-950 border border-white/10 text-white rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 ring-brand"
            >
              <option value="thuis">Thuis</option>
              <option value="uit">Uit</option>
            </select>
            <input
              placeholder="Competitie (optioneel)"
              value={competition}
              onChange={(e) => setCompetition(e.target.value)}
              className="bg-gray-950 border border-white/10 text-white rounded-lg px-3 py-2.5 text-sm col-span-2 focus:outline-none focus:ring-2 ring-brand"
            />
          </div>
          <button
            type="submit"
            disabled={submitting}
            className="btn-brand text-white px-5 py-2.5 rounded-lg text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {submitting ? "Bezig…" : "Toevoegen"}
          </button>
        </form>
      )}

      {masTestEvents.length > 0 && (
        <div className="bg-gray-900/60 border border-white/10 rounded-2xl p-6 mb-6 shadow-xl shadow-black/20">
          <h2 className="text-white font-semibold mb-1">Aankomende MAS-testen</h2>
          <p className="text-sm text-gray-400 mb-3">
            Geprojecteerd tot het einde van het seizoen — wordt automatisch bijgewerkt zodra een
            coach een testresultaat invoert.
          </p>
          <ul className="divide-y divide-white/5">
            {masTestEvents.map((ev) => (
              <li key={ev.id} className="py-2.5 text-sm text-gray-300 flex justify-between">
                <span>{new Date(ev.event_date).toLocaleDateString("nl-BE")}</span>
                <span className="text-gray-400">{ev.player_ids.map(playerLabel).join(", ")}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {loading && <p className="text-gray-400">Laden…</p>}
      {error && <p className="text-red-400">{error}</p>}
      {!loading && !error && (
        <div className="bg-gray-900/60 border border-white/10 rounded-2xl overflow-hidden shadow-xl shadow-black/20">
          {matches.length === 0 ? (
            <p className="px-4 py-6 text-center text-gray-500 text-sm">
              Nog geen wedstrijden ingegeven. Voeg er een toe hierboven.
            </p>
          ) : (
            <table className="w-full text-sm text-left text-gray-300">
              <thead>
                <tr className="text-[10px] uppercase tracking-wider text-gray-500 border-b border-white/10">
                  <th className="px-4 py-3 font-medium">Datum</th>
                  <th className="px-4 py-3 font-medium">Tegenstander</th>
                  <th className="px-4 py-3 font-medium">Thuis/Uit</th>
                  <th className="px-4 py-3 font-medium">Competitie</th>
                  <th className="px-4 py-3 font-medium"></th>
                </tr>
              </thead>
              <tbody>
                {matches.map((m) => (
                  <tr key={m.id} className="border-b border-white/5 last:border-b-0 hover:bg-white/[0.03] transition-colors">
                    <td className="px-4 py-3">{new Date(m.match_date).toLocaleString("nl-BE")}</td>
                    <td className="px-4 py-3 font-medium text-white">{m.opponent}</td>
                    <td className="px-4 py-3">{m.is_home ? "Thuis" : "Uit"}</td>
                    <td className="px-4 py-3">{m.competition ?? "—"}</td>
                    <td className="px-4 py-3 text-right">
                      <button onClick={() => navigate("/")} className="text-brand hover:opacity-80 text-xs font-medium">
                        Naar MAS-paneel →
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  );
}
