import { StaleBadge } from "@/components/stale-badge";
import { wholeNumber } from "@/lib/format";
import type { Plan } from "@/lib/types";
import { cn } from "@/lib/utils";

/** FR-2.16: today's recommendation first, big and clear. */
export function TodayPanel({ plan }: { plan: Plan }) {
  const today = plan.days[0];
  const water = today.run_minutes > 0;

  return (
    <section
      aria-label="Today's recommendation"
      className={cn(
        "mt-4 rounded-xl p-5",
        water ? "bg-water text-water-foreground" : "border border-leaf/30 bg-leaf-soft text-foreground",
      )}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className={cn("text-sm", water ? "text-water-foreground/85" : "text-muted-foreground")}>Today</p>
        {today.stale && <StaleBadge onDark={water} />}
      </div>

      {water ? (
        <>
          <p className="mt-1 text-4xl leading-tight font-bold tabular-nums sm:text-5xl">
            Water for{" "}
            {/* Keep the number and its unit on one line. */}
            <span className="whitespace-nowrap">
              {wholeNumber(today.run_minutes)} {today.run_minutes === 1 ? "minute" : "minutes"}
            </span>
          </p>
          <p className="mt-1 text-lg tabular-nums">{wholeNumber(today.litres)} litres over the whole plot</p>
        </>
      ) : (
        <>
          <p className="mt-1 text-4xl leading-tight font-bold sm:text-5xl">No irrigation today</p>
          <p className="mt-1 text-lg">The soil holds enough water for the crop today.</p>
        </>
      )}

      <SoilBar plan={plan} onDark={water} />
    </section>
  );
}

/** The soil water left at the end of today, against the line where the plan starts watering. */
function SoilBar({ plan, onDark }: { plan: Plan; onDark: boolean }) {
  const level = plan.days[0].bucket_level_mm;
  const fill = Math.min(100, Math.max(0, (level / plan.taw_mm) * 100));
  const line = (plan.threshold_mm / plan.taw_mm) * 100;

  return (
    <div className="mt-5">
      {/* The sentence below says the same in words, so the bar is hidden from screen readers. */}
      <div aria-hidden className="relative">
        <div className={cn("h-2.5 overflow-hidden rounded-full", onDark ? "bg-white/25" : "bg-leaf/15")}>
          <div className={cn("h-full rounded-full", onDark ? "bg-white" : "bg-leaf")} style={{ width: `${fill}%` }} />
        </div>
        {/* The half-full line sticks out above and below the bar, so it shows over the fill and the empty track. */}
        <div
          className={cn(
            "absolute -inset-y-1 w-1 -translate-x-1/2 rounded-full",
            onDark ? "bg-[#0d3d66] ring-1 ring-white" : "bg-foreground",
          )}
          style={{ left: `${line}%` }}
        />
      </div>
      <p className={cn("mt-1.5 text-sm tabular-nums", onDark ? "text-water-foreground/85" : "text-muted-foreground")}>
        Soil water tonight {level} of {plan.taw_mm} mm. Watering starts below {plan.threshold_mm} mm.
      </p>
    </div>
  );
}
