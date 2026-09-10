import { createClient } from "@/lib/supabase/server";

const TODAY = new Date().toISOString().slice(0, 10);

export default async function MealsPage() {
  const supabase = await createClient();
  const { data: registrations } = await supabase
    .from("meals")
    .select("id, athlete_id, is_registered, note")
    .eq("meal_date", TODAY);

  const athleteIds = (registrations ?? []).map((registration) => registration.athlete_id);
  const { data: athleteRows } =
    athleteIds.length > 0 ? await supabase.from("athletes").select("id, full_name").in("id", athleteIds) : { data: [] };
  const athleteNameById = new Map((athleteRows ?? []).map((athlete) => [athlete.id, athlete.full_name]));

  const registeredCount = (registrations ?? []).filter((registration) => registration.is_registered).length;

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <div>
        <h1 className="text-xs font-semibold uppercase tracking-wider text-emerald-400">Performance Catering</h1>
        <p className="mt-1 text-2xl font-bold text-white">Warme maaltijden — {TODAY}</p>
      </div>

      <div className="rounded-2xl border border-white/10 bg-gray-900/60 p-5 shadow-xl shadow-black/20">
        <p className="text-xs font-medium uppercase tracking-wide text-gray-500">Aan te maken vandaag</p>
        <p className="mt-2 text-3xl font-bold text-emerald-400">{registeredCount}</p>
      </div>

      <div className="overflow-x-auto rounded-2xl border border-white/10 bg-gray-900/60 shadow-xl shadow-black/20">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-white/10 text-xs uppercase tracking-wide text-gray-500">
              <th className="px-4 py-3 font-medium">Atleet</th>
              <th className="px-4 py-3 font-medium">Status</th>
              <th className="px-4 py-3 font-medium">Opmerking</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/5">
            {(registrations ?? []).map((registration) => (
              <tr key={registration.id}>
                <td className="px-4 py-3 text-gray-100">{athleteNameById.get(registration.athlete_id) ?? "—"}</td>
                <td className="px-4 py-3">
                  <span
                    className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${
                      registration.is_registered ? "bg-emerald-500/15 text-emerald-400" : "bg-gray-700/50 text-gray-400"
                    }`}
                  >
                    {registration.is_registered ? "Aangemeld" : "Afgemeld"}
                  </span>
                </td>
                <td className="px-4 py-3 text-gray-400">{registration.note ?? "—"}</td>
              </tr>
            ))}
            {(registrations ?? []).length === 0 && (
              <tr>
                <td colSpan={3} className="px-4 py-10 text-center text-sm text-gray-500">
                  Nog geen maaltijdregistraties voor vandaag.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
