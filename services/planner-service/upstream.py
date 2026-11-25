"""Calls to registry-service and weather-service.

Every answer is checked strictly before the engine sees it, and every number is converted once with
Fraction(str(value)) (JL-019). Anything unusable raises UpstreamUnavailable, never a default or a 0 (FR-2.14).
"""

import math
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from fractions import Fraction
from urllib.parse import quote
from uuid import UUID

import httpx2

from engine import WeatherDay

REGISTRY = "registry-service"
WEATHER = "weather-service"


class UpstreamUnavailable(Exception):
    """A service is down, too slow, or gave an unusable answer: the request gets 503 UPSTREAM_UNAVAILABLE."""

    def __init__(self, service: str, reason: str) -> None:
        super().__init__(f"{service}: {reason}")
        self.service = service


class PlotNotFound(Exception):
    """registry-service has no plot with this id: the request gets 404 NOT_FOUND."""


@dataclass(frozen=True)
class Plot:
    crop_id: str
    planting_date: date
    soil_id: str
    emitter_id: str
    area_m2: Fraction
    row_spacing_m: Fraction
    emitter_spacing_m: Fraction
    lat: float  # sent on to weather-service as received
    lon: float


@dataclass(frozen=True)
class Forecast:
    fetched_at: datetime
    stale: bool
    days: list[WeatherDay]


# --- registry-service ---


def get_plot(client: httpx2.Client, base_url: str, plot_id: UUID) -> Plot:
    response = send(client, REGISTRY, f"{base_url.rstrip('/')}/v1/plots/{plot_id}")
    if response.status_code == 404:
        raise PlotNotFound()
    body = json_body(response, REGISTRY)
    try:
        return Plot(
            crop_id=text(body["crop_id"]),
            planting_date=date.fromisoformat(body["planting_date"]),
            soil_id=text(body["soil_id"]),
            emitter_id=text(body["emitter_id"]),
            area_m2=positive(body["area_m2"]),
            row_spacing_m=positive(body["row_spacing_m"]),
            emitter_spacing_m=positive(body["emitter_spacing_m"]),
            lat=coordinate(body["lat"]),
            lon=coordinate(body["lon"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise UpstreamUnavailable(REGISTRY, f"unusable plot: {exc!r}") from exc


def get_soil_water(client: httpx2.Client, base_url: str, soil_id: str) -> Fraction:
    """available_water_mm_per_m of the soil. A missing soil is a registry fault here, not a 404 for the caller."""
    body = json_body(send(client, REGISTRY, f"{base_url.rstrip('/')}/v1/soils/{quote(soil_id, safe='')}"), REGISTRY)
    try:
        return positive(body["available_water_mm_per_m"])
    except (KeyError, TypeError, ValueError) as exc:
        raise UpstreamUnavailable(REGISTRY, f"unusable soil: {exc!r}") from exc


def get_emitter_flow(client: httpx2.Client, base_url: str, emitter_id: str) -> Fraction:
    """flow_lph of one emitter."""
    body = json_body(send(client, REGISTRY, f"{base_url.rstrip('/')}/v1/emitters/{quote(emitter_id, safe='')}"), REGISTRY)
    try:
        return positive(body["flow_lph"])
    except (KeyError, TypeError, ValueError) as exc:
        raise UpstreamUnavailable(REGISTRY, f"unusable emitter: {exc!r}") from exc


# --- weather-service ---


def get_forecast(client: httpx2.Client, base_url: str, lat: float, lon: float, days: int) -> Forecast:
    """The forecast for the plot's point: exactly `days` consecutive days, each with ET0 and rain (FR-2.8)."""
    url = f"{base_url.rstrip('/')}/v1/forecast"
    body = json_body(send(client, WEATHER, url, params={"lat": lat, "lon": lon, "days": days}), WEATHER)
    try:
        stale = body["stale"]
        if not isinstance(stale, bool):
            raise TypeError(f"stale is not true or false: {stale!r}")
        fetched_at = datetime.fromisoformat(body["fetched_at"])
        forecast_days = [
            WeatherDay(date=date.fromisoformat(day["date"]), et0_mm=non_negative(day["et0_mm"]), rain_mm=non_negative(day["rain_mm"]))
            for day in body["days"]
        ]
    except (KeyError, TypeError, ValueError) as exc:
        raise UpstreamUnavailable(WEATHER, f"unusable forecast: {exc!r}") from exc

    if len(forecast_days) != days:
        raise UpstreamUnavailable(WEATHER, f"expected {days} days, got {len(forecast_days)}")
    for n, day in enumerate(forecast_days):
        if day.date != forecast_days[0].date + timedelta(days=n):
            raise UpstreamUnavailable(WEATHER, "forecast days are not consecutive")
    return Forecast(fetched_at=fetched_at, stale=stale, days=forecast_days)


# --- HTTP and value checks ---


def send(client: httpx2.Client, service: str, url: str, params: dict | None = None) -> httpx2.Response:
    try:
        return client.get(url, params=params)
    except httpx2.HTTPError as exc:  # timeouts and connection errors are subclasses
        raise UpstreamUnavailable(service, f"request failed: {type(exc).__name__}") from exc


def json_body(response: httpx2.Response, service: str) -> dict:
    if response.status_code != 200:
        raise UpstreamUnavailable(service, f"status {response.status_code}")
    try:
        body = response.json()
    except ValueError as exc:
        raise UpstreamUnavailable(service, "body is not JSON") from exc
    if not isinstance(body, dict):
        raise UpstreamUnavailable(service, "body is not a JSON object")
    return body


def exact(value) -> Fraction:
    """A JSON number as an exact Fraction of the decimal that was sent. null, text, true/false, NaN, inf: ValueError."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"not a number: {value!r}")
    return Fraction(str(value))  # NaN and infinity raise ValueError here


def positive(value) -> Fraction:
    number = exact(value)
    if number <= 0:
        raise ValueError(f"not > 0: {value!r}")
    return number


def non_negative(value) -> Fraction:
    number = exact(value)
    if number < 0:
        raise ValueError(f"negative: {value!r}")
    return number


def coordinate(value) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"not a coordinate: {value!r}")
    return value


def text(value) -> str:
    if not isinstance(value, str):
        raise TypeError(f"not text: {value!r}")
    return value
