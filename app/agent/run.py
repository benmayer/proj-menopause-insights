"""CLI: python -m app.agent.run --dataset demo_synthetic_perimenopause --user synth_peri --out samples/report_1.md

By default the data API runs in-process (same HTTP calls, no server needed).
Use --api http://127.0.0.1:8000 to call a running `uvicorn app.api.main:app`.
"""
import argparse
import sys
from pathlib import Path

from app.agent import nodes
from app.agent.graph import build_graph


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", required=True, help="dataset_id, e.g. demo_synthetic_perimenopause")
    ap.add_argument("--user", default=None, help="user_id (optional if the dataset has one user)")
    ap.add_argument("--intake", default=None, help='JSON file: {"symptoms": {"sleep": 3}, "top_concern": "...", '
                    '"hormones": "yes|no", "surgery": "yes|no", "last_period": "lt_3m|3_12m|over_12m"}')
    ap.add_argument("--age", type=float, default=None, help="age if the data has none")
    ap.add_argument("--out", default=None, help="write the report here (markdown)")
    ap.add_argument("--api", default=None, help="base URL of a running API (default: in-process)")
    a = ap.parse_args(argv)

    if a.api:
        import os
        os.environ["API_BASE_URL"] = a.api
    else:
        from fastapi.testclient import TestClient
        from app.api.main import app
        client = TestClient(app)  # runs the lifespan, preloading demo datasets
        client.__enter__()
        nodes.http = lambda: client

    import json
    intake = json.loads(Path(a.intake).read_text()) if a.intake else None
    out = build_graph().invoke({"dataset_id": a.dataset, "user_id": a.user, "age": a.age, "intake": intake})
    findings, human = out["report"], out["human_report"]
    if not out.get("passed"):
        findings = ("> **Verification failed after retries.** Unverified: " + "; ".join(out["check_errors"])
                    + "\n\n" + findings)
        print("FINDINGS CHECK FAILED:", out["check_errors"], file=sys.stderr)
    if out.get("guard_errors"):
        human = ("> **Guardrail failed after retries.** Unresolved: " + "; ".join(out["guard_errors"])
                 + "\n\n" + human)
        print("GUARDRAIL FAILED:", out["guard_errors"], file=sys.stderr)
    print(f"findings retries: {out.get('retries', 0)}  guardrail retries: {out.get('i_retries', 0)}", file=sys.stderr)
    if a.out:
        p = Path(a.out)
        p.write_text(human)
        findings_path = p.with_name(p.stem + "_findings" + p.suffix)
        findings_path.write_text(findings)
        print(f"saved {p} and {findings_path}", file=sys.stderr)
    else:
        print(human)
    return 0 if out.get("passed") and not out.get("guard_errors") else 1


if __name__ == "__main__":
    raise SystemExit(main())
