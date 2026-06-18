"""Agent C — UCP 600 Compliance.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.rules import ucp600
from app.schemas.ucp import UCPResult
from app.tools.policy_loader import load_policy
from app.utils.io import write_json


def run_agent_c(state: dict[str, Any], run_dir: str | Path | None = None) -> dict[str, Any]:
    extracted = state.get("extracted_docs", {})
    context = state.get("context_packet", {})
    policy = load_policy(state.get("jurisdiction"))
    run_id = state.get("run_id", "run")

    checks, findings = ucp600.run_checks(extracted, context, policy)
    m_checks, m_findings = ucp600.mandatory_field_checks(extracted)
    checks += m_checks
    findings += m_findings

    result = UCPResult(run_id=str(run_id), checks=checks, findings=findings)

    if run_dir is not None:
        write_json(Path(run_dir) / "ucp_result.json", result)

    return {
        "ucp_result": result.model_dump(mode="json"),
        "findings": [f.model_dump(mode="json") for f in findings],
        "trace": [{
            "agent": "agent_c_ucp",
            "checks": len(checks),
            "passed": sum(1 for c in checks if c.passed),
            "findings": len(findings),
        }],
    }
