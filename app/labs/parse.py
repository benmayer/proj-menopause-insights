"""Lab report parser (plain code, no LLM). German practice/lab PDFs with a text layer.

Reads ONLY an allow-list of analytes plus draw date, cycle day and the date of birth (used to compute age, then dropped).
Name, address, lab number and every other result (e.g. infection serology) are never extracted or returned.
The flag (below / within / above) is computed here from the range printed on the report, not read from the PDF's +/- marks.
"""
import io
import re
from datetime import date

import pypdf

MAX_BYTES = 5_000_000


class LabParseError(ValueError):
    pass


# canonical key -> aliases as printed on German reports (matched case-insensitively as whole words)
ANALYTES = {
    "fsh": ["FSH"], "lh": ["LH"], "e2": ["E2", "Estradiol", "Östradiol"],
    "progesterone": ["Prog", "Progesteron"], "amh": ["AMH"], "prolactin": ["Prol", "Prolaktin"],
    "testosterone": ["Testosteron"], "shbg": ["SHBG"], "dheas": ["DHEAS", "DHEA-S"], "fai": ["FAI"],
    "tsh": ["TSH"], "ft3": ["fT3"], "ft4": ["fT4"], "ferritin": ["Ferritin"], "tpo": ["TPO"],
    "hb": ["HB", "Hämoglobin"], "androstenedione": ["Androstendion"],
}
UNITS = ["mIU/ml", "µIU/ml", "uIU/ml", "ng/ml", "pg/ml", "nmol/L", "nmol/l", "µg/dl", "ng/dl", "ng/l", "pg/dl",
         "mg/dl", "g/dl", "kIU/l", "IU/ml", "IU/l", "U/l", "Vol%", "c/pl", "c/nl", "Index", "fl", "pg", "ng"]
U = "|".join(re.escape(u) for u in sorted(UNITS, key=len, reverse=True))
N = r"\d+(?:[.,]\d+)?"
ALIAS = {a.lower(): k for k, v in ANALYTES.items() for a in v}
START = re.compile(r"^(?:\(\*\)\s*)?(" + "|".join(re.escape(a) for a in sorted(ALIAS, key=len, reverse=True)) + r")\b\s+(" + N + r")\s*[-+]?\s*(" + U + r")",
                   re.I)
BLOCK_END = re.compile(r"^(?:\(\*\)|Patient:|\(MVZ|Beckmann|Befund |bei Rückfragen)")


def _num(s: str) -> float:
    return float(s.replace(",", "."))


def _date(s: str) -> date:
    d, m, y = (int(x) for x in s.split("."))
    return date(y, m, d)


def _age(dob: date, on: date) -> int:
    return on.year - dob.year - ((on.month, on.day) < (dob.month, dob.day))


def _range(rest: str):
    """(low, high) from the text after the unit. '3,5 - 12,5', '0,17 ng/ml -\\n7,37 ng/ml', '< 34.0'."""
    m = re.search(rf"({N})\s*(?:{U})?\s*-\s*({N})", rest, re.I)
    if m:
        return _num(m.group(1)), _num(m.group(2))
    m = re.search(rf"<\s*({N})", rest)
    if m:
        return None, _num(m.group(1))
    m = re.search(rf">\s*({N})", rest)
    if m:
        return _num(m.group(1)), None
    return None, None


def flag(value: float, low, high) -> str | None:
    if low is not None and value < low:
        return "below"
    if high is not None and value > high:
        return "above"
    return "within" if (low is not None or high is not None) else None


def parse_text(text: str, today: date | None = None) -> dict:
    today = today or date.today()
    m = re.search(r"Entnahme:\s*(\d{2}\.\d{2}\.\d{4})", text) or re.search(r"Eingang:\s*(\d{2}\.\d{2}\.\d{4})", text)
    if not m:
        raise LabParseError("No draw date (Entnahme) found: is this a lab report?")
    draw = _date(m.group(1))
    zt = re.search(r"\bZT:\s*(\d{1,2})\b", text)
    dob = re.search(r"geb\. am:\s*(\d{2}\.\d{2}\.\d{4})", text)

    results, block = [], None
    for line in (ln.strip() for ln in text.splitlines()):
        s = START.match(line)
        if s:
            block = {"analyte": ALIAS[s.group(1).lower()], "value": _num(s.group(2)), "unit": s.group(3), "rest": line[s.end():]}
            results.append(block)
        elif BLOCK_END.match(line):
            block = None
        elif block is not None:
            block["rest"] += " " + line
    out = []
    for r in results:
        low, high = _range(r.pop("rest"))
        out.append({**r, "ref_low": low, "ref_high": high, "flag": flag(r["value"], low, high)})
    if not out:
        raise LabParseError("No supported lab values found in this report.")
    return {"draw_date": str(draw), "cycle_day": int(zt.group(1)) if zt else None,
            "age_at_draw": _age(_date(dob.group(1)), draw) if dob else None,
            "age_today": _age(_date(dob.group(1)), today) if dob else None,
            "results": out}


def parse_pdf(data: bytes, today: date | None = None) -> dict:
    if len(data) > MAX_BYTES:
        raise LabParseError("File too large (max 5 MB).")
    try:
        text = "\n".join(p.extract_text() or "" for p in pypdf.PdfReader(io.BytesIO(data)).pages)
    except Exception:
        raise LabParseError("Could not read this PDF.") from None
    if len(text.strip()) < 50:
        raise LabParseError("This PDF has no text layer (scanned?). Only text PDFs are supported.")
    return parse_text(text, today)
