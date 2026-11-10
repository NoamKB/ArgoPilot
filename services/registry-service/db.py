import os
import sqlite3
from collections.abc import Iterator
from pathlib import Path
from typing import Annotated

from fastapi import Depends

DEFAULT_DB_PATH = Path(__file__).resolve().parent / "registry.db"

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
