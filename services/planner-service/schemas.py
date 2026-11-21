from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel


class PlanDay(BaseModel):
    date: date
    et0_mm: float
    rain_mm: float
    kc: float
    litres: int
    run_minutes: int
    bucket_level_mm: float
    stale: bool


class Plan(BaseModel):
    plot_id: UUID
    crop_id: str
    taw_mm: float
    threshold_mm: float
    forecast_fetched_at: datetime
    days: list[PlanDay]
