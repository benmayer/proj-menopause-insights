"""Semantic lookup in Supabase via the match_documents SQL function."""
from app.rag.clients import embed, supabase_client


def retrieve(query: str, k: int = 3, section: str | None = None) -> list[dict]:
    """Top-k chunks for `query`, optionally restricted to one section. Each has similarity (0-1)."""
    res = supabase_client().rpc("match_documents", {
        "query_embedding": embed([query])[0], "match_count": k, "filter_section": section}).execute()
    return res.data


def symptom_cards(system_keys: list[str]) -> list[dict]:
    """Exact lookup (no embedding) of the symptom-map card for each body system key."""
    from app.agent.symptoms import SYSTEMS

    titles = [SYSTEMS[k][0] for k in system_keys if k in SYSTEMS]
    if not titles:
        return []
    res = (supabase_client().table("documents").select("id,section,title,content,source,metadata")
           .eq("section", "symptom_map").in_("title", titles).execute())
    order = {t: i for i, t in enumerate(titles)}
    return sorted(res.data, key=lambda r: order[r["title"]])
