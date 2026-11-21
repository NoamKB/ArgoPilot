import logging

import pytest
from fastapi.testclient import TestClient

from config import ENV_FILE, SERVICE_DIR, Settings, load_settings
from main import app


def test_settings_come_from_the_environment():
    settings = load_settings()

    assert settings.provider_base_url == "https://provider.test/v1/forecast"
    assert settings.provider_timeout_seconds == 3
    assert settings.provider_retries == 2
    assert settings.forecast_fresh_hours == 3
    assert settings.forecast_max_stale_hours == 24
    assert settings.provider_api_key.get_secret_value() == ""


def test_env_file_is_the_one_in_this_service():
    assert ENV_FILE == SERVICE_DIR / ".env"


def test_api_key_may_be_unset(monkeypatch):
    monkeypatch.delenv("PROVIDER_API_KEY")

    assert load_settings().provider_api_key.get_secret_value() == ""


def test_missing_variable_stops_startup_and_names_it(monkeypatch):
    monkeypatch.delenv("PROVIDER_BASE_URL")
    monkeypatch.setenv("PROVIDER_API_KEY", "key-that-must-not-leak")

    with pytest.raises(RuntimeError) as error:
        with TestClient(app):  # entering runs the startup (lifespan)
            pass

    message = str(error.value)
    assert "PROVIDER_BASE_URL: Field required" in message
    assert "key-that-must-not-leak" not in message


@pytest.mark.parametrize(
    ("name", "value"),
    [("PROVIDER_TIMEOUT_SECONDS", "0"), ("PROVIDER_RETRIES", "-1"), ("FORECAST_FRESH_HOURS", "0"), ("PROVIDER_RETRIES", "two")],
)
def test_invalid_value_is_rejected_with_its_name(monkeypatch, name, value):
    monkeypatch.setenv(name, value)

    with pytest.raises(RuntimeError, match=name):
        load_settings()


def test_stale_limit_shorter_than_freshness_is_rejected(monkeypatch):
    monkeypatch.setenv("FORECAST_MAX_STALE_HOURS", "2")

    with pytest.raises(RuntimeError, match="FORECAST_MAX_STALE_HOURS must not be less than FORECAST_FRESH_HOURS"):
        load_settings()


def test_api_key_is_hidden_in_the_settings_repr(monkeypatch):
    monkeypatch.setenv("PROVIDER_API_KEY", "key-that-must-not-leak")

    assert "key-that-must-not-leak" not in repr(Settings())


def test_startup_logs_the_provider_without_the_key(monkeypatch, caplog):
    monkeypatch.setenv("PROVIDER_API_KEY", "key-that-must-not-leak")
    caplog.set_level(logging.INFO, logger="uvicorn.error")

    with TestClient(app):
        pass

    assert "Weather provider: https://provider.test/v1/forecast (fresh 3 h, stale up to 24 h, 2 retries)" in caplog.text
    assert "key-that-must-not-leak" not in caplog.text
