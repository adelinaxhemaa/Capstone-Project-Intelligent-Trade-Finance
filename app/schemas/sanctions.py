"""Agent E (Sanctions Screening)
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import Field

from app.schemas.common import RiskLevel, TFBaseModel
from app.schemas.findings import Finding


class EntityType(str, Enum):
    

    PARTY = "party"
    VESSEL = "vessel"
    COUNTRY = "country"
    BANK = "bank"


class ListSource(str, Enum):
    

    OFAC = "OFAC"
    EU = "EU"
    UN = "UN"


class ScreenedEntity(TFBaseModel):
    

    name: str
    entity_type: EntityType
    jurisdiction: Optional[str] = None


class SanctionsHit(TFBaseModel):
    

    entity: ScreenedEntity
    list_source: ListSource
    matched_name: str = Field(..., description="The list entry that matched")
    score: float = Field(..., ge=0.0, le=1.0, description="Match similarity")
    is_false_positive: bool = False
    detail: Optional[str] = None
    recommendation: Optional[str] = None
    finding_id: Optional[str] = None


class SanctionsScreen(TFBaseModel):
    

    run_id: str
    screened: list[ScreenedEntity] = Field(default_factory=list)
    hits: list[SanctionsHit] = Field(default_factory=list)
    country_risk: dict[str, RiskLevel] = Field(
        default_factory=dict, description="jurisdiction -> risk tier"
    )
    findings: list[Finding] = Field(default_factory=list)

    @property
    def has_active_hit(self) -> bool:
        return any(not h.is_false_positive for h in self.hits)
