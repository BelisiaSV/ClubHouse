"use client";

import { useMemo, useState } from "react";
import type { AthleteLite } from "./ExceptionDialog";
import { MEAL_WEEKDAYS, type MealException, type MealFreeDay, type MealPlan, getMealForDay, toDateStr } from "@/lib/meals";

interface MonthOverviewTabProps {
  athletes: AthleteLite[];
  plans: MealPlan[];
  exceptions: MealException[];
  freeDays: MealFreeDay[];
}

const MONTH_NAMES = [
  "januari", "februari", "maart", "april", "mei", "juni",
  "juli", "augustus", "september", "oktober", "november", "december",
];

/** Per-athlete meal totals for one calendar month — for the school's own bookkeeping. */
export default function MonthOverviewTab({ athletes, plans, exceptions, freeDays }: MonthOverviewTabProps) {
  const now = new Date();
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth() + 1);

  const schoolDays = useMemo(() => {
    const daysInMonth = new Date(year, month, 0).getDate();
    const result: string[] = [];
    for (let day = 1; day <= daysInMonth; day++) {
      const date = new Date(year, month - 1, day);
      if ((MEAL_WEEKDAYS as readonly number[]).includes(date.getDay())) result.push(toDateStr(date));
    }
    return result;
  }, [year, month]);

  const rows = useMemo(() => {
    const sorted = [...athletes].sort((a, b) => a.full_name.localeCompare(b.full_name));
    return sorted.map((athlete) => {
      let s = 0;
      let v = 0;
      let gv = 0;
      schoolDays.forEach((dateStr) => {
        const code = getMealForDay(athlete.id, dateStr, plans, exceptions, freeDays);
        if (code === "s") s++;
        else if (code === "v") v++;
        else if (code === "gv") gv++;
      });
      return { athlete, s, v, gv, total: s + v + gv };
    });
  }, [athletes, schoolDays, plans, exceptions, freeDays]);

  const grandTotal = rows.reduce(
    (acc, r) => ({ s: acc.s + r.s, v: acc.v + r.v, gv: acc.gv + r.gv, total: acc.total + r.total }),
    { s: 0, v: 0, gv: 0, total: 0 }
  );

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-end gap-3">
        <label className="flex flex-col text-sm text-gray-300">
          Maand
          <select value={month} onChange={(e) => setMonth(Number(e.target.value))} className={selectClass}>
            {MONTH_NAMES.map((name, i) => (
              <option key={name} value={i + 1}>
                {name.charAt(0).toUpperCase() + name.slice(1)}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col text-sm text-gray-300">
          Jaar
          <select value={year} onChange={(e) => setYear(Number(e.target.value))} className={selectClass}>
            {[now.getFullYear() - 1, now.getFullYear(), now.getFullYear() + 1].map((y) => (
              <option key={y} value={y}>
                {y}
              </option>
            ))}
          </select>
        </label>
        <span className="pb-2 text-xs text-gray-500">{schoolDays.length} schooldagen</span>
      </div>

      <div className="overflow-x-auto rounded-2xl border border-white/10 bg-gray-900/60 shadow-xl shadow-black/20">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-white/10 text-xs uppercase tracking-wide text-gray-500">
              <th className="px-4 py-3 font-medium">Leerling</th>
              <th className="px-4 py-3 text-center font-medium text-sky-400">S</th>
              <th className="px-4 py-3 text-center font-medium text-emerald-400">V</th>
              <th className="px-4 py-3 text-center font-medium text-amber-400">GV</th>
              <th className="px-4 py-3 text-center font-medium">Totaal</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/5">
            {rows.map(({ athlete, s, v, gv, total }) => (
              <tr key={athlete.id}>
                <td className="px-4 py-2.5 text-gray-100">{athlete.full_name}</td>
                <td className="px-4 py-2.5 text-center text-sky-300">{s || ""}</td>
                <td className="px-4 py-2.5 text-center text-emerald-300">{v || ""}</td>
                <td className="px-4 py-2.5 text-center text-amber-300">{gv || ""}</td>
                <td className="px-4 py-2.5 text-center font-semibold text-white">{total || "0"}</td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr className="border-t border-white/10 font-semibold">
              <td className="px-4 py-3 text-gray-200">Totaal</td>
              <td className="px-4 py-3 text-center text-sky-400">{grandTotal.s}</td>
              <td className="px-4 py-3 text-center text-emerald-400">{grandTotal.v}</td>
              <td className="px-4 py-3 text-center text-amber-400">{grandTotal.gv}</td>
              <td className="px-4 py-3 text-center text-emerald-400">{grandTotal.total}</td>
            </tr>
          </tfoot>
        </table>
      </div>
    </div>
  );
}

const selectClass =
  "mt-1 rounded-lg border border-white/10 bg-gray-950 px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-emerald-500";
