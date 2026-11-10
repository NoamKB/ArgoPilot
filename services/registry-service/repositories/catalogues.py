import sqlite3


def list_crops(conn: sqlite3.Connection) -> list[dict]:
    return [dict(row) for row in conn.execute("SELECT id, name FROM crops")]


def get_crop(conn: sqlite3.Connection, crop_id: str) -> dict | None:
    row = conn.execute("SELECT id, name FROM crops WHERE id = ?", (crop_id,)).fetchone()
    return dict(row) if row else None


def list_soils(conn: sqlite3.Connection) -> list[dict]:
    return [dict(row) for row in conn.execute("SELECT id, name, available_water_mm_per_m FROM soils")]


def get_soil(conn: sqlite3.Connection, soil_id: str) -> dict | None:
    row = conn.execute(
        "SELECT id, name, available_water_mm_per_m FROM soils WHERE id = ?", (soil_id,)
    ).fetchone()
    return dict(row) if row else None


def list_emitters(conn: sqlite3.Connection) -> list[dict]:
    return [dict(row) for row in conn.execute("SELECT id, name, flow_lph FROM emitters")]


def get_emitter(conn: sqlite3.Connection, emitter_id: str) -> dict | None:
    row = conn.execute(
        "SELECT id, name, flow_lph FROM emitters WHERE id = ?", (emitter_id,)
    ).fetchone()
    return dict(row) if row else None
