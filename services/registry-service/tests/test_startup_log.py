import logging

from fastapi.testclient import TestClient

from main import app


def startup_log(monkeypatch, caplog, url: str) -> str:
    monkeypatch.setenv("DATABASE_URL", url)
    caplog.set_level(logging.INFO, logger="uvicorn.error")
    with TestClient(app):  # entering the client runs the app's startup (lifespan)
        pass
    return caplog.text


def test_startup_logs_backend_and_target_with_password_hidden(monkeypatch, caplog):
    text = startup_log(monkeypatch, caplog, "postgresql+psycopg://app:s3cret-9q@db.example.com:5432/prod")
    assert "Database: postgresql, postgresql+psycopg://app:***@db.example.com:5432/prod" in text
    assert "s3cret-9q" not in text


def test_startup_logs_sqlite_file(monkeypatch, caplog, tmp_path):
    text = startup_log(monkeypatch, caplog, f"sqlite:///{tmp_path / 'registry.db'}")
    assert f"Database: sqlite, sqlite:///{tmp_path / 'registry.db'}" in text


def test_startup_log_for_unencoded_at_hides_the_password(monkeypatch, caplog):
    text = startup_log(monkeypatch, caplog, "postgresql+psycopg://app:p@ss@db.example.com/prod")
    assert "%40" in text
    assert "ss@db" not in text
