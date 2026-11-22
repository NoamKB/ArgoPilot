// The optional "starting soil water" simulation on the plot page (?soil=40).
// Only reads the page URL. The planner does every calculation.

export type SoilStart = { kind: "default" } | { kind: "simulated"; pct: number } | { kind: "invalid" };

/** "?soil=40" → simulated 40. Missing → default (a full bucket). Anything but a whole number 0-100 → invalid. */
export function parseSoilParam(value: string | string[] | undefined): SoilStart {
  if (value === undefined) {
    return { kind: "default" };
  }
  if (typeof value !== "string" || !/^\d{1,3}$/.test(value)) {
    return { kind: "invalid" };
  }
  const pct = Number(value);
  return pct <= 100 ? { kind: "simulated", pct } : { kind: "invalid" };
}
