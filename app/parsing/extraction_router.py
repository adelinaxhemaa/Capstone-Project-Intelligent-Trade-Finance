from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from app.parsing import ocr_parser, pdf_parser, quality_scorer
from app.tools.policy_loader import load_policy

@dataclass
class RoutedResult:
    document: pdf_parser.ParsedDocument
    quality_score: float
    ocr_used: bool
    route: str  # "born_digital" | "ocr" | "ocr_unavailable_fallback"

def route_document(
    path: str | Path,
    ocr_quality_cutoff: float | None = None,
) -> RoutedResult:
    if ocr_quality_cutoff is None:
        ocr_quality_cutoff = float(load_policy().get("ocr_quality_cutoff", 0.6))

    parsed = pdf_parser.parse_pdf(path)
    qscore = quality_scorer.score(parsed)

    if qscore >= ocr_quality_cutoff:
        parsed.notes.append(f"born-digital (quality {qscore} >= cutoff {ocr_quality_cutoff})")
        return RoutedResult(parsed, qscore, ocr_used=False, route="born_digital")

    # Low quality → try OCR
    ocr = ocr_parser.ocr_pdf(path)
    if ocr.method == "ocr":
        ocr.notes.append(f"routed to OCR (quality {qscore} < cutoff {ocr_quality_cutoff})")
        return RoutedResult(ocr, qscore, ocr_used=True, route="ocr")

    # OCR unavailable → fall back to whatever born-digital text we had
    parsed.notes.append(
        f"OCR unavailable ({'; '.join(ocr.notes)}); using born-digital text (quality {qscore})"
    )
    return RoutedResult(parsed, qscore, ocr_used=False, route="ocr_unavailable_fallback")
