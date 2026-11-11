"""Streamlit UI: upload (or pick a demo) -> generate -> report, findings, chart -> optional email.

Talks to the FastAPI data service at API_BASE_URL; if none is running it uses the same app in-process.
Run: streamlit run ui/app.py
"""
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx
import streamlit as st

from app.agent import nodes
from app.agent.symptoms import SYSTEMS
from app.agent.graph import build_graph
from ui.charts import cycle_chart

st.set_page_config(page_title="Menohelp", page_icon="🌿", layout="wide")
API = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")
MAX_EMAILS = 3


class _Keep:
    """Context manager around a shared in-process client that must not be closed after each call."""
    def __init__(self, c):
        self.c = c

    def __enter__(self):
        return self.c

    def __exit__(self, *a):
        return False


@st.cache_resource
def client_factory():
    """HTTP client factory: a running API if reachable, else the app in-process (same HTTP calls)."""
    try:
        httpx.get(f"{API}/health", timeout=2).raise_for_status()
        return lambda: httpx.Client(base_url=API, timeout=60)
    except Exception:
        from fastapi.testclient import TestClient
        from app.api.main import app
        tc = TestClient(app)
        tc.__enter__()  # runs the lifespan: preloads demo datasets
        return lambda: _Keep(tc)


def api(method: str, path: str, **kw):
    with client_factory()() as c:
        r = c.request(method, path, **kw)
    r.raise_for_status()
    return r.json()


# --- optional password gate --------------------------------------------------
if os.getenv("APP_PASSWORD") and not st.session_state.get("ok"):
    pw = st.text_input("Password", type="password")
    if pw and pw == os.environ["APP_PASSWORD"]:
        st.session_state["ok"] = True
        st.rerun()
    st.stop()

st.title("🌿 Menohelp")
st.caption("Upload your cycle data and get a plain-language report. Not medical advice.")

RATING = {0: "none", 1: "mild", 2: "moderate", 3: "strong"}
step = st.session_state.get("step", "input")


def run_report(dataset_id, user_id, age, intake):
    nodes.http = client_factory()
    with st.spinner("Analysing your cycles, reading the reference material, writing and checking the report…"):
        try:
            out = build_graph().invoke({"dataset_id": dataset_id, "user_id": user_id, "age": age or None,
                                        "intake": intake})
            cycles = api("GET", "/cycles", params={"dataset_id": dataset_id, "user_id": user_id})["cycles"]
            st.session_state.update(result={"out": out, "cycles": cycles}, step="report")
            return True
        except Exception as e:
            st.session_state.pop("result", None)
            st.error(f"Something went wrong: {str(e)[:300]}")
            return False


# --- step 1: data + inputs ---------------------------------------------------
if step == "input" or not st.session_state.get("result"):
    st.header("Step 1 of 2: your data and symptoms")

    st.subheader("Your data")
    mode = st.radio("Source", ["Demo data", "Upload my file"], horizontal=True)
    dataset_id = None
    if mode == "Demo data":
        dataset_id = st.selectbox("Demo dataset", api("GET", "/demos")["datasets"])
        st.caption("Public demo data only (Kaggle or synthetic).")
    else:
        up = st.file_uploader("CSV or JSON (Clue measurements.json works)", type=["csv", "json"])
        st.caption("Held in memory for about 1 hour, never written to disk or a database.")
        if up is not None:
            key = f"{up.name}-{up.size}"
            if st.session_state.get("upload_key") != key:
                try:
                    with client_factory()() as c:
                        r = c.post("/upload", files={"file": (up.name, up.getvalue())})
                    r.raise_for_status()
                    st.session_state.update(upload_key=key, upload=r.json())
                except Exception as e:
                    st.session_state.pop("upload", None)
                    detail = getattr(getattr(e, "response", None), "text", str(e))
                    st.error(f"Could not read the file: {detail[:300]}")
            if st.session_state.get("upload"):
                dataset_id = st.session_state["upload"]["dataset_id"]
                st.success(f"{st.session_state['upload']['n_rows']} rows read")

    user_id = None
    if dataset_id:
        users = api("GET", "/users", params={"dataset_id": dataset_id})["users"]
        if len(users) > 1:
            user_id = st.selectbox("Person", users)
        elif users:
            user_id = users[0]

    st.subheader("About you (optional)")
    c1, c2, c3 = st.columns(3)
    age = c1.number_input("Age (if not in your file)", min_value=0, max_value=90, value=0,
                          help="0 = not given. Used to tailor the wording.")
    hormones = c2.selectbox("Hormonal contraception or hormone therapy?", ["No", "Yes", "Not sure"],
                            help="The pill or hormonal coil sets your cycle, so cycle length then says little.")
    surgery = c3.selectbox("Hysterectomy, ablation or ovaries removed?", ["No", "Yes", "Not sure"])

    st.subheader("Symptoms (optional)")
    st.caption("Rate how much each area bothers you. Leave at 'none' if it doesn't apply. "
               "Your answers are sent to OpenAI to write the report. Please don't type names or contact details. "
               "Nothing is stored.")
    ratings = {}
    for k, (title, examples) in SYSTEMS.items():
        left, right = st.columns([2, 3])
        left.markdown(f"**{title}**  \n<small>{examples}</small>", unsafe_allow_html=True)
        v = right.select_slider(title, options=list(RATING), value=0, key=f"r_{k}",
                                format_func=RATING.get, label_visibility="collapsed")
        if v:
            ratings[k] = v
    top_concern = st.text_input("What bothers you most? (optional)", max_chars=200,
                                placeholder="e.g. I wake at 3am and can't get back to sleep")
    go = st.button("Generate report", type="primary", disabled=not dataset_id)
    if go:
        intake = {"symptoms": ratings, "top_concern": top_concern, "last_period": None,
                  "hormones": {"Yes": "yes", "No": "no"}.get(hormones),
                  "surgery": {"Yes": "yes", "No": "no"}.get(surgery)}
        if run_report(dataset_id, user_id, age, intake):
            st.rerun()
    st.stop()

# --- step 2: report ----------------------------------------------------------
res = st.session_state["result"]
st.header("Step 2 of 2: your report")
if st.button("← Start over"):
    st.session_state.update(step="input")
    st.session_state.pop("result", None)
    st.rerun()

out, cycles = res["out"], res["cycles"]
if not out.get("passed") or out.get("guard_errors"):
    st.warning("This report did not fully pass our automatic checks: "
               + "; ".join(out.get("check_errors", []) + out.get("guard_errors", [])))

def show_chart():
    st.pyplot(cycle_chart(cycles, out["stats"].get("events", [])))
    st.caption("Green band: 21-35 days, the typical range used by the NHS. Dots mark long, short and skipped cycles.")


def report_with_chart(md: str):
    """Render the report with the cycle chart right after the first section ("What we found")."""
    parts = re.split(r"(?m)^(?=## )", md, maxsplit=2)  # [title, first section, rest]
    if len(parts) < 3:
        st.markdown(md)
        return show_chart()
    st.markdown(parts[0] + parts[1])
    show_chart()
    st.markdown(parts[2])


tab_report, tab_findings = st.tabs(["Your report", "Verified findings"])
with tab_report:
    report_with_chart(out["human_report"])
    st.download_button("Download report (.md)", out["human_report"], file_name="cycle_report.md")
    st.divider()
    st.subheader("Email this report")
    sent = st.session_state.get("emails_sent", 0)
    to = st.text_input("Send to", placeholder="you@example.com")
    if st.button("Send email", disabled=not to or sent >= MAX_EMAILS):
        try:
            from app.email import send_report
            send_report(to, out["human_report"])
            st.session_state["emails_sent"] = sent + 1
            st.success("Sent. The address is not stored.")
        except Exception as e:
            st.error(f"Could not send: {str(e)[:200]}")
    if sent >= MAX_EMAILS:
        st.caption("Email limit reached for this session.")
with tab_findings:
    st.markdown(out["report"])
    with st.expander("Raw computed stats"):
        st.json(out["stats"])
