"""The LangGraph pipeline (orchestration spine).

Full graph: intake -> extract -> (manual_review?) -> ucp -> match -> sanctions
-> (freeze?) -> orchestrate -> END. Two conditional edges implement the
"intelligent routing" the brief calls for: a low-confidence extraction diverts
through `manual_review`, and an active sanctions hit diverts through `freeze`
before the orchestrator's decision.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from langgraph.graph import END, START, StateGraph

from app.agents.agent_a_intake import run_agent_a
from app.agents.agent_b_extraction import run_agent_b
from app.agents.agent_c_ucp import run_agent_c
from app.agents.agent_d_matching import run_agent_d
from app.agents.agent_e_sanctions import run_agent_e
from app.agents.agent_h_orchestrator import run_agent_h
from app.audit.audit_logger import write_audit_log
from app.reports.report_builder import build_reports
from app.state import PipelineState
from app.utils.io import create_run_dir, new_run_id, write_json


# --------------------------------------------------------------------------- #
# Nodes
# --------------------------------------------------------------------------- #
def node_intake(state: PipelineState) -> dict[str, Any]:
    return run_agent_a(state["input_path"], state["run_dir"])


def node_extract(state: PipelineState) -> dict[str, Any]:
    return run_agent_b(state, state["run_dir"])


def node_manual_review(state: PipelineState) -> dict[str, Any]:
    low = [f for f in _all_fields(state) if f.get("low_confidence")]
    return {"route": "manual_review",
            "trace": [{"agent": "manual_review", "count": len(low),
                       "flagged_fields": [f["name"] for f in low][:20]}]}


def node_ucp(state: PipelineState) -> dict[str, Any]:
    return run_agent_c(state, state["run_dir"])


def node_match(state: PipelineState) -> dict[str, Any]:
    return run_agent_d(state, state["run_dir"])


def node_sanctions(state: PipelineState) -> dict[str, Any]:
    return run_agent_e(state, state["run_dir"])


def node_freeze(state: PipelineState) -> dict[str, Any]:
    return {"route": "freeze",
            "trace": [{"agent": "freeze", "reason": "active sanctions hit"}]}


def node_orchestrate(state: PipelineState) -> dict[str, Any]:
    return run_agent_h(state, state["run_dir"])


def node_report(state: PipelineState) -> dict[str, Any]:
    """Render the human-readable audit log + reports from the run artifacts."""
    run_dir = state["run_dir"]
    write_audit_log(state, run_dir)
    build_reports(state, run_dir)
    return {"trace": [{"agent": "report", "rendered": ["audit_log.md", "discrepancies.md", "run_report.md"]}]}


# --------------------------------------------------------------------------- #
# Conditional routing
# --------------------------------------------------------------------------- #
def _all_fields(state: PipelineState) -> list[dict]:
    docs = state.get("extracted_docs", {}).get("documents", [])
    return [f for d in docs for f in d.get("fields", [])]


def route_after_extract(state: PipelineState) -> str:
    if any(f.get("low_confidence") for f in _all_fields(state)):
        return "manual_review"
    return "continue"


def route_after_sanctions(state: PipelineState) -> str:
    if state.get("sanctions_screen", {}).get("hits"):
        active = any(not h.get("is_false_positive") for h in state["sanctions_screen"]["hits"])
        if active:
            return "freeze"
    return "continue"


# --------------------------------------------------------------------------- #
# Graph assembly
# --------------------------------------------------------------------------- #
def build_graph():
    g = StateGraph(PipelineState)
    g.add_node("intake", node_intake)
    g.add_node("extract", node_extract)
    g.add_node("manual_review", node_manual_review)
    g.add_node("ucp", node_ucp)
    g.add_node("match", node_match)
    g.add_node("sanctions", node_sanctions)
    g.add_node("freeze", node_freeze)
    g.add_node("orchestrate", node_orchestrate)
    g.add_node("report", node_report)

    g.add_edge(START, "intake")
    g.add_edge("intake", "extract")
    g.add_conditional_edges("extract", route_after_extract,
                            {"manual_review": "manual_review", "continue": "ucp"})
    g.add_edge("manual_review", "ucp")
    g.add_edge("ucp", "match")
    g.add_edge("match", "sanctions")
    g.add_conditional_edges("sanctions", route_after_sanctions,
                            {"freeze": "freeze", "continue": "orchestrate"})
    g.add_edge("freeze", "orchestrate")
    g.add_edge("orchestrate", "report")
    g.add_edge("report", END)
    return g.compile()


_GRAPH = build_graph()


def run_pipeline(input_path: str | Path, run_id: str | None = None) -> dict[str, Any]:
    run_id = run_id or new_run_id()
    rid, run_dir = create_run_dir(run_id)
    initial: PipelineState = {
        "run_id": rid, "run_dir": str(run_dir), "input_path": str(input_path),
        "findings": [], "trace": [],
    }
    start = time.perf_counter()
    final_state = _GRAPH.invoke(initial)
    elapsed = round(time.perf_counter() - start, 3)

    # metrics.json: deterministic counts (from the decision) PLUS timing/throughput
    # (reporting only — excluded from determinism comparisons).
    decision = final_state.get("final_decision", {})
    metrics = dict(decision.get("metrics", {}))
    docs = metrics.get("documents_processed", 0)
    throughput = round(docs / elapsed, 3) if elapsed > 0 else None
    metrics["processing_seconds"] = elapsed
    metrics["throughput"] = throughput
    metrics["throughput_docs_per_sec"] = throughput
    write_json(Path(run_dir) / "metrics.json", metrics)
    if isinstance(decision, dict) and "metrics" in decision:
        decision["metrics"].update(
            {
                "processing_seconds": elapsed,
                "throughput": throughput,
                "throughput_docs_per_sec": throughput,
            }
        )

    write_json(Path(run_dir) / "run_metadata.json", {
        "run_id": rid, "input_path": str(input_path),
        "route": final_state.get("route", "continue"),
        "trace": final_state.get("trace", []),
        "finding_count": len(final_state.get("findings", [])),
        "processing_seconds": elapsed,
    })
    return final_state


if __name__ == "__main__":
    import sys

    target = sys.argv[1] if len(sys.argv) > 1 else "tests/bundles/bundle_01_clean"
    state = run_pipeline(target)
    dec = state.get("final_decision", {})
    print("run:", state["run_id"], "| route:", state.get("route", "continue"))
    print("DECISION:", dec.get("action"), "—", dec.get("rationale"))
    print("findings:", len(state.get("findings", [])))
    for t in state.get("trace", []):
        print("  ", t)
