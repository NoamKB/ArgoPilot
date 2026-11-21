"""Engine tests: every API value in .claude/skills/irrigation-calc-reference/references/worked-examples.md."""

from datetime import date, timedelta
from fractions import Fraction

import pytest

import engine
from engine import CROPS, OutOfSeason, PlotInputs, WeatherDay

TOMATO = CROPS["tomato"]
PEPPER = CROPS["bell-pepper"]


def F(value: str) -> Fraction:
    return Fraction(value)


def weather(first_day: date, et0: list[str], rain: list[str] | None = None) -> list[WeatherDay]:
    rain = rain or ["0"] * len(et0)
    return [
        WeatherDay(date=first_day + timedelta(days=n), et0_mm=F(e), rain_mm=F(r)) for n, (e, r) in enumerate(zip(et0, rain))
    ]


def plot(crop_id: str, planting_date: date, awc: str, area: str, flow: str, row="1.5", spacing="0.4") -> PlotInputs:
    return PlotInputs(
        crop_id=crop_id,
        planting_date=planting_date,
        available_water_mm_per_m=F(awc),
        area_m2=F(area),
        row_spacing_m=F(row),
        emitter_spacing_m=F(spacing),
        flow_lph_per_emitter=F(flow),
    )


def api_rows(result: engine.PlanResult) -> list[tuple[float, int, int, float]]:
    """The rounded (kc, litres, run_minutes, bucket_level_mm) of every day, as the API shows them."""
    return [
        (
            float(engine.round_half_up(day.kc, 3)),
            int(engine.round_half_up(day.litres, 0)),
            int(engine.round_half_up(day.run_minutes, 0)),
            float(engine.round_half_up(day.bucket_level_mm, 3)),
        )
        for day in result.days
    ]


# --- Case 1: the building blocks only. 6,900 L / 248 min is one day's ETc, not a plan output. ---


def test_case_1_one_day_of_etc_as_litres_and_run_minutes():
    kc = engine.kc_on(TOMATO, date(2026, 6, 1), date(2026, 6, 1) + timedelta(days=99))  # day 100: mid-season
    etc = engine.etc_mm(kc, F("6.0"))
    flow = engine.system_flow_lph(F("1000"), F("1.5"), F("0.4"), F("1.0"))
    litres = etc * F("1000")
    minutes = engine.run_minutes_for(litres, flow)

    assert kc == F("1.15")
    assert etc == F("6.9")
    assert flow == Fraction(5000, 3)  # 1,666.666... emitters x 1.0 L/h
    assert minutes == F("248.4")
    assert float(engine.round_half_up(kc, 3)) == 1.15
    assert int(engine.round_half_up(litres, 0)) == 6900
    assert int(engine.round_half_up(minutes, 0)) == 248


# --- Case 2: Kc interpolation in the development stage. ---


def test_case_2_pepper_development_kc():
    assert engine.kc_on(PEPPER, date(2026, 10, 1), date(2026, 11, 19)) == F("0.825")


# --- Case 3: seven days of the bucket, with rain and the 24 h cap. ---


def test_case_3_tomato_on_sand_seven_days():
    first_day = date(2026, 11, 21)
    west_block = plot("tomato", first_day - timedelta(days=99), awc="83", area="1500", flow="0.6")
    days = weather(first_day, ["6.0", "6.0", "5.0", "6.0", "6.0", "5.5", "6.0"], ["0", "0", "5", "0", "0", "0", "0"])

    result = engine.plan_days(west_block, days)

    assert result.taw_mm == F("58.1")
    assert result.threshold_mm == F("29.05")
    assert api_rows(result) == [
        (1.15, 0, 0, 51.2),
        (1.15, 0, 0, 44.3),
        (1.15, 0, 0, 43.55),
        (1.15, 0, 0, 36.65),
        (1.15, 0, 0, 29.75),
        (1.15, 36000, 1440, 47.425),
        (1.15, 0, 0, 40.525),
    ]
    assert [day.date for day in result.days] == [first_day + timedelta(days=n) for n in range(7)]
    assert result.days[2].rain_mm == 5
    assert result.days[5].et0_mm == F("5.5")


def test_case_3_capped_day_never_reports_the_uncapped_volume():
    first_day = date(2026, 11, 21)
    west_block = plot("tomato", first_day - timedelta(days=99), awc="83", area="1500", flow="0.6")
    days = weather(first_day, ["6.0", "6.0", "5.0", "6.0", "6.0", "5.5", "6.0"], ["0", "0", "5", "0", "0", "0", "0"])

    day_6 = engine.plan_days(west_block, days).days[5]

    assert day_6.litres == 36000  # not 42,525
    assert day_6.run_minutes == 1440  # not 1,701
    assert day_6.bucket_level_mm == F("47.425")  # not 51.775


# --- B1-B4: spots where floats give a wrong answer. ---


def test_b1_a_day_that_ends_at_exactly_half_does_not_irrigate():
    b1 = plot("tomato", date(2026, 11, 1), awc="90", area="1000", flow="1.0")

    result = engine.plan_days(b1, weather(date(2026, 11, 20), ["7.5"] * 7))

    assert result.threshold_mm == F("31.5")
    assert api_rows(result) == [(0.6, 0, 0, level) for level in [58.5, 54.0, 49.5, 45.0, 40.5, 36.0, 31.5]]


def test_b2_just_below_half_irrigates_on_day_7():
    b2 = plot("tomato", date(2026, 11, 1), awc="90", area="1000", flow="1.0")

    rows = api_rows(engine.plan_days(b2, weather(date(2026, 11, 20), ["7.501"] * 7)))

    assert [row[1:3] for row in rows[:6]] == [(0, 0)] * 6
    assert rows[6] == (0.6, 27004, 972, 58.499)


def test_b3_kc_tie_rounds_up():
    kc = engine.kc_on(PEPPER, date(2026, 10, 1), date(2026, 11, 1))

    assert kc == F("0.6225")
    assert float(engine.round_half_up(kc, 3)) == 0.623


def test_b4_litres_and_minutes_ties_round_up():
    b4 = plot("bell-pepper", date(2026, 8, 1), awc="83", area="500", flow="1.0")

    rows = api_rows(engine.plan_days(b4, weather(date(2026, 11, 20), ["3.5"] * 7)))

    assert [row[1] for row in rows] == [0, 0, 0, 0, 0, 9188, 0]
    assert [row[2] for row in rows] == [0, 0, 0, 0, 0, 662, 0]
    assert [row[3] for row in rows] == [37.825, 34.15, 30.475, 26.8, 23.125, 37.825, 34.15]
    assert {row[0] for row in rows} == {1.05}


# --- B5: the rounding helper on its own. ---


@pytest.mark.parametrize(
    ("value", "places", "expected"),
    [
        ("0.6225", 3, "0.623"),
        ("0.62249", 3, "0.622"),
        ("9187.5", 0, "9188"),
        ("9187.4999", 0, "9187"),
        ("661.5", 0, "662"),
        ("86.8775", 3, "86.878"),
        ("86.8774", 3, "86.877"),
    ],
)
def test_b5_round_half_up(value, places, expected):
    assert engine.round_half_up(F(value), places) == F(expected)


# --- B6: growing-season boundaries (Today = the field's local date, the forecast's first date). ---

TOMATO_PLANTED = date(2026, 6, 1)  # season day 180 = 2026-11-27
PEPPER_PLANTED = date(2026, 12, 1)


@pytest.mark.parametrize(
    ("crop_id", "planted", "today", "days", "in_season"),
    [
        ("tomato", TOMATO_PLANTED, date(2026, 11, 21), 7, True),
        ("tomato", TOMATO_PLANTED, date(2026, 11, 22), 7, False),
        ("tomato", TOMATO_PLANTED, date(2026, 11, 22), 6, True),
        ("tomato", TOMATO_PLANTED, date(2026, 11, 27), 1, True),
        ("tomato", TOMATO_PLANTED, date(2026, 11, 28), 1, False),
        ("bell-pepper", PEPPER_PLANTED, date(2026, 11, 30), 7, False),
        ("bell-pepper", PEPPER_PLANTED, date(2026, 12, 1), 7, True),
    ],
)
def test_b6_season_boundaries(crop_id, planted, today, days, in_season):
    crop = CROPS[crop_id]

    if in_season:
        engine.check_season(crop, planted, today, days)
    else:
        with pytest.raises(OutOfSeason):
            engine.check_season(crop, planted, today, days)


def test_b6_out_of_season_plan_is_rejected_whole():
    late_tomato = plot("tomato", TOMATO_PLANTED, awc="83", area="1500", flow="0.6")

    with pytest.raises(OutOfSeason):
        engine.plan_days(late_tomato, weather(date(2026, 11, 22), ["5.0"] * 7))


def test_kc_is_never_invented_outside_the_season():
    with pytest.raises(OutOfSeason):
        engine.kc_on(TOMATO, TOMATO_PLANTED, date(2026, 11, 28))
    with pytest.raises(OutOfSeason):
        engine.kc_on(PEPPER, PEPPER_PLANTED, date(2026, 11, 30))


# --- The early season check, across the field's possible local dates. ---


@pytest.mark.parametrize(
    ("crop_id", "planted", "utc_today", "days", "definitely_out"),
    [
        # Field one day behind the planner on the tomato's last season day: not rejected early.
        ("tomato", TOMATO_PLANTED, date(2026, 11, 28), 1, False),
        ("tomato", TOMATO_PLANTED, date(2026, 11, 29), 1, True),
        # Field one day ahead of the planner on the pepper's planting day: not rejected early.
        ("bell-pepper", PEPPER_PLANTED, date(2026, 11, 30), 7, False),
        ("bell-pepper", PEPPER_PLANTED, date(2026, 11, 29), 7, True),
        # Well inside the season, and far outside it.
        ("tomato", TOMATO_PLANTED, date(2026, 10, 1), 7, False),
        ("tomato", date(2025, 1, 1), date(2026, 11, 21), 7, True),
    ],
)
def test_definitely_out_of_season(crop_id, planted, utc_today, days, definitely_out):
    assert engine.definitely_out_of_season(CROPS[crop_id], planted, utc_today, days) is definitely_out


# --- Kc curve shape. ---


@pytest.mark.parametrize(
    ("crop_id", "day", "kc"),
    [
        ("tomato", 1, "0.60"),
        ("tomato", 35, "0.60"),
        ("tomato", 36, Fraction(3, 5) + Fraction(1, 45) * Fraction(55, 100)),
        ("tomato", 80, "1.15"),
        ("tomato", 150, "1.15"),
        ("tomato", 165, "0.975"),
        ("tomato", 180, "0.80"),
        ("bell-pepper", 30, "0.60"),
        ("bell-pepper", 70, "1.05"),
        ("bell-pepper", 180, "1.05"),
        ("bell-pepper", 210, "0.90"),
    ],
)
def test_kc_by_season_day(crop_id, day, kc):
    planted = date(2026, 1, 1)

    assert engine.kc_on(CROPS[crop_id], planted, planted + timedelta(days=day - 1)) == Fraction(kc)


def test_planting_day_is_day_1():
    assert engine.day_number(date(2026, 11, 1), date(2026, 11, 1)) == 1


def test_season_lengths():
    assert TOMATO.season_length == 180
    assert PEPPER.season_length == 210


# --- Exact arithmetic and invalid inputs. ---


def test_every_calculated_value_is_a_fraction():
    b4 = plot("bell-pepper", date(2026, 8, 1), awc="83", area="500", flow="1.0")

    result = engine.plan_days(b4, weather(date(2026, 11, 20), ["3.5"] * 7))

    values = [result.taw_mm, result.threshold_mm]
    for day in result.days:
        values += [day.et0_mm, day.rain_mm, day.kc, day.litres, day.run_minutes, day.bucket_level_mm]
    assert all(type(value) is Fraction for value in values)


def test_bucket_never_goes_below_zero_when_the_cap_cannot_keep_up():
    tiny_flow = plot("tomato", date(2026, 8, 14), awc="83", area="1500", flow="0.01")

    result = engine.plan_days(tiny_flow, weather(date(2026, 11, 21), ["30"] * 7))

    assert all(day.bucket_level_mm >= 0 for day in result.days)
    assert result.days[-1].bucket_level_mm == 0
    assert all(day.run_minutes == 1440 for day in result.days[1:])


def test_rain_above_a_full_bucket_is_lost():
    sand = plot("tomato", date(2026, 8, 14), awc="83", area="1500", flow="0.6")

    result = engine.plan_days(sand, weather(date(2026, 11, 21), ["1.0"], ["50"]))

    assert result.days[0].bucket_level_mm == F("58.1") - F("1.15")


def test_unknown_crop_is_an_error():
    with pytest.raises(ValueError, match="no crop profile for 'maize'"):
        engine.crop_profile("maize")


@pytest.mark.parametrize(
    "field", ["available_water_mm_per_m", "area_m2", "row_spacing_m", "emitter_spacing_m", "flow_lph_per_emitter"]
)
@pytest.mark.parametrize("bad", [F("0"), F("-1")])
def test_non_positive_plot_value_is_an_error(field, bad):
    values = {
        "available_water_mm_per_m": F("83"),
        "area_m2": F("1500"),
        "row_spacing_m": F("1.5"),
        "emitter_spacing_m": F("0.4"),
        "flow_lph_per_emitter": F("0.6"),
    }
    values[field] = bad

    with pytest.raises(ValueError, match=field):
        engine.plan_days(PlotInputs(crop_id="tomato", planting_date=date(2026, 8, 14), **values), weather(date(2026, 11, 21), ["5"]))


@pytest.mark.parametrize("field", ["et0_mm", "rain_mm"])
def test_negative_weather_value_is_an_error(field):
    day = {"date": date(2026, 11, 21), "et0_mm": F("5"), "rain_mm": F("0")}
    day[field] = F("-0.1")

    with pytest.raises(ValueError, match=field):
        engine.plan_days(plot("tomato", date(2026, 8, 14), "83", "1500", "0.6"), [WeatherDay(**day)])


def test_a_float_input_is_rejected():
    float_plot = PlotInputs(
        crop_id="tomato",
        planting_date=date(2026, 8, 14),
        available_water_mm_per_m=F("83"),
        area_m2=1500.0,
        row_spacing_m=F("1.5"),
        emitter_spacing_m=F("0.4"),
        flow_lph_per_emitter=F("0.6"),
    )

    with pytest.raises(ValueError, match="area_m2 must be a Fraction"):
        engine.plan_days(float_plot, weather(date(2026, 11, 21), ["5"]))


def test_a_float_weather_value_is_rejected():
    days = [WeatherDay(date=date(2026, 11, 21), et0_mm=5.0, rain_mm=F("0"))]

    with pytest.raises(ValueError, match="et0_mm must be a Fraction"):
        engine.plan_days(plot("tomato", date(2026, 8, 14), "83", "1500", "0.6"), days)


def test_no_forecast_days_is_an_error():
    with pytest.raises(ValueError, match="no forecast days"):
        engine.plan_days(plot("tomato", date(2026, 8, 14), "83", "1500", "0.6"), [])


def test_forecast_days_must_follow_one_another():
    days = weather(date(2026, 11, 21), ["5", "5"])
    days[1] = WeatherDay(date=date(2026, 11, 23), et0_mm=F("5"), rain_mm=F("0"))

    with pytest.raises(ValueError, match="consecutive"):
        engine.plan_days(plot("tomato", date(2026, 8, 14), "83", "1500", "0.6"), days)
