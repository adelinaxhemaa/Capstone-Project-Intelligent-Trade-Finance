"""Agents C, D, E, and H all emit Findings, so Agent H can merge,
deduplicate, and rank them .

"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import Field

from app.schemas.common import BoundingBox, DocumentType, Severity, TFBaseModel


class FindingType(str, Enum):
    

    UCP_VIOLATION = "ucp_violation"
    CROSS_DOC_MISMATCH = "cross_doc_mismatch"
    TOLERANCE_BREACH = "tolerance_breach"
    SANCTIONS_HIT = "sanctions_hit"
    LOW_CONFIDENCE = "low_confidence"
    FORMAT = "format"
    OTHER = "other"


class EvidencePointer(TFBaseModel):
    

    source_file: str
    document_type: DocumentType
    field_name: Optional[str] = None
    bbox: Optional[BoundingBox] = None
    snippet: Optional[str] = None


class Finding(TFBaseModel):
    

    id: str = Field(
        ...,
        description="Deterministic id (hash of type+location+value) from utils/ids",
    )
    type: FindingType
    severity: Severity
    title: str
    description: str
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    source_agent: str = Field(..., description="e.g. 'agent_c_ucp'")
    evidence: list[EvidencePointer] = Field(default_factory=list)
    recommendation: Optional[str] = None
    open_questions: list[str] = Field(
        default_factory=list,
        description="Where automation is unsure and a human should look",
    )
