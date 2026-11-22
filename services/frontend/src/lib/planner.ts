import "server-only";
import { serviceUrl } from "@/lib/config";
import type { Plan, PlanResult } from "@/lib/types";

// Longer than the planner's own worst case: registry calls (3 s each) plus weather-service (12 s).
const TIMEOUT_MS = 25_000;

/**
 * The 7-day plan of a plot, or the planner's error passed through (FR-2.18).
 * initialSoilWaterPct (0-100) asks the planner to simulate another starting soil level; leave it out for the default.
 */
export async function getPlan(plotId: string, initialSoilWaterPct?: number): Promise<PlanResult> {
  const base = await serviceUrl("planner");
  const query = new URLSearchParams({ days: "7" });
  if (initialSoilWaterPct !== undefined) {
    query.set("initial_soil_water_pct", String(initialSoilWaterPct));
  }
  let response: Response;
  try {
    response = await fetch(`${base}/v1/plots/${encodeURIComponent(plotId)}/plan?${query}`, {
      cache: "no-store",
      signal: AbortSignal.timeout(TIMEOUT_MS),
    });
  } catch {
    return { ok: false, status: 0, code: "PLANNER_UNREACHABLE", detail: "planner-service is unavailable." };
  }

  const body: unknown = await response.json().catch(() => null);
  if (response.ok && isPlan(body)) {
    return { ok: true, plan: body };
  }
  if (!response.ok && isErrorBody(body)) {
    return { ok: false, status: response.status, code: body.code, detail: body.detail };
  }
  return {
    ok: false,
    status: response.status,
    code: "UNEXPECTED",
    detail: `planner-service gave an unexpected answer (HTTP ${response.status}).`,
  };
}

function isPlan(body: unknown): body is Plan {
  return typeof body === "object" && body !== null && Array.isArray((body as Plan).days) && (body as Plan).days.length > 0;
}

function isErrorBody(body: unknown): body is { code: string; detail: string } {
  const candidate = body as { code?: unknown; detail?: unknown } | null;
  return typeof candidate?.code === "string" && typeof candidate?.detail === "string";
}
