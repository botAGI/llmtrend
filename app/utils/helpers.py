"""Shared utility functions for the AI Trend Monitor application.

Pure helper functions with no side effects -- safe to import anywhere.
"""

import re
import unicodedata
from datetime import datetime, timezone


def slugify(text: str) -> str:
    """Convert arbitrary text into a URL-safe, lowercase slug.

    Unicode characters are transliterated to ASCII where possible.
    Whitespace and separators become hyphens; everything that is not
    alphanumeric or a hyphen is removed.  Leading/trailing hyphens and
    consecutive hyphens are collapsed.

    Args:
        text: The input string.

    Returns:
        A lowercase, hyphen-separated slug suitable for URLs or filenames.
    """
    # Normalize unicode to NFKD and strip accents / combining marks.
    value = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    value = value.lower().strip()
    value = re.sub(r"[\s_]+", "-", value)            # whitespace / underscores -> hyphens
    value = re.sub(r"[^a-z0-9\-]", "", value)        # remove non-alphanumeric (except -)
    value = re.sub(r"-{2,}", "-", value)              # collapse multiple hyphens
    value = value.strip("-")
    return value


def format_number(n: int | float) -> str:
    """Format a number into a compact, human-readable string.

    Examples:
        >>> format_number(999)
        '999'
        >>> format_number(1234)
        '1.2K'
        >>> format_number(1234567)
        '1.2M'
        >>> format_number(1234567890)
        '1.2B'

    Args:
        n: The numeric value to format.

    Returns:
        A string like ``"1.2K"``, ``"3.5M"``, or ``"1.2B"``.
    """
    abs_n = abs(n)
    sign = "-" if n < 0 else ""

    if abs_n >= 1_000_000_000:
        return f"{sign}{abs_n / 1_000_000_000:.1f}B"
    if abs_n >= 1_000_000:
        return f"{sign}{abs_n / 1_000_000:.1f}M"
    if abs_n >= 1_000:
        return f"{sign}{abs_n / 1_000:.1f}K"
    return f"{sign}{abs_n:g}"


def format_percent(value: float) -> str:
    """Format a percentage value with an explicit sign.

    Args:
        value: The percentage (e.g. 12.34 for 12.34%).

    Returns:
        A string like ``"+12.3%"`` or ``"-5.1%"``.
    """
    sign = "+" if value >= 0 else ""
    return f"{sign}{value:.1f}%"


def truncate(text: str, max_length: int = 200) -> str:
    """Truncate *text* to *max_length* characters, appending ``"..."`` if cut.

    If the text is already within the limit it is returned unchanged.

    Args:
        text: The input string.
        max_length: Maximum allowed length (including the ellipsis).

    Returns:
        The possibly-truncated string.
    """
    if len(text) <= max_length:
        return text
    return text[: max_length - 3].rstrip() + "..."


def parse_comma_separated(value: str) -> list[str]:
    """Split a comma-separated string into a trimmed list of non-empty tokens.

    Args:
        value: A raw string such as ``"a, b, c"`` or ``""``.

    Returns:
        A list of stripped, non-empty strings.  An empty input yields ``[]``.
    """
    if not value or not value.strip():
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def utc_now() -> datetime:
    """Return the current time as a timezone-aware UTC :class:`datetime`."""
    return datetime.now(tz=timezone.utc)


def days_ago(n: int) -> datetime:
    """Return a timezone-aware UTC :class:`datetime` for *n* days before now.

    Args:
        n: Number of days to subtract (must be non-negative).

    Returns:
        A timezone-aware UTC datetime.
    """
    from datetime import timedelta

    return utc_now() - timedelta(days=n)
