"""UI smoke tests with Streamlit's AppTest (no browser). The LLM graph is replaced by a fake."""
import pytest
from streamlit.testing.v1 import AppTest

from ui.charts import cycle_chart

FAKE = {"report": "# Findings\nok", "human_report": "# Your cycle report\n## What we found\nhello",
        "passed": True, "guard_errors": [], "check_errors": [],
        "stats": {"events": [{"type": "skipped", "date": "2024-06-10", "length_days": 64, "first_time": True}]}}


def test_ui_renders_and_generates(monkeypatch):
    class FakeGraph:
        def invoke(self, state):
            assert state["dataset_id"].startswith("demo_") and state["user_id"]
            return FAKE
    monkeypatch.setattr("app.agent.graph.build_graph", lambda: FakeGraph())
    at = AppTest.from_file("../ui/app.py", default_timeout=30).run()
    assert not at.exception
    at.selectbox[0].select("demo_synthetic_perimenopause")
    at = at.run()
    at.button[0].click()
    at = at.run()
    assert not at.exception, at.exception
    assert any("hello" in m.value for m in at.markdown)


def test_chart_builds():
    fig = cycle_chart([{"cycle_start": "2024-01-01", "cycle_length": 28}, {"cycle_start": "2024-01-29", "cycle_length": 64}],
                      FAKE["stats"]["events"])
    assert fig.axes


def test_ui_passes_symptoms_and_triage_answers_to_the_graph(monkeypatch):
    seen = {}

    class FakeGraph:
        def invoke(self, state):
            seen.update(state)
            return FAKE
    monkeypatch.setattr("app.agent.graph.build_graph", lambda: FakeGraph())
    at = AppTest.from_file("../ui/app.py", default_timeout=30).run()
    at.selectbox[0].select("demo_synthetic_perimenopause")
    at = at.run()
    at.select_slider(key="r_sleep").set_value(2)
    at.select_slider(key="r_temperature").set_value(3)
    at = at.run()
    at.text_input[0].input("I wake at 3am")
    at.button[0].click()
    at = at.run()
    assert not at.exception, at.exception
    assert set(seen["intake"]["symptoms"]) == {"sleep", "temperature"} and seen["intake"]["symptoms"]["temperature"] == 3 and seen["intake"]["top_concern"] == "I wake at 3am"
    assert seen["intake"]["hormones"] == "no" and seen["intake"]["last_period"] is None
    assert any("Step 2 of 2" in h.value for h in at.header)


def test_ui_confirms_lab_values_and_passes_labs_id_to_the_graph(monkeypatch):
    from app.api.store import lab_store
    draw = {"draw_date": "2025-04-03", "cycle_day": 7, "age_at_draw": 30, "age_today": 32,
            "results": [{"analyte": "fsh", "value": 10.33, "unit": "mIU/ml", "ref_low": 3.5, "ref_high": 12.5, "flag": "within"},
                        {"analyte": "tpo", "value": 21.1, "unit": "kIU/l", "ref_low": None, "ref_high": 34.0, "flag": "within"}]}
    lid = lab_store.put([draw])
    seen = {}

    class FakeGraph:
        def invoke(self, state):
            seen.update(state)
            return {**FAKE, "findings": {"labs": {"alignment": {"level": "moderate", "count": 2,
                                                                "signals": [{"id": "x", "text": "AMH is at the low end"}]}}}}
    monkeypatch.setattr("app.agent.graph.build_graph", lambda: FakeGraph())
    at = AppTest.from_file("../ui/app.py", default_timeout=30)
    at.session_state["labs"] = {"labs_id": lid, "draws": [draw]}
    at = at.run()
    assert not at.exception, at.exception
    assert any("Cycle day of the blood draw on 2025-04-03" in n.label for n in at.number_input)
    at.selectbox[0].select("demo_synthetic_perimenopause")
    at = at.run()
    at.number_input(key=f"cd_{lid}_2025-04-03").set_value(3)   # reader supplies the cycle day
    at.button[0].click()
    at = at.run()
    assert not at.exception, at.exception
    assert seen["labs_id"] == lid and seen["age"] == 32                # age filled from the lab report's date of birth
    assert lab_store.get(lid)[0]["cycle_day"] == 3                 # the correction reached the server
    assert any("line up" in e.label for e in at.expander)
