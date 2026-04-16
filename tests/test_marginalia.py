"""TDD Tests for Marginalia and MarginaliaTarget ORM models.

Marginalia are free-form notes that can be attached to any record
via URIs. They support the memex ecosystem contract:
- UUID-based durable IDs
- Soft delete via archived_at
- Multi-target attachment via MarginaliaTarget join table
- Cascade delete from Marginalia to MarginaliaTarget
"""

from datetime import UTC, datetime

from sqlalchemy import select

from mail_memex.core.marginalia import (
    create_marginalia,
    delete_marginalia,
    get_marginalia,
    list_marginalia,
    restore_marginalia,
    update_marginalia,
)
from mail_memex.core.models import Marginalia, MarginaliaTarget


class TestMarginaliaModel:
    """Tests for the Marginalia ORM model."""

    def test_create_marginalia(self, session) -> None:
        """Create a marginalia with UUID, content, and verify defaults."""
        note = Marginalia(content="This thread is important for the Q1 review.")
        session.add(note)
        session.commit()

        result = session.get(Marginalia, note.id)
        assert result.content == "This thread is important for the Q1 review."
        assert result.uuid is not None
        assert len(result.uuid) == 32  # hex UUID without dashes
        assert result.pinned is False
        assert result.category is None
        assert result.color is None
        assert result.created_at is not None
        assert result.updated_at is not None
        assert result.archived_at is None

    def test_marginalia_with_targets(self, session) -> None:
        """Marginalia can be attached to multiple target URIs."""
        note = Marginalia(content="Cross-referencing these two emails.")
        note.targets = [
            MarginaliaTarget(target_uri="mail-memex://email/abc123@example.com"),
            MarginaliaTarget(target_uri="mail-memex://thread/thread-001"),
        ]
        session.add(note)
        session.commit()

        result = session.get(Marginalia, note.id)
        assert len(result.targets) == 2
        uris = {t.target_uri for t in result.targets}
        assert "mail-memex://email/abc123@example.com" in uris
        assert "mail-memex://thread/thread-001" in uris

    def test_marginalia_soft_delete(self, session) -> None:
        """Setting archived_at should persist (soft delete)."""
        note = Marginalia(content="Temporary note.")
        session.add(note)
        session.commit()

        now = datetime.now(UTC)
        note.archived_at = now
        session.commit()

        result = session.get(Marginalia, note.id)
        assert result.archived_at is not None

    def test_marginalia_cascade_delete_targets(self, session) -> None:
        """Deleting a marginalia should cascade-delete its targets."""
        note = Marginalia(content="Note with targets.")
        note.targets = [
            MarginaliaTarget(target_uri="mail-memex://email/del1@example.com"),
            MarginaliaTarget(target_uri="mail-memex://email/del2@example.com"),
        ]
        session.add(note)
        session.commit()

        note_id = note.id
        session.delete(note)
        session.commit()

        # Targets should be gone
        remaining = (
            session.execute(
                select(MarginaliaTarget).where(
                    MarginaliaTarget.marginalia_id == note_id
                )
            )
            .scalars()
            .all()
        )
        assert len(remaining) == 0

    def test_marginalia_category_and_color(self, session) -> None:
        """Optional category and color fields should persist."""
        note = Marginalia(
            content="Flagged for follow-up.",
            category="follow-up",
            color="#ff6600",
        )
        session.add(note)
        session.commit()

        result = session.get(Marginalia, note.id)
        assert result.category == "follow-up"
        assert result.color == "#ff6600"

    def test_marginalia_uuid_unique(self, session) -> None:
        """Each marginalia should get a unique UUID."""
        note1 = Marginalia(content="First note.")
        note2 = Marginalia(content="Second note.")
        session.add_all([note1, note2])
        session.commit()

        assert note1.uuid != note2.uuid


class TestMarginaliaTargetModel:
    """Tests for the MarginaliaTarget ORM model."""

    def test_target_back_populates_marginalia(self, session) -> None:
        """MarginaliaTarget.marginalia should back-populate to the parent."""
        note = Marginalia(content="Parent note.")
        target = MarginaliaTarget(target_uri="mail-memex://email/back-pop@example.com")
        note.targets.append(target)
        session.add(note)
        session.commit()

        result = (
            session.execute(
                select(MarginaliaTarget).where(
                    MarginaliaTarget.target_uri
                    == "mail-memex://email/back-pop@example.com"
                )
            )
            .scalars()
            .first()
        )
        assert result.marginalia is not None
        assert result.marginalia.content == "Parent note."


class TestMarginaliaCRUD:
    """Tests for the marginalia CRUD functions."""

    def test_create_marginalia_crud(self, session) -> None:
        """create_marginalia returns dict with uuid, content, target_uris."""
        result = create_marginalia(
            session,
            target_uris=["mail-memex://email/abc@example.com"],
            content="Important note",
        )
        assert isinstance(result, dict)
        assert "uuid" in result
        assert result["content"] == "Important note"
        assert result["target_uris"] == ["mail-memex://email/abc@example.com"]
        assert result["pinned"] is False
        assert result["category"] is None
        assert result["color"] is None
        assert result["archived_at"] is None
        assert "created_at" in result
        assert "updated_at" in result

    def test_create_marginalia_multi_target(self, session) -> None:
        """create_marginalia stores multiple target URIs."""
        result = create_marginalia(
            session,
            target_uris=[
                "mail-memex://email/a@example.com",
                "mail-memex://thread/t-001",
            ],
            content="Cross-reference note",
            category="ref",
            color="#ff0000",
            pinned=True,
        )
        assert set(result["target_uris"]) == {
            "mail-memex://email/a@example.com",
            "mail-memex://thread/t-001",
        }
        assert result["category"] == "ref"
        assert result["color"] == "#ff0000"
        assert result["pinned"] is True

    def test_list_marginalia_excludes_archived(self, session) -> None:
        """list_marginalia excludes archived records by default."""
        create_marginalia(session, target_uris=[], content="Active note")
        archived = create_marginalia(session, target_uris=[], content="Archived note")
        delete_marginalia(session, uuid=archived["uuid"])  # soft delete

        results = list_marginalia(session)
        contents = [r["content"] for r in results]
        assert "Active note" in contents
        assert "Archived note" not in contents

    def test_list_marginalia_include_archived(self, session) -> None:
        """list_marginalia with include_archived=True shows all records."""
        create_marginalia(session, target_uris=[], content="Active note")
        archived = create_marginalia(session, target_uris=[], content="Archived note")
        delete_marginalia(session, uuid=archived["uuid"])

        results = list_marginalia(session, include_archived=True)
        contents = [r["content"] for r in results]
        assert "Active note" in contents
        assert "Archived note" in contents

    def test_list_marginalia_filter_by_target(self, session) -> None:
        """list_marginalia filters by target_uri when provided."""
        create_marginalia(
            session,
            target_uris=["mail-memex://email/x@example.com"],
            content="Note for X",
        )
        create_marginalia(
            session,
            target_uris=["mail-memex://email/y@example.com"],
            content="Note for Y",
        )

        results = list_marginalia(session, target_uri="mail-memex://email/x@example.com")
        assert len(results) == 1
        assert results[0]["content"] == "Note for X"

    def test_list_marginalia_limit(self, session) -> None:
        """list_marginalia respects limit parameter."""
        for i in range(10):
            create_marginalia(session, target_uris=[], content=f"Note {i}")

        results = list_marginalia(session, limit=3)
        assert len(results) == 3

    def test_get_marginalia_by_uuid(self, session) -> None:
        """get_marginalia returns the specific record by UUID."""
        created = create_marginalia(session, target_uris=[], content="Find me")
        result = get_marginalia(session, uuid=created["uuid"])
        assert result is not None
        assert result["uuid"] == created["uuid"]
        assert result["content"] == "Find me"

    def test_get_marginalia_not_found(self, session) -> None:
        """get_marginalia returns None for a missing UUID."""
        result = get_marginalia(session, uuid="nonexistentuuid0000000000000000")
        assert result is None

    def test_update_marginalia_crud(self, session) -> None:
        """update_marginalia changes only specified fields."""
        created = create_marginalia(
            session,
            target_uris=[],
            content="Original content",
            category="work",
            color="#aabbcc",
            pinned=False,
        )
        updated = update_marginalia(session, uuid=created["uuid"], content="Updated content")
        assert updated is not None
        assert updated["content"] == "Updated content"
        # Other fields unchanged
        assert updated["category"] == "work"
        assert updated["color"] == "#aabbcc"
        assert updated["pinned"] is False

    def test_update_marginalia_multiple_fields(self, session) -> None:
        """update_marginalia can update several fields at once."""
        created = create_marginalia(
            session, target_uris=[], content="Old", pinned=False
        )
        updated = update_marginalia(
            session,
            uuid=created["uuid"],
            pinned=True,
            category="important",
            color="#ff0000",
        )
        assert updated["pinned"] is True
        assert updated["category"] == "important"
        assert updated["color"] == "#ff0000"
        assert updated["content"] == "Old"  # unchanged

    def test_update_marginalia_not_found(self, session) -> None:
        """update_marginalia returns None for a missing UUID."""
        result = update_marginalia(session, uuid="nonexistentuuid0000000000000000", content="x")
        assert result is None

    def test_delete_marginalia_soft(self, session) -> None:
        """delete_marginalia (soft=default) sets archived_at, record still in DB."""
        created = create_marginalia(session, target_uris=[], content="Soft delete me")
        deleted = delete_marginalia(session, uuid=created["uuid"])
        assert deleted is not None
        assert deleted["archived_at"] is not None

        # Record still exists in the database
        m = session.execute(
            select(Marginalia).where(Marginalia.uuid == created["uuid"])
        ).scalar_one_or_none()
        assert m is not None
        assert m.archived_at is not None

    def test_delete_marginalia_hard(self, session) -> None:
        """delete_marginalia with hard=True permanently removes the record."""
        created = create_marginalia(session, target_uris=[], content="Hard delete me")
        deleted = delete_marginalia(session, uuid=created["uuid"], hard=True)
        assert deleted is not None

        m = session.execute(
            select(Marginalia).where(Marginalia.uuid == created["uuid"])
        ).scalar_one_or_none()
        assert m is None

    def test_delete_marginalia_not_found(self, session) -> None:
        """delete_marginalia returns None for a missing UUID."""
        result = delete_marginalia(session, uuid="nonexistentuuid0000000000000000")
        assert result is None

    def test_restore_marginalia(self, session) -> None:
        """restore_marginalia clears archived_at."""
        created = create_marginalia(session, target_uris=[], content="Restore me")
        delete_marginalia(session, uuid=created["uuid"])  # soft delete first

        restored = restore_marginalia(session, uuid=created["uuid"])
        assert restored is not None
        assert restored["archived_at"] is None

        # Confirm it now appears in default list
        results = list_marginalia(session)
        uuids = [r["uuid"] for r in results]
        assert created["uuid"] in uuids

    def test_restore_marginalia_not_found(self, session) -> None:
        """restore_marginalia returns None for a missing UUID."""
        result = restore_marginalia(session, uuid="nonexistentuuid0000000000000000")
        assert result is None
