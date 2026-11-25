import logging
from contextlib import asynccontextmanager

import httpx2
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from config import load_settings
from engine import OutOfSeason
from routers import plan
from upstream import PlotNotFound, UpstreamUnavailable

# uvicorn prints INFO lines only for its own loggers; "uvicorn.error" is its general log.
logger = logging.getLogger("uvicorn.error")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # A missing or invalid variable stops the service here, before it serves any request.
    settings = load_settings()
    logger.info(
        "Registry: %s (timeout %g s); weather: %s (timeout %g s)",
        settings.registry_url,
        settings.registry_timeout_seconds,
        settings.weather_url,
        settings.weather_timeout_seconds,
    )
    app.state.settings = settings
    with (
        httpx2.Client(timeout=settings.registry_timeout_seconds) as registry_client,
        httpx2.Client(timeout=settings.weather_timeout_seconds) as weather_client,
    ):
        app.state.registry_client = registry_client
        app.state.weather_client = weather_client
        yield


app = FastAPI(title="AgroPilot planner-service", version="0.1.0", lifespan=lifespan)
app.include_router(plan.router)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    # FR-2.12: {"code": "VALIDATION", "detail": "days: Input should be less than or equal to 7"}
    detail = "; ".join(f"{error['loc'][-1]}: {error['msg']}" for error in exc.errors())
    return JSONResponse(status_code=422, content={"code": "VALIDATION", "detail": detail})


@app.exception_handler(PlotNotFound)
async def plot_not_found_handler(request: Request, exc: PlotNotFound):
    # FR-2.12
    return JSONResponse(status_code=404, content={"code": "NOT_FOUND", "detail": "Plot not found."})


@app.exception_handler(OutOfSeason)
async def out_of_season_handler(request: Request, exc: OutOfSeason):
    # JL-020
    return JSONResponse(
        status_code=409, content={"code": "PLOT_OUT_OF_SEASON", "detail": "The plot is outside its growing season."}
    )


@app.exception_handler(UpstreamUnavailable)
async def upstream_unavailable_handler(request: Request, exc: UpstreamUnavailable):
    # FR-2.14: the detail names the service. The reason goes to the log only.
    logger.warning("Upstream failure: %s", exc)
    return JSONResponse(
        status_code=503,
        content={"code": "UPSTREAM_UNAVAILABLE", "detail": f"{exc.service} is unavailable or did not answer in time."},
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
