import sqlite3
from uuid import uuid4


def list_farms(conn: sqlite3.Connection) -> list[dict]:
    return [dict(row) for row in conn.execute("SELECT id, name FROM farms")]


def get_farm(conn: sqlite3.Connection, farm_id: str) -> dict | None:
    row = conn.execute("SELECT id, name FROM farms WHERE id = ?", (farm_id,)).fetchone()
    return dict(row) if row else None


def create_farm(conn: sqlite3.Connection, name: str) -> dict:
    farm = {"id": str(uuid4()), "name": name}
    with conn:
        conn.execute("INSERT INTO farms (id, name) VALUES (:id, :name)", farm)
    return farm


def update_farm_name(conn: sqlite3.Connection, farm_id: str, name: str) -> bool:
    with conn:
        cursor = conn.execute("UPDATE farms SET name = ? WHERE id = ?", (name, farm_id))
    return cursor.rowcount == 1


def delete_farm(conn: sqlite3.Connection, farm_id: str) -> bool:
    with conn:
        cursor = conn.execute("DELETE FROM farms WHERE id = ?", (farm_id,))
    return cursor.rowcount == 1
