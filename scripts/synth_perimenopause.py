"""Labelled-synthetic demo users with a KNOWN pattern (seeded, reproducible).

synth_peri   : stable early on, then cycle length drifts up, variability grows, one skipped cycle.
synth_stable : control user, no trend. Lets us check that the stats do NOT invent a pattern.
Output: samples/demo_synthetic_perimenopause.csv (normalised schema). SYNTHETIC, not real data.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import numpy as np
import pandas as pd
from app.analysis.normalise import normalise

SEED = 42
N_CYCLES = 26


def make_user(rng, user_id, age, peri: bool) -> pd.DataFrame:
    lengths = []
    for i in range(N_CYCLES):
        if peri:
            t = max(0, i - 8) / (N_CYCLES - 9)          # 0 for first 8 cycles, then ramps to 1
            mean, sd = 28 + 8 * t, 1.5 + 5 * t           # lengthening + rising variability
        else:
            mean, sd = 28, 1.5
        lengths.append(int(round(rng.normal(mean, sd))))
    if peri:
        lengths[18] = int(rng.integers(58, 66))           # one skipped cycle (~2 months)
    starts = pd.Timestamp("2023-01-04") + pd.to_timedelta(np.cumsum([0] + lengths[:-1]), unit="D")
    flow = rng.choice(["Light", "Moderate", "Heavy"], size=N_CYCLES, p=[0.25, 0.55, 0.20])
    return pd.DataFrame({"user_id": user_id, "cycle_start": starts, "cycle_length": lengths,
                         "period_length": rng.integers(4, 7, size=N_CYCLES), "flow": flow, "age": age})


if __name__ == "__main__":
    rng = np.random.default_rng(SEED)
    df = pd.concat([make_user(rng, "synth_peri", 47, True), make_user(rng, "synth_stable", 33, False)])
    df = normalise(df)
    out = ROOT / "samples" / "demo_synthetic_perimenopause.csv"
    df.to_csv(out, index=False)
    for uid, g in df.groupby("user_id"):
        cl = g.cycle_length.astype(int)
        print(uid, "first8 mean/sd", round(cl[:8].mean(), 1), round(cl[:8].std(), 1),
              "| last8 mean/sd", round(cl[-8:].mean(), 1), round(cl[-8:].std(), 1), "| max", cl.max())
