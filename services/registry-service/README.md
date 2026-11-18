# registry-service

## Overview

The AgroPilot registry service stores farms and their plots and serves read-only catalogues of crops, soils, and drip emitters. It is a FastAPI application that stores its data in the SQLite file `registry.db` locally and in tests, or in PostgreSQL in production, selected by `DATABASE_URL`.

| Resource | Routes |
| --- | --- |
| Farms | `POST`, `GET` `/v1/farms` and `GET`, `PATCH`, `DELETE` `/v1/farms/{id}` |
| Plots | `POST`, `GET` `/v1/plots` (optional `?farm_id=`) and `GET`, `PATCH`, `DELETE` `/v1/plots/{id}` |
| Catalogues | `GET` `/v1/crops`, `/v1/soils`, `/v1/emitters`, each with `/{id}` |

Errors use FastAPI's default format, for example `{"detail": "Plot not found"}`.

## Setup & prerequisites

- Python 3.12 (pinned in the repository's `.python-version`)
- [uv](https://docs.astral.sh/uv/)
- The `sqlite3` command-line tool (preinstalled on macOS)

Run every command from this directory:

```bash
cd services/registry-service
uv sync
bash seed_registry.sh
```

`uv sync` installs the locked dependencies into `.venv`. `seed_registry.sh` creates `registry.db` with 2 farms, 4 plots, and the catalogues. It deletes any existing `registry.db` first, so run it again whenever you want a clean database.

## Running the API

```bash
uv run uvicorn main:app --host 127.0.0.1 --port 8000
```

- Health check: http://127.0.0.1:8000/health
- Swagger UI: http://127.0.0.1:8000/docs

Example requests:

```bash
curl http://127.0.0.1:8000/v1/emitters/dripnet-pc-1.0
curl "http://127.0.0.1:8000/v1/plots?farm_id=b7e2c0a0-3c1d-4f0a-9a11-0c5d2e6f1001"
curl -X POST http://127.0.0.1:8000/v1/farms -H "Content-Type: application/json" -d '{"name": "North farm"}'
```

Request bodies must be sent with `Content-Type: application/json`. Without it, the API returns `422`.

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `DATABASE_URL` | `sqlite:///<this directory>/registry.db` | The database. Unset or empty means the default SQLite file. |

Two URL forms are supported:

```bash
DATABASE_URL=sqlite:////absolute/path/to/registry.db             # SQLite; a relative path resolves from the current directory
DATABASE_URL=postgresql+psycopg://user:password@host:5432/dbname  # PostgreSQL through psycopg 3
```

- Put `DATABASE_URL` in `.env` in this directory. `.env` is git-ignored; `.env.example` shows the format and holds no credentials.
- A variable already set in the environment wins over `.env`.
- Keep `+psycopg` in PostgreSQL URLs. With a plain `postgresql://`, SQLAlchemy picks the driver by its own version (psycopg2 in 2.0, psycopg 3 in 2.1); this service installs psycopg 3 only.
- Percent-encode special characters in a password, for example `@` as `%40` and `/` as `%2F`. The service refuses a URL with an unencoded `@` in the password, without printing the URL.
- At startup the service logs the database it uses, with the password hidden, for example `INFO: Database: sqlite, sqlite:////…/registry.db`.

The service never creates the database or its tables. If the database is missing or unreachable, data routes return `503` with a `Retry-After` header and `/health` still returns `200`.

To run against a separate SQLite file, seed it and point the service at it:

```bash
bash seed_registry.sh /tmp/registry-dev.db
DATABASE_URL=sqlite:////tmp/registry-dev.db uv run uvicorn main:app --host 127.0.0.1 --port 8001
```

## PostgreSQL setup

Create the tables and catalogues in an existing, empty PostgreSQL database:

```bash
DATABASE_URL='postgresql+psycopg://user:password@host:5432/dbname' uv run python -m scripts.setup_postgres
```

- **Initial schema setup only, not a migration tool.** An existing table is left unchanged, even if its definition differs, and an existing catalogue row is not updated.
- Safe to run again: it uses `CREATE TABLE IF NOT EXISTS` and `INSERT ... ON CONFLICT DO NOTHING`, and never drops or deletes anything.
- It refuses a SQLite URL and prints the target with the password hidden before changing anything.
- `--demo` also inserts the 2 demo farms and 4 demo plots. **Never use `--demo` on a production database.**
- Run it with `python -m` from this directory, so that it can import `db`.

## Automated tests

```bash
uv run pytest
```

Every test points `DATABASE_URL` at its own temporary SQLite file, so tests never read or change `registry.db` or use a `DATABASE_URL` from `.env`. Some tests start a real uvicorn process to check behavior under parallel requests.

**On PostgreSQL**, with Docker running:

```bash
docker run --rm -d --name agropilot-test-pg -e POSTGRES_PASSWORD=agropilot-local-test -p 127.0.0.1:5435:5432 postgres:17
TEST_DATABASE_URL='postgresql+psycopg://postgres:agropilot-local-test@127.0.0.1:5435/postgres' uv run pytest
docker stop agropilot-test-pg
```

- The same suite runs on PostgreSQL. Each test that needs a database gets a fresh `agropilot_test_<random>` database, dropped afterwards. Tests that only make sense on one backend are skipped on the other.
- The run stops unless `TEST_DATABASE_URL` points to `localhost` or `127.0.0.1`.
- `-p 127.0.0.1:5435:5432` publishes the port only on this machine. Port 5435 avoids other local PostgreSQL servers; if it is busy, use another free port in both commands.
- `agropilot-local-test` is a fixed throwaway password for this disposable, localhost-only container. Never reuse it for production, and do not treat it as a real secret.
- Set `TEST_DATABASE_URL` in the shell for one run. If `.env` defines it, `pytest` stops before running any test.

**Coverage** must be 100% (`fail_under` in `pyproject.toml`), with branch coverage. Some lines run only on SQLite and others only on PostgreSQL, so coverage is measured over both runs, with the test container running:

```bash
uv run pytest --cov --cov-fail-under=0 --cov-report=
TEST_DATABASE_URL='postgresql+psycopg://postgres:agropilot-local-test@127.0.0.1:5435/postgres' uv run pytest --cov --cov-append --cov-report=term --cov-report=html
open htmlcov/index.html
```

- The first run records coverage without checking it. The second adds its own (`--cov-append`) and fails below 100%.
- A single `uv run pytest --cov` on SQLite stops at about 95%: it skips the PostgreSQL-only lines of `scripts/setup_postgres.py`.
- CI (`.github/workflows/registry-service.yaml`) runs the same two runs on every pull request into `main`, with a PostgreSQL service container, and uploads `htmlcov/` as the `coverage-report` artifact.

## Performance & load testing

**Official NFR-1.1 benchmark** (`GET` list and `GET` by id, p95 at most 100 ms at 10 requests per second):

```bash
uv run python scripts/measure_p95.py
```

The script seeds a temporary SQLite database, starts its own uvicorn server, and sends 1,200 requests at a fixed 10 requests per second for 120 seconds across 11 successful `GET` routes. It prints p50, p95, and max latency per route and overall, and ends with `PASS` or `FAIL`. Any non-`200` response is a failure. Use `--duration 10` for a quick check.

**On PostgreSQL**, benchmark an existing database that already has the demo data. With the test container above running:

```bash
docker exec agropilot-test-pg createdb -U postgres agropilot_bench
DATABASE_URL='postgresql+psycopg://postgres:agropilot-local-test@127.0.0.1:5435/agropilot_bench' uv run python -m scripts.setup_postgres --demo
uv run python scripts/measure_p95.py --database-url 'postgresql+psycopg://postgres:agropilot-local-test@127.0.0.1:5435/agropilot_bench'
```

The script only sends `GET` requests and never writes to that database. On macOS, Docker Desktop runs PostgreSQL inside a virtual machine, so this number reflects the local setup, not production.

**Optional stress test** with [oha](https://github.com/hatoo/oha), against a running server:

```bash
oha -z 30s -c 50 --no-tui http://127.0.0.1:8000/v1/plots
```

The benchmark measures latency at the fixed load the requirement names. The stress test sends as many requests as 50 concurrent connections can, to find limits and errors under overload. Its numbers are not the NFR-1.1 result.

While either runs, the uvicorn terminal shows errors, and macOS Activity Monitor shows the CPU and memory of the `python` process.

## Manual smoke test on PostgreSQL

About 2 minutes, with Docker running. It uses its own container and port, so it does not affect the test container.

1. Start PostgreSQL:
   ```bash
   docker run -d --name agropilot-smoke-pg -e POSTGRES_PASSWORD=agropilot-local-test -p 127.0.0.1:5434:5432 postgres:17
   ```
2. Point the app at it: `cp .env.example .env`, then add this line to `.env`:
   ```bash
   DATABASE_URL=postgresql+psycopg://postgres:agropilot-local-test@127.0.0.1:5434/postgres
   ```
3. Create the schema and demo data: `uv run python -m scripts.setup_postgres --demo`
4. Start the app: `uv run uvicorn main:app --host 127.0.0.1 --port 8000`. In a second terminal:
   - `curl -s http://127.0.0.1:8000/v1/farms` lists the 2 demo farms.
   - Creating a plot with an existing name returns `409`:
     ```bash
     curl -s -i -X POST http://127.0.0.1:8000/v1/plots -H "Content-Type: application/json" -d '{"farm_id": "b7e2c0a0-3c1d-4f0a-9a11-0c5d2e6f1001", "name": "North block", "area_m2": 1000, "crop_id": "tomato", "planting_date": "2026-03-01", "soil_id": "loam", "row_spacing_m": 1.5, "emitter_spacing_m": 0.4, "emitter_id": "dripnet-pc-1.0", "lat": 31.25, "lon": 34.79}'
     ```
   - Deleting a farm that has plots returns `409`: `curl -s -i -X DELETE http://127.0.0.1:8000/v1/farms/b7e2c0a0-3c1d-4f0a-9a11-0c5d2e6f1001`
5. `docker stop agropilot-smoke-pg`. Then `curl -s -i http://127.0.0.1:8000/v1/farms` returns `503` with `retry-after: 5`.
6. `docker start agropilot-smoke-pg`, wait a few seconds, and repeat the request: it returns `200` without restarting the app.
7. Clean up: stop the app, run `docker rm -f agropilot-smoke-pg`, and remove the `DATABASE_URL` line from `.env` so the app uses `registry.db` again.
