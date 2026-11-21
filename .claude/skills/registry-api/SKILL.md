---
name: registry-api
description: The HTTP API conventions for AgroPilot's registry-service (routes, response fields, PATCH semantics, error status codes and bodies, required tests). Use whenever you add, change, review, or test an endpoint, router, response model, or error response in services/registry-service, including farms, plots, crops, soils, emitters, status codes, 404/409/422/503 handling, or HTTPException. Use it even when the request only says "add a field to plots", "change what the API returns", or "fix this endpoint".
---

# registry-service API conventions

These rules keep every endpoint consistent with the specification and with the code that already exists. Clients (planner-service, the frontend) and the tests depend on them. Follow the existing code in `routers/farms.py` and `routers/plots.py`. Do not invent a new style.

Each rule is tagged with its source:
- **[P1]**: the P1 specification.
- **[Clarification]**: `docs/instructor-clarifications.md`.
- **[Project]**: a decision we made.

If a rule here seems to conflict with the specification or a clarification, stop and ask the user. Do not choose one on your own.

## Before you write code

1. Find the requirement in the source of truth: the specification linked in `CLAUDE.md` plus `docs/instructor-clarifications.md`.
2. **If the specification does not say what should happen in some case, ask the user.** Do not invent behavior, a status code, a field, or an error message. Nobody can review an API that does more than the specification says. Only the user can decide what goes beyond it. Examples: a filter the spec doesn't list, what to do with a duplicate the spec doesn't mention, a status code for a case the spec doesn't cover.

## Routes

- Every API route is under `/v1`, set with the router `prefix` (`APIRouter(prefix="/v1/farms")`). [P1]
- `GET /health` is the one exception. It stays at the root, as the P1 and P2 specifications require. Do not move it. [P1]

## Responses

- **Return only the fields the specification lists.** Never add a field on your own, even if it seems useful (`created_at`, counts, nested objects). Every endpoint sets `response_model=` to a model in `schemas.py`, so extra columns from the repository are dropped. [P1]
- Lists are JSON arrays, never wrapped in an object. No rows means `200` and `[]`, not `404`. [P1]
- Use the status codes from the specification's endpoint table: `201` for `POST`, `204` with no body for `DELETE`, `200` otherwise. [P1]

## PATCH

`PATCH` changes only the fields in the body. A field that is left out stays as it is. An empty body changes nothing and returns `200` with the current resource. [P1]

- Read which fields were sent with `body.model_dump(exclude_unset=True)` or `body.model_fields_set`. Never use a plain `model_dump()`. It fills in missing fields with `None` and overwrites stored data.
- Update models use `ConfigDict(extra="forbid")`, so an unknown field is `422`, not ignored silently.

## Errors

The specification (FR-1.4) asks for `application/problem+json` (RFC 9457) with a `code` field. The instructor confirmed that **FastAPI's default error responses are sufficient** [Clarification]. The service uses FastAPI's defaults on purpose. Do not add problem+json, a `code` field, or custom exception handlers. That would be a change across the whole service and needs the user's approval and a plan first.

Use the status codes from the specification [P1]:

| Case | Status | How |
|---|---|---|
| Bad field, wrong type, unknown body field, non-UUID id | `422` | Pydantic and FastAPI do it automatically |
| Unknown crop, soil, or emitter in a body | `422` | `HTTPException(422, detail="Unknown crop")` |
| Unknown id | `404` | `HTTPException(404, detail="Farm not found")` |
| Duplicate plot name on the same farm, deleting a farm that still has plots | `409` | catch `IntegrityError`, check `violated_constraint(exc)` |
| Database unreachable | `503` + `Retry-After` | already handled in `main.py`. Do not catch it in a router |

- Raise `HTTPException` in routers. Repositories return `None` or `False` and never raise HTTP errors.
- Reuse the existing `detail` texts ("Farm not found", "Plot not found", "Unknown emitter") for the same case. Tests assert exact bodies, so a reworded message is a breaking change. [Project]
- Re-raise any `IntegrityError` you don't recognize. An unexpected database error must stay `500`, never turn into a guessed `409`. [Project]

## Tests

Every endpoint you add or change gets tests for the success case **and every failure case it can return**. Use the table above as the checklist: if the endpoint can return 404, 409, or 422, each one has a test. [Project]

- Put tests in the matching `tests/test_<resource>.py` and use the `client` fixture. It gives a fresh, seeded database.
- Assert the status code **and** the exact body: `assert response.json() == {"detail": "Farm not found"}`. For lists, check the empty case returns `[]`.
- For PATCH, test that a field left out of the body stays unchanged and that an empty body changes nothing.
- Use `assert_unavailable(response)` from `conftest.py` for `503`.
- CI requires 100% branch coverage over the SQLite and PostgreSQL runs together. A failure branch with no test fails CI.

## Before you say the work is done

Run the suite from `services/registry-service` and report the result:

```bash
uv run pytest
```

If you can, also run it on PostgreSQL (`TEST_DATABASE_URL`, see the service README, "Automated tests"). If you didn't, say so. Never report the work as done while a test fails, and never claim tests passed if you didn't run them.
