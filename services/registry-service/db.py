import functools
import os
import sqlite3
import threading
from collections.abc import Iterator
from pathlib import Path
from typing import Annotated

import psycopg
from dotenv import load_dotenv
from fastapi import Depends
from sqlalchemy import Engine, create_engine, make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.pool import NullPool

SERVICE_DIR = Path(__file__).resolve().parent
ENV_FILE = SERVICE_DIR / ".env"
DEFAULT_DATABASE_URL = f"sqlite:///{SERVICE_DIR / 'registry.db'}"

DEFAULT_DB_PATH = Path(__file__).resolve().parent / "registry.db"


def load_env_file(path: Path = ENV_FILE) -> None:
    """Load .env into the environment. A variable that is already set wins."""
    load_dotenv(path, override=False)


# Here, not in main.py, so that scripts read configuration exactly the way the app does.
load_env_file()


def get_database_url() -> str:
    return os.environ.get("DATABASE_URL") or DEFAULT_DATABASE_URL


def open_sqlite(db_path: Path) -> sqlite3.Connection:
    """Open an existing SQLite file for reading and writing, with foreign keys enforced."""
    # mode=rw: a missing file is an error (503), not a new empty database.
    uri = db_path.as_uri() + "?mode=rw"
    conn = sqlite3.connect(uri, uri=True, check_same_thread=False)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
    except sqlite3.Error:
        conn.close()
        raise
    return conn


_engines: dict[str, Engine] = {}
_engines_lock = threading.Lock()


def get_engine(url: str) -> Engine:
    """Return the engine for this URL, creating it on first use."""
    # The lock stops two concurrent first requests from creating two engines (two pools).
    with _engines_lock:
        if url not in _engines:
            _engines[url] = _create_engine(url)
        return _engines[url]


def _create_engine(url: str) -> Engine:
    backend = make_url(url).get_backend_name()
    if backend == "sqlite":
        # Resolved once, here: the engine stays on this file even if DATABASE_URL
        # or the current directory changes later.
        db_path = Path(make_url(url).database).resolve()
        # creator= keeps open_sqlite's mode=rw, so a missing file stays a 503.
        # NullPool: a fresh connection per request, as before (JL-002).
        return create_engine(
            "sqlite://",
            creator=functools.partial(open_sqlite, db_path),
            poolclass=NullPool,
        )
    if backend == "postgresql":
        # pre_ping replaces pooled connections that the server has closed.
        return create_engine(url, pool_pre_ping=True)
    raise ValueError(f"Unsupported DATABASE_URL backend: {backend}")


def dispose_engines() -> None:
    """Close every engine's connections and empty the cache (used by tests)."""
    with _engines_lock:
        for engine in _engines.values():
            engine.dispose()
        _engines.clear()

# SQLite result codes that mean the database file cannot be used right now.
# SQLITE_ERROR is not here: SQLite uses it for SQL mistakes such as a typo or a missing table.
UNAVAILABLE_ERROR_NAMES = (
    "SQLITE_CANTOPEN",
    "SQLITE_NOTADB",
    "SQLITE_CORRUPT",
    "SQLITE_IOERR",
    "SQLITE_BUSY",
    "SQLITE_LOCKED",
    "SQLITE_FULL",
    "SQLITE_READONLY",
)

# PostgreSQL SQLSTATE codes (or two-character classes) that mean the database
# cannot be used right now. Anything else, such as a syntax error, stays a 500.
POSTGRES_UNAVAILABLE_SQLSTATES = (
    "08",                         # connection exception: connection lost or failed
    "28",                         # invalid authorization: wrong password, access denied
    "3D000",                      # database does not exist
    "53",                         # insufficient resources: too many connections, disk full
    "57P01", "57P02", "57P03",    # server shutting down, crashed, or still starting up
    "58",                         # system error: I/O failure on the server
)


def is_postgres_unavailable(orig: psycopg.Error) -> bool:
    """True if a psycopg error means the database is unavailable (503)."""
    # The code is checked before the class: 3D000 (missing database) is a
    # ProgrammingError, and 57014 (query cancelled) is an OperationalError.
    if orig.sqlstate is None:
        # The client library failed before the server answered, e.g. connection refused.
        # A client-side DataError (a NUL in text) also has no code, hence the class check.
        return isinstance(orig, psycopg.OperationalError)
    return orig.sqlstate.startswith(POSTGRES_UNAVAILABLE_SQLSTATES)


def violated_constraint(exc: IntegrityError) -> str | None:
    """'unique' or 'foreign_key' for the violations the routers map; otherwise None."""
    if isinstance(exc.orig, sqlite3.Error):
        return {
            "SQLITE_CONSTRAINT_UNIQUE": "unique",
            "SQLITE_CONSTRAINT_FOREIGNKEY": "foreign_key",
        }.get(getattr(exc.orig, "sqlite_errorname", None))
    if isinstance(exc.orig, psycopg.Error):
        return {"23505": "unique", "23503": "foreign_key"}.get(exc.orig.sqlstate)
    return None


def get_db_path() -> Path:
    return Path(os.environ.get("REGISTRY_DB_PATH", DEFAULT_DB_PATH))


def get_db() -> Iterator[sqlite3.Connection]:
    uri = get_db_path().resolve().as_uri() + "?mode=rw"
    conn = sqlite3.connect(uri, uri=True, check_same_thread=False)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        yield conn
    finally:
        conn.close()


def is_unavailable(exc: sqlite3.DatabaseError) -> bool:
    error_name = getattr(exc, "sqlite_errorname", None) or ""
    return error_name.startswith(UNAVAILABLE_ERROR_NAMES)


DbConnection = Annotated[sqlite3.Connection, Depends(get_db)]
