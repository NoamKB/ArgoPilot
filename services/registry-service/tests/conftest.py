import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from main import app

SERVICE_DIR = Path(__file__).resolve().parent.parent
SEED_SCRIPT = SERVICE_DIR / "seed_registry.sh"


def seed_database(path: Path) -> None:
    subprocess.run(["bash", str(SEED_SCRIPT), str(path)], check=True, capture_output=True)


@pytest.fixture(autouse=True)
def isolated_db_path(tmp_path, monkeypatch) -> Path:
    path = tmp_path / "registry.db"
    monkeypatch.setenv("REGISTRY_DB_PATH", str(path))
    return path


@pytest.fixture
def seeded_db(isolated_db_path) -> Path:
    seed_database(isolated_db_path)
    return isolated_db_path


@pytest.fixture
def client(seeded_db) -> TestClient:
    return TestClient(app)


@pytest.fixture
def live_server(seeded_db):
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", str(port)],
        cwd=SERVICE_DIR,
        env={**os.environ, "REGISTRY_DB_PATH": str(seeded_db)},
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    base_url = f"http://127.0.0.1:{port}"
    try:
        deadline = time.monotonic() + 10
        while True:
            try:
                urllib.request.urlopen(f"{base_url}/health", timeout=1)
                break
            except OSError:
                if time.monotonic() > deadline:
                    raise
                time.sleep(0.1)
        yield base_url
    finally:
        process.terminate()
        process.wait(timeout=10)
