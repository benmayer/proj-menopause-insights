"""Lab parser tests. Fixtures are made-up text in the layout of real German lab PDFs (no real patient data)."""
import json
from datetime import date
from pathlib import Path

import pytest

from app.labs.parse import LabParseError, parse_pdf, parse_text

FAKE = """Praxis Muster
Endbefund
Frau
Erika Mustermann
Beispielweg 1
12345 Teststadt
Patient: Erika Mustermann Labornummer:99999 Seite 1 / 2
geb. am: 16.07.1980 ZT: 7 Eingang: 03.04.2025 16:20:38
Entnahme: 03.04.2025
Untersuchung Resultat EinheitReferenzbereich
FAI 1,54 Index
Ferritin 45,9 ng/ml 11 - 306,8
ng/ml
LH 2,33-mIU/ml2,4 - 12,6
mIU/ml
Testosteron 0,40+ng/ml 0,08 - 0,48
ng/ml
FSH 10,33 mIU/ml3,5 - 12,5
mIU/ml
TSH 0,69 µIU/ml 0,27 - 4,0
µIU/ml
AMH 0,39 ng/ml 0,17 ng/ml -
7,37 ng/ml
ng/ml
(*) HB 11.5-g/dl 11.6 - 15.5 g/dl11.6-15.5
(*) CTRG 39.7+AU/ml < 9.0 IgG-Antikörper gegen C. trachomatis wurden nachgewiesen.
(*) TPO 21.1 kIU/l < 34.0
"""


def by(res):
    return {r["analyte"]: r for r in res["results"]}


def test_values_ranges_and_flags_come_from_the_printed_range():
    r = by(parse_text(FAKE, today=date(2026, 11, 11)))
    assert r["fsh"] | {} == {"analyte": "fsh", "value": 10.33, "unit": "mIU/ml", "ref_low": 3.5, "ref_high": 12.5, "flag": "within"}
    assert r["lh"]["flag"] == "below" and r["lh"]["value"] == 2.33
    assert r["hb"]["flag"] == "below" and r["hb"]["unit"] == "g/dl"
    assert r["tsh"]["unit"] == "µIU/ml" and r["tsh"]["flag"] == "within"
    assert r["fai"]["flag"] is None and r["fai"]["ref_low"] is None


def test_plus_sign_in_the_pdf_is_ignored_the_range_decides():
    # printed with a "+" glyph, but 0.40 is inside 0.08-0.48
    assert by(parse_text(FAKE))["testosterone"]["flag"] == "within"


def test_wrapped_and_upper_only_ranges():
    r = by(parse_text(FAKE))
    assert (r["amh"]["ref_low"], r["amh"]["ref_high"]) == (0.17, 7.37)
    assert (r["tpo"]["ref_low"], r["tpo"]["ref_high"]) == (None, 34.0)


def test_only_allow_listed_analytes_and_no_personal_data():
    res = parse_text(FAKE, today=date(2026, 11, 11))
    assert "ctrg" not in by(res)
    dump = json.dumps(res, ensure_ascii=False)
    for secret in ("Mustermann", "Beispielweg", "99999", "1980", "16.07"):
        assert secret not in dump
    assert res["draw_date"] == "2025-04-03" and res["cycle_day"] == 7
    assert res["age_at_draw"] == 44 and res["age_today"] == 46


def test_errors():
    with pytest.raises(LabParseError):
        parse_text("just some text without a date")
    with pytest.raises(LabParseError):
        parse_text("Entnahme: 03.04.2025\nnothing else we know")
    with pytest.raises(LabParseError):
        parse_pdf(b"%PDF-1.4 not really a pdf")
    with pytest.raises(LabParseError):
        parse_pdf(b"x" * 5_000_001)


REAL = sorted(Path(__file__).parent.parent.glob("data/bloodtests/*.pdf"))


@pytest.mark.skipif(not REAL, reason="real lab PDFs are local only (data/ is gitignored)")
@pytest.mark.parametrize("pdf", REAL, ids=lambda p: p.name)
def test_real_pdfs_parse_and_leak_nothing(pdf):
    res = parse_pdf(pdf.read_bytes())
    r = by(res)
    assert {"fsh", "e2", "tsh", "ft3", "ft4", "lh"} <= set(r)
    assert all(x["flag"] for k, x in r.items() if x["ref_low"] is not None or x["ref_high"] is not None)
    assert "ctrg" not in r and res["age_at_draw"] is not None
    assert not {"name", "dob", "address"} & set(res)
