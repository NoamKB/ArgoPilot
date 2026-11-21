from datetime import date, datetime

from pydantic import BaseModel


class ForecastDay(BaseModel):
    date: date
    et0_mm: float
    rain_mm: float


class Forecast(BaseModel):
    lat: float
    lon: float
    source: str
    fetched_at: datetime
    stale: bool
    days: list[ForecastDay]
