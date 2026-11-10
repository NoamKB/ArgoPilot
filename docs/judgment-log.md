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
