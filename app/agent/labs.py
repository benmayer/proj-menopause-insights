"""Lab summary and alignment, computed in code (no LLM). Feeds `findings["labs"]`, which Check treats as allowed numbers.

Everything here is arithmetic on the values the reader confirmed plus the ranges printed on the report.
Thresholds come from the coaching material (page refs) and live in one block so they can be reviewed in one place.
"""
from app.agent.age_norms import age_norm

# --- thresholds (review these) -------------------------------------------------
FSH_LATE_TRANSITION = 25.0      # IU/L = mIU/ml. Modul 3 p. 29 (STRAW+10): above 25 in the late menopausal transition
EARLY_CYCLE_DAYS = (2, 5)       # FSH, LH, E2 "baseline" draw. Modul 3 p. 29 footnote (day 2-5), p. 57 (day 3), Modul 2 p. 33 (day 2-4)
LUTEAL_DAYS = (19, 23)          # progesterone: about day 21, 5-7 days after ovulation. Modul 2 p. 33, Modul 3 p. 57
AMH_LOW_POSITION = 10           # AMH in the lowest 10 % of the span printed on the report counts as "low end" (our heuristic, no source value)
ALIGN_HIGH, ALIGN_MODERATE = 4, 2   # number of agreeing signals for the level (our heuristic)
ALIGN_HIGH_YOUNG = 3  # under 40 the age signal cannot count, so one fewer is needed, but one must be a lab signal
LAB_SIGNALS = {"fsh_high", "e2_low", "amh_low"}

LABELS = {"fsh": "FSH", "lh": "LH", "e2": "oestradiol (E2)", "progesterone": "progesterone", "amh": "AMH",
          "prolactin": "prolactin", "testosterone": "testosterone", "shbg": "SHBG", "dheas": "DHEA-S", "fai": "free androgen index",
          "androstenedione": "androstenedione", "tsh": "TSH", "ft3": "free T3", "ft4": "free T4", "tpo": "TPO antibodies",
          "ferritin": "ferritin", "hb": "haemoglobin"}
# Reader-facing headline per analyte: full name and what the test is for (plain, neutral; matches rag_docs/lab_map.md)
ABOUT = {"fsh": ("FSH (follicle-stimulating hormone)", "drives the ripening of eggs; rises when the ovaries respond less"),
         "lh": ("LH (luteinising hormone)", "triggers ovulation; read together with FSH"),
         "e2": ("oestradiol (E2)", "the main oestrogen, made by the ovaries"),
         "progesterone": ("progesterone", "made after ovulation; shows whether ovulation took place"),
         "amh": ("AMH (anti-Müllerian hormone)", "a marker of egg reserve: how many eggs the ovaries still hold"),
         "prolactin": ("prolactin", "the milk hormone; high levels can disturb the cycle"),
         "testosterone": ("testosterone", "a male-type hormone that women make in small amounts"),
         "shbg": ("SHBG (sex hormone-binding globulin)", "a carrier protein that binds sex hormones in the blood"),
         "dheas": ("DHEA-S", "an adrenal hormone the body turns into other sex hormones"),
         "fai": ("free androgen index", "how much testosterone is free and active"),
         "androstenedione": ("androstenedione", "a precursor of testosterone and oestrogen"),
         "tsh": ("TSH (thyroid-stimulating hormone)", "the main check of thyroid function"),
         "ft3": ("free T3", "active thyroid hormone"), "ft4": ("free T4", "thyroid hormone"),
         "tpo": ("TPO antibodies", "a marker of an autoimmune thyroid condition"),
         "ferritin": ("ferritin", "the body's iron store"),
         "hb": ("haemoglobin", "the oxygen carrier in red blood cells; low with anaemia")}
GROUP = {**{k: "sex hormones" for k in ("fsh", "lh", "e2", "progesterone", "prolactin", "testosterone", "shbg", "dheas", "fai", "androstenedione")},
         "amh": "ovarian reserve", **{k: "thyroid" for k in ("tsh", "ft3", "ft4", "tpo")}, "ferritin": "iron", "hb": "iron"}
# lab_map card title per analyte (exact lookup), and German retrieval queries into the module chunks
LAB_CARD = {"fsh": "FSH (follicle-stimulating hormone)", "lh": "LH (luteinising hormone)", "e2": "Estradiol (E2)",
            "progesterone": "Progesterone", "tsh": "TSH (thyroid-stimulating hormone)",
            "ft3": "fT3 and fT4 (free thyroid hormones)", "ft4": "fT3 and fT4 (free thyroid hormones)",
            "shbg": "SHBG (sex hormone-binding globulin)", "testosterone": "Testosterone",
            "dheas": "DHEA-S (dehydroepiandrosterone sulfate)", "ferritin": "Ferritin (storage iron)"}
GENERAL_CARD = "How to read lab values"
LAB_QUERIES = {
    "fsh": "FSH Anstieg Perimenopause Menopause Laborwert Schwankung Interpretation",
    "lh": "LH FSH Verhältnis Laborwerte Perimenopause",
    "e2": "Östradiol Laborwert Perimenopause schwankend Zyklustag",
    "amh": "AMH Anti-Müller-Hormon Eizellreserve vorzeitige Ovarialinsuffizienz frühe Menopause",
    "tsh": "TSH Schilddrüse Ausschluss Schilddrüsenfunktionsstörung Symptome Wechseljahre",
    "progesterone": "Progesteron Lutealphase Gelbkörperinsuffizienz Laborwert Zyklustag 21",
    "general": "Laborwerte Blutentnahme Zyklustag Hormonwerte schwanken Aussagekraft Perimenopause",
    "early": "vorzeitige Menopause Ovarialinsuffizienz unter 40 Jahren Abklärung Symptome",
}


def lab_topics(labs: dict | None, young: bool = False) -> list[str]:
    """Which retrieval topics to run: always FSH/E2/TSH/AMH when measured, anything outside range, general reading tips."""
    if not labs:
        return []
    last = labs["draws"][-1]["results"]
    have = {r["analyte"] for r in last}
    topics = {a for a in ("fsh", "e2", "tsh", "amh") if a in have}
    topics |= {r["analyte"] for r in last if r["flag"] in ("below", "above") and r["analyte"] in LAB_QUERIES}
    out = ["general"] + sorted(topics)
    if young:
        out.append("early")
    return out


def lab_card_titles(labs: dict | None) -> list[str]:
    if not labs:
        return []
    have = [r["analyte"] for r in labs["draws"][-1]["results"]]
    titles = [GENERAL_CARD]
    for a in have:
        t = LAB_CARD.get(a)
        if t and t not in titles:
            titles.append(t)
    return titles


EARLY_CYCLE = {"fsh", "lh", "e2", "testosterone", "shbg", "androstenedione"}
# Values the pill, a hormonal coil or hormone therapy changes; not read as a natural signal when the reader uses them.
HORMONE_AFFECTED = {"fsh", "lh", "e2", "progesterone", "shbg", "testosterone", "fai", "dheas"}


def timing(analyte: str, cycle_day: int | None) -> tuple[str, str | None]:
    """('suitable'|'not_suitable'|'not_stated'|'any_time', note). Based on the draw-timing tables in the material."""
    if analyte in EARLY_CYCLE:
        lo, hi = EARLY_CYCLE_DAYS
        what = f"cycle day {lo} to {hi}"
    elif analyte == "progesterone":
        lo, hi = LUTEAL_DAYS
        what = f"cycle day {lo} to {hi}, about a week after ovulation"
    else:
        return "any_time", None
    if cycle_day is None:
        return "not_stated", f"no cycle day on the report; the material suggests {what}"
    ok = lo <= cycle_day <= hi
    return ("suitable" if ok else "not_suitable"), \
        f"drawn on cycle day {cycle_day}; the material suggests {what}"


POSITION_FOR = {"fsh", "amh"}  # where in the printed span a value sits; meaningless for very wide ranges (E2: 20-3000)


def _position(r: dict) -> int | None:
    lo, hi = r.get("ref_low"), r.get("ref_high")
    if r["analyte"] not in POSITION_FOR or lo is None or hi is None or hi <= lo:
        return None
    return round((r["value"] - lo) / (hi - lo) * 100)


def summarise_labs(draws: list[dict] | None, age: float | None = None) -> dict | None:
    """Per-draw values with flags, timing, position in the printed range and (where a norm exists) position among
    healthy women of the same age; changes between the first and last draw. `age` is used when a draw has no age."""
    if not draws:
        return None
    out_draws = []
    for d in sorted(draws, key=lambda d: d["draw_date"]):
        res = []
        for r in d["results"]:
            t, note = timing(r["analyte"], d.get("cycle_day"))
            draw_age = d.get("age_at_draw") if d.get("age_at_draw") is not None else age
            res.append({"age_norm": age_norm(r["analyte"], r["value"], r["unit"], draw_age),"analyte": r["analyte"], "label": LABELS.get(r["analyte"], r["analyte"]),
                        "group": GROUP.get(r["analyte"], "other"), "value": r["value"], "unit": r["unit"],
                        "ref_low": r.get("ref_low"), "ref_high": r.get("ref_high"), "flag": r.get("flag"),
                        "position_pct": _position(r), "timing": t, "timing_note": note})
        out_draws.append({"date": d["draw_date"], "cycle_day": d.get("cycle_day"), "age_at_draw": d.get("age_at_draw"),
                          "results": res})
    last = out_draws[-1]
    changes = []
    if len(out_draws) >= 2:
        first = out_draws[0]
        old = {r["analyte"]: r for r in first["results"]}
        for r in last["results"]:
            o = old.get(r["analyte"])
            if o and o["unit"] == r["unit"] and o["value"]:
                changes.append({"analyte": r["analyte"], "label": r["label"], "unit": r["unit"],
                                "from_date": first["date"], "to_date": last["date"],
                                "from_value": o["value"], "to_value": r["value"],
                                # cycle-dependent values are only comparable when both draws were on a suitable cycle day
                                "comparable": (o["timing"] == r["timing"] == "any_time") or (o["timing"] == r["timing"] == "suitable"),
                                "change": round(r["value"] - o["value"], 2),
                                "change_pct": round((r["value"] - o["value"]) / o["value"] * 100, 1)})
    outside = [{"label": r["label"], "value": r["value"], "unit": r["unit"], "flag": r["flag"], "date": last["date"]}
               for r in last["results"] if r["flag"] in ("below", "above")]
    thyroid = [r["label"] for r in last["results"] if r["group"] == "thyroid" and r["flag"] in ("below", "above")]
    low_for_age = [{"label": r["label"], "value": r["value"], "unit": r["unit"], "date": d["date"], **r["age_norm"]}
                   for d in out_draws for r in d["results"]
                   if (r.get("age_norm") or {}).get("position") in ("well_below", "below")]
    return {"n_draws": len(out_draws), "draws": out_draws, "latest_date": last["date"], "changes": changes,
            "thresholds": {"fsh_late_transition": FSH_LATE_TRANSITION},
            "outside_range": outside, "thyroid_outside_range": thyroid, "low_for_age": low_for_age}


def _latest(labs: dict, analyte: str) -> dict | None:
    return next((r for r in labs["draws"][-1]["results"] if r["analyte"] == analyte), None)


def align_labs(labs: dict, category: str, findings: dict, age: float | None) -> dict:
    """Count how many independent signals point the same way (all computed here). Not a score and never shown as a label.

    Signals: irregular cycle (natural cycles only), FSH high, oestradiol low, AMH at the low end, symptoms of the kind the
    material links to the transition, age 40+. Sex-hormone values are ignored when hormonal contraception/therapy is used.
    """
    labs = dict(labs)
    masked = category == "masked_by_hormones"
    sig: list[dict] = []

    def add(i: str, text: str):
        sig.append({"id": i, "text": text})

    if category == "irregular_recent" and findings.get("flags"):
        add("cycle_irregular", "the cycle pattern shows the irregularity the material describes for the transition")
    fsh, e2, amh = _latest(labs, "fsh"), _latest(labs, "e2"), _latest(labs, "amh")
    if fsh and not masked and (fsh["flag"] == "above" or fsh["value"] >= FSH_LATE_TRANSITION):
        add("fsh_high", "FSH is above the range printed on the report"
            if fsh["flag"] == "above" else f"FSH is at or above {FSH_LATE_TRANSITION:g}")
    if e2 and not masked and e2["flag"] == "below":
        add("e2_low", "oestradiol is below the range printed on the report")
    amh_pos = (amh or {}).get("age_norm") and amh["age_norm"]["position"]
    if amh and amh_pos in ("well_below", "below"):
        add("amh_low", "AMH is below the 10th percentile for the reader's age")
    elif amh and not amh_pos and (amh["flag"] == "below" or (amh["position_pct"] is not None and amh["position_pct"] <= AMH_LOW_POSITION)):
        add("amh_low", "AMH is at the low end of the range printed on the report")
    sym = (findings.get("symptoms") or {}).get("systems", [])
    if any(s["key"] in ("temperature", "sleep", "cycle") and s["rating"] in ("moderate", "strong") for s in sym):
        add("symptoms", "the reader rates hot flushes or sweating, sleep or cycle symptoms as moderate or strong")
    if age is not None and age >= 40:
        add("age_40_plus", "age is 40 or above")
    n = len(sig)
    young = age is not None and age < 40
    lab_backed = bool(LAB_SIGNALS & {x["id"] for x in sig})
    high = n >= ALIGN_HIGH or (young and n >= ALIGN_HIGH_YOUNG and lab_backed)
    labs["alignment"] = {"signals": sig, "count": n,
                         "level": "high" if high else "moderate" if n >= ALIGN_MODERATE else "low"}
    labs["unreliable"] = sorted(HORMONE_AFFECTED) if masked else []
    return labs
