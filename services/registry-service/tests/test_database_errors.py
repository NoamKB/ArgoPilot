import sqlite3

import pytest
from fastapi.testclient import TestClient

from conftest import seed_database
from db import is_unavailable
from main import app
from repositories import catalogues as catalogue_repository


def assert_unavailable(response):
    assert response.status_code == 503
    assert response.headers["retry-after"] == "5"
    assert response.json() == {"detail": "Database unavailable"}


def test_missing_database_file_returns_503(isolated_db_path):
    client = TestClient(app)

    assert_unavailable(client.get("/v1/crops"))
    assert not isolated_db_path.exists()


def test_corrupt_database_file_returns_503(isolated_db_path):
    isolated_db_path.write_bytes(b"not a database" * 512)

    assert_unavailable(TestClient(app).get("/v1/crops"))


def test_health_stays_ok_without_database():
    response = TestClient(app).get("/health")

    assert response.status_code == 200


def test_reseeding_recovers_without_restart(isolated_db_path):
    client = TestClient(app)
    assert_unavailable(client.get("/v1/crops"))

    seed_database(isolated_db_path)

    assert client.get("/v1/crops").status_code == 200


def test_sql_bug_returns_500_not_503(seeded_db, monkeypatch):
    def broken_query(conn):
        return conn.execute("SELEC id FROM crops").fetchall()

    monkeypatch.setattr(catalogue_repository, "list_crops", broken_query)
    response = TestClient(app, raise_server_exceptions=False).get("/v1/crops")

    assert response.status_code == 500
    assert response.text == "Internal Server Error"
    assert "retry-after" not in response.headers


def test_unseeded_empty_file_returns_500(isolated_db_path):
    isolated_db_path.write_bytes(b"")

    response = TestClient(app, raise_server_exceptions=False).get("/v1/crops")

    assert response.status_code == 500


@pytest.mark.parametrize(
    ("error_name", "unavailable"),
    [
        ("SQLITE_CANTOPEN", True),
        ("SQLITE_NOTADB", True),
        ("SQLITE_BUSY", True),
        ("SQLITE_IOERR_READ", True),
        ("SQLITE_ERROR", False),
        ("SQLITE_CONSTRAINT_UNIQUE", False),
        (None, False),
    ],
)
def test_is_unavailable_classification(error_name, unavailable):
    exc = sqlite3.OperationalError("test")
    exc.sqlite_errorname = error_name

    assert is_unavailable(exc) is unavailable
