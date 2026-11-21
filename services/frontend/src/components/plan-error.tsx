import Link from "next/link";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";

type Props = { code: string; detail: string; status: number };

/** FR-2.18: what happened, in plain words. Never a blank page or a stack trace. */
export function PlanError({ code, detail, status }: Props) {
  const { title, text, destructive } = describe(code, detail, status);
  return (
    <Alert variant={destructive ? "destructive" : "default"} className="mt-4 p-4">
      <AlertTitle className="text-base font-bold">{title}</AlertTitle>
      <AlertDescription className="text-base text-foreground">
        <p>{text}</p>
        {code === "NOT_FOUND" || code === "VALIDATION" ? (
          <p>
            <Link href="/">Back to all farms</Link>
          </p>
        ) : null}
      </AlertDescription>
    </Alert>
  );
}

function describe(code: string, detail: string, status: number) {
  switch (code) {
    case "UPSTREAM_UNAVAILABLE":
      // The planner's detail names the service, e.g. "weather-service is unavailable or did not answer in time."
      return { title: "No plan right now", text: `${detail} Try again in a minute.`, destructive: true };
    case "PLANNER_UNREACHABLE":
      return { title: "No plan right now", text: `${detail} Try again in a minute.`, destructive: true };
    case "PLOT_OUT_OF_SEASON":
      return {
        title: "No plan for this plot",
        text: "The plot is outside its growing season: it isn't planted yet, or the 7 days run past the end of the season.",
        destructive: false,
      };
    case "NOT_FOUND":
      return { title: "Plot not found", text: "There is no plot with this address.", destructive: false };
    case "VALIDATION":
      return { title: "Plot not found", text: "This isn't a valid plot address.", destructive: false };
    default:
      return {
        title: "No plan right now",
        text: `The planner answered with an unexpected error${status ? ` (HTTP ${status})` : ""}. Try again in a minute.`,
        destructive: true,
      };
  }
}
