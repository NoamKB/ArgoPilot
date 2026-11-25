"""Create the registry-service schema and catalogues in PostgreSQL.

Initial schema setup only. Not a migration tool: a table that already exists is left
unchanged, even if its definition differs, and an existing catalogue row is not updated.

Run from services/registry-service, with DATABASE_URL set in the environment or .env:
    uv run python -m scripts.setup_postgres          # schema + catalogues
    uv run python -m scripts.setup_postgres --demo   # also the demo farms and plots: the 15 seed rows (FR-2.2)
"""

import argparse
import sys

from sqlalchemy import Connection, text

from db import display_url, get_database_url, get_engine, parse_database_url

DEMO_WARNING = "WARNING: inserting demo farms and plots. Do not use --demo on a database with real grower data."

# Same tables as seed_registry.sh, with two PostgreSQL-specific choices:
# - DOUBLE PRECISION, not REAL: PostgreSQL's REAL is a 4-byte float (about 6 digits)
#   and would round coordinates; SQLite's REAL is 8 bytes.
# - planting_date stays TEXT: a DATE column returns a Python date, but the API
#   model declares planting_date as str.
CREATE_SCHEMA_SQL = [
    """
    CREATE TABLE IF NOT EXISTS farms (
      id   TEXT PRIMARY KEY,
      name TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS crops (
      id   TEXT PRIMARY KEY,
      name TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS soils (
      id                       TEXT PRIMARY KEY,
      name                     TEXT NOT NULL,
      available_water_mm_per_m INTEGER NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS emitters (
      id       TEXT PRIMARY KEY,
      name     TEXT NOT NULL,
      flow_lph DOUBLE PRECISION NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS plots (
      id                TEXT PRIMARY KEY,
      farm_id           TEXT NOT NULL REFERENCES farms(id),
      name              TEXT NOT NULL,
      area_m2           DOUBLE PRECISION NOT NULL,
      crop_id           TEXT NOT NULL REFERENCES crops(id),
      planting_date     TEXT NOT NULL,
      soil_id           TEXT NOT NULL REFERENCES soils(id),
      row_spacing_m     DOUBLE PRECISION NOT NULL,
      emitter_spacing_m DOUBLE PRECISION NOT NULL,
      emitter_id        TEXT NOT NULL REFERENCES emitters(id),
      lat               DOUBLE PRECISION NOT NULL,
      lon               DOUBLE PRECISION NOT NULL,
      UNIQUE (farm_id, name)
    )
    """,
]

# Copied exactly from seed_registry.sh. The two copies are kept in sync by hand (JL-005).
CATALOGUES_SQL = [
    """
    INSERT INTO crops (id, name) VALUES
      ('tomato', 'Tomato'),
      ('bell-pepper', 'Bell pepper')
    ON CONFLICT DO NOTHING
    """,
    """
    INSERT INTO soils (id, name, available_water_mm_per_m) VALUES
      ('sand', 'Sand', 83),
      ('loam', 'Loam', 175),
      ('clay-loam', 'Clay loam', 200)
    ON CONFLICT DO NOTHING
    """,
    """
    INSERT INTO emitters (id, name, flow_lph) VALUES
      ('dripnet-pc-0.6', 'DripNet PC', 0.6),
      ('dripnet-pc-1.0', 'DripNet PC', 1.0),
      ('dripnet-pc-1.6', 'DripNet PC', 1.6),
      ('dripnet-pc-2.0', 'DripNet PC', 2.0)
    ON CONFLICT DO NOTHING
    """,
]

DEMO_DATA_SQL = [
    """
    INSERT INTO farms (id, name) VALUES
      ('b7e2c0a0-3c1d-4f0a-9a11-0c5d2e6f1001', 'Demo cooperative'),
      ('a9c1e4b2-6f70-4d8e-a144-3f8b5c904004', 'East farm')
    ON CONFLICT DO NOTHING
    """,
    """
    INSERT INTO plots (
      id, farm_id, name, area_m2, crop_id, planting_date, soil_id,
      row_spacing_m, emitter_spacing_m, emitter_id, lat, lon
    ) VALUES
      (
        'c8f3d1b0-4d2e-5a1b-8b22-1d6e3f702002',
        'b7e2c0a0-3c1d-4f0a-9a11-0c5d2e6f1001',
        'North block', 1000, 'tomato', '2026-03-01', 'loam',
        1.5, 0.4, 'dripnet-pc-1.0', 31.25, 34.79
      ),
      (
        'd9a4e2c1-5e3f-4b6a-9c33-2e7f4a803003',
        'b7e2c0a0-3c1d-4f0a-9a11-0c5d2e6f1001',
        'East block', 800, 'bell-pepper', '2026-04-12', 'clay-loam',
        1.5, 0.4, 'dripnet-pc-1.6', 31.26, 34.80
      ),
      (
        'e0b5f3d2-6f40-4c7b-8d44-3f8a5b914004',
        'a9c1e4b2-6f70-4d8e-a144-3f8b5c904004',
        'West block', 1500, 'tomato', '2026-02-15', 'sand',
        1.5, 0.4, 'dripnet-pc-0.6', 31.40, 34.60
      ),
      (
        'f1c6a4e3-7051-4d8c-9e55-4a9b6c025005',
        'a9c1e4b2-6f70-4d8e-a144-3f8b5c904004',
        'Greenhouse', 400, 'bell-pepper', '2026-05-01', 'loam',
        1.2, 0.3, 'dripnet-pc-2.0', 31.41, 34.61
      )
    ON CONFLICT DO NOTHING
    """,
]


def create_schema(conn: Connection) -> None:
    for statement in CREATE_SCHEMA_SQL:
        conn.execute(text(statement))


def insert_catalogues(conn: Connection) -> None:
    for statement in CATALOGUES_SQL:
        conn.execute(text(statement))


def insert_demo_data(conn: Connection) -> None:
    for statement in DEMO_DATA_SQL:
        conn.execute(text(statement))


def count_rows(conn: Connection, table: str) -> int:
    return conn.execute(text(f"SELECT count(*) FROM {table}")).scalar_one()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Create the registry-service schema and catalogues in PostgreSQL. "
        "Initial schema setup only. Not a migration tool."
    )
    parser.add_argument(
        "--demo", action="store_true", help="also insert the 2 demo farms and 4 demo plots (not on a database with real grower data)"
    )
    args = parser.parse_args(argv)

    url = get_database_url()
    try:
        parsed = parse_database_url(url)
    except ValueError as error:
        print(error, file=sys.stderr)
        return 1
    if parsed.get_backend_name() != "postgresql":
        print("setup_postgres only works with a PostgreSQL DATABASE_URL.", file=sys.stderr)
        return 1

    print(f"Target: {display_url(parsed)}")
    if args.demo:
        print(DEMO_WARNING)

    # One transaction: PostgreSQL rolls back DDL too, so a failure changes nothing.
    with get_engine(url).begin() as conn:
        create_schema(conn)
        insert_catalogues(conn)
        if args.demo:
            insert_demo_data(conn)
        catalogues = (
            f"Catalogues: {count_rows(conn, 'crops')} crops, {count_rows(conn, 'soils')} soils, "
            f"{count_rows(conn, 'emitters')} emitters."
        )
        if args.demo:
            demo = f"Demo data: {count_rows(conn, 'farms')} farms, {count_rows(conn, 'plots')} plots."
        else:
            demo = "Demo data: skipped."

    print(f"{catalogues} {demo}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
