"""End-to-end demo, including the configurability requirement.

Runs three things:
  1. a clean bundle  -> HONOUR
  2. the amount-tolerance bundle -> ESCALATE (invoice 30% over, tolerance 5%)
  3. CONFIGURABILITY: raise the policy's amount_tolerance_pct to 35 and re-run
     the SAME bundle -> the decision flips to HONOUR, with no code change.

Run from the repo root:  python demo.py   (or: make demo)
"""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("USE_LLM", "false")  # deterministic, no key needed

from app.config import ROOT_DIR
from app.pipeline import run_pipeline
from app.tools import policy_loader
from samples.make_sample_bundle import make_amount_tolerance_bundle, make_clean_bundle

POLICY_FILE = ROOT_DIR / "config" / "policy_pack.yaml"


def _decision(bundle: Path, run_id: str) -> tuple[str, int]:
    state = run_pipeline(bundle, run_id=run_id)
    dec = state["final_decision"]
    return dec["action"], len(dec["findings"])


def _set_tolerance(pct: float) -> None:
    """Edit amount_tolerance_pct in the policy pack and clear the policy cache."""
    lines = POLICY_FILE.read_text(encoding="utf-8").splitlines()
    out = []
    for ln in lines:
        if ln.strip().startswith("amount_tolerance_pct:"):
            out.append(f"amount_tolerance_pct: {pct}")
        else:
            out.append(ln)
    POLICY_FILE.write_text("\n".join(out) + "\n", encoding="utf-8")
    policy_loader._base_plus_regional.cache_clear()


def main() -> None:
    base = ROOT_DIR / "tests" / "bundles"
    clean = make_clean_bundle(base)
    tol = make_amount_tolerance_bundle(base)

    print("=" * 64)
    print("INTELLIGENT TRADE FINANCE — DEMO")
    print("=" * 64)

    act, n = _decision(clean, "demo_clean")
    print(f"\n1) Clean bundle              -> {act.upper()} ({n} findings)")

    act, n = _decision(tol, "demo_tol_default")
    print(f"2) Amount 30% over (tol 5%)  -> {act.upper()} ({n} findings)")

    print("\n3) CONFIGURABILITY: raise amount_tolerance_pct 5 -> 35, re-run the SAME bundle")
    original = POLICY_FILE.read_text(encoding="utf-8")
    try:
        _set_tolerance(35.0)
        act, n = _decision(tol, "demo_tol_raised")
        print(f"   Amount 30% over (tol 35%) -> {act.upper()} ({n} findings)  <- decision flipped via config only")
    finally:
        POLICY_FILE.write_text(original, encoding="utf-8")  # restore
        policy_loader._base_plus_regional.cache_clear()

    print("\nPolicy restored. Artifacts written under runs/. Done.")
    print("=" * 64)


if __name__ == "__main__":
    main()
