# registry-service on SQLite and PostgreSQL — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Project override:** the user runs every terminal command (see "Checkpoints"). An implementer writes files and stops at each checkpoint. It never runs `uv`, `docker`, `pytest`, `uvicorn`, `curl`, or project scripts itself.

**Goal:** registry-service runs on PostgreSQL in production and on the SQLite file `registry.db` locally and in tests. `DATABASE_URL` selects the database. Endpoint behavior is unchanged, apart from the approved NUL exception.

**Architecture:**
- SQLAlchemy Core with handwritten `text()` SQL replaces direct `sqlite3` calls. There is one engine per URL.
- `get_db` opens one transaction per request (`engine.begin()`, with `Depends(..., scope="function")`).
- `db.py` sorts database errors by driver code into three outcomes: 503 for an unavailable database, a constraint mapping for the routers, or 500.
- `scripts/setup_postgres.py` creates the PostgreSQL schema and catalogues.
- The existing test suite runs against either database. `TEST_DATABASE_URL` selects PostgreSQL.

**Tech stack:**
- Python 3.12 with FastAPI (`~=0.121`).
- SQLAlchemy `~=2.1` with psycopg 3 (`psycopg[binary]~=3.3`), and python-dotenv `~=1.0`.
- pytest and httpx2.
- PostgreSQL 17 in Docker, for tests and the benchmark only.

**Spec:** `docs/superpowers/specs/2026-11-13-postgresql-design.md` (approved; commit `4197c7e`). Section references below (§N) point to it. Read it before any task.

## Checkpoints

A checkpoint is a command the **user** runs. Every checkpoint has this shape:

> **Checkpoint X.Y (you run)**
> - **Dir:** where to run it
> - **Command:** the exact command
> - **Effect:** what it changes: files, containers, databases, or nothing
> - **Expected:** the lines that mean success, or the expected failure on a test-first step
> - **Send back:** what to paste into the chat

**After each checkpoint, the implementer stops and waits.**
- Its report separates "your output shows ..." from "not yet run".
- If the output differs from **Expected**, the implementer does not guess a fix. It uses `superpowers:systematic-debugging`, explains the cause, and proposes the fix before editing.

**Directory:** all commands run from `services/registry-service` unless a checkpoint says otherwise.

**Testing policy (risk-based):**
- After a change, run only the tests for the changed functionality.
- Run the full suite at the integration milestones only:
  - Checkpoint 4.10: SQLite, after the switch;
  - Checkpoint 8.2: SQLite, after the fixture rework;
  - Checkpoint 8.3: PostgreSQL;
  - Task 11: both databases.
- No separate expected-failure runs. The new tests are reviewed as code before they run. The one exception is the Task 6 mutation check, which is the only evidence that the commit test detects a missing `scope="function"`.
- Database isolation is unchanged. Every test uses a temporary SQLite file or a temporary PostgreSQL database.

**Commit steps:**
- The implementer shows `git status`, the staged file list, and the secrets review (§2).
- The user approves; then the implementer commits.
- No push and no AI attribution lines.
- Stage the exact paths only. Never stage `experiments/`, `.env`, or `registry.db`.

## Global Constraints

- `fastapi~=0.121`, `sqlalchemy~=2.1`, `psycopg[binary]~=3.3`, `python-dotenv~=1.0`. No `psycopg2`, and no other new runtime dependency.
- PostgreSQL URLs always use the `postgresql+psycopg://` form. The app never rewrites URLs.
- The default URL is `sqlite:///<absolute service dir>/registry.db` when `DATABASE_URL` is unset or empty.
- **R1:** every status code, error `detail`, and the `Retry-After: 5` header stay exactly as they are today. The only change is that NUL input returns 422 (§7, JL-009).
- 503 body: `{"detail": "Database unavailable"}`, header `Retry-After: 5`. A 500 is plain-text `Internal Server Error`.
- Repositories and routers never call `commit()`, `rollback()`, or `begin()` (§4 rule 1).
- After catching a database error, a router raises its `HTTPException` immediately (§4 rule 2).
- **Credentials** never appear in tracked files, IDE settings, code, or printed output. The one exception is the throwaway test password `agropilot-local-test`, used only for the localhost container.
  - Every printed URL uses `render_as_string(hide_password=True)`.
- **Docker:** the port is always published as `-p 127.0.0.1:<port>:5432`, and the image is `postgres:17`.
- **Code style:**
  - Short plain-English docstrings, only on non-obvious functions.
  - Comments explain design decisions, never syntax.
  - No classes in scripts.
- **Do not touch:** `docs/learning/`, `docs/presentations/`, `.vscode/launch.json`, `.claude/settings*.json`, or `seed_registry.sh`. Do not rebuild `request-debugger.html`.

## Review Focus

These are the failure modes most likely to hurt a real user that the spec implies but does not test directly. Each one has a test in the task named.

1. **A test run reaches the real `registry.db`, or a production `DATABASE_URL` loaded from `.env`.**
   - Expected: every test points at a temporary database.
   - Covered by: Task 4 `test_autouse_fixture_points_at_temporary_database`, and Task 4's step ordering (no full run on a half-switched tree).
2. **A relative SQLite path in `DATABASE_URL` while the working directory changes.**
   - Expected: the engine stays on the file that the path meant when the engine was created.
   - Covered by: Task 2 `test_relative_sqlite_path_is_resolved_once`.
3. **An empty `DATABASE_URL=` line in `.env`.**
   - Expected: the default SQLite file, not a crash.
   - Covered by: Task 2 `test_empty_database_url_uses_default`.
4. **A real production password containing `@`, `/`, or `:`.**
   - Expected: it works once percent-encoded, and the docs say so.
   - Covered by: Task 2 `test_percent_encoded_password_is_decoded`, plus the doc lines in Task 10.
5. **PostgreSQL restarts, or kills idle connections, while the app runs.**
   - Expected: the next request succeeds without restarting the app (`pool_pre_ping`).
   - Covered by: Task 8 `test_request_succeeds_after_server_closes_connections`, plus the smoke test in Task 10.

## File map

| File | Responsibility | Task |
|---|---|---|
| `pyproject.toml`, `uv.lock` | Dependencies; pytest markers | 1, 4 |
| `db.py` | Configuration, engines, request transaction, error classification | 2, 3, 4 |
| `main.py` | `SQLAlchemyError` handler | 4 |
| `repositories/{farms,plots,catalogues}.py` | SQL only (`text()`, `.mappings()`) | 4 |
| `routers/{farms,plots,catalogues}.py` | HTTP; constraint mapping; NUL in catalogue paths | 4, 5 |
| `schemas.py` | `reject_nul`, `NoNulStr`, `Name` | 5 |
| `scripts/setup_postgres.py` | PostgreSQL schema, catalogues, and demo data | 7 |
| `scripts/measure_p95.py` | `DATABASE_URL`; `--database-url` | 4, 9 |
| `tests/conftest.py` | Backend selection, isolation, and PostgreSQL fixtures | 4, 8 |
| `tests/test_db_config.py` | Engine cache, binding, and environment precedence | 2 |
| `tests/test_database_errors.py` | Classifiers; 503/500 behavior | 3, 4, 8 |
| `tests/test_nul_input.py` | NUL returns 422 | 5 |
| `tests/test_transactions.py` | Commit failure; atomic rollback | 6 |
| `tests/test_setup_postgres.py` | Setup-script behavior on both backends | 7 |
| `tests/test_postgres_only.py` | PostgreSQL-only behavior | 8 |
| `tests/test_plots.py` | High-precision round trip | 7 |
| `tests/test_measure_p95.py` | `benchmark_database` | 9 |
| `.env.example`, `README.md`, `CLAUDE.md` | Usage docs | 10 |

---

### Task 0: Baseline

Nothing is edited in this task.

- [ ] **Checkpoint 0.1 (you run)**
  - **Command:** `git status --short && uv run pytest -q`
  - **Effect:** none. The tests use temporary databases.
  - **Expected:** all tests pass. The last line reads `N passed in ...`. The earlier note recorded 171; the actual number is the baseline.
  - **Send back:** the last line, plus anything in `git status` other than `?? experiments/`.

- [ ] **Checkpoint 0.2 (you run)**
  - **Command:** `docker --version && sqlite3 --version`
  - **Effect:** none.
  - **Expected:** two version lines. Docker Desktop must be running before Task 8.
  - **Send back:** both lines.

---

### Task 1: Dependencies

**Files:** Modify `pyproject.toml` and `uv.lock`. The changes come from `uv add`; the implementer edits nothing by hand.

- [ ] **Checkpoint 1.1 (you run)**
  - **Command:** `uv add "fastapi~=0.121" "sqlalchemy~=2.1" "psycopg[binary]~=3.3" "python-dotenv~=1.0"`
  - **Effect:**
    - Rewrites `dependencies` in `pyproject.toml`.
    - Updates `uv.lock`.
    - Installs the packages into `.venv`.
    - The installed FastAPI (0.162.0) already satisfies `~=0.121`, so it should stay.
  - **Expected:** `Resolved ... packages`, and lines with `+ sqlalchemy==2.1.x`, `+ psycopg==3.3.x`, `+ psycopg-binary==3.3.x`, `+ python-dotenv==1.x`.
  - **Send back:** the full output.

- [ ] **Checkpoint 1.2 (you run)**
  - **Command:** `uv lock --check && grep -c 'name = "psycopg2' uv.lock; uv run pytest -q`
  - **Effect:** none.
  - **Expected:**
    - `uv lock --check` succeeds.
    - The `grep` count is `0` (V6: no psycopg2).
    - Same pass count as Checkpoint 0.1.
  - **Send back:** the three results.

- [ ] **Step 1.3:** The implementer reads the `pyproject.toml` diff and reports the exact locked versions (V6).

- [x] **Step 1.4: Commit** (done: `baf7900`) `pyproject.toml` and `uv.lock`. Message: `build: add SQLAlchemy, psycopg 3, python-dotenv; raise FastAPI floor to 0.121`

---

### Task 2: Configuration and engines in `db.py` (added alongside the old code)

The new functions are added next to today's `get_db_path` and `get_db`. Nothing calls them yet, so the app's behavior does not change in this task.

**Files:**
- Modify: `db.py`
- Create: `tests/test_db_config.py`

**Interfaces (Produces):**

```python
SERVICE_DIR: Path                      # Path(__file__).resolve().parent
ENV_FILE: Path                         # SERVICE_DIR / ".env"
DEFAULT_DATABASE_URL: str              # f"sqlite:///{SERVICE_DIR / 'registry.db'}"
def load_env_file(path: Path = ENV_FILE) -> None          # load_dotenv(path, override=False); called once at import
def get_database_url() -> str                             # DATABASE_URL, or DEFAULT_DATABASE_URL if unset or ""
def open_sqlite(db_path: Path) -> sqlite3.Connection      # today's connect code: mode=rw URI, check_same_thread=False, PRAGMA foreign_keys = ON
def get_engine(url: str) -> Engine                        # cached per URL string, created under a threading.Lock
def dispose_engines() -> None                             # dispose all, empty the cache
```

**`get_engine` rules (§4):**
- Pick the backend with `make_url(url).get_backend_name()`.
- **SQLite:**
  - `db_path = Path(make_url(url).database).resolve()`, computed once.
  - `create_engine("sqlite://", creator=functools.partial(open_sqlite, db_path), poolclass=NullPool)`.
- **PostgreSQL:** `create_engine(url, pool_pre_ping=True)`.
- **Any other backend:** raise `ValueError("Unsupported DATABASE_URL backend: <name>")`.
- Comments explain why `creator=` is used (a missing file stays a 503) and why `NullPool` (JL-002).

- [ ] **Step 2.1: Write `tests/test_db_config.py`**

```python
# Helpers: make_sqlite_file(path) -> path   (sqlite3.connect(path).close(); returns path)
#          connected_file(engine) -> str      (row[2] of "PRAGMA database_list" via engine.connect())

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
    engine = get_engine("postgresql+psycopg://user:pw@127.0.0.1:5433/db")   # create_engine does not connect
    assert isinstance(engine.pool, QueuePool)
    assert engine.pool.size() == 5
    assert engine.pool._pre_ping is True   # private: SQLAlchemy has no public accessor for this setting

def test_each_sqlite_engine_stays_bound_to_its_file(tmp_path, monkeypatch):
    a, b = make_sqlite_file(tmp_path / "a.db"), make_sqlite_file(tmp_path / "b.db")
    engine_a, engine_b = get_engine(f"sqlite:///{a}"), get_engine(f"sqlite:///{b}")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{b}")
    assert connected_file(engine_a) == str(a.resolve())
    assert connected_file(engine_b) == str(b.resolve())

def test_relative_sqlite_path_is_resolved_once(tmp_path, monkeypatch):            # Review Focus 2
    first, second = tmp_path / "first", tmp_path / "second"
    first.mkdir(); second.mkdir()
    make_sqlite_file(first / "registry.db"); make_sqlite_file(second / "registry.db")
    monkeypatch.chdir(first)
    engine = get_engine("sqlite:///registry.db")
    monkeypatch.chdir(second)
    assert connected_file(engine) == str((first / "registry.db").resolve())

def test_percent_encoded_password_is_decoded():                                   # Review Focus 4
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

def test_empty_database_url_uses_default(monkeypatch):                           # Review Focus 3
    monkeypatch.setenv("DATABASE_URL", "")
    assert get_database_url() == DEFAULT_DATABASE_URL
```

  - Add an autouse fixture **local to this file** that calls `dispose_engines()` after each test. `conftest.py` does not do this until Task 4.
  - Add a fixture `unset_database_url(monkeypatch)` that calls `monkeypatch.setenv("DATABASE_URL", "unused")` and then `monkeypatch.delenv("DATABASE_URL")`.
    - `delenv` on a variable that is not set records nothing. Anything `load_env_file` writes later would then leak into the following tests.
    - `setenv` first records "was not set", so teardown removes whatever `load_env_file` wrote.

- [ ] **Step 2.2: Implement the interfaces above in `db.py`.** Keep `get_db_path`, `get_db`, `is_unavailable`, and `DbConnection` unchanged for now.

- [ ] **Checkpoint 2.3 (you run)**
  - **Command:** `uv run pytest tests/test_db_config.py -v`
  - **Effect:** none. The tests create SQLite files only under pytest's temporary directories.
  - **Expected:** `12 passed`. Nothing calls the new code yet, so the other tests cannot be affected.
  - **Send back:** the last line, plus any failure output.

- [ ] **Step 2.4: Commit** `db.py` and `tests/test_db_config.py`. Message: `feat: add DATABASE_URL configuration and per-URL engines`

---

### Task 3: PostgreSQL and constraint classifiers (pure functions)

**Files:**
- Modify: `db.py`
- Modify: `tests/test_database_errors.py` (add tests only)

**Interfaces (Produces):**

```python
POSTGRES_UNAVAILABLE_SQLSTATES: tuple[str, ...]          # exact tuple and comments from spec §6
def is_postgres_unavailable(orig: psycopg.Error) -> bool  # spec §6 body: check sqlstate first, then the class only when sqlstate is None
def violated_constraint(exc: sqlalchemy.exc.IntegrityError) -> str | None   # spec §6 body: "unique" | "foreign_key" | None
```

Both functions get docstrings. The comment on `is_postgres_unavailable` explains why the SQLSTATE is checked before the class: `3D000` is a `ProgrammingError`.

- [ ] **Step 3.1: Add the tests**

```python
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

# integrity_error(orig) -> sqlalchemy.exc.IntegrityError("stmt", {}, orig)
# sqlite_error(cls, name) -> cls("test") with .sqlite_errorname = name
@pytest.mark.parametrize(("orig", "expected"), [
    (sqlite_error(sqlite3.IntegrityError, "SQLITE_CONSTRAINT_UNIQUE"), "unique"),
    (sqlite_error(sqlite3.IntegrityError, "SQLITE_CONSTRAINT_FOREIGNKEY"), "foreign_key"),
    (sqlite_error(sqlite3.IntegrityError, "SQLITE_CONSTRAINT_NOTNULL"), None),
    (psycopg.errors.lookup("23505")("test"), "unique"),
    (psycopg.errors.lookup("23503")("test"), "foreign_key"),
    (psycopg.errors.lookup("23502")("test"), None),
])
def test_violated_constraint(orig, expected):
    assert violated_constraint(integrity_error(orig)) == expected
```

- [ ] **Step 3.2: Implement** both functions and the tuple in `db.py`, copied from spec §6.

- [ ] **Checkpoint 3.3 (you run)**
  - **Command:** `uv run pytest tests/test_database_errors.py -q`
  - **Expected:** all pass: the existing tests in that file + 21 new.
  - **Send back:** the last line.

- [ ] **Step 3.4: Commit** `db.py` and `tests/test_database_errors.py`. Message: `feat: classify PostgreSQL errors and constraint violations`

---

### Task 4: Switch the request path to SQLAlchemy (SQLite)

This is the central change, and it is all or nothing. Until every step through 4.9 is written, the suite cannot pass.

**Safety:** do not run the full suite, or any test that uses `client`, `seeded_db`, or `live_server`, before Step 4.9. On a half-switched tree, an old `get_db` would read the default path, and a write test could change the real `registry.db` (Review Focus 1).

**Files:**
- Modify: `db.py`, `main.py`
- Modify: `repositories/farms.py`, `repositories/plots.py`, `repositories/catalogues.py`
- Modify: `routers/farms.py`, `routers/plots.py`, `routers/catalogues.py`
- Modify: `tests/conftest.py`, `tests/test_database_errors.py`
- Modify: `pyproject.toml` (markers only)
- Modify: `scripts/measure_p95.py` (one line)

**Interfaces:**
- Consumes: Task 2 (`get_engine`, `get_database_url`, `dispose_engines`) and Task 3 (`is_postgres_unavailable`, `violated_constraint`).
- Produces:

```python
# db.py
SQLITE_UNAVAILABLE_ERROR_NAMES: tuple[str, ...]           # renamed from UNAVAILABLE_ERROR_NAMES; contents unchanged
def get_db() -> Iterator[Connection]                      # spec §4 body: `with engine.begin() as conn: yield conn`
DbConnection = Annotated[Connection, Depends(get_db, scope="function")]
def is_unavailable(exc: SQLAlchemyError) -> bool          # spec §6 body
# removed: DEFAULT_DB_PATH, get_db_path, the old get_db

# tests/conftest.py
BACKEND: str                         # "postgresql" if TEST_DATABASE_URL is set, else "sqlite"
def assert_unavailable(response) -> None                  # moved here from test_database_errors.py
@pytest.fixture(autouse=True) isolated_environment(tmp_path, monkeypatch) -> str   # sets DATABASE_URL=sqlite:///<tmp>/registry.db; teardown dispose_engines()
@pytest.fixture sqlite_db_path(tmp_path) -> Path          # tmp_path / "registry.db"
@pytest.fixture database_url(isolated_environment) -> str # SQLite: returns isolated_environment (the PostgreSQL branch comes in Task 8)
@pytest.fixture seeded_db(database_url) -> str            # SQLite: seed_database(Path(make_url(url).database)); returns the URL
@pytest.fixture client(seeded_db) -> TestClient           # unchanged body
@pytest.fixture live_server(seeded_db)                    # env={**os.environ, "DATABASE_URL": seeded_db}
def pytest_collection_modifyitems(config, items)          # skips postgres_only when BACKEND == "sqlite", and sqlite_only when "postgresql"
```

`pyproject.toml` gets this under `[tool.pytest.ini_options]`:

```toml
markers = ["sqlite_only: needs the SQLite backend", "postgres_only: needs TEST_DATABASE_URL"]
```

**Mechanical rules for repositories (spec §5):**
- Replace `?` with `:name`, wrap every statement in `text()`, and pass parameters as a dict.
- Use `result.mappings()` and `.mappings().first()`.
- Remove every `with conn:`.
- Use `result.rowcount == 1`.
- Change the type hints to `sqlalchemy.Connection`.
- Keep the SQL strings and `UPDATABLE_COLUMNS` otherwise unchanged.

**Routers:**
- `routers/farms.py` `delete_farm` and `routers/plots.py` both catch `sqlalchemy.exc.IntegrityError`.
- They branch on `violated_constraint(exc)`, mapping to the same responses as §6.
- Any other value re-raises.
- Remove `import sqlite3`.

**`main.py`:**
- `@app.exception_handler(SQLAlchemyError)`, with the same body.
- Remove `import sqlite3`.

**`scripts/measure_p95.py`:**
- `env={**os.environ, "DATABASE_URL": f"sqlite:///{db_path}"}`.
- Nothing else changes in this task.

- [ ] **Step 4.1: Write the test changes** in `tests/test_database_errors.py` and `tests/conftest.py`.
  - Mark these `@pytest.mark.sqlite_only` and switch them to `sqlite_db_path`:
    - `test_missing_database_file_returns_503`
    - `test_corrupt_database_file_returns_503`
    - `test_reseeding_recovers_without_restart`
    - `test_unseeded_empty_file_returns_500`
  - `test_sql_bug_returns_500_not_503`: the broken query becomes `conn.execute(text("SELEC id FROM crops")).all()`. Without `text()`, the test would hit a different error than the SQL bug it means to test.
  - `test_is_unavailable_classification`: wrap each `sqlite3` error in `DBAPIError(None, None, orig)`. Add these cases:

```python
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

def test_autouse_fixture_points_at_temporary_database(tmp_path):            # Review Focus 1
    assert get_database_url() == f"sqlite:///{tmp_path / 'registry.db'}"
```

- [ ] **Step 4.2:** Change `db.py` as listed under Interfaces. The comment above `DbConnection` explains `scope="function"`: without it, a failed commit still sends 201 (JL-008).
- [ ] **Step 4.3:** `main.py` handler.
- [ ] **Step 4.4:** `repositories/catalogues.py`.
- [ ] **Step 4.5:** `repositories/farms.py`.
- [ ] **Step 4.6:** `repositories/plots.py`.
- [ ] **Step 4.7:** The three routers.
- [ ] **Step 4.8:** The markers in `pyproject.toml`, and the environment line in `measure_p95.py`.
- [ ] **Step 4.9: Read-only check by the implementer.** These searches must return nothing:
  - `grep -rn "REGISTRY_DB_PATH\|sqlite3.Row\|with conn:\|get_db_path" --include=*.py .`
  - `grep -n "import sqlite3" main.py routers/ repositories/`

  `db.py` and the tests may still import `sqlite3`. Report the result.

- [ ] **Checkpoint 4.10 (you run)**
  - **Command:** `uv run pytest -q`
  - **Effect:** none. Every test uses a temporary database.
  - **Expected:** all pass, 0 failed. No tests are skipped, because no test carries `postgres_only` yet. The count is Task 3's count + 5 new tests + the cases added to `test_is_unavailable_classification`; the implementer states the exact number before you run it.
  - **Send back:** the last line, plus any failure output in full.

- [ ] **Checkpoint 4.11 (you run): the real app on SQLite**
  - **Command:**
    - Terminal 1: `uv run uvicorn main:app --host 127.0.0.1 --port 8000`
    - Terminal 2: `curl -s -i http://127.0.0.1:8000/health` and `curl -s -i http://127.0.0.1:8000/v1/crops`
  - **First:** `bash seed_registry.sh`. It **deletes and recreates** the local `registry.db`, which holds only demo data, so the check starts from a known state. `seed_registry.sh` itself is not changed.
  - **Effect:** the server reads the local `registry.db`.
  - **Expected:** `HTTP/1.1 200 OK` and `{"status":"ok"}` for health; `200` and a two-crop list for crops.
  - **Send back:** both status lines and bodies. Stop the server with Ctrl+C.

- [ ] **Step 4.12: Commit** the files listed in this task. Message: `feat: serve requests through SQLAlchemy with one transaction per request`

---

### Task 5: Reject NUL characters (JL-009)

**Files:**
- Modify: `schemas.py`, `routers/catalogues.py`
- Create: `tests/test_nul_input.py`

**Interfaces (Produces):**
- `reject_nul(value: str) -> str` (the docstring is in §7).
- `NoNulStr = Annotated[str, AfterValidator(reject_nul)]`.
- `Name = Annotated[str, Field(min_length=1), AfterValidator(reject_nul)]`.
- `PlotCreate` and `PlotUpdate` use `crop_id`, `soil_id`, and `emitter_id` as `NoNulStr` (with the `= None` default in `PlotUpdate`).
- `routers/catalogues.py` uses path parameters `crop_id: NoNulStr`, `soil_id: NoNulStr`, and `emitter_id: NoNulStr`.

- [ ] **Step 5.1: Write `tests/test_nul_input.py`**

```python
NUL = "a\x00b"
# Reuse DEMO_FARM_ID, NORTH_BLOCK_ID, SPEC_EXAMPLE by importing from test_plots.

def assert_nul_rejected(response):
    assert response.status_code == 422
    assert "must not contain NUL characters" in response.json()["detail"][0]["msg"]

@pytest.mark.parametrize(("method", "path"), [("POST", "/v1/farms"), ("PATCH", f"/v1/farms/{DEMO_FARM_ID}")])
def test_nul_in_farm_name(client, method, path):
    assert_nul_rejected(client.request(method, path, json={"name": NUL}))

@pytest.mark.parametrize("field", ["name", "crop_id", "soil_id", "emitter_id"])
def test_nul_in_plot_create(client, field):
    assert_nul_rejected(client.post("/v1/plots", json={**SPEC_EXAMPLE, field: NUL}))

@pytest.mark.parametrize("field", ["name", "crop_id", "soil_id", "emitter_id"])
def test_nul_in_plot_update(client, field):
    assert_nul_rejected(client.patch(f"/v1/plots/{NORTH_BLOCK_ID}", json={field: NUL}))

@pytest.mark.parametrize("path", ["/v1/crops/a%00b", "/v1/soils/a%00b", "/v1/emitters/a%00b"])
def test_nul_in_catalogue_path(client, path):
    assert_nul_rejected(client.get(path))
```

- [ ] **Step 5.2: Implement** the interfaces above.

- [ ] **Checkpoint 5.3 (you run)**
  - **Command:** `uv run pytest tests/test_nul_input.py tests/test_plot_models.py tests/test_plots.py tests/test_farms.py tests/test_catalogues.py -q`. These are the tests for every endpoint and model that `schemas.py` and `routers/catalogues.py` touch.
  - **Expected:** all pass. The 3 catalogue-path cases confirm V3, that `AfterValidator` works on a path parameter.
  - **Send back:** the last line.

- [ ] **Step 5.4: Commit** `schemas.py`, `routers/catalogues.py`, and `tests/test_nul_input.py`. Message: `feat: reject NUL characters in string input (JL-009)`

---

### Task 6: Transaction tests (JL-008)

Task 4 already implements the behavior. This task proves it, and then checks that the commit test really detects a missing `scope="function"`.

**Files:** Create `tests/test_transactions.py`.

**Interfaces:**
- Consumes: `get_engine`, `get_database_url`, and `DbConnection` from `db`; `assert_unavailable` from `conftest`.
- Consumes: `farm_repository.create_farm(conn, name) -> dict` and `plot_repository.create_plot(conn, fields) -> dict`.

- [ ] **Step 6.1: Write the tests**

```python
def unavailable_driver_error() -> Exception:
    """A driver error that the classifier treats as 'database unavailable', for the current backend."""
    # SQLite: sqlite3.OperationalError("database is locked") with sqlite_errorname = "SQLITE_BUSY"
    # PostgreSQL: psycopg.errors.lookup("57P01")("terminating connection")

def test_failed_commit_returns_503_not_201(client, monkeypatch):
    """Simulated failure: do_commit raises before COMMIT reaches the database.
    The no-row check covers only this simulated case. A real failed COMMIT can have
    an unknown outcome (spec section 6)."""
    engine = get_engine(get_database_url())          # the same cached engine the app uses
    def failing_commit(dbapi_connection):
        raise unavailable_driver_error()
    # monkeypatch.context(), not monkeypatch.undo(): undo() would also remove the autouse
    # DATABASE_URL override, and the GET below would then read the default database.
    with monkeypatch.context() as patch:
        patch.setattr(engine.dialect, "do_commit", failing_commit)
        assert_unavailable(client.post("/v1/farms", json={"name": "Commit test"}))
    assert "Commit test" not in [farm["name"] for farm in client.get("/v1/farms").json()]

def test_second_write_failure_rolls_back_the_first(seeded_db):
    # A test-only app; no production route is added.
    test_app = FastAPI()
    @test_app.post("/two-writes")
    def two_writes(conn: DbConnection):
        farm = farm_repository.create_farm(conn, "Rollback test")
        plot_repository.create_plot(conn, {**PLOT_FIELDS, "farm_id": farm["id"], "crop_id": "no-such-crop"})
    response = TestClient(test_app, raise_server_exceptions=False).post("/two-writes")
    assert response.status_code == 500                # the foreign-key IntegrityError has no handler in test_app
    names = [farm["name"] for farm in TestClient(app).get("/v1/farms").json()]
    assert "Rollback test" not in names
```

`PLOT_FIELDS` is `SPEC_EXAMPLE` without `farm_id`, with `planting_date` kept as a string.

- [ ] **Checkpoint 6.2 (you run)**
  - **Command:** `uv run pytest tests/test_transactions.py -v`
  - **Expected:** `2 passed`. This confirms V1, and only for the simulated case.
  - **Send back:** the two result lines.

- [ ] **Checkpoint 6.3 (you run): mutation check.** Kept because it is the only evidence that the commit test detects the bug JL-008 describes.
  - **Before:** the implementer temporarily changes `Depends(get_db, scope="function")` to `Depends(get_db)` in `db.py`.
  - **Command:** `uv run pytest tests/test_transactions.py::test_failed_commit_returns_503_not_201 -q`
  - **Expected:** `1 failed`, with `assert 201 == 503`.
  - **After:** the implementer reverts the change and shows that `git diff db.py` is empty. Since the file is back to the version that passed in 6.2, no rerun is needed.
  - **Send back:** the assertion line.

- [ ] **Step 6.4: Commit** `tests/test_transactions.py`. Message: `test: cover failed commit and multi-write rollback`

---

### Task 7: PostgreSQL setup script

**Files:**
- Create: `scripts/setup_postgres.py`, `tests/test_setup_postgres.py`
- Modify: `tests/test_plots.py` (one test)

**Run form (deviation from spec §8):**
- The script imports `db`. With `uv run python scripts/setup_postgres.py`, Python puts `scripts/` on `sys.path`, not the service directory, so `import db` fails.
- **Chosen fix:** run it as `uv run python -m scripts.setup_postgres [--demo]`. That adds the current directory to `sys.path`, with no path manipulation in code.
- The README and the docstring use this form.

**Interfaces (Produces):**

```python
CREATE_SCHEMA_SQL: list[str]            # the five CREATE TABLE IF NOT EXISTS statements, exactly as in spec §8
def create_schema(conn: Connection) -> None
def insert_catalogues(conn: Connection) -> None      # 2 crops, 3 soils, 4 emitters copied from seed_registry.sh; ON CONFLICT DO NOTHING
def insert_demo_data(conn: Connection) -> None       # 2 farms, 4 plots copied from seed_registry.sh; ON CONFLICT DO NOTHING
def main(argv: list[str] | None = None) -> int       # argparse: --demo; returns 0 on success, 1 on a non-PostgreSQL URL
```

**`main` behavior (§8), in order:**
1. `url = db.get_database_url()`. If the backend is not `postgresql`: print `setup_postgres only works with a PostgreSQL DATABASE_URL.` to stderr and return 1. Nothing connects.
2. Print `Target: <url with the password hidden>`.
3. With `--demo`, print the exact warning from §8.
4. In one `db.get_engine(url).begin()`: `create_schema`, then `insert_catalogues`, then `insert_demo_data` if `--demo`.
5. Print counts read back from the database: `Catalogues: N crops, N soils, N emitters. Demo data: skipped.`, or `... Demo data: N farms, N plots.` with `--demo`.

**Also required:**
- The module docstring and the argparse description say "Initial schema setup only. Not a migration tool."
- Comments explain `DOUBLE PRECISION` and `planting_date TEXT`.
- No `DROP`, `DELETE`, or `TRUNCATE`.

- [ ] **Step 7.1: Write the tests**

```python
# tests/test_setup_postgres.py
def test_refuses_sqlite_url(capsys, sqlite_db_path):
    assert main([]) == 1
    assert "PostgreSQL" in capsys.readouterr().err
    assert not sqlite_db_path.exists()

# tests/test_plots.py
def test_high_precision_coordinates_round_trip(client):
    created = client.post("/v1/plots", json={**SPEC_EXAMPLE, "name": "Precise block", "lat": 31.2512345, "lon": 34.7912345678})
    assert created.status_code == 201
    stored = client.get(f"/v1/plots/{created.json()['id']}").json()
    assert (stored["lat"], stored["lon"]) == (31.2512345, 34.7912345678)
```

`test_refuses_sqlite_url` runs on both backends: the autouse fixture always points `DATABASE_URL` at SQLite. On SQLite, the precision test passes from the start. It exists to catch `REAL` rounding on PostgreSQL in Task 8.

- [ ] **Step 7.2: Implement** `scripts/setup_postgres.py`. The implementer reads `seed_registry.sh` and copies every catalogue and demo value exactly.

- [ ] **Checkpoint 7.3 (you run)**
  - **Command:** `uv run pytest tests/test_setup_postgres.py tests/test_plots.py -q`, then `DATABASE_URL="sqlite:///$PWD/registry.db" uv run python -m scripts.setup_postgres; echo "exit=$?"`
  - **Effect:** none. The SQLite URL is forced explicitly, so the result does not depend on `.env`. The script refuses before it connects, so `registry.db` is not opened.
  - **Expected:**
    - All tests pass.
    - The script prints `setup_postgres only works with a PostgreSQL DATABASE_URL.`, then `exit=1`.
  - **Send back:** the last pytest line and the two script lines.

- [ ] **Step 7.4: Commit** `scripts/setup_postgres.py`, `tests/test_setup_postgres.py`, and `tests/test_plots.py`. Message: `feat: add PostgreSQL initial setup script`

---

### Task 8: PostgreSQL test fixtures and PostgreSQL-only tests

**Files:**
- Modify: `tests/conftest.py`, `tests/test_database_errors.py`
- Create: `tests/test_postgres_only.py`

**Interfaces (Produces, in `conftest.py`):**

```python
TEST_DATABASE_URL: str | None                       # os.environ.get("TEST_DATABASE_URL"), read after `from main import app`
def pytest_sessionstart(session)                    # localhost guard (§9): host must be "localhost" or "127.0.0.1", else
                                                    # pytest.exit(f"TEST_DATABASE_URL must point to localhost, got {hidden}", returncode=2)
@pytest.fixture(scope="session") admin_engine()     # create_engine(TEST_DATABASE_URL, isolation_level="AUTOCOMMIT", poolclass=NullPool);
                                                    # comment: CREATE/DROP DATABASE cannot run inside a transaction; dispose at session end
@pytest.fixture postgres_admin_url() -> str         # TEST_DATABASE_URL
@pytest.fixture database_url(isolated_environment, request, monkeypatch) -> str
    # SQLite: unchanged.
    # PostgreSQL: name = f"agropilot_test_{uuid4().hex}"; CREATE DATABASE "<name>" via admin_engine
    #   (request.getfixturevalue("admin_engine")); url = make_url(TEST_DATABASE_URL).set(database=name)
    #   .render_as_string(hide_password=False); setenv DATABASE_URL; yield url;
    #   teardown: dispose_engines(); assert name.startswith("agropilot_test_");
    #   DROP DATABASE IF EXISTS "<name>" WITH (FORCE). Drops only the name held in this local variable.
@pytest.fixture seeded_db(database_url) -> str
    # PostgreSQL: with get_engine(url).begin() as conn: create_schema, insert_catalogues, insert_demo_data
```

**`tests/test_postgres_only.py`:** module-level `pytestmark = pytest.mark.postgres_only`.

```python
def test_wrong_password_returns_503_without_logging_password(postgres_admin_url, monkeypatch, caplog):
    bad = make_url(postgres_admin_url).set(password="wrong-password-7f3a").render_as_string(hide_password=False)
    monkeypatch.setenv("DATABASE_URL", bad)
    assert_unavailable(TestClient(app).get("/v1/crops"))
    assert "Database unavailable" in caplog.text                        # the warning was logged...
    assert "wrong-password-7f3a" not in caplog.text                     # ...without the password (V7)

def test_missing_database_returns_503(postgres_admin_url, monkeypatch):
    missing = make_url(postgres_admin_url).set(database=f"agropilot_test_missing_{uuid4().hex}")
    monkeypatch.setenv("DATABASE_URL", missing.render_as_string(hide_password=False))
    assert_unavailable(TestClient(app).get("/v1/crops"))                # V2

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
    assert capsys.readouterr().out == first      # the same target and counts: nothing added the second time
    assert len(TestClient(app).get("/v1/plots").json()) == 4

def test_request_succeeds_after_server_closes_connections(client, database_url, admin_engine):   # Review Focus 5
    assert client.get("/v1/crops").status_code == 200        # leaves one pooled connection
    name = make_url(database_url).database
    with admin_engine.connect() as conn:
        conn.execute(text("SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                          "WHERE datname = :name AND pid <> pg_backend_pid()"), {"name": name})
    assert client.get("/v1/crops").status_code == 200        # pool_pre_ping replaces the dead connection
```

**`tests/test_database_errors.py`, which runs on both backends:**

```python
def test_unreachable_postgres_returns_503(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:pw@127.0.0.1:1/db")   # nothing listens on port 1
    assert_unavailable(TestClient(app).get("/v1/crops"))      # its own client: no test database is created
```

- [ ] **Step 8.1: Write** the fixtures and the tests above.

- [ ] **Checkpoint 8.2 (you run): the SQLite suite, then start the test container**
  - **Command:**
    1. `uv run pytest -q`
    2. `docker run --rm -d --name agropilot-test-pg -e POSTGRES_PASSWORD=agropilot-local-test -p 127.0.0.1:5433:5432 postgres:17`
    3. `docker exec agropilot-test-pg pg_isready -U postgres`
  - **Effect:**
    - Step 1 changes nothing.
    - Step 2 downloads `postgres:17` the first time, then starts a container that is removed when it stops (`--rm`). The port is reachable only from this Mac.
  - **Expected:**
    1. All pass, with `6 skipped` (the `postgres_only` tests). `test_unreachable_postgres_returns_503` passes.
    2. A container ID.
    3. `/var/run/postgresql:5432 - accepting connections`. If it says `no response`, wait a few seconds and run it again.
  - **Send back:** the pytest last line and the `pg_isready` line. If step 1 fails, stop there.

- [ ] **Checkpoint 8.3 (you run): the full suite on PostgreSQL, leftover check, localhost guard**
  - **Command:**
    1. `time TEST_DATABASE_URL='postgresql+psycopg://postgres:agropilot-local-test@127.0.0.1:5433/postgres' uv run pytest -q`
    2. `docker exec agropilot-test-pg psql -U postgres -Atc "SELECT count(*) FROM pg_database WHERE datname LIKE 'agropilot_test_%'"`
    3. `TEST_DATABASE_URL='postgresql+psycopg://postgres:agropilot-local-test@example.com:5433/postgres' uv run pytest -q`
  - **Effect:**
    1. Creates one `agropilot_test_<hex>` database for each test that needs one, and drops each after its test. `TEST_DATABASE_URL` is set for this one command only.
    2. Read-only.
    3. None. The run stops before any test connects.
  - **Expected:**
    1. All pass, with `4 skipped` (the `sqlite_only` tests). The `real` time is V5. A first run may expose real backend differences. If so, **stop**: the implementer debugs before changing anything.
    2. `0`, meaning no leftover databases (V8).
    3. `TEST_DATABASE_URL must point to localhost, got postgresql+psycopg://postgres:***@example.com:5433/postgres`. The password does not appear.
  - **Send back:** the last pytest line and `real` time, the number, and the guard line. Send any failure in full.

- [ ] **Step 8.4: Commit** `tests/conftest.py`, `tests/test_database_errors.py`, and `tests/test_postgres_only.py`. Message: `test: run the suite on PostgreSQL with isolated per-test databases`

Keep the container running for Task 9.

---

### Task 9: Benchmark on both databases

**Files:**
- Modify: `scripts/measure_p95.py`, `tests/test_measure_p95.py`

**Interfaces (Produces):**

```python
@contextmanager
def benchmark_database(database_url: str | None) -> Iterator[str]
    # None: a temporary directory, seed_registry.sh into <tmp>/registry.db, yield f"sqlite:///<tmp>/registry.db"; removed afterwards.
    # Otherwise: yield database_url unchanged; never writes to it.
```

**`main()` changes:**
- Add the option `--database-url`, with help text: `benchmark an existing database that already has the demo data (default: a temporary seeded SQLite file)`.
- Print `Target: <hidden-password URL>`.
- Pass `DATABASE_URL` explicitly to the server subprocess.
- The measuring and reporting functions do not change (§10).

- [ ] **Step 9.1: Write the tests**

```python
def test_default_benchmark_database_is_a_seeded_temporary_sqlite_file():
    with benchmark_database(None) as url:
        path = Path(make_url(url).database)
        assert url.startswith("sqlite:///") and path.exists()
    assert not path.exists()

def test_given_database_url_is_used_unchanged():
    given = "postgresql+psycopg://user:pw@127.0.0.1:5433/agropilot_bench"
    with benchmark_database(given) as url:
        assert url == given
```

- [ ] **Step 9.2: Implement.**

- [ ] **Checkpoint 9.3 (you run): benchmark tests, then the SQLite benchmark** (about 2 minutes)
  - **Command:** `uv run pytest tests/test_measure_p95.py -q && uv run python scripts/measure_p95.py`
  - **Effect:** the benchmark uses a temporary database and server, both removed afterwards.
  - **Expected:**
    - All pass.
    - `Target: sqlite:///...`, a table with 11 routes, `Non-200 responses: 0 of 1200`, then `... PASS`.
  - **Send back:** the pytest last line, the table, and the last two lines.

- [ ] **Checkpoint 9.4 (you run): the PostgreSQL benchmark, then stop the container** (about 2 minutes)
  - **Command:**
    1. `docker exec agropilot-test-pg createdb -U postgres agropilot_bench`
    2. `DATABASE_URL='postgresql+psycopg://postgres:agropilot-local-test@127.0.0.1:5433/agropilot_bench' uv run python -m scripts.setup_postgres --demo`
    3. `uv run python scripts/measure_p95.py --database-url 'postgresql+psycopg://postgres:agropilot-local-test@127.0.0.1:5433/agropilot_bench'`
    4. `docker stop agropilot-test-pg`
  - **Effect:**
    - Steps 1–2 create the database `agropilot_bench` inside the throwaway container, with schema, catalogues, and demo data.
    - Step 3 sends GET requests only.
    - Step 4 stops the container. `--rm` deletes it and all its data, including `agropilot_bench`.
  - **Expected:**
    2. `Target: postgresql+psycopg://postgres:***@127.0.0.1:5433/agropilot_bench`, the `--demo` warning, and `Catalogues: 2 crops, 3 soils, 4 emitters. Demo data: 2 farms, 4 plots.`
    3. `Target: ...***...`, the table, and `Non-200 responses: 0 of 1200`. PASS or FAIL is reported either way (§10).
    4. `agropilot-test-pg`.
  - **Send back:** the three setup lines, the table, and the benchmark's last two lines. If step 2 fails, stop before step 3.

- [ ] **Step 9.5: Implementer report.** The report gives:
  - both p95 results, and whether each meets 100 ms;
  - a comparison per endpoint.

  A meaningful regression (PostgreSQL above 100 ms, or far above SQLite on one endpoint) is flagged with a proposed investigation. You decide what to do.

- [ ] **Step 9.6: Commit** `scripts/measure_p95.py` and `tests/test_measure_p95.py`. Message: `feat: benchmark an existing database with --database-url`

---

### Task 10: Documentation and the manual smoke test

**Files:**
- Create: `.env.example`, with the exact content of §11, plus one line: `# Percent-encode special characters in the password, e.g. @ -> %40, / -> %2F.`
- Modify: `README.md`
  - Replace the `REGISTRY_DB_PATH` rows and the example at lines 54-62.
  - Replace the test paragraph at line 71.
  - Add the sections from §11: Configuration, PostgreSQL setup (with the `python -m scripts.setup_postgres` form), PostgreSQL tests (with the throwaway-password statement), Benchmark, and Smoke test.
  - The smoke test uses the container `agropilot-smoke-pg` on `127.0.0.1:5434`, so it cannot clash with the test container.
- Modify: `CLAUDE.md` (repository root), as in §11.
  - Also replace "Each test seeds a temporary database through `REGISTRY_DB_PATH`".
  - Also update "a FastAPI app on one SQLite file".

- [ ] **Step 10.1: Write** the three files. The implementer runs the read-only check `grep -rn "REGISTRY_DB_PATH" --exclude-dir=.venv --exclude-dir=docs .` from the repository root. It must print nothing; `docs/` keeps its P1 snapshot.

- [ ] **Step 10.2: Review together.** You read the README sections. The implementer explains any line on request.

- [ ] **Checkpoint 10.3 (you run): the smoke test**, following the new README exactly:
  1. `docker run -d --name agropilot-smoke-pg -e POSTGRES_PASSWORD=agropilot-local-test -p 127.0.0.1:5434:5432 postgres:17`
  2. `cp .env.example .env`. Then edit `.env` and add `DATABASE_URL=postgresql+psycopg://postgres:agropilot-local-test@127.0.0.1:5434/postgres`.
  3. `uv run python -m scripts.setup_postgres --demo`
  4. `uv run uvicorn main:app --host 127.0.0.1 --port 8000`, then in a second terminal:
     - `curl -s http://127.0.0.1:8000/v1/farms` returns 2 farms.
     - A duplicate plot `POST` returns `409`.
     - `curl -s -i -X DELETE http://127.0.0.1:8000/v1/farms/b7e2c0a0-3c1d-4f0a-9a11-0c5d2e6f1001` returns `409`.
  5. `docker stop agropilot-smoke-pg`; then `curl -s -i http://127.0.0.1:8000/v1/farms` returns `503` and `retry-after: 5`.
  6. `docker start agropilot-smoke-pg`; wait about 3 s; then `curl -s -i http://127.0.0.1:8000/v1/farms` returns `200`, with no app restart.

  7. Clean up: stop the server (Ctrl+C), then `docker rm -f agropilot-smoke-pg`, then remove the `DATABASE_URL` line from `.env`, or delete `.env`.

  - **Effect:**
    - Steps 1–6 create a container and a local `.env`, which git ignores.
    - Step 7 deletes the container and its data. Without the `.env` line, the local app goes back to `registry.db`. Tests are unaffected either way, because the autouse fixture overrides `DATABASE_URL`.
  - **Send back:** each status line, and the `docker rm` output (`agropilot-smoke-pg`).

- [ ] **Step 10.4: Commit** `.env.example`, `README.md`, and `CLAUDE.md`. The secrets review must show `.env` as ignored and not staged. Message: `docs: document DATABASE_URL, PostgreSQL setup, tests, and benchmark`

---

### Task 11: Final verification and follow-ups

- [ ] **Checkpoint 11.1 (you run)**
  - **Command:** `uv lock --check && uv run pytest -q`
  - **Expected:** both pass.

- [ ] **Checkpoint 11.2 (you run)**
  - **Command:** start `agropilot-test-pg` as in Checkpoint 8.2 steps 2–3, run the PostgreSQL suite and the leftover check as in Checkpoint 8.3 steps 1–2, then `docker stop agropilot-test-pg`.
  - **Expected:** all pass, 4 skipped.

- [ ] **Step 11.3: Whole-branch review.** Use `superpowers:requesting-code-review` against the spec, from `4197c7e` to `HEAD`. Report the findings; fix only with your approval.

- [ ] **Step 11.4: Close the V items.** The implementer lists V1–V8 from spec §14, each with the checkpoint that closed it.

- [ ] **Step 11.5: Follow-ups.** These stay open and are not done here:
  - **F1:** the walkthrough.
  - **F2:** the slides and presenter guide.
  - **F3:** the request debugger. Decide, from the source structure in spec §13, between modes in the existing debugger and a separate presentation. Do not rebuild `request-debugger.html` before that decision.
  - **F4:** a pool-tuning benchmark with a concurrent-load mode.
  - **F5:** secrets management.
  - **F6:** a migration tool.

- [ ] **Step 11.6:** Pushing and opening a PR need a separate approval: `superpowers:finishing-a-development-branch`. The implementer does not push.

---

## Progress and rulings (implementer's record)

- Task 0: complete. The user ran 0.1 and 0.2; all passed.
- Task 1: complete. Commit `baf7900`. Locked: fastapi 0.162.0, sqlalchemy 2.1.8, psycopg and psycopg-binary 3.3.9, python-dotenv 1.2.4. No psycopg2.
- Ruling (plan): the user asked for risk-based checkpoints, so separate expected-failure runs were removed. User instructions override the TDD skill's watch-it-fail step. Cost if wrong: a test that passes for the wrong reason goes unnoticed until review. Mitigation: the Task 6 mutation check is kept.
- Task 2: Ruling: the plan used `monkeypatch.delenv(..., raising=False)` to isolate tests that call `load_env_file`. Confirmed in pytest 9.2 `delitem`: when the variable is not set, `delenv` records nothing, so `load_env_file`'s write would leak into later tests. Replaced with the `unset_database_url` fixture (setenv, then delenv). Cost if wrong: none; it is strictly safer.
- Task 2: Ruling: `open_sqlite` drops `row_factory = sqlite3.Row`, because SQLAlchemy builds the rows and `.mappings()` replaces it. It closes the connection if the PRAGMA fails; today's `get_db` closed it in `finally`. Cost if wrong: none for behavior.
- Task 2: Ruling: engine construction lives in a private helper, `_create_engine`, so the lock block stays short. It is not part of any interface.
- Task 2: complete. Commit `9ce595a`; `tests/test_db_config.py` → 12 passed. The user then authorized Claude to run every command and commit; no push.
- Task 3: complete. Commit `7e56bca`; `tests/test_database_errors.py` → 34 passed.
- Task 4: complete. Commit `c41986c`; full suite 209 passed; the real `registry.db` checksum was unchanged by the run. Live app: `/health` 200, `/v1/crops` 200, POST farm 201 persisted. The demo database was reseeded afterwards.
- Task 4: Ruling: `test_autouse_fixture_points_at_temporary_database` lives in `test_db_config.py` (configuration), not `test_database_errors.py`. Cost if wrong: none.
- Task 5: complete. Commit `bd0a180`; the affected test files → 166 passed.
- Task 5: Ruling: the `Plot` response model keeps `str` for the catalogue IDs. Only the input models and path parameters use `NoNulStr`, as in spec §7. Cost if wrong: none.
- Task 6: complete. Commit on this line's HEAD; 2 passed. Mutation check: without `scope="function"`, the test fails because `TestClient` re-raises the commit error after the response. With `raise_server_exceptions=False`, it shows `assert 201 == 503`. `db.py` was reverted with no diff.
- Task 6: commit `fec0bb1`.
- Task 7: complete. Commit `ca0fec7`; 42 passed. With `DATABASE_URL` forced to SQLite, the script refuses with `exit=1`, and the `registry.db` checksum is unchanged.
- Task 8: Ruling: port 5433 is taken by `pg16-rehearsal`, another project's PostgreSQL 16 container, which was left untouched. The test container uses `127.0.0.1:5435` instead, and the README and CLAUDE.md say so; the smoke test stays on 5434. Spec §11 still says 5433. Cost if wrong: one port number in the docs. Risk avoided: test fixtures pointed at another project's server.
- Task 8: complete. Commit `b21b4c5`. SQLite: 227 passed, 6 skipped. PostgreSQL: 229 passed, 4 skipped in 7 s (V5). Leftover databases: 0 (V8). Localhost guard: exit 2, password hidden.
- Task 9: complete. Commit `9c92fc4`. SQLite p95 10.45 ms, PASS. PostgreSQL p95 18.70 ms, PASS: every endpoint is about 8 ms above SQLite, a uniform gap that fits the Docker VM hop; no regression to flag.
- Task 9: Ruling: the test container stayed running until Task 11 instead of stopping at 9.4, to avoid an extra restart. Cost if wrong: none.
- Task 10: complete. Commit `af9f6b8`. The smoke test passed every step: 2 farms, 409 and 409, 503 with retry-after 5, 200 after the restart. The container and `.env` were removed. The logged warning has no password (V7).
- Task 11: `uv lock --check` OK. SQLite: 229 passed, 6 skipped. PostgreSQL: 231 passed, 4 skipped; leftover 0. The test container is stopped.
- Final review: a fresh reviewer on Opus found 0 Critical, 2 Important, and 5 Minor issues. It judged every plan ruling sound.
- Final: fixed: an unencoded `@` in the password leaked the rest of the password into logs and printed targets. Fix: `parse_database_url`, used in `_create_engine` and `setup_postgres`. Tests `test_unencoded_at_in_password_is_rejected_without_echoing_it` and `test_unencoded_at_in_password_is_refused_before_printing` went RED→GREEN. SQLite: 231 passed, 6 skipped. PostgreSQL: 233 passed, 4 skipped. Leftover databases: 0.
- Final: Ruling: `measure_p95.py --database-url` gets no `@` check. The URL is typed by the operator on their own command line, so printing it adds no exposure, and importing `db` would load `.env` into the benchmark process. Cost if wrong: the tail of a mistyped password is echoed to the operator's own terminal.
- Final: Ruling: the review's Important #2 is not fixed. An exported empty `DATABASE_URL` overrides `.env` and falls back to SQLite, exactly as spec §4 says ("unset or empty → default"). Changing that rule changes the approved spec, so it goes to the user as a decision. Cost if wrong: a misconfigured production host silently uses the local SQLite file, or returns 503 for everything.
- Final: minor (deferred): the 503 warning now logs SQL and bound parameters (user data, not credentials); fix with `hide_parameters=True`.
- Final: minor (deferred): there is no PostgreSQL `connect_timeout`, so a host that drops packets makes connects hang for the OS TCP timeout; fix with `connect_args={"connect_timeout": 5}`.
- Final: minor (deferred): `conftest.py` reads `TEST_DATABASE_URL` after `.env` is loaded, and its comment endorses that, contrary to "never in .env".
- Final: minor (deferred): a misconfigured URL fails only at the first request; startup still succeeds.
- Final: minor (deferred): spec §8 (`python scripts/...`) and §11 (port 5433) are out of date compared with the implementation (`-m` and 5435).
