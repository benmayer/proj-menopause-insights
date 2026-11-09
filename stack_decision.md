# Stack decision

**Primary: LangGraph.** The agent is a fixed pipeline with a validation loop (Fetch → Analyse → Retrieve → Write → Check, looping back to Write on a number mismatch), plus tool calls to an API and a vector store. A graph with typed state and conditional edges expresses that directly, keeps each step testable alone, and makes the retry limit explicit. It is also plain Python, so the stats code, FastAPI client and OpenAI calls need no glue layer.

**Secondary: n8n.** It suits simple triggers and glue (for example, a scheduled run that emails a report) but would hide the Check loop and the "LLM never does arithmetic" rule inside visual nodes. It is left for the GTM sprints, where scheduling and integrations matter more than agent logic.

**Supporting choices.** FastAPI exposes computed stats so the LLM never sees raw data. Supabase (Postgres + pgvector) holds the RAG documents in one managed service. OpenAI writes the report and creates embeddings. Streamlit and Resend cover the UI and email.
