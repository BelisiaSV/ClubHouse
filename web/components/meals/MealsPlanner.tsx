"use client";

import { useState } from "react";
import type { AthleteLite } from "./ExceptionDialog";
import type { MealException, MealFreeDay, MealPlan } from "@/lib/meals";
import WeekPlanningTab from "./WeekPlanningTab";
import DayExportTab from "./DayExportTab";
import MailingTab from "./MailingTab";
import MonthOverviewTab from "./MonthOverviewTab";
import ExceptionsTab from "./ExceptionsTab";
import ChangeLogTab from "./ChangeLogTab";

interface MealsPlannerProps {
  athletes: AthleteLite[];
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
] as const;

type TabKey = (typeof TABS)[number]["key"];

/**
 * Ported from the standalone "Maaltijdplanning" HTML tool staff already
 * used — see supabase/migrations/0001_init.sql's meal_plans/meal_
 * exceptions/meal_free_days comment. Only active, non-boarding athletes
 * are counted here (internaatsleerlingen eat at the internaat — see
 * AthleteMealPlan on the profile page).
 */
export default function MealsPlanner({ athletes, plans, exceptions, freeDays }: MealsPlannerProps) {
  const [tab, setTab] = useState<TabKey>("planning");

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

      {tab === "planning" && <WeekPlanningTab athletes={athletes} plans={plans} exceptions={exceptions} freeDays={freeDays} />}
      {tab === "export" && <DayExportTab athletes={athletes} plans={plans} exceptions={exceptions} freeDays={freeDays} />}
      {tab === "mailing" && <MailingTab athletes={athletes} plans={plans} exceptions={exceptions} freeDays={freeDays} />}
      {tab === "maand" && <MonthOverviewTab athletes={athletes} plans={plans} exceptions={exceptions} freeDays={freeDays} />}
      {tab === "uitz" && <ExceptionsTab athletes={athletes} exceptions={exceptions} freeDays={freeDays} />}
      {tab === "wijzigingen" && <ChangeLogTab athletes={athletes} plans={plans} exceptions={exceptions} />}
    </div>
  );
}
