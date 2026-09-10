import Link from "next/link";
import type { ReactNode } from "react";
import { notFound } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import AthleteMeetings from "@/components/athletes/AthleteMeetings";
import AthleteCustomFields from "@/components/athletes/AthleteCustomFields";

const REQUEST_TYPE_LABEL: Record<string, string> = {
  vroeger_vertrek: "Vroeger vertrek",
  later_toekomen: "Later toekomen",
  afwezigheid: "Afwezigheid",
  overig: "Overig",
};

const STATUS_CLASS: Record<string, string> = {
  in_afwachting: "bg-amber-500/15 text-amber-400",
  goedgekeurd: "bg-emerald-500/15 text-emerald-400",
  geweigerd: "bg-red-500/15 text-red-400",
};

function calculateAge(dateOfBirth: string | null): number | null {
  if (!dateOfBirth) return null;
  const birth = new Date(dateOfBirth);
  const today = new Date();
  let age = today.getFullYear() - birth.getFullYear();
  const hasHadBirthdayThisYear =
    today.getMonth() > birth.getMonth() || (today.getMonth() === birth.getMonth() && today.getDate() >= birth.getDate());
  if (!hasHadBirthdayThisYear) age -= 1;
  return age;
}

export default async function AthleteProfilePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const supabase = await createClient();

  const [{ data: athlete }, { data: permissions }, { data: meetings }, { data: customFields }] = await Promise.all([
    supabase.from("athletes").select("*").eq("id", id).single(),
    supabase
      .from("permissions")
      .select("id, request_type, requested_date, status")
      .eq("athlete_id", id)
      .order("requested_date", { ascending: false })
      .limit(10),
    supabase.from("athlete_meetings").select("*").eq("athlete_id", id).order("meeting_date", { ascending: false }),
    supabase.from("athlete_custom_fields").select("*").eq("athlete_id", id).order("created_at", { ascending: true }),
  ]);

  if (!athlete) {
    notFound();
  }

  const age = calculateAge(athlete.date_of_birth);

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-xs font-semibold uppercase tracking-wider text-emerald-400">Atleetprofiel</h1>
          <p className="mt-1 text-2xl font-bold text-white">{athlete.full_name}</p>
          <p className="mt-1 text-sm text-gray-500">
            {[athlete.sport, athlete.class_group, age !== null ? `${age} jaar` : null].filter(Boolean).join(" · ") || "—"}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <span
            className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${
              athlete.is_active ? "bg-emerald-500/15 text-emerald-400" : "bg-gray-700/50 text-gray-400"
            }`}
          >
            {athlete.is_active ? "Actief" : "Inactief"}
          </span>
          <Link
            href={`/athletes/${athlete.id}/edit`}
            className="rounded-lg bg-emerald-600 px-3.5 py-2 text-sm font-medium text-white transition hover:bg-emerald-500"
          >
            Bewerken
          </Link>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <InfoCard title="Basisgegevens">
          <InfoRow label="Geboortedatum" value={athlete.date_of_birth} />
          <InfoRow label="Sport" value={athlete.sport} />
          <InfoRow label="Klas" value={athlete.class_group} />
          <InfoRow label="Club (extern)" value={athlete.external_club} />
        </InfoCard>

        <InfoCard title="Contact">
          <InfoRow label="Ouder/voogd" value={athlete.guardian_name} />
          <InfoRow label="Telefoon ouder/voogd" value={athlete.guardian_phone} />
          <InfoRow label="E-mail ouder/voogd" value={athlete.guardian_email} />
          <InfoRow label="E-mail leerling" value={athlete.contact_email} />
          <InfoRow label="Telefoon leerling" value={athlete.contact_phone} />
        </InfoCard>

        <InfoCard title="Internaat & logistiek">
          <InfoRow label="Internaatsleerling" value={athlete.is_boarding_student ? "Ja" : "Nee"} />
          {athlete.is_boarding_student && <InfoRow label="Internaat" value={athlete.boarding_school_name} />}
          <InfoRow label="Vertrekuur" value={athlete.departure_time?.slice(0, 5) ?? null} />
          <InfoRow label="Opmerking" value={athlete.departure_notes} />
        </InfoCard>

        <InfoCard title="Maaltijden & medisch">
          <InfoRow label="Warme maaltijd" value={athlete.meal_plan_opt_in ? "Ja" : "Nee"} />
          <InfoRow label="Medische screening" value={athlete.medical_screening_done ? "Gedaan" : "Nog niet gedaan"} />
          <InfoRow label="Datum screening" value={athlete.medical_screening_date} />
          <InfoRow label="Opmerking screening" value={athlete.medical_screening_notes} />
        </InfoCard>
      </div>

      {athlete.notes && (
        <div className="rounded-2xl border border-white/10 bg-gray-900/60 p-5 shadow-xl shadow-black/20">
          <h2 className="mb-2 text-sm font-semibold text-white">Notities</h2>
          <p className="whitespace-pre-wrap text-sm text-gray-400">{athlete.notes}</p>
        </div>
      )}

      <div className="rounded-2xl border border-white/10 bg-gray-900/60 p-5 shadow-xl shadow-black/20">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-white">Toestemmingen</h2>
          <Link href="/permissions" className="text-xs font-medium text-emerald-400 hover:opacity-80">
            Alles bekijken →
          </Link>
        </div>
        {(permissions ?? []).length === 0 ? (
          <p className="text-sm text-gray-500">Geen toestemmingsaanvragen voor deze atleet.</p>
        ) : (
          <ul className="divide-y divide-white/5">
            {(permissions ?? []).map((permission) => (
              <li key={permission.id} className="flex items-center justify-between py-2.5 text-sm">
                <span className="text-gray-300">{REQUEST_TYPE_LABEL[permission.request_type] ?? permission.request_type}</span>
                <span className="text-gray-500">{permission.requested_date}</span>
                <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${STATUS_CLASS[permission.status]}`}>
                  {permission.status}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>

      <AthleteMeetings athleteId={athlete.id} meetings={meetings ?? []} />
      <AthleteCustomFields athleteId={athlete.id} fields={customFields ?? []} />
    </div>
  );
}

function InfoCard({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="rounded-2xl border border-white/10 bg-gray-900/60 p-5 shadow-xl shadow-black/20">
      <h2 className="mb-3 text-sm font-semibold text-white">{title}</h2>
      <dl className="space-y-2">{children}</dl>
    </div>
  );
}

function InfoRow({ label, value }: { label: string; value: string | null | undefined }) {
  return (
    <div className="flex items-start justify-between gap-3 text-sm">
      <dt className="text-gray-500">{label}</dt>
      <dd className="text-right text-gray-200">{value || "—"}</dd>
    </div>
  );
}
