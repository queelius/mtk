"""Input validation helpers for MCP tool arguments."""

from __future__ import annotations


def require_str(args: dict, key: str) -> str:
    """Extract a required string argument."""
    value = args.get(key)
    if not value or not isinstance(value, str):
        raise ValueError(f"Missing required argument: {key}")
    return value


def optional_str(args: dict, key: str, default: str | None = None) -> str | None:
    """Extract an optional string argument."""
    value = args.get(key)
    if value is None:
        return default
    return str(value)


def optional_int(args: dict, key: str, default: int = 0) -> int:
    """Extract an optional integer argument."""
    value = args.get(key)
    if value is None:
        return default
    return int(value)


def optional_bool(args: dict, key: str, default: bool = False) -> bool:
    """Extract an optional boolean argument."""
    value = args.get(key)
    if value is None:
        return default
    return bool(value)


def optional_list(args: dict, key: str) -> list[str]:
    """Extract an optional list-of-strings argument."""
    value = args.get(key)
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v) for v in value]
    return [str(value)]
