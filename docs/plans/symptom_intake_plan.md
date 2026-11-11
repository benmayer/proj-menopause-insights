# Plan: symptom intake, quick vs advanced report, Apple Health (for review)

Goal: make reports specific. Today the only personal input is cycle dates (see `docs/findings_and_improvements.md`).
Deadline Fri 13 Nov 11:00, so each step says what is in and what is cut.

## 1. What the new documents are and how we use them

| File (`rag_docs/knowledge/`) | What it is | Use |
|---|---|---|
| `MenoCert - Symptomfragebogen.pdf` | 3-page onboarding form: 34 symptoms rated 0-3, cycle history, lifestyle, worries | **Design template for the UI form.** Not ingested |
| `MenoCert SKRIPT Webinar 2 - Tabellen und Grafiken II.pdf` | One table: organ system, possible symptoms, possible hormonal factors | **Reverse lookup** (symptom -> possible factors). Becomes the *symptom map* (section 3) |
| `Cheat Sheet - Diagnose peri- vs. postmenopausal` | Diagnostic flowchart | **Exclude.** Diagnosis conflicts with our "never diagnose" rule |
| `Cheat Sheet - Toolkit ...`, `Übersicht Komorbidität und Hormontherapie` | Hormone-therapy options and contraindication tables | **Exclude.** Prescribing information; our rule is "HT = an option to discuss with a GP" |
| `Cheat Sheet - Beratungsgespräch` | 7-step coaching conversation | Inspiration for report flow only. Not ingested |
| `Ernährungsdokumentation` | Blank food diary | Ignore |
| `modules/` (5 module PDFs) | Already ingested (316 chunks) | Keep |

**Housekeeping bug to fix first.** You moved the modules into `modules/`. `ingest_pdf.py` only reads the top folder and *deletes all
`knowledge` rows before inserting*, so re-running it now would wipe the modules and ingest the cheat sheets. Fix: read
`modules/**/*.pdf` only (explicit allow-list), so forms and clinical tables can never enter the RAG.

## 2. Quick vs advanced report

| | Quick (default, about 1 min) | Advanced (about 5-8 min) |
|---|---|---|
| Inputs | Age (optional), last period (approx.), tick the **body systems** where you notice changes (the 15 rows of the MenoCert table, each with 2-3 example symptoms), rate only the ticked ones 1-3, one line: "what bothers you most?" | All 34 symptoms in body-system groups (0-3), most bothersome, cycle history and what changed, hormonal contraception/HT yes/no, chronic condition yes/no, lifestyle (stress 0-10, activity, alcohol, smoking, diet self-rating), worries, what already helped |
| Report | Current structure plus "What your symptoms may point to" and symptom-specific help | Adds symptom overview by body system, lifestyle section, and "Questions to bring to your doctor or coach" |
| LLM cost | About the same as now | About 1.5x (longer prompt) |

Left out of both: name, height, weight, last gynaecology visit, family history details, medication names (sensitive, low value).

## 3. Using the symptom table "in reverse" (the symptom map)
- Turn the table into `rag_docs/symptom_map.md`: one chunk per organ system (15), each listing its symptoms and the
  "possible hormonal factors" (e.g. thermoregulation: hot flushes, sweating, feeling cold; factors: oestrogen deficiency,
  thyroid disorder). New RAG section `symptom_map`, source cited as MenoCert webinar table.
- **Deterministic lookup, not fuzzy search.** A small dict (`app/agent/symptoms.py`) maps each form symptom to a body system; Retrieve then
  fetches the cards for the systems the reader rated above 0. Precise and testable.
- Interpret gets a new section **"What your symptoms may point to"**: for each reported system, name the factors the table lists as
  *possible* contributors, and say several causes can look the same.
- **New guardrails:** never "your oestrogen/progesterone is low" or any statement about measured levels (we have none); wording must be
  "can be linked to" / "the material lists". Banned-pattern test added.
- Deterministic **red flags** (from `docs/agent_extensions.md`) for symptoms like palpitations, panic attacks, severe low mood or
  painful sex rated 3: fixed text pointing to a doctor or professional support, not LLM-written.

## 3b. Learning from the diagnosis flowchart (triage node)
We do not reproduce the diagnosis. We borrow its **routing logic** to choose *how to analyse and write*, as a deterministic
`triage` node (plain code, no LLM) between Analyse and Retrieve. The flowchart asks, in this order: how long since the last period
and was bleeding regular; any hormonal contraception or HT; hysterectomy, hormonal coil, endometrial ablation or ovaries removed;
age; hot flushes or night sweats. Those become 5 yes/no inputs in the form, and the output is an internal **context category**, never shown as a label:

| Category | Rule (from the flowchart's branches) | Effect on the report |
|---|---|---|
| `masked_by_hormones` | combined pill / hormonal contraception / HT | Cycle data is artificial: skip trend and variability claims, say why, focus on symptoms |
| `no_period_12m` | last period more than 12 months ago | No cycle trend section; symptom-led, plus "worth discussing with a doctor" |
| `irregular_recent` | regular earlier, irregular within about 12 months | Full cycle analysis (today's report) |
| `regular` | regular recent cycles | Cycle section short; stable-pattern wording |
| `surgical_or_other` | hysterectomy, ablation, ovaries removed | Cycle data unreliable, symptom-led |
| `young` | under 40 (already built) | Never framed as transition |

Biggest single gain: the **contraception check**. Today a pill user would get a confident cycle trend that is meaningless.
The report may say "the material describes cycles becoming irregular within the final year before periods stop"; it never says
"you are perimenopausal" (guardrail unchanged). Age cut-offs from the chart (52 and 58) are shown to us only as routing, and
you wanted to verify age limits yourself, so they live in one constants block. Caveat: the chart is a clinician's tool adapted from
the 2023 Practitioner's Toolkit; we use only the logic, never its text, and it stays out of the RAG.

## 4. Pipeline changes
```
UI form -> state.symptoms/intake -> analyse (symptom summary + case tags) -> triage (context category) -> retrieve (symptom cards + symptom-specific knowledge)
        -> write findings -> check -> interpret (prioritise top 3) -> guardrail
```
- **Symptom summary computed in code** (counts per body system, top 3 by rating, number rated 2-3). The LLM does no arithmetic; Check
  allows only those numbers. We do not compute a clinical score or call anything a "menopause rating".
- **Case tags** combine cycle patterns, symptoms and age (e.g. `skipped + vasomotor + 46`), steering German retrieval queries per top symptom.
- **Interpret prompt rewrite:** pick the 3 priorities from what the reader reported; tie each point to their input; group "Things that
  may help" by symptom; drop what the input does not support; hormone-therapy line only when flags or vasomotor/urogenital symptoms are present.
- Findings report stays facts-only and gains a symptom summary table.

## 5. Privacy
Symptoms and free text are health data and are sent to OpenAI to write the report. The UI says so before the form, asks users not to enter names,
keeps everything in session memory only, and does not log answers. GTM sprint 1 covers consent and GDPR properly.

## 6. Apple Health or blood test: pick one (recommendation: Apple Health, lightly)
| | Blood test values | Apple Health |
|---|---|---|
| Fit with our rules | Poor: interpreting lab values is medical interpretation; ranges depend on lab, cycle day and units. Our rule is "never diagnose" | Good: numbers computed in code, verified by Check, no medical claims |
| Usefulness in perimenopause | Low: the coaching material itself says FSH is cycle-dependent and fluctuates in perimenopause (Modul 4, p. 9-10) | Medium: sleep, resting heart rate and activity back up reported symptoms and lifestyle advice |
| Effort | OCR/PDF or manual entry, range table we do not have | Streaming parse of a huge export, local only |
| Demo | Needs real lab results | Needs your own export |

Choose blood tests only if you have real lab PDFs and a vetted range source. Otherwise Apple Health.

**Apple Health scope if built:** local script reads Export All Health Data (`export.xml`, streamed) and writes a small summary (average sleep and awake
time, resting heart rate trend, workout minutes per week, cycle records) that the form can pre-fill or the UI can upload. HealthKit is on-device only,
so a web app cannot read it live; the zip exceeds our 5 MB limit. Apple defines
[symptom identifiers](https://developer.apple.com/documentation/healthkit/symptom-type-identifiers.md) (hot flashes, night sweats, sleep changes), but how they appear in `export.xml`
is **unverified**: check with a real export first. Not needed for the rubric; build only after steps 1-5, otherwise GTM sprint 2 / Phase 12.

## 7. Order of work and cuts
1. **Fix ingest** (modules only, allow-list) and test. 15 min.
2. **Symptom map**: `symptom_map.md` (15 cards drafted from the table, you review), `symptoms.py` mapping, ingest, tests. 45 min.
3. **Quick form in the UI** (symptom picker, ratings, top concern) and state plumbing. 45 min.
4. **Pipeline**: symptom summary and tags, targeted retrieval, Interpret rewrite, new guardrails and red flags, tests. 1.5 h.
5. **Persona reports** (young irregular, mid-40s peri pattern plus hot flushes and sleep, stable 30s, long gap, few cycles) and your review. 45 min.
6. **Advanced form** only after steps 1-5 look good. 1-1.5 h.
7. Then the remaining deliverables: Resend send test, deploy, README, demo.

**Cut first if time runs out:** Advanced form, then red-flag extras. **Never cut:** quick form, symptom map, guardrails, deployment, README, demo video.

## Decisions
1. Quick form: 15 body-system ticks from the MenoCert table (not my earlier 12). **Decided 11 Nov.**
2. Diagnosis flowchart: not ingested; its logic is used as the triage node. Hormone-therapy tables stay out. **Decided.**
3. Symptom answers may go to OpenAI, with an in-UI notice. **Decided (Ben).**
4. Apple Health or blood test: Ben to confirm (recommendation above: Apple Health, after steps 1-5).
