import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { createMatch, listMatches } from "../api/client";

export default function Matches() {
  const navigate = useNavigate();
  const [matches, setMatches] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

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
  }, []);

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
    <div className="max-w-2xl mx-auto py-10 px-4">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-white">Wedstrijden</h1>
          <p className="text-sm text-gray-400">Kalender van wedstrijden — nodig voor het MAS-compensatiepaneel.</p>
        </div>
        <button
          onClick={() => setShowForm((v) => !v)}
          className="bg-emerald-600 hover:bg-emerald-500 text-white px-4 py-2 rounded-md text-sm"
        >
          {showForm ? "Annuleren" : "+ Wedstrijd toevoegen"}
        </button>
      </div>

      {showForm && (
        <form onSubmit={handleSubmit} className="bg-gray-800 rounded-lg p-4 mb-6 space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <input
              required
              placeholder="Tegenstander"
              value={opponent}
              onChange={(e) => setOpponent(e.target.value)}
              className="bg-gray-900 text-white rounded-md px-3 py-2 text-sm col-span-2"
            />
            <input
              type="datetime-local"
              required
              value={matchDate}
              onChange={(e) => setMatchDate(e.target.value)}
              className="bg-gray-900 text-white rounded-md px-3 py-2 text-sm"
            />
            <select
              value={isHome ? "thuis" : "uit"}
              onChange={(e) => setIsHome(e.target.value === "thuis")}
              className="bg-gray-900 text-white rounded-md px-3 py-2 text-sm"
            >
              <option value="thuis">Thuis</option>
              <option value="uit">Uit</option>
            </select>
            <input
              placeholder="Competitie (optioneel)"
              value={competition}
              onChange={(e) => setCompetition(e.target.value)}
              className="bg-gray-900 text-white rounded-md px-3 py-2 text-sm col-span-2"
            />
          </div>
          <button
            type="submit"
            disabled={submitting}
            className="bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white px-4 py-2 rounded-md text-sm"
          >
            {submitting ? "Bezig…" : "Toevoegen"}
          </button>
        </form>
      )}

      {loading && <p className="text-gray-400">Laden…</p>}
      {error && <p className="text-red-400">{error}</p>}
      {!loading && !error && (
        <div className="bg-gray-800 rounded-lg overflow-hidden">
          {matches.length === 0 ? (
            <p className="px-4 py-6 text-center text-gray-500 text-sm">
              Nog geen wedstrijden ingegeven. Voeg er een toe hierboven.
            </p>
          ) : (
            <table className="w-full text-sm text-left text-gray-300">
              <thead className="bg-gray-700 text-gray-200">
                <tr>
                  <th className="px-4 py-2">Datum</th>
                  <th className="px-4 py-2">Tegenstander</th>
                  <th className="px-4 py-2">Thuis/Uit</th>
                  <th className="px-4 py-2">Competitie</th>
                  <th className="px-4 py-2"></th>
                </tr>
              </thead>
              <tbody>
                {matches.map((m) => (
                  <tr key={m.id} className="border-t border-gray-700">
                    <td className="px-4 py-2">{new Date(m.match_date).toLocaleString("nl-BE")}</td>
                    <td className="px-4 py-2">{m.opponent}</td>
                    <td className="px-4 py-2">{m.is_home ? "Thuis" : "Uit"}</td>
                    <td className="px-4 py-2">{m.competition ?? "—"}</td>
                    <td className="px-4 py-2 text-right">
                      <button
                        onClick={() => navigate("/")}
                        className="text-emerald-400 hover:underline text-xs"
                      >
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
