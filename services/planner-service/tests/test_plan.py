from datetime import date, timedelta

import httpx2
import pytest
from fastapi.testclient import TestClient

from main import app
from tests.conftest import ET0, FETCHED_AT, PLOT_ID, RAIN, TODAY, forecast_body, plot_body

URL = f"/v1/plots/{PLOT_ID}/plan"
OUT_OF_SEASON = {"code": "PLOT_OUT_OF_SEASON", "detail": "The plot is outside its growing season."}
REGISTRY_DOWN = {"code": "UPSTREAM_UNAVAILABLE", "detail": "registry-service is unavailable or did not answer in time."}
WEATHER_DOWN = {"code": "UPSTREAM_UNAVAILABLE", "detail": "weather-service is unavailable or did not answer in time."}

# Case 3 API values (worked-examples.md): kc, litres, run_minutes, bucket_level_mm.
CASE_3 = [
    (1.15, 0, 0, 51.2),
    (1.15, 0, 0, 44.3),
    (1.15, 0, 0, 43.55),
    (1.15, 0, 0, 36.65),
    (1.15, 0, 0, 29.75),
    (1.15, 36000, 1440, 47.425),
    (1.15, 0, 0, 40.525),
]


def test_plan_reproduces_case_3_end_to_end(client):
    response = client.get(URL)

    assert response.status_code == 200
    assert response.json() == {
        "plot_id": PLOT_ID,
        "crop_id": "tomato",
        "taw_mm": 58.1,
        "threshold_mm": 29.05,
        "forecast_fetched_at": FETCHED_AT,
        "days": [
            {
                "date": (TODAY + timedelta(days=n)).isoformat(),
                "et0_mm": ET0[n],
                "rain_mm": RAIN[n],
                "kc": kc,
                "litres": litres,
                "run_minutes": minutes,
                "bucket_level_mm": level,
                "stale": False,
            }
            for n, (kc, litres, minutes, level) in enumerate(CASE_3)
        ],
    }


def test_plan_asks_registry_then_weather_for_the_plot_point(client, registry, weather):
    client.get(URL)

    assert registry.paths() == [f"/v1/plots/{PLOT_ID}", "/v1/soils/sand", "/v1/emitters/dripnet-pc-0.6"]
    assert len(weather.requests) == 1
    assert dict(weather.requests[0].url.params) == {"lat": "31.25", "lon": "34.79", "days": "7"}


def test_registry_and_weather_base_urls_come_from_settings(client, registry, weather):
    client.get(URL)

    assert str(registry.requests[0].url).startswith("http://registry.test/v1/plots/")
    assert str(weather.requests[0].url).startswith("http://weather.test/v1/forecast?")


@pytest.mark.parametrize("days", [1, 3, 7])
def test_days_sets_the_plan_length(client, weather, days):
    response = client.get(URL, params={"days": days})

    assert response.status_code == 200
    assert len(response.json()["days"]) == days
    assert weather.requests[0].url.params["days"] == str(days)
    assert response.json()["days"][0]["date"] == TODAY.isoformat()  # the first day is today


def test_et0_and_rain_are_shown_as_weather_service_sent_them(client, weather):
    weather.routes["/v1/forecast"] = forecast_body(days=1, et0=[3.13], rain=[0.1])

    day = client.get(URL, params={"days": 1}).json()["days"][0]

    assert (day["et0_mm"], day["rain_mm"]) == (3.13, 0.1)


# --- 422 VALIDATION ---


@pytest.mark.parametrize("days", ["0", "8", "-1", "abc", "2.5", ""])
def test_bad_days_is_422_and_calls_no_service(client, registry, weather, days):
    response = client.get(URL, params={"days": days})

    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION"
    assert response.json()["detail"].startswith("days: ")
    assert registry.requests == [] and weather.requests == []


def test_plot_id_that_is_not_a_uuid_is_422_and_calls_no_service(client, registry):
    response = client.get("/v1/plots/not-a-uuid/plan")

    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION"
    assert response.json()["detail"].startswith("plot_id: ")
    assert registry.requests == []


# --- 404 NOT_FOUND ---


def test_unknown_plot_is_404_and_weather_is_not_called(client, registry, weather):
    del registry.routes[f"/v1/plots/{PLOT_ID}"]

    response = client.get(URL)

    assert response.status_code == 404
    assert response.json() == {"code": "NOT_FOUND", "detail": "Plot not found."}
    assert weather.requests == []


# --- 409 PLOT_OUT_OF_SEASON ---


def test_clearly_out_of_season_plot_is_409_without_soil_emitter_or_weather_calls(client, registry, weather):
    registry.routes[f"/v1/plots/{PLOT_ID}"] = plot_body(planting_date="2025-01-01")
    weather.routes["/v1/forecast"] = httpx2.ConnectError("weather is down")  # JL-020: 409 even then

    response = client.get(URL)

    assert response.status_code == 409
    assert response.json() == OUT_OF_SEASON
    assert registry.paths() == [f"/v1/plots/{PLOT_ID}"]
    assert weather.requests == []


def test_planner_a_day_ahead_of_the_field_on_the_last_season_day_still_plans(client, registry, weather, today):
    # Tomato planted 2026-06-01: day 180, the last season day, is 2026-11-27 at the field.
    registry.routes[f"/v1/plots/{PLOT_ID}"] = plot_body(planting_date="2026-06-01")
    weather.routes["/v1/forecast"] = forecast_body(days=1, first_day=date(2026, 11, 27))
    today.date = date(2026, 11, 28)  # UTC is already the next day

    response = client.get(URL, params={"days": 1})

    assert response.status_code == 200
    assert response.json()["days"][0]["date"] == "2026-11-27"
    assert response.json()["days"][0]["kc"] == 0.8


def test_planner_a_day_behind_the_field_on_the_planting_day_still_plans(client, registry, weather, today):
    registry.routes[f"/v1/plots/{PLOT_ID}"] = plot_body(crop_id="bell-pepper", planting_date="2026-12-01")
    weather.routes["/v1/forecast"] = forecast_body(days=7, first_day=date(2026, 12, 1))
    today.date = date(2026, 11, 30)  # UTC is still the day before

    response = client.get(URL)

    assert response.status_code == 200
    assert response.json()["days"][0]["date"] == "2026-12-01"
    assert {day["kc"] for day in response.json()["days"]} == {0.6}


def test_forecast_dates_outside_the_season_are_409_after_the_weather_call(client, registry, weather, today):
    registry.routes[f"/v1/plots/{PLOT_ID}"] = plot_body(planting_date="2026-06-01")
    weather.routes["/v1/forecast"] = forecast_body(days=1, first_day=date(2026, 11, 28))  # the field is on day 181
    today.date = date(2026, 11, 27)

    response = client.get(URL, params={"days": 1})

    assert response.status_code == 409
    assert response.json() == OUT_OF_SEASON
    assert len(weather.requests) == 1


# --- Stale forecast (FR-2.13) ---


def test_stale_forecast_still_plans_with_every_day_stale(client, weather):
    weather.routes["/v1/forecast"] = forecast_body(stale=True)

    response = client.get(URL)

    assert response.status_code == 200
    assert [day["stale"] for day in response.json()["days"]] == [True] * 7
    assert response.json()["forecast_fetched_at"] == FETCHED_AT
    assert [day["run_minutes"] for day in response.json()["days"]] == [row[2] for row in CASE_3]


# --- 503 UPSTREAM_UNAVAILABLE (FR-2.14): never a plan of zeros ---


def plot_path() -> str:
    return f"/v1/plots/{PLOT_ID}"


@pytest.mark.parametrize(
    ("path", "answer"),
    [
        (plot_path(), httpx2.ConnectError("connection refused")),
        (plot_path(), httpx2.ReadTimeout("too slow")),
        (plot_path(), httpx2.Response(500, json={"detail": "Internal Server Error"})),
        (plot_path(), httpx2.Response(503, json={"detail": "Database unavailable"})),
        (plot_path(), httpx2.Response(200, text="not json")),
        (plot_path(), httpx2.Response(200, json=["not", "an", "object"])),
        (plot_path(), plot_body(area_m2=0)),
        (plot_path(), plot_body(row_spacing_m=-1.5)),
        (plot_path(), plot_body(emitter_spacing_m=None)),
        (plot_path(), plot_body(area_m2=True)),
        (plot_path(), plot_body(area_m2="1500")),
        (plot_path(), plot_body(planting_date="not a date")),
        (plot_path(), plot_body(crop_id=None)),
        (plot_path(), plot_body(lat=None)),
        (plot_path(), plot_body(lon=False)),
        (plot_path(), {key: value for key, value in plot_body().items() if key != "soil_id"}),
        ("/v1/soils/sand", httpx2.Response(404, json={"detail": "Soil not found"})),
        ("/v1/soils/sand", httpx2.ReadTimeout("too slow")),
        ("/v1/soils/sand", {"id": "sand", "name": "Sand"}),
        ("/v1/soils/sand", {"id": "sand", "name": "Sand", "available_water_mm_per_m": 0}),
        ("/v1/emitters/dripnet-pc-0.6", httpx2.Response(404, json={"detail": "Emitter not found"})),
        ("/v1/emitters/dripnet-pc-0.6", {"id": "dripnet-pc-0.6", "name": "DripNet PC", "flow_lph": None}),
        ("/v1/emitters/dripnet-pc-0.6", {"id": "dripnet-pc-0.6", "name": "DripNet PC", "flow_lph": -0.6}),
    ],
)
def test_registry_failure_is_503_naming_registry(client, registry, weather, path, answer):
    registry.routes[path] = answer

    response = client.get(URL)

    assert response.status_code == 503
    assert response.json() == REGISTRY_DOWN
    assert weather.requests == []


def bad_forecast(**changes) -> dict:
    body = forecast_body()
    body.update(changes)
    return body


def with_day(n: int, **changes) -> dict:
    body = forecast_body()
    body["days"][n].update(changes)
    return body


@pytest.mark.parametrize(
    "answer",
    [
        httpx2.ConnectError("connection refused"),
        httpx2.ReadTimeout("longer than WEATHER_TIMEOUT_SECONDS"),
        httpx2.Response(503, json={"code": "UNAVAILABLE", "detail": "Weather provider unavailable"}),
        httpx2.Response(422, json={"code": "VALIDATION", "detail": "lat: ..."}),
        httpx2.Response(200, text="not json"),
        forecast_body(days=6),  # too few days
        bad_forecast(days=[]),
        bad_forecast(days=None),
        bad_forecast(stale="false"),
        bad_forecast(fetched_at="yesterday"),
        {key: value for key, value in forecast_body().items() if key != "stale"},
        with_day(3, et0_mm=None),
        with_day(3, rain_mm=-0.1),
        with_day(3, et0_mm="6.0"),
        with_day(3, date="2026-11-30"),  # not consecutive
        with_day(0, date=None),
        {key: value for key, value in forecast_body().items() if key != "days"},
    ],
)
def test_weather_failure_is_503_naming_weather(client, weather, answer):
    weather.routes["/v1/forecast"] = answer

    response = client.get(URL)

    assert response.status_code == 503
    assert response.json() == WEATHER_DOWN


def test_nan_or_infinite_weather_value_is_503(client, weather):
    # Python's json writes and reads bare NaN / Infinity, so a buggy upstream could send them.
    weather.routes["/v1/forecast"] = httpx2.Response(
        200, content=b'{"fetched_at": "2026-11-21T06:00:00Z", "stale": false, "days": [{"date": "2026-11-21", "et0_mm": NaN, "rain_mm": Infinity}]}'
    )

    response = client.get(URL, params={"days": 1})

    assert response.status_code == 503
    assert response.json() == WEATHER_DOWN


def test_upstream_failure_reason_is_logged(client, registry, caplog):
    registry.routes[f"/v1/plots/{PLOT_ID}"] = httpx2.ConnectError("connection refused")

    with caplog.at_level("WARNING"):
        client.get(URL)

    assert "registry-service: request failed: ConnectError" in caplog.text


# --- A crop the planner has no profile for: a bug, not a plan ---


def test_unknown_crop_is_a_500_not_a_plan(registry, weather, today):
    registry.routes[f"/v1/plots/{PLOT_ID}"] = plot_body(crop_id="maize")
    with TestClient(app, raise_server_exceptions=False) as test_client:
        app.state.registry_client = registry.client()
        app.state.weather_client = weather.client()
        response = test_client.get(URL)

    assert response.status_code == 500
    assert weather.requests == []
