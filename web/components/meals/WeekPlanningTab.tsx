"use client";

import { useMemo, useState } from "react";
import MealPill from "./MealPill";
import ExceptionDialog, { type AthleteLite } from "./ExceptionDialog";
import {
  DAY_SHORT,
  type MealException,
  type MealFreeDay,
  type MealPlan,
  addDays,
  countDay,
  getMealForDay,
  getMondayOf,
  subjectId,
  toDateStr,
  weekMealDays,
} from "@/lib/meals";

interface WeekPlanningTabProps {
  athletes: AthleteLite[];
  plans: MealPlan[];
  exceptions: MealException[];
  freeDays: MealFreeDay[];
}

export default function WeekPlanningTab({ athletes, plans, exceptions, freeDays }: WeekPlanningTabProps) {
  const [monday, setMonday] = useState(() => getMondayOf(new Date()));
  const [cell, setCell] = useState<{ athleteId: string; date: string } | null>(null);

  const days = useMemo(() => weekMealDays(monday), [monday]);
  const sortedAthletes = useMemo(() => [...athletes].sort((a, b) => a.full_name.localeCompare(b.full_name)), [athletes]);
  const athleteIds = useMemo(() => sortedAthletes.map((a) => a.id), [sortedAthletes]);
  const totals = useMemo(() => days.map((d) => countDay(athleteIds, toDateStr(d), plans, exceptions, freeDays)), [
    days,
    athleteIds,
    plans,
    exceptions,
    freeDays,
  ]);

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <button type="button" onClick={() => setMonday(addDays(monday, -7))} className={navBtnClass}>
          ← vorige week
        </button>
        <button type="button" onClick={() => setMonday(getMondayOf(new Date()))} className={navBtnClass}>
          vandaag
        </button>
        <button type="button" onClick={() => setMonday(addDays(monday, 7))} className={navBtnClass}>
          volgende week →
        </button>
        <span className="text-sm text-gray-500">
          Week {toDateStr(days[0])} – {toDateStr(days[3])}
        </span>
      </div>

      <div className="mb-3 rounded-lg border border-sky-500/20 bg-sky-500/10 px-3.5 py-2.5 text-xs text-sky-300">
        Klik op een cel om een uitzondering (afwezigheid of eenmalige maaltijd) te registreren.
      </div>

      <div className="overflow-x-auto rounded-2xl border border-white/10 bg-gray-900/60 shadow-xl shadow-black/20">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-white/10 text-xs uppercase tracking-wide text-gray-500">
              <th className="px-4 py-3 font-medium">Naam</th>
              <th className="px-4 py-3 font-medium">Klas</th>
              {days.map((d) => (
                <th key={toDateStr(d)} className="px-3 py-3 text-center font-medium">
                  {DAY_SHORT[d.getDay()]}
                  <br />
                  <span className="font-normal normal-case text-gray-600">{toDateStr(d).slice(5)}</span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-white/5">
            {sortedAthletes.map((athlete) => (
              <tr key={athlete.id}>
                <td className="px-4 py-2.5 text-gray-100">{athlete.full_name}</td>
                <td className="px-4 py-2.5 text-gray-500">{athlete.class_group ?? "—"}</td>
                {days.map((d) => {
                  const dateStr = toDateStr(d);
                  const code = getMealForDay(athlete.id, dateStr, plans, exceptions, freeDays);
                  return (
                    <td
                      key={dateStr}
                      className="cursor-pointer px-3 py-2.5 text-center transition hover:bg-white/5"
                      onClick={() => setCell({ athleteId: athlete.id, date: dateStr })}
                    >
                      <MealPill code={code} />
                    </td>
                  );
                })}
              </tr>
            ))}
            {sortedAthletes.length === 0 && (
              <tr>
                <td colSpan={2 + days.length} className="px-4 py-10 text-center text-sm text-gray-500">
                  Geen leerlingen in het maaltijdprogramma.
                </td>
              </tr>
            )}
          </tbody>
          <tfoot>
            <tr className="border-t border-white/10 font-semibold">
              <td className="px-4 py-3 text-gray-200">Totaal</td>
              <td />
              {totals.map((t, i) => (
                <td key={i} className="px-3 py-3 text-center">
                  {t.vrij ? (
                    <span className="text-xs italic text-gray-600">vrij</span>
                  ) : (
                    <>
                      <span className="text-base font-bold text-emerald-400">{t.total}</span>
                      <div className="text-[10px] font-normal text-gray-500">
                        {[t.s ? `${t.s}s` : "", t.v ? `${t.v}v` : "", t.gv ? `${t.gv}gv` : ""].filter(Boolean).join(" ")}
                      </div>
                    </>
                  )}
                </td>
              ))}
            </tr>
          </tfoot>
        </table>
      </div>

      {cell && (
        <ExceptionDialog
          athletes={athletes}
          fixedAthleteId={cell.athleteId}
          defaultDate={cell.date}
          existing={exceptions.filter(
            (e) => subjectId(e) === cell.athleteId && e.date_from <= cell.date && (!e.date_to || e.date_to >= cell.date)
          )}
          onClose={() => setCell(null)}
        />
      )}
    </div>
  );
}

const navBtnClass = "rounded-lg border border-white/10 px-3 py-1.5 text-xs font-medium text-gray-300 hover:bg-white/5";
