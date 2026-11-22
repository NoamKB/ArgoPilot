import type { ReactNode } from "react";
import { Popover, PopoverContent, PopoverDescription, PopoverTitle, PopoverTrigger } from "@/components/ui/popover";
import { cn } from "@/lib/utils";

// One short sentence per label: what the value means, not how it is calculated.
const TERMS = {
  minutes: { title: "Minutes", text: "How long to run the drip system that day; 0 means no watering." },
  rain: { title: "Rain", text: "How much rain is expected that day, in millimetres." },
  et0: { title: "ET0", text: "How much water a standard patch of grass would lose to sun and wind that day, in millimetres." },
  kc: { title: "Kc", text: "How much water this crop uses compared with grass at its current age." },
  soil: { title: "Soil water", text: "How much water is expected to be left around the roots at the end of the day, in millimetres." },
  stale: { title: "Stale forecast", text: "This day uses an older saved forecast because a newer one couldn't be fetched." },
} as const;

export type Term = keyof typeof TERMS;

/**
 * A label that opens a short explanation. It is a real button, so it works with a mouse click, a tap and the
 * keyboard (Enter or Space to open, Escape to close). underline=false for labels that already look clickable.
 */
export function TermHelp({
  term,
  children,
  underline = true,
  className,
}: {
  term: Term;
  children: ReactNode;
  underline?: boolean;
  className?: string;
}) {
  const { title, text } = TERMS[term];
  return (
    <Popover>
      <PopoverTrigger
        className={cn(
          "cursor-help rounded-sm text-inherit focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring",
          underline && "underline decoration-dotted decoration-1 underline-offset-4",
          className,
        )}
      >
        {children}
      </PopoverTrigger>
      <PopoverContent className="w-64">
        <PopoverTitle className="font-bold">{title}</PopoverTitle>
        <PopoverDescription className="text-foreground">{text}</PopoverDescription>
      </PopoverContent>
    </Popover>
  );
}
