import type { Plan } from "@/lib/types";

const DAILY_CAP_MINUTES = 1440; // the planner never asks for more than 24 hours a day

/**
 * Shown only for a simulated starting level: these numbers are not a field-verified recommendation.
 * The stronger warning uses only values the planner returned; no irrigation rule is repeated here.
 */
export function SimulationNotice({ plan, pct }: { plan: Plan; pct: number }) {
  const startsBelowLine = pct / 100 < plan.threshold_mm / plan.taw_mm;
  const hitsLimit = plan.days.some((day) => day.run_minutes >= DAILY_CAP_MINUTES || day.bucket_level_mm === 0);

  return (
    <div role="status" className="mt-4 rounded-lg border border-foreground/25 bg-card px-3 py-2 text-sm">
      <p className="font-bold">Simulation result, not a field-verified irrigation recommendation.</p>
      <p>Check the soil before you water.</p>
      {(startsBelowLine || hitsLimit) && (
        <p className="mt-1.5">
          {startsBelowLine && "This start is below the watering line, so the plan waters right away. "}
          {hitsLimit && "On at least one day the plan reaches the 24-hour limit or the soil runs dry. "}
          Verify soil moisture in the field first.
        </p>
      )}
    </div>
  );
}
