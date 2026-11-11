"""Lab summary, draw timing and alignment: all computed in code from confirmed values."""
from app.agent import nodes
from app.agent.labs import align_labs, summarise_labs, timing


def draw(date, day, **vals):
    rng = {"fsh": (3.5, 12.5, "mIU/ml"), "e2": (20, 3000, "pg/ml"), "amh": (0.17, 7.37, "ng/ml"),
           "tsh": (0.27, 4.0, "µIU/ml"), "lh": (2.4, 12.6, "mIU/ml")}
    res = []
    for k, v in vals.items():
        lo, hi, u = rng[k]
        res.append({"analyte": k, "value": v, "unit": u, "ref_low": lo, "ref_high": hi,
                    "flag": "below" if v < lo else "above" if v > hi else "within"})
    return {"draw_date": date, "cycle_day": day, "age_at_draw": 44, "age_today": 46, "results": res}


def test_timing_windows():
    assert timing("fsh", 3)[0] == "suitable" and timing("fsh", 7)[0] == "not_suitable"
    assert timing("fsh", None)[0] == "not_stated" and timing("tsh", 7) == ("any_time", None)
    assert timing("progesterone", 21)[0] == "suitable" and timing("progesterone", 3)[0] == "not_suitable"
    assert "cycle day 7" in timing("fsh", 7)[1] and "2 to 5" in timing("fsh", 7)[1]


def test_summary_flags_changes_and_comparability():
    s = summarise_labs([draw("2025-04-03", 7, fsh=10.3, amh=0.39, tsh=0.7), draw("2022-11-10", None, fsh=10.7, tsh=0.8)])
    assert s["n_draws"] == 2 and s["latest_date"] == "2025-04-03"          # sorted by date
    ch = {c["analyte"]: c for c in s["changes"]}
    assert ch["tsh"]["comparable"] and ch["tsh"]["change"] == -0.1
    assert not ch["fsh"]["comparable"]                                      # one draw has no cycle day, one is off-window
    assert "amh" not in ch                                                  # only in one draw
    amh = next(r for r in s["draws"][-1]["results"] if r["analyte"] == "amh")
    assert amh["position_pct"] == 3 and amh["group"] == "ovarian reserve"
    e2 = summarise_labs([draw("2025-04-03", 3, e2=30)])["draws"][0]["results"][0]
    assert e2["position_pct"] is None                                       # not meaningful for the very wide E2 range
    assert summarise_labs(None) is None and summarise_labs([]) is None


def test_thyroid_outside_range_is_listed():
    s = summarise_labs([draw("2025-04-03", 3, tsh=6.0, fsh=8.0)])
    assert s["thyroid_outside_range"] == ["TSH"] and s["outside_range"][0]["flag"] == "above"


def _align(labs, cat="irregular_recent", flags=True, symptoms=None, age=46):
    f = {"flags": [{"rule": "x"}] if flags else [], "symptoms": {"systems": symptoms or []}}
    return align_labs(summarise_labs(labs), cat, f, age)["alignment"]


def test_alignment_counts_signals_and_levels():
    high = _align([draw("2025-04-03", 3, fsh=30.0, e2=15, amh=0.1)], symptoms=[{"key": "temperature", "rating": "strong"}])
    assert {s["id"] for s in high["signals"]} == {"cycle_irregular", "fsh_high", "e2_low", "amh_low", "symptoms", "age_40_plus"}
    assert high["level"] == "high"
    low = _align([draw("2025-04-03", 3, fsh=6.0, e2=100, amh=3.0)], cat="regular", flags=False, age=30)
    assert low["count"] == 0 and low["level"] == "low"


def test_age_is_a_soft_signal_not_a_block():
    young = _align([draw("2025-04-03", 3, fsh=30.0, amh=0.1)], age=30, symptoms=[{"key": "sleep", "rating": "moderate"}])
    assert young["level"] == "high" and "age_40_plus" not in {s["id"] for s in young["signals"]}


def test_hormonal_contraception_ignores_sex_hormone_signals():
    f = {"flags": [], "symptoms": {"systems": []}}
    labs = align_labs(summarise_labs([draw("2025-04-03", 3, fsh=30.0, e2=15, amh=0.1)]), "masked_by_hormones", f, 46)
    ids = {s["id"] for s in labs["alignment"]["signals"]}
    assert "fsh_high" not in ids and "e2_low" not in ids and "amh_low" in ids
    assert "fsh" in labs["unreliable"]


def test_analyse_and_triage_carry_labs_into_findings():
    st = {"age": 46.0, "skipped_cycles": 1, "consecutive_jumps": 3, "mean_change": 9.0, "recent_mean": 39.0, "events": []}
    state = {"stats": st, "dataset_id": "x", "intake": {"symptoms": {"temperature": 3}},
             "labs": [draw("2025-04-03", 3, fsh=30.0)]}
    state["findings"] = nodes.analyse(state)["findings"]
    out = nodes.triage(state)["findings"]
    assert out["labs"]["draws"][0]["results"][0]["analyte"] == "fsh" and out["labs"]["alignment"]["level"] in ("moderate", "high")
    no_labs = nodes.analyse({"stats": st, "dataset_id": "x"})["findings"]
    assert no_labs["labs"] is None
