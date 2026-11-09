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
See `.env.example` (to be added). Never commit `.env`.

## Setup / run
_To be completed as phases are built._

## Docs
- `docs/plans/implementation-plan.md`: phased plan and current status
- `docs/PROJECT_DRAFT.md`: design draft
- `docs/plans/gtm_future_sprints.md`: go-to-market sprints
- `stack_decision.md`: _to be added_
- `samples/`: _to be added_
- Demo recording: _to be added_
