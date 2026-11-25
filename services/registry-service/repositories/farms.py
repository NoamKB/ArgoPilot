from uuid import uuid4

from sqlalchemy import Connection, text


def list_farms(conn: Connection) -> list[dict]:
    return [dict(row) for row in conn.execute(text("SELECT id, name FROM farms")).mappings()]


def get_farm(conn: Connection, farm_id: str) -> dict | None:
    row = conn.execute(text("SELECT id, name FROM farms WHERE id = :id"), {"id": farm_id}).mappings().first()
    return dict(row) if row else None


def total_plot_area(conn: Connection, farm_id: str) -> float:
    # SUM over zero rows is NULL; COALESCE turns it into 0.
    query = text("SELECT COALESCE(SUM(area_m2), 0) FROM plots WHERE farm_id = :farm_id")
    return conn.execute(query, {"farm_id": farm_id}).scalar_one()


def create_farm(conn: Connection, name: str) -> dict:
    farm = {"id": str(uuid4()), "name": name}
    conn.execute(text("INSERT INTO farms (id, name) VALUES (:id, :name)"), farm)
    return farm


def update_farm_name(conn: Connection, farm_id: str, name: str) -> bool:
    result = conn.execute(text("UPDATE farms SET name = :name WHERE id = :id"), {"name": name, "id": farm_id})
    return result.rowcount == 1


def delete_farm(conn: Connection, farm_id: str) -> bool:
    result = conn.execute(text("DELETE FROM farms WHERE id = :id"), {"id": farm_id})
    return result.rowcount == 1
