# Menopause Insights: Project Draft

> Status: draft v0.1. Items marked **(TBC)** need a decision.

## 1. Idea
An agent that reads menstrual cycle data, looks for patterns linked to the
perimenopause transition (e.g. growing cycle-length variability, skipped
cycles), and writes a custom report with plain-language context.
Not a diagnostic tool. Reports must carry a "not medical advice" note.

## 2. Architecture

```
Google Sheet ──(Sheets API)──▶ FastAPI ──(/cycles, /stats)──▶ LangGraph agent ──▶ Report
                                                                   │
                                                     RAG (vector DB): reference docs
                                                     + report instructions/templates
```

```
Streamlit UI ──▶ LangGraph agent ──▶ Report (on screen) ──▶ Email (Resend API)
```

Principle: **the LLM never sees raw data.** FastAPI returns computed stats;
the LLM only interprets and writes.

## 3. Components

| Layer | Tech | Job |
|---|---|---|
| Data source | Google Sheet | Holds Clue export + Kaggle data |
| Data API (consumed) | Google Sheets API (service account) | Live read access |
| Data API (designed) | FastAPI + Pydantic | `/cycles`, `/stats`, `/health` |
| Analysis | pandas | Cycle length, variability, trend, gaps |
| Agent | LangGraph | Orchestrates the steps below |
| LLM | OpenAI (model TBC) | Writes the report |
| RAG | Vector DB (Pinecone, TBC) | Reference knowledge + report instructions |
| UI | Streamlit (TBC) | Pick data source, generate report, view, email |
| Email | Resend API (TBC) | Send report to a user-entered address |
| Hosting | Render (FastAPI) + Streamlit Community Cloud (UI) (TBC) | Public URL |

## 4. LangGraph flow
1. **Fetch**: tool calls FastAPI endpoints
2. **Analyse**: deterministic stats (no LLM arithmetic)
3. **Retrieve**: RAG lookup of reference ranges and section instructions
4. **Write**: LLM drafts report from stats + retrieved context
5. **Check**: verify every number in the report matches computed stats;
   loop back to Write on mismatch

## 5. Data
- **Clue export**: my own data, one person. Real but small. Keep private;
  do not commit to git. Check export format on arrival **(TBC)**.
- **Kaggle**: dataset **(TBC)**; pick one with cycle lengths per user, ideally
  with age. Verify licence and columns before relying on it.
- **Normalisation**: map both sources to one schema:
  `user_id, cycle_start, cycle_length, period_length, age (optional)`.

## 6. RAG content (draft)
- Reference ranges for typical vs. variable cycle length (from a cited source)
- Report instructions, one short doc per section:
  summary, trend, variability, flags, caveats
- Tone and disclaimer rules

## 7. Report (target output TBD tepending on data availability in data)
1. Summary (3 lines)
2. Cycle length trend (chart) & Period intensity
3. Variability over time
4. Pattern recognitions, anything worth knowing 
5. Flags worth discussing with a doctor

## 8. Build order
. Sheet + Sheets API access (service account)
2. FastAPI wrapper, tested locally
3. LangGraph: Fetch → Analyse → Write
4. Add RAG, then Check loop
5. Streamlit UI (button → report on screen)
6. Email sending, then deploy FastAPI + UI
7. Evaluate on Clue data vs. Kaggle; write-up
## 9. Risks
| Risk | Mitigation |
|---|---|
| Health data privacy | Own data only; secrets and CSVs in `.gitignore`; redact before sharing |
| LLM hallucinated numbers | Check node; LLM never does arithmetic |
| Sounds like medical advice | Fixed disclaimer; wording rules in RAG |
| Small personal sample | Use Kaggle for volume; state the limits in the report |
| Sheets API quotas | Cache in FastAPI |
| Public URL exposes health data / email abuse | Demo uses Kaggle/synthetic data only; password gate on the UI; rate-limit sends; no report storage |
| Secrets (OpenAI, Google, Resend keys) | Env vars on the host, never in repo |

## 10. Open questions
- OpenAI model choice and budget
- Kaggle dataset choice
- Hosting choice (Render + Streamlit Cloud vs. all-in-one) and free-tier limits
- Email provider (Resend needs a verified sender/domain to send to others)
