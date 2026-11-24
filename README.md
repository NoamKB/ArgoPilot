# AgroPilot

AgroPilot helps a grower manage agricultural crops with modern AI. The goal of the current assignment, P2, is to answer the grower's daily question: *should I water this plot today, and for how many minutes?*

The project is built in course assignments, each on top of the previous one. P1 is complete; P2 is in progress.

## Services

Each service is self-contained in `services/<name>/`, with its own dependencies and its own README for setup, running, testing, and troubleshooting. Services talk to each other over HTTP only.

| Service | Status | Port | What it does | Guide |
| --- | --- | --- | --- | --- |
| `registry-service` | **Implemented** | 8000 | Stores farms and plots, and serves the crop, soil, and drip-emitter catalogues. SQLite on a developer's machine, PostgreSQL in production. | [README](services/registry-service/README.md) |
| `weather-service` | Planned (P2) | 8001 | Daily forecast (ET0 and rain) from Open-Meteo, cached per area. | — |
| `planner-service` | Planned (P2) | 8002 | The 7-day irrigation plan for a plot, from the registry and the forecast. | — |
| `frontend` | Planned (P2) | 3000 | Web page with today's recommendation and the 7-day plan. | — |

To get started, follow the [registry-service Quick Start](services/registry-service/README.md#3-quick-start-sqlite).

## Assignments

| Assignment | Status | Specification |
| --- | --- | --- |
| P1 — Registry Service API | Complete | [p1_registry_api.md](https://github.com/alonitac/OzVeruach26/blob/main/tasks/p1_registry_api.md) |
| P2 — Weather, planner, and the daily plan | In progress (registry part complete) | [p2.md](https://github.com/alonitac/OzVeruach26/blob/main/tasks/p2.md) |

Instructor clarifications that change or add to a specification are in [`docs/instructor-clarifications.md`](docs/instructor-clarifications.md).

## Continuous integration

Every pull request into `main` runs [`.github/workflows/registry-service.yaml`](.github/workflows/registry-service.yaml): the registry tests on SQLite and PostgreSQL with 100% branch coverage, and a dependency vulnerability audit. `main` only changes through a pull request whose checks passed.

## EC2 Development Server

The project uses an Ubuntu EC2 instance on AWS.

### SSH Access

Configure your SSH key and connect using:

```bash
ssh -i ~/.ssh/ozveruach-dev-ec2-key.pem ubuntu@<EC2_PUBLIC_IP>
```

Alternatively, configure an SSH alias and run:

```bash
ssh agropilot-ec2
```

## EC2 Operations

The Registry Service runs on an Ubuntu EC2 instance, managed by `systemd`.

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

The service is enabled to start automatically when the instance boots.

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

6. Reconnect:

```bash
ssh agropilot-ec2
```

7. Verify that the service started automatically:

```bash
sudo systemctl status registry.service
curl http://127.0.0.1:8000/health
```

To test the API remotely, use the new public IP:

```bash
curl http://<NEW_PUBLIC_IP>:8000/health
```

Remote access requires an appropriate inbound Security Group rule.

**Note:** Stop the EC2 instance when it is not needed to avoid unnecessary compute charges. EBS storage charges may continue.

## Project resources

- **Presentations** ([`docs/presentations/`](docs/presentations/)): the P1 slides ([`p1-slides.pptx`](docs/presentations/p1/p1-slides.pptx), English, with Hebrew speaker notes) and the Hebrew [P1 presenter guide](docs/presentations/p1/p1-presenter-guide.md).
- **Request debuggers**: interactive step-by-step walkthroughs of how the registry handles a request.
  - [`request-debugger.html`](docs/presentations/p1/request-debugger.html): the P1 version (sqlite3).
  - [`request-debugger-sqlalchemy.html`](docs/presentations/p2/request-debugger-sqlalchemy.html): the SQLAlchemy and PostgreSQL version, built before the P2 configuration change.
  - Source and rebuild instructions: [`debugger-src/build_debugger.py`](docs/presentations/p2/debugger-src/build_debugger.py).
- **Learning**: [`docs/learning/p1-walkthrough.md`](docs/learning/p1-walkthrough.md) explains every P1 file, increment by increment.
- **Design records**:
  - [`docs/judgment-log.md`](docs/judgment-log.md): significant engineering decisions and their reasons.
  - [`docs/superpowers/`](docs/superpowers/): the design document and implementation plan for moving the registry to PostgreSQL.
