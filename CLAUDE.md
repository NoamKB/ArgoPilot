# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

AgroPilot helps a grower manage agricultural crops with modern AI. The product name is **AgroPilot**; the repository folder is spelled `ArgoPilot`. Use "AgroPilot" in code and docs.

The repo has `registry-service` (P1, moved to PostgreSQL in P2), `weather-service`, `planner-service` and `frontend` (P2).

## Commands

There is no root `pyproject.toml`. Run every `uv` command from the service directory, using Python 3.12 from the service's own `.python-version` (uv ignores the repo-root file once a service has its own `pyproject.toml`, so every new service needs one).

```bash
cd services/registry-service
uv sync                                                # install locked dependencies, including the dev group, into .venv
bash seed_registry.sh [--reset]                        # create registry.db; refuses an existing file unless --reset
uv run uvicorn main:app --host 127.0.0.1 --port 8000   # run the service
curl http://127.0.0.1:8000/health                      # expect {"status":"ok"}
uv run pytest                                          # run all tests
uv run pytest tests/test_plots.py::test_patch_with_empty_body_changes_nothing   # run one test
uv run python scripts/measure_p95.py                   # NFR-1.1 benchmark, 120 s at 10 rps
uv run python scripts/measure_p95.py --database-url URL   # benchmark an existing database that has the demo data
uv run python -m scripts.setup_postgres [--demo]       # PostgreSQL schema + catalogues (initial setup only); --demo adds the demo farms and plots (FR-2.2)
TEST_DATABASE_URL='postgresql+psycopg://postgres:agropilot-local-test@127.0.0.1:5435/postgres' uv run pytest   # suite on PostgreSQL; container command in the service README
uv lock --check                                        # verify uv.lock matches pyproject.toml
uv audit --locked --preview-features audit-command     # known vulnerabilities in uv.lock (CI job `audit`)
```

```bash
cd services/weather-service
uv sync && cp .env.example .env                        # first time; every variable but PROVIDER_API_KEY is required
uv run uvicorn main:app --host 127.0.0.1 --port 8001   # run the service (calls Open-Meteo)
uv run pytest --cov                                    # all tests, 100% branch coverage; no network, never reads .env
uv run python scripts/measure_p95.py                   # NFR-2.3 benchmark against a local fake Open-Meteo, 120 s at 10 rps
```

```bash
cd services/planner-service
uv sync && cp .env.example .env                        # first time; every variable is required
uv run uvicorn main:app --host 127.0.0.1 --port 8002   # run the service (needs registry on 8000 and weather on 8001)
uv run pytest --cov                                    # all tests, 100% branch coverage; fake registry and weather, never reads .env
```

```bash
cd services/frontend
nvm use                                                # Node 24 from the repo's .nvmrc; the shell default (18) is too old for Next.js 16
npm install && cp .env.example .env.local              # first time
npm run dev                                            # http://localhost:3000 (needs the three services)
npm run build && npm run lint                          # production build and ESLint; there are no frontend tests
```

weather-service, planner-service and frontend have no CI workflow yet.

**CI:** `.github/workflows/registry-service.yaml` runs on every pull request into `main`. Job `test` runs the suite on SQLite, then on a PostgreSQL service container, and requires 100% branch coverage over both runs (two-step commands in the service README, "Automated tests"). Job `audit` runs `uv audit`. The `protect-main` ruleset requires a pull request and both jobs; actions are pinned to commit SHAs.

To debug, use the `registry-service`, `weather-service` or `planner-service` config in `.vscode/launch.json`. It runs the same uvicorn command under debugpy with the service's `.venv` interpreter, so run `uv sync` first.

Tests use pytest and `httpx2` (Starlette's `TestClient` imports it) from the `dev` dependency group. An autouse fixture points `DATABASE_URL` at a temporary SQLite file for every test; seeding needs the `sqlite3` CLI. With `TEST_DATABASE_URL` (localhost only; set in the shell, and pytest stops if `.env` defines it), tests that need a database get a fresh PostgreSQL database each; `sqlite_only` and `postgres_only` markers skip tests for the other backend. No linter, formatter, or type checker is configured; the ruff and mypy entries in `.gitignore` are placeholders.

## Architecture

- **Services:** each service lives in `services/<name>/` and is self-contained, with its own `pyproject.toml`, `uv.lock`, and `.venv`. There is no uv workspace and no shared code between services.
- **`registry-service`:** a FastAPI app on SQLite (`registry.db`, local and tests) or PostgreSQL (production: the Docker container `agropilot-pg`, database `registry`, port 5436), selected by `DATABASE_URL`, which `config.py` reads with pydantic-settings from the environment or `.env` on every call. A request goes `routers/` (HTTP: input, status codes, order of checks) → Pydantic models in `schemas.py` → `repositories/` (handwritten SQL with SQLAlchemy Core `text()`, return data or `None`) → database. There is no service layer and no ORM. `db.py` keeps one engine per URL (SQLite: `NullPool`, bound to its file, `mode=rw`, foreign keys on; PostgreSQL: psycopg 3, `pool_pre_ping`, 5 s `connect_timeout`; both with `hide_parameters=True`). At startup `main.py` logs the selected database with the password hidden. `get_db` opens one transaction per request with `engine.begin()`, and `Depends(get_db, scope="function")` commits before the response is sent; repositories and routers never commit. Endpoints are plain `def` because the drivers block. Errors use FastAPI's defaults; the one custom handler in `main.py` turns database-unavailable errors into `503` with `Retry-After`, classified by `sqlite_errorname` or PostgreSQL SQLSTATE so SQL bugs stay `500`. String inputs reject NUL characters (PostgreSQL cannot store them). There is no auth.
- **`weather-service`:** FastAPI + `httpx2`, no database. `GET /v1/forecast` (`routers/forecast.py`) → in-memory cache per 0.1° grid cell (`cache.py`, fresh 3 h) → Open-Meteo (`provider.py`, the only place with Open-Meteo field names; 1 attempt + 2 retries, strict check of every field, unit and date) → on failure, the cached forecast up to 24 h old with `stale: true`, else `503 UNAVAILABLE` + `Retry-After`. It never fills in a missing value (FR-2.8). Errors are `{code, detail}`. `config.py` is read once at startup, and a missing variable stops it. Tests swap in a `MockTransport` fake provider and override the `utc_now` dependency. Worst case before a stale answer or 503 is about 9 s (3 × 3 s timeout), so the planner's timeout for weather-service must be longer.
- **`planner-service`:** FastAPI + `httpx2`, no database. `GET /v1/plots/{id}/plan?days=` (`routers/plan.py`) → registry plot (`upstream.py`) → early season check → registry soil and emitter → weather forecast → `engine.py` → output rounding in the router. `engine.py` is pure (no HTTP), calculates with `fractions.Fraction` only, and follows the `irrigation-calc-reference` skill exactly. `upstream.py` checks every answer strictly and converts numbers once with `Fraction(str(v))`; anything unusable is `503 UPSTREAM_UNAVAILABLE` naming the service, never a 0. The plan's dates are the forecast's dates (the plot's local date). The early check uses the UTC date ± 1 day and answers 409 only when all three fail; the engine's check on the forecast dates is final. Optional `initial_soil_water_pct` (0–100, default 100 = the JL-011 full bucket) only sets the day-1 starting level for a simulation; the response always echoes it. Errors are `{code, detail}`: `VALIDATION`, `NOT_FOUND`, `PLOT_OUT_OF_SEASON`, `UPSTREAM_UNAVAILABLE`. Tests use `MockTransport` fakes of both services and override the `utc_today` dependency.
- **`frontend`:** Next.js 16 (App Router, Cache Components on), TypeScript, Tailwind CSS 4, shadcn/ui. Server components only: every service call is in `src/lib/` and reads `REGISTRY_URL`, `WEATHER_URL` and `PLANNER_URL` after `connection()`, so the browser never calls the services. Uncached data sits inside `<Suspense>`, as Cache Components requires. Read the Next.js docs in `node_modules/next/dist/docs/` before changing it (see `services/frontend/AGENTS.md`).
- **Imports depend on the working directory:** `[tool.uv] package = false` means the service is not an installed package, so `main:app` only resolves when uvicorn runs from the service's own folder (the launch configs set `cwd` for this).

## Assignment

AgroPilot is built incrementally: each course assignment builds on the existing implementation. Earlier specifications stay binding unless a later one changes them. Add a line here when a new assignment starts and move the **current** marker.

- **P1 — Registry Service API** (complete): [specification](https://github.com/alonitac/OzVeruach26/blob/main/tasks/p1_registry_api.md), [seed script](https://github.com/alonitac/OzVeruach26/blob/main/tasks/seed_registry.sh)
- **P2 — Weather, planner, and the daily plan** (complete): [specification](https://github.com/alonitac/OzVeruach26/blob/main/tasks/p2.md)
- Course repository (read-only): https://github.com/alonitac/OzVeruach26. All implementation and Git changes stay in my personal AgroPilot repository.

**Source of truth:** the official specification plus instructor clarifications documented in `docs/instructor-clarifications.md` (created when the first clarification arrives). If they seem to conflict, ask me.

- Before implementing a feature, verify that the source of truth requires it. Discuss anything beyond it before adding it.
- If the specification cannot be accessed, report the problem instead of assuming its requirements.
- Preserve previously implemented functionality unless a new assignment explicitly requires changing it.

## How we work

This is a learning project. My goal is to become an independent Backend and AI-Augmented Software Engineer. **I must understand every line of code generated by the AI.**

**New assignments and significant changes** (a new endpoint or feature, a schema or data-model change, a new dependency, a change across several files, or anything that changes existing behavior):

1. Read the specification and inspect the existing code. Check for course-provided tests and verification instructions.
2. Propose an incremental plan and wait for my approval.
3. Implement one small, logically complete change at a time. After each, pause for my questions and approval before the next.

**Minor edits** (a typo, comment, rename, or small fix in one place with obvious behavior) do not need a plan or prior approval.

**Every change, minor or not:**

- Show the diff and explain the new code, line by line when needed.
- Run the relevant tests and report the result.
- Do not modify unrelated code, introduce unnecessary dependencies, or perform broad refactoring.
- Preserve existing local changes.

**Teaching:** explain unfamiliar concepts intuitively before technical details. Challenge my technical assumptions and explain tradeoffs. Prefer simple, readable Python over unnecessary abstractions. Do not replace learning with automatic code generation.

## Git safety

- Do not commit, push, or perform destructive operations without my explicit approval.
- Before any approved commit or push, verify the current branch, Git status, and remote destination. Never push to the course repository.

## Engineering judgment log

Maintain `docs/judgment-log.md` with the `record-decision` skill (`/record-decision`). When I finalize a significant decision (a lasting choice between real alternatives, or rejecting or changing an AI recommendation), end your reply with a one-line offer to record it. Do not offer for routine questions or small changes. Never write to the log until I approve the exact entry.

## Deliverables

The specification defines the required deliverables. The solution must be easy for course instructors to explain, demonstrate, and review. Do not build extra deliverables (documents, UI, or infrastructure) unless the specification requires them or I approve them; suggest them instead.

## Reports

In this project, use the ChatGPT report format from `~/.claude/CLAUDE.md` only when I ask for a report or when a task is completed. Otherwise, answer directly and briefly.
