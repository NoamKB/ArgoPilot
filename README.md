# AgroPilot

AgroPilot helps a grower manage agricultural crops with modern AI. It answers the grower's daily question: *should I
water this plot today, and for how many minutes?*

The project is built in course assignments, each on top of the previous one:

| Assignment | Status | What it added | Specification |
| --- | --- | --- | --- |
| P1 — Registry Service API | Complete | `registry-service`: farms, plots, and the crop, soil and emitter catalogues | [p1_registry_api.md](https://github.com/alonitac/OzVeruach26/blob/main/tasks/p1_registry_api.md) |
| P2 — Weather, planner, and the daily plan | Complete | PostgreSQL for the registry, `weather-service`, `planner-service`, and the `frontend` | [p2.md](https://github.com/alonitac/OzVeruach26/blob/main/tasks/p2.md) |

Instructor clarifications that change or add to a specification are in
[`docs/instructor-clarifications.md`](docs/instructor-clarifications.md).

## How the system fits together

```text
                                      ┌────────────────────┐
                               ┌────► │  registry-service  │ ──► SQLite (local) or PostgreSQL (production)
                               │      │  :8000             │
 ┌─────────┐   ┌────────────┐  │      └────────────────────┘
 │ Browser │ ─►│ frontend   │ ─┤      ┌────────────────────┐      ┌────────────────────┐
 └─────────┘   │ :3000      │  └────► │  planner-service   │ ───► │  registry-service  │
               └────────────┘         │  :8002             │      └────────────────────┘
                                      │                    │      ┌────────────────────┐
                                      │                    │ ───► │  weather-service   │ ──► Open-Meteo
                                      └────────────────────┘      │  :8001             │
                                                                  └────────────────────┘
```

Each service is self-contained in `services/<name>/`, with its own dependencies, its own `.env`, and its own README.
Services never import each other's code; they talk over HTTP only. The browser talks only to the frontend, which
calls the services from the server.

| Service | Port | What it does | Guide |
| --- | --- | --- | --- |
| `registry-service` | 8000 | Stores farms and plots, and serves the crop, soil and drip-emitter catalogues. SQLite on a developer's machine, PostgreSQL in production. | [README](services/registry-service/README.md) |
| `weather-service` | 8001 | Daily forecast (ET0 and rain) from Open-Meteo, cached in memory per 0.1° grid cell, with retries and a stale fallback. | [README](services/weather-service/README.md) |
| `planner-service` | 8002 | The 1–7 day irrigation plan of a plot (FAO-56), from the registry and the forecast. | [README](services/planner-service/README.md) |
| `frontend` | 3000 | Next.js web app: the farms and plots, today's recommendation, the 7-day plan, and a status line for the three services. | [README](services/frontend/README.md) |

## Run the whole system locally

### Prerequisites

| Tool | Check |
| --- | --- |
| [uv](https://docs.astral.sh/uv/) (installs Python 3.12 by itself) | `uv --version` |
| `sqlite3` command-line tool (preinstalled on macOS) | `sqlite3 --version` |
| Node.js 24, through [nvm](https://github.com/nvm-sh/nvm) or installed directly | `node --version` |
| `curl`, and optionally [`jq`](https://jqlang.org/) to format JSON | `curl --version` |
| Internet access (weather-service calls Open-Meteo; no API key needed) | — |

### Start the services

Start them in this order, **each in its own terminal**, from the repository root. Each one keeps running until you
press `Ctrl+C`. The "first time" lines are needed only once.

**Terminal 1: registry-service** (on SQLite; PostgreSQL is in its [README](services/registry-service/README.md#5-run-with-postgresql))

```bash
cd services/registry-service
uv sync && bash seed_registry.sh          # first time: install, and create registry.db with the demo data
uv run uvicorn main:app --host 127.0.0.1 --port 8000
```

**Terminal 2: weather-service**

```bash
cd services/weather-service
uv sync && cp .env.example .env           # first time
uv run uvicorn main:app --host 127.0.0.1 --port 8001
```

**Terminal 3: planner-service**

```bash
cd services/planner-service
uv sync && cp .env.example .env           # first time
uv run uvicorn main:app --host 127.0.0.1 --port 8002
```

**Terminal 4: frontend**

```bash
cd services/frontend
nvm use                                   # Node 24 from .nvmrc (skip if Node 24 is your default)
npm install && cp .env.example .env.local # first time
npm run dev
```

The `cp` commands copy the safe example settings, which already point at the ports above. Don't run them again
later: they overwrite your own settings.

### Check that it works

In a fifth terminal:

```bash
curl http://127.0.0.1:8000/health         # each one: {"status":"ok"}
curl http://127.0.0.1:8001/health
curl http://127.0.0.1:8002/health
```

Then open http://localhost:3000. It lists two farms with four plots, and the status line at the top shows the three
services as up.

### Get a plan: add a plot that is in season

The four demo plots were planted in February to May 2026. Their seasons (tomato 180 days, bell pepper 210 days) are
over, so their plot pages say **"No plan for this plot"** (the planner answers `409 PLOT_OUT_OF_SEASON`). That is the
correct answer, not a bug.

To see a plan, add a tomato plot planted 60 days ago:

```bash
PLANTED=$(date -v-60d +%F)                # macOS; on Linux: date -d '60 days ago' +%F
curl -X POST http://127.0.0.1:8000/v1/plots -H "Content-Type: application/json" -d "{\"farm_id\": \"b7e2c0a0-3c1d-4f0a-9a11-0c5d2e6f1001\", \"name\": \"Demo in-season plot\", \"area_m2\": 1000, \"crop_id\": \"tomato\", \"planting_date\": \"$PLANTED\", \"soil_id\": \"loam\", \"row_spacing_m\": 1.5, \"emitter_spacing_m\": 0.4, \"emitter_id\": \"dripnet-pc-1.0\", \"lat\": 31.25, \"lon\": 34.79}"
```

The response is the new plot with its `id` (status `201`). Reload http://localhost:3000 and open "Demo in-season plot":
it shows today's recommendation and the 7-day plan. The plan assumes the soil is full this morning, so the first days
often need no water. To see a watering day on this in-season plot, use the simulation form below the plan, for
example a 40% start (`?soil=40` in the page address). A simulation changes only the starting soil water, not the
season: the demo plots still say "No plan for this plot" with any `?soil` value. The same plan as JSON:

```bash
curl "http://127.0.0.1:8002/v1/plots/<the new id>/plan" | jq .
```

Running the `POST` a second time gives `409`, because the farm already has a plot with that name. The plot stays in
`registry.db`; delete it with `curl -X DELETE http://127.0.0.1:8000/v1/plots/<the new id>`.

## Run the tests

Every test runs offline: the other services and Open-Meteo are replaced by fakes, and no test reads your `.env`.

| Service | Command (from the service folder) | What it checks |
| --- | --- | --- |
| `registry-service` | `uv run pytest` | The API on SQLite. For PostgreSQL and the 100% coverage over both, see its [README](services/registry-service/README.md#7-run-tests--coverage). |
| `weather-service` | `uv run pytest --cov` | All tests, 100% branch coverage |
| `planner-service` | `uv run pytest --cov` | All tests, including the skill's worked examples, 100% branch coverage |
| `frontend` | `npm run build && npm run lint` | Production build and ESLint (there are no frontend tests) |

The performance checks (NFR-1.1, NFR-2.2, NFR-2.3) are described in the registry and weather READMEs.

## Continuous integration and deployment

- **CI:** every pull request into `main` runs [`registry-service.yaml`](.github/workflows/registry-service.yaml):
  the registry tests on SQLite and PostgreSQL with 100% branch coverage, and a dependency vulnerability audit. The
  `protect-main` ruleset requires a pull request and both jobs to pass. weather-service, planner-service and the
  frontend have no CI workflow yet; run their checks locally (above).
- **CD:** every push to `main` runs [`deploy-registry.yaml`](.github/workflows/deploy-registry.yaml). It connects to
  the EC2 server over SSH, checks out exactly that commit, runs `uv sync --locked`, and restarts `registry.service`.
  Only registry-service is deployed.

## EC2 server

registry-service runs on an Ubuntu EC2 instance on AWS, managed by `systemd`, and starts automatically when the
instance boots.

### SSH access

```bash
ssh -i ~/.ssh/ozveruach-dev-ec2-key.pem ubuntu@<EC2_PUBLIC_IP>
ssh agropilot-ec2                         # the same, with the SSH alias below
```

### Managing the service

Run these commands on the EC2 instance:

```bash
sudo systemctl status registry.service    # Check status
sudo systemctl start registry.service     # Start service
sudo systemctl stop registry.service      # Stop service
sudo systemctl restart registry.service   # Restart service
sudo journalctl -u registry.service -n 50 # View recent logs
sudo journalctl -fu registry.service      # Follow logs
```

### Connecting after an EC2 restart

Stopping and starting an EC2 instance may change its public IP address. A normal reboot does not.

1. Open **AWS Console → EC2 → Instances**.
2. Select the instance and click **Instance state → Start instance**, if stopped.
3. Wait until the instance is running and its status checks pass.
4. Copy its new **Public IPv4 address** from the instance details.
5. On your local machine, update `HostName` in `~/.ssh/config`:

   ```sshconfig
   Host agropilot-ec2
       HostName <NEW_PUBLIC_IP>
       User ubuntu
       IdentityFile ~/.ssh/ozveruach-dev-ec2-key.pem
       IdentitiesOnly yes
   ```

6. Reconnect with `ssh agropilot-ec2`, and check that the service started by itself:

   ```bash
   sudo systemctl status registry.service
   curl http://127.0.0.1:8000/health
   ```

To test the API remotely, use the new public IP: `curl http://<NEW_PUBLIC_IP>:8000/health`. Remote access needs an
inbound Security Group rule for port 8000. If the IP changed, update the `EC2_HOST` secret of the GitHub repository
too, or the deployment workflow can't connect.

**Note:** stop the EC2 instance when it is not needed, to avoid compute charges. EBS storage charges may continue.

## Documentation

- [`docs/superpowers/`](docs/superpowers/): the design document and implementation plan for moving the registry to
  PostgreSQL, written with the Superpowers skills.
- [`services/planner-service/docs/research/fao56.md`](services/planner-service/docs/research/fao56.md): the FAO-56
  research behind the irrigation formulas.
- [`.claude/skills/irrigation-calc-reference/`](.claude/skills/irrigation-calc-reference/SKILL.md): the irrigation
  formulas, units, rounding rules and worked examples that the planner follows exactly.
- [`docs/judgment-log.md`](docs/judgment-log.md): significant engineering decisions and their reasons.
