"""IMAP account configuration dataclass."""

from __future__ import annotations

from dataclasses import dataclass, field


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
