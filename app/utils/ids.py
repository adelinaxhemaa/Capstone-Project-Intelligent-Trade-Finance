"""Deterministic identifiers"""

from __future__ import annotations

import hashlib


def deterministic_id(*parts: object, length: int = 12) -> str:
    """Stable short hex id from the given parts."""
    joined = "|".join("" if p is None else str(p) for p in parts)
    digest = hashlib.sha256(joined.encode("utf-8")).hexdigest()
    return digest[:length]


def finding_id(finding_type: str, location: str, value: object = "") -> str:
    """Convenience wrapper for Finding IDs."""
    return deterministic_id(finding_type, location, value)
