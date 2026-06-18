from __future__ import annotations
from app.parsing.pdf_parser import ParsedDocument

# Words-per-page that we consider clearly "born-digital".
_WORDS_PER_PAGE_FULL = 30.0


def _alpha_ratio(text: str) -> float:
    if not text:
        return 0.0
    alpha = sum(c.isalpha() or c.isspace() for c in text)
    return alpha / len(text)


def score(parsed: ParsedDocument) -> float:
    """Return a 0..1 text-quality score for a born-digital parse."""
    if parsed.page_count == 0:
        return 0.0
    words_per_page = parsed.word_count / parsed.page_count
    coverage = min(1.0, words_per_page / _WORDS_PER_PAGE_FULL)
    legibility = _alpha_ratio(parsed.full_text)
    # Coverage dominates; legibility is a mild damper for garbled text.
    return round(coverage * (0.5 + 0.5 * legibility), 4)


def needs_ocr(parsed: ParsedDocument, cutoff: float) -> bool:
    """True if the born-digital text is below the OCR cutoff."""
    return score(parsed) < cutoff