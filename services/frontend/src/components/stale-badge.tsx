import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

/** FR-2.17: placed next to the numbers that come from an old forecast. */
export function StaleBadge({ onDark = false }: { onDark?: boolean }) {
  return (
    <Badge className={cn("border-stale/40 bg-stale-soft text-stale", onDark && "border-transparent")}>
      Stale forecast
    </Badge>
  );
}
