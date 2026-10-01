import sqlite3

from alembic import command
from alembic.config import Config

from job_search_agent.config import reset_settings


def test_migrations_build_current_schema(tmp_path, monkeypatch):
    database = tmp_path / "migrated.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{database}")
    reset_settings()

    command.upgrade(Config("alembic.ini"), "head")

    with sqlite3.connect(database) as connection:
        indexes = connection.execute("PRAGMA index_list(applications)").fetchall()
    assert any(index[2] for index in indexes)
    reset_settings()
