# Questions reviewers really asked

Add entries after each review (`/review-prep record`), only with the user's approval. The **pattern** is what matters for future assignments: check it against the new code even when the exact question won't repeat.

## P2 — review on 24.11.2026

### What does the health check in the frontend mean, and how is it run? Once at server start, or repeatedly?

- **Short answer:** a liveness check. The frontend server (not the browser) calls `GET /health` on registry, weather and planner in parallel, 2 s timeout, no cache (`services/frontend/src/lib/health.ts`). Up means "the process answers HTTP" — `/health` returns a constant and checks no dependency. It runs on every full page load because `StatusLine` sits in the root layout; it does not re-run on `<Link>` navigation (layouts don't re-render) and nothing polls.
- **Pattern:** *when does X run* (startup / request / navigation / timer) and *what does a check really prove* (liveness vs readiness).

### What happens to the system at maximum load?

- **Short answer:** measured with oha on a laptop: plans stay under 30 ms p95 up to 200 req/s; at 400 requested the system delivered about 320/s and p95 rose to about 4 s — requests queue. Mechanism (reasoned): one uvicorn process per service, `def` endpoints share a 40-thread pool, 4 sequential upstream calls per plan; past the limit requests wait, then the planner's 3 s registry timeout turns into 503 UPSTREAM_UNAVAILABLE. Slow, then explicit errors — never a wrong number. No rate limiting.
- **Pattern:** *the ceiling and the overload behaviour* — queue, timeout or reject, and what the user sees.

### If we ran several instances of the services, what would happen to load, and how would requests be divided?

- **Short answer:** today there is one instance each and no load balancer. With a load balancer (round robin / least connections, using `/health` to drop dead instances): planner and frontend are stateless and scale out; registry on PostgreSQL scales but each instance opens its own pool (watch `max_connections`, PgBouncer); SQLite cannot be shared; weather works but its in-memory cache becomes per instance — more provider calls and inconsistent stale/503 answers. Fix: shared cache (Redis) or route by grid cell.
- **Pattern:** *what state breaks when you scale out* — in-memory caches, local files, per-instance pools.

### How is the weather service built, its cache, and what happens to the cache under load?

- **Short answer:** grid cell of 0.1° → in-memory dict with a lock → fresh 3 h → otherwise Open-Meteo (1 + 2 retries, 3 s each) → on failure stale up to 24 h, else 503 + Retry-After 60. Hits are cheap. On a miss the lock covers only the dict, not the fetch, so many concurrent misses for one cell all call Open-Meteo (cache stampede). Fix: a per-cell lock or stale-while-revalidate.
- **Pattern:** *cache miss under concurrency* — is the fetch protected, or only the dictionary?

## What reviewers liked

### P2 — review on 24.11.2026

- **The out-of-season error.** A plot whose crop is out of season gets `409 PLOT_OUT_OF_SEASON` instead of a made-up plan, and the frontend says "No plan for this plot". *Pattern:* a vivid domain case where the system refuses rather than guesses.
- **The frontend.** A short live demo of the UI: plot page, simulation, an error state. *Pattern:* show it working, briefly.
- **The cache design answer.** Asked: "with many servers in parallel, does each one keep its own cache?" Answer: a cache per instance wastes memory and repeats provider calls, so move the cache out into a shared external cache managed by its own system. Entries can be grouped by location (grid cell) or by the time of the Open-Meteo call. That was the answer they were looking for. *Pattern:* scaling questions about state. Name the problem with per-instance state, then move it out to a shared, managed store.
