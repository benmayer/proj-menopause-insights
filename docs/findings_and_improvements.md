# Findings, struggles and improvement plan (11 Nov 2026)

Status after Phase 6: the agent runs end to end and every report passes its checks. The reports are
**correct but generic**. This page records what we learned and how we plan to fix it.

## What works
- **LLM never does arithmetic.** Stats come from `stats.py`; the Check node verifies every number, date and
  field name in the findings report (retry loop, max 2).
- **Two-layer output.** `report` (verified findings, facts only) then `human_report` (meaning + advice, built on the
  findings and on cited coaching chunks). A code-only Guardrail checks citations, numbers, banned wording.
- **RAG with citations.** 316 coaching-material chunks (5 German MenoCert modules) + 15 instruction/reference chunks in
  Supabase pgvector; every advice line carries `[S#]` mapped to document and page.
- **Age rule enforced in code.** Under-40 readers are never framed as perimenopausal (the guardrail rewrites it).
- Dated events (skipped/long/short/jump, `first_time`) give the report concrete moments to point at.

## What we struggle with
| Problem | Cause |
|---|---|
| Reports are generic ("many causes, only a doctor can tell") | The only personal input is cycle dates, so retrieval can only ask "irregular cycle, what helps" |
| Advice is broad (sleep, stress, tracking) | Raw ~400-token PDF chunks, cut mid-topic; no per-symptom structure |
| The guardrail pushes toward safe, vague text | Rule "every line must cite a source" plus "advice only from sources" rewards generic sentences |
| No prioritisation | The prompt does not ask the model to pick what matters most for this person |
| Source tags skip numbers (S1, S3, S6) | Tags are assigned before the model chooses which chunks to use (cosmetic) |
| Odd lines, e.g. hormone-therapy mention for a stable user | Instruction says to always mention it; should depend on flags/symptoms |
| German sources, English reports | Cross-language retrieval scores ~0.5 vs ~0.7 for German queries; queries are therefore written in German |
| Bibliography chunks polluted retrieval | Dropped at ingest (chunks dense with `doi`, `(2019)`, `et al.`) |

## Technical lessons
- Supabase direct DB host is IPv6-only; `scripts/setup_supabase.py` falls back to the IPv4 session pooler.
- gpt-5.x chat needs `max_completion_tokens`. `python -I` breaks `-m app...`. Bare `pytest` needs `pytest.ini`.
- Retrieval quality depends more on the *query* (German, case-specific) than on the model.

## Plan to improve relevance (in order)
1. **Symptom and concern input in the UI** (after the Streamlit UI exists): age, tick list of ~10 symptoms with severity
   (1-3), one free-text "What are you struggling with most?". Symptoms become case tags that drive retrieval.
2. **Symptom cards in the RAG** (`rag_docs/`): a short structured card per symptom/case (what it can be linked to,
   options the coaching material names, when to see a GP, page references). Drafted from the PDFs, reviewed by Ben.
   Retrieval returns a focused card instead of a fragment. Biggest expected gain.
3. **Prompt rewrite for Interpret:** pick the top 3 priorities from what the reader reported; tie each point to their
   input; organise "Things that may help" by symptom; omit anything the input does not support.
4. **Richer case tags:** combine cycle patterns, symptoms and age (e.g. skipped cycle + hot flushes + 46) to select cards.
5. Smaller fixes: renumber used source tags, make the hormone-therapy line conditional on flags/symptoms.
6. **Later:** Clue symptom parser (long table, `/symptoms` endpoint), charts with labelled events, own prediction model.

## How we will judge it
Generate persona reports (young irregular, mid-40s with the synthetic pattern, stable 30s, long gap, very few cycles,
plus symptom variants) and review with Ben: Is it specific to the input? Is every claim cited? Anything unsafe?
Keep the guardrail checks as tests (`tests/test_graph.py`).
