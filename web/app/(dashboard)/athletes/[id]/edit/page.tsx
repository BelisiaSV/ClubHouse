import { notFound } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import AthleteForm from "@/components/athletes/AthleteForm";

export default async function EditAthletePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const supabase = await createClient();
  const { data: athlete } = await supabase.from("athletes").select("*").eq("id", id).single();

  if (!athlete) {
    notFound();
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div>
        <h1 className="text-xs font-semibold uppercase tracking-wider text-emerald-400">Atleten</h1>
        <p className="mt-1 text-2xl font-bold text-white">Profiel bewerken — {athlete.full_name}</p>
      </div>
      <AthleteForm athlete={athlete} />
    </div>
  );
}
