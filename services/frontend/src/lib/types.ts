// Shapes of the registry-service and planner-service responses this app uses.

export type Farm = {
  id: string;
  name: string;
};

export type Plot = {
  id: string;
  farm_id: string;
  name: string;
  area_m2: number;
  crop_id: string;
  planting_date: string;
};

export type FarmWithPlots = Farm & { plots: Plot[] };

export type PlanDay = {
  date: string;
  et0_mm: number;
  rain_mm: number;
  kc: number;
  litres: number;
  run_minutes: number;
  bucket_level_mm: number;
  stale: boolean;
};

export type Plan = {
  plot_id: string;
  crop_id: string;
  taw_mm: number;
  threshold_mm: number;
  forecast_fetched_at: string;
  days: PlanDay[];
};

/** The planner's answer: a plan, or its {code, detail} error. */
export type PlanResult =
  | { ok: true; plan: Plan }
  | { ok: false; status: number; code: string; detail: string };
