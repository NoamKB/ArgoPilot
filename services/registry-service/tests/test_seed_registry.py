import sqlite3
import subprocess
from pathlib import Path

SEED_SCRIPT = Path(__file__).resolve().parent.parent / "seed_registry.sh"


def run_seed(*args: str, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(["bash", str(SEED_SCRIPT), *args], cwd=cwd, capture_output=True, text=True)


def farm_names(db_path: Path) -> list[str]:
    with sqlite3.connect(db_path) as conn:
        return [name for (name,) in conn.execute("SELECT name FROM farms ORDER BY name")]


def add_farm(db_path: Path, name: str) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute("INSERT INTO farms (id, name) VALUES ('added-by-test', ?)", (name,))


def test_new_path_is_seeded(tmp_path):
    db_path = tmp_path / "new.db"

    result = run_seed(str(db_path), cwd=tmp_path)

    assert result.returncode == 0
    assert len(farm_names(db_path)) == 2


def test_default_path_is_registry_db_in_current_directory(tmp_path):
    result = run_seed(cwd=tmp_path)

    assert result.returncode == 0
    assert len(farm_names(tmp_path / "registry.db")) == 2


def test_existing_database_is_left_unchanged(tmp_path):
    db_path = tmp_path / "registry.db"
    run_seed(str(db_path), cwd=tmp_path)
    add_farm(db_path, "Grower data")
    before = db_path.read_bytes()

    result = run_seed(str(db_path), cwd=tmp_path)

    assert result.returncode == 1
    assert "--reset" in result.stderr
    assert db_path.read_bytes() == before


def test_reset_replaces_existing_database_with_fresh_seed(tmp_path):
    db_path = tmp_path / "registry.db"
    run_seed(str(db_path), cwd=tmp_path)
    add_farm(db_path, "Grower data")

    result = run_seed("--reset", str(db_path), cwd=tmp_path)

    assert result.returncode == 0
    assert "Grower data" not in farm_names(db_path)
    assert len(farm_names(db_path)) == 2
