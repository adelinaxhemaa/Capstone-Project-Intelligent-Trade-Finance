"""Report builder.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.config import get_settings
from app.llm import narrator
from app.reports.render import render_template
from app.utils.io import write_text


def build_reports(state: dict[str, Any], run_dir: str | Path) -> dict[str, Path]:
    run_dir = Path(run_dir)
    decision = state.get("final_decision", {})
    findings = decision.get("findings", state.get("findings", []))
    action = decision.get("action", "unknown")
    rationale = decision.get("rationale", "")

    narrative = None
    if get_settings().use_llm:
        narrative = narrator.narrate(action, rationale, findings)

    common = {
        "run_id": state.get("run_id", "run"),
        "action": action,
        "rationale": rationale,
        "narrative": narrative,
        "findings": findings,
        "metrics": decision.get("metrics", {}),
        "route": state.get("route", "continue"),
        "sanctions": state.get("sanctions_screen", {}),
    }

    disc = write_text(run_dir / "discrepancies.md", render_template("discrepancies.md.j2", common))
    rep = write_text(run_dir / "reports" / "run_report.md", render_template("run_report.md.j2", common))
    return {"discrepancies": disc, "run_report": rep}
