"""NFR-1.1 benchmark: p95 latency of successful GET requests at a fixed request rate.

Seeds a temporary database, starts uvicorn against it, sends requests on a fixed
schedule (open loop), and reports p95 per endpoint and overall. Latency is measured
from each request's scheduled send time, so a slow server cannot hide its delay.
Exits with status 1 if any response is not 200, or if the overall p95 or any
endpoint's p95 exceeds the target.
"""

import argparse
import math
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

SERVICE_DIR = Path(__file__).resolve().parent.parent
TARGET_P95_MS = 100

ENDPOINTS = [
    "/v1/farms",
    "/v1/farms/b7e2c0a0-3c1d-4f0a-9a11-0c5d2e6f1001",
    "/v1/plots",
    "/v1/plots?farm_id=b7e2c0a0-3c1d-4f0a-9a11-0c5d2e6f1001",
    "/v1/plots/c8f3d1b0-4d2e-5a1b-8b22-1d6e3f702002",
    "/v1/crops",
    "/v1/crops/tomato",
    "/v1/soils",
    "/v1/soils/sand",
    "/v1/emitters",
    "/v1/emitters/dripnet-pc-1.0",
]


def p95(latencies_ms: list[float]) -> float:
    ordered = sorted(latencies_ms)
    return ordered[math.ceil(0.95 * len(ordered)) - 1]


def benchmark_passed(results: list[tuple[str, int, float]]) -> bool:
    if any(status != 200 for _, status, _ in results):
        return False
    latencies = [latency for _, _, latency in results]
    if not latencies or p95(latencies) > TARGET_P95_MS:
        return False
    for path in ENDPOINTS:
        values = [latency for p, _, latency in results if p == path]
        if not values or p95(values) > TARGET_P95_MS:
            return False
    return True


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
            pool.submit(send, ENDPOINTS[index % len(ENDPOINTS)], scheduled)
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--rate", type=float, default=10, help="requests per second (default 10)")
    parser.add_argument("--duration", type=float, default=120, help="seconds (default 120)")
    args = parser.parse_args()

    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "registry.db"
        subprocess.run(["bash", "seed_registry.sh", str(db_path)], cwd=SERVICE_DIR, check=True, capture_output=True)
        port = free_port()
        server = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", str(port), "--log-level", "warning"],
            cwd=SERVICE_DIR,
            env={**os.environ, "REGISTRY_DB_PATH": str(db_path)},
        )
        base_url = f"http://127.0.0.1:{port}"
        try:
            wait_until_up(base_url)
            for path in ENDPOINTS:
                urllib.request.urlopen(f"{base_url}{path}", timeout=10).read()
            print(f"Sending {int(args.rate * args.duration)} requests at {args.rate:g} rps for {args.duration:g} s ...")
            results = run_benchmark(base_url, args.rate, args.duration)
        finally:
            server.terminate()
            server.wait(timeout=10)

    failures = [result for result in results if result[1] != 200]
    latencies = [latency for _, status, latency in results if status == 200]

    print(f"\n{'endpoint':58} {'n':>5} {'p50 ms':>8} {'p95 ms':>8} {'max ms':>8}")
    for path in ENDPOINTS:
        values = [latency for p, status, latency in results if p == path and status == 200]
        if values:
            print(f"GET {path:54} {len(values):5} {sorted(values)[len(values) // 2]:8.2f} {p95(values):8.2f} {max(values):8.2f}")
        else:
            print(f"GET {path:54} {0:5}  no successful responses")
    if latencies:
        print(f"{'ALL':58} {len(latencies):5} {sorted(latencies)[len(latencies) // 2]:8.2f} {p95(latencies):8.2f} {max(latencies):8.2f}")
    print(f"\nNon-200 responses: {len(failures)} of {len(results)}")

    passed = benchmark_passed(results)
    print(f"NFR-1.1 (overall and every endpoint p95 <= {TARGET_P95_MS} ms, all responses 200): {'PASS' if passed else 'FAIL'}")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
