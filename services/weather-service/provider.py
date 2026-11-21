"""The Open-Meteo client. Open-Meteo's parameter and field names stay in this module."""

import logging
import math
from datetime import date, datetime, timedelta

import httpx2

from cache import CachedForecast
from config import Settings
from schemas import ForecastDay

logger = logging.getLogger(__name__)

SOURCE = "open-meteo"
FORECAST_DAYS = 7  # always fetch the most a request can ask for, so one cached forecast answers any `days`
ET0 = "et0_fao_evapotranspiration"  # FAO-56 reference evapotranspiration, mm per day
RAIN = "precipitation_sum"  # rain + showers + snowfall (as water), mm per day


class ProviderError(Exception):
    """The provider gave no usable forecast."""


def fetch_forecast(client: httpx2.Client, settings: Settings, lat: float, lon: float, now: datetime) -> CachedForecast:
    """Fetch and check the 7-day forecast, retrying `provider_retries` times (FR-2.6).

    Raises ProviderError if every attempt fails.
    """
    attempts = 1 + settings.provider_retries
    for attempt in range(1, attempts + 1):
        try:
            return fetch_once(client, settings, lat, lon, now)
        except ProviderError as exc:
            logger.warning("Weather provider attempt %d of %d failed: %s", attempt, attempts, exc)
    raise ProviderError(f"no usable forecast after {attempts} attempts")


def fetch_once(client: httpx2.Client, settings: Settings, lat: float, lon: float, now: datetime) -> CachedForecast:
    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": f"{ET0},{RAIN}",
        "forecast_days": FORECAST_DAYS,
        "timezone": "auto",  # days follow the point's local calendar, starting at its local today
    }
    api_key = settings.provider_api_key.get_secret_value()
    if api_key:
        params["apikey"] = api_key
    try:
        response = client.get(settings.provider_base_url, params=params)
    except httpx2.HTTPError as exc:
        # Only the error type: the message of some errors holds the URL, and with it the API key.
        raise ProviderError(f"request failed: {type(exc).__name__}") from exc
    if response.status_code != 200:
        raise ProviderError(f"status {response.status_code}")
    try:
        body = response.json()
    except ValueError as exc:
        raise ProviderError("body is not JSON") from exc
    return parse_forecast(body, now)


def parse_forecast(body, now: datetime) -> CachedForecast:
    """Turn the provider's body into a CachedForecast, or raise ProviderError. Never fills in a value (FR-2.8)."""
    try:
        daily = body["daily"]
        units = body["daily_units"]
        dates, et0_values, rain_values = daily["time"], daily[ET0], daily[RAIN]
        et0_unit, rain_unit = units[ET0], units[RAIN]
        utc_offset_seconds = body["utc_offset_seconds"]
    except (KeyError, TypeError) as exc:
        raise ProviderError(f"missing field {exc}") from exc

    if et0_unit != "mm" or rain_unit != "mm":
        raise ProviderError(f"unexpected units: {et0_unit!r}, {rain_unit!r}")
    if not isinstance(utc_offset_seconds, int) or isinstance(utc_offset_seconds, bool):
        raise ProviderError("utc_offset_seconds is not a whole number")
    for values in (dates, et0_values, rain_values):
        if not isinstance(values, list) or len(values) != FORECAST_DAYS:
            raise ProviderError(f"expected {FORECAST_DAYS} daily values")

    days = tuple(
        ForecastDay(date=parse_date(day), et0_mm=parse_amount(et0), rain_mm=parse_amount(rain))
        for day, et0, rain in zip(dates, et0_values, rain_values)
    )
    forecast = CachedForecast(fetched_at=now.replace(microsecond=0), utc_offset_seconds=utc_offset_seconds, days=days)

    # The days must be today, tomorrow, ... at the point's local date; a gap or a shifted day is a bad forecast.
    expected = forecast.local_today(now)
    for day in days:
        if day.date != expected:
            raise ProviderError(f"expected {expected.isoformat()}, got {day.date.isoformat()}")
        expected += timedelta(days=1)
    return forecast


def parse_date(value) -> date:
    if not isinstance(value, str):
        raise ProviderError(f"date is not a string: {value!r}")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ProviderError(f"date is not ISO: {value!r}") from exc


def parse_amount(value) -> float:
    """A daily amount in mm: a finite number, not below 0. null and anything else is a bad forecast."""
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise ProviderError(f"bad daily amount: {value!r}")
    return value
