"use client";

import { type FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase/client";
import type { AthleteMeetingType, Database } from "@/types/database";

type Meeting = Database["public"]["Tables"]["athlete_meetings"]["Row"];

const TYPE_LABEL: Record<AthleteMeetingType, string> = {
  klassenraad: "Klassenraad",
  deliberatie: "Deliberatie",
};

/**
 * Log of klassenraad/deliberatie entries for one athlete — a date, prep
 * notes, and a report per meeting (see supabase/migrations/0001_init.sql's
 * athlete_meetings table). Renders the existing list + an inline add form.
 */
export default function AthleteMeetings({ athleteId, meetings }: { athleteId: string; meetings: Meeting[] }) {
  const router = useRouter();
  const [showForm, setShowForm] = useState(false);
  const [meetingType, setMeetingType] = useState<AthleteMeetingType>("klassenraad");
  const [meetingDate, setMeetingDate] = useState("");
  const [preparationNotes, setPreparationNotes] = useState("");
  const [reportNotes, setReportNotes] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    if (!meetingDate) return;

    setSubmitting(true);
    setError(null);

    const supabase = createClient();
    const {
      data: { user },
    } = await supabase.auth.getUser();

    const { error: insertError } = await supabase.from("athlete_meetings").insert({
      athlete_id: athleteId,
      meeting_type: meetingType,
      meeting_date: meetingDate,
      preparation_notes: preparationNotes.trim() || null,
      report_notes: reportNotes.trim() || null,
      created_by: user?.id,
    });

    if (insertError) {
      setError("Toevoegen mislukt. Probeer opnieuw.");
      setSubmitting(false);
      return;
    }

    setMeetingDate("");
    setPreparationNotes("");
    setReportNotes("");
    setShowForm(false);
    setSubmitting(false);
    router.refresh();
  };

  return (
    <div className="rounded-2xl border border-white/10 bg-gray-900/60 p-5 shadow-xl shadow-black/20">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-white">Klassenraden &amp; deliberaties</h2>
        <button
          type="button"
          onClick={() => setShowForm((v) => !v)}
          className="text-xs font-medium text-emerald-400 hover:opacity-80"
        >
          {showForm ? "Annuleren" : "+ Toevoegen"}
        </button>
      </div>

      {showForm && (
        <form onSubmit={handleSubmit} className="mb-4 space-y-3 rounded-xl border border-white/10 bg-gray-950/60 p-4">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <label className="flex flex-col text-sm text-gray-300">
              Type
              <select
                value={meetingType}
                onChange={(e) => setMeetingType(e.target.value as AthleteMeetingType)}
                className={selectClass}
              >
                <option value="klassenraad">Klassenraad</option>
                <option value="deliberatie">Deliberatie</option>
              </select>
            </label>
            <label className="flex flex-col text-sm text-gray-300">
              Datum
              <input
                type="date"
                required
                value={meetingDate}
                onChange={(e) => setMeetingDate(e.target.value)}
                className={selectClass}
              />
            </label>
          </div>
          <label className="flex flex-col text-sm text-gray-300">
            Voorbereiding
            <textarea
              value={preparationNotes}
              onChange={(e) => setPreparationNotes(e.target.value)}
              rows={2}
              className={selectClass}
            />
          </label>
          <label className="flex flex-col text-sm text-gray-300">
            Verslag
            <textarea value={reportNotes} onChange={(e) => setReportNotes(e.target.value)} rows={2} className={selectClass} />
          </label>
          {error && <p className="text-sm text-red-400">{error}</p>}
          <button
            type="submit"
            disabled={submitting}
            className="rounded-lg bg-emerald-600 px-3.5 py-2 text-sm font-medium text-white transition hover:bg-emerald-500 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {submitting ? "Bezig…" : "Opslaan"}
          </button>
        </form>
      )}

      {meetings.length === 0 ? (
        <p className="text-sm text-gray-500">Nog geen klassenraden of deliberaties geregistreerd.</p>
      ) : (
        <ul className="space-y-3">
          {meetings.map((meeting) => (
            <li key={meeting.id} className="rounded-xl border border-white/5 bg-gray-950/40 p-3.5 text-sm">
              <div className="flex items-center justify-between">
                <span className="font-medium text-gray-100">{TYPE_LABEL[meeting.meeting_type]}</span>
                <span className="text-gray-500">{meeting.meeting_date}</span>
              </div>
              {meeting.preparation_notes && (
                <p className="mt-1.5 text-gray-400">
                  <span className="text-gray-500">Voorbereiding: </span>
                  {meeting.preparation_notes}
                </p>
              )}
              {meeting.report_notes && (
                <p className="mt-1 text-gray-400">
                  <span className="text-gray-500">Verslag: </span>
                  {meeting.report_notes}
                </p>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

const selectClass =
  "mt-1 w-full rounded-lg border border-white/10 bg-gray-950 px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-emerald-500";
