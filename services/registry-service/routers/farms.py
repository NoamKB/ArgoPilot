import sqlite3
from uuid import UUID

from fastapi import APIRouter, HTTPException

from db import DbConnection
from repositories import farms as farm_repository
from schemas import Farm, FarmCreate, FarmUpdate

router = APIRouter(prefix="/v1/farms", tags=["farms"])


def get_farm_or_404(conn: sqlite3.Connection, farm_id: UUID) -> dict:
    farm = farm_repository.get_farm(conn, str(farm_id))
    if farm is None:
        raise HTTPException(status_code=404, detail="Farm not found")
    return farm


@router.post("", status_code=201, response_model=Farm)
def create_farm(body: FarmCreate, conn: DbConnection):
    return farm_repository.create_farm(conn, body.name)


@router.get("", response_model=list[Farm])
def list_farms(conn: DbConnection):
    return farm_repository.list_farms(conn)


@router.get("/{farm_id}", response_model=Farm)
def get_farm(farm_id: UUID, conn: DbConnection):
    return get_farm_or_404(conn, farm_id)


@router.patch("/{farm_id}", response_model=Farm)
def update_farm(farm_id: UUID, body: FarmUpdate, conn: DbConnection):
    if "name" in body.model_fields_set:
        if not farm_repository.update_farm_name(conn, str(farm_id), body.name):
            raise HTTPException(status_code=404, detail="Farm not found")
    return get_farm_or_404(conn, farm_id)


@router.delete("/{farm_id}", status_code=204)
def delete_farm(farm_id: UUID, conn: DbConnection) -> None:
    try:
        deleted = farm_repository.delete_farm(conn, str(farm_id))
    except sqlite3.IntegrityError as exc:
        if exc.sqlite_errorname == "SQLITE_CONSTRAINT_FOREIGNKEY":
            raise HTTPException(status_code=409, detail="Farm still has plots") from exc
        raise
    if not deleted:
        raise HTTPException(status_code=404, detail="Farm not found")
