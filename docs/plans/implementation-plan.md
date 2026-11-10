# Implementation Plan: Menopause Analysis

Design reference: `../PROJECT_DRAFT.md`. Rubric: see bottom.
Deadline: **Fri 13 Nov 2026, 11:00** (Day 5 is only until 11:00).

## STATUS (update before ending every session)

- **Current phase:** 3 (Phases 0-2 done; report template deferred, see Phase 1). **Today (Tue 10 Nov):** Phases 3, 4, 5 (goal: RAG retrieval working, each tool tested alone, empty graph skeleton)
- **Last completed:** Phase 0 (skeleton, conda env, `requirements.txt`, `.env.example`); Phase 1 (`stack_decision.md`, Kaggle datasets chosen and explored, workflow sketch in README, synthetic generator added to Phase 2). Phase 2 (key tests for OpenAI/Supabase/Resend, normaliser, synthetic generator, demo CSVs in `samples/`). Earlier: repo created, drafts written (`docs/PROJECT_DRAFT.md`, `docs/plans/gtm_future_sprints.md`), CLAUDE.md + README + this plan. Decisions: vector store = **Supabase (pgvector)**, not Pinecone; **stretch** = own prediction model (Phase 11), wearables (Phase 12)
- **Next action:** Phase 3 — `app/analysis/stats.py` + pytest, then `app/api` (`store.py`, `/health`, `/upload`, `/cycles`, `/stats`). Then Phase 4 (enable pgvector, RAG docs), Phase 5 (graph skeleton). Report template stays TBD until stats exist
- **Env:** conda env `ironhack` (Py 3.12), not venv. Env var names follow `.env`: `SUPABASE_PROJECT_URL`, `SUPABASE_API_KEY` (verify it is the service/secret key in Phase 2), `SUPABASE_DB_PASSWORD`
- **Decisions:** Google Sheets dropped; data enters via CSV upload. MVP holds uploads in memory only (`app/api/store.py`, swappable for Supabase later). Persistence, accounts, consent/GDPR = first GTM sprint
- **Blockers / decisions pending:** ~~Kaggle dataset~~ (decided), OpenAI model, Clue export format (see Open questions)

## Resume protocol
1. Read STATUS above, then the phase you're in.
2. Finish tasks in order; tick boxes as you go.
3. Run the phase's exit check before moving on.
4. Update STATUS (phase, last completed, next action, blockers).

## Target layout
```
app/api/        FastAPI (main.py, models.py, store.py)
app/analysis/   pandas stats (stats.py)
app/agent/      LangGraph (state.py, nodes.py, graph.py)
app/rag/        ingest.py, retrieve.py (Supabase pgvector)
app/ingest/     STRETCH: apple_health.py, fitbit.py
app/ml/         STRETCH: train.py, predict.py, models/ (gitignored artifacts)
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
- [x] Add data ignores to `.gitignore` (`data/raw/`, `*.clue.csv`); confirm `.env` is ignored
- [x] Create folder skeleton above
- [x] `.env.example`: `OPENAI_API_KEY`, `SUPABASE_PROJECT_URL`, `SUPABASE_DB_PASSWORD`, `SUPABASE_API_KEY`, `RESEND_API_KEY`, `EMAIL_FROM`, `API_BASE_URL`, `APP_PASSWORD`
- [x] conda env `ironhack` + `requirements.txt` (fastapi, uvicorn, pandas, pydantic, langgraph, langchain-openai, supabase, streamlit, resend, pytest, python-dotenv)
- **Exit (met):** `python -c "import langgraph, fastapi, streamlit"` succeeds

## Phase 1 — Scope & stack (Mon)
- [x] `stack_decision.md` (repo root): LangGraph primary (agent + RAG + validation loop + tool calls fit a graph; n8n secondary for simple triggers/glue), 3–5 sentences
- [x] Choose Kaggle dataset (check licence + columns); note it in STATUS. Done: primary `menstrual-health-dataset` (puspitachowdhury2), secondary `menstrual-cycle-data-with-factors-dataset` (akshayas02); see `docs/kaggle_datasets.md`
- [ ] Report template draft (adapt to columns available). **Deferred** to after Phase 3, when real stats exist; draft sections are in `docs/PROJECT_DRAFT.md` §7
- [x] Workflow sketch ≤10 boxes (in README)
- [ ] `docs/plans/gtm_future_sprints.md` exists; sprint titles final. Rubric wants it at repo root, so copy/move there by Phase 10
- **Exit:** `stack_decision.md` exists; GTM file exists (root by Phase 10). **Met.**

## Phase 2 — Data & APIs (Mon–Tue)
- [x] ~~Google Cloud / Sheets~~ **Dropped**: data enters via CSV upload (Streamlit → FastAPI `POST /upload`, held in memory, never stored)
- [x] Normaliser (`app/analysis/normalise.py`, used by upload + `scripts/build_demo_data.py`; Clue export format still to inspect when it arrives) → schema `user_id, cycle_start, cycle_length, period_length, age?` (+ any flow-intensity column)
- [x] `scripts/synth_perimenopause.py` (done: `synth_peri` + control `synth_stable`): generate a labelled-synthetic demo user with a known perimenopause pattern (rising cycle variability, gradual lengthening, one skipped cycle). Seeded, so reproducible. Neither Kaggle set contains a trend (see `docs/kaggle_datasets.md`); this makes the Pattern/Flags sections fire and gives Check a known truth
- [x] Export normalised demo CSVs (Kaggle + synthetic) to `samples/`; Clue stays local, uploaded by hand
- [x] Test each key alone (`scripts/test_*.py`): OpenAI OK (embeddings 1536 dims + chat), Supabase OK (secret key, direct DB connects; **pgvector not yet enabled**, do in Phase 4), Resend key valid but send-only, so real send test in Phase 8; sender domain `menohelp.app` set up by user (confirmed 10 Nov)
- **Exit (met):** ≥3 APIs tested (rubric), keys in `.env` only

## Phase 3 — FastAPI + stats (Tue)
- [ ] `app/analysis/stats.py`: cycle length mean/SD, rolling variability, trend slope, skipped/long cycles, period intensity if available
- [ ] Pytest on stats with hand-computed fixtures
- [ ] `app/api/store.py`: dataset store behind a tiny interface (in-memory dict now; Supabase table later)
- [ ] `app/api`: `GET /health`, `POST /upload` (CSV → normalise → in-memory, returns `dataset_id`), `/cycles?dataset_id=&user_id=`, `/stats?...`; Pydantic response models
- **Exit:** tests pass; `uvicorn app.api.main:app` serves `/docs`

## Phase 4 — RAG grounding with Supabase (Tue)
- [ ] Supabase project; enable `vector` extension; table `documents(id, section, content, source, embedding vector(1536))`; SQL match function (cosine, top-k, filter by section)
- [ ] Write `rag_docs/`: reference ranges (cited, check sources), one instruction doc per report section, tone/disclaimer rules
- [ ] `ingest.py` chunk + embed (OpenAI embeddings) + insert; `retrieve.py` calls the match function
- [ ] RLS on; service key used server-side only, never in the UI
- [ ] Retrieval test: 3 queries return the expected doc
- **Exit:** retrieval works standalone
- Verify current Supabase vector API with Context7 before coding

## Phase 5 — Graph skeleton (Tue)
- [ ] State schema; nodes Fetch → Analyse → Retrieve → Write → Check (stubs)
- [ ] Each tool/node callable and tested alone
- **Exit:** graph runs end-to-end with stubs
- Use Context7 for current LangGraph API before coding

## Phase 6 — Autonomous core (Wed)
- [ ] Fetch calls the FastAPI endpoints (not the CSV directly)
- [ ] Write: OpenAI, structured sections, uses only stats + retrieved text
- [ ] Check: extract every number from the report, compare to stats; on mismatch return to Write (max 2 retries)
- [ ] CLI: `python -m app.agent.run --user <id> --out samples/report_1.md`
- **Exit:** **first full report** saved (ugly is fine)

## Phase 7 — Harden (Thu)
- [ ] Retries/backoff on OpenAI, Supabase; validate uploads (columns, size, dates); clear errors for missing data
- [ ] Cleaner report structure + disclaimer on every report
- [ ] 2nd sample report from a different user/source
- **Exit:** 2 reports in `samples/`

## Phase 8 — UI & email (Thu)
- [ ] Streamlit: password gate, CSV upload (or pick a bundled demo file), Generate, render report + chart, email field + Send
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

## Phase 11 — STRETCH: own prediction model (only if core is done)
Gate: Phase 6 finished by Wed and Kaggle data has enough users/cycles per user. Never delay Phases 7–10 for this.
- [ ] Pick one narrow target, e.g. next cycle length, or "irregular next cycle" (binary)
- [ ] Features: last N cycle lengths, rolling mean/SD, age if available. Split by **user**, not by row, to avoid leakage
- [ ] Baseline first (mean of last 3 cycles), then scikit-learn model (e.g. gradient boosting); compare on held-out users
- [ ] Save model artifact (gitignored or small file); `app/ml/predict.py`; FastAPI `/predict`
- [ ] Add a Predict tool/node to the graph; report shows prediction with uncertainty and "estimate, not medical advice"
- [ ] Report the honest result: if it doesn't beat the baseline, say so (still a valid finding)
- **Exit:** metric vs baseline documented in README

## Phase 12 — STRETCH: wearable data (Apple Health, Fitbit)
Gate: core done (Phase 10). Local only; never in the public demo (health data).
- [ ] **Verify current API status first** (Context7/vendor docs): Fitbit Web API endpoints and auth; Google Fit REST is being retired in favour of Health Connect. Pick what still works
- [ ] Apple Health: Streamlit upload of the export ZIP, parse `export.xml` (cycle, sleep, heart rate, temperature if present) in `app/ingest/apple_health.py`
- [ ] Fitbit: OAuth2 flow + fetch sleep/heart rate (and cycle data if exposed) in `app/ingest/fitbit.py`
- [ ] Normalise into the existing schema + daily signals table; expose via FastAPI (`/signals`)
- [ ] Analyse: simple correlation between cycle variability and sleep/HR trends; mention as exploratory, not causal
- [ ] Document consent and data-handling in README
- **Exit:** one wearable source flows through to the report

## Rubric checklist
- [ ] Working MVP: trigger → tools → structured report (LangGraph, runnable, entrypoint in README)
- [ ] `stack_decision.md`
- [ ] `gtm_future_sprints.md` (2–3 sprints: goal, user/buyer, channel, deliverable, metric)
- [ ] ≥2 sample reports in `samples/`
- [ ] README: setup, run, file map, architecture, ≥3 tools/APIs, env vars, no secrets
- [ ] Demo 5–7 min, link in README

## Risks
See `docs/PROJECT_DRAFT.md` §9. Top two: Clue data leaking (gitignore + demo-only deployment), LLM numbers drifting (Check node).

## Open questions
- OpenAI model + budget
- Kaggle dataset (needs per-user cycle lengths)
- Clue export columns (is period intensity available?)
- Resend sender verification (may limit sends to own address)
- Stretch: does the Kaggle dataset have enough users/cycles for a meaningful model?
