import { shortTimestamp } from "@/lib/format";
import type { Plan } from "@/lib/types";

/** FR-2.17: says why some days are marked stale and how old their forecast is. */
export function StaleNotice({ plan }: { plan: Plan }) {
  if (!plan.days.some((day) => day.stale)) {
    return null;
  }
  return (
    <p role="status" className="mt-4 rounded-lg border border-stale/40 bg-stale-soft px-3 py-2 text-sm text-stale">
      A newer weather forecast couldn&apos;t be fetched, so days marked &quot;Stale forecast&quot; use the one from{" "}
      {shortTimestamp(plan.forecast_fetched_at)}.
    </p>
  );
}
