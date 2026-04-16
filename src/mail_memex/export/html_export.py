"""HTML Single File Application export for mail-memex.

Generates a self-contained HTML file with an embedded SQLite database
that can be viewed in a browser using sql.js.

The export database is denormalized (tags as JSON arrays, no join tables)
and includes an FTS5 index for client-side search.
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
    """Export emails as a self-contained HTML application.

    Builds an in-memory SQLite database with a denormalized schema,
    base64-encodes it, and embeds it into a single HTML page that uses
    sql.js to provide an interactive email client in the browser.
    """

    format_name: str = "html"

    def __init__(self, output_path: Path) -> None:
        self.output_path = Path(output_path)

    def export(self, emails: list[Email]) -> ExportResult:
        """Export emails as a self-contained HTML application.

        Args:
            emails: List of Email ORM objects to export.

        Returns:
            ExportResult with statistics.
        """
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
