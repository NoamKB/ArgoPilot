import "server-only";
import { serviceUrl, type ServiceName } from "@/lib/config";

const TIMEOUT_MS = 2_000;
const SERVICES: ServiceName[] = ["registry", "weather", "planner"];

export type ServiceStatus = { name: ServiceName; up: boolean };

/** GET /health on each service, in parallel (FR-2.19). Down = no 200 within 2 seconds. */
export async function getServiceStatus(): Promise<ServiceStatus[]> {
  return Promise.all(
    SERVICES.map(async (name) => {
      try {
        const response = await fetch(`${await serviceUrl(name)}/health`, {
          cache: "no-store",
          signal: AbortSignal.timeout(TIMEOUT_MS),
        });
        return { name, up: response.ok };
      } catch {
        return { name, up: false };
      }
    }),
  );
}
