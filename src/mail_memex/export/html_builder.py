"""Build an in-memory SQLite database for HTML SPA export.

Creates a denormalized export schema with tags as JSON arrays (no join
tables). We deliberately *do not* ship FTS5 virtual tables: the vendored
sql.js build (``src/mail_memex/export/vendored/sql-wasm.{js,wasm}``) is
not compiled with ``SQLITE_ENABLE_FTS5``, so FTS5 queries would throw
in the browser. Client-side search uses a LIKE fallback instead, which
is adequate for a single-user email archive.

``PRAGMA journal_mode=DELETE`` is set before serialisation so no WAL
sidecar gets left behind if the process is interrupted mid-export.
"""

from __future__ import annotations

import json
import sqlite3
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mail_memex.core.models import Email


def build_export_db(emails: list[Email]) -> bytes:
    """Build an in-memory SQLite database and return its raw bytes.

    The export schema is denormalized for simplicity in the browser:
    - emails table with tags_json (JSON array) instead of a join table
    - threads table with pre-computed stats

    Args:
        emails: List of Email ORM objects to include.

    Returns:
        Raw SQLite database bytes. Size minimised by running VACUUM
        before serialisation.
    """
    conn = sqlite3.connect(":memory:")
    cursor = conn.cursor()
    # DELETE mode -> no -wal/-shm sidecars travel with the exported DB.
    cursor.execute("PRAGMA journal_mode=DELETE")

    # Create simplified, denormalized schema
    cursor.execute("""
        CREATE TABLE emails (
            id INTEGER PRIMARY KEY,
            message_id TEXT,
            from_addr TEXT,
            from_name TEXT,
            to_addrs TEXT,
            subject TEXT,
            date TEXT,
            body_text TEXT,
            body_preview TEXT,
            thread_id TEXT,
            tags_json TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE threads (
            thread_id TEXT PRIMARY KEY,
            subject TEXT,
            email_count INTEGER,
            first_date TEXT,
            last_date TEXT
        )
    """)

    threads_seen: dict[str, tuple[str, str | None, int, str | None, str | None]] = {}

    for email in emails:
        tags = [t.name for t in email.tags] if email.tags else []
        cursor.execute(
            "INSERT INTO emails VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                email.id,
                email.message_id,
                email.from_addr,
                email.from_name,
                email.to_addrs,
                email.subject,
                email.date.isoformat() if email.date else None,
                email.body_text,
                email.body_preview,
                email.thread_id,
                json.dumps(tags) if tags else None,
            ),
        )

        if email.thread_id and email.thread and email.thread_id not in threads_seen:
            t = email.thread
            threads_seen[email.thread_id] = (
                t.thread_id,
                t.subject,
                t.email_count,
                t.first_date.isoformat() if t.first_date else None,
                t.last_date.isoformat() if t.last_date else None,
            )

    for td in threads_seen.values():
        cursor.execute("INSERT INTO threads VALUES (?,?,?,?,?)", td)

    conn.commit()
    # VACUUM packs the file to a minimum on-disk size; over the wire
    # the gzip-step in html_export.py will compress the result further.
    conn.execute("VACUUM")

    # Serialize to bytes -- available in Python 3.11+
    db_bytes: bytes = conn.serialize()
    conn.close()
    return db_bytes
