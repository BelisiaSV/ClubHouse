"use client";

import { useMemo, useState } from "react";
import MealPill from "./MealPill";
import type { AthleteLite } from "./ExceptionDialog";
import { MEAL_WEEKDAYS, type MealException, type MealFreeDay, type MealPlan, fromDateStr, getActiveException, isFreeDay, getMealForDay, toDateStr } from "@/lib/meals";

interface DayExportTabProps {
  athletes: AthleteLite[];
  boardingSubjects: AthleteLite[];
  plans: MealPlan[];
  exceptions: MealException[];
  freeDays: MealFreeDay[];
}

/** The kitchen-facing list for one day: who eats, and what. */
export default function DayExportTab({ athletes, boardingSubjects, plans, exceptions, freeDays }: DayExportTabProps) {
  const [dateStr, setDateStr] = useState(() => toDateStr(new Date()));

  const dayOfWeek = fromDateStr(dateStr).getDay();
  const isSchoolMealDay = (MEAL_WEEKDAYS as readonly number[]).includes(dayOfWeek);
  const vrij = isFreeDay(dateStr, freeDays);

  const rows = useMemo(() => {
    if (!isSchoolMealDay || vrij) return [];
    return athletes
      .map((athlete) => ({ athlete, code: getMealForDay(athlete.id, dateStr, plans, exceptions, freeDays) }))
      .filter((r) => r.code)
      .sort((a, b) => `${a.athlete.class_group ?? ""}${a.athlete.full_name}`.localeCompare(`${b.athlete.class_group ?? ""}${b.athlete.full_name}`));
  }, [athletes, dateStr, plans, exceptions, freeDays, isSchoolMealDay, vrij]);

  // Boarding students present today with their own lunch package (internaat
  // closed) — purely informational for staff, never part of the s/v/gv/
  // totaal counts below, since they don't eat the kitchen's warm meal.
  const lunchpakketRows = useMemo(() => {
    if (!isSchoolMealDay || vrij) return [];
    return boardingSubjects
      .filter((subject) => getActiveException(exceptions, subject.id, dateStr)?.exception_type === "eigen_lunchpakket")
      .sort((a, b) => `${a.class_group ?? ""}${a.full_name}`.localeCompare(`${b.class_group ?? ""}${b.full_name}`));
  }, [boardingSubjects, dateStr, exceptions, isSchoolMealDay, vrij]);

  const counts = { s: rows.filter((r) => r.code === "s").length, v: rows.filter((r) => r.code === "v").length, gv: rows.filter((r) => r.code === "gv").length };

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-end gap-3">
        <label className="flex flex-col text-sm text-gray-300">
          Kies een datum
          <input
            type="date"
            value={dateStr}
            onChange={(e) => setDateStr(e.target.value)}
            className="mt-1 rounded-lg border border-white/10 bg-gray-950 px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-emerald-500"
          />
        </label>
        <button
          type="button"
          onClick={() => window.print()}
          className="rounded-lg border border-white/10 px-3.5 py-2 text-sm font-medium text-gray-300 hover:bg-white/5"
        >
          Afdrukken
        </button>
      </div>

      {!isSchoolMealDay ? (
        <p className="rounded-2xl border border-white/10 bg-gray-900/60 p-6 text-center text-sm text-gray-500">
          {toDateStr(fromDateStr(dateStr))} is geen schooldag met warme maaltijden.
        </p>
      ) : vrij ? (
        <p className="rounded-2xl border border-amber-500/20 bg-amber-500/10 p-6 text-center text-sm text-amber-300">
          Vrije dag — geen warme maaltijden op {dateStr}.
        </p>
      ) : (
        <div className="rounded-2xl border border-white/10 bg-gray-900/60 shadow-xl shadow-black/20">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/10 px-5 py-4">
            <p className="text-lg font-bold text-white">{dateStr}</p>
            <div className="flex gap-4 text-sm">
              <span className="text-sky-300">
                <strong>{counts.s}</strong> s
              </span>
              <span className="text-emerald-300">
                <strong>{counts.v}</strong> v
              </span>
              <span className="text-amber-300">
                <strong>{counts.gv}</strong> gv
              </span>
              <span className="text-gray-300">
                <strong>{rows.length}</strong> totaal
              </span>
            </div>
          </div>
          {rows.length === 0 ? (
            <p className="p-8 text-center text-sm text-gray-500">Geen leerlingen met maaltijd deze dag.</p>
          ) : (
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-white/10 text-xs uppercase tracking-wide text-gray-500">
                  <th className="px-4 py-2.5 font-medium">#</th>
                  <th className="px-4 py-2.5 font-medium">Naam</th>
                  <th className="px-4 py-2.5 font-medium">Klas</th>
                  <th className="px-4 py-2.5 text-center font-medium">Maaltijd</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {rows.map(({ athlete, code }, i) => (
                  <tr key={athlete.id}>
                    <td className="px-4 py-2 text-gray-600">{i + 1}</td>
                    <td className="px-4 py-2 text-gray-100">{athlete.full_name}</td>
                    <td className="px-4 py-2 text-gray-500">{athlete.class_group ?? "—"}</td>
                    <td className="px-4 py-2 text-center">
                      <MealPill code={code} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {isSchoolMealDay && !vrij && lunchpakketRows.length > 0 && (
        <div className="mt-4 rounded-2xl border border-amber-500/20 bg-amber-500/10 shadow-xl shadow-black/20">
          <div className="border-b border-amber-500/20 px-5 py-3">
            <p className="text-sm font-semibold text-amber-300">Eigen lunchpakket (internaat gesloten)</p>
            <p className="text-xs text-amber-300/70">
              Aanwezig vandaag met eigen lunchpakket — niet meegeteld in de aantallen hierboven.
            </p>
          </div>
          <table className="w-full text-left text-sm">
            <tbody className="divide-y divide-white/5">
              {lunchpakketRows.map((subject, i) => (
                <tr key={subject.id}>
                  <td className="px-4 py-2 text-gray-600">{i + 1}</td>
                  <td className="px-4 py-2 text-gray-100">{subject.full_name}</td>
                  <td className="px-4 py-2 text-gray-500">{subject.class_group ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
