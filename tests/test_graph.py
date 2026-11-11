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
GOOD = ("# Your cycle report\n## What we found\nYour data shows 6 cycles.\n"
        "## What this may mean\nCycles can change in the transition. [S1]\n"
        "## Things that may help\nTracking cycles can help. [S1]\n"
        "## Talking to your doctor\nHormone therapy can be an option to discuss with a GP.\n")


def test_guard_accepts_clean_cited_report():
    st = {"stats": STATS, "findings": {}, "context": CTX}
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
    errs = nodes.guard_report(bad, {"stats": STATS, "findings": {}, "context": CTX})
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
    st = {"stats": STATS, "findings": {"case_tags": ["young"]}, "context": CTX}
    bad = GOOD.replace("in the transition", "in the hormonal transition")
    assert any("under 40" in e for e in nodes.guard_report(bad, st))
    assert not any("under 40" in e for e in nodes.guard_report(GOOD.replace("in the transition", "for many reasons"), st))
