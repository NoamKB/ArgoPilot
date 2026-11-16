from scripts.setup_postgres import main


def test_refuses_sqlite_url(capsys, sqlite_db_path):
    # Runs on both backends: the autouse fixture always points DATABASE_URL at SQLite.
    assert main([]) == 1
    assert "PostgreSQL" in capsys.readouterr().err
    assert not sqlite_db_path.exists()
