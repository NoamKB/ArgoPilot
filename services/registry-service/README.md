# registry-service

## Overview

The AgroPilot registry service stores farms and their plots and serves read-only catalogues of crops, soils, and drip emitters. It is a FastAPI application on top of one SQLite file, `registry.db`.

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
| `REGISTRY_DB_PATH` | `registry.db` in this directory | Path of the SQLite file. A relative path is resolved from the current directory. |

The service never creates the database file. If the file is missing or unreadable, data routes return `503` with a `Retry-After` header and `/health` still returns `200`.

To run against a separate database, seed it and point the service at it:

```bash
bash seed_registry.sh /tmp/registry-dev.db
REGISTRY_DB_PATH=/tmp/registry-dev.db uv run uvicorn main:app --host 127.0.0.1 --port 8001
```

## Automated tests

```bash
uv run pytest
```

Each test seeds its own temporary database through `REGISTRY_DB_PATH`, so tests never read or change `registry.db`. Some tests start a real uvicorn process to check behavior under parallel requests.

## Performance & load testing

**Official NFR-1.1 benchmark** (`GET` list and `GET` by id, p95 at most 100 ms at 10 requests per second):

```bash
uv run python scripts/measure_p95.py
```

The script seeds a temporary database, starts its own uvicorn server, and sends 1,200 requests at a fixed 10 requests per second for 120 seconds across 11 successful `GET` routes. It prints p50, p95, and max latency per route and overall, and ends with `PASS` or `FAIL`. Any non-`200` response is a failure. Use `--duration 10` for a quick check.

**Optional stress test** with [oha](https://github.com/hatoo/oha), against a running server:

```bash
oha -z 30s -c 50 --no-tui http://127.0.0.1:8000/v1/plots
```

The benchmark measures latency at the fixed load the requirement names. The stress test sends as many requests as 50 concurrent connections can, to find limits and errors under overload. Its numbers are not the NFR-1.1 result.

While either runs, the uvicorn terminal shows errors, and macOS Activity Monitor shows the CPU and memory of the `python` process.
