import Link from "next/link";
import { Suspense } from "react";
import { PlanDays } from "@/components/plan-days";
import { PlanError } from "@/components/plan-error";
import { SimulationForm } from "@/components/simulation-form";
import { SimulationNotice } from "@/components/simulation-notice";
import { StaleNotice } from "@/components/stale-notice";
import { TodayPanel } from "@/components/today-panel";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { cropName, shortDate } from "@/lib/format";
import { getPlan } from "@/lib/planner";
import { getPlot } from "@/lib/registry";
import { parseSoilParam } from "@/lib/simulation";
import type { PlanResult } from "@/lib/types";

type Props = PageProps<"/plots/[id]">;

export default function PlotPage({ params, searchParams }: Props) {
  return (
    <>
      <Link href="/" className="text-sm text-muted-foreground underline-offset-4 hover:underline">
        All farms
      </Link>
      <Suspense fallback={<p className="mt-4 text-muted-foreground">Loading the plan…</p>}>
        <PlotContent params={params} searchParams={searchParams} />
      </Suspense>
    </>
  );
}

async function PlotContent({ params, searchParams }: Pick<Props, "params" | "searchParams">) {
  const { id } = await params;
  const start = parseSoilParam((await searchParams).soil);
  const pct = start.kind === "simulated" ? start.pct : undefined;
  const [plot, result] = await Promise.all([
    getPlot(id),
    start.kind === "invalid" ? null : getPlan(id, pct),
  ]);

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

      <PlanSection result={result} pct={pct} />
      {/* The form is offered whenever there is a plan, or a simulation to correct or reset. */}
      {(result?.ok || start.kind !== "default") && (
        <SimulationForm plotId={id} pct={pct} resettable={start.kind !== "default"} />
      )}
    </>
  );
}

function PlanSection({ result, pct }: { result: PlanResult | null; pct?: number }) {
  if (result === null) {
    return <SimulationProblem text="Starting soil water must be a whole number from 0 to 100." />;
  }
  if (!result.ok) {
    return (
      <div className="max-w-2xl">
        <PlanError code={result.code} detail={result.detail} status={result.status} />
      </div>
    );
  }
  // Never show numbers labelled with a starting level the planner didn't use (for example an older planner).
  if (pct !== undefined && result.plan.initial_soil_water_pct !== pct) {
    return (
      <SimulationProblem text="planner-service didn't apply the simulated starting level, so no plan is shown. It may be an older version: restart it and try again." />
    );
  }

  return (
    // One column below 1280 px. Wider: today on the left at 320-416 px, the 7 days take the rest (they need about 650 px).
    <div className="xl:grid xl:grid-cols-[minmax(20rem,26rem)_minmax(0,1fr)] xl:items-start xl:gap-10">
      <div>
        <TodayPanel plan={result.plan} simulated={pct !== undefined} />
        {pct !== undefined && <SimulationNotice plan={result.plan} pct={pct} />}
        <StaleNotice plan={result.plan} />
      </div>
      <PlanDays days={result.plan.days} />
    </div>
  );
}

function SimulationProblem({ text }: { text: string }) {
  return (
    <Alert variant="destructive" className="mt-4 max-w-2xl p-4">
      <AlertTitle className="text-base font-bold">Can&apos;t run this simulation</AlertTitle>
      <AlertDescription className="text-base">{text}</AlertDescription>
    </Alert>
  );
}
