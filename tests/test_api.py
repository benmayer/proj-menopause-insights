import json

from fastapi.testclient import TestClient

from app.api.main import app


def test_health_and_demo_stats():
    with TestClient(app) as c:  # context manager runs lifespan (loads demos)
        assert c.get("/health").json() == {"status": "ok"}
        assert "demo_synthetic_perimenopause" in c.get("/demos").json()["datasets"]
        r = c.get("/stats", params={"dataset_id": "demo_synthetic_perimenopause", "user_id": "synth_peri"})
        assert r.status_code == 200 and r.json()["skipped_cycles"] == 1


def test_upload_clue_like_json_then_stats():
    days = [("2024-01-01", "light"), ("2024-01-02", "heavy"), ("2024-01-29", "medium"), ("2024-02-26", "light"),
            ("2024-03-25", "light"), ("2024-04-22", "light"), ("2024-05-20", "light")]
    raw = json.dumps([{"type": "period", "id": str(i), "date": d, "value": {"option": f}}
                      for i, (d, f) in enumerate(days)])
    with TestClient(app) as c:
        up = c.post("/upload", files={"file": ("measurements.json", raw, "application/json")})
        assert up.status_code == 200 and up.json()["n_rows"] == 6
        did = up.json()["dataset_id"]
        s = c.get("/stats", params={"dataset_id": did}).json()  # single user: no user_id needed
        assert s["n_cycles"] == 5 and s["mean_length"] == 28.0
        assert len(c.get("/cycles", params={"dataset_id": did}).json()["cycles"]) == 6


def test_errors_are_clear():
    with TestClient(app) as c:
        assert c.get("/stats", params={"dataset_id": "nope"}).status_code == 404
        bad = c.post("/upload", files={"file": ("x.csv", "a,b\n1,2\n", "text/csv")})
        assert bad.status_code == 422 and "start date" in bad.json()["detail"]
        assert c.get("/stats", params={"dataset_id": "demo_synthetic_perimenopause"}).status_code == 422
