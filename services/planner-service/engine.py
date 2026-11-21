"""The irrigation engine: every number in a plan (FR-2.11).

The formulas, crop values and rounding are exactly those in .claude/skills/irrigation-calc-reference/SKILL.md.
Everything is calculated with exact fractions (JL-019): every input must already be a Fraction, made with
Fraction(str(value)) from the value registry-service or weather-service sent. This module does no HTTP.
"""

import math
from dataclasses import dataclass
from datetime import date, timedelta
from fractions import Fraction

DAILY_CAP_HOURS = 24  # a drip system can't run more than a day in a day (JL-014)


class OutOfSeason(Exception):
    """A plan day falls outside the crop's growing season: the request gets 409 PLOT_OUT_OF_SEASON (JL-020)."""


@dataclass(frozen=True)
class CropProfile:
    """FAO-56 values for one crop (SKILL.md "Crop values"): stage lengths in days, Kc, root depth in m."""

    l_ini: int
    l_dev: int
    l_mid: int
    l_late: int
    kc_ini: Fraction
    kc_mid: Fraction
    kc_end: Fraction
    root_depth_m: Fraction

    @property
    def season_length(self) -> int:
        return self.l_ini + self.l_dev + self.l_mid + self.l_late


CROPS = {
    "tomato": CropProfile(35, 45, 70, 30, Fraction("0.60"), Fraction("1.15"), Fraction("0.80"), Fraction("0.7")),
    "bell-pepper": CropProfile(30, 40, 110, 30, Fraction("0.60"), Fraction("1.05"), Fraction("0.90"), Fraction("0.5")),
}


@dataclass(frozen=True)
class PlotInputs:
    """What the engine needs from registry-service: the plot, its soil and its emitter."""

    crop_id: str
    planting_date: date
    available_water_mm_per_m: Fraction
    area_m2: Fraction
    row_spacing_m: Fraction
    emitter_spacing_m: Fraction
    flow_lph_per_emitter: Fraction


@dataclass(frozen=True)
class WeatherDay:
    """One forecast day from weather-service, in mm."""

    date: date
    et0_mm: Fraction
    rain_mm: Fraction


@dataclass(frozen=True)
class DayResult:
    """One plan day, unrounded. Round only for the API output (SKILL.md "Rounding")."""

    date: date
    et0_mm: Fraction
    rain_mm: Fraction
    kc: Fraction
    litres: Fraction
    run_minutes: Fraction
    bucket_level_mm: Fraction


@dataclass(frozen=True)
class PlanResult:
    taw_mm: Fraction
    threshold_mm: Fraction
    days: list[DayResult]


def crop_profile(crop_id: str) -> CropProfile:
    """The crop's profile. An unknown crop means the planner and registry's catalogue disagree: a bug, not a 0."""
    try:
        return CROPS[crop_id]
    except KeyError:
        raise ValueError(f"no crop profile for {crop_id!r}") from None


# --- Growing season and Kc [FAO Ch. 6, Eq. 66] ---


def day_number(planting_date: date, day: date) -> int:
    """Days since planting, counting the planting day as day 1."""
    return (day - planting_date).days + 1


def in_season(crop: CropProfile, planting_date: date, first_day: date, days: int) -> bool:
    i_first = day_number(planting_date, first_day)
    i_last = i_first + days - 1
    return i_first >= 1 and i_last <= crop.season_length


def check_season(crop: CropProfile, planting_date: date, first_day: date, days: int) -> None:
    """Raise OutOfSeason unless every plan day is inside the season. first_day is the field's local today."""
    if not in_season(crop, planting_date, first_day, days):
        raise OutOfSeason()


def definitely_out_of_season(crop: CropProfile, planting_date: date, utc_today: date, days: int) -> bool:
    """The early check, before any weather call.

    UTC offsets range from -12 h to +14 h, so the field's local today is utc_today - 1, utc_today or utc_today + 1.
    True only when the plan is out of season for all three, so it never rejects a date the field is really on.
    The forecast's first date decides the remaining cases (check_season in plan_days).
    """
    candidates = (utc_today + timedelta(days=shift) for shift in (-1, 0, 1))
    return not any(in_season(crop, planting_date, today, days) for today in candidates)


def kc_on(crop: CropProfile, planting_date: date, day: date) -> Fraction:
    """Kc on one day. Outside the season there is no Kc: no held Kc end, no 0, no extended curve."""
    i = day_number(planting_date, day)
    if i < 1 or i > crop.season_length:
        raise OutOfSeason()
    end_dev = crop.l_ini + crop.l_dev
    end_mid = end_dev + crop.l_mid
    if i <= crop.l_ini:
        return crop.kc_ini
    if i <= end_dev:
        return crop.kc_ini + Fraction(i - crop.l_ini, crop.l_dev) * (crop.kc_mid - crop.kc_ini)
    if i <= end_mid:
        return crop.kc_mid
    return crop.kc_mid + Fraction(i - end_mid, crop.l_late) * (crop.kc_end - crop.kc_mid)


# --- Water and the drip system ---


def etc_mm(kc: Fraction, et0_mm: Fraction) -> Fraction:
    """The crop's water use that day, in mm [FAO Eq. 56]."""
    return kc * et0_mm


def system_flow_lph(area_m2: Fraction, row_spacing_m: Fraction, emitter_spacing_m: Fraction, flow_lph: Fraction) -> Fraction:
    """Litres per hour of the whole plot: emitter density estimate (not rounded) x flow per emitter [Units]."""
    emitters = area_m2 / (row_spacing_m * emitter_spacing_m)
    return emitters * flow_lph


def run_minutes_for(litres: Fraction, system_flow: Fraction) -> Fraction:
    return litres / system_flow * 60


# --- The soil bucket, day by day [FAO Ch. 8; SKILL.md "One day of the soil bucket"] ---


def plan_days(plot: PlotInputs, forecast: list[WeatherDay]) -> PlanResult:
    """The plan for the forecast's days. The bucket is full this morning (JL-011).

    Raises OutOfSeason if any day is outside the season, ValueError for an invalid input. Never treats one as 0.
    """
    check_inputs(plot, forecast)
    crop = crop_profile(plot.crop_id)
    check_season(crop, plot.planting_date, forecast[0].date, len(forecast))

    taw = plot.available_water_mm_per_m * crop.root_depth_m  # bucket size, mm [FAO Eq. 82]
    threshold = taw / 2  # "below half -> irrigate" [P2]
    flow = system_flow_lph(plot.area_m2, plot.row_spacing_m, plot.emitter_spacing_m, plot.flow_lph_per_emitter)
    daily_cap_l = flow * DAILY_CAP_HOURS

    days = []
    previous_end = taw
    for day in forecast:
        kc = kc_on(crop, plot.planting_date, day.date)
        # 1. Rain counts at the start of the day; water above a full bucket is lost.
        start = min(previous_end + day.rain_mm, taw)
        # 2. The crop's water use.
        etc = etc_mm(kc, day.et0_mm)
        # 3. Irrigate if the day would end strictly below half; then refill to full (JL-012, JL-013).
        desired_mm = taw - start if start - etc < threshold else Fraction(0)
        # 4. Litres and run time, capped at 24 h of the system's flow (JL-014).
        applied_l = min(desired_mm * plot.area_m2, daily_cap_l)
        applied_mm = applied_l / plot.area_m2
        # 5. The bucket at the end of the day, never below empty.
        end = max(start + applied_mm - etc, Fraction(0))

        days.append(
            DayResult(
                date=day.date,
                et0_mm=day.et0_mm,
                rain_mm=day.rain_mm,
                kc=kc,
                litres=applied_l,
                run_minutes=run_minutes_for(applied_l, flow),
                bucket_level_mm=end,
            )
        )
        previous_end = end
    return PlanResult(taw_mm=taw, threshold_mm=threshold, days=days)


def check_inputs(plot: PlotInputs, forecast: list[WeatherDay]) -> None:
    """Every number must be an exact Fraction (a float would silently spread float error) and in range."""
    for name in ("available_water_mm_per_m", "area_m2", "row_spacing_m", "emitter_spacing_m", "flow_lph_per_emitter"):
        value = require_fraction(name, getattr(plot, name))
        if value <= 0:
            raise ValueError(f"{name} must be > 0, got {value}")
    if not forecast:
        raise ValueError("no forecast days")
    for n, day in enumerate(forecast):
        for name in ("et0_mm", "rain_mm"):
            if require_fraction(name, getattr(day, name)) < 0:
                raise ValueError(f"{name} must be >= 0 on {day.date}")
        if day.date != forecast[0].date + timedelta(days=n):
            raise ValueError("forecast days must be consecutive")


def require_fraction(name: str, value) -> Fraction:
    if type(value) is not Fraction:
        raise ValueError(f"{name} must be a Fraction, got {type(value).__name__}")
    return value


# --- Rounding, for the API output only [SKILL.md "Rounding"] ---


def round_half_up(value: Fraction, places: int) -> Fraction:
    """Round an exact value that is >= 0, with .5 rounding up."""
    scale = 10**places
    return Fraction(math.floor(value * scale + Fraction(1, 2)), scale)
