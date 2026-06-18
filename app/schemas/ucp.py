"""Agent C (UCP 600 Compliance) output contract.

"""

from __future__ import annotations

from typing import Optional

from pydantic import Field

from app.schemas.common import TFBaseModel
from app.schemas.findings import Finding


class UCPCheck(TFBaseModel):
    

    rule_id: str = Field(..., description="Internal id, e.g. 'presentation_period'")
    article: str = Field(..., description="UCP reference, e.g. 'UCP600 Art. 14(c)'")
    description: str
    passed: bool
    detail: Optional[str] = Field(
        default=None, description="Why it passed/failed, in plain language"
    )
    finding_id: Optional[str] = Field(
        default=None, description="Linked Finding id when the check fails"
    )


class UCPResult(TFBaseModel):
    

    run_id: str
    checks: list[UCPCheck] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)

    @property
    def all_passed(self) -> bool:
        return all(c.passed for c in self.checks)
