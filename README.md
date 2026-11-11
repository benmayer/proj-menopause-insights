# Menohelp (Project Menopause Insights)

An autonomous LangGraph agent that analyses menstrual cycle data for
perimenopause-related patterns and writes a custom, grounded report. Not medical advice.

> **Status:** in development (Week 6, Ironhack AI Bootcamp). See
> [`docs/plans/implementation-plan.md`](docs/plans/implementation-plan.md) for progress.

## What problem are we solving?
Perimenopause can start years before periods stop, and one of its earliest signs is
changing cycle patterns: longer or shorter cycles, growing variability, skipped periods.
Cycle apps log this data but rarely turn it into a clear picture, and the changes are
easy to miss or dismiss. People often arrive at a doctor's appointment with no
organised evidence.

## Who is it for?
People who track their cycle (for example in Clue) and want to understand whether their
pattern is shifting, typically in their late 30s to 50s. Secondary users: anyone
preparing for a conversation with a doctor.

## What it does
- Reads cycle data and computes stats (mean, variability, trend, long or skipped cycles)
- Looks for patterns that are commonly associated with perimenopause
- Writes a plain-language report grounded in reference documents (RAG)
- Checks that every number in the report matches the computed stats
- Shows the report in a web UI and can email it

It is not a diagnostic tool. Every report carries a "not medical advice" note and
suggests topics to discuss with a doctor.

## Upload format
Accepts **CSV or JSON**. Any file with a cycle start date works; headers are matched loosely (case, spaces, underscores ignored).
- **Required:** start date (`cycle_start`, `start_date`, `date`, `period_start`)
- **Optional:** `user_id` (missing = one person), `cycle_length` (missing = derived from gaps between start dates), `period_length`, `flow`, `age`
- **Clue export:** upload `measurements.json` as is. Bleeding days are grouped into cycles (a gap of more than 7 days starts a new cycle); cycle length, period length and flow are derived. Age isn't in the export.
- Demo files are in `samples/` (Kaggle sets, credit below, plus a labelled-synthetic perimenopause user). Regenerate with `scripts/build_demo_data.py` and `scripts/synth_perimenopause.py`.

## Status (11 Nov 2026)
| Part | State |
|---|---|
| Data in | CSV or JSON upload (incl. Clue `measurements.json`), normalised to one schema. Done, tested |
| Stats | `app/analysis/stats.py`: length, trend, recent-vs-baseline, flag counts, dated events. Done, hand-computed tests |
| Data API | FastAPI `/health /upload /users /cycles /stats /demos`, in-memory store. Done |
| RAG | Supabase pgvector: 15 instruction/reference chunks + 316 coaching-material chunks (5 PDFs, cited by page). Done |
| Agent | LangGraph: fetch, analyse, retrieve, write, check, interpret, guardrail. Done; reports pass checks but are generic |
| Reports | `samples/report_*.md` (human) + `*_findings.md` (verified facts) |
| UI | `streamlit run ui/app.py`: two steps (data, symptoms and lab PDFs, then report). Cycle chart inside the report, findings, lab alignment, email button (send tested). Done |
| Blood tests | Lab PDF upload: parsed in code (allow-listed analytes, name and DOB dropped), reader confirms values, flags from the printed range, draw timing, alignment of cycle + symptoms + labs, interpretation with guardrails. Plan: [`docs/plans/blood_test_plan.md`](docs/plans/blood_test_plan.md). Done |
| Next | Deploy, README polish, GTM file to repo root, demo video |

Run the UI: `streamlit run ui/app.py` (uses `API_BASE_URL` if a `uvicorn app.api.main:app` is running, otherwise the API in-process).
Run the tests: `pytest` (92 tests; the RAG ones need `.env` keys).
Generate a report: `python -m app.agent.run --dataset demo_synthetic_perimenopause --user synth_peri --out samples/report_1.md`

## Architecture

```
CSV upload ──▶ FastAPI ──(/cycles, /stats)──▶ LangGraph agent ──▶ Report
                                                                   │
                                                    RAG (Supabase pgvector): reference docs
                                                    + report instructions
Streamlit UI ──▶ agent ──▶ report on screen ──▶ email (Resend)
```

**Agent flow:** Fetch (stats + optional lab draws) → Analyse (flags, case tags, symptom and lab summary) → Triage (context category) → Retrieve → Write findings → Check (every number/date
verified; loops back on mismatch) → Interpret (meaning + advice from cited coaching chunks) → Guardrail
(citations, numbers, banned wording; loops back to Interpret).

**Principle:** the LLM never sees raw data. FastAPI returns computed stats; the LLM only
interprets and writes.

## Workflow

```
 1 Trigger         user picks a data source/user in Streamlit (or CLI) and clicks Generate
 2 Fetch           agent calls FastAPI /cycles and /stats (uploaded CSV, held in memory)
 3 Analyse         pandas stats: mean/SD, rolling variability, trend slope, long/skipped cycles
 4 Retrieve        RAG query to Supabase pgvector: reference ranges + section instructions
 5 Write           OpenAI drafts report sections from stats + retrieved text only
 6 Check           extract every number from the draft, compare with computed stats
 7   ├─ mismatch   back to Write (max 2 retries)
 8   └─ pass       add "not medical advice" disclaimer
 9 Output          report rendered in UI (with chart)
10 Email           optional send via Resend (rate-limited, nothing stored)
```

## Stack
| Layer | Tech |
|---|---|
| Agent | LangGraph + OpenAI |
| Data API | FastAPI + pandas |
| Data source | CSV upload (Clue export or Kaggle/synthetic), normalised in FastAPI |
| Grounding | RAG, Supabase (pgvector) |
| UI | Streamlit |
| Email | Resend |
| Stretch | scikit-learn prediction model trained on Kaggle data |

## APIs / tools
OpenAI API · Supabase · Resend (details and test scripts to be added).

## Environment variables
See [`.env.example`](.env.example) for the full list (OpenAI, Supabase, Resend, app settings). Copy to `.env` and fill in. Never commit `.env`.

## Setup / run
Uses a conda env (Python 3.12), not a venv:

```bash
conda activate ironhack
pip install -r requirements.txt
cp .env.example .env   # then fill in keys
```
Run commands will be added as each phase is built.

## Docs
- `docs/plans/implementation-plan.md`: phased plan and current status
- `docs/PROJECT_DRAFT.md`: design draft
- `docs/plans/gtm_future_sprints.md`: go-to-market sprints
- `stack_decision.md`: why LangGraph (n8n secondary)
- `docs/kaggle_datasets.md`: dataset evaluation and findings
- `docs/agent_extensions.md`: proposed extensions (case triage, events, charts, symptom tool, guardrail) and target graph
- `docs/img/graph_minimal.png`, `docs/img/graph_full.png`: slide-ready diagrams of the core and extended agent graph (`scripts/draw_graphs.py`)
- `docs/graph.mmd`: LangGraph diagram (Mermaid, generated)
- `docs/rag_design.md`: chunking, embeddings, retrieval settings and the PDF plan
- `samples/`: _to be added_
- Demo recording: _to be added_

## Data credits
Demo data is synthetic. Sources (via Kaggle): `puspitachowdhury2/menstrual-health-dataset` (CC BY-NC 4.0, non-commercial) and `akshayas02/menstrual-cycle-data-with-factors-dataset` (CC0). Files in `samples/` are normalised derivatives of these, plus a generated perimenopause example.
