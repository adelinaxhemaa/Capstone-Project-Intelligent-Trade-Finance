from __future__ import annotations

import re


def parse_amount(value: str | float | int | None) -> float | None:
    """Parse a money-ish string to a float. Strips currency symbols, codes,
    thousands separators. Returns None if nothing numeric is found."""
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value)
    # Remove everything except digits, dot, minus.
    cleaned = re.sub(r"[^\d.\-]", "", text.replace(",", ""))
    if cleaned in ("", "-", ".", "-."):
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def pct_difference(value: float, reference: float) -> float | None:
    """Signed percentage difference of value vs reference. None if reference is 0."""
    if reference == 0:
        return None
    return (value - reference) / reference * 100.0


def within_tolerance(
    value: float | str | None,
    reference: float | str | None,
    tolerance_pct: float,
) -> tuple[bool, float | None]:
    """Return (is_within, signed_pct_diff). If either amount can't be parsed,
    returns (False, None)."""
    v, r = parse_amount(value), parse_amount(reference)
    if v is None or r is None:
        return False, None
    diff = pct_difference(v, r)
    if diff is None:
        return False, None
    return abs(diff) <= tolerance_pct, diff
