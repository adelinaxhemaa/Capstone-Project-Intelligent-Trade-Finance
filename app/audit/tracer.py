"""Execution tracer.

Turns the raw per-node trace entries (accumulated in state['trace']) into an
ordered, human-readable execution record for the audit log and run metadata.
"""

from __future__ import annotations

from typing import Any

# Canonical node order for display.
_ORDER = ["agent_a_intake", "agent_b_extraction", "manual_review", "agent_c_ucp",
          "agent_d_matching", "agent_e_sanctions", "freeze", "agent_h_orchestrator"]


def execution_trace(state: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the trace entries in canonical pipeline order."""
    trace = state.get("trace", [])
    return sorted(trace, key=lambda t: _ORDER.index(t["agent"]) if t.get("agent") in _ORDER else 99)


def trace_lines(state: dict[str, Any]) -> list[str]:
    """One readable line per executed node."""
    lines: list[str] = []
    for step in execution_trace(state):
        agent = step.get("agent", "?")
        rest = ", ".join(f"{k}={v}" for k, v in step.items() if k != "agent")
        lines.append(f"{agent}: {rest}")
    return lines
