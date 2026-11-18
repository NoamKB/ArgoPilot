import sqlite3
from pathlib import Path

import psycopg
import pytest
import sqlalchemy.exc
from sqlalchemy import make_url
from sqlalchemy.pool import NullPool, QueuePool

from conftest import defines_test_database_url
from db import (
    DEFAULT_DATABASE_URL,
    describe_database_url,
    SERVICE_DIR,
    dispose_engines,
    get_database_url,
    get_engine,
    load_env_file,
    open_sqlite,
)


@pytest.fixture(autouse=True)
def fresh_engine_cache():
    yield
    dispose_engines()


@pytest.fixture
def unset_database_url(monkeypatch):
    # delenv alone records nothing when the variable is already unset, so a value
    # written later by load_env_file would leak into other tests. setenv first
    # records "was unset", and teardown then removes whatever was written.
    monkeypatch.setenv("DATABASE_URL", "unused")
    monkeypatch.delenv("DATABASE_URL")


def make_sqlite_file(path: Path) -> Path:
    sqlite3.connect(path).close()
    return path


def printed_chained_error(error: BaseException) -> BaseException | None:
    """The earlier error Python would print under this one in a traceback, if any."""
    if error.__cause__ is not None:
        return error.__cause__
    return None if error.__suppress_context__ else error.__context__


def connected_file(engine) -> str:
    """Return the file the engine's connection actually opened."""
    with engine.connect() as conn:
        return conn.exec_driver_sql("PRAGMA database_list").all()[0][2]


def test_same_url_returns_same_engine(tmp_path):
    url = f"sqlite:///{tmp_path / 'a.db'}"
    assert get_engine(url) is get_engine(url)


def test_different_urls_return_different_engines(tmp_path):
    assert get_engine(f"sqlite:///{tmp_path / 'a.db'}") is not get_engine(f"sqlite:///{tmp_path / 'b.db'}")


def test_dispose_engines_empties_the_cache(tmp_path):
    url = f"sqlite:///{tmp_path / 'a.db'}"
    first = get_engine(url)
    dispose_engines()
    assert get_engine(url) is not first


def test_sqlite_engine_uses_null_pool(tmp_path):
    assert isinstance(get_engine(f"sqlite:///{tmp_path / 'a.db'}").pool, NullPool)


def test_postgres_engine_uses_queue_pool_with_pre_ping():
    # create_engine does not connect, so no PostgreSQL server is needed.
    engine = get_engine("postgresql+psycopg://user:pw@127.0.0.1:5433/db")
    assert isinstance(engine.pool, QueuePool)
    assert engine.pool.size() == 5
    assert engine.pool._pre_ping is True  # private: SQLAlchemy has no public accessor for this setting


def test_each_sqlite_engine_stays_bound_to_its_file(tmp_path, monkeypatch):
    a = make_sqlite_file(tmp_path / "a.db")
    b = make_sqlite_file(tmp_path / "b.db")
    engine_a = get_engine(f"sqlite:///{a}")
    engine_b = get_engine(f"sqlite:///{b}")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{b}")
    assert connected_file(engine_a) == str(a.resolve())
    assert connected_file(engine_b) == str(b.resolve())


def test_relative_sqlite_path_is_resolved_once(tmp_path, monkeypatch):
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    make_sqlite_file(first / "registry.db")
    make_sqlite_file(second / "registry.db")
    monkeypatch.chdir(first)
    engine = get_engine("sqlite:///registry.db")
    monkeypatch.chdir(second)
    assert connected_file(engine) == str((first / "registry.db").resolve())


def test_percent_encoded_password_is_decoded():
    engine = get_engine("postgresql+psycopg://user:p%40ss%2Fword@127.0.0.1:5433/db")
    assert engine.url.password == "p@ss/word"


def test_env_file_value_is_used_when_variable_unset(tmp_path, unset_database_url):
    env_file = tmp_path / ".env"
    env_file.write_text("DATABASE_URL=sqlite:////from/env/file.db\n")
    load_env_file(env_file)
    assert get_database_url() == "sqlite:////from/env/file.db"


def test_environment_wins_over_env_file(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:////from/environment.db")
    env_file = tmp_path / ".env"
    env_file.write_text("DATABASE_URL=sqlite:////from/env/file.db\n")
    load_env_file(env_file)
    assert get_database_url() == "sqlite:////from/environment.db"


def test_default_url_is_absolute_service_registry_db(unset_database_url):
    assert get_database_url() == f"sqlite:///{SERVICE_DIR / 'registry.db'}"
    assert Path(make_url(get_database_url()).database).is_absolute()


def test_empty_database_url_uses_default(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "")
    assert get_database_url() == DEFAULT_DATABASE_URL


def test_autouse_fixture_points_at_temporary_database(tmp_path):
    # Guards against any test reaching the real registry.db or a DATABASE_URL from .env.
    assert get_database_url() == f"sqlite:///{tmp_path / 'registry.db'}"


@pytest.mark.parametrize(
    ("url", "password_part"),
    [
        ("postgresql+psycopg://app:p@ss@db.example.com/prod", "ss@db"),  # rest of password in the host
        ("postgresql+psycopg://app:p@ss/xyzzy@db.example.com/prod", "xyzzy"),  # ... in the database name
        ("postgresql+psycopg://app:p@ss:99xyzzy@db.example.com/prod", "99xyzzy"),  # ... in the port
    ],
)
def test_unencoded_at_in_password_is_rejected_without_echoing_it(url, password_part):
    # An unencoded '@' ends the password early; the rest would appear in errors and logs.
    with pytest.raises(ValueError) as error:
        get_engine(url)
    assert "%40" in str(error.value)
    assert password_part not in str(error.value)
    assert printed_chained_error(error.value) is None


def test_unparseable_url_error_does_not_echo_it():
    with pytest.raises(ValueError) as error:
        get_engine("postgresql+psycopg://app:pw@db.example.com:12ab/prod")
    assert "12ab" not in str(error.value)
    assert printed_chained_error(error.value) is None  # the parse error quoted the port


def test_described_url_hides_password_and_query():
    described = describe_database_url("postgresql+psycopg://app:s3cret@db.example.com/prod?sslpassword=k3y")
    assert described == "postgresql, postgresql+psycopg://app:***@db.example.com/prod"


def test_env_file_with_test_database_url_is_detected(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("TEST_DATABASE_URL=postgresql+psycopg://u:p@127.0.0.1:5435/postgres\n")
    assert defines_test_database_url(env_file) is True


def test_env_file_without_test_database_url_is_accepted(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("DATABASE_URL=sqlite:////tmp/registry.db\n")
    assert defines_test_database_url(env_file) is False
    assert defines_test_database_url(tmp_path / "missing.env") is False


def test_postgres_engine_sets_a_5_second_connect_timeout(monkeypatch):
    engine = get_engine("postgresql+psycopg://user:pw@127.0.0.1:5435/db")
    received = {}

    def fake_connect(*args, **kwargs):  # records what psycopg would receive; no server needed
        received.update(kwargs)
        raise psycopg.OperationalError("not connecting in this test")

    monkeypatch.setattr(engine.dialect, "connect", fake_connect)
    with pytest.raises(sqlalchemy.exc.OperationalError):
        engine.connect()
    assert received["connect_timeout"] == 5


def test_unsupported_backend_is_refused():
    with pytest.raises(ValueError, match="Unsupported DATABASE_URL backend: mysql"):
        get_engine("mysql://user@127.0.0.1/db")


def test_failed_foreign_keys_pragma_closes_the_connection(tmp_path, monkeypatch):
    class PragmaFailsConnection:
        closed = False

        def execute(self, sql):
            raise sqlite3.OperationalError("disk I/O error")

        def close(self):
            self.closed = True

    connection = PragmaFailsConnection()
    monkeypatch.setattr(sqlite3, "connect", lambda *args, **kwargs: connection)

    with pytest.raises(sqlite3.OperationalError):
        open_sqlite(tmp_path / "registry.db")
    assert connection.closed  # not left open: NullPool would never close it
