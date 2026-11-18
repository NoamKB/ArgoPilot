import runpy
import sys
from pathlib import Path

import pytest

from scripts import setup_postgres
from scripts.setup_postgres import main


def test_refuses_sqlite_url(capsys, sqlite_db_path):
    # Runs on both backends: the autouse fixture always points DATABASE_URL at SQLite.
    assert main([]) == 1
    assert "PostgreSQL" in capsys.readouterr().err
    assert not sqlite_db_path.exists()


def test_unencoded_at_in_password_is_refused_before_printing(monkeypatch, capsys):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://app:p@ss@db.example.com/prod")
    assert main([]) == 1
    output = capsys.readouterr()
    assert "%40" in output.err
    assert "ss@db" not in output.out + output.err


def test_running_the_script_exits_with_the_main_result(monkeypatch, capsys):
    # As `python -m scripts.setup_postgres`: the exit code is main()'s return value.
    monkeypatch.setattr(sys, "argv", ["setup_postgres.py"])

    with pytest.raises(SystemExit) as exit_info:
        runpy.run_path(str(Path(setup_postgres.__file__)), run_name="__main__")

    assert exit_info.value.code == 1  # the autouse fixture's SQLite URL is refused
    assert "PostgreSQL" in capsys.readouterr().err
