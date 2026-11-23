# AgroPilot P2 — System Architecture, Engineering Decisions, and Technical Interview Deep Dive

A learning guide to the AgroPilot P2 system: what each part does, how a request travels through the system, how failures are handled, how the irrigation numbers are calculated, how everything was tested, how part of it is checked and deployed to AWS, and what is still missing. It is written to be read on its own, without the repository, and to serve as source material for an educational podcast.

---

## How to read this guide

**Who it is for.** A Python developer who knows basic backend ideas (HTTP, JSON, a database, a web framework) and wants to understand a small distributed system, and the pipeline that deploys part of it, well enough to explain and defend them in a technical presentation. Infrastructure terms are explained in plain words where they first matter, so the guide can be followed without looking anything up.

**What it is based on.** Everything here was checked against the repository on 22 November 2026, on the branch `p2` at commit `b7565b7`. That commit contains the full P2 implementation: the registry, weather, planner and frontend services. P2 has not been merged into `main` yet, and its pull request has not been opened. (`main` is the repository's primary branch, the one treated as production. A pull request is GitHub's request to merge one branch into another. Part 13 explains both.)

Part 13, on CI/CD and the AWS deployment, has a different basis, because that work lives on `main`, not on `p2`. It was checked on the evening of 22 November 2026 against `main` on GitHub at commit `77f7ab0`: the two workflow files, the repository's branch rules, the names of its stored secrets, the history of every recorded workflow run and the logs of the latest ones, all read through GitHub's API. The EC2 server itself was not accessed.

**How claims are labelled.** Seven labels appear throughout, because different kinds of statements deserve different amounts of trust:

- **[P2 spec]** means the official assignment requires it. It is not our choice.
- **[Course tutorial]** means one of the course's official tutorials instructs it, for example the GitHub Actions and AWS tutorials. These are course requirements too, but separate from the P2 specification. They appear mainly in Part 13.
- **[FAO-56]** means a principle or value from the FAO Irrigation and Drainage Paper 56, the standard reference for crop water needs. Our research notes on it are in `services/planner-service/docs/research/fao56.md`.
- **[Project decision]** means a choice we made ourselves, usually recorded with its alternatives and costs in the Engineering Judgment Log, `docs/judgment-log.md`, as an entry such as JL-011.
- **[Verified]** means it was observed: a test that passed, a measurement, or a command whose output was checked. The date is given when it matters.
- **[Documented]** means the project's own documentation, such as a README, states it, but it wasn't checked for this guide. For the EC2 server, checking would need access to the machine.
- **[Not verified]** means it is claimed somewhere or is plausible, but there is no evidence for it in the repository.

**A note on diagrams.** The guide contains a few Mermaid diagrams (Mermaid is a text format that many Markdown viewers draw as a picture). Every diagram is also explained in prose, so nothing depends on seeing it.

**A companion.** The repository also has the P2 Explorer, `docs/presentations/p2-explorer.html`, an interactive Hebrew page. It was built by tracing the real planner code line by line while it ran against the same fake registry and weather services the tests use. Its numbers are real outputs of the engine, but its upstream services are fakes, not live ones.

---

## Part 1 — The system in one picture

### 1.1 The question AgroPilot answers

A grower has a plot of tomatoes or bell peppers watered by drip irrigation. Every morning the grower has one practical question, which the assignment states directly: *"Should I water this plot today, and for how many minutes?"* The assignment's own illustration of an answer is: "Today: water for 38 minutes. Tomorrow: no need. Day 4: 45 minutes."

To answer it, the system needs three kinds of knowledge. It needs facts about the plot: how big it is, what grows on it, when it was planted, what soil it has, and what drip emitters are installed. It needs the weather for the coming days: how much water the sun and wind will pull out of the field, and how much rain will fall. And it needs agronomy: the rules that turn those facts into "irrigate today for so many minutes."

P2 splits that knowledge across separate services, so that each one has a single job.

### 1.2 The components and what each one owns

There are four services of our own, one external provider, and the grower's browser.

**The browser** is where the grower reads the plan. It only ever talks to the frontend.

**The frontend** (`services/frontend`, port 3000) is a Next.js 16 web application written in TypeScript, which is JavaScript with type annotations that are checked before the code runs. Next.js is a framework for React, the JavaScript library for building user interfaces, and it can run part of the application on a server. The frontend uses Next.js's App Router, in which the folder structure under `app/` defines the pages; Tailwind CSS, which styles elements with small ready-made classes; and shadcn/ui, a set of ready-made interface components copied into the project. It renders pages on the server: the Next.js server builds the page and sends the finished result to the browser. Every call to another service lives in `src/lib/` and runs on the Next.js server, never in the browser. It shows farms, plots, today's recommendation and the 7-day plan. It does not calculate any irrigation number.

**The registry-service** (`services/registry-service`, port 8000) is a FastAPI application that stores farms and plots and serves read-only catalogues of crops, soils and drip emitters. It was built in assignment P1 on SQLite. In P2 it gained PostgreSQL support: the same code runs on either database, chosen by a configuration variable.

**The weather-service** (`services/weather-service`, port 8001) is a FastAPI application without a database. It fetches daily forecasts from Open-Meteo, keeps them in memory per geographic grid cell, and serves two numbers per day: ET0 (how much water a reference grass surface loses) and rain. It knows coordinates and dates only, and nothing about farms or crops.

**The planner-service** (`services/planner-service`, port 8002) is a FastAPI application without a database. For one plot, it asks the registry for the plot, its soil and its emitter, asks the weather-service for the forecast at the plot's location, and runs the irrigation engine (`engine.py`). Every number in a plan comes from that engine.

**Open-Meteo** is a free public weather API. Only the weather-service talks to it.

Each service is a separate folder with its own dependencies (`pyproject.toml` and `uv.lock` for the Python services), its own virtual environment and its own `.env` file. `pyproject.toml` lists the packages a service needs and the version ranges it accepts. `uv.lock`, the *lockfile*, records the exact version that was chosen for every package, including the packages those packages need, so a laptop, CI and the server all install the identical set. Services never import each other's code; they talk over HTTP only **[P2 spec]**.

```mermaid
flowchart LR
    B[Browser] -->|pages only| F[frontend<br/>Next.js :3000]
    F -->|farms, plots, health| R[registry-service :8000]
    F -->|plan, health| P[planner-service :8002]
    F -->|health only| W[weather-service :8001]
    P -->|plot, soil, emitter| R
    P -->|forecast| W
    R --> DB[(SQLite file or PostgreSQL)]
    W -->|only when its cache can't answer| O[Open-Meteo]
```

In words: the browser talks only to the frontend. The frontend's server calls the registry for farm and plot lists, the planner for the plan, and all three Python services for their health status. The planner calls the registry and the weather-service. The registry reads its database. The weather-service calls Open-Meteo only when its cache can't answer.

It helps to see what each component knows and what it deliberately does not know:

| Component | Knows | Deliberately doesn't know |
| --- | --- | --- |
| registry-service | Farms, plots, the crop, soil and emitter catalogues | Weather, irrigation rules |
| weather-service | Coordinates, dates, Open-Meteo's API | Farms, plots, crops |
| planner-service | FAO-56 crop profiles, the irrigation formulas | Where the data is stored, Open-Meteo's field names |
| frontend | How to show a plan to a person | How a plan is calculated |

### 1.3 What a plan looks like

The planner's main endpoint is `GET /v1/plots/{id}/plan?days=7`. Its answer, shortened to three of its seven days, looks like this. It is the example from the planner README, and it is exactly what the test `test_plan_reproduces_case_3_end_to_end` checks:

```json
{
  "plot_id": "3f8a6c2e-1b4d-4e5f-9a7b-0c1d2e3f4a5b",
  "crop_id": "tomato",
  "taw_mm": 58.1,
  "threshold_mm": 29.05,
  "initial_soil_water_pct": 100,
  "forecast_fetched_at": "2026-11-21T06:00:00Z",
  "days": [
    { "date": "2026-11-21", "et0_mm": 6.0, "rain_mm": 0.0, "kc": 1.15, "litres": 0,     "run_minutes": 0,    "bucket_level_mm": 51.2,   "stale": false },
    { "date": "2026-11-26", "et0_mm": 5.5, "rain_mm": 0.0, "kc": 1.15, "litres": 36000, "run_minutes": 1440, "bucket_level_mm": 47.425, "stale": false },
    { "date": "2026-11-27", "et0_mm": 6.0, "rain_mm": 0.0, "kc": 1.15, "litres": 0,     "run_minutes": 0,    "bucket_level_mm": 40.525, "stale": false }
  ]
}
```

Each day says how much water the plot needs (`litres`), how long to run the drip system (`run_minutes`, 0 means no irrigation), and how much water is expected to remain in the soil at the end of the day (`bucket_level_mm`). The assignment required `date`, `et0_mm`, `kc`, `litres`, `run_minutes`, `stale` and the end-of-day bucket level **[P2 spec, FR-2.10]**, and left the exact JSON to us. We added `rain_mm`, `taw_mm`, `threshold_mm`, `initial_soil_water_pct` and `forecast_fetched_at` **[Project decision]**, so that a person can check the calculation and see how old the forecast is. Part 8 explains every number.

### 1.4 Five principles that recur

Five ideas appear again and again in this system. Knowing them makes most individual decisions predictable.

1. **Fail closed: never invent a number.** If any input is missing or unusable, the system answers with an error, never with a default or a zero. The assignment calls a forecast of zeros "the worst possible bug in this system" **[P2 spec, FR-2.8]**. Section 4.6 explains why.
2. **One owner per responsibility.** Open-Meteo's field names exist only in `weather-service/provider.py`. The irrigation formulas exist only in `planner-service/engine.py`. The frontend formats numbers and never computes them.
3. **Configuration, not code.** Everything that differs between a laptop and production, such as URLs, timeouts, retry counts, freshness times and credentials, is in each service's `.env` file. That is a plain-text file of `NAME=value` lines, read as if they were *environment variables*, the named values a program receives from the operating system when it starts. It is read by one `config.py` with pydantic-settings, a library that loads environment variables and the `.env` file into a typed Python object and checks every value **[P2 spec]**. A Python service with a missing required variable refuses to start and names the variable.
4. **Exactness where it matters.** The engine calculates with exact fractions and rounds only when it builds the API response, so hand-calculated examples come out exactly (JL-018, JL-019).
5. **Tests that don't need the network.** Every external dependency, whether Open-Meteo, the registry or the weather-service, can be replaced by a fake in tests, and the clock can be controlled. A *fake* is a small stand-in, written for the tests, that answers the way the real service would for the cases a test needs, without any network. Tests are fast and repeatable and never depend on a live service.

### 1.5 Vocabulary

- **ET0 (reference evapotranspiration):** how much water, in mm per day, a standard well-watered grass surface would lose to evaporation and transpiration, given the day's weather. It describes the weather's "thirst", not the crop's.
- **Kc (crop coefficient):** a factor that turns ET0 into a specific crop's water use at its current growth stage. A young plant has a low Kc, a fully grown one a higher Kc.
- **ETc (crop evapotranspiration):** the crop's water use that day, ETc = Kc × ET0, in mm.
- **TAW (total available water):** how much water, in mm, the soil in the root zone can hold for the plant when full. It is the size of the "soil bucket".
- **Threshold:** half of TAW. When the bucket would fall below it during a day, the plan irrigates **[P2 spec]**.
- **Emitter:** a small outlet on a drip line that delivers a fixed flow, measured in litres per hour.
- **Upstream service:** a service that another service depends on. For the planner, the registry and the weather-service are upstream.
- **Grid cell:** a 0.1° × 0.1° square of latitude and longitude. All points in one cell share one cached forecast.
- **Fresh / stale:** a cached forecast is *fresh* for 3 hours. A *stale* forecast is an older cached one, served only when Open-Meteo fails.
- **p95 (95th-percentile latency):** the response time that 95 % of requests beat. It ignores the slowest 5 %, so one slow outlier doesn't dominate, but it still reflects how most users experience the service.
- **MockTransport:** a feature of the HTTP client library (`httpx2`) that sends requests to a Python function instead of the network. Tests use it to fake other services.
- **Dependency override:** a FastAPI feature that lets a test replace a dependency function, such as "what is today's date", with its own version. Section 4.1 explains the idea behind it.

---

## Part 2 — Review question 1: Which sensitive data exists and how do you protect it?

### 2.1 An inventory first

"Sensitive" means anything that causes harm if it leaks or is changed by the wrong person. Before discussing protection, it is worth being precise about what actually exists in this project, because a vague answer ("we protect secrets") is much weaker than an inventory.

| Item | Where it lives | Why it is sensitive |
| --- | --- | --- |
| The PostgreSQL password, inside `DATABASE_URL` | `services/registry-service/.env` (not in Git) | Full access to the registry's "production" database |
| The Open-Meteo API key, `PROVIDER_API_KEY` | `services/weather-service/.env` | Would identify and bill a paid account. It is empty today, because the free tier needs no key |
| The SSH private key and host of the EC2 server | The developer's `~/.ssh`, and GitHub Actions secrets `EC2_SSH_KEY` and `EC2_HOST` used by a deployment workflow on `main` (Part 13) | Shell access to a cloud server, with administrator rights |
| Grower data: farm and plot names, areas, planting dates, plot coordinates | The registry database | Business data. Coordinates reveal exactly where a grower's fields are |
| Service URLs | Each service's `.env`, the frontend's `.env.local` | Low sensitivity, but they describe the internal topology: which services exist and where they listen |
| The test database password | The registry README and CI workflow, committed on purpose | **Not** a secret: a fixed, documented throwaway value for a disposable PostgreSQL container that listens only on 127.0.0.1 |

Just as important is what does **not** exist. There are no user accounts, passwords, emails or payment details, because the system has no login at all. That is a missing control, discussed in Section 2.4, but it also means there is no personal account data to leak.

### 2.2 How secrets are kept out of places they don't belong

Think of a secret as having several ways to escape: through Git, through an AI assistant reading files, through logs and error messages, through API responses, through the network, and through the browser. The project closes each of them separately.

**Out of Git.** The root `.gitignore` ignores `.env` and every `.env.*` file except `.env.example`. The frontend's own `.gitignore` ignores `.env*` except `.env.example`. Each service has a committed `.env.example` listing every variable with a safe example value, and the registry's example uses a `<password>` placeholder **[P2 spec]**. **[Verified 2026-11-22]**: `git ls-files` lists only the four `.env.example` files, and no `.env` or `.env.local` file.

**Out of the AI assistant's view.** `.claude/settings.json` contains `{ "permissions": { "deny": ["Read(**/.env)"] } }`, which stops Claude Code from reading `.env` files **[P2 spec]**. The assignment itself warns that this "is not a security boundary, only a guard against accidents", and that "a real production secret never belongs on a machine where an agent runs commands."

**Out of logs and error messages.** This is where most of the careful work went, because logs are copied, shipped and read by many people:

- The weather-service stores the API key as a pydantic `SecretStr`, which prints as `**********` (test `test_api_key_is_hidden_in_the_settings_repr`).
- When an Open-Meteo call fails, `provider.py` logs only the exception's type, such as `ReadTimeout`, never its message. The reason is subtle: the key travels as a URL query parameter (`apikey`), and some HTTP error messages quote the URL (test `test_failure_log_never_shows_the_api_key`).
- The weather and planner `config.py` files build their own startup error message, because pydantic's default validation error prints every value it read, which would include the API key.
- The registry hides the password and the query string whenever it prints a database URL, for example in the startup line `Database: postgresql, postgresql+psycopg://postgres:***@127.0.0.1:5436/registry` (test `test_described_url_hides_password_and_query`).
- The registry refuses a `DATABASE_URL` with an unencoded `@` in the password and never repeats the URL in that error. An unencoded `@` would push the rest of the password into the host name, which does appear in logs (test `test_unencoded_at_in_password_is_rejected_without_echoing_it`).
- Every SQLAlchemy engine uses `hide_parameters=True`, so a database error in the log never contains the farm or plot names that were bound into the SQL (test `test_unavailable_log_hides_sql_parameter_values`). A wrong PostgreSQL password produces a 503 without the password in the log (test `test_wrong_password_returns_503_without_logging_password`).

**Out of API responses.** When the planner can't use an upstream answer, its 503 body only names the service, such as `"weather-service is unavailable or did not answer in time."`. The technical reason goes to the planner's log. The frontend's error page shows a plain message and a retry button, never a stack trace.

**Off the network.** The documented commands bind every service to `127.0.0.1`. *Binding* is the choice of which network address a server listens on. `127.0.0.1`, called localhost or the loopback address, is a machine's private address for talking to itself, so only programs on the same machine can reach the service. The opposite choice, `0.0.0.0`, means every network interface, including a public one; the course's EC2 setup uses it on purpose (Part 13). The PostgreSQL containers publish their ports only on localhost (`-p 127.0.0.1:5436:5432`). The registry's test suite refuses to run when `TEST_DATABASE_URL` points anywhere other than localhost, and it stops when `.env` defines that variable. This matters because the PostgreSQL test fixtures create and drop databases (a pytest *fixture* is a function that prepares what a test needs and cleans up afterwards). Pointed at a real server, they would be destructive.

**Out of the browser.** All service calls run on the Next.js server. The files in `src/lib/` start with `import "server-only"`, a marker package that makes the build fail if such a file is ever pulled into code that runs in the browser. There are no `NEXT_PUBLIC_` variables, the Next.js mechanism that would copy a value into browser code. The browser never learns a service URL, let alone a key.

### 2.3 Protecting data integrity, not only secrecy

Sensitive data can also be harmed by being changed or corrupted. The registry has several defenses here:

- All SQL is written with bound parameters, for example `WHERE id = :id`, through SQLAlchemy's `text()`. A value is always sent as data, never pasted into the SQL string. This is the standard defence against *SQL injection*, an attack in which a crafted input, such as a plot name containing `'; DROP TABLE plots; --`, changes what the SQL does. A test stores SQL text as a plot name and checks that it is saved as plain text (`test_sql_in_a_name_is_stored_as_plain_text`).
- The only dynamic SQL, the `SET` clause of a PATCH, accepts column names only from a fixed allow-list (`test_update_refuses_a_column_name_outside_the_allow_list`).
- Request bodies are validated strictly by Pydantic: unknown fields are rejected, numbers must be real positive numbers, latitude and longitude must be in range, and a planting date must be a valid date that is not in the future.
- The database enforces foreign keys, which are columns whose value must match an existing row in another table (a plot's `farm_id` must name a real farm), and a unique plot name per farm.
- NUL characters are rejected in every string input, because PostgreSQL can't store them (JL-009).

One privacy-friendly side effect is worth mentioning, although it was not designed as a security control. The weather-service sends Open-Meteo the *centre of the grid cell*, not the plot's exact coordinates (test `test_provider_is_asked_about_the_cell_centre`). An outside provider therefore learns only an area of roughly 11 by 9.5 km, not a grower's exact field.

### 2.4 Local credentials versus production secrets, and what is missing

The "production" database in P2 is a PostgreSQL 17 Docker container on the developer's laptop (`agropilot-pg`). A *container* runs a program, here the PostgreSQL server, isolated from the rest of the machine, together with everything that program needs, started from a ready-made package called an *image*. The instructor confirmed that Docker is sufficient for P2 (`docs/instructor-clarifications.md`). Note that "production" has two meanings in this project: for the P2 specification it is this local database, and for the course's deployment tutorial it is the EC2 server that runs the registry (Part 13). The README creates it with `read -rs PG_PASSWORD`, so the password is typed without being shown or stored in the shell history, and the password then lives only in the registry's git-ignored `.env`. This is a reasonable practice for a course environment. It is not production-grade secret management.

The honest list of missing controls:

- **No authentication or authorization** on any service. Anyone who can reach the registry's port can create, change and delete farms and plots.
- **No TLS** between services. TLS is the encryption layer behind HTTPS; without it, anyone who can see the network traffic can read and change it. Everything here is plain HTTP on localhost, and the EC2 registry is documented as plain HTTP on port 8000 (Part 13).
- **No secrets manager and no rotation.** Secrets are plain text in `.env` files on disk. A secrets manager, such as AWS Secrets Manager, stores secrets encrypted, controls who may read each one and logs every read. Rotation means replacing a secret regularly, so a leaked copy stops working.
- **No least-privilege database user.** The documented URL template connects as the `postgres` superuser, the all-powerful administrator account. A least-privilege user may do only what the application needs, such as reading and writing the registry's five tables, so a leaked password couldn't drop the database or create new users.
- **No rate limiting** on our own APIs.
- **No audit log** of who changed what.
- **Deployment:** on `main` (not yet on `p2`), a GitHub Actions workflow, `deploy-registry.yaml`, deploys the registry to an Ubuntu EC2 server, a virtual machine rented from Amazon Web Services, over SSH, an encrypted remote terminal. Its third-party action, `appleboy/ssh-action@v1.2.5`, is pinned to a version tag, which is a movable label. The CI workflow (continuous integration: the automated checks on every pull request) instead pins every action to a full commit SHA, the fixed fingerprint of one exact version. A tag can be moved to different code, and this action has access to the SSH key secret, so the deploy workflow is the weaker of the two. The repository doesn't contain the EC2 server's systemd unit, its service definition for the Linux service manager, or its `.env`, so its network exposure and which database it uses can't be verified here **[Not verified]**. Part 13 explains these terms and covers the deployment and its security in detail.

> **Interview follow-up:** "Is the deny rule in `.claude/settings.json` a security control?"
>
> **Model answer:** No. It stops the coding assistant from reading `.env` by accident, but any process running as the same user can still read the file, and the assistant can still run shell commands. The real protection is that production secrets shouldn't be on that machine at all. The assignment says the same thing.

---

## Part 3 — Review question 2: Explain the user flow from the browser to the services and back.

### 3.1 User flow versus system flow

These two review questions sound alike but ask different things. The **user flow** is the journey of a person: which pages they open, what they click, and what they see. The **system flow** (Part 4) is the journey of the data: which component calls which, in what order, and what happens when a call fails. A good answer to this question stays at the person's level and points to the system flow for the internals.

### 3.2 Step one: the farm list

The grower opens `http://localhost:3000/`. The browser sends one request, `GET /`, to the Next.js server, and from then on talks only to that server.

On the server, two independent pieces of the page start at once. The shared layout's status line calls `GET /health` on the registry, the weather-service and the planner, in parallel, with a 2-second timeout each. A health endpoint is a cheap URL that answers 200 whenever the process is running, so a person or a monitoring tool can check that the service is alive. A service counts as "up" if it answers 200 within 2 seconds. At the same time, the page's farm list calls the registry twice in parallel, `GET /v1/farms` and `GET /v1/plots`, with a 5-second timeout, and groups the plots under their farms on the server.

Both pieces sit inside React `<Suspense>` boundaries. `<Suspense>` is a React component that wraps a part of the page that has to wait for data. While that part waits, React shows a fallback, a placeholder, and carries on with the rest of the page. The Next.js configuration turns on Cache Components, a Next.js 16 mode in which nothing is cached unless the code asks for it, and any part of a page that reads uncached data must sit inside Suspense, so the rest of the page can be sent without waiting for it. The practical effect is *streaming*: the server sends the page in pieces over one open response, instead of waiting until everything is ready. The browser receives the page shell immediately, with "Checking services…" and "Loading farms…" placeholders, and each part replaces its placeholder as soon as its data arrives. A slow health check doesn't delay the farm list.

The grower sees every farm with its plots **[P2 spec, FR-2.15]**. Each plot shows its crop and area and links to `/plots/{id}`. The status line shows, in words and with a coloured dot, whether each service is up **[P2 spec, FR-2.19]**.

### 3.3 Step two: the plot page

The grower taps a plot. The browser asks the Next.js server for `/plots/{id}`. When Next.js navigates inside the app, the browser downloads a server-rendered page payload rather than a full HTML page. That payload, called the React Server Components payload, is a compact description of the rendered page, which the browser's copy of React turns into the screen. Either way it comes from the Next.js server, never from a backend service.

On the server, two calls start in parallel. `getPlot(id)` asks the registry for the plot, only to show the page header: the plot's name, crop and planting date. `getPlan(id)` asks the planner for `GET /v1/plots/{id}/plan?days=7`, with a 25-second timeout and no caching. The planner then does all the work described in Part 4.

The page shows **today's recommendation first, big and clear** **[P2 spec, FR-2.16]**. If today's `run_minutes` is above zero, a blue panel says "Water for 1,440 minutes" and how many litres that is for the whole plot. Otherwise a green panel says "No irrigation today" and "The soil holds enough water for the crop today." Under it, a bar shows the soil water expected tonight against the line where watering starts, for example "Soil water tonight 51.2 of 58.1 mm. Watering starts below 29.05 mm." A sentence always states the assumption the plan started from: "Assumes the soil starts today full (100%). Default assumption, not a measurement."

Below that, the 7-day plan appears. On screens narrower than 640 px it is a list, so a 375 px phone doesn't scroll sideways **[P2 spec, NFR-2.8]**. On wider screens it is a table. The technical labels Minutes, ET0, Rain, Kc, Soil water and Stale forecast open a one-sentence explanation when clicked, tapped or opened with the keyboard. If a forecast is stale, every affected day carries a "Stale forecast" badge, and a note says when the forecast was fetched **[P2 spec, FR-2.17]**.

### 3.4 Step three (optional): a simulation

Because the system can't measure the soil, every plan starts from an assumption (Section 8.12). Below the plan, a small form lets the grower try another starting level. It is a plain HTML form that only sets `?soil=40` in the page URL. The page checks the value is a whole number from 0 to 100, passes it to the planner as `initial_soil_water_pct`, and shows the result with a "Simulation" badge and the note "Simulation result, not a field-verified irrigation recommendation. Check the soil before you water." If the planner's answer doesn't echo the same value back, for example from an older planner, the page shows a message instead of numbers labelled with a level the planner didn't use.

### 3.5 The point to stress: the frontend doesn't calculate

The frontend's job is presentation. It never computes litres, minutes, Kc or bucket levels. The only arithmetic it does is for display: the soil bar's width as a percentage of TAW, and two comparisons in the simulation warning ("does this start lie below the watering line?", "does any day reach 1,440 minutes or an empty bucket?"), which use only values the planner returned.

Keeping the frontend on the server has several benefits. The service URLs stay private. Every timeout is set in one place. There are no cross-origin (CORS) questions: a browser won't let a page read answers from a different *origin*, meaning a different scheme, host or port, unless that server explicitly allows it with CORS headers, and here the browser only ever talks to the Next.js server. And services that have no authentication are never exposed to every browser on the internet.

> **Interview follow-up:** "Does the browser ever receive the planner's JSON?"
>
> **Model answer:** Not directly. The planner's JSON goes to the Next.js server, which turns it into HTML and React's server-component payload. The browser receives the rendered page. It never knows the planner exists.

---

## Part 4 — Review question 3: Explain the system flow from the frontend to the services and back. Not only the happy path, explain what happens and how when an error occurs.

### 4.1 The happy path, step by step

This walkthrough follows one real request with real data from the repository: the plot used by the planner's tests and README. It has the values of the seed plot "West block" (the *seed data* is the fixed set of demo rows that the setup scripts load into a new database): a 1,500 m² tomato plot on sand, rows 1.5 m apart, an emitter every 0.4 m, emitters of 0.6 litres per hour, at latitude 31.25, longitude 34.79. The test fixture plants it 99 days before 21 November 2026, on 14 August 2026, so 21 November is day 100 of its season, in mid-season. The forecast is the one from worked example Case 3. (In the real seed database, West block was planted in February and is past its season, so a live request for it gets a 409. Section 4.3, scenario C, explains why.)

```mermaid
sequenceDiagram
    participant F as frontend (Next.js server)
    participant P as planner-service
    participant R as registry-service
    participant W as weather-service
    participant O as Open-Meteo
    F->>P: GET /v1/plots/{id}/plan?days=7
    P->>P: validate id, days, initial_soil_water_pct
    P->>R: GET /v1/plots/{id}
    R-->>P: 200 plot
    P->>P: early season check (UTC date − 1, same, + 1)
    P->>R: GET /v1/soils/sand
    R-->>P: 200 soil
    P->>R: GET /v1/emitters/dripnet-pc-0.6
    R-->>P: 200 emitter
    P->>W: GET /v1/forecast?lat=31.25&lon=34.79&days=7
    alt fresh forecast in the cache
        W-->>P: 200 cached forecast, stale false
    else no fresh forecast
        W->>O: 7 days of ET0 and precipitation for the cell centre
        O-->>W: daily values
        W-->>P: 200 new forecast, stale false
    end
    P->>P: final season check on the forecast dates, engine, rounding
    P-->>F: 200 plan
```

In words, in chronological order:

1. **The frontend calls the planner.** `getPlan` sends `GET http://127.0.0.1:8002/v1/plots/3f8a6c2e-1b4d-4e5f-9a7b-0c1d2e3f4a5b/plan?days=7`.
2. **The planner validates the request** before doing anything else. FastAPI checks that the plot id is a UUID (a universally unique identifier: a 128-bit random value written as 36 characters, like the id above), `days` is a whole number from 1 to 7, and the optional `initial_soil_water_pct` is a whole number from 0 to 100 (default 100). If any check fails, the answer is 422 and no other service is called.
3. **The planner gets today's UTC date** from a small dependency function, `utc_today`. This is FastAPI's form of *dependency injection*. The endpoint doesn't call `date.today()` itself; it declares, with `Depends`, that it needs the value `utc_today` returns, and FastAPI calls that function and hands the result to the endpoint as a parameter. Because FastAPI does the handing over, a test can tell it to hand over something else, such as a fixed date, without changing the endpoint. The registry's endpoints receive their database connection the same way (Section 7.4). One word of caution: "dependency" has three meanings in this guide. It can be a FastAPI dependency like this one, a package listed in `pyproject.toml`, or a service that another service relies on. The context always makes clear which.
4. **The planner asks the registry for the plot**: `GET /v1/plots/{id}`. Inside the registry, the router calls the repository, which runs `SELECT ... FROM plots WHERE id = :id` inside one database transaction opened for this request, and returns the row as JSON. (A *transaction* groups database operations so that they take effect all together or not at all; Section 7.4.) The planner receives `crop_id "tomato"`, `planting_date "2026-08-14"`, `soil_id "sand"`, `emitter_id "dripnet-pc-0.6"`, `area_m2 1500.0`, `row_spacing_m 1.5`, `emitter_spacing_m 0.4`, `lat 31.25`, `lon 34.79`. The planner's `upstream.py` checks every field (Section 6.2) and converts every number into an exact fraction.
5. **The early season check.** The planner looks up the tomato profile (a 180-day season) and asks whether the plan could possibly be in season. It doesn't yet know the plot's local date, only its own UTC date, so it tries the UTC date minus one day, the same day, and plus one day (Section 8.6). Here the plan covers season days 100 to 106, well inside 1 to 180, so it continues.
6. **The planner asks for the soil**: `GET /v1/soils/sand` returns `available_water_mm_per_m: 83`.
7. **The planner asks for the emitter**: `GET /v1/emitters/dripnet-pc-0.6` returns `flow_lph: 0.6`.
8. **The planner asks the weather-service for the forecast**: `GET /v1/forecast?lat=31.25&lon=34.79&days=7`. Inside the weather-service, the point falls into grid cell (312, 347), whose centre is (31.25, 34.75). If the cache has a forecast for that cell that is younger than 3 hours and still covers 7 days from today, it answers at once. Otherwise it calls Open-Meteo for the cell centre, checks the answer strictly, stores it, and answers.
9. **The planner checks the forecast**: `stale` must be a real true or false, `fetched_at` a valid timestamp, there must be exactly 7 days with consecutive dates, and every ET0 and rain value must be a finite number of at least 0. Here ET0 is 6.0, 6.0, 5.0, 6.0, 6.0, 5.5, 6.0 mm and rain is 0, 0, 5, 0, 0, 0, 0 mm.
10. **The engine runs.** It first repeats the season check on the forecast's own dates, which are the plot's local dates. Then it calculates TAW, the threshold and the drip system's flow, and walks the soil bucket day by day. Days 1 to 5 need no irrigation. Day 6 irrigates 36,000 litres over 1,440 minutes, limited by the 24-hour cap (Part 8).
11. **The router rounds the output** (Kc and mm values to 3 decimals, litres and minutes to whole numbers, .5 always rounding up) and returns the plan JSON shown in Section 1.3.
12. **The frontend renders it.** Today needs no water, so the green panel says "No irrigation today". The list or table shows day 6 as "1,440 min, 36,000 L".

The order and parameters of these calls aren't just described; they are tested. `test_plan_asks_registry_then_weather_for_the_plot_point` checks that the registry received exactly `/v1/plots/{id}`, `/v1/soils/sand` and `/v1/emitters/dripnet-pc-0.6` in that order, and that the weather-service received one request with `lat=31.25`, `lon=34.79` and `days=7`.

What goes in and out at each hop:

| Hop | Request | Essential response |
| --- | --- | --- |
| frontend → planner | `GET /v1/plots/{id}/plan?days=7` | The plan |
| planner → registry | `GET /v1/plots/{id}` | crop, planting date, soil id, emitter id, area, spacings, lat, lon |
| planner → registry | `GET /v1/soils/sand` | `available_water_mm_per_m: 83` |
| planner → registry | `GET /v1/emitters/dripnet-pc-0.6` | `flow_lph: 0.6` |
| planner → weather | `GET /v1/forecast?lat=31.25&lon=34.79&days=7` | `fetched_at`, `stale`, and per day `date`, `et0_mm`, `rain_mm` |
| weather → Open-Meteo (cache miss only) | `latitude=31.25&longitude=34.75&daily=et0_fao_evapotranspiration,precipitation_sum&forecast_days=7&timezone=auto` | `daily` arrays, `daily_units`, `utc_offset_seconds` |

### 4.2 Two error dialects, translated at the boundary

The services don't share one error format, and that is deliberate. The registry, built in P1, uses FastAPI's default error bodies, such as `{"detail": "Plot not found"}`. The instructor confirmed that this is enough for P1 (`docs/instructor-clarifications.md`). The weather-service and the planner use `{"code": "...", "detail": "..."}`, with the codes the P2 assignment names: `VALIDATION`, `NOT_FOUND`, `UNAVAILABLE` and `UPSTREAM_UNAVAILABLE`, plus our own `PLOT_OUT_OF_SEASON` **[P2 spec; Project decision JL-020]**.

The planner translates every registry or weather error into its own vocabulary before answering, so the frontend has to understand only one dialect: the planner's. This pattern, translating errors at every service boundary, comes up again in Section 4.4.

### 4.3 The failure scenarios

For each failure: what triggers it, which component notices, what happens inside, the response, why it was designed that way, and which test proves it.

First, a short reminder of the HTTP status codes that appear below. A code in the 400s says the *caller* asked for something wrong; a code in the 500s says something failed on the *server's* side. **422** Unprocessable Content means the request was understood, but its values are invalid. **404** Not Found means the thing asked for doesn't exist. **409** Conflict means the request is valid but clashes with the current state of the thing it is about. **500** Internal Server Error means a bug. **503** Service Unavailable means a temporary problem, so trying again later may work.

**A. Invalid query parameters.**
*Trigger:* `days=8`, `days=abc`, `days=2.5`, an empty `days`, a plot id that isn't a UUID, or an `initial_soil_water_pct` of -1, 101, 50.5 or text.
*Detected by:* FastAPI's request validation in the planner, before the endpoint function runs.
*Inside:* a custom exception handler in `main.py`, a function FastAPI calls whenever a given exception escapes an endpoint, turns FastAPI's `RequestValidationError` into the planner's format and lists every invalid parameter.
*Response:* `422 {"code": "VALIDATION", "detail": "days: Input should be less than or equal to 7"}`.
*Why:* a bad request should fail fast and cheaply. Calling other services for a request that will be refused anyway wastes their capacity **[P2 spec, FR-2.12]**.
*Tests:* `test_bad_days_is_422_and_calls_no_service`, `test_plot_id_that_is_not_a_uuid_is_422_and_calls_no_service` and `test_bad_starting_soil_water_is_422_and_calls_no_service`. Each checks the status and code, and also that the fake registry and weather received no request at all. The weather-service validates its own parameters the same way (`test_invalid_query_returns_422_validation`, `test_every_invalid_parameter_is_listed`).

**B. Unknown plot.**
*Trigger:* a valid UUID that the registry doesn't know.
*Detected by:* the registry answers 404. The planner's `get_plot` sees the 404 and raises `PlotNotFound`.
*Response:* `404 {"code": "NOT_FOUND", "detail": "Plot not found."}` **[P2 spec, FR-2.12]**.
*Why:* this is a genuine "doesn't exist", not an outage, so it gets its own status. Only the plot lookup treats a registry 404 this way (see scenario E for the soil and emitter).
*Test:* `test_unknown_plot_is_404_and_weather_is_not_called`.

**C. The plot is outside its growing season.**
*Trigger:* the plan would include a day before planting or after the season's last day. Tomato has a 180-day season and bell pepper 210 days.
*Detected by:* the planner, twice. The early check runs right after the plot is read. The final check runs inside the engine on the forecast's dates.
*Inside:* FAO-56 gives crop coefficients only from planting to harvest. Rather than invent a Kc for other days, the planner refuses the whole request (JL-020). A clearly out-of-season plot is refused before the soil, emitter and weather calls, even when the weather-service is down. A plot within a day of a season boundary is decided only on the forecast's real dates, so a 409 is never based on a date the field isn't on.
*Response:* `409 {"code": "PLOT_OUT_OF_SEASON", "detail": "The plot is outside its growing season."}`.
*Why:* the request is valid, but the plot's current state doesn't allow a plan, which is what 409 Conflict means. Any plan for those days would contain invented numbers.
*Tests:* `test_clearly_out_of_season_plot_is_409_without_soil_emitter_or_weather_calls` (with a weather-service that would fail if called), `test_planner_a_day_ahead_of_the_field_on_the_last_season_day_still_plans`, `test_planner_a_day_behind_the_field_on_the_planting_day_still_plans`, `test_forecast_dates_outside_the_season_are_409_after_the_weather_call`, and in the engine `test_b6_season_boundaries` and `test_kc_is_never_invented_outside_the_season`.
*Practical consequence* **[Verified 2026-11-22 with the engine]**: all four seed plots are out of season for a 7-day plan from 22 November 2026, on season days 267, 225, 281 and 206. A live demonstration therefore needs in-season demo plots added through `POST /v1/plots`, while the seed data stays unchanged (JL-015).

**D. The registry is unavailable.** A refused connection, no answer within 3 seconds, or any status other than 200, including the registry's own `503 Database unavailable`, becomes `503 {"code": "UPSTREAM_UNAVAILABLE", "detail": "registry-service is unavailable or did not answer in time."}`, and the weather-service is never called. Part 6 covers this in depth.

**E. The registry answers, but the answer is unusable.** A body that isn't JSON, a JSON list instead of an object, a missing field, a number that is null, text, true or false, NaN or infinite, or an area, spacing, flow or soil value that isn't above zero: each becomes the same 503 naming the registry. A 404 for the plot's *soil* or *emitter* is also treated as a registry fault, not as a 404 for the caller, because the registry's own foreign keys make it impossible for a plot to reference a soil that doesn't exist. Part 6 covers this, including the `latitude` instead of `lat` case.

**F. The weather-service is down, or Open-Meteo is down with no usable cached forecast.**
*Trigger:* the weather-service can't be reached, doesn't answer within the planner's 12-second timeout, or answers `503 UNAVAILABLE` because Open-Meteo failed and it has no forecast young enough to serve as stale.
*Detected by:* the planner's `upstream.py`. Any non-200 status, or an HTTP error such as a timeout or a refused connection, raises `UpstreamUnavailable("weather-service", ...)`.
*Response:* `503 {"code": "UPSTREAM_UNAVAILABLE", "detail": "weather-service is unavailable or did not answer in time."}` **[P2 spec, FR-2.14]**.
*Why:* without a forecast, no number in the plan can be calculated honestly. A plan of zeros would say "no water needed".
*Test:* `test_weather_failure_is_503_naming_weather`, parametrized over 17 different bad answers: pytest runs the same test function once for each answer in a list, and reports each run separately.

**G. The weather data is missing, malformed or incomplete.** There are two lines of defence. First, the weather-service checks Open-Meteo's body: required fields, `mm` as the unit, exactly 7 days starting at the point's local today, and finite non-negative values. One bad day rejects the whole forecast (Part 5). Second, the planner checks the weather-service's answer again: the right number of days, consecutive dates, real numbers, a boolean `stale`, a valid timestamp. A forecast with a null ET0, a negative rain value, text where a number belongs, a missing day, or even NaN and Infinity (which Python's JSON parser accepts) gets a 503 (`test_weather_failure_is_503_naming_weather`, `test_nan_or_infinite_weather_value_is_503`). Checking twice may look redundant, but each service defends its own *contract*, the agreed shape and meaning of the requests it accepts and the answers it gives: the planner can't assume the weather-service is bug-free.

**H. A stale forecast: a degraded success, not a failure.**
*Trigger:* Open-Meteo fails, but the weather-service has a forecast for the cell that is at most 24 hours old and still covers the requested days.
*Inside:* the weather-service answers 200 with the cached numbers, the original `fetched_at` and `"stale": true`. The planner calculates the plan normally and marks every day `stale: true`, because the weather-service marks the forecast as a whole **[P2 spec, FR-2.13]**.
*What the user sees:* a "Stale forecast" badge next to each affected day, and a note: "A newer weather forecast couldn't be fetched, so days marked 'Stale forecast' use the one from 21 Nov, 06:00 UTC."
*Test:* `test_stale_forecast_still_plans_with_every_day_stale` checks that all seven days are stale, that `forecast_fetched_at` is the old timestamp, and that the run minutes are still those of Case 3.

**I. Timeouts and retries: the timeout ladder.** Each caller waits a little longer than the worst case of the service it calls:

| Caller → callee | Timeout | Retries |
| --- | --- | --- |
| weather → Open-Meteo | 3 s per attempt | 1 attempt + 2 retries, no wait between them: about 9 s worst case |
| planner → weather | 12 s | none, because the weather-service already retries |
| planner → registry | 3 s per call, three calls in sequence | none |
| frontend → planner | 25 s | none |
| frontend → registry | 5 s | none |
| frontend → each `/health` | 2 s | none |

The key relationship is 9 s < 12 s. If the planner's weather timeout were shorter than the weather-service's own worst case, the planner would give up just before the weather-service returned a perfectly good stale forecast. Likewise, 3 × 3 s for the registry calls plus 12 s for the weather call is 21 s, below the frontend's 25 s. One caveat **[Not verified]**: in `httpx`, whose API `httpx2` keeps, a timeout number applies separately to each phase of a request (connecting, writing, reading, and waiting for a free connection from the client's pool of reusable connections), not to the request as a whole. So these totals are the expected worst cases, not hard guarantees.

**J. A crop the planner doesn't know.** If the registry ever returned a `crop_id` other than `tomato` or `bell-pepper`, the planner raises an error and answers 500 (`test_unknown_crop_is_a_500_not_a_plan`). This is intentional: it would mean the planner and the registry's catalogue disagree, which is a bug to fix, not a situation to paper over with an invented Kc.

**K. The planner itself is down or answers nonsense.** Only the frontend can notice this. If the planner can't be reached within 25 seconds, `getPlan` returns the code `PLANNER_UNREACHABLE`. If it answers with a body that is neither a plan nor a `{code, detail}` error, `getPlan` returns `UNEXPECTED`.

**L. The frontend is misconfigured.** If `REGISTRY_URL`, `WEATHER_URL` or `PLANNER_URL` is missing, the server throws an error at request time, the Next.js error page shows "Something went wrong" with a "Try again" button, and the server log names the missing variable.

### 4.4 How a failure travels through the system

The most instructive case follows a failure from the bottom of the stack to the grower's screen.

Suppose Open-Meteo is down and the weather-service has no recent forecast for the plot's cell. The weather-service tries once and retries twice, each attempt waiting up to 3 seconds. It then answers `503 {"code": "UNAVAILABLE", "detail": "Weather provider unavailable and no usable cached forecast."}` with the header `Retry-After: 60`, a standard HTTP header that tells the client how many seconds to wait before trying again. The planner sees a non-200 status from the weather-service and raises `UpstreamUnavailable("weather-service", "status 503")`. Its handler logs `Upstream failure: weather-service: status 503` and answers `503 {"code": "UPSTREAM_UNAVAILABLE", "detail": "weather-service is unavailable or did not answer in time."}`. The frontend recognizes the code and shows "No plan right now. weather-service is unavailable or did not answer in time. Try again in a minute."

At every boundary, the lower-level error is translated into the vocabulary of the level above, and the technical detail stays in that service's log. Two consequences are worth noticing:

- The planner doesn't forward the weather-service's `Retry-After` header, and the assignment doesn't require it. The frontend's "Try again in a minute" happens to match the 60 seconds.
- The message names the weather-service even though the real culprit is Open-Meteo. Meanwhile the status line may say "weather-service up", because `/health` only shows that the process answers, not that its provider works. Both statements are true, but a user may find them confusing. A real product might add a second health check that reports dependencies, often called a *readiness* check, as opposed to the *liveness* check that only shows the process is alive.

The registry has the same pattern one level down. If its database is down, the registry answers `503 {"detail": "Database unavailable"}` with `Retry-After: 5`, and the planner turns that into the 503 naming the registry. The registry's `/health` still returns 200 in that case, so the status line again shows the service as up.

### 4.5 What the grower sees

The frontend's `plan-error.tsx` maps each planner code to a message **[P2 spec, FR-2.18]**:

| Planner code | Title | Message |
| --- | --- | --- |
| `UPSTREAM_UNAVAILABLE` | No plan right now | The planner's detail, for example "weather-service is unavailable or did not answer in time.", then "Try again in a minute." |
| `PLANNER_UNREACHABLE` (frontend-only) | No plan right now | "planner-service is unavailable. Try again in a minute." |
| `PLOT_OUT_OF_SEASON` | No plan for this plot | "The plot is outside its growing season: it isn't planted yet, or the 7 days run past the end of the season." Shown as information, not as an error |
| `NOT_FOUND` | Plot not found | "There is no plot with this address.", with a link back to all farms |
| `VALIDATION` | Plot not found | "This isn't a valid plot address." The only way a user can cause a `VALIDATION` error is a malformed plot id in the URL, because the frontend always sends `days=7` and checks the simulation value itself |
| anything else | No plan right now | "The planner answered with an unexpected error (HTTP 500). Try again in a minute." |

On the farm list, a registry failure shows "Can't load the farms. registry-service is unavailable. Check that it is running, then reload the page." The rule throughout is "never a blank page and never a stack trace" **[P2 spec, FR-2.18]**.

### 4.6 Why missing data must never silently become zero

This is the central safety idea of the system, so it is worth slowing down.

Imagine the weather-service received a forecast with ET0 missing for today and "helpfully" filled in 0. The planner would calculate ETc = Kc × 0 = 0 mm: the crop uses no water today. The bucket wouldn't drop, so the plan would say "No irrigation today." For the Case 3 plot, the real ETc on a 6 mm day is 6.9 mm, which is 10,350 litres over 1,500 m². That much water would silently go missing from the plan, on a day that looks completely normal on screen.

The asymmetry is the key insight. An error message is *visibly* wrong: the grower knows something is broken and checks the field. A zero is *invisibly* wrong: "no water needed" is a perfectly ordinary answer, indistinguishable from a real one. The assignment puts it bluntly: "A forecast of zeros looks like 'no water needed'. That is the worst possible bug in this system" **[P2 spec, FR-2.8]**.

So the system *fails closed* everywhere. The weather-service never fills in a missing day or value. The planner never defaults a missing plot field. The engine rejects non-positive areas, spacings and flows, and negative ET0 or rain. The engine even refuses plain Python floats as inputs, because they would bring back rounding errors (Section 8.13). When the system can't be right, it says so.

---

## Part 5 — Review question 4: Why do we need the weather service? Why not talking with Open-Meteo directly from the frontend? How did you test this service?

### 5.1 Why a dedicated weather-service

The assignment's architecture puts the weather-service between the planner and Open-Meteo **[P2 spec]**, but the reasons are worth being able to argue on their own.

**The calculation happens in the planner, so the forecast is needed on the server anyway.** If the browser fetched the forecast, it would have to send the numbers to the planner, and the planner would have to trust ET0 and rain values supplied by a browser. Anyone could then submit made-up weather. The integrity of the plan would depend on the client. Fetching on the server keeps the data path trustworthy.

**One cache for everyone.** A browser can cache only for its own user. The weather-service caches once per grid cell for all plots and all users, which reduces calls to Open-Meteo dramatically (Part 11).

**One place for resilience rules.** Retries, timeouts, freshness, the stale fallback and the 24-hour limit are written once, in one service, and tested once.

**One place for validation.** The rule "never invent a number" (FR-2.8) is enforced once, at the only place where provider data enters the system.

**A narrow, provider-neutral contract.** The rest of the system sees only `date`, `et0_mm` and `rain_mm`. Open-Meteo's field names, such as `et0_fao_evapotranspiration`, exist only in `provider.py` **[P2 spec]**. Switching to another provider, or to Open-Meteo's paid endpoint, changes one module and some configuration, not the planner.

**Secrets stay on the server.** A paid plan needs an API key. Any key used by browser code is public by definition.

**Testability.** Because Open-Meteo sits behind one HTTP client in one service, tests can replace it with a fake and control the clock (Section 5.6).

**Consistency with the frontend's own rule.** The browser never calls any service directly.

### 5.2 What is asked from Open-Meteo, and why

The weather-service calls:

```
GET https://api.open-meteo.com/v1/forecast?latitude=…&longitude=…
    &daily=et0_fao_evapotranspiration,precipitation_sum&forecast_days=7&timezone=auto
```

| Our field | Open-Meteo daily variable | Unit | Meaning |
| --- | --- | --- | --- |
| `et0_mm` | `et0_fao_evapotranspiration` | mm | FAO-56 Penman-Monteith reference evapotranspiration, daily sum |
| `rain_mm` | `precipitation_sum` | mm | All precipitation: rain, showers and snowfall as water |
| `date` | `daily.time` | ISO date | The local day at the point |

Three choices deserve a sentence each. `precipitation_sum` is used rather than `rain_sum` because all water that reaches the soil counts for the soil bucket, and `rain_sum` leaves out snowfall **[Project decision]**. `timezone=auto` makes Open-Meteo return days according to the point's local calendar, so "today" is the field's today, not the server's. And the service always asks for 7 days, the most any request can ask for, so one cached forecast can answer requests for any number of days.

Note that ET0 is *calculated by Open-Meteo*, not by us. We trust the provider's Penman-Monteith calculation and don't check it against weather station data. That is a reasonable dependency, but it is a dependency.

### 5.3 How the provider's answer is checked

`provider.py`'s `parse_forecast` treats Open-Meteo as untrusted input. A forecast is refused if any of these is true:

- A required field is missing: `daily`, `daily_units`, the ET0 or rain arrays, the dates, or `utc_offset_seconds`.
- A unit isn't `mm`. This catches, for example, a provider configured for inches.
- The UTC offset isn't a whole number.
- There aren't exactly 7 values in each array.
- A value isn't a finite number of at least 0. Null, text, booleans, negative numbers and NaN are all refused.
- A date isn't an ISO date.
- The dates aren't exactly today, tomorrow and so on at the point's local date. A shifted, missing or reordered day is refused.

**One bad value rejects the whole forecast.** The service never answers with six good days and a gap, and never patches the gap.

### 5.4 The grid-cell cache

A cache answers repeated requests without asking the provider again. The design question is "what counts as the same request?" Two plots 200 metres apart have practically the same weather, so caching by exact coordinates would waste provider calls. The assignment specifies the answer: "Two requests for points in the same 0.1° grid cell share one forecast" **[P2 spec, FR-2.5]**.

The cell of a point is `(floor(lat × 10), floor(lon × 10))`. The plot at (31.25, 34.79) is in cell (312, 347), which covers latitudes 31.2 to 31.3 and longitudes 34.7 to 34.8. The forecast is fetched for the cell's centre, (31.25, 34.75), so every point in the cell gets exactly the same forecast, whichever point happened to ask first. At this latitude a 0.1° cell is roughly 11 km north to south and 9.5 km east to west.

Two details show the care taken at the edges:

- **Decimal, not float, for the cell.** In floating-point arithmetic, 31.3 × 10 is 312.99999999999994, which would put a point at exactly 31.3 into the wrong cell. `grid_cell` uses `Decimal(str(lat))`, the number as it was written, so 31.3 lands in cell 313 (`test_grid_cell`).
- **The poles and the date line.** A latitude of exactly 90 would be cell 900, whose centre, 90.05, isn't a valid latitude. The code limits the cell index, so `lat = 90` joins the cell below it and the centre sent to the provider is always valid (`test_cell_centre_is_a_valid_coordinate_at_the_poles_and_the_date_line`).

The cache is a Python dictionary in the service's memory, guarded by a `threading.Lock`. FastAPI runs plain `def` endpoints in a *thread pool*. A thread is an independent line of execution inside one process. A thread pool is a set of threads kept ready, and each incoming request is handed to a free one, a *worker thread*. Several requests can therefore run at the same moment and touch the cache together (`test_cache_is_safe_to_use_from_several_threads`). The lock lets only one thread at a time run the code it guards, so two threads can't change the dictionary in the middle of each other's update. A restart empties the cache, and the assignment explicitly allows that **[P2 spec]**. Two simultaneous requests for a cell without a fresh forecast may both call the provider. The lock protects the dictionary's consistency; it doesn't merge duplicate fetches. The README documents this.

### 5.5 Freshness and the stale limit

A cached forecast is **fresh** for 3 hours (`FORECAST_FRESH_HOURS`). While it is fresh, the provider isn't called **[P2 spec, FR-2.5]**. One subtlety: after local midnight, a forecast fetched yesterday evening is still fresh by age but has one day fewer from today. If it can't cover the request, a new forecast is fetched (`test_after_local_midnight_a_fresh_forecast_with_too_few_days_is_fetched_again`).

When the provider fails, the last forecast for the cell is served as **stale** if it is at most 24 hours old (`FORECAST_MAX_STALE_HOURS`) and still covers every requested date from today **[P2 spec, FR-2.6; Project decision JL-021]**. Days that are already past are dropped, so a stale answer still starts at today. The assignment left the age limit to us. 24 hours was chosen for three reasons:

- Irrigation is decided once a day, so a forecast from within the last day is still a reasonable basis.
- After 24 hours a forecast no longer covers 7 days from today anyway.
- An old forecast that looks normal is worse than a clear "unavailable".

The alternatives were 12 hours, which gives more 503s during a long outage, and 48 hours, which uses weather data that is too likely to be wrong. The configuration also refuses a stale limit shorter than the freshness time (`test_stale_limit_shorter_than_freshness_is_rejected`).

```mermaid
flowchart TD
    A[GET /v1/forecast lat, lon, days] --> V{lat, lon, days valid?}
    V -- no --> E[422 VALIDATION]
    V -- yes --> C{Cell has a forecast younger than 3 h<br/>that covers the days from local today?}
    C -- yes --> H[200, stale: false, no provider call]
    C -- no --> P[Call Open-Meteo: 1 attempt + 2 retries, 3 s each]
    P -- valid forecast --> S[Store for the cell, 200, stale: false]
    P -- every attempt failed --> T{Cached forecast at most 24 h old<br/>that covers the requested days?}
    T -- yes --> ST[200, stale: true, original fetched_at]
    T -- no --> U[503 UNAVAILABLE, Retry-After: 60]
```

In words: an invalid request is refused at once. A fresh cached forecast that covers the request answers without any provider call. Otherwise Open-Meteo is tried up to three times. A valid answer is stored and returned. If every attempt fails, a cached forecast up to 24 hours old that covers the days is returned marked stale. With nothing usable, the answer is 503 with `Retry-After: 60` **[P2 spec, FR-2.7]**.

### 5.6 How the weather-service was tested

**[Verified 2026-11-22]**: 135 tests passed with 100 % branch coverage over every module, including the benchmark script.

The tests never touch the network and never read the developer's `.env`. Three tools make that possible.

**A fake Open-Meteo.** `tests/conftest.py` defines `FakeProvider`, a small class whose `handler` method receives each HTTP request the service sends, records it, and returns the next queued answer: a JSON body, a specific `httpx2.Response` such as a 500, or an exception such as `ReadTimeout` to simulate a timeout. It is plugged in with `httpx2.MockTransport`. An HTTP client is built in layers, and its bottom layer, the *transport*, is the part that actually opens connections and sends bytes. A MockTransport replaces only that layer with a Python function, so the service code runs exactly as in production; only the network is replaced. The sample body has the same shape as Open-Meteo's answer, and a comment records that this shape was checked against the live API on 21 November 2026.

**A controllable clock.** The endpoint gets "now" from a dependency function, `utc_now`. Tests override it with a `Clock` object they can move forward. Freshness, staleness and midnight can then be tested in milliseconds instead of hours.

**Fixed settings.** An autouse fixture, one that pytest applies to every test automatically, sets the test configuration and disables the `.env` file, so a developer's local settings can never change a test result.

Read as a story, the tests document the service's behaviour:

- `test_points_in_the_same_cell_share_one_provider_call`: (31.21, 34.71) and (31.29, 34.79) cause one provider call, and each answer still echoes its own coordinates.
- `test_a_neighbouring_cell_gets_its_own_provider_call`: a point just across a cell edge, such as latitude 31.19 or 31.3, causes a second call.
- `test_fresh_forecast_is_served_without_a_provider_call`: after 2 hours 59 minutes, still one call. `test_after_3_hours_the_forecast_is_fetched_again`: at exactly 3 hours, a second call.
- `test_provider_failure_serves_the_last_forecast_as_stale`: five hours later the provider returns 500. The answer is the old forecast with `stale: true`, after exactly 1 + 3 provider requests: the first fetch, then one attempt and two retries.
- `test_stale_forecast_is_served_up_to_24_hours` and `test_stale_forecast_older_than_24_hours_returns_503`: exactly 24 hours is still served; 24 hours and 1 second is a 503.
- `test_a_recovered_provider_replaces_the_stale_forecast`: once the provider works again, the next answer is fresh.
- `test_a_forecast_from_another_cell_is_never_used`: a neighbour's forecast is never served as stale for another cell.
- `test_a_forecast_with_a_missing_value_returns_503_not_zeros`: a null ET0 on day 7 refuses the whole forecast, even for a request that asks only for day 1.
- `test_every_failure_is_retried_twice_then_raises`, in `test_provider.py`: a table of 32 failure kinds, from timeouts, connection errors and error statuses to HTML instead of JSON, missing fields, inches instead of mm, 6 days instead of 7, null, NaN, negative or text values, dates that aren't ISO, a forecast that starts yesterday or tomorrow, a missing day and days out of order. Each one is checked to cause exactly 3 attempts and then an error.
- Configuration tests: a missing variable stops startup and names it (`test_missing_variable_stops_startup_and_names_it`), and the startup log never shows the key.

**The performance benchmark** (`scripts/measure_p95.py`, Part 10) starts a real uvicorn server (uvicorn is the web server program that listens on a port and passes each HTTP request to the FastAPI application) and a small fake Open-Meteo HTTP server on the same machine, so it tests real HTTP without the internet.

**The live provider.** No automated test calls the real Open-Meteo, by design: an automated test that depends on a third party's availability fails for reasons unrelated to our code. Evidence of manual live checks exists. The weather README shows a real response for (31.25, 34.79) fetched at 17:08 UTC on 21 November 2026, with ET0 values of 3.15, 2.65 and 2.63 mm, and a local session note records a live check of the same day: 7 real days, a second point answered from the cache, `lat=91` refused with 422. That session note isn't committed, so the README sample is the committed evidence.

> **Interview follow-up:** "Your fake provider is written by you. What if Open-Meteo's real format differs from your fake?"
>
> **Model answer:** That's the real limit of fakes: they test our logic against our *understanding* of the provider. We reduced the risk by building the fake from a real response and checking it against the live API once. And production code is strict: if the real format drifts, the service refuses the forecast and answers 503 rather than misreading it. The failure would be loud, not silent. A scheduled contract check against the live API would close the gap, but we don't have one.

---

## Part 6 — Review question 5: Edge cases: What happens if the registry service is down? What happens if it changes the response format, e.g. `latitude` instead of `lat`?

### 6.1 "The registry is down" has three meanings

An important first step in answering this question well is to notice that "down" can mean different things, and each one looks different from the outside.

1. **The process isn't running.** The planner's HTTP client gets a refused connection (`httpx2.ConnectError`).
2. **The process runs, but its database is unavailable.** For example, the PostgreSQL container is stopped. The registry is designed for this: it classifies database errors, and for "unavailable" ones it answers `503 {"detail": "Database unavailable"}` with `Retry-After: 5`. Its `/health` still answers 200, because `/health` only shows that the process is running.
3. **The process is too slow.** The planner gives up after `REGISTRY_TIMEOUT_SECONDS`, 3 seconds (`httpx2.ReadTimeout`).

In all three cases the planner's `send` or `json_body` function raises `UpstreamUnavailable("registry-service", reason)`. The handler logs the reason, for example `Upstream failure: registry-service: request failed: ConnectError`, and answers:

```http
HTTP/1.1 503 Service Unavailable
{"code": "UPSTREAM_UNAVAILABLE", "detail": "registry-service is unavailable or did not answer in time."}
```

The weather-service isn't called, because without the plot the planner doesn't know which coordinates to ask about. It also never answers with a plan of zeros **[P2 spec, FR-2.14]**.

**Tests:** `test_registry_failure_is_503_naming_registry` runs the same assertions for 23 different registry failures across the plot, soil and emitter calls, including a refused connection, a timeout, a 500, a 503 "Database unavailable", text instead of JSON, and a JSON list. Every case asserts the exact 503 body and that the weather-service received no request. `test_upstream_failure_reason_is_logged` checks the log line.

**What the grower sees:** the farm list says "Can't load the farms. registry-service is unavailable…". The plot page says "No plan right now. registry-service is unavailable or did not answer in time. Try again in a minute." The status line shows "registry-service down" in case 1, and possibly in case 3 if the health check also times out. In case 2 it shows "up", because health doesn't check the database, which is a limitation.

**Recovery.** No restart is needed anywhere. The planner holds no state about the failure, so the next request simply tries again. On PostgreSQL, the registry keeps a *connection pool*: a few database connections that stay open and are lent to one request after another, because opening a new PostgreSQL connection, with its network handshake and login, takes time. The pool uses `pool_pre_ping`, which checks a pooled connection before using it and replaces it if the server closed it. The README's optional outage check demonstrates this: stop the container, get a 503, start it again, and the same request returns 200 without restarting the service. Tests cover recovery as well: `test_request_succeeds_after_server_closes_connections` on PostgreSQL and `test_reseeding_recovers_without_restart` on SQLite.

### 6.2 The registry changes its format: `latitude` instead of `lat`

Here is exactly what the code does. `upstream.get_plot` builds the plot from the registry's body with explicit lookups such as `lat=coordinate(body["lat"])`. If the registry renamed the field to `latitude`, the body has no `"lat"` key, and Python raises `KeyError('lat')`. That lookup sits inside `try ... except (KeyError, TypeError, ValueError)`, which converts any shape problem into:

```python
raise UpstreamUnavailable(REGISTRY, f"unusable plot: {exc!r}")   # "unusable plot: KeyError('lat')"
```

The planner logs `Upstream failure: registry-service: unusable plot: KeyError('lat')` and answers the same 503 naming the registry. It doesn't look for alternative names, doesn't guess, and doesn't default the coordinate.

**Why not be "tolerant"?** A tolerant client might default a missing coordinate to (0, 0). That point is in the Gulf of Guinea, off West Africa. The weather-service would happily return a real, plausible forecast for it, and the planner would produce a plan that looks completely normal and is completely wrong. Failing loudly is the only safe answer, for the same reason as Section 4.6: a visible error beats an invisible wrong number.

The same strictness covers every kind of format change:

- A *missing field* gives `KeyError` (tested by removing `soil_id`).
- A *null value* gives an error (tested with `lat=None`, `crop_id=None`, `emitter_spacing_m=None`).
- A *changed type* gives an error (tested with `area_m2="1500"` as text, `area_m2=True`, `lon=False`).
- An *invalid value* gives an error (tested with `area_m2=0`, `row_spacing_m=-1.5`, a planting date that isn't a date).
- An *added field* is harmless: the planner reads only the fields it needs and ignores the rest. Adding to an API is safe; renaming or removing breaks clients.

Three honest gaps belong in a complete answer:

- **There is no test that literally renames `lat` to `latitude`.** The mechanism is the same one tested by the missing `soil_id` case, but a reviewer may reasonably ask for that exact case.
- **The message is imprecise.** "registry-service is unavailable or did not answer in time" is wrong in spirit when the registry is up but has changed its contract. The log has the precise reason. A future improvement could say "gave an unusable answer". The assignment only requires the detail to name the service.
- **The frontend isn't as strict.** It also reads the registry directly, for the farm list and the plot header, and treats the JSON as typed data without checking it at runtime. A renamed `lat` wouldn't affect it, because it doesn't use coordinates. But a renamed `name` would show empty text instead of an error.

In a larger system, the standard tools against this problem are contract tests, versioned APIs and shared schemas. In a contract test, the consumer, here the planner, writes down what it expects from the provider, such as a field `lat` holding a number. Those expectations then run as a test against the real provider, here the registry, in the provider's own test suite. A rename breaks the registry's build before it is released, instead of breaking the planner in production. Versioned APIs put a breaking change under a new prefix: every route here already starts with `/v1/` for this reason. Shared schemas can be checked automatically, for example against the OpenAPI document that FastAPI generates. OpenAPI is a standard, machine-readable description of an API's endpoints and JSON shapes, which FastAPI serves at `/openapi.json`.

### 6.3 Two more registry edge cases

**A soil or emitter that returns 404.** For the plot itself, a 404 means "no such plot" and becomes the planner's 404. For the soil or emitter, a 404 becomes a 503 naming the registry. The reason is the database design: a plot's `soil_id` and `emitter_id` are foreign keys, so the registry can't contain a plot pointing to a missing soil. If it says the soil is missing, the registry itself is broken, and the honest answer is "the registry gave an unusable answer", not "your request was wrong".

**A registry 500.** An unexpected registry error, such as a SQL bug, is a 500 in the registry and a 503 naming the registry in the planner. The registry deliberately separates "the database is unavailable" (503, try again later) from "our SQL is wrong" (500, a bug). It classifies errors by SQLite's error names or PostgreSQL's SQLSTATE codes. SQLSTATE is a five-character error code defined by the SQL standard; its first two characters give the class, so every code that starts with `08` is a connection problem (Section 7.7). The classification keeps SQL bugs from being hidden as outages (`test_sql_bug_returns_500_not_503`).

> **Interview follow-up:** "Why does the planner check every field instead of using a Pydantic model for the registry's answer?"
>
> **Model answer:** A Pydantic model would also work. What matters is the strictness and the conversion. Every number has to become an exact `Fraction` from the decimal the registry sent, and booleans, NaN and infinity have to be rejected, which needs explicit checks either way. The hand-written functions `exact`, `positive`, `non_negative`, `coordinate` and `text` keep those rules visible in one small module, with their own unit tests in `test_upstream.py`.

---

## Part 7 — Deep dive: the registry's move from SQLite to PostgreSQL

### 7.1 Why PostgreSQL

In P1, the registry stored its data in a SQLite file. SQLite is a library, not a server: the application opens the database file directly. It is excellent for development and tests, because it needs no installation and a test can create a fresh database file in milliseconds. But it allows only one writer at a time, it can't be shared over a network by several application servers, and it has no users or permissions of its own.

P2 requires PostgreSQL in production and SQLite on a developer's machine **[P2 spec, FR-2.1]**, and switching between them must need only configuration, no code change **[P2 spec, NFR-2.1]**. PostgreSQL is a database server: many clients can connect at once, writes from different clients don't block each other the way SQLite's single writer does, and it has users, permissions and network access. The assignment also required that one documented command creates the tables in an empty PostgreSQL database and loads the same 15 seed rows as `seed_registry.sh` **[P2 spec, FR-2.2]**, and that the P1 latency target still holds on PostgreSQL **[P2 spec, NFR-2.2]**. This part was designed and planned with the Superpowers skills, a set of instruction packages for the Claude Code assistant that guide brainstorming, design and planning, as the assignment required. The design document and the plan are committed in `docs/superpowers/`.

### 7.2 Why SQLAlchemy, and why only its Core

The assignment says "All data access goes through SQLAlchemy" **[P2 spec]**. Within that, the project chose **SQLAlchemy Core with handwritten SQL**, not the ORM, the object-relational mapper, which maps tables to Python classes and writes the SQL itself (JL-007). The repositories still contain readable SQL such as `SELECT id, farm_id, name, ... FROM plots WHERE id = :id`, wrapped in `text()` and executed with a dictionary of parameters. SQLAlchemy contributes three things:

- One parameter syntax (`:name`) for both databases. SQLite's own driver, the library that speaks a database's protocol, uses `?`, and psycopg, the PostgreSQL driver, uses `%s`.
- Engines and connection pooling.
- A uniform exception hierarchy.

The alternatives were a hand-written adapter over the `sqlite3` and `psycopg` drivers, set aside as custom infrastructure to own, and PostgreSQL only, ruled out by the requirement to keep SQLite. The ORM wasn't needed: the P1 code was already SQL-based and readable, and the ORM would add a second set of concepts without adding a feature the registry needs. The cost: SQLAlchemy is a large dependency with its own concepts, such as engines, pools and `text()`.

### 7.3 How `DATABASE_URL` selects the database

`config.py` defines one setting with pydantic-settings:

```python
database_url: str = DEFAULT_DATABASE_URL   # sqlite:///<service folder>/registry.db
```

The value comes from, in order of priority, an environment variable, the service's `.env` file, and the default. An empty value, even one exported in the environment, means the default SQLite file (JL-010). Two example values:

```bash
DATABASE_URL=sqlite:////absolute/path/to/registry.db
DATABASE_URL=postgresql+psycopg://postgres:<password>@127.0.0.1:5436/registry
```

The `+psycopg` part names the driver, psycopg 3. Without it, SQLAlchemy picks a driver by its own version, so the README asks to keep it. Settings are read on *every* call to `get_database_url()`, so a test that changes the variable takes effect immediately. At startup, `main.py` logs which database was selected, with the password hidden, because an operator otherwise can't tell that an empty variable silently fell back to SQLite (JL-010). This is the evidence for NFR-2.1: moving between the databases is a one-line change in `.env`, and the same test suite runs on both through a variable.

### 7.4 How both databases are supported in `db.py`

`db.py` keeps one SQLAlchemy *engine* per URL. An engine is SQLAlchemy's object for one database: it knows how to open connections to it and owns their pool. Each engine is created on first use under a lock, so two simultaneous first requests can't create two connection pools. The engine differs by backend.

**SQLite.** The engine is bound once to the resolved absolute path of the file, so it stays on that file even if the working directory changes later. Connections are opened by `open_sqlite` with `mode=rw`: a missing file is an error, which becomes a 503, rather than SQLite silently creating a new empty database. Every connection turns foreign keys on with `PRAGMA foreign_keys = ON`, because SQLite doesn't enforce them by default. The pool class is `NullPool`, a fresh connection per request, as in P1 (JL-002). That is cheap, because there is no server to connect to.

**PostgreSQL.** The engine uses SQLAlchemy's default connection pool, with three settings: `pool_pre_ping=True` checks a pooled connection before each use, so a connection closed by a database restart is replaced instead of failing the request; `connect_timeout: 5` makes an unreachable host fail after 5 seconds (a 503) instead of after the operating system's TCP timeout of a minute or more; and `hide_parameters=True` keeps user data out of logs. The pool's size and other settings are SQLAlchemy's defaults. JL-007 records that they were left as defaults, to be checked by the benchmark (Part 10), not tuned.

**One transaction per request.** The dependency `get_db` opens `with engine.begin() as conn:` and yields the connection to the endpoint. If the endpoint returns normally, the transaction commits; if it raises, it rolls back. Repositories and routers never commit themselves (JL-008). One detail matters a great deal: the dependency is declared with `Depends(get_db, scope="function")`, which makes FastAPI run the commit *before* the response is sent. An experiment recorded in JL-008 showed that without it, a commit that failed after the endpoint returned would still send "201 Created" to the client, which would be a lie about stored data. Tests cover a failed commit (`test_failed_commit_returns_503_not_201`) and a full rollback when the second of two writes fails (`test_second_write_failure_rolls_back_the_first`).

### 7.5 Creating and seeding the database

There are two seeding paths, one per backend.

**SQLite:** `bash seed_registry.sh` creates `registry.db` with the schema, the catalogues and demo data. It refuses to touch an existing file unless given `--reset`, and the README warns that `--reset` deletes the data.

**PostgreSQL:** `uv run python -m scripts.setup_postgres --demo` is the one documented setup command **[P2 spec, FR-2.2]**. It:

- refuses a non-PostgreSQL URL, and prints the target with the password hidden before changing anything;
- runs `CREATE TABLE IF NOT EXISTS` for the five tables and `INSERT ... ON CONFLICT DO NOTHING` for the rows, so running it twice is harmless. Such an operation is called *idempotent*: doing it twice leaves the same result as doing it once (`test_setup_is_idempotent`);
- does all of it in **one transaction**. PostgreSQL can roll back table creation as part of a transaction, so a failure halfway leaves nothing behind;
- inserts the catalogues always (2 crops, 3 soils, 4 emitters) and the demo data only with `--demo` (2 farms, 4 plots). That totals 15 rows. Demo farms are optional because they shouldn't appear in a real grower database (JL-005).

It is explicitly *not* a migration tool (JL-004). A *migration* is a versioned script that changes an existing schema step by step, such as adding a column, while the database records which steps have already run. Here an existing table isn't changed even if its definition differs, and there is no schema version tracking. The alternatives were creating tables at application startup, or migrations with Alembic, SQLAlchemy's migration tool. Both were set aside as more infrastructure than the assignment needs, at the cost that future schema changes must be done carefully by hand.

Two type choices differ from SQLite, both documented in the script:

- **`DOUBLE PRECISION`, not `REAL`, for decimal numbers.** In PostgreSQL, `REAL` is a 4-byte float with about 6 significant digits, which would round coordinates and areas. In SQLite, `REAL` is 8 bytes.
- **`planting_date` stays `TEXT`.** A PostgreSQL `DATE` column returns a Python `date` object, while the API model declares the field as text. Keeping text makes both backends return identical JSON.

### 7.6 How the tables relate, and how data reaches the planner

The schema has three catalogues and two data tables:

- `crops (id, name)`: `tomato`, `bell-pepper`.
- `soils (id, name, available_water_mm_per_m)`: sand 83, loam 175, clay-loam 200.
- `emitters (id, name, flow_lph)`: DripNet PC at 0.6, 1.0, 1.6 and 2.0 litres per hour.
- `farms (id, name)`.
- `plots (id, farm_id → farms, name, area_m2, crop_id → crops, planting_date, soil_id → soils, row_spacing_m, emitter_spacing_m, emitter_id → emitters, lat, lon)`, with `UNIQUE (farm_id, name)`.

A farm has many plots. Each plot references exactly one crop, one soil and one emitter through foreign keys. The registry API exposes these as separate resources, so the planner follows the references itself: first the plot, then `/v1/soils/{soil_id}`, then `/v1/emitters/{emitter_id}`. That costs three round trips instead of one join, but it keeps the registry a general-purpose API rather than one shaped around the planner's needs. Part 10 discusses the cost.

The registry also protects references at the API level. Before inserting or updating a plot, `check_references` verifies that the farm exists (404 "Farm not found") and that the crop, soil and emitter exist (422 "Unknown crop", "Unknown soil" or "Unknown emitter"). A duplicate plot name on the same farm becomes 409. If a concurrent request deletes the farm between the check and the insert, the database's foreign key catches it, and the error is mapped by its constraint code (PostgreSQL 23503, SQLite `SQLITE_CONSTRAINT_FOREIGNKEY`) to the same 404.

### 7.7 Database errors: unavailable versus bug

A database error can mean "the database can't be used right now", which is worth a retry, or "our code is wrong", which is a bug. The registry's handler in `main.py` calls `is_unavailable(exc)` and answers 503 with `Retry-After: 5` only in the first case. Everything else is re-raised and becomes a 500.

- On SQLite, the classification uses the error name: `SQLITE_CANTOPEN`, `SQLITE_NOTADB`, `SQLITE_CORRUPT`, `SQLITE_IOERR`, `SQLITE_BUSY`, `SQLITE_LOCKED`, `SQLITE_FULL` and `SQLITE_READONLY` mean unavailable. `SQLITE_ERROR` doesn't, because SQLite also uses it for SQL typos and missing tables.
- On PostgreSQL, it uses the SQLSTATE code: class `08` (connection exception), `28` (authorization failed), `3D000` (database doesn't exist), `53` (insufficient resources), `57P01` to `57P03` (shutting down, crashed, starting up) and `58` (system error).

Tests check both lists and the boundary cases, for example that an empty but existing SQLite file without tables gives 500, not 503, and that a SQL bug gives 500.

### 7.8 How PostgreSQL support was tested

The decision was to run the **same test suite** on both databases rather than writing a second one (JL-006). By default, every test gets its own temporary SQLite file. When `TEST_DATABASE_URL` is set in the shell and points to localhost, every test that needs a database gets a fresh, randomly named PostgreSQL database, which is dropped afterwards. Tests that only make sense on one backend carry a `sqlite_only` or `postgres_only` marker. PostgreSQL-only examples include a wrong password giving 503 without logging the password, a missing database giving 503, an empty database giving 500, the setup script being idempotent, and a request succeeding after the server closed its connections.

**[Verified 2026-11-22]**: on SQLite, 272 tests passed and the 6 PostgreSQL-only tests were skipped. The PostgreSQL run wasn't repeated for this guide, because it needs a throwaway container. CI runs it on every pull request into `main`.

**Continuous integration** (`.github/workflows/registry-service.yaml`) has two jobs, both required by the `protect-main` ruleset before a merge. Job `test` runs the suite on SQLite, then on a PostgreSQL 17 service container, and requires 100 % branch coverage measured over both runs together, because some lines run only on one backend. Job `audit` runs `uv audit`, which checks the locked dependencies for known vulnerabilities. All actions in this workflow are pinned to full commit SHAs. The latest CI runs on GitHub, for pull requests merged on 18 and 22 November 2026, succeeded. Part 13 explains this workflow and the branch rules step by step.

### 7.9 Practical differences and trade-offs

| Topic | SQLite | PostgreSQL |
| --- | --- | --- |
| What it is | A file, opened as a library | A server, reached over the network |
| Connections | A new one per request (`NullPool`) | A pool, with `pool_pre_ping` |
| Concurrent writes | One writer at a time | Many |
| `REAL` | 8 bytes | 4 bytes, hence `DOUBLE PRECISION` |
| NUL in text | Stored | Refused, hence the 422 on both (JL-009) |
| Unavailable errors | By error name | By SQLSTATE |
| Setup | `seed_registry.sh` | `scripts/setup_postgres.py` |

The NUL decision deserves a sentence, because it is the one intended behaviour change from P1. Without it, a NUL character in a name returned 201 on SQLite but 500 on PostgreSQL. The project chose consistent, predictable behaviour on both (422) over preserving SQLite's permissiveness (JL-009).

### 7.10 Local "production" versus a real deployment

To keep claims precise, here is the actual setup:

- **The P2 "production" database** is the Docker container `agropilot-pg` on the developer's Mac: PostgreSQL 17, database `registry`, port 5436 published only on 127.0.0.1, data in the Docker volume `agropilot-pg-data`, which survives container removal. The instructor accepted Docker as sufficient.
- **The test database** is a separate throwaway container, `agropilot-test-pg` on port 5435, created with `--rm` so it disappears when stopped.
- **A cloud deployment** exists for the registry only. The root README on `p2` documents an Ubuntu EC2 server running the registry under systemd. `main` has a workflow that, on every push to `main`, connects over SSH, moves the server's copy of the repository to exactly the merged commit, runs `uv sync --locked` and restarts the service. Part 13 describes it in detail, including its two recorded deployments on 22 November 2026, one of which needed a second attempt. Which database the EC2 registry uses can't be seen in the repository **[Not verified]**.
- **The weather-service, planner and frontend have not been deployed anywhere.** They run on the developer's machine. It would be wrong to say "the P2 system is deployed".

---

## Part 8 — Deep dive: the planner's irrigation model

This is the heart of P2. The aim of this part is that you could rebuild the calculation on paper.

### 8.1 The problem, from first principles

A plant draws water from the soil around its roots. The sun and wind pull that water out through the leaves, and some evaporates from the soil surface. Rain and irrigation put water back. If the soil gets too dry, the plant suffers before it wilts: it closes its pores, grows less and yields less. If we water too much, the extra water drains below the roots and is wasted, along with nutrients.

So irrigation planning is bookkeeping. We track how much usable water is in the root zone, subtract what the crop will use each day, add rain, and irrigate when the level would fall too low. Every intermediate value in the engine exists to answer one part of that bookkeeping:

- **ET0** answers: how thirsty is today's weather?
- **Kc** answers: how thirsty is *this crop at this age* compared with reference grass?
- **ETc** answers: how much water will the crop use today?
- **TAW** answers: how much usable water can this soil hold for these roots?
- **The threshold** answers: how low may it go before we act?
- **The bucket level** answers: where are we now?
- **Emitter count and flow** answer: how fast can this drip system deliver water?
- **Litres and run minutes** answer: what exactly should the grower do?

### 8.2 Water as a depth

Agronomists measure water as a depth in millimetres, as if the water were spread evenly over the field. The conversion to volume is the most useful fact in the whole model:

```
1 mm of water over 1 m² = 0.001 m × 1 m² = 0.001 m³ = 1 litre
```

So 6.9 mm over a 1,500 m² plot is 6.9 × 1,500 = 10,350 litres. A depth makes rain, irrigation and crop water use directly comparable, whatever the plot's size **[P2 spec; Units]**.

### 8.3 ET0, the weather's thirst

ET0 is the water a standard, well-watered grass surface would lose in a day, in mm. It depends on temperature, sunshine, humidity and wind, and FAO-56 defines how to calculate it with the Penman-Monteith equation **[FAO-56]**. The weather-service gets it ready-made from Open-Meteo as `et0_fao_evapotranspiration`. The engine treats it as an input; it never calculates or adjusts ET0. The test values (6.0 mm) are summer-like values taken from the assignment's own example. The live Open-Meteo values for the same point in late November were around 2.6 to 3.2 mm.

### 8.4 Kc, the crop factor, and its growth stages

A crop doesn't use water like grass, and its use changes as it grows. FAO-56 describes a season in four stages **[FAO-56, Ch. 6]**:

- **Initial:** a small plant. Most water loss is evaporation from the soil, so Kc is low.
- **Development:** the canopy grows, so Kc rises steadily.
- **Mid-season:** full canopy, so Kc is at its peak.
- **Late season:** the crop matures, so Kc falls.

The engine uses one fixed profile per crop (JL-016):

| Crop | Stage lengths, ini / dev / mid / late (days) | Season length | Kc ini / mid / end | Root depth |
| --- | --- | --- | --- | --- |
| Tomato | 35 / 45 / 70 / 30 | 180 days | 0.60 / 1.15 / 0.80 | 0.7 m |
| Bell pepper | 30 / 40 / 110 / 30 | 210 days | 0.60 / 1.05 / 0.90 | 0.5 m |

Where these numbers come from **[FAO-56, with Project decisions]**:

- The stage lengths are FAO-56 Table 11's "Arid Region" rows, used for every plot whatever its planting month.
- The Kc values come from Table 12. Tomato's end value, 0.80, is chosen inside FAO's range of 0.70 to 0.90.
- The root depths are the small ends of Table 22's ranges (tomato 0.7 to 1.5 m, pepper 0.5 to 1.0 m), because a footnote recommends the smaller values for scheduling.

These are deliberate P2 simplifications based on FAO-56 values, not values claimed to be right for every location or season.

**Which day of the season is it?** The planting day counts as day 1 **[Project decision]**:

```
i = (date − planting_date) in days + 1
```

**Kc on day i** follows FAO-56's straight-line interpolation (Ch. 6, Eq. 66) **[FAO-56]**:

```
Initial stage      (i ≤ L_ini):                    Kc = Kc_ini
Development stage  (L_ini < i ≤ L_ini + L_dev):    Kc = Kc_ini + (i − L_ini) / L_dev × (Kc_mid − Kc_ini)
Mid-season         (… ≤ L_ini + L_dev + L_mid):    Kc = Kc_mid
Late season        (… ≤ season length):            Kc = Kc_mid + (i − L_ini − L_dev − L_mid) / L_late × (Kc_end − Kc_mid)
```

In words: Kc is flat in the initial stage, rises in a straight line during development, is flat again at its peak, and falls in a straight line in the late season. Kc has no unit; it is a ratio. Three substitutions, all **[Verified 2026-11-22 with the engine]**:

- **Bell pepper, worked example Case 2.** Planted 1 October 2026; on 19 November it is day 49 + 1 = 50. That is in development (days 31 to 70). Kc = 0.60 + (50 − 30) / 40 × (1.05 − 0.60) = 0.60 + 0.5 × 0.45 = **0.825**.
- **Tomato on day 50.** Kc = 0.60 + (50 − 35) / 45 × (1.15 − 0.60) = 0.60 + 0.3333… × 0.55 = 0.78333…, shown as **0.783**.
- **Tomato on day 165, late season.** Kc = 1.15 + (165 − 150) / 30 × (0.80 − 1.15) = 1.15 − 0.175 = **0.975**.

### 8.5 ETc, the crop's water use

```
ETc = Kc × ET0          [FAO-56, Ch. 5, Eq. 56]
```

Kc has no unit and ET0 is in mm per day, so ETc is in mm per day. For the Case 3 tomato in mid-season on a 6.0 mm day: ETc = 1.15 × 6.0 = **6.9 mm**. This is the amount the soil bucket loses that day.

FAO-56 also offers a more precise "dual" coefficient that separates evaporation from the soil surface from transpiration by the plant, and it recommends the dual method for drip irrigation, where much of the soil stays dry. The project uses the single Kc without FAO's climate adjustments, because those need wind speed and humidity, while the weather-service provides only ET0 and rain **[P2 spec, FR-2.3; Project decision JL-017]**. The cost: less accuracy for drip, mostly early in the season.

### 8.6 The growing season, and why out-of-season plots are refused

FAO-56's curve exists only from planting to the end of the season. Outside it there is no Kc, so the engine has nothing honest to calculate with. The rule (JL-020) **[Project decision]**:

```
i_first = (today − planting_date) in days + 1
i_last  = i_first + days − 1
if i_first < 1 or i_last > season_length:  → 409 PLOT_OUT_OF_SEASON
```

The planting day (i = 1) and the last season day (i = 180 or 210) are inside the season. A plot near the end of its season can still get a shorter plan: `days=1` works on its very last day (worked example B6).

**Which "today"?** The plan's dates are the forecast's dates, which are the local dates at the plot. Before the forecast arrives, the planner knows only its own UTC date. Time zones run from 12 hours behind UTC to 14 hours ahead, so the field's today is the UTC date, the day before, or the day after. The early check therefore refuses only when the plan would be out of season on *all three* candidate dates. The final check, on the forecast's real dates, decides the remaining cases. This is why a plot near midnight never gets a wrong 409. The cost: a plot within one day of a season boundary needs the forecast before its 409, so if the weather-service is down at that moment, that plot gets a 503.

### 8.7 TAW, the size of the soil bucket

Soil holds water like a sponge. After heavy watering drains away, the soil sits at **field capacity**. At the **wilting point** the plant can no longer extract water. The water between those two levels, over the depth the roots reach, is the plant's usable reserve **[FAO-56, Ch. 8]**:

```
TAW = 1000 × (θFC − θWP) × Zr        [FAO-56, Eq. 82]
    = available_water_mm_per_m × Zr
```

θFC and θWP are the soil's water content at field capacity and at the wilting point, in cubic metres of water per cubic metre of soil. `1000 × (θFC − θWP)` is the usable water per metre of soil depth, in mm per m, and the registry stores it per soil as `available_water_mm_per_m`. Zr is the root depth in metres. The units give mm per m × m = mm.

For the Case 3 plot on sand: TAW = 83 × 0.7 = **58.1 mm**. The registry's sand value of 83 mm per m lies inside FAO-56 Table 19's range for sand, where θFC − θWP is 0.05 to 0.11, or 50 to 110 mm per m. The same tomato on loam (175 mm per m) would have a bucket of 122.5 mm: loam holds water far better than sand, so it needs irrigating much less often.

One simplification to remember: Zr is fixed for the whole season (JL-016), so a young plant gets a bucket as deep as a grown plant's, even though its real roots are shallower.

### 8.8 The threshold, and why it isn't FAO's

```
threshold = TAW / 2          [P2 spec: "When the level would fall below half, irrigate"]
```

For Case 3: 58.1 / 2 = **29.05 mm**. This rule comes from the assignment, not from FAO-56.

FAO-56 uses a crop-specific fraction p: the share of TAW a crop can use before it starts to suffer stress, called the readily available water, RAW = p × TAW (Eq. 83). Table 22 gives p = 0.40 for tomato and 0.30 for pepper. By FAO, tomato starts to lose water uptake once its bucket is below about 60 % full, and pepper below about 70 % full, before FAO's adjustment of p for the day's ETc. The P2 rule waits until 50 %. So the plan can let the soil dry into a range where FAO-56 expects mild stress. That is an honest limitation of following the specification's simpler rule.

### 8.9 The daily bucket, step by step

For each day of the plan, in this order:

```
1. start = min(previous_end + rain_mm, TAW)
2. etc   = Kc × ET0
3. if start − etc < threshold:  desired_mm = TAW − start   else  desired_mm = 0
4. applied_l   = min(desired_mm × area_m2, daily_cap_l)
   applied_mm  = applied_l / area_m2
   run_minutes = applied_l / system_flow_lph × 60
5. end = max(start + applied_mm − etc, 0)
```

Why each step is written the way it is:

- **Step 1, rain at the start of the day, capped at a full bucket.** The model is daily, not hourly, so rain is counted in the morning even if it really falls in the evening **[Project decision, JL-013]**. Water beyond a full bucket is lost: it drains below the roots, which FAO-56 calls deep percolation (Eq. 86 and 88) **[FAO-56]**.
- **Step 3, look ahead within the same day.** The plan asks, "If we don't irrigate, would the bucket end today below half?" FAO-56's Annex 8 example decides from the *previous* day's end level and irrigates the next day. We act before the level crosses the line instead of discovering afterwards that it did **[Project decision, JL-013]**. The comparison is *strictly* below: a day that ends exactly at half doesn't irrigate. This matches the assignment's own example, where a 70 mm bucket losing 7 mm a day reaches exactly 35 mm after day 5 and is irrigated on day 6 **[P2 spec]**.
- **Step 3, refill to full.** On an irrigation day the plan gives what the bucket is missing, TAW − start, like FAO's Annex 8 example (JL-012). The alternative, replacing only today's ETc, would keep the bucket hovering just above half and irrigate almost every day. Refilling produces a clear rhythm: fill, drain for several days, fill again. That rhythm is exactly why the plan doesn't water every day.
- **Step 4, the 24-hour cap.** A drip system can't run more than 24 hours in a day **[Project decision, JL-014]** (Section 8.10).
- **Step 5, never below empty.** The clamp at 0 follows FAO-56's limits on the bucket (Eq. 86). It only matters when even capped irrigation can't keep up. Those numbers mean the crop is under water stress and must not be presented as safe.

There is also no efficiency factor: the water applied is counted fully as water in the root zone, as in the assignment's example **[P2 spec]**. Real drip systems lose a little to uneven distribution.

### 8.10 From millimetres to minutes: the drip system

The bucket works in mm. The grower needs minutes. The bridge is the drip system's total flow **[Units]**:

```
emitters        = area_m2 / (row_spacing_m × emitter_spacing_m)      m² / (m × m) = a count
system_flow_lph = emitters × flow_lph_per_emitter                     count × L/h = L/h
desired_l       = desired_mm × area_m2                                mm × m² = L
daily_cap_l     = system_flow_lph × 24                                L/h × h = L
run_minutes     = applied_l / system_flow_lph × 60                    L / (L/h) × 60 = min
```

Each emitter "serves" one rectangle of row spacing × emitter spacing. For Case 3: emitters = 1,500 / (1.5 × 0.4) = 1,500 / 0.6 = **2,500**. Total flow = 2,500 × 0.6 = **1,500 L/h**. Over 1,500 m², that is exactly **1 mm per hour**, a handy fact for this plot: every hour of irrigation adds 1 mm to the bucket. The daily cap is 1,500 × 24 = **36,000 L**, which is 24 mm or 1,440 minutes. The emitter count is a density estimate and is deliberately not rounded to a whole number. For the assignment's 1,000 m² example it is 1,666.67.

**Why the cap matters.** Without it, the plan could ask for 1,701 minutes in one day, which no clock allows. With the cap, the plan delivers what fits in 24 hours, updates the bucket with the water *actually delivered*, and carries nothing over automatically to the next day. Never reporting the uncapped volume is the same honesty principle as never inventing zeros: the plan must not show a full bucket that the system can't fill.

### 8.11 A complete seven-day walkthrough: worked example Case 3

The plot: tomato in mid-season (Kc 1.15 all week), sand at 83 mm per m, root depth 0.7 m, 1,500 m², rows 1.5 m, emitters every 0.4 m at 0.6 L/h. The bucket starts full. TAW = 58.1 mm, threshold = 29.05 mm, flow = 1 mm per hour, cap = 24 mm a day. Every value below was calculated by hand in `worked-examples.md`, is reproduced by the tests, and was **[Verified 2026-11-22]** by running the engine again.

| Day | Date | ET0 | Rain | Start (after rain) | ETc | Start − ETc | Below 29.05? | Irrigation | End |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 21 Nov | 6.0 | 0 | 58.1 | 6.9 | 51.2 | no | none | 51.2 |
| 2 | 22 Nov | 6.0 | 0 | 51.2 | 6.9 | 44.3 | no | none | 44.3 |
| 3 | 23 Nov | 5.0 | 5 | 49.3 | 5.75 | 43.55 | no | none | 43.55 |
| 4 | 24 Nov | 6.0 | 0 | 43.55 | 6.9 | 36.65 | no | none | 36.65 |
| 5 | 25 Nov | 6.0 | 0 | 36.65 | 6.9 | 29.75 | no, by 0.70 mm | none | 29.75 |
| 6 | 26 Nov | 5.5 | 0 | 29.75 | 6.325 | 23.425 | **yes** | 24 mm = 36,000 L = 1,440 min (capped) | 47.425 |
| 7 | 27 Nov | 6.0 | 0 | 47.425 | 6.9 | 40.525 | no | none | 40.525 |

Here is the story the table tells.

**Day 1** starts with a full bucket of 58.1 mm. The crop uses 1.15 × 6.0 = 6.9 mm, so the day would end at 51.2, far above 29.05. No irrigation.

**Day 3** shows how rain works. The bucket ended day 2 at 44.3. Five mm of rain are added in the morning: min(44.3 + 5, 58.1) = 49.3, below the cap of a full bucket, so nothing is lost. ET0 is lower that day, so ETc is 1.15 × 5.0 = 5.75. The day ends at 43.55. Yesterday's rain still counts tomorrow, as the assignment puts it.

**Day 5** is the instructive "no irrigation" day. It starts at 36.65 and loses 6.9, ending at 29.75, only 0.70 mm above the threshold. Not *below* half, so no irrigation.

**Day 6** is the irrigation day. It starts at 29.75. The crop would use 1.15 × 5.5 = 6.325, ending at 23.425, which is below 29.05, so irrigate. The bucket is missing 58.1 − 29.75 = 28.35 mm. Over 1,500 m² that is 42,525 litres, and at 1 mm per hour it would take 28.35 hours, or 1,701 minutes. That exceeds a day, so the plan is capped at 36,000 L = 24 mm = 1,440 minutes. The bucket ends at 29.75 + 24 − 6.325 = **47.425 mm**. The uncapped answer, 51.775 mm, is *not* the plan: it would claim water the system can't deliver.

**Day 7** starts from what was really delivered, 47.425. It loses 6.9 and ends at 40.525. Nothing carries over from day 6's shortfall.

The API returns, for every day, `kc 1.15`, and for day 6, `litres 36000` and `run_minutes 1440`. The other days have zeros for both, and the end levels are 51.2, 44.3, 43.55, 36.65, 29.75, 47.425 and 40.525.

### 8.12 The starting assumption, and the simulation option

Every plan needs this morning's soil level, and AgroPilot has **no soil moisture sensor and no irrigation history**. So the starting level is always an assumption, never a measurement.

**The default: a full bucket (JL-011)** **[Project decision]**. The alternative of starting at half was set aside, because it is just as much a guess and would make most plans irrigate on day 1 purely because of the guess. Simulating the bucket from the planting date was rejected, because the weather-service provides only forecast days, not past rain and irrigation. A full start gives a clear, repeatable plan that can be checked by hand, and the assignment's own example also starts full. The cost is real: if the soil is actually dry, the plan can say "no irrigation" when the field needs water. That is why the frontend always says "Default assumption, not a measurement."

**The optional simulation.** `initial_soil_water_pct`, a whole number from 0 to 100, changes only the level on the morning of day 1: previous_end = TAW × pct / 100. TAW, the threshold, the refill-to-full rule and the cap stay the same. Leaving the parameter out gives exactly the same plan as before, and the response always echoes the value used. Two examples, **[Verified 2026-11-22 with the engine]**:

- **Worked example B7, Case 3 starting half full (50 %).** Day 1 starts at 29.05. It would end at 29.05 − 6.9 = 22.15, below the threshold, so irrigate. The bucket is missing 29.05 mm = 43,575 L, capped at 36,000 L, 1,440 minutes. The day ends at 29.05 + 24 − 6.9 = 46.15. The bucket then drains to 31.6 by day 4. Day 5 would end at 24.7, so it irrigates again, capped, and ends at 48.7. End levels: 46.15, 39.25, 38.5, 31.6, 48.7, 42.375, 35.475.
- **Starting empty (0 %).** Day 1 irrigates at the cap and ends at 0 + 24 − 6.9 = 17.1, still below the threshold. Day 2 irrigates at the cap again (ending at 34.2), and so does day 4 (ending at 50.55). An empty start needs three full 24-hour irrigation days in the first four days.

The lesson for a presentation: low starting levels push the plan straight to the 24-hour cap. That is a sign the model's limits have been reached, not a realistic schedule. The frontend shows a stronger warning exactly then. These numbers are simulations, not field-verified recommendations.

### 8.13 Units, rounding and exact arithmetic

The engine calculates everything at full precision and rounds only when building the API response (JL-018): `kc`, `bucket_level_mm`, `taw_mm` and `threshold_mm` to 3 decimals, and `litres` and `run_minutes` to whole numbers. `et0_mm` and `rain_mm` are returned exactly as the weather-service sent them. The rounding is "half up", so .5 always rounds up. Python's built-in `round()` can't be used, because it rounds .5 to the nearest even number (`round(2.5)` is 2), so the engine has a small `round_half_up` helper. A rounded value is never fed back into the next day's calculation, otherwise each day would add a small error.

One implementation detail is worth knowing because of what it protects. The engine uses Python's `fractions.Fraction`, which stores numbers exactly as a numerator over a denominator, instead of floats (JL-019). With floats, Kc for pepper on day 32 is 0.62249999… instead of exactly 0.6225, so it rounds to 0.622 instead of 0.623 (worked example B3). Worse, a day that should end at *exactly* half can end a hair below it, so a float engine would irrigate when it shouldn't: worked example B1 records exactly that case. Exact fractions make the strict "below half" test reliable without any tolerance. The cost is speed, which doesn't matter for seven loop iterations, and discipline: one float mixed in silently brings the errors back, so the engine refuses float inputs and a test checks that every calculated value is a `Fraction`.

### 8.14 The assignment's example, and why the plan doesn't return it

The assignment's example is a 1,000 m² tomato plot in mid-season with ET0 6.0 mm and no rain, rows 1.5 m apart, emitters every 0.4 m at 1.0 L/h. It shows `litres 6900` and `run_minutes 248`. The arithmetic (worked example Case 1, **[Verified]**):

```
ETc       = 1.15 × 6.0 = 6.9 mm
litres    = 6.9 mm × 1,000 m² = 6,900 L
emitters  = 1,000 / (1.5 × 0.4) = 1,666.67      flow = 1,666.67 L/h
run time  = 6,900 / 1,666.67 = 4.14 h = 248.4 min  →  248
```

That example replaces *one day's* water use. Our plan, following the bucket rules, returns zero on most days and a refill on the irrigation day, so it never returns exactly this row. The tests check the ETc, flow and run-time steps on their own to prove the arithmetic matches the specification (`test_case_1_one_day_of_etc_as_litres_and_run_minutes`).

### 8.15 Where each rule comes from

| Rule | Source |
| --- | --- |
| ETc = Kc × ET0 | FAO-56, Eq. 56 |
| Four stages, straight-line Kc between them | FAO-56, Ch. 6, Eq. 66 |
| Stage lengths, Kc values, root depths | FAO-56 Tables 11, 12, 22, with fixed choices (JL-016) |
| Single Kc, no climate adjustment | Project decision (JL-017) |
| TAW = soil water per metre × root depth | FAO-56, Eq. 82 |
| Irrigate when the level would fall below half | P2 spec |
| Water as depth, 1 mm on 1 m² = 1 L | P2 spec; units |
| Bucket between 0 and full; overflow lost | FAO-56, Eq. 86 and 88 |
| Start full by default | Project decision (JL-011) |
| Optional starting level | Project decision (simulation) |
| Refill to full | Project decision, after FAO-56 Annex 8 (JL-012) |
| Rain and irrigation at the start of the day; same-day look-ahead | Project decision (JL-013) |
| 24-hour cap | Project decision (JL-014) |
| Emitter count = area ÷ (row × emitter spacing) | Units |
| Planting day is day 1; refuse out-of-season plans | Project decision (JL-020) |
| Round only the output, half up | Project decision (JL-018) |
| Exact fractions | Project decision (JL-019) |

### 8.16 What the model can't tell you

The model is a transparent, checkable simplification. It isn't a field-validated agronomic tool, and the plan must not be presented as a guaranteed recommendation. Its main limits:

- **No measured soil moisture.** The starting level is assumed. A real system would start from a sensor reading or a measured water content (FAO-56 Eq. 87).
- **The forecast is treated as certain.** If forecast rain doesn't come, the plan may have skipped a needed irrigation.
- **A daily model.** Evening rain counts in the morning, and irrigation is assumed possible at the start of every day.
- **A 50 % threshold instead of FAO's p**, so mild stress can begin before the plan reacts (Section 8.8).
- **Single Kc, fixed stage lengths, fixed root depth.** These are less accurate for drip, for unusual planting months and for young plants.
- **The bucket is an average over the whole plot.** Drip wets only part of the soil (FAO's wetted fraction), which this model ignores.
- **No efficiency factor, no runoff, no capillary rise from groundwater.**
- **Under water stress, the model doesn't reduce crop water use** (FAO's Ks coefficient), so numbers near an empty bucket are pessimistic bookkeeping, not a prediction.
- **The 24-hour cap is a modelling limit, not a schedule.** Real systems run in shifts and share water between plots.
- **Nothing in the repository compares a plan with what really happened in a field.**

> **Interview follow-up:** "Why not let an AI model adjust the numbers, since it knows agronomy?"
>
> **Model answer:** The assignment forbids it: "Every number in the plan comes from your engine. No AI model computes or adjusts irrigation numbers." The engineering reason is checkability. Every number can be traced to a formula with a documented source, recalculated by hand, and tested. An AI adjustment can't be reproduced or audited the same way.

---

## Part 9 — Review question 6: How did you test the planner service, which depends on the weather and the registry service? Explain the approach.

### 9.1 The core idea: separate what you calculate from whom you call

Testing a service that depends on two others is hard if the tests need those services running. They become slow and *flaky*, passing or failing at random for reasons outside the code, and a failure doesn't say whose fault it is. The planner is built so that its two concerns can be tested separately:

- **`engine.py` is pure.** It takes plain Python values and returns plain values. It does no HTTP, reads no clock and touches no files. In programming terms it is made of *pure functions*: the same inputs always give the same outputs, and nothing else changes. It can be tested with nothing but inputs and expected outputs.
- **`routers/plan.py` and `upstream.py` do the orchestration and the HTTP.** Orchestration means deciding which services to call, in what order, and what to check in between. They can be tested by replacing the network with fakes.

This separation is a design decision with a testing payoff. A wrong number points at the engine. A wrong status code points at the orchestration.

**[Verified 2026-11-22]**: 174 planner tests passed in 0.39 seconds, with 100 % branch coverage over every module (342 statements and 58 branches, none missed).

### 9.2 Layer 1: the engine, tested against hand calculations

`tests/test_engine.py` reproduces every value in the worked examples of the irrigation skill. A *skill* is a Markdown instruction file that the Claude Code assistant loads when a task needs it. This one, `.claude/skills/irrigation-calc-reference`, holds the exact formulas, crop values and rounding rules (Section 12.2). Its worked-example values were calculated by hand *before* the engine existed, so they are independent of it:

- `test_case_1_one_day_of_etc_as_litres_and_run_minutes`: the assignment's 248 minutes.
- `test_case_2_pepper_development_kc`: Kc 0.825.
- `test_case_3_tomato_on_sand_seven_days` and `test_case_3_capped_day_never_reports_the_uncapped_volume`.
- `test_b1_a_day_that_ends_at_exactly_half_does_not_irrigate` and `test_b2_just_below_half_irrigates_on_day_7`: the threshold boundary, in both directions.
- `test_b3_kc_tie_rounds_up`, `test_b4_litres_and_minutes_ties_round_up` and `test_b5_round_half_up`: rounding ties.
- `test_b6_season_boundaries`, `test_definitely_out_of_season`, `test_kc_is_never_invented_outside_the_season` and `test_planting_day_is_day_1`: the season.
- `test_b7_case_3_starting_half_full` and `test_empty_start_waters_on_day_1_but_never_past_the_daily_cap`: the simulation.
- Physical rules: `test_rain_above_a_full_bucket_is_lost` and `test_bucket_never_goes_below_zero_when_the_cap_cannot_keep_up`.
- Input rules: non-positive plot values, negative weather values, no forecast days, non-consecutive days, an unknown crop, and float inputs are all refused. `test_every_calculated_value_is_a_fraction` guards the exact arithmetic.

Boundary cases were chosen deliberately at the places where a plausible implementation would go wrong: a day ending exactly at half, values exactly at .5, the first and last season day, and the day before and after them.

### 9.3 Layer 2: the converters, tested on their own

`tests/test_upstream.py` tests the small functions that turn JSON values into exact numbers. `exact` keeps the decimal that was sent (0.4 becomes exactly 2/5) and rejects null, text, booleans, NaN, infinity and lists. `positive` rejects 0 and negative values, and `coordinate` and `text` have their own checks. These are tiny tests, but they pin down the rules that protect the engine from bad data.

### 9.4 Layer 3: the endpoint, with fake services

`tests/conftest.py` defines `FakeService`, used twice: once as the registry and once as the weather-service. A fake holds a dictionary from URL path to answer. An answer can be a dict (sent as a 200 JSON body), a specific `httpx2.Response` such as a 503, an exception such as `httpx2.ReadTimeout` to simulate a timeout, or a function that builds an answer from the request. An unknown path returns 404. The fake also records every request it receives.

How it is wired in matters. The planner creates two `httpx2.Client` objects at startup, one per upstream, with their timeouts. The test fixture starts the real application with FastAPI's `TestClient`, which calls the application directly inside the test process, as an HTTP client would, without starting a server. It then replaces those two clients with clients built on `httpx2.MockTransport(fake.handler)`, the same technique as in the weather-service (Section 5.6): instead of opening a network connection, the client hands each fully built request to the fake's Python function and uses whatever response it returns. Everything above the network, including URL building, query parameters, status handling, JSON parsing, validation, the engine, rounding, exception handlers and response serialization (turning the Python result into JSON text), runs exactly as in production.

```python
# The essence of the fixture (tests/conftest.py)
app.dependency_overrides[utc_today] = lambda: today.date      # a date the test controls
with TestClient(app) as test_client:                          # runs startup: settings, two clients
    app.state.registry_client = registry.client()             # MockTransport → fake registry
    app.state.weather_client = weather.client()               # MockTransport → fake weather
    yield test_client
```

The fake bodies are shaped like the real services' answers. `plot_body()` mirrors the registry's `GET /v1/plots/{id}`, and `forecast_body()` mirrors the weather-service's `GET /v1/forecast`. Tests change one field at a time, for example `plot_body(area_m2=0)`, to create exactly one fault.

The tests assert three kinds of things:

1. **The answer:** status code and exact body. For example, `test_plan_reproduces_case_3_end_to_end` compares the whole JSON.
2. **The calls that were made:** order, paths and query parameters (`test_plan_asks_registry_then_weather_for_the_plot_point`, `test_days_sets_the_plan_length`).
3. **The calls that were *not* made:** for example, that a 422 calls no service, an unknown plot never calls the weather-service, and a clearly out-of-season plot doesn't call the soil, emitter or weather. This is how the "fail fast" and "check before you call" rules are proven, not just claimed.

Two more control points make the tests deterministic. The **date** comes from the `utc_today` dependency, which tests override. That is how the "planner a day ahead of the field" and "a day behind" cases are tested. And the **settings** come from a fixture that sets fixed test values and disables the `.env` file, so a developer's configuration can't change a test. Configuration has its own tests, for example that a missing variable stops startup and names it (`test_missing_variable_stops_startup_and_names_it`), and that the startup log shows both upstream URLs and timeouts.

The failure matrix is the largest part. There are 23 registry failures, 17 weather failures, a NaN and Infinity case, a logging check and the unknown-crop 500 (Parts 4 and 6).

### 9.5 What 100 % branch coverage does and doesn't mean

**Line coverage** says every line ran at least once. **Branch coverage** is stricter: every decision went both ways. For example, both the "irrigate" and the "don't irrigate" side of `if start - etc < threshold`, and both outcomes of every `try`. The Python services enforce 100 % branch coverage; a run below it fails.

What it guarantees: no code exists that the tests never executed, so there is no forgotten error branch that has never run.

What it doesn't guarantee:

- **That the assertions are right.** A test can execute a line without checking its result.
- **That the requirements are complete.** Coverage measures the code you wrote, not the code you forgot to write.
- **That the fakes match reality** (Section 9.6).
- **That the system behaves well under concurrency, real network latency or real timeouts.** A simulated `ReadTimeout` is raised instantly; nothing actually waits 3 seconds.

That is why the worked examples, calculated by hand, matter as much as coverage: they check the *values*, not just that code ran.

### 9.6 What fakes can't catch

The biggest risk of fake upstreams is **contract drift**. The fakes are hand-written copies of what we believe the registry and weather-service return. If the real registry changed a field, the planner's tests would still pass, because the fake didn't change. The project limits this risk three ways. The planner validates strictly, so drift produces a loud 503 rather than a wrong plan (Part 6). The services are developed in one repository, so a change is visible in one review. And the fake bodies were written from the real response models. But there is **no automated test that runs the real services together**, and no consumer-driven contract test. That is the most important gap in the testing strategy.

### 9.7 The testing picture across the whole system

| Part | What runs | Result | In CI? |
| --- | --- | --- | --- |
| registry-service | 278 tests: API, SQL safety, transactions, database-error classification, seed and setup scripts; some start a real uvicorn process | **[Verified 2026-11-22]** 272 passed, 6 PostgreSQL-only skipped on SQLite | Yes, on SQLite and PostgreSQL, 100 % branch coverage over both runs, plus `uv audit` |
| weather-service | 135 tests with a fake Open-Meteo and a controllable clock | **[Verified 2026-11-22]** 135 passed, 100 % | No |
| planner-service | 174 tests with fake registry and weather | **[Verified 2026-11-22]** 174 passed, 100 % | No |
| frontend | No automated tests. `npm run lint` (ESLint, a *linter*: a tool that reads code without running it and flags likely mistakes) and `npm run build` (a TypeScript type check during the production build) | **[Verified 2026-11-22]** lint passed. The build wasn't re-run for this guide | No |
| irrigation skill | 6 evaluation cases checking that an AI assistant using the skill gets the calculation right: the exact-half threshold, half-up ties, Kc by date, an out-of-season plot, the seven-day bucket with the cap, the spec's run time | Results not recorded in the repository | No |
| P2 Explorer | Its build traces the real planner code against the fakes and fails if a traced value differs from a worked example | A local session note records "all checks passed" | No |
| Benchmarks | registry and weather p95 (Part 10) | **[Verified 2026-11-22]** both PASS | No |
| Real end-to-end | Manual only: the README smoke tests (quick manual checks that the main path works at all), the live weather check on 21 November 2026, the frontend run in a browser | Recorded in the README sample, commit messages and local notes; no committed log of a full live run | No |

The frontend's phone layout at 375 px (NFR-2.8) and the visible error states (FR-2.18) were checked in a browser according to the frontend commit message. That check isn't repeatable automatically and wasn't repeated for this guide **[Not verified for this guide]**.

> **Interview follow-up:** "If all the planner's tests use fakes, how do you know the planner works with the real registry?"
>
> **Model answer:** The tests prove the planner's logic for every answer the registry can give, good or bad. They don't prove that the registry gives the answer the fake gives. That part rests on three things: the fake bodies mirror the registry's response models, the planner refuses any answer that doesn't match its expectations, and a manual run with all services. An automated end-to-end or contract test is the missing piece, and it would be my next addition.

---

## Part 10 — Review question 7: In terms of performance, is there a bottleneck in the system? How do you know?

### 10.1 A suspected bottleneck is not a measured one

A **suspected** bottleneck comes from reasoning: "this step involves the network, so it is probably slow." A **measured** bottleneck comes from timing the system under a defined load and seeing where the time goes. Engineers regularly guess wrong about performance, so a credible answer separates the two clearly. Here is what is measured, then what is only reasoned.

### 10.2 What was measured

The assignment sets latency targets only for the registry and for the weather-service's fresh path:

- **NFR-1.1**, from P1: the registry's `GET` list and `GET` by id, p95 at most 100 ms at 10 requests per second.
- **NFR-2.2**: the same on PostgreSQL.
- **NFR-2.3**: a fresh forecast, served without a provider call, p95 at most 100 ms at 10 requests per second.

Both benchmark scripts run the real service under uvicorn on the same machine and send 1,200 requests at a steady 10 per second for 120 seconds. They report p50 (the median), p95 and maximum per route and overall. They report FAIL if any response isn't 200, or if any route's p95 is over 100 ms, not just the overall p95 (JL-003). The weather script also fails if any provider call happens besides the single warm-up request. It uses a fake Open-Meteo on the same machine, set to a time zone where it is noon when the run starts, so a run never crosses local midnight.

| Measurement | Result | Evidence |
| --- | --- | --- |
| Registry on SQLite, 11 GET routes | p95 **10.73 ms** overall, slowest route 10.97 ms, max 18.23 ms, 0 of 1,200 failed: PASS | **[Verified]** re-run 2026-11-22 for this guide |
| Weather fresh path, two points in one cell | p95 **8.57 ms** overall, max 13.58 ms, 0 of 1,200 failed, 1 provider call (the warm-up): PASS | **[Verified]** re-run 2026-11-22 for this guide |
| Registry on PostgreSQL 17 in Docker on macOS | p95 **18.70 ms**: PASS, about 8 ms above SQLite on every route | Recorded in the committed PostgreSQL plan, `docs/superpowers/plans/2026-11-16-postgresql.md`, not re-run today. A later local session note records 13.84 ms |
| Earlier registry SQLite runs | 9.07 ms (P1), 9.76 ms (JL-003), 10.45 ms (PostgreSQL plan) | Committed docs |
| Planner, end to end | **Not measured.** P2 sets no latency target for it | — |
| Frontend page load | **Not measured** | — |

How to read these numbers fairly:

- They were measured on a developer's laptop over the loopback address (Section 2.2), so the traffic never left the machine and they exclude real network latency between machines.
- At 10 requests per second the services are lightly loaded, so these are latency figures, not capacity limits.
- The 8 ms gap between PostgreSQL and SQLite was uniform across routes. The plan document attributes it to the extra hop into Docker's virtual machine on macOS: on a Mac, Docker runs Linux containers inside a small virtual machine, so every query crosses one more network boundary. That interpretation is plausible but wasn't measured separately.

### 10.3 The anatomy of one plan request

Without an end-to-end measurement, the honest way to discuss the planner is to list what a request does and reason about each part:

1. **Four HTTP calls, made one after another**: plot, soil, emitter, forecast. Each is a full round trip over HTTP to another process.
2. **Each registry call** opens a database transaction and runs one primary-key lookup. On SQLite it also opens a new connection (`NullPool`). The benchmark puts each such call at about 10 ms p95 on this machine, *including* the HTTP overhead.
3. **The weather call** is a dictionary lookup when the cache is fresh, about 8.6 ms p95 including HTTP. On a cache miss it includes a call to Open-Meteo over the internet, whose latency was never measured. On a provider failure it can take about 9 seconds (three attempts of up to 3 seconds) before a stale answer or a 503.
4. **The engine** runs seven loop iterations of exact fraction arithmetic. JL-019 notes that fractions are slower than floats and that this doesn't matter for a 7-day plan. That is reasonable, since this is microseconds of work next to milliseconds of network, but it isn't measured.
5. **The frontend** renders on the server. The plot page calls the registry and the planner in parallel, and the layout calls three `/health` endpoints in parallel, all uncached (`cache: "no-store"`).

### 10.4 Synchronous versus asynchronous execution

Two pieces of background first. A *blocking* call makes its thread wait, doing nothing else, until the answer arrives; an `httpx2.Client` request and a database query are both blocking. FastAPI itself runs on an *event loop*: one thread that juggles many requests by switching to another request whenever the current one is waiting. An `async def` endpoint runs on that loop and must never block, because a blocking call would stall every request the loop is juggling.

All three Python services define their endpoints with plain `def`, not `async def`, and use the blocking `httpx2.Client`. FastAPI therefore runs each endpoint in a worker thread from its thread pool (Section 5.4), so a blocking wait for the network or the database occupies one thread but doesn't freeze the server. The pool comes from AnyIO, the concurrency library underneath Starlette, which is in turn the toolkit FastAPI is built on. Its default limit is 40 threads, and the project doesn't change it. The reason for this choice is in the project notes: the database drivers block, and synchronous code is simpler to read and debug.

The trade-off shows up only under slow upstreams. If the weather-service is in its 9-second failure path, each planner request waiting on it holds a thread for up to 12 seconds. About 40 such requests at once would exhaust the pool, and new requests would queue, even ones that don't need weather. An `async` planner with an async client could wait on many slow calls without holding threads, and could run the soil, emitter and forecast calls *concurrently* once the plot is known. The plot must come first, because it provides the soil id, the emitter id and the coordinates. That would turn four sequential round trips into two. It wasn't done, because nothing measured shows it is needed at this scale, and the code would be harder to follow.

### 10.5 So, is there a bottleneck?

A careful answer has three parts.

- **Measured:** the two parts that have targets, the registry and the weather fresh path, are each about 10 to 20 ms at p95, roughly a tenth of their 100 ms targets.
- **Suspected, by reasoning:** the slowest step of a normal plan request is the **Open-Meteo call on a cache miss**, an internet round trip, but it happens at most about once per grid cell every 3 hours (Part 11). The worst case is the **provider failure path**, up to about 9 seconds before a stale answer or a 503. During normal operation, the next largest cost is the **three sequential registry calls** made by the planner. Estimated at roughly 30 to 50 ms for a warm plan, *this estimate is unmeasured*.
- **How we would know for sure:** benchmark the planner end to end with the real registry and a weather-service pointed at a fake provider, the same method as the existing scripts. Log per-hop timings, or profile under load. Until then, the claim "the planner has no bottleneck" can't be made from evidence.

> **Interview follow-up:** "The registry opens a new SQLite connection for every request. Isn't that the bottleneck?"
>
> **Model answer:** It was a deliberate P1 choice (JL-002), and the measurement supports it: 10.73 ms p95 including the HTTP round trip, against a 100 ms target. Opening a SQLite connection is cheap because there is no server. The limit we'd hit first under heavy *write* load is SQLite's single writer, and a pool wouldn't fix that. That's one reason production is PostgreSQL, which does use a pool.

---

## Part 11 — Review question 8: How did you deal with API rate limit of Open-Meteo?

### 11.1 What Open-Meteo's limits are

On 22 November 2026, Open-Meteo's terms and pricing pages state that the free API is for **non-commercial use only**, at "less than 10'000 API calls per day, 5'000 per hour and 600 per minute," and about 300,000 per month. Limits are "applied by IP addresses and application". Typically one HTTP request counts as one API call, but a request for more than 10 weather variables or more than 2 weeks of data for one location counts as several. Our request asks for 2 variables and 7 days, so it counts as one call. Commercial use requires a paid subscription, which comes with an API key for a separate customer endpoint. These facts come from Open-Meteo's website, not from the repository; the repository doesn't record the limits anywhere.

### 11.2 How the design keeps calls low

The project's answer to rate limits is **mitigation by design**: make far fewer calls than users make requests.

1. **One caller.** Only the weather-service talks to Open-Meteo. Neither the frontend, nor the browser, nor the planner does. Every rate-related rule therefore lives in one place.
2. **One forecast per grid cell.** All plots and users within the same 0.1° cell share one cached forecast (FR-2.5). Ten plots in one valley cost one call, not ten.
3. **Three hours of freshness.** While a cell's forecast is younger than 3 hours, no provider call is made, however many requests arrive.
4. **Always 7 days.** One fetch answers requests for any number of days, so a 1-day request followed by a 7-day request doesn't cost two calls.
5. **A stale fallback.** When the provider fails, including when it refuses us for exceeding a limit, the last good forecast for the cell is served for up to 24 hours, so a short refusal doesn't take the planner down.
6. **A paid-plan hook.** `PROVIDER_API_KEY` and `PROVIDER_BASE_URL` already exist in the configuration **[P2 spec]**, so moving to a paid plan is a configuration change, not a code change.

### 11.3 The arithmetic

In normal operation, a cell causes at most one provider call per 3 hours: 24 / 3 = **8 calls per cell per day**, plus at most one extra shortly after local midnight, when a still-fresh forecast no longer covers 7 days. Against the daily limit of 10,000, that allows roughly 1,100 to 1,250 distinct grid cells per day before the daily limit is near. That is far more than a course demo or a small farm cooperative needs. Request volume doesn't change this number. Whether a cell gets one request per day or 10 per second, it still causes at most about 8 calls, because everything else is answered from memory, as the benchmark shows: 1,200 requests, 1 provider call.

### 11.4 Where mitigation stops: this is not enforcement

It is important to be precise here. The design *reduces* calls; it doesn't *guarantee* staying under the limit. The repository has no rate limiter, quota counter or call budget. Specifically:

- **No backoff, and no special handling of HTTP 429 ("Too Many Requests").** *Backoff* means waiting between retries, usually longer after each failure, to give a struggling server room to recover. A 429 is treated like any other non-200 status and is retried twice immediately. Being rate-limited therefore causes three calls instead of one. Open-Meteo's `Retry-After` header, if sent, is ignored.
- **No memory of failures ("negative caching").** During an outage, once a cell's forecast is older than 3 hours, *every* request for that cell tries the provider again, three times. At 10 requests per second, that is up to 30 calls per second, which would reach the 600-per-minute limit in about 20 seconds. Each request is still answered (stale or 503), but the provider is hammered exactly when it is struggling.
- **Duplicate fetches.** Two simultaneous requests for a cell without a fresh forecast can both call the provider.
- **A per-process cache.** A restart empties it. Several weather-service instances would each have their own cache and each fetch separately.
- **No monitoring.** Nothing counts calls per day or warns before a limit is reached.
- **Licensing, not only rate.** The free tier is non-commercial. A real product would need a paid plan regardless of call volume.

Natural next steps would be: a short "cooldown" after a failure, so a failing cell is retried at most once a minute; respecting `Retry-After` on 429; a per-cell lock, so only one request fetches while others wait; a call counter with an alert; and, for scale, a shared cache such as Redis, an in-memory database that several processes can use at once. None of these is implemented, and none is required by P2.

> **Interview follow-up:** "So what is your one-sentence answer to 'how did you deal with the rate limit'?"
>
> **Model answer:** We route every Open-Meteo call through one service that caches a 7-day forecast per 0.1° cell for 3 hours, which caps normal use at about 8 calls per cell per day whatever the traffic, and falls back to a stale forecast when the provider refuses us. It's a mitigation, not enforcement: we don't count calls, back off, or treat 429 specially, so a long outage under heavy traffic could still exceed the per-minute limit.

---

## Part 12 — Review question 9: How did you validate the FR and NFR of the system? How did you check that you built the system right?

### 12.1 Building the system right versus building the right system

Software engineering separates two questions. **Verification** asks "did we build the system right?": does it do what the specification says? **Validation** asks "did we build the right system?": does it solve the user's real problem? This project has strong evidence for verification and only weak evidence for validation. Being clear about that is part of a good answer.

### 12.2 The verification chain

The approach is a chain in which each link checks the one before:

1. **The specification** defines the requirements (FR-2.1 to FR-2.19, the NFRs, and the global configuration rules).
2. **Domain research** with citations turned "use FAO-56" into concrete formulas (`fao56.md`). The assignment required this research step, and the notes record what wasn't verified, for example that the print edition wasn't cross-checked.
3. **A knowledge skill**, `irrigation-calc-reference`, wrote down the exact formulas, units, crop values and rounding rules, each tagged with its source (FAO, P2, project or units), together with **cases calculated by hand before the engine existed**. Six evaluation cases test whether an AI assistant using the skill gets the calculation right.
4. **Tests reproduce the hand calculations exactly**, and test every failure branch, at 100 % branch coverage.
5. **Benchmarks** measure the NFRs with an explicit PASS or FAIL rule that is itself tested (`test_measure_p95.py` in both services checks, for example, that one slow route fails the run even when the overall p95 passes).
6. **CI** re-runs the registry's suites on both databases for every pull request into `main` (Part 13).
7. **The Judgment Log** records every significant decision, its alternatives and its costs, so a reviewer can check the reasoning, not just the result.
8. **Manual checks** in a running system: the README smoke tests, the live weather check, the browser checks of the frontend.

### 12.3 Requirement by requirement

| Requirement | How it is met | Evidence |
| --- | --- | --- |
| FR-2.1 PostgreSQL in production, SQLite locally | `DATABASE_URL` selects the backend; `db.py` builds the matching engine | Test suite on both backends; CI; the startup log line |
| FR-2.2 One command creates the tables and 15 seed rows | `scripts.setup_postgres --demo` | `test_setup_postgres.py`, PostgreSQL-only setup tests, README expected output |
| NFR-2.1 Switching needs only configuration | No code path depends on the backend choice beyond `db.py` | The same suite, switched by an environment variable |
| NFR-2.2 Registry p95 ≤ 100 ms on PostgreSQL | — | 18.70 ms recorded in the committed plan (later note: 13.84 ms); not re-run today |
| FR-2.3 Forecast endpoint with date, ET0, rain | `routers/forecast.py`, `provider.py` | `test_forecast_returns_7_days_from_today`, `test_fetch_maps_the_provider_fields` |
| FR-2.4 Coordinate and days ranges, 422 VALIDATION | FastAPI `Query` limits, custom handler | `test_invalid_query_returns_422_validation`, `test_boundary_values_are_accepted` |
| FR-2.5 One forecast per 0.1° cell, fresh 3 h | `cache.py` | Cell, freshness and midnight tests (Section 5.6) |
| FR-2.6 Two retries, then the last forecast as stale | `fetch_forecast`, stale branch | `test_every_failure_is_retried_twice_then_raises`, `test_provider_failure_serves_the_last_forecast_as_stale` |
| FR-2.7 503 UNAVAILABLE with Retry-After | `ForecastUnavailable` handler | `test_provider_failure_without_a_cached_forecast_returns_503` |
| FR-2.8 Never invent numbers | Strict parsing; whole forecast refused | `test_a_forecast_with_a_missing_value_returns_503_not_zeros`, the 32-case failure table |
| NFR-2.3 Fresh forecast p95 ≤ 100 ms | In-memory cache | **8.57 ms, PASS, re-run 2026-11-22** |
| FR-2.9 Plan for 1 to 7 days, default 7, starting today | `routers/plan.py` | `test_days_sets_the_plan_length` |
| FR-2.10 Fields per day; `run_minutes: 0` without irrigation | `schemas.py`, router | `test_plan_reproduces_case_3_end_to_end` |
| FR-2.11 Every number calculated as in the skill | `engine.py` follows the skill | Engine tests reproduce Cases 1 to 3 and B1 to B7 |
| FR-2.12 Bad days 422 VALIDATION, unknown plot 404 NOT_FOUND | Validation and `PlotNotFound` handlers | `test_bad_days_is_422_and_calls_no_service`, `test_unknown_plot_is_404_and_weather_is_not_called` |
| FR-2.13 A stale forecast still plans, every day stale | `stale` copied to each day | `test_stale_forecast_still_plans_with_every_day_stale` |
| FR-2.14 Upstream down or slow: 503 naming the service, never zeros | `UpstreamUnavailable` | The 23-case registry and 17-case weather failure tests |
| FR-2.15 Farm list with plot links | `app/page.tsx` | Manual (no frontend tests) |
| FR-2.16 Today first, then the 7 days | `TodayPanel`, `PlanDays` | Manual |
| FR-2.17 Stale visible next to the numbers | `StaleBadge` per day, `StaleNotice` | Manual |
| FR-2.18 Errors explained, never blank or a stack trace | `PlanError`, `error.tsx` | Manual; the planner's error codes are tested |
| FR-2.19 Status line from `/health` | `StatusLine`, `health.ts` | Manual |
| NFR-2.8 Usable at 375 px | List below 640 px, today above the fold (visible without scrolling) | The frontend commit message; not re-verified for this guide |
| Global: settings in `.env` via pydantic-settings, `.env.example`, `.env` never committed | One `config.py` per Python service | Config tests; `git ls-files` **[Verified]** |
| Global: a clear error at startup when a variable is missing | Custom `load_settings` | `test_missing_variable_stops_startup_and_names_it` (weather, planner). The registry has a SQLite default by design (JL-010). The frontend reads its URLs at request time, so a missing one shows on the first request, not at startup |
| Global: block the agent from reading `.env` | `.claude/settings.json` | The file exists |

### 12.4 What the evidence doesn't cover

- **The frontend requirements** (FR-2.15 to FR-2.19, NFR-2.8) rest on manual checks. There are no automated frontend tests, and the frontend has no CI.
- **The weather-service and planner have no CI workflow**, so their suites protect only when someone runs them.
- **No automated end-to-end test** runs the real services together.
- **NFR-2.2 on PostgreSQL** was measured on the developer's Docker setup and not re-measured for this guide.
- **Validation in the agronomic sense**, whether the plans are good for real crops, isn't evidenced at all. The plan follows a documented, simplified model; it has never been compared with field data.
- **Submission requirements still open:** the P2 pull request, with the measured NFR numbers, the skills used and suggested changes to the irrigation skill, hadn't been opened as of 22 November 2026. The root `README.md` still lists the weather-service, planner and frontend as "Planned", which is out of date.

> **Interview follow-up:** "How do you know your hand-calculated worked examples are themselves right?"
>
> **Model answer:** They were calculated step by step from the documented formulas and re-checked on a second date. Some boundary cases were computed with exact fractions specifically to find spots where floats fail. And they agree with the assignment's own example, 6,900 litres and 248 minutes, and its 70 mm bucket story. But they verify consistency with our *chosen* model, not agronomic truth. If a formula choice were wrong, the examples would agree with it.

---

## Part 13 — Deep dive: CI/CD and the AWS deployment

The nine review questions don't ask about deployment, but a reviewer may well ask how code gets from a laptop to a server. Following the course tutorials, the project built a delivery pipeline around the registry. This part describes that pipeline as it actually is, not as a generic tutorial would. Its sources differ from the rest of the guide:

- **The workflow files on `main`** at commit `77f7ab0` on GitHub: `.github/workflows/registry-service.yaml` and `.github/workflows/deploy-registry.yaml`. The `p2` branch has only the first of them.
- **GitHub's own records**, read through its API on 22 November 2026: the repository's branch ruleset, the names of its stored secrets, every recorded workflow run, and the logs of the latest runs.
- **The course tutorials** **[Course tutorial]**: "Continuous Integration (CI) with GitHub Actions", "Continuous Delivery (CD) with GitHub Actions" and "Amazon Web Services (AWS) - Intro to Cloud Computing", in the course repository. The project followed them closely, so they are also the best description of how the server was meant to be set up.
- **The EC2 sections of the README on `p2`** **[Documented]**.

What this part can't draw on is the EC2 server itself. Nobody logged in to the machine for this guide, so everything about its inside, such as its systemd unit file, its database and its firewall rules, is either documented or marked **[Not verified]**.

None of this comes from the P2 specification. CI and CD aren't P2 requirements; they are course work done on `main`, in parallel with P2.

### 13.1 CI and CD from first principles

Imagine the project without them. A developer finishes a change, runs the tests on their laptop (or forgets to), merges it, then logs in to the server, downloads the new code, installs packages and restarts the service by hand. Every manual step can be skipped or done slightly differently. And "it works on my machine" hides everything the laptop has that a clean machine doesn't: a `.venv`, a `.env`, a `registry.db`.

**Continuous Integration (CI)** means that changes are merged into `main` often, and every change is checked automatically, on a clean machine, before it gets in. The course puts the goal simply: "A broken change is caught on its branch, minutes after it was pushed, not by a grower in the field" **[Course tutorial]**. CI answers the question *is this change safe to merge?*

**Continuous Delivery (CD)**, in the course's definition, "means a merge to `main` deploys that commit to production environment" **[Course tutorial]**. CD answers the question *how does a merged change reach the server?* Its answer: the same scripted way every time, with a log. A note on names: many texts reserve "continuous delivery" for a pipeline that keeps every change *ready* to deploy while a person presses the final button, and call a fully automatic deploy on every merge "continuous deployment". By that stricter vocabulary, AgroPilot has continuous deployment. The mechanism is what matters: here, the merge *is* the deploy.

Why both? CI protects `main`: it keeps broken code out. CD protects the server: the deployed version is always a known commit, installed the same way every time, and every deployment leaves a record of what was deployed, when, and whether it worked. Together they turn deploying from an event into a routine.

Both run on **GitHub Actions**, GitHub's built-in automation service. A *workflow* is a YAML file (a plain-text settings format whose structure comes from indentation) in `.github/workflows/` that says *when* to run (`on`, the triggering event) and *what* to run (`jobs`, each a list of `steps`). Each job runs on a *runner*, a fresh virtual machine that GitHub creates for that job and deletes afterwards. A step either runs a shell command (`run`) or uses an *action* (`uses`): a ready-made, published building block such as "check out the repository" or "install uv".

### 13.2 Push, pull request, merge and deployment

These words are easy to blur, and in this repository each one has a different effect.

- **A commit** is a snapshot of the files, saved in the local repository on the developer's machine. Nothing leaves the laptop.
- **A push** uploads commits from the laptop to a branch on GitHub. Pushing a feature branch triggers nothing by itself, because no workflow listens for pushes to feature branches. Pushing new commits to a branch that already has an open pull request does re-run CI, because the pull request has changed.
- **A pull request** (PR) is a request, made on GitHub, to merge one branch into another, here always into `main`. It is the place for review and for automated checks. Opening or updating a pull request into `main` triggers the CI workflow.
- **A merge** adds the branch's commits to `main`. GitHub records it as a *merge commit*, for example `77f7ab0 Merge pull request #9…`. GitHub treats the merge as a push to `main`, and that push triggers the deploy workflow.
- **A deployment** puts a specific version of the code on the server and runs it. Here it is one run of the `deploy-registry` workflow.

The real history of pull request #9 on 22 November 2026 shows all of them **[Verified]**. Times are UTC; the commit's own timestamp is 22:39 local time, UTC+2.

| Time (UTC) | Event | What it triggered |
| --- | --- | --- |
| 20:39 | Commit `5804a72`, "ci: deploy registry using the workflow commit SHA", on the branch `feature/cd-commit-pinning` | Nothing |
| 20:42 | The pull request into `main` triggers CI | Job `audit` passed in 7 seconds, job `test` in 56 seconds |
| 20:44:11 | The pull request is merged: merge commit `77f7ab0` on `main` | A `deploy-registry` run, 2 seconds later |
| 20:44:48 | Deploy attempt 1 fails: the runner can't reach the server | Nothing changed on the server |
| 20:48:49 | Deploy attempt 2, re-run by hand | The server moves to `77f7ab0`; success at 20:48:56 |

The only earlier deployment, for pull request #8 at 13:27 UTC the same day, succeeded on its first attempt.

### 13.3 The CI workflow, step by step

`registry-service.yaml` starts with its trigger:

```yaml
on:
  pull_request:
    branches: [main]
```

It runs for every pull request into `main`: when the pull request is opened, and again whenever new commits are pushed to it. It has no `paths` filter, a list of folders that would limit the workflow to changes inside them, so it also runs for a pull request that touches only documentation or the planner, and even then it tests only the registry. It doesn't run on a push to `main`, so the merged result isn't tested again after the merge (Section 13.4 explains why that matters).

The workflow has two jobs, which run at the same time on two separate runners.

**Job `test`** runs on `ubuntu-latest`, with `services/registry-service` as the working directory of every command.

1. **A PostgreSQL service container.** The `services:` block asks GitHub to start a `postgres:17` container next to the job, with port 5435 on the runner forwarded to PostgreSQL's port 5432. Its health options (`pg_isready`, checked every 2 seconds, up to 15 times) make the job wait until the database actually accepts connections. Its password is the documented throwaway test password, not a secret, and the container disappears with the runner.
2. **Check out the code** with `actions/checkout` and **install uv** with `astral-sh/setup-uv`. Both actions are *pinned to a full commit SHA*, for example `actions/checkout@3d3c42e5…  # v7.0.1`. A SHA is the unique fingerprint of one exact commit of the action's code. A version tag such as `v7` is only a movable label: its owner, or anyone who takes over the owner's account, can point it at different code later. A SHA can't be moved. The workflow's own comment says so: "a tag can be moved, a commit cannot." The course tutorial uses tags (`@v7`); pinning to SHAs is the project's own tightening **[Project decision]**.
3. **`uv sync --locked`** installs exactly the versions in `uv.lock`, and fails if the lockfile doesn't match `pyproject.toml`. A forgotten `uv lock` is therefore caught on the branch.
4. **Verify the Python version.** The log of the latest run shows `Python 3.12.16`, chosen from the service's `.python-version`.
5. **Run the tests on SQLite:** `uv run pytest --cov --cov-fail-under=0 --cov-report=`. This runs the whole suite on temporary SQLite files and records which lines and branches ran. `--cov-fail-under=0` switches off the 100 % gate for this run, because SQLite alone can't reach it, and the empty `--cov-report=` prints no report yet.
6. **Run the tests on PostgreSQL and check 100 % coverage.** With `TEST_DATABASE_URL` pointing at the service container, the suite runs again, this time on PostgreSQL. `--cov-append` adds this run's coverage data to the SQLite run's, and now the project's `fail_under = 100` setting applies: the job fails if any line or branch ran in neither run. That is the reason for the two-step design, because some code runs only on SQLite and some only on PostgreSQL.
7. **Upload the coverage report.** The HTML report is stored with the run as an *artifact*, a file GitHub keeps with the run for download, named `coverage-report`. `if: always()` makes this step run even when the tests failed, which is exactly when the report is most useful.

**Job `audit`** checks the *packages*, not our code. `uv audit --locked --preview-features audit-command` looks up every version in `uv.lock` in OSV, a public database of known vulnerabilities, and fails if any package is listed. The extra flag is needed because the command is still new in uv. The course states the limit honestly: "A passing audit doesn't prove the packages are safe. It only means none of them is on the list today" **[Course tutorial]**.

**What the latest run showed** **[Verified]**. The CI run for pull request #9 tested `main`'s registry code:

- On SQLite: 263 passed, 6 skipped (the PostgreSQL-only tests).
- On PostgreSQL: 265 passed, 4 skipped (the SQLite-only tests).
- Combined coverage: 555 statements and 112 branches, 100 %.
- Audit: "Found no known vulnerabilities and no adverse project statuses in 31 packages".
- The `coverage-report` artifact is kept until 20 February 2027.

These numbers differ from the 272 passed tests in Section 7.8 because `p2`'s registry has more code and more tests than `main`'s. All four CI runs recorded on GitHub, between 18 and 22 November 2026, succeeded.

**What CI doesn't check:** the weather-service, the planner and the frontend have no workflow at all. There is no linter in CI, no end-to-end test, and no test of the deployment.

### 13.4 Branch protection and required checks

A green or red check only informs, unless something enforces it. On GitHub that is *branch protection*, configured here as a *ruleset* named `protect-main`, as the CI tutorial instructs **[Course tutorial]**. Read through GitHub's API, it contains **[Verified]**:

| Rule | What it means |
| --- | --- |
| Target: the default branch, `main`; enforcement active | The rules are enforced on `main`, not just reported |
| Restrict deletions | Nobody can delete `main` |
| Block force pushes | Nobody can rewrite `main`'s history. A *force push* replaces a branch's history with a different one, which could silently erase merged work |
| Require a pull request before merging, with 0 required approvals | `main` changes only through a pull request. No reviewer's approval is required, so a solo developer can merge their own pull request |
| Require status checks to pass: `test` and `audit`, from GitHub Actions | The Merge button stays blocked until both CI jobs have passed on the pull request |
| "Require branches to be up to date": off | A pull request can be merged even if `main` has moved on since its checks ran |
| Bypass list: empty | Nobody is exempt from the rules. The repository's owner can still edit or switch off the ruleset in the settings |

In practice, a direct `git push` to `main` is rejected, and the only way into `main` is a pull request whose `test` and `audit` checks are green. The CI tutorial demonstrates the rejected push; it wasn't repeated for this guide.

Three consequences are worth understanding:

- **The ruleset is what connects CI to CD.** The deploy workflow doesn't check whether CI passed. It doesn't need to, because a push to `main` can only come from a merge, and a merge needs green checks. If the ruleset were switched off, a red pull request could be merged and deployed.
- **The final merged code isn't always the code that was tested.** For a pull request, GitHub's CI tests a trial merge of the branch into `main` as `main` was when the checks ran. Because "up to date" isn't required and CI doesn't run again on `main`, a second pull request merged in between can make the final result differ from what was tested, so two pull requests that each passed could break each other. With one developer and small pull requests the risk is small, but it is real.
- **Required checks are matched by job name.** If the job `test` were renamed, the required check `test` would never report, and every pull request would stay blocked waiting for it. Renaming a job means updating the ruleset too.

### 13.5 The deployment target: AWS, EC2, Ubuntu, SSH, secrets and systemd

**AWS and EC2.** Amazon Web Services (AWS) rents out computing resources in Amazon's data centres. EC2, short for Elastic Compute Cloud, is its service for virtual machines, called *instances*: a computer you start, stop and pay for by the hour, without owning any hardware. The AWS tutorial creates one in the `us-east-1` region, with Ubuntu, the `t3.medium` type and a 15 GiB disk **[Course tutorial]**. The README on `p2` confirms that an Ubuntu EC2 instance runs the registry **[Documented]**. Its exact type, region and current state weren't checked for this guide **[Not verified]**.

Two AWS details matter for the deployment:

- **The public address can change.** Stopping and starting an instance can give it a new public IP address; a reboot doesn't. The deploy workflow finds the server through the address stored in the `EC2_HOST` secret, so after such a change the deploy can't connect until the secret is updated. The CD tutorial's fix is an *Elastic IP*, a fixed public address that belongs to the AWS account and is attached to the instance **[Course tutorial]**. Whether one is used here is **[Not verified]**.
- **The security group is the firewall.** A *security group* is AWS's virtual firewall for an instance: a list of the ports that accept traffic, and from where. By default only port 22, SSH, is open. The AWS tutorial adds a rule that opens port 8000, the registry's port, to `0.0.0.0/0`, which means every address on the internet **[Course tutorial]**. The README on `p2` says remote access "requires an appropriate inbound Security Group rule" **[Documented]**. The actual rules are **[Not verified]**.

**Ubuntu** is a Linux distribution, the operating system on the instance. Its standard EC2 image has a user named `ubuntu`, who may run commands as the administrator with `sudo` without typing a password **[Course tutorial]**. The deploy relies on that.

**SSH**, Secure Shell, is the encrypted remote terminal used to run commands on the instance. It logs in with a *key pair*. The public key sits on the server, in the `ubuntu` user's list of authorized keys. The private key, the `.pem` file that AWS lets you download once, when the instance is created, stays with the client. Whoever holds the private key can log in. The client proves that it holds the key by signing a challenge, so the private key itself never travels to the server. SSH also has the reverse check: the server has its own *host key*, which lets the client confirm it is talking to the right machine. That is what the "Are you sure you want to continue connecting?" question on a first connection is about.

**GitHub Secrets.** A workflow file is committed, and in this public repository anyone can read it, so it can't contain a private key. GitHub stores such values separately, encrypted, as *Actions secrets*. A workflow refers to one as `${{ secrets.EC2_SSH_KEY }}`. GitHub inserts the value only when the run starts, and replaces it with `***` wherever it would appear in the log. Nobody can read a secret back, through the website or the API; only its name and when it was last updated are visible. This repository has exactly the two secrets the CD tutorial asks for, both last updated around 13:00 UTC on 22 November 2026 **[Verified]**: `EC2_HOST`, the server's public address, and `EC2_SSH_KEY`, the whole private key file. GitHub doesn't give secrets to workflows started by pull requests from *forks*, other people's copies of a public repository, so a stranger's pull request can't read them.

**systemd** is Ubuntu's service manager, the first program the system starts. It starts long-running programs, keeps them running, restarts them and collects their logs. Each program it manages is a *unit*, described by a small unit file. The AWS tutorial's unit for the registry, `/etc/systemd/system/registry.service`, contains, in short **[Course tutorial]**:

```ini
[Service]
WorkingDirectory=/home/ubuntu/ArgoPilot/services/registry-service
ExecStart=/home/ubuntu/ArgoPilot/services/registry-service/.venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

In words: run uvicorn from the service's own virtual environment, in the folder that contains `main.py`, listening on every network address (`0.0.0.0`) at port 8000. If the program crashes, start it again. And once the unit is *enabled*, start it at every boot. The README on `p2` lists the operator's commands **[Documented]**: `sudo systemctl status registry.service` shows whether it runs, `sudo systemctl restart registry.service` restarts it, and `sudo journalctl -u registry.service -n 50` shows its last 50 log lines. The unit file actually installed on the server isn't in the repository, so its exact contents are **[Not verified]**.

**Why a restart is needed.** A running Python program has already loaded its code into memory, so new files on disk change nothing until the process is replaced. `systemctl restart` stops the running uvicorn process by sending it SIGTERM, the standard polite request to exit, waits for it to end, and starts a new process, which loads the new code.

### 13.6 The CD workflow, step by step

This is `deploy-registry.yaml` on `main` at `77f7ab0`, in full:

```yaml
name: deploy-registry

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - name: Deploy registry-service
        uses: appleboy/ssh-action@v1.2.5
        with:
          host: ${{ secrets.EC2_HOST }}
          username: ubuntu
          key: ${{ secrets.EC2_SSH_KEY }}
          script: |
            set -e
            cd /home/ubuntu/ArgoPilot
            git fetch origin main
            git reset --hard ${{ github.sha }}
            cd services/registry-service
            /home/ubuntu/.local/bin/uv sync --locked
            sudo systemctl restart registry.service
```

**The trigger** is every push to `main`, which under the ruleset means every merged pull request. There is no `paths` filter, so a pull request that changes only documentation also redeploys and restarts the registry.

**The runner** doesn't check out the code, and doesn't need to: its only job is to open an SSH connection and send a script. The step uses `appleboy/ssh-action`, a third-party action. The run log shows it downloading a separate program, `drone-ssh` version 1.8.2, which makes the connection. It connects as `ubuntu` to the address in `EC2_HOST` on port 22, with the key in `EC2_SSH_KEY`. It waits up to 30 seconds for the connection and allows the script up to 10 minutes; those are the action's defaults, visible in the log **[Verified]**. No host-key fingerprint is configured, so the server's identity isn't checked; the CD tutorial says the same **[Course tutorial]**.

Before the script is sent, GitHub replaces `${{ github.sha }}` with the full SHA of the commit that triggered this run. The script then runs on the server, line by line:

1. **`set -e`** stops the script at the first command that fails. The action then reports failure, and the job turns red.
2. **`cd /home/ubuntu/ArgoPilot`** enters the server's own Git clone of the repository. The log shows the clone fetching from GitHub over HTTPS. Because the repository is public, fetching needs no credentials on the server.
3. **`git fetch origin main`** downloads the new commits from GitHub without changing any file yet. In the latest run the log shows `b27acfa..77f7ab0  main -> origin/main`.
4. **`git reset --hard 77f7ab0…`** makes the files on the server exactly the files of that commit. A change made by hand to a tracked file on the server is thrown away. Files Git doesn't track, such as `.venv`, `registry.db` and `.env`, are left alone, so the data and the local configuration survive a deploy. The log shows `HEAD is now at 77f7ab0 Merge pull request #9…`.
5. **`/home/ubuntu/.local/bin/uv sync --locked`** installs exactly the locked packages into the service's `.venv`. The full path is needed because an SSH session that only runs a script doesn't load the login settings that put `uv` on the `PATH`, the list of folders in which the shell looks for programs **[Course tutorial]**. In the latest run nothing needed installing: "Resolved 32 packages… Checked 28 packages". By default `uv sync` also installs the `dev` group, so test tools such as pytest end up on the server too.
6. **`sudo systemctl restart registry.service`** replaces the running registry process with one that runs the new code.

If every line succeeds, the action prints "Successfully executed commands to all hosts." and the run is green. Running the same deploy twice leaves the server in the same state, so the deploy is idempotent (Section 7.5).

**Why the commit SHA, and not `git pull`?** The first version of the workflow, merged in pull request #8, ran `git checkout main` and `git pull`, exactly as in the CD tutorial. That always deploys the current tip of `main`, its latest commit, whichever run executes it. The tutorial's exercise "Deploy this run's commit" shows why that matters. If a merge breaks production, the natural rollback is to re-run the last good deploy, but with `git pull` the re-run just deploys the broken tip again. With `git reset --hard ${{ github.sha }}`, each run deploys its own commit, and a re-run keeps the same SHA. Re-running an older, good run therefore puts the older version back on the server, while `main` on GitHub still has the bad commit until a fix is merged **[Course tutorial]**. Pull request #9 made that change on 22 November 2026.

One subtlety follows from how GitHub re-runs work **[Not verified by trying it]**: a re-run uses the workflow file as it was at that run's commit. The deploy run for `b27acfa`, from pull request #8, still contains the old `git pull` script, so re-running it would deploy the tip of `main`, not `b27acfa`. Rollback by re-run works only to commits from `77f7ab0` onward.

### 13.7 What happens after merging into main

Here is the whole chain for one change, from the developer's laptop to the running registry.

```mermaid
sequenceDiagram
    participant D as Developer
    participant G as GitHub
    participant C as CI runners
    participant R as Deploy runner
    participant E as EC2 instance
    D->>G: push branch, open pull request into main
    G->>C: pull_request event
    C-->>G: test and audit pass
    D->>G: Merge, allowed by protect-main
    G->>G: merge commit on main, a push event
    G->>R: start deploy-registry with the commit SHA
    R->>E: SSH to port 22 as ubuntu, with EC2_SSH_KEY
    E->>G: git fetch origin main
    E->>E: git reset --hard SHA, uv sync --locked
    E->>E: sudo systemctl restart registry.service
    E-->>R: script exit code 0
    R-->>G: run green
```

In words, step by step:

1. The developer pushes a branch and opens a pull request into `main`.
2. GitHub starts the CI workflow, and two fresh runners run `test` and `audit`.
3. When both pass, the `protect-main` ruleset allows the merge, and the developer clicks Merge.
4. GitHub creates the merge commit on `main`. That is a push to `main`.
5. The push starts `deploy-registry` on a new runner, a temporary machine provided by GitHub, not the EC2 instance. GitHub inserts the two secrets and the commit's SHA.
6. The runner downloads the SSH action and opens an SSH connection to the instance's port 22.
7. On the instance, the script fetches the new commits, resets the files to exactly the merged commit, and installs the locked packages.
8. systemd stops the old registry process and starts a new one on the new code. While the process restarts, requests to the registry fail for a moment; how long wasn't measured.
9. The script's success travels back over SSH, and the run turns green.

What the chain doesn't contain matters just as much: **nothing checks that the new version works.** No step calls `/health` after the restart. With the tutorial's unit file, which sets no `Type=`, systemd treats the service as a "simple" one, and `systemctl restart` reports success as soon as the new process has been started, not when the registry answers. A version that crashes at startup would still give a green run, and `Restart=on-failure` would try to start it a few more times before systemd gives up. The CD tutorial's own check is manual. On the instance, `git -C /home/ubuntu/ArgoPilot log -1 --oneline` should show the merged commit, and `curl -fsS http://127.0.0.1:8000/health` should return `{"status":"ok"}` **[Course tutorial]**. Whether that check was done after the latest deploy isn't recorded **[Not verified]**.

Between the merge and the end of a successful deploy, `main` and the server hold different versions. For pull request #9 that gap lasted almost five minutes, from 20:44:11 to 20:48:56, because the first attempt failed.

### 13.8 How to detect a failed workflow or deployment

**A failed CI check** shows on the pull request page as a red cross next to `test` or `audit`, and the Merge button stays blocked. "Details" opens the log of every step. If the tests ran, the `coverage-report` artifact on the run's summary page shows which lines were missed.

**A failed deployment** shows on the repository's **Actions** tab as a red `deploy-registry` run, with the failing step and its log. From a terminal, `gh run list` lists recent runs, and `gh run view <run id> --log-failed` prints the log of the failed step. GitHub normally also notifies the person whose push started a failed run, depending on their notification settings **[Not verified]**.

**A real example.** The first attempt to deploy pull request #9 failed after 30 seconds, with one line in the log **[Verified]**:

```
dial tcp ***:22: i/o timeout
```

Read it from right to left. `i/o timeout`: nothing answered in time. `:22`: on the SSH port. `dial tcp ***`: while opening a network connection to the address in `EC2_HOST`, which GitHub masked. So the runner couldn't even reach the instance. Typical causes are a stopped instance, a public address that changed after a stop and start, a security group that doesn't let the runner in, or a passing network problem. Both secrets were last updated hours earlier, so both attempts used the same address; whatever was wrong at 20:44 had changed by 20:48. The log can't say what it was, and the cause isn't recorded **[Not verified]**. Four minutes later the run was started again by hand, and the second attempt succeeded. The failure was harmless: the script never started, so the server simply stayed on the previous version, `b27acfa`.

**What turns a deploy red:** the server can't be reached; the key is refused; `git fetch` can't reach GitHub; the commit isn't found; `uv sync --locked` fails, for example because the lockfile doesn't match or the package index, the online store uv downloads packages from, is unreachable; or `systemctl` fails, for example because the unit doesn't exist.

**What a green deploy doesn't rule out:** a new version that crashes at startup, a broken `.env` on the server, a missing database, or a registry that runs but answers with errors. None of these turns the run red. They can only be found on the server, with `sudo systemctl status registry.service`, `sudo journalctl -u registry.service` and `curl http://127.0.0.1:8000/health`, or from outside with a request to the public address on port 8000, if the security group allows it. There is no monitoring and no alerting.

### 13.9 Security implications and limitations

The pipeline follows the course tutorials, which teach the mechanism step by step. It isn't a hardened production setup, and a reviewer who asks "is it secure?" deserves a precise answer.

1. **The deploy key is effectively the key to the whole server.** `EC2_SSH_KEY` logs in as `ubuntu`, and `ubuntu` can run any command as administrator without a password. Whoever obtains that key controls the instance: they can read the registry's data and its `.env`, change the code, or use the machine for something else. In the CD tutorial the secret holds the key the instance was launched with, which is also the developer's own login key **[Course tutorial]**; whether a separate deploy key is used here is **[Not verified]**. GitHub keeps the secret encrypted and masks it in logs, and only someone who can push to the repository can write a workflow that uses it. The repository has exactly one person with that access, its owner **[Verified]**.
2. **A third-party action receives the key, pinned only by a tag.** `appleboy/ssh-action@v1.2.5` is the version the CD tutorial uses. But a tag can be moved, while the CI workflow pins every action to a commit SHA. This action is the one that receives the private key, so it is the one where pinning matters most. It also downloads a second program, `drone-ssh`, each time it runs. Pinning the action to its commit SHA would at least remove the movable tag from the chain.
3. **The server's identity isn't checked.** Without a host-key fingerprint, the runner can't tell the real instance from another machine answering at the same address. Because SSH key login never sends the private key, an impostor wouldn't learn it, but the deploy could go to the wrong machine. The action's `fingerprint` setting would pin the host key.
4. **Port 22 has to be reachable from GitHub.** GitHub's hosted runners connect from a large and changing pool of addresses, so in practice the SSH port must be open to the whole internet for this design to work, and it is scanned there constantly. What protects it is key-only login, which is the default on Ubuntu's EC2 images **[Not verified on this instance]**.
5. **The registry API may be open to the internet without authentication or TLS.** If the security group has the AWS tutorial's rule for port 8000 from `0.0.0.0/0`, anyone on the internet can read every farm and plot, including field coordinates, and create, change or delete them, over plain HTTP. Part 2 lists the missing authentication; on a public address it stops being theoretical. The actual rule is **[Not verified]**.
6. **No health check and no automatic rollback** (Section 13.7). A green run means "restarted", not "working". Rollback is a manual re-run, and only to commits from `77f7ab0` onward.
7. **Every push to `main` restarts the registry**, including documentation-only merges, with a short interruption each time. There is one instance and no load balancer in front of it (a component that spreads requests over several instances, so one can restart while the others answer), so a deploy can't avoid that interruption.
8. **Overlapping deploys aren't prevented.** The workflow has no `concurrency` setting, so two merges in quick succession start two deploy runs that can overlap. Each resets the server to its own commit, and whichever finishes last wins, which could be the older one. With one developer this is unlikely; a `concurrency` group would make the runs wait for each other.
9. **The checks cover only the registry.** CI tests nothing else, and nothing re-tests the merged commit (Section 13.4).
10. **Some properties are good, and worth stating too.** The workflow token that GitHub gives every run is read-only by default in this repository **[Verified]**, and the deploy workflow doesn't use it at all. Secrets appear neither in the repository nor in the logs. The deploy is repeatable. And a failed connection leaves the server untouched.

Natural next steps, none of them implemented:

- A final script line that calls `/health` with a few retries, so a broken version turns the run red.
- `ssh-action` pinned to a commit SHA, and the server's host key pinned with `fingerprint`.
- A separate deploy key whose `sudo` rights cover only `systemctl restart registry.service`.
- A `concurrency` group, and a `paths` filter so that documentation changes don't restart the service.
- An Elastic IP.
- A security group that opens port 8000 only to known addresses, or HTTPS through a reverse proxy, a web server such as nginx that sits in front of the application, handles the encryption and forwards each request.
- `uv sync --locked --no-dev` on the server.
- CI workflows for the weather-service, planner and frontend.

### 13.10 What runs on AWS, and what stays local

| Component | Where it runs | Evidence |
| --- | --- | --- |
| registry-service, code from `main` at `77f7ab0` | The EC2 instance, under systemd | **[Verified]** The deploy log shows the server's files reset to `77f7ab0` and a successful restart command. That the service answered afterwards is **[Not verified]** |
| The EC2 registry's database | On the instance: SQLite or PostgreSQL, unknown | `main`'s registry uses the SQLite file `registry.db` unless `DATABASE_URL` is set, and the AWS tutorial seeds SQLite with `bash seed_registry.sh` **[Course tutorial]**. The server's actual setting is **[Not verified]** |
| weather-service, planner-service, frontend | The developer's Mac only | They exist only on `p2`, which isn't merged. Even after the merge, the deploy script restarts only `registry.service`, so their code would be copied to the server but not run **[Verified from the script]** |
| The P2 "production" database, `agropilot-pg` | Docker on the developer's Mac | Section 7.10 |
| CI's PostgreSQL | A service container on a GitHub runner, discarded after each run | The workflow file |
| CI and deploy runners | Temporary virtual machines that GitHub provides and deletes after each job | The workflow files and run logs |

Two clarifications follow from the table.

First, the version on EC2 isn't the P2 version. `main`'s registry is the P1 registry plus PostgreSQL support. The registry changes made on `p2`, such as the pydantic-settings configuration, the safer seed script and `GET /v1/farms/{id}/area`, will reach the server only with the P2 merge. That merge will be the first deploy that changes the registry's configuration code, so it is worth watching that run and checking `/health` on the server afterwards.

Second, "production" means two different things in this project. For the P2 specification, the production database is the PostgreSQL container on the developer's Mac, which the instructor accepted. For the course's CD tutorial, the production environment is the EC2 instance. Neither is a production system in the industry sense, and it would be wrong to say "the P2 system is deployed to AWS".

> **Interview follow-up:** "Your deploy run is green. Is production working?"
>
> **Model answer:** Not necessarily. Green means every command in the script succeeded: the server reached the merged commit, installed the locked packages, and systemd accepted the restart. It doesn't mean the registry answers, because nothing calls `/health` afterwards, and `systemctl restart` returns as soon as the new process has started. I'd check `systemctl status` and `curl /health` on the instance. The first improvement I'd make is a health check as the script's last line, so that a broken version turns the run red.

> **Interview follow-up:** "What can someone do with the `EC2_SSH_KEY` secret?"
>
> **Model answer:** Everything. It logs in as `ubuntu`, which has passwordless `sudo`, so it is equivalent to administrator access to the instance and to the registry's data. That's why it lives only in GitHub's encrypted secrets, and only the repository owner can write workflows that use it. I'd also pin the action that receives it to a commit SHA, and limit the key's `sudo` rights to restarting the one service.

---

## Part 14 — The engineering decisions that matter

Most decisions have already appeared in context. This is the short list of the ones worth defending in a presentation, each with its main alternative and its cost.

1. **Separate registry, weather and planner services** **[P2 spec]**. Each has one job and can fail, be tested and evolve on its own. The cost: three network hops for one plan, three processes to run, and error translation at every boundary.
2. **Keep SQLite and add PostgreSQL, behind SQLAlchemy Core** (JL-007). The decisive benefits: fast local tests and identical SQL on both backends. The alternative was a hand-written driver adapter. The cost: a large dependency, and two backends whose differences (types, NUL, error codes) must be handled explicitly.
3. **A dedicated weather-service with a grid-cell cache** **[P2 spec, plus project choices JL-021]**: a trustworthy data path, low provider usage and resilience in one place. The cost: an in-memory cache that is lost on restart and not shared between instances.
4. **Fail closed everywhere** **[P2 spec, FR-2.8 and FR-2.14]**: strict validation at every boundary, whole-forecast rejection, no defaults. The cost: more 503s. A single bad value blocks a whole plan, which is the right trade for a system whose worst failure is a silent zero.
5. **A pure engine, separate from HTTP orchestration** **[Project decision]**: the calculation can be tested against hand calculations without any service. The cost: the router has to convert and pass everything explicitly.
6. **A simplified daily soil-water bucket** (JL-011 to JL-014, JL-017): single Kc, refill to full, same-day look-ahead, rain in the morning, a 24-hour cap. It is checkable by hand and close to FAO-56's structure, at the cost of precision (Section 8.16).
7. **An explicit starting-water assumption, and a simulation option** (JL-011): the plan always states that its start is an assumption, and lets the user explore another start. The cost: the default can say "no irrigation" for a dry field, and simulated numbers can look authoritative, hence the badge and warning.
8. **Refuse out-of-season plans with 409** (JL-020): never invent a Kc outside FAO's curve. The cost: no 7-day plan near the season's end, and the seed plots can't be demonstrated without adding in-season plots (JL-015).
9. **Server-side frontend** **[P2 spec]**: the browser never sees services, URLs or keys. The cost: every page render waits on server-side calls, and it needs Suspense streaming to stay responsive.
10. **Required checks before every merge** **[Course tutorial]**: the `protect-main` ruleset blocks a merge into `main` until `test` and `audit` pass, and the CI actions are pinned to commit SHAs **[Project decision]**. The cost: the checks cover only the registry, and the merged result isn't tested again.
11. **Deploy every merge automatically, pinned to the run's commit** **[Course tutorial]**. A merge into `main` deploys the registry to EC2 by itself, and each run deploys its own commit, so re-running an older run is a one-click rollback (Part 13). The cost: a green deploy proves only that the service was restarted, not that it works; the SSH key stored in GitHub gives full control of the server; and only the registry is deployed.

---

## Part 15 — Limitations, gaps, and what was not verified

Collected in one place, grouped by kind.

**Model limitations:** no soil measurement; a forecast treated as certain; a daily model; the 50 % threshold instead of FAO's p; single Kc with fixed stages and fixed root depth; a plot-average bucket that ignores drip's partial wetting; no efficiency, runoff or capillary rise; no stress reduction near an empty bucket; the 24-hour cap as a modelling limit; no field validation.

**System limitations:** no authentication, authorization or TLS; secrets in plain `.env` files; a superuser database account; `/health` endpoints that don't report dependencies; an imprecise 503 message for a contract break; a frontend that doesn't validate the registry's JSON at runtime; an in-process cache that isn't shared or persisted; synchronous endpoints that can exhaust the thread pool when upstreams are slow; no rate enforcement, backoff or 429 handling; Open-Meteo's free tier being non-commercial.

**Testing gaps:** no automated test of the real services together; no contract tests; no frontend tests; no CI for the weather-service, planner or frontend; no literal `lat` → `latitude` test; no planner or frontend performance measurement.

**Deployment limitations:** only the registry is deployed; no health check after a deploy and no automatic rollback; an SSH key in GitHub Secrets that has passwordless `sudo` on the server; a tag-pinned third-party deploy action; no host-key check; an SSH port that must be reachable from GitHub's runners; a registry API without authentication or TLS that may be reachable from the internet; a restart, with a short interruption, on every push to `main`; no protection against overlapping deploys; no re-test of the merged commit.

**Evidence that wasn't re-verified for this guide:** the PostgreSQL benchmark (recorded at 18.70 ms in the committed plan; a later local note says 13.84 ms); the PostgreSQL test run of `p2`'s registry (CI ran `main`'s registry on PostgreSQL on 18 and 22 November); the frontend production build; the phone layout at 375 px; the skill evaluation results; the Explorer's build checks (a local note records "all checks passed"); and everything on the EC2 instance itself: its systemd unit, its database, its security group rules, whether it has an Elastic IP, whether `/health` answered after the latest deploy, and the cause of the failed first deploy attempt on 22 November.

**Verified for this guide on 22 November 2026:** the planner (174 tests), weather-service (135) and registry on SQLite (272 passed, 6 skipped) suites; 100 % branch coverage for the planner and weather-service; both local benchmarks (registry 10.73 ms, weather 8.57 ms, both PASS); frontend lint; every worked-example number, by running the engine; the seed plots being out of season; that no `.env` file is tracked by Git; Open-Meteo's published free-tier limits; and, through GitHub's API, the CI and deploy workflows on `main` at `77f7ab0`, the `protect-main` ruleset, the names of the two secrets, the CI run for pull request #9 (263 and 265 tests passed, 100 % coverage, no known vulnerabilities) and the history and logs of both deploy runs.

---

## Part 16 — Interview practice

Short questions a reviewer might ask, with concise model answers. Several earlier sections have their own follow-ups; these add to them.

**"Walk me through what happens when I open a plot page."**
The Next.js server calls the registry for the plot's name and the planner for the plan, in parallel. The planner validates the request, reads the plot, checks the season, reads the soil and emitter, gets the forecast from the weather-service, which uses its cache or Open-Meteo, runs the engine and rounds the output. The frontend shows today's recommendation first, then the 7 days.

**"Where is the irrigation logic?"**
Only in `planner-service/engine.py`. The frontend formats. The registry stores. The weather-service provides ET0 and rain.

**"Why does the plan say 'no irrigation' today when it's hot?"**
Because by default the plan assumes the bucket is full this morning, and one hot day doesn't empty half of it. On Case 3 the first irrigation is on day 6. If the grower knows the soil is drier, the simulation option shows what happens with a lower start. And the plan says plainly that its start is an assumption.

**"Why 409 for an out-of-season plot, and not 404 or 422?"**
The plot exists, so it isn't 404, and the request is well-formed, so it isn't 422. The conflict is with the plot's current state: there is no FAO Kc for those days. 409 Conflict describes exactly that.

**"Why does the planner use a 12-second timeout for weather but 3 seconds for the registry?"**
The weather-service may legitimately take about 9 seconds (three attempts of 3 seconds) before returning a stale forecast. The planner must outwait that, or it would throw away a good answer. The registry does a local database lookup and has no retries, so 3 seconds is plenty.

**"What happens if Open-Meteo is down for two days?"**
For up to 24 hours after the last good forecast, plans still work, marked stale. After that, or as soon as the stale forecast no longer covers the requested days, the weather-service answers 503 and the planner answers 503 naming the weather-service. No plan of guessed numbers is ever returned.

**"What's the difference between `stale: true` and a 503?"**
`stale: true` is a degraded success: real numbers from an older forecast, clearly marked. A 503 means there are no trustworthy numbers at all.

**"Why exact fractions?"**
So that a day ending exactly at half really ends at half, and .5 ties round as hand calculations do. Floats got both wrong in worked examples B1 and B3.

**"How do you test a timeout without waiting?"**
The fake transport raises `httpx2.ReadTimeout` instantly, which is exactly the exception a real timeout produces. The code path is identical; only the waiting is skipped.

**"How do you test something that depends on the time of day?"**
The current time is a dependency function (`utc_now` in the weather-service, `utc_today` in the planner), and tests replace it with a value they control and move forward.

**"Why is the registry's error format different from the planner's?"**
The registry is P1 code, where the instructor accepted FastAPI's default `{"detail": ...}`. P2 specified `{code, detail}` for the new services. The planner translates, so the frontend sees only one format.

**"What do CI and CD mean in your project, concretely?"**
CI is `registry-service.yaml`. On every pull request into `main` it runs the registry's tests on SQLite, then on PostgreSQL, requires 100 % branch coverage over both runs, and audits the locked packages for known vulnerabilities. The `protect-main` ruleset makes both jobs required before a merge. CD is `deploy-registry.yaml`. On every push to `main`, which means every merge, it connects to the EC2 instance over SSH, resets the server's copy of the repository to the merged commit, installs the locked packages and restarts the registry's systemd service.

**"What exactly happens when you click Merge?"**
GitHub creates a merge commit on `main`, which counts as a push. That push starts `deploy-registry` on a fresh GitHub runner. The runner reads the host and the key from GitHub Secrets, opens SSH to the instance, and runs the script: `git fetch`, `git reset --hard` to the run's commit SHA, `uv sync --locked`, `systemctl restart`. When the server is reachable, the whole run takes a few seconds; the successful deploy of pull request #9 took seven.

**"Why `git reset --hard` to the commit SHA, and not `git pull`?"**
So that each run deploys its own commit, not whatever happens to be the tip of `main`. Then re-running an older, good run is a rollback. With `git pull`, a re-run would deploy the broken tip again.

**"How do you roll back a bad deployment?"**
Re-run the last good `deploy-registry` run from the Actions tab. That works for runs from `77f7ab0` onward, because older runs still contain the `git pull` script. The server goes back to the good commit, but `main` still has the bad one, so the real fix is a revert, a new commit that undoes the bad one, merged through a pull request, which then deploys normally.

**"A deploy failed with `dial tcp ***:22: i/o timeout`. What does that mean?"**
The runner couldn't open a network connection to the server's SSH port at all. The instance may have been stopped, its public address may have changed, or the firewall may have blocked the runner. Nothing on the server changed, because the script never started. Fix the cause, update `EC2_HOST` if the address changed, and re-run. It happened to us once, on 22 November, and the re-run four minutes later succeeded.

**"Can someone merge broken code into `main`?"**
Not without changing the ruleset. `main` accepts changes only through a pull request whose `test` and `audit` checks passed, and force pushes and deletion are blocked. But the checks test only the registry, no approval is required, and the merged combination isn't tested again, so broken code in the other services, or a bad interaction between two pull requests, could still get in.

**"Is the P2 system deployed to AWS?"**
No. Only the registry is deployed, from `main`, which doesn't contain P2's other services yet. The weather-service, planner and frontend run on the developer's machine, and P2's own production database is a PostgreSQL container on that machine. Even after the P2 merge, the deploy script restarts only the registry.

**"What would you change first to make this production-ready?"**
Authentication and authorization on the APIs; secrets in a secrets manager, with a least-privilege database user; TLS between services; an automated end-to-end or contract test plus CI for all services; a cooldown and 429 handling in the weather-service; a health check at the end of every deploy, with the deploy action and the server's host key pinned and a deploy key that can only restart the service; and a real soil-moisture input instead of the full-bucket assumption.

**"What is the single most important design rule in this system?"**
Never present an invented number as real. Missing or unusable data becomes an explicit error, because in irrigation a silent zero means "no water needed".

---

## Part 17 — Recap

AgroPilot P2 answers one question for a grower: should this plot be watered today, and for how long? It does so with three focused Python services and a server-rendered web frontend. The **registry** stores plots and catalogues and now runs on SQLite or PostgreSQL through one configuration variable, with SQLAlchemy Core, one transaction per request and careful error classification. The **weather-service** is the only gateway to Open-Meteo: it validates every value, caches one 7-day forecast per 0.1° cell for 3 hours, retries twice, serves a forecast up to 24 hours old as clearly stale, and otherwise says plainly that it is unavailable. The **planner** gathers the plot, soil, emitter and forecast, refuses anything it can't trust, and runs a pure engine that follows a documented, simplified FAO-56 model: Kc from the growth stage, ETc = Kc × ET0, a soil bucket sized by TAW, irrigation when the level would fall below half, a refill to full, and a 24-hour cap, all in exact arithmetic and rounded only at the end. The **frontend** calls everything from the server, puts today's recommendation first, and explains stale data and failures in plain words.

The thread running through every layer is **fail closed**. A missing number becomes an error, never a zero, because a zero would quietly tell the grower not to water. The testing strategy follows from the architecture: a pure engine tested against hand calculations, endpoints tested against fake services and a controllable clock, 100 % branch coverage, and benchmarks with explicit pass rules. The latency targets that exist were measured and met with a wide margin.

Around the code sits a delivery pipeline built by following the course tutorials. Every pull request into `main` runs the registry's tests on SQLite and on PostgreSQL, with 100 % coverage over both runs, plus a dependency audit, and the `protect-main` ruleset blocks the merge until both pass. Every merge then deploys the registry to an Ubuntu EC2 instance over SSH: the server moves to exactly the merged commit, installs the locked packages and restarts the systemd service, and an older run can be re-run as a rollback. Only the registry is deployed. The weather-service, planner and frontend run on the developer's machine, so the P2 system as a whole isn't deployed anywhere.

The limits are just as important to state. The plan starts from an assumed soil level, trusts the forecast, simplifies FAO-56, and has never been checked against a real field, so it is a transparent model, not an agronomic guarantee. The system has no authentication, no rate enforcement towards Open-Meteo, no automated end-to-end or frontend tests, and no CI outside the registry. The deployment has no health check, so a green deploy means "restarted", not "working", and its SSH key is effectively administrator access to the server. What happens inside the EC2 instance couldn't be verified without logging in to it. Knowing exactly which claims are verified and which are not is the difference between describing a system and understanding it.
