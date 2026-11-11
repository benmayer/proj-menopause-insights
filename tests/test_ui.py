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
    at.selectbox[1].select("synth_peri") if len(at.selectbox) > 1 else None
    at.button[0].click()
    at = at.run()
    assert not at.exception, at.exception
    assert any("hello" in m.value for m in at.markdown)


def test_chart_builds():
    fig = cycle_chart([{"cycle_start": "2024-01-01", "cycle_length": 28}, {"cycle_start": "2024-01-29", "cycle_length": 64}],
                      FAKE["stats"]["events"])
    assert fig.axes
