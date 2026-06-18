"""Template rendering helper (shared by reports and the audit log)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

_TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"


@lru_cache(maxsize=1)
def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR)),
        autoescape=select_autoescape(enabled_extensions=()),  # plain markdown, no HTML escaping
        trim_blocks=True,
        lstrip_blocks=True,
    )


def render_template(name: str, context: dict[str, Any]) -> str:
    return _env().get_template(name).render(**context)
