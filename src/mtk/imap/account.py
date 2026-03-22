"""IMAP account configuration dataclass."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ImapAccountConfig:
    """Configuration for a single IMAP account.

    Credentials are stored in the system keyring, not in config files.
    """

    name: str = ""
    host: str = ""
    port: int = 993
    username: str = ""
    use_ssl: bool = True
    provider: str = "generic"  # "generic" or "gmail"
    folders: list[str] = field(default_factory=lambda: ["INBOX"])
    oauth2: bool = False

    @property
    def is_gmail(self) -> bool:
        return self.provider == "gmail"

    @property
    def keyring_service(self) -> str:
        """Keyring service name for credential storage."""
        return f"mtk-imap-{self.name}"

    @classmethod
    def from_dict(cls, name: str, data: dict[str, Any]) -> ImapAccountConfig:
        """Create from dictionary."""
        return cls(
            name=name,
            host=data.get("host", ""),
            port=data.get("port", 993),
            username=data.get("username", ""),
            use_ssl=data.get("use_ssl", True),
            provider=data.get("provider", "generic"),
            folders=data.get("folders", ["INBOX"]),
            oauth2=data.get("oauth2", False),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "host": self.host,
            "port": self.port,
            "username": self.username,
            "use_ssl": self.use_ssl,
            "provider": self.provider,
            "folders": self.folders,
            "oauth2": self.oauth2,
        }
