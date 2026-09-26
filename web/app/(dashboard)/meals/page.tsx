import { createClient } from "@/lib/supabase/server";
import MealsPlanner from "@/components/meals/MealsPlanner";
import type { AthleteLite } from "@/components/meals/ExceptionDialog";

export default async function MealsPage() {
  const supabase = await createClient();

  const [{ data: athletes }, { data: externalAthletes }, { data: otherStudents }, { data: plans }, { data: exceptions }, { data: freeDays }] =
    await Promise.all([
      supabase.from("athletes").select("id, full_name, class_group, is_boarding_student").eq("is_active", true).order("full_name", { ascending: true }),
      // Unfiltered (incl. inactive): the Leerlingen tab manages the full roster.
      supabase.from("external_athletes").select("*").order("full_name", { ascending: true }),
      supabase.from("other_students").select("*").order("full_name", { ascending: true }),
      supabase.from("meal_plans").select("*"),
      supabase.from("meal_exceptions").select("*"),
      supabase.from("meal_free_days").select("*"),
    ]);

  const activeExternalAthletes = (externalAthletes ?? []).filter((a) => a.is_active);
  const activeOtherStudents = (otherStudents ?? []).filter((a) => a.is_active);

  const subjects: AthleteLite[] = [
    ...(athletes ?? []).filter((a) => !a.is_boarding_student).map((a) => ({ id: a.id, full_name: a.full_name, class_group: a.class_group, kind: "athlete" as const })),
    ...activeExternalAthletes
      .filter((a) => !a.is_boarding_student)
      .map((a) => ({ id: a.id, full_name: a.full_name, class_group: a.class_group, kind: "external_athlete" as const })),
    ...activeOtherStudents
      .filter((a) => !a.is_boarding_student)
      .map((a) => ({ id: a.id, full_name: a.full_name, class_group: a.class_group, kind: "other_student" as const })),
  ];

  // Internaatsleerlingen (any of the 3 populations): normally eat at the
  // internaat, so they're excluded from the kitchen roster/counts above —
  // but on a day the internaat itself is closed they come eat here with
  // their own lunch package ('eigen_lunchpakket' exception), which is
  // tracked for staff visibility without ever counting toward s/v/gv.
  const boardingSubjects: AthleteLite[] = [
    ...(athletes ?? []).filter((a) => a.is_boarding_student).map((a) => ({ id: a.id, full_name: a.full_name, class_group: a.class_group, kind: "athlete" as const })),
    ...activeExternalAthletes
      .filter((a) => a.is_boarding_student)
      .map((a) => ({ id: a.id, full_name: a.full_name, class_group: a.class_group, kind: "external_athlete" as const })),
    ...activeOtherStudents
      .filter((a) => a.is_boarding_student)
      .map((a) => ({ id: a.id, full_name: a.full_name, class_group: a.class_group, kind: "other_student" as const })),
  ];

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <div>
        <h1 className="text-xs font-semibold uppercase tracking-wider text-emerald-400">Performance Catering</h1>
        <p className="mt-1 text-2xl font-bold text-white">Warme maaltijden</p>
      </div>

      <MealsPlanner
        subjects={subjects}
        boardingSubjects={boardingSubjects}
        externalAthletes={externalAthletes ?? []}
        otherStudents={otherStudents ?? []}
        plans={plans ?? []}
        exceptions={exceptions ?? []}
        freeDays={freeDays ?? []}
      />
    </div>
  );
}
