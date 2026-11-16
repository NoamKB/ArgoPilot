import pytest

from repositories import plots as plot_repository
from test_plots import NORTH_BLOCK_ID

SQL_LIKE_TEXT = "Robert'); DROP TABLE farms; --"


def test_update_refuses_a_column_name_outside_the_allow_list():
    # update_plot builds "SET <column> = :<column>" from the dict keys, so the keys must
    # be checked before any SQL exists. conn=None proves no statement runs: using it would
    # raise AttributeError instead of ValueError.
    with pytest.raises(ValueError, match="Not updatable"):
        plot_repository.update_plot(None, NORTH_BLOCK_ID, {"name = 'x', farm_id": "x"})


def test_sql_in_a_name_is_stored_as_plain_text(client):
    created = client.post("/v1/farms", json={"name": SQL_LIKE_TEXT})
    assert created.status_code == 201
    assert client.get(f"/v1/farms/{created.json()['id']}").json()["name"] == SQL_LIKE_TEXT
    assert len(client.get("/v1/farms").json()) == 3  # the 2 demo farms + this one: the table is intact


def test_sql_in_a_catalogue_path_matches_nothing(client):
    response = client.get("/v1/crops/tomato' OR '1'='1")
    assert response.status_code == 404
