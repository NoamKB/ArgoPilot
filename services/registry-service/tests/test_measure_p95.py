import itertools
import runpy
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import make_url

from scripts import measure_p95
from scripts.measure_p95 import (
    ENDPOINTS,
    TARGET_P95_MS,
    benchmark_database,
    benchmark_passed,
    free_port,
    p95,
    run_benchmark,
    wait_until_up,
)

SCRIPT = Path(measure_p95.__file__)
UNKNOWN_FARM_PATH = "/v1/farms/00000000-0000-4000-8000-000000000000"

FAST_MS = 10.0
SLOW_MS = 200.0


def fast_results(samples_per_endpoint: int = 10) -> list[tuple[str, int, float]]:
    return [(path, 200, FAST_MS) for path in ENDPOINTS for _ in range(samples_per_endpoint)]


def test_all_fast_endpoints_pass():
    assert benchmark_passed(fast_results())


def test_one_slow_endpoint_fails_even_when_overall_p95_passes():
    results = fast_results()
    slow_path = ENDPOINTS[0]
    slow_count = 0
    for index, (path, status, _) in enumerate(results):
        if path == slow_path and slow_count < 5:
            results[index] = (path, status, SLOW_MS)
            slow_count += 1

    assert p95([latency for _, _, latency in results]) <= TARGET_P95_MS
    assert p95([latency for path, _, latency in results if path == slow_path]) > TARGET_P95_MS
    assert not benchmark_passed(results)


def test_missing_endpoint_fails():
    results = [result for result in fast_results() if result[0] != ENDPOINTS[-1]]
    assert not benchmark_passed(results)


def test_non_200_response_fails():
    results = fast_results()
    path, _, latency = results[0]
    results[0] = (path, 500, latency)
    assert not benchmark_passed(results)


def test_default_benchmark_database_is_a_seeded_temporary_sqlite_file():
    with benchmark_database(None) as url:
        path = Path(make_url(url).database)
        assert url.startswith("sqlite:///") and path.exists()
    assert not path.exists()


def test_given_database_url_is_used_unchanged():
    given = "postgresql+psycopg://user:pw@127.0.0.1:5435/agropilot_bench"
    with benchmark_database(given) as url:
        assert url == given


def test_no_results_fail():
    assert not benchmark_passed([])


def test_free_port_can_be_bound():
    port = free_port()
    assert 0 < port < 65536


def test_wait_until_up_returns_when_health_answers(live_server):
    assert wait_until_up(live_server) is None


def test_wait_until_up_retries_then_raises_after_the_deadline(monkeypatch):
    # A fake clock: start at 0 (deadline 10), still 0 after the first failure, then 11.
    clock = iter([0, 0, 11])
    sleeps = []
    fake_time = SimpleNamespace(monotonic=lambda: next(clock), sleep=sleeps.append)
    monkeypatch.setattr(measure_p95, "time", fake_time)

    with pytest.raises(OSError):
        wait_until_up(f"http://127.0.0.1:{free_port()}")  # nothing listens there
    assert sleeps == [0.1]  # one retry before giving up


def test_run_benchmark_records_path_status_and_latency(live_server):
    results = run_benchmark(live_server, rate=50, duration=0.2)

    assert sorted(path for path, _, _ in results) == sorted(ENDPOINTS[i % len(ENDPOINTS)] for i in range(10))
    assert {status for _, status, _ in results} == {200}
    assert all(latency > 0 for _, _, latency in results)


def test_run_benchmark_records_http_error_status(live_server, monkeypatch):
    monkeypatch.setattr(measure_p95, "ENDPOINTS", [UNKNOWN_FARM_PATH])

    results = run_benchmark(live_server, rate=50, duration=0.04)

    assert [status for _, status, _ in results] == [404, 404]


def test_run_benchmark_records_0_without_a_server_and_never_waits_when_behind(monkeypatch):
    # A fake clock that moves one second per reading: every request is already late,
    # so the loop sends it at once instead of sleeping.
    clock = itertools.count(start=1000)
    sleeps = []
    fake_time = SimpleNamespace(perf_counter=lambda: next(clock), sleep=sleeps.append)
    monkeypatch.setattr(measure_p95, "time", fake_time)

    results = run_benchmark(f"http://127.0.0.1:{free_port()}", rate=10, duration=0.3)

    assert [status for _, status, _ in results] == [0, 0, 0]
    assert sleeps == []


def test_script_runs_end_to_end_and_exit_code_matches_verdict(monkeypatch, capsys):
    # A short real run: a temporary seeded SQLite file, a real uvicorn server, 25 requests.
    # It checks that the script works, not how fast this machine is.
    monkeypatch.setattr(sys, "argv", ["measure_p95.py", "--rate", "50", "--duration", "0.5"])

    with pytest.raises(SystemExit) as exit_info:
        runpy.run_path(str(SCRIPT), run_name="__main__")

    output = capsys.readouterr().out
    assert "Sending 25 requests at 50 rps for 0.5 s" in output
    assert "Non-200 responses: 0 of 25" in output
    assert output.splitlines()[-1].endswith("PASS" if exit_info.value.code == 0 else "FAIL")


def test_report_without_successful_responses_fails(monkeypatch, capsys):
    # As if the database went down during the run: every request answered 503.
    monkeypatch.setattr(measure_p95, "run_benchmark", lambda base_url, rate, duration: [(path, 503, 1.0) for path in ENDPOINTS])
    monkeypatch.setattr(sys, "argv", ["measure_p95.py", "--duration", "1"])

    assert measure_p95.main() == 1

    output = capsys.readouterr().out
    assert output.count("no successful responses") == len(ENDPOINTS)
    assert "ALL" not in output  # no overall line without a single successful request
    assert f"Non-200 responses: {len(ENDPOINTS)} of {len(ENDPOINTS)}" in output
    assert output.splitlines()[-1].endswith("FAIL")
