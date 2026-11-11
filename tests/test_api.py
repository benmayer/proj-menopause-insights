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


def _fake_draw(date="2025-04-03", fsh=10.33):
    return {"draw_date": date, "cycle_day": 7, "age_at_draw": 44, "age_today": 46,
            "results": [{"analyte": "fsh", "value": fsh, "unit": "mIU/ml", "ref_low": 3.5, "ref_high": 12.5, "flag": "within"}]}


def test_labs_upload_append_correct_and_delete(monkeypatch):
    draws = iter([_fake_draw("2025-04-03"), _fake_draw("2022-11-10", 8.0), _fake_draw("2025-04-03", 11.0)])
    monkeypatch.setattr("app.api.main.parse_pdf", lambda content: next(draws))
    with TestClient(app) as c:
        a = c.post("/labs", files={"file": ("a.pdf", b"%PDF")})
        assert a.status_code == 200
        lid = a.json()["labs_id"]
        b = c.post("/labs", params={"labs_id": lid}, files={"file": ("b.pdf", b"%PDF")}).json()
        assert [d["draw_date"] for d in b["draws"]] == ["2022-11-10", "2025-04-03"]  # sorted by date
        again = c.post("/labs", params={"labs_id": lid}, files={"file": ("c.pdf", b"%PDF")}).json()
        assert len(again["draws"]) == 2 and again["draws"][1]["results"][0]["value"] == 11.0  # same date replaced
        # reader corrects a value: server recomputes the flag from the printed range
        fixed = again["draws"]
        fixed[1]["results"][0]["value"] = 15.0
        out = c.put(f"/labs/{lid}", json=fixed).json()
        assert out["draws"][1]["results"][0]["flag"] == "above"
        bad = fixed
        bad[0]["results"][0]["analyte"] = "chlamydia"
        assert c.put(f"/labs/{lid}", json=bad).status_code == 422
        assert c.delete(f"/labs/{lid}").json() == {"deleted": True}
        assert c.get(f"/labs/{lid}").status_code == 404


def test_labs_bad_file_is_a_clear_422():
    with TestClient(app) as c:
        r = c.post("/labs", files={"file": ("x.pdf", b"not a pdf")})
        assert r.status_code == 422 and "PDF" in r.json()["detail"]
