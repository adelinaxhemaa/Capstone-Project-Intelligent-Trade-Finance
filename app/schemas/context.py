
from __future__ import annotations

from typing import Optional

from pydantic import Field

from app.schemas.common import BoundingBox, DocumentType, TFBaseModel


class ClassifiedDocument(TFBaseModel):
    

    source_file: str = Field(..., description="Filename inside the bundle")
    document_type: DocumentType
    page_count: int = Field(..., ge=0)


class Party(TFBaseModel):
    

    name: str
    role: str = Field(..., description="e.g. applicant, beneficiary, issuing_bank")
    country: Optional[str] = None
    address: Optional[str] = None


class ShipmentParams(TFBaseModel):
    

    port_of_loading: Optional[str] = None
    port_of_discharge: Optional[str] = None
    latest_shipment_date: Optional[str] = None  
    partial_shipment_allowed: Optional[bool] = None
    transhipment_allowed: Optional[bool] = None


class LCTerms(TFBaseModel):
    

    lc_number: Optional[str] = None
    issue_date: Optional[str] = None  
    expiry_date: Optional[str] = None  
    expiry_place: Optional[str] = None
    amount: Optional[float] = None
    currency: Optional[str] = None
    tolerance_pct: Optional[float] = Field(
        default=None, description="Allowed +/- variance on amount, e.g. 5.0"
    )
    presentation_period_days: Optional[int] = Field(
        default=None, description="Days to present after shipment (default 21 if unset)"
    )
    documents_required: list[str] = Field(default_factory=list)


class ContextPacket(TFBaseModel):
    

    run_id: str
    documents: list[ClassifiedDocument] = Field(default_factory=list)
    lc_terms: LCTerms = Field(default_factory=LCTerms)
    parties: list[Party] = Field(default_factory=list)
    shipment: ShipmentParams = Field(default_factory=ShipmentParams)
    presentation_date: str | None = Field(
        default=None, description="Date documents were presented (from manifest); drives the 21-day rule",
    )
    applicable_rules: list[str] = Field(
        default_factory=lambda: ["UCP600"],
        description="Rule sets in force, e.g. UCP600, eUCP",
    )
    risk_flags: list[str] = Field(
        default_factory=list,
        description="Intake heuristics hits, e.g. 'new_counterparty'",
    )


class EvidenceItem(TFBaseModel):
   

    field_name: str
    source_file: str
    document_type: DocumentType
    bbox: Optional[BoundingBox] = None
    text_snippet: Optional[str] = None


class EvidenceIndex(TFBaseModel):
    

    run_id: str
    items: list[EvidenceItem] = Field(default_factory=list)

    def find(self, field_name: str) -> list[EvidenceItem]:
        """Return all evidence items for a given field name."""
        return [item for item in self.items if item.field_name == field_name]
