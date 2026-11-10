import json

import pytest

from app.analysis.normalise import NormaliseError, load_upload


def clue(days):
    return json.dumps([{"type": "period", "id": str(i), "date": d, "value": {"option": f}}
                       for i, (d, f) in enumerate(days)] +
                      [{"type": "pain", "id": "x", "date": "2024-01-02", "value": [{"option": "cramps"}]}]).encode()


def test_clue_groups_days_into_cycles():
    # cycle 1: 3 days (Jan 1-3), cycle 2 starts Jan 29 (28 days later), 2 days
    raw = clue([("2024-01-01", "light"), ("2024-01-02", "heavy"), ("2024-01-03", "heavy"),
                ("2024-01-29", "medium"), ("2024-01-30", "medium")])
    df = load_upload(raw, "measurements.json")
    assert len(df) == 2
    assert df.cycle_length.iloc[0] == 28 and df.cycle_length.isna().iloc[1]
    assert list(df.period_length) == [3, 2]
    assert list(df.flow) == ["Heavy", "Medium"]  # most common flow per period


def test_csv_without_cycle_length_derives_it():
    df = load_upload(b"Start Date\n2024-01-01\n2024-01-30\n2024-02-27\n", "me.csv")
    assert list(df.cycle_length.dropna()) == [29, 28]
    assert (df.user_id == "me").all()


def test_missing_date_column_gives_clear_error():
    with pytest.raises(NormaliseError):
        load_upload(b"foo,bar\n1,2\n", "x.csv")


def test_bad_json_gives_clear_error():
    with pytest.raises(NormaliseError):
        load_upload(b"[{not json", "x.json")
