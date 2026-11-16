import sqlite3

import psycopg
from fastapi import FastAPI
from fastapi.testclient import TestClient

from conftest import BACKEND, assert_unavailable
from db import DbConnection, get_database_url, get_engine
from main import app
from repositories import farms as farm_repository
from repositories import plots as plot_repository
from test_plots import SPEC_EXAMPLE

PLOT_FIELDS = {key: value for key, value in SPEC_EXAMPLE.items() if key != "farm_id"}


def unavailable_driver_error() -> Exception:
    """A driver error that the classifier treats as 'database unavailable', for the current backend."""
    if BACKEND == "sqlite":
        error = sqlite3.OperationalError("database is locked")
        error.sqlite_errorname = "SQLITE_BUSY"
        return error
    return psycopg.errors.lookup("57P01")("terminating connection")


def test_failed_commit_returns_503_not_201(client, monkeypatch):
    """Simulated failure: do_commit raises before COMMIT reaches the database.

    The no-row check covers only this simulated case. A real failed COMMIT can have
    an unknown outcome (spec section 6).
    """
    engine = get_engine(get_database_url())  # the same cached engine the app uses

    def failing_commit(dbapi_connection):
        raise unavailable_driver_error()

    # monkeypatch.context(), not monkeypatch.undo(): undo() would also remove the autouse
    # DATABASE_URL override, and the GET below would then read the default database.
    with monkeypatch.context() as patch:
        patch.setattr(engine.dialect, "do_commit", failing_commit)
        assert_unavailable(client.post("/v1/farms", json={"name": "Commit test"}))

    assert "Commit test" not in [farm["name"] for farm in client.get("/v1/farms").json()]


def test_second_write_failure_rolls_back_the_first(seeded_db):
    # A test-only app with two writes in one request; no production route is added.
    test_app = FastAPI()

    @test_app.post("/two-writes")
    def two_writes(conn: DbConnection):
        farm = farm_repository.create_farm(conn, "Rollback test")
        plot_repository.create_plot(conn, {**PLOT_FIELDS, "farm_id": farm["id"], "crop_id": "no-such-crop"})

    response = TestClient(test_app, raise_server_exceptions=False).post("/two-writes")

    assert response.status_code == 500  # the foreign-key IntegrityError has no handler in test_app
    names = [farm["name"] for farm in TestClient(app).get("/v1/farms").json()]
    assert "Rollback test" not in names
