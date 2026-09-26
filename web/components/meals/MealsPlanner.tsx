"use client";

import { useState } from "react";
import type { AthleteLite } from "./ExceptionDialog";
import type { MealException, MealFreeDay, MealPlan } from "@/lib/meals";
import type { Database } from "@/types/database";
import WeekPlanningTab from "./WeekPlanningTab";
import DayExportTab from "./DayExportTab";
import MailingTab from "./MailingTab";
import MonthOverviewTab from "./MonthOverviewTab";
import ExceptionsTab from "./ExceptionsTab";
import ChangeLogTab from "./ChangeLogTab";
import SubjectsTab from "./SubjectsTab";

type ExternalAthlete = Database["public"]["Tables"]["external_athletes"]["Row"];
type OtherStudent = Database["public"]["Tables"]["other_students"]["Row"];

interface MealsPlannerProps {
  subjects: AthleteLite[];
  boardingSubjects: AthleteLite[];
  externalAthletes: ExternalAthlete[];
  otherStudents: OtherStudent[];
  plans: MealPlan[];
  exceptions: MealException[];
  freeDays: MealFreeDay[];
}

const TABS = [
  { key: "planning", label: "Weekplanning" },
  { key: "export", label: "Dagexport" },
  { key: "mailing", label: "Mailing" },
  { key: "maand", label: "Maandoverzicht" },
  { key: "uitz", label: "Uitzonderingen" },
  { key: "wijzigingen", label: "Wijzigingen" },
  { key: "leerlingen", label: "Leerlingen" },
] as const;

type TabKey = (typeof TABS)[number]["key"];

/**
 * Ported from the standalone "Maaltijdplanning" HTML tool staff already
 * used — see supabase/migrations/0001_init.sql's meal_plans/meal_
 * exceptions/meal_free_days comment. `subjects` combines all three
 * populations that eat warme maaltijden here (topsport athletes, external
 * athletes, other students) into one roster for every tab. Boarding
 * students (any of the 3 populations) are excluded from that roster/the
 * kitchen counts — they eat at the internaat — but still appear in
 * `boardingSubjects` for Uitzonderingen/Wijzigingen and Dagexport's
 * separate "eigen lunchpakket" section, for the days the internaat itself
 * is closed and they come eat here with their own lunch package instead.
 */
export default function MealsPlanner({
  subjects,
  boardingSubjects,
  externalAthletes,
  otherStudents,
  plans,
  exceptions,
  freeDays,
}: MealsPlannerProps) {
  const [tab, setTab] = useState<TabKey>("planning");
  const allSubjects = [...subjects, ...boardingSubjects];

  return (
    <div>
      <div className="mb-5 flex flex-wrap gap-1 border-b border-white/10">
        {TABS.map((t) => (
          <button
            key={t.key}
            type="button"
            onClick={() => setTab(t.key)}
            className={`border-b-2 px-3.5 py-2.5 text-sm font-medium transition-colors ${
              tab === t.key ? "border-emerald-500 text-emerald-400" : "border-transparent text-gray-500 hover:text-gray-300"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === "planning" && <WeekPlanningTab athletes={subjects} plans={plans} exceptions={exceptions} freeDays={freeDays} />}
      {tab === "export" && (
        <DayExportTab
          athletes={subjects}
          boardingSubjects={boardingSubjects}
          plans={plans}
          exceptions={exceptions}
          freeDays={freeDays}
        />
      )}
      {tab === "mailing" && <MailingTab athletes={subjects} plans={plans} exceptions={exceptions} freeDays={freeDays} />}
      {tab === "maand" && <MonthOverviewTab athletes={subjects} plans={plans} exceptions={exceptions} freeDays={freeDays} />}
      {tab === "uitz" && <ExceptionsTab athletes={allSubjects} exceptions={exceptions} freeDays={freeDays} />}
      {tab === "wijzigingen" && <ChangeLogTab athletes={allSubjects} plans={plans} exceptions={exceptions} />}
      {tab === "leerlingen" && <SubjectsTab externalAthletes={externalAthletes} otherStudents={otherStudents} plans={plans} />}
    </div>
  );
}
