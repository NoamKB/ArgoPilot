from datetime import UTC, datetime, timedelta

import httpx2
import pytest
from conftest import ET0, RAIN, TODAY, open_meteo_body

from routers.forecast import utc_now

DEMO = "/v1/forecast?lat=31.25&lon=34.79"


def dates(response) -> list[str]:
    return [day["date"] for day in response.json()["days"]]


def assert_unavailable(response) -> None:
    assert response.status_code == 503
    assert response.headers["retry-after"] == "60"
    assert response.json() == {"code": "UNAVAILABLE", "detail": "Weather provider unavailable and no usable cached forecast."}


# --- FR-2.3: the forecast ---


def test_forecast_returns_7_days_from_today(client):
    response = client.get(f"{DEMO}&days=7")

    assert response.status_code == 200
    assert response.json() == {
        "lat": 31.25,
        "lon": 34.79,
        "source": "open-meteo",
        "fetched_at": "2026-11-21T06:00:00Z",
        "stale": False,
        "days": [
            {"date": (TODAY + timedelta(days=i)).isoformat(), "et0_mm": ET0[i], "rain_mm": RAIN[i]} for i in range(7)
        ],
    }


def test_days_defaults_to_7(client):
    assert len(client.get(DEMO).json()["days"]) == 7


@pytest.mark.parametrize("days", [1, 3, 7])
def test_days_limits_the_answer_to_the_first_days(client, days):
    assert dates(client.get(f"{DEMO}&days={days}")) == [(TODAY + timedelta(days=i)).isoformat() for i in range(days)]


def test_utc_now_is_the_current_utc_time():
    before = datetime.now(UTC)
    now = utc_now()

    assert now.tzinfo is UTC
    assert before <= now <= datetime.now(UTC)


def test_provider_is_asked_about_the_cell_centre(client, fake_provider):
    client.get(DEMO)

    params = fake_provider.requests[0].url.params
    assert (params["latitude"], params["longitude"]) == ("31.25", "34.75")


# --- FR-2.4: validation ---


@pytest.mark.parametrize("query", ["lat=90&lon=180", "lat=-90&lon=-180", "lat=0&lon=0&days=1", "lat=0&lon=0&days=7"])
def test_boundary_values_are_accepted(client, query):
    assert client.get(f"/v1/forecast?{query}").status_code == 200


@pytest.mark.parametrize(
    ("query", "detail"),
    [
        ("lat=90.0001&lon=0", "lat: Input should be less than or equal to 90"),
        ("lat=-90.0001&lon=0", "lat: Input should be greater than or equal to -90"),
        ("lat=0&lon=180.0001", "lon: Input should be less than or equal to 180"),
        ("lat=0&lon=-181", "lon: Input should be greater than or equal to -180"),
        ("lat=0&lon=0&days=0", "days: Input should be greater than or equal to 1"),
        ("lat=0&lon=0&days=8", "days: Input should be less than or equal to 7"),
        ("lat=0&lon=0&days=2.5", "days: Input should be a valid integer, unable to parse string as an integer"),
        ("lon=0", "lat: Field required"),
        ("lat=0", "lon: Field required"),
        ("lat=north&lon=0", "lat: Input should be a valid number, unable to parse string as a number"),
        ("lat=nan&lon=0", None),
        ("lat=0&lon=inf", None),
    ],
)
def test_invalid_query_returns_422_validation(client, fake_provider, query, detail):
    response = client.get(f"/v1/forecast?{query}")

    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION"
    if detail is not None:
        assert response.json()["detail"] == detail
    assert fake_provider.requests == []


def test_every_invalid_parameter_is_listed(client):
    response = client.get("/v1/forecast?lat=91&lon=0&days=0")

    assert response.json() == {
        "code": "VALIDATION",
        "detail": "lat: Input should be less than or equal to 90; days: Input should be greater than or equal to 1",
    }


# --- FR-2.5: one forecast per 0.1° cell, fresh for 3 hours ---


def test_points_in_the_same_cell_share_one_provider_call(client, fake_provider):
    first = client.get("/v1/forecast?lat=31.21&lon=34.71")
    second = client.get("/v1/forecast?lat=31.29&lon=34.79&days=3")

    assert len(fake_provider.requests) == 1
    assert second.json()["days"] == first.json()["days"][:3]
    assert (second.json()["lat"], second.json()["lon"]) == (31.29, 34.79)  # each answer echoes its own point


@pytest.mark.parametrize("other", ["lat=31.19&lon=34.79", "lat=31.25&lon=34.69", "lat=31.3&lon=34.79"])
def test_a_neighbouring_cell_gets_its_own_provider_call(client, fake_provider, other):
    client.get(DEMO)
    client.get(f"/v1/forecast?{other}")

    assert len(fake_provider.requests) == 2


def test_fresh_forecast_is_served_without_a_provider_call(client, fake_provider, clock):
    client.get(DEMO)
    clock.advance(hours=2, minutes=59)

    response = client.get(DEMO)

    assert len(fake_provider.requests) == 1
    assert response.json()["stale"] is False
    assert response.json()["fetched_at"] == "2026-11-21T06:00:00Z"


def test_after_3_hours_the_forecast_is_fetched_again(client, fake_provider, clock):
    client.get(DEMO)
    clock.advance(hours=3)

    response = client.get(DEMO)

    assert len(fake_provider.requests) == 2
    assert response.json()["fetched_at"] == "2026-11-21T09:00:00Z"


def test_after_local_midnight_a_fresh_forecast_with_too_few_days_is_fetched_again(client, fake_provider, clock):
    # Fetched at 23:30 local (21:30 UTC); one hour later it is still fresh, but the 21st is over.
    clock.now = clock.now.replace(hour=21, minute=30)
    client.get(DEMO)
    clock.advance(hours=1)
    fake_provider.answer(open_meteo_body(start=TODAY + timedelta(days=1)))

    short = client.get(f"{DEMO}&days=6")
    full = client.get(f"{DEMO}&days=7")

    assert dates(short)[0] == (TODAY + timedelta(days=1)).isoformat()  # 6 days are left: served from the cache
    assert len(fake_provider.requests) == 2  # 7 days are not: fetched again
    assert dates(full) == [(TODAY + timedelta(days=i)).isoformat() for i in range(1, 8)]


# --- FR-2.6: provider failures and stale forecasts ---


def test_provider_failure_serves_the_last_forecast_as_stale(client, fake_provider, clock):
    fresh = client.get(DEMO).json()
    clock.advance(hours=5)
    fake_provider.answer(httpx2.Response(500))

    response = client.get(DEMO)

    assert response.status_code == 200
    assert response.json() == {**fresh, "stale": True}
    assert len(fake_provider.requests) == 1 + 3  # the first fetch, then one attempt and two retries


def test_stale_answer_starts_at_today(client, fake_provider, clock):
    client.get(DEMO)
    clock.advance(hours=20)  # 02:00 local on the 22nd
    fake_provider.answer(httpx2.ReadTimeout("timed out"))

    response = client.get(f"{DEMO}&days=6")

    assert response.json()["stale"] is True
    assert dates(response) == [(TODAY + timedelta(days=i)).isoformat() for i in range(1, 7)]


def test_stale_forecast_is_served_up_to_24_hours(client, fake_provider, clock):
    client.get(f"{DEMO}&days=1")
    clock.advance(hours=24)
    fake_provider.answer(httpx2.Response(503))

    response = client.get(f"{DEMO}&days=6")

    assert response.status_code == 200
    assert response.json()["stale"] is True


def test_a_recovered_provider_replaces_the_stale_forecast(client, fake_provider, clock):
    client.get(DEMO)
    clock.advance(hours=4)
    fake_provider.answer(httpx2.Response(500), httpx2.Response(500), httpx2.Response(500), open_meteo_body())
    assert client.get(DEMO).json()["stale"] is True

    response = client.get(DEMO)

    assert response.json()["stale"] is False
    assert response.json()["fetched_at"] == "2026-11-21T10:00:00Z"


# --- FR-2.7 and FR-2.8: no usable forecast means 503, never invented numbers ---


def test_provider_failure_without_a_cached_forecast_returns_503(client, fake_provider):
    fake_provider.answer(httpx2.ConnectError("refused"))

    assert_unavailable(client.get(DEMO))
    assert len(fake_provider.requests) == 3


def test_a_forecast_from_another_cell_is_never_used(client, fake_provider):
    client.get(DEMO)
    fake_provider.answer(httpx2.Response(500))

    assert_unavailable(client.get("/v1/forecast?lat=31.35&lon=34.79"))


def test_stale_forecast_older_than_24_hours_returns_503(client, fake_provider, clock):
    client.get(f"{DEMO}&days=1")
    clock.advance(hours=24, seconds=1)
    fake_provider.answer(httpx2.Response(500))

    assert_unavailable(client.get(f"{DEMO}&days=1"))


def test_stale_forecast_with_too_few_days_left_returns_503(client, fake_provider, clock):
    client.get(DEMO)
    clock.advance(hours=20)  # the 22nd: 6 days are left
    fake_provider.answer(httpx2.Response(500))

    assert_unavailable(client.get(f"{DEMO}&days=7"))


def test_a_forecast_with_a_missing_value_returns_503_not_zeros(client, fake_provider):
    body = open_meteo_body()
    body["daily"]["et0_fao_evapotranspiration"][6] = None
    fake_provider.answer(body)

    response = client.get(f"{DEMO}&days=1")  # day 7 is not even asked for: the whole forecast is refused

    assert_unavailable(response)


def test_a_forecast_with_a_missing_day_returns_503(client, fake_provider):
    fake_provider.answer(open_meteo_body(et0=ET0[:6], rain=RAIN[:6]))

    assert_unavailable(client.get(f"{DEMO}&days=6"))
