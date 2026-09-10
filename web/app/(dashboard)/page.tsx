import Link from "next/link";
import { createClient } from "@/lib/supabase/server";
import { countDay, toDateStr } from "@/lib/meals";

const TODAY = toDateStr(new Date());

async function getKpis() {
  const supabase = await createClient();

  const [athletes, mealAthletes, mealPlansToday, mealExceptionsToday, mealFreeDays, pendingPermissions, upcomingPermissions] =
    await Promise.all([
      supabase.from("athletes").select("id", { count: "exact", head: true }).eq("is_active", true),
      supabase.from("athletes").select("id").eq("is_active", true).eq("is_boarding_student", false),
      supabase.from("meal_plans").select("*").lte("effective_from", TODAY),
      supabase
        .from("meal_exceptions")
        .select("*")
        .lte("date_from", TODAY)
        .or(`date_to.is.null,date_to.gte.${TODAY}`),
      supabase.from("meal_free_days").select("*").eq("free_date", TODAY),
      supabase.from("permissions").select("id", { count: "exact", head: true }).eq("status", "in_afwachting"),
      supabase
        .from("permissions")
        .select("id, athlete_id, request_type, requested_date, status")
        .eq("status", "in_afwachting")
        .order("requested_date", { ascending: true })
        .limit(5),
    ]);

  const mealsTodayCount = countDay(
    (mealAthletes.data ?? []).map((a) => a.id),
    TODAY,
    mealPlansToday.data ?? [],
    mealExceptionsToday.data ?? [],
    mealFreeDays.data ?? []
  ).total;

  const athleteIds = (upcomingPermissions.data ?? []).map((permission) => permission.athlete_id);
  const { data: athleteRows } =
    athleteIds.length > 0
      ? await supabase.from("athletes").select("id, full_name").in("id", athleteIds)
      : { data: [] };
  const athleteNameById = new Map((athleteRows ?? []).map((athlete) => [athlete.id, athlete.full_name]));

  return {
    activeAthleteCount: athletes.count ?? 0,
    mealsTodayCount,
    pendingPermissionCount: pendingPermissions.count ?? 0,
    upcomingPermissions: (upcomingPermissions.data ?? []).map((permission) => ({
      ...permission,
      athleteName: athleteNameById.get(permission.athlete_id) ?? "Onbekende atleet",
    })),
  };
}

const REQUEST_TYPE_LABEL: Record<string, string> = {
  vroeger_vertrek: "Vroeger vertrek",
  later_toekomen: "Later toekomen",
  afwezigheid: "Afwezigheid",
  overig: "Overig",
};

export default async function DashboardPage() {
  const { activeAthleteCount, mealsTodayCount, pendingPermissionCount, upcomingPermissions } = await getKpis();

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <div>
        <h1 className="text-xs font-semibold uppercase tracking-wider text-emerald-400">Operations Dashboard</h1>
        <p className="mt-1 text-2xl font-bold text-white">Vandaag op de Performance Desk</p>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <KpiTile label="Actieve atleten" value={activeAthleteCount} href="/athletes" />
        <KpiTile label="Maaltijden vandaag" value={mealsTodayCount} href="/meals" />
        <KpiTile
          label="Toestemmingen in afwachting"
          value={pendingPermissionCount}
          href="/permissions"
          accent={pendingPermissionCount > 0}
        />
      </div>

      <div className="rounded-2xl border border-white/10 bg-gray-900/60 p-5 shadow-xl shadow-black/20">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-white">Wachtend op beslissing</h2>
          <Link href="/permissions" className="text-xs font-medium text-emerald-400 hover:opacity-80">
            Alles bekijken →
          </Link>
        </div>
        {upcomingPermissions.length === 0 ? (
          <p className="text-sm text-gray-500">Geen openstaande toestemmingen. Alles is afgehandeld.</p>
        ) : (
          <ul className="divide-y divide-white/5">
            {upcomingPermissions.map((permission) => (
              <li key={permission.id} className="flex items-center justify-between py-2.5 text-sm">
                <span className="text-gray-200">{permission.athleteName}</span>
                <span className="text-gray-500">{REQUEST_TYPE_LABEL[permission.request_type] ?? permission.request_type}</span>
                <span className="text-gray-500">{permission.requested_date}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

function KpiTile({
  label,
  value,
  href,
  accent = false,
}: {
  label: string;
  value: number;
  href: string;
  accent?: boolean;
}) {
  return (
    <Link
      href={href}
      className="block rounded-2xl border border-white/10 bg-gray-900/60 p-5 shadow-xl shadow-black/20 transition hover:border-emerald-500/40"
    >
      <p className="text-xs font-medium uppercase tracking-wide text-gray-500">{label}</p>
      <p className={`mt-2 text-3xl font-bold ${accent ? "text-emerald-400" : "text-white"}`}>{value}</p>
    </Link>
  );
}
