"""Embed the real registry-service source files into a debugger template.

There are two debuggers:
- request-debugger-sqlalchemy.html, from debugger-sqlalchemy.template.html: the current code
  (SQLAlchemy Core, PostgreSQL). Rebuild it after the registry-service code changes.
- request-debugger.html, from debugger.template.html: the P1 snapshot (sqlite3), with the P1
  source already embedded. Do not rebuild it from main: its step texts match the P1 code only.

Run from services/registry-service (the script reads the source files from the current directory
and needs the service's packages):
    uv run python ../../docs/presentations/p2/debugger-src/build_debugger.py \
        ../../docs/presentations/p2/debugger-src/debugger-sqlalchemy.template.html \
        ../../docs/presentations/p2/request-debugger-sqlalchemy.html
Then check the step data (needs Node.js):
    node ../../docs/presentations/p2/debugger-src/check_debugger.js ../../docs/presentations/p2/request-debugger-sqlalchemy.html
The step texts find their lines by searching the source, so after a code change the checker may
report missing lines, and the step texts may need updating.
"""
import json
import sqlite3
import sys
from pathlib import Path

import fastapi
import psycopg
import pydantic
import sqlalchemy
import starlette
import uvicorn

FILES = [
    "main.py", "db.py", "schemas.py",
    "routers/catalogues.py", "routers/farms.py", "routers/plots.py",
    "repositories/catalogues.py", "repositories/farms.py", "repositories/plots.py",
    "seed_registry.sh", "scripts/setup_postgres.py",
]

template_path, output_path = Path(sys.argv[1]), Path(sys.argv[2])
service = Path.cwd()
sources = {name: (service / name).read_text(encoding="utf-8") for name in FILES}
versions = (
    f"FastAPI {fastapi.__version__} · Starlette {starlette.__version__} · Pydantic {pydantic.VERSION}"
    f" · uvicorn {uvicorn.__version__} · SQLAlchemy {sqlalchemy.__version__} · psycopg {psycopg.__version__}"
    f" · Python {sys.version.split()[0]} · SQLite {sqlite3.sqlite_version}"
)

# "</" would end the <script> element early, so escape it inside the JSON.
src_json = json.dumps(sources, ensure_ascii=False).replace("</", "<\\/")
html = template_path.read_text(encoding="utf-8")
assert html.count("__SRC_JSON__") == 1 and html.count("__VERSIONS__") == 1
html = html.replace("__SRC_JSON__", src_json).replace("__VERSIONS__", json.dumps(versions, ensure_ascii=False))
output_path.write_text(html, encoding="utf-8")
print(f"wrote {output_path} ({len(html):,} characters)")
print(versions)
