from __future__ import annotations
from typing import Optional
from pydantic import Field
from app.schemas.common import BoundingBox, DocumentType, TFBaseModel


class ExtractedField(TFBaseModel):
    """A single field pulled from a document, with evidence and confidence."""

    name: str = Field(..., description="Canonical field name, e.g. 'invoice_amount'")
    value: Optional[str] = Field(
        default=None, description="Raw extracted value as text; None if not found"
    )
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Extraction confidence in [0, 1]"
    )
    source_file: str = Field(..., description="Document the value came from")
    document_type: DocumentType
    bbox: Optional[BoundingBox] = Field(
        default=None, description="Where on the page the value sits"
    )
    low_confidence: bool = Field(
        default=False,
        description="True when confidence is below the policy-pack cutoff "
        "(routes to manual review / optional LLM fallback)",
    )
    llm_derived: bool = Field(
        default=False,
        description="True if resolved by the LLM fallback rather than rules",
    )


class DocumentExtraction(TFBaseModel):
    """All fields extracted from one document."""

    source_file: str
    document_type: DocumentType
    synthetic: bool = Field(
        default=False, description="True if this doc used the synthetic-data fallback"
    )
    fields: list[ExtractedField] = Field(default_factory=list)


class ExtractedDocs(TFBaseModel):
    """Aggregated extraction across every document in the bundle."""

    run_id: str
    documents: list[DocumentExtraction] = Field(default_factory=list)

    def all_fields(self) -> list[ExtractedField]:
        """Flatten fields across all documents (for cross-doc matching)."""
        return [f for doc in self.documents for f in doc.fields]

    def fields_named(self, name: str) -> list[ExtractedField]:
        """Every occurrence of a field name across documents."""
        return [f for f in self.all_fields() if f.name == name]
