"""Export mail-memex data to arkiv bundles.

Output can be a directory, a ``.zip`` archive, or a ``.tar.gz`` tarball;
the choice is inferred from the output path's extension. All three layouts
contain the same files:

- ``records.jsonl`` : one JSON line per active email and marginalia record.
- ``schema.yaml``   : archive self-description + per-key metadata stats.
- ``README.md``     : arkiv ECHO frontmatter + human-readable explanation.

Record URI scheme follows the cross-archive contract::

    mail-memex://email/<message_id>
    mail-memex://thread/<thread_id>
    mail-memex://marginalia/<uuid>

Compression choice prioritises longevity: ``.zip`` and ``.tar.gz`` are
both ubiquitous on every OS (30+ years of universal tooling). Modern
compressors like ``zstd`` are deliberately avoided so the bundle still
opens in 2050.
"""

from __future__ import annotations

import io
import json
import tarfile
import zipfile
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

from mail_memex.export.base import ExportResult

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from mail_memex.core.models import Email


# ---------------------------------------------------------------------------
# Bundle format detection
# ---------------------------------------------------------------------------


def _detect_compression(path: str | Path) -> str:
    """Infer output format from *path*'s extension.

    Returns one of ``"zip"``, ``"tar.gz"``, ``"dir"``.
    """
    lower = str(path).lower()
    if lower.endswith(".zip"):
        return "zip"
    if lower.endswith(".tar.gz") or lower.endswith(".tgz"):
        return "tar.gz"
    return "dir"


# ---------------------------------------------------------------------------
# Record building
# ---------------------------------------------------------------------------


def _email_to_record(email: Email, include_body: bool) -> dict[str, Any]:
    """Convert an Email ORM row to an arkiv record."""
    record: dict[str, Any] = {
        "mimetype": "message/rfc822",
        "uri": f"mail-memex://email/{email.message_id}",
        "kind": "email",
    }

    if email.date:
        record["timestamp"] = email.date.isoformat()

    if include_body and email.body_text:
        record["content"] = email.body_text

    metadata: dict[str, Any] = {
        "message_id": email.message_id,
        "from_addr": email.from_addr,
        "subject": email.subject,
    }

    if email.from_name:
        metadata["from_name"] = email.from_name
    if email.thread_id:
        metadata["thread_id"] = email.thread_id
    if email.in_reply_to:
        metadata["in_reply_to"] = email.in_reply_to
    if email.to_addrs:
        metadata["to_addrs"] = email.to_addrs
    if email.cc_addrs:
        metadata["cc_addrs"] = email.cc_addrs
    if email.bcc_addrs:
        metadata["bcc_addrs"] = email.bcc_addrs
    if email.tags:
        metadata["tags"] = sorted(t.name for t in email.tags)
    if email.attachments:
        metadata["has_attachments"] = True
        metadata["attachment_count"] = len(email.attachments)
        metadata["attachments"] = [
            {
                "filename": a.filename,
                "content_type": a.content_type,
                "size": a.size,
            }
            for a in email.attachments
        ]

    record["metadata"] = metadata
    return record


def _marginalia_to_record(m: Any) -> dict[str, Any]:
    """Convert a Marginalia ORM row to an arkiv record."""
    record: dict[str, Any] = {
        "mimetype": "text/plain",
        "uri": f"mail-memex://marginalia/{m.uuid}",
        "kind": "marginalia",
    }

    if m.created_at:
        record["timestamp"] = (
            m.created_at.isoformat()
            if hasattr(m.created_at, "isoformat")
            else str(m.created_at)
        )

    if m.content:
        record["content"] = m.content

    metadata: dict[str, Any] = {
        "uuid": m.uuid,
        "target_uris": [t.target_uri for t in m.targets],
        "pinned": bool(m.pinned),
    }
    if m.category:
        metadata["category"] = m.category
    if m.color:
        metadata["color"] = m.color
    if m.created_at and hasattr(m.created_at, "isoformat"):
        metadata["created_at"] = m.created_at.isoformat()
    if m.updated_at and hasattr(m.updated_at, "isoformat"):
        metadata["updated_at"] = m.updated_at.isoformat()

    record["metadata"] = metadata
    return record


# ---------------------------------------------------------------------------
# Serialisation helpers
# ---------------------------------------------------------------------------


def _records_to_jsonl_bytes(records: list[dict[str, Any]]) -> bytes:
    buf = io.StringIO()
    for rec in records:
        buf.write(json.dumps(rec, default=str, ensure_ascii=False) + "\n")
    return buf.getvalue().encode("utf-8")


def _schema_yaml_bytes(
    counts: dict[str, int],
) -> bytes:
    """Render schema.yaml with declared field docs + live per-kind counts."""
    schema = {
        "scheme": "mail-memex",
        "counts": counts,
        "kinds": {
            "email": {
                "description": "An RFC 2822 email message.",
                "uri": "mail-memex://email/<message_id>",
                "fields": {
                    "kind": "Always 'email'.",
                    "uri": "Canonical mail-memex URI.",
                    "mimetype": "Always 'message/rfc822'.",
                    "content": "Plain-text body (if include_body=True).",
                    "metadata.message_id": "RFC 2822 Message-ID.",
                    "metadata.from_addr": "Sender email address.",
                    "metadata.from_name": "Sender display name (optional).",
                    "metadata.subject": "Subject line.",
                    "metadata.to_addrs": (
                        "Comma-joined To: recipients (optional)."
                    ),
                    "metadata.cc_addrs": (
                        "Comma-joined Cc: recipients (optional)."
                    ),
                    "metadata.bcc_addrs": (
                        "Comma-joined Bcc: recipients (optional)."
                    ),
                    "metadata.thread_id": "Thread identifier (optional).",
                    "metadata.in_reply_to": (
                        "Message-ID this email is a reply to (optional)."
                    ),
                    "metadata.tags": "Array of tag names (optional).",
                    "metadata.attachments": (
                        "Array of {filename, content_type, size} objects "
                        "(optional)."
                    ),
                },
            },
            "marginalia": {
                "description": "A free-form note attached to one or more URIs.",
                "uri": "mail-memex://marginalia/<uuid>",
                "fields": {
                    "kind": "Always 'marginalia'.",
                    "uri": "Canonical mail-memex URI.",
                    "mimetype": "Always 'text/plain'.",
                    "content": "Note body.",
                    "metadata.uuid": "32-char hex UUID (durable identity).",
                    "metadata.target_uris": (
                        "Array of URIs this note is attached to. May be "
                        "zero-length (orphan)."
                    ),
                    "metadata.pinned": "Whether the note is pinned.",
                    "metadata.category": "Optional free-form category.",
                    "metadata.color": "Optional CSS color hint.",
                    "metadata.created_at": "ISO-8601 UTC creation timestamp.",
                    "metadata.updated_at": (
                        "ISO-8601 UTC last-update timestamp."
                    ),
                },
            },
        },
    }
    buf = io.StringIO()
    buf.write("# Auto-generated by mail-memex. Edit freely.\n")
    yaml.safe_dump(
        schema,
        buf,
        default_flow_style=False,
        sort_keys=False,
        allow_unicode=True,
    )
    return buf.getvalue().encode("utf-8")


def _readme_bytes(counts: dict[str, int]) -> bytes:
    """Render README.md with arkiv ECHO frontmatter + usage notes."""
    try:
        from importlib.metadata import version as _pkg_version

        version = _pkg_version("mail-memex")
    except Exception:
        version = "unknown"

    today = date.today().isoformat()
    n_email = counts.get("email", 0)
    n_margin = counts.get("marginalia", 0)
    lines = [
        "---",
        "name: mail-memex archive",
        (
            f'description: "{n_email} emails + {n_margin} '
            'marginalia exported from mail-memex"'
        ),
        f"datetime: {today}",
        f"generator: mail-memex {version}",
        "contents:",
        "  - path: records.jsonl",
        "    description: Email and marginalia records (arkiv JSONL format)",
        "  - path: schema.yaml",
        "    description: Record schema + per-kind counts",
        "---",
        "",
        "# mail-memex Archive",
        "",
        (
            f"This archive contains {n_email} email(s) and {n_margin} "
            "note(s) (marginalia)"
        ),
        "exported from mail-memex in "
        "[arkiv](https://github.com/queelius/arkiv) format.",
        "",
        "Each line in `records.jsonl` is one record. Records are typed by `kind`:",
        "",
        "- `email`: an RFC 2822 email with metadata and optional body text.",
        "- `marginalia`: a free-form note attached to one or more URIs.",
        "",
        "URIs follow the cross-archive `mail-memex://` scheme and stay stable",
        "across re-imports, so marginalia survive their target email being",
        "re-imported or round-tripped through another archive.",
        "",
        "## Importing back into mail-memex",
        "",
        "```bash",
        "# Insert-or-ignore on message_id + uuid; safe for re-imports.",
        "mail-memex import arkiv <this bundle>",
        "",
        "# Or with explicit --merge semantics (same effect today; reserved",
        "# for a future stricter-insert mode).",
        "mail-memex import arkiv <this bundle> --merge",
        "```",
        "",
    ]
    return "\n".join(lines).encode("utf-8")


def _write_file(path: Path, data: bytes) -> None:
    path.write_bytes(data)


def _write_zip(
    path: Path, jsonl: bytes, schema_yaml: bytes, readme: bytes
) -> None:
    """Write the three bundle files into a single .zip archive."""
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("records.jsonl", jsonl)
        zf.writestr("schema.yaml", schema_yaml)
        zf.writestr("README.md", readme)


def _write_tar_gz(
    path: Path, jsonl: bytes, schema_yaml: bytes, readme: bytes
) -> None:
    """Write the three bundle files into a single .tar.gz archive."""
    with tarfile.open(path, "w:gz") as tf:
        for name, data in (
            ("records.jsonl", jsonl),
            ("schema.yaml", schema_yaml),
            ("README.md", readme),
        ):
            info = tarfile.TarInfo(name=name)
            info.size = len(data)
            tf.addfile(info, io.BytesIO(data))


# ---------------------------------------------------------------------------
# Exporter class (preserves public API)
# ---------------------------------------------------------------------------


class ArkivExporter:
    """Export mail-memex data to an arkiv bundle.

    Output format is inferred from *output_path*'s extension:

    - ``path.zip``             -> single zip file
    - ``path.tar.gz``/``.tgz`` -> single gzip-compressed tarball
    - any other path           -> directory with records.jsonl,
                                  schema.yaml, and README.md

    Exports both emails and marginalia by default. Pass a session via
    :meth:`export` if you want marginalia records to be included; the
    older signature ``export(emails)`` still works (it skips marginalia).
    """

    format_name: str = "arkiv"

    def __init__(
        self,
        output_path: Path,
        include_body: bool = True,
    ) -> None:
        self.output_path = Path(output_path)
        self.include_body = include_body

    def export(
        self,
        emails: list[Email],
        session: Session | None = None,
    ) -> ExportResult:
        """Export emails (and marginalia, if session provided) to a bundle."""
        # Build records: emails in time order, then marginalia in time order.
        records: list[dict[str, Any]] = [
            _email_to_record(e, self.include_body) for e in emails
        ]
        marginalia_count = 0
        if session is not None:
            marginalia_count = self._append_marginalia_records(records, session)

        counts = {
            "email": len(emails),
            "marginalia": marginalia_count,
        }

        jsonl_bytes = _records_to_jsonl_bytes(records)
        schema_bytes = _schema_yaml_bytes(counts)
        readme_bytes = _readme_bytes(counts)

        fmt = _detect_compression(self.output_path)
        if fmt == "zip":
            self.output_path.parent.mkdir(parents=True, exist_ok=True)
            _write_zip(self.output_path, jsonl_bytes, schema_bytes, readme_bytes)
        elif fmt == "tar.gz":
            self.output_path.parent.mkdir(parents=True, exist_ok=True)
            _write_tar_gz(
                self.output_path, jsonl_bytes, schema_bytes, readme_bytes
            )
        else:
            out_dir = self.output_path
            out_dir.mkdir(parents=True, exist_ok=True)
            _write_file(out_dir / "records.jsonl", jsonl_bytes)
            _write_file(out_dir / "schema.yaml", schema_bytes)
            _write_file(out_dir / "README.md", readme_bytes)

        return ExportResult(
            format="arkiv",
            output_path=str(self.output_path),
            emails_exported=len(emails),
        )

    def _append_marginalia_records(
        self, records: list[dict[str, Any]], session: Session
    ) -> int:
        """Query active marginalia via *session* and append to *records*."""
        from sqlalchemy import select

        from mail_memex.core.models import Marginalia

        stmt = (
            select(Marginalia)
            .where(Marginalia.archived_at.is_(None))
            .order_by(Marginalia.created_at)
        )
        rows = list(session.execute(stmt).scalars().all())
        for m in rows:
            records.append(_marginalia_to_record(m))
        return len(rows)
