import Link from "next/link";
import { Button } from "@/components/ui/button";

/**
 * Lets the user try another starting soil level. A plain GET form: it only changes ?soil= in the page URL,
 * the page asks the planner again, and the planner does the calculation. Works without client JavaScript.
 */
export function SimulationForm({ plotId, pct, resettable }: { plotId: string; pct?: number; resettable: boolean }) {
  return (
    <section aria-labelledby="simulate" className="mt-10 max-w-xl border-t pt-6">
      <h2 id="simulate" className="text-lg font-bold">
        Simulate a different starting soil water
      </h2>
      <p className="mt-1 text-sm text-muted-foreground">
        The planner can&apos;t measure the soil, so it assumes it starts today full. Try another level to see when
        watering would start. The result is a simulation, not a measurement.
      </p>
      <form action={`/plots/${plotId}`} method="get" className="mt-3 flex flex-wrap items-end gap-3">
        <label className="flex flex-col gap-1 text-sm">
          Starting soil water (%)
          <input
            type="number"
            name="soil"
            min={0}
            max={100}
            step={1}
            required
            defaultValue={pct ?? 100}
            className="h-9 w-28 rounded-md border bg-card px-3 text-base tabular-nums"
          />
        </label>
        <Button type="submit">Simulate</Button>
        {resettable && (
          <Link href={`/plots/${plotId}`} className="pb-2 text-sm underline underline-offset-4">
            Reset to full
          </Link>
        )}
      </form>
    </section>
  );
}
