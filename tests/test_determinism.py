"""Determinism test.
"""

import os
import tempfile
from functools import lru_cache
from pathlib import Path

import pytest

# Deterministic artifacts that must match byte-for-byte.
_DETERMINISTIC = [
    "extracted_docs.json",
    "ucp_result.json",
    "match_result.json",
    "sanctions_screen.json",
    "final_decision.json",
]


def _run_into(base_dir: str, run_id: str, bundle: Path) -> Path:
    
    os.environ["RUN_DIR"] = base_dir
    os.environ["USE_LLM"] = "false"
    import app.config as config
    config.get_settings.cache_clear()
    # policy loader caches per-jurisdiction; safe to keep, but clear to be sure
    from app.tools import policy_loader
    policy_loader._base_plus_regional.cache_clear()
    from app.pipeline import run_pipeline
    run_pipeline(bundle, run_id=run_id)
    return Path(base_dir) / run_id


@pytest.fixture(scope="module")
def clean_bundle():
    from samples.make_sample_bundle import make_clean_bundle
    return make_clean_bundle(Path(tempfile.mkdtemp()))


def test_decision_artifacts_are_byte_identical(clean_bundle):
    dir_a = _run_into(tempfile.mkdtemp(), "det", clean_bundle)
    dir_b = _run_into(tempfile.mkdtemp(), "det", clean_bundle)

    for name in _DETERMINISTIC:
        a = (dir_a / name).read_bytes()
        b = (dir_b / name).read_bytes()
        assert a == b, f"Non-deterministic artifact: {name}"


def test_finding_ids_are_stable(clean_bundle):
    """Finding IDs are content hashes, so they must be reproducible."""
    import json
    dir_a = _run_into(tempfile.mkdtemp(), "det", clean_bundle)
    dir_b = _run_into(tempfile.mkdtemp(), "det", clean_bundle)
    fa = json.loads((dir_a / "final_decision.json").read_text())
    fb = json.loads((dir_b / "final_decision.json").read_text())
    assert [x["id"] for x in fa["findings"]] == [x["id"] for x in fb["findings"]]
