"""
Assessment Adapter implementation for FDE Assessment 3.
Provides the standard handle_request entry point tested by the evaluation harness.
Routes requests to:
- Architecture A: Single-Agent Baseline (src/agent_single.py)
- Architecture B: Staged 2-Agent Variant (src/agent_staged.py)
"""
from __future__ import annotations

from src.contracts import Architecture, ProcurementDecision
from src.agent_single import run_single_agent
from src.agent_staged import run_staged_agents


def handle_request(request_id: str, architecture: Architecture = "single") -> ProcurementDecision:
    """Assessment adapter callable by public and hidden evaluation suites."""
    arch_norm = str(architecture).strip().lower()
    if arch_norm in ["single", "a", "baseline"]:
        return run_single_agent(request_id)
    elif arch_norm in ["staged", "b", "two_agent", "2-agent"]:
        return run_staged_agents(request_id)
    else:
        raise ValueError(f"Unknown architecture: '{architecture}'. Choose 'single' or 'staged'.")
