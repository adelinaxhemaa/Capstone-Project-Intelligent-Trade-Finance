from __future__ import annotations
from app.schemas.common import BoundingBox, DocumentType
from app.schemas.context import EvidenceItem
from app.schemas.findings import EvidencePointer


def make_bbox(page: int, x0: float, y0: float, x1: float, y1: float) -> BoundingBox:
    return BoundingBox(page=page, x0=x0, y0=y0, x1=x1, y1=y1)


def make_evidence_item(
    field_name: str,
    source_file: str,
    document_type: DocumentType,
    bbox: BoundingBox | None = None,
    text_snippet: str | None = None,
) -> EvidenceItem:
    """For the universal evidence index (Agent A / B)."""
    return EvidenceItem(
        field_name=field_name,
        source_file=source_file,
        document_type=document_type,
        bbox=bbox,
        text_snippet=text_snippet,
    )


def make_pointer(
    source_file: str,
    document_type: DocumentType,
    field_name: str | None = None,
    bbox: BoundingBox | None = None,
    snippet: str | None = None,
) -> EvidencePointer:
    """For a Finding's evidence list (Agents C/D/E/H)."""
    return EvidencePointer(
        source_file=source_file,
        document_type=document_type,
        field_name=field_name,
        bbox=bbox,
        snippet=snippet,
    )


def pointer_from_item(item: EvidenceItem) -> EvidencePointer:
    """Convert an evidence-index item into a finding pointer."""
    return EvidencePointer(
        source_file=item.source_file,
        document_type=item.document_type,
        field_name=item.field_name,
        bbox=item.bbox,
        snippet=item.text_snippet,
    )
