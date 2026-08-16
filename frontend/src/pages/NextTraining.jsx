import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import {
  deleteSession,
  finalizeSession,
  getCompositionProposal,
  getNextTrainingOverview,
  getRecentSessions,
  getSessionDetail,
  getVormenLibrary,
  getVormTarget,
  proposeWeek,
  recalculateComposition,
} from "../api/client";

const FOCUS_LABELS = {
  accumulation: "Accumulatie",
  intensification: "Intensificatie",
  realization: "Realisatie",
  deload: "Deload",
  recovery: "Herstel",
};

function fmtDate(dateStr) {
  if (!dateStr) return "—";
  return new Date(dateStr).toLocaleDateString("nl-BE", { day: "numeric", month: "short", year: "numeric" });
}

function todayIso() {
  return new Date().toISOString().slice(0, 10);
}

function repsValue(block, vormenByKey) {
  const isBout = vormenByKey[block.vorm]?.is_bout_vorm;
  return isBout ? block.num_bouts : block.duration_min;
}

function repsLabel(block, vormenByKey) {
  const isBout = vormenByKey[block.vorm]?.is_bout_vorm;
  return isBout
    ? `${block.num_bouts}x ${block.bout_duration_min}' (rust ${block.rest_between_bouts_min}')`
    : `${block.duration_min}'`;
}

/** One proposed training of the active week: fetches its own oefenvormen
 * composition on first expand, then lets the coach adjust each block's
 * reps (num_bouts for partijvormen, duration_min for continue vormen — never
 * the bout length itself), add extra blocks, skip a block by setting it to
 * 0, and finalize. */
function SessionProposalCard({ proposal, numPlayers, vormenLibrary, defaultSessionDate, onFinalized }) {
  const vormenByKey = useMemo(() => Object.fromEntries(vormenLibrary.map((v) => [v.vorm, v])), [vormenLibrary]);

  const [expanded, setExpanded] = useState(false);
  const [composition, setComposition] = useState(null);
  const [skipVormen, setSkipVormen] = useState(new Set());
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [busyIndex, setBusyIndex] = useState(null); // index of the block currently being recalculated

  const [addVorm, setAddVorm] = useState("");
  const [addReps, setAddReps] = useState("1");
  const [adding, setAdding] = useState(false);

  const [sessionDate, setSessionDate] = useState(defaultSessionDate);
  const [finalizing, setFinalizing] = useState(false);
  const [finalizeError, setFinalizeError] = useState(null);
  const [finalizeConfirmation, setFinalizeConfirmation] = useState(null);

  const loadComposition = async () => {
    setLoading(true);
    setError(null);
    try {
      const comp = await getCompositionProposal(proposal.session_id, { num_players: Number(numPlayers) });
      setComposition(comp);
      setSkipVormen(new Set());
    } catch (err) {
      setError(err.response?.data?.detail ?? err.message);
    } finally {
      setLoading(false);
    }
  };

  const toggleExpand = () => {
    const next = !expanded;
    setExpanded(next);
    if (next && !composition) loadComposition();
  };

  const recalc = async (blocks, skipSet) => {
    try {
      const result = await recalculateComposition(proposal.session_id, {
        blocks,
        target_distance_km: composition.target_distance_km,
        skip_vormen: Array.from(skipSet),
      });
      setComposition((c) => ({ ...c, ...result, blocks }));
    } catch (err) {
      setError(err.response?.data?.detail ?? err.message);
    }
  };

  const updateBlockReps = async (index, rawValue) => {
    const block = composition.blocks[index];
    const value = Number(rawValue);
    const nextSkip = new Set(skipVormen);

    if (!rawValue || value <= 0) {
      nextSkip.add(block.vorm);
      setSkipVormen(nextSkip);
      await recalc(composition.blocks, nextSkip);
      return;
    }
    nextSkip.delete(block.vorm);

    setBusyIndex(index);
    setError(null);
    try {
      const isBout = vormenByKey[block.vorm]?.is_bout_vorm;
      const payload = isBout
        ? { vorm: block.vorm, num_bouts: value, num_players: Number(numPlayers) }
        : { vorm: block.vorm, duration_min: value, num_players: Number(numPlayers) };
      const updatedBlock = await getVormTarget(proposal.session_id, payload);
      const newBlocks = composition.blocks.map((b, i) => (i === index ? updatedBlock : b));
      setSkipVormen(nextSkip);
      await recalc(newBlocks, nextSkip);
    } catch (err) {
      setError(err.response?.data?.detail ?? err.message);
    } finally {
      setBusyIndex(null);
    }
  };

  const handleRemoveBlock = async (index) => {
    const block = composition.blocks[index];
    const newBlocks = composition.blocks.filter((_, i) => i !== index);
    const nextSkip = new Set(skipVormen);
    nextSkip.delete(block.vorm); // gone entirely now, no longer just skipped
    setSkipVormen(nextSkip);
    await recalc(newBlocks, nextSkip);
  };

  const handleAddBlock = async () => {
    const vormMeta = vormenByKey[addVorm];
    if (!vormMeta) return;
    setAdding(true);
    setError(null);
    try {
      const value = Number(addReps);
      const payload = vormMeta.is_bout_vorm
        ? { vorm: addVorm, num_bouts: value, num_players: Number(numPlayers) }
        : { vorm: addVorm, duration_min: value, num_players: Number(numPlayers) };
      const newBlock = await getVormTarget(proposal.session_id, payload);
      const newBlocks = [...composition.blocks, newBlock];
      await recalc(newBlocks, skipVormen);
      setAddVorm("");
      setAddReps("1");
    } catch (err) {
      setError(err.response?.data?.detail ?? err.message);
    } finally {
      setAdding(false);
    }
  };

  const handleFinalize = async () => {
    setFinalizing(true);
    setFinalizeError(null);
    setFinalizeConfirmation(null);
    try {
      const finalBlocks = composition.blocks.filter((b) => !skipVormen.has(b.vorm));
      await finalizeSession(proposal.session_id, {
        session_date: sessionDate,
        blocks: finalBlocks,
        skip_vormen: Array.from(skipVormen),
      });
      setFinalizeConfirmation("Sessie afgerond en opgeslagen in Recente sessies.");
      onFinalized();
    } catch (err) {
      setFinalizeError(err.response?.data?.detail ?? err.message);
    } finally {
      setFinalizing(false);
    }
  };

  return (
    <div className="bg-gray-950/60 border border-white/10 rounded-xl overflow-hidden">
      <button
        onClick={toggleExpand}
        className="w-full flex items-center justify-between gap-3 px-4 py-3 text-left hover:bg-white/[0.03] transition-colors"
      >
        <div>
          <p className="text-white font-medium text-sm">
            Sessie {proposal.session_index} — {proposal.suggested_session_type}
          </p>
          <p className="text-xs text-gray-500">
            {proposal.adjusted_duration_min}' · {proposal.adjusted_distance_km} km · intensiteit{" "}
            {Math.round(proposal.intensity_pct_mas_low * 100)}-{Math.round(proposal.intensity_pct_mas_high * 100)}%
            MAS
          </p>
        </div>
        <span className="text-gray-400 text-xs shrink-0">{expanded ? "Inklappen ▲" : "Samenstellen ▼"}</span>
      </button>

      {expanded && (
        <div className="px-4 pb-4 space-y-4 border-t border-white/10 pt-4">
          <p className="text-xs text-gray-500">{proposal.adjustment_note}</p>
          {proposal.player_flags.length > 0 && (
            <ul className="space-y-0.5">
              {proposal.player_flags.map((f, i) => (
                <li key={i} className="text-[11px] text-amber-400">
                  {f.player_name}: {f.detail}
                </li>
              ))}
            </ul>
          )}

          {loading && <p className="text-gray-400 text-sm">Oefenvormen laden…</p>}
          {error && <p className="text-red-400 text-sm">{error}</p>}

          {composition && (
            <>
              <div className="overflow-x-auto">
                <table className="w-full text-sm text-left text-gray-300 min-w-[560px]">
                  <thead>
                    <tr className="text-[10px] uppercase tracking-wider text-gray-500 border-b border-white/10">
                      <th className="px-3 py-2 font-medium">Vorm</th>
                      <th className="px-3 py-2 font-medium">Opzet</th>
                      <th className="px-3 py-2 font-medium">
                        Herhalingen (bouts) / duur — 0 = overslaan
                      </th>
                      <th className="px-3 py-2 font-medium">Afstand</th>
                      <th className="px-3 py-2 font-medium"></th>
                    </tr>
                  </thead>
                  <tbody>
                    {composition.blocks.map((b, i, arr) => {
                      const skipped = skipVormen.has(b.vorm);
                      const isBout = vormenByKey[b.vorm]?.is_bout_vorm;
                      // Keyed by vorm + occurrence rather than array index: index-based
                      // keys made an uncontrolled reps <input> (defaultValue) keep a
                      // STALE value from whatever used to sit at that index whenever a
                      // block before it was removed — React reused the DOM node for a
                      // completely different block instead of remounting it.
                      const occurrence = arr.slice(0, i).filter((x) => x.vorm === b.vorm).length;
                      return (
                        <tr key={`${b.vorm}__${occurrence}`} className={`border-b border-white/5 last:border-b-0 ${skipped ? "opacity-40" : ""}`}>
                          <td className="px-3 py-2 font-medium text-white">{b.label}</td>
                          <td className="px-3 py-2 text-xs text-gray-400">{b.format_hint || "—"}</td>
                          <td className="px-3 py-2">
                            <div className="flex items-center gap-1.5">
                              <input
                                type="number"
                                min="0"
                                step={isBout ? 1 : 1}
                                defaultValue={repsValue(b, vormenByKey)}
                                onBlur={(e) => updateBlockReps(i, e.target.value)}
                                disabled={busyIndex === i}
                                className="bg-gray-900 border border-white/10 text-white rounded-lg px-2 py-1 text-xs w-16 focus:outline-none focus:ring-2 ring-brand"
                              />
                              <span className="text-xs text-gray-500">{isBout ? "bouts" : "min"}</span>
                            </div>
                            <p className="text-[11px] text-gray-500 mt-0.5">{repsLabel(b, vormenByKey)}</p>
                          </td>
                          <td className="px-3 py-2">{b.distance_km} km</td>
                          <td className="px-3 py-2">
                            <button
                              type="button"
                              onClick={() => handleRemoveBlock(i)}
                              title="Blok volledig verwijderen"
                              className="text-gray-500 hover:text-red-400 text-xs px-1.5 py-1 rounded hover:bg-white/5"
                            >
                              ✕
                            </button>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>

              <div className="flex flex-wrap items-end gap-2 bg-white/[0.02] border border-white/10 rounded-lg p-3">
                <label className="flex flex-col text-gray-400 text-[11px] gap-1">
                  Vorm toevoegen
                  <select
                    value={addVorm}
                    onChange={(e) => {
                      setAddVorm(e.target.value);
                      const meta = vormenByKey[e.target.value];
                      setAddReps(meta?.is_bout_vorm ? "1" : "10");
                    }}
                    className="bg-gray-900 border border-white/10 text-white rounded-lg px-2 py-1.5 text-xs focus:outline-none focus:ring-2 ring-brand"
                  >
                    <option value="">Kies een vorm…</option>
                    {vormenLibrary.map((v) => (
                      <option key={v.vorm} value={v.vorm}>
                        {v.label}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="flex flex-col text-gray-400 text-[11px] gap-1">
                  {vormenByKey[addVorm]?.is_bout_vorm ? "Bouts" : "Duur (min)"}
                  <input
                    type="number"
                    min="1"
                    value={addReps}
                    onChange={(e) => setAddReps(e.target.value)}
                    className="bg-gray-900 border border-white/10 text-white rounded-lg px-2 py-1.5 text-xs w-20 focus:outline-none focus:ring-2 ring-brand"
                  />
                </label>
                <button
                  onClick={handleAddBlock}
                  disabled={!addVorm || adding}
                  className="bg-white/5 hover:bg-white/10 border border-white/10 text-white px-3 py-1.5 rounded-lg text-xs font-medium disabled:opacity-50"
                >
                  {adding ? "Bezig…" : "+ Blok toevoegen"}
                </button>
              </div>

              <div className="flex flex-wrap items-center justify-between gap-3 text-sm">
                <p className="text-gray-400">
                  Totaal: <span className="text-white font-medium">{composition.total_distance_km} km</span> ·{" "}
                  {composition.total_work_duration_min}' werktijd · {composition.total_clock_time_min}' op het veld
                </p>
                <label className="flex items-center gap-2 text-xs text-gray-400">
                  Sessiedatum
                  <input
                    type="date"
                    value={sessionDate}
                    onChange={(e) => setSessionDate(e.target.value)}
                    className="bg-gray-900 border border-white/10 text-white rounded-lg px-2.5 py-1.5 text-xs focus:outline-none focus:ring-2 ring-brand"
                  />
                </label>
              </div>
              <p className="text-xs text-gray-500">{composition.deviation_note}</p>

              <button
                onClick={handleFinalize}
                disabled={finalizing}
                className="btn-brand text-white px-5 py-2.5 rounded-lg text-sm font-medium w-full disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {finalizing ? "Bezig…" : "Sessie afronden"}
              </button>
              {finalizeError && <p className="text-red-400 text-sm">{finalizeError}</p>}
              {finalizeConfirmation && <p className="text-emerald-400 text-sm">{finalizeConfirmation}</p>}
            </>
          )}
        </div>
      )}
    </div>
  );
}

export default function NextTraining() {
  const compositionRef = useRef(null);

  const [overview, setOverview] = useState(null);
  const [overviewLoading, setOverviewLoading] = useState(true);
  const [overviewError, setOverviewError] = useState(null);

  const [recent, setRecent] = useState([]);
  const [recentLoading, setRecentLoading] = useState(true);
  const [recentError, setRecentError] = useState(null);

  const [detailId, setDetailId] = useState(null);
  const [detail, setDetail] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState(null);
  const [deletingId, setDeletingId] = useState(null);

  const [numPlayers, setNumPlayers] = useState("");
  const [vormenLibrary, setVormenLibrary] = useState([]);

  const [weekProposals, setWeekProposals] = useState(null);
  const [generating, setGenerating] = useState(false);
  const [weekError, setWeekError] = useState(null);

  const loadOverview = () => {
    setOverviewLoading(true);
    getNextTrainingOverview()
      .then((data) => {
        setOverview(data);
        setOverviewError(null);
        setNumPlayers((prev) => (prev === "" ? String(data.squad_count) : prev));
      })
      .catch((err) => setOverviewError(err.response?.data?.detail ?? err.message))
      .finally(() => setOverviewLoading(false));
  };

  const loadRecent = () => {
    setRecentLoading(true);
    getRecentSessions()
      .then((data) => {
        setRecent(data);
        setRecentError(null);
      })
      .catch((err) => setRecentError(err.response?.data?.detail ?? err.message))
      .finally(() => setRecentLoading(false));
  };

  useEffect(() => {
    loadOverview();
    loadRecent();
    getVormenLibrary()
      .then(setVormenLibrary)
      .catch(() => {});
  }, []);

  const scrollToComposition = () => {
    compositionRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  const handleGenerateWeek = async () => {
    setGenerating(true);
    setWeekError(null);
    setWeekProposals(null);
    try {
      const proposals = await proposeWeek();
      setWeekProposals(proposals);
    } catch (err) {
      setWeekError(err.response?.data?.detail ?? err.message);
    } finally {
      setGenerating(false);
    }
  };

  const handleSessionFinalized = () => {
    loadRecent();
    loadOverview();
  };

  const openDetail = async (id) => {
    setDetailId(id);
    setDetail(null);
    setDetailError(null);
    setDetailLoading(true);
    try {
      const data = await getSessionDetail(id);
      setDetail(data);
    } catch (err) {
      setDetailError(err.response?.data?.detail ?? err.message);
    } finally {
      setDetailLoading(false);
    }
  };

  const closeDetail = () => {
    setDetailId(null);
    setDetail(null);
    setDetailError(null);
  };

  const handleDeleteSession = async (id, e) => {
    e?.stopPropagation();
    if (!window.confirm("Deze sessie definitief verwijderen?")) return;
    setDeletingId(id);
    try {
      await deleteSession(id);
      if (detailId === id) closeDetail();
      loadRecent();
    } catch (err) {
      setRecentError(err.response?.data?.detail ?? err.message);
    } finally {
      setDeletingId(null);
    }
  };

  const tiles = useMemo(() => {
    if (!overview) return [];
    return [
      {
        key: "squad",
        label: "Spelersgroep",
        value: overview.squad_count,
        sub: "spelers in de A-kern",
        to: "/players",
      },
      {
        key: "flagged",
        label: "Belast / overbelast / geblesseerd",
        value: overview.flagged_count,
        sub: "spelers met een actief signaal",
        to: "/players?filter=flagged",
        warn: overview.flagged_count > 0,
      },
      {
        key: "sessions",
        label: "Sessies deze week",
        value: overview.sessions_this_week,
        sub: overview.week_focus ? FOCUS_LABELS[overview.week_focus] ?? overview.week_focus : "geen actieve cyclus",
        to: "/matches",
      },
      {
        key: "next",
        label: "Volgende sessie",
        value: overview.next_session ? overview.next_session.label : "—",
        sub: overview.next_session
          ? overview.next_session.session_type === "match"
            ? "wedstrijd"
            : "training"
          : "niets gepland",
        onClick: scrollToComposition,
      },
    ];
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [overview]);

  const defaultSessionDate = overview?.next_session?.session_date ?? todayIso();

  return (
    <div className="max-w-6xl mx-auto py-12 px-4 space-y-8">
      <div>
        <h1 className="text-3xl font-bold text-white tracking-tight mb-1.5">Dashboard</h1>
        <p className="text-sm text-gray-400 max-w-2xl leading-relaxed">
          Statusoverzicht van de spelersgroep, de trainingen van deze week samenstellen, en de recente
          sessiegeschiedenis.
        </p>
      </div>

      {overviewLoading && <p className="text-gray-400 text-sm">Laden…</p>}
      {overviewError && <p className="text-red-400 text-sm">{overviewError}</p>}

      {!overviewLoading && !overviewError && overview && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {tiles.map((tile) => {
            const content = (
              <>
                <p className="text-[10px] uppercase tracking-wider text-gray-500 font-medium mb-2">{tile.label}</p>
                <p className={`text-3xl font-bold mb-1 ${tile.warn ? "text-amber-400" : "text-white"}`}>
                  {tile.value}
                </p>
                <p className="text-xs text-gray-500">{tile.sub}</p>
              </>
            );
            const className = `text-left bg-gray-900/60 border rounded-2xl p-5 shadow-xl shadow-black/20 hover:bg-white/5 transition-colors ${
              tile.warn ? "border-amber-500/30" : "border-white/10"
            }`;
            return tile.to ? (
              <Link key={tile.key} to={tile.to} className={className}>
                {content}
              </Link>
            ) : (
              <button key={tile.key} onClick={tile.onClick} className={className}>
                {content}
              </button>
            );
          })}
        </div>
      )}

      <div ref={compositionRef} className="bg-gray-900/60 border border-white/10 rounded-2xl p-6 shadow-xl shadow-black/20 space-y-5">
        <div>
          <h2 className="text-white font-semibold mb-1">Trainingen deze week samenstellen</h2>
          <p className="text-sm text-gray-400">
            Genereert automatisch een voorstel voor elke training van de actieve cyclusweek, op basis
            van de teambelasting — jij geeft enkel het aantal aanwezige spelers door.
          </p>
        </div>

        <div className="flex flex-wrap items-end gap-3">
          <label className="flex flex-col text-gray-300 text-xs gap-1">
            Aantal spelers aanwezig
            <input
              type="number"
              min="1"
              value={numPlayers}
              onChange={(e) => setNumPlayers(e.target.value)}
              className="bg-gray-950 border border-white/10 text-white rounded-lg px-3 py-2 text-sm w-32 focus:outline-none focus:ring-2 ring-brand"
            />
          </label>
          <button
            onClick={handleGenerateWeek}
            disabled={generating || !numPlayers}
            className="btn-brand text-white px-5 py-2.5 rounded-lg text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {generating ? "Bezig…" : "Stel trainingen samen"}
          </button>
        </div>

        {weekError && <p className="text-red-400 text-sm">{weekError}</p>}

        {weekProposals && (
          <div className="space-y-3">
            {weekProposals.map((proposal) => (
              <SessionProposalCard
                key={proposal.session_id}
                proposal={proposal}
                numPlayers={numPlayers}
                vormenLibrary={vormenLibrary}
                defaultSessionDate={defaultSessionDate}
                onFinalized={handleSessionFinalized}
              />
            ))}
          </div>
        )}
      </div>

      <div className="bg-gray-900/60 border border-white/10 rounded-2xl shadow-xl shadow-black/20">
        <div className="p-6 pb-0">
          <h2 className="text-white font-semibold mb-1">Recente sessies</h2>
          <p className="text-sm text-gray-400 mb-4">Klik op een sessie voor het volledige overzicht.</p>
        </div>

        {recentLoading && <p className="text-gray-400 text-sm px-6 pb-6">Laden…</p>}
        {recentError && <p className="text-red-400 text-sm px-6 pb-6">{recentError}</p>}

        {!recentLoading && !recentError && recent.length === 0 && (
          <p className="text-gray-500 text-sm px-6 pb-6">Nog geen afgeronde sessies.</p>
        )}

        {!recentLoading && !recentError && recent.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-sm text-left text-gray-300 min-w-[640px]">
              <thead>
                <tr className="text-[10px] uppercase tracking-wider text-gray-500 border-b border-white/10">
                  <th className="px-6 py-3 font-medium">Sessie</th>
                  <th className="px-4 py-3 font-medium">Type</th>
                  <th className="px-4 py-3 font-medium">Datum</th>
                  <th className="px-4 py-3 font-medium">Belasting</th>
                  <th className="px-4 py-3 font-medium">RPE</th>
                  <th className="px-4 py-3 font-medium"></th>
                </tr>
              </thead>
              <tbody>
                {recent.map((s) => (
                  <tr
                    key={s.id}
                    onClick={() => openDetail(s.id)}
                    className="border-b border-white/5 last:border-b-0 hover:bg-white/[0.03] transition-colors cursor-pointer"
                  >
                    <td className="px-6 py-3 font-medium text-white">{s.session_label}</td>
                    <td className="px-4 py-3">{s.type_summary}</td>
                    <td className="px-4 py-3 text-gray-400">{fmtDate(s.session_date)}</td>
                    <td className="px-4 py-3">{s.total_distance_km} km</td>
                    <td className="px-4 py-3">{s.team_avg_rpe != null ? s.team_avg_rpe : "—"}</td>
                    <td className="px-4 py-3">
                      <button
                        type="button"
                        onClick={(e) => handleDeleteSession(s.id, e)}
                        disabled={deletingId === s.id}
                        title="Sessie verwijderen"
                        className="text-gray-500 hover:text-red-400 text-xs px-1.5 py-1 rounded hover:bg-white/5 disabled:opacity-50"
                      >
                        {deletingId === s.id ? "…" : "✕"}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {detailId && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center p-4 z-50" onClick={closeDetail}>
          <div
            className="bg-gray-900 border border-white/10 rounded-2xl shadow-2xl max-w-2xl w-full max-h-[85vh] overflow-y-auto p-6 space-y-4"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-start justify-between gap-3">
              <h3 className="text-white font-semibold text-lg">Sessiedetail</h3>
              <button onClick={closeDetail} className="text-gray-400 hover:text-white text-sm">
                Sluiten ✕
              </button>
            </div>

            {detailLoading && <p className="text-gray-400 text-sm">Laden…</p>}
            {detailError && <p className="text-red-400 text-sm">{detailError}</p>}

            {detail && (
              <>
                <p className="text-sm text-gray-400">
                  {fmtDate(detail.session_date)} · {detail.total_distance_km} km ·{" "}
                  {detail.total_work_duration_min}' werktijd
                </p>

                <div className="overflow-x-auto">
                  <table className="w-full text-sm text-left text-gray-300 min-w-[480px]">
                    <thead>
                      <tr className="text-[10px] uppercase tracking-wider text-gray-500 border-b border-white/10">
                        <th className="px-3 py-2 font-medium">Vorm</th>
                        <th className="px-3 py-2 font-medium">Duur / bouts</th>
                        <th className="px-3 py-2 font-medium">Afstand</th>
                      </tr>
                    </thead>
                    <tbody>
                      {detail.blocks.map((b, i) => (
                        <tr key={i} className="border-b border-white/5 last:border-b-0">
                          <td className="px-3 py-2 font-medium text-white">{b.label}</td>
                          <td className="px-3 py-2">
                            {b.num_bouts != null
                              ? `${b.num_bouts}x ${b.bout_duration_min}' (rust ${b.rest_between_bouts_min}')`
                              : `${b.duration_min}'`}
                          </td>
                          <td className="px-3 py-2">{b.distance_km} km</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                {detail.skipped_vormen.length > 0 && (
                  <div className="text-xs text-gray-500 pt-2 border-t border-white/10">
                    Overgeslagen (0'): {detail.skipped_vormen.join(", ")}
                  </div>
                )}

                <button
                  type="button"
                  onClick={(e) => handleDeleteSession(detailId, e)}
                  disabled={deletingId === detailId}
                  className="text-red-400 hover:text-red-300 text-xs pt-2 border-t border-white/10 w-full text-left disabled:opacity-50"
                >
                  {deletingId === detailId ? "Bezig met verwijderen…" : "Sessie verwijderen"}
                </button>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
