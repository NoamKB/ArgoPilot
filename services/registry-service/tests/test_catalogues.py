import json
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import pytest

CATALOGUE_ROUTES = [
    "/v1/crops",
    "/v1/crops/tomato",
    "/v1/soils",
    "/v1/soils/sand",
    "/v1/emitters",
    "/v1/emitters/dripnet-pc-1.0",
]


def test_get_emitter_matches_spec_example(client):
    response = client.get("/v1/emitters/dripnet-pc-1.0")

    assert response.status_code == 200
    assert response.json() == {"id": "dripnet-pc-1.0", "name": "DripNet PC", "flow_lph": 1.0}


def test_get_soil_matches_spec_example(client):
    response = client.get("/v1/soils/sand")

    assert response.status_code == 200
    assert response.json() == {"id": "sand", "name": "Sand", "available_water_mm_per_m": 83}


def test_get_crop_matches_spec_example(client):
    response = client.get("/v1/crops/tomato")

    assert response.status_code == 200
    assert response.json() == {"id": "tomato", "name": "Tomato"}


def test_list_crops(client):
    response = client.get("/v1/crops")

    assert response.status_code == 200
    assert {crop["id"] for crop in response.json()} == {"tomato", "bell-pepper"}


def test_list_soils(client):
    response = client.get("/v1/soils")

    assert response.status_code == 200
    assert {soil["id"] for soil in response.json()} == {"sand", "loam", "clay-loam"}


def test_list_emitters(client):
    response = client.get("/v1/emitters")

    assert response.status_code == 200
    assert {emitter["id"] for emitter in response.json()} == {
        "dripnet-pc-0.6",
        "dripnet-pc-1.0",
        "dripnet-pc-1.6",
        "dripnet-pc-2.0",
    }


@pytest.mark.parametrize("path", ["/v1/crops/potato", "/v1/soils/rock", "/v1/emitters/unknown"])
def test_unknown_catalogue_id_returns_404(client, path):
    response = client.get(path)

    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


@pytest.mark.parametrize("path", CATALOGUE_ROUTES)
@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
def test_other_methods_on_catalogues_return_405(client, method, path):
    response = client.request(method, path)

    assert response.status_code == 405
    assert response.headers["allow"] == "GET"
    assert response.json() == {"detail": "Method Not Allowed"}


def test_parallel_catalogue_requests_against_real_server(live_server):
    def fetch(path):
        with urllib.request.urlopen(f"{live_server}{path}", timeout=10) as response:
            return response.status, json.load(response)

    paths = CATALOGUE_ROUTES * 9
    with ThreadPoolExecutor(max_workers=50) as pool:
        results = list(pool.map(fetch, paths[:50]))

    assert [status for status, _ in results] == [200] * 50
    assert results[1][1] == {"id": "tomato", "name": "Tomato"}
