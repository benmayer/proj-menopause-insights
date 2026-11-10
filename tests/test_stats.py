"""Hand-computed fixtures. Working is in the comments."""
import pandas as pd
import pytest

from app.analysis.stats import compute_stats, cycle_series


def frame(lengths, **extra):
    starts = pd.Timestamp("2024-01-01") + pd.to_timedelta(
        [sum(lengths[:i]) for i in range(len(lengths))], unit="D")
    df = pd.DataFrame({"user_id": "u", "cycle_start": starts, "cycle_length": pd.array(lengths, "Int64"),
                       "period_length": pd.NA, "flow": pd.NA, "age": pd.NA})
    for k, v in extra.items():
        df[k] = v
    return df


def test_basic_stats_stable_user():
    # lengths 28,30,26,32,28,30: mean 29; deviations -1,1,-3,3,-1,1 -> squares sum 22 -> var 22/5=4.4 -> sd 2.098
    # slope: sum((x-2.5)(y-29)) = 5.0, sum((x-2.5)^2) = 17.5 -> 0.2857
    s = compute_stats(frame([28, 30, 26, 32, 28, 30]))
    assert s["n_cycles"] == 6 and not s["low_confidence"]
    assert s["mean_length"] == 29.0 and s["median_length"] == 29.0
    assert s["sd_length"] == 2.1
    assert s["trend_days_per_cycle"] == 0.29
    assert (s["min_length"], s["max_length"]) == (26, 32)
    assert s["consecutive_jumps"] == 0 and s["long_cycles"] == 0 and s["skipped_cycles"] == 0
    assert s["baseline_mean"] is None  # only 6 cycles, no baseline before the recent window


def test_perimenopause_like_pattern():
    # 28 x6 then 35,42,50,64. Recent window (last 6) = 28,28,35,42,50,64: mean 247/6 = 41.17, sd 14.03.
    # Baseline (first 4) = 28,28,28,28: mean 28, sd 0. Jumps >= 7: 7,7,8,14 = 4. >35: 42,50,64 = 3. >=60: 64 = 1.
    s = compute_stats(frame([28] * 6 + [35, 42, 50, 64]))
    assert s["baseline_mean"] == 28.0 and s["baseline_sd"] == 0.0
    assert s["recent_mean"] == 41.2 and s["recent_sd"] == 14.0
    assert s["mean_change"] == 13.2 and s["sd_change"] == 14.0
    assert (s["consecutive_jumps"], s["long_cycles"], s["skipped_cycles"]) == (4, 3, 1)
    assert s["trend_days_per_cycle"] > 3


def test_last_cycle_without_length_is_ignored():
    df = frame([28, 28, 28, 28])
    df.loc[3, "cycle_length"] = pd.NA
    assert compute_stats(df)["n_cycles"] == 3


def test_period_and_flow():
    # period lengths 4,5,6 -> mean 5.0; flow 2 of 3 light -> 67%
    s = compute_stats(frame([28, 28, 28], period_length=[4, 5, 6], flow=["Light", "Light", "Heavy"]))
    assert s["mean_period_length"] == 5.0
    assert s["flow_share"] == {"Light": 67, "Heavy": 33}


def test_too_few_cycles_is_low_confidence_and_safe():
    s = compute_stats(frame([28, 30]))
    assert s["low_confidence"] and s["trend_days_per_cycle"] is None and s["sd_length"] == pytest.approx(1.4)
    assert compute_stats(frame([28]).iloc[0:0])["n_cycles"] == 0


def test_cycle_series_rolling_sd():
    s = cycle_series(frame([28, 30, 26]))
    assert list(s.columns) == ["cycle_start", "cycle_length", "rolling_sd"]
    assert s["rolling_sd"].iloc[2] == pytest.approx(2.0)  # sd of 28,30,26 = sqrt(8/2)
