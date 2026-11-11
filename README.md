# AgroPilot

AgroPilot helps a grower manage agricultural crops with modern AI. 


## Where to start

Services live under `services/`. The service in the repository today is `registry-service`, a FastAPI application. 

```bash
cd services/registry-service
uv sync
uv run uvicorn main:app --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000/health. A running service returns `{"status": "ok"}`.

## Presentations

Assignment presentations live in [`docs/presentations/`](docs/presentations/): the slides (English, with Hebrew speaker notes) and a Hebrew presenter guide for each assignment, starting with P1.

[`request-debugger.html`](docs/presentations/request-debugger.html) is an interactive step-by-step walkthrough of how the registry service handles a request; its source and rebuild instructions are in [`debugger-src/`](docs/presentations/debugger-src/).
