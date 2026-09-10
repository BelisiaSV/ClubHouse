"use client";

import { type FormEvent, type ReactNode, useState } from "react";
import { useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase/client";
import type { Database } from "@/types/database";

type AthleteRow = Database["public"]["Tables"]["athletes"]["Row"];

interface AthleteFormProps {
  athlete?: AthleteRow;
}

const toTimeInputValue = (value: string | null) => (value ? value.slice(0, 5) : "");

/**
 * One profile per athlete, created once and edited from here (see the
 * Performance Desk brief: the fixed fields below, plus the meetings +
 * custom-fields sections on the profile page for whatever this form
 * doesn't cover). Handles both create (no `athlete` prop) and edit.
 */
export default function AthleteForm({ athlete }: AthleteFormProps) {
  const router = useRouter();
  const isEdit = Boolean(athlete);

  const [fullName, setFullName] = useState(athlete?.full_name ?? "");
  const [dateOfBirth, setDateOfBirth] = useState(athlete?.date_of_birth ?? "");
  const [sport, setSport] = useState(athlete?.sport ?? "");
  const [classGroup, setClassGroup] = useState(athlete?.class_group ?? "");
  const [externalClub, setExternalClub] = useState(athlete?.external_club ?? "");
  const [isActive, setIsActive] = useState(athlete?.is_active ?? true);

  const [contactEmail, setContactEmail] = useState(athlete?.contact_email ?? "");
  const [contactPhone, setContactPhone] = useState(athlete?.contact_phone ?? "");
  const [guardianName, setGuardianName] = useState(athlete?.guardian_name ?? "");
  const [guardianPhone, setGuardianPhone] = useState(athlete?.guardian_phone ?? "");
  const [guardianEmail, setGuardianEmail] = useState(athlete?.guardian_email ?? "");

  const [isBoardingStudent, setIsBoardingStudent] = useState(athlete?.is_boarding_student ?? false);
  const [boardingSchoolName, setBoardingSchoolName] = useState(athlete?.boarding_school_name ?? "");
  const [departureTime, setDepartureTime] = useState(toTimeInputValue(athlete?.departure_time ?? null));
  const [departureNotes, setDepartureNotes] = useState(athlete?.departure_notes ?? "");

  const [mealPlanOptIn, setMealPlanOptIn] = useState(athlete?.meal_plan_opt_in ?? false);

  const [medicalScreeningDone, setMedicalScreeningDone] = useState(athlete?.medical_screening_done ?? false);
  const [medicalScreeningDate, setMedicalScreeningDate] = useState(athlete?.medical_screening_date ?? "");
  const [medicalScreeningNotes, setMedicalScreeningNotes] = useState(athlete?.medical_screening_notes ?? "");

  const [notes, setNotes] = useState(athlete?.notes ?? "");

  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setSubmitting(true);
    setError(null);

    const supabase = createClient();
    const payload = {
      full_name: fullName.trim(),
      date_of_birth: dateOfBirth || null,
      sport: sport.trim() || null,
      class_group: classGroup.trim() || null,
      external_club: externalClub.trim() || null,
      is_active: isActive,
      contact_email: contactEmail.trim() || null,
      contact_phone: contactPhone.trim() || null,
      guardian_name: guardianName.trim() || null,
      guardian_phone: guardianPhone.trim() || null,
      guardian_email: guardianEmail.trim() || null,
      is_boarding_student: isBoardingStudent,
      boarding_school_name: isBoardingStudent ? boardingSchoolName.trim() || null : null,
      departure_time: departureTime || null,
      departure_notes: departureNotes.trim() || null,
      meal_plan_opt_in: mealPlanOptIn,
      medical_screening_done: medicalScreeningDone,
      medical_screening_date: medicalScreeningDate || null,
      medical_screening_notes: medicalScreeningNotes.trim() || null,
      notes: notes.trim() || null,
    };

    if (isEdit && athlete) {
      const { error: updateError } = await supabase.from("athletes").update(payload).eq("id", athlete.id);
      if (updateError) {
        setError("Opslaan mislukt. Probeer opnieuw.");
        setSubmitting(false);
        return;
      }
      router.push(`/athletes/${athlete.id}`);
      router.refresh();
      return;
    }

    const {
      data: { user },
    } = await supabase.auth.getUser();
    const { data: inserted, error: insertError } = await supabase
      .from("athletes")
      .insert({ ...payload, created_by: user?.id })
      .select("id")
      .single();

    if (insertError || !inserted) {
      setError("Aanmaken mislukt. Probeer opnieuw.");
      setSubmitting(false);
      return;
    }
    router.push(`/athletes/${inserted.id}`);
    router.refresh();
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <FormSection title="Basisgegevens">
        <Field label="Naam" required>
          <input
            type="text"
            required
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            className={inputClass}
          />
        </Field>
        <Field label="Geboortedatum">
          <input type="date" value={dateOfBirth ?? ""} onChange={(e) => setDateOfBirth(e.target.value)} className={inputClass} />
        </Field>
        <Field label="Sport">
          <input type="text" value={sport ?? ""} onChange={(e) => setSport(e.target.value)} className={inputClass} />
        </Field>
        <Field label="Klas">
          <input type="text" value={classGroup ?? ""} onChange={(e) => setClassGroup(e.target.value)} className={inputClass} />
        </Field>
        <Field label="Club (extern)">
          <input type="text" value={externalClub ?? ""} onChange={(e) => setExternalClub(e.target.value)} className={inputClass} />
        </Field>
        <Checkbox label="Actief" checked={isActive} onChange={setIsActive} />
      </FormSection>

      <FormSection title="Contact">
        <Field label="Naam ouder/voogd">
          <input type="text" value={guardianName ?? ""} onChange={(e) => setGuardianName(e.target.value)} className={inputClass} />
        </Field>
        <Field label="Telefoon ouder/voogd">
          <input type="tel" value={guardianPhone ?? ""} onChange={(e) => setGuardianPhone(e.target.value)} className={inputClass} />
        </Field>
        <Field label="E-mail ouder/voogd">
          <input type="email" value={guardianEmail ?? ""} onChange={(e) => setGuardianEmail(e.target.value)} className={inputClass} />
        </Field>
        <Field label="E-mail leerling (optioneel)">
          <input type="email" value={contactEmail ?? ""} onChange={(e) => setContactEmail(e.target.value)} className={inputClass} />
        </Field>
        <Field label="Telefoon leerling (optioneel)">
          <input type="tel" value={contactPhone ?? ""} onChange={(e) => setContactPhone(e.target.value)} className={inputClass} />
        </Field>
      </FormSection>

      <FormSection title="Internaat & logistiek">
        <Checkbox label="Internaatsleerling" checked={isBoardingStudent} onChange={setIsBoardingStudent} />
        {isBoardingStudent && (
          <Field label="Welk internaat">
            <input
              type="text"
              value={boardingSchoolName ?? ""}
              onChange={(e) => setBoardingSchoolName(e.target.value)}
              className={inputClass}
            />
          </Field>
        )}
        <Field label="Vertrekuur uit school">
          <input type="time" value={departureTime} onChange={(e) => setDepartureTime(e.target.value)} className={inputClass} />
        </Field>
        <Field label="Opmerking vertrekuren" wide>
          <textarea
            value={departureNotes ?? ""}
            onChange={(e) => setDepartureNotes(e.target.value)}
            rows={2}
            className={inputClass}
            placeholder="Bv. verschilt per dag — zie rooster"
          />
        </Field>
      </FormSection>

      <FormSection title="Warme maaltijden">
        <Checkbox label="Neemt warme maaltijd" checked={mealPlanOptIn} onChange={setMealPlanOptIn} />
      </FormSection>

      <FormSection title="Medische screening">
        <Checkbox label="Screening gedaan" checked={medicalScreeningDone} onChange={setMedicalScreeningDone} />
        <Field label="Datum screening">
          <input
            type="date"
            value={medicalScreeningDate ?? ""}
            onChange={(e) => setMedicalScreeningDate(e.target.value)}
            className={inputClass}
          />
        </Field>
        <Field label="Opmerkingen screening" wide>
          <textarea
            value={medicalScreeningNotes ?? ""}
            onChange={(e) => setMedicalScreeningNotes(e.target.value)}
            rows={2}
            className={inputClass}
          />
        </Field>
      </FormSection>

      <FormSection title="Notities">
        <Field label="Algemene notities" wide>
          <textarea value={notes ?? ""} onChange={(e) => setNotes(e.target.value)} rows={3} className={inputClass} />
        </Field>
      </FormSection>

      {error && <p className="text-sm text-red-400">{error}</p>}

      <div className="flex justify-end gap-3">
        <button
          type="button"
          onClick={() => router.back()}
          className="rounded-lg border border-white/10 px-4 py-2.5 text-sm font-medium text-gray-300 hover:bg-white/5"
        >
          Annuleren
        </button>
        <button
          type="submit"
          disabled={submitting}
          className="rounded-lg bg-emerald-600 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-emerald-500 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {submitting ? "Bezig…" : isEdit ? "Wijzigingen opslaan" : "Profiel aanmaken"}
        </button>
      </div>
    </form>
  );
}

const inputClass =
  "mt-1 w-full rounded-lg border border-white/10 bg-gray-950 px-3 py-2.5 text-sm text-white placeholder:text-gray-500 focus:outline-none focus:ring-2 focus:ring-emerald-500";

function FormSection({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="rounded-2xl border border-white/10 bg-gray-900/60 p-5 shadow-xl shadow-black/20">
      <h2 className="mb-4 text-sm font-semibold text-white">{title}</h2>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">{children}</div>
    </div>
  );
}

function Field({
  label,
  required,
  wide,
  children,
}: {
  label: string;
  required?: boolean;
  wide?: boolean;
  children: ReactNode;
}) {
  return (
    <label className={`flex flex-col text-sm text-gray-300 ${wide ? "sm:col-span-2" : ""}`}>
      {label}
      {required && <span className="text-red-400"> *</span>}
      {children}
    </label>
  );
}

function Checkbox({
  label,
  checked,
  onChange,
}: {
  label: string;
  checked: boolean;
  onChange: (value: boolean) => void;
}) {
  return (
    <label className="flex items-center gap-2.5 text-sm text-gray-300">
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        className="h-4 w-4 rounded border-white/20 bg-gray-950 text-emerald-600 focus:ring-emerald-500"
      />
      {label}
    </label>
  );
}
