# frontend

The AgroPilot web app for growers: the farms, their plots, and each plot's irrigation plan. Next.js (App Router),
TypeScript, Tailwind CSS and shadcn/ui.

| Page | Shows |
| --- | --- |
| `/` | Every farm with its plots; each plot links to its page (FR-2.15) |
| `/plots/{id}` | Today's recommendation first ("Water for N minutes" or "No irrigation today"), then the 7-day plan (FR-2.16). `?soil=40` simulates another starting soil level |

Every page also shows whether registry-service, weather-service and planner-service are up (`GET /health`, FR-2.19).

- **The browser never calls the services.** Pages fetch on the server, and every call lives in `src/lib/`
  (`registry.ts`, `planner.ts`, `health.ts`). There are no API routes and no `NEXT_PUBLIC_` variables.
- **Stale forecast (FR-2.17):** each affected day carries a "Stale forecast" badge, and a note says how old the
  forecast is.
- **Errors (FR-2.18):** the planner's error is shown in plain words. A down service is named, for example
  "weather-service is unavailable or did not answer in time." An out-of-season plot, an unknown plot and an unreachable
  planner each get their own message. Unexpected errors show a short message and a retry button, never a stack trace.
- **Starting soil water:** the planner can't measure the soil, so every plan says which starting level it assumed.
  By default that is "full (100%), default assumption, not a measurement".
- **Simulation (optional):** below the plan, a small form sets `?soil=0`–`100` in the page URL. The page passes it to
  the planner as `initial_soil_water_pct`, and the planner does the calculation. A simulated plan carries a
  "Simulation" badge and a note that it isn't a field-verified recommendation, with a stronger warning when the start
  is below the watering line or a day reaches the 24-hour limit. An invalid value, or a planner that doesn't echo the
  value back, shows a message instead of a plan. The code is in `src/lib/simulation.ts`,
  `src/components/simulation-form.tsx` and `src/components/simulation-notice.tsx`.
- **Phones (NFR-2.8):** below 640 px the 7 days are a list instead of a table, so a 375 px screen doesn't scroll
  sideways, and today's recommendation sits above the fold.

## Run

Node 24 (the repo's `.nvmrc`). Start registry-service (8000), weather-service (8001) and planner-service (8002) first.

```bash
cd services/frontend
nvm use                         # Node 24
npm install
cp .env.example .env.local      # first time; .env.local is git-ignored
npm run dev                     # http://localhost:3000
```

```bash
npm run build                   # production build
npm run lint                    # ESLint
```

## Configuration

`.env.local`, read on the server at request time:

| Variable | Example | Used for |
| --- | --- | --- |
| `REGISTRY_URL` | `http://127.0.0.1:8000` | Farms and plots, and the status line |
| `WEATHER_URL` | `http://127.0.0.1:8001` | The status line only (the planner calls weather-service itself) |
| `PLANNER_URL` | `http://127.0.0.1:8002` | The plan, and the status line |

A missing variable stops the page with "Something went wrong", and the server log names the variable.
