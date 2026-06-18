"""Decision logger.

Captures *why* the orchestrator reached its decision: the action, the rationale,
the severity breakdown, and the specific findings that drove the outcome. This
is the audit answer to "explain this decision".
"""

from __future__ import annotations

from typing import Any

_DRIVER_SEVERITIES = {"critical", "major"}


def decision_chain(state: dict[str, Any]) -> dict[str, Any]:
    decision = state.get("final_decision", {})
    findings = decision.get("findings", state.get("findings", []))
    severity_counts = {s: sum(1 for f in findings if f.get("severity") == s)
                       for s in ("critical", "major", "minor", "info")}
    drivers = [
        {"id": f["id"], "severity": f["severity"], "type": f["type"], "title": f["title"]}
        for f in findings if f.get("severity") in _DRIVER_SEVERITIES
    ]
    return {
        "action": decision.get("action"),
        "rationale": decision.get("rationale"),
        "route": state.get("route", "continue"),
        "severity_counts": severity_counts,
        "drivers": drivers,
    }
