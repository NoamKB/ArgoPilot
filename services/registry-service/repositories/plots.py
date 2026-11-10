import sqlite3
from uuid import uuid4

SELECT_PLOTS = """
    SELECT id, farm_id, name, area_m2, crop_id, planting_date, soil_id,
           row_spacing_m, emitter_spacing_m, emitter_id, lat, lon
    FROM plots
"""

INSERT_PLOT = """
    INSERT INTO plots (
        id, farm_id, name, area_m2, crop_id, planting_date, soil_id,
        row_spacing_m, emitter_spacing_m, emitter_id, lat, lon
    ) VALUES (
        :id, :farm_id, :name, :area_m2, :crop_id, :planting_date, :soil_id,
        :row_spacing_m, :emitter_spacing_m, :emitter_id, :lat, :lon
    )
"""

UPDATABLE_COLUMNS = {
    "farm_id", "name", "area_m2", "crop_id", "planting_date", "soil_id",
    "row_spacing_m", "emitter_spacing_m", "emitter_id", "lat", "lon",
}


def list_plots(conn: sqlite3.Connection, farm_id: str | None = None) -> list[dict]:
    if farm_id is None:
        rows = conn.execute(SELECT_PLOTS)
    else:
        rows = conn.execute(SELECT_PLOTS + " WHERE farm_id = ?", (farm_id,))
    return [dict(row) for row in rows]


def get_plot(conn: sqlite3.Connection, plot_id: str) -> dict | None:
    row = conn.execute(SELECT_PLOTS + " WHERE id = ?", (plot_id,)).fetchone()
    return dict(row) if row else None


def create_plot(conn: sqlite3.Connection, fields: dict) -> dict:
    plot = {"id": str(uuid4()), **fields}
    with conn:
        conn.execute(INSERT_PLOT, plot)
    return plot


def update_plot(conn: sqlite3.Connection, plot_id: str, changes: dict) -> bool:
    if not changes.keys() <= UPDATABLE_COLUMNS:
        raise ValueError(f"Not updatable: {changes.keys() - UPDATABLE_COLUMNS}")
    assignments = ", ".join(f"{column} = :{column}" for column in changes)
    with conn:
        cursor = conn.execute(f"UPDATE plots SET {assignments} WHERE id = :id", {**changes, "id": plot_id})
    return cursor.rowcount == 1


def delete_plot(conn: sqlite3.Connection, plot_id: str) -> bool:
    with conn:
        cursor = conn.execute("DELETE FROM plots WHERE id = ?", (plot_id,))
    return cursor.rowcount == 1
