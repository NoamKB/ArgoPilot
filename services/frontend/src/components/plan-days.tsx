import { StaleBadge } from "@/components/stale-badge";
import { TermHelp } from "@/components/term-help";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { shortDate, wholeNumber } from "@/lib/format";
import type { PlanDay } from "@/lib/types";

/**
 * FR-2.16: the 7-day plan. A list on phones (no sideways scrolling at 375 px), a table on wider screens.
 * The technical labels open a one-sentence explanation (TermHelp) on click, tap or keyboard.
 */
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
              <TermHelp
                term="minutes"
                className={day.run_minutes > 0 ? "font-bold text-water tabular-nums" : "text-muted-foreground"}
              >
                {day.run_minutes > 0
                  ? `${wholeNumber(day.run_minutes)} min, ${wholeNumber(day.litres)} L`
                  : "No irrigation"}
              </TermHelp>
            </div>
            <p className="mt-1 text-sm text-muted-foreground tabular-nums">
              <TermHelp term="et0">ET0</TermHelp> {day.et0_mm} mm, <TermHelp term="rain">rain</TermHelp> {day.rain_mm}{" "}
              mm, <TermHelp term="kc">Kc</TermHelp> {day.kc}, <TermHelp term="soil">soil</TermHelp>{" "}
              {day.bucket_level_mm} mm
            </p>
            {day.stale && (
              <div className="mt-1.5">
                <TermHelp term="stale" underline={false}>
                  <StaleBadge />
                </TermHelp>
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
              <TableHead className="text-right">
                <TermHelp term="minutes">Minutes</TermHelp>
              </TableHead>
              <TableHead className="text-right">Litres</TableHead>
              <TableHead className="text-right">
                <TermHelp term="et0">ET0 (mm)</TermHelp>
              </TableHead>
              <TableHead className="text-right">
                <TermHelp term="rain">Rain (mm)</TermHelp>
              </TableHead>
              <TableHead className="text-right">
                <TermHelp term="kc">Kc</TermHelp>
              </TableHead>
              <TableHead className="text-right">
                <TermHelp term="soil">Soil water (mm)</TermHelp>
              </TableHead>
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
                <TableCell>
                  {day.stale && (
                    <TermHelp term="stale" underline={false}>
                      <StaleBadge />
                    </TermHelp>
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
      <p className="mt-2 text-sm text-muted-foreground">Tap or click an underlined label to see what it means.</p>
    </section>
  );
}
