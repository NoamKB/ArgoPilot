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
