"use client";

import { type FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase/client";
import MealPill from "@/components/meals/MealPill";
import type { MealCode } from "@/types/database";
import type { MealPlan } from "@/lib/meals";

const DAY_FIELDS: { key: "monday_code" | "tuesday_code" | "thursday_code" | "friday_code"; label: string }[] = [
  { key: "monday_code", label: "Maandag" },
  { key: "tuesday_code", label: "Dinsdag" },
  { key: "thursday_code", label: "Donderdag" },
  { key: "friday_code", label: "Vrijdag" },
];

const CODE_OPTIONS: { value: MealCode; label: string }[] = [
  { value: "", label: "∅" },
  { value: "s", label: "s" },
  { value: "v", label: "v" },
  { value: "gv", label: "gv" },
];

/**
 * The athlete's weekly warme-maaltijden plan — which of Mon/Tue/Thu/Fri
 * they eat, and which meal code. Versioned: a new row per change rather
 * than mutating the old one, so /meals's Wijzigingen tab keeps a full
 * history. Feeds the cross-athlete Meals module (see app/(dashboard)/
 * meals) — this is the per-athlete setup half of it.
 */
export default function AthleteMealPlan({ athleteId, plans }: { athleteId: string; plans: MealPlan[] }) {
  const router = useRouter();
  const [showForm, setShowForm] = useState(false);
  const [effectiveFrom, setEffectiveFrom] = useState("");
  const [codes, setCodes] = useState<Record<string, MealCode>>({
    monday_code: "s",
    tuesday_code: "s",
    thursday_code: "s",
    friday_code: "s",
  });
  const [reason, setReason] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const sortedPlans = [...plans].sort((a, b) => b.effective_from.localeCompare(a.effective_from));

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    if (!effectiveFrom) return;

    setSubmitting(true);
    setError(null);

    const supabase = createClient();
    const {
      data: { user },
    } = await supabase.auth.getUser();

    const { error: insertError } = await supabase.from("meal_plans").insert({
      athlete_id: athleteId,
      effective_from: effectiveFrom,
      monday_code: codes.monday_code,
      tuesday_code: codes.tuesday_code,
      thursday_code: codes.thursday_code,
      friday_code: codes.friday_code,
      reason: reason.trim() || null,
      created_by: user?.id,
    });

    if (insertError) {
      setError("Opslaan mislukt — bestaat er al een planversie op deze datum?");
      setSubmitting(false);
      return;
    }

    setEffectiveFrom("");
    setReason("");
    setShowForm(false);
    setSubmitting(false);
    router.refresh();
  };

  return (
    <div className="rounded-2xl border border-white/10 bg-gray-900/60 p-5 shadow-xl shadow-black/20">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-white">Maaltijdplanning</h2>
        <button type="button" onClick={() => setShowForm((v) => !v)} className="text-xs font-medium text-emerald-400 hover:opacity-80">
          {showForm ? "Annuleren" : "+ Planningswijziging"}
        </button>
      </div>

      {showForm && (
        <form onSubmit={handleSubmit} className="mb-4 space-y-3 rounded-xl border border-white/10 bg-gray-950/60 p-4">
          <label className="flex flex-col text-sm text-gray-300">
            Geldig vanaf
            <input
              type="date"
              required
              value={effectiveFrom}
              onChange={(e) => setEffectiveFrom(e.target.value)}
              className={fieldClass}
            />
          </label>
          <div className="space-y-2">
            {DAY_FIELDS.map(({ key, label }) => (
              <div key={key} className="flex items-center gap-3">
                <span className="w-20 text-sm text-gray-400">{label}</span>
                <div className="flex gap-1.5">
                  {CODE_OPTIONS.map((opt) => (
                    <button
                      key={opt.value}
                      type="button"
                      onClick={() => setCodes((c) => ({ ...c, [key]: opt.value }))}
                      className={`rounded-lg border px-2.5 py-1 text-xs font-medium ${
                        codes[key] === opt.value
                          ? "border-emerald-500 bg-emerald-600 text-white"
                          : "border-white/10 text-gray-400 hover:bg-white/5"
                      }`}
                    >
                      {opt.label}
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </div>
          <label className="flex flex-col text-sm text-gray-300">
            Reden voor wijziging
            <input
              type="text"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="bv. Overschakeling naar vegetarisch"
              className={fieldClass}
            />
          </label>
          {error && <p className="text-sm text-red-400">{error}</p>}
          <button
            type="submit"
            disabled={submitting}
            className="rounded-lg bg-emerald-600 px-3.5 py-2 text-sm font-medium text-white transition hover:bg-emerald-500 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {submitting ? "Bezig…" : "Opslaan"}
          </button>
        </form>
      )}

      {sortedPlans.length === 0 ? (
        <p className="text-sm text-gray-500">Nog geen maaltijdplanning ingesteld.</p>
      ) : (
        <ul className="space-y-3 border-l-2 border-emerald-600 pl-4">
          {sortedPlans.map((plan, i) => (
            <li key={plan.id} className="relative">
              <div className="flex items-center gap-2 text-xs text-gray-500">
                {plan.effective_from}
                {i === 0 && (
                  <span className="rounded-full bg-emerald-500/15 px-2 py-0.5 text-[10px] font-semibold text-emerald-400">huidig</span>
                )}
              </div>
              <div className="mt-1 flex gap-3 text-xs">
                {DAY_FIELDS.map(({ key, label }) => (
                  <span key={key} className="flex items-center gap-1 text-gray-400">
                    {label.slice(0, 2)}:<MealPill code={plan[key]} />
                  </span>
                ))}
              </div>
              {plan.reason && <p className="mt-1 text-xs italic text-gray-500">{plan.reason}</p>}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

const fieldClass =
  "mt-1 w-full rounded-lg border border-white/10 bg-gray-950 px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-emerald-500";
