from __future__ import annotations
from datetime import date, datetime
from dateutil import parser as _dateparser


def parse_date(value: str | date | datetime | None) -> date | None:
    """Best-effort parse to a date; returns None if unparseable/empty."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        # dayfirst=False matches most trade-doc conventions; adjust per region if needed.
        return _dateparser.parse(str(value), dayfirst=False, fuzzy=True).date()
    except (ValueError, OverflowError, TypeError):
        return None


def normalize_date(value: str | date | datetime | None) -> str | None:
    """Parse then return an ISO date string, or None."""
    d = parse_date(value)
    return d.isoformat() if d else None


def days_between(start: str | date | None, end: str | date | None) -> int | None:
    """Whole days from start to end (end - start). None if either is unparseable."""
    a, b = parse_date(start), parse_date(end)
    if a is None or b is None:
        return None
    return (b - a).days
