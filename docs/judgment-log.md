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

## JL-007: Use SQLAlchemy Core to support SQLite and PostgreSQL

- **Date:** 2026-11-12
- **Assignment:** P1 — Registry Service API
- **Context:** The app must support SQLite and PostgreSQL, selected by `DATABASE_URL`, but the repositories called `sqlite3` directly.
- **AI recommendation:** SQLAlchemy Core with handwritten SQL and the `psycopg` driver.
- **Alternatives:** A handwritten adapter over `sqlite3` and `psycopg`, set aside as custom code to own; PostgreSQL only, ruled out by the SQLite requirement.
- **Decision:** Use SQLAlchemy Core: one engine per URL, `NullPool` for SQLite, and the default PostgreSQL pool with `pool_pre_ping=True`.
- **Reasoning:** SQLAlchemy is a well-known library that supports both databases with one parameter syntax and built-in connection pooling, and it offers an ORM and Python SQL expressions if needed later.
- **Tradeoffs:** It is a large dependency with its own concepts. The pool settings are defaults and will be benchmarked later.

## JL-008: One database transaction per request

- **Date:** 2026-11-13
- **Assignment:** P1 — Registry Service API
- **Context:** Repository-level commits would prevent future operations with several writes, such as creating a farm and a plot, from being atomic.
- **AI recommendation:** First, commits inside each repository function; revised to a request-scoped transaction after the user questioned transaction ownership.
- **Alternatives:** Repository-level commits, rejected because they block multi-write atomicity; an explicit `conn.commit()` in each write endpoint, set aside because a forgotten commit silently discards a write.
- **Decision:** `get_db` opens one transaction per request with `engine.begin()`, and the dependency uses `scope="function"` so the commit runs before the response is sent; the FastAPI minimum rises to 0.121.0. Tests cover a failed commit (503 with `Retry-After`) and a full rollback when the second of two writes fails.
- **Reasoning:** Centralized transaction ownership keeps repositories focused on SQL and lets future multi-write operations be atomic without refactoring or extra layers. A transaction that writes data must commit before the client is told the write succeeded.
- **Tradeoffs:** Correctness depends on `scope="function"`: an experiment showed that without it, a failed commit still returns 201.

## JL-009: Reject NUL characters in string inputs on both databases

- **Date:** 2026-11-13
- **Assignment:** P1 — Registry Service API
- **Context:** PostgreSQL text cannot contain NUL characters, so NUL in names, catalogue IDs in plot bodies, or catalogue paths returned 201, 422, or 404 on SQLite but 500 on PostgreSQL.
- **AI recommendation:** Accept it as a documented known difference without code changes, to keep SQLite's current behavior.
- **Alternatives:** Rejecting NUL in name fields only, set aside because catalogue IDs and catalogue paths would still return 500 on PostgreSQL.
- **Decision:** Reject NUL in all string inputs that reach the database with a 422 validation error on both databases. This makes both backends consistent, and deliberately changes legacy SQLite behavior for NUL input, the one intended exception to "existing endpoints keep behaving exactly the same".
- **Reasoning:** PostgreSQL's data constraints are preserved instead of SQLite's permissive behavior, for PostgreSQL compatibility and predictable API behavior.
- **Tradeoffs:** On SQLite, NUL input changes from 201, 422 "Unknown crop", or 404 to a 422 validation error.

## JL-010: Keep the empty-DATABASE_URL fallback; log the selected database at startup

- **Date:** 2026-11-17
- **Assignment:** P1 — Registry Service API
- **Context:** An exported empty `DATABASE_URL` (e.g. docker-compose `${DATABASE_URL}` with the host variable unset) overrides `.env`, and the approved rule then selects the default SQLite file without any message.
- **AI recommendation:** Keep the rule; optionally log the selected database at startup.
- **Alternatives:** Treat an empty value as unset so `.env` applies, rejected as a hidden exception to "the environment wins" that only fixes the `.env` case; an `APP_ENV=production` setting that forbids the SQLite fallback, rejected as a new concept outside the assignment.
- **Decision:** Keep the precedence and fallback rule. At startup, log the backend and target through uvicorn's logger, with the password and query string hidden.
- **Reasoning:** One simple, predictable rule, made visible to the operator without changing behavior.
- **Tradeoffs:** The log only reports a misconfiguration and doesn't prevent it; someone has to read it. A startup check that fails on an invalid URL is deferred.

## JL-011: Start every plan with a full soil bucket

- **Date:** 2026-11-20
- **Assignment:** P2 — Weather, planner, and the daily plan
- **Context:** The plan needs a soil water level for this morning, but AgroPilot has no soil moisture measurement and no irrigation history.
- **AI recommendation:** Start with a full bucket, and document that this is not a measured value.
- **Alternatives:** Start at half (the 50 % threshold), set aside because it is just as much a guess and would make most plans irrigate on day 1 only because of the starting value. Simulate the bucket from the planting date, rejected because weather-service gives only forecast days (FR-2.3), not past rain and irrigation.
- **Decision:** Every plan starts with a full bucket (bucket level = TAW). This is our assumption, not something FAO-56 or the spec requires.
- **Reasoning:** Both starting points are guesses, but a full bucket gives a clear, repeatable plan that can be checked by hand. The spec's own example (a 70 mm bucket that reaches half after 5 days) also starts full.
- **Tradeoffs:** If the soil is actually dry, the plan can say "no irrigation" when the field needs water. The plan does not replace checking the soil.

## JL-012: Refill the bucket to full when irrigating

- **Date:** 2026-11-20
- **Assignment:** P2 — Weather, planner, and the daily plan
- **Context:** When the bucket would drop below half, the plan has to decide how much water to give.
- **AI recommendation:** Refill the bucket to full, as in the FAO-56 scheduling example (Annex 8).
- **Alternatives:** Give back only that day's crop water use (ETc), rejected because the bucket then stays just above half and the plan irrigates almost every day. A target between half and full, set aside because it adds another value to choose.
- **Decision:** On an irrigation day, add the water the bucket is missing (TAW minus the start level) at the start of the day, up to the daily cap (JL-014).
- **Reasoning:** The plan is easy to follow: the bucket fills, drains for a few days, and fills again, which shows why the plan does not irrigate every day.
- **Tradeoffs:** Each irrigation is bigger and longer, and with low flow a full refill may not fit in one day (JL-014).

## JL-013: Decide irrigation from today's forecast, at the start of the day

- **Date:** 2026-11-20
- **Assignment:** P2 — Weather, planner, and the daily plan
- **Context:** The model works in whole days, so it needs a rule for when rain and irrigation count, and whether to irrigate before or after the bucket crosses half.
- **AI recommendation:** Check whether the bucket would end today below half without irrigation; if so, irrigate at the start of the day.
- **Alternatives:** Decide from yesterday's end level and irrigate the next day, as FAO-56 Annex 8 does, rejected because the bucket can drop below half before the irrigation.
- **Decision:** Rain and irrigation are added at the start of the day, and water above a full bucket is lost. Irrigation is decided from today's forecast, before the day's ETc is taken out.
- **Reasoning:** The plan acts before the bucket drops below half, instead of finding out afterwards that water was missing.
- **Tradeoffs:** A daily model, not hourly: evening rain counts in the morning, irrigation is assumed possible at the start of every day, and the forecast is treated as certain. If forecast rain does not come, the plan may have skipped a needed irrigation.

## JL-014: Cap irrigation at 24 hours a day

- **Date:** 2026-11-20
- **Assignment:** P2 — Weather, planner, and the daily plan
- **Context:** In hand case 3 (the seed plot West block values), refilling the bucket on day 6 needed 1,701 minutes, but a day has only 1,440.
- **AI recommendation:** Show that the run is not possible, or split the irrigation over several days.
- **Alternatives:** Return 1,701 minutes as a theoretical value, rejected because no day is that long. Split the irrigation over several days automatically, rejected because it adds a more complex scheduling mechanism.
- **Decision:** Limit irrigation to 1,440 minutes a day, and limit the litres and millimetres to match. The bucket is updated with the water the plan can deliver within that limit, and nothing carries over to the next day.
- **Reasoning:** A plan cannot ask for more than a day of irrigation in one day, and it must not show a full bucket that the system cannot fill.
- **Tradeoffs:** The bucket may be only partly refilled: in case 3 it ends day 6 at 47.425 mm instead of 51.775. The 24-hour limit is a model limit, not a practical schedule to run. The planner does not measure what was really applied, and there is no hourly scheduling or warning when the cap is hit.

## JL-015: Add in-season demo plots through the API; keep the seed data unchanged

- **Date:** 2026-11-20
- **Assignment:** P2 — Weather, planner, and the daily plan
- **Context:** On 2026-11-20, three of the four seed plots were past the end of their growing season, and the fourth (Greenhouse, pepper, day 204 of 210) leaves it within a week, so the seed plots cannot show a normal in-season plan.
- **AI recommendation:** Keep using the final Kc after the season ends, so the seed plots still show irrigation numbers. A separate suggestion was to add in-season demo plots through `POST /v1/plots`.
- **Alternatives:** Keep the final Kc after the season, or return zero irrigation after harvest; both rejected. Change the seed planting dates, rejected because FR-2.2 requires loading the same 15 seed rows.
- **Decision:** Demonstrate the plan with plots planted inside their growing season, added through the API. The seed data stays unchanged. What the planner returns for out-of-season plots is still an open decision.
- **Reasoning:** The demo shows Kc from real growth stages instead of a value invented for plots after harvest, and the seed data still matches FR-2.2.
- **Tradeoffs:** Demo plots must be added before a demo on a new database. Until the open decision is made, the planner has no defined answer for out-of-season plots.

## JL-016: Fixed crop profiles for tomato and bell pepper

- **Date:** 2026-11-21
- **Assignment:** P2 — Weather, planner, and the daily plan
- **Context:** FAO-56 gives several stage-length rows per crop for different regions and planting months (Table 11), a range for tomato's end-of-season Kc (0.70–0.90, Table 12), and a range of root depths (Table 22). The spec does not say which values to use.
- **AI recommendation:** One fixed profile per crop: the "Arid Region" stage lengths (tomato 35/45/70/30 days, pepper 30/40/110/30), tomato Kc end 0.80, and fixed root depths of 0.7 m for tomato and 0.5 m for pepper.
- **Alternatives:** The Mediterranean rows, set aside because they fit spring planting and give shorter seasons. Choosing the row by planting month, rejected because it adds a lookup rule and edge cases, such as months with no row.
- **Decision:** Use these values for every plot, whatever its location or planting month. Tomato Kc end 0.80 is the middle of FAO's range, the root depths are the smallest values in FAO's ranges, and pepper's Kc values (0.60 / 1.05 / 0.90) come straight from Table 12. These are deliberate P2 simplifications based on FAO-56 reference values, not values that are correct for every location or season.
- **Reasoning:** One fixed, documented profile per crop keeps the P2 engine simple and testable, and every value can be traced to a FAO-56 table.
- **Tradeoffs:** A plot planted in another season gets stage lengths that may not match its real growth. A fixed root depth gives young plants a bigger bucket than their roots really reach. The root depth also moves the irrigation day: on the sand plot in the `half-up-ties` eval, 0.7 m first irrigates on day 6 and 0.8 m on day 7.

## JL-017: Single crop coefficient without climate adjustment

- **Date:** 2026-11-20
- **Assignment:** P2 — Weather, planner, and the daily plan
- **Context:** FAO-56 recommends the dual crop coefficient for drip irrigation (Table 10), but weather-service returns only ET0 and rain (FR-2.3).
- **AI recommendation:** Use the single Kc from Table 12, without FAO's climate adjustments.
- **Alternatives:** The dual Kc, rejected because it needs wind speed and humidity, which would extend weather-service beyond FR-2.3.
- **Decision:** The engine uses the unadjusted single Kc from Table 12, changing in a straight line between growth stages (Eq. 66).
- **Reasoning:** It works with the data the system has, matches the spec's own example (Kc 1.15), and is easy to explain.
- **Tradeoffs:** Less accurate for drip than the dual Kc, mostly early in the season, when much of the water loss is evaporation from wet soil.

## JL-018: Round only the API output, with .5 rounding up

- **Date:** 2026-11-20
- **Assignment:** P2 — Weather, planner, and the daily plan
- **Context:** The calculation produces values like 248.4 minutes and Kc 0.99833…, and the spec does not say how to round them.
- **AI recommendation:** Whole minutes and litres with .5 rounding up, `kc` to 2 decimals, and millimetre values (`et0_mm` and the bucket level) to 1 decimal.
- **Alternatives:** Round only `run_minutes` and return the other values unrounded; not chosen.
- **Decision:** Keep full precision in the calculation and round only the API output, with .5 always rounding up: `run_minutes` and `litres` to whole numbers, `kc` and `bucket_level_mm` to 3 decimals. `et0_mm` is returned exactly as weather-service sent it. The 1,440-minute cap is applied before rounding, and a rounded value is never used in a later calculation.
- **Reasoning:** Rounded values fed back into the bucket would add a small error every day. Three decimals show the hand-calculated values unchanged, such as Kc 0.825 and a bucket level of 47.425 mm, which 2 and 1 decimals would show as 0.83 and 47.4.
- **Tradeoffs:** Python's `round()` cannot be used, because it rounds .5 to the even number (`round(2.5)` is 2), so the engine needs its own small rounding helper.

## JL-019: Calculate with exact fractions instead of floats

- **Date:** 2026-11-21
- **Assignment:** P2 — Weather, planner, and the daily plan
- **Context:** A skill eval found a rounding bug: Kc for pepper on day 32 is exactly 0.6225 and should round up to 0.623, but a float stores it as 0.62249999…, which rounds down to 0.622. The same problem can make a day that ends at exactly half look slightly below half, so the plan irrigates when it should not.
- **AI recommendation:** First, round floats to 9 decimals before the output rounding. After tests showed this still failed for large values such as litres on big plots, the recommendation changed to exact fractions with Python's `fractions.Fraction`.
- **Alternatives:** Rounding floats to 12 significant digits, set aside because it passed the tests but depends on a chosen precision limit. `Decimal` for every calculation, which can work with a defined precision rule, set aside because every division (such as 1000 / 0.6) must then be rounded to that precision, and the rule has to be chosen and tested.
- **Decision:** The engine converts every input once with `Fraction(str(value))` and does all calculations with exact fractions. The 50 % threshold check is exact, with no tolerance, and values are rounded (.5 up) only for the API output.
- **Reasoning:** Fractions give exactly the hand-calculated numbers, with no precision setting to manage, and the code still reads like normal arithmetic.
- **Tradeoffs:** One float mixed into the calculation, such as `0.5 * taw`, silently brings the float errors back, so inputs are converted in one place and a test checks that the results are fractions. Fractions are slower than floats, which does not matter for a 7-day plan.

## JL-020: Reject out-of-season plans with 409 PLOT_OUT_OF_SEASON

- **Date:** 2026-11-21
- **Assignment:** P2 — Weather, planner, and the daily plan
- **Context:** FAO-56 gives Kc values only from planting to the end of the season (tomato 180 days, pepper 210 days). A plan covers today to today + days − 1, so it can start before planting or run past the season's last day. The P2 specification does not say what the planner should do then.
- **AI recommendation:** None. The rule came from the user.
- **Alternatives:** Inventing a Kc for the days outside the season (keeping the last Kc, using 0, or extending the curve), set aside because those numbers would not come from FAO-56.
- **Decision:** If the first plan day is before planting or the last plan day is past the season, the planner rejects the whole request with `409` and the body `{"code": "PLOT_OUT_OF_SEASON", "detail": "The plot is outside its growing season."}`. The check runs after the plot is read from registry-service and before the forecast is requested from weather-service.
- **Reasoning:** The request itself is valid; the problem is the plot's current state, which is what 409 means. Any plan for those days would contain invented numbers. A specific code lets the frontend show the grower a clear message. Checking before the weather call avoids a call for a plan that will be refused anyway.
- **Tradeoffs:** A plot in the last days of its season gets no 7-day plan, only a shorter one (for example `days=1` on its last day). All four seed plots are out of season for a 7-day plan from 2026-11-21, so the demo needs in-season plots. When weather-service is down, an out-of-season plot gets 409 instead of 503.

## JL-021: Serve a stale forecast for at most 24 hours

- **Date:** 2026-11-21
- **Assignment:** P2 — Weather, planner, and the daily plan
- **Context:** A cached forecast is fresh for 3 hours. After that, weather-service tries the provider again. If the provider fails, FR-2.6 says to serve the last forecast for the cell with `stale: true`. P2 leaves it to the project to decide how old that forecast may be before the service returns 503 instead.
- **AI recommendation:** 24 hours.
- **Alternatives:** 12 hours, set aside because it gives more 503s during a long provider outage. 48 hours, set aside because weather data that old is too likely to be wrong.
- **Decision:** The limit is 24 hours (`FORECAST_MAX_STALE_HOURS`). The service serves stale data only when the provider fails, the cached forecast is no older than 24 hours, and it covers every requested date from today. Otherwise it returns `503 UNAVAILABLE` with `Retry-After`.
- **Reasoning:** 24 hours balances service availability against the risk of planning irrigation with outdated weather data. The grower sees that the forecast is stale.
- **Tradeoffs:** If Open-Meteo is down for more than a day, the planner gets no forecast and cannot give a plan. A stale forecast from before local midnight has one day fewer, so a 7-day request can fail while shorter requests still work.
