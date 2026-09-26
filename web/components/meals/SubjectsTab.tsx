"use client";

import { Fragment, type FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase/client";
import SubjectMealPlanEditor from "./SubjectMealPlanEditor";
import type { Database } from "@/types/database";
import type { MealPlan } from "@/lib/meals";

type ExternalAthlete = Database["public"]["Tables"]["external_athletes"]["Row"];
type OtherStudent = Database["public"]["Tables"]["other_students"]["Row"];
type ManagedKind = "external_athlete" | "other_student";

interface Row {
  id: string;
  kind: ManagedKind;
  full_name: string;
  class_group: string | null;
  is_boarding_student: boolean;
  is_active: boolean;
}

interface SubjectsTabProps {
  externalAthletes: ExternalAthlete[];
  otherStudents: OtherStudent[];
  plans: MealPlan[];
}

interface FormState {
  kind: ManagedKind;
  fullName: string;
  classGroup: string;
  isBoarding: boolean;
}

const EMPTY_FORM: FormState = { kind: "other_student", fullName: "", classGroup: "", isBoarding: false };

const TABLE: Record<ManagedKind, "external_athletes" | "other_students"> = {
  external_athlete: "external_athletes",
  other_student: "other_students",
};

const KIND_LABEL: Record<ManagedKind, string> = {
  external_athlete: "Externe sporter",
  other_student: "Andere leerling",
};

/**
 * "Leerlingen" tab: CRUD on external_athletes/other_students — the two
 * populations that eat warme maaltijden but, unlike topsport athletes,
 * have no profile page elsewhere in the app to manage them from. Topsport
 * athletes stay managed on their own /athletes profile page.
 */
export default function SubjectsTab({ externalAthletes, otherStudents, plans }: SubjectsTabProps) {
  const router = useRouter();
  const [mode, setMode] = useState<"none" | "add" | string>("none");
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);

  const rows: Row[] = [
    ...externalAthletes.map((a) => ({
      id: a.id,
      kind: "external_athlete" as const,
      full_name: a.full_name,
      class_group: a.class_group,
      is_boarding_student: a.is_boarding_student,
      is_active: a.is_active,
    })),
    ...otherStudents.map((a) => ({
      id: a.id,
      kind: "other_student" as const,
      full_name: a.full_name,
      class_group: a.class_group,
      is_boarding_student: a.is_boarding_student,
      is_active: a.is_active,
    })),
  ].sort((a, b) => a.full_name.localeCompare(b.full_name));

  const startAdd = () => {
    setForm(EMPTY_FORM);
    setError(null);
    setMode("add");
  };

  const startEdit = (row: Row) => {
    setForm({ kind: row.kind, fullName: row.full_name, classGroup: row.class_group ?? "", isBoarding: row.is_boarding_student });
    setError(null);
    setMode(row.id);
  };

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    if (!form.fullName.trim()) return;

    setSubmitting(true);
    setError(null);

    const supabase = createClient();
    const payload = {
      full_name: form.fullName.trim(),
      class_group: form.classGroup.trim() || null,
      is_boarding_student: form.isBoarding,
    };

    const { error: writeError } =
      mode === "add"
        ? await supabase.from(TABLE[form.kind]).insert({
            ...payload,
            created_by: (await supabase.auth.getUser()).data.user?.id,
          })
        : await supabase.from(TABLE[form.kind]).update(payload).eq("id", mode);

    if (writeError) {
      setError("Opslaan mislukt. Probeer opnieuw.");
      setSubmitting(false);
      return;
    }

    setMode("none");
    setSubmitting(false);
    router.refresh();
  };

  const setActive = async (row: Row, active: boolean) => {
    const supabase = createClient();
    await supabase.from(TABLE[row.kind]).update({ is_active: active }).eq("id", row.id);
    router.refresh();
  };

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-gray-500">
          Externe sporters en andere leerlingen die ook warme maaltijden eten — topsporters beheer je op hun eigen leerlingprofiel.
        </p>
        <button
          type="button"
          onClick={() => (mode === "add" ? setMode("none") : startAdd())}
          className="rounded-lg bg-emerald-600 px-3.5 py-2 text-sm font-medium text-white transition hover:bg-emerald-500"
        >
          {mode === "add" ? "Annuleren" : "+ Toevoegen"}
        </button>
      </div>

      {mode === "add" && (
        <form onSubmit={handleSubmit} className="mb-4 space-y-3 rounded-xl border border-white/10 bg-gray-900/60 p-4">
          <SubjectFormFields form={form} setForm={setForm} lockKind={false} />
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

      <div className="overflow-hidden rounded-2xl border border-white/10 bg-gray-900/60 shadow-xl shadow-black/20">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-white/10 text-xs uppercase tracking-wide text-gray-500">
              <th className="px-4 py-3 font-medium">Naam</th>
              <th className="px-4 py-3 font-medium">Type</th>
              <th className="px-4 py-3 font-medium">Klas</th>
              <th className="px-4 py-3 font-medium">Internaat</th>
              <th className="px-4 py-3 font-medium" />
            </tr>
          </thead>
          <tbody className="divide-y divide-white/5">
            {rows.map((row) => (
              <Fragment key={row.id}>
                {mode === row.id ? (
                  <tr>
                    <td colSpan={5} className="p-0">
                      <form onSubmit={handleSubmit} className="space-y-3 border-y border-emerald-500/30 bg-gray-950/60 p-4">
                        <SubjectFormFields form={form} setForm={setForm} lockKind />
                        {error && <p className="text-sm text-red-400">{error}</p>}
                        <div className="flex gap-2">
                          <button
                            type="submit"
                            disabled={submitting}
                            className="rounded-lg bg-emerald-600 px-3.5 py-2 text-sm font-medium text-white transition hover:bg-emerald-500 disabled:cursor-not-allowed disabled:opacity-50"
                          >
                            {submitting ? "Bezig…" : "Opslaan"}
                          </button>
                          <button
                            type="button"
                            onClick={() => setMode("none")}
                            className="rounded-lg border border-white/10 px-3.5 py-2 text-sm text-gray-300 hover:bg-white/5"
                          >
                            Annuleren
                          </button>
                        </div>
                      </form>
                    </td>
                  </tr>
                ) : (
                  <tr className={!row.is_active ? "opacity-50" : ""}>
                    <td className="px-4 py-2.5 text-gray-100">{row.full_name}</td>
                    <td className="px-4 py-2.5 text-gray-400">{KIND_LABEL[row.kind]}</td>
                    <td className="px-4 py-2.5 text-gray-400">{row.class_group ?? "—"}</td>
                    <td className="px-4 py-2.5 text-gray-400">{row.is_boarding_student ? "Ja" : "—"}</td>
                    <td className="px-4 py-2.5 text-right">
                      <div className="flex justify-end gap-3">
                        <button
                          type="button"
                          onClick={() => setExpanded(expanded === row.id ? null : row.id)}
                          className="text-xs text-gray-500 hover:text-emerald-400"
                        >
                          {expanded === row.id ? "Planning verbergen" : "Planning"}
                        </button>
                        <button type="button" onClick={() => startEdit(row)} className="text-xs text-gray-500 hover:text-emerald-400">
                          Bewerken
                        </button>
                        {row.is_active ? (
                          <button type="button" onClick={() => setActive(row, false)} className="text-xs text-gray-500 hover:text-red-400">
                            Deactiveren
                          </button>
                        ) : (
                          <button type="button" onClick={() => setActive(row, true)} className="text-xs text-gray-500 hover:text-emerald-400">
                            Heractiveren
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                )}
                {expanded === row.id && (
                  <tr>
                    <td colSpan={5} className="border-t border-white/5 bg-gray-950/40 p-4">
                      <SubjectMealPlanEditor
                        subjectId={row.id}
                        kind={row.kind}
                        plans={plans.filter(
                          (p) => (row.kind === "external_athlete" ? p.external_athlete_id : p.other_student_id) === row.id
                        )}
                      />
                    </td>
                  </tr>
                )}
              </Fragment>
            ))}
            {rows.length === 0 && (
              <tr>
                <td colSpan={5} className="px-4 py-10 text-center text-sm text-gray-500">
                  Nog geen externe sporters of andere leerlingen toegevoegd.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function SubjectFormFields({
  form,
  setForm,
  lockKind,
}: {
  form: FormState;
  setForm: (updater: (f: FormState) => FormState) => void;
  lockKind: boolean;
}) {
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      <label className="flex flex-col text-sm text-gray-300">
        Type
        <select
          value={form.kind}
          disabled={lockKind}
          onChange={(e) => setForm((f) => ({ ...f, kind: e.target.value as ManagedKind }))}
          className={`${fieldClass} disabled:opacity-60`}
        >
          <option value="other_student">Andere leerling</option>
          <option value="external_athlete">Externe sporter</option>
        </select>
      </label>
      <label className="flex flex-col text-sm text-gray-300">
        Naam
        <input
          type="text"
          required
          value={form.fullName}
          onChange={(e) => setForm((f) => ({ ...f, fullName: e.target.value }))}
          className={fieldClass}
        />
      </label>
      <label className="flex flex-col text-sm text-gray-300">
        Klas
        <input
          type="text"
          value={form.classGroup}
          onChange={(e) => setForm((f) => ({ ...f, classGroup: e.target.value }))}
          className={fieldClass}
        />
      </label>
      <label className="mt-6 flex items-center gap-2 text-sm text-gray-300">
        <input
          type="checkbox"
          checked={form.isBoarding}
          onChange={(e) => setForm((f) => ({ ...f, isBoarding: e.target.checked }))}
          className="h-4 w-4 rounded border-white/10 bg-gray-950"
        />
        Internaatsleerling
      </label>
    </div>
  );
}

const fieldClass =
  "mt-1 w-full rounded-lg border border-white/10 bg-gray-950 px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-emerald-500";
