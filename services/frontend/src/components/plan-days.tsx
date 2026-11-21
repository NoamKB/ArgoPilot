import { StaleBadge } from "@/components/stale-badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { shortDate, wholeNumber } from "@/lib/format";
import type { PlanDay } from "@/lib/types";

/** FR-2.16: the 7-day plan. A list on phones (no sideways scrolling at 375 px), a table on wider screens. */
export function PlanDays({ days }: { days: PlanDay[] }) {
  return (
    <section aria-labelledby="next-days" className="mt-8 xl:mt-4">
      <h2 id="next-days" className="text-lg font-bold">
        Next {days.length} days
      </h2>

      <ol className="mt-2 divide-y border-y sm:hidden">
        {days.map((day) => (
          <li key={day.date} className="py-3">
            <div className="flex items-baseline justify-between gap-3">
              <span className="font-bold">{shortDate(day.date)}</span>
              <span className={day.run_minutes > 0 ? "font-bold text-water tabular-nums" : "text-muted-foreground"}>
                {day.run_minutes > 0
                  ? `${wholeNumber(day.run_minutes)} min, ${wholeNumber(day.litres)} L`
                  : "No irrigation"}
              </span>
            </div>
            <p className="mt-1 text-sm text-muted-foreground tabular-nums">
              ET0 {day.et0_mm} mm, rain {day.rain_mm} mm, Kc {day.kc}, soil {day.bucket_level_mm} mm
            </p>
            {day.stale && (
              <div className="mt-1.5">
                <StaleBadge />
              </div>
            )}
          </li>
        ))}
      </ol>

      <div className="mt-2 hidden sm:block">
        <Table className="tabular-nums">
          <TableHeader>
            <TableRow>
              <TableHead>Day</TableHead>
              <TableHead className="text-right">Minutes</TableHead>
              <TableHead className="text-right">Litres</TableHead>
              <TableHead className="text-right">ET0 (mm)</TableHead>
              <TableHead className="text-right">Rain (mm)</TableHead>
              <TableHead className="text-right">Kc</TableHead>
              <TableHead className="text-right">Soil water (mm)</TableHead>
              <TableHead>
                <span className="sr-only">Forecast</span>
              </TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {days.map((day) => (
              <TableRow key={day.date}>
                <TableCell className="font-bold">{shortDate(day.date)}</TableCell>
                <TableCell className={day.run_minutes > 0 ? "text-right font-bold text-water" : "text-right"}>
                  {wholeNumber(day.run_minutes)}
                </TableCell>
                <TableCell className="text-right">{wholeNumber(day.litres)}</TableCell>
                <TableCell className="text-right">{day.et0_mm}</TableCell>
                <TableCell className="text-right">{day.rain_mm}</TableCell>
                <TableCell className="text-right">{day.kc}</TableCell>
                <TableCell className="text-right">{day.bucket_level_mm}</TableCell>
                <TableCell>{day.stale && <StaleBadge />}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
      <p className="mt-2 text-sm text-muted-foreground">
        ET0 is the water a standard patch of grass loses that day. Kc scales it to this crop at its age. Soil water is
        what is left in the root zone at the end of the day.
      </p>
    </section>
  );
}
