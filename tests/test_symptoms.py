import re
from pathlib import Path

from app.agent.symptoms import SYMPTOMS, SYSTEMS, systems_of

_CARDS = Path(__file__).resolve().parent.parent / "rag_docs" / "symptom_map.md"
if not _CARDS.exists():  # licensed-source transcription: kept local, not in git
    pytest.skip("rag_docs/symptom_map.md is local only", allow_module_level=True)
CARDS = _CARDS.read_text()


def test_every_system_has_a_card_and_every_card_a_system():
    titles = set(re.findall(r"(?m)^## (.+)$", CARDS))
    assert titles == {t for t, _ in SYSTEMS.values()} and len(titles) == 15


def test_questionnaire_has_34_symptoms_all_mapped_to_known_systems_or_none():
    assert len(SYMPTOMS) == 34
    assert all(sys is None or sys in SYSTEMS for _, _, sys in SYMPTOMS.values())


def test_systems_of_ignores_zero_and_unmapped():
    got = systems_of({"hot_flushes": 2, "night_sweats": 3, "fatigue": 3, "brain_fog": 0, "sleep_problems": 1})
    assert got == ["temperature", "sleep"]  # fatigue has no table row; brain_fog rated 0
    assert systems_of({"eyes": 1}) == ["eyes"]


def test_live_symptom_cards_lookup():
    import os
    import pytest
    if not os.getenv("SUPABASE_API_KEY"):
        pytest.skip("needs .env keys")
    from app.rag.retrieve import symptom_cards
    cards = symptom_cards(["temperature", "sleep"])
    assert [c["title"] for c in cards] == ["Temperature regulation", "Sleep regulation"]
    assert "thyroid" in cards[0]["content"]
