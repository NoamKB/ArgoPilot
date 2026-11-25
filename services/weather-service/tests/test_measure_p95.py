import itertools
import json
import runpy
import sys
import urllib.request
from datetime import UTC, datetime, time, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from provider import parse_forecast
from scripts import measure_p95
from scripts.measure_p95 import (
    PATHS,
    TARGET_P95_MS,
    benchmark_passed,
    fake_forecast_body,
    fake_provider,
    free_port,
    p95,
    run_benchmark,
    wait_until_up,
)

SCRIPT = Path(measure_p95.__file__)
FAST_MS = 10.0
SLOW_MS = 200.0


def fast_results(samples_per_path: int = 20) -> list[tuple[str, int, float]]:
    return [(path, 200, FAST_MS) for path in PATHS for _ in range(samples_per_path)]


def test_p95():
    assert p95([float(i) for i in range(1, 101)]) == 95.0


def test_all_fast_paths_with_one_provider_call_pass():
    assert benchmark_passed(fast_results(), provider_calls=1)


@pytest.mark.parametrize("calls", [0, 2])
def test_any_provider_call_besides_the_warm_up_fails(calls):
    assert not benchmark_passed(fast_results(), provider_calls=calls)


def test_one_slow_path_fails_even_when_overall_p95_passes():
    results = fast_results()
    slow = [i for i, (path, _, _) in enumerate(results) if path == PATHS[0]][:2]
    for index in slow:
        results[index] = (PATHS[0], 200, SLOW_MS)

    assert p95([latency for _, _, latency in results]) <= TARGET_P95_MS
    assert not benchmark_passed(results, provider_calls=1)


def test_slow_overall_fails():
    assert not benchmark_passed([(path, 200, SLOW_MS) for path, _, _ in fast_results()], provider_calls=1)


def test_missing_path_fails():
    assert not benchmark_passed([r for r in fast_results() if r[0] != PATHS[-1]], provider_calls=1)


def test_non_200_response_fails():
    results = fast_results()
    results[0] = (results[0][0], 503, FAST_MS)
    assert not benchmark_passed(results, provider_calls=1)


def test_no_results_fail():
    assert not benchmark_passed([], provider_calls=1)


def test_fake_forecast_body_passes_the_provider_check():
    now = datetime.now(UTC)
    assert len(parse_forecast(fake_forecast_body(), now).days) == 7


@pytest.mark.parametrize("hour", [0, 6, 12, 23])
def test_fake_point_is_at_local_noon_so_a_run_never_crosses_local_midnight(hour):
    # Without this, a run that started at 23:59 UTC would need a new forecast at midnight and fail.
    now = datetime(2026, 11, 21, hour, 59, 30, tzinfo=UTC)
    forecast = parse_forecast(fake_forecast_body(now), now)

    assert (now + timedelta(seconds=forecast.utc_offset_seconds)).time() == time(12, 0)
    assert forecast.days_from_today(now + timedelta(hours=11, minutes=59), 7) is not None


def test_fake_provider_answers_and_counts_calls():
    with fake_provider() as (url, calls):
        with urllib.request.urlopen(f"{url}?latitude=31.25", timeout=5) as response:
            body = json.loads(response.read())

    assert body["daily"]["et0_fao_evapotranspiration"] == fake_forecast_body()["daily"]["et0_fao_evapotranspiration"]
    assert calls == ["/v1/forecast?latitude=31.25"]


def test_free_port_can_be_bound():
    assert 0 < free_port() < 65536


def test_wait_until_up_retries_then_raises_after_the_deadline(monkeypatch):
    clock = iter([0, 0, 11])  # start (deadline 10), after the first failure, after the second
    sleeps = []
    monkeypatch.setattr(measure_p95, "time", SimpleNamespace(monotonic=lambda: next(clock), sleep=sleeps.append))

    with pytest.raises(OSError):
        wait_until_up(f"http://127.0.0.1:{free_port()}")  # nothing listens there
    assert sleeps == [0.1]


def test_run_benchmark_records_path_status_and_latency(monkeypatch):
    # Any HTTP server will do here: the fake provider answers every GET with 200.
    with fake_provider() as (url, _):
        base = url.removesuffix("/v1/forecast")
        monkeypatch.setattr(measure_p95, "PATHS", ["/v1/forecast?x=1"])
        results = run_benchmark(base, rate=50, duration=0.04)

    assert [status for _, status, _ in results] == [200, 200]
    assert all(latency > 0 for _, _, latency in results)


def test_run_benchmark_records_the_error_code(monkeypatch):
    def not_found(url, timeout):
        raise urllib.error.HTTPError(url, 404, "Not Found", None, None)

    monkeypatch.setattr(measure_p95.urllib.request, "urlopen", not_found)

    results = run_benchmark("http://127.0.0.1:1", rate=50, duration=0.04)

    assert [status for _, status, _ in results] == [404, 404]


def test_run_benchmark_records_0_without_a_server_and_never_waits_when_behind(monkeypatch):
    clock = itertools.count(start=1000)  # one second per reading: every request is already late
    sleeps = []
    monkeypatch.setattr(measure_p95, "time", SimpleNamespace(perf_counter=lambda: next(clock), sleep=sleeps.append))

    results = run_benchmark(f"http://127.0.0.1:{free_port()}", rate=10, duration=0.3)

    assert [status for _, status, _ in results] == [0, 0, 0]
    assert sleeps == []


def test_script_runs_end_to_end_and_exit_code_matches_verdict(monkeypatch, capsys):
    # A short real run: the fake provider, a real uvicorn server, 25 requests.
    # It checks that the script works, not how fast this machine is.
    monkeypatch.setattr(sys, "argv", ["measure_p95.py", "--rate", "50", "--duration", "0.5"])

    with pytest.raises(SystemExit) as exit_info:
        runpy.run_path(str(SCRIPT), run_name="__main__")

    output = capsys.readouterr().out
    assert "Sending 25 requests at 50 rps for 0.5 s" in output
    assert "Non-200 responses: 0 of 25" in output
    assert "Provider calls: 1 (expected 1, the warm-up)" in output
    assert output.splitlines()[-1].endswith("PASS" if exit_info.value.code == 0 else "FAIL")


def test_report_without_successful_responses_fails(monkeypatch, capsys):
    # As if the service broke during the run: every request answered 503.
    monkeypatch.setattr(measure_p95, "run_benchmark", lambda base_url, rate, duration: [(path, 503, 1.0) for path in PATHS])
    monkeypatch.setattr(sys, "argv", ["measure_p95.py", "--duration", "1"])

    assert measure_p95.main() == 1

    output = capsys.readouterr().out
    assert output.count("no successful responses") == len(PATHS)
    assert "ALL" not in output
    assert output.splitlines()[-1].endswith("FAIL")
