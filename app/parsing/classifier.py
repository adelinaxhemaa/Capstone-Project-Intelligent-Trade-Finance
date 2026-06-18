from __future__ import annotations
from app.parsing.pdf_parser import ParsedDocument
from app.schemas.common import DocumentType

# Ordered: more specific phrases first. Each maps signal keywords → type.
_SIGNALS: list[tuple[DocumentType, tuple[str, ...]]] = [
    (DocumentType.LETTER_OF_CREDIT,
     ("documentary credit", "letter of credit", "irrevocable credit", "mt700", "issuing bank")),
    (DocumentType.BILL_OF_LADING,
     ("bill of lading", "b/l no", "shipped on board", "port of loading", "port of discharge")),
    (DocumentType.PACKING_LIST,
     ("packing list", "net weight", "gross weight", "number of packages")),
    (DocumentType.CERTIFICATE_OF_ORIGIN,
     ("certificate of origin", "country of origin", "chamber of commerce")),
    (DocumentType.INSPECTION_CERTIFICATE,
     ("inspection certificate", "certificate of inspection", "pre-shipment inspection")),
    (DocumentType.COMMERCIAL_INVOICE,
     ("commercial invoice", "invoice no", "invoice number", "unit price")),
]


def classify(parsed: ParsedDocument, manifest_hint: str | None = None) -> DocumentType:
    """Return the most likely document type from the text (manifest hint breaks ties)."""
    text = parsed.full_text.lower()

    scores: dict[DocumentType, int] = {}
    for dtype, keywords in _SIGNALS:
        hits = sum(1 for kw in keywords if kw in text)
        if hits:
            scores[dtype] = hits

    if scores:
        best = max(scores.items(), key=lambda kv: kv[1])
        # If the manifest hinted a type that also scored, prefer it on ties.
        if manifest_hint:
            try:
                hinted = DocumentType(manifest_hint)
                if scores.get(hinted, 0) == best[1]:
                    return hinted
            except ValueError:
                pass
        return best[0]

    # No content signal — fall back to the manifest hint if valid.
    if manifest_hint:
        try:
            return DocumentType(manifest_hint)
        except ValueError:
            pass
    return DocumentType.UNKNOWN
