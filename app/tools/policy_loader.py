"""Policy loading and layering."""

from __future__ import annotations

from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from app.config import ROOT_DIR

CONFIG_DIR = ROOT_DIR / "config"


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge override into a copy of base (override wins)."""
    result = deepcopy(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result


@lru_cache(maxsize=8)
def _base_plus_regional(jurisdiction: str | None) -> dict[str, Any]:
    policy = _load_yaml(CONFIG_DIR / "policy_pack.yaml")
    if jurisdiction:
        regional = _load_yaml(CONFIG_DIR / "regional" / f"{jurisdiction.lower()}_policy.yaml")
        policy = _deep_merge(policy, regional)
    return policy


def load_policy(
    jurisdiction: str | None = None,
    bundle_override: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return the merged policy dict for this run."""
    policy = deepcopy(_base_plus_regional(jurisdiction))
    if bundle_override:
        policy = _deep_merge(policy, bundle_override)
    return policy


def applied_layers(jurisdiction: str | None, bundle_override: dict | None) -> list[str]:
    """For the audit log: which policy layers were applied, in order."""
    layers = ["base:policy_pack.yaml"]
    if jurisdiction and (CONFIG_DIR / "regional" / f"{jurisdiction.lower()}_policy.yaml").exists():
        layers.append(f"regional:{jurisdiction.lower()}_policy.yaml")
    if bundle_override:
        layers.append("bundle:sanctions_policy")
    return layers
