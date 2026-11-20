from datetime import date
from typing import Annotated
from uuid import UUID

from pydantic import AfterValidator, BaseModel, ConfigDict, Field


def not_in_future(value: str) -> str:
    if date.fromisoformat(value) > date.today():
        raise ValueError("planting_date must not be in the future")
    return value


def reject_nul(value: str) -> str:
    """PostgreSQL text cannot store NUL, so reject it on both databases."""
    if "\x00" in value:
        raise ValueError("must not contain NUL characters")
    return value


NoNulStr = Annotated[str, AfterValidator(reject_nul)]
Name = Annotated[str, Field(min_length=1), AfterValidator(reject_nul)]
PositiveNumber = Annotated[float, Field(gt=0, strict=True, allow_inf_nan=False)]
Latitude = Annotated[float, Field(ge=-90, le=90, strict=True, allow_inf_nan=False)]
Longitude = Annotated[float, Field(ge=-180, le=180, strict=True, allow_inf_nan=False)]
PlantingDate = Annotated[str, Field(pattern=r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$"), AfterValidator(not_in_future)]


class Crop(BaseModel):
    id: str
    name: str


class Soil(BaseModel):
    id: str
    name: str
    available_water_mm_per_m: int


class Emitter(BaseModel):
    id: str
    name: str
    flow_lph: float


class FarmCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Name


class FarmUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Name = None


class Farm(BaseModel):
    id: UUID
    name: str


class FarmArea(BaseModel):
    farm_id: UUID
    total_area_m2: float


class PlotCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    farm_id: UUID
    name: Name
    area_m2: PositiveNumber
    crop_id: NoNulStr
    planting_date: PlantingDate
    soil_id: NoNulStr
    row_spacing_m: PositiveNumber
    emitter_spacing_m: PositiveNumber
    emitter_id: NoNulStr
    lat: Latitude
    lon: Longitude


class PlotUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    farm_id: UUID = None
    name: Name = None
    area_m2: PositiveNumber = None
    crop_id: NoNulStr = None
    planting_date: PlantingDate = None
    soil_id: NoNulStr = None
    row_spacing_m: PositiveNumber = None
    emitter_spacing_m: PositiveNumber = None
    emitter_id: NoNulStr = None
    lat: Latitude = None
    lon: Longitude = None


class Plot(BaseModel):
    id: UUID
    farm_id: UUID
    name: str
    area_m2: float
    crop_id: str
    planting_date: str
    soil_id: str
    row_spacing_m: float
    emitter_spacing_m: float
    emitter_id: str
    lat: float
    lon: float
