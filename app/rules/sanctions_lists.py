"""Sanctions list loading + screening (pure functions).

"""

from __future__ import annotations

import csv
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.config import ROOT_DIR
from app.tools.fuzzy_match_tool import set_similarity, similarity

_DATA = ROOT_DIR / "app" / "data" / "sanctions"

# Map list-file -> ListSource enum value
_LIST_FILES = {
    "ofac_sdn.csv": "OFAC",
    "eu_consolidated.csv": "EU",
    "un_consolidated.csv": "UN",
}


@lru_cache(maxsize=1)
def _load_lists() -> dict[str, list[str]]:
    lists: dict[str, list[str]] = {}
    for filename, source in _LIST_FILES.items():
        path = _DATA / filename
        names: list[str] = []
        if path.exists():
            with open(path, newline="", encoding="utf-8") as f:
                names = [row["name"] for row in csv.DictReader(f) if row.get("name")]
        lists[source] = names
    return lists


@lru_cache(maxsize=1)
def _load_adverse_media() -> list[str]:
    path = _DATA / "adverse_media.csv"
    if not path.exists():
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return [row["name"] for row in csv.DictReader(f) if row.get("name")]


def screen_name(name: str, threshold: float) -> list[dict[str, Any]]:
    
    hits: list[dict[str, Any]] = []
    for source, names in _load_lists().items():
        for entry in names:
            sc = set_similarity(name, entry)
            if sc >= threshold:
                hits.append({"source": source, "matched_name": entry, "score": round(sc / 100, 3)})
    return hits


def adverse_media_hits(name: str, threshold: float) -> list[str]:
    
    return [entry for entry in _load_adverse_media() if set_similarity(name, entry) >= threshold]


def country_risk_tier(country: str | None, policy: dict[str, Any]) -> str | None:
    if not country:
        return None
    cr = policy.get("country_risk", {})
    c = country.strip()
    # match by ISO-ish code or name fragment
    for tier in ("high", "medium"):
        for entry in cr.get(tier, []):
            if entry.lower() == c.lower() or entry.lower() in c.lower():
                return tier
    return cr.get("default", "low")


def dual_use_terms(text: str, policy: dict[str, Any]) -> list[str]:
    if not text:
        return []
    low = text.lower()
    return [kw for kw in policy.get("dual_use_keywords", []) if kw.lower() in low]
