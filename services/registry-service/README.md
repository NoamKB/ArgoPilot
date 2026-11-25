# registry-service

## 1. What is this service?

The AgroPilot registry stores farms and their plots, and serves read-only lists (catalogues) of crops, soils, and drip emitters. It is a FastAPI web API. It keeps its data in a SQLite file, `registry.db`, on a developer's machine, and in PostgreSQL in production (added in P2).

`planner-service` reads a plot, its soil and its emitter from here, and the `frontend` reads the farms and plots. To run the whole system, see the [root README](../../README.md#run-the-whole-system-locally).

| Data | Routes |
| --- | --- |
| Farms | `POST`, `GET` `/v1/farms`, `GET`, `PATCH`, `DELETE` `/v1/farms/{id}`, and `GET` `/v1/farms/{id}/area` (total area of the farm's plots) |
| Plots | `POST`, `GET` `/v1/plots` (optional `?farm_id=`) and `GET`, `PATCH`, `DELETE` `/v1/plots/{id}` |
| Catalogues | `GET` `/v1/crops`, `/v1/soils`, `/v1/emitters`, each with `/{id}` |

Errors use FastAPI's default format, for example `{"detail": "Plot not found"}`.

## 2. Prerequisites

| Tool | Needed for | Check |
| --- | --- | --- |
| [uv](https://docs.astral.sh/uv/) | everything | `uv --version` |
| `sqlite3` command-line tool | creating the SQLite database, and the tests | `sqlite3 --version` (preinstalled on macOS) |
| `curl` | the checks in this guide | `curl --version` |
| Docker | PostgreSQL only: production, PostgreSQL tests, PostgreSQL benchmark | `docker info` |

Python 3.12 is pinned in this folder's `.python-version`. uv uses it (uv ignores the `.python-version` at the repository root).

**Run every command from this folder** unless a step says otherwise:

```bash
cd services/registry-service
```

## 3. Quick Start (SQLite)

### First time

```bash
uv sync
bash seed_registry.sh
```

Expected:

```text
Wrote registry.db
  2 farms, 4 plots, 2 crops, 3 soils, 4 emitters
```

- `uv sync` installs the locked dependencies into `.venv`.
- `seed_registry.sh` creates `registry.db` with demo data. If `registry.db` already exists, it stops and changes nothing:
  `registry.db already exists and was not changed. To delete it and write a fresh one: bash seed_registry.sh --reset registry.db`
- **Warning:** `--reset` permanently deletes `registry.db` and all its data. Before any reset, back up the file: `cp registry.db registry.db.backup` (the backup is git-ignored).

### Every day

```bash
uv run uvicorn main:app --host 127.0.0.1 --port 8000
```

Expected, at the end of the output:

```text
INFO:     Database: sqlite, sqlite:////…/services/registry-service/registry.db
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
```

- The `Database:` line shows which database the service uses. If it shows `postgresql`, your `.env` sets `DATABASE_URL` (see [Configuration](#6-configuration)).
- Stop the service with `Ctrl+C`. The data in `registry.db` stays.

## 4. Verify It Works

With the service running, in a second terminal:

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/v1/farms
curl http://127.0.0.1:8000/v1/emitters/dripnet-pc-1.0
```

Expected, with the demo data:

```text
{"status":"ok"}
[{"id":"b7e2c0a0-3c1d-4f0a-9a11-0c5d2e6f1001","name":"Demo cooperative"},{"id":"a9c1e4b2-6f70-4d8e-a144-3f8b5c904004","name":"East farm"}]
{"id":"dripnet-pc-1.0","name":"DripNet PC","flow_lph":1.0}
```

- `/health` only shows that the service is running. It returns `200` even when the database is down. A data route such as `/v1/farms` shows that the database works.
- In a browser, http://127.0.0.1:8000/docs lists every route and lets you try them.

These two requests change no data. Each returns `409`, because the data they would create or remove conflicts with existing data:

```bash
curl -s -i -X DELETE http://127.0.0.1:8000/v1/farms/b7e2c0a0-3c1d-4f0a-9a11-0c5d2e6f1001
curl -s -i -X POST http://127.0.0.1:8000/v1/plots -H "Content-Type: application/json" -d '{"farm_id": "b7e2c0a0-3c1d-4f0a-9a11-0c5d2e6f1001", "name": "North block", "area_m2": 1000, "crop_id": "tomato", "planting_date": "2026-03-01", "soil_id": "loam", "row_spacing_m": 1.5, "emitter_spacing_m": 0.4, "emitter_id": "dripnet-pc-1.0", "lat": 31.25, "lon": 34.79}'
```

The first is refused because the farm still has plots. The second is refused because the farm already has a plot named "North block".

This request **adds a farm**:

```bash
curl -X POST http://127.0.0.1:8000/v1/farms -H "Content-Type: application/json" -d '{"name": "North farm"}'
```

Expected: `{"id":"<new id>","name":"North farm"}` with status `201`. Request bodies need the `Content-Type: application/json` header; without it, the API returns `422`.

## 5. Run with PostgreSQL

Production is PostgreSQL 17 in the Docker container `agropilot-pg`: database `registry`, port 5436, data in the Docker volume `agropilot-pg-data`. It is separate from the throwaway container the tests use (`agropilot-test-pg`, port 5435).

### First time (once per machine)

Prerequisite: Docker is running, and the container does not exist yet. `docker ps -a --filter name=agropilot-pg` must list no container. If it lists one, skip to [Every day](#every-day-1). Never create it a second time.

1. Create the container. `read -rs` asks for a password without showing it or saving it in your shell history. Use letters and digits, so it needs no encoding:
   ```bash
   read -rs PG_PASSWORD
   docker run -d --name agropilot-pg -e POSTGRES_PASSWORD="$PG_PASSWORD" -e POSTGRES_DB=registry -v agropilot-pg-data:/var/lib/postgresql/data -p 127.0.0.1:5436:5432 postgres:17
   unset PG_PASSWORD
   ```
2. Wait until it is ready. Repeat until it prints `accepting connections`:
   ```bash
   docker exec agropilot-pg pg_isready -U postgres
   ```
3. Point the service at it. If `.env` does not exist yet, create it with `cp .env.example .env` (this overwrites an existing `.env`, so check first). In `.env`, remove the `# ` before the PostgreSQL line and put your password in it:
   ```bash
   DATABASE_URL=postgresql+psycopg://postgres:<password>@127.0.0.1:5436/registry
   ```
4. Create the tables and load the 15 seed rows of `seed_registry.sh`. This is the one setup command (FR-2.2):
   ```bash
   uv run python -m scripts.setup_postgres --demo
   ```
   Expected:
   ```text
   Target: postgresql+psycopg://postgres:***@127.0.0.1:5436/registry
   WARNING: inserting demo farms and plots. Do not use --demo on a database with real grower data.
   Catalogues: 2 crops, 3 soils, 4 emitters. Demo data: 2 farms, 4 plots.
   ```

### Every day

```bash
docker start agropilot-pg
docker exec agropilot-pg pg_isready -U postgres
uv run uvicorn main:app --host 127.0.0.1 --port 8000
```

- `docker start` is harmless if the container is already running.
- Expected in the startup log: `Database: postgresql, postgresql+psycopg://postgres:***@127.0.0.1:5436/registry`.
- Then run the checks in [Verify It Works](#4-verify-it-works).

To count the rows directly in the database (read-only):

```bash
docker exec agropilot-pg psql -U postgres -d registry -c "SELECT 'crops' AS tbl, count(*) FROM crops UNION ALL SELECT 'soils', count(*) FROM soils UNION ALL SELECT 'emitters', count(*) FROM emitters UNION ALL SELECT 'farms', count(*) FROM farms UNION ALL SELECT 'plots', count(*) FROM plots;"
```

After the first-time setup, the counts are 2, 3, 4, 2, 4. Farms and plots grow as you add them.

### Keep the data safe

- The data lives in the volume `agropilot-pg-data`. It survives service restarts, `docker stop` and `docker start agropilot-pg`, Docker restarts, and removing the container.
- Only `docker volume rm agropilot-pg-data` deletes it. Do not run it unless you mean to lose all production data.
- If you recreate the container on the same volume, the old password and data stay. `POSTGRES_PASSWORD` and `POSTGRES_DB` only apply to an empty volume.

### Outage check (optional, changes no data)

With the service running:

1. `docker stop agropilot-pg`. Then `curl -s -i http://127.0.0.1:8000/v1/farms` returns `503` with `retry-after: 5` and `{"detail":"Database unavailable"}`.
2. `docker start agropilot-pg`, wait a few seconds, and repeat the request. It returns `200` with the same farms, without restarting the service.

### About `setup_postgres`

- **Initial schema setup only, not a migration tool.** An existing table is left unchanged, even if its definition differs, and an existing catalogue row is not updated.
- Safe to run again: it uses `CREATE TABLE IF NOT EXISTS` and `INSERT ... ON CONFLICT DO NOTHING`, and never drops or deletes anything.
- It refuses a SQLite URL, and it prints the target with the password hidden before it changes anything.
- Without `--demo`, it loads the catalogues only. `--demo` adds the 2 demo farms and 4 demo plots. Do not use `--demo` on a database that holds real grower data.
- Run it with `python -m` from this folder, so that it can import `db`.

### Switch back to SQLite

Put `# ` in front of the `DATABASE_URL` line in `.env`, then restart the service. The startup log shows `Database: sqlite`.

## 6. Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `DATABASE_URL` | `sqlite:///<this folder>/registry.db` | The database. Unset or empty means the default SQLite file. |

```bash
DATABASE_URL=sqlite:////absolute/path/to/registry.db             # SQLite; a relative path resolves from the current directory
DATABASE_URL=postgresql+psycopg://user:password@host:5432/dbname  # PostgreSQL through psycopg 3
```

- Put `DATABASE_URL` in `.env` in this folder. `.env` is git-ignored and must never be committed. `.env.example` shows the format and holds no credentials.
- `config.py` reads the settings with [pydantic-settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) on every request. A variable set in the environment wins over `.env`, and `.env` wins over the default.
- Percent-encode special characters in a password, for example `@` as `%40` and `/` as `%2F`. The service refuses a URL with an unencoded `@` in the password, without printing the URL.
- At startup the service logs the database it uses, with the password hidden.
- The service never creates the database or its tables. If the database is missing or unreachable, data routes return `503` with a `Retry-After` header, and `/health` still returns `200`.
- Keep `+psycopg` in PostgreSQL URLs. With a plain `postgresql://`, SQLAlchemy picks the driver by its own version (psycopg2 in 2.0, psycopg 3 in 2.1). This service installs psycopg 3 only.

To run against a separate SQLite file, seed it and point the service at it for one run:

```bash
bash seed_registry.sh /tmp/registry-dev.db
DATABASE_URL=sqlite:////tmp/registry-dev.db uv run uvicorn main:app --host 127.0.0.1 --port 8010
```

Port 8010 keeps it apart from the other services (8000 to 8002). planner-service and the frontend still use the registry on 8000.

## 7. Run Tests & Coverage

### Tests on SQLite (no Docker needed)

```bash
uv run pytest
```

Expected: the run ends with `passed` and some `skipped`. The skipped tests need PostgreSQL.

Every test uses its own temporary SQLite file. Tests never read or change `registry.db`, and never use the `DATABASE_URL` from `.env`. Some tests start a real uvicorn process.

### Tests on PostgreSQL

With Docker running:

```bash
docker run --rm -d --name agropilot-test-pg -e POSTGRES_PASSWORD=agropilot-local-test -p 127.0.0.1:5435:5432 postgres:17
docker exec agropilot-test-pg pg_isready -U postgres
TEST_DATABASE_URL='postgresql+psycopg://postgres:agropilot-local-test@127.0.0.1:5435/postgres' uv run pytest
docker stop agropilot-test-pg
```

- Repeat `pg_isready` until it prints `accepting connections`.
- Each test that needs a database gets a fresh `agropilot_test_<random>` database, which is dropped afterwards. Tests that only make sense on one database are skipped on the other.
- `--rm` deletes the container and everything in it when it stops. That is intended: it is throwaway. It never touches `agropilot-pg`.
- The run stops unless `TEST_DATABASE_URL` points to `localhost` or `127.0.0.1`.
- Set `TEST_DATABASE_URL` in the shell for one run. If `.env` defines it, `pytest` stops before running any test.
- `agropilot-local-test` is a fixed throwaway password for this localhost-only container. Never reuse it for production.
- `-p 127.0.0.1:5435:5432` makes the port reachable only from this machine. If port 5435 is busy, use another free port in both commands.

### Coverage (must be 100%)

Coverage is branch coverage, with `fail_under = 100` in `pyproject.toml`. Some lines run only on SQLite and others only on PostgreSQL, so it is measured over both runs. Start the test container first (see above), then:

```bash
uv run pytest --cov --cov-fail-under=0 --cov-report=
TEST_DATABASE_URL='postgresql+psycopg://postgres:agropilot-local-test@127.0.0.1:5435/postgres' uv run pytest --cov --cov-append --cov-report=term --cov-report=html
open htmlcov/index.html
docker stop agropilot-test-pg
```

- The first run records coverage without checking it. The second adds its own (`--cov-append`) and fails below 100%.
- Expected at the end of the second run: `Required test coverage of 100.0% reached.`
- `htmlcov/index.html` is the report. Red lines never ran. Yellow lines are conditions that went only one way.
- A single `uv run pytest --cov` on SQLite stops at about 95%, because it skips the PostgreSQL-only lines of `scripts/setup_postgres.py`.

## 8. Performance & CI

### Benchmark (NFR-1.1, and NFR-2.2 on PostgreSQL)

The requirement: `GET` list and `GET` by id, p95 at most 100 ms at 10 requests per second.

```bash
uv run python scripts/measure_p95.py
```

- It seeds a temporary SQLite file, starts its own uvicorn server, and sends 1,200 requests at 10 per second for 120 seconds, across 11 `GET` routes.
- It prints p50, p95, and max latency per route and overall. It ends with `NFR-1.1 (overall and every endpoint p95 <= 100 ms, all responses 200): PASS` or `FAIL`. Any non-`200` response is a failure.
- Use `--duration 10` for a quick check.

**On PostgreSQL**, the benchmark uses a database that already has the demo data. With the test container running:

```bash
docker exec agropilot-test-pg createdb -U postgres agropilot_bench
DATABASE_URL='postgresql+psycopg://postgres:agropilot-local-test@127.0.0.1:5435/agropilot_bench' uv run python -m scripts.setup_postgres --demo
uv run python scripts/measure_p95.py --database-url 'postgresql+psycopg://postgres:agropilot-local-test@127.0.0.1:5435/agropilot_bench'
```

- The script only sends `GET` requests and never writes to that database. `agropilot_bench` disappears when the test container stops.
- On macOS, Docker Desktop runs PostgreSQL inside a virtual machine, so the number reflects the local setup, not production.

**Optional stress test** with [oha](https://github.com/hatoo/oha), against a running service:

```bash
oha -z 30s -c 50 --no-tui http://127.0.0.1:8000/v1/plots
```

This sends as many requests as 50 parallel connections can, to find limits and errors under overload. Its numbers are not the NFR-1.1 result. While the benchmark or the stress test runs, the uvicorn terminal shows errors, and macOS Activity Monitor shows the CPU and memory of the `python` process.

### CI

`.github/workflows/registry-service.yaml` runs on every pull request into `main`:

- Job `test`: the coverage runs above, on SQLite and then on a PostgreSQL service container. It fails below 100% and uploads `htmlcov/` as the `coverage-report` artifact (at the bottom of the run's **Summary** page on GitHub).
- Job `audit`: checks `uv.lock` for known vulnerabilities. To run it locally:
  ```bash
  uv audit --locked --preview-features audit-command
  ```
  Expected: `Found no known vulnerabilities …`.
- The `protect-main` ruleset requires a pull request, and both jobs must pass before a merge.

## 9. Troubleshooting

| Symptom | Cause | Fix |
| --- | --- | --- |
| `registry.db already exists and was not changed` | The safety check in `seed_registry.sh` | Nothing to fix: the existing file and its data are kept. Start the service as usual. |
| `sqlite3 is not installed.` | The `sqlite3` command-line tool is missing | Install it, then run the script again. |
| `address already in use` when starting uvicorn | Another process uses the port | Stop the other server (`Ctrl+C` in its terminal), or find it with `lsof -i :8000`. Ports 8001 and 8002 belong to weather-service and planner-service. |
| Data routes return `503` `{"detail":"Database unavailable"}` | The database cannot be reached: the SQLite file is missing, or the PostgreSQL container is stopped, or the password or database name in `.env` is wrong | SQLite: `bash seed_registry.sh`. PostgreSQL: `docker start agropilot-pg`, then check `DATABASE_URL` in `.env`. |
| Data routes return `500 Internal Server Error` on SQLite | The file exists but has no tables (for example, an empty file) | Do not delete the file: it may hold data. Check which file the startup log's `Database:` line names. To work with fresh data, seed a separate file and run against it (see the end of [Configuration](#6-configuration)). |
| Startup log: `Database: invalid. DATABASE_URL could not be parsed.` | Special characters in the password are not encoded | Percent-encode them, for example `@` as `%40`. |
| Startup log shows `postgresql`, but you want SQLite | `.env` sets `DATABASE_URL` | See [Switch back to SQLite](#switch-back-to-sqlite). |
| `setup_postgres only works with a PostgreSQL DATABASE_URL.` | `DATABASE_URL` is not set to PostgreSQL | Set it in `.env` (see [PostgreSQL first time](#first-time-once-per-machine), step 3). |
| `docker run` fails: the name `/agropilot-pg` is already in use | The container already exists | Do not recreate it: `docker start agropilot-pg`. |
| `pg_isready` does not print `accepting connections` | PostgreSQL is still starting | Wait a few seconds and run it again. |
| `422` on a `POST` or `PATCH` | Missing `Content-Type: application/json` header, or an invalid body | Add the header. The response's `detail` names the invalid field. |
| `pytest` stops: `Remove TEST_DATABASE_URL from .env; set it in the shell for one run.` | `.env` defines `TEST_DATABASE_URL` | Remove it from `.env`. |
| `pytest` stops: `TEST_DATABASE_URL must point to localhost` | It points to another host | Use the local test container URL above. |
| Coverage fails at about 95% | Only the SQLite run was measured | Run both coverage commands in [Coverage](#coverage-must-be-100). |
