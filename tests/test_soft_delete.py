"""TDD Tests for soft delete (archived_at) on Email and Thread models.

The memex ecosystem convention: every record table carries an
archived_at TIMESTAMP NULL column. Default queries should filter
WHERE archived_at IS NULL. This module verifies the column exists,
defaults to None, and can be set to a datetime.
"""

from datetime import UTC, datetime

from mail_memex.core.models import Email, Thread


class TestEmailSoftDelete:
    """Tests for Email.archived_at column."""

    def test_email_archived_at_default_none(self, session) -> None:
        """New email should have archived_at=None by default."""
        email = Email(
            message_id="soft-del-1@example.com",
            from_addr="sender@example.com",
            date=datetime(2024, 1, 15, 10, 0, 0),
        )
        session.add(email)
        session.commit()

        result = session.get(Email, email.id)
        assert result.archived_at is None

    def test_email_soft_delete(self, session) -> None:
        """Setting archived_at to a datetime should persist."""
        email = Email(
            message_id="soft-del-2@example.com",
            from_addr="sender@example.com",
            date=datetime(2024, 1, 15, 10, 0, 0),
        )
        session.add(email)
        session.commit()

        now = datetime.now(UTC)
        email.archived_at = now
        session.commit()

        result = session.get(Email, email.id)
        assert result.archived_at is not None


class TestThreadSoftDelete:
    """Tests for Thread.archived_at column."""

    def test_thread_archived_at_default_none(self, session) -> None:
        """New thread should have archived_at=None by default."""
        thread = Thread(thread_id="soft-del-thread-1")
        session.add(thread)
        session.commit()

        result = session.get(Thread, thread.id)
        assert result.archived_at is None


def test_search_excludes_archived_emails(session) -> None:
    """SearchEngine should not return archived emails."""
    from mail_memex.search.engine import SearchEngine

    active = Email(
        message_id="active@example.com",
        from_addr="a@b.com",
        subject="Active email about projects",
        body_text="This email is active and searchable.",
        date=datetime(2024, 1, 1),
    )
    archived = Email(
        message_id="archived@example.com",
        from_addr="a@b.com",
        subject="Archived email about projects",
        body_text="This email is archived and hidden.",
        date=datetime(2024, 1, 2),
        archived_at=datetime.now(UTC),
    )
    session.add_all([active, archived])
    session.commit()

    engine = SearchEngine(session)
    results = engine.search("projects")
    message_ids = [r.email.message_id for r in results]

    assert "active@example.com" in message_ids
    assert "archived@example.com" not in message_ids


def test_search_include_archived_returns_archived(session) -> None:
    """SearchEngine.search(include_archived=True) must return archived rows.
    Used by export commands with --include-archived to produce full mirrors."""
    from mail_memex.search.engine import SearchEngine

    active = Email(
        message_id="live@example.com",
        from_addr="a@b.com",
        subject="Live project update",
        body_text="live body",
        date=datetime(2024, 1, 1),
    )
    archived = Email(
        message_id="gone@example.com",
        from_addr="a@b.com",
        subject="Archived project update",
        body_text="archived body",
        date=datetime(2024, 1, 2),
        archived_at=datetime.now(UTC),
    )
    session.add_all([active, archived])
    session.commit()

    engine = SearchEngine(session)
    results = engine.search("project", include_archived=True)
    ids = {r.email.message_id for r in results}
    assert "live@example.com" in ids
    assert "gone@example.com" in ids


class TestExportSoftDelete:
    """Export must filter soft-deleted emails by default — the workspace
    convention is that archived records stay URI-resolvable but do not
    appear in default enumerations. Export is the most common way records
    leave the system; shipping archived data by default is the wrong
    default."""

    def test_bare_export_excludes_archived(self, session) -> None:
        from mail_memex.cli.main import _prepare_export

        session.add_all(
            [
                Email(
                    message_id="live-1@example.com",
                    from_addr="a@b.com",
                    subject="Live",
                    date=datetime(2024, 1, 1),
                ),
                Email(
                    message_id="gone-1@example.com",
                    from_addr="a@b.com",
                    subject="Gone",
                    date=datetime(2024, 1, 2),
                    archived_at=datetime.now(UTC),
                ),
            ]
        )
        session.commit()

        emails = _prepare_export(session, query=None)
        ids = {e.message_id for e in emails}
        assert "live-1@example.com" in ids
        assert "gone-1@example.com" not in ids

    def test_bare_export_include_archived_includes_both(self, session) -> None:
        from mail_memex.cli.main import _prepare_export

        session.add_all(
            [
                Email(
                    message_id="live-2@example.com",
                    from_addr="a@b.com",
                    subject="Live",
                    date=datetime(2024, 1, 1),
                ),
                Email(
                    message_id="gone-2@example.com",
                    from_addr="a@b.com",
                    subject="Gone",
                    date=datetime(2024, 1, 2),
                    archived_at=datetime.now(UTC),
                ),
            ]
        )
        session.commit()

        emails = _prepare_export(session, query=None, include_archived=True)
        ids = {e.message_id for e in emails}
        assert {"live-2@example.com", "gone-2@example.com"}.issubset(ids)

    def test_query_export_respects_include_archived(self, session) -> None:
        from mail_memex.cli.main import _prepare_export

        session.add_all(
            [
                Email(
                    message_id="live-3@example.com",
                    from_addr="alice@b.com",
                    subject="Alice live",
                    body_text="",
                    date=datetime(2024, 1, 1),
                ),
                Email(
                    message_id="gone-3@example.com",
                    from_addr="alice@b.com",
                    subject="Alice archived",
                    body_text="",
                    date=datetime(2024, 1, 2),
                    archived_at=datetime.now(UTC),
                ),
            ]
        )
        session.commit()

        # default: excludes archived
        default_ids = {
            e.message_id for e in _prepare_export(session, "from:alice")
        }
        assert default_ids == {"live-3@example.com"}

        # with flag: includes archived
        full_ids = {
            e.message_id
            for e in _prepare_export(session, "from:alice", include_archived=True)
        }
        assert full_ids == {"live-3@example.com", "gone-3@example.com"}
