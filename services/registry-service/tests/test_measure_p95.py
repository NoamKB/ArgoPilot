from pathlib import Path

from sqlalchemy import make_url

from scripts.measure_p95 import ENDPOINTS, TARGET_P95_MS, benchmark_database, benchmark_passed, p95

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
