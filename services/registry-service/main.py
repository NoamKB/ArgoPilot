import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exception_handlers import http_exception_handler
from sqlalchemy.exc import SQLAlchemyError

from db import describe_database_url, get_database_url, is_unavailable
from routers import catalogues, farms, plots

logger = logging.getLogger(__name__)
# uvicorn prints INFO lines only for its own loggers; "uvicorn.error" is its general log.
startup_logger = logging.getLogger("uvicorn.error")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Shows which database DATABASE_URL selected, e.g. when an empty value fell back to SQLite.
    # It does not connect, so the app still starts while the database is down.
    startup_logger.info("Database: %s", describe_database_url(get_database_url()))
    yield


app = FastAPI(title="AgroPilot registry-service", version="0.1.0", lifespan=lifespan)
app.include_router(farms.router)
app.include_router(plots.router)
app.include_router(catalogues.router)


@app.exception_handler(SQLAlchemyError)
async def database_error_handler(request: Request, exc: SQLAlchemyError):
    if not is_unavailable(exc):
        raise exc
    logger.warning("Database unavailable: %s", exc)
    return await http_exception_handler(
        request,
        HTTPException(status_code=503, detail="Database unavailable", headers={"Retry-After": "5"}),
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
