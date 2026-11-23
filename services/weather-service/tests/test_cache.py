import threading
from datetime import timedelta

import pytest
from conftest import NOW, TODAY

from cache import CachedForecast, ForecastCache, cell_centre, grid_cell
from schemas import ForecastDay


@pytest.mark.parametrize(
    ("lat", "lon", "cell"),
    [
        (31.25, 34.79, (312, 347)),
        (31.2, 34.7, (312, 347)),  # the lower edge belongs to the cell
        (31.29999, 34.79999, (312, 347)),
        (31.3, 34.8, (313, 348)),  # a point exactly on the upper edge starts the next cell
        (-0.05, -0.05, (-1, -1)),  # floor, not truncation: -0.05 is below 0
        (0.0, 0.0, (0, 0)),
        (-90, -180, (-900, -1800)),
        (90, 180, (899, 1799)),  # the top edges join the cell below them
        (89.95, 179.95, (899, 1799)),
    ],
)
def test_grid_cell(lat, lon, cell):
    assert grid_cell(lat, lon) == cell


@pytest.mark.parametrize(("lat", "lon"), [(90, 180), (-90, -180), (90, -180), (-90, 180)])
def test_cell_centre_is_a_valid_coordinate_at_the_poles_and_the_date_line(lat, lon):
    centre_lat, centre_lon = cell_centre(grid_cell(lat, lon))

    assert -90 < centre_lat < 90
    assert -180 < centre_lon < 180


def test_cell_centre():
    assert cell_centre((312, 347)) == (31.25, 34.75)
    assert cell_centre((-1, -1)) == (-0.05, -0.05)


def forecast_starting(start, count=7) -> CachedForecast:
    days = tuple(ForecastDay(date=start + timedelta(days=i), et0_mm=3.0, rain_mm=0.0) for i in range(count))
    return CachedForecast(fetched_at=NOW, utc_offset_seconds=7200, days=days)


def test_days_from_today_skips_past_days():
    forecast = forecast_starting(TODAY - timedelta(days=1))

    days = forecast.days_from_today(NOW, 3)

    assert [day.date for day in days] == [TODAY, TODAY + timedelta(days=1), TODAY + timedelta(days=2)]


def test_days_from_today_is_none_when_too_few_are_left():
    forecast = forecast_starting(TODAY - timedelta(days=1))

    assert forecast.days_from_today(NOW, 6) is not None
    assert forecast.days_from_today(NOW, 7) is None


def test_age():
    assert forecast_starting(TODAY).age(NOW + timedelta(hours=2)) == timedelta(hours=2)


def test_cache_keeps_one_forecast_per_cell():
    cache = ForecastCache()
    first, second = forecast_starting(TODAY), forecast_starting(TODAY, count=6)

    assert cache.get((312, 347)) is None
    cache.put((312, 347), first)
    cache.put((313, 347), second)
    assert cache.get((312, 347)) is first
    assert cache.get((313, 347)) is second


def test_cache_is_safe_to_use_from_several_threads():
    cache = ForecastCache()
    forecast = forecast_starting(TODAY)

    def work(index):
        cache.put((index, 0), forecast)
        assert cache.get((index, 0)) is forecast

    threads = [threading.Thread(target=work, args=(i,)) for i in range(50)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert all(cache.get((i, 0)) is forecast for i in range(50))
