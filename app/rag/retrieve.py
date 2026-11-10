"""Semantic lookup in Supabase via the match_documents SQL function."""
from app.rag.clients import embed, supabase_client


def retrieve(query: str, k: int = 3, section: str | None = None) -> list[dict]:
    """Top-k chunks for `query`, optionally restricted to one section. Each has similarity (0-1)."""
    res = supabase_client().rpc("match_documents", {
        "query_embedding": embed([query])[0], "match_count": k, "filter_section": section}).execute()
    return res.data
