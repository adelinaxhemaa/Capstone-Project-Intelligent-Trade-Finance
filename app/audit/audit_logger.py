"""Audit-log assembly.

Renders runs/<id>/audit_log.md from the execution trace + decision chain +
findings, via the Jinja2 template. This is the step-by-step, evidence-linked
record the brief's auditability criterion calls for.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.audit import decision_logger, tracer
from app.reports.render import render_template
from app.utils.io import write_text


def write_audit_log(state: dict[str, Any], run_dir: str | Path) -> Path:
    context = state.get("context_packet", {})
    findings = state.get("final_decision", {}).get("findings", state.get("findings", []))
    md = render_template("audit_log.md.j2", {
        "run_id": state.get("run_id", "run"),
        "lc_terms": context.get("lc_terms", {}),
        "documents": context.get("documents", []),
        "trace_lines": tracer.trace_lines(state),
        "decision": decision_logger.decision_chain(state),
        "findings": findings,
        "applied_rules": context.get("applicable_rules", []),
    })
    return write_text(Path(run_dir) / "audit_log.md", md)
