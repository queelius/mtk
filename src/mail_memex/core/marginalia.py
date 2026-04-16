"""CRUD operations for Marginalia records.

All functions return plain dicts (not ORM objects) for safe MCP serialization
across session boundaries.

Dict schema:
    uuid          str       hex UUID without dashes
    content       str       note body
    category      str|None  optional label
    color         str|None  optional CSS color hint
    pinned        bool
    created_at    str       ISO-8601 UTC timestamp
    updated_at    str       ISO-8601 UTC timestamp
    archived_at   str|None  ISO-8601 UTC timestamp, or None
    target_uris   list[str] URIs this note is attached to
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from mail_memex.core.models import Marginalia, MarginaliaTarget

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _iso(dt: datetime | None) -> str | None:
    """Render a datetime as ISO-8601 UTC string, or None."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.isoformat()


def _to_dict(m: Marginalia) -> dict[str, Any]:
    """Convert a Marginalia ORM instance to a plain dict."""
    return {
        "uuid": m.uuid,
        "content": m.content,
        "category": m.category,
        "color": m.color,
        "pinned": m.pinned,
        "created_at": _iso(m.created_at),
        "updated_at": _iso(m.updated_at),
        "archived_at": _iso(m.archived_at),
        "target_uris": [t.target_uri for t in m.targets],
    }


def _get_by_uuid(session: Session, uuid: str) -> Marginalia | None:
    """Fetch a Marginalia row by UUID, or None."""
    return session.execute(
        select(Marginalia).where(Marginalia.uuid == uuid)
    ).scalar_one_or_none()


# ---------------------------------------------------------------------------
# Public CRUD functions
# ---------------------------------------------------------------------------


def create_marginalia(
    session: Session,
    target_uris: list[str],
    content: str,
    category: str | None = None,
    color: str | None = None,
    pinned: bool = False,
) -> dict[str, Any]:
    """Create a new marginalia note and attach it to the given target URIs.

    Args:
        session: Active SQLAlchemy session.
        target_uris: Zero or more ``<archive>://<kind>/<id>`` URIs.
        content: Note body text.
        category: Optional free-form label (e.g. ``"follow-up"``).
        color: Optional CSS color hint (e.g. ``"#ff6600"``).
        pinned: Whether the note should be pinned; defaults to False.

    Returns:
        Plain dict representation of the created record.
    """
    m = Marginalia(
        content=content,
        category=category,
        color=color,
        pinned=pinned,
        targets=[MarginaliaTarget(target_uri=uri) for uri in target_uris],
    )
    session.add(m)
    session.flush()
    return _to_dict(m)


def list_marginalia(
    session: Session,
    target_uri: str | None = None,
    include_archived: bool = False,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Return marginalia records, newest first.

    Args:
        session: Active SQLAlchemy session.
        target_uri: If given, only return notes attached to this URI.
        include_archived: When False (default) skip soft-deleted records.
        limit: Maximum number of results to return.

    Returns:
        List of plain dicts.
    """
    stmt = select(Marginalia).order_by(Marginalia.created_at.desc()).limit(limit)
    if not include_archived:
        stmt = stmt.where(Marginalia.archived_at.is_(None))
    if target_uri is not None:
        stmt = stmt.join(Marginalia.targets).where(
            MarginaliaTarget.target_uri == target_uri
        )
    rows = session.execute(stmt).scalars().all()
    return [_to_dict(m) for m in rows]


def get_marginalia(session: Session, uuid: str) -> dict[str, Any] | None:
    """Fetch a single marginalia by its UUID.

    Args:
        session: Active SQLAlchemy session.
        uuid: 32-character hex UUID.

    Returns:
        Plain dict, or None if no record matches.
    """
    m = _get_by_uuid(session, uuid)
    return _to_dict(m) if m is not None else None


def update_marginalia(
    session: Session,
    uuid: str,
    content: str | None = None,
    category: str | None = None,
    color: str | None = None,
    pinned: bool | None = None,
) -> dict[str, Any] | None:
    """Update specified fields on an existing marginalia note.

    Only fields explicitly passed (i.e. not ``None`` for ``content``,
    ``category``, ``color``; not ``None`` for ``pinned``) are changed.

    Args:
        session: Active SQLAlchemy session.
        uuid: Record UUID.
        content: New note body, or None to leave unchanged.
        category: New category, or None to leave unchanged.
        color: New color, or None to leave unchanged.
        pinned: New pinned flag, or None to leave unchanged.

    Returns:
        Updated plain dict, or None if not found.
    """
    m = _get_by_uuid(session, uuid)
    if m is None:
        return None
    if content is not None:
        m.content = content
    if category is not None:
        m.category = category
    if color is not None:
        m.color = color
    if pinned is not None:
        m.pinned = pinned
    m.updated_at = datetime.now(UTC)
    session.flush()
    return _to_dict(m)


def delete_marginalia(
    session: Session,
    uuid: str,
    hard: bool = False,
) -> dict[str, Any] | None:
    """Delete a marginalia note.

    By default performs a soft delete (sets ``archived_at``).  Pass
    ``hard=True`` to permanently remove the row and its targets.

    Args:
        session: Active SQLAlchemy session.
        uuid: Record UUID.
        hard: When True, issue a hard (permanent) DELETE.

    Returns:
        Plain dict snapshot of the record before deletion, or None if not found.
    """
    m = _get_by_uuid(session, uuid)
    if m is None:
        return None
    snapshot = _to_dict(m)
    if hard:
        session.delete(m)
    else:
        m.archived_at = datetime.now(UTC)
        snapshot["archived_at"] = _iso(m.archived_at)
    session.flush()
    return snapshot


def restore_marginalia(session: Session, uuid: str) -> dict[str, Any] | None:
    """Undo a soft delete by clearing ``archived_at``.

    Args:
        session: Active SQLAlchemy session.
        uuid: Record UUID.

    Returns:
        Updated plain dict, or None if not found.
    """
    m = _get_by_uuid(session, uuid)
    if m is None:
        return None
    m.archived_at = None
    m.updated_at = datetime.now(UTC)
    session.flush()
    return _to_dict(m)
