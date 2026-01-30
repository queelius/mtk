"""Search functionality for mtk."""

from mtk.search.engine import SearchEngine, SearchResult
from mtk.search.fts import fts5_available, fts_stats, rebuild_fts_index

__all__ = [
    "SearchEngine",
    "SearchResult",
    "fts5_available",
    "fts_stats",
    "rebuild_fts_index",
]
