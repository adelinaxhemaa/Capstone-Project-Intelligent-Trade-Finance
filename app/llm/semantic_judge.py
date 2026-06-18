from __future__ import annotations
from pydantic import BaseModel, Field
from app.llm.client import invoke_structured


class SemanticVerdict(BaseModel):
    same_goods: bool = Field(description="True if the two descriptions plausibly refer to the same goods")
    ambiguous: bool = Field(description="True if it cannot be determined with confidence")
    reason: str = Field(description="Brief explanation")


_PROMPT = """In trade finance, goods descriptions across documents may be worded
differently yet refer to the same goods. Do these two descriptions plausibly
refer to the same goods? Answer for flagging only; do not make a compliance ruling.

A: {a}
B: {b}"""


def judge(desc_a: str, desc_b: str) -> SemanticVerdict | None:
    """None if the LLM is disabled or the call fails."""
    return invoke_structured(_PROMPT.format(a=desc_a, b=desc_b), SemanticVerdict)