import { createClient } from "@/lib/supabase/server";
import type { PermissionStatus } from "@/types/database";

const REQUEST_TYPE_LABEL: Record<string, string> = {
  vroeger_vertrek: "Vroeger vertrek",
  later_toekomen: "Later toekomen",
  afwezigheid: "Afwezigheid",
  overig: "Overig",
};

const STATUS_LABEL: Record<PermissionStatus, string> = {
  in_afwachting: "In afwachting",
  goedgekeurd: "Goedgekeurd",
  geweigerd: "Geweigerd",
};

const STATUS_CLASS: Record<PermissionStatus, string> = {
  in_afwachting: "bg-amber-500/15 text-amber-400",
  goedgekeurd: "bg-emerald-500/15 text-emerald-400",
  geweigerd: "bg-red-500/15 text-red-400",
};

export default async function PermissionsPage() {
  const supabase = await createClient();
  const { data: permissions } = await supabase
    .from("permissions")
    .select("id, athlete_id, request_type, requested_date, status, reason")
    .order("requested_date", { ascending: false })
    .limit(100);

  const athleteIds = [...new Set((permissions ?? []).map((permission) => permission.athlete_id))];
  const { data: athleteRows } =
    athleteIds.length > 0 ? await supabase.from("athletes").select("id, full_name").in("id", athleteIds) : { data: [] };
  const athleteNameById = new Map((athleteRows ?? []).map((athlete) => [athlete.id, athlete.full_name]));

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <div>
        <h1 className="text-xs font-semibold uppercase tracking-wider text-emerald-400">Toestemmingen-Matrix</h1>
        <p className="mt-1 text-2xl font-bold text-white">Afwijkingen &amp; toestemmingen</p>
      </div>

      <div className="overflow-x-auto rounded-2xl border border-white/10 bg-gray-900/60 shadow-xl shadow-black/20">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-white/10 text-xs uppercase tracking-wide text-gray-500">
              <th className="px-4 py-3 font-medium">Atleet</th>
              <th className="px-4 py-3 font-medium">Type</th>
              <th className="px-4 py-3 font-medium">Datum</th>
              <th className="px-4 py-3 font-medium">Reden</th>
              <th className="px-4 py-3 font-medium">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/5">
            {(permissions ?? []).map((permission) => (
              <tr key={permission.id}>
                <td className="px-4 py-3 text-gray-100">{athleteNameById.get(permission.athlete_id) ?? "—"}</td>
                <td className="px-4 py-3 text-gray-400">{REQUEST_TYPE_LABEL[permission.request_type] ?? permission.request_type}</td>
                <td className="px-4 py-3 text-gray-400">{permission.requested_date}</td>
                <td className="px-4 py-3 text-gray-400">{permission.reason ?? "—"}</td>
                <td className="px-4 py-3">
                  <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${STATUS_CLASS[permission.status]}`}>
                    {STATUS_LABEL[permission.status]}
                  </span>
                </td>
              </tr>
            ))}
            {(permissions ?? []).length === 0 && (
              <tr>
                <td colSpan={5} className="px-4 py-10 text-center text-sm text-gray-500">
                  Nog geen toestemmingsaanvragen.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
