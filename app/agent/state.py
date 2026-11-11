from typing import TypedDict


class AgentState(TypedDict, total=False):
    # input
    dataset_id: str
    user_id: str | None
    age: float | None    # optional, entered in the UI when the file has no age
    intake: dict | None  # UI form: symptoms {system_key: 1-3}, top_concern, hormones, surgery, last_period
    # filled by nodes
    stats: dict          # Fetch: computed by the FastAPI /stats endpoint (never raw rows)
    findings: dict       # Analyse: deterministic interpretation of stats (which flags trigger)
    context: list[dict]  # Retrieve: RAG chunks (reference ranges, instructions, advice)
    report: str          # Write: verified findings report (facts only)
    human_report: str    # Interpret: reader-facing report with meaning + advice, cited
    sources: dict        # Interpret: tag -> citation, e.g. S1 -> 'Modul 3 ..., S. 19'
    guard_errors: list[str]  # Guardrail problems with the interpretation
    i_retries: int       # Guardrail failures so far
    passed: bool         # Check: did every number match the stats?
    check_errors: list[str]
    retries: int         # Check failures so far
