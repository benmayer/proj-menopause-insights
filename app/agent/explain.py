"""Cross-source reasoning in code: which possible explanations does the data support, contradict, or leave untested?

Each candidate is a factor the coaching material links to cycle changes and symptoms (symptom table, Modul 3 lab
table). For each one we look at:
  - relevance: what in the reader's cycle pattern and symptoms makes it worth considering
  - evidence:  what the blood results say (supports / contradicts), using printed ranges and age norms
Status: 'supported' (a lab value points to it), 'contradicted' (measured, all normal), 'untested' (not measured).
The report talks about supported ones, suggests testing for relevant untested ones, and leaves contradicted ones
out unless the contradiction itself is notable (strong relevance, but the values are clearly normal).
Nothing here is a diagnosis; it decides what the report should focus on.
"""
from app.agent.labs import HORMONE_AFFECTED

# key: label, analytes that test it, how each analyte supports it, systems/cycle signals that make it relevant
CANDIDATES = {
    "ovarian": {
        "label": "changes in ovarian hormone production (lower egg reserve, or the start of the hormonal transition)",
        "tests": {"amh": "low_for_age_or_below", "fsh": "above_or_late", "e2": "below"},
        "systems": {"cycle", "temperature", "sleep", "mind", "skin", "sexuality"}, "cycle": True,
    },
    "thyroid": {
        "label": "a thyroid problem",
        "tests": {"tsh": "outside", "ft3": "outside", "ft4": "outside", "tpo": "above"},
        "systems": {"mind", "sleep", "skin", "hair_nails", "metabolism", "temperature", "heart", "cycle"}, "cycle": True,
    },
    "iron": {
        "label": "low iron or anaemia (often linked to heavy periods)",
        "tests": {"hb": "below", "ferritin": "below"},
        "systems": {"cycle", "hair_nails", "mind", "heart"}, "cycle": False,
    },
    "prolactin": {
        "label": "raised prolactin",
        "tests": {"prolactin": "above"},
        "systems": {"cycle", "breast", "sexuality"}, "cycle": True,
    },
    "androgens": {
        "label": "higher male-type hormones, as seen with PCOS",
        "tests": {"testosterone": "above", "fai": "above", "dheas": "above", "androstenedione": "above"},
        "systems": {"skin", "hair_nails", "metabolism", "cycle"}, "cycle": True,
    },
    "progesterone": {
        "label": "too little progesterone in the second half of the cycle",
        "tests": {"progesterone": "below_luteal", "lh": "lh_over_fsh"},
        "systems": {"breast", "cycle", "sleep", "mind"}, "cycle": False,
    },
}
FSH_LATE = 25.0
NOTABLE_WEIGHT = 6  # strong lead from cycle + symptoms (our heuristic)
UNTESTED_WEIGHT, MAX_UNTESTED = 3, 2  # suggest testing only for clear leads, and at most two


def _supports(rule: str, r: dict, results: dict) -> bool | None:
    """True = supports, False = measured and normal, None = can't be read (e.g. wrong cycle day)."""
    flag = r.get("flag")
    if rule == "low_for_age_or_below":
        pos = (r.get("age_norm") or {}).get("position")
        return flag == "below" or pos in ("well_below", "below")
    if rule == "above_or_late":
        return flag == "above" or r["value"] >= FSH_LATE
    if rule == "outside":
        return flag in ("below", "above")
    if rule in ("above", "below"):
        return flag == rule
    if rule == "below_luteal":
        return (flag == "below") if r.get("timing") == "suitable" else None
    if rule == "lh_over_fsh":
        fsh = results.get("fsh")
        # LH above FSH speaks for a corpus-luteum insufficiency (lab_map); the normal ratio does not rule it out
        return True if fsh and fsh["unit"] == r["unit"] and r["value"] > fsh["value"] else None
    return None


def _evidence_text(a: str, r: dict, rule: str, ok: bool) -> str:
    n = r.get("age_norm") or {}
    if a == "amh" and n.get("position") in ("well_below", "below"):
        return f"{r['label']} {r['value']} {r['unit']} is below the 10th percentile for age {n['age']}"
    if rule == "lh_over_fsh":
        return f"LH is {'higher' if ok else 'lower'} than FSH"
    where = {"below": "below", "above": "above"}.get(r.get("flag"), "within")
    if n.get("position") == "typical" and where == "below":  # below the lab's all-ages range, but normal for the age
        return f"{r['label']} {r['value']} {r['unit']} is below the lab's range, which is usual at age {n['age']}"
    return f"{r['label']} {r['value']} {r['unit']} is {where} the lab's range"


def explain(findings: dict, labs: dict | None, category: str, age: float | None = None) -> list[dict]:
    """Candidate explanations with relevance, evidence and status. Ordered: supported first, then by relevance."""
    sym = {s["key"]: s["rating"] for s in (findings.get("symptoms") or {}).get("systems", [])}
    cycle_irregular = bool(findings.get("flags")) and category == "irregular_recent"
    masked = category == "masked_by_hormones"
    draws = (labs or {}).get("draws") or []
    out = []
    for key, c in CANDIDATES.items():
        why = [f"{s} symptoms ({sym[s]})" for s in c["systems"] if s in sym]
        if c["cycle"] and cycle_irregular:
            why.insert(0, "irregular cycle pattern")
        weight = sum({"strong": 2, "moderate": 1, "mild": 0.5}.get(sym.get(s), 0) for s in c["systems"]) \
            + (2 if c["cycle"] and cycle_irregular else 0)
        sup, con, seen = [], [], set()
        for d in reversed(draws):  # newest draw first; one reading per analyte
            results = {r["analyte"]: r for r in d["results"]}
            for a, rule in c["tests"].items():
                r = results.get(a)
                if not r or a in seen or (masked and a in HORMONE_AFFECTED):
                    continue
                ok = _supports(rule, r, results)
                if ok is None:
                    continue
                seen.add(a)
                (sup if ok else con).append({"analyte": a, "date": d["date"], "text": _evidence_text(a, r, rule, ok)})
        if key == "ovarian" and cycle_irregular and age is not None and age >= 40:
            # STRAW+10: the early transition is defined by the cycle pattern itself (rag_docs/reference_ranges.md)
            sup.append({"analyte": "cycle", "date": None,
                        "text": "irregular cycles at age 40 or over match the cycle marker of the early transition"})
        status = "supported" if sup else "contradicted" if con else "untested"
        if status == "untested" and not why:
            continue
        if status == "contradicted" and not why:
            continue  # nothing pointed here and the values are normal: nothing to say
        label = c["label"]
        if key == "ovarian" and age is not None:  # the age decides which reading fits
            label = ("the hormonal transition (falling ovarian hormone production)" if age >= 40 else
                     "a lower egg reserve than usual for this age, which at this age would mean an early change")
        out.append({"key": key, "label": label, "status": status, "relevance": why, "weight": weight,
                    "supporting": sup, "contradicting": con,
                    "mention": status == "supported" or (status == "untested" and weight >= UNTESTED_WEIGHT)})
    # at most a few untested ideas, strongest first, so the conclusion stays focused
    for x in sorted((x for x in out if x["status"] == "untested" and x["mention"]), key=lambda x: -x["weight"])[MAX_UNTESTED:]:
        x["mention"] = False
    # a ruled-out explanation is worth one line only when it was the strongest lead and nothing else is supported
    if not any(x["status"] == "supported" for x in out):
        for x in out:
            if x["status"] == "contradicted" and x["weight"] >= NOTABLE_WEIGHT and x["weight"] == max(y["weight"] for y in out):
                x["mention"] = True
    order = {"supported": 0, "untested": 1, "contradicted": 2}
    return sorted(out, key=lambda x: (order[x["status"]], -x["weight"]))
