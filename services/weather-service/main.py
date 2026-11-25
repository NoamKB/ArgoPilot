import logging
from contextlib import asynccontextmanager

import httpx2
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from cache import ForecastCache
from config import load_settings
from routers import forecast
from routers.forecast import ForecastUnavailable

# uvicorn prints INFO lines only for its own loggers; "uvicorn.error" is its general log.
startup_logger = logging.getLogger("uvicorn.error")

RETRY_AFTER_SECONDS = 60


@asynccontextmanager
async def lifespan(app: FastAPI):
    # A missing or invalid variable stops the service here, before it serves any request.
    settings = load_settings()
    startup_logger.info(
        "Weather provider: %s (fresh %g h, stale up to %g h, %d retries)",
        settings.provider_base_url,
        settings.forecast_fresh_hours,
        settings.forecast_max_stale_hours,
        settings.provider_retries,
    )
    app.state.settings = settings
    app.state.cache = ForecastCache()
    with httpx2.Client(timeout=settings.provider_timeout_seconds) as client:
        app.state.http_client = client
        yield


app = FastAPI(title="AgroPilot weather-service", version="0.1.0", lifespan=lifespan)
app.include_router(forecast.router)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    # FR-2.4: {"code": "VALIDATION", "detail": "lat: Input should be less than or equal to 90"}
    detail = "; ".join(f"{error['loc'][-1]}: {error['msg']}" for error in exc.errors())
    return JSONResponse(status_code=422, content={"code": "VALIDATION", "detail": detail})


@app.exception_handler(ForecastUnavailable)
async def forecast_unavailable_handler(request: Request, exc: ForecastUnavailable):
    # FR-2.7
    return JSONResponse(
        status_code=503,
        content={"code": "UNAVAILABLE", "detail": "Weather provider unavailable and no usable cached forecast."},
        headers={"Retry-After": str(RETRY_AFTER_SECONDS)},
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
