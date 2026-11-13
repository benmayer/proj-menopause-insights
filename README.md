# 🌿 Menohelp (Project Menopause Insights)

> Receive qualified insights and practical support based on **menstrual cycle data** and **blood test results**, to understand any **symptoms** you might have.

A LangGraph agent that combines a cycle log, blood test PDFs and a symptom form into a plain-language, source-grounded report. Not medical advice. Ironhack AI Bootcamp, Project 3 (Week 6). Ben Mayer.

**Demo recording:** [Google Drive](https://drive.google.com/file/d/1w0rhwgC-fppPOUWuHr0-NE5V6HCCCZfk/view?usp=drive_link)
**Presentation:** [Google Slides](https://docs.google.com/presentation/d/1Zm3EHbjQGncJBF3cwiD7ZBUsNYVuNgiSyCgnS4iy63k/edit)

## Why: the problem
On average, a woman in Germany receives a perimenopause diagnosis **6 years after it started**, and lives with untreated symptoms in the meantime. She tries to make sense of her symptoms alone, and doctors rarely have the time to connect many different ones. A cycle log holds months of data that is hard to read, let alone to understand as a trend.

## Who is it for?
Women between 35 and 50+ who already track their cycle in an app (Clue, Flo etc.). Secondary: anyone preparing for a conversation with a doctor or gynaecologist.

## What the user gets
- **Make sense of all the data:** cycle log, blood tests and symptoms in one report (aligned across sources).
- **Verified analysis:** code computes every number and checks the draft against it; the model only writes the text.
- **Practical advice:** what may help and what to discuss with a doctor, taken only from certified coaching material (not public). Sources are listed in the UI's Quality tab.

Not a diagnostic tool: every report carries a "not medical advice" note, no doses, never tells anyone to start or stop medication.

## How it works (5 steps)
1. **Upload:** exported cycle data, blood test PDF, symptom form
2. **Analyse:** code calculates cycle statistics and flags changes
3. **Look up:** finds matching coaching material in a RAG database
4. **Write and check:** the model drafts the report; code checks every number against the data
5. **Deliver:** report on screen, with an email option

**Privacy / GDPR:** the model never sees raw cycle data, only calculated statistics. Lab PDFs are parsed in code (allow-listed values only; name and date of birth dropped). The MVP keeps uploads in memory only.

## Upload format
Accepts **CSV or JSON**. Any file with a cycle start date works; headers are matched loosely (case, spaces, underscores ignored).
- **Required:** start date (`cycle_start`, `start_date`, `date`, `period_start`)
- **Optional:** `user_id` (missing = one person), `cycle_length` (missing = derived from gaps between start dates), `period_length`, `flow`, `age`
- **Clue export:** upload `measurements.json` as is. Bleeding days are grouped into cycles (a gap of more than 7 days starts a new cycle); cycle length, period length and flow are derived. Age isn't in the export.
- Demo files are in `samples/` (Kaggle sets, credit below, plus a labelled-synthetic perimenopause user). Regenerate with `scripts/build_demo_data.py` and `scripts/synth_perimenopause.py`.

## Status (13 Nov 2026)
| Part | State |
|---|---|
| Data in | CSV or JSON upload (incl. Clue `measurements.json`), normalised to one schema. Done, tested |
| Stats | `app/analysis/stats.py`: length, trend, recent-vs-baseline, flag counts, dated events. Done, hand-computed tests |
| Data API | FastAPI `/health /upload /users /cycles /stats /demos`, in-memory store. Done |
| RAG | Supabase pgvector: 15 instruction/reference chunks + 316 coaching-material chunks (5 PDFs, cited by page). Done |
| Agent | LangGraph: fetch, analyse, retrieve, write, check, interpret, guardrail. Done; reports pass checks but are generic |
| Reports | `samples/full_demo_cycle_report.md` (real data, full report with chart), `samples/report_1_perimenopause.md`, `samples/report_2_stable_control.md` (+ `*_findings.md` verified facts). Older runs in `samples/archives/` |
| UI | `streamlit run ui/app.py`: two steps (data, symptoms and lab PDFs, then report). Cycle chart inside the report, findings, lab alignment, email button (send tested). Done |
| Blood tests | Lab PDF upload: parsed in code (allow-listed analytes, name and DOB dropped), reader confirms values, flags from the printed range, draw timing, alignment of cycle + symptoms + labs, interpretation with guardrails. Plan: [`docs/plans/blood_test_plan.md`](docs/plans/blood_test_plan.md). Done |
| Not built (dropped) | Prediction model and wearable data (Apple Health, Fitbit): only synthetic data, no suitable wearable data |
| Not deployed | Runs locally; Render + Streamlit Cloud planned |

Run the UI: `streamlit run ui/app.py` (uses `API_BASE_URL` if a `uvicorn app.api.main:app` is running, otherwise the API in-process).
Run the API (optional): `uvicorn app.api.main:app --reload`
Run the tests: `pytest` (112 tests; the RAG ones need `.env` keys).
Generate a report (cycle + symptoms + labs):
```bash
python -m app.agent.run --dataset demo_synthetic_perimenopause --user synth_peri \
  --intake samples/archives/persona_4_intake.json --labs-json samples/demo_labs_peri.json \
  --out samples/report_1_perimenopause.md
```

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
| API | Used for |
|---|---|
| **OpenAI** (`gpt-5.4-mini` + embeddings) | Writes the findings draft and the reader report; embeds coaching chunks and queries |
| **Supabase** (Postgres + pgvector) | Stores and searches the RAG chunks (`documents` table, RLS on) |
| **Resend** | Emails the report to an address the user enters |
| **FastAPI** (own) | `/health /upload /users /cycles /stats /labs /demos` |

## Environment variables
Copy `.env.example` to `.env` and fill in. Never commit `.env`.

| Variable | Purpose |
|---|---|
| `OPENAI_API_KEY`, `OPENAI_MODEL` | OpenAI key and model name |
| `SUPABASE_PROJECT_URL`, `SUPABASE_API_KEY`, `SUPABASE_DB_PASSWORD` | Supabase RAG store (service key) |
| `RESEND_API_KEY`, `EMAIL_FROM` | Email sending |
| `API_BASE_URL` | Running FastAPI URL; empty = UI uses the API in-process |
| `APP_PASSWORD` | Optional UI password |
| `KAGGLE_API_KEY` | Only to re-download demo datasets |

## Setup / run
Uses a conda env (Python 3.12), not a venv:

```bash
conda activate ironhack
pip install -r requirements.txt
cp .env.example .env   # then fill in keys
```
Then: `streamlit run ui/app.py`. The RAG store needs `python scripts/setup_supabase.py` (once) and `python -m app.rag.ingest` (after editing `rag_docs/`).

## File map
```
app/api        FastAPI (upload, cycles, stats, labs)
app/analysis   normalise + pandas stats (code does all arithmetic)
app/labs       lab PDF parser
app/agent      LangGraph: state, graph, nodes, labs, symptoms, age norms, explain, run (CLI)
app/rag        ingest / retrieve (Supabase pgvector)
app/email.py   Resend sender
ui/app.py      Streamlit UI
rag_docs/      instruction + reference chunks embedded into RAG
samples/       demo inputs and example reports
scripts/       setup + demo data generators
tests/         pytest (112 tests)
```

## Docs
- `docs/plans/implementation-plan.md`: phased plan and current status
- `docs/PROJECT_DRAFT.md`: design draft
- `stack_decision.md`: why LangGraph (n8n secondary)
- `docs/kaggle_datasets.md`: dataset evaluation and findings
- `docs/agent_extensions.md`: proposed extensions (case triage, events, charts, symptom tool, guardrail) and target graph
- `docs/img/graph_minimal.png`, `docs/img/graph_full.png`: slide-ready diagrams of the core and extended agent graph (`scripts/draw_graphs.py`)
- `docs/graph.mmd`: LangGraph diagram (Mermaid, generated)
- `docs/rag_design.md`: chunking, embeddings, retrieval settings and the PDF plan
- `gtm_future_sprints.md`: 3 go-to-market sprints (repo root)
- `docs/report_improvements.md`: how the report was reworked
- `samples/full_demo_cycle_report.md` (+ `report_graphic.png`): full report on real data (cycle, blood tests, symptoms), the quality showcase. `samples/`: demo inputs, two synthetic example reports (`report_1_*`, `report_2_*`), `archives/` for older runs

## Data credits
Demo data is synthetic. Sources (via Kaggle): `puspitachowdhury2/menstrual-health-dataset` (CC BY-NC 4.0, non-commercial) and `akshayas02/menstrual-cycle-data-with-factors-dataset` (CC0). Files in `samples/` are normalised derivatives of these, plus a generated perimenopause example.
