# Engineering Judgment Log

Significant engineering decisions made during AI-assisted development of AgroPilot.

## JL-001: Escalate undefined error codes for 405 and 500

- **Date:** 2026-11-01
- **Assignment:** P1 — Registry Service API
- **Context:** The specification requires every error to have a `code` from a list of four (VALIDATION, NOT_FOUND, CONFLICT, UNAVAILABLE), but it also requires a 405 response, and neither 405 nor 500 fits any of the four.
- **AI recommendation:** Use `VALIDATION` for 405 and `UNAVAILABLE` for 500, to follow the specification's wording.
- **Alternatives:** New codes such as METHOD_NOT_ALLOWED and INTERNAL, rejected because they invent codes. No `code` field on 405 and 500, rejected as a final solution because it does not fully satisfy FR-1.4.
- **Decision:** Use only the codes the specification defines, continue development, and ask the instructor for clarification.
- **Reasoning:** The requirements contradict each other. Inventing error codes, or using codes that incorrectly describe the error, was not acceptable.
- **Tradeoffs:** The implementation might have to change later. The instructor eventually confirmed that FastAPI's default error responses were sufficient.

## JL-002: One SQLite connection per request

- **Date:** 2026-11-08
- **Assignment:** P1 — Registry Service API
- **Context:** registry-service needs a way to connect to its SQLite database for each API request.
- **AI recommendation:** Open a new SQLite connection for each request, without a connection pool.
- **Alternatives:** A connection pool that reuses connections between requests, set aside because it adds unnecessary complexity for P1.
- **Decision:** Open one SQLite connection per request, without a connection pool, as the AI recommended.
- **Reasoning:** Opening a SQLite connection is relatively cheap, because SQLite accesses a local database file and does not connect to a separate database server.
- **Tradeoffs:** Opening and closing a connection adds some overhead to every request. Reviewed afterward: SQLite allows only one writer at a time, which can limit heavy concurrent writes, and a pool would not remove that limit. The GET benchmark measured a p95 of about 9.07 ms at 10 requests per second, below the required 100 ms; this supports the choice for P1 but does not prove it scales under heavy write load.

## JL-003: Require every endpoint's p95 to pass the benchmark

- **Date:** 2026-11-10
- **Assignment:** P1 — Registry Service API
- **Context:** The NFR-1.1 benchmark printed a p95 for each of the 11 GET endpoints, but its PASS condition checked only the overall p95, so one endpoint could exceed 100 ms and the benchmark would still report PASS.
- **AI recommendation:** Leave the PASS condition as it was for now, because every endpoint was far below 100 ms, and treat the fix as an optional one-line change for later.
- **Alternatives:** Keep the overall-only check and add the slowest endpoint's p95 to the pull request, set aside because it leaves a known validation gap.
- **Decision:** Fix the PASS condition before merging: PASS now requires every response to be 200, the overall p95 and every endpoint's p95 to be at most 100 ms, and every endpoint to have results. Four tests cover it, including one slow endpoint that fails while the overall p95 passes.
- **Reasoning:** The benchmark could report PASS even when an individual endpoint exceeds 100 ms, and a known validation gap should not be left in before merging.
- **Tradeoffs:** Checking each endpoint separately makes the benchmark stricter and prevents false positives. However, each endpoint receives only about 109 requests, so a few slow requests may cause a failure due to temporary performance fluctuations. Reviewed afterward: all 171 tests passed, and the updated benchmark passed with an overall p95 of 9.76 ms and a slowest endpoint p95 of 9.97 ms.

## JL-004: Create the PostgreSQL schema with a setup script

- **Date:** 2026-11-10
- **Assignment:** P1 — Registry Service API
- **Context:** registry-service needed a way to create its initial PostgreSQL tables and seed data.
- **AI recommendation:** Use a separate, re-runnable setup script instead of creating tables at application startup or introducing Alembic.
- **Alternatives:** Automatic table creation at application startup, or versioned migrations with Alembic; both set aside for a simpler solution that fits the current scope.
- **Decision:** Create the initial PostgreSQL schema and seed data with a simple setup script, as the AI recommended.
- **Reasoning:** Schema changes such as creating tables and adding columns have already been done manually in another project, and migration infrastructure should not become a major part of this assignment.
- **Tradeoffs:** There is no automatic schema version tracking, so future schema changes need manual, careful execution, including backups and validation when existing data is modified. A migration tool can be added later if the project becomes more complex.

## JL-005: Seed catalogues in PostgreSQL; keep demo data optional

- **Date:** 2026-11-10
- **Assignment:** P1 — Registry Service API
- **Context:** The PostgreSQL setup script from JL-004 needed a defined scope of rows: the catalogues the API depends on (2 crops, 3 soils, 4 emitters), the demo data from `seed_registry.sh` (2 farms, 4 plots), or both.
- **AI recommendation:** Insert the catalogues only, copied exactly from `seed_registry.sh`, and leave demo farms and plots out of PostgreSQL.
- **Alternatives:** Insert catalogues and demo data together, set aside because demo farms would appear in a production `GET /v1/farms` and need manual cleanup later.
- **Decision:** The PostgreSQL setup creates the schema and seeds the catalogues. The 2 demo farms and 4 demo plots are optional, for development and testing only, and are never inserted automatically into a production database.
- **Reasoning:** Required catalogue data and optional demo data have different purposes and should be kept separate. The implementation should stay simple, without extra seeding infrastructure.
- **Tradeoffs:** A PostgreSQL development database needs an explicit extra step to get demo data. Keeping the catalogue rows identical to `seed_registry.sh` means both seed sources must be kept in sync by hand.

## JL-006: Run the existing test suite against both SQLite and PostgreSQL

- **Date:** 2026-11-10
- **Assignment:** P1 — Registry Service API
- **Context:** The endpoints must behave exactly the same on PostgreSQL as on SQLite, and the mission requires tests to use SQLite by default, so a way to verify PostgreSQL behavior was needed.
- **AI recommendation:** Both an opt-in run of the existing test suite against a temporary PostgreSQL database, and a short manual smoke-test section in the README for demonstration.
- **Alternatives:** An opt-in PostgreSQL test run alone, without the README demo; or a manual smoke test only, set aside because it covers about 10 of roughly 170 cases and could miss differences such as number or date formats. A separate test suite per database was rejected as duplication.
- **Decision:** Reuse the existing API test suite for both databases, with SQLite as the default. PostgreSQL runs use a temporary, isolated test database through adapted fixtures. Tests that are specific to one database, such as a missing or corrupt SQLite file returning 503, stay separate. A short manual smoke-test section is added to the README.
- **Reasoning:** This is a good tradeoff between the smallest solution and comprehensive test coverage of the entire change, without duplicating tests or adding unnecessary testing infrastructure.
- **Tradeoffs:** The test fixtures become somewhat more complex. The PostgreSQL run is opt-in and needs Docker, so it protects only when someone runs it; there is no CI to run it automatically.
