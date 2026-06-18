"""Shared LLM client (LangChain).
"""

from __future__ import annotations

from typing import Any, TypeVar

from pydantic import BaseModel

from app.config import get_settings

_CALL_LOG: list[dict[str, Any]] = []

T = TypeVar("T", bound=BaseModel)


def is_enabled() -> bool:
    s = get_settings()
    if not s.use_llm:
        return False
    if s.llm_provider == "openai" and not s.openai_api_key:
        return False
    return True


def call_log() -> list[dict[str, Any]]:
    
    return list(_CALL_LOG)


def _build_model():
    
    s = get_settings()
    if s.llm_provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(model="claude-3-5-sonnet-latest", temperature=0)
    # default: openai
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(model="gpt-4o-mini", temperature=0, api_key=s.openai_api_key)


def invoke_structured(prompt: str, schema: type[T]) -> T | None:
    
    if not is_enabled():
        return None
    try:
        model = _build_model().with_structured_output(schema)
        result = model.invoke(prompt)
        _CALL_LOG.append({
            "prompt": prompt[:2000],
            "schema": schema.__name__,
            "result": result.model_dump() if isinstance(result, BaseModel) else str(result),
        })
        return result  # type: ignore[return-value]
    except Exception as exc:  # network/key/parse error → degrade to rules
        _CALL_LOG.append({"prompt": prompt[:2000], "error": f"{type(exc).__name__}: {exc}"})
        return None
