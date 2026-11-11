"""Graph nodes. A node takes the state and returns only the keys it changes.

Fetch/Analyse/Retrieve/Check/Guardrail are deterministic. Only Write and Interpret call the LLM.
Write: verified FINDINGS (facts only). Interpret: reader-facing meaning + advice built on those
findings and on cited coaching-material chunks. Check and Guardrail verify both, in code.
"""
import json
import os
import re

import httpx

from app.agent.state import AgentState

MAX_RETRIES = 2

DISCLAIMER = ("This report is generated from your logged cycle data for information only. "
              "It is not medical advice and is not a diagnosis. Please talk to a doctor or other "
              "qualified health professional about any concerns.")

# Findings report sections in order: (heading, rag section holding its instructions)
SECTIONS = [("Summary", "summary"), ("Cycle length trend", "trend"), ("Variability", "variability"),
            ("Patterns", "patterns"), ("Notable cycles", "events"),
            ("Worth discussing with a doctor", "flags"), ("Caveats", "caveats")]
INTERPRET_HEADINGS = ["What we found", "What this may mean", "Things that may help", "Talking to your doctor"]

# Coaching material is German, so retrieval queries are German (cross-language scores are much lower).
# Case tags (from Analyse) steer which queries run.
TAG_QUERIES = {
    "variability_up": "Zyklus wird unregelmäßiger, schwankende Zykluslänge in der Perimenopause",
    "lengthening": "Zyklus verlängert sich, längere Zyklen in der Perimenopause",
    "skipped": "ausbleibende Periode, Zyklusausfall, Amenorrhoe in den Wechseljahren",
    "short_cycles": "verkürzter Zyklus, kurze Zyklen, Gelbkörperschwäche",
    "young": "unregelmäßiger Zyklus bei jüngeren Frauen, mögliche Ursachen wie Stress, PCOS, Schilddrüse",
    "stable": "regelmäßiger Zyklus, Zyklusbeobachtung und Selbstbeobachtung in der Beratung",
    "always": "Beratung Lebensstil Bewegung Ernährung Schlaf Stress bei Zyklusveränderungen",
    "gp": "Hormontherapie als Option, ärztliche Abklärung bei Zyklusveränderungen",
}
KNOWLEDGE_MIN_SIM, KNOWLEDGE_MAX_CHUNKS = 0.45, 6


# --- Fetch -------------------------------------------------------------------
def http() -> httpx.Client:
    """HTTP client for the data API. Tests replace this with a TestClient."""
    return httpx.Client(base_url=os.getenv("API_BASE_URL", "http://127.0.0.1:8000"), timeout=30)


def fetch(state: AgentState) -> dict:
    """Get computed stats from FastAPI /stats. The agent never sees raw cycle rows."""
    params = {"dataset_id": state["dataset_id"]}
    if state.get("user_id"):
        params["user_id"] = state["user_id"]
    with http() as c:
        r = c.get("/stats", params=params)
    r.raise_for_status()
    stats = r.json()
    if state.get("age") and stats.get("age") is None:  # age entered in the UI when the file has none
        stats["age"] = float(state["age"])
    return {"stats": stats, "retries": 0, "i_retries": 0}


# --- Analyse -----------------------------------------------------------------
def analyse(state: AgentState) -> dict:
    """Flag rules (rag_docs/instr_flags.md) and case tags, applied deterministically (no LLM)."""
    s = state["stats"]
    flags = []
    if (s.get("skipped_cycles") or 0) > 0:
        flags.append({"rule": "skipped_cycles", "value": s["skipped_cycles"],
                      "text": "a cycle of 60 days or more"})
    if (s.get("consecutive_jumps") or 0) >= 2:
        flags.append({"rule": "consecutive_jumps", "value": s["consecutive_jumps"],
                      "text": "cycle length changed by 7 days or more between consecutive cycles"})
    if s.get("mean_change") is not None and abs(s["mean_change"]) >= 7:
        flags.append({"rule": "mean_change", "value": s["mean_change"],
                      "text": "recent average differs from earlier average by 7 days or more"})
    rm = s.get("recent_mean")
    if rm is not None and not 21 <= rm <= 35:
        flags.append({"rule": "recent_mean", "value": rm, "text": "recent average outside 21 to 35 days"})

    tags = []
    if (s.get("consecutive_jumps") or 0) >= 2 or (s.get("sd_change") or 0) >= 3:
        tags.append("variability_up")
    if (s.get("mean_change") or 0) >= 5 or (s.get("trend_total_change_days") or 0) >= 7:
        tags.append("lengthening")
    if (s.get("skipped_cycles") or 0) > 0:
        tags.append("skipped")
    if (s.get("short_cycles") or 0) > 0:
        tags.append("short_cycles")
    if s.get("age") is not None and s["age"] < 40:
        tags.append("young")
    if not flags and not tags:
        tags.append("stable")
    return {"findings": {"flags": flags, "no_flags": not flags, "case_tags": tags,
                         "is_demo": str(state.get("dataset_id", "")).startswith("demo_")}}


# --- Retrieve ----------------------------------------------------------------
def retrieve(state: AgentState) -> dict:
    """RAG: instruction/reference/tone chunks, plus coaching `knowledge` chosen by the case tags."""
    from app.rag.retrieve import retrieve as rag

    ctx = []
    for section, query, k in [("reference", "typical cycle length and irregular cycle ranges", 3),
                              ("tone", "tone wording rules and required disclaimer", 2),
                              ("interpret", "interpretation instructions", 1)]:
        ctx += rag(query, k=k, section=section)
    for _, section in SECTIONS:
        if section != "events":
            ctx += rag(f"{section} section instructions", k=1, section=section)

    found = {}
    for tag in state["findings"].get("case_tags", []) + ["always", "gp"]:
        for h in rag(TAG_QUERIES[tag], k=3, section="knowledge"):
            if h["similarity"] >= KNOWLEDGE_MIN_SIM and h["id"] not in found:
                found[h["id"]] = h
    top = sorted(found.values(), key=lambda h: -h["similarity"])[:KNOWLEDGE_MAX_CHUNKS]
    return {"context": ctx + top}


def _by(ctx: list[dict], *sections) -> str:
    return "\n\n".join(f"[{c['section']}: {c['title']}]\n{c['content']}" for c in ctx if c["section"] in sections)


# --- Write (findings) --------------------------------------------------------
def _prompt(state: AgentState) -> list[dict]:
    ctx = state.get("context", [])
    outline = "\n".join(f"## {h}" for h, _ in SECTIONS)
    system = (
        "You write the FINDINGS part of a cycle-data report: facts only, no advice.\n"
        "HARD RULES\n"
        "- Use ONLY numbers and dates that appear in STATS, FINDINGS or REFERENCE below. Never calculate, round or "
        "estimate a new number. Copy values exactly as given.\n"
        "- Write dates as YYYY-MM-DD exactly as in the data.\n"
        "- Write in plain words. NEVER print field names such as sd_length, trend_days_per_cycle, recent_mean, "
        "low_confidence or consecutive_jumps; say 'variation', 'trend', 'recent average', 'jumps' instead.\n"
        "- Never diagnose or name a condition or stage. Do NOT write a disclaimer or closing note; one is appended "
        "automatically.\n"
        "- If a stat is null, do not mention it.\n"
        "- 'Notable cycles' section: list each item of stats.events (newest last) as one bullet: the date the cycle "
        "started and its length in days, in plain words (skipped = 60 days or more, long = over 35, short = under 21, "
        "jump = 7 days or more different from the cycle before). Say 'first time in this data' when first_time is "
        "true. Do not say what it means medically. If there are no events, write 'No notable cycles.'\n"
        f"- Output markdown starting with '# Your cycle findings' then exactly these sections:\n{outline}\n\n"
        f"TONE AND WORDING RULES\n{_by(ctx, 'tone')}\n\n"
        f"REFERENCE RANGES\n{_by(ctx, 'reference')}\n\n"
        f"SECTION INSTRUCTIONS\n{_by(ctx, 'summary', 'trend', 'variability', 'patterns', 'flags', 'caveats')}\n")
    user = ("STATS (the only source of numbers):\n" + json.dumps(state["stats"], indent=1) +
            "\n\nFINDINGS:\n" + json.dumps(state["findings"], indent=1))
    if state.get("check_errors"):
        user += ("\n\nYour previous draft failed verification. Fix ONLY these problems, using exact values "
                 "from STATS:\n- " + "\n- ".join(state["check_errors"]))
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def _llm(messages: list[dict]) -> str:
    from app.rag.clients import openai_client
    resp = openai_client().chat.completions.create(
        model=os.getenv("OPENAI_MODEL", "gpt-5.4-mini"), max_completion_tokens=3000, messages=messages)
    return resp.choices[0].message.content


def _strip_disclaimer(body: str) -> str:
    # the model sometimes writes its own disclaimer; cut it, ours is appended
    return re.split(r"(?m)^\W*This report is generated from your logged", body)[0].strip()


def write(state: AgentState) -> dict:
    """OpenAI drafts the findings report from stats + findings + retrieved context only."""
    body = _strip_disclaimer(_llm(_prompt(state)))
    return {"report": f"{body}\n\n---\n*{DISCLAIMER}*\n"}


# --- Check (findings) ----------------------------------------------------------
ISO = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
MONTH_YEAR = re.compile(r"\b(January|February|March|April|May|June|July|August|September|October|November|"
                        r"December)\s+(\d{4})\b")
NUM = re.compile(r"(?<![\w.\[])\d+(?:\.\d+)?")
FIELD_NAME = re.compile(r"\b[a-z]+(?:_[a-z]+)+\b")
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
          "November", "December"]


def _walk(x, nums: set, dates: set):
    """Collect every number and ISO date in a nested stats/findings structure."""
    if isinstance(x, dict):
        for v in x.values():
            _walk(v, nums, dates)
    elif isinstance(x, list):
        for v in x:
            _walk(v, nums, dates)
    elif isinstance(x, bool) or x is None:
        pass
    elif isinstance(x, (int, float)):
        nums.add(abs(float(x)))
    elif isinstance(x, str):
        if ISO.fullmatch(x):
            dates.add(x)
        else:
            nums.update(float(n) for n in NUM.findall(x))


def check_report(report: str, state: AgentState, sections: tuple | None = None) -> list[str]:
    """Problems in a report: numbers/dates not in stats/findings/reference, or raw field names.

    `sections`: which retrieved chunk sections may contribute allowed numbers (None = all).
    """
    nums, dates = set(), set()
    _walk(state.get("stats", {}), nums, dates)
    _walk(state.get("findings", {}), nums, dates)
    for c in state.get("context", []):  # thresholds quoted from reference/instruction chunks
        if sections is None or c["section"] in sections:
            nums.update(float(n) for n in NUM.findall(c["content"]))
    nums |= {float(d[:4]) for d in dates}  # years of known dates
    ym = {(MONTHS[int(d[5:7]) - 1], d[:4]) for d in dates}

    # drop the appended disclaimer/sources and markdown list markers before scanning
    text = re.split(r"\n---\n", report)[0]
    text = re.sub(r"(?m)^\s*(\d+[.)]|[-*])\s+", "", text)
    errors = []
    for d in ISO.findall(text):
        iso = "-".join(d)
        if iso not in dates:
            errors.append(f"date {iso} is not in the data")
    for m, y in MONTH_YEAR.findall(text):
        if (m, y) not in ym:
            errors.append(f"month {m} {y} is not in the data")
    scrubbed = MONTH_YEAR.sub("", ISO.sub("", text))
    for n in NUM.findall(scrubbed):
        if float(n) not in nums:
            errors.append(f"number {n} is not in the stats or reference text")
    for f in set(FIELD_NAME.findall(text)):
        errors.append(f"raw field name '{f}': use plain words")
    return sorted(set(errors))


def check(state: AgentState) -> dict:
    """Verify every number and date in the findings. On failure: record errors and count a retry."""
    errors = check_report(state.get("report", ""), state)
    if not errors:
        return {"passed": True, "check_errors": []}
    return {"passed": False, "check_errors": errors, "retries": state.get("retries", 0) + 1}


def route_after_check(state: AgentState) -> str:
    """Pass -> Interpret. Fail -> back to Write, at most MAX_RETRIES times, then Interpret anyway."""
    if state.get("passed"):
        return "interpret"
    return "write" if state.get("retries", 0) <= MAX_RETRIES else "interpret"


# --- Interpret ---------------------------------------------------------------
def _source_map(ctx: list[dict]) -> dict:
    """S1, S2, ... -> citation text for the knowledge chunks (stable order)."""
    ks = [c for c in ctx if c["section"] == "knowledge"]
    return {f"S{i}": c["title"].rsplit(" (#", 1)[0] for i, c in enumerate(ks, start=1)}


def _interpret_prompt(state: AgentState) -> list[dict]:
    ctx = state.get("context", [])
    ks = [c for c in ctx if c["section"] == "knowledge"]
    sources = "\n\n".join(f"[S{i}] {c['title'].rsplit(' (#', 1)[0]}\n{c['content']}" for i, c in enumerate(ks, 1))
    outline = "\n".join(f"## {h}" for h in INTERPRET_HEADINGS)
    system = (
        "You turn VERIFIED FINDINGS into a reader-facing report with interpretation and advice.\n"
        "HARD RULES\n"
        "- Numbers and dates: only those in the findings report or stats. No new numbers, no figures from the sources.\n"
        "- Plain words; never print field names like sd_length. Never diagnose; never say 'you have' or "
        "'you are in' perimenopause or any condition. Say 'your data shows'.\n"
        "- Meaning and advice come ONLY from the numbered SOURCES. Every sentence in 'What this may mean' and "
        "'Things that may help' ends with a tag like [S2] naming the source it comes from. Never invent a tag.\n"
        "- No doses. Never tell the reader to start, stop or change a medication or supplement. Hormone therapy or "
        "other treatment: 'can be an option to discuss with a GP'. Use 'can help' / 'some people find'.\n"
        "- Do NOT write a disclaimer or source list; both are appended automatically.\n"
        f"- Output markdown starting with '# Your cycle report' then exactly these sections:\n{outline}\n\n"
        f"TONE AND WORDING RULES\n{_by(ctx, 'tone')}\n\n"
        f"INTERPRETATION INSTRUCTIONS\n{_by(ctx, 'interpret')}\n\n"
        f"SOURCES (German coaching material; translate the ideas)\n{sources or '(none retrieved)'}\n")
    if "young" in state["findings"].get("case_tags", []):
        system += ("\nAGE RULE: this reader is under 40. Do NOT frame the findings as perimenopause, menopause or "
                   "'the hormonal transition'. Use only the sources' points about other common reasons cycles vary "
                   "(for example stress, sleep, thyroid, PCOS) and say a doctor can check them.\n")
    user = ("VERIFIED FINDINGS REPORT:\n" + state["report"].split("\n---\n")[0] +
            "\n\nCASE TAGS: " + ", ".join(state["findings"].get("case_tags", [])) +
            "\nFLAGS: " + json.dumps(state["findings"].get("flags", [])))
    if state.get("guard_errors"):
        user += ("\n\nYour previous draft failed these checks. Fix ONLY these problems:\n- "
                 + "\n- ".join(state["guard_errors"]))
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def interpret(state: AgentState) -> dict:
    """OpenAI writes the human report from verified findings + cited coaching chunks."""
    body = _strip_disclaimer(_llm(_interpret_prompt(state)))
    sources = _source_map(state.get("context", []))
    used = [t for t in sources if f"[{t}]" in body]
    src = "\n".join(f"- [{t}] {sources[t]}" for t in used)
    tail = f"\n\n---\n**Sources (MenoCert coaching material)**\n{src}" if src else ""
    return {"human_report": f"{body}{tail}\n\n---\n*{DISCLAIMER}*\n", "sources": sources}


# --- Guardrail (interpretation) ---------------------------------------------
TAG = re.compile(r"\[(S\d+)\]")
BANNED = [(re.compile(r"\byou (have|are in|suffer from)\b", re.I), "diagnostic wording ('you have / you are in')"),
          (re.compile(r"\b\d+(\.\d+)?\s?(mg|µg|mcg|ml|iu|g)\b", re.I), "dose or lab figure"),
          (re.compile(r"\b(stop|start|increase|reduce|skip)\s+(taking|your)\b", re.I),
           "instruction to change medication"),
          (re.compile(r"\b(will cure|guaranteed|always works|fix(es)? everything)\b", re.I), "promise of outcome")]


YOUNG_BANNED = re.compile(r"transition|perimenopaus|menopaus|wechseljahr", re.I)


def guard_report(body: str, state: AgentState) -> list[str]:
    """Deterministic checks on the human report. Returns problems (empty = pass)."""
    sources = _source_map(state.get("context", []))
    text = re.split(r"\n---\n", body)[0]
    errors = check_report(text, state, sections=("reference",))
    for h in INTERPRET_HEADINGS:
        if f"## {h}" not in text:
            errors.append(f"missing section '{h}'")
    for t in set(TAG.findall(text)):
        if t not in sources:
            errors.append(f"citation [{t}] does not exist")
    for h in ("What this may mean", "Things that may help"):
        m = re.search(rf"## {h}\n(.*?)(?=\n## |\Z)", text, re.S)
        if m and sources:
            for line in [x.strip() for x in m.group(1).splitlines() if x.strip()]:
                if not TAG.search(line):
                    errors.append(f"uncited statement in '{h}': {line[:60]}")
    if "young" in state.get("findings", {}).get("case_tags", []) and YOUNG_BANNED.search(text):
        errors.append("reader is under 40: do not frame findings as perimenopause/menopause/hormonal transition")
    for rx, msg in BANNED:
        if rx.search(text):
            errors.append(f"banned pattern: {msg}")
    return sorted(set(errors))


def guardrail(state: AgentState) -> dict:
    errors = guard_report(state.get("human_report", ""), state)
    if not errors:
        return {"guard_errors": []}
    return {"guard_errors": errors, "i_retries": state.get("i_retries", 0) + 1}


def route_after_guard(state: AgentState) -> str:
    """No errors -> finish. Errors -> back to Interpret, at most MAX_RETRIES times, then finish flagged."""
    if not state.get("guard_errors"):
        return "end"
    return "interpret" if state.get("i_retries", 0) <= MAX_RETRIES else "end"
