"""Email export functionality for mail-memex.

Supports multiple formats: JSON, mbox, Markdown, HTML (single-file app), and arkiv (JSONL).
"""

from mail_memex.export.arkiv_export import ArkivExporter
from mail_memex.export.base import Exporter, ExportResult
from mail_memex.export.html_export import HtmlExporter
from mail_memex.export.json_export import JsonExporter
from mail_memex.export.markdown_export import MarkdownExporter
from mail_memex.export.mbox_export import MboxExporter

__all__ = [
    "ArkivExporter",
    "Exporter",
    "ExportResult",
    "HtmlExporter",
    "JsonExporter",
    "MboxExporter",
    "MarkdownExporter",
]
