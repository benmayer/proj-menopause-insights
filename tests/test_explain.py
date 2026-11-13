"""Age norms, cross-source explanations, cycle comparison and the fixed notes: all computed in code."""
from app.agent import nodes
from app.agent.age_norms import age_norm
from app.agent.explain import explain
from app.agent.labs import align_labs, summarise_labs
from tests.test_lab_summary import draw


def test_amh_age_norm_places_value_by_age():
    young = age_norm("amh", 0.42, "ng/ml", 32)
    assert young["position"] == "below" and young["median"] > 3 and young["typical_for_age"] >= 44
    assert age_norm("amh", 0.42, "ng/ml", 46)["position"] == "typical"          # same value, normal at 46
    assert age_norm("amh", 3.0, "ng/ml", 32)["position"] == "typical"
    assert age_norm("amh", 0.42, "ng/ml", None) is None and age_norm("fsh", 5, "mIU/ml", 32) is None
    assert age_norm("amh", 0.42, "mg/l", 32) is None                             # unknown unit: no comparison


def young_labs(**vals):
    d = draw("2025-06-17", 8, **vals)
    d["age_at_draw"] = 31
    return [d]


def test_amh_low_for_age_counts_even_inside_printed_range_and_young_can_reach_high():
    labs = summarise_labs(young_labs(amh=0.42, fsh=9.8, tsh=0.85))
    amh = labs["draws"][0]["results"][0]
    assert amh["flag"] == "within" and amh["age_norm"]["position"] in ("below", "well_below")
    assert labs["low_for_age"][0]["label"] == "AMH"
    f = {"flags": [{"rule": "x"}], "symptoms": {"systems": [{"key": "cycle", "rating": "strong"}]}}
    al = align_labs(labs, "irregular_recent", f, 32)["alignment"]
    assert {s["id"] for s in al["signals"]} == {"cycle_irregular", "amh_low", "symptoms"} and al["level"] == "high"
    no_lab = align_labs(summarise_labs(young_labs(amh=3.0)), "irregular_recent", f, 32)["alignment"]
    assert no_lab["level"] == "moderate"                                          # 2 signals, none from the blood test


def _findings(systems, flags=True):
    return {"flags": [{"rule": "x"}] if flags else [], "symptoms": {"systems": systems}}


def test_explanations_support_contradict_and_leave_untested():
    labs = summarise_labs(young_labs(amh=0.42, tsh=0.85, hb=11.0))
    sym = [{"key": "cycle", "rating": "strong"}, {"key": "mind", "rating": "strong"}, {"key": "skin", "rating": "moderate"}]
    ex = {x["key"]: x for x in explain(_findings(sym), labs, "irregular_recent")}
    assert ex["ovarian"]["status"] == "supported" and ex["iron"]["status"] == "supported"
    assert ex["thyroid"]["status"] == "contradicted" and not ex["thyroid"]["mention"]   # normal TSH: leave it out
    assert ex["androgens"]["status"] == "untested" and ex["androgens"]["mention"]      # worth testing
    assert list(ex)[0] in ("ovarian", "iron")                                           # supported first


def test_ruled_out_lead_is_mentioned_only_when_nothing_else_is_supported():
    labs = summarise_labs(young_labs(tsh=1.0, amh=3.0, hb=13.0))
    sym = [{"key": k, "rating": "strong"} for k in ("mind", "sleep", "metabolism", "hair_nails")]
    ex = {x["key"]: x for x in explain(_findings(sym), labs, "irregular_recent")}
    assert ex["thyroid"]["status"] == "contradicted" and ex["thyroid"]["mention"]
    st = {"findings": {"explanations": list(ex.values())}}
    assert all(x["status"] != "contradicted" or x["label"] == ex["thyroid"]["label"] for x in nodes._explanations_view(st["findings"]))


def test_lh_below_fsh_does_not_rule_out_low_progesterone():
    labs = summarise_labs(young_labs(lh=2.2, fsh=9.8))
    ex = {x["key"]: x for x in explain(_findings([{"key": "breast", "rating": "strong"}]), labs, "irregular_recent")}
    assert ex["progesterone"]["status"] == "untested"


def test_hormonal_contraception_masks_sex_hormone_evidence():
    labs = summarise_labs(young_labs(fsh=30.0, e2=15))
    ex = {x["key"]: x for x in explain(_findings([{"key": "cycle", "rating": "strong"}], flags=False), labs, "masked_by_hormones")}
    assert ex["ovarian"]["status"] == "untested"


def test_cycle_comparison_against_typical_cycles():
    c = nodes.compare_cycles({"n_cycles": 26, "mean_length": 31.8, "recent_mean": 39.2, "sd_length": 6.8,
                              "recent_sd": 10.6, "consecutive_jumps": 5, "short_cycles": 1, "long_cycles": 4})
    assert c["mean_length_in_typical_range"] and not c["recent_mean_in_typical_range"]
    assert c["consecutive_pairs"] == 25 and c["jump_pct_of_pairs"] == 20 and c["cycles_outside_typical_range"] == 5
    assert c["sd_length_vs_typical"] == "more than typical" and c["recent_sd_vs_typical"] == "much more than typical"
    assert nodes.compare_cycles({"n_cycles": 1}) is None


def test_notes_block_states_timing_once_per_draw():
    f = {"labs": summarise_labs(young_labs(fsh=9.8, lh=2.2, amh=0.42))}
    notes = nodes.notes_block(f)
    timing = [n for n in notes if "cycle day 8" in n]
    assert len(timing) == 1 and "FSH and LH on cycle day 2 to 5" in timing[0]
    assert any("Ji et al. 2022" in n for n in notes) and "not a diagnosis" in notes[-1]
    assert nodes.notes_block({}) == [notes[-1]]


def test_guard_low_for_age_needs_the_age_norm():
    from tests.test_lab_pipeline import GOODLAB, _g, state
    older = state([draw("2025-06-17", 3, amh=0.5)], None, age=46.0)      # typical for age 44 (age at draw)
    bad = GOODLAB.replace("Your data shows", "Your AMH is very low for your age. Your data shows")
    assert any("age norm" in e for e in _g(bad, older))
    assert any("age norm" in e for e in _g(bad.replace("for your age", "for age 44"), older))
    assert any("age norm" in e for e in _g(bad.replace("Your AMH is very low for your age", "The very low AMH for age"), older))
    young = state(young_labs(amh=0.42), None, age=32.0)
    assert not any("age norm" in e for e in _g(bad, young))


def test_cycle_pattern_alone_supports_the_transition_from_40():
    f = _findings([], flags=True)
    old = {x["key"]: x for x in explain(f, None, "irregular_recent", 47)}
    young = {x["key"]: x for x in explain(f, None, "irregular_recent", 32)}
    assert old["ovarian"]["status"] == "supported" and young["ovarian"]["status"] == "untested"


def test_pill_drops_cycle_comparison():
    st = {"stats": {"n_cycles": 10, "mean_length": 28.0, "skipped_cycles": 0, "consecutive_jumps": 0}, "dataset_id": "u",
          "intake": {"hormones": "yes"}}
    st["findings"] = nodes.analyse(st)["findings"]
    assert st["findings"]["cycle_compare"] and nodes.triage(st)["findings"]["cycle_compare"] is None


def test_guard_blocks_cycle_claims_when_cycle_is_masked():
    from tests.test_graph import GOOD, CTX, STATS
    f = {"flags": [{"rule": "x"}], "category": "masked_by_hormones"}
    st = {"stats": STATS, "findings": f, "context": CTX}
    bad = GOOD.replace("Your data shows 6 cycles.", "Your cycles sit in the typical 21 to 35 days.")
    assert any("not a natural signal" in e for e in nodes.guard_report(bad, st))
    assert not any("not a natural signal" in e for e in nodes.guard_report(bad, {**st, "findings": {"flags": [{"rule": "x"}]}}))


def test_reader_report_strips_tags_and_groups_sections():
    md = ("# Your cycle report\n## Summary\nAll fine.\n## Your cycle\nLonger cycles. [S1][S2]\n"
          "## Your blood results\nAMH is low [S3].\n## What it could mean\nIt fits. [S1]\n"
          "## Talking to your doctor\n- Bring it.\n## Things that may help\n- Sleep. [S4]\n")
    out = nodes.reader_report(md)
    assert "[S" not in out and "low." in out and "Longer cycles.\n" in out
    assert out.index("## What we found") < out.index("### Your cycle") < out.index("### Your blood results")
    assert out.index("## Conclusion") < out.index("### What it could mean") < out.index("### Talking to your doctor")
    assert "## Summary" in out and "### Summary" not in out


def test_labs_brief_headlines_only_for_values_that_mean_something():
    labs = summarise_labs(young_labs(fsh=9.8, lh=2.2, amh=0.42), age=31)
    brief = nodes._labs_brief(labs, [])
    assert [x["name"] for x in brief["stand_out"]] == ["AMH (anti-Müllerian hormone)"]
    assert any(x["label"] == "LH" for x in brief["also_outside"]) or all(x["label"] != "LH" for x in brief["stand_out"])
