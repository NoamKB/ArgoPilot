from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request

import provider
from cache import CachedForecast, cell_centre, grid_cell
from schemas import Forecast, ForecastDay

router = APIRouter(prefix="/v1", tags=["forecast"])


class ForecastUnavailable(Exception):
    """No fresh forecast, the provider failed, and no usable cached one: main.py answers 503 (FR-2.7)."""


def utc_now() -> datetime:
    # A dependency, so tests can move the clock.
    return datetime.now(UTC)


@router.get("/forecast", response_model=Forecast)
def get_forecast(
    request: Request,
    lat: Annotated[float, Query(ge=-90, le=90)],
    lon: Annotated[float, Query(ge=-180, le=180)],
    now: Annotated[datetime, Depends(utc_now)],
    days: Annotated[int, Query(ge=1, le=7)] = 7,
):
    settings = request.app.state.settings
    cache = request.app.state.cache
    cell = grid_cell(lat, lon)
    cached = cache.get(cell)

    # FR-2.5: while the cell's forecast is fresh, answer without calling the provider.
    # After local midnight a fresh forecast can have too few days left; then fetch again.
    if cached and cached.age(now) < timedelta(hours=settings.forecast_fresh_hours):
        selected = cached.days_from_today(now, days)
        if selected is not None:
            return forecast_response(lat, lon, cached, selected, stale=False)

    try:
        centre_lat, centre_lon = cell_centre(cell)
        fetched = provider.fetch_forecast(request.app.state.http_client, settings, centre_lat, centre_lon, now)
    except provider.ProviderError:
        # FR-2.6: the last forecast for this cell, marked stale, if it is not too old and still covers the days.
        if cached and cached.age(now) <= timedelta(hours=settings.forecast_max_stale_hours):
            selected = cached.days_from_today(now, days)
            if selected is not None:
                return forecast_response(lat, lon, cached, selected, stale=True)
        raise ForecastUnavailable() from None

    cache.put(cell, fetched)
    # fetch_forecast checked that the 7 days start today, so the first `days` are the ones asked for.
    return forecast_response(lat, lon, fetched, list(fetched.days[:days]), stale=False)


def forecast_response(lat: float, lon: float, forecast: CachedForecast, days: list[ForecastDay], stale: bool) -> Forecast:
    return Forecast(lat=lat, lon=lon, source=provider.SOURCE, fetched_at=forecast.fetched_at, stale=stale, days=days)
