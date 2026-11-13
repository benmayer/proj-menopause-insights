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

## Update: symptom intake built (11 Nov, steps 3-4 of `docs/plans/symptom_intake_plan.md`)
- **UI:** quick form (last period, hormonal contraception/HT, surgery, 15 body-system ticks rated mild/moderate/strong, one-line top concern, OpenAI notice).
- **Pipeline:** `analyse` computes a symptom summary in code, new deterministic `triage` node picks a context category
  (`masked_by_hormones`, `surgical_or_other`, `no_period_12m`, `young`, `irregular_recent`, `regular`) that drops cycle-trend claims when cycle length is not a natural signal,
  `retrieve` adds symptom-table cards (exact lookup) and guarantees practical-advice chunks for each top symptom, `interpret` prioritises the reader's concern, adds
  "What your symptoms may point to", and appends fixed red-flag text (code-written) for strong heart/mind/cycle ratings.
- **New guardrails:** symptom section required and cited, no claims about the reader's own hormone levels, hormone-therapy mentioned only when flags or temperature/sexuality symptoms or a question about it.
- **Result:** persona reports (`samples/persona_*.md`) now reflect the reader's words and symptoms; pill user gets a "cycle data is artificial" note instead of a trend.
- **Known limits:** guardrail checks that a citation exists and is present, not that the cited source supports the sentence (e.g. a cooling-down tip cited to the symptom table);
  next candidate is an LLM-judge claim-support check. Advice quality is bounded by what the chunks contain; symptom cards are lookups, not curated advice.

## Update 12 Nov: report rework after Ben's review of the full demo report (`samples/Report Feedback.md`)
Feedback: hard to follow, each source treated separately, "the material says" voice, disclaimers in every sentence,
no comparison with typical values, a very low AMH for a reader in her early 30s shown only as "within range", irrelevant thyroid caveat.
Almost all of it came from our own prompt and guardrail, not from missing data or graph shape.

| Change | Where |
|---|---|
| New outline: Summary (combined) → Your cycle → Your blood results → Your symptoms → What it could mean together → Things that may help → Talking to your doctor; fixed "How to read this report" notes once at the end | `nodes.interpret_headings`, `nodes.notes_block` |
| Coach voice: sources are the agent's own knowledge, cited by tag; "the material/table says" is a guardrail error | `_interpret_prompt`, `BANNED`, `rag_docs/instr_interpret.md`, `tone_and_disclaimer.md` (re-ingested) |
| Citations per paragraph in the conclusion and advice, at least one per cycle/blood section; no tags needed in summary/doctor | `guard_report` |
| Cycle compared with typical cycles (21-35 days, few days' variation, share of 7-day jumps), computed in code | `nodes.compare_cycles` |
| Age norms for lab values whose printed range ignores age (AMH now): Ji et al. 2022, Ann Lab Med, healthy women, per-year percentiles, smoothed ±2 years. Code writes the comparison sentence; the LLM copies it | `app/agent/age_norms.py` |
| Cross-source explanations in code: each candidate (ovarian/transition, thyroid, iron, prolactin, androgens, progesterone) is supported / contradicted / untested by the blood results, with relevance from cycle + symptoms. Contradicted ones are dropped unless they were the only strong lead; at most 2 untested ones become "worth testing". Retrieval adds advice chunks for them | `app/agent/explain.py`, `nodes.triage`, `nodes.retrieve` |
| Claims "your X is low/high" and "low for your age" are allowed only when code backs them (printed range or age norm) | `supported_claims`, `_hormone_claim_errors` |
| Under-40 alignment: "high" at 3 signals if one is a lab signal (the age signal cannot count) | `labs.align_labs` |

Lessons: the model reads "below the lab range" as "low for your age" and will invent percentile bands; only a
code-written phrase plus a specific guard message fixed it. LLM interpretation stays in words, judgement on
values stays in code. Sample reports (synthetic): `samples/persona_*.md`.
