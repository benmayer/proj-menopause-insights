import json
import pytest
from fastapi.testclient import TestClient

from app.agent import nodes
from app.agent.graph import build_graph
from app.agent.nodes import MAX_RETRIES, check_report, route_after_check
from app.api.main import app

STATS = {"n_cycles": 6, "first_cycle": "2024-01-01", "last_cycle": "2024-06-10", "mean_length": 29.0,
         "sd_length": 2.1, "recent_mean": 41.2, "mean_change": 13.2, "skipped_cycles": 1,
         "consecutive_jumps": 3,
         "events": [{"type": "skipped", "date": "2024-06-10", "length_days": 64, "first_time": True}]}


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_fetch_gets_stats_over_http(client, monkeypatch):
    monkeypatch.setattr(nodes, "http", lambda: client)
    out = nodes.fetch({"dataset_id": "demo_synthetic_perimenopause", "user_id": "synth_peri", "retries": 5})
    assert out["retries"] == 0 and out["stats"]["n_cycles"] == 26
    assert out["stats"]["events"] and out["stats"]["events"][0]["date"]


def test_analyse_case_tags():
    f = nodes.analyse({"stats": {**STATS, "sd_change": 5.0, "age": 33}, "dataset_id": "u"})["findings"]
    assert {"variability_up", "lengthening", "skipped", "young"} <= set(f["case_tags"])
    calm = nodes.analyse({"stats": {"skipped_cycles": 0, "consecutive_jumps": 0}, "dataset_id": "u"})["findings"]
    assert calm["case_tags"] == ["stable"]


def test_analyse_flag_rules():
    f = nodes.analyse({"stats": STATS, "dataset_id": "demo_x"})["findings"]
    assert {x["rule"] for x in f["flags"]} == {"skipped_cycles", "consecutive_jumps", "mean_change",
                                               "recent_mean"} and f["is_demo"]
    calm = nodes.analyse({"stats": {"skipped_cycles": 0, "consecutive_jumps": 1, "mean_change": 2.0,
                                    "recent_mean": 29.0}, "dataset_id": "u"})["findings"]
    assert calm["no_flags"] and not calm["is_demo"]


# --- Check: the guardrail ------------------------------------------------------
def test_check_accepts_report_using_only_known_values():
    st = {"stats": STATS, "findings": {}, "context": []}
    ok = "## Summary\n6 cycles from 2024-01-01 to 2024-06-10, mean 29.0 days, sd 2.1.\n- 2024-06-10: 64 days, skipped."
    assert check_report(ok, st) == []


def test_check_catches_wrong_number_and_unknown_date():
    st = {"stats": STATS, "findings": {}, "context": []}
    errs = check_report("Mean 31.0 days. Started 2024-02-02. See March 2024.", st)
    assert any("31.0" in e for e in errs) and any("2024-02-02" in e for e in errs)
    assert any("March 2024" in e for e in errs)


def test_check_allows_reference_thresholds_and_month_year_of_known_date():
    st = {"stats": STATS, "findings": {}, "context": [{"content": "shorter than 21 or longer than 35 days"}]}
    assert check_report("Cycles over 35 days or under 21. The gap began in June 2024.", st) == []


def test_check_node_counts_retries():
    st = {"stats": STATS, "findings": {}, "context": [], "report": "Mean 99 days", "retries": 1}
    out = nodes.check(st)
    assert out["passed"] is False and out["retries"] == 2 and out["check_errors"]


def test_check_flags_raw_field_names():
    st = {"stats": STATS, "findings": {}, "context": []}
    assert any("sd_length" in e for e in check_report("The sd_length is 2.1.", st))


def test_router():
    assert route_after_check({"passed": True}) == "interpret"
    assert route_after_check({"passed": False, "retries": 1}) == "write"
    assert route_after_check({"passed": False, "retries": MAX_RETRIES}) == "write"
    assert route_after_check({"passed": False, "retries": MAX_RETRIES + 1}) == "interpret"


def test_guard_router():
    assert nodes.route_after_guard({"guard_errors": []}) == "end"
    assert nodes.route_after_guard({"guard_errors": ["x"], "i_retries": 1}) == "interpret"
    assert nodes.route_after_guard({"guard_errors": ["x"], "i_retries": MAX_RETRIES + 1}) == "end"


# --- Guardrail on the human report --------------------------------------------
CTX = [{"section": "knowledge", "title": "Modul 3, S. 19 (#29)", "content": "x"},
       {"section": "reference", "title": "r", "content": "shorter than 21 days"}]
GOOD = ("# Your cycle report\n## Summary\nYour data shows 6 cycles.\n"
        "## Your cycle\nYour cycles vary more than typical cycles do. [S1]\n"
        "## What it could mean together\nCycles can change in the transition. [S1]\n"
        "## Things that may help\nTracking cycles can help. [S1]\n"
        "## Talking to your doctor\nHormone therapy can be an option to discuss with a GP.\n")


def test_guard_accepts_clean_cited_report():
    st = {"stats": STATS, "findings": {"flags": [{"rule": "x"}]}, "context": CTX}
    assert nodes.guard_report(GOOD, st) == []


@pytest.mark.parametrize("bad,expect", [
    (GOOD.replace("[S1]", "[S9]", 1), "does not exist"),
    (GOOD.replace("Tracking cycles can help. [S1]", "Tracking cycles can help."), "uncited"),
    (GOOD.replace("Hormone therapy can be", "You have perimenopause. Hormone therapy can be"), "diagnostic"),
    (GOOD.replace("Tracking cycles", "Take 50 mg daily. Tracking cycles"), "dose"),
    (GOOD.replace("## Talking to your doctor", "## Other"), "missing section"),
    (GOOD.replace("6 cycles", "7 cycles"), "number 7"),
])
def test_guard_catches(bad, expect):
    errs = nodes.guard_report(bad, {"stats": STATS, "findings": {"flags": [{"rule": "x"}]}, "context": CTX})
    assert any(expect in e for e in errs), errs


# --- Whole graph with the LLM and RAG stubbed ---------------------------------
def test_graph_end_to_end_and_retry_loop(client, monkeypatch):
    monkeypatch.setattr(nodes, "http", lambda: client)
    monkeypatch.setattr(nodes, "retrieve", lambda s: {"context": []})
    drafts = iter(["Mean 99 days.", "Mean 31.8 days."])  # first draft invents a number
    seen = []

    def fake_write(s):
        seen.append(list(s.get("check_errors", [])))
        return {"report": next(drafts)}

    monkeypatch.setattr(nodes, "write", fake_write)
    monkeypatch.setattr(nodes, "interpret", lambda s: {"human_report": "## What we found\nok"})
    monkeypatch.setattr(nodes, "guardrail", lambda s: {"guard_errors": []})
    out = build_graph().invoke({"dataset_id": "demo_synthetic_perimenopause", "user_id": "synth_peri"})
    assert len(seen) == 2 and seen[0] == [] and seen[1]  # second write was told what was wrong
    assert out["retries"] == 1 and out["passed"] is True  # 31.8 is the real mean of synth_peri


def test_graph_gives_up_after_max_retries(client, monkeypatch):
    monkeypatch.setattr(nodes, "http", lambda: client)
    monkeypatch.setattr(nodes, "retrieve", lambda s: {"context": []})
    calls = {"n": 0}

    def bad_write(s):
        calls["n"] += 1
        return {"report": "Mean 12345 days."}

    monkeypatch.setattr(nodes, "write", bad_write)
    monkeypatch.setattr(nodes, "interpret", lambda s: {"human_report": "x"})
    monkeypatch.setattr(nodes, "guardrail", lambda s: {"guard_errors": []})
    out = build_graph().invoke({"dataset_id": "demo_synthetic_perimenopause", "user_id": "synth_peri"})
    assert calls["n"] == 1 + MAX_RETRIES and out["passed"] is False


def test_guard_blocks_menopause_framing_for_young_reader():
    st = {"stats": STATS, "findings": {"case_tags": ["young"], "flags": [{"rule": "x"}]}, "context": CTX}
    bad = GOOD.replace("in the transition", "in the hormonal transition")
    assert any("under 40" in e for e in nodes.guard_report(bad, st))
    assert not any("under 40" in e for e in nodes.guard_report(GOOD.replace("in the transition", "for many reasons"), st))


# --- Symptom intake, triage, red flags -----------------------------------------
def _state(intake=None, **stats):
    st = {"stats": {**STATS, **stats}, "dataset_id": "u", "intake": intake}
    st["findings"] = nodes.analyse(st)["findings"]
    return st


def test_symptom_summary_computed_in_code():
    s = nodes.summarise_symptoms({"symptoms": {"temperature": 3, "sleep": 2, "eyes": 0, "hot_flushes": 1},
                                  "top_concern": "  poor sleep  "})
    assert [x["key"] for x in s["systems"]] == ["temperature", "sleep"]      # strongest first, max per system
    assert s["systems"][0]["rating"] == "strong" and s["top_concern"] == "poor sleep" and s["n_systems"] == 2
    assert nodes.summarise_symptoms({"symptoms": {}}) is None and nodes.summarise_symptoms(None) is None


@pytest.mark.parametrize("intake,extra,cat", [
    ({"hormones": "yes"}, {}, "masked_by_hormones"),
    ({"surgery": "yes"}, {}, "surgical_or_other"),
    ({"last_period": "over_12m"}, {}, "no_period_12m"),
    (None, {"age": 30}, "irregular_recent"),                                   # age is a soft signal: irregular cycles still count
    (None, {"age": 30, "skipped_cycles": 0, "consecutive_jumps": 0, "mean_change": 1.0, "recent_mean": 29.0}, "young"),
    (None, {}, "irregular_recent"),                                            # STATS carries skipped cycle + jumps
    (None, {"skipped_cycles": 0, "consecutive_jumps": 0, "mean_change": 1.0, "recent_mean": 29.0}, "regular"),
])
def test_triage_categories(intake, extra, cat):
    st = _state(intake, **extra)
    out = nodes.triage(st)["findings"]
    assert out["category"] == cat
    if cat in nodes.CYCLE_UNRELIABLE:
        assert out["flags"] == [] and out["no_flags"]            # cycle-pattern claims suppressed


def test_triage_red_flags_for_strong_ratings():
    st = _state({"symptoms": {"heart": 3, "mind": 3, "sleep": 3, "temperature": 2}})
    assert set(nodes.triage(st)["findings"]["red_flags"]) == {"heart", "mind"}


def test_findings_sections_follow_triage():
    f = nodes.triage(_state({"hormones": "yes", "symptoms": {"sleep": 2}}))["findings"]
    heads = nodes._sections({"findings": f})
    assert "About your cycle data" in heads and "Your reported symptoms" in heads and "Variability" not in heads


def test_interpret_adds_fixed_red_flag_text_and_symptom_section(monkeypatch):
    st = _state({"symptoms": {"heart": 3}})
    st["findings"] = nodes.triage(st)["findings"]
    st["context"], st["report"] = [], "# Findings\n---\n"
    monkeypatch.setattr(nodes, "_llm", lambda m: "# Your cycle report\n## Summary\nok")
    out = nodes.interpret(st)["human_report"]
    assert "Worth acting on soon" in out and nodes.RED_FLAG_TEXT["heart"] in out
    assert "How to read this report" in out and out.rstrip().endswith(f"*{nodes.DISCLAIMER}*")
    heads = nodes.interpret_headings(st)
    assert heads[:2] == [nodes.SUMMARY_H, nodes.CYCLE_H] and heads[2] == nodes.SYMPTOM_HEADING


SYM_CTX = [{"section": "symptom_map", "title": "Sleep regulation", "content": "x"},
           {"section": "reference", "title": "r", "content": "shorter than 21 days"}]
SYM_GOOD = GOOD.replace("## What it could mean together", "## Your symptoms\n"
                        "You report sleep symptoms, rated moderate.\n"
                        "## What it could mean together")


def _sym_state(flags=True):
    return {"stats": STATS, "findings": {"flags": [{"rule": "x"}] if flags else [],
                                         "symptoms": {"systems": [{"key": "sleep"}]}}, "context": SYM_CTX}


def test_guard_symptom_section_required():
    st = _sym_state()
    assert nodes.guard_report(SYM_GOOD, st) == []
    assert any("missing section" in e for e in nodes.guard_report(GOOD, st))


@pytest.mark.parametrize("phrase", ["The table lists progesterone deficiency as a factor.", "The material says sleep matters.",
                                    "According to the source, cycles vary.", "The coaching material suggests rest."])
def test_guard_blocks_talk_about_the_material(phrase):
    bad = SYM_GOOD.replace("You report sleep symptoms", phrase + " You report sleep symptoms")
    assert any("speak as the coach" in e for e in nodes.guard_report(bad, _sym_state()))


def test_guard_needs_a_tag_in_the_cycle_section():
    bad = GOOD.replace("typical cycles do. [S1]", "typical cycles do.")
    assert any("cites no source" in e for e in nodes.guard_report(bad, _sym_state()))


def test_guard_blocks_claims_about_own_hormone_levels():
    st = _sym_state()
    bad = SYM_GOOD.replace("You report sleep symptoms", "Your progesterone is low. You report sleep symptoms")
    assert any("hormone levels" in e for e in nodes.guard_report(bad, st))


def test_guard_hormone_therapy_only_when_relevant():
    st = _sym_state(flags=False)  # sleep symptom only, no flags
    assert any("hormone therapy" in e for e in nodes.guard_report(SYM_GOOD, st))      # GOOD offers HT as an option
    assert not any("hormone therapy" in e for e in nodes.guard_report(SYM_GOOD, _sym_state(flags=True)))
    plain = SYM_GOOD.replace("Hormone therapy can be an option to discuss with a GP.", "You use hormone therapy.")
    assert not any("hormone therapy" in e for e in nodes.guard_report(plain, st))


def test_fetch_includes_labs_and_takes_age_from_them(client, monkeypatch):
    from app.api.store import lab_store
    lid = lab_store.put([{"draw_date": "2025-04-03", "cycle_day": 7, "age_at_draw": 30, "age_today": 32,
                          "results": [{"analyte": "fsh", "value": 10.3, "unit": "mIU/ml", "ref_low": 3.5,
                                       "ref_high": 12.5, "flag": "within"}]}])
    monkeypatch.setattr(nodes, "http", lambda: client)
    base = {"dataset_id": "demo_synthetic_perimenopause", "user_id": "synth_peri", "labs_id": lid}
    out = nodes.fetch(base)
    assert out["labs"][0]["results"][0]["analyte"] == "fsh"
    # a file without an age column (Clue-like) takes the age from the lab report's date of birth
    days = ["2024-01-01", "2024-01-29", "2024-02-26", "2024-03-25", "2024-04-22", "2024-05-20"]
    raw = json.dumps([{"type": "period", "id": str(i), "date": d, "value": {"option": "light"}} for i, d in enumerate(days)])
    did = client.post("/upload", files={"file": ("m.json", raw, "application/json")}).json()["dataset_id"]
    assert nodes.fetch({"dataset_id": did, "labs_id": lid})["stats"]["age"] == 32.0
    assert nodes.fetch({"dataset_id": did, "labs_id": lid, "age": 41})["stats"]["age"] == 41.0  # UI age wins
    gone = nodes.fetch({**base, "labs_id": "expired"})
    assert gone["labs"] == []  # expired id: no labs, no crash
    assert nodes.fetch({"dataset_id": "demo_synthetic_perimenopause", "user_id": "synth_peri"})["labs"] == []
