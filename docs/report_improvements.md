# Improving the reader report: what we changed, learned and fixed

12 Nov 2026. Three feedback rounds on the full demo report (real cycle data, blood tests and symptoms of the test user, run locally only).
All examples below use **synthetic persona values**, not the test user's data.

---

## 1. Starting point

Pipeline (LangGraph):

```
Fetch → Analyse → Triage → Retrieve → Write → Check (retry) → Interpret → Guardrail (retry) → Report
         code      code      RAG        LLM     code             LLM          code
```

Only **Write** (facts report) and **Interpret** (reader report) call the LLM. Everything else is code or retrieval.

### What the first full report got wrong (feedback round 1)
- Hard to follow: cycle, blood tests and symptoms were treated as three separate reports and never combined.
- No summary at the top, and disclaimers scattered through every paragraph.
- It spoke *about* its sources ("the table lists…", "the source says…") instead of speaking as a coach to the reader.
- Cycles were not compared with what a typical cycle looks like.
- Symptoms: every symptom area was looked up separately ("breast tenderness can be caused by X, Y, Z") instead of giving one overall picture.
- A very low AMH for a woman in her early 30s was described only as "within the printed range". That was technically true and missed the main point.
- Irrelevant lines: a thyroid paragraph even though all thyroid values were normal.

### Root cause
Most of these problems came from **our own prompt and guardrail**, not from the model:
- The outline forced one section per data source, so nothing was combined.
- The guardrail required a citation on every line, so the model wrote "the table lists…" to attach one.
- A fixed rule always mentioned thyroid.
- Nothing in code said whether a value is low *for the reader's age*, so the model had nothing to base that on.

---

## 2. The principle we sharpened

> **Code computes, RAG explains, the LLM writes, code verifies.**

| Job | Who does it | Example |
|---|---|---|
| Numbers and comparisons | Code | cycle length vs the typical 21–35 days; AMH vs healthy women of the same age |
| Which explanations the data supports | Code (`explain.py`) | "ovarian change: supported by AMH; thyroid: measured and normal" |
| What a finding *means*, and advice | RAG (coaching material) | what a lower egg reserve means; what can help with PMS |
| Turning it into readable text | LLM | the report |
| Checking the text | Code (guardrail) | numbers match, no diagnosis wording, no unbacked "low" claims |

The LLM got it wrong every time we let it judge a value itself. It invented percentiles, and it called a normal AMH at 46 "very low for your age". Each time, the fix was to have code compute the judgement and hand the LLM the exact wording.

---

## 3. Round 1: report rework

### Structure and voice
- New outline: **Summary**, then Your cycle, Your blood results and Your symptoms, then What it could mean together, Talking to your doctor and Things that may help.
- Coach voice: "your blood results show". No "the material says". Sources are shown only by tags.
- At most **one** short step-back sentence, placed after a pointed claim. General caveats (single snapshot, cycle-day timing, not a diagnosis) moved into a fixed **"How to read this report"** block that code writes once at the end.

### Cycle compared with typical cycles (code)
`compare_cycles()` puts the reader's numbers next to typical values:
- Average and recent average vs the typical 21–35 days.
- Variation vs a few days: bands for typical, more than typical and much more than typical.
- How often consecutive cycles changed by 7 or more days.

### Age norms for lab values (code, not RAG)
- `app/agent/age_norms.py` holds per-year AMH percentiles from **Ji et al. 2022** (Ann Lab Med, 1,429 healthy women aged 19–54).
- `age_norm()` looks up the reader's age at the blood draw, smooths over ±2 years, converts units and returns a band plus a plain sentence written by code, e.g. *"very low for age 31: lower than in 95 of 100 healthy women of this age"*. It also returns the age at which the value would be typical ("typical for women around 46").
- **Why a lookup and not RAG:** this needs an exact row and exact numbers. A similarity search can return the wrong row, and the LLM would then have to read the table and compare values itself, which is exactly the step it got wrong.
- A short description of the study is added to the context, so the report can still cite it.

### Cross-source reasoning (code: `app/agent/explain.py`)
Each candidate cause (ovarian change, thyroid, iron, prolactin, androgens/PCOS, progesterone) gets:
- **relevance:** which symptoms and cycle signals point to it (weighted by strength),
- **evidence:** what the blood values say (supports / contradicts / not measured),
- a **status:** supported, contradicted or untested.

Rule (general, replacing the thyroid-only rule): *If cycle and symptoms point to something but the blood results show it's normal, don't mention it, unless the lead was strong and nothing else explains the picture.* Untested causes are suggested as tests only if the lead is clear, and at most two of them.

### Symptoms as one picture (code)
Code computes the symptom load (number of areas, how many are strong or moderate). The prompt asks for a short overview, not one lookup per symptom.

### New guardrail checks
- Ban on source talk ("the table lists", "according to the source").
- **Hormone claims:** "your FSH is high" is allowed only if code backs it (outside the lab's range, or below the age norm).
- **Low for age:** blocked unless the age norm says so, with a specific error message for the retry.
- **Cycle claims** are blocked for readers whose cycle is not natural (pill or hormonal coil).

### Synthetic test personas
Four personas cover the edge cases:
- a young reader with low AMH,
- a 46-year-old with typical perimenopause labs,
- a pill user,
- a reader with cycle data only.

All are generated, with no real values (see the privacy lesson below).

---

## 4. Round 1.5: the "still bad" report that was stale code

The second review still showed the old headings and wording. **Cause:** Streamlit had been running since the morning. It reloads files in `ui/` but **not** the imported agent code in `app/`, so the UI was still running the old pipeline.
**Fix:** restart Streamlit after changes in `app/`. Now noted in the plan's STATUS.

---

## 5. Round 2: reader view vs audit view

Feedback: no warning banner at the top, citations don't help the reader, and the blood results need better formatting.

- **Two views of one report.** The LLM still writes the cited draft, and the guardrail checks that draft. Then `reader_report()` (code) removes the tags and adds the group headings:
  - **Summary**
  - **What we found:** Your cycle · Your blood results · Your symptoms
  - **Conclusion:** What it could mean together · Talking to your doctor · Things that may help
- **New "Quality" tab** in the UI: check status, retries, the sources behind the report, and the report with tags. The warning banner moved there.
- **The cycle leads the conclusion:** start with what the cycle pattern can point to, then the blood results support or qualify that picture, and symptoms add context. For pill users it starts from the blood results instead.
- **One timing note** for all blood tests instead of one per draw. The word "printed" is banned; the report says "the lab's range".
- **Fixes found in the persona runs:**
  - The LLM called AMH 0.12 at age 46 "very low for your age", although it is typical at 46. Guard plus retries failed three times, because each retry samples again from the same prior.
    - **Fix at the source:** the evidence text now says "below the lab's range, *which is usual at age 46*", and the prompt names the values that are normal for the reader's age.
    - Result: it passed on the first try.
  - The diagnostic-wording rule ("you have…") also blocked "you have one skipped cycle". It now allows counts, and still blocks "you have PCOS".

---

## 6. Round 3: less template, plainer language

Feedback: the fixed block layout (headline, result, meaning) read worse than before, "very low" was repeated, and the conclusion was hard to read.

- **Back to flowing bullets**, now with the full name: *"Your AMH (anti-Müllerian hormone) of 0.42 ng/ml is very low for age 31: …"*. The comparison is said **once**.
- **Code writes the lists of other values.** Out-of-range values that mean little alone ("Also outside the lab's range: LH, prolactin…") and the in-range list are added by code, so the LLM only writes about the values that matter. The guardrail flags it if the LLM repeats them.
- **Plain-language conclusion:** short sentences, one idea each, everyday words ("the hormone levels seen after menopause", not "postmenopausal range"), at most 3 sentences per paragraph.
- **Internal terms banned** in the reader text ("untested", "supported explanation").

---

## 7. What we learned

1. **Look at your own instructions first.** The worst output came from our outline and guardrail rules, not from the model.
2. **Never let the LLM judge a value.** Comparisons and bands are computed; the LLM gets the wording. Every exception went wrong.
3. **Fix the input rather than adding retries.** A guard plus a retry resamples the same mistake. Giving the model correct evidence fixed it on the first try.
4. **Reference data is a lookup, not RAG.** Exact rows and numbers belong in code (or a data file). RAG is for meaning and advice.
5. **Make rules general.** "Don't mention thyroid when it's normal" became "don't mention any cause the blood results rule out".
6. **Guards can be too broad or too narrow.** "You have…" blocked harmless counts, and internal words like "untested" leaked until a guard caught them. Every new guard needs a test for both cases.
7. **Readers and auditors need different views.** Citations stay, because they let us verify that advice comes from the coaching material, but they belong in the Quality tab, not the report.
8. **Template the facts, not the prose.** Fixed lists written by code are reliable. A rigid layout for the whole section made the report read worse. The balance: code writes lists and numbers, the LLM writes the sentences around them.
9. **Test with personas.** Young, perimenopausal, pill and cycle-only readers each broke a different rule.
10. **Restart the app before reviewing.** One review round was lost to stale code.
11. **Privacy needs active care.** Personas and tests must use generated values. Real values copied by mistake were found and replaced; the real report stays in `samples/private/` (gitignored).

---

## 8. Numbers

| | Before | After |
|---|---|---|
| Automated tests | 92 | 111 |
| Persona reports passing the guardrail | mid-rework, 2 of 4 still failed after 3 retries | 4 of 4, with 0–1 retries (round 2) |
| Who decides "low for age" | LLM (invented) | code (age norm, Ji et al. 2022) |
| Citations in the reader report | on every line | none (in the Quality tab) |

---

## 9. Open points
- The round-3 changes pass all 111 tests, but the four personas have **not** been rerun against the LLM since the last edits (the run was stopped). Rerun them, then regenerate the real report locally.
- Symptom ideas not built yet:
  - describe the shape of the symptom load (broad vs one dominant area),
  - link each symptom to the finding it fits,
  - start from the reader's top concern.
- Nothing is committed yet.

### Main files
`app/agent/nodes.py` (Interpret prompt, `reader_report`, guardrail) · `app/agent/explain.py` (cross-source reasoning) · `app/agent/age_norms.py` (AMH age norms) · `app/agent/labs.py` (lab summary, names) · `ui/app.py` (Quality tab) · `tests/test_explain.py`, `tests/test_lab_pipeline.py`
