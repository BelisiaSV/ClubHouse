import type { Database, MealCode } from "@/types/database";

export type MealPlan = Database["public"]["Tables"]["meal_plans"]["Row"];
export type MealException = Database["public"]["Tables"]["meal_exceptions"]["Row"];
export type MealFreeDay = Database["public"]["Tables"]["meal_free_days"]["Row"];

/**
 * Ported from the standalone "Maaltijdplanning" HTML tool's getMeal()/
 * countDay() — see supabase/migrations/0001_init.sql's meal_plans/
 * meal_exceptions/meal_free_days comment for why nothing here is a
 * materialized per-day row. Meal days are Mon/Tue/Thu/Fri (JS getDay():
 * 1,2,4,5) — Wednesday and weekends never carry a warm meal.
 */
export const MEAL_WEEKDAYS = [1, 2, 4, 5] as const;

export const DAY_LABELS: Record<number, string> = { 1: "Maandag", 2: "Dinsdag", 4: "Donderdag", 5: "Vrijdag" };
export const DAY_SHORT: Record<number, string> = { 1: "MA", 2: "DI", 4: "DO", 5: "VR" };

const DAY_CODE_KEY: Record<number, "monday_code" | "tuesday_code" | "thursday_code" | "friday_code"> = {
  1: "monday_code",
  2: "tuesday_code",
  4: "thursday_code",
  5: "friday_code",
};

export const MEAL_CODE_LABEL: Record<MealCode, string> = {
  s: "Standaard",
  v: "Vegetarisch",
  gv: "Geen varkensvlees",
  "": "Geen maaltijd",
};

export function toDateStr(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

export function fromDateStr(dateStr: string): Date {
  const [year, month, day] = dateStr.split("-").map(Number);
  return new Date(year, month - 1, day);
}

export function getMondayOf(date: Date): Date {
  const d = new Date(date);
  d.setHours(0, 0, 0, 0);
  const day = d.getDay();
  d.setDate(d.getDate() + (day === 0 ? -6 : 1 - day));
  return d;
}

export function addDays(date: Date, days: number): Date {
  const d = new Date(date);
  d.setDate(d.getDate() + days);
  return d;
}

/** The 4 meal days (Mon/Tue/Thu/Fri) of the week starting on `monday`. */
export function weekMealDays(monday: Date): Date[] {
  return [0, 1, 3, 4].map((offset) => addDays(monday, offset));
}

export function isFreeDay(dateStr: string, freeDays: MealFreeDay[]): boolean {
  return freeDays.some((f) => f.free_date === dateStr);
}

/** The plan version in force on `dateStr` — the latest one whose effective_from is on or before it. */
export function getActivePlan(plans: MealPlan[], athleteId: string, dateStr: string): MealPlan | null {
  const applicable = plans.filter((p) => p.athlete_id === athleteId && p.effective_from <= dateStr);
  if (applicable.length === 0) return null;
  return applicable.reduce((latest, p) => (p.effective_from > latest.effective_from ? p : latest));
}

/** The exception in force on `dateStr` (open-ended when date_to is null), most recent match wins. */
export function getActiveException(exceptions: MealException[], athleteId: string, dateStr: string): MealException | null {
  const applicable = exceptions
    .filter((e) => e.athlete_id === athleteId && e.date_from <= dateStr && (!e.date_to || e.date_to >= dateStr))
    .sort((a, b) => b.date_from.localeCompare(a.date_from));
  return applicable[0] ?? null;
}

/**
 * The effective meal code for one athlete on one date. Returns `null` for
 * "vrij" (a school-wide free day, or a non-meal weekday) so callers can
 * render that distinctly from an explicit "no meal" ('') plan choice.
 */
export function getMealForDay(
  athleteId: string,
  dateStr: string,
  plans: MealPlan[],
  exceptions: MealException[],
  freeDays: MealFreeDay[]
): MealCode | null {
  if (isFreeDay(dateStr, freeDays)) return null;

  const exception = getActiveException(exceptions, athleteId, dateStr);
  if (exception) return exception.meal_code;

  const dayOfWeek = fromDateStr(dateStr).getDay();
  const key = DAY_CODE_KEY[dayOfWeek];
  if (!key) return null;

  const plan = getActivePlan(plans, athleteId, dateStr);
  return plan ? plan[key] : "";
}

export interface DayCounts {
  s: number;
  v: number;
  gv: number;
  total: number;
  vrij: boolean;
}

export function countDay(
  athleteIds: string[],
  dateStr: string,
  plans: MealPlan[],
  exceptions: MealException[],
  freeDays: MealFreeDay[]
): DayCounts {
  if (isFreeDay(dateStr, freeDays)) {
    return { s: 0, v: 0, gv: 0, total: 0, vrij: true };
  }
  let s = 0;
  let v = 0;
  let gv = 0;
  athleteIds.forEach((athleteId) => {
    const code = getMealForDay(athleteId, dateStr, plans, exceptions, freeDays);
    if (code === "s") s++;
    else if (code === "v") v++;
    else if (code === "gv") gv++;
  });
  return { s, v, gv, total: s + v + gv, vrij: false };
}
