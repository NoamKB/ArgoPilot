"""NFR-2.3 benchmark: p95 latency of fresh forecasts (no provider call) at a fixed request rate.

Starts a small fake Open-Meteo server and uvicorn pointed at it, so no network is needed. Warms the cache
with one request, then sends requests on a fixed schedule (open loop) and reports p95 per path and overall.
Latency is measured from each request's scheduled send time, so a slow server cannot hide its delay.
Exits with status 1 if any response is not 200, if the overall p95 or any path's p95 exceeds the target,
or if the fake provider was called more than once (every request after the first must come from the cache).
"""

import argparse
import json
import math
import os
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

SERVICE_DIR = Path(__file__).resolve().parent.parent
TARGET_P95_MS = 100

# All in the same 0.1° cell, so the whole run needs one provider call.
PATHS = [
    "/v1/forecast?lat=31.25&lon=34.79&days=7",
    "/v1/forecast?lat=31.21&lon=34.71&days=1",
]


def p95(latencies_ms: list[float]) -> float:
    ordered = sorted(latencies_ms)
    return ordered[math.ceil(0.95 * len(ordered)) - 1]


def benchmark_passed(results: list[tuple[str, int, float]], provider_calls: int) -> bool:
    if provider_calls != 1:
        return False
    if any(status != 200 for _, status, _ in results):
        return False
    latencies = [latency for _, _, latency in results]
    if not latencies or p95(latencies) > TARGET_P95_MS:
        return False
    for path in PATHS:
        values = [latency for p, _, latency in results if p == path]
        if not values or p95(values) > TARGET_P95_MS:
            return False
    return True


def fake_forecast_body(now: datetime | None = None) -> dict:
    """A valid 7-day Open-Meteo body for a point where it is now noon.

    The UTC offset is chosen so the point's local time is 12:00, so a run shorter than 12 hours never crosses
    local midnight, and the cached forecast covers 7 days from today for the whole run, whatever the time of day.
    """
    now = now or datetime.now(UTC)
    seconds_since_utc_midnight = now.hour * 3600 + now.minute * 60 + now.second
    offset = 12 * 3600 - seconds_since_utc_midnight  # from -12 h to +12 h, like a real time zone
    today = (now + timedelta(seconds=offset)).date()
    return {
        "utc_offset_seconds": offset,
        "daily_units": {"time": "iso8601", "et0_fao_evapotranspiration": "mm", "precipitation_sum": "mm"},
        "daily": {
            "time": [(today + timedelta(days=i)).isoformat() for i in range(7)],
            "et0_fao_evapotranspiration": [3.1, 2.8, 2.6, 2.5, 2.1, 2.3, 2.6],
            "precipitation_sum": [0.0, 4.2, 0.0, 0.0, 0.0, 1.5, 0.0],
        },
    }


@contextmanager
def fake_provider() -> Iterator[tuple[str, list[str]]]:
    """Yield the URL of a local fake Open-Meteo and the list of paths it was called with."""
    calls: list[str] = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            calls.append(self.path)
            body = json.dumps(fake_forecast_body()).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):  # keep the benchmark output readable
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}/v1/forecast", calls
    finally:
        server.shutdown()
        server.server_close()


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def wait_until_up(base_url: str) -> None:
    deadline = time.monotonic() + 10
    while True:
        try:
            urllib.request.urlopen(f"{base_url}/health", timeout=1)
            return
        except OSError:
            if time.monotonic() > deadline:
                raise
            time.sleep(0.1)


def run_benchmark(base_url: str, rate: float, duration: float) -> list[tuple[str, int, float]]:
    total = int(rate * duration)
    results: list[tuple[str, int, float]] = []
    lock = threading.Lock()

    def send(path: str, scheduled: float) -> None:
        try:
            with urllib.request.urlopen(f"{base_url}{path}", timeout=10) as response:
                response.read()
                status = response.status
        except urllib.error.HTTPError as error:
            status = error.code
        except OSError:
            status = 0
        latency_ms = (time.perf_counter() - scheduled) * 1000
        with lock:
            results.append((path, status, latency_ms))

    start = time.perf_counter() + 0.5
    with ThreadPoolExecutor(max_workers=50) as pool:
        for index in range(total):
            scheduled = start + index / rate
            delay = scheduled - time.perf_counter()
            if delay > 0:
                time.sleep(delay)
            pool.submit(send, PATHS[index % len(PATHS)], scheduled)
    return results


def service_environment(provider_url: str) -> dict[str, str]:
    # Passed explicitly: the environment wins over .env, so .env is never used by accident.
    return {
        **os.environ,
        "PROVIDER_BASE_URL": provider_url,
        "PROVIDER_API_KEY": "",
        "PROVIDER_TIMEOUT_SECONDS": "3",
        "PROVIDER_RETRIES": "2",
        "FORECAST_FRESH_HOURS": "3",
        "FORECAST_MAX_STALE_HOURS": "24",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--rate", type=float, default=10, help="requests per second (default 10)")
    parser.add_argument("--duration", type=float, default=120, help="seconds (default 120)")
    args = parser.parse_args()

    with fake_provider() as (provider_url, provider_calls):
        port = free_port()
        server = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", str(port), "--log-level", "warning"],
            cwd=SERVICE_DIR,
            env=service_environment(provider_url),
        )
        base_url = f"http://127.0.0.1:{port}"
        try:
            wait_until_up(base_url)
            urllib.request.urlopen(f"{base_url}{PATHS[0]}", timeout=10).read()  # fills the cache: the one provider call
            print(f"Sending {int(args.rate * args.duration)} requests at {args.rate:g} rps for {args.duration:g} s ...")
            results = run_benchmark(base_url, args.rate, args.duration)
        finally:
            server.terminate()
            server.wait(timeout=10)
        calls = len(provider_calls)

    failures = [result for result in results if result[1] != 200]
    latencies = [latency for _, status, latency in results if status == 200]

    print(f"\n{'path':48} {'n':>5} {'p50 ms':>8} {'p95 ms':>8} {'max ms':>8}")
    for path in PATHS:
        values = [latency for p, status, latency in results if p == path and status == 200]
        if values:
            print(f"GET {path:44} {len(values):5} {sorted(values)[len(values) // 2]:8.2f} {p95(values):8.2f} {max(values):8.2f}")
        else:
            print(f"GET {path:44} {0:5}  no successful responses")
    if latencies:
        print(f"{'ALL':48} {len(latencies):5} {sorted(latencies)[len(latencies) // 2]:8.2f} {p95(latencies):8.2f} {max(latencies):8.2f}")
    print(f"\nNon-200 responses: {len(failures)} of {len(results)}")
    print(f"Provider calls: {calls} (expected 1, the warm-up)")

    passed = benchmark_passed(results, calls)
    print(f"NFR-2.3 (fresh forecast p95 <= {TARGET_P95_MS} ms overall and per path, all 200, one provider call): {'PASS' if passed else 'FAIL'}")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
