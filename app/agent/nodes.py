"""Graph nodes. SKELETON: each is a stub returning a placeholder; real logic lands in Phase 6.

A node takes the state and returns only the keys it changes.
"""
from app.agent.state import AgentState

MAX_RETRIES = 2


def fetch(state: AgentState) -> dict:
    """Phase 6: call FastAPI /stats (and /cycles) for dataset_id/user_id."""
    return {"stats": {"n_cycles": 0}, "retries": 0}


def analyse(state: AgentState) -> dict:
    """Phase 6: apply the flag rules to the stats (deterministic, no LLM)."""
    return {"findings": {"flags": []}}


def retrieve(state: AgentState) -> dict:
    """Phase 6: app.rag.retrieve per report section (reference, instructions, advice)."""
    return {"context": []}


def write(state: AgentState) -> dict:
    """Phase 6: OpenAI drafts the report from stats + findings + context only."""
    return {"report": f"# STUB REPORT (attempt {state.get('retries', 0) + 1})\n"}


def check(state: AgentState) -> dict:
    """Phase 6: extract every number in the report and compare with the stats."""
    return {"passed": True, "check_errors": []}


def route_after_check(state: AgentState) -> str:
    """Pass -> finish. Fail -> back to Write, at most MAX_RETRIES times, then finish anyway."""
    if state.get("passed"):
        return "end"
    return "write" if state.get("retries", 0) <= MAX_RETRIES else "end"
