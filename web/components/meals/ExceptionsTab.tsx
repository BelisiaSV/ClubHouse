"use client";

import { type FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase/client";
import ExceptionDialog, { type AthleteLite } from "./ExceptionDialog";
import MealPill from "./MealPill";
import type { MealException, MealFreeDay } from "@/lib/meals";

interface ExceptionsTabProps {
  athletes: AthleteLite[];
  exceptions: MealException[];
  freeDays: MealFreeDay[];
}

const TYPE_LABEL: Record<string, string> = {
  ziek: "Ziek",
  afwezig_schoolreis_stage: "Afwezig — schoolreis / stage",
  afwezig_andere: "Afwezig — andere reden",
  eenmalige_maaltijd: "Eenmalige maaltijd",
  stopt_tijdelijk: "Stopt tijdelijk",
  heropstart: "Heropstart",
  andere: "Andere",
};

export default function ExceptionsTab({ athletes, exceptions, freeDays }: ExceptionsTabProps) {
  const router = useRouter();
  const [sub, setSub] = useState<"exc" | "vrij">("exc");
  const [showExcDialog, setShowExcDialog] = useState(false);
  const [showFdForm, setShowFdForm] = useState(false);
  const [fdDate, setFdDate] = useState("");
  const [fdDescription, setFdDescription] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const athleteNameById = new Map(athletes.map((a) => [a.id, a.full_name]));

  const handleAddFreeDay = async (event: FormEvent) => {
    event.preventDefault();
    if (!fdDate) return;
    setSubmitting(true);

    const supabase = createClient();
    const {
      data: { user },
    } = await supabase.auth.getUser();
    await supabase.from("meal_free_days").insert({ free_date: fdDate, description: fdDescription.trim() || null, created_by: user?.id });

    setFdDate("");
    setFdDescription("");
    setShowFdForm(false);
    setSubmitting(false);
    router.refresh();
  };

  const handleDeleteFreeDay = async (id: string) => {
    const supabase = createClient();
    await supabase.from("meal_free_days").delete().eq("id", id);
    router.refresh();
  };

  return (
    <div>
      <div className="mb-4 flex gap-2">
        <button type="button" onClick={() => setSub("exc")} className={subTabClass(sub === "exc")}>
          Uitzonderingen ({exceptions.length})
        </button>
        <button type="button" onClick={() => setSub("vrij")} className={subTabClass(sub === "vrij")}>
          Vrije schooldagen ({freeDays.length})
        </button>
      </div>

      {sub === "exc" ? (
        <div>
          <div className="mb-3 flex items-center justify-between">
            <p className="text-sm text-gray-500">Afwezigheden &amp; eenmalige maaltijden.</p>
            <button
              type="button"
              onClick={() => setShowExcDialog(true)}
              className="rounded-lg bg-emerald-600 px-3.5 py-2 text-sm font-medium text-white transition hover:bg-emerald-500"
            >
              + Nieuwe uitzondering
            </button>
          </div>
          <div className="overflow-x-auto rounded-2xl border border-white/10 bg-gray-900/60 shadow-xl shadow-black/20">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-white/10 text-xs uppercase tracking-wide text-gray-500">
                  <th className="px-4 py-3 font-medium">Leerling</th>
                  <th className="px-4 py-3 font-medium">Type</th>
                  <th className="px-4 py-3 font-medium">Van</th>
                  <th className="px-4 py-3 font-medium">Tot</th>
                  <th className="px-4 py-3 text-center font-medium">Code</th>
                  <th className="px-4 py-3 font-medium">Opmerking</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {[...exceptions]
                  .sort((a, b) => b.date_from.localeCompare(a.date_from))
                  .map((exc) => (
                    <tr key={exc.id}>
                      <td className="px-4 py-2.5 text-gray-100">{athleteNameById.get(exc.athlete_id) ?? "—"}</td>
                      <td className="px-4 py-2.5 text-gray-400">{TYPE_LABEL[exc.exception_type] ?? exc.exception_type}</td>
                      <td className="px-4 py-2.5 text-gray-400">{exc.date_from}</td>
                      <td className="px-4 py-2.5 text-gray-500">{exc.date_to && exc.date_to !== exc.date_from ? exc.date_to : "—"}</td>
                      <td className="px-4 py-2.5 text-center">
                        <MealPill code={exc.meal_code} />
                      </td>
                      <td className="px-4 py-2.5 text-gray-500">{exc.note ?? "—"}</td>
                    </tr>
                  ))}
                {exceptions.length === 0 && (
                  <tr>
                    <td colSpan={6} className="px-4 py-10 text-center text-sm text-gray-500">
                      Nog geen uitzonderingen.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      ) : (
        <div>
          <div className="mb-3 flex items-center justify-between">
            <p className="text-sm text-gray-500">Dagen waarop de school geen warme maaltijden aanbiedt.</p>
            <button
              type="button"
              onClick={() => setShowFdForm((v) => !v)}
              className="rounded-lg bg-emerald-600 px-3.5 py-2 text-sm font-medium text-white transition hover:bg-emerald-500"
            >
              {showFdForm ? "Annuleren" : "+ Vrije dag toevoegen"}
            </button>
          </div>

          {showFdForm && (
            <form onSubmit={handleAddFreeDay} className="mb-4 flex flex-wrap items-end gap-3 rounded-xl border border-white/10 bg-gray-900/60 p-4">
              <label className="flex flex-col text-sm text-gray-300">
                Datum
                <input type="date" required value={fdDate} onChange={(e) => setFdDate(e.target.value)} className={fieldClass} />
              </label>
              <label className="flex flex-1 flex-col text-sm text-gray-300">
                Omschrijving
                <input
                  type="text"
                  value={fdDescription}
                  onChange={(e) => setFdDescription(e.target.value)}
                  placeholder="bv. Wapenstilstand, studiedag, ..."
                  className={fieldClass}
                />
              </label>
              <button
                type="submit"
                disabled={submitting}
                className="rounded-lg bg-emerald-600 px-3.5 py-2 text-sm font-medium text-white transition hover:bg-emerald-500 disabled:cursor-not-allowed disabled:opacity-50"
              >
                Opslaan
              </button>
            </form>
          )}

          <div className="overflow-x-auto rounded-2xl border border-white/10 bg-gray-900/60 shadow-xl shadow-black/20">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-white/10 text-xs uppercase tracking-wide text-gray-500">
                  <th className="px-4 py-3 font-medium">Datum</th>
                  <th className="px-4 py-3 font-medium">Omschrijving</th>
                  <th className="px-4 py-3 font-medium" />
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {[...freeDays]
                  .sort((a, b) => a.free_date.localeCompare(b.free_date))
                  .map((fd) => (
                    <tr key={fd.id}>
                      <td className="px-4 py-2.5 text-gray-100">{fd.free_date}</td>
                      <td className="px-4 py-2.5 text-gray-400">{fd.description ?? "—"}</td>
                      <td className="px-4 py-2.5 text-right">
                        <button type="button" onClick={() => handleDeleteFreeDay(fd.id)} className="text-xs text-gray-500 hover:text-red-400">
                          Verwijderen
                        </button>
                      </td>
                    </tr>
                  ))}
                {freeDays.length === 0 && (
                  <tr>
                    <td colSpan={3} className="px-4 py-10 text-center text-sm text-gray-500">
                      Nog geen vrije dagen.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {showExcDialog && <ExceptionDialog athletes={athletes} onClose={() => setShowExcDialog(false)} />}
    </div>
  );
}

function subTabClass(active: boolean) {
  return `rounded-lg px-3.5 py-2 text-sm font-medium ${
    active ? "bg-emerald-600 text-white" : "border border-white/10 text-gray-400 hover:bg-white/5"
  }`;
}

const fieldClass =
  "mt-1 rounded-lg border border-white/10 bg-gray-950 px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-emerald-500";
