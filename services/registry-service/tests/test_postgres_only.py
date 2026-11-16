from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import make_url, text

from conftest import assert_unavailable
from main import app
from scripts.setup_postgres import main

pytestmark = pytest.mark.postgres_only


def test_wrong_password_returns_503_without_logging_password(postgres_admin_url, monkeypatch, caplog):
    bad = make_url(postgres_admin_url).set(password="wrong-password-7f3a").render_as_string(hide_password=False)
    monkeypatch.setenv("DATABASE_URL", bad)

    assert_unavailable(TestClient(app).get("/v1/crops"))
    assert "Database unavailable" in caplog.text  # the warning was logged...
    assert "wrong-password-7f3a" not in caplog.text  # ...without the password (V7)


def test_missing_database_returns_503(postgres_admin_url, monkeypatch):
    missing = make_url(postgres_admin_url).set(database=f"agropilot_test_missing_{uuid4().hex}")
    monkeypatch.setenv("DATABASE_URL", missing.render_as_string(hide_password=False))

    assert_unavailable(TestClient(app).get("/v1/crops"))  # V2


def test_empty_database_returns_500(database_url):
    response = TestClient(app, raise_server_exceptions=False).get("/v1/crops")

    assert response.status_code == 500


def test_setup_without_demo_creates_catalogues_and_no_farms(database_url, capsys):
    assert main([]) == 0
    assert "Catalogues: 2 crops, 3 soils, 4 emitters. Demo data: skipped." in capsys.readouterr().out
    assert TestClient(app).get("/v1/farms").json() == []


def test_setup_is_idempotent(database_url, capsys):
    assert main(["--demo"]) == 0
    first = capsys.readouterr().out
    assert main(["--demo"]) == 0
    assert capsys.readouterr().out == first  # the same target and counts: nothing added the second time
    assert len(TestClient(app).get("/v1/plots").json()) == 4


def test_request_succeeds_after_server_closes_connections(client, database_url, admin_engine):
    assert client.get("/v1/crops").status_code == 200  # leaves a pooled connection
    name = make_url(database_url).database
    with admin_engine.connect() as conn:
        conn.execute(
            text("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = :name AND pid <> pg_backend_pid()"),
            {"name": name},
        )
    assert client.get("/v1/crops").status_code == 200  # pool_pre_ping replaces the dead connection
