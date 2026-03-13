from app.core.config import settings
from app.core.database import run_migrations_to_head
from sqlalchemy import create_engine, inspect


def test_runtime_migration_expands_odoo_draft_action_lengths(tmp_path, monkeypatch):
    database_path = tmp_path / "runtime-schema.sqlite"
    database_url = f"sqlite:///{database_path.as_posix()}"

    monkeypatch.setattr(settings, "DATABASE_URL", database_url, raising=False)
    run_migrations_to_head(database_url)

    engine = create_engine(database_url)
    try:
        columns = {
            column["name"]: column
            for column in inspect(engine).get_columns("odoo_draft_actions")
        }
    finally:
        engine.dispose()

    assert getattr(columns["action_key"]["type"], "length", None) == 500
    assert getattr(columns["target_path"]["type"], "length", None) == 2048
