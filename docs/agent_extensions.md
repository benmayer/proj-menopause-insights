# Agent extensions: proposal for review

Status: **proposal, not built.** The core graph (Fetch → Analyse → Retrieve → Write → Check) is deliberately simple. Plan: build it for real (Phase 6), read the first reports, then add logic only where the results show a gap. Do not add nodes before there is a reason.

## Why extend at all
One generic report does not fit everyone. A 29-year-old with irregular cycles needs different framing from a 47-year-old with a lengthening pattern or someone with no period for 12 months. Advice from the coaching material also depends on the person's situation and symptoms.

## Decisions (Ben, 10 Nov)
- Age field in the UI (optional) when the file has none: **yes**.
- Symptom tool: **yes, build it**.
- Add **data visualisation** and **dated events** so the report can point at specific occurrences (see below).

## Proposals (in suggested order)

### 1. Case triage node (deterministic, no LLM) — recommended
New node after Analyse. Sets `state["case"]` from age and the stats, then a conditional edge picks the report variant and the retrieval filter.

| Case | Rough trigger (thresholds to confirm from sources) | Report approach |
|---|---|---|
| `young_irregular` | age under about 40 and irregular cycles | Do **not** frame as perimenopause. Other common causes (stress, PCOS, thyroid, contraception, pregnancy); suggest a GP visit. Stopping periods before 45: NHS says speak to a GP |
| `typical_pattern` | about 40-55 with growing variability or lengthening | Full report, advice section on |
| `stable` | no flags | Short report: reassurance, tracking tips, no flags section |
| `no_period_12m` | 12+ months since last start | NHS: any bleeding then needs a GP. Different template |
| `low_data` | fewer than 6 cycles | Short report that says what data is needed |
| `age_unknown` | no age (Clue has none) | Neutral framing; UI asks for age (optional field) |

Cheap, testable with fixtures, and it keeps the LLM out of the decision.

### 2. Retrieval by case
Tag chunks with an audience (`young`, `peri`, `post`, `all`). Retrieve filters by the triaged case so advice matches the person. Needs the `metadata jsonb` column already planned for PDFs (see `rag_design.md`).

### 3. Red-flag check (deterministic) — recommended
In Analyse or a tool. Flags that always say "see a GP": periods longer than 7 days, bleeding between periods, heavier bleeding than before, any bleeding after 12 months without a period (NHS list in `rag_docs/reference_ranges.md`). Clue data has `spotting` entries that can feed this.

### 4. Symptom tool — high value, check after first reports
`get_symptom_summary(dataset_id, user_id)` on FastAPI. The Clue export logs pain, sleep, energy, mood, skin and more; the normaliser currently ignores them. Frequencies and trends per symptom would let the Retrieve and advice steps match coaching advice to symptoms ("sleep trouble" → sleep advice). Kaggle set B has pain, mood and sleep columns for the demo. Symptom data is more sensitive; same local-only rule for Clue.

### 4b. Events and visuals (new, decided)
Today `stats.py` only returns counts. To say "you skipped a period in December, the first time in your data" we need **events**: a deterministic list, computed in `stats.py` and returned by `/stats`.

```
events: [{type: "skipped_cycle", date: "2025-12-03", length_days: 64, first_time: true},
         {type: "long_cycle", ...}, {type: "jump", date, change_days}, {type: "short_cycle", ...},
         {type: "longest_cycle", ...}, symptom spikes later]
```
- `first_time` = no earlier event of that type in the data (computed, never guessed by the LLM).
- The Write node may only mention dates and events that exist in this list. The Check node verifies dates as well as numbers.
- The advice step pairs an event with retrieved guidance: what it can mean, what to look out for, when to see a GP.
- **Charts** (matplotlib, built from `cycle_series` + events; shown in Streamlit and embedded in the email as an image):
  1. Cycle length over time, shaded 21-35 day reference band, events marked and labelled with dates.
  2. Rolling variability (SD) over time.
  3. Later: symptom frequency by month, flow/period length.
- Report text refers to the chart ("see the marked point in Dec 2025").

### 5. Guardrail node before the end
Deterministic scan of the final report: disclaimer present, no diagnostic phrases ("you have", "you are in perimenopause"), no doses, every advice item traceable to a retrieved chunk with a citation. Extends the Check node's number check.

### 6. Agentic search tool — probably skip for the MVP
Letting the LLM call `search_knowledge(query)` itself is more flexible but less predictable and harder to check. The fixed Retrieve node is easier to test and explain.

## How to review (before building any of it)
1. Finish Phase 6 and generate reports for five personas: young irregular, mid-40s with the synthetic pattern, stable 30s, no period for 12 months, very few cycles.
2. Read them. Note where the output is wrong, generic or risky.
3. Build only the extensions that fix what you saw. Likely first: 1, 3, then 5.

## Cost and timing
Deadline is Fri 13 Nov 11:00 and Phases 7-10 (hardening, UI, deploy, demo) come first. Rough effort: triage + router 1-2 h, red flags 1 h, guardrail 1 h, symptom tool 2-3 h, case-tagged retrieval 1 h. Anything not done goes into the GTM sprints as the product roadmap.

## Still open
- What does the coaching material say about different life stages? That should set the age thresholds, not my guesses.
- Which symptoms to cover first (the Clue export has pain, sleep, energy, feelings, skin, digestion, discharge, cravings, exercise, spotting).

## Target graph if all proposals are built
```
START
  │
fetch ─────── stats + dated events + symptoms (FastAPI endpoints)
  │
analyse ───── flag rules + red-flag check (deterministic)
  │
triage ────── case: young_irregular | typical_pattern | stable | no_period_12m | low_data  (uses age if given)
  │
  ├── low_data ─────────────────────────────┐ (skips advice retrieval, short template)
  │                                         │
  ├── retrieve (filtered by case) ──┐       │
  └── chart (matplotlib PNGs) ──────┤ parallel
                                    ▼       ▼
                                  write (template chosen by case)
                                    │
                                  check ───── numbers + dates match stats/events? ── no ─┐
                                    │ yes                                                │
                                  guardrail ─ disclaimer, banned phrases, advice cited? ─ no ─┤
                                    │ yes                                                │
                                   END ◄──── back to write, max 2 retries ◄──────────────┘
                                    │
                         report.md + charts → Streamlit / email
```

| | Core (now) | Full |
|---|---|---|
| Nodes | 5 | 8 (+ triage, chart, guardrail) |
| Branches | 1 (retry loop) | 3 (case router, parallel retrieve/chart, two-stage retry) |
| LLM calls | 1 (Write) | 1 (Write), everything else deterministic |
| Data tools | `/stats` | `/stats` with events, `/symptoms`, charts |

The shape stays the same: only Write uses an LLM; everything that decides, measures or verifies is plain code.
