"use client";

import { type FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase/client";
import type { Database } from "@/types/database";

type CustomField = Database["public"]["Tables"]["athlete_custom_fields"]["Row"];

/**
 * Free-form "add anything else" label/value list per athlete — the escape
 * hatch for whatever the fixed profile fields don't cover (see
 * athlete_custom_fields in supabase/migrations/0001_init.sql).
 */
export default function AthleteCustomFields({ athleteId, fields }: { athleteId: string; fields: CustomField[] }) {
  const router = useRouter();
  const [label, setLabel] = useState("");
  const [value, setValue] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleAdd = async (event: FormEvent) => {
    event.preventDefault();
    if (!label.trim()) return;

    setSubmitting(true);
    setError(null);

    const supabase = createClient();
    const {
      data: { user },
    } = await supabase.auth.getUser();

    const { error: insertError } = await supabase.from("athlete_custom_fields").insert({
      athlete_id: athleteId,
      label: label.trim(),
      value: value.trim() || null,
      created_by: user?.id,
    });

    if (insertError) {
      setError("Toevoegen mislukt. Probeer opnieuw.");
      setSubmitting(false);
      return;
    }

    setLabel("");
    setValue("");
    setSubmitting(false);
    router.refresh();
  };

  const handleDelete = async (id: string) => {
    const supabase = createClient();
    await supabase.from("athlete_custom_fields").delete().eq("id", id);
    router.refresh();
  };

  return (
    <div className="rounded-2xl border border-white/10 bg-gray-900/60 p-5 shadow-xl shadow-black/20">
      <h2 className="mb-4 text-sm font-semibold text-white">Extra velden</h2>

      {fields.length === 0 ? (
        <p className="mb-4 text-sm text-gray-500">Nog geen extra velden toegevoegd.</p>
      ) : (
        <ul className="mb-4 space-y-2">
          {fields.map((field) => (
            <li key={field.id} className="flex items-start justify-between gap-3 rounded-xl border border-white/5 bg-gray-950/40 p-3 text-sm">
              <div>
                <p className="font-medium text-gray-100">{field.label}</p>
                {field.value && <p className="text-gray-400">{field.value}</p>}
              </div>
              <button
                type="button"
                onClick={() => handleDelete(field.id)}
                className="shrink-0 text-xs text-gray-500 hover:text-red-400"
              >
                Verwijderen
              </button>
            </li>
          ))}
        </ul>
      )}

      <form onSubmit={handleAdd} className="flex flex-col gap-2 sm:flex-row">
        <input
          type="text"
          placeholder="Label"
          value={label}
          onChange={(e) => setLabel(e.target.value)}
          className="flex-1 rounded-lg border border-white/10 bg-gray-950 px-3 py-2 text-sm text-white placeholder:text-gray-500 focus:outline-none focus:ring-2 focus:ring-emerald-500"
        />
        <input
          type="text"
          placeholder="Waarde"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          className="flex-1 rounded-lg border border-white/10 bg-gray-950 px-3 py-2 text-sm text-white placeholder:text-gray-500 focus:outline-none focus:ring-2 focus:ring-emerald-500"
        />
        <button
          type="submit"
          disabled={submitting || !label.trim()}
          className="shrink-0 rounded-lg bg-emerald-600 px-3.5 py-2 text-sm font-medium text-white transition hover:bg-emerald-500 disabled:cursor-not-allowed disabled:opacity-50"
        >
          Toevoegen
        </button>
      </form>
      {error && <p className="mt-2 text-sm text-red-400">{error}</p>}
    </div>
  );
}
