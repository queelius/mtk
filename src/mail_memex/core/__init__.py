"""Core data models and database functionality."""

from mail_memex.core.database import Database, close_db, get_db, init_db
from mail_memex.core.models import (
    Attachment,
    Base,
    Email,
    Tag,
    Thread,
)

__all__ = [
    # Models
    "Base",
    "Email",
    "Thread",
    "Tag",
    "Attachment",
    # Database
    "Database",
    "get_db",
    "init_db",
    "close_db",
]
