from app.agent import nodes
from app.agent.graph import build_graph
from app.agent.nodes import MAX_RETRIES, route_after_check


# --- each node alone ---------------------------------------------------------
def test_each_node_returns_its_keys():
    assert "stats" in nodes.fetch({"dataset_id": "x"})
    assert "findings" in nodes.analyse({"stats": {}})
    assert "context" in nodes.retrieve({"findings": {}})
    assert "report" in nodes.write({"stats": {}})
    assert nodes.check({"report": ""})["passed"] is True


def test_router():
    assert route_after_check({"passed": True}) == "end"
    assert route_after_check({"passed": False, "retries": 1}) == "write"
    assert route_after_check({"passed": False, "retries": MAX_RETRIES}) == "write"
    assert route_after_check({"passed": False, "retries": MAX_RETRIES + 1}) == "end"


# --- whole graph -------------------------------------------------------------
def test_graph_runs_end_to_end():
    out = build_graph().invoke({"dataset_id": "demo_synthetic_perimenopause", "user_id": "synth_peri"})
    assert out["report"].startswith("# STUB REPORT") and out["passed"] is True


def test_check_failure_loops_back_to_write_then_gives_up(monkeypatch):
    calls = {"write": 0}
    real_write = nodes.write

    def counting_write(state):
        calls["write"] += 1
        return real_write(state)

    monkeypatch.setattr(nodes, "write", counting_write)
    monkeypatch.setattr(nodes, "check", lambda s: {"passed": False, "check_errors": ["mismatch"],
                                                   "retries": s.get("retries", 0) + 1})
    out = build_graph().invoke({"dataset_id": "x"})
    assert calls["write"] == 1 + MAX_RETRIES  # first attempt + 2 retries
    assert out["passed"] is False and out["check_errors"] == ["mismatch"]
