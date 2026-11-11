# Plan: blood test upload and interpretation (for review)

Goal: let a reader upload a lab report (PDF) so the report can interpret hormone values together with cycle data and symptoms.
Deadline Fri 13 Nov 11:00. Interpretation is wanted; absolute diagnosis is not.

## Decisions (Ben, 11 Nov)
1. Interpret, don't diagnose. Hedged wording ("consistent with", "the material describes"), always with a doctor suggestion where it matters.
2. **Age is a soft signal, not a hard guardrail.** Under 40 makes transition less likely, not impossible (early menopause is in the material). If cycle, symptoms and labs align strongly, the report may say so, without a diagnostic label.
3. Use date of birth from the lab PDF: read in code only, to compute age at the draw and today. The DOB, name, address and lab number never reach the LLM, the API response or logs.
4. Sources for interpretation: the five module PDFs, `SLK 4.1`, and `rag_docs/lab_map.md` (transcribed from Modul 3 p. 60, reference ranges only, no therapy-target column).
5. Demo: the same person's Clue data and two lab PDFs, anonymised (consent given). Real files stay in gitignored `data/`.

## 1. Sample files (what the parser must handle)
Two digital (text) PDFs from a German fertility practice, 2022 and 2025. Layout is messy: value, unit, flag and range run together
(`FSH 10,74 mIU/ml3,5 - 12,5`, `LH 1,80-mIU/ml2,4 - 12,6`), decimal commas, a trailing `+` or `-` flag glued to the unit, ranges that wrap lines,
and in 2025 a cycle day (`ZT: 7`). Header holds personal data. The 2025 file adds AMH. Blood counts and an infection antibody are present and out of scope.

## 2. Parser (new, plain code: `app/labs/parse.py`)
- Extract text with pypdf (no OCR). Reject files over 5 MB or with no text layer ("scanned PDFs not supported yet").
- **Allow-list of analytes** with German and English aliases: FSH, LH, E2/Estradiol, Prog/Progesteron, AMH, Prol/Prolaktin, Testosteron, SHBG, DHEAS, FAI, TSH, fT3, fT4, Ferritin, TPO, HB, Androstendion. Everything else is ignored (infection serology never stored).
- One regex per analyte capturing: value (decimal comma), unit, range low/high (a lab range such as `0,17 ng/ml - 7,37 ng/ml` and `< 34.0` variants).
- **Flag computed by us** (below / within / above the printed range). The printed `+`/`-` glyph is ignored.
- Extract: draw date (`Entnahme`), cycle day (`ZT: n`, optional), DOB (used for age, then discarded).
- Output: `{draw_date, cycle_day, age_at_draw, results: [{analyte, value, unit, ref_low, ref_high, flag}]}`. Nothing else is kept.
- **Confirm step in the UI:** parsed values are shown in an editable table so the reader can fix a misread value before it is used. Parsing errors are the main risk; this is the safeguard.
- Several PDFs allowed (2022 + 2025): sorted by draw date.

## 3. API
- `POST /labs`: multipart PDF, returns parsed structure. Held in memory with the dataset TTL, never written to disk.
- `GET /labs?dataset_id=`: the confirmed values (the UI posts the edited table back via `PUT /labs`).
- Real files are never logged; error messages never echo file content.

## 4. LangGraph changes (no new node; shape unchanged)
```
fetch (+labs) -> analyse (+lab summary) -> triage (+lab context) -> retrieve (+lab queries) -> write (+Lab values) -> check (+lab numbers)
              -> interpret (+blood test section) -> guardrail (+lab rules) -> end
```

| Node | Change |
|---|---|
| State | `labs`: list of draws; `lab_summary`. |
| Fetch | Reads labs from the API (optional). |
| Analyse | `summarise_labs` in code: per analyte flag, value vs printed range, change between draws (absolute and percent), cycle day at draw, and whether the draw phase fits the analyte (FSH on cycle day 2-5 is the most comparable; a day-19-21 progesterone is the ovulation check). Also a **lab alignment** tag: counts of signals pointing the same way (irregular cycles, FSH above range, low E2, symptoms rated strong). Computed in code, never by the LLM. |
| Triage | Hormonal contraception or HT makes sex-hormone values uninformative: added caveat, same as the cycle caveat. `young` stops suppressing; it becomes a context note. |
| Retrieve | German queries per analyte that is out of range, plus FSH, E2, TSH when present. Pulls `lab_map` cards by exact title (like `symptom_cards`) and top `knowledge` chunks per analyte. AMH queries target Modul 3 chunks (POI, ovarian reserve). |
| Write (findings) | New facts-only "Lab values" section: value, unit, printed range, flag, date, cycle day. |
| Check | Allows exactly the lab numbers, dates and the computed changes. |
| Interpret | New section **"What your blood test may show"**: ties values to cycle and symptoms, cites `lab_map` and `knowledge` chunks, states limits (one snapshot, cycle phase, FSH swings in the transition). Prioritises what matters most. Wording tiers below. |
| Guardrail | Rules below. |

### Wording tiers (Interpret prompt and guardrail)
- Allowed: "above the range printed on your report", "in the range the material lists for the late transition", "consistent with", "the material describes", "worth discussing with a doctor".
- Allowed under 40 if alignment is high: "your values and cycle pattern are in line with what the material describes as an early transition; this is uncommon at your age, so a doctor should check it".
- Banned: "you are in menopause / perimenopause / have POI" as a label, "you have a thyroid disorder", anything that says a level is the cause, dosing, starting or stopping medication, "no need to see a doctor".
- Hormone therapy stays gated (flags, temperature or sexuality symptoms, or the reader asked).
- Code-written **safety lines** (not LLM): TSH out of range gets "thyroid values outside range are worth a doctor's check"; very high FSH or no period for 12 months or more plus young age gets "see a doctor".

### Age rule change
`YOUNG_BANNED` currently bans transition wording for under-40 readers outright. Replace with: banned labels always; transition wording only when `lab alignment` reaches a threshold *and* the report includes the doctor line. Threshold and wording go in one constants block; Ben reviews.

## 5. RAG
- Done: `lab_map.md` (10 cards), `SLK 4.1` ingested (4 chunks), 320 knowledge chunks.
- Add `lab_map` cards for AMH and prolactin once Ben supplies a source (not in the Module 3 table; Module 3 text mentions AMH).
- Each lab card keeps the unit gotcha (fT4 ng/dl vs ng/l). Interpret always compares to the range printed on the report.
- Done (11 Nov): audit of all PDFs for image-only content. 34 tables/charts transcribed into `rag_docs/image_transcripts/modul_2..5.md` (German, reviewed by Ben) and ingested as `knowledge` chunks (354 total). Key ones for labs: Modul 3 p. 29 (STRAW+10: FSH over 25 IU/L, cycle criteria), p. 57 (draw timing), p. 59 (hormone ratios), Modul 2 p. 20 and 26 (before/after menopause, by life phase), p. 33 (draw timing).

## 6. UI (step 1)
- New "Blood tests (optional)" block: upload one or more PDFs, editable table of parsed values with flags, privacy note (values go to OpenAI, name and address are never sent).
- Step 2: the report gains the blood test section; the findings tab gains the lab table; optional small chart of each analyte across draws with its range band.

## 7. Tests
- Parser unit tests on **synthetic fixtures** shaped like the real PDFs (generated with reportlab, committed). Real files stay gitignored; Ben's anonymised PDFs go in `data/bloodtests/` and `samples/` only if fully anonymised.
- Parser: decimal comma, glued units, wrapped ranges, `+/-` flags ignored, DOB never in output, unknown analytes dropped, no text layer rejected.
- Analyse: flags, change between draws, alignment tag.
- Check: lab numbers allowed, invented numbers rejected.
- Guardrail: banned labels, thyroid claim, absolute wording, young reader with and without alignment, doctor line required.
- UI: upload, confirm table edit, the lab values reach the graph.
- E2E mock run with labs, then a real-model run for the demo persona.

## 8. Order of work
Status: step 1 (parser) and step 2 (API `/labs` POST/GET/PUT/DELETE, `LabStore`, state `labs_id`/`labs`, Fetch, age from lab DOB) are DONE. Step 3 DONE too: `app/agent/labs.py` (summarise_labs, draw-timing, changes with comparable flag, align_labs, thresholds block), analyse + triage wiring, `young` no longer blocks the irregular category, 79 tests. Next: step 4 retrieve + write + check.
1. Parser + fixtures + tests, run against the real PDFs locally (45 min)
2. API + state + fetch (30 min)
3. `summarise_labs` + alignment + triage changes + tests (45 min)
4. Retrieve + Write + Check (45 min)
5. Interpret prompt (`instr_interpret.md`), guardrail rules, age-rule change, tests (1.25 h)
6. UI: upload, confirm table, chart (1 h)
7. Demo persona run (anonymised Clue + labs), review with Ben (45 min)

Cut first: lab chart, AMH/prolactin cards. Never cut: confirm table, DOB handling, guardrails.

## 9. Risks
- **Misparsed value** → confirm table; Check only verifies consistency with parsed values, not with the PDF.
- **Over-interpretation** → code-computed alignment, wording tiers, guardrail on labels, human review of the demo report.
- **Single snapshot / cycle phase** → every lab statement carries the draw day and phase caveat.
- **Privacy** → DOB used in code only; only analyte, value, unit, range and age go to OpenAI; GTM sprint 1 covers consent.
- **Reference ranges differ by lab** → always the printed range first.
- **Sparse source material** → the material has no AMH or prolactin table; those stay descriptive until a source is added.
