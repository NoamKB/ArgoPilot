import json
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from uuid import UUID

import pytest

DEMO_FARM_ID = "b7e2c0a0-3c1d-4f0a-9a11-0c5d2e6f1001"
EAST_FARM_ID = "a9c1e4b2-6f70-4d8e-a144-3f8b5c904004"
UNKNOWN_FARM_ID = "00000000-0000-4000-8000-000000000000"


def test_list_farms_returns_seed_farms(client):
    response = client.get("/v1/farms")

    assert response.status_code == 200
    assert {farm["id"] for farm in response.json()} == {DEMO_FARM_ID, EAST_FARM_ID}


def test_get_farm(client):
    response = client.get(f"/v1/farms/{DEMO_FARM_ID}")

    assert response.status_code == 200
    assert response.json() == {"id": DEMO_FARM_ID, "name": "Demo cooperative"}


def test_get_farm_accepts_uppercase_uuid(client):
    response = client.get(f"/v1/farms/{DEMO_FARM_ID.upper()}")

    assert response.status_code == 200
    assert response.json()["id"] == DEMO_FARM_ID


def test_unknown_farm_returns_404(client):
    response = client.get(f"/v1/farms/{UNKNOWN_FARM_ID}")

    assert response.status_code == 404
    assert response.json() == {"detail": "Farm not found"}


def test_non_uuid_farm_id_returns_422(client):
    assert client.get("/v1/farms/not-a-uuid").status_code == 422


def test_create_farm_then_read_it(client):
    response = client.post("/v1/farms", json={"name": "North farm"})

    assert response.status_code == 201
    farm = response.json()
    assert farm["name"] == "North farm"
    UUID(farm["id"])
    assert client.get(f"/v1/farms/{farm['id']}").json() == farm


@pytest.mark.parametrize(
    "body",
    [{}, {"name": ""}, {"name": None}, {"name": 5}, {"name": "A", "id": DEMO_FARM_ID}],
)
def test_create_farm_rejects_invalid_body(client, body):
    assert client.post("/v1/farms", json=body).status_code == 422


def test_create_farm_without_json_content_type_returns_422(client):
    assert client.post("/v1/farms", content="name=North").status_code == 422


def test_patch_farm_renames_it(client):
    response = client.patch(f"/v1/farms/{DEMO_FARM_ID}", json={"name": "Renamed"})

    assert response.status_code == 200
    assert response.json() == {"id": DEMO_FARM_ID, "name": "Renamed"}
    assert client.get(f"/v1/farms/{DEMO_FARM_ID}").json()["name"] == "Renamed"


def test_patch_farm_with_empty_body_changes_nothing(client):
    response = client.patch(f"/v1/farms/{DEMO_FARM_ID}", json={})

    assert response.status_code == 200
    assert response.json() == {"id": DEMO_FARM_ID, "name": "Demo cooperative"}


@pytest.mark.parametrize("body", [{"name": None}, {"name": ""}, {"unknown": "x"}])
def test_patch_farm_rejects_invalid_body(client, body):
    assert client.patch(f"/v1/farms/{DEMO_FARM_ID}", json=body).status_code == 422
    assert client.get(f"/v1/farms/{DEMO_FARM_ID}").json()["name"] == "Demo cooperative"


def test_patch_unknown_farm_returns_404(client):
    assert client.patch(f"/v1/farms/{UNKNOWN_FARM_ID}", json={"name": "X"}).status_code == 404
    assert client.patch(f"/v1/farms/{UNKNOWN_FARM_ID}", json={}).status_code == 404


def test_delete_farm_with_plots_returns_409_and_keeps_farm(client):
    response = client.delete(f"/v1/farms/{DEMO_FARM_ID}")

    assert response.status_code == 409
    assert response.json() == {"detail": "Farm still has plots"}
    assert client.get(f"/v1/farms/{DEMO_FARM_ID}").status_code == 200


def test_delete_farm_without_plots_returns_204_with_no_body(client):
    farm_id = client.post("/v1/farms", json={"name": "Empty farm"}).json()["id"]

    response = client.delete(f"/v1/farms/{farm_id}")

    assert response.status_code == 204
    assert response.content == b""
    assert client.get(f"/v1/farms/{farm_id}").status_code == 404


def test_delete_unknown_farm_returns_404(client):
    assert client.delete(f"/v1/farms/{UNKNOWN_FARM_ID}").status_code == 404


def test_parallel_farm_creation_against_real_server(live_server):
    def create(index):
        request = urllib.request.Request(
            f"{live_server}/v1/farms",
            data=json.dumps({"name": f"Farm {index}"}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status

    with ThreadPoolExecutor(max_workers=20) as pool:
        statuses = list(pool.map(create, range(20)))

    assert statuses == [201] * 20
    with urllib.request.urlopen(f"{live_server}/v1/farms", timeout=10) as response:
        assert len(json.load(response)) == 22
