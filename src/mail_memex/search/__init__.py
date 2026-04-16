"""Search functionality for mail-memex."""

from mail_memex.search.engine import SearchEngine, SearchResult
from mail_memex.search.fts import fts5_available, fts_stats, rebuild_fts_index

__all__ = [
    "SearchEngine",
    "SearchResult",
    "fts5_available",
    "fts_stats",
    "rebuild_fts_index",
]
