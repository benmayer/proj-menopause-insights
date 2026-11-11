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
