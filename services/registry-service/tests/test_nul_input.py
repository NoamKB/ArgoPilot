import pytest

from test_plots import DEMO_FARM_ID, NORTH_BLOCK_ID, SPEC_EXAMPLE

NUL = "a\x00b"


def assert_nul_rejected(response):
    assert response.status_code == 422
    assert "must not contain NUL characters" in response.json()["detail"][0]["msg"]


@pytest.mark.parametrize(("method", "path"), [("POST", "/v1/farms"), ("PATCH", f"/v1/farms/{DEMO_FARM_ID}")])
def test_nul_in_farm_name(client, method, path):
    assert_nul_rejected(client.request(method, path, json={"name": NUL}))


@pytest.mark.parametrize("field", ["name", "crop_id", "soil_id", "emitter_id"])
def test_nul_in_plot_create(client, field):
    assert_nul_rejected(client.post("/v1/plots", json={**SPEC_EXAMPLE, field: NUL}))


@pytest.mark.parametrize("field", ["name", "crop_id", "soil_id", "emitter_id"])
def test_nul_in_plot_update(client, field):
    assert_nul_rejected(client.patch(f"/v1/plots/{NORTH_BLOCK_ID}", json={field: NUL}))


@pytest.mark.parametrize("path", ["/v1/crops/a%00b", "/v1/soils/a%00b", "/v1/emitters/a%00b"])
def test_nul_in_catalogue_path(client, path):
    assert_nul_rejected(client.get(path))
