import { createClient } from "@/lib/supabase/server";
import MealsPlanner from "@/components/meals/MealsPlanner";

export default async function MealsPage() {
  const supabase = await createClient();

  const [{ data: athletes }, { data: plans }, { data: exceptions }, { data: freeDays }] = await Promise.all([
    supabase
      .from("athletes")
      .select("id, full_name, class_group")
      .eq("is_active", true)
      .eq("is_boarding_student", false)
      .order("full_name", { ascending: true }),
    supabase.from("meal_plans").select("*"),
    supabase.from("meal_exceptions").select("*"),
    supabase.from("meal_free_days").select("*"),
  ]);

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <div>
        <h1 className="text-xs font-semibold uppercase tracking-wider text-emerald-400">Performance Catering</h1>
        <p className="mt-1 text-2xl font-bold text-white">Warme maaltijden</p>
      </div>

      <MealsPlanner athletes={athletes ?? []} plans={plans ?? []} exceptions={exceptions ?? []} freeDays={freeDays ?? []} />
    </div>
  );
}
