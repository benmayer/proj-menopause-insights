# Kaggle dataset evaluation

Phase 1 task. Source: Kaggle public metadata API (descriptions, licences, sizes).
**Not yet verified:** actual CSV columns, rows, and cycles per user (needs download).

## Requirements
- Multiple cycles per user over time (trend and variability stats)
- Cycle length + start date; period/flow intensity is a bonus
- Age is a bonus (perimenopause context)
- Licence allows a public demo

## Candidates

| Dataset | Verdict | Licence | Size | Why |
|---|---|---|---|---|
| [puspitachowdhury2/menstrual-health-dataset](https://www.kaggle.com/datasets/puspitachowdhury2/menstrual-health-dataset) | **Primary** | CC BY-NC 4.0 | 1.9 MB | Synthetic. `Period_Log.csv` (cycle number, start date, cycle length, flow intensity, pain, PMS, mood, sleep, stress) linked by `user_id` to `User_Profile.csv` (age, BMI, PCOS, lifestyle). One-to-many gives a per-user time series. |
| [akshayas02/menstrual-cycle-data-with-factors-dataset](https://www.kaggle.com/datasets/akshayas02/menstrual-cycle-data-with-factors-dataset) | **Secondary** | CC0 | 95 KB | Synthetic, 100 users. Start date, cycle length, period duration, next-cycle start, age, BMI, lifestyle. Cleanest licence. Cycles per user unknown. |
| [kishakishani/menstrual-cycle-survey](https://www.kaggle.com/datasets/kishakishani/menstrual-cycle-survey) | Rejected | Unknown | 24 KB | One row per participant (survey), so no time series. |
| [jwiest/casestudycapstone](https://www.kaggle.com/datasets/jwiest/casestudycapstone) | Rejected for core | Unknown | 855 KB | Fitbit/Bellabeat case study; its own description says it has no menstrual data. Possible Phase 12 (wearables) reference only. |
| [mdabdulkaium/pcos-dataset](https://www.kaggle.com/datasets/mdabdulkaium/pcos-dataset) | Rejected | Unknown | 83 KB | PCOS classification features, not cycle history. |
| [wizdore/msmarcotrainingdoc](https://www.kaggle.com/datasets/wizdore/msmarcotrainingdoc) | Rejected | Unknown | 8.8 GB | MS MARCO search training data; unrelated. |

(The survey link was supplied twice.)

## Decision (pending column check)
Use **puspitachowdhury2** as primary and **akshayas02** as secondary. Two sources
let the two required sample reports come from different data and force the
normalisation step to be real.

## Caveats
- Both are **synthetic**: no genuine perimenopause signal. The demo proves the
  pipeline, not clinical findings. Reports built on them must say the data is
  synthetic. The real test is the Clue export.
- CC BY-NC 4.0 (primary): non-commercial use with attribution. Fine for the
  bootcamp demo; credit the author in the README. Not suitable for a commercial
  product without different data.
- Licence "Unknown" on the rejected sets is another reason not to rely on them.

## Verified findings (downloaded and explored)

| | A: akshayas02 | B: puspitachowdhury2 |
|---|---|---|
| Rows / users | 895 / 100 | 17,976 / 2,000 |
| Cycles per user (min/median/max) | 6 / 9 / 12 | 6 / 9 / 12 |
| Cycle length (median, SD) | **37**, 7.5 (min 25, max 50) | **28**, 2.4 (min 22, max 44) |
| Within-user SD (median) | 7.3 | 1.9 |
| Age range / users 40+ | 18-45 / 20 | 16-43 / 2 |
| Period length | yes (3-7 days) | no |
| Flow intensity | no | yes (`flow_level`: Light/Moderate/Heavy) |
| Extras | stress, sleep, diet, symptoms | pain, mood, hormones (estrogen/progesterone), `User_Profile` (age, BMI, PCOS) |
| Nulls | none | `prev_cycle_length` (first cycle per user, expected), `exercise_frequency` 385 |
| Cycle length == gap to next start date | 100% | 100% |
| Mean per-user trend slope (days/cycle) | +0.22 (SD 1.15) | 0.00 (SD 0.31) |

### What this means
- **B is the realistic one**: median 28 days, tight spread. Has flow intensity but no period length, and few users over 40.
- **A is noisy and unrealistic**: median 37 days with large random swings in every user, so almost every user looks "irregular". Has period length and more 40+ users, and every user has a constant age.
- **Neither contains a perimenopause trend.** Slopes average ~0, so the data is random variation, not a growing-variability pattern. An honest report on either will say "no clear trend".
- Cycle length always equals the gap to the next start date, so lengths are consistent with dates. The last cycle per user has no next start to check.
- Dates: B starts 2024-01-01 to 2025-04-05. A timestamps include microseconds and need trimming to dates.

### Implications for the build
- Normalisation maps both to `user_id, cycle_start, cycle_length, period_length?, flow?, age`. `period_length` is null for B, `flow` is null for A, so the schema and stats must tolerate missing columns.
- Use **B for the main demo** (realistic baseline) and **A as the second source** with a different data shape.
- Add a small **synthetic generator** (`scripts/`) producing a demo user with a built-in perimenopause pattern (rising variability, a skipped cycle, a gradual lengthening trend). This is the only way to show the Flag/Pattern sections firing, and it gives the Check node and a future prediction model a known truth. Label it clearly as synthetic.
- Hormone columns in B (estrogen, progesterone) are tempting but not needed for the core. Skip for now.

## Local files (`data/raw/`, gitignored)
| Folder | Keep? |
|---|---|
| `menstrual-health-dataset/` | **Keep** (primary) |
| `menstrual-cycle-data-with-factors-dataset/` | **Keep** (secondary) |
| `casestudycapstone/` | Delete (no menstrual data); re-download only if Phase 12 needs Fitbit samples |
| `menstrual-cycle-survey/` | Delete (one row per person, no time series) |
| `pcos-dataset/` | Delete (classification features, not cycle history) |
| MS MARCO (`wizdore`) | Never downloaded (8.8 GB, unrelated) |
