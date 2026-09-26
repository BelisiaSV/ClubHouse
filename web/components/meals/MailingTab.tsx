"use client";

import { useMemo, useState } from "react";
import type { AthleteLite } from "./ExceptionDialog";
import { addDays, countDay, getMondayOf, toDateStr, weekMealDays, type MealException, type MealFreeDay, type MealPlan } from "@/lib/meals";

interface MailingTabProps {
  athletes: AthleteLite[];
  plans: MealPlan[];
  exceptions: MealException[];
  freeDays: MealFreeDay[];
}

const DAY_NAME: Record<number, string> = { 1: "MAANDAG", 2: "DINSDAG", 4: "DONDERDAG", 5: "VRIJDAG" };

/** Generates the weekly count e-mail text catering/kitchen staff need. */
export default function MailingTab({ athletes, plans, exceptions, freeDays }: MailingTabProps) {
  const [monday, setMonday] = useState(() => addDays(getMondayOf(new Date()), 7));
  const [copied, setCopied] = useState(false);

  const days = useMemo(() => weekMealDays(monday), [monday]);
  const athleteIds = useMemo(() => athletes.map((a) => a.id), [athletes]);
  const dayData = useMemo(
    () => days.map((d) => ({ date: d, totals: countDay(athleteIds, toDateStr(d), plans, exceptions, freeDays) })),
    [days, athleteIds, plans, exceptions, freeDays]
  );
  const weekTotal = dayData.reduce(
    (acc, { totals }) => ({ s: acc.s + totals.s, v: acc.v + totals.v, gv: acc.gv + totals.gv, total: acc.total + totals.total }),
    { s: 0, v: 0, gv: 0, total: 0 }
  );

  const mailText = useMemo(() => {
    const lines = [
      `Beste,`,
      ``,
      `Gelieve hieronder de aantallen warme maaltijden te vinden voor de week van ${toDateStr(days[0])} t.e.m. ${toDateStr(days[3])}:`,
      ``,
      ...dayData.flatMap(({ date, totals }) => {
        if (totals.vrij) return [`${DAY_NAME[date.getDay()]} ${toDateStr(date)} — vrije dag`, ``];
        return [
          `${DAY_NAME[date.getDay()]} ${toDateStr(date)}`,
          `  Standaard:          ${String(totals.s).padStart(3)}`,
          `  Vegetarisch:        ${String(totals.v).padStart(3)}`,
          `  Geen varkensvlees:  ${String(totals.gv).padStart(3)}`,
          `  ──────────────────────`,
          `  Totaal:             ${String(totals.total).padStart(3)}`,
          ``,
        ];
      }),
      `TOTAAL WEEK`,
      `  Standaard:          ${String(weekTotal.s).padStart(3)}`,
      `  Vegetarisch:        ${String(weekTotal.v).padStart(3)}`,
      `  Geen varkensvlees:  ${String(weekTotal.gv).padStart(3)}`,
      `  ──────────────────────`,
      `  Totaal:             ${String(weekTotal.total).padStart(3)}`,
      ``,
      `Met vriendelijke groeten,`,
    ];
    return lines.join("\n");
  }, [dayData, days, weekTotal]);

  const handleCopy = async () => {
    await navigator.clipboard?.writeText(mailText);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <button type="button" onClick={() => setMonday(addDays(monday, -7))} className={navBtnClass}>
          ← vorige week
        </button>
        <span className="rounded-lg border border-white/10 bg-gray-900/60 px-3.5 py-1.5 text-sm text-gray-300">
          {toDateStr(days[0])} – {toDateStr(days[3])}
        </span>
        <button type="button" onClick={() => setMonday(addDays(monday, 7))} className={navBtnClass}>
          volgende week →
        </button>
        <button
          type="button"
          onClick={handleCopy}
          className="ml-auto rounded-lg bg-emerald-600 px-3.5 py-2 text-sm font-medium text-white transition hover:bg-emerald-500"
        >
          {copied ? "Gekopieerd ✓" : "Kopieer mailtekst"}
        </button>
      </div>

      <div className="mb-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
        {dayData.map(({ date, totals }) => (
          <div key={toDateStr(date)} className="rounded-xl border border-white/10 bg-gray-900/60 p-3.5">
            <div className="mb-2 flex items-center justify-between">
              <strong className="text-sm text-white">
                {DAY_NAME[date.getDay()].slice(0, 2)} {toDateStr(date).slice(5)}
              </strong>
              {totals.vrij ? (
                <span className="rounded-full bg-gray-700/50 px-2 py-0.5 text-[10px] text-gray-400">vrij</span>
              ) : (
                <span className="text-base font-bold text-emerald-400">{totals.total}</span>
              )}
            </div>
            {!totals.vrij && (
              <div className="space-y-1 text-xs">
                <div className="flex justify-between text-sky-300">
                  <span>s</span>
                  <span>{totals.s}</span>
                </div>
                <div className="flex justify-between text-emerald-300">
                  <span>v</span>
                  <span>{totals.v}</span>
                </div>
                <div className="flex justify-between text-amber-300">
                  <span>gv</span>
                  <span>{totals.gv}</span>
                </div>
              </div>
            )}
          </div>
        ))}
      </div>

      <div className="rounded-2xl border border-white/10 bg-gray-900/60 p-5 shadow-xl shadow-black/20">
        <h2 className="mb-2 text-sm font-semibold text-white">Mailtekst</h2>
        <pre className="max-h-72 overflow-y-auto whitespace-pre-wrap rounded-xl border border-white/5 bg-gray-950/60 p-4 font-mono text-xs text-gray-300">
          {mailText}
        </pre>
      </div>
    </div>
  );
}

const navBtnClass = "rounded-lg border border-white/10 px-3 py-1.5 text-xs font-medium text-gray-300 hover:bg-white/5";
