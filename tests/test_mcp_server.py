"""Tests for MCP server tool handlers.

Tests the tool handler functions directly (without MCP transport),
using the populated_db fixture for realistic data.
"""

from __future__ import annotations

import json

import pytest

from mtk.core.database import Database
from mtk.mcp.tools import (
    TOOL_HANDLERS,
    get_correspondence_timeline,
    get_inbox,
    get_reply_context,
    get_stats,
    list_people,
    list_tags,
    search_emails,
    show_email,
    show_person,
    show_thread,
    tag_batch,
    tag_email,
)
from mtk.mcp.validation import (
    optional_bool,
    optional_int,
    optional_list,
    optional_str,
    require_str,
)


def _parse_result(result: list[dict]) -> dict | list | str:
    """Parse the text content from a tool result."""
    assert len(result) >= 1
    text = result[0]["text"]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


# =============================================================================
# Validation tests
# =============================================================================


class TestValidation:
    """Tests for input validation helpers."""

    def test_require_str_present(self) -> None:
        assert require_str({"key": "value"}, "key") == "value"

    def test_require_str_missing(self) -> None:
        with pytest.raises(ValueError, match="Missing required"):
            require_str({}, "key")

    def test_require_str_empty(self) -> None:
        with pytest.raises(ValueError, match="Missing required"):
            require_str({"key": ""}, "key")

    def test_optional_str(self) -> None:
        assert optional_str({"key": "val"}, "key") == "val"
        assert optional_str({}, "key") is None
        assert optional_str({}, "key", "default") == "default"

    def test_optional_int(self) -> None:
        assert optional_int({"key": 42}, "key") == 42
        assert optional_int({}, "key", 10) == 10

    def test_optional_bool(self) -> None:
        assert optional_bool({"key": True}, "key") is True
        assert optional_bool({}, "key") is False

    def test_optional_list(self) -> None:
        assert optional_list({"key": ["a", "b"]}, "key") == ["a", "b"]
        assert optional_list({}, "key") == []
        assert optional_list({"key": "single"}, "key") == ["single"]


# =============================================================================
# Tool handler tests
# =============================================================================


class TestSearchEmails:
    """Tests for search_emails tool."""

    def test_basic_search(self, populated_db: Database) -> None:
        with populated_db.session() as session:
            result = search_emails(session, {"query": "project"})
            data = _parse_result(result)
            assert isinstance(data, list)
            assert len(data) >= 1
            assert "message_id" in data[0]

    def test_search_with_limit(self, populated_db: Database) -> None:
        with populated_db.session() as session:
            result = search_emails(session, {"query": "project", "limit": 1})
            data = _parse_result(result)
            assert len(data) <= 1

    def test_search_no_results(self, populated_db: Database) -> None:
        with populated_db.session() as session:
            result = search_emails(session, {"query": "xyznonexistent"})
            data = _parse_result(result)
            assert isinstance(data, list)
            assert len(data) == 0

    def test_search_requires_query(self, populated_db: Database) -> None:
        with populated_db.session() as session, pytest.raises(ValueError):
            search_emails(session, {})


class TestGetInbox:
    """Tests for get_inbox tool."""

    def test_inbox_returns_emails(self, populated_db: Database) -> None:
        with populated_db.session() as session:
            result = get_inbox(session, {})
            data = _parse_result(result)
            assert isinstance(data, list)
            assert len(data) >= 1

    def test_inbox_with_limit(self, populated_db: Database) -> None:
        with populated_db.session() as session:
            result = get_inbox(session, {"limit": 2})
            data = _parse_result(result)
            assert len(data) <= 2

    def test_inbox_with_since(self, populated_db: Database) -> None:
        with populated_db.session() as session:
            result = get_inbox(session, {"since": "2024-01-17"})
            data = _parse_result(result)
            # Should only include emails on or after Jan 17
            assert isinstance(data, list)


class TestGetStats:
    """Tests for get_stats tool."""

    def test_stats_returns_counts(self, populated_db: Database) -> None:
        with populated_db.session() as session:
            result = get_stats(session, {})
            data = _parse_result(result)
            assert data["emails"] == 5
            assert data["people"] == 3
            assert data["threads"] == 2
            assert data["tags"] == 4


class TestShowEmail:
    """Tests for show_email tool."""

    def test_show_by_exact_id(self, populated_db: Database) -> None:
        with populated_db.session() as session:
            result = show_email(session, {"message_id": "email1@example.com"})
            data = _parse_result(result)
            assert data["message_id"] == "email1@example.com"
            assert data["subject"] == "Project Discussion"
            assert "body_text" in data

    def test_show_by_partial_id(self, populated_db: Database) -> None:
        with populated_db.session() as session:
            result = show_email(session, {"message_id": "email1@"})
            data = _parse_result(result)
            assert data["message_id"] == "email1@example.com"

    def test_show_not_found(self, populated_db: Database) -> None:
        with populated_db.session() as session:
            result = show_email(session, {"message_id": "nonexistent@nowhere.com"})
            text = result[0]["text"]
            assert "not found" in text.lower()


class TestShowThread:
    """Tests for show_thread tool."""

    def test_show_by_thread_id(self, populated_db: Database) -> None:
        with populated_db.session() as session:
            result = show_thread(session, {"thread_id": "thread-001"})
            data = _parse_result(result)
            assert data["thread_id"] == "thread-001"
            assert data["message_count"] == 3
            assert len(data["messages"]) == 3

    def test_show_thread_not_found(self, populated_db: Database) -> None:
        with populated_db.session() as session:
            result = show_thread(session, {"thread_id": "nonexistent"})
            text = result[0]["text"]
            assert "not found" in text.lower()


class TestGetReplyContext:
    """Tests for get_reply_context tool."""

    def test_reply_context(self, populated_db: Database) -> None:
        with populated_db.session() as session:
            result = get_reply_context(session, {"message_id": "email2@example.com"})
            data = _parse_result(result)
            assert "replying_to" in data
            assert "suggested_headers" in data
            assert data["suggested_headers"]["to"] == "bob@example.com"

    def test_reply_context_adds_re(self, populated_db: Database) -> None:
        with populated_db.session() as session:
            result = get_reply_context(session, {"message_id": "email1@example.com"})
            data = _parse_result(result)
            assert data["suggested_headers"]["subject"].startswith("Re:")


class TestTagEmail:
    """Tests for tag_email tool."""

    def test_add_tag(self, populated_db: Database) -> None:
        with populated_db.session() as session:
            result = tag_email(
                session,
                {"message_id": "email3@example.com", "add": ["followup"]},
            )
            data = _parse_result(result)
            assert "followup" in data["tags"]

    def test_remove_tag(self, populated_db: Database) -> None:
        with populated_db.session() as session:
            result = tag_email(
                session,
                {"message_id": "email1@example.com", "remove": ["important"]},
            )
            data = _parse_result(result)
            assert "important" not in data["tags"]

    def test_tag_not_found(self, populated_db: Database) -> None:
        with populated_db.session() as session:
            result = tag_email(
                session,
                {"message_id": "nonexistent@nowhere.com", "add": ["test"]},
            )
            text = result[0]["text"]
            assert "not found" in text.lower()


class TestTagBatch:
    """Tests for tag_batch tool."""

    def test_batch_tag(self, populated_db: Database) -> None:
        with populated_db.session() as session:
            result = tag_batch(
                session,
                {"query": "from:alice", "add": ["alice-mail"]},
            )
            data = _parse_result(result)
            assert data["matched"] >= 1
            assert data["modified"] >= 1


class TestListTags:
    """Tests for list_tags tool."""

    def test_list_tags(self, populated_db: Database) -> None:
        with populated_db.session() as session:
            result = list_tags(session, {})
            data = _parse_result(result)
            assert isinstance(data, list)
            assert len(data) >= 1
            assert "name" in data[0]
            assert "count" in data[0]


class TestListPeople:
    """Tests for list_people tool."""

    def test_list_people(self, populated_db: Database) -> None:
        with populated_db.session() as session:
            result = list_people(session, {})
            data = _parse_result(result)
            assert isinstance(data, list)
            assert len(data) >= 1
            assert "name" in data[0]


class TestShowPerson:
    """Tests for show_person tool."""

    def test_show_person(self, populated_db: Database) -> None:
        with populated_db.session() as session:
            # First get a person ID
            people = list_people(session, {"limit": 1})
            people_data = _parse_result(people)
            person_id = people_data[0]["id"]

            result = show_person(session, {"person_id": person_id})
            data = _parse_result(result)
            assert "name" in data
            assert "email" in data
            assert "email_count" in data

    def test_show_person_not_found(self, populated_db: Database) -> None:
        with populated_db.session() as session:
            result = show_person(session, {"person_id": 99999})
            text = result[0]["text"]
            assert "not found" in text.lower()


class TestGetCorrespondenceTimeline:
    """Tests for get_correspondence_timeline tool."""

    def test_timeline(self, populated_db: Database) -> None:
        with populated_db.session() as session:
            people = list_people(session, {"limit": 1})
            people_data = _parse_result(people)
            person_id = people_data[0]["id"]

            result = get_correspondence_timeline(
                session, {"person_id": person_id, "granularity": "month"}
            )
            data = _parse_result(result)
            assert isinstance(data, dict)


# =============================================================================
# Dispatch registry tests
# =============================================================================


class TestToolRegistry:
    """Tests for tool dispatch registry."""

    def test_all_tools_registered(self) -> None:
        """All 13 tool handlers should be in the registry."""
        assert len(TOOL_HANDLERS) == 13

    def test_all_handlers_callable(self) -> None:
        """All handlers should be callable."""
        for name, handler in TOOL_HANDLERS.items():
            assert callable(handler), f"{name} is not callable"

    def test_handler_names_match(self) -> None:
        """Handler names should match expected tool names."""
        expected = {
            "search_emails",
            "get_inbox",
            "get_stats",
            "show_email",
            "show_thread",
            "get_reply_context",
            "tag_email",
            "tag_batch",
            "list_tags",
            "list_people",
            "show_person",
            "get_correspondence_timeline",
            "notmuch_sync",
        }
        assert set(TOOL_HANDLERS.keys()) == expected
