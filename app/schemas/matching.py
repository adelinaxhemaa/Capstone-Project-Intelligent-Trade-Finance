from __future__ import annotations
from enum import Enum
from typing import Optional
from pydantic import Field
from app.schemas.common import TFBaseModel
from app.schemas.findings import Finding


class MatchType(str, Enum):
    """How a field was compared across documents."""

    EXACT = "exact"
    FUZZY = "fuzzy"
    TOLERANCE = "tolerance"


class FieldMatch(TFBaseModel):
    """Result of comparing one field across the documents that carry it."""

    field_name: str
    match_type: MatchType
    matched: bool
    values: dict[str, Optional[str]] = Field(
        default_factory=dict, description="source_file -> value compared"
    )
    score: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Fuzzy similarity or tolerance ratio when applicable",
    )
    detail: Optional[str] = None
    finding_id: Optional[str] = Field(
        default=None, description="Linked Finding id when matched is False"
    )


class MatchResult(TFBaseModel):
    """All cross-document field comparisons for a run."""

    run_id: str
    matches: list[FieldMatch] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)

    @property
    def all_matched(self) -> bool:
        return all(m.matched for m in self.matches)
