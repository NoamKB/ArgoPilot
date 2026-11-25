import "server-only";
import { connection } from "next/server";

const VARIABLES = {
  registry: "REGISTRY_URL",
  weather: "WEATHER_URL",
  planner: "PLANNER_URL",
} as const;

export type ServiceName = keyof typeof VARIABLES;

/** The base URL of a service, from .env.local. Read on every request, never baked in at build time. */
export async function serviceUrl(service: ServiceName): Promise<string> {
  await connection();
  const name = VARIABLES[service];
  const value = process.env[name];
  if (!value) {
    throw new Error(`${name} is not set. Copy .env.example to .env.local and fill it in.`);
  }
  return value.replace(/\/+$/, "");
}
