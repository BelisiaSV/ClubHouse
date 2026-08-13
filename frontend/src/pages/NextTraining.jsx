import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import {
  finalizeSession,
  getCompositionProposal,
  getNextTrainingOverview,
  getRecentSessions,
  getSessionDetail,
  proposeTrainingAuto,
  recalculateComposition,
} from "../api/client";

const FOCUS_LABELS = {
  accumulation: "Accumulatie",
  intensification: "Intensificatie",
  realization: "Realisatie",
  deload: "Deload",
  recovery: "Herstel",
};

const BOUT_VORMEN = new Set(["ssg", "msg", "lsg", "transitie"]);

function fmtDate(dateStr) {
  if (!dateStr) return "—";
  return new Date(dateStr).toLocaleDateString("nl-BE", { day: "numeric", month: "short", year: "numeric" });
}

function todayIso() {
  return new Date().toISOString().slice(0, 10);
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

  const [kmPerTraining, setKmPerTraining] = useState("5.5");
  const [numPlayers, setNumPlayers] = useState("");
  const [sessionDate, setSessionDate] = useState(todayIso());

  const [proposal, setProposal] = useState(null); // TrainingProposalSchema (has session_id + target_*)
  const [composition, setComposition] = useState(null); // SessionCompositionProposalSchema
  const [skipVormen, setSkipVormen] = useState(new Set());
  const [generating, setGenerating] = useState(false);
  const [compositionError, setCompositionError] = useState(null);
  const [recalculating, setRecalculating] = useState(false);

  const [finalizing, setFinalizing] = useState(false);
  const [finalizeError, setFinalizeError] = useState(null);
  const [finalizeConfirmation, setFinalizeConfirmation] = useState(null);

  const loadOverview = () => {
    setOverviewLoading(true);
    getNextTrainingOverview()
      .then((data) => {
        setOverview(data);
        setOverviewError(null);
        setNumPlayers((prev) => (prev === "" ? String(data.squad_count) : prev));
        setSessionDate((prev) => (prev === todayIso() && data.next_session ? data.next_session.session_date : prev));
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
  }, []);

  const scrollToComposition = () => {
    compositionRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  const handleGenerate = async () => {
    setGenerating(true);
    setCompositionError(null);
    setProposal(null);
    setComposition(null);
    setSkipVormen(new Set());
    setFinalizeConfirmation(null);
    try {
      const prop = await proposeTrainingAuto(Number(kmPerTraining));
      setProposal(prop);
      const players = numPlayers === "" ? overview?.squad_count ?? 1 : Number(numPlayers);
      const comp = await getCompositionProposal(prop.session_id, { num_players: players });
      setComposition(comp);
    } catch (err) {
      setCompositionError(err.response?.data?.detail ?? err.message);
    } finally {
      setGenerating(false);
    }
  };

  const toggleSkip = async (vorm) => {
    if (!proposal || !composition) return;
    const next = new Set(skipVormen);
    if (next.has(vorm)) next.delete(vorm);
    else next.add(vorm);
    setSkipVormen(next);

    setRecalculating(true);
    setCompositionError(null);
    try {
      const result = await recalculateComposition(proposal.session_id, {
        blocks: composition.blocks,
        target_distance_km: composition.target_distance_km,
        skip_vormen: Array.from(next),
      });
      setComposition((c) => ({ ...c, ...result }));
    } catch (err) {
      setCompositionError(err.response?.data?.detail ?? err.message);
    } finally {
      setRecalculating(false);
    }
  };

  const handleFinalize = async () => {
    if (!proposal || !composition) return;
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
      setProposal(null);
      setComposition(null);
      setSkipVormen(new Set());
      loadRecent();
      loadOverview();
    } catch (err) {
      setFinalizeError(err.response?.data?.detail ?? err.message);
    } finally {
      setFinalizing(false);
    }
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

  return (
    <div className="max-w-6xl mx-auto py-12 px-4 space-y-8">
      <div>
        <h1 className="text-3xl font-bold text-white tracking-tight mb-1.5">Next Training</h1>
        <p className="text-sm text-gray-400 max-w-2xl leading-relaxed">
          Statusoverzicht van de spelersgroep, de eerstvolgende sessie samenstellen, en de recente
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
          <h2 className="text-white font-semibold mb-1">Sessie samenstellen</h2>
          <p className="text-sm text-gray-400">
            Genereert een km-doel op basis van de actieve cyclusweek en de teambelasting, en stelt daarna
            concrete oefenvormen voor.
          </p>
        </div>

        <div className="flex flex-wrap items-end gap-3">
          <label className="flex flex-col text-gray-300 text-xs gap-1">
            Sessiedatum
            <input
              type="date"
              value={sessionDate}
              onChange={(e) => setSessionDate(e.target.value)}
              className="bg-gray-950 border border-white/10 text-white rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 ring-brand"
            />
          </label>
          <label className="flex flex-col text-gray-300 text-xs gap-1">
            Km-doel per training
            <input
              type="number"
              step="0.1"
              min="0.1"
              value={kmPerTraining}
              onChange={(e) => setKmPerTraining(e.target.value)}
              className="bg-gray-950 border border-white/10 text-white rounded-lg px-3 py-2 text-sm w-32 focus:outline-none focus:ring-2 ring-brand"
            />
          </label>
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
            onClick={handleGenerate}
            disabled={generating}
            className="btn-brand text-white px-5 py-2.5 rounded-lg text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {generating ? "Bezig…" : "Stel training samen"}
          </button>
        </div>

        {compositionError && <p className="text-red-400 text-sm">{compositionError}</p>}

        {proposal && (
          <div className="bg-gray-950/60 border border-white/10 rounded-xl p-4 text-sm text-gray-300 space-y-1">
            <p className="text-white font-medium">{proposal.suggested_session_type}</p>
            <p className="text-xs text-gray-500">
              {proposal.adjusted_duration_min}' · {proposal.adjusted_distance_km} km · intensiteit{" "}
              {Math.round(proposal.intensity_pct_mas_low * 100)}-{Math.round(proposal.intensity_pct_mas_high * 100)}%
              MAS
            </p>
            <p className="text-xs text-gray-500">{proposal.adjustment_note}</p>
            {proposal.player_flags.length > 0 && (
              <ul className="pt-1.5 mt-1.5 border-t border-white/10 space-y-0.5">
                {proposal.player_flags.map((f, i) => (
                  <li key={i} className="text-[11px] text-amber-400">
                    {f.player_name}: {f.detail}
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}

        {composition && (
          <div className="space-y-3">
            <div className="overflow-x-auto">
              <table className="w-full text-sm text-left text-gray-300 min-w-[640px]">
                <thead>
                  <tr className="text-[10px] uppercase tracking-wider text-gray-500 border-b border-white/10">
                    <th className="px-3 py-2 font-medium">Vorm</th>
                    <th className="px-3 py-2 font-medium">Opzet</th>
                    <th className="px-3 py-2 font-medium">Duur / bouts</th>
                    <th className="px-3 py-2 font-medium">Afstand</th>
                    <th className="px-3 py-2 font-medium">0' — sla over</th>
                  </tr>
                </thead>
                <tbody>
                  {composition.blocks.map((b, i) => {
                    const skipped = skipVormen.has(b.vorm);
                    return (
                      <tr
                        key={i}
                        className={`border-b border-white/5 last:border-b-0 ${skipped ? "opacity-40" : ""}`}
                      >
                        <td className="px-3 py-2 font-medium text-white">{b.label}</td>
                        <td className="px-3 py-2 text-xs text-gray-400">{b.format_hint || "—"}</td>
                        <td className="px-3 py-2">
                          {BOUT_VORMEN.has(b.vorm)
                            ? `${b.num_bouts}x ${b.bout_duration_min}' (rust ${b.rest_between_bouts_min}')`
                            : `${b.duration_min}'`}
                        </td>
                        <td className="px-3 py-2">{b.distance_km} km</td>
                        <td className="px-3 py-2">
                          <input
                            type="checkbox"
                            checked={skipped}
                            onChange={() => toggleSkip(b.vorm)}
                            disabled={recalculating}
                            className="rounded border-white/20 bg-gray-950"
                          />
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            <div className="flex flex-wrap items-center justify-between gap-3 text-sm">
              <p className="text-gray-400">
                Totaal: <span className="text-white font-medium">{composition.total_distance_km} km</span> ·{" "}
                {composition.total_work_duration_min}' werktijd · {composition.total_clock_time_min}' op het veld
              </p>
              <button
                onClick={handleFinalize}
                disabled={finalizing}
                className="btn-brand text-white px-5 py-2.5 rounded-lg text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {finalizing ? "Bezig…" : "Sessie afronden"}
              </button>
            </div>
            <p className="text-xs text-gray-500">{composition.deviation_note}</p>
            {finalizeError && <p className="text-red-400 text-sm">{finalizeError}</p>}
            {finalizeConfirmation && <p className="text-emerald-400 text-sm">{finalizeConfirmation}</p>}
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
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {detailId && (
        <div
          className="fixed inset-0 bg-black/60 flex items-center justify-center p-4 z-50"
          onClick={closeDetail}
        >
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
                            {BOUT_VORMEN.has(b.vorm)
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
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
