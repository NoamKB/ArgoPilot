"""Embed the real registry-service source files into the debugger template.

Rebuild the debugger after the registry-service code changes. Run from services/registry-service
(the script reads the source files from the current directory and needs the service's packages):
    uv run python ../../docs/presentations/debugger-src/build_debugger.py \
        ../../docs/presentations/debugger-src/debugger.template.html \
        ../../docs/presentations/request-debugger.html
Then check the step data (needs Node.js):
    node ../../docs/presentations/debugger-src/check_debugger.js ../../docs/presentations/request-debugger.html
The step texts in the template refer to line numbers in the source files, so after a code change
the checker may report lines out of range, and the step texts may need updating.
"""
import json
import sqlite3
import sys
from pathlib import Path

import fastapi
import pydantic
import starlette
import uvicorn

FILES = [
    "main.py", "db.py", "schemas.py",
    "routers/catalogues.py", "routers/farms.py", "routers/plots.py",
    "repositories/catalogues.py", "repositories/farms.py", "repositories/plots.py",
    "seed_registry.sh",
]

template_path, output_path = Path(sys.argv[1]), Path(sys.argv[2])
service = Path.cwd()
sources = {name: (service / name).read_text(encoding="utf-8") for name in FILES}
versions = (
    f"FastAPI {fastapi.__version__} · Starlette {starlette.__version__} · Pydantic {pydantic.VERSION}"
    f" · uvicorn {uvicorn.__version__} · Python {sys.version.split()[0]} · SQLite {sqlite3.sqlite_version}"
)

# "</" would end the <script> element early, so escape it inside the JSON.
src_json = json.dumps(sources, ensure_ascii=False).replace("</", "<\\/")
html = template_path.read_text(encoding="utf-8")
assert html.count("__SRC_JSON__") == 1 and html.count("__VERSIONS__") == 1
html = html.replace("__SRC_JSON__", src_json).replace("__VERSIONS__", json.dumps(versions, ensure_ascii=False))
output_path.write_text(html, encoding="utf-8")
print(f"wrote {output_path} ({len(html):,} characters)")
print(versions)
