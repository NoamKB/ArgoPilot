import logging
import sqlite3

from fastapi import FastAPI, HTTPException, Request
from fastapi.exception_handlers import http_exception_handler

from db import is_unavailable
from routers import catalogues, farms, plots

logger = logging.getLogger(__name__)

app = FastAPI(title="AgroPilot registry-service", version="0.1.0")
app.include_router(farms.router)
app.include_router(plots.router)
app.include_router(catalogues.router)


@app.exception_handler(sqlite3.DatabaseError)
async def database_error_handler(request: Request, exc: sqlite3.DatabaseError):
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
