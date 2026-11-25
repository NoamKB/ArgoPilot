from datetime import UTC, date, datetime
from fractions import Fraction
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request

import engine
import upstream
from engine import round_half_up
from schemas import Plan, PlanDay

router = APIRouter(prefix="/v1", tags=["plan"])


def utc_today() -> date:
    # A dependency, so tests can set the date. The field's own date comes later, from the forecast.
    return datetime.now(UTC).date()


@router.get("/plots/{plot_id}/plan", response_model=Plan)
def get_plan(
    request: Request,
    plot_id: UUID,
    today: Annotated[date, Depends(utc_today)],
    days: Annotated[int, Query(ge=1, le=7)] = 7,
    # Optional simulation: the soil water this morning as a whole percentage of a full bucket. 100 = JL-011 default.
    initial_soil_water_pct: Annotated[int, Query(ge=0, le=100)] = 100,
):
    settings = request.app.state.settings
    registry = request.app.state.registry_client
    weather = request.app.state.weather_client

    # 1. The plot (404 if registry doesn't know it).
    plot = upstream.get_plot(registry, settings.registry_url, plot_id)
    crop = engine.crop_profile(plot.crop_id)

    # 2. Early season check, before any weather call (JL-020). Rejects only when no possible field date is in season.
    if engine.definitely_out_of_season(crop, plot.planting_date, today, days):
        raise engine.OutOfSeason()

    # 3. Its soil and emitter, then the forecast for its point.
    soil_water = upstream.get_soil_water(registry, settings.registry_url, plot.soil_id)
    emitter_flow = upstream.get_emitter_flow(registry, settings.registry_url, plot.emitter_id)
    forecast = upstream.get_forecast(weather, settings.weather_url, plot.lat, plot.lon, days)

    # 4. The engine; its own season check on the forecast's dates is the final one.
    result = engine.plan_days(
        engine.PlotInputs(
            crop_id=plot.crop_id,
            planting_date=plot.planting_date,
            available_water_mm_per_m=soil_water,
            area_m2=plot.area_m2,
            row_spacing_m=plot.row_spacing_m,
            emitter_spacing_m=plot.emitter_spacing_m,
            flow_lph_per_emitter=emitter_flow,
        ),
        forecast.days,
        initial_fraction=Fraction(initial_soil_water_pct, 100),
    )

    # 5. Round for the output only (SKILL.md "Rounding").
    return Plan(
        plot_id=plot_id,
        crop_id=plot.crop_id,
        taw_mm=float(round_half_up(result.taw_mm, 3)),
        threshold_mm=float(round_half_up(result.threshold_mm, 3)),
        initial_soil_water_pct=initial_soil_water_pct,
        forecast_fetched_at=forecast.fetched_at,
        days=[
            PlanDay(
                date=day.date,
                # float(Fraction(str(x))) gives back x exactly, so ET0 and rain are shown as weather-service sent them.
                et0_mm=float(day.et0_mm),
                rain_mm=float(day.rain_mm),
                kc=float(round_half_up(day.kc, 3)),
                litres=int(round_half_up(day.litres, 0)),
                run_minutes=int(round_half_up(day.run_minutes, 0)),
                bucket_level_mm=float(round_half_up(day.bucket_level_mm, 3)),
                stale=forecast.stale,  # weather-service marks the whole forecast (FR-2.13)
            )
            for day in result.days
        ],
    )
