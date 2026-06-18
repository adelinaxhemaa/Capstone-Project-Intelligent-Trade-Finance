"""Agent H — Exception Triage & Lead Orchestration.

Consolidates every finding, deduplicates and ranks by severity, and applies
RULE-BASED logic to decide the action (honour / refuse / escalate / manual
review). Drafts the SWIFT message, emits the posting payload and a
human-readable discrepancies list, and assembles the final decision + metrics.
No LLM in the decision path (an optional narrative is added in stage 5).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.schemas.common import Severity
from app.schemas.decision import Action, FinalDecision, Metrics, SwiftDraft, SwiftMessageType
from app.schemas.findings import Finding
from app.tools.policy_loader import load_policy
from app.utils.io import write_json, write_text

_SEVERITY_RANK = {Severity.CRITICAL.value: 0, Severity.MAJOR.value: 1,
                  Severity.MINOR.value: 2, Severity.INFO.value: 3}


def _dedupe_rank(findings: list[dict]) -> list[dict]:
    by_id: dict[str, dict] = {}
    for f in findings:
        by_id.setdefault(f["id"], f)
    return sorted(by_id.values(), key=lambda f: _SEVERITY_RANK.get(f["severity"], 9))


def _decide(findings: list[dict], state: dict, policy: dict, lc_amount: float | None) -> tuple[Action, str]:
    sev = {f["severity"] for f in findings}
    types = {f["type"] for f in findings}
    threshold = float(policy.get("approval_threshold_amount", 1_000_000))

    if "sanctions_hit" in types:
        return Action.REFUSE, "Active sanctions match — transaction frozen and refused."
    if Severity.CRITICAL.value in sev:
        return Action.REFUSE, "Critical discrepancy present — documents refused."
    if Severity.MAJOR.value in sev:
        return Action.ESCALATE, "Major discrepancy present — escalate to applicant for waiver."
    if state.get("route") == "manual_review":
        return Action.MANUAL_REVIEW, "Low-confidence extraction — routed for manual review."
    if lc_amount is not None and lc_amount > threshold:
        return Action.ESCALATE, f"Amount exceeds approval threshold ({threshold:.0f}) — manual approval required."
    if Severity.MINOR.value in sev:
        return Action.HONOUR, "Only minor discrepancies — honour with noted observations."
    return Action.HONOUR, "Documents comply with the credit terms — honour."


def _swift_draft(action: Action, context: dict, lc_amount: float | None) -> SwiftDraft:
    lc = context.get("lc_terms", {})
    ref = lc.get("lc_number") or "N/A"
    cur = lc.get("currency") or "USD"
    amt = lc.get("amount") or lc_amount or 0
    if action == Action.HONOUR:
        content = (
            f":20:{ref}\n"
            f":32B:{cur}{amt:,.2f}\n"
            ":77A:DOCUMENTS COMPLYING. AUTHORISATION TO PAY/ACCEPT/NEGOTIATE.\n"
        )
        return SwiftDraft(message_type=SwiftMessageType.MT752, content=content)
    # Non-honour: draft a credit reference summary (real-world refusal would be MT734).
    content = (
        f":20:{ref}\n"
        f":32B:{cur}{amt:,.2f}\n"
        f":77J:DECISION={action.value.upper()}. SEE DISCREPANCIES. "
        "(NOTE: a real refusal would be sent as MT734.)\n"
    )
    return SwiftDraft(message_type=SwiftMessageType.MT700, content=content)


def run_agent_h(state: dict[str, Any], run_dir: str | Path | None = None) -> dict[str, Any]:
    context = state.get("context_packet", {})
    extracted = state.get("extracted_docs", {})
    sanctions = state.get("sanctions_screen", {})
    policy = load_policy(state.get("jurisdiction"))
    run_id = state.get("run_id", "run")

    findings = _dedupe_rank(state.get("findings", []))
    lc_amount = context.get("lc_terms", {}).get("amount")

    action, rationale = _decide(findings, state, policy, lc_amount)
    swift = _swift_draft(action, context, lc_amount)

    docs = extracted.get("documents", [])
    all_fields = [f for d in docs for f in d.get("fields", [])]
    discrepancy_count = sum(1 for f in findings if f["severity"] in (Severity.CRITICAL.value, Severity.MAJOR.value, Severity.MINOR.value))
    metrics = Metrics(
        documents_processed=len(docs),
        fields_extracted=len(all_fields),
        low_confidence_count=sum(1 for f in all_fields if f.get("low_confidence")),
        discrepancy_count=discrepancy_count,
        sanctions_hit_count=len(sanctions.get("hits", [])),
        discrepancy_rate=round(discrepancy_count / len(docs), 3) if docs else None,
    )

    decision = FinalDecision(
        run_id=str(run_id), action=action, rationale=rationale,
        findings=[Finding(**f) for f in findings],
        swift_draft=swift, metrics=metrics,
    )

    posting_payload = {
        "run_id": str(run_id),
        "title": f"Trade finance examination: {action.value}",
        "decision": action.value,
        "rationale": rationale,
        "severity_summary": {s: sum(1 for f in findings if f["severity"] == s)
                             for s in ("critical", "major", "minor", "info")},
        "discrepancies": [{"id": f["id"], "severity": f["severity"], "title": f["title"]} for f in findings],
    }

    if run_dir is not None:
        run_dir = Path(run_dir)
        write_json(run_dir / "final_decision.json", decision)
        write_text(run_dir / "swift_draft.txt", swift.content)
        write_json(run_dir / "posting_payload.json", posting_payload)

    return {
        "final_decision": decision.model_dump(mode="json"),
        "trace": [{"agent": "agent_h_orchestrator", "action": action.value,
                   "findings": len(findings), "discrepancy_count": discrepancy_count}],
    }
