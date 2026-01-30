"""Gmail-specific IMAP extensions.

Handles X-GM-LABELS, X-GM-THRID, and other Gmail IMAP quirks.
"""

from __future__ import annotations

from typing import Any


class GmailExtensions:
    """Gmail-specific IMAP extensions.

    Gmail IMAP uses non-standard extensions:
    - X-GM-LABELS: Gmail labels (instead of/in addition to folders)
    - X-GM-THRID: Gmail thread ID
    - X-GM-MSGID: Gmail message ID
    """

    @staticmethod
    def extract_labels(fetch_data: dict[bytes, Any]) -> list[str]:
        """Extract Gmail labels from IMAP FETCH response.

        Args:
            fetch_data: Raw FETCH response dict for a single message.

        Returns:
            List of Gmail label strings.
        """
        labels_key = b"X-GM-LABELS"
        raw_labels = fetch_data.get(labels_key, ())

        labels = []
        for label in raw_labels:
            if isinstance(label, bytes):
                labels.append(label.decode("utf-8", errors="replace"))
            else:
                labels.append(str(label))

        return labels

    @staticmethod
    def extract_thread_id(fetch_data: dict[bytes, Any]) -> str | None:
        """Extract Gmail thread ID from IMAP FETCH response.

        Args:
            fetch_data: Raw FETCH response dict.

        Returns:
            Gmail thread ID string, or None.
        """
        thrid_key = b"X-GM-THRID"
        thrid = fetch_data.get(thrid_key)
        if thrid is not None:
            return str(thrid)
        return None

    @staticmethod
    def build_fetch_items(gmail_extensions: bool = True) -> list[str]:
        """Build FETCH item list with optional Gmail extensions.

        Args:
            gmail_extensions: Include Gmail-specific FETCH items.

        Returns:
            List of FETCH items to request.
        """
        items = ["UID", "FLAGS", "ENVELOPE", "RFC822.SIZE", "BODY.PEEK[TEXT]"]
        if gmail_extensions:
            items.extend(["X-GM-LABELS", "X-GM-THRID", "X-GM-MSGID"])
        return items
