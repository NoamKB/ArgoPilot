from datetime import UTC, date, datetime, timedelta

import httpx2
import pytest
from fastapi.testclient import TestClient

from config import Settings
from main import app
from routers.forecast import utc_now

TEST_SETTINGS = {
    "PROVIDER_BASE_URL": "https://provider.test/v1/forecast",
    "PROVIDER_API_KEY": "",
    "PROVIDER_TIMEOUT_SECONDS": "3",
    "PROVIDER_RETRIES": "2",
    "FORECAST_FRESH_HOURS": "3",
    "FORECAST_MAX_STALE_HOURS": "24",
}

# 06:00 UTC is 08:00 in Israel (UTC+2), so the local today is 2026-11-21.
NOW = datetime(2026, 11, 21, 6, 0, tzinfo=UTC)
TODAY = date(2026, 11, 21)
ISRAEL_OFFSET = 7200
ET0 = [3.13, 2.66, 2.59, 2.48, 2.14, 2.32, 2.6]
RAIN = [0.0, 0.0, 4.2, 0.0, 0.0, 1.5, 0.0]


@pytest.fixture(autouse=True)
def test_settings(monkeypatch):
    """Every test uses these settings, never a developer's .env."""
    monkeypatch.setitem(Settings.model_config, "env_file", None)
    for name, value in TEST_SETTINGS.items():
        monkeypatch.setenv(name, value)


def open_meteo_body(start: date = TODAY, et0=ET0, rain=RAIN, offset: int = ISRAEL_OFFSET) -> dict:
    """A body shaped like Open-Meteo's daily forecast (checked against the live API on 2026-11-21)."""
    return {
        "latitude": 31.25,
        "longitude": 34.75,
        "utc_offset_seconds": offset,
        "timezone": "Asia/Jerusalem",
        "daily_units": {"time": "iso8601", "et0_fao_evapotranspiration": "mm", "precipitation_sum": "mm"},
        "daily": {
            "time": [(start + timedelta(days=i)).isoformat() for i in range(len(et0))],
            "et0_fao_evapotranspiration": list(et0),
            "precipitation_sum": list(rain),
        },
    }


class FakeProvider:
    """Stands in for Open-Meteo. Each call takes the next queued answer; the last one repeats.

    An answer is a dict (sent as a 200 JSON body), an httpx2.Response, or an exception to raise.
    """

    def __init__(self) -> None:
        self.answers: list = [open_meteo_body()]
        self.requests: list[httpx2.Request] = []

    def answer(self, *answers) -> None:
        self.answers = list(answers)

    def handler(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(request)
        answer = self.answers.pop(0) if len(self.answers) > 1 else self.answers[0]
        if isinstance(answer, Exception):
            raise answer
        if isinstance(answer, dict):
            return httpx2.Response(200, json=answer)
        return answer

    def client(self) -> httpx2.Client:
        return httpx2.Client(transport=httpx2.MockTransport(self.handler))


class Clock:
    def __init__(self) -> None:
        self.now = NOW

    def advance(self, **delta) -> None:
        self.now += timedelta(**delta)


@pytest.fixture
def fake_provider() -> FakeProvider:
    return FakeProvider()


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def client(fake_provider, clock):
    """The app with an empty cache, the fake provider, and a clock the test controls."""
    app.dependency_overrides[utc_now] = lambda: clock.now
    with TestClient(app) as test_client:  # entering runs the lifespan: settings, a new cache, an httpx2 client
        app.state.http_client = fake_provider.client()
        yield test_client
        app.state.http_client.close()
    app.dependency_overrides.clear()
