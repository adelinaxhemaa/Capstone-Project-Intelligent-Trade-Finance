"""The LangGraph shared state.

`PipelineState` is the object threaded through every node of the graph in
`app/pipeline.py`. Each node reads what it needs and returns a partial dict
that LangGraph merges in. Artifacts are stored as plain JSON-able dicts
(model_dump output) so the state stays serializable and easy to inspect.

`findings` and `trace` use additive reducers so every node can append
without clobbering earlier entries.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict


class PipelineState(TypedDict, total=False):
    # --- run identity / inputs ---
    run_id: str
    run_dir: str
    input_path: str
    is_bundle: bool
    jurisdiction: str | None

    # --- per-agent artifacts (JSON-able dicts) ---
    context_packet: dict[str, Any]
    evidence_index: dict[str, Any]
    extracted_docs: dict[str, Any]
    ucp_result: dict[str, Any]
    match_result: dict[str, Any]
    sanctions_screen: dict[str, Any]
    final_decision: dict[str, Any]
    metrics: dict[str, Any]

    # --- accumulated across nodes (additive) ---
    findings: Annotated[list[dict[str, Any]], add]
    trace: Annotated[list[dict[str, Any]], add]

    # --- routing signal set by conditional edges ---
    route: str
