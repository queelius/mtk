"""Tests for HTML SFA export."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from mail_memex.core.database import Database
from mail_memex.core.models import Email, Tag, Thread
from mail_memex.export.html_export import HtmlExporter


@pytest.fixture
def file_db(tmp_path: Path) -> Database:
    """Create a populated database as a file on disk."""
    db_path = tmp_path / "test.db"
    db = Database(db_path)
    db.create_tables()

    with db.session() as session:
        # Create thread
        thread1 = Thread(
            thread_id="thread-001",
            subject="Project Discussion",
            email_count=3,
            first_date=datetime(2024, 1, 15, 10, 0),
            last_date=datetime(2024, 1, 15, 12, 0),
        )
        session.add(thread1)
        session.flush()

        # Create emails
        emails_data = [
            {
                "message_id": "email1@example.com",
                "thread_id": "thread-001",
                "from_addr": "alice@example.com",
                "from_name": "Alice Smith",
                "subject": "Project Discussion",
                "date": datetime(2024, 1, 15, 10, 0, 0),
                "body_text": "Let's discuss the new project.",
                "body_preview": "Let's discuss the new project.",
            },
            {
                "message_id": "email2@example.com",
                "thread_id": "thread-001",
                "from_addr": "bob@example.com",
                "from_name": "Bob Jones",
                "subject": "Re: Project Discussion",
                "date": datetime(2024, 1, 15, 11, 0, 0),
                "body_text": "Sounds good, let's do it.",
                "body_preview": "Sounds good, let's do it.",
                "in_reply_to": "email1@example.com",
            },
            {
                "message_id": "email3@example.com",
                "thread_id": "thread-001",
                "from_addr": "alice@example.com",
                "from_name": "Alice Smith",
                "subject": "Re: Project Discussion",
                "date": datetime(2024, 1, 15, 12, 0, 0),
                "body_text": "Great, meeting tomorrow.",
                "body_preview": "Great, meeting tomorrow.",
                "in_reply_to": "email2@example.com",
            },
            {
                "message_id": "email4@example.com",
                "from_addr": "alice@example.com",
                "from_name": "Alice Smith",
                "subject": "Weekend Plans",
                "date": datetime(2024, 1, 16, 9, 0, 0),
                "body_text": "Anyone free this weekend?",
                "body_preview": "Anyone free this weekend?",
            },
            {
                "message_id": "email5@example.com",
                "from_addr": "bob@example.com",
                "from_name": "Bob Jones",
                "subject": "URGENT: Server down",
                "date": datetime(2024, 1, 17, 8, 0, 0),
                "body_text": "The server is down!",
                "body_preview": "The server is down!",
            },
        ]
        for data in emails_data:
            session.add(Email(**data))
        session.flush()

        # Create tags and associate
        work_tag = Tag(name="work", source="mtk")
        urgent_tag = Tag(name="urgent", source="mtk")
        session.add_all([work_tag, urgent_tag])
        session.flush()

        email1 = session.query(Email).filter_by(message_id="email1@example.com").first()
        email5 = session.query(Email).filter_by(message_id="email5@example.com").first()
        email1.tags.append(work_tag)
        email5.tags.append(urgent_tag)

        session.commit()

    return db


class TestHtmlExporter:
    def test_export_creates_file(self, file_db: Database, tmp_path: Path) -> None:
        output = tmp_path / "archive.html"
        exporter = HtmlExporter(output, file_db.db_path)
        result = exporter.export_from_db()
        assert output.exists()
        assert result.emails_exported > 0

    def test_output_is_valid_html(self, file_db: Database, tmp_path: Path) -> None:
        output = tmp_path / "archive.html"
        exporter = HtmlExporter(output, file_db.db_path)
        exporter.export_from_db()
        content = output.read_text()
        assert content.startswith("<!DOCTYPE html>")
        assert "</html>" in content

    def test_contains_sql_js_cdn(self, file_db: Database, tmp_path: Path) -> None:
        output = tmp_path / "archive.html"
        exporter = HtmlExporter(output, file_db.db_path)
        exporter.export_from_db()
        content = output.read_text()
        assert "sql-wasm.js" in content
        # The WASM binary is resolved at runtime via locateFile
        assert "cdnjs.cloudflare.com/ajax/libs/sql.js/1.11.0/" in content

    def test_contains_embedded_database(self, file_db: Database, tmp_path: Path) -> None:
        output = tmp_path / "archive.html"
        exporter = HtmlExporter(output, file_db.db_path)
        exporter.export_from_db()
        content = output.read_text()
        # The database should be base64-encoded in a JS variable
        assert "const DB_BASE64" in content

    def test_export_result_format(self, file_db: Database, tmp_path: Path) -> None:
        output = tmp_path / "archive.html"
        exporter = HtmlExporter(output, file_db.db_path)
        result = exporter.export_from_db()
        assert result.format == "html"
        assert result.output_path == str(output)

    def test_export_result_count(self, file_db: Database, tmp_path: Path) -> None:
        output = tmp_path / "archive.html"
        exporter = HtmlExporter(output, file_db.db_path)
        result = exporter.export_from_db()
        assert result.emails_exported == 5

    def test_export_result_to_dict(self, file_db: Database, tmp_path: Path) -> None:
        output = tmp_path / "archive.html"
        exporter = HtmlExporter(output, file_db.db_path)
        result = exporter.export_from_db()
        d = result.to_dict()
        assert d["format"] == "html"
        assert d["emails_exported"] == 5
        assert d["output_path"] == str(output)

    def test_contains_ui_elements(self, file_db: Database, tmp_path: Path) -> None:
        """Verify the HTML contains key UI elements."""
        output = tmp_path / "archive.html"
        exporter = HtmlExporter(output, file_db.db_path)
        exporter.export_from_db()
        content = output.read_text()
        # Search box
        assert 'id="search-box"' in content
        # Stats bar
        assert 'id="stats"' in content
        # List and detail panes
        assert 'id="list-pane"' in content
        assert 'id="detail-pane"' in content

    def test_creates_parent_directories(self, file_db: Database, tmp_path: Path) -> None:
        output = tmp_path / "sub" / "dir" / "archive.html"
        exporter = HtmlExporter(output, file_db.db_path)
        result = exporter.export_from_db()
        assert output.exists()
        assert result.emails_exported == 5

    def test_embedded_db_is_valid_base64(self, file_db: Database, tmp_path: Path) -> None:
        """Verify the embedded database is valid base64 that decodes to SQLite bytes."""
        import base64
        import re

        output = tmp_path / "archive.html"
        exporter = HtmlExporter(output, file_db.db_path)
        exporter.export_from_db()
        content = output.read_text()

        # Extract the base64 blob
        match = re.search(r'const DB_BASE64 = "([A-Za-z0-9+/=]+)"', content)
        assert match is not None
        b64 = match.group(1)

        # Decode and verify it starts with SQLite magic bytes
        decoded = base64.b64decode(b64)
        assert decoded[:16].startswith(b"SQLite format 3")

    def test_export_empty_database(self, tmp_path: Path) -> None:
        """Export works with a database that has no emails."""
        db_path = tmp_path / "empty.db"
        db = Database(db_path)
        db.create_tables()

        output = tmp_path / "empty.html"
        exporter = HtmlExporter(output, db_path)
        result = exporter.export_from_db()
        assert output.exists()
        assert result.emails_exported == 0
        assert result.format == "html"
        db.close()
