import sqlite3
from typing import NoReturn
from uuid import UUID

from fastapi import APIRouter, HTTPException

from db import DbConnection
from repositories import catalogues as catalogue_repository
from repositories import farms as farm_repository
from repositories import plots as plot_repository
from schemas import Plot, PlotCreate, PlotUpdate

router = APIRouter(prefix="/v1/plots", tags=["plots"])


def get_plot_or_404(conn: sqlite3.Connection, plot_id: UUID) -> dict:
    plot = plot_repository.get_plot(conn, str(plot_id))
    if plot is None:
        raise HTTPException(status_code=404, detail="Plot not found")
    return plot


def check_references(conn: sqlite3.Connection, fields: dict) -> None:
    if "farm_id" in fields and farm_repository.get_farm(conn, fields["farm_id"]) is None:
        raise HTTPException(status_code=404, detail="Farm not found")
    if "crop_id" in fields and catalogue_repository.get_crop(conn, fields["crop_id"]) is None:
        raise HTTPException(status_code=422, detail="Unknown crop")
    if "soil_id" in fields and catalogue_repository.get_soil(conn, fields["soil_id"]) is None:
        raise HTTPException(status_code=422, detail="Unknown soil")
    if "emitter_id" in fields and catalogue_repository.get_emitter(conn, fields["emitter_id"]) is None:
        raise HTTPException(status_code=422, detail="Unknown emitter")


def raise_for_integrity_error(exc: sqlite3.IntegrityError) -> NoReturn:
    if exc.sqlite_errorname == "SQLITE_CONSTRAINT_UNIQUE":
        raise HTTPException(status_code=409, detail="Plot name already exists on this farm") from exc
    if exc.sqlite_errorname == "SQLITE_CONSTRAINT_FOREIGNKEY":
        # The farm passed check_references but was deleted by a concurrent request.
        raise HTTPException(status_code=404, detail="Farm not found") from exc
    raise exc


@router.post("", status_code=201, response_model=Plot)
def create_plot(body: PlotCreate, conn: DbConnection):
    fields = body.model_dump(mode="json")
    check_references(conn, fields)
    try:
        return plot_repository.create_plot(conn, fields)
    except sqlite3.IntegrityError as exc:
        raise_for_integrity_error(exc)


@router.get("", response_model=list[Plot])
def list_plots(conn: DbConnection, farm_id: UUID | None = None):
    return plot_repository.list_plots(conn, str(farm_id) if farm_id else None)


@router.get("/{plot_id}", response_model=Plot)
def get_plot(plot_id: UUID, conn: DbConnection):
    return get_plot_or_404(conn, plot_id)


@router.patch("/{plot_id}", response_model=Plot)
def update_plot(plot_id: UUID, body: PlotUpdate, conn: DbConnection):
    get_plot_or_404(conn, plot_id)
    changes = body.model_dump(mode="json", exclude_unset=True)
    if changes:
        check_references(conn, changes)
        try:
            updated = plot_repository.update_plot(conn, str(plot_id), changes)
        except sqlite3.IntegrityError as exc:
            raise_for_integrity_error(exc)
        if not updated:
            raise HTTPException(status_code=404, detail="Plot not found")
    return get_plot_or_404(conn, plot_id)


@router.delete("/{plot_id}", status_code=204)
def delete_plot(plot_id: UUID, conn: DbConnection) -> None:
    if not plot_repository.delete_plot(conn, str(plot_id)):
        raise HTTPException(status_code=404, detail="Plot not found")
