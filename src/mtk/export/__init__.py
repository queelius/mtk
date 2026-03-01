"""Email export functionality for mtk.

Supports multiple formats: JSON, mbox, Markdown, and HTML (single-file app).
Integrates with privacy filtering for safe exports.
"""

from mtk.export.base import Exporter, ExportResult
from mtk.export.html_export import HtmlExporter
from mtk.export.json_export import JsonExporter
from mtk.export.markdown_export import MarkdownExporter
from mtk.export.mbox_export import MboxExporter

__all__ = [
    "Exporter",
    "ExportResult",
    "HtmlExporter",
    "JsonExporter",
    "MboxExporter",
    "MarkdownExporter",
]
