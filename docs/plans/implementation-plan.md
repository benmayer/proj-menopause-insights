# Implementation Plan: Menopause Analysis

Design reference: `../PROJECT_DRAFT.md`. Rubric: see bottom.
Deadline: **Fri 13 Nov 2026, 11:00** (Day 5 is only until 11:00).

## STATUS (update before ending every session)

- **Current phase:** Streamlit UI built (`ui/app.py`, demo/upload, age, report, chart, findings, email button; email NOT yet send-tested). Next: symptom input + symptom cards, send test, deploy. Deadline Fri 13 Nov 11:00
- **Last completed:** Phase 0 (skeleton, conda env, `requirements.txt`, `.env.example`); Phase 1 (`stack_decision.md`, Kaggle datasets chosen and explored, workflow sketch in README, synthetic generator added to Phase 2). Phase 5 (LangGraph skeleton: state, 5 stub nodes, router, graph, 4 tests); Phase 4 (pgvector + `documents` table + RLS, 8 rag_docs, ingest/retrieve, 5 live tests); Phase 3 (stats.py, FastAPI /health /upload /users /cycles /stats, store.py, 13 tests); Phase 2 (key tests for OpenAI/Supabase/Resend, normaliser, synthetic generator, demo CSVs in `samples/`). Earlier: repo created, drafts written (`docs/PROJECT_DRAFT.md`, `docs/plans/gtm_future_sprints.md`), CLAUDE.md + README + this plan. Decisions: vector store = **Supabase (pgvector)**, not Pinecone; **stretch** = own prediction model (Phase 11), wearables (Phase 12)
- **Findings and improvement plan:** `docs/findings_and_improvements.md`
- **Next action:** review `samples/persona_*.md` with Ben (symptom intake steps 3-4 done: quick form, symptom summary, triage node, symptom-table cards, new guardrails, 61 tests). Then: Resend send test, deploy (Render + Streamlit Cloud), README (file map, env vars, 3+ APIs), GTM file to repo root, demo video. Advanced form only if time. Apple Health / blood tests skipped (no sample data)
- **Env:** conda env `ironhack` (Py 3.12), not venv. Env var names follow `.env`: `SUPABASE_PROJECT_URL`, `SUPABASE_API_KEY` (verify it is the service/secret key in Phase 2), `SUPABASE_DB_PASSWORD`
- **Decisions:** Google Sheets dropped; data enters via CSV upload. MVP holds uploads in memory only (`app/api/store.py`, swappable for Supabase later). Persistence, accounts, consent/GDPR = first GTM sprint
- **Blockers / decisions pending:** ~~Kaggle dataset~~ (decided), ~~OpenAI model~~ (`gpt-5.4-mini`), Clue export format (see Open questions)

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
- [x] Normaliser (`app/analysis/normalise.py`, used by upload + `scripts/build_demo_data.py`; accepts CSV and JSON incl. Clue `measurements.json`; tests in `tests/test_normalise.py`) → schema `user_id, cycle_start, cycle_length, period_length, age?` (+ any flow-intensity column)
- [x] `scripts/synth_perimenopause.py` (done: `synth_peri` + control `synth_stable`): generate a labelled-synthetic demo user with a known perimenopause pattern (rising cycle variability, gradual lengthening, one skipped cycle). Seeded, so reproducible. Neither Kaggle set contains a trend (see `docs/kaggle_datasets.md`); this makes the Pattern/Flags sections fire and gives Check a known truth
- [x] Export normalised demo CSVs (Kaggle + synthetic) to `samples/`; Clue stays local, uploaded by hand
- [x] Test each key alone (`scripts/test_*.py`): OpenAI OK (embeddings 1536 dims + chat), Supabase OK (secret key, direct DB connects; **pgvector not yet enabled**, do in Phase 4), Resend key valid but send-only, so real send test in Phase 8; sender domain `menohelp.app` set up by user (confirmed 10 Nov)
- **Exit (met):** ≥3 APIs tested (rubric), keys in `.env` only

## Phase 3 — FastAPI + stats (Tue)
- [x] `app/analysis/stats.py`: cycle length mean/SD, rolling variability, trend slope, skipped/long cycles, period intensity if available
- [x] Pytest on stats with hand-computed fixtures (`tests/test_stats.py`, `tests/test_api.py`; 13 passing)
- [x] `app/api/store.py`: dataset store behind a tiny interface (in-memory dict now; Supabase table later)
- [x] `app/api`: `GET /health`, `POST /upload` (CSV → normalise → in-memory, returns `dataset_id`), `/cycles?dataset_id=&user_id=`, `/stats?...`; Pydantic response models
- **Exit (met):** tests pass; `uvicorn app.api.main:app` serves `/docs`; real Clue file uploads and returns stats. Extras: `/users`, `/demos` (bundled `demo_*.csv` preloaded)

## Phase 4 — RAG grounding with Supabase (Tue)
- [x] Supabase project; enable `vector` extension; table `documents(id, section, content, source, embedding vector(1536))`; SQL match function (cosine, top-k, filter by section)
- [x] Write `rag_docs/` (8 files, 13 chunks; reference ranges from NHS + STRAW+10; **re-check wording against the sources before the demo**; "before 45" came from an NHS Scotland guideline, not the main NHS page): reference ranges (cited, check sources), one instruction doc per report section, tone/disclaimer rules
- [x] `ingest.py` chunk + embed (OpenAI embeddings) + insert; `retrieve.py` calls the match function
- [x] RLS on; service key used server-side only, never in the UI
- [x] Retrieval test: 4 queries return the expected doc + section filter (`tests/test_rag.py`, live, needs keys)
- [x] **4b PDF pipeline** (DONE 11 Nov: `app/rag/ingest_pdf.py`, 5 MenoCert German modules in gitignored `rag_docs/knowledge/`, 316 chunks, bibliography dropped, `metadata jsonb` doc/page, German retrieval queries; run `python -m app.rag.ingest_pdf`). Original plan: (after the skeleton; see `docs/rag_design.md`): coaching-material PDFs → extract/clean/chunk (≈400 tok, 10-15% overlap) → `knowledge` section with title+page metadata; add `metadata jsonb`; `.gitignore` `rag_pdfs/`; confirm licence/reuse first
- **Exit (met):** retrieval works standalone. Schema in `sql/001_documents.sql`, applied by `scripts/setup_supabase.py`; ingest with `python -m app.rag.ingest`
- Verify current Supabase vector API with Context7 before coding

## Phase 5 — Graph skeleton (Tue)
- [x] State schema; nodes Fetch → Analyse → Retrieve → Write → Check (stubs)
- [x] Each tool/node callable and tested alone (`tests/test_graph.py`; API, stats, normaliser and RAG have their own tests)
- **Exit (met):** graph runs end-to-end with stubs; the Check→Write retry loop (max 2) is tested. Diagram: `docs/graph.mmd`
- Use Context7 for current LangGraph API before coding

## Phase 6 — Autonomous core (Wed)
- [x] Fetch calls the FastAPI `/stats` (not the CSV directly; `/cycles` not needed, the LLM never sees rows)
- [x] Write: OpenAI `gpt-5.4-mini`, structured sections, uses only stats + retrieved text
- [x] Check: extract every number and date from the report, compare to stats; on mismatch return to Write (max 2 retries)
- [x] CLI: `python -m app.agent.run --dataset <id> --user <id> --out samples/report_1.md` (in-process API by default, `--api URL` for a live server)
- **Exit (met):** `samples/report_1.md` (synth_peri) and `report_2.md` (synth_stable), both verified first try. 28 tests

Added after first report: two-layer output. `report` (verified findings) -> Interpret (reader-facing meaning/advice, only from cited `knowledge` chunks, tags [S#]) -> Guardrail (code: citations exist and every meaning/advice line cited, numbers/dates from stats, no dose/diagnosis/medication-change wording, young readers never framed as menopause). Graph: fetch, analyse (flags + case tags), retrieve (tag-driven German queries), write, check, interpret, guardrail. 40 tests.

## Phase 6b — Review & extend (after first report)
Proposal in `docs/agent_extensions.md`: case triage node, red-flag check, guardrail node, symptom tool, case-tagged retrieval. Generate 5 persona reports first, read them, then build only what the results justify. Time-box; Phases 7-10 take priority.
- [x] **Events**: `stats.py` returns a dated `events` list (skipped/long/short cycle, jump, longest) with `first_time`; add to `/stats`; hand-computed tests. Check node verifies dates too
- [ ] **Symptom tool**: normaliser keeps Clue symptom entries (separate long table); `/symptoms` endpoint: frequency per symptom, per month, trend; used by Retrieve/advice
- [ ] **Age**: optional age field in the UI, passed to the graph when the file has none
- [ ] Generate persona reports; review with Ben
- [ ] Decide which extensions to build; log the rest as roadmap in GTM file

## Phase 7 — Harden (Thu)
- [ ] Retries/backoff on OpenAI, Supabase; validate uploads (columns, size, dates); clear errors for missing data
- [ ] Cleaner report structure + disclaimer on every report
- [ ] 2nd sample report from a different user/source
- **Exit:** 2 reports in `samples/`

## Phase 8 — UI & email (Thu)
- [ ] Streamlit: password gate, CSV upload (or pick a bundled demo file), Generate, render report + charts (matplotlib: cycle length with 21-35 band and labelled events; rolling variability; later symptoms), email field + Send (chart embedded as image)
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
- ~~OpenAI model~~ Decided: `gpt-5.4-mini` (env `OPENAI_MODEL`; verified working 10 Nov). Budget still open
- Kaggle dataset (needs per-user cycle lengths)
- ~~Clue export columns~~ Resolved: `measurements.json` has daily `period` entries with flow (light/medium/heavy), 89 cycles 2019-2026; no age. Local only in `data/clue/` (gitignored)
- Resend sender verification (may limit sends to own address)
- Stretch: does the Kaggle dataset have enough users/cycles for a meaningful model?
