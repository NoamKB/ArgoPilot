from sqlalchemy import Connection, text


def list_crops(conn: Connection) -> list[dict]:
    return [dict(row) for row in conn.execute(text("SELECT id, name FROM crops")).mappings()]


def get_crop(conn: Connection, crop_id: str) -> dict | None:
    row = conn.execute(text("SELECT id, name FROM crops WHERE id = :id"), {"id": crop_id}).mappings().first()
    return dict(row) if row else None


def list_soils(conn: Connection) -> list[dict]:
    return [dict(row) for row in conn.execute(text("SELECT id, name, available_water_mm_per_m FROM soils")).mappings()]


def get_soil(conn: Connection, soil_id: str) -> dict | None:
    row = conn.execute(
        text("SELECT id, name, available_water_mm_per_m FROM soils WHERE id = :id"), {"id": soil_id}
    ).mappings().first()
    return dict(row) if row else None


def list_emitters(conn: Connection) -> list[dict]:
    return [dict(row) for row in conn.execute(text("SELECT id, name, flow_lph FROM emitters")).mappings()]


def get_emitter(conn: Connection, emitter_id: str) -> dict | None:
    row = conn.execute(
        text("SELECT id, name, flow_lph FROM emitters WHERE id = :id"), {"id": emitter_id}
    ).mappings().first()
    return dict(row) if row else None
