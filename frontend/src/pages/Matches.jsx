import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  createMatch,
  getCalendarEvents,
  getCurrentCycles,
  getKmOverview,
  listMatches,
  listPlayers,
} from "../api/client";

const FOCUS_META = {
  accumulation: {
    label: "Accumulatie",
    badge: "bg-emerald-500/15 text-emerald-400",
    cellBg: "bg-emerald-500/30",
    dot: "bg-emerald-500",
  },
  intensification: {
    label: "Intensificatie",
    badge: "bg-amber-500/15 text-amber-400",
    cellBg: "bg-amber-500/30",
    dot: "bg-amber-500",
  },
  realization: {
    label: "Realisatie",
    badge: "bg-red-500/15 text-red-400",
    cellBg: "bg-red-500/30",
    dot: "bg-red-500",
  },
  deload: {
    label: "Deload",
    badge: "bg-cyan-500/15 text-cyan-400",
    cellBg: "bg-cyan-500/30",
    dot: "bg-cyan-500",
  },
  recovery: {
    label: "Herstel",
    badge: "bg-slate-500/15 text-slate-400",
    cellBg: "bg-slate-500/30",
    dot: "bg-slate-500",
  },
};

const WEEKDAY_HEADERS = ["Ma", "Di", "Wo", "Do", "Vr", "Za", "Zo"];
const MONTH_LABEL_FMT = new Intl.DateTimeFormat("nl-BE", { month: "long", year: "numeric" });

const addDays = (date, n) => {
  const result = new Date(date);
  result.setDate(result.getDate() + n);
  return result;
};

// Parsed as local midnight (not UTC) so day-of-month arithmetic never shifts
// a day off depending on the browser's timezone offset.
const parseDateOnly = (str) => new Date(`${str}T00:00:00`);

const dayKey = (date) =>
  `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;

function cycleEndDate(cycle) {
  return addDays(parseDateOnly(cycle.start_date), cycle.length_weeks * 7);
}

function getPhaseForDate(date, cycles) {
  for (const cycle of cycles) {
    if (!cycle) continue;
    const cycleStart = parseDateOnly(cycle.start_date);
    const cycleEnd = cycleEndDate(cycle);
    if (date < cycleStart || date >= cycleEnd) continue;
    for (let i = 0; i < cycle.weeks.length; i++) {
      const weekStart = parseDateOnly(cycle.weeks[i].week_start_date);
      const weekEnd = i + 1 < cycle.weeks.length ? parseDateOnly(cycle.weeks[i + 1].week_start_date) : cycleEnd;
      if (date >= weekStart && date < weekEnd) return cycle.weeks[i].focus;
    }
  }
  return null;
}

export default function Matches() {
  const navigate = useNavigate();
  const [matches, setMatches] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [masTestEvents, setMasTestEvents] = useState([]);
  const [playersById, setPlayersById] = useState({});

  const [cycles, setCycles] = useState({ active: null, queued: null });
  const [kmOverview, setKmOverview] = useState([]);

  const [viewDate, setViewDate] = useState(() => new Date());

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
    getCurrentCycles()
      .then(setCycles)
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (!cycles.active) {
      setKmOverview([]);
      return;
    }
    getKmOverview(cycles.active.id)
      .then(setKmOverview)
      .catch(() => setKmOverview([]));
  }, [cycles.active]);

  const playerLabel = (playerId) => {
    const player = playersById[playerId];
    return player ? `${player.first_name} ${player.last_name}` : "onbekende speler";
  };

  const matchesByDay = useMemo(() => {
    const map = new Map();
    for (const m of matches) {
      const key = dayKey(new Date(m.match_date));
      if (!map.has(key)) map.set(key, []);
      map.get(key).push(m);
    }
    return map;
  }, [matches]);

  const masEventsByDay = useMemo(() => {
    const map = new Map();
    for (const ev of masTestEvents) {
      const key = dayKey(parseDateOnly(ev.event_date));
      if (!map.has(key)) map.set(key, []);
      map.get(key).push(ev);
    }
    return map;
  }, [masTestEvents]);

  const activeCycles = useMemo(() => [cycles.active, cycles.queued].filter(Boolean), [cycles]);

  const calendarWeeks = useMemo(() => {
    const year = viewDate.getFullYear();
    const month = viewDate.getMonth();
    const firstOfMonth = new Date(year, month, 1);
    const startWeekday = (firstOfMonth.getDay() + 6) % 7; // Monday = 0
    const gridStart = addDays(firstOfMonth, -startWeekday);

    const days = [];
    for (let i = 0; i < 42; i++) {
      const date = addDays(gridStart, i);
      const key = dayKey(date);
      days.push({
        date,
        key,
        inMonth: date.getMonth() === month,
        isToday: key === dayKey(new Date()),
        focus: getPhaseForDate(date, activeCycles),
        matches: matchesByDay.get(key) ?? [],
        masEvents: masEventsByDay.get(key) ?? [],
      });
    }
    const weeks = [];
    for (let i = 0; i < days.length; i += 7) weeks.push(days.slice(i, i + 7));
    return weeks;
  }, [viewDate, activeCycles, matchesByDay, masEventsByDay]);

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
    <div className="max-w-5xl mx-auto py-12 px-4 space-y-6">
      <div className="flex items-center justify-between mb-2">
        <div>
          <h1 className="text-3xl font-bold text-white tracking-tight mb-1">Kalender</h1>
          <p className="text-sm text-gray-400">Cyclusfasen, wedstrijden en MAS-testen in één overzicht.</p>
        </div>
        <button
          onClick={() => setShowForm((v) => !v)}
          className="btn-brand text-white px-5 py-2.5 rounded-lg text-sm font-medium shrink-0"
        >
          {showForm ? "Annuleren" : "+ Wedstrijd toevoegen"}
        </button>
      </div>

      {showForm && (
        <form onSubmit={handleSubmit} className="bg-gray-900/60 border border-white/10 rounded-2xl p-6 space-y-4 shadow-xl shadow-black/20">
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

      {!cycles.active && (
        <div className="bg-gray-900/60 border border-white/10 rounded-2xl p-5 text-sm text-gray-400">
          Nog geen actieve trainingscyclus — de cyclusfasen verschijnen hier zodra je er een instelt via{" "}
          <button onClick={() => navigate("/settings")} className="text-brand hover:opacity-80 font-medium">
            Instellingen
          </button>
          .
        </div>
      )}

      <div className="bg-gray-900/60 border border-white/10 rounded-2xl p-5 shadow-xl shadow-black/20">
        <div className="flex items-center justify-between mb-4">
          <button
            onClick={() => setViewDate((d) => new Date(d.getFullYear(), d.getMonth() - 1, 1))}
            className="p-1.5 rounded-lg text-gray-400 hover:bg-white/5 hover:text-white"
            aria-label="Vorige maand"
          >
            ←
          </button>
          <h2 className="text-white font-semibold capitalize">{MONTH_LABEL_FMT.format(viewDate)}</h2>
          <button
            onClick={() => setViewDate((d) => new Date(d.getFullYear(), d.getMonth() + 1, 1))}
            className="p-1.5 rounded-lg text-gray-400 hover:bg-white/5 hover:text-white"
            aria-label="Volgende maand"
          >
            →
          </button>
        </div>

        <div className="grid grid-cols-7 gap-1 text-center text-[10px] uppercase tracking-wider text-gray-500 mb-1.5">
          {WEEKDAY_HEADERS.map((d) => (
            <div key={d}>{d}</div>
          ))}
        </div>

        <div className="grid grid-cols-7 gap-1">
          {calendarWeeks.flat().map((day) => {
            const meta = day.focus ? FOCUS_META[day.focus] : null;
            return (
              <div
                key={day.key}
                className={`rounded-lg p-1.5 min-h-[64px] text-left border ${
                  day.isToday ? "border-brand" : "border-white/5"
                } ${day.inMonth ? (meta ? meta.cellBg : "bg-white/[0.02]") : "bg-transparent opacity-30"}`}
              >
                <div className={`text-xs font-medium ${day.inMonth ? "text-gray-300" : "text-gray-600"}`}>
                  {day.date.getDate()}
                </div>
                {day.matches.map((m) => (
                  <div key={m.id} className="mt-1 text-[9px] font-semibold px-1 py-0.5 rounded bg-white/10 text-white truncate">
                    vs {m.opponent}
                  </div>
                ))}
                {day.masEvents.length > 0 && (
                  <div className="mt-1 text-[9px] font-semibold px-1 py-0.5 rounded bg-violet-500/20 text-violet-300 truncate">
                    MAS-test
                  </div>
                )}
              </div>
            );
          })}
        </div>

        <div className="flex flex-wrap items-center gap-3 mt-4 pt-4 border-t border-white/10">
          {Object.entries(FOCUS_META).map(([key, meta]) => (
            <span key={key} className="inline-flex items-center gap-1.5 text-xs text-gray-400">
              <span className={`h-2 w-2 rounded-full ${meta.dot}`} />
              {meta.label}
            </span>
          ))}
          <span className="inline-flex items-center gap-1.5 text-xs text-gray-400">
            <span className="h-2 w-2 rounded-full bg-white/40" />
            Wedstrijd
          </span>
          <span className="inline-flex items-center gap-1.5 text-xs text-gray-400">
            <span className="h-2 w-2 rounded-full bg-violet-400" />
            MAS-test
          </span>
        </div>
      </div>

      {kmOverview.length > 0 && (
        <div className="bg-gray-900/60 border border-white/10 rounded-2xl overflow-hidden shadow-xl shadow-black/20">
          <div className="px-5 py-4 border-b border-white/10">
            <h2 className="text-white font-semibold">Weekoverzicht kilometerplan — actieve cyclus</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm text-left text-gray-300">
              <thead>
                <tr className="text-[10px] uppercase tracking-wider text-gray-500 border-b border-white/10">
                  <th className="px-4 py-2.5 font-medium whitespace-nowrap">Week</th>
                  <th className="px-4 py-2.5 font-medium whitespace-nowrap">Training km</th>
                  <th className="px-4 py-2.5 font-medium whitespace-nowrap">Wedstrijd km</th>
                  <th className="px-4 py-2.5 font-medium whitespace-nowrap">Totaal</th>
                </tr>
              </thead>
              <tbody>
                {kmOverview.map((w) => {
                  const meta = FOCUS_META[w.focus];
                  return (
                    <tr key={w.week_number} className="border-b border-white/5 last:border-b-0">
                      <td className="px-4 py-2.5 whitespace-nowrap">
                        <span className="inline-flex items-center gap-1.5">
                          <span className={`h-1.5 w-1.5 rounded-full ${meta?.dot ?? "bg-gray-500"}`} />
                          W{w.week_number} · {meta?.label ?? w.focus}
                        </span>
                      </td>
                      <td className="px-4 py-2.5 whitespace-nowrap">{w.team_training_km} km</td>
                      <td className="px-4 py-2.5 whitespace-nowrap">{w.team_match_km} km</td>
                      <td className="px-4 py-2.5 font-medium text-white whitespace-nowrap">{w.team_weekly_target_km} km</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {masTestEvents.length > 0 && (
        <div className="bg-gray-900/60 border border-white/10 rounded-2xl p-6 shadow-xl shadow-black/20">
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

      <div className="bg-gray-900/60 border border-white/10 rounded-2xl overflow-hidden shadow-xl shadow-black/20">
        <div className="px-5 py-4 border-b border-white/10">
          <h2 className="text-white font-semibold">Wedstrijden</h2>
        </div>
        {loading && <p className="px-5 py-4 text-gray-400 text-sm">Laden…</p>}
        {error && <p className="px-5 py-4 text-red-400 text-sm">{error}</p>}
        {!loading && !error && (
          matches.length === 0 ? (
            <p className="px-4 py-6 text-center text-gray-500 text-sm">
              Nog geen wedstrijden ingegeven. Voeg er een toe hierboven.
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm text-left text-gray-300">
                <thead>
                  <tr className="text-[10px] uppercase tracking-wider text-gray-500 border-b border-white/10">
                    <th className="px-4 py-3 font-medium whitespace-nowrap">Datum</th>
                    <th className="px-4 py-3 font-medium whitespace-nowrap">Tegenstander</th>
                    <th className="px-4 py-3 font-medium whitespace-nowrap">Thuis/Uit</th>
                    <th className="px-4 py-3 font-medium whitespace-nowrap">Competitie</th>
                    <th className="px-4 py-3 font-medium"></th>
                  </tr>
                </thead>
                <tbody>
                  {matches.map((m) => (
                    <tr key={m.id} className="border-b border-white/5 last:border-b-0 hover:bg-white/[0.03] transition-colors">
                      <td className="px-4 py-3 whitespace-nowrap">{new Date(m.match_date).toLocaleString("nl-BE")}</td>
                      <td className="px-4 py-3 font-medium text-white whitespace-nowrap">{m.opponent}</td>
                      <td className="px-4 py-3 whitespace-nowrap">{m.is_home ? "Thuis" : "Uit"}</td>
                      <td className="px-4 py-3 whitespace-nowrap">{m.competition ?? "—"}</td>
                      <td className="px-4 py-3 text-right whitespace-nowrap">
                        <button onClick={() => navigate("/")} className="text-brand hover:opacity-80 text-xs font-medium">
                          Naar MAS-paneel →
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )
        )}
      </div>
    </div>
  );
}
