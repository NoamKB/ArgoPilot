import math
import threading
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal

from schemas import ForecastDay

# The highest cell index on each axis. Without this limit, lat 90 would be cell 900, whose centre (90.05) is not a
# valid latitude; it joins cell 899 (89.9 to 90.0) instead. The same for lon 180.
MAX_LAT_CELL = 899
MAX_LON_CELL = 1799

Cell = tuple[int, int]


def grid_cell(lat: float, lon: float) -> Cell:
    """The 0.1° cell of a point: (floor(lat × 10), floor(lon × 10)).

    Decimal(str(value)) uses the number as written: the float 31.3 times 10 is 312.99999999999994,
    which would put 31.3 in the 31.2 cell.
    """
    lat_cell = math.floor(Decimal(str(lat)) * 10)
    lon_cell = math.floor(Decimal(str(lon)) * 10)
    return min(lat_cell, MAX_LAT_CELL), min(lon_cell, MAX_LON_CELL)


def cell_centre(cell: Cell) -> tuple[float, float]:
    """The point the provider is asked about, so every point in a cell gets the same forecast."""
    lat_cell, lon_cell = cell
    return (lat_cell + 0.5) / 10, (lon_cell + 0.5) / 10


@dataclass(frozen=True)
class CachedForecast:
    """One provider forecast for a grid cell, as it is kept in memory."""

    fetched_at: datetime  # UTC
    utc_offset_seconds: int  # the point's local time minus UTC, from the provider
    days: tuple[ForecastDay, ...]

    def age(self, now: datetime) -> timedelta:
        return now - self.fetched_at

    def local_today(self, now: datetime) -> date:
        return (now + timedelta(seconds=self.utc_offset_seconds)).date()

    def days_from_today(self, now: datetime, count: int) -> list[ForecastDay] | None:
        """The first `count` days from today, or None if fewer are left. A missing day is never filled in (FR-2.8)."""
        today = self.local_today(now)
        remaining = [day for day in self.days if day.date >= today]
        if len(remaining) < count:
            return None
        return remaining[:count]


class ForecastCache:
    """Forecasts by grid cell, in the memory of this process. A restart empties it."""

    def __init__(self) -> None:
        self._forecasts: dict[Cell, CachedForecast] = {}
        # Endpoints run in a thread pool, so two requests can use the cache at the same time.
        self._lock = threading.Lock()

    def get(self, cell: Cell) -> CachedForecast | None:
        with self._lock:
            return self._forecasts.get(cell)

    def put(self, cell: Cell, forecast: CachedForecast) -> None:
        with self._lock:
            self._forecasts[cell] = forecast
