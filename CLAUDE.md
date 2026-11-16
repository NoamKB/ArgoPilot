# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

AgroPilot helps a grower manage agricultural crops with modern AI. The product name is **AgroPilot**; the repository folder is spelled `ArgoPilot`. Use "AgroPilot" in code and docs.

The repo has one service, `registry-service`, which implements the P1 specification (see Assignment). Later assignments build on it.

## Commands

There is no root `pyproject.toml`. Run every `uv` command from the service directory, using Python 3.12 (`.python-version`).

```bash
cd services/registry-service
uv sync                                                # install locked dependencies, including the dev group, into .venv
bash seed_registry.sh                                  # (re)create registry.db; deletes the existing file first
uv run uvicorn main:app --host 127.0.0.1 --port 8000   # run the service
curl http://127.0.0.1:8000/health                      # expect {"status":"ok"}
uv run pytest                                          # run all tests
uv run pytest tests/test_plots.py::test_patch_with_empty_body_changes_nothing   # run one test
uv run python scripts/measure_p95.py                   # NFR-1.1 benchmark, 120 s at 10 rps
uv run python scripts/measure_p95.py --database-url URL   # benchmark an existing database that has the demo data
uv run python -m scripts.setup_postgres [--demo]       # PostgreSQL schema + catalogues (initial setup only; --demo never on production)
TEST_DATABASE_URL='postgresql+psycopg://postgres:agropilot-local-test@127.0.0.1:5435/postgres' uv run pytest   # suite on PostgreSQL; container command in the service README
uv lock --check                                        # verify uv.lock matches pyproject.toml
```

To debug, use the `registry-service` config in `.vscode/launch.json`. It runs the same uvicorn command under debugpy with the service's `.venv` interpreter, so run `uv sync` first.

Tests use pytest and `httpx2` (Starlette's `TestClient` imports it) from the `dev` dependency group. An autouse fixture points `DATABASE_URL` at a temporary SQLite file for every test; seeding needs the `sqlite3` CLI. With `TEST_DATABASE_URL` (localhost only, shell only, never in `.env`), tests that need a database get a fresh PostgreSQL database each; `sqlite_only` and `postgres_only` markers skip tests for the other backend. No linter, formatter, or type checker is configured; the ruff and mypy entries in `.gitignore` are placeholders.

## Architecture

- **Services:** each service lives in `services/<name>/` and is self-contained, with its own `pyproject.toml`, `uv.lock`, and `.venv`. There is no uv workspace and no shared code between services.
- **`registry-service`:** a FastAPI app on SQLite (`registry.db`, local and tests) or PostgreSQL (production), selected by `DATABASE_URL` from the environment or `.env`. A request goes `routers/` (HTTP: input, status codes, order of checks) → Pydantic models in `schemas.py` → `repositories/` (handwritten SQL with SQLAlchemy Core `text()`, return data or `None`) → database. There is no service layer and no ORM. `db.py` keeps one engine per URL (SQLite: `NullPool`, bound to its file, `mode=rw`, foreign keys on; PostgreSQL: psycopg 3, `pool_pre_ping`). `get_db` opens one transaction per request with `engine.begin()`, and `Depends(get_db, scope="function")` commits before the response is sent; repositories and routers never commit. Endpoints are plain `def` because the drivers block. Errors use FastAPI's defaults; the one custom handler in `main.py` turns database-unavailable errors into `503` with `Retry-After`, classified by `sqlite_errorname` or PostgreSQL SQLSTATE so SQL bugs stay `500`. String inputs reject NUL characters (PostgreSQL cannot store them). There is no auth.
- **Imports depend on the working directory:** `[tool.uv] package = false` means the service is not an installed package, so `main:app` only resolves when uvicorn runs from `services/registry-service` (the launch config sets `cwd` for this).

## Assignment

AgroPilot is built incrementally: each course assignment builds on the existing implementation.

- Current assignment: **P1 — Registry Service API**
- Specification: https://github.com/alonitac/OzVeruach26/blob/main/tasks/p1_registry_api.md
- Seed script: https://github.com/alonitac/OzVeruach26/blob/main/tasks/seed_registry.sh
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
