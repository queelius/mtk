"""HTML Single File Application export for mail-memex.

Generates a self-contained HTML file with:

- Inlined sql-wasm.js (the vendored build; no CDN).
- Base64-encoded sql-wasm.wasm (decoded via WebAssembly.instantiate()).
- Gzipped + base64-encoded SQLite database (decompressed in-browser via
  ``DecompressionStream('gzip')``).
- The SPA UI (html_template).

The archive is designed to be genuinely portable: one file, opens
anywhere, no network requests, no CDN dependency, no authentication
on the author's behalf.

The shipped DB has FTS5 virtual tables stripped (the vendored sql.js
build is not compiled with FTS5). Client-side search uses LIKE.
"""

from __future__ import annotations

import base64
import gzip
from pathlib import Path
from typing import TYPE_CHECKING

from mail_memex.export.base import ExportResult
from mail_memex.export.html_builder import build_export_db
from mail_memex.export.html_template import HTML_TEMPLATE

if TYPE_CHECKING:
    from mail_memex.core.models import Email


_VENDORED_DIR = Path(__file__).parent / "vendored"
# gzip level 6 is the sweet spot: near-maximum ratio, modest CPU cost.
_DB_GZIP_LEVEL = 6


def _read_vendored(filename: str) -> bytes:
    return (_VENDORED_DIR / filename).read_bytes()


class HtmlExporter:
    """Export emails as a self-contained HTML application.

    Builds an in-memory SQLite database with a denormalized schema,
    gzips it, base64-encodes it, and embeds it together with sql.js
    into a single HTML page. No server, no CDN, no network requests
    — opens in any modern browser.
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
        # 1. Build the raw SQLite bytes.
        db_bytes = build_export_db(emails)

        # 2. Gzip and base64-encode the DB for transport inside the page.
        db_gz = gzip.compress(db_bytes, compresslevel=_DB_GZIP_LEVEL)
        db_b64 = base64.b64encode(db_gz).decode("ascii")

        # 3. Inline the sql.js loader JS verbatim and base64-encode the wasm.
        sqljs_js = _read_vendored("sql-wasm.js").decode("utf-8")
        wasm_b64 = base64.b64encode(_read_vendored("sql-wasm.wasm")).decode("ascii")

        # 4. Substitute into the template. Defensively escape ``</script>``
        # in the sql.js body just in case a future minifier-change emits
        # the literal sequence; it does not appear in the current vendored
        # build but the cost of defensiveness is one str.replace().
        sqljs_js_safe = sqljs_js.replace("</script>", "<\\/script>")

        html = (
            HTML_TEMPLATE
            .replace("__SQLJS_INLINE__", sqljs_js_safe)
            .replace("__WASM_BASE64__", wasm_b64)
            .replace("__DB_BASE64_GZ__", db_b64)
        )

        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        self.output_path.write_text(html, encoding="utf-8")

        return ExportResult(
            format="html",
            output_path=str(self.output_path),
            emails_exported=len(emails),
        )
