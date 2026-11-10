from datetime import date, timedelta

import pytest
from pydantic import ValidationError

from schemas import PlotCreate, PlotUpdate

VALID_PLOT = {
    "farm_id": "b7e2c0a0-3c1d-4f0a-9a11-0c5d2e6f1001",
    "name": "South block",
    "area_m2": 1000,
    "crop_id": "tomato",
    "planting_date": "2026-03-01",
    "soil_id": "loam",
    "row_spacing_m": 1.5,
    "emitter_spacing_m": 0.4,
    "emitter_id": "dripnet-pc-1.0",
    "lat": 31.25,
    "lon": 34.79,
}

TOMORROW = (date.today() + timedelta(days=1)).isoformat()


def test_spec_example_is_valid():
    plot = PlotCreate.model_validate(VALID_PLOT)

    assert plot.area_m2 == 1000
    assert str(plot.farm_id) == VALID_PLOT["farm_id"]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("planting_date", date.today().isoformat()),
        ("lat", -90),
        ("lat", 90),
        ("lon", -180),
        ("lon", 180.0),
        ("area_m2", 0.01),
    ],
)
def test_boundary_values_are_accepted(field, value):
    PlotCreate.model_validate({**VALID_PLOT, field: value})


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("area_m2", 0),
        ("area_m2", -5),
        ("area_m2", True),
        ("area_m2", "1000"),
        ("area_m2", float("inf")),
        ("area_m2", float("nan")),
        ("row_spacing_m", 0),
        ("emitter_spacing_m", -0.1),
        ("planting_date", TOMORROW),
        ("planting_date", "2026-02-30"),
        ("planting_date", "01-03-2026"),
        ("planting_date", "2026-03-01T00:00:00"),
        ("planting_date", 0),
        ("lat", 90.0001),
        ("lat", -91),
        ("lon", 180.5),
        ("lon", -181),
        ("lat", "31.25"),
        ("name", ""),
        ("farm_id", "not-a-uuid"),
        ("crop_id", 5),
    ],
)
def test_invalid_values_are_rejected(field, value):
    with pytest.raises(ValidationError):
        PlotCreate.model_validate({**VALID_PLOT, field: value})


@pytest.mark.parametrize("field", list(VALID_PLOT))
def test_every_field_is_required(field):
    body = {key: value for key, value in VALID_PLOT.items() if key != field}

    with pytest.raises(ValidationError):
        PlotCreate.model_validate(body)


def test_unknown_field_is_rejected():
    with pytest.raises(ValidationError):
        PlotCreate.model_validate({**VALID_PLOT, "id": "c8f3d1b0-4d2e-5a1b-8b22-1d6e3f702002"})


def test_update_tracks_only_sent_fields():
    update = PlotUpdate.model_validate({"name": "Renamed"})

    assert update.model_dump(exclude_unset=True) == {"name": "Renamed"}


def test_empty_update_is_valid():
    assert PlotUpdate.model_validate({}).model_dump(exclude_unset=True) == {}


@pytest.mark.parametrize("field", list(VALID_PLOT))
def test_update_rejects_null(field):
    with pytest.raises(ValidationError):
        PlotUpdate.model_validate({field: None})


@pytest.mark.parametrize(
    ("field", "value"),
    [("area_m2", 0), ("planting_date", TOMORROW), ("lat", 91), ("name", "")],
)
def test_update_applies_the_same_rules(field, value):
    with pytest.raises(ValidationError):
        PlotUpdate.model_validate({field: value})
