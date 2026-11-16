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
from sqlalchemy import URL, Connection, Engine, create_engine, make_url
from sqlalchemy.exc import ArgumentError, DBAPIError, IntegrityError, SQLAlchemyError
from sqlalchemy.exc import TimeoutError as PoolTimeoutError
from sqlalchemy.pool import NullPool

SERVICE_DIR = Path(__file__).resolve().parent
ENV_FILE = SERVICE_DIR / ".env"
DEFAULT_DATABASE_URL = f"sqlite:///{SERVICE_DIR / 'registry.db'}"


def load_env_file(path: Path = ENV_FILE) -> None:
    """Load .env into the environment. A variable that is already set wins."""
    load_dotenv(path, override=False)


# Here, not in main.py, so that scripts read configuration exactly the way the app does.
load_env_file()


def get_database_url() -> str:
    return os.environ.get("DATABASE_URL") or DEFAULT_DATABASE_URL


# Fixed text: an error about a bad URL must never repeat the URL, which may hold a password.
INVALID_URL_MESSAGE = (
    "DATABASE_URL could not be parsed. Percent-encode special characters in the password, e.g. @ as %40."
)


def parse_database_url(url: str) -> URL:
    """Parse a database URL, refusing one that would put part of the password elsewhere."""
    # A server URL has at most one '@', between the credentials and the host. A second one
    # means an unencoded '@' in the password: the rest of the password would land in the
    # host, port, or database name, which appear in errors, logs, and printed targets.
    if not url.startswith("sqlite") and url.count("@") > 1:
        raise ValueError(INVALID_URL_MESSAGE)
    try:
        return make_url(url)
    except (ValueError, ArgumentError):
        # from None: the original error, which can quote part of the URL, is not attached.
        raise ValueError(INVALID_URL_MESSAGE) from None


def display_url(parsed: URL) -> str:
    """The URL for logs and printed targets: password hidden, query string left out."""
    # The query string can hold secrets too, such as sslpassword.
    return parsed.set(query={}).render_as_string(hide_password=True)


def describe_database_url(url: str) -> str:
    """Backend and target for the startup log. Never echoes an invalid URL."""
    try:
        parsed = parse_database_url(url)
    except ValueError:
        return f"invalid. {INVALID_URL_MESSAGE}"
    return f"{parsed.get_backend_name()}, {display_url(parsed)}"


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


# Every engine uses hide_parameters=True: database errors are logged, and their
# bound values (farm and plot names) are user data that does not belong in logs.
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
    parsed = parse_database_url(url)
    backend = parsed.get_backend_name()
    if backend == "sqlite":
        # Resolved once, here: the engine stays on this file even if DATABASE_URL
        # or the current directory changes later.
        db_path = Path(parsed.database).resolve()
        # creator= keeps open_sqlite's mode=rw, so a missing file stays a 503.
        # NullPool: a fresh connection per request, as before (JL-002).
        return create_engine(
            "sqlite://",
            creator=functools.partial(open_sqlite, db_path),
            poolclass=NullPool,
            hide_parameters=True,
        )
    if backend == "postgresql":
        # pre_ping replaces pooled connections that the server has closed.
        # connect_timeout: a host that drops packets fails after 5 s (503), instead of
        # waiting for the operating system's TCP timeout of a minute or more.
        return create_engine(
            url,
            pool_pre_ping=True,
            hide_parameters=True,
            connect_args={"connect_timeout": 5},
        )
    raise ValueError(f"Unsupported DATABASE_URL backend: {backend}")


def dispose_engines() -> None:
    """Close every engine's connections and empty the cache (used by tests)."""
    with _engines_lock:
        for engine in _engines.values():
            engine.dispose()
        _engines.clear()


def get_db() -> Iterator[Connection]:
    """Give the endpoint one connection inside one transaction."""
    engine = get_engine(get_database_url())
    with engine.begin() as conn:  # commits if the endpoint returns, rolls back if it raises
        yield conn


# scope="function" runs the commit BEFORE the response is sent. Without it, a commit
# that fails after the endpoint returned would still send 201 to the client (JL-008).
DbConnection = Annotated[Connection, Depends(get_db, scope="function")]


# SQLite result codes that mean the database file cannot be used right now.
# SQLITE_ERROR is not here: SQLite uses it for SQL mistakes such as a typo or a missing table.
SQLITE_UNAVAILABLE_ERROR_NAMES = (
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


def is_unavailable(exc: SQLAlchemyError) -> bool:
    """True if a database error means the database is unavailable (503), not our bug (500)."""
    if isinstance(exc, PoolTimeoutError):  # every pooled connection stayed busy for pool_timeout
        return True
    if not isinstance(exc, DBAPIError):
        return False
    if isinstance(exc.orig, sqlite3.Error):
        error_name = getattr(exc.orig, "sqlite_errorname", None) or ""
        return error_name.startswith(SQLITE_UNAVAILABLE_ERROR_NAMES)
    if isinstance(exc.orig, psycopg.Error):
        return is_postgres_unavailable(exc.orig)
    return False
