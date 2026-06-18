"""Agent H (Triage & Orchestration).
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import Field

from app.schemas.common import TFBaseModel
from app.schemas.findings import Finding


class Action(str, Enum):
    

    HONOUR = "honour"
    REFUSE = "refuse"
    ESCALATE = "escalate"
    MANUAL_REVIEW = "manual_review"


class SwiftMessageType(str, Enum):
    MT700 = "MT700"
    MT752 = "MT752"


class SwiftDraft(TFBaseModel):
    

    message_type: SwiftMessageType
    content: str


class Metrics(TFBaseModel):
    

    documents_processed: int = 0
    fields_extracted: int = 0
    low_confidence_count: int = 0
    discrepancy_count: int = 0
    sanctions_hit_count: int = 0
    discrepancy_rate: Optional[float] = Field(
        default=None, description="discrepancies per document processed"
    )
    throughput: Optional[float] = Field(
        default=None, description="documents per second (reporting only)"
    )
    extraction_accuracy: Optional[float] = Field(
        default=None, ge=0.0, le=1.0, description="vs. ground truth when available"
    )
    throughput_docs_per_sec: Optional[float] = Field(
        default=None, description="documents processed per second"
    )
    processing_seconds: Optional[float] = Field(
        default=None, description="For reporting only; never used in decision logic"
    )


class FinalDecision(TFBaseModel):
    

    run_id: str
    action: Action
    rationale: str
    findings: list[Finding] = Field(
        default_factory=list, description="Merged, deduplicated, ranked"
    )
    swift_draft: Optional[SwiftDraft] = None
    metrics: Metrics = Field(default_factory=Metrics)
