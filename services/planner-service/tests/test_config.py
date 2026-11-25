import pytest
from fastapi.testclient import TestClient

from config import ENV_FILE, SERVICE_DIR, load_settings
from main import app


def test_settings_come_from_the_environment():
    settings = load_settings()

    assert settings.registry_url == "http://registry.test"
    assert settings.weather_url == "http://weather.test"
    assert settings.registry_timeout_seconds == 3
    assert settings.weather_timeout_seconds == 12


def test_env_file_is_the_one_in_this_service():
    assert ENV_FILE == SERVICE_DIR / ".env"


@pytest.mark.parametrize("name", ["REGISTRY_URL", "WEATHER_URL", "REGISTRY_TIMEOUT_SECONDS", "WEATHER_TIMEOUT_SECONDS"])
def test_missing_variable_stops_startup_and_names_it(monkeypatch, name):
    monkeypatch.delenv(name)

    with pytest.raises(RuntimeError, match=f"{name}: Field required"):
        with TestClient(app):  # entering runs the startup (lifespan)
            pass


@pytest.mark.parametrize(
    ("name", "value"),
    [("REGISTRY_TIMEOUT_SECONDS", "0"), ("WEATHER_TIMEOUT_SECONDS", "-1"), ("WEATHER_TIMEOUT_SECONDS", "twelve")],
)
def test_invalid_value_is_rejected_with_its_name(monkeypatch, name, value):
    monkeypatch.setenv(name, value)

    with pytest.raises(RuntimeError, match=name):
        load_settings()


def test_startup_logs_both_services_and_timeouts(caplog):
    with caplog.at_level("INFO", logger="uvicorn.error"):
        with TestClient(app):
            pass

    assert "Registry: http://registry.test (timeout 3 s); weather: http://weather.test (timeout 12 s)" in caplog.text
