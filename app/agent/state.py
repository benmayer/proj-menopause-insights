from typing import TypedDict


class AgentState(TypedDict, total=False):
    # input
    dataset_id: str
    user_id: str | None
    # filled by nodes
    stats: dict          # Fetch: computed by the FastAPI /stats endpoint (never raw rows)
    findings: dict       # Analyse: deterministic interpretation of stats (which flags trigger)
    context: list[dict]  # Retrieve: RAG chunks (reference ranges, instructions, advice)
    report: str          # Write: markdown draft
    passed: bool         # Check: did every number match the stats?
    check_errors: list[str]
    retries: int         # Check failures so far
