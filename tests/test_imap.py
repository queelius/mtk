"""Tests for IMAP sync module.

Tests cover:
- Tag mapping (IMAP flags ↔ mtk tags, Gmail labels ↔ mtk tags)
- Auth manager
- Sync state management
- Pull sync with mock IMAPClient
- Push sync with mock IMAPClient
- Queue-based push
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

import pytest
from sqlalchemy import select

from mtk.core.database import Database
from mtk.core.models import Email, ImapPendingPush, ImapSyncState, Tag
from mtk.imap.account import ImapAccountConfig
from mtk.imap.gmail import GmailExtensions
from mtk.imap.mapping import TagMapper
from mtk.imap.push import PushSync, queue_tag_change

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def imap_account() -> ImapAccountConfig:
    """Test IMAP account config."""
    return ImapAccountConfig(
        name="test",
        host="imap.example.com",
        port=993,
        username="user@example.com",
        use_ssl=True,
        provider="generic",
        folders=["INBOX", "Sent"],
    )


@pytest.fixture
def gmail_account() -> ImapAccountConfig:
    """Test Gmail account config."""
    return ImapAccountConfig(
        name="gmail",
        host="imap.gmail.com",
        port=993,
        username="user@gmail.com",
        use_ssl=True,
        provider="gmail",
        folders=["INBOX"],
        oauth2=True,
    )


@pytest.fixture
def imap_db() -> Database:
    """Database with IMAP models."""
    database = Database(":memory:")
    database.create_tables()
    return database


@pytest.fixture
def imap_populated_db(imap_db: Database) -> Database:
    """Database with IMAP-tracked emails."""
    with imap_db.session() as session:
        # Create emails with IMAP tracking
        email1 = Email(
            message_id="imap1@example.com",
            from_addr="sender@example.com",
            from_name="Sender",
            subject="IMAP Email 1",
            body_text="Body of IMAP email 1",
            date=datetime(2024, 1, 15, 10, 0),
            imap_uid=100,
            imap_account="test",
            imap_folder="INBOX",
        )
        email2 = Email(
            message_id="imap2@example.com",
            from_addr="sender2@example.com",
            subject="IMAP Email 2",
            body_text="Body of IMAP email 2",
            date=datetime(2024, 1, 15, 11, 0),
            imap_uid=101,
            imap_account="test",
            imap_folder="INBOX",
        )
        email3 = Email(
            message_id="local@example.com",
            from_addr="local@example.com",
            subject="Local Email (not IMAP)",
            body_text="This email is not from IMAP",
            date=datetime(2024, 1, 15, 12, 0),
        )
        session.add_all([email1, email2, email3])

        # Create sync state
        state = ImapSyncState(
            account_name="test",
            folder="INBOX",
            uid_validity=12345,
            last_uid=101,
            last_sync=datetime(2024, 1, 15, 12, 0),
        )
        session.add(state)

        # Create some tags
        read_tag = Tag(name="read", source="imap")
        flagged_tag = Tag(name="flagged", source="imap")
        session.add_all([read_tag, flagged_tag])
        session.flush()

        email1.tags.append(read_tag)
        email1.tags.append(flagged_tag)

        session.commit()

    return imap_db


# =============================================================================
# Tag Mapping Tests
# =============================================================================


class TestTagMapper:
    """Tests for IMAP ↔ mtk tag mapping."""

    def test_imap_flags_to_tags(self) -> None:
        """Standard IMAP flags should map to mtk tags."""
        mapper = TagMapper()
        tags = mapper.imap_to_tags(["\\Seen", "\\Flagged"])
        assert "read" in tags
        assert "flagged" in tags

    def test_unknown_flag_ignored(self) -> None:
        """Unknown flags should be ignored."""
        mapper = TagMapper()
        tags = mapper.imap_to_tags(["\\Seen", "\\CustomFlag"])
        assert "read" in tags
        assert len(tags) == 1

    def test_tags_to_imap_flags(self) -> None:
        """mtk tags should map back to IMAP flags."""
        mapper = TagMapper()
        flags = mapper.tags_to_imap_flags({"read", "flagged"})
        assert "\\Seen" in flags
        assert "\\Flagged" in flags

    def test_gmail_labels_to_tags(self) -> None:
        """Gmail labels should map to mtk tags."""
        mapper = TagMapper(is_gmail=True)
        tags = mapper.imap_to_tags(["\\Seen"], ["\\Inbox", "\\Starred", "CATEGORY_SOCIAL"])
        assert "read" in tags
        assert "inbox" in tags
        assert "starred" in tags
        assert "social" in tags

    def test_gmail_custom_labels_passthrough(self) -> None:
        """Unknown Gmail labels should pass through as lowercase."""
        mapper = TagMapper(is_gmail=True)
        tags = mapper.imap_to_tags([], ["MyCustomLabel"])
        assert "mycustomlabel" in tags

    def test_tags_to_gmail_labels(self) -> None:
        """mtk tags should map back to Gmail labels."""
        mapper = TagMapper(is_gmail=True)
        labels = mapper.tags_to_gmail_labels({"inbox", "starred", "important"})
        assert "\\Inbox" in labels
        assert "\\Starred" in labels
        assert "\\Important" in labels

    def test_diff_tags(self) -> None:
        """diff_tags should compute additions and removals."""
        mapper = TagMapper()
        add, remove = mapper.diff_tags(
            current_tags={"read", "flagged"},
            new_tags={"read", "replied"},
        )
        assert "replied" in add
        assert "flagged" in remove
        assert "read" not in add
        assert "read" not in remove

    def test_bytes_flags(self) -> None:
        """Should handle bytes flags (as returned by imapclient)."""
        mapper = TagMapper()
        tags = mapper.imap_to_tags([b"\\Seen", b"\\Flagged"])
        assert "read" in tags
        assert "flagged" in tags

    def test_custom_mappings(self) -> None:
        """Custom mappings should work alongside standard ones."""
        mapper = TagMapper(custom_mappings={"$Junk": "spam"})
        tags = mapper.imap_to_tags(["\\Seen", "$Junk"])
        assert "read" in tags
        assert "spam" in tags


# =============================================================================
# Gmail Extensions Tests
# =============================================================================


class TestGmailExtensions:
    """Tests for Gmail-specific IMAP extensions."""

    def test_extract_labels(self) -> None:
        labels = GmailExtensions.extract_labels(
            {
                b"X-GM-LABELS": (b"\\Inbox", b"\\Important", b"MyLabel"),
            }
        )
        assert labels == ["\\Inbox", "\\Important", "MyLabel"]

    def test_extract_labels_empty(self) -> None:
        labels = GmailExtensions.extract_labels({})
        assert labels == []

    def test_extract_thread_id(self) -> None:
        thrid = GmailExtensions.extract_thread_id({b"X-GM-THRID": 123456789})
        assert thrid == "123456789"

    def test_extract_thread_id_missing(self) -> None:
        thrid = GmailExtensions.extract_thread_id({})
        assert thrid is None

    def test_build_fetch_items(self) -> None:
        items = GmailExtensions.build_fetch_items(gmail_extensions=True)
        assert "X-GM-LABELS" in items
        assert "X-GM-THRID" in items

    def test_build_fetch_items_no_gmail(self) -> None:
        items = GmailExtensions.build_fetch_items(gmail_extensions=False)
        assert "X-GM-LABELS" not in items


# =============================================================================
# Account Tests
# =============================================================================


class TestImapAccountConfig:
    """Tests for IMAP account config."""

    def test_is_gmail(self, gmail_account: ImapAccountConfig) -> None:
        assert gmail_account.is_gmail is True

    def test_not_gmail(self, imap_account: ImapAccountConfig) -> None:
        assert imap_account.is_gmail is False

    def test_keyring_service(self, imap_account: ImapAccountConfig) -> None:
        assert imap_account.keyring_service == "mtk-imap-test"


# =============================================================================
# Sync State Tests
# =============================================================================


class TestSyncState:
    """Tests for IMAP sync state management."""

    def test_sync_state_created(self, imap_populated_db: Database) -> None:
        """Sync state should be created correctly."""
        with imap_populated_db.session() as session:
            state = session.execute(
                select(ImapSyncState).where(
                    ImapSyncState.account_name == "test",
                    ImapSyncState.folder == "INBOX",
                )
            ).scalar()
            assert state is not None
            assert state.uid_validity == 12345
            assert state.last_uid == 101

    def test_imap_tracked_email(self, imap_populated_db: Database) -> None:
        """Emails should have IMAP tracking fields."""
        with imap_populated_db.session() as session:
            email = session.execute(
                select(Email).where(Email.message_id == "imap1@example.com")
            ).scalar()
            assert email is not None
            assert email.imap_uid == 100
            assert email.imap_account == "test"
            assert email.imap_folder == "INBOX"

    def test_non_imap_email(self, imap_populated_db: Database) -> None:
        """Non-IMAP emails should have null tracking fields."""
        with imap_populated_db.session() as session:
            email = session.execute(
                select(Email).where(Email.message_id == "local@example.com")
            ).scalar()
            assert email is not None
            assert email.imap_uid is None
            assert email.imap_account is None


# =============================================================================
# Push Queue Tests
# =============================================================================


class TestPushQueue:
    """Tests for the tag change push queue."""

    def test_queue_tag_change(self, imap_populated_db: Database) -> None:
        """queue_tag_change should create a pending push entry."""
        with imap_populated_db.session() as session:
            email = session.execute(
                select(Email).where(Email.message_id == "imap1@example.com")
            ).scalar()

            queue_tag_change(session, email.id, "test", "add", "important")
            session.commit()

            pending = (
                session.execute(select(ImapPendingPush).where(ImapPendingPush.email_id == email.id))
                .scalars()
                .all()
            )
            assert len(pending) == 1
            assert pending[0].action == "add"
            assert pending[0].tag_name == "important"

    def test_queue_multiple_changes(self, imap_populated_db: Database) -> None:
        """Multiple tag changes should create multiple entries."""
        with imap_populated_db.session() as session:
            email = session.execute(
                select(Email).where(Email.message_id == "imap1@example.com")
            ).scalar()

            queue_tag_change(session, email.id, "test", "add", "urgent")
            queue_tag_change(session, email.id, "test", "remove", "read")
            session.commit()

            pending = (
                session.execute(select(ImapPendingPush).where(ImapPendingPush.email_id == email.id))
                .scalars()
                .all()
            )
            assert len(pending) == 2


# =============================================================================
# Push Sync Tests (with mock)
# =============================================================================


class TestPushSync:
    """Tests for push sync with mock IMAPClient."""

    def test_push_empty_queue(
        self, imap_populated_db: Database, imap_account: ImapAccountConfig
    ) -> None:
        """Push with empty queue should do nothing."""
        with imap_populated_db.session() as session:
            mapper = TagMapper()
            push = PushSync(session, imap_account, mapper)
            mock_client = MagicMock()

            result = push.push(mock_client)
            assert result.processed == 0
            assert result.succeeded == 0

    def test_push_add_flags(
        self, imap_populated_db: Database, imap_account: ImapAccountConfig
    ) -> None:
        """Push should add IMAP flags for tag additions."""
        with imap_populated_db.session() as session:
            email = session.execute(
                select(Email).where(Email.message_id == "imap1@example.com")
            ).scalar()

            queue_tag_change(session, email.id, "test", "add", "replied")
            session.flush()

            mapper = TagMapper()
            push = PushSync(session, imap_account, mapper)
            mock_client = MagicMock()

            result = push.push(mock_client)
            assert result.succeeded >= 1
            mock_client.select_folder.assert_called()
            mock_client.add_flags.assert_called()

    def test_push_remove_flags(
        self, imap_populated_db: Database, imap_account: ImapAccountConfig
    ) -> None:
        """Push should remove IMAP flags for tag removals."""
        with imap_populated_db.session() as session:
            email = session.execute(
                select(Email).where(Email.message_id == "imap1@example.com")
            ).scalar()

            queue_tag_change(session, email.id, "test", "remove", "read")
            session.flush()

            mapper = TagMapper()
            push = PushSync(session, imap_account, mapper)
            mock_client = MagicMock()

            result = push.push(mock_client)
            assert result.succeeded >= 1
            mock_client.remove_flags.assert_called()

    def test_push_clears_queue(
        self, imap_populated_db: Database, imap_account: ImapAccountConfig
    ) -> None:
        """Push should clear processed items from queue."""
        with imap_populated_db.session() as session:
            email = session.execute(
                select(Email).where(Email.message_id == "imap1@example.com")
            ).scalar()

            queue_tag_change(session, email.id, "test", "add", "flagged")
            session.flush()

            mapper = TagMapper()
            push = PushSync(session, imap_account, mapper)
            mock_client = MagicMock()

            push.push(mock_client)

            # Queue should be empty
            remaining = (
                session.execute(
                    select(ImapPendingPush).where(ImapPendingPush.account_name == "test")
                )
                .scalars()
                .all()
            )
            assert len(remaining) == 0

    def test_push_non_imap_email_skipped(
        self, imap_populated_db: Database, imap_account: ImapAccountConfig
    ) -> None:
        """Push for non-IMAP emails should skip gracefully."""
        with imap_populated_db.session() as session:
            email = session.execute(
                select(Email).where(Email.message_id == "local@example.com")
            ).scalar()

            queue_tag_change(session, email.id, "test", "add", "important")
            session.flush()

            mapper = TagMapper()
            push = PushSync(session, imap_account, mapper)
            mock_client = MagicMock()

            result = push.push(mock_client)
            # Should have errors but not crash
            assert result.failed >= 1


# =============================================================================
# CLI Command Tests
# =============================================================================


class TestImapCLI:
    """Tests for IMAP CLI commands."""

    def test_imap_help(self) -> None:
        """imap subcommand should have help."""
        from typer.testing import CliRunner

        from mtk.cli.main import app

        runner = CliRunner()
        result = runner.invoke(app, ["imap", "--help"])
        assert result.exit_code == 0
        assert "imap" in result.output.lower()

    def test_imap_accounts_help(self) -> None:
        """imap accounts should have help."""
        from typer.testing import CliRunner

        from mtk.cli.main import app

        runner = CliRunner()
        result = runner.invoke(app, ["imap", "accounts", "--help"])
        assert result.exit_code == 0
