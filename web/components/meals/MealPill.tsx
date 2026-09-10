import type { MealCode } from "@/types/database";

const COLOR_CLASS: Record<string, string> = {
  s: "bg-sky-500/15 text-sky-300",
  v: "bg-emerald-500/15 text-emerald-300",
  gv: "bg-amber-500/15 text-amber-300",
};

/** null = "vrij" (free day / non-meal weekday), '' = explicit "no meal". */
export default function MealPill({ code }: { code: MealCode | null }) {
  if (code === null) return <span className="text-xs italic text-gray-600">vrij</span>;
  if (code === "") return <span className="text-xs text-gray-600">∅</span>;
  return <span className={`rounded px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wide ${COLOR_CLASS[code]}`}>{code}</span>;
}
