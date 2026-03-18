"""Base exporter interface and common utilities."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from mtk.core.models import Email


def _email_to_dict(email: Email) -> dict[str, Any]:
    """Convert an Email ORM object to a plain dictionary.

    This is the canonical conversion used by export.
    """
    return {
        "message_id": email.message_id,
        "from_addr": email.from_addr,
        "from_name": email.from_name,
        "to_addrs": email.to_addrs,
        "cc_addrs": email.cc_addrs,
        "bcc_addrs": email.bcc_addrs,
        "subject": email.subject,
        "date": email.date,
        "in_reply_to": email.in_reply_to,
        "references": email.references,
        "body_text": email.body_text,
        "body_html": email.body_html,
        "body_preview": email.body_preview,
        "thread_id": email.thread_id,
        "tags": [t.name for t in email.tags] if hasattr(email, "tags") and email.tags else [],
        "attachments": [
            {
                "filename": a.filename,
                "content_type": a.content_type,
                "size": a.size,
            }
            for a in email.attachments
        ]
        if hasattr(email, "attachments") and email.attachments
        else [],
    }


@dataclass
class ExportResult:
    """Result of an export operation."""

    format: str
    output_path: str
    emails_exported: int = 0
    emails_excluded: int = 0
    attachments_exported: int = 0
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON output."""
        result = {
            "format": self.format,
            "output_path": self.output_path,
            "emails_exported": self.emails_exported,
            "emails_excluded": self.emails_excluded,
            "attachments_exported": self.attachments_exported,
        }
        if self.errors:
            result["errors"] = self.errors
        return result


class Exporter(ABC):
    """Base class for email exporters."""

    format_name: str = "base"

    def __init__(
        self,
        output_path: Path,
        include_attachments: bool = False,
    ) -> None:
        self.output_path = output_path
        self.include_attachments = include_attachments

    @abstractmethod
    def export(self, emails: list[Email]) -> ExportResult:
        """Export emails to the target format.

        Args:
            emails: List of Email objects to export.

        Returns:
            ExportResult with statistics.
        """
        pass

    def _emails_to_dicts(self, emails: list[Email]) -> list[dict[str, Any]]:
        """Convert emails to dictionaries for export.

        Returns:
            List of email dictionaries.
        """
        return [_email_to_dict(email) for email in emails]

    def _format_date(self, dt: datetime | None) -> str:
        """Format datetime for export."""
        if dt is None:
            return ""
        return dt.strftime("%a, %d %b %Y %H:%M:%S %z") or dt.isoformat()
