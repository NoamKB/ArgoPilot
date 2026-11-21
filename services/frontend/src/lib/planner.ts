import "server-only";
import { serviceUrl } from "@/lib/config";
import type { Plan, PlanResult } from "@/lib/types";

// Longer than the planner's own worst case: registry calls (3 s each) plus weather-service (12 s).
const TIMEOUT_MS = 25_000;

/** The 7-day plan of a plot, or the planner's error passed through (FR-2.18). */
export async function getPlan(plotId: string): Promise<PlanResult> {
  const base = await serviceUrl("planner");
  let response: Response;
  try {
    response = await fetch(`${base}/v1/plots/${encodeURIComponent(plotId)}/plan?days=7`, {
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
