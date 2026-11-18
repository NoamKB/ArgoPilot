import json
import sqlite3
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from main import app
from repositories import plots as plot_repository
from test_database_errors import integrity_error, sqlite_error

DEMO_FARM_ID = "b7e2c0a0-3c1d-4f0a-9a11-0c5d2e6f1001"
EAST_FARM_ID = "a9c1e4b2-6f70-4d8e-a144-3f8b5c904004"
UNKNOWN_ID = "00000000-0000-4000-8000-000000000000"
NORTH_BLOCK_ID = "c8f3d1b0-4d2e-5a1b-8b22-1d6e3f702002"

NORTH_BLOCK = {
    "id": NORTH_BLOCK_ID,
    "farm_id": DEMO_FARM_ID,
    "name": "North block",
    "area_m2": 1000.0,
    "crop_id": "tomato",
    "planting_date": "2026-03-01",
    "soil_id": "loam",
    "row_spacing_m": 1.5,
    "emitter_spacing_m": 0.4,
    "emitter_id": "dripnet-pc-1.0",
    "lat": 31.25,
    "lon": 34.79,
}

SPEC_EXAMPLE = {
    "farm_id": DEMO_FARM_ID,
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


# --- GET ---


def test_list_all_plots(client):
    response = client.get("/v1/plots")

    assert response.status_code == 200
    assert {plot["name"] for plot in response.json()} == {
        "North block",
        "East block",
        "West block",
        "Greenhouse",
    }


def test_list_plots_of_one_farm(client):
    response = client.get("/v1/plots", params={"farm_id": DEMO_FARM_ID})

    assert response.status_code == 200
    assert {plot["name"] for plot in response.json()} == {"North block", "East block"}


def test_list_plots_of_unknown_farm_returns_empty_list(client):
    response = client.get("/v1/plots", params={"farm_id": UNKNOWN_ID})

    assert response.status_code == 200
    assert response.json() == []


def test_list_plots_with_invalid_farm_id_returns_422(client):
    assert client.get("/v1/plots", params={"farm_id": "abc"}).status_code == 422


def test_get_seed_plot_with_version_5_uuid(client):
    response = client.get(f"/v1/plots/{NORTH_BLOCK_ID}")

    assert response.status_code == 200
    assert response.json() == NORTH_BLOCK


def test_get_unknown_plot_returns_404(client):
    response = client.get(f"/v1/plots/{UNKNOWN_ID}")

    assert response.status_code == 404
    assert response.json() == {"detail": "Plot not found"}


def test_get_plot_with_invalid_id_returns_422(client):
    assert client.get("/v1/plots/not-a-uuid").status_code == 422


# --- POST ---


def test_create_spec_example_returns_object_plus_id(client):
    response = client.post("/v1/plots", json=SPEC_EXAMPLE)

    assert response.status_code == 201
    created = response.json()
    assert {key: value for key, value in created.items() if key != "id"} == SPEC_EXAMPLE
    assert client.get(f"/v1/plots/{created['id']}").json() == created


def test_create_plot_for_unknown_farm_returns_404(client):
    response = client.post("/v1/plots", json={**SPEC_EXAMPLE, "farm_id": UNKNOWN_ID})

    assert response.status_code == 404
    assert response.json() == {"detail": "Farm not found"}


@pytest.mark.parametrize(
    ("field", "detail"),
    [("crop_id", "Unknown crop"), ("soil_id", "Unknown soil"), ("emitter_id", "Unknown emitter")],
)
def test_create_plot_with_unknown_catalogue_entry_returns_422(client, field, detail):
    response = client.post("/v1/plots", json={**SPEC_EXAMPLE, field: "does-not-exist"})

    assert response.status_code == 422
    assert response.json() == {"detail": detail}


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("area_m2", 0),
        ("row_spacing_m", -1),
        ("emitter_spacing_m", 0),
        ("planting_date", (date.today() + timedelta(days=1)).isoformat()),
        ("lat", 91),
        ("lon", -181),
    ],
)
def test_create_plot_rejects_fr_1_3_violations(client, field, value):
    response = client.post("/v1/plots", json={**SPEC_EXAMPLE, field: value})

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", field]


def test_duplicate_plot_name_on_same_farm_returns_409(client):
    response = client.post("/v1/plots", json={**SPEC_EXAMPLE, "name": "North block"})

    assert response.status_code == 409
    assert response.json() == {"detail": "Plot name already exists on this farm"}


def test_same_plot_name_on_another_farm_is_allowed(client):
    response = client.post(
        "/v1/plots", json={**SPEC_EXAMPLE, "farm_id": EAST_FARM_ID, "name": "North block"}
    )

    assert response.status_code == 201


def test_check_order_body_then_farm_then_catalogue_then_unique(client):
    invalid_body_and_unknown_farm = {**SPEC_EXAMPLE, "farm_id": UNKNOWN_ID, "area_m2": 0}
    unknown_farm_and_emitter = {**SPEC_EXAMPLE, "farm_id": UNKNOWN_ID, "emitter_id": "x"}
    unknown_emitter_and_duplicate = {**SPEC_EXAMPLE, "emitter_id": "x", "name": "North block"}

    assert client.post("/v1/plots", json=invalid_body_and_unknown_farm).status_code == 422
    assert client.post("/v1/plots", json=unknown_farm_and_emitter).status_code == 404
    assert client.post("/v1/plots", json=unknown_emitter_and_duplicate).status_code == 422


def test_parallel_duplicate_creates_allow_exactly_one(live_server):
    def create(_):
        request = urllib.request.Request(
            f"{live_server}/v1/plots",
            data=json.dumps({**SPEC_EXAMPLE, "name": "Race block"}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                return response.status
        except urllib.error.HTTPError as error:
            return error.code

    with ThreadPoolExecutor(max_workers=10) as pool:
        statuses = sorted(pool.map(create, range(10)))

    assert statuses == [201] + [409] * 9


# --- PATCH ---


def test_patch_changes_only_sent_fields(client):
    response = client.patch(f"/v1/plots/{NORTH_BLOCK_ID}", json={"area_m2": 1200, "name": "North"})

    assert response.status_code == 200
    assert response.json() == {**NORTH_BLOCK, "area_m2": 1200.0, "name": "North"}
    assert client.get(f"/v1/plots/{NORTH_BLOCK_ID}").json() == response.json()


def test_patch_with_empty_body_changes_nothing(client):
    response = client.patch(f"/v1/plots/{NORTH_BLOCK_ID}", json={})

    assert response.status_code == 200
    assert response.json() == NORTH_BLOCK


def test_patch_to_own_name_is_allowed(client):
    response = client.patch(f"/v1/plots/{NORTH_BLOCK_ID}", json={"name": "North block"})

    assert response.status_code == 200


def test_patch_moves_plot_to_another_farm(client):
    response = client.patch(f"/v1/plots/{NORTH_BLOCK_ID}", json={"farm_id": EAST_FARM_ID})

    assert response.status_code == 200
    assert response.json()["farm_id"] == EAST_FARM_ID


def test_patch_rename_to_existing_name_returns_409_and_keeps_row(client):
    response = client.patch(f"/v1/plots/{NORTH_BLOCK_ID}", json={"name": "East block"})

    assert response.status_code == 409
    assert client.get(f"/v1/plots/{NORTH_BLOCK_ID}").json() == NORTH_BLOCK


def test_patch_move_into_name_collision_returns_409(client):
    body = {"farm_id": EAST_FARM_ID, "name": "Greenhouse"}

    assert client.patch(f"/v1/plots/{NORTH_BLOCK_ID}", json=body).status_code == 409


@pytest.mark.parametrize(
    ("body", "status"),
    [
        ({"farm_id": UNKNOWN_ID}, 404),
        ({"emitter_id": "unknown"}, 422),
        ({"soil_id": "rock"}, 422),
        ({"area_m2": 0}, 422),
        ({"planting_date": (date.today() + timedelta(days=1)).isoformat()}, 422),
        ({"lat": 95}, 422),
        ({"name": None}, 422),
        ({"id": UNKNOWN_ID}, 422),
    ],
)
def test_patch_applies_all_rules(client, body, status):
    response = client.patch(f"/v1/plots/{NORTH_BLOCK_ID}", json=body)

    assert response.status_code == status
    assert client.get(f"/v1/plots/{NORTH_BLOCK_ID}").json() == NORTH_BLOCK


def test_patch_unknown_plot_returns_404(client):
    assert client.patch(f"/v1/plots/{UNKNOWN_ID}", json={"name": "X"}).status_code == 404
    assert client.patch(f"/v1/plots/{UNKNOWN_ID}", json={}).status_code == 404


# --- DELETE ---


def test_delete_plot_returns_204_with_no_body(client):
    response = client.delete(f"/v1/plots/{NORTH_BLOCK_ID}")

    assert response.status_code == 204
    assert response.content == b""
    assert client.get(f"/v1/plots/{NORTH_BLOCK_ID}").status_code == 404


def test_delete_unknown_plot_returns_404(client):
    assert client.delete(f"/v1/plots/{UNKNOWN_ID}").status_code == 404


def test_farm_can_be_deleted_after_its_plots(client):
    for plot in client.get("/v1/plots", params={"farm_id": DEMO_FARM_ID}).json():
        assert client.delete(f"/v1/plots/{plot['id']}").status_code == 204

    assert client.delete(f"/v1/farms/{DEMO_FARM_ID}").status_code == 204


def test_high_precision_coordinates_round_trip(client):
    # Passes on SQLite from the start; catches 4-byte REAL rounding on PostgreSQL.
    created = client.post("/v1/plots", json={**SPEC_EXAMPLE, "name": "Precise block", "lat": 31.2512345, "lon": 34.7912345678})
    assert created.status_code == 201
    stored = client.get(f"/v1/plots/{created.json()['id']}").json()
    assert (stored["lat"], stored["lon"]) == (31.2512345, 34.7912345678)


# The next tests simulate another request changing the data between the router's
# checks and the UPDATE: the repository is replaced by one that fails the way the database would.


def test_patch_when_farm_is_deleted_meanwhile_returns_404(client, monkeypatch):
    def update_fails(conn, plot_id, changes):
        raise integrity_error(sqlite_error(sqlite3.IntegrityError, "SQLITE_CONSTRAINT_FOREIGNKEY"))

    monkeypatch.setattr(plot_repository, "update_plot", update_fails)
    response = client.patch(f"/v1/plots/{NORTH_BLOCK_ID}", json={"farm_id": EAST_FARM_ID})

    assert response.status_code == 404
    assert response.json() == {"detail": "Farm not found"}


def test_patch_with_another_integrity_error_returns_500(seeded_db, monkeypatch):
    def update_fails(conn, plot_id, changes):
        raise integrity_error(sqlite_error(sqlite3.IntegrityError, "SQLITE_CONSTRAINT_CHECK"))

    monkeypatch.setattr(plot_repository, "update_plot", update_fails)
    client = TestClient(app, raise_server_exceptions=False)
    response = client.patch(f"/v1/plots/{NORTH_BLOCK_ID}", json={"name": "Renamed"})

    assert response.status_code == 500
    assert response.text == "Internal Server Error"


def test_patch_when_plot_is_deleted_meanwhile_returns_404(client, monkeypatch):
    monkeypatch.setattr(plot_repository, "update_plot", lambda conn, plot_id, changes: False)  # no row updated
    response = client.patch(f"/v1/plots/{NORTH_BLOCK_ID}", json={"name": "Renamed"})

    assert response.status_code == 404
    assert response.json() == {"detail": "Plot not found"}
