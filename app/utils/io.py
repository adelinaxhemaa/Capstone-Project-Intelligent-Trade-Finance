"""Run-directory management and deterministic file I/O."""

from __future__ import annotations

import csv
import datetime as _dt
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from pydantic import BaseModel

from app.config import get_settings


def _jsonable(data: Any) -> Any:
    
    if isinstance(data, BaseModel):
        return data.model_dump(mode="json")
    return data


def write_json(path: str | Path, data: Any) -> Path:
    
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = _jsonable(data)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(payload, f, sort_keys=True, indent=2, ensure_ascii=False)
        f.write("\n")
    return path


def read_json(path: str | Path) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_text(path: str | Path, text: str) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
  
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    return path


def write_csv(
    path: str | Path,
    fieldnames: list[str],
    rows: Iterable[Mapping[str, Any]],
) -> Path:
    
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return path


def new_run_id() -> str:
    
    return "run_" + _dt.datetime.now().strftime("%Y%m%d_%H%M%S")


def create_run_dir(run_id: str | None = None) -> tuple[str, Path]:
    
    run_id = run_id or new_run_id()
    base = get_settings().run_dir / run_id
    (base / "input").mkdir(parents=True, exist_ok=True)
    (base / "reports").mkdir(parents=True, exist_ok=True)
    return run_id, base
