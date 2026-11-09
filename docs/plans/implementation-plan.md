# Implementation Plan: Menopause Analysis

Design reference: `../../PROJECT_DRAFT.md`. Rubric: see bottom.
Deadline: **Fri 13 Nov 2026, 11:00** (Day 5 is only until 11:00).

## STATUS (update before ending every session)

- **Current phase:** 0 (not started)
- **Last completed:** repo created, drafts written (`PROJECT_DRAFT.md`, `GTM_SPRINT_REPORT.md`), CLAUDE.md + README + this plan
- **Next action:** Phase 0 — folder skeleton, `.env.example`, venv, `requirements.txt`
- **Blockers / decisions pending:** Kaggle dataset, OpenAI model, Clue export format (see Open questions)

## Resume protocol
1. Read STATUS above, then the phase you're in.
2. Finish tasks in order; tick boxes as you go.
3. Run the phase's exit check before moving on.
4. Update STATUS (phase, last completed, next action, blockers).

## Target layout
```
app/api/        FastAPI (main.py, models.py, sheets.py)
app/analysis/   pandas stats (stats.py)
app/agent/      LangGraph (state.py, nodes.py, graph.py)
app/rag/        ingest.py, retrieve.py
app/email.py    Resend sender
ui/app.py       Streamlit
rag_docs/       markdown docs to embed
data/raw/       Clue + Kaggle files (GITIGNORED)
samples/        generated reports (demo data only)
tests/
docs/plans/     this file
```

---

## Phase 0 — Setup (Mon)
- [ ] Add data ignores to `.gitignore` (`data/raw/`, `*.clue.csv`); confirm `.env` is ignored
- [ ] Create folder skeleton above
- [ ] `.env.example`: `OPENAI_API_KEY`, `GOOGLE_SERVICE_ACCOUNT_JSON`, `SHEET_ID`, `PINECONE_API_KEY`, `PINECONE_INDEX`, `RESEND_API_KEY`, `EMAIL_FROM`, `API_BASE_URL`, `APP_PASSWORD`
- [ ] venv + `requirements.txt` (fastapi, uvicorn, pandas, pydantic, gspread/google-api-python-client, langgraph, langchain-openai, pinecone, streamlit, resend, pytest, python-dotenv)
- **Exit:** `python -c "import langgraph, fastapi, streamlit"` succeeds

## Phase 1 — Scope & stack (Mon)
- [ ] `stack_decision.md`: LangGraph primary (agent + RAG + validation loop + tool calls fit a graph; n8n secondary for simple triggers/glue), 3–5 sentences
- [ ] Choose Kaggle dataset (check licence + columns); note it in STATUS
- [ ] Report template draft (adapt to columns available)
- [ ] Workflow sketch ≤10 boxes (in README)
- [ ] Rename `GTM_SPRINT_REPORT.md` → `gtm_future_sprints.md` (required name, repo root); sprint titles final
- **Exit:** `stack_decision.md`, `gtm_future_sprints.md` exist at root

## Phase 2 — Data & APIs (Mon–Tue)
- [ ] Google Cloud project, enable Sheets API, service account, share Sheet with its email
- [ ] Inspect Clue export; write `scripts/normalise.py` → schema `user_id, cycle_start, cycle_length, period_length, age?` (+ any flow-intensity column)
- [ ] Load Kaggle + synthetic into a **demo** Sheet; Clue into a separate **private** Sheet
- [ ] Test each key alone: OpenAI, Sheets read, Pinecone, Resend (script per key under `scripts/`)
- **Exit:** ≥3 APIs tested (rubric), keys in `.env` only

## Phase 3 — FastAPI + stats (Tue)
- [ ] `app/analysis/stats.py`: cycle length mean/SD, rolling variability, trend slope, skipped/long cycles, period intensity if available
- [ ] Pytest on stats with hand-computed fixtures
- [ ] `app/api`: `GET /health`, `/cycles?user_id=`, `/stats?user_id=`; Pydantic response models; in-memory cache of Sheet reads
- **Exit:** tests pass; `uvicorn app.api.main:app` serves `/docs`

## Phase 4 — RAG grounding (Tue)
- [ ] Write `rag_docs/`: reference ranges (cited, check sources), one instruction doc per report section, tone/disclaimer rules
- [ ] `ingest.py` chunk + embed + upsert; `retrieve.py` top-k by section
- [ ] Retrieval test: 3 queries return the expected doc
- **Exit:** retrieval works standalone

## Phase 5 — Graph skeleton (Tue)
- [ ] State schema; nodes Fetch → Analyse → Retrieve → Write → Check (stubs)
- [ ] Each tool/node callable and tested alone
- **Exit:** graph runs end-to-end with stubs
- Use Context7 for current LangGraph API before coding

## Phase 6 — Autonomous core (Wed)
- [ ] Fetch calls the FastAPI endpoints (not the Sheet directly)
- [ ] Write: OpenAI, structured sections, uses only stats + retrieved text
- [ ] Check: extract every number from the report, compare to stats; on mismatch return to Write (max 2 retries)
- [ ] CLI: `python -m app.agent.run --user <id> --out samples/report_1.md`
- **Exit:** **first full report** saved (ugly is fine)

## Phase 7 — Harden (Thu)
- [ ] Retries/backoff on Sheets, OpenAI, Pinecone; clear errors for missing data
- [ ] Cleaner report structure + disclaimer on every report
- [ ] 2nd sample report from a different user/source
- **Exit:** 2 reports in `samples/`

## Phase 8 — UI & email (Thu)
- [ ] Streamlit: password gate, user/source select, Generate, render report + chart, email field + Send
- [ ] `app/email.py` via Resend; rate-limit (e.g. 3 sends/session); no report storage
- **Exit:** full flow works locally with demo data

## Phase 9 — Deploy (Thu)
- [ ] FastAPI on Render; set env vars on host
- [ ] UI on Streamlit Community Cloud; point `API_BASE_URL` at Render
- [ ] Demo data only on public deployment; Render free tier cold start noted in README
- **Exit:** public URL generates and emails a report

## Phase 10 — Docs & demo (Thu–Fri)
- [ ] README complete (setup, run, file map, architecture, tool/API list, env vars)
- [ ] Slides; demo script 5–7 min: autonomy, report, stack rationale, GTM sprints
- [ ] Recording link in README; final secrets check (`git log -p | grep -i key`)
- [ ] Submit repo URL before Fri 11:00
- **Exit:** rubric checklist all ticked

---

## Rubric checklist
- [ ] Working MVP: trigger → tools → structured report (LangGraph, runnable, entrypoint in README)
- [ ] `stack_decision.md`
- [ ] `gtm_future_sprints.md` (2–3 sprints: goal, user/buyer, channel, deliverable, metric)
- [ ] ≥2 sample reports in `samples/`
- [ ] README: setup, run, file map, architecture, ≥3 tools/APIs, env vars, no secrets
- [ ] Demo 5–7 min, link in README

## Risks
See `PROJECT_DRAFT.md` §9. Top two: Clue data leaking (gitignore + demo-only deployment), LLM numbers drifting (Check node).

## Open questions
- OpenAI model + budget
- Kaggle dataset (needs per-user cycle lengths)
- Clue export columns (is period intensity available?)
- Resend sender verification (may limit sends to own address)
