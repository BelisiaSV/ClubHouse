import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { generateForMatch, getMatchPlayers, listMatches, updateMatchPlayer } from "../api/client";

const THRESHOLD_MIN = 60;
const MINUTE_OPTIONS = Array.from({ length: 91 }, (_, i) => i);

const STATUS_LABELS = {
  basis: "Basis (90')",
  bank: "Bank (0')",
  niet_geselecteerd: "Niet geselecteerd",
};

function fmtMatchLabel(m) {
  const d = new Date(m.match_date);
  return `${d.toLocaleDateString("nl-BE", { day: "numeric", month: "short" })} · vs ${m.opponent}`;
}

export default function Compensation() {
  const [matches, setMatches] = useState([]);
  const [matchesLoading, setMatchesLoading] = useState(true);
  const [matchesError, setMatchesError] = useState(null);
  const [selectedMatchId, setSelectedMatchId] = useState("");

  const [rows, setRows] = useState([]);
  const [rowsLoading, setRowsLoading] = useState(false);
  const [rowsError, setRowsError] = useState(null);
  // per player_id: { state: 'idle'|'saving'|'saved'|'error', pending: {selection_status, minutes_played} }
  const [rowSaveState, setRowSaveState] = useState({});

  const [generating, setGenerating] = useState(false);
  const [generateError, setGenerateError] = useState(null);
  const [result, setResult] = useState(null);

  useEffect(() => {
    listMatches()
      .then((data) => {
        setMatches(data);
        if (data.length > 0) setSelectedMatchId(data[0].id);
      })
      .catch((err) => setMatchesError(err.response?.data?.detail ?? err.message))
      .finally(() => setMatchesLoading(false));
  }, []);

  const loadRows = (matchId) => {
    if (!matchId) return;
    setRowsLoading(true);
    setRowsError(null);
    setResult(null);
    setGenerateError(null);
    getMatchPlayers(matchId)
      .then((data) => {
        setRows(data);
        setRowSaveState({});
      })
      .catch((err) => setRowsError(err.response?.data?.detail ?? err.message))
      .finally(() => setRowsLoading(false));
  };

  useEffect(() => {
    loadRows(selectedMatchId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedMatchId]);

  const savePlayerRow = async (playerId, payload) => {
    setRowSaveState((st) => ({ ...st, [playerId]: { state: "saving", pending: payload } }));
    try {
      const updated = await updateMatchPlayer(selectedMatchId, playerId, payload);
      setRows((rs) => rs.map((r) => (r.player_id === playerId ? updated : r)));
      setRowSaveState((st) => ({ ...st, [playerId]: { state: "saved" } }));
    } catch (err) {
      setRowSaveState((st) => ({
        ...st,
        [playerId]: { state: "error", pending: payload, message: err.response?.data?.detail ?? err.message },
      }));
    }
  };

  // Native <select> onChange only fires once, when the dropdown closes on a
  // new choice — so this already satisfies "save on close, not per keystroke"
  // without needing an artificial debounce timer.
  const handleStatusChange = (row, newStatus) => {
    setRows((rs) => rs.map((r) => (r.player_id === row.player_id ? { ...r, selection_status: newStatus } : r)));
    savePlayerRow(row.player_id, { selection_status: newStatus });
  };

  const handleMinutesChange = (row, newMinutes) => {
    const minutes = newMinutes === "" ? null : Number(newMinutes);
    setRows((rs) =>
      rs.map((r) =>
        r.player_id === row.player_id ? { ...r, minutes_played: minutes ?? r.minutes_played } : r
      )
    );
    savePlayerRow(row.player_id, { selection_status: row.selection_status, minutes_played: minutes });
  };

  const retryRow = (row) => {
    const pending = rowSaveState[row.player_id]?.pending;
    if (pending) savePlayerRow(row.player_id, pending);
  };

  const eligibleCount = rows.filter((r) => r.minutes_played < THRESHOLD_MIN).length;

  const handleGenerate = async () => {
    setGenerating(true);
    setGenerateError(null);
    setResult(null);
    try {
      const data = await generateForMatch(selectedMatchId);
      setResult(data);
    } catch (err) {
      const status = err.response?.status;
      const detail = err.response?.data?.detail;
      if (status === 400) {
        setGenerateError(detail || "Kon geen schema's genereren.");
      } else if (status !== 401) {
        // 401s are handled globally (redirect to login) by the api client.
        setGenerateError(detail || err.message);
      }
    } finally {
      setGenerating(false);
    }
  };

  if (matchesLoading) {
    return <p className="text-gray-400 p-6">Laden…</p>;
  }

  return (
    <div className="max-w-4xl mx-auto py-12 px-4 space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-white tracking-tight mb-1.5">MAS &amp; Compensatiepaneel</h1>
        <p className="text-sm text-gray-400 max-w-2xl leading-relaxed">
          Kies een wedstrijd en stel per speler zijn status of exacte speelminuten in. Spelers onder de
          drempel krijgen een MAS-gebaseerd inhaalprogramma.
        </p>
      </div>

      {matchesError && <p className="text-red-400 text-sm">{matchesError}</p>}

      {matches.length === 0 && !matchesError && (
        <div className="bg-gray-900/60 border border-white/10 rounded-2xl p-10 text-center space-y-4 shadow-xl shadow-black/20">
          <p className="text-gray-400 text-sm">Nog geen wedstrijden ingegeven.</p>
          <Link to="/matches" className="inline-block btn-brand text-white px-5 py-2.5 rounded-lg text-sm font-medium">
            Ga naar de kalender →
          </Link>
        </div>
      )}

      {matches.length > 0 && (
        <>
          <div className="flex items-center gap-3 flex-wrap bg-gray-900/60 border border-white/10 rounded-xl px-4 py-3">
            <span className="text-sm text-gray-400 font-medium">Wedstrijd</span>
            <select
              value={selectedMatchId}
              onChange={(e) => setSelectedMatchId(e.target.value)}
              className="bg-gray-950 border border-white/10 text-white rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 ring-brand"
            >
              {matches.map((m) => (
                <option key={m.id} value={m.id}>
                  {fmtMatchLabel(m)}
                </option>
              ))}
            </select>
            {!rowsLoading && !rowsError && (
              <span className="text-sm text-gray-500">
                {eligibleCount} speler(s) komen in aanmerking (drempel {THRESHOLD_MIN}')
              </span>
            )}
          </div>

          {rowsLoading && <p className="text-gray-400 text-sm">Spelers laden…</p>}
          {rowsError && <p className="text-red-400 text-sm">{rowsError}</p>}

          {!rowsLoading && !rowsError && rows.length > 0 && (
            <div className="overflow-x-auto bg-gray-900/60 border border-white/10 rounded-2xl shadow-xl shadow-black/20">
              <table className="w-full text-sm text-left text-gray-300 min-w-[760px]">
                <thead>
                  <tr className="text-[10px] uppercase tracking-wider text-gray-500 border-b border-white/10">
                    <th className="px-4 py-3 font-medium">Speler</th>
                    <th className="px-4 py-3 font-medium">Status</th>
                    <th className="px-4 py-3 font-medium">Minuten (override)</th>
                    <th className="px-4 py-3 font-medium">MAS</th>
                    <th className="px-4 py-3 font-medium">Compensatie</th>
                    <th className="px-4 py-3 font-medium"></th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r) => {
                    const save = rowSaveState[r.player_id];
                    const eligible = r.minutes_played < THRESHOLD_MIN;
                    return (
                      <tr key={r.player_id} className="border-b border-white/5 last:border-b-0 hover:bg-white/[0.03] transition-colors">
                        <td className="px-4 py-3">
                          <div className="font-medium text-white">
                            {r.jersey_number != null ? `#${r.jersey_number} ` : ""}
                            {r.first_name} {r.last_name}
                          </div>
                        </td>
                        <td className="px-4 py-3">
                          <select
                            value={r.selection_status}
                            onChange={(e) => handleStatusChange(r, e.target.value)}
                            className="bg-gray-900 text-white rounded-md px-2 py-1 text-xs border border-gray-700"
                          >
                            {Object.entries(STATUS_LABELS).map(([value, label]) => (
                              <option key={value} value={value}>
                                {label}
                              </option>
                            ))}
                          </select>
                        </td>
                        <td className="px-4 py-3">
                          <select
                            value={r.minutes_played}
                            onChange={(e) => handleMinutesChange(r, e.target.value)}
                            className="bg-gray-900 text-white rounded-md px-2 py-1 text-xs border border-gray-700 w-20"
                          >
                            {MINUTE_OPTIONS.map((m) => (
                              <option key={m} value={m}>
                                {m}'
                              </option>
                            ))}
                          </select>
                        </td>
                        <td className="px-4 py-3 text-gray-400">
                          {r.mas_kmh != null ? `${r.mas_kmh} km/u` : "—"}
                        </td>
                        <td className="px-4 py-3">
                          {eligible ? (
                            <span className="inline-flex text-xs px-2 py-0.5 rounded bg-amber-500/20 text-amber-400">
                              In aanmerking
                            </span>
                          ) : (
                            <span className="text-xs text-gray-500">{r.minutes_played}' gespeeld</span>
                          )}
                        </td>
                        <td className="px-4 py-3 w-16">
                          {save?.state === "saving" && (
                            <span className="text-xs text-gray-500">Bezig…</span>
                          )}
                          {save?.state === "saved" && (
                            <span className="text-emerald-400 text-sm" title="Opgeslagen">
                              ✓
                            </span>
                          )}
                          {save?.state === "error" && (
                            <div className="flex items-center gap-1">
                              <span className="text-red-400 text-xs" title={save.message}>
                                ✕ fout
                              </span>
                              <button
                                onClick={() => retryRow(r)}
                                className="text-emerald-400 text-xs underline"
                              >
                                Opnieuw
                              </button>
                            </div>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}

          {!rowsLoading && !rowsError && rows.length > 0 && (
            <div className="flex items-center justify-between flex-wrap gap-3">
              <span className="text-xs text-gray-500">
                Schema's worden gegenereerd voor de actieve cyclus/week van vandaag.
              </span>
              <button
                onClick={handleGenerate}
                disabled={generating || eligibleCount === 0}
                style={{ backgroundColor: "#D9A441" }}
                className="text-white px-4 py-2 rounded-md text-sm font-medium disabled:opacity-40 disabled:cursor-not-allowed"
              >
                {generating ? "Bezig met genereren…" : "Maak schema's"}
              </button>
            </div>
          )}

          {generateError && (
            <div className="bg-red-950/40 border border-red-800 text-red-300 text-sm rounded-md p-4">
              <p className="font-medium mb-1">Kon geen schema's genereren</p>
              <p>{generateError}</p>
            </div>
          )}

          {result && (
            <div className="bg-gray-800 rounded-lg p-4 space-y-3">
              <div className="text-xs uppercase tracking-wider text-gray-500">
                Gegenereerde inhaalschema's · {result.context_label}
              </div>
              {result.programs.length === 0 && (
                <p className="text-sm text-gray-400">Geen programma's gegenereerd voor deze wedstrijd.</p>
              )}
              {result.programs.map((p, i) => (
                <div key={i} className="bg-gray-900 rounded-md p-3">
                  <div className="font-medium text-white text-sm">{p.player_name}</div>
                  <div className="text-xs text-gray-400 mt-0.5">
                    {p.trigger_detail} · {p.structure_description}
                  </div>
                </div>
              ))}
              {result.skipped.length > 0 && (
                <div className="pt-2 border-t border-gray-700 text-xs text-gray-500">
                  Overgeslagen: {result.skipped.map((s) => `${s.player_name} (${s.reason})`).join(", ")}
                </div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}
