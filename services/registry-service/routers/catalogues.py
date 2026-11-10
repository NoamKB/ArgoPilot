from fastapi import APIRouter, HTTPException

from db import DbConnection
from repositories import catalogues as catalogue_repository
from schemas import Crop, Emitter, Soil

router = APIRouter(prefix="/v1", tags=["catalogues"])


@router.get("/crops", response_model=list[Crop])
def list_crops(conn: DbConnection):
    return catalogue_repository.list_crops(conn)


@router.get("/crops/{crop_id}", response_model=Crop)
def get_crop(crop_id: str, conn: DbConnection):
    crop = catalogue_repository.get_crop(conn, crop_id)
    if crop is None:
        raise HTTPException(status_code=404, detail="Crop not found")
    return crop


@router.get("/soils", response_model=list[Soil])
def list_soils(conn: DbConnection):
    return catalogue_repository.list_soils(conn)


@router.get("/soils/{soil_id}", response_model=Soil)
def get_soil(soil_id: str, conn: DbConnection):
    soil = catalogue_repository.get_soil(conn, soil_id)
    if soil is None:
        raise HTTPException(status_code=404, detail="Soil not found")
    return soil


@router.get("/emitters", response_model=list[Emitter])
def list_emitters(conn: DbConnection):
    return catalogue_repository.list_emitters(conn)


@router.get("/emitters/{emitter_id}", response_model=Emitter)
def get_emitter(emitter_id: str, conn: DbConnection):
    emitter = catalogue_repository.get_emitter(conn, emitter_id)
    if emitter is None:
        raise HTTPException(status_code=404, detail="Emitter not found")
    return emitter
