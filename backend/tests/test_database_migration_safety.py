import pytest

from app.core import database as database_module


class _FakeInspector:
    def __init__(self, tables, columns_by_table):
        self._tables = tables
        self._columns_by_table = columns_by_table

    def get_table_names(self):
        return self._tables

    def get_columns(self, table_name):
        return [{"name": name} for name in self._columns_by_table.get(table_name, [])]


class _FakeConnection:
    def __init__(self):
        self.executed = []
        self.committed = False

    def execute(self, statement):
        self.executed.append(statement)

    def commit(self):
        self.committed = True


def test_ensure_column_exists_rejects_unsafe_identifiers():
    conn = _FakeConnection()

    with pytest.raises(ValueError, match="Unsafe table identifier"):
        database_module._ensure_column_exists(
            conn, "audits;DROP TABLE audits", "webhook_url", "VARCHAR(500)"
        )

    with pytest.raises(ValueError, match="Unsafe column identifier"):
        database_module._ensure_column_exists(
            conn, "audits", "webhook_url;DROP", "VARCHAR(500)"
        )


def test_ensure_column_exists_rejects_unsafe_column_definitions():
    conn = _FakeConnection()

    with pytest.raises(ValueError, match="Unsafe column definition"):
        database_module._ensure_column_exists(
            conn,
            "audits",
            "webhook_url",
            "VARCHAR(500); DROP TABLE audits",
        )


def test_ensure_column_exists_executes_safe_alter(monkeypatch):
    conn = _FakeConnection()
    inspector = _FakeInspector(["audits"], {"audits": []})
    monkeypatch.setattr(database_module, "inspect", lambda _connection: inspector)

    database_module._ensure_column_exists(
        conn,
        "audits",
        "webhook_url",
        "varchar(500)",
    )

    assert conn.committed is True
    assert len(conn.executed) == 1
    statement = str(conn.executed[0])
    assert "ALTER TABLE audits ADD COLUMN webhook_url VARCHAR(500)" in statement


def test_ensure_column_exists_noop_when_table_missing(monkeypatch):
    conn = _FakeConnection()
    inspector = _FakeInspector([], {})
    monkeypatch.setattr(database_module, "inspect", lambda _connection: inspector)

    database_module._ensure_column_exists(
        conn,
        "audits",
        "webhook_url",
        "VARCHAR(500)",
    )

    assert conn.executed == []
    assert conn.committed is False
