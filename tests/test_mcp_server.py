"""Tests for the pure-SQL MCP server (run_sql + get_schema).

Tests the tool functions directly using the populated_db fixture,
and tests create_server() with a temporary database.
"""

from __future__ import annotations

import json
import os
from unittest.mock import patch

from mtk.core.database import Database
from mtk.mcp.server import create_server, get_schema, run_sql

# =============================================================================
# TestRunSql
# =============================================================================


class TestRunSql:
    """Tests for the run_sql tool function."""

    def test_select_returns_rows(self, populated_db: Database) -> None:
        with populated_db.session() as session:
            result = json.loads(run_sql(session, "SELECT * FROM emails ORDER BY date"))
            assert isinstance(result, list)
            assert len(result) == 5
            assert "message_id" in result[0]
            assert "from_addr" in result[0]
            assert "subject" in result[0]

    def test_select_empty_result(self, populated_db: Database) -> None:
        with populated_db.session() as session:
            result = json.loads(
                run_sql(session, "SELECT * FROM emails WHERE message_id = 'nonexistent'")
            )
            assert result == []

    def test_readonly_blocks_insert(self, populated_db: Database) -> None:
        with populated_db.session() as session:
            result = json.loads(
                run_sql(session, "INSERT INTO tags (name, source) VALUES ('test', 'mtk')")
            )
            assert "error" in result
            assert "readonly" in result["error"].lower() or "blocked" in result["error"].lower()

    def test_readonly_blocks_delete(self, populated_db: Database) -> None:
        with populated_db.session() as session:
            result = json.loads(run_sql(session, "DELETE FROM tags WHERE name = 'important'"))
            assert "error" in result

    def test_readonly_blocks_update(self, populated_db: Database) -> None:
        with populated_db.session() as session:
            result = json.loads(
                run_sql(session, "UPDATE emails SET subject = 'hacked' WHERE id = 1")
            )
            assert "error" in result

    def test_writable_allows_insert(self, populated_db: Database) -> None:
        with populated_db.session() as session:
            result = json.loads(
                run_sql(
                    session,
                    "INSERT INTO tags (name, source) VALUES ('newtag', 'mtk')",
                    readonly=False,
                )
            )
            assert "affected_rows" in result
            assert result["affected_rows"] == 1

        # Verify the insert persisted
        with populated_db.session() as session:
            check = json.loads(run_sql(session, "SELECT * FROM tags WHERE name = 'newtag'"))
            assert len(check) == 1
            assert check[0]["name"] == "newtag"

    def test_fts5_search(self, populated_db: Database) -> None:
        with populated_db.session() as session:
            result = json.loads(
                run_sql(session, "SELECT * FROM emails_fts WHERE emails_fts MATCH 'project'")
            )
            assert isinstance(result, list)
            assert len(result) >= 1

    def test_invalid_sql_returns_error(self, populated_db: Database) -> None:
        with populated_db.session() as session:
            result = json.loads(run_sql(session, "SELECTT * FROMM nowhere"))
            assert "error" in result

    def test_ddl_always_blocked(self, populated_db: Database) -> None:
        with populated_db.session() as session:
            for stmt in [
                "DROP TABLE emails",
                "ALTER TABLE emails ADD COLUMN foo TEXT",
                "CREATE TABLE evil (id INTEGER)",
                "ATTACH DATABASE ':memory:' AS evil",
                "DETACH DATABASE evil",
            ]:
                result = json.loads(run_sql(session, stmt, readonly=False))
                assert "error" in result, f"DDL not blocked: {stmt}"
                assert "not allowed" in result["error"].lower() or "DDL" in result["error"]

    def test_pragma_allowed(self, populated_db: Database) -> None:
        with populated_db.session() as session:
            result = json.loads(run_sql(session, "PRAGMA table_info('emails')"))
            assert isinstance(result, list)
            assert len(result) > 0
            # PRAGMA table_info returns columns: cid, name, type, notnull, dflt_value, pk
            assert "name" in result[0]


# =============================================================================
# TestGetSchema
# =============================================================================


class TestGetSchema:
    """Tests for the get_schema tool function."""

    def test_returns_valid_json(self, populated_db: Database) -> None:
        with populated_db.session() as session:
            result = json.loads(get_schema(session))
            assert isinstance(result, dict)

    def test_contains_tables(self, populated_db: Database) -> None:
        with populated_db.session() as session:
            result = json.loads(get_schema(session))
            tables = result["tables"]
            for name in ["emails", "persons", "threads", "tags"]:
                assert name in tables, f"Missing table: {name}"

    def test_table_has_columns(self, populated_db: Database) -> None:
        with populated_db.session() as session:
            result = json.loads(get_schema(session))
            emails = result["tables"]["emails"]
            assert "columns" in emails
            col_names = [c["name"] for c in emails["columns"]]
            assert "message_id" in col_names
            assert "from_addr" in col_names

    def test_includes_fts5(self, populated_db: Database) -> None:
        with populated_db.session() as session:
            result = json.loads(get_schema(session))
            tables = result["tables"]
            assert "emails_fts" in tables

    def test_includes_descriptions(self, populated_db: Database) -> None:
        with populated_db.session() as session:
            result = json.loads(get_schema(session))
            emails = result["tables"]["emails"]
            assert "description" in emails
            assert emails["description"] != ""

    def test_includes_tips(self, populated_db: Database) -> None:
        with populated_db.session() as session:
            result = json.loads(get_schema(session))
            assert "tips" in result
            assert isinstance(result["tips"], list)
            assert len(result["tips"]) > 0

    def test_table_has_ddl(self, populated_db: Database) -> None:
        with populated_db.session() as session:
            result = json.loads(get_schema(session))
            for name, entry in result["tables"].items():
                assert "ddl" in entry, f"Table {name} missing ddl field"


# =============================================================================
# TestCreateServer
# =============================================================================


class TestCreateServer:
    """Tests for create_server() factory."""

    def test_creates_server(self, tmp_path) -> None:
        db_path = tmp_path / "test.db"
        with patch.dict(os.environ, {"MTK_DATABASE_PATH": str(db_path)}):
            server = create_server()
        assert server is not None
        # The Server class has a 'name' attribute
        assert server.name == "mtk"
