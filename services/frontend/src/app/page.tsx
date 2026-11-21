import Link from "next/link";
import { Suspense } from "react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { cropName, wholeNumber } from "@/lib/format";
import { getFarmsWithPlots } from "@/lib/registry";

export default function Home() {
  return (
    <>
      <h1 className="text-2xl font-bold tracking-tight">Farms and plots</h1>
      <p className="mt-1 text-muted-foreground">Choose a plot to see today&apos;s watering and the next 7 days.</p>
      <Suspense fallback={<p className="mt-6 text-muted-foreground">Loading farms…</p>}>
        <FarmList />
      </Suspense>
    </>
  );
}

async function FarmList() {
  const result = await getFarmsWithPlots();
  if (!result.ok) {
    return (
      <Alert variant="destructive" className="mt-6">
        <AlertTitle>Can&apos;t load the farms</AlertTitle>
        <AlertDescription>registry-service is unavailable. Check that it is running, then reload the page.</AlertDescription>
      </Alert>
    );
  }
  if (result.farms.length === 0) {
    return <p className="mt-6">No farms yet. Add a farm and its plots in registry-service.</p>;
  }

  return (
    <div className="mt-6 grid gap-8 lg:grid-cols-2 lg:gap-x-12 xl:grid-cols-3">
      {result.farms.map((farm) => (
        <section key={farm.id} aria-labelledby={`farm-${farm.id}`}>
          <h2 id={`farm-${farm.id}`} className="text-lg font-bold">
            {farm.name}
          </h2>
          {farm.plots.length === 0 ? (
            <p className="mt-2 text-muted-foreground">No plots on this farm.</p>
          ) : (
            <ul className="mt-2 divide-y border-y">
              {farm.plots.map((plot) => (
                <li key={plot.id}>
                  <Link
                    href={`/plots/${plot.id}`}
                    className="flex items-baseline justify-between gap-4 py-3 hover:text-water focus-visible:text-water"
                  >
                    <span className="font-bold underline-offset-4 hover:underline">{plot.name}</span>
                    <span className="shrink-0 text-right text-sm whitespace-nowrap text-muted-foreground">
                      {cropName(plot.crop_id)}, {wholeNumber(plot.area_m2)} m²
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </section>
      ))}
    </div>
  );
}
