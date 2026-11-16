from uuid import uuid4

from sqlalchemy import Connection, text

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


def list_plots(conn: Connection, farm_id: str | None = None) -> list[dict]:
    if farm_id is None:
        result = conn.execute(text(SELECT_PLOTS))
    else:
        result = conn.execute(text(SELECT_PLOTS + " WHERE farm_id = :farm_id"), {"farm_id": farm_id})
    return [dict(row) for row in result.mappings()]


def get_plot(conn: Connection, plot_id: str) -> dict | None:
    row = conn.execute(text(SELECT_PLOTS + " WHERE id = :id"), {"id": plot_id}).mappings().first()
    return dict(row) if row else None


def create_plot(conn: Connection, fields: dict) -> dict:
    plot = {"id": str(uuid4()), **fields}
    conn.execute(text(INSERT_PLOT), plot)
    return plot


def update_plot(conn: Connection, plot_id: str, changes: dict) -> bool:
    if not changes.keys() <= UPDATABLE_COLUMNS:
        raise ValueError(f"Not updatable: {changes.keys() - UPDATABLE_COLUMNS}")
    assignments = ", ".join(f"{column} = :{column}" for column in changes)
    result = conn.execute(text(f"UPDATE plots SET {assignments} WHERE id = :id"), {**changes, "id": plot_id})
    return result.rowcount == 1


def delete_plot(conn: Connection, plot_id: str) -> bool:
    result = conn.execute(text("DELETE FROM plots WHERE id = :id"), {"id": plot_id})
    return result.rowcount == 1
