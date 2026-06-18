from __future__ import annotations
from pydantic import BaseModel, Field
from app.llm.client import invoke_structured


class FieldGuess(BaseModel):
    """Structured output schema for a single field extraction."""

    value: str | None = Field(description="The extracted value, or null if not present in the text")
    confidence: float = Field(ge=0.0, le=1.0, description="Model's confidence in the value")


_PROMPT = """Extract a single field value from a trade-finance document.

Field to extract: {field}
Document type: {doc_type}

Instructions:
- Return the value exactly as written in the document.
- The field label may be followed by a SWIFT tag like "(Field 20)" — ignore the
  tag and return the value after it.
- The value may be on the same line as the label OR on the line directly below it.
- Return null ONLY if the field genuinely does not appear anywhere in the text.
- Provide a confidence between 0 and 1.

--- DOCUMENT TEXT (may be noisy OCR) ---
{text}
--- END ---"""


def extract_field(field_name: str, doc_type: str, document_text: str) -> FieldGuess | None:
    """Attempt to recover one field via the LLM. None if LLM disabled/failed."""
    prompt = _PROMPT.format(field=field_name, doc_type=doc_type, text=document_text[:6000])
    return invoke_structured(prompt, FieldGuess)