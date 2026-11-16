# Design: registry-service on SQLite and PostgreSQL

- **Date:** 2026-11-13 (revised 2026-11-14)
- **Status:** Approved 2026-11-16 (revision 4: SQLite engine bound to its file; scope of the commit-failure test)
- **Branch:** `feature/p1-postgresql`
- **Service:** `services/registry-service`
- **Decisions:** JL-004 to JL-009 in `docs/judgment-log.md`

## 1. Goal and source of truth

Let registry-service run on PostgreSQL in production while it keeps using the SQLite file `registry.db` locally and in tests. `DATABASE_URL` selects the database.

**Source:** the task "Move the registry to PostgreSQL, with Superpowers skills set" in `tutorials/intro_to_coding_assistant.md` of the course repository `alonitac/OzVeruach26`.

### Requirements

- **R1.** Existing endpoints keep behaving exactly the same: status codes, response bodies, and `Retry-After` on 503.
  - Error bodies stay FastAPI's default `application/json` (`{"detail": ...}`), not `application/problem+json`. This follows `docs/instructor-clarifications.md` and the user's decision, and overrides the tutorial's wording.
  - The one intended exception is NUL characters in string input; see section 7 and JL-009.
- **R2.** Locally and in tests, the app uses the SQLite file `registry.db`. In production it uses an existing PostgreSQL database. The app reads `DATABASE_URL` from the environment, loaded from `.env`.
- **R3.** The PostgreSQL database starts empty. A setup script creates the schema and the catalogues. Demo data is optional and never inserted automatically (JL-004, JL-005).

### Success criteria

- `uv run pytest` passes on SQLite with no Docker.
- The same suite passes against a local PostgreSQL 17 container when `TEST_DATABASE_URL` is set.
- The p95 benchmark is run on both databases (section 10).
  - SQLite must still pass NFR-1.1.
  - For PostgreSQL, report the measured p95 and whether it meets the 100 ms target. A miss measured only through Docker on macOS does not automatically block the work. A meaningful regression is flagged and investigated.
- The README smoke test can be shown to an instructor in about two minutes.

## 2. Working method

### The user runs the commands

The user runs every `uv`, Docker, database-setup, server, health-check, test, and benchmark command. Claude writes code and documentation, and runs only read-only inspection (reading files, `git status`, `git diff`).

The implementation plan is a sequence of small **checkpoints**. Each checkpoint gives:
1. the exact command, and the directory to run it from;
2. what the command does, including any effect on files, containers, or databases;
3. the expected output, or the lines that matter in it;
4. what to send back, normally the summary line or the error.

Claude then stops until the user reports the result. For test-first steps, the plan says when the user should expect a failing run and when a passing one.

Claude's reports separate two kinds of claim:
- "the user's output shows ...";
- "not yet run".

Claude never reports a test or command as passing unless the user's output shows it.

### Code readability

- Non-obvious functions get a short, plain-English docstring. Examples: `get_db`, `get_engine`, `open_sqlite`, `is_unavailable`, `is_postgres_unavailable`, `violated_constraint`, and the PostgreSQL fixtures.
- Comments explain design decisions, not syntax. Examples:
  - why `scope="function"`;
  - why `creator=` and `NullPool`;
  - why the SQLSTATE is checked before the exception class;
  - why `DOUBLE PRECISION`, and why `planting_date` is `TEXT`;
  - why `AUTOCOMMIT`.
- No comment repeats what the line already says.

### Security

- Credentials appear only in the git-ignored `.env` or in the user's shell. Never in:
  - tracked files, including `.env.example`, the README, and the specification and plan documents;
  - IDE settings (`.vscode/launch.json` gets no environment variables, because `db.py` reads `.env` itself);
  - source code or test code;
  - log and print output.
- **The one exception is the test container's password** (section 11).
  - It is a fixed throwaway value, `agropilot-local-test`, for a disposable PostgreSQL container that listens only on 127.0.0.1.
  - It is documented as such, is never reused for production, and is not treated as a real secret.
- **Printed URLs hide the password:** `URL.render_as_string(hide_password=True)`.
  - This covers the setup script's target line, the localhost-guard error, and the benchmark's target line.
  - SQLAlchemy's `URL` repr also masks the password.
- **Before any commit:** Claude reviews `git status` and the staged diff for credentials. It checks that `.env` is ignored (`git check-ignore`) and searches the staged diff for URLs with a password in them. It shows the user the result.
- Claude does not add or broaden Claude Code permissions, and does not edit permission settings (`.claude/settings*.json`), without discussing it with the user first.

## 3. Summary of changes

| Path | Change |
|---|---|
| `pyproject.toml`, `uv.lock` | `fastapi~=0.121` (was `~=0.115`). Add `sqlalchemy~=2.1`, `psycopg[binary]~=3.3`, and `python-dotenv~=1.0`. The user runs `uv add`; `uv.lock` records the exact versions. No `psycopg2`. |
| `.env.example` | New. Placeholders only (section 11). `.gitignore` already allows it and ignores `.env`. |
| `db.py` | Rewritten: configuration, engines, the request transaction, and error classification. |
| `main.py` | The exception handler moves from `sqlite3.DatabaseError` to `SQLAlchemyError`. |
| `repositories/*.py` | Use `text()`, `:name` placeholders, and `.mappings()`. No transaction code. |
| `routers/*.py` | Type hints change to `sqlalchemy.Connection`. Integrity errors are mapped through `violated_constraint`. Catalogue path parameters reject NUL. |
| `schemas.py` | NUL validator on names and catalogue IDs. |
| `scripts/setup_postgres.py` | New. Initial PostgreSQL schema, catalogues, and optional demo data. |
| `scripts/measure_p95.py` | `DATABASE_URL` replaces `REGISTRY_DB_PATH`, plus a `--database-url` option (section 10). |
| `tests/` | Fixtures for both backends, plus new tests (section 9). |
| `README.md`, `CLAUDE.md` | Configuration, PostgreSQL setup, PostgreSQL tests, benchmark, and smoke test. |

**Unchanged:**
- `seed_registry.sh` and `.vscode/launch.json`.
- The SQL statements, apart from their placeholders.
- Every status code and error message.
- `docs/learning/` and `docs/presentations/`, including `request-debugger.html`. They stay a P1 snapshot; see the follow-ups in section 13.

## 4. Configuration and connections (`db.py`)

### Reading the URL

- When `db.py` is imported, it calls `load_env_file()`, which runs `load_dotenv(path, override=False)`. The default path is `SERVICE_DIR / ".env"`.
  - The path parameter exists only so that a test can pass a temporary file.
  - With `override=False`, a variable that is already set always wins over `.env`. That includes one set in production or by a test.
  - The call lives in `db.py`, not `main.py` as first proposed, so that `scripts/setup_postgres.py` reads configuration exactly the way the app does.
- `get_database_url()` returns `os.environ.get("DATABASE_URL")`. If that is unset or empty, it returns `sqlite:///<absolute service dir>/registry.db`.
  - The default stays an absolute path.
  - A relative SQLite path inside `DATABASE_URL` resolves from the current directory, the way `REGISTRY_DB_PATH` resolves today.
- **PostgreSQL URL format:** `postgresql+psycopg://user:password@host:5432/dbname`.
  - **Why `+psycopg` is written out:** SQLAlchemy chooses the driver for a plain `postgresql://` URL, and that choice depends on its version.
    - SQLAlchemy 2.0 uses `psycopg2`.
    - SQLAlchemy 2.1 uses `psycopg` 3.
    - Confirmed in the SQLAlchemy source at tags `rel_2_0`, `rel_2_1_0`, and `rel_2_1_8`, and in the 2.1 migration notes.
  - With `+psycopg`, the driver stays psycopg 3 regardless of the SQLAlchemy version.
  - `.env.example` and the README use this form. The app does not rewrite URLs.
- `REGISTRY_DB_PATH` is removed.

### Engines

- **One engine per URL.**
  - A module-level `dict[str, Engine]` holds them.
  - `get_engine(url)` creates the engine on first use. It does this under a `threading.Lock`, so two concurrent first requests cannot create two pools.
- `dispose_engines()` disposes every engine and empties the dict. The test teardown calls it.
- **SQLite:**
  - `create_engine("sqlite://", creator=functools.partial(open_sqlite, db_path), poolclass=NullPool)`.
  - **Each engine stays bound to its own file.**
    - `db_path` is computed once, when the engine is created: it is the URL's database path (`make_url(url).database`), resolved to an absolute path.
    - `open_sqlite(db_path)` connects to that path only. It never reads `DATABASE_URL` or the current directory again.
    - So changing the environment variable, or the current directory, after the engine exists cannot redirect the cached engine to another file.
  - `open_sqlite` is today's connect code otherwise unchanged: a `file:` URI with `?mode=rw`, `uri=True`, `check_same_thread=False`, and `PRAGMA foreign_keys = ON`.
  - With `creator=`, a missing file stays a `SQLITE_CANTOPEN` error (503) and is not replaced by a new empty file.
  - `NullPool` keeps one fresh connection per request (JL-002).
- **PostgreSQL:**
  - `create_engine(url, pool_pre_ping=True)` with the default pool: `pool_size=5`, `max_overflow=10`, `pool_timeout=30` (JL-007).

### Request transaction (JL-008)

```python
def get_db() -> Iterator[Connection]:
    """Give the endpoint one connection inside one transaction."""
    engine = get_engine(get_database_url())
    with engine.begin() as conn:   # commits if the endpoint returns, rolls back if it raises
        yield conn

# scope="function": the commit runs BEFORE the response is sent.
DbConnection = Annotated[Connection, Depends(get_db, scope="function")]
```

**Confirmed by experiment on FastAPI 0.162.0:**
- Without `scope="function"`, a commit that fails after `yield` still sends `201` to the client.
- With it, the exception handler runs and the client gets `503`.
- An `HTTPException` raised in the endpoint reaches the dependency, which rolls back.

`scope=` first exists in FastAPI 0.121.0. Confirmed: 0.120.4 has no `scope` parameter, and 0.121.0 does. Hence `fastapi~=0.121`, which means `>=0.121,<1.0`.

**Rules:**
1. Repositories and routers never call `commit()`, `rollback()`, or `begin()`. `get_db` owns the transaction.
2. After catching a database error, a router raises its `HTTPException` immediately and runs no more queries. PostgreSQL rejects statements in a failed transaction.

## 5. Repositories

Mechanical changes only:

| Today | New |
|---|---|
| `conn.execute("... WHERE id = ?", (x,))` | `conn.execute(text("... WHERE id = :id"), {"id": x})` |
| `dict(row) for row in cursor` | `dict(row) for row in result.mappings()` |
| `.fetchone()` | `.mappings().first()` |
| `with conn:` around writes | removed |
| `cursor.rowcount == 1` | `result.rowcount == 1` |

`UPDATABLE_COLUMNS` in `repositories/plots.py` keeps guarding the column names in the dynamic `UPDATE`.

There is no `ORDER BY`. No test or spec relies on list order.

## 6. Error mapping

### 503 classification (`db.py`)

```python
SQLITE_UNAVAILABLE_ERROR_NAMES = (...)   # today's list, unchanged

POSTGRES_UNAVAILABLE_SQLSTATES = (
    "08",                         # connection exception: connection lost or failed
    "28",                         # invalid authorization: wrong password, access denied
    "3D000",                      # database does not exist
    "53",                         # insufficient resources: too many connections, disk full
    "57P01", "57P02", "57P03",    # server shutting down, crashed, or still starting up
    "58",                         # system error: I/O failure on the server
)

def is_postgres_unavailable(orig: psycopg.Error) -> bool:
    if orig.sqlstate is None:
        # The client library failed before the server answered, e.g. connection refused.
        return isinstance(orig, psycopg.OperationalError)
    return orig.sqlstate.startswith(POSTGRES_UNAVAILABLE_SQLSTATES)

def is_unavailable(exc: SQLAlchemyError) -> bool:
    if isinstance(exc, PoolTimeoutError):     # sqlalchemy.exc.TimeoutError: the pool stayed full for pool_timeout
        return True
    if not isinstance(exc, DBAPIError):
        return False
    if isinstance(exc.orig, sqlite3.Error):
        error_name = getattr(exc.orig, "sqlite_errorname", None) or ""
        return error_name.startswith(SQLITE_UNAVAILABLE_ERROR_NAMES)
    if isinstance(exc.orig, psycopg.Error):
        return is_postgres_unavailable(exc.orig)
    return False
```

**Facts this rule relies on, confirmed on psycopg 3.3.9:**
- Connection refused raises `OperationalError` with `sqlstate = None`.
- `3D000` is a `ProgrammingError`. That is why the rule checks the code before the class.
- A NUL in text raises a client-side `DataError` that also has `sqlstate = None`. That is why the `None` branch also checks the class.
- `57014`, `40001`, and `40P01` are `OperationalError`s, but they are not on the list, so they become 500.

**Expected behavior:** a wrong password (`28P01`, `28000`) and a missing database (`3D000`) return 503 with `Retry-After: 5`. This mirrors SQLite, where `SQLITE_CANTOPEN` returns 503.

### Constraint classification (`db.py`)

```python
def violated_constraint(exc: IntegrityError) -> str | None:
    """'unique' or 'foreign_key' for the violations the routers map; otherwise None."""
    if isinstance(exc.orig, sqlite3.Error):
        return {"SQLITE_CONSTRAINT_UNIQUE": "unique",
                "SQLITE_CONSTRAINT_FOREIGNKEY": "foreign_key"}.get(exc.orig.sqlite_errorname)
    if isinstance(exc.orig, psycopg.Error):
        return {"23505": "unique", "23503": "foreign_key"}.get(exc.orig.sqlstate)
    return None
```

### Routers and handler

| Router | Constraint | Response (unchanged) |
|---|---|---|
| `routers/farms.py` `delete_farm` | `foreign_key` | 409 `Farm still has plots` |
| `routers/plots.py` `raise_for_integrity_error` | `unique` | 409 `Plot name already exists on this farm` |
| `routers/plots.py` `raise_for_integrity_error` | `foreign_key` | 404 `Farm not found` |

Any other `IntegrityError` is re-raised.

The handler in `main.py` is `@app.exception_handler(SQLAlchemyError)`, with the same body as today:
- If `is_unavailable(exc)`: log a warning and return 503 with `{"detail": "Database unavailable"}` and `Retry-After: 5`.
- Otherwise re-raise, which gives a plain-text `500 Internal Server Error`.

**What the logged warning contains:**
- It includes the driver's message, which can name the host, port, and database user.
- psycopg does not put the password in its error messages. V7 checks this against the wrong-password test.

### Where each error appears

| When | Example | Handled by | Result |
|---|---|---|---|
| Connect (dependency setup) | Missing file, server down, wrong password | Handler | 503 |
| Statement: constraint | Duplicate plot name; deleting a farm that has plots; the farm deleted concurrently | Router | 409 / 409 / 404 |
| Statement: environment | `SQLITE_BUSY`, connection lost | Handler | 503 |
| Statement: our bug | SQL typo, missing table, unmapped constraint | Handler | 500 |
| Commit | Connection lost, `SQLITE_BUSY`/`FULL`/`IOERR` | Handler (`scope="function"`) | 503 |
| Pool checkout | All 15 connections busy for 30 s | Handler | 503 |

**A failed commit has an unknown outcome.**
- If the connection is lost while `COMMIT` is in flight, the server may already have committed. The client cannot know.
- So a 503 from a failed commit means "the result is unknown; retry later", not "nothing was saved".
- This design does not try to resolve that ambiguity; it only guarantees that a failed commit is never reported as a success.
- Retrying a `POST /v1/farms` after such a 503 could create a second farm, because each POST generates a new ID.

Constraints are checked immediately, at the statement. That is PostgreSQL's default, and no constraint is declared `DEFERRABLE`. So a constraint violation is raised inside the router.

## 7. NUL characters (JL-009)

`schemas.py`:

```python
def reject_nul(value: str) -> str:
    """PostgreSQL text cannot store NUL, so reject it on both databases."""
    if "\x00" in value:
        raise ValueError("must not contain NUL characters")
    return value

NoNulStr = Annotated[str, AfterValidator(reject_nul)]
Name = Annotated[str, Field(min_length=1), AfterValidator(reject_nul)]
```

**Where the validator applies:**
- `Name`, for farm and plot names on POST and PATCH.
- `crop_id`, `soil_id`, and `emitter_id` in `PlotCreate` and `PlotUpdate`, which use `NoNulStr`.
- The path parameters `crop_id`, `soil_id`, and `emitter_id` in `routers/catalogues.py`.

**Where it doesn't need to:**
- UUID fields and paths are already validated as UUIDs.
- `planting_date` has a digits-only pattern.

**Result:** FastAPI's default 422 validation error on both databases.

**Behavior change on SQLite:**

| NUL in | Before | After |
|---|---|---|
| A farm or plot name | 201 | 422 validation error |
| A catalogue ID in a plot body | 422 `Unknown crop` | 422 validation error |
| A catalogue path | 404 | 422 validation error |

## 8. PostgreSQL setup script (`scripts/setup_postgres.py`)

**Purpose:** initial schema setup only. It is **not a migration tool**. Its docstring, `--help` text, and the README all say so.

```bash
uv run python scripts/setup_postgres.py          # schema + catalogues
uv run python scripts/setup_postgres.py --demo   # also 2 demo farms + 4 demo plots (development only)
```

**Behavior:**
- Reads the URL with `db.get_database_url()`. It exits with an error unless the backend is PostgreSQL.
- Before it changes anything, it prints the target with the password hidden.
- With `--demo`, it prints `WARNING: inserting demo farms and plots. Never use --demo on a production database.`
- Runs everything in one `engine.begin()` transaction. PostgreSQL rolls back DDL too, so a failure leaves the database unchanged.
- Uses `CREATE TABLE IF NOT EXISTS` and `INSERT ... ON CONFLICT DO NOTHING`. There is no `DROP`, `DELETE`, or `TRUNCATE`.
- Ends by printing row counts, for example `Catalogues: 2 crops, 3 soils, 4 emitters. Demo data: skipped.`
- Exposes `create_schema(conn)`, `insert_catalogues(conn)`, and `insert_demo_data(conn)`. The PostgreSQL test fixtures import these.

**Known limits (JL-004):**
- A table that already exists with a different definition is left unchanged.
- A changed catalogue row is not overwritten.

### Schema

```sql
CREATE TABLE IF NOT EXISTS farms (
  id   TEXT PRIMARY KEY,
  name TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS crops (
  id   TEXT PRIMARY KEY,
  name TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS soils (
  id                       TEXT PRIMARY KEY,
  name                     TEXT NOT NULL,
  available_water_mm_per_m INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS emitters (
  id       TEXT PRIMARY KEY,
  name     TEXT NOT NULL,
  flow_lph DOUBLE PRECISION NOT NULL
);
CREATE TABLE IF NOT EXISTS plots (
  id                TEXT PRIMARY KEY,
  farm_id           TEXT NOT NULL REFERENCES farms(id),
  name              TEXT NOT NULL,
  area_m2           DOUBLE PRECISION NOT NULL,
  crop_id           TEXT NOT NULL REFERENCES crops(id),
  planting_date     TEXT NOT NULL,
  soil_id           TEXT NOT NULL REFERENCES soils(id),
  row_spacing_m     DOUBLE PRECISION NOT NULL,
  emitter_spacing_m DOUBLE PRECISION NOT NULL,
  emitter_id        TEXT NOT NULL REFERENCES emitters(id),
  lat               DOUBLE PRECISION NOT NULL,
  lon               DOUBLE PRECISION NOT NULL,
  UNIQUE (farm_id, name)
);
```

**Why these types:**
- **`DOUBLE PRECISION`, not `REAL`.** PostgreSQL's `REAL` is a 4-byte float with about 6 significant digits, while SQLite's `REAL` is an 8-byte float. `REAL` would silently round high-precision coordinates.
- **`planting_date` stays `TEXT`.** A `DATE` column returns a Python `date`, and the response model declares `planting_date: str`, so every plot response would fail with 500.
- **IDs stay `TEXT`**, so values match SQLite exactly.
- **No extra index.** The index behind `UNIQUE (farm_id, name)` already serves `WHERE farm_id = :farm_id`.

### Data

- **Catalogues:** copied exactly from `seed_registry.sh`: 2 crops, 3 soils, 4 emitters, with the same IDs, names, and values.
- **Demo data (`--demo`):** the 2 farms and 4 plots from `seed_registry.sh`.
- The two copies of these rows are kept in sync by hand (JL-005). Shared tests that assert exact catalogue values on both backends catch drift.

## 9. Tests

### Backend selection

- `uv run pytest` runs on SQLite (the default).
- With `TEST_DATABASE_URL` set to an admin URL for a local PostgreSQL 17 container, `uv run pytest` runs the same suite on PostgreSQL. The command is in section 11.
- Tests never use a `DATABASE_URL` from `.env`: an autouse fixture always overrides it.
- `TEST_DATABASE_URL` is set in the shell for one run and never written in `.env`. Because `db.py` loads every key from `.env`, a `TEST_DATABASE_URL` written there would silently switch the default run to PostgreSQL.

### Fixtures (`tests/conftest.py`)

A PostgreSQL database is created only for tests that need one. Pure unit tests run without a database on both backends.

| Fixture | Used by | SQLite | PostgreSQL |
|---|---|---|---|
| `isolated_environment` (autouse; replaces `isolated_db_path`) | Every test | Sets `DATABASE_URL` to an unseeded temp path. A test that touches the database by accident gets 503; it never reaches the real `registry.db` or `.env`. Teardown: `dispose_engines()`. | Same. No database is created. |
| `database_url` | Requested by `seeded_db`, `client`, and `live_server` | Returns the temp SQLite URL | Creates `agropilot_test_<uuid4 hex>` and sets `DATABASE_URL` to it. Teardown: `dispose_engines()`, then drops that database. |
| `seeded_db` | Tests that need data | `seed_registry.sh` (unchanged) | `create_schema`, `insert_catalogues`, `insert_demo_data` |
| `client`, `live_server` | API tests | Unchanged, except that `live_server` passes `DATABASE_URL` | Same |
| `sqlite_db_path` | SQLite-only tests | The file path | Not used (the test is skipped) |
| `postgres_admin_url` | PostgreSQL-only tests | Not used (the test is skipped) | The admin URL |

**Backend-specific tests:**
- They use the markers `sqlite_only` and `postgres_only`, registered in `pyproject.toml`.
- `pytest_collection_modifyitems` marks the tests for the other backend as skipped.
- Pytest sets up no fixtures for a skipped test, so a SQLite-only test never creates a PostgreSQL database.

### PostgreSQL fixture safety

1. **Localhost guard.** At session start, the run stops with an error unless the host in `TEST_DATABASE_URL` is `localhost` or `127.0.0.1`. The error message shows the URL with the password hidden.
2. **No transaction around database creation.** `CREATE DATABASE` and `DROP DATABASE` cannot run inside a transaction. They run on an admin engine created with `isolation_level="AUTOCOMMIT"` and `poolclass=NullPool`.
3. **Only drop what this test created.**
   - The fixture drops only the exact name it generated and holds in a local variable.
   - Before the drop, it asserts that the name starts with `agropilot_test_`. It then runs `DROP DATABASE IF EXISTS "<name>" WITH (FORCE)`.
   - It never lists databases or drops them by pattern.

A fresh database for each test that needs one is the chosen isolation. The extra runtime will be measured before any optimization is considered.

### Test placement

**The whole existing suite runs on both backends,** including the concurrency tests. The exceptions are the SQLite-file tests listed below.

**New tests on both backends:**

| Test | File | Proves |
|---|---|---|
| A failed commit returns 503 with `Retry-After: 5`, never 201 | `tests/test_transactions.py` | JL-008 `scope="function"`. The test monkeypatches `engine.dialect.do_commit` to raise a driver error that means "unavailable" (`SQLITE_BUSY` or `57P01`). The patch raises *before* `COMMIT` reaches the database, so the test may also check that this simulated failure saved no row. Its docstring says the check covers only this simulated case. A real failed commit can have an unknown outcome (section 6), and the test does not claim otherwise. |
| When the second of two writes fails, both are rolled back | `tests/test_transactions.py` | JL-008 atomicity. Uses a FastAPI app built inside the test with the real `DbConnection`: `create_farm`, then `create_plot` with an unknown `crop_id` (a real foreign-key violation). Afterwards, `GET /v1/farms` shows no new farm. No production route is added. |
| Pool timeout returns 503 with `Retry-After` | `tests/test_database_errors.py` | A repository function is monkeypatched to raise `PoolTimeoutError`. |
| NUL input returns 422 | `tests/test_nul_input.py` | Parametrized over: farm and plot `name` (POST and PATCH); `crop_id`, `soil_id`, `emitter_id`; and `/v1/{crops,soils,emitters}/a%00b`. |
| High-precision coordinates round-trip exactly | `tests/test_plots.py` | No `REAL` precision loss. Example: `lat: 31.2512345`, `lon: 34.7912345678`. |

**New unit tests (no database, always run):**

`tests/test_database_errors.py`, the classifiers:
- SQLite names (adapted from the existing test).
- PostgreSQL codes that are unavailable: `08006`, `08001`, `28P01`, `28000`, `3D000`, `53300`, `57P01`, `57P03`, and `58030`.
- Codes and errors that are not: `57014`, `40001`, `40P01`, `42601`, and a client-side `DataError`.
- `PoolTimeoutError`.
- `violated_constraint` for both drivers.

`tests/test_db_config.py`, our own wiring only, not SQLAlchemy's or python-dotenv's behavior:

| Test | Proves |
|---|---|
| `get_engine` returns the same engine for the same URL and a different one for a different URL | One engine (one pool) per URL |
| After `dispose_engines()`, `get_engine` returns a new engine | The cache is emptied, so tests do not share pools |
| Two SQLite URLs pointing at two temp files: each engine's connection reports its own file (`PRAGMA database_list`), also after `DATABASE_URL` is changed to the other file | Each SQLite engine stays bound to its original file. Uses two empty temp files; no seeding. |
| A SQLite URL gets `NullPool`; a PostgreSQL URL gets `QueuePool` with `pool_pre_ping` on | Our engine settings (JL-002, JL-007). `create_engine` does not connect, so no server is needed. |
| `load_env_file(tmp .env)` with `DATABASE_URL` unset: `get_database_url()` returns the file's value | `.env` is read from the given path |
| Same file, `DATABASE_URL` already set: the environment value wins | `override=False` precedence |
| `DATABASE_URL` unset and no `.env` value: the absolute `<service dir>/registry.db` | The default |

Not tested: the lock in `get_engine`. A race test would be slow and flaky, and the lock is a single `with` statement.

Other unit tests:
- Unreachable PostgreSQL returns 503: `DATABASE_URL` points to `127.0.0.1:1`. The test builds its own `TestClient(app)` instead of using the `client` fixture, so it creates no test database.
- `setup_postgres.py` refuses a SQLite URL.

**SQLite only (existing, now marked `sqlite_only`):**
- A missing file returns 503.
- A corrupt file returns 503.
- An empty file returns 500.
- Reseeding recovers without a restart.

**PostgreSQL only (new, marked `postgres_only`):**
- A wrong password returns 503 with `Retry-After`, and the logged warning does not contain the password.
- A nonexistent database returns 503 with `Retry-After`.
- An empty database with no tables returns 500 (the counterpart of SQLite's empty file).
- `setup_postgres.py` run twice succeeds and changes nothing.
- Without `--demo` there are no farms.

## 10. p95 benchmark (`scripts/measure_p95.py`)

### Options compared

- **One configurable script (chosen).**
  - The measuring and reporting code is already HTTP-only and backend-agnostic: `run_benchmark`, `p95`, `benchmark_passed`, and the report.
  - Only the setup in `main()` depends on the database, and that part is about five lines.
- **Shared measurement functions with a separate setup script per backend.** Rejected: the second script would repeat argument parsing, server startup, warm-up, and reporting, only to change those five lines.
- **The benchmark creates and drops its own PostgreSQL database.** Rejected: it would duplicate the fixture's create and drop code, and put `DROP DATABASE` in a second script.

### Design

- **Without options:** behavior is unchanged. The script seeds a temporary SQLite file with `seed_registry.sh` and starts uvicorn with `DATABASE_URL=sqlite:///<tmp>/registry.db`.
- **`--database-url URL`:** the script benchmarks that database as it is.
  - The database must already contain the demo data, created by `setup_postgres.py --demo`.
  - The existing warm-up request to each endpoint fails fast if the data is missing.
  - The script sends only GET requests and never writes.
  - It prints the target with the password hidden.
- The server subprocess always receives `DATABASE_URL` explicitly. Because the environment wins over `.env` (section 4), the benchmark never uses `.env` by accident.
- No classes. Functions only; no new dependencies.

### Running

- The user runs both benchmarks after implementation: SQLite, then a local PostgreSQL 17 container.
- **Expected caveat:** on macOS, Docker Desktop runs PostgreSQL inside a virtual machine and forwards the port through it. So the PostgreSQL number reflects this local setup, not production.
- **Reporting:** state both p95 results and whether each meets the 100 ms target.
  - A PostgreSQL miss caused only by Docker on macOS does not automatically block the work.
  - A meaningful regression is flagged and investigated, and the findings go to the user, who decides. Examples: PostgreSQL p95 above 100 ms, or far above SQLite on one endpoint.
- Pool-tuning experiments stay a separate follow-up (section 13).

## 11. Documentation

### `.env.example`

Placeholders only:

```bash
# Copy to .env (git-ignored) and fill in. Real credentials go only in .env.
# Unset or empty DATABASE_URL: the SQLite file registry.db in this directory.
# DATABASE_URL=sqlite:////absolute/path/to/registry.db
# PostgreSQL through psycopg 3 (keep "+psycopg"):
# DATABASE_URL=postgresql+psycopg://<user>:<password>@<host>:5432/<database>
# Do not put TEST_DATABASE_URL here; set it in the shell for a test run.
```

### `services/registry-service/README.md`

1. **Configuration:**
   - `DATABASE_URL` replaces `REGISTRY_DB_PATH`.
   - Both URL forms.
   - `.env` and `.env.example`, and the precedence rule.
   - Why `+psycopg` is written out (section 4).
2. **PostgreSQL setup:**
   - How to use `setup_postgres.py`.
   - "Initial schema setup only, not a migration tool."
   - A warning never to use `--demo` on production.
3. **Running tests on PostgreSQL:**
   1. `docker run --rm -d --name agropilot-test-pg -e POSTGRES_PASSWORD=agropilot-local-test -p 127.0.0.1:5433:5432 postgres:17`
   2. `TEST_DATABASE_URL='postgresql+psycopg://postgres:agropilot-local-test@127.0.0.1:5433/postgres' uv run pytest`
   3. `docker stop agropilot-test-pg`

   - `-p 127.0.0.1:5433:5432` publishes the port only on the loopback interface, so other machines on the network cannot reach the container.
   - Port 5433 avoids a conflict with any local PostgreSQL on 5432.
   - The README states that `agropilot-local-test` is a fixed throwaway password for this disposable, localhost-only container: never reuse it for production, and do not treat it as a real secret.
4. **Benchmark:** both commands from section 10, with the macOS Docker caveat.
5. **Manual smoke test** (about 2 minutes):
   - Start a named PostgreSQL 17 container, without `--rm`, with the same loopback binding and throwaway password. Put `DATABASE_URL` in `.env`, run `setup_postgres.py --demo`, and start the app.
   - `GET /v1/farms` shows the 2 demo farms.
   - A duplicate plot name returns 409.
   - Deleting a farm that has plots returns 409.
   - After `docker stop`, `GET /v1/farms` returns 503 with `Retry-After`.
   - After `docker start`, requests recover without restarting the app.
   - Finish with `docker rm -f`.

### `CLAUDE.md`

Update:
- the commands block: add the PostgreSQL test command, the setup script, and the benchmark option;
- the test sentence that mentions `REGISTRY_DB_PATH`;
- the `registry-service` architecture bullet: SQLAlchemy Core on SQLite or PostgreSQL, the request transaction, and the error classification.

## 12. Commits

- Nothing is committed without the user's approval.
- Before each approved commit, Claude shows:
  - the branch, `git status`, and the remote;
  - the credential review from section 2.
- No AI attribution lines.

## 13. Out of scope and follow-ups

These are tracked here and repeated as the final task of the implementation plan, so they are not lost.

| ID | Follow-up | Notes |
|---|---|---|
| F1 | Update `docs/learning/p1-walkthrough.md` | Deferred. It describes the P1 `sqlite3` code. |
| F2 | Update the P1 slides and presenter guide (`docs/presentations/p1-slides.pptx`, `p1-presenter-guide.md`) | Deferred. |
| F3 | **Request debugger:** extend `request-debugger.html` with SQLite and PostgreSQL modes, or create a separate presentation | Decide after implementation, by reviewing the source structure (below). Until then, do not rebuild `request-debugger.html`. |
| F4 | Pool-tuning benchmark (3+5, 5+10, 10+15; `pre_ping` on and off) | Needs a concurrent-load mode. At 10 rps and about 10 ms per request, fewer than one connection is in use on average, so pool sizes cannot differ. FastAPI runs sync endpoints in a 40-thread pool, which is more than the 15 connections the pool allows. |
| F5 | Secrets management for cloud deployment (Secret Manager or mounted secrets) | `.env` is for local use only. |
| F6 | A migration tool, if the schema starts to change over time | JL-004. |

**F3 source structure, as found today:**
- `docs/presentations/debugger-src/build_debugger.py` (45 lines) reads the current service files and writes them into `debugger.template.html` (2,070 lines). The files are `main.py`, `db.py`, `schemas.py`, the routers, the repositories, and `seed_registry.sh`.
- It also embeds the library versions, including the SQLite version.
- `check_debugger.js` checks that the step texts point at line numbers that exist.
- **Consequence:** rebuilding after this change would replace the P1 code inside `request-debugger.html` with the new code, and break the step texts that point at P1 line numbers. The existing HTML is preserved only as long as it is not rebuilt in place.
- The build script already takes the template and output paths as arguments. A separate output file is therefore cheap to produce. The real work is writing the step texts, in either option.

## 14. To verify during implementation

| ID | Item | Covered by |
|---|---|---|
| V1 | Making `dialect.do_commit` raise a driver error produces a wrapped `DBAPIError` that reaches the handler. This proves the simulated case only (section 6). | The commit-failure test |
| V2 | A wrong password and a missing database reach the handler as 503, whether psycopg reports a SQLSTATE or `None` | The PostgreSQL-only tests |
| V3 | `AfterValidator` on a FastAPI path parameter returns 422 | The NUL tests |
| V4 | Errors raised by the SQLite `creator=` hook are wrapped as `DBAPIError` | The existing missing-file and corrupt-file 503 tests |
| V5 | Runtime of the PostgreSQL suite | The user's test output |
| V6 | Exact versions of the new dependencies; the lock contains `psycopg` and not `psycopg2` | `uv.lock` after the user runs `uv add` |
| V7 | The logged 503 warning for a wrong password contains no password | The wrong-password test |
| V8 | Skipped backend-specific tests create no PostgreSQL database | The PostgreSQL run's skip count, plus no leftover `agropilot_test_` databases after the run (one read-only `psql` listing, which the user runs) |
