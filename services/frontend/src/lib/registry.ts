import "server-only";
import { serviceUrl } from "@/lib/config";
import type { Farm, FarmWithPlots, Plot } from "@/lib/types";

const TIMEOUT_MS = 5_000;

export type FarmsResult = { ok: true; farms: FarmWithPlots[] } | { ok: false };

async function getJson<T>(base: string, path: string): Promise<T> {
  const response = await fetch(`${base}${path}`, {
    cache: "no-store",
    signal: AbortSignal.timeout(TIMEOUT_MS),
  });
  if (!response.ok) {
    throw new Error(`registry-service answered HTTP ${response.status} for ${path}`);
  }
  return (await response.json()) as T;
}

/** Every farm with its plots (FR-2.15). One call for farms and one for all plots. */
export async function getFarmsWithPlots(): Promise<FarmsResult> {
  const base = await serviceUrl("registry"); // a missing variable is a setup error, not "registry is down"
  try {
    const [farms, plots] = await Promise.all([
      getJson<Farm[]>(base, "/v1/farms"),
      getJson<Plot[]>(base, "/v1/plots"),
    ]);
    return {
      ok: true,
      farms: farms.map((farm) => ({ ...farm, plots: plots.filter((plot) => plot.farm_id === farm.id) })),
    };
  } catch (error) {
    console.error("registry-service request failed:", error);
    return { ok: false };
  }
}

/** The plot, or null when registry doesn't know it or can't be reached. The planner's answer explains which. */
export async function getPlot(id: string): Promise<Plot | null> {
  const base = await serviceUrl("registry");
  try {
    return await getJson<Plot>(base, `/v1/plots/${encodeURIComponent(id)}`);
  } catch {
    return null;
  }
}
