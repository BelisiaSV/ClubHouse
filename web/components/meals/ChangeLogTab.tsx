"use client";

import { useMemo } from "react";
import MealPill from "./MealPill";
import type { AthleteLite } from "./ExceptionDialog";
import { subjectId, type MealException, type MealPlan } from "@/lib/meals";

interface ChangeLogTabProps {
  athletes: AthleteLite[];
  plans: MealPlan[];
  exceptions: MealException[];
}

const EXCEPTION_LABEL: Record<string, string> = {
  ziek: "Ziek",
  afwezig_schoolreis_stage: "Afwezig — schoolreis / stage",
  afwezig_andere: "Afwezig — andere reden",
  eenmalige_maaltijd: "Eenmalige maaltijd",
  stopt_tijdelijk: "Stopt tijdelijk",
  heropstart: "Heropstart",
  andere: "Andere",
  eigen_lunchpakket: "Eigen lunchpakket (internaat gesloten)",
};

type ChangeRow =
  | { kind: "plan"; date: string; sortKey: string; athleteId: string; reason: string | null; plan: MealPlan }
  | { kind: "exception"; date: string; sortKey: string; athleteId: string; reason: string | null; exception: MealException };

/** Full audit trail for bookkeeping: every plan version + every exception, newest first. */
export default function ChangeLogTab({ athletes, plans, exceptions }: ChangeLogTabProps) {
  const athleteById = new Map(athletes.map((a) => [a.id, a]));

  const changes: ChangeRow[] = useMemo(() => {
    const planRows: ChangeRow[] = plans.map((p) => ({
      kind: "plan",
      date: p.effective_from,
      sortKey: p.created_at,
      athleteId: subjectId(p),
      reason: p.reason,
      plan: p,
    }));
    const exceptionRows: ChangeRow[] = exceptions.map((e) => ({
      kind: "exception",
      date: e.date_from,
      sortKey: e.created_at,
      athleteId: subjectId(e),
      reason: e.note,
      exception: e,
    }));
    return [...planRows, ...exceptionRows].sort((a, b) => b.date.localeCompare(a.date) || b.sortKey.localeCompare(a.sortKey));
  }, [plans, exceptions]);

  return (
    <div>
      <div className="mb-4 rounded-lg border border-sky-500/20 bg-sky-500/10 px-3.5 py-2.5 text-xs text-sky-300">
        Volledige historiek voor de boekhouding — alle planversies en uitzonderingen.
      </div>
      <div className="overflow-x-auto rounded-2xl border border-white/10 bg-gray-900/60 shadow-xl shadow-black/20">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-white/10 text-xs uppercase tracking-wide text-gray-500">
              <th className="px-4 py-3 font-medium">Datum</th>
              <th className="px-4 py-3 font-medium">Type</th>
              <th className="px-4 py-3 font-medium">Leerling</th>
              <th className="px-4 py-3 font-medium">Planning</th>
              <th className="px-4 py-3 font-medium">Reden / opmerking</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/5">
            {changes.map((change) => {
              const athlete = athleteById.get(change.athleteId);
              return (
                <tr key={`${change.kind}-${change.kind === "plan" ? change.plan.id : change.exception.id}`}>
                  <td className="whitespace-nowrap px-4 py-2.5 text-gray-100">{change.date}</td>
                  <td className="px-4 py-2.5">
                    {change.kind === "plan" ? (
                      <span className="rounded-full bg-sky-500/15 px-2 py-0.5 text-[11px] font-medium text-sky-300">Planwijziging</span>
                    ) : (
                      <span className="rounded-full bg-amber-500/15 px-2 py-0.5 text-[11px] font-medium text-amber-300">
                        {EXCEPTION_LABEL[change.exception.exception_type] ?? change.exception.exception_type}
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-2.5 text-gray-200">{athlete?.full_name ?? "—"}</td>
                  <td className="px-4 py-2.5">
                    {change.kind === "plan" ? (
                      <div className="flex gap-2 text-xs">
                        <span>MA:{<MealPill code={change.plan.monday_code} />}</span>
                        <span>DI:{<MealPill code={change.plan.tuesday_code} />}</span>
                        <span>DO:{<MealPill code={change.plan.thursday_code} />}</span>
                        <span>VR:{<MealPill code={change.plan.friday_code} />}</span>
                      </div>
                    ) : (
                      <MealPill code={change.exception.meal_code} />
                    )}
                  </td>
                  <td className="px-4 py-2.5 text-gray-500">{change.reason ?? "—"}</td>
                </tr>
              );
            })}
            {changes.length === 0 && (
              <tr>
                <td colSpan={5} className="px-4 py-10 text-center text-sm text-gray-500">
                  Nog geen wijzigingen.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
