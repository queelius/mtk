"""Bidirectional mapping between IMAP flags/Gmail labels and mtk tags."""

from __future__ import annotations

from dataclasses import dataclass, field

# Standard IMAP flag → mtk tag mappings
_IMAP_FLAG_TO_TAG: dict[str, str] = {
    "\\Seen": "read",
    "\\Flagged": "flagged",
    "\\Answered": "replied",
    "\\Draft": "draft",
    "\\Deleted": "deleted",
}

_TAG_TO_IMAP_FLAG: dict[str, str] = {v: k for k, v in _IMAP_FLAG_TO_TAG.items()}

# Gmail label → mtk tag mappings
_GMAIL_LABEL_TO_TAG: dict[str, str] = {
    "\\Inbox": "inbox",
    "\\Sent": "sent",
    "\\Draft": "draft",
    "\\Spam": "spam",
    "\\Trash": "trash",
    "\\Starred": "starred",
    "\\Important": "important",
    "CATEGORY_PERSONAL": "personal",
    "CATEGORY_SOCIAL": "social",
    "CATEGORY_PROMOTIONS": "promotions",
    "CATEGORY_UPDATES": "updates",
    "CATEGORY_FORUMS": "forums",
}

_TAG_TO_GMAIL_LABEL: dict[str, str] = {v: k for k, v in _GMAIL_LABEL_TO_TAG.items()}


@dataclass
class TagMapper:
    """Bidirectional mapper between IMAP flags/Gmail labels and mtk tags.

    Args:
        is_gmail: Whether to use Gmail label mapping in addition to IMAP flags.
        custom_mappings: Additional custom mappings (imap_value → mtk_tag).
    """

    is_gmail: bool = False
    custom_mappings: dict[str, str] = field(default_factory=dict)

    def imap_to_tags(self, flags: list[str], labels: list[str] | None = None) -> set[str]:
        """Convert IMAP flags (and optionally Gmail labels) to mtk tags.

        Args:
            flags: IMAP flags (e.g., ["\\Seen", "\\Flagged"]).
            labels: Gmail X-GM-LABELS (only used if is_gmail=True).

        Returns:
            Set of mtk tag names.
        """
        tags: set[str] = set()

        # Standard IMAP flags
        for flag in flags:
            flag_str = flag.decode() if isinstance(flag, bytes) else str(flag)
            tag = _IMAP_FLAG_TO_TAG.get(flag_str)
            if tag:
                tags.add(tag)
            # Check custom mappings
            custom_tag = self.custom_mappings.get(flag_str)
            if custom_tag:
                tags.add(custom_tag)

        # Gmail labels
        if self.is_gmail and labels:
            for label in labels:
                label_str = label.decode() if isinstance(label, bytes) else str(label)
                tag = _GMAIL_LABEL_TO_TAG.get(label_str)
                if tag:
                    tags.add(tag)
                else:
                    # Pass through unknown Gmail labels as-is (lowercased)
                    tags.add(label_str.lower().replace(" ", "-"))

        return tags

    def tags_to_imap_flags(self, tags: set[str]) -> list[str]:
        """Convert mtk tags back to IMAP flags.

        Only returns flags that have known IMAP flag equivalents.

        Args:
            tags: Set of mtk tag names.

        Returns:
            List of IMAP flag strings.
        """
        flags = []
        reverse_custom = {v: k for k, v in self.custom_mappings.items()}

        for tag in tags:
            flag = _TAG_TO_IMAP_FLAG.get(tag)
            if flag:
                flags.append(flag)
            custom_flag = reverse_custom.get(tag)
            if custom_flag:
                flags.append(custom_flag)

        return flags

    def tags_to_gmail_labels(self, tags: set[str]) -> list[str]:
        """Convert mtk tags back to Gmail labels.

        Args:
            tags: Set of mtk tag names.

        Returns:
            List of Gmail label strings.
        """
        labels = []
        for tag in tags:
            label = _TAG_TO_GMAIL_LABEL.get(tag)
            if label:
                labels.append(label)
        return labels

    def diff_tags(self, current_tags: set[str], new_tags: set[str]) -> tuple[set[str], set[str]]:
        """Compute tag additions and removals.

        Args:
            current_tags: Current set of tags.
            new_tags: Desired set of tags.

        Returns:
            Tuple of (tags_to_add, tags_to_remove).
        """
        return new_tags - current_tags, current_tags - new_tags
