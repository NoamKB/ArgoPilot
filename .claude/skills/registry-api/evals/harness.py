"""Code checks for the registry-api skill evals.

Each eval case runs in its own copy of the repository, so parallel runs never touch
the real working tree or each other. Two commands:

  prepare: build the starting copy for one case (a pinned commit, plus the case's
           "before" state, e.g. with PATCH /v1/plots/{id} removed), install the
           locked dependencies, and check that the starting tests pass.
  check:   after the agent finished, start the copy's own uvicorn on a free port with
           a freshly seeded database, run the case's curl checks, `uv run pytest`,
           the starting tests against the changed code, and any hidden test.
           Prints a JSON list of {"text", "passed", "evidence"} and writes the diff.

  python3 harness.py prepare CASE REPO_ROOT DEST
  python3 harness.py check CASE DEST OUTPUTS_DIR

Assertions that need judgment (do the tests cover the failure cases?) are not here.
They are graded by an LLM judge from the diff and the agent's final answer.
"""

import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

SERVICE = Path("services/registry-service")

# Pinned so every run starts from the same code, whatever the branch looks like later.
# 2e01589 adds GET /v1/farms/{id}/area; its parent is the same code without it.
HEAD_COMMIT = "2e01589"
BEFORE_AREA_COMMIT = "2e01589^"

DEMO_FARM_ID = "b7e2c0a0-3c1d-4f0a-9a11-0c5d2e6f1001"
EAST_FARM_ID = "a9c1e4b2-6f70-4d8e-a144-3f8b5c904004"
UNKNOWN_ID = "00000000-0000-4000-8000-000000000000"
NORTH_BLOCK_ID = "c8f3d1b0-4d2e-5a1b-8b22-1d6e3f702002"
NORTH_BLOCK = {
    "id": NORTH_BLOCK_ID,
    "farm_id": DEMO_FARM_ID,
    "name": "North block",
    "area_m2": 1000.0,
    "crop_id": "tomato",
    "planting_date": "2026-03-01",
    "soil_id": "loam",
    "row_spacing_m": 1.5,
    "emitter_spacing_m": 0.4,
    "emitter_id": "dripnet-pc-1.0",
    "lat": 31.25,
    "lon": 34.79,
}


# ---------------------------------------------------------------- prepare


def run(cmd, cwd, env=None, check=True):
    return subprocess.run(cmd, cwd=cwd, env=env, check=check, capture_output=True, text=True)


def extract(repo: Path, commit: str, target: Path, *paths: str) -> None:
    """`git archive COMMIT [PATHS] | tar -x -C TARGET`, without a shell."""
    archive = subprocess.run(["git", "archive", "--format=tar", commit, *paths], cwd=repo, check=True, capture_output=True).stdout
    subprocess.run(["tar", "-x", "-C", str(target)], input=archive, check=True)


def replace_once(path: Path, old: str, new: str) -> None:
    """Replace text that must be there exactly once, so a changed file fails loudly."""
    text = path.read_text()
    if text.count(old) != 1:
        raise SystemExit(f"{path}: expected exactly one match for {old[:60]!r}")
    path.write_text(text.replace(old, new))


def remove_block(path: Path, start: str) -> None:
    """Remove a top-level block (function, class, decorated test) that starts with `start`.

    The block ends where the next top-level statement begins, i.e. at the next line that
    is neither blank nor indented. Blank lines before the next block are kept as they were.
    """
    lines = path.read_text().splitlines(keepends=True)
    # `start` may span several lines (a decorator and its def), so match from each line on.
    starts = [i for i in range(len(lines)) if "".join(lines[i:i + start.count("\n") + 1]).startswith(start)]
    if len(starts) != 1:
        raise SystemExit(f"{path}: expected exactly one block starting with {start!r}")
    begin = starts[0]
    end = begin + 1
    # A decorator block goes on until (and through) its def or class line.
    in_decorators = lines[begin].startswith("@")
    while end < len(lines):
        line = lines[end]
        if line.strip() == "" or line[0] in " \t)]}":  # body, or a closing bracket
            end += 1
        elif in_decorators and line.startswith(("def ", "class ", "@")):
            in_decorators = line.startswith("@")
            end += 1
        else:
            break
    # Give back the blank lines that separated this block from the next one.
    while end > begin + 1 and lines[end - 1].strip() == "":
        end -= 1
    # Drop the blank lines before the block, so two separators don't pile up.
    while begin > 0 and lines[begin - 1].strip() == "":
        begin -= 1
    path.write_text("".join(lines[:begin] + lines[end:]))


def without_plot_patch(service: Path) -> None:
    """Starting state for patch-plot-endpoint: PATCH /v1/plots/{id} does not exist yet."""
    remove_block(service / "routers/plots.py", '@router.patch("/{plot_id}"')
    replace_once(service / "routers/plots.py", "from schemas import Plot, PlotCreate, PlotUpdate", "from schemas import Plot, PlotCreate")
    remove_block(service / "repositories/plots.py", "UPDATABLE_COLUMNS = {")
    remove_block(service / "repositories/plots.py", "def update_plot(")
    remove_block(service / "schemas.py", "class PlotUpdate(")

    tests = service / "tests"
    for name in [
        "test_patch_changes_only_sent_fields", "test_patch_with_empty_body_changes_nothing",
        "test_patch_to_own_name_is_allowed", "test_patch_moves_plot_to_another_farm",
        "test_patch_rename_to_existing_name_returns_409_and_keeps_row",
        "test_patch_move_into_name_collision_returns_409", "test_patch_unknown_plot_returns_404",
        "test_patch_when_farm_is_deleted_meanwhile_returns_404",
        "test_patch_with_another_integrity_error_returns_500",
        "test_patch_when_plot_is_deleted_meanwhile_returns_404",
    ]:
        remove_block(tests / "test_plots.py", f"def {name}(")
    remove_block(tests / "test_plots.py", '@pytest.mark.parametrize(\n    ("body", "status"),')  # test_patch_applies_all_rules
    replace_once(tests / "test_plots.py", "\n\n# --- PATCH ---\n", "")
    replace_once(
        tests / "test_plots.py",
        "\n\n# The next tests simulate another request changing the data between the router's\n"
        "# checks and the UPDATE: the repository is replaced by one that fails the way the database would.\n",
        "",
    )
    for name in ["test_update_tracks_only_sent_fields", "test_empty_update_is_valid"]:
        remove_block(tests / "test_plot_models.py", f"def {name}(")
    remove_block(tests / "test_plot_models.py", '@pytest.mark.parametrize("field", list(VALID_PLOT))\ndef test_update_rejects_null')
    remove_block(tests / "test_plot_models.py", '@pytest.mark.parametrize(\n    ("field", "value"),\n    [("area_m2", 0), ("planting_date", TOMORROW)')
    replace_once(tests / "test_plot_models.py", "from schemas import PlotCreate, PlotUpdate", "from schemas import PlotCreate")
    remove_block(tests / "test_nul_input.py", '@pytest.mark.parametrize("field", ["name", "crop_id", "soil_id", "emitter_id"])\ndef test_nul_in_plot_update')
    remove_block(tests / "test_sql_safety.py", "def test_update_refuses_a_column_name_outside_the_allow_list(")
    replace_once(service / "README.md", "`GET`, `PATCH`, `DELETE` `/v1/plots/{id}`", "`GET`, `DELETE` `/v1/plots/{id}`")


def delete_farm_without_409(service: Path) -> None:
    """Starting state for delete-farm-with-plots: the foreign-key error escapes as a 500."""
    router = service / "routers/farms.py"
    replace_once(
        router,
        "    try:\n"
        "        deleted = farm_repository.delete_farm(conn, str(farm_id))\n"
        "    except IntegrityError as exc:\n"
        '        if violated_constraint(exc) == "foreign_key":\n'
        '            raise HTTPException(status_code=409, detail="Farm still has plots") from exc\n'
        "        raise\n"
        "    if not deleted:\n",
        "    if not farm_repository.delete_farm(conn, str(farm_id)):\n",
    )
    replace_once(router, "from sqlalchemy.exc import IntegrityError\n", "")
    replace_once(router, "from db import DbConnection, violated_constraint", "from db import DbConnection")
    tests = service / "tests/test_farms.py"
    remove_block(tests, "def test_delete_farm_with_plots_returns_409_and_keeps_farm(")
    remove_block(tests, "def test_delete_farm_with_another_integrity_error_returns_500(")


# case name -> (commit to start from, change that makes the starting state, or None)
CASES = {
    "farm-area-endpoint": (BEFORE_AREA_COMMIT, None),
    "patch-plot-endpoint": (HEAD_COMMIT, without_plot_patch),
    "delete-farm-with-plots": (HEAD_COMMIT, delete_farm_without_409),
    "error-format-compliance": (HEAD_COMMIT, None),
    "explain-soil-field": (HEAD_COMMIT, None),
}


def prepare(case: str, repo_root: Path, dest: Path) -> None:
    commit, make_starting_state = CASES[case]
    if dest.exists():
        raise SystemExit(f"{dest} already exists; remove it first")
    dest.mkdir(parents=True)
    # Only tracked files: no .env (it can hold a password), no registry.db, no .venv,
    # and no untracked skills, so the baseline run cannot find the skill under test.
    extract(repo_root, commit, dest)
    shutil.rmtree(dest / ".claude/skills/registry-api", ignore_errors=True)
    if make_starting_state:
        make_starting_state(dest / SERVICE)

    # A git repository of its own, so the diff of the agent's work is `git diff`.
    git = ["git", "-c", "user.name=eval", "-c", "user.email=eval@localhost", "-c", "commit.gpgsign=false"]
    run(git + ["init", "-q", "-b", "main"], cwd=dest)
    run(git + ["add", "-A"], cwd=dest)
    run(git + ["commit", "-q", "-m", f"starting state for {case}"], cwd=dest)

    service = dest / SERVICE
    run(["uv", "sync", "--frozen", "-q"], cwd=service)
    result = run(["uv", "run", "--frozen", "pytest", "-q", "-p", "no:cacheprovider"], cwd=service, check=False)
    if result.returncode != 0:
        raise SystemExit(f"starting tests fail for {case}:\n{result.stdout[-3000:]}")
    print(f"{case}: ready at {dest} ({result.stdout.strip().splitlines()[-1]})")


# ---------------------------------------------------------------- check


class Server:
    """The copy's own uvicorn on a free port, with a freshly seeded SQLite file."""

    def __init__(self, service: Path):
        self.service = service
        self.tmp = Path(tempfile.mkdtemp(prefix="registry-eval-"))

    def __enter__(self):
        db = self.tmp / "registry.db"
        run(["bash", "seed_registry.sh", str(db)], cwd=self.service)
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        self.base = f"http://127.0.0.1:{port}"
        self.process = subprocess.Popen(
            [str(self.service / ".venv/bin/python"), "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", str(port)],
            cwd=self.service,
            env={**os.environ, "DATABASE_URL": f"sqlite:///{db}"},
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        deadline = time.monotonic() + 15
        while True:
            try:
                urllib.request.urlopen(f"{self.base}/health", timeout=1)
                return self
            except OSError:
                if time.monotonic() > deadline or self.process.poll() is not None:
                    raise SystemExit("the changed service did not start")
                time.sleep(0.2)

    def __exit__(self, *exc):
        self.process.terminate()
        self.process.wait(timeout=10)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def curl(self, method: str, path: str, body=None):
        """Call the API with curl. Returns (status, content_type, parsed JSON or text, command)."""
        out = self.tmp / "body"
        cmd = ["curl", "-s", "-X", method, "-o", str(out), "-w", "%{http_code} %{content_type}", self.base + path]
        if body is not None:
            cmd += ["-H", "Content-Type: application/json", "--data", json.dumps(body)]
        status, _, content_type = run(cmd, cwd=self.tmp).stdout.partition(" ")
        text = out.read_text() if out.exists() else ""
        out.unlink(missing_ok=True)
        try:
            payload = json.loads(text)
        except ValueError:
            payload = text
        shown = f"curl -X {method} {path}" + (f" -d '{json.dumps(body)}'" if body is not None else "")
        return int(status), content_type, payload, shown


def result(text: str, passed: bool, evidence: str) -> dict:
    return {"text": text, "passed": bool(passed), "evidence": evidence}


def described(response) -> str:
    status, content_type, payload, shown = response
    return f"{shown} -> {status} {content_type} {json.dumps(payload)[:300]}"


def changed_files(dest: Path) -> list[str]:
    status = run(["git", "status", "--porcelain", "-uall"], cwd=dest).stdout
    return [line[3:] for line in status.splitlines() if line.strip()]


def run_pytest(dest: Path) -> dict:
    """`uv run pytest` in the agent's copy, as the user would run it."""
    out = run(["uv", "run", "--frozen", "pytest", "-q", "-p", "no:cacheprovider"], cwd=dest / SERVICE, check=False)
    last = out.stdout.strip().splitlines()[-1] if out.stdout.strip() else out.stderr[-300:]
    return result("uv run pytest passes in services/registry-service", out.returncode == 0, f"exit {out.returncode}: {last}")


def run_tests_on_copy(dest: Path, tests_dir: Path, extra: dict[str, str] | None = None, select=None):
    """Run a given tests/ folder (plus extra files) against the agent's changed code."""
    with tempfile.TemporaryDirectory(prefix="registry-eval-tests-") as tmp:
        work = Path(tmp) / "service"
        shutil.copytree(dest / SERVICE, work, ignore=shutil.ignore_patterns(".venv", "__pycache__", "registry.db", "htmlcov", ".coverage", ".pytest_cache"))
        shutil.rmtree(work / "tests")
        shutil.copytree(tests_dir, work / "tests")
        for name, content in (extra or {}).items():
            (work / "tests" / name).write_text(content)
        cmd = [str(dest / SERVICE / ".venv/bin/python"), "-m", "pytest", "-q", "-p", "no:cacheprovider"] + (select or [])
        out = run(cmd, cwd=work, check=False)
        lines = out.stdout.strip().splitlines()
        return out.returncode == 0, (lines[-1] if lines else out.stderr[-300:]), out.stdout


def starting_tests(dest: Path) -> Path:
    """The tests/ folder as it was before the agent started (the copy's first commit)."""
    target = Path(tempfile.mkdtemp(prefix="registry-eval-start-"))
    root = run(["git", "rev-list", "--max-parents=0", "HEAD"], cwd=dest).stdout.split()[0]
    extract(dest, root, target, f"{SERVICE}/tests")
    return target / SERVICE / "tests"


def no_regressions(dest: Path) -> dict:
    passed, last, _ = run_tests_on_copy(dest, starting_tests(dest))
    return result("The tests that existed before the change still pass against the changed code", passed, last)


def number_in(payload) -> list:
    return [v for v in payload.values() if isinstance(v, (int, float)) and not isinstance(v, bool)] if isinstance(payload, dict) else []


def check_farm_area(server: Server, dest: Path) -> list[dict]:
    checks = []
    demo = server.curl("GET", f"/v1/farms/{DEMO_FARM_ID}/area")
    checks.append(result(
        "GET /v1/farms/{demo farm id}/area returns 200 with a total of 1800 (North block 1000 + East block 800)",
        demo[0] == 200 and 1800 in number_in(demo[2]), described(demo)))
    extra = [k for k in demo[2]] if isinstance(demo[2], dict) else ["(not an object)"]
    numbers = number_in(demo[2])
    only_listed = isinstance(demo[2], dict) and len(numbers) == 1 and len(demo[2]) <= 2 and all(
        isinstance(v, (int, float)) or v == DEMO_FARM_ID for v in demo[2].values())
    checks.append(result(
        "The area response holds only the total and at most the farm id, with no extra fields such as a plot count",
        only_listed, f"fields: {extra}"))
    unknown = server.curl("GET", f"/v1/farms/{UNKNOWN_ID}/area")
    checks.append(result(
        'GET /v1/farms/{unknown id}/area returns 404, Content-Type application/json, body exactly {"detail": "Farm not found"}',
        unknown[0] == 404 and unknown[1].startswith("application/json") and unknown[2] == {"detail": "Farm not found"},
        described(unknown)))
    created = server.curl("POST", "/v1/farms", {"name": "Eval empty farm"})
    farm_id = created[2].get("id") if isinstance(created[2], dict) else None
    empty = server.curl("GET", f"/v1/farms/{farm_id}/area")
    checks.append(result(
        "A farm with no plots returns 200 with a total of 0, not 404",
        empty[0] == 200 and number_in(empty[2]) == [0], described(empty)))
    bad = server.curl("GET", "/v1/farms/not-a-uuid/area")
    checks.append(result("A non-UUID farm id returns 422", bad[0] == 422, described(bad)))
    return checks


def check_patch_plot(server: Server, dest: Path) -> list[dict]:
    checks = []
    path = f"/v1/plots/{NORTH_BLOCK_ID}"

    # Failure cases first, while the plot is still the seed row.
    def expect(status, body=None):
        return lambda r: r[0] == status and (body is None or r[2] == body)

    cases = [
        ("PATCH on an unknown plot id returns 404 with body exactly {\"detail\": \"Plot not found\"}",
         "PATCH", f"/v1/plots/{UNKNOWN_ID}", {"name": "X"}, expect(404, {"detail": "Plot not found"}), False),
        ("PATCH with an unknown farm_id returns 404 with body exactly {\"detail\": \"Farm not found\"} and leaves the plot unchanged",
         "PATCH", path, {"farm_id": UNKNOWN_ID}, expect(404, {"detail": "Farm not found"}), True),
        ("PATCH with an unknown crop_id returns 422 with body exactly {\"detail\": \"Unknown crop\"} and leaves the plot unchanged",
         "PATCH", path, {"crop_id": "unknown"}, expect(422, {"detail": "Unknown crop"}), True),
        ("PATCH that renames a plot to another plot's name on the same farm returns 409 with body exactly "
         "{\"detail\": \"Plot name already exists on this farm\"} and leaves the plot unchanged",
         "PATCH", path, {"name": "East block"}, expect(409, {"detail": "Plot name already exists on this farm"}), True),
        ("PATCH with a field that plots don't have returns 422 and leaves the plot unchanged",
         "PATCH", path, {"colour": "red"}, expect(422), True),
        ("PATCH with area_m2 0 returns 422 and leaves the plot unchanged",
         "PATCH", path, {"area_m2": 0}, expect(422), True),
    ]
    failures = []
    for text, method, target, body, ok, keeps_row in cases:
        response = server.curl(method, target, body)
        passed = ok(response)
        evidence = described(response)
        if keeps_row:
            after = server.curl("GET", path)
            passed = passed and after[2] == NORTH_BLOCK
            evidence += f" | then GET {'unchanged' if after[2] == NORTH_BLOCK else 'CHANGED: ' + json.dumps(after[2])[:200]}"
        failures.append(result(text, passed, evidence))

    empty = server.curl("PATCH", path, {})
    checks.append(result("PATCH with an empty body {} returns 200 and the plot unchanged",
                         empty[0] == 200 and empty[2] == NORTH_BLOCK, described(empty)))
    partial = server.curl("PATCH", path, {"area_m2": 1200})
    after = server.curl("GET", path)
    expected = {**NORTH_BLOCK, "area_m2": 1200.0}
    checks.insert(0, result(
        "PATCH with only area_m2 returns 200 and changes area_m2 only; every other field of the plot is unchanged, and GET returns the same plot",
        partial[0] == 200 and partial[2] == expected and after[2] == expected,
        described(partial) + f" | then GET -> {json.dumps(after[2])[:300]}"))
    return checks + failures


HIDDEN_DELETE_TEST = '''
import sqlite3

from fastapi.testclient import TestClient

from main import app
from repositories import farms as farm_repository
from test_database_errors import integrity_error, sqlite_error


def test_hidden_other_integrity_error_on_delete_stays_500(client, monkeypatch):
    # A farm without plots, so a fix that checks for plots first still reaches delete_farm.
    farm_id = client.post("/v1/farms", json={"name": "Hidden test farm"}).json()["id"]

    def delete_fails(conn, farm_id):
        raise integrity_error(sqlite_error(sqlite3.IntegrityError, "SQLITE_CONSTRAINT_CHECK"))

    monkeypatch.setattr(farm_repository, "delete_farm", delete_fails)
    response = TestClient(app, raise_server_exceptions=False).delete(f"/v1/farms/{farm_id}")

    assert response.status_code == 500
'''


def check_delete_farm(server: Server, dest: Path) -> list[dict]:
    checks = []
    response = server.curl("DELETE", f"/v1/farms/{DEMO_FARM_ID}")
    checks.append(result(
        'DELETE /v1/farms/{farm with plots} returns 409 with Content-Type application/json and a body of the form {"detail": "<text>"}',
        response[0] == 409 and response[1].startswith("application/json") and isinstance(response[2], dict)
        and list(response[2]) == ["detail"] and isinstance(response[2]["detail"], str),
        described(response)))
    farm = server.curl("GET", f"/v1/farms/{DEMO_FARM_ID}")
    plots = server.curl("GET", f"/v1/plots?farm_id={DEMO_FARM_ID}")
    checks.append(result("After that 409, the farm and its plots still exist",
                         farm[0] == 200 and isinstance(plots[2], list) and len(plots[2]) == 2,
                         f"{described(farm)} | plots of the farm: {len(plots[2]) if isinstance(plots[2], list) else plots[2]}"))
    created = server.curl("POST", "/v1/farms", {"name": "Eval empty farm"})
    deleted = server.curl("DELETE", f"/v1/farms/{created[2].get('id')}")
    checks.append(result("DELETE of a farm without plots still returns 204 with an empty body",
                         deleted[0] == 204 and deleted[2] == "", described(deleted)))
    unknown = server.curl("DELETE", f"/v1/farms/{UNKNOWN_ID}")
    checks.append(result('DELETE of an unknown farm still returns 404 with body exactly {"detail": "Farm not found"}',
                         unknown[0] == 404 and unknown[2] == {"detail": "Farm not found"}, described(unknown)))
    passed, last, out = run_tests_on_copy(dest, starting_tests(dest), {"test_hidden_delete_farm.py": HIDDEN_DELETE_TEST},
                                          ["tests/test_hidden_delete_farm.py"])
    failure = next((line for line in out.splitlines() if line.startswith("E ")), "")
    checks.append(result(
        "When deleting a farm raises an IntegrityError other than a foreign-key violation, the response is 500, not 409 (hidden test)",
        passed, f"{last} {failure}".strip()))
    return checks


def check_error_format(server: Server, dest: Path) -> list[dict]:
    unknown = server.curl("GET", f"/v1/farms/{UNKNOWN_ID}")
    invalid = server.curl("POST", "/v1/farms", {"name": ""})
    service_changes = [f for f in changed_files(dest) if f.startswith(str(SERVICE))]
    return [
        result('GET /v1/farms/{unknown id} still returns 404, Content-Type application/json, body exactly {"detail": "Farm not found"}',
               unknown[0] == 404 and unknown[1].startswith("application/json") and unknown[2] == {"detail": "Farm not found"},
               described(unknown)),
        result("A request with an invalid body still returns FastAPI's default 422 body: Content-Type application/json and a detail list",
               invalid[0] == 422 and invalid[1].startswith("application/json") and isinstance(invalid[2], dict)
               and list(invalid[2]) == ["detail"] and isinstance(invalid[2]["detail"], list),
               described(invalid)),
        result("No file in services/registry-service was changed", not service_changes, f"changed: {service_changes or 'none'}"),
    ]


def check_explain(server: Server, dest: Path) -> list[dict]:
    changes = changed_files(dest)
    return [result("No file in the repository was changed", not changes, f"changed: {changes or 'none'}")]


CHECKS = {
    "farm-area-endpoint": (check_farm_area, True),
    "patch-plot-endpoint": (check_patch_plot, True),
    "delete-farm-with-plots": (check_delete_farm, True),
    "error-format-compliance": (check_error_format, False),
    "explain-soil-field": (check_explain, False),
}


def check(case: str, dest: Path, outputs: Path) -> None:
    outputs.mkdir(parents=True, exist_ok=True)
    # The diff first, before running anything that could leave files behind.
    run(["git", "add", "-A", "-N"], cwd=dest)
    (outputs / "changes.diff").write_text(run(["git", "diff"], cwd=dest).stdout or "(no changes)\n")
    run(["git", "reset", "-q"], cwd=dest)
    case_checks, needs_pytest = CHECKS[case]
    results = []
    if case != "explain-soil-field":
        with Server(dest / SERVICE) as server:
            results += case_checks(server, dest)
    else:
        results += case_checks(None, dest)
    if needs_pytest:
        results.append(run_pytest(dest))
    if case != "explain-soil-field":
        results.append(no_regressions(dest))
    (outputs / "code_checks.json").write_text(json.dumps(results, indent=2))
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    command, *args = sys.argv[1:]
    if command == "prepare":
        prepare(args[0], Path(args[1]).resolve(), Path(args[2]).resolve())
    elif command == "check":
        check(args[0], Path(args[1]).resolve(), Path(args[2]).resolve())
    else:
        raise SystemExit(__doc__)
