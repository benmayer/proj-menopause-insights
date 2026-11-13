"""Age-specific norms for lab values whose printed lab range ignores age (computed in code, never by the LLM).

Generic: `AGE_NORMS[analyte]` holds per-year percentiles; `age_norm(analyte, value, unit, age)` places a value.
Filled for AMH now, because the range a lab prints for AMH (e.g. 0.17-7.37 ng/ml) spans all ages, so a value can be
"within range" while being very low for the reader's age.

AMH source: Ji M, et al. Age Group-specific Reference Intervals for the Elecsys Anti-Müllerian Hormone Assay in Healthy
Korean Women: a Nationwide Population-based Study. Ann Lab Med 2022;42(6):621-629, doi:10.3343/alm.2022.42.6.621,
Supplemental Table S1 (1,429 healthy women aged 19-54, KNHANES, Elecsys assay; pmol/L).
Single years hold only 17-57 women, so we smooth over +-2 years (mean of the per-year percentiles; our heuristic).
"""
PMOL_PER_NG = 7.14  # AMH: 1 ng/ml = 7.14 pmol/L
SMOOTH_YEARS = 2

# age: (p5, p10, p25, p50) in pmol/L, copied from Ji et al. 2022, Table S1
AMH_PMOL = {
    19: (6.64, 13.00, 16.36, 31.29), 20: (13.14, 18.64, 23.57, 33.93), 21: (8.93, 13.00, 22.43, 32.93),
    22: (9.50, 14.71, 19.64, 28.36), 23: (16.71, 19.21, 23.00, 29.71), 24: (3.14, 7.36, 15.21, 25.43),
    25: (15.07, 18.79, 23.86, 32.21), 26: (8.71, 16.14, 19.50, 30.71), 27: (4.00, 12.14, 17.79, 33.00),
    28: (5.93, 6.64, 12.29, 26.64), 29: (8.21, 14.14, 16.57, 28.14), 30: (2.79, 5.64, 14.29, 19.93),
    31: (5.29, 10.43, 15.07, 25.71), 32: (2.43, 8.29, 16.71, 25.93), 33: (0.21, 6.00, 14.14, 23.79),
    34: (3.29, 5.43, 13.00, 23.79), 35: (1.86, 4.64, 8.93, 15.79), 36: (2.29, 5.00, 8.50, 16.43),
    37: (2.57, 4.64, 7.86, 13.43), 38: (4.00, 5.43, 7.93, 14.21), 39: (1.43, 5.00, 8.29, 13.14),
    40: (0.50, 1.43, 5.00, 10.00), 41: (1.14, 2.00, 4.36, 8.93), 42: (1.43, 2.79, 4.36, 9.43),
    43: (0.07, 0.50, 3.07, 7.64), 44: (0.07, 0.21, 1.57, 4.21), 45: (0.07, 0.29, 1.14, 3.86),
    46: (0.14, 0.43, 1.14, 1.93), 47: (0.07, 0.07, 0.07, 0.93), 48: (0.07, 0.07, 0.29, 0.64),
    49: (0.07, 0.07, 0.07, 0.29), 50: (0.07, 0.07, 0.07, 0.14), 51: (0.07, 0.07, 0.07, 0.07),
    52: (0.07, 0.07, 0.07, 0.07), 53: (0.07, 0.07, 0.07, 0.07), 54: (0.07, 0.07, 0.07, 0.07),
}
AMH_SOURCE = "Ji et al. 2022, Ann Lab Med: AMH by age in healthy women (Elecsys assay)"

AGE_NORMS = {"amh": {"table": AMH_PMOL, "to_unit": {"ng/ml": 1 / PMOL_PER_NG, "pmol/l": 1.0}, "source": AMH_SOURCE}}

# Plain-language position, from the bands below (used by the prompt and the guardrail)
BANDS = [("well_below", "p5"), ("below", "p10"), ("low_side", "p25")]
PLAIN = {"well_below": "very low for age {a}: lower than in 95 of 100 healthy women of this age",
         "below": "low for age {a}: lower than in 90 of 100 healthy women of this age",
         "low_side": "on the low side for age {a}: in the lowest quarter of healthy women of this age",
         "typical": "typical for age {a}"}


def _smoothed(table: dict, age: int) -> dict:
    ages = [a for a in range(age - SMOOTH_YEARS, age + SMOOTH_YEARS + 1) if a in table]
    rows = [table[a] for a in ages]
    return {k: sum(r[i] for r in rows) / len(rows) for i, k in enumerate(("p5", "p10", "p25", "p50"))}


def age_norm(analyte: str, value: float, unit: str, age: float | None) -> dict | None:
    """Where `value` sits among healthy women of the same age. None when there is no norm, age or matching unit."""
    norm = AGE_NORMS.get(analyte)
    if not norm or age is None:
        return None
    factor = norm["to_unit"].get((unit or "").lower())
    table = norm["table"]
    a = int(age)
    if factor is None or not min(table) <= a <= max(table):
        return None
    p = {k: round(v * factor, 2) for k, v in _smoothed(table, a).items()}
    position = next((name for name, key in BANDS if value < p[key]), "typical")
    # the age at which this value is the median (e.g. "typical for women around 45"); None if typical for own age
    typical_age = None
    if position != "typical":
        older = [x for x in sorted(table) if x > a and _smoothed(table, x)["p50"] * factor <= value]
        typical_age = older[0] if older else None
    return {"age": a, "unit": unit, "p5": p["p5"], "p10": p["p10"], "median": p["p50"], "position": position,
            "plain": PLAIN[position].format(a=a),
            "typical_for_age": typical_age, "source": norm["source"]}


def norm_card(analyte: str) -> dict | None:
    """A context chunk describing the norm, so the report can cite it like the coaching material."""
    if analyte != "amh":
        return None
    return {"id": "age_norm_amh", "section": "age_norm", "title": AMH_SOURCE, "source": "doi:10.3343/alm.2022.42.6.621",
            "content": "AMH falls steadily with age. In 1,429 healthy women, the median AMH was highest in the early 20s and "
                       "fell to very low levels by the late 40s. A value below the 10th percentile for one's age means "
                       "fewer than 1 in 10 healthy women of that age have a value this low. The range printed on a lab "
                       "report usually covers all ages, so a value can be inside it and still be low for one's age. "
                       "Values differ between assays and populations, so the norm is a guide, not a cut-off."}
