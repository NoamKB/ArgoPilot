import sqlite3

import psycopg
import pytest
import sqlalchemy.exc
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from conftest import assert_unavailable, seed_database
from db import is_postgres_unavailable, is_unavailable, violated_constraint
from main import app
from repositories import catalogues as catalogue_repository


@pytest.mark.sqlite_only
def test_missing_database_file_returns_503(sqlite_db_path):
    client = TestClient(app)

    assert_unavailable(client.get("/v1/crops"))
    assert not sqlite_db_path.exists()


@pytest.mark.sqlite_only
def test_corrupt_database_file_returns_503(sqlite_db_path):
    sqlite_db_path.write_bytes(b"not a database" * 512)

    assert_unavailable(TestClient(app).get("/v1/crops"))


def test_health_stays_ok_without_database():
    response = TestClient(app).get("/health")

    assert response.status_code == 200


@pytest.mark.sqlite_only
def test_reseeding_recovers_without_restart(sqlite_db_path):
    client = TestClient(app)
    assert_unavailable(client.get("/v1/crops"))

    seed_database(sqlite_db_path)

    assert client.get("/v1/crops").status_code == 200


def test_sql_bug_returns_500_not_503(seeded_db, monkeypatch):
    def broken_query(conn):
        return conn.execute(text("SELEC id FROM crops")).all()

    monkeypatch.setattr(catalogue_repository, "list_crops", broken_query)
    response = TestClient(app, raise_server_exceptions=False).get("/v1/crops")

    assert response.status_code == 500
    assert response.text == "Internal Server Error"
    assert "retry-after" not in response.headers


@pytest.mark.sqlite_only
def test_unseeded_empty_file_returns_500(sqlite_db_path):
    sqlite_db_path.write_bytes(b"")

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
    orig = sqlite3.OperationalError("test")
    orig.sqlite_errorname = error_name

    assert is_unavailable(DBAPIError(None, None, orig)) is unavailable


def test_pool_timeout_is_unavailable():
    assert is_unavailable(sqlalchemy.exc.TimeoutError("pool")) is True


def test_non_driver_sqlalchemy_error_is_not_unavailable():
    assert is_unavailable(sqlalchemy.exc.ArgumentError("bad")) is False


def test_postgres_driver_error_is_routed_to_postgres_rule():
    assert is_unavailable(DBAPIError(None, None, psycopg.errors.lookup("57P01")("x"))) is True


def test_pool_timeout_returns_503(client, monkeypatch):
    def full_pool(conn):
        raise sqlalchemy.exc.TimeoutError("QueuePool limit reached")

    monkeypatch.setattr(catalogue_repository, "list_crops", full_pool)

    assert_unavailable(client.get("/v1/crops"))


@pytest.mark.parametrize("sqlstate", ["08006", "08001", "28P01", "28000", "3D000", "53300", "57P01", "57P03", "58030"])
def test_postgres_unavailable_sqlstates(sqlstate):
    assert is_postgres_unavailable(psycopg.errors.lookup(sqlstate)("test")) is True


@pytest.mark.parametrize("sqlstate", ["57014", "40001", "40P01", "42601"])
def test_postgres_sqlstates_that_are_not_unavailable(sqlstate):
    assert is_postgres_unavailable(psycopg.errors.lookup(sqlstate)("test")) is False


def test_client_side_operational_error_without_sqlstate_is_unavailable():
    assert is_postgres_unavailable(psycopg.OperationalError("connection refused")) is True


def test_client_side_data_error_without_sqlstate_is_not_unavailable():
    assert is_postgres_unavailable(psycopg.DataError("NUL")) is False


def sqlite_error(error_class, error_name):
    exc = error_class("test")
    exc.sqlite_errorname = error_name
    return exc


def integrity_error(orig):
    return sqlalchemy.exc.IntegrityError("stmt", {}, orig)


@pytest.mark.parametrize(
    ("orig", "expected"),
    [
        (sqlite_error(sqlite3.IntegrityError, "SQLITE_CONSTRAINT_UNIQUE"), "unique"),
        (sqlite_error(sqlite3.IntegrityError, "SQLITE_CONSTRAINT_FOREIGNKEY"), "foreign_key"),
        (sqlite_error(sqlite3.IntegrityError, "SQLITE_CONSTRAINT_NOTNULL"), None),
        (psycopg.errors.lookup("23505")("test"), "unique"),
        (psycopg.errors.lookup("23503")("test"), "foreign_key"),
        (psycopg.errors.lookup("23502")("test"), None),
    ],
)
def test_violated_constraint(orig, expected):
    assert violated_constraint(integrity_error(orig)) == expected
