"""Tests for HTML SPA export."""

from __future__ import annotations

import base64
import re
from pathlib import Path

from sqlalchemy import select

from mail_memex.core.database import Database
from mail_memex.core.models import Email
from mail_memex.export.html_export import HtmlExporter


class TestHtmlExporter:
    def test_html_export_creates_file(self, populated_db: Database, tmp_dir: Path) -> None:
        output = tmp_dir / "archive.html"
        with populated_db.session() as session:
            emails = list(session.execute(select(Email)).scalars())
            exporter = HtmlExporter(output)
            result = exporter.export(emails)
        assert output.exists()
        assert result.emails_exported == 5
        assert result.format == "html"

    def test_html_export_contains_sql_js(self, populated_db: Database, tmp_dir: Path) -> None:
        output = tmp_dir / "archive.html"
        with populated_db.session() as session:
            emails = list(session.execute(select(Email)).scalars())
            HtmlExporter(output).export(emails)
        html = output.read_text()
        assert "sql-wasm.js" in html
        assert "mail-memex" in html

    def test_html_export_embeds_database(self, populated_db: Database, tmp_dir: Path) -> None:
        output = tmp_dir / "archive.html"
        with populated_db.session() as session:
            emails = list(session.execute(select(Email)).scalars())
            HtmlExporter(output).export(emails)
        html = output.read_text()
        assert "DB_BASE64" in html

    def test_output_is_valid_html(self, populated_db: Database, tmp_dir: Path) -> None:
        output = tmp_dir / "archive.html"
        with populated_db.session() as session:
            emails = list(session.execute(select(Email)).scalars())
            HtmlExporter(output).export(emails)
        content = output.read_text()
        assert content.startswith("<!DOCTYPE html>")
        assert "</html>" in content

    def test_export_result_to_dict(self, populated_db: Database, tmp_dir: Path) -> None:
        output = tmp_dir / "archive.html"
        with populated_db.session() as session:
            emails = list(session.execute(select(Email)).scalars())
            result = HtmlExporter(output).export(emails)
        d = result.to_dict()
        assert d["format"] == "html"
        assert d["emails_exported"] == 5
        assert d["output_path"] == str(output)

    def test_contains_ui_elements(self, populated_db: Database, tmp_dir: Path) -> None:
        """Verify the HTML contains key UI elements."""
        output = tmp_dir / "archive.html"
        with populated_db.session() as session:
            emails = list(session.execute(select(Email)).scalars())
            HtmlExporter(output).export(emails)
        content = output.read_text()
        assert 'id="search-box"' in content
        assert 'id="stats"' in content
        assert 'id="list-pane"' in content
        assert 'id="detail-pane"' in content

    def test_creates_parent_directories(self, populated_db: Database, tmp_dir: Path) -> None:
        output = tmp_dir / "sub" / "dir" / "archive.html"
        with populated_db.session() as session:
            emails = list(session.execute(select(Email)).scalars())
            result = HtmlExporter(output).export(emails)
        assert output.exists()
        assert result.emails_exported == 5

    def test_embedded_db_is_valid_base64(self, populated_db: Database, tmp_dir: Path) -> None:
        """Verify the embedded database is valid base64 that decodes to SQLite bytes."""
        output = tmp_dir / "archive.html"
        with populated_db.session() as session:
            emails = list(session.execute(select(Email)).scalars())
            HtmlExporter(output).export(emails)
        content = output.read_text()
        match = re.search(r'const DB_BASE64 = "([A-Za-z0-9+/=]+)"', content)
        assert match is not None
        b64 = match.group(1)
        decoded = base64.b64decode(b64)
        assert decoded[:16].startswith(b"SQLite format 3")

    def test_export_empty_emails(self, tmp_dir: Path) -> None:
        """Export works with an empty list of emails."""
        output = tmp_dir / "empty.html"
        exporter = HtmlExporter(output)
        result = exporter.export([])
        assert output.exists()
        assert result.emails_exported == 0
        assert result.format == "html"

    def test_export_preserves_tags_as_json(self, populated_db: Database, tmp_dir: Path) -> None:
        """Tags should be stored as JSON arrays in the export DB."""
        import json
        import sqlite3

        output = tmp_dir / "archive.html"
        with populated_db.session() as session:
            emails = list(session.execute(select(Email)).scalars())
            HtmlExporter(output).export(emails)
        content = output.read_text()

        # Extract base64, decode, and open the embedded DB
        match = re.search(r'const DB_BASE64 = "([A-Za-z0-9+/=]+)"', content)
        assert match is not None
        db_bytes = base64.b64decode(match.group(1))

        import os
        import tempfile

        with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as f:
            f.write(db_bytes)
            tmp_db = f.name

        try:
            conn = sqlite3.connect(tmp_db)
            cursor = conn.execute(
                "SELECT tags_json FROM emails WHERE tags_json IS NOT NULL"
            )
            rows = cursor.fetchall()
            conn.close()
            # At least one email should have tags
            assert len(rows) > 0
            for (tags_json,) in rows:
                tags = json.loads(tags_json)
                assert isinstance(tags, list)
        finally:
            os.unlink(tmp_db)

    def test_export_includes_fts5_index(self, populated_db: Database, tmp_dir: Path) -> None:
        """The export DB should contain an FTS5 index."""
        import os
        import sqlite3
        import tempfile

        output = tmp_dir / "archive.html"
        with populated_db.session() as session:
            emails = list(session.execute(select(Email)).scalars())
            HtmlExporter(output).export(emails)
        content = output.read_text()

        match = re.search(r'const DB_BASE64 = "([A-Za-z0-9+/=]+)"', content)
        assert match is not None
        db_bytes = base64.b64decode(match.group(1))

        with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as f:
            f.write(db_bytes)
            tmp_db = f.name

        try:
            conn = sqlite3.connect(tmp_db)
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='emails_fts'"
            )
            assert cursor.fetchone() is not None
            conn.close()
        finally:
            os.unlink(tmp_db)


class TestHtmlBuilder:
    def test_build_export_db_returns_bytes(self, populated_db: Database) -> None:
        from mail_memex.export.html_builder import build_export_db

        with populated_db.session() as session:
            emails = list(session.execute(select(Email)).scalars())
            db_bytes = build_export_db(emails)
        assert isinstance(db_bytes, bytes)
        assert db_bytes[:16].startswith(b"SQLite format 3")

    def test_build_export_db_has_correct_email_count(self, populated_db: Database) -> None:
        import os
        import sqlite3
        import tempfile

        from mail_memex.export.html_builder import build_export_db

        with populated_db.session() as session:
            emails = list(session.execute(select(Email)).scalars())
            db_bytes = build_export_db(emails)

        with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as f:
            f.write(db_bytes)
            tmp_db = f.name

        try:
            conn = sqlite3.connect(tmp_db)
            count = conn.execute("SELECT COUNT(*) FROM emails").fetchone()[0]
            conn.close()
            assert count == 5
        finally:
            os.unlink(tmp_db)

    def test_build_export_db_has_threads(self, populated_db: Database) -> None:
        import os
        import sqlite3
        import tempfile

        from mail_memex.export.html_builder import build_export_db

        with populated_db.session() as session:
            emails = list(session.execute(select(Email)).scalars())
            db_bytes = build_export_db(emails)

        with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as f:
            f.write(db_bytes)
            tmp_db = f.name

        try:
            conn = sqlite3.connect(tmp_db)
            count = conn.execute("SELECT COUNT(*) FROM threads").fetchone()[0]
            conn.close()
            assert count > 0
        finally:
            os.unlink(tmp_db)

    def test_build_export_db_empty(self) -> None:
        from mail_memex.export.html_builder import build_export_db

        db_bytes = build_export_db([])
        assert isinstance(db_bytes, bytes)
        assert db_bytes[:16].startswith(b"SQLite format 3")
