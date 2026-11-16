import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from uuid import uuid4

import pytest
from dotenv import dotenv_values
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, make_url, text
from sqlalchemy.pool import NullPool

from db import ENV_FILE, dispose_engines, get_engine
from main import app
from scripts.setup_postgres import create_schema, insert_catalogues, insert_demo_data

SERVICE_DIR = Path(__file__).resolve().parent.parent
SEED_SCRIPT = SERVICE_DIR / "seed_registry.sh"

# pytest_sessionstart stops the run if .env defines TEST_DATABASE_URL, so this value
# always comes from the shell, even though importing db has loaded .env.
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
BACKEND = "postgresql" if TEST_DATABASE_URL else "sqlite"
TEST_DATABASE_PREFIX = "agropilot_test_"


def seed_database(path: Path) -> None:
    subprocess.run(["bash", str(SEED_SCRIPT), str(path)], check=True, capture_output=True)


def assert_unavailable(response) -> None:
    assert response.status_code == 503
    assert response.headers["retry-after"] == "5"
    assert response.json() == {"detail": "Database unavailable"}


def defines_test_database_url(env_file: Path) -> bool:
    """True if this .env file sets TEST_DATABASE_URL, which belongs in the shell only."""
    return "TEST_DATABASE_URL" in dotenv_values(env_file)


def pytest_sessionstart(session):
    """Stop the run before any test if the PostgreSQL test settings are unsafe."""
    # From .env, it would silently switch every test run to PostgreSQL.
    if defines_test_database_url(ENV_FILE):
        pytest.exit("Remove TEST_DATABASE_URL from .env; set it in the shell for one run.", returncode=2)
    # Only on this machine: the fixtures create and drop databases.
    if TEST_DATABASE_URL is None:
        return
    url = make_url(TEST_DATABASE_URL)
    if url.host not in ("localhost", "127.0.0.1"):
        hidden = url.render_as_string(hide_password=True)
        pytest.exit(f"TEST_DATABASE_URL must point to localhost, got {hidden}", returncode=2)


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


@pytest.fixture(scope="session")
def admin_engine():
    # CREATE DATABASE and DROP DATABASE cannot run inside a transaction, hence AUTOCOMMIT.
    engine = create_engine(TEST_DATABASE_URL, isolation_level="AUTOCOMMIT", poolclass=NullPool)
    yield engine
    engine.dispose()


@pytest.fixture
def postgres_admin_url() -> str:
    return TEST_DATABASE_URL


@pytest.fixture
def database_url(isolated_environment, request, monkeypatch):
    """The URL of an empty database for this test: a temp SQLite path, or a fresh PostgreSQL database."""
    if BACKEND == "sqlite":
        yield isolated_environment
        return

    admin_engine = request.getfixturevalue("admin_engine")
    name = f"{TEST_DATABASE_PREFIX}{uuid4().hex}"
    with admin_engine.connect() as conn:
        conn.execute(text(f'CREATE DATABASE "{name}"'))
    url = make_url(TEST_DATABASE_URL).set(database=name).render_as_string(hide_password=False)
    monkeypatch.setenv("DATABASE_URL", url)
    try:
        yield url
    finally:
        dispose_engines()  # close the app's pooled connections to this database first
        # Drop only the exact name created above; never list or drop databases by pattern.
        assert name.startswith(TEST_DATABASE_PREFIX)
        with admin_engine.connect() as conn:
            conn.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))


@pytest.fixture
def seeded_db(database_url) -> str:
    if BACKEND == "sqlite":
        seed_database(Path(make_url(database_url).database))
    else:
        with get_engine(database_url).begin() as conn:
            create_schema(conn)
            insert_catalogues(conn)
            insert_demo_data(conn)
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
