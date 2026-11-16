import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import make_url

from db import dispose_engines
from main import app

SERVICE_DIR = Path(__file__).resolve().parent.parent
SEED_SCRIPT = SERVICE_DIR / "seed_registry.sh"

# Read after importing main, so a TEST_DATABASE_URL loaded from .env is seen too.
BACKEND = "postgresql" if os.environ.get("TEST_DATABASE_URL") else "sqlite"


def seed_database(path: Path) -> None:
    subprocess.run(["bash", str(SEED_SCRIPT), str(path)], check=True, capture_output=True)


def assert_unavailable(response) -> None:
    assert response.status_code == 503
    assert response.headers["retry-after"] == "5"
    assert response.json() == {"detail": "Database unavailable"}


def pytest_collection_modifyitems(config, items):
    """Skip the tests that need the other backend."""
    other = "postgres_only" if BACKEND == "sqlite" else "sqlite_only"
    skip = pytest.mark.skip(reason=f"{other} test; this run uses {BACKEND}")
    for item in items:
        if other in item.keywords:
            item.add_marker(skip)


@pytest.fixture(autouse=True)
def isolated_environment(tmp_path, monkeypatch) -> str:
    """Point every test at a temporary SQLite path, never registry.db or a URL from .env."""
    url = f"sqlite:///{tmp_path / 'registry.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    yield url
    dispose_engines()


@pytest.fixture
def sqlite_db_path(tmp_path) -> Path:
    return tmp_path / "registry.db"


@pytest.fixture
def database_url(isolated_environment) -> str:
    return isolated_environment


@pytest.fixture
def seeded_db(database_url) -> str:
    seed_database(Path(make_url(database_url).database))
    return database_url


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
        env={**os.environ, "DATABASE_URL": seeded_db},
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
