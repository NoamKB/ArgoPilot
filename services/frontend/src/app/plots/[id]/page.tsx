import Link from "next/link";
import { Suspense } from "react";
import { PlanDays } from "@/components/plan-days";
import { PlanError } from "@/components/plan-error";
import { StaleNotice } from "@/components/stale-notice";
import { TodayPanel } from "@/components/today-panel";
import { cropName, shortDate } from "@/lib/format";
import { getPlan } from "@/lib/planner";
import { getPlot } from "@/lib/registry";

export default function PlotPage({ params }: PageProps<"/plots/[id]">) {
  return (
    <>
      <Link href="/" className="text-sm text-muted-foreground underline-offset-4 hover:underline">
        All farms
      </Link>
      <Suspense fallback={<p className="mt-4 text-muted-foreground">Loading the plan…</p>}>
        <PlotContent params={params} />
      </Suspense>
    </>
  );
}

async function PlotContent({ params }: { params: PageProps<"/plots/[id]">["params"] }) {
  const { id } = await params;
  const [plot, result] = await Promise.all([getPlot(id), getPlan(id)]);

  return (
    <>
      <header className="mt-2">
        <h1 className="text-2xl font-bold tracking-tight">{plot?.name ?? "Plot"}</h1>
        {plot && (
          <p className="text-muted-foreground">
            {cropName(plot.crop_id)}, planted {shortDate(plot.planting_date)}
          </p>
        )}
      </header>

      {result.ok ? (
        // One column below 1280 px. Wider: today on the left at 320-416 px, the 7 days take the rest (they need about 650 px).
        <div className="xl:grid xl:grid-cols-[minmax(20rem,26rem)_minmax(0,1fr)] xl:items-start xl:gap-10">
          <div>
            <TodayPanel plan={result.plan} />
            <StaleNotice plan={result.plan} />
          </div>
          <PlanDays days={result.plan.days} />
        </div>
      ) : (
        <div className="max-w-2xl">
          <PlanError code={result.code} detail={result.detail} status={result.status} />
        </div>
      )}
    </>
  );
}
