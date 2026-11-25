from datetime import date, timedelta

import httpx2
import pytest
from fastapi.testclient import TestClient

from config import Settings
from main import app
from routers.plan import utc_today

TEST_SETTINGS = {
    "REGISTRY_URL": "http://registry.test",
    "WEATHER_URL": "http://weather.test",
    "REGISTRY_TIMEOUT_SECONDS": "3",
    "WEATHER_TIMEOUT_SECONDS": "12",
}

TODAY = date(2026, 11, 21)
PLOT_ID = "3f8a6c2e-1b4d-4e5f-9a7b-0c1d2e3f4a5b"
# Case 3 (worked-examples.md): the seed plot "West block", tomato on sand, mid-season (day 100 today).
PLANTED = TODAY - timedelta(days=99)
ET0 = [6.0, 6.0, 5.0, 6.0, 6.0, 5.5, 6.0]
RAIN = [0.0, 0.0, 5.0, 0.0, 0.0, 0.0, 0.0]
FETCHED_AT = "2026-11-21T06:00:00Z"


@pytest.fixture(autouse=True)
def test_settings(monkeypatch):
    """Every test uses these settings, never a developer's .env."""
    monkeypatch.setitem(Settings.model_config, "env_file", None)
    for name, value in TEST_SETTINGS.items():
        monkeypatch.setenv(name, value)


def plot_body(**changes) -> dict:
    """A body shaped like registry-service's GET /v1/plots/{id}."""
    body = {
        "id": PLOT_ID,
        "farm_id": "0b6a4a2e-7c1d-4f3e-8a9b-1c2d3e4f5a6b",
        "name": "West block",
        "area_m2": 1500.0,
        "crop_id": "tomato",
        "planting_date": PLANTED.isoformat(),
        "soil_id": "sand",
        "row_spacing_m": 1.5,
        "emitter_spacing_m": 0.4,
        "emitter_id": "dripnet-pc-0.6",
        "lat": 31.25,
        "lon": 34.79,
    }
    body.update(changes)
    return body


SOIL = {"id": "sand", "name": "Sand", "available_water_mm_per_m": 83}
EMITTER = {"id": "dripnet-pc-0.6", "name": "DripNet PC", "flow_lph": 0.6}


def forecast_body(days: int = 7, first_day: date = TODAY, et0=ET0, rain=RAIN, stale: bool = False) -> dict:
    """A body shaped like weather-service's GET /v1/forecast."""
    return {
        "lat": 31.25,
        "lon": 34.79,
        "source": "open-meteo",
        "fetched_at": FETCHED_AT,
        "stale": stale,
        "days": [
            {"date": (first_day + timedelta(days=n)).isoformat(), "et0_mm": et0[n], "rain_mm": rain[n]} for n in range(days)
        ],
    }


class FakeService:
    """Stands in for registry-service or weather-service. Answers by URL path; an unknown path is a 404.

    An answer is a dict (sent as a 200 JSON body), an httpx2.Response, an exception to raise,
    or a function of the request that returns one of those.
    """

    def __init__(self, routes: dict) -> None:
        self.routes = routes
        self.requests: list[httpx2.Request] = []

    def handler(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(request)
        answer = self.routes.get(request.url.path, httpx2.Response(404, json={"detail": "Not Found"}))
        if callable(answer):
            answer = answer(request)
        if isinstance(answer, Exception):
            raise answer
        if isinstance(answer, httpx2.Response):
            return answer
        return httpx2.Response(200, json=answer)

    def paths(self) -> list[str]:
        return [request.url.path for request in self.requests]

    def client(self) -> httpx2.Client:
        return httpx2.Client(transport=httpx2.MockTransport(self.handler))


@pytest.fixture
def registry() -> FakeService:
    return FakeService(
        {
            f"/v1/plots/{PLOT_ID}": plot_body(),
            "/v1/soils/sand": SOIL,
            "/v1/emitters/dripnet-pc-0.6": EMITTER,
        }
    )


@pytest.fixture
def weather() -> FakeService:
    return FakeService({"/v1/forecast": lambda request: forecast_body(days=int(request.url.params["days"]))})


class Today:
    def __init__(self) -> None:
        self.date = TODAY


@pytest.fixture
def today() -> Today:
    return Today()


@pytest.fixture
def client(registry, weather, today):
    """The app with fake registry and weather services, and a UTC date the test controls."""
    app.dependency_overrides[utc_today] = lambda: today.date
    with TestClient(app) as test_client:  # entering runs the lifespan: settings and two httpx2 clients
        app.state.registry_client = registry.client()
        app.state.weather_client = weather.client()
        yield test_client
        app.state.registry_client.close()
        app.state.weather_client.close()
    app.dependency_overrides.clear()
