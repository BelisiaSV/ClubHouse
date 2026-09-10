"use client";

import { type FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase/client";
import type { MealCode, MealExceptionType } from "@/types/database";
import type { MealException } from "@/lib/meals";

export interface AthleteLite {
  id: string;
  full_name: string;
  class_group: string | null;
}

interface ExceptionDialogProps {
  athletes: AthleteLite[];
  fixedAthleteId?: string;
  defaultDate?: string;
  existing?: MealException[];
  onClose: () => void;
}

const TYPE_OPTIONS: { value: MealExceptionType; label: string }[] = [
  { value: "ziek", label: "Ziek" },
  { value: "afwezig_schoolreis_stage", label: "Afwezig — schoolreis / stage" },
  { value: "afwezig_andere", label: "Afwezig — andere reden" },
  { value: "eenmalige_maaltijd", label: "Eenmalige maaltijd" },
  { value: "stopt_tijdelijk", label: "Stopt tijdelijk" },
  { value: "heropstart", label: "Heropstart" },
  { value: "andere", label: "Andere" },
];

const CODE_OPTIONS: { value: MealCode; label: string }[] = [
  { value: "", label: "∅ geen maaltijd" },
  { value: "s", label: "s — standaard" },
  { value: "v", label: "v — vegetarisch" },
  { value: "gv", label: "gv — geen varkensvlees" },
];

/** Shared add/edit-exception modal — opened both from a Weekplanning grid
 * cell click (fixedAthleteId + defaultDate set) and from the Uitzonderingen
 * tab's "+ Nieuwe uitzondering" button (athlete picked in the form). */
export default function ExceptionDialog({ athletes, fixedAthleteId, defaultDate, existing, onClose }: ExceptionDialogProps) {
  const router = useRouter();
  const [athleteId, setAthleteId] = useState(fixedAthleteId ?? "");
  const [exceptionType, setExceptionType] = useState<MealExceptionType>("ziek");
  const [mealCode, setMealCode] = useState<MealCode>("");
  const [dateFrom, setDateFrom] = useState(defaultDate ?? "");
  const [dateTo, setDateTo] = useState(defaultDate ?? "");
  const [note, setNote] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fixedAthlete = fixedAthleteId ? athletes.find((a) => a.id === fixedAthleteId) : null;

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    if (!athleteId || !dateFrom) return;

    setSubmitting(true);
    setError(null);

    const supabase = createClient();
    const {
      data: { user },
    } = await supabase.auth.getUser();

    const { error: insertError } = await supabase.from("meal_exceptions").insert({
      athlete_id: athleteId,
      exception_type: exceptionType,
      meal_code: mealCode,
      date_from: dateFrom,
      date_to: dateTo || null,
      note: note.trim() || null,
      registered_by: user?.id,
    });

    if (insertError) {
      setError("Opslaan mislukt. Probeer opnieuw.");
      setSubmitting(false);
      return;
    }

    router.refresh();
    onClose();
  };

  const handleDelete = async (id: string) => {
    const supabase = createClient();
    await supabase.from("meal_exceptions").delete().eq("id", id);
    router.refresh();
  };

  return (
    <div className="fixed inset-0 z-30 flex items-start justify-center overflow-y-auto bg-black/60 p-5" onClick={onClose}>
      <div
        className="w-full max-w-md rounded-2xl border border-white/10 bg-gray-900 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-white/10 px-5 py-4">
          <h2 className="text-sm font-semibold text-white">
            Uitzondering{fixedAthlete ? ` — ${fixedAthlete.full_name}` : ""}
          </h2>
          <button type="button" onClick={onClose} className="text-gray-500 hover:text-gray-300">
            ×
          </button>
        </div>

        <div className="space-y-4 p-5">
          {existing && existing.length > 0 && (
            <div className="space-y-2 rounded-xl border border-white/10 bg-gray-950/60 p-3">
              <p className="text-xs font-semibold text-gray-400">Bestaande uitzondering(en)</p>
              {existing.map((exc) => (
                <div key={exc.id} className="flex items-center justify-between gap-2 text-xs text-gray-300">
                  <span>
                    {TYPE_OPTIONS.find((t) => t.value === exc.exception_type)?.label ?? exc.exception_type} · {exc.date_from}
                    {exc.date_to && exc.date_to !== exc.date_from ? ` t.e.m. ${exc.date_to}` : ""}
                  </span>
                  <button type="button" onClick={() => handleDelete(exc.id)} className="text-red-400 hover:opacity-80">
                    verwijderen
                  </button>
                </div>
              ))}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-3">
            {!fixedAthlete && (
              <label className="flex flex-col text-sm text-gray-300">
                Leerling
                <select value={athleteId} onChange={(e) => setAthleteId(e.target.value)} required className={fieldClass}>
                  <option value="">— kies leerling —</option>
                  {athletes.map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.full_name} {a.class_group ? `(${a.class_group})` : ""}
                    </option>
                  ))}
                </select>
              </label>
            )}
            <label className="flex flex-col text-sm text-gray-300">
              Type
              <select
                value={exceptionType}
                onChange={(e) => setExceptionType(e.target.value as MealExceptionType)}
                className={fieldClass}
              >
                {TYPE_OPTIONS.map((t) => (
                  <option key={t.value} value={t.value}>
                    {t.label}
                  </option>
                ))}
              </select>
            </label>
            <div className="grid grid-cols-2 gap-3">
              <label className="flex flex-col text-sm text-gray-300">
                Van
                <input type="date" required value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} className={fieldClass} />
              </label>
              <label className="flex flex-col text-sm text-gray-300">
                Tot (leeg = open)
                <input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} className={fieldClass} />
              </label>
            </div>
            <label className="flex flex-col text-sm text-gray-300">
              Maaltijdcode
              <select value={mealCode} onChange={(e) => setMealCode(e.target.value as MealCode)} className={fieldClass}>
                {CODE_OPTIONS.map((c) => (
                  <option key={c.value} value={c.value}>
                    {c.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="flex flex-col text-sm text-gray-300">
              Opmerking
              <input
                type="text"
                value={note}
                onChange={(e) => setNote(e.target.value)}
                placeholder="bv. mama belde, arts-bezoek, ..."
                className={fieldClass}
              />
            </label>
            {error && <p className="text-sm text-red-400">{error}</p>}
            <div className="flex justify-end gap-3 pt-2">
              <button type="button" onClick={onClose} className="rounded-lg border border-white/10 px-3.5 py-2 text-sm text-gray-300 hover:bg-white/5">
                Annuleren
              </button>
              <button
                type="submit"
                disabled={submitting}
                className="rounded-lg bg-emerald-600 px-3.5 py-2 text-sm font-medium text-white transition hover:bg-emerald-500 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {submitting ? "Bezig…" : "Opslaan"}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}

const fieldClass =
  "mt-1 w-full rounded-lg border border-white/10 bg-gray-950 px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-emerald-500";
