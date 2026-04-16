# mtk to mail-memex Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rename mtk to mail-memex with full ecosystem contract compliance: FastMCP, soft delete, marginalia, and static HTML SPA.

**Architecture:** Package rename from `mtk` (import: `mtk`) to `mail-memex` (import: `mail_memex`). MCP server upgraded from `mcp.server.Server` to `FastMCP`. Schema extended with `archived_at` soft delete on emails/threads, new marginalia tables. HTML SPA export rewritten with builder+template pattern for a self-contained single-file archive viewer.

**Tech Stack:** Python 3.11+, SQLAlchemy 2.0, FastMCP, Typer, Rich, sql.js (WASM), pytest

**Spec:** `docs/superpowers/specs/2026-04-15-mtk-to-mail-memex-design.md`

---

## File Map

### Renamed (src/mtk/ -> src/mail_memex/)

Every `.py` file under `src/mtk/` moves to `src/mail_memex/` with identical internal structure. All `from mtk.` imports become `from mail_memex.`. These files are listed explicitly only when they also get content changes beyond the rename.

### Modified (beyond import rename)

| File | Changes |
|------|---------|
| `pyproject.toml` | Package name, scripts, wheel target, version |
| `src/mail_memex/__init__.py` | Version bump, updated docstring |
| `src/mail_memex/core/models.py` | `archived_at` on Email/Thread, new Marginalia + MarginaliaTarget models |
| `src/mail_memex/core/config.py` | New default paths (`mail-memex`), new env var name |
| `src/mail_memex/core/database.py` | Updated error message, import paths |
| `src/mail_memex/mcp/server.py` | Full rewrite: FastMCP, execute_sql, get_record, search_emails, marginalia tools |
| `src/mail_memex/mcp/__init__.py` | Updated for FastMCP run pattern |
| `src/mail_memex/mcp/__main__.py` | Updated import path |
| `src/mail_memex/search/engine.py` | Filter `archived_at IS NULL` in all queries |
| `src/mail_memex/search/fts.py` | No content changes (filtering at query layer) |
| `src/mail_memex/export/arkiv_export.py` | URI scheme `mail-memex://email/...` |
| `src/mail_memex/export/html_export.py` | Rewrite: builder+template pattern, export-schema DB |
| `src/mail_memex/cli/main.py` | Updated import paths, config paths in error messages |
| `src/mail_memex/cli/imap_cli.py` | Updated import paths |
| `tests/conftest.py` | Updated imports, fixture dir names, add marginalia fixtures |
| All `tests/test_*.py` | Updated imports |

### New Files

| File | Purpose |
|------|---------|
| `src/mail_memex/core/marginalia.py` | Marginalia CRUD operations (UUID gen, soft delete, multi-URI targets) |
| `src/mail_memex/export/html_builder.py` | Builds in-memory SQLite export DB with denormalized schema |
| `src/mail_memex/export/html_template.py` | HTML+CSS+JS template string for single-file SPA |
| `scripts/migrate-from-mtk.py` | Standalone migration script (not installed) |
| `tests/test_marginalia.py` | Marginalia model and CRUD tests |
| `tests/test_soft_delete.py` | archived_at filtering tests across search, MCP, export |

---

## Task 1: Package Rename (Mechanical)

Move `src/mtk/` to `src/mail_memex/`, update all imports, update pyproject.toml. No behavioral changes yet.

**Files:**
- Move: `src/mtk/` -> `src/mail_memex/` (entire tree)
- Modify: `pyproject.toml`
- Modify: every `.py` file under `src/mail_memex/` and `tests/`

- [ ] **Step 1: Rename the package directory**

```bash
mv src/mtk src/mail_memex
```

- [ ] **Step 2: Update pyproject.toml**

Replace the full content of `pyproject.toml` with the renamed version. Key changes:

```toml
[project]
name = "mail-memex"
version = "0.5.0"
description = "Mail Memex - Personal email archive with full-text search and SQL/MCP access"
authors = [
    { name = "Alex Towell", email = "lex@metafunctor.com" }
]
keywords = ["email", "mail", "archive", "search", "imap", "memex"]

[project.scripts]
mail-memex = "mail_memex.cli.main:app"

[tool.hatch.build.targets.wheel]
packages = ["src/mail_memex"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
addopts = "-v --tb=short"

[tool.coverage.run]
source = ["src/mail_memex"]
branch = true
```

Leave all other sections (build-system, optional-dependencies, tool.mypy, tool.ruff) unchanged except updating `source` paths.

- [ ] **Step 3: Replace all `from mtk.` and `import mtk.` across the codebase**

Use sed to do the mechanical replacement in all Python files:

```bash
# In src/mail_memex/
find src/mail_memex -name '*.py' -exec sed -i 's/from mtk\./from mail_memex./g' {} +
find src/mail_memex -name '*.py' -exec sed -i 's/import mtk\./import mail_memex./g' {} +
find src/mail_memex -name '*.py' -exec sed -i 's/"mtk"/"mail_memex"/g' {} +

# In tests/
find tests -name '*.py' -exec sed -i 's/from mtk\./from mail_memex./g' {} +
find tests -name '*.py' -exec sed -i 's/import mtk\./import mail_memex./g' {} +
find tests -name '*.py' -exec sed -i 's/"mtk\./"mail_memex./g' {} +
```

- [ ] **Step 4: Update `src/mail_memex/__init__.py`**

```python
"""mail-memex - Personal email archive.

A toolkit for managing personal email archives with full-text search
and SQL/MCP access. Part of the *-memex personal archive ecosystem.
"""

__version__ = "0.5.0"
```

- [ ] **Step 5: Update config default paths in `src/mail_memex/core/config.py`**

Change the class methods:

```python
@classmethod
def default_config_dir(cls) -> Path:
    """Get the default config directory (~/.config/mail-memex)."""
    return Path.home() / ".config" / "mail-memex"

@classmethod
def default_data_dir(cls) -> Path:
    """Get the default data directory (~/.local/share/mail-memex)."""
    return Path.home() / ".local" / "share" / "mail-memex"
```

- [ ] **Step 6: Update database default path in `src/mail_memex/core/database.py`**

Change the error message in `get_db()`:

```python
def get_db() -> Database:
    """Get the global database instance."""
    if _db is None:
        raise RuntimeError("Database not initialized. Run 'mail-memex init' first.")
    return _db
```

- [ ] **Step 7: Update env var in `src/mail_memex/mcp/server.py`**

In the `_get_db_path()` function, change:

```python
env_path = os.environ.get("MAIL_MEMEX_DATABASE_PATH")
```

And change the default db filename:

```python
return MtkConfig.default_data_dir() / "mail-memex.db"
```

- [ ] **Step 8: Update CLI default db path in `src/mail_memex/cli/main.py`**

In `get_db()`:

```python
config.db_path = config.default_data_dir() / "mail-memex.db"
```

And in the `init` command:

```python
config.db_path = config.default_data_dir() / "mail-memex.db"
```

- [ ] **Step 9: Update test fixture paths in `tests/conftest.py`**

Change fixture dir names from `mtk` to `mail-memex`:

```python
@pytest.fixture
def config_dir(tmp_dir: Path) -> Path:
    """Create a mock config directory."""
    config = tmp_dir / ".config" / "mail-memex"
    config.mkdir(parents=True)
    return config

@pytest.fixture
def data_dir(tmp_dir: Path) -> Path:
    """Create a mock data directory."""
    data = tmp_dir / ".local" / "share" / "mail-memex"
    data.mkdir(parents=True)
    return data
```

Update `mock_config` fixture similarly.

- [ ] **Step 10: Reinstall and run tests**

```bash
pip install -e ".[dev]"
pytest
```

Expected: All existing tests pass with new import paths.

- [ ] **Step 11: Commit**

```bash
git add -A
git commit -m "feat: rename mtk to mail-memex

Package rename: mtk -> mail-memex (import: mail_memex).
CLI entrypoint: mail-memex. Config: ~/.config/mail-memex/.
Data: ~/.local/share/mail-memex/mail-memex.db.
Env var: MAIL_MEMEX_DATABASE_PATH.
Version bump to 0.5.0."
```

---

## Task 2: Schema Changes (archived_at + marginalia models)

Add `archived_at` to Email and Thread. Add Marginalia and MarginaliaTarget models.

**Files:**
- Modify: `src/mail_memex/core/models.py`
- Create: `tests/test_soft_delete.py`
- Create: `tests/test_marginalia.py` (model tests only, CRUD in Task 4)

- [ ] **Step 1: Write test for archived_at column on Email**

Create `tests/test_soft_delete.py`:

```python
"""Tests for archived_at soft delete on emails and threads."""

from datetime import UTC, datetime

from mail_memex.core.models import Email, Thread


def test_email_archived_at_default_none(session):
    """New emails have archived_at=None by default."""
    email = Email(
        message_id="soft1@example.com",
        from_addr="a@b.com",
        date=datetime(2024, 1, 1),
    )
    session.add(email)
    session.flush()
    assert email.archived_at is None


def test_email_soft_delete(session):
    """Setting archived_at marks an email as soft-deleted."""
    email = Email(
        message_id="soft2@example.com",
        from_addr="a@b.com",
        date=datetime(2024, 1, 1),
    )
    session.add(email)
    session.flush()

    email.archived_at = datetime.now(UTC)
    session.flush()

    assert email.archived_at is not None


def test_thread_archived_at_default_none(session):
    """New threads have archived_at=None by default."""
    thread = Thread(
        thread_id="thread-soft1",
        subject="Test",
    )
    session.add(thread)
    session.flush()
    assert thread.archived_at is None
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_soft_delete.py -v
```

Expected: FAIL with `TypeError` because `archived_at` is not a column on Email/Thread.

- [ ] **Step 3: Add archived_at to Email and Thread in models.py**

In `src/mail_memex/core/models.py`, add to the `Email` class after `updated_at`:

```python
# Soft delete
archived_at: Mapped[datetime | None] = mapped_column(default=None)
```

Add the same to the `Thread` class after `updated_at`:

```python
# Soft delete
archived_at: Mapped[datetime | None] = mapped_column(default=None)
```

- [ ] **Step 4: Run soft delete tests**

```bash
pytest tests/test_soft_delete.py -v
```

Expected: PASS (3 tests).

- [ ] **Step 5: Write tests for Marginalia and MarginaliaTarget models**

Add to `tests/test_marginalia.py`:

```python
"""Tests for Marginalia model and relationships."""

from datetime import UTC, datetime

from mail_memex.core.models import Marginalia, MarginaliaTarget


def test_create_marginalia(session):
    """Create a marginalia record with a generated UUID."""
    m = Marginalia(
        content="This email has the contract terms.",
    )
    session.add(m)
    session.flush()

    assert m.id is not None
    assert m.uuid is not None
    assert len(m.uuid) == 32  # hex UUID without hyphens
    assert m.content == "This email has the contract terms."
    assert m.archived_at is None
    assert m.pinned is False


def test_marginalia_with_targets(session):
    """Marginalia can reference multiple target URIs."""
    m = Marginalia(content="Cross-reference note")
    session.add(m)
    session.flush()

    t1 = MarginaliaTarget(
        marginalia_id=m.id,
        target_uri="mail-memex://email/abc@example.com",
    )
    t2 = MarginaliaTarget(
        marginalia_id=m.id,
        target_uri="mail-memex://thread/thread-abc",
    )
    session.add_all([t1, t2])
    session.flush()

    assert len(m.targets) == 2
    uris = {t.target_uri for t in m.targets}
    assert "mail-memex://email/abc@example.com" in uris
    assert "mail-memex://thread/thread-abc" in uris


def test_marginalia_soft_delete(session):
    """Marginalia supports soft delete via archived_at."""
    m = Marginalia(content="To be archived")
    session.add(m)
    session.flush()

    m.archived_at = datetime.now(UTC)
    session.flush()

    assert m.archived_at is not None


def test_marginalia_cascade_delete_targets(session):
    """Deleting marginalia cascades to its targets."""
    m = Marginalia(content="Will be deleted")
    session.add(m)
    session.flush()

    t = MarginaliaTarget(
        marginalia_id=m.id,
        target_uri="mail-memex://email/xyz@example.com",
    )
    session.add(t)
    session.flush()

    session.delete(m)
    session.flush()

    remaining = session.query(MarginaliaTarget).all()
    assert len(remaining) == 0


def test_marginalia_category_and_color(session):
    """Marginalia supports optional category and color."""
    m = Marginalia(
        content="Important note",
        category="follow-up",
        color="#ff6b6b",
        pinned=True,
    )
    session.add(m)
    session.flush()

    assert m.category == "follow-up"
    assert m.color == "#ff6b6b"
    assert m.pinned is True
```

- [ ] **Step 6: Run test to verify it fails**

```bash
pytest tests/test_marginalia.py -v
```

Expected: FAIL with `ImportError` because Marginalia and MarginaliaTarget don't exist.

- [ ] **Step 7: Add Marginalia and MarginaliaTarget models to models.py**

Add `import uuid as _uuid` at the top of `src/mail_memex/core/models.py` (after existing imports).

Add after the `ImapSyncState` class:

```python
class Marginalia(Base):
    """Free-form notes attached to email/thread records via URIs."""

    __tablename__ = "marginalia"

    id: Mapped[int] = mapped_column(primary_key=True)
    uuid: Mapped[str] = mapped_column(
        String(32), unique=True, index=True,
        default=lambda: _uuid.uuid4().hex,
    )
    content: Mapped[str] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(String(100))
    color: Mapped[str | None] = mapped_column(String(20))
    pinned: Mapped[bool] = mapped_column(default=False)

    # Metadata
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC)
    )
    archived_at: Mapped[datetime | None] = mapped_column(default=None)

    # Relationships
    targets: Mapped[list[MarginaliaTarget]] = relationship(
        back_populates="marginalia", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Marginalia {self.uuid[:8]}... '{self.content[:30]}'>"


class MarginaliaTarget(Base):
    """Join table linking marginalia to target URIs."""

    __tablename__ = "marginalia_targets"

    marginalia_id: Mapped[int] = mapped_column(
        ForeignKey("marginalia.id", ondelete="CASCADE"), primary_key=True,
    )
    target_uri: Mapped[str] = mapped_column(Text, primary_key=True)

    # Relationships
    marginalia: Mapped[Marginalia] = relationship(back_populates="targets")

    def __repr__(self) -> str:
        return f"<MarginaliaTarget {self.target_uri}>"
```

Note: `MarginaliaTarget` must be defined before `Marginalia` in the file (or use string annotations in the relationship), since `Marginalia.targets` references `MarginaliaTarget`. Alternatively, define `MarginaliaTarget` first without the relationship back-reference, then `Marginalia`, then add the back-reference. The simplest approach: define `MarginaliaTarget` first (without `relationship`), then `Marginalia` with the `targets` relationship, then add `marginalia` relationship to `MarginaliaTarget`. Or use the SQLAlchemy string-based forward reference pattern which is already in use in the codebase (see `Thread` and `Email`).

- [ ] **Step 8: Run all model tests**

```bash
pytest tests/test_marginalia.py tests/test_soft_delete.py tests/test_database.py -v
```

Expected: All pass.

- [ ] **Step 9: Run full test suite to verify no regressions**

```bash
pytest
```

Expected: All pass.

- [ ] **Step 10: Commit**

```bash
git add -A
git commit -m "feat: add archived_at soft delete and marginalia models

Email and Thread gain archived_at column for soft delete.
New Marginalia model with UUID, content, category, color, pinned.
MarginaliaTarget join table for multi-URI attachment.
Marginalia URI: mail-memex://marginalia/{uuid}."
```

---

## Task 3: Search and Export Filter archived_at

Make SearchEngine, CLI, and exporters respect `archived_at IS NULL`.

**Files:**
- Modify: `src/mail_memex/search/engine.py`
- Modify: `src/mail_memex/cli/main.py` (the `_prepare_export` function)
- Modify: `tests/test_soft_delete.py` (add integration tests)

- [ ] **Step 1: Write test for search excluding archived emails**

Add to `tests/test_soft_delete.py`:

```python
from mail_memex.search.engine import SearchEngine


def test_search_excludes_archived_emails(session):
    """SearchEngine should not return archived emails."""
    from mail_memex.core.models import Email

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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_soft_delete.py::test_search_excludes_archived_emails -v
```

Expected: FAIL (archived email is currently returned).

- [ ] **Step 3: Add archived_at filter to SearchEngine**

In `src/mail_memex/search/engine.py`, modify `_like_search` to add the filter. After `conditions = []` add:

```python
# Always exclude archived emails
conditions.append(Email.archived_at.is_(None))
```

In `_fts5_search`, after `conditions = [Email.id.in_(fts_email_ids)]` add:

```python
conditions.append(Email.archived_at.is_(None))
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_soft_delete.py -v
```

Expected: All pass.

- [ ] **Step 5: Run full test suite**

```bash
pytest
```

Expected: All pass.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat: search engine filters out archived emails

Both FTS5 and LIKE search paths now exclude emails
where archived_at IS NOT NULL."
```

---

## Task 4: Marginalia CRUD Module

Create the CRUD operations module used by MCP tools.

**Files:**
- Create: `src/mail_memex/core/marginalia.py`
- Modify: `tests/test_marginalia.py` (add CRUD tests)

- [ ] **Step 1: Write tests for marginalia CRUD**

Add to `tests/test_marginalia.py`:

```python
from mail_memex.core.marginalia import (
    create_marginalia,
    list_marginalia,
    get_marginalia,
    update_marginalia,
    delete_marginalia,
    restore_marginalia,
)


def test_create_marginalia_crud(session):
    """create_marginalia returns a dict with uuid and targets."""
    result = create_marginalia(
        session,
        target_uris=["mail-memex://email/test@example.com"],
        content="Important note",
        category="review",
    )
    assert "uuid" in result
    assert result["content"] == "Important note"
    assert result["category"] == "review"
    assert len(result["target_uris"]) == 1


def test_list_marginalia_excludes_archived(session):
    """list_marginalia excludes soft-deleted records by default."""
    create_marginalia(session, ["mail-memex://email/a@b.com"], "Active note")
    result2 = create_marginalia(session, ["mail-memex://email/c@d.com"], "Archived note")
    delete_marginalia(session, result2["uuid"])
    session.commit()

    results = list_marginalia(session)
    assert len(results) == 1
    assert results[0]["content"] == "Active note"


def test_list_marginalia_include_archived(session):
    """list_marginalia can include archived records."""
    create_marginalia(session, ["mail-memex://email/a@b.com"], "Active note")
    result2 = create_marginalia(session, ["mail-memex://email/c@d.com"], "Archived note")
    delete_marginalia(session, result2["uuid"])
    session.commit()

    results = list_marginalia(session, include_archived=True)
    assert len(results) == 2


def test_list_marginalia_filter_by_target(session):
    """list_marginalia can filter by target URI."""
    create_marginalia(session, ["mail-memex://email/target1@b.com"], "Note A")
    create_marginalia(session, ["mail-memex://email/target2@b.com"], "Note B")
    session.commit()

    results = list_marginalia(session, target_uri="mail-memex://email/target1@b.com")
    assert len(results) == 1
    assert results[0]["content"] == "Note A"


def test_get_marginalia_by_uuid(session):
    """get_marginalia returns a specific record."""
    result = create_marginalia(session, ["mail-memex://email/x@b.com"], "Find me")
    session.commit()

    found = get_marginalia(session, result["uuid"])
    assert found is not None
    assert found["content"] == "Find me"


def test_get_marginalia_not_found(session):
    """get_marginalia returns None for missing UUID."""
    found = get_marginalia(session, "nonexistent-uuid")
    assert found is None


def test_update_marginalia_crud(session):
    """update_marginalia changes specified fields only."""
    result = create_marginalia(session, ["mail-memex://email/x@b.com"], "Original")
    session.commit()

    updated = update_marginalia(session, result["uuid"], content="Updated", pinned=True)
    assert updated["content"] == "Updated"
    assert updated["pinned"] is True


def test_delete_marginalia_soft(session):
    """delete_marginalia soft-deletes by default."""
    result = create_marginalia(session, ["mail-memex://email/x@b.com"], "Soft delete me")
    session.commit()

    delete_marginalia(session, result["uuid"])
    session.commit()

    found = get_marginalia(session, result["uuid"])
    assert found is not None
    assert found["archived_at"] is not None


def test_delete_marginalia_hard(session):
    """delete_marginalia with hard=True permanently removes."""
    result = create_marginalia(session, ["mail-memex://email/x@b.com"], "Hard delete me")
    session.commit()

    delete_marginalia(session, result["uuid"], hard=True)
    session.commit()

    found = get_marginalia(session, result["uuid"])
    assert found is None


def test_restore_marginalia(session):
    """restore_marginalia clears archived_at."""
    result = create_marginalia(session, ["mail-memex://email/x@b.com"], "Restore me")
    delete_marginalia(session, result["uuid"])
    session.commit()

    restored = restore_marginalia(session, result["uuid"])
    assert restored["archived_at"] is None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_marginalia.py::test_create_marginalia_crud -v
```

Expected: FAIL with `ImportError` (module doesn't exist).

- [ ] **Step 3: Create marginalia CRUD module**

Create `src/mail_memex/core/marginalia.py`:

```python
"""Marginalia CRUD operations.

Functions return plain dicts (not ORM objects) for direct use
by MCP tools and JSON serialization.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from mail_memex.core.models import Marginalia, MarginaliaTarget


def _to_dict(m: Marginalia) -> dict[str, Any]:
    """Convert Marginalia ORM object to a plain dict."""
    return {
        "uuid": m.uuid,
        "content": m.content,
        "category": m.category,
        "color": m.color,
        "pinned": m.pinned,
        "created_at": m.created_at.isoformat() if m.created_at else None,
        "updated_at": m.updated_at.isoformat() if m.updated_at else None,
        "archived_at": m.archived_at.isoformat() if m.archived_at else None,
        "target_uris": [t.target_uri for t in m.targets],
    }


def create_marginalia(
    session: Session,
    target_uris: list[str],
    content: str,
    category: str | None = None,
    color: str | None = None,
    pinned: bool = False,
) -> dict[str, Any]:
    """Create a marginalia record with target URIs."""
    m = Marginalia(
        content=content,
        category=category,
        color=color,
        pinned=pinned,
    )
    session.add(m)
    session.flush()

    for uri in target_uris:
        t = MarginaliaTarget(marginalia_id=m.id, target_uri=uri)
        session.add(t)
    session.flush()

    return _to_dict(m)


def list_marginalia(
    session: Session,
    target_uri: str | None = None,
    include_archived: bool = False,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """List marginalia, optionally filtered by target URI."""
    stmt = select(Marginalia)

    if not include_archived:
        stmt = stmt.where(Marginalia.archived_at.is_(None))

    if target_uri:
        stmt = stmt.join(MarginaliaTarget).where(
            MarginaliaTarget.target_uri == target_uri
        )

    stmt = stmt.order_by(Marginalia.created_at.desc()).limit(limit)
    results = session.execute(stmt).scalars().all()
    return [_to_dict(m) for m in results]


def get_marginalia(session: Session, uuid: str) -> dict[str, Any] | None:
    """Get a single marginalia record by UUID."""
    m = session.execute(
        select(Marginalia).where(Marginalia.uuid == uuid)
    ).scalar()
    if m is None:
        return None
    return _to_dict(m)


def update_marginalia(
    session: Session,
    uuid: str,
    content: str | None = None,
    category: str | None = None,
    color: str | None = None,
    pinned: bool | None = None,
) -> dict[str, Any] | None:
    """Update specified fields on a marginalia record."""
    m = session.execute(
        select(Marginalia).where(Marginalia.uuid == uuid)
    ).scalar()
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

    session.flush()
    return _to_dict(m)


def delete_marginalia(
    session: Session,
    uuid: str,
    hard: bool = False,
) -> dict[str, Any] | None:
    """Delete a marginalia record. Soft delete by default."""
    m = session.execute(
        select(Marginalia).where(Marginalia.uuid == uuid)
    ).scalar()
    if m is None:
        return None

    if hard:
        session.delete(m)
        session.flush()
        return {"uuid": uuid, "deleted": True}

    m.archived_at = datetime.now(UTC)
    session.flush()
    return _to_dict(m)


def restore_marginalia(session: Session, uuid: str) -> dict[str, Any] | None:
    """Restore a soft-deleted marginalia record."""
    m = session.execute(
        select(Marginalia).where(Marginalia.uuid == uuid)
    ).scalar()
    if m is None:
        return None

    m.archived_at = None
    session.flush()
    return _to_dict(m)
```

- [ ] **Step 4: Run marginalia tests**

```bash
pytest tests/test_marginalia.py -v
```

Expected: All pass.

- [ ] **Step 5: Run full test suite**

```bash
pytest
```

Expected: All pass.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat: add marginalia CRUD module

Create, list, get, update, soft/hard delete, restore operations.
Functions return plain dicts for MCP serialization.
Multi-URI target support via MarginaliaTarget join table."
```

---

## Task 5: MCP Server Rewrite (FastMCP + Contract Tools)

Rewrite MCP server from `mcp.server.Server` to `FastMCP`. Add `execute_sql`, `get_record`, `search_emails`, and marginalia tools.

**Files:**
- Modify: `src/mail_memex/mcp/server.py` (full rewrite)
- Modify: `src/mail_memex/mcp/__init__.py` (update for FastMCP)
- Modify: `src/mail_memex/mcp/__main__.py` (update import)
- Modify: `tests/test_mcp_server.py` (rewrite for new tools)

- [ ] **Step 1: Write tests for new MCP tools**

Rewrite `tests/test_mcp_server.py`:

```python
"""Tests for mail-memex MCP server tools."""

import json
from datetime import datetime

import pytest

from mail_memex.core.database import Database
from mail_memex.core.models import Email, Tag, Thread, email_tags


@pytest.fixture
def mcp_db(db: Database) -> Database:
    """Database with sample data for MCP tests."""
    with db.session() as session:
        email = Email(
            message_id="mcp-test@example.com",
            from_addr="alice@example.com",
            from_name="Alice",
            subject="MCP Test Email",
            body_text="This is a test for the MCP server.",
            date=datetime(2024, 6, 15, 10, 0),
            to_addrs="bob@example.com",
        )
        thread = Thread(
            thread_id="thread-mcp-test",
            subject="MCP Thread",
            email_count=1,
            first_date=datetime(2024, 6, 15),
            last_date=datetime(2024, 6, 15),
        )
        session.add_all([email, thread])
        session.flush()
        email.thread_id = "thread-mcp-test"
        session.commit()
    return db


class TestExecuteSQL:
    """Tests for the execute_sql tool."""

    def test_select_query(self, mcp_db):
        from mail_memex.mcp.server import execute_sql_impl
        with mcp_db.session() as session:
            result = json.loads(execute_sql_impl(session, "SELECT COUNT(*) as cnt FROM emails"))
        assert result[0]["cnt"] == 1

    def test_ddl_blocked(self, mcp_db):
        from mail_memex.mcp.server import execute_sql_impl
        with mcp_db.session() as session:
            result = json.loads(execute_sql_impl(session, "DROP TABLE emails"))
        assert "error" in result

    def test_write_blocked_readonly(self, mcp_db):
        from mail_memex.mcp.server import execute_sql_impl
        with mcp_db.session() as session:
            result = json.loads(execute_sql_impl(
                session, "DELETE FROM emails WHERE 1=1", readonly=True
            ))
        assert "error" in result

    def test_write_allowed_non_readonly(self, mcp_db):
        from mail_memex.mcp.server import execute_sql_impl
        with mcp_db.session() as session:
            result = json.loads(execute_sql_impl(
                session,
                "UPDATE emails SET subject='changed' WHERE message_id='mcp-test@example.com'",
                readonly=False,
            ))
        assert "affected_rows" in result


class TestGetSchema:
    """Tests for the get_schema tool."""

    def test_returns_tables(self, mcp_db):
        from mail_memex.mcp.server import get_schema_impl
        with mcp_db.session() as session:
            result = json.loads(get_schema_impl(session))
        assert "tables" in result
        assert "emails" in result["tables"]
        assert "marginalia" in result["tables"]
        assert "tips" in result


class TestGetRecord:
    """Tests for the get_record tool."""

    def test_get_email_by_message_id(self, mcp_db):
        from mail_memex.mcp.server import get_record_impl
        with mcp_db.session() as session:
            result = json.loads(get_record_impl(session, "email", "mcp-test@example.com"))
        assert result["message_id"] == "mcp-test@example.com"
        assert result["from_addr"] == "alice@example.com"

    def test_get_thread_by_id(self, mcp_db):
        from mail_memex.mcp.server import get_record_impl
        with mcp_db.session() as session:
            result = json.loads(get_record_impl(session, "thread", "thread-mcp-test"))
        assert result["thread_id"] == "thread-mcp-test"

    def test_get_record_not_found(self, mcp_db):
        from mail_memex.mcp.server import get_record_impl
        with mcp_db.session() as session:
            result = json.loads(get_record_impl(session, "email", "nonexistent@example.com"))
        assert result["error"] == "NOT_FOUND"

    def test_get_record_invalid_kind(self, mcp_db):
        from mail_memex.mcp.server import get_record_impl
        with mcp_db.session() as session:
            result = json.loads(get_record_impl(session, "bookmark", "abc"))
        assert "error" in result


class TestSearchEmails:
    """Tests for the search_emails tool."""

    def test_search_by_text(self, mcp_db):
        from mail_memex.mcp.server import search_emails_impl
        with mcp_db.session() as session:
            result = json.loads(search_emails_impl(session, "MCP Test"))
        assert len(result) >= 1
        assert result[0]["message_id"] == "mcp-test@example.com"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_mcp_server.py -v
```

Expected: FAIL (old server API, missing impl functions).

- [ ] **Step 3: Rewrite MCP server module**

Replace `src/mail_memex/mcp/server.py` with the full FastMCP implementation from the spec. The complete code is in the spec document at `docs/superpowers/specs/2026-04-15-mtk-to-mail-memex-design.md`, section 2. Key components:

- `TABLE_DESCRIPTIONS` dict updated with marginalia tables and archived_at docs
- `QUERY_TIPS` list updated with marginalia and soft-delete examples
- `get_schema_impl(session)` - unchanged logic, updated descriptions
- `execute_sql_impl(session, sql, readonly)` - renamed from `run_sql`
- `get_record_impl(session, kind, record_id)` - NEW: resolves email/thread/marginalia URIs
- `search_emails_impl(session, query, limit)` - NEW: wraps SearchEngine
- `create_server()` - rewritten with `FastMCP("mail-memex")`, registers all tools
- Marginalia tools delegate to `mail_memex.core.marginalia` CRUD functions

- [ ] **Step 4: Update MCP entry points**

Replace `src/mail_memex/mcp/__init__.py`:

```python
"""MCP server for mail-memex."""

from __future__ import annotations


def run_server() -> None:
    """Run the MCP server on stdio transport."""
    from mail_memex.mcp.server import create_server

    mcp = create_server()
    mcp.run(transport="stdio")
```

Replace `src/mail_memex/mcp/__main__.py`:

```python
"""Entry point for python -m mail_memex.mcp."""

from mail_memex.mcp import run_server

run_server()
```

- [ ] **Step 5: Run MCP tests**

```bash
pytest tests/test_mcp_server.py -v
```

Expected: All pass.

- [ ] **Step 6: Run full test suite**

```bash
pytest
```

Expected: All pass.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: rewrite MCP server with FastMCP and contract tools

Upgrade from mcp.server.Server to FastMCP('mail-memex').
Contract tools: execute_sql (was run_sql), get_schema, get_record.
Domain tools: search_emails, marginalia CRUD (7 tools).
get_record resolves mail-memex://email/, thread/, marginalia/ URIs."
```

---

## Task 6: Update arkiv Export URI Scheme

**Files:**
- Modify: `src/mail_memex/export/arkiv_export.py`
- Modify: `tests/test_arkiv.py`

- [ ] **Step 1: Update URI in arkiv export**

In `src/mail_memex/export/arkiv_export.py`, change the URI format:

```python
"uri": f"mail-memex://email/{email.message_id}",
```

- [ ] **Step 2: Update test assertions**

In `tests/test_arkiv.py`, find any assertion checking for `mtk://` and change to `mail-memex://`.

- [ ] **Step 3: Run arkiv tests**

```bash
pytest tests/test_arkiv.py -v
```

Expected: All pass.

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "feat: update arkiv export URI to mail-memex://email/"
```

---

## Task 7: HTML SPA Export Rewrite

Rewrite the HTML export with builder+template pattern. Build an in-memory export DB with denormalized schema, embed it base64 in a single HTML file.

**Files:**
- Create: `src/mail_memex/export/html_builder.py`
- Create: `src/mail_memex/export/html_template.py`
- Modify: `src/mail_memex/export/html_export.py`
- Modify: `src/mail_memex/cli/main.py` (update html export command)
- Modify: `tests/test_html_export.py`

- [ ] **Step 1: Write test for HTML SPA export**

Update `tests/test_html_export.py`:

```python
"""Tests for HTML SPA export."""

from pathlib import Path

from mail_memex.core.database import Database
from mail_memex.core.models import Email
from mail_memex.export.html_export import HtmlExporter


def test_html_export_creates_file(populated_db: Database, tmp_dir: Path):
    """HTML export creates a single HTML file."""
    output = tmp_dir / "archive.html"
    with populated_db.session() as session:
        from sqlalchemy import select
        emails = list(session.execute(select(Email)).scalars())
        exporter = HtmlExporter(output)
        result = exporter.export(emails)

    assert output.exists()
    assert result.emails_exported == 5
    assert result.format == "html"


def test_html_export_contains_sql_js(populated_db: Database, tmp_dir: Path):
    """HTML output references sql.js for client-side SQLite."""
    output = tmp_dir / "archive.html"
    with populated_db.session() as session:
        from sqlalchemy import select
        emails = list(session.execute(select(Email)).scalars())
        exporter = HtmlExporter(output)
        exporter.export(emails)

    html = output.read_text()
    assert "sql-wasm.js" in html
    assert "mail-memex" in html


def test_html_export_embeds_database(populated_db: Database, tmp_dir: Path):
    """HTML output contains base64-encoded SQLite database."""
    output = tmp_dir / "archive.html"
    with populated_db.session() as session:
        from sqlalchemy import select
        emails = list(session.execute(select(Email)).scalars())
        exporter = HtmlExporter(output)
        exporter.export(emails)

    html = output.read_text()
    assert "DB_BASE64" in html
```

- [ ] **Step 2: Create HTML builder module**

Create `src/mail_memex/export/html_builder.py`. This module builds an in-memory SQLite database with denormalized schema (emails with tags_json, threads, FTS5 index) and returns the raw bytes. Uses `sqlite3.connect(":memory:")`, inserts data, then serializes via `conn.serialize()` (Python 3.11+ `sqlite3` backup API).

Key points:
- Schema: `emails` (with `tags_json TEXT`), `threads`, `emails_fts` (FTS5)
- Tags denormalized as JSON array per email
- Threads collected from email relationships
- Returns `bytes` of the SQLite database

- [ ] **Step 3: Create HTML template module**

Create `src/mail_memex/export/html_template.py`. Contains the `HTML_TEMPLATE` string constant with the full HTML+CSS+JS for the SPA. Uses `%s` for the base64 DB injection and `%%` for literal percent signs in CSS.

Key UI features:
- Inbox list view with date, from, subject, tags columns
- FTS5 search with LIKE fallback
- Email detail view with body text
- Thread navigation
- Tags rendered from JSON array (not join table)

- [ ] **Step 4: Rewrite HTML export module**

Replace `src/mail_memex/export/html_export.py`:

```python
"""HTML Single File Application export for mail-memex.

Generates a self-contained HTML file with an embedded SQLite database
that can be viewed in a browser using sql.js.
"""

from __future__ import annotations

import base64
from pathlib import Path
from typing import TYPE_CHECKING

from mail_memex.export.base import ExportResult
from mail_memex.export.html_builder import build_export_db
from mail_memex.export.html_template import HTML_TEMPLATE

if TYPE_CHECKING:
    from mail_memex.core.models import Email


class HtmlExporter:
    """Export emails as a self-contained HTML SPA."""

    format_name: str = "html"

    def __init__(self, output_path: Path) -> None:
        self.output_path = Path(output_path)

    def export(self, emails: list[Email]) -> ExportResult:
        """Export emails to a single HTML file with embedded SQLite."""
        db_bytes = build_export_db(emails)
        db_base64 = base64.b64encode(db_bytes).decode("ascii")

        html = HTML_TEMPLATE % db_base64

        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        self.output_path.write_text(html, encoding="utf-8")

        return ExportResult(
            format="html",
            output_path=str(self.output_path),
            emails_exported=len(emails),
        )
```

- [ ] **Step 5: Update CLI html export command**

In `src/mail_memex/cli/main.py`, update the `export_html` command to use the new API (takes a list of emails, supports `--query` filtering):

```python
@export_app.command("html")
def export_html(
    output: Path = typer.Argument(..., help="Output HTML file path"),
    query: str | None = typer.Option(None, "--query", "-q", help="Search query to filter"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output result as JSON"),
) -> None:
    """Export email archive as a self-contained HTML application."""
    from mail_memex.export.html_export import HtmlExporter

    db = get_db()
    with db.session() as session:
        emails = _prepare_export(session, query)
        exporter = HtmlExporter(output)
        result = exporter.export(emails)

    if json_output:
        print(json_lib.dumps(result.to_dict(), indent=2))
    else:
        console.print(f"[green]Exported archive to {output}[/green]")
        console.print(f"  {result.emails_exported} emails, {output.stat().st_size / 1024:.0f} KB")
```

- [ ] **Step 6: Run HTML export tests**

```bash
pytest tests/test_html_export.py -v
```

Expected: All pass.

- [ ] **Step 7: Run full test suite**

```bash
pytest
```

Expected: All pass.

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "feat: rewrite HTML SPA export with builder+template pattern

html_builder.py creates in-memory SQLite with denormalized schema
(tags as JSON arrays, FTS5 index). html_template.py provides the
single-file UI with search, thread view, and tag display.
HtmlExporter now takes a list of Email objects (not a db path),
consistent with other exporters. Supports --query filtering."
```

---

## Task 8: Migration Script and Documentation

**Files:**
- Create: `scripts/migrate-from-mtk.py`
- Modify: `CLAUDE.md`

- [ ] **Step 1: Create migration script**

Create `scripts/migrate-from-mtk.py`:

```python
#!/usr/bin/env python3
"""Standalone migration script: mtk -> mail-memex.

Copies config and database from old mtk paths to new mail-memex paths.
Not part of the mail-memex package. Run once, then delete.

Usage:
    python scripts/migrate-from-mtk.py
    python scripts/migrate-from-mtk.py --dry-run
"""

import shutil
import sys
from pathlib import Path


def main() -> None:
    dry_run = "--dry-run" in sys.argv

    old_config = Path.home() / ".config" / "mtk" / "config.yaml"
    new_config = Path.home() / ".config" / "mail-memex" / "config.yaml"

    old_db = Path.home() / ".local" / "share" / "mtk" / "mtk.db"
    new_db = Path.home() / ".local" / "share" / "mail-memex" / "mail-memex.db"

    actions = []

    if old_config.exists() and not new_config.exists():
        actions.append(("config", old_config, new_config))
    elif old_config.exists() and new_config.exists():
        print(f"SKIP: {new_config} already exists")
    else:
        print(f"SKIP: {old_config} not found")

    if old_db.exists() and not new_db.exists():
        actions.append(("database", old_db, new_db))
        for suffix in ("-wal", "-shm"):
            sidecar = old_db.with_name(old_db.name + suffix)
            if sidecar.exists():
                new_sidecar = new_db.with_name(new_db.name + suffix)
                actions.append(("sidecar", sidecar, new_sidecar))
    elif old_db.exists() and new_db.exists():
        print(f"SKIP: {new_db} already exists")
    else:
        print(f"SKIP: {old_db} not found")

    if not actions:
        print("Nothing to migrate.")
        return

    for kind, src, dst in actions:
        if dry_run:
            print(f"WOULD COPY {kind}: {src} -> {dst}")
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            print(f"COPIED {kind}: {src} -> {dst}")

    if not dry_run and new_config.exists():
        text = new_config.read_text()
        text = text.replace(str(old_db), str(new_db))
        text = text.replace("mtk.db", "mail-memex.db")
        new_config.write_text(text)
        print(f"UPDATED db_path in {new_config}")

    if dry_run:
        print("\nDry run complete. Run without --dry-run to execute.")
    else:
        print("\nMigration complete. Verify mail-memex works, then remove old paths.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Make it executable**

```bash
chmod +x scripts/migrate-from-mtk.py
```

- [ ] **Step 3: Update CLAUDE.md**

Rewrite CLAUDE.md to reflect the new package name, paths, MCP tools, marginalia, and soft delete. Key updates:

- Project name: mail-memex (package: `mail_memex`)
- CLI: `mail-memex`
- Config: `~/.config/mail-memex/config.yaml`
- Database: `~/.local/share/mail-memex/mail-memex.db`
- Env var: `MAIL_MEMEX_DATABASE_PATH`
- MCP: FastMCP with execute_sql, get_schema, get_record, search_emails, marginalia tools
- Schema: archived_at on emails/threads, marginalia + marginalia_targets tables
- URI scheme: `mail-memex://email/`, `mail-memex://thread/`, `mail-memex://marginalia/`

- [ ] **Step 4: Run full test suite**

```bash
pytest
```

Expected: All pass.

- [ ] **Step 5: Run test coverage**

```bash
pytest --cov=src/mail_memex --cov-report=term-missing
```

Review coverage for new modules (marginalia.py, html_builder.py, mcp/server.py).

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "docs: add migration script and update CLAUDE.md for mail-memex

Standalone scripts/migrate-from-mtk.py copies config+db from old paths.
CLAUDE.md rewritten for mail-memex naming, contract tools, soft delete,
marginalia, and new HTML SPA export."
```

---

## Task 9: Final Verification

Ensure everything works end-to-end.

- [ ] **Step 1: Clean reinstall**

```bash
pip install -e ".[all]"
```

- [ ] **Step 2: Run full test suite with coverage**

```bash
pytest --cov=src/mail_memex --cov-report=term-missing
```

Expected: All tests pass.

- [ ] **Step 3: Verify CLI works**

```bash
mail-memex --version
mail-memex --help
```

Expected: Shows `mail-memex version 0.5.0` and help text.

- [ ] **Step 4: Verify MCP entry point**

```bash
python -m mail_memex.mcp 2>&1 | head -1 || echo "MCP server starts on stdio (expected)"
```

- [ ] **Step 5: Type check**

```bash
mypy src/mail_memex
```

Expected: No errors (or only pre-existing ones).

- [ ] **Step 6: Lint**

```bash
ruff check src/mail_memex tests
```

Expected: Clean.

- [ ] **Step 7: Commit any final fixes**

If any fixes were needed:

```bash
git add -A
git commit -m "fix: address lint/type issues from mail-memex rename"
```
