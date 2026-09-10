import AthleteForm from "@/components/athletes/AthleteForm";

export default function NewAthletePage() {
  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div>
        <h1 className="text-xs font-semibold uppercase tracking-wider text-emerald-400">Atleten</h1>
        <p className="mt-1 text-2xl font-bold text-white">Nieuw atleetprofiel</p>
      </div>
      <AthleteForm />
    </div>
  );
}
