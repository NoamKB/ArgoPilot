import sqlite3
from pathlib import Path

import pytest
from sqlalchemy import make_url
from sqlalchemy.pool import NullPool, QueuePool

from db import (
    DEFAULT_DATABASE_URL,
    SERVICE_DIR,
    dispose_engines,
    get_database_url,
    get_engine,
    load_env_file,
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


def test_unencoded_at_in_password_is_rejected_without_echoing_it():
    # "p@ss" unencoded: make_url would read password "p" and host "ss@db.example.com",
    # and the host (part of the password) would then appear in error logs.
    with pytest.raises(ValueError) as error:
        get_engine("postgresql+psycopg://app:p@ss@db.example.com/prod")
    assert "%40" in str(error.value)
    assert "ss@db" not in str(error.value)
