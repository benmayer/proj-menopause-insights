"""Live retrieval test (needs OPENAI + Supabase keys and `python -m app.rag.ingest` run once)."""
import os

import pytest

from app.rag.retrieve import retrieve

pytestmark = pytest.mark.skipif(not os.getenv("SUPABASE_API_KEY"), reason="needs .env keys")

CASES = [
    ("What cycle length counts as irregular?", "Typical cycle length"),
    ("What persistent difference between consecutive cycles marks the early transition?", "Early transition marker"),
    ("What exact disclaimer must end every report?", "Required disclaimer"),
    ("When should someone see a GP about bleeding?", "When the NHS suggests seeing a GP"),
]


@pytest.mark.parametrize("query,expected_title", CASES)
def test_top_hit(query, expected_title):
    hits = retrieve(query, k=3)
    assert hits[0]["title"] == expected_title, [(h["title"], round(h["similarity"], 2)) for h in hits]


def test_section_filter_and_instruction_lookup():
    hits = retrieve("how to write the flags section", k=2, section="flags")
    assert hits and all(h["section"] == "flags" for h in hits)
    assert "not a diagnosis" in hits[0]["content"]
