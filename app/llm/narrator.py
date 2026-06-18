"""LLM narrator.

Writes a plain-English summary of an already-decided examination. Runs only
when USE_LLM=true. 
"""

from __future__ import annotations

from app.llm.client import invoke_structured
from pydantic import BaseModel, Field


class Narrative(BaseModel):
    summary: str = Field(description="2-4 sentence plain-English summary for a reviewer")


_PROMPT = """Summarize this trade-finance documentary-credit examination for a human
reviewer in 2-4 sentences. State the decision and the main reasons. Do not add
facts beyond those given; do not change the decision.

Decision: {action}
Rationale: {rationale}
Findings:
{findings}"""


def narrate(action: str, rationale: str, findings: list[dict]) -> str | None:
    """Return a prose summary, or None if the LLM is disabled/failed."""
    flist = "\n".join(f"- [{f.get('severity')}] {f.get('title')}: {f.get('description')}"
                      for f in findings) or "- none"
    result = invoke_structured(
        _PROMPT.format(action=action, rationale=rationale, findings=flist), Narrative
    )
    return result.summary if result else None
