from __future__ import annotations
import re
from app.utils.dates import normalize_date

_FIELD_TAG = re.compile(r"\(\s*field\s*\d+[a-z]?\s*\)", re.I)
_PARENS = re.compile(r"\([^)]*\)")
_CURRENCIES = {"USD", "EUR", "GBP", "JPY", "CHF", "CNY", "AUD", "CAD", "SEK",
               "NOK", "SGD", "HKD", "AED", "INR", "DKK", "PLN"}
_DATE_RE = re.compile(
    r"(\d{4}-\d{2}-\d{2}|\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4}|\d{1,2}[/.]\d{1,2}[/.]\d{2,4})"
)
_AMOUNT_RE = re.compile(r"(\d{1,3}(?:,\d{3})+(?:\.\d{2})?|\d+\.\d{2}|\d{4,})")
_TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9\-/]{3,}")
_CONNECTORS = {"exporter", "importer", "amount", "and place", "and date", "place"}


def _clean(s: str) -> str:
    """Strip parentheticals (SWIFT tags like '(Field 20)' and labels like
    '(Beneficiary)') and leading separators."""
    return _PARENS.sub(" ", s).strip(" \t:-/").strip()


def _typed_value(sources: list[str], kind: str) -> str | None:
    if kind == "id":
        for s in sources:
            for m in _TOKEN_RE.finditer(s):
                tok = m.group(0)
                if any(ch.isdigit() for ch in tok):
                    return tok
        return None
    if kind == "date":
        for s in sources:
            m = _DATE_RE.search(s)
            if m:
                iso = normalize_date(m.group(1))
                if iso:
                    return iso
        return None
    if kind == "amount":
        for s in sources:
            m = _AMOUNT_RE.search(s)
            if m:
                return m.group(1)
        return None
    if kind == "currency":
        for s in sources:
            for m in re.finditer(r"\b([A-Za-z]{3})\b", s):
                if m.group(1).upper() in _CURRENCIES:
                    return m.group(1).upper()
        return None
    if kind == "flag":
        joined = " ".join(sources).lower()
        if "prohibit" in joined or "not allow" in joined or "not permit" in joined:
            return "prohibited"
        if "allow" in joined or "permit" in joined:
            return "allowed"
        return None
    # name / text
    for s in sources:
        c = _clean(s)
        if not c or c.startswith("("):
            continue
        if kind == "name":
            if len(c) >= 3 and any(ch.isalpha() for ch in c) and c.lower() not in _CONNECTORS:
                return c[:80]
        else:  # text
            if len(c) >= 2:
                return c[:160]
    return None


def extract_value(full_text: str, label_patterns: list[str], kind: str) -> str | None:
    """Find the first label match that yields a VALID value of the given kind.
    Looks at the rest of the label's line and the next two non-empty lines."""
    lines = full_text.splitlines()
    for i, line in enumerate(lines):
        for pat in label_patterns:
            m = re.search(pat, line, flags=re.IGNORECASE)
            if not m:
                continue
            region = line[m.end():]
            following: list[str] = []
            for j in range(i + 1, min(i + 4, len(lines))):
                t = lines[j].strip()
                if t:
                    following.append(t)
                if len(following) >= 2:
                    break
            val = _typed_value([region] + following, kind)
            if val is not None:
                return val
    return None
