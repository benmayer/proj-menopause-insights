# Stack decision

Menohelp reads cycle data, blood tests and symptoms, so an unsourced claim or a hallucinated number is a serious risk. That is why the pipeline is a checked loop, not a straight line.

## Choice: LangGraph for orchestration

### Why: the report needs checks

The report is built from sensitive health data. An unsourced claim, a number that is not in the data, or diagnosis or dosing wording is a serious risk, so guardrails are part of the design. The model cannot check its own draft, so code does it:

- `check` verifies that every number and date in the findings draft exists in the stats, findings or reference text.
- `guardrail` verifies the reader report: required sections, citations that exist, no uncited advice, and no banned or diagnostic wording.

A failed check has to send the draft back to be rewritten. That makes the pipeline a loop with shared state, not a straight line, and a straight line would not need an orchestration framework. Code decides the facts and the rules (what is true, which case applies, what may be said). The model only writes the text.

### The pipeline

```
fetch → analyse → triage → retrieve → write → check ⟲ write
      → interpret → guardrail ⟲ interpret → end
```

Only `write` and `interpret` generate text with the language model. The other six are plain code (`retrieve` also calls an embedding model for search). The route after each check is a plain function (`route_after_check`, `route_after_guard`), and each loop stops after 2 retries, after which the report is flagged.

### Why LangGraph fits

- **Loops are edges.** The retry from `check` to `write` and from `guardrail` to `interpret` is a conditional edge with a counter in state. The retry limit is visible in one place and cannot become an endless loop.
- **Typed shared state.** `AgentState` holds stats, findings, retrieved chunks, both drafts, error lists and retry counters. Each node reads what it needs and returns only what it changes, so every step can be unit-tested with a hand-built state (`tests/test_graph.py`, `tests/test_lab_pipeline.py`).
- **Deterministic routing.** The model never decides which step runs next. Python functions inspect the check results.
- **Rules as testable code.** The check rules are many, and they need unit tests. They live in ordinary Python functions, which fits better than visual nodes.

### Alternatives considered

| Option | Why not |
|---|---|
| **n8n** | Good for triggers and delivery (for example a scheduled email). The checks are many coded rules that need unit tests, and these would be hard to test or review as visual nodes. n8n stays a candidate for the scheduling and integration work in the go-to-market sprints. |
| **Plain Python script** | A script with two `while` loops would also run this pipeline. LangGraph adds a dependency, and in exchange the steps, state and loops are named and can be drawn. For a one-person project the gain is small. |
| **LangChain agent with tools (model chooses the next step)** | Suits open-ended tasks. This pipeline has a fixed order and strict rules about what the model may do, so letting the model route would add risk and no benefit. |
| **Multi-agent frameworks (CrewAI, AutoGen)** | There is one task with one writer, not several roles that need to negotiate. |

### What we do not use

LangGraph also offers checkpointing, human-in-the-loop interrupts and streaming. This project uses none of them. Uploads are held in memory for about an hour, and a report run takes one request. If the pilots in sprint 1 need saved runs or manual review before sending, checkpointing and interrupts are the features to add.

## Supporting choices

| Part | Choice | Reason |
|---|---|---|
| Data layer | FastAPI + pandas | The API returns computed stats, so the model sees aggregates and never raw cycle rows. |
| Knowledge base | Supabase (Postgres + pgvector) | Documents, embeddings and similarity search in one managed service. Chosen over Pinecone to avoid a second account. |
| Language model | OpenAI `gpt-5.4-mini` + embeddings | Writes the findings draft and the reader report. Model name is set by `OPENAI_MODEL`. |
| UI | Streamlit | Upload, report, findings and quality tabs, and the email button, in one Python file. |
| Email | Resend | Sends the report to an address the user enters. |
| Hosting | Render (API) + Streamlit Community Cloud (UI) | Planned, not yet deployed. |
