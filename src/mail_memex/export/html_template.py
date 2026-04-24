"""HTML+CSS+JS template for the mail-memex single-file archive application.

The template itself lives as a plain ``templates_index.html`` sibling
file so the massive JS body does not need Python string escaping.  The
exporter reads it at call time and substitutes three placeholders:

- ``__SQLJS_INLINE__``   : the full body of sql-wasm.js (vendored, no CDN).
- ``__WASM_BASE64__``    : base64-encoded sql-wasm.wasm bytes.
- ``__DB_BASE64_GZ__``   : base64-encoded gzip-compressed SQLite DB bytes.

Everything is loaded client-side without a network fetch. The DB is
decompressed via ``DecompressionStream('gzip')`` and the wasm binary is
handed to ``initSqlJs`` as a ``wasmBinary``, so sql.js never tries to
locate its ``.wasm`` sibling file.

Palette and typography track llm-memex's "personal archive" aesthetic
(walnut+amber dark, cream+bronze light, Inter/Iowan/JetBrains faces)
so the ecosystem looks coherent.

Hash routes:

- ``#/``                  home (recent emails)
- ``#/email/:id``         one email detail view
- ``#/thread/:id``        all emails in a thread
- ``#/search/:q``         LIKE search results
- ``#/tag/:name``         emails with a given tag
"""

from __future__ import annotations

from pathlib import Path

_TEMPLATE_PATH = Path(__file__).parent / "templates_index.html"

# Read eagerly so import failures surface early rather than at first export.
HTML_TEMPLATE: str = _TEMPLATE_PATH.read_text(encoding="utf-8")
