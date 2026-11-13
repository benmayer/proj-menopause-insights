"""Labs through Retrieve, Write, Interpret and the Guardrail (LLM and RAG stubbed)."""
import pytest

from app.agent import nodes
from tests.test_lab_summary import draw

STATS = {"n_cycles": 26, "age": 46.0, "skipped_cycles": 1, "consecutive_jumps": 3, "mean_change": 9.0,
         "recent_mean": 39.0, "events": []}


def state(labs, intake=None, age=46.0, **extra):
    st = {"stats": {**STATS, "age": age}, "dataset_id": "x", "intake": intake, "labs": labs, **extra}
    st["findings"] = nodes.analyse(st)["findings"]
    st["findings"] = nodes.triage(st)["findings"]
    return st


HIGH = [draw("2025-04-03", 3, fsh=30.0, e2=15.0, amh=0.1, hb=11.5)]
SYM = {"symptoms": {"temperature": 3, "sleep": 2}}


def test_findings_and_interpret_sections_follow_labs():
    st = state(HIGH, SYM)
    assert nodes.LAB_FINDINGS_HEADING in nodes._sections(st)
    heads = nodes.interpret_headings(st)
    assert heads.index(nodes.LAB_HEADING) == heads.index(nodes.CYCLE_H) + 1
    assert heads.index(nodes.SYMPTOM_HEADING) == heads.index(nodes.LAB_HEADING) + 1 and heads[-3] == nodes.MEANING_H
    plain = state(None)
    assert nodes.LAB_FINDINGS_HEADING not in nodes._sections(plain) and nodes.LAB_HEADING not in nodes.interpret_headings(plain)


def test_prompts_carry_lab_rules_and_values():
    st = state(HIGH, SYM)
    st["context"], st["report"] = [], "# Findings\n---\n"
    w = nodes._prompt(st)
    assert "Your lab values" in w[0]["content"] and '"fsh"' in w[1]["content"]
    i = nodes._interpret_prompt(st)
    assert "READER LABS" in i[1]["content"] and "LABS BRIEF" in i[1]["content"] and "EXPLANATIONS" in i[1]["content"]
    assert "Say a value is low or high only when the data shows it" in i[0]["content"]
    assert "READER LABS" not in nodes._interpret_prompt({**state(None), "context": [], "report": "x\n---\n"})[1]["content"]


def test_llm_sees_only_relevant_lab_groups():
    labs = [draw("2025-04-03", 3, fsh=8.0, tsh=1.0)]
    labs[0]["results"].append({"analyte": "ferritin", "value": 45.9, "unit": "ng/ml", "ref_low": 11, "ref_high": 306.8, "flag": "within"})
    view = nodes._labs_view(state(labs)["findings"]["labs"])
    assert {r["analyte"] for r in view["draws"][0]["results"]} == {"fsh", "tsh"}      # ferritin within range: left out


def test_retrieve_adds_lab_cards_and_lab_chunks(monkeypatch):
    import app.rag.retrieve as rr
    hit = lambda i, sec="knowledge": {"id": i, "section": sec, "title": f"t{i}", "content": "c", "similarity": 0.7}
    monkeypatch.setattr(rr, "retrieve", lambda q, k=3, section=None: [hit(hash((q, n)) % 10**6, section) for n in range(k)])
    monkeypatch.setattr(rr, "symptom_cards", lambda keys: [])
    asked = []
    monkeypatch.setattr(rr, "lab_cards", lambda titles: asked.append(titles) or [{"id": "L", "section": "lab_map", "title": titles[0], "content": "x"}])
    ctx = nodes.retrieve(state(HIGH, SYM))["context"]
    assert asked and asked[0][0] == "How to read lab values" and "FSH (follicle-stimulating hormone)" in asked[0]
    assert any(c["section"] == "lab_map" for c in ctx)
    assert nodes.retrieve(state(None))["context"]  # no labs: no lab cards requested
    assert len(asked) == 1


LABCTX = [{"section": "knowledge", "title": "Modul 3, S. 29 (#1)", "content": "FSH above 25"},
          {"section": "lab_map", "title": "FSH (follicle-stimulating hormone)", "content": "range 3.0 to 15.0"},
          {"section": "reference", "title": "r", "content": "21 to 35 days"}]
GOODLAB = ("# Your cycle report\n## Summary\nYour data shows 26 cycles.\n"
           "## Your cycle\nYour recent average is 39.0 days, longer than typical. [S1]\n"
           "## Your blood results\n"
           "- Your FSH (follicle-stimulating hormone) was 30 mIU/ml, above the lab's range. FSH rises in the transition. [S1]\n"
           "- Your oestradiol (E2) is below the lab's range.\n"
           "- Your AMH (anti-Müllerian hormone) is below the lab's range.\n"
           "- Your haemoglobin was 11.5 g/dl, below the lab's range.\n"
           "## What it could mean\nChanges can have many causes and a doctor can check them. [S1]\n"
           "## Things that may help\nSome people find sleep routines help. [S1]\n"
           "## Talking to your doctor\nBring these results to your doctor. [S1]")


def _g(body, st):
    st["context"] = LABCTX
    return nodes.guard_report(body, st)


def test_guard_accepts_clean_lab_report_and_does_not_treat_lab_values_as_doses():
    assert _g(GOODLAB, state(HIGH)) == []


def test_guard_lab_section_required_cited_and_wording():
    st = state(HIGH)
    assert any("missing section" in e for e in _g(GOODLAB.replace("## Your blood results", "## Blood"), st))
    assert any("must name 'haemoglobin'" in e for e in _g(GOODLAB.replace("Your haemoglobin", "Your Hb"), st))
    assert any("bullets" in e for e in _g(GOODLAB.replace("- Your haemoglobin", "- Your TSH is in range.\n- Your haemoglobin"), st))
    assert any("internal term" in e for e in _g(GOODLAB.replace("Bring these", "This remains untested. Bring these"), st))
    assert any("never 'printed'" in e for e in _g(GOODLAB.replace("above the lab's range", "above the printed range"), st))
    unc = GOODLAB.replace("FSH rises in the transition. [S1]", "FSH rises in the transition.")
    assert any("cites no source" in e for e in _g(unc, st))
    unc_help = GOODLAB.replace("sleep routines help. [S1]", "sleep routines help.")
    assert any("uncited" in e for e in _g(unc_help, st))
    # low/high claims are allowed when code backs them (FSH above range, E2 below), not otherwise
    assert _g(GOODLAB.replace("Your FSH was 30", "Your FSH is high at 30"), st) == []
    assert _g(GOODLAB.replace("Your data shows", "Your oestradiol is low. Your data shows"), st) == []
    assert any("hormone levels" in e for e in _g(GOODLAB.replace("Your data shows", "Your TSH is high. Your data shows"), st))
    assert any("speak as the coach" in e for e in _g(GOODLAB.replace("FSH rises", "The material says FSH rises"), st))
    assert any("cannot confirm" in e for e in _g(GOODLAB.replace("Bring these", "This test confirms it. Bring these"), st))
    assert any("labelling" in e for e in _g(GOODLAB.replace("Bring these", "You are entering menopause. Bring these"), st))


def test_age_is_soft_for_young_readers_only_with_high_alignment_and_a_doctor():
    wording = GOODLAB.replace("Changes can have", "The pattern is in line with an early transition. Changes can have")
    high = state(HIGH, None, age=32.0)
    assert high["findings"]["labs"]["alignment"]["level"] == "high" and "young" in high["findings"]["case_tags"]
    assert _g(wording, high) == []                                            # allowed: strong alignment + "doctor" present
    no_doc = wording.replace("doctor", "clinician")  # heading and sentences no longer mention a doctor
    assert any("needs a suggestion" in e for e in _g(no_doc, high))
    weak = state([draw("2025-04-03", 3, fsh=6.0, e2=100.0, amh=3.0)], None, age=32.0)
    assert any("under 40" in e for e in _g(wording, weak))                    # no alignment: still blocked


def test_interpret_adds_fixed_lab_safety_lines(monkeypatch):
    monkeypatch.setattr(nodes, "_llm", lambda m: "# Your cycle report\n## Summary\nok")
    thyroid = state([draw("2025-04-03", 3, tsh=6.0)], None)
    thyroid["context"], thyroid["report"] = [], "# F\n---\n"
    out = nodes.interpret(thyroid)["human_report"]
    assert nodes.LAB_SAFETY["thyroid"] in out and "Worth acting on soon" in out
    young = state(HIGH, SYM, age=32.0)
    young["context"], young["report"] = [], "# F\n---\n"
    assert nodes.LAB_SAFETY["early"] in nodes.interpret(young)["human_report"]
    calm = state([draw("2025-04-03", 3, tsh=1.0)], None)
    calm["context"], calm["report"] = [], "# F\n---\n"
    assert "Worth acting on soon" not in nodes.interpret(calm)["human_report"]


@pytest.mark.parametrize("age,expect", [(46.0, "age_40_plus"), (32.0, None)])
def test_age_signal_only_counts_from_40(age, expect):
    ids = {s["id"] for s in state(HIGH, SYM, age=age)["findings"]["labs"]["alignment"]["signals"]}
    assert (expect in ids) if expect else ("age_40_plus" not in ids)


def test_early_for_your_age_is_blocked_for_readers_40_and_over():
    older = state(HIGH, None, age=46.0)
    bad = GOODLAB.replace("Changes can have", "This would be early for your age. Changes can have")
    assert any("early for the reader" in e for e in _g(bad, older))
    young = state(HIGH, None, age=32.0)
    assert not any("early for the reader" in e for e in _g(bad, young))


def test_lab_rules_depend_on_age_and_ask_for_comparable_changes():
    assert "NEVER say anything would be 'early'" in nodes.lab_rules(False) and "under 40" not in nodes.lab_rules(False)
    assert "early menopause" in nodes.lab_rules(True) and "LABS BRIEF changes" in nodes.lab_rules(False)
