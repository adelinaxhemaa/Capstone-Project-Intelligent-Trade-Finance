from __future__ import annotations
from pathlib import Path
from typing import Any
from app.config import get_settings
from app.llm import semantic_judge
from app.rules import matching_rules
from app.rules.matching_rules import AMBIGUOUS_LOW
from app.schemas.common import DocumentType, Severity
from app.schemas.findings import EvidencePointer, Finding, FindingType
from app.schemas.matching import MatchResult
from app.tools.policy_loader import load_policy
from app.utils.ids import finding_id
from app.utils.io import write_json


def run_agent_d(state: dict[str, Any], run_dir: str | Path | None = None) -> dict[str, Any]:
    extracted = state.get("extracted_docs", {})
    context = state.get("context_packet", {})
    policy = load_policy(state.get("jurisdiction"))
    run_id = state.get("run_id", "run")
    name_threshold = float(policy.get("fuzzy", {}).get("name_match_threshold", 85))

    matches, findings = matching_rules.compare(extracted, context, policy)

    # Optional semantic flag for ambiguous goods descriptions (review only).
    semantic_used = False
    if get_settings().use_llm:
        a, b, score_pct = matching_rules.goods_description_pair(extracted)
        if a and b and score_pct is not None and AMBIGUOUS_LOW <= score_pct < name_threshold:
            verdict = semantic_judge.judge(a, b)
            if verdict is not None:
                semantic_used = True
                if verdict.ambiguous or verdict.same_goods:
                    findings.append(Finding(
                        id=finding_id("semantic_flag", "goods_description", a + b),
                        type=FindingType.LOW_CONFIDENCE, severity=Severity.MINOR,
                        title="Goods description needs human review",
                        description=f"Descriptions may refer to the same goods (LLM): {verdict.reason}",
                        confidence=0.5, source_agent="agent_d_matching",
                        evidence=[EvidencePointer(source_file="goods_description",
                                                  document_type=DocumentType.COMMERCIAL_INVOICE,
                                                  field_name="goods_description")],
                        open_questions=["Do these goods descriptions refer to the same goods?"],
                        recommendation="Human reviewer to confirm goods-description equivalence.",
                    ))

    result = MatchResult(run_id=str(run_id), matches=matches, findings=findings)

    if run_dir is not None:
        write_json(Path(run_dir) / "match_result.json", result)

    return {
        "match_result": result.model_dump(mode="json"),
        "findings": [f.model_dump(mode="json") for f in findings],
        "trace": [{
            "agent": "agent_d_matching",
            "comparisons": len(matches),
            "mismatches": sum(1 for m in matches if not m.matched),
            "findings": len(findings),
            "semantic_flag_used": semantic_used,
        }],
    }