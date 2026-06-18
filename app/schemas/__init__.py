"""Schema package: the frozen data contracts between all six agents"""

from app.schemas.common import (
    BoundingBox,
    DocumentType,
    RiskLevel,
    Severity,
    TFBaseModel,
)
from app.schemas.context import (
    ClassifiedDocument,
    ContextPacket,
    EvidenceIndex,
    EvidenceItem,
    LCTerms,
    Party,
    ShipmentParams,
)
from app.schemas.decision import (
    Action,
    FinalDecision,
    Metrics,
    SwiftDraft,
    SwiftMessageType,
)
from app.schemas.extraction import DocumentExtraction, ExtractedDocs, ExtractedField
from app.schemas.findings import EvidencePointer, Finding, FindingType
from app.schemas.matching import FieldMatch, MatchResult, MatchType
from app.schemas.sanctions import (
    EntityType,
    ListSource,
    SanctionsHit,
    SanctionsScreen,
    ScreenedEntity,
)
from app.schemas.ucp import UCPCheck, UCPResult

__all__ = [
    # common
    "TFBaseModel",
    "BoundingBox",
    "DocumentType",
    "Severity",
    "RiskLevel",
    # context
    "ContextPacket",
    "ClassifiedDocument",
    "Party",
    "ShipmentParams",
    "LCTerms",
    "EvidenceIndex",
    "EvidenceItem",
    # extraction
    "ExtractedField",
    "DocumentExtraction",
    "ExtractedDocs",
    # findings
    "Finding",
    "FindingType",
    "EvidencePointer",
    # ucp
    "UCPCheck",
    "UCPResult",
    # matching
    "FieldMatch",
    "MatchResult",
    "MatchType",
    # sanctions
    "ScreenedEntity",
    "SanctionsHit",
    "SanctionsScreen",
    "EntityType",
    "ListSource",
    # decision
    "FinalDecision",
    "Action",
    "SwiftDraft",
    "SwiftMessageType",
    "Metrics",
]
