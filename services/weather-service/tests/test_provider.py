import copy
import json
import logging
from datetime import timedelta

import httpx2
import pytest
from conftest import ET0, NOW, RAIN, TODAY, FakeProvider, open_meteo_body

from config import load_settings
from provider import ProviderError, fetch_forecast, parse_forecast


def fetch(fake: FakeProvider, now=NOW):
    with fake.client() as client:
        return fetch_forecast(client, load_settings(), 31.25, 34.75, now)


def test_fetch_maps_the_provider_fields():
    forecast = fetch(FakeProvider())

    assert forecast.fetched_at == NOW
    assert forecast.utc_offset_seconds == 7200
    assert [day.date for day in forecast.days] == [TODAY + timedelta(days=i) for i in range(7)]
    assert [day.et0_mm for day in forecast.days] == ET0
    assert [day.rain_mm for day in forecast.days] == RAIN


def test_fetch_asks_for_7_local_days_of_et0_and_precipitation():
    fake = FakeProvider()
    fetch(fake)

    params = fake.requests[0].url.params
    assert str(fake.requests[0].url).startswith("https://provider.test/v1/forecast?")
    assert params["latitude"] == "31.25" and params["longitude"] == "34.75"
    assert params["daily"] == "et0_fao_evapotranspiration,precipitation_sum"
    assert params["forecast_days"] == "7"
    assert params["timezone"] == "auto"
    assert "apikey" not in params


def test_fetch_sends_the_api_key_only_when_set(monkeypatch):
    monkeypatch.setenv("PROVIDER_API_KEY", "paid-plan-key")
    fake = FakeProvider()
    fetch(fake)

    assert fake.requests[0].url.params["apikey"] == "paid-plan-key"


def test_fetched_at_drops_microseconds():
    assert fetch(FakeProvider(), NOW.replace(microsecond=123456)).fetched_at == NOW


def test_fetch_succeeds_on_the_last_retry():
    fake = FakeProvider()
    fake.answer(httpx2.Response(500), httpx2.Response(502), open_meteo_body())

    forecast = fetch(fake)

    assert len(fake.requests) == 3
    assert [day.et0_mm for day in forecast.days] == ET0


def body_without(*path):
    body = copy.deepcopy(open_meteo_body())
    target = body
    for key in path[:-1]:
        target = target[key]
    del target[path[-1]]
    return body


def body_with(value, *path):
    body = copy.deepcopy(open_meteo_body())
    target = body
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    return body


def with_daily_value(field, index, value):
    body = copy.deepcopy(open_meteo_body())
    body["daily"][field][index] = value
    return body


FAILURES = {
    "timeout": httpx2.ReadTimeout("timed out"),
    "connection error": httpx2.ConnectError("refused"),
    "error status": httpx2.Response(500, json={"error": True}),
    "client error status": httpx2.Response(400, json={"error": True, "reason": "bad"}),
    "not JSON": httpx2.Response(200, text="<html>maintenance</html>"),
    "JSON list": httpx2.Response(200, json=[1, 2, 3]),
    "no daily": body_without("daily"),
    "no units": body_without("daily_units"),
    "no ET0": body_without("daily", "et0_fao_evapotranspiration"),
    "no rain": body_without("daily", "precipitation_sum"),
    "no dates": body_without("daily", "time"),
    "no ET0 unit": body_without("daily_units", "et0_fao_evapotranspiration"),
    "no offset": body_without("utc_offset_seconds"),
    "daily not an object": body_with([1], "daily"),
    "ET0 in inches": body_with("inch", "daily_units", "et0_fao_evapotranspiration"),
    "rain in inches": body_with("inch", "daily_units", "precipitation_sum"),
    "offset not a number": body_with("7200", "utc_offset_seconds"),
    "offset a boolean": body_with(True, "utc_offset_seconds"),
    "6 days": open_meteo_body(et0=ET0[:6], rain=RAIN[:6]),
    "ET0 not a list": body_with(3.1, "daily", "et0_fao_evapotranspiration"),
    "ET0 null": with_daily_value("et0_fao_evapotranspiration", 6, None),
    "rain null": with_daily_value("precipitation_sum", 0, None),
    "ET0 a string": with_daily_value("et0_fao_evapotranspiration", 2, "3.1"),
    "ET0 a boolean": with_daily_value("et0_fao_evapotranspiration", 2, False),
    "ET0 negative": with_daily_value("et0_fao_evapotranspiration", 2, -0.1),
    # Python's json module reads a bare NaN, so the check must catch it. json.dumps writes NaN by default.
    "rain NaN": httpx2.Response(200, content=json.dumps(with_daily_value("precipitation_sum", 1, float("nan")))),
    "date not a string": with_daily_value("time", 0, 20261121),
    "date not ISO": with_daily_value("time", 0, "21/11/2026"),
    "starts yesterday": open_meteo_body(start=TODAY - timedelta(days=1)),
    "starts tomorrow": open_meteo_body(start=TODAY + timedelta(days=1)),
    "a day missing": with_daily_value("time", 3, (TODAY + timedelta(days=4)).isoformat()),
    "days out of order": with_daily_value("time", 1, (TODAY + timedelta(days=5)).isoformat()),
}


@pytest.mark.parametrize("answer", FAILURES.values(), ids=FAILURES.keys())
def test_every_failure_is_retried_twice_then_raises(answer, caplog):
    fake = FakeProvider()
    fake.answer(answer)

    with pytest.raises(ProviderError, match="no usable forecast after 3 attempts"):
        fetch(fake)

    assert len(fake.requests) == 3
    assert caplog.text.count("Weather provider attempt") == 3


def test_zero_retries_means_one_attempt(monkeypatch):
    monkeypatch.setenv("PROVIDER_RETRIES", "0")
    fake = FakeProvider()
    fake.answer(httpx2.Response(500))

    with pytest.raises(ProviderError):
        fetch(fake)
    assert len(fake.requests) == 1


def test_failure_log_never_shows_the_api_key(monkeypatch, caplog):
    monkeypatch.setenv("PROVIDER_API_KEY", "paid-plan-key")
    caplog.set_level(logging.WARNING)
    fake = FakeProvider()
    fake.answer(httpx2.ConnectError("refused"))

    with pytest.raises(ProviderError):
        fetch(fake)
    assert "request failed: ConnectError" in caplog.text
    assert "paid-plan-key" not in caplog.text


def test_local_today_follows_the_provider_offset():
    # 23:00 UTC on the 20th is already the 21st in Israel (UTC+2), so a forecast starting on the 21st is right.
    late_evening = NOW.replace(day=20, hour=23)

    forecast = parse_forecast(open_meteo_body(), late_evening)

    assert forecast.days[0].date == TODAY


def test_whole_numbers_and_zero_are_kept_as_given():
    body = open_meteo_body(et0=[3, 0, 2.5, 2.5, 2.5, 2.5, 2.5], rain=[0, 0, 0, 0, 0, 0, 0])

    forecast = parse_forecast(body, NOW)

    assert [day.et0_mm for day in forecast.days][:2] == [3, 0]
    assert all(day.rain_mm == 0 for day in forecast.days)
