import Link from "next/link";
import { createClient } from "@/lib/supabase/server";

export default async function AthletesPage() {
  const supabase = await createClient();
  const { data: athletes } = await supabase
    .from("athletes")
    .select("id, full_name, sport, class_group, external_club, is_active")
    .order("full_name", { ascending: true });

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xs font-semibold uppercase tracking-wider text-emerald-400">Atleten</h1>
          <p className="mt-1 text-2xl font-bold text-white">Overzicht atleten</p>
        </div>
        <Link
          href="/athletes/new"
          className="rounded-lg bg-emerald-600 px-3.5 py-2 text-sm font-medium text-white transition hover:bg-emerald-500"
        >
          + Nieuwe atleet
        </Link>
      </div>

      <div className="overflow-x-auto rounded-2xl border border-white/10 bg-gray-900/60 shadow-xl shadow-black/20">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-white/10 text-xs uppercase tracking-wide text-gray-500">
              <th className="px-4 py-3 font-medium">Naam</th>
              <th className="px-4 py-3 font-medium">Sport</th>
              <th className="px-4 py-3 font-medium">Klas</th>
              <th className="px-4 py-3 font-medium">Externe club</th>
              <th className="px-4 py-3 font-medium">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/5">
            {(athletes ?? []).map((athlete) => (
              <tr key={athlete.id} className="cursor-pointer transition-colors hover:bg-white/5">
                <td className="px-4 py-3 text-gray-100">
                  <Link href={`/athletes/${athlete.id}`} className="block">
                    {athlete.full_name}
                  </Link>
                </td>
                <td className="px-4 py-3 text-gray-400">
                  <Link href={`/athletes/${athlete.id}`} className="block">
                    {athlete.sport ?? "—"}
                  </Link>
                </td>
                <td className="px-4 py-3 text-gray-400">
                  <Link href={`/athletes/${athlete.id}`} className="block">
                    {athlete.class_group ?? "—"}
                  </Link>
                </td>
                <td className="px-4 py-3 text-gray-400">
                  <Link href={`/athletes/${athlete.id}`} className="block">
                    {athlete.external_club ?? "—"}
                  </Link>
                </td>
                <td className="px-4 py-3">
                  <Link href={`/athletes/${athlete.id}`} className="block">
                    <span
                      className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${
                        athlete.is_active ? "bg-emerald-500/15 text-emerald-400" : "bg-gray-700/50 text-gray-400"
                      }`}
                    >
                      {athlete.is_active ? "Actief" : "Inactief"}
                    </span>
                  </Link>
                </td>
              </tr>
            ))}
            {(athletes ?? []).length === 0 && (
              <tr>
                <td colSpan={5} className="px-4 py-10 text-center text-sm text-gray-500">
                  Nog geen atleten toegevoegd.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
