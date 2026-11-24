# Code sweep checklist

Go through each category for every service touched by the assignment. The question in each line is the one a reviewer would ask; the hint says where the answer usually is in this project. Skip a line only when it truly doesn't apply, and say so in the prep doc.

## When does it run

- What runs once at startup, what runs on every request, what runs in the background or on a timer? (`lifespan` in `main.py`, module-level code, `connection()` in the frontend.)
- Server components in a Next.js **layout** do not re-render on client-side navigation (`<Link>`); they run on a full page load. Anything in `layout.tsx` (status line, health checks) refreshes only on reload. Check where each server call sits: layout or page.
- Is anything polled or retried automatically? Is anything cached, and for how long (`cache: "no-store"`, in-memory caches, HTTP caching)?

## What a check really checks

- What does each `/health` return, and what does "up" actually prove (liveness: the process answers) versus what it doesn't (readiness: the database, the upstream services, the provider)?
- What does each validation reject, and where (frontend, router `Query(...)`, schema, engine)? Is it checked twice, and why?

## State

- Where is state kept: database, in-memory dict, local file, browser URL? Who owns it?
- What is lost on restart? What grows without limit (caches without eviction)?
- What is shared between threads (locks) and what would not be shared between processes or instances?

## Flows

- Client side: what runs in the browser, what runs on the frontend server, what the browser never sees (service URLs, secrets).
- Server side: the exact sequence of calls for the main request, sync or parallel, and where each answer is validated.
- For each upstream: its timeout, its retries, and the order — does each caller wait longer than the callee's worst case?

## Failure

- For each dependency down, slow, or returning a changed format: who notices, what status and error code go up, what the user sees, and where the technical detail is logged.
- Is any failure turned into a default value (a 0, an empty list)? In this project that is the cardinal sin; show where it's prevented.
- Logs: where do they go (stdout/stderr of the terminal? a file?), and are they kept anywhere? Today every service logs to its terminal only.

## Load and scaling

- What is measured (tool, rate, p95) and what is not. Throughput ceiling if known, and which hop saturates first if known.
- Concurrency limits: uvicorn processes (one by default), the thread pool for `def` endpoints (40), database pool size and timeout, HTTP client connection limits.
- Under overload: do requests queue, time out, or get rejected? What does the user see?
- Several instances of each service behind a load balancer: which services are stateless and scale out; which state breaks (in-memory caches become per-instance; SQLite can't be shared; each instance multiplies DB connections).
- Caches under load: hit path cost; miss path — can many concurrent misses for the same key all call the upstream (cache stampede)? Is the lock around the dict only, or around the fetch?
- External limits: provider rate limits and how calls are kept low.

## Security and sensitive data

- Secrets: where they live (`.env`, GitHub secrets), how they're kept out of git, logs and error messages.
- Sensitive data at rest and in transit; what's exposed publicly; authentication (there is none so far — say so).
- Which ports listen on `127.0.0.1` versus `0.0.0.0`.

## Testing and verification

- What each test suite covers (counts, coverage, which fakes), and what no test covers (end to end, real provider, real browser).
- How each FR and NFR was verified: test, benchmark, manual check, or not at all.
- CI: which services have it and what it runs.
