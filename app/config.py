"""Application settings.

Loads `.env` once and exposes a typed, cached settings object the rest of
the app reads from. 
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv


ROOT_DIR = Path(__file__).resolve().parents[1]


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    use_llm: bool
    llm_provider: str
    openai_api_key: str | None
    ocr_engine: str
    tesseract_cmd: str | None
    run_dir: Path

    @staticmethod
    def load() -> "Settings":
        load_dotenv(ROOT_DIR / ".env")
        run_dir = Path(os.getenv("RUN_DIR", "runs"))
        if not run_dir.is_absolute():
            run_dir = ROOT_DIR / run_dir
        return Settings(
            use_llm=_as_bool(os.getenv("USE_LLM"), default=False),
            llm_provider=os.getenv("LLM_PROVIDER", "openai").strip().lower(),
            openai_api_key=os.getenv("OPENAI_API_KEY") or None,
            ocr_engine=os.getenv("OCR_ENGINE", "tesseract").strip().lower(),
            tesseract_cmd=os.getenv("TESSERACT_CMD") or None,
            run_dir=run_dir,
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached settings singleton. Call this everywhere instead of reading env."""
    return Settings.load()
