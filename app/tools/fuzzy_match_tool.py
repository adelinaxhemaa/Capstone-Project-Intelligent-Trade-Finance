from __future__ import annotations
from rapidfuzz import fuzz, process


def _norm(s: str | None) -> str:
    return (s or "").strip().lower()


def similarity(a: str | None, b: str | None) -> float:
    """Token-sort ratio as a 0..100 score (order-insensitive)."""
    return float(fuzz.token_sort_ratio(_norm(a), _norm(b)))


def set_similarity(a: str | None, b: str | None) -> float:
    """Token-set ratio (0..100). Subset-aware: handles suffixes like
    'Ltd'/'Co'/'LLC' — better for entity/sanctions name screening."""
    return float(fuzz.token_set_ratio(_norm(a), _norm(b)))


def is_match(a: str | None, b: str | None, threshold: float = 85.0) -> bool:
    """True if the two strings score at/above the threshold (0..100)."""
    return similarity(a, b) >= threshold


def best_match(
    query: str | None,
    choices: list[str],
    threshold: float = 85.0,
) -> tuple[str, float] | None:
    """Return (best_choice, score) above threshold, else None."""
    if not query or not choices:
        return None
    result = process.extractOne(
        _norm(query),
        {i: _norm(c) for i, c in enumerate(choices)},
        scorer=fuzz.token_sort_ratio,
    )
    if result is None:
        return None
    _matched_norm, score, idx = result
    if score >= threshold:
        return choices[idx], float(score)
    return None
