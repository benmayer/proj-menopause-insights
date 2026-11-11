"""Symptom vocabulary: the 15 body systems of the MenoCert table and the 34 symptoms of the onboarding
questionnaire, each symptom mapped to a body system (or None when the table has no matching row).

`SYSTEMS` keys -> card title in rag_docs/symptom_map.md. The mapping is deterministic code, not search:
a symptom the table does not list stays unmapped and gets no "possible hormonal factors" card.
"""

# key: (card title = '## ' heading in symptom_map.md, example symptoms shown in the quick form)
SYSTEMS = {
    "mind":        ("Central nervous system and mind", "brain fog, mood swings, irritability, anxiety"),
    "sleep":       ("Sleep regulation", "trouble falling asleep, waking early, unrefreshing sleep"),
    "skin":        ("Skin and mucous membranes", "dry or itchy skin, dry mouth"),
    "hair_nails":  ("Hair and nails", "thinning hair, brittle nails"),
    "breast":      ("Breasts", "tenderness or pain"),
    "cycle":       ("Cycle and reproduction", "irregular, very heavy or very light periods, PMS"),
    "sexuality":   ("Sexuality and libido", "low libido, vaginal dryness, painful sex"),
    "heart":       ("Cardiovascular system", "palpitations, blood pressure swings"),
    "muscles":     ("Muscles and joints", "joint or muscle pain, tension, cramps"),
    "bones":       ("Bones", "bone pain, concern about bone density"),
    "metabolism":  ("Metabolism and weight", "weight gain around the belly, cravings"),
    "digestion":   ("Digestion", "bloating, constipation, food intolerances"),
    "immune":      ("Immune system", "frequent infections, allergies, inflammation"),
    "temperature": ("Temperature regulation", "hot flushes, night sweats, feeling cold"),
    "eyes":        ("Eyes and vision", "dry eyes, light sensitivity"),
}

# Questionnaire symptoms: id -> (English label, German label, system key or None)
SYMPTOMS = {
    "hot_flushes":      ("Hot flushes", "Hitzewallungen", "temperature"),
    "night_sweats":     ("Night sweats / sweating", "Nachtschweiß / Schwitzen", "temperature"),
    "sleep_problems":   ("Sleep problems", "Schlafprobleme", "sleep"),
    "mood_swings":      ("Mood swings", "Stimmungsschwankungen", "mind"),
    "irritability":     ("Irritability", "Reizbarkeit", "mind"),
    "anxiety":          ("Anxiety", "Angst", "mind"),
    "fatigue":          ("Exhaustion / fatigue", "Erschöpfung / Müdigkeit", None),
    "brain_fog":        ("Brain fog", "Gehirnnebel", "mind"),
    "low_libido":       ("Reduced libido", "Verminderte Libido", "sexuality"),
    "low_mood":         ("Depressive mood", "Depressive Verstimmungen", "mind"),
    "palpitations":     ("Heart palpitations", "Herzklopfen", "heart"),
    "itching":          ("Itching", "Juckreiz", "skin"),
    "joint_muscle":     ("Joint and muscle pain", "Gelenk- & Muskelschmerzen", "muscles"),
    "weight_gain":      ("Weight gain (hard to control)", "Gewichtszunahme", "metabolism"),
    "skin_changes":     ("Skin changes (dryness, elasticity)", "Hautveränderungen", "skin"),
    "headaches":        ("Headaches", "Kopfschmerzen", None),
    "bloating":         ("Bloating", "Blähungen", "digestion"),
    "thinning_hair":    ("Thinning hair", "Dünner werdendes Haar", "hair_nails"),
    "dry_eyes":         ("Dry eyes", "Trockene Augen", "eyes"),
    "dry_mouth":        ("Dry mouth", "Trockener Mund", "skin"),
    "breast_pain":      ("Sore breasts", "Schmerzende Brüste", "breast"),
    "tearfulness":      ("Tearfulness / sensitivity", "Weinerlichkeit / Dünnhäutigkeit", "mind"),
    "panic_attacks":    ("Panic attacks", "Panikattacken", "mind"),
    "brittle_nails":    ("Brittle nails", "Brüchige Nägel", "hair_nails"),
    "uti":              ("Urinary tract infections", "Harnwegsinfekte", None),
    "incontinence":     ("Urinary incontinence", "Harninkontinenz", None),
    "restless_legs":    ("Restless legs", "Unruhige Beine", None),
    "vaginal_dryness":  ("Vaginal dryness", "Trockene Vagina", "sexuality"),
    "vaginal_discomfort": ("Vaginal discomfort (burning, itching, thrush)", "Vaginales Unbehagen", "sexuality"),
    "discharge":        ("Increased vaginal discharge", "Verstärkter vaginaler Ausfluss", None),
    "painful_sex":      ("Painful sex", "Schmerzhafter Sex", "sexuality"),
    "low_confidence":   ("Low self-confidence", "Geringes Selbstvertrauen", None),
    "cannot_cope":      ("Unable to get tasks done", "Unfähigkeit, Aufgaben zu erledigen", None),
    "anger":            ("Anger and rage", "Wut und Zorn", "mind"),
}


def systems_of(ratings: dict[str, int]) -> list[str]:
    """Body-system keys with at least one symptom rated > 0 (symptom ids, or system keys directly)."""
    out = []
    for k, v in ratings.items():
        if not v:
            continue
        key = k if k in SYSTEMS else (SYMPTOMS[k][2] if k in SYMPTOMS else None)
        if key and key not in out:
            out.append(key)
    return out


def rate_systems(ratings: dict[str, int]) -> dict[str, int]:
    """Highest rating (1-3) per body system, from symptom ids or system keys. Zeros and unmapped symptoms drop out."""
    out: dict[str, int] = {}
    for k, v in ratings.items():
        key = k if k in SYSTEMS else (SYMPTOMS[k][2] if k in SYMPTOMS else None)
        if key and v:
            out[key] = max(out.get(key, 0), int(v))
    return out
