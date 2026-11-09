# proj-menopause-insights

An autonomous LangGraph agent that analyses menstrual cycle data for
perimenopause-related patterns and writes a custom, grounded report. Not medical advice.

> **Status:** in development (Week 6, Ironhack AI Bootcamp). See
> [`docs/plans/implementation-plan.md`](docs/plans/implementation-plan.md) for progress.

## Architecture

```
Google Sheet ──(Sheets API)──▶ FastAPI ──(/cycles, /stats)──▶ LangGraph agent ──▶ Report
                                                                   │
                                                    RAG (Supabase pgvector): reference docs
                                                    + report instructions
Streamlit UI ──▶ agent ──▶ report on screen ──▶ email (Resend)
```

**Agent flow:** Fetch → Analyse → Retrieve → Write → Check (verifies every number
against computed stats; loops back to Write on mismatch).

**Principle:** the LLM never sees raw data. FastAPI returns computed stats; the LLM only
interprets and writes.

## Workflow

```
 1 Trigger         user picks a data source/user in Streamlit (or CLI) and clicks Generate
 2 Fetch           agent calls FastAPI /cycles and /stats (Sheet read, cached)
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
| Data source | Google Sheets API (Clue export + Kaggle) |
| Grounding | RAG, Supabase (pgvector) |
| UI | Streamlit |
| Email | Resend |
| Stretch | scikit-learn prediction model trained on Kaggle data |

## APIs / tools
Google Sheets API · OpenAI API · Supabase · Resend (details and test scripts to be added).

## Environment variables
See [`.env.example`](.env.example) for the full list (OpenAI, Supabase, Google Sheets, Resend, app settings). Copy to `.env` and fill in. Never commit `.env`.

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
- `samples/`: _to be added_
- Demo recording: _to be added_
