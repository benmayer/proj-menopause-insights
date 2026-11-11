"""Deterministic cycle statistics. The ONLY place numbers are computed.

The agent's Write node may only quote values from this output; the Check node verifies them.
Input: normalised frame for ONE user (see normalise.py). Output: plain dict (JSON-friendly).
Unavailable values are None, never guessed.
"""
import numpy as np
import pandas as pd

# Markers used in the Flags section (sources to be cited in rag_docs, verify before relying on them).
SHORT_DAYS = 21          # cycle shorter than this
LONG_DAYS = 35           # cycle longer than this
SKIPPED_DAYS = 60        # very long gap, possible skipped cycle(s)
JUMP_DAYS = 7            # difference between consecutive cycles
RECENT_WINDOW = 6        # cycles in the "recent" window
MIN_BASELINE = 3         # cycles needed before the recent window for a baseline
MIN_CYCLES = 6           # fewer than this: stats are flagged as low-confidence


def _r(x, nd=1):
    return None if x is None or pd.isna(x) else round(float(x), nd)


def _sd(a):
    return float(np.std(a, ddof=1)) if len(a) >= 2 else None


MAX_EVENTS = 15          # most recent events kept in the output


def cycle_events(df: pd.DataFrame) -> list[dict]:
    """Dated flagged cycles, oldest first. `date` = start of the cycle, `length_days` = its length.

    type: skipped (>=60), long (>35), short (<21), jump (>=7 days different from the previous cycle).
    first_time: no earlier cycle of the same type. A cycle can carry several events (e.g. long + jump).
    """
    d = df.dropna(subset=["cycle_length"]).sort_values("cycle_start")
    seen, events, prev = set(), [], None
    for start, length in zip(d["cycle_start"], d["cycle_length"].astype(float)):
        types = []
        if length >= SKIPPED_DAYS:
            types.append("skipped")
        elif length > LONG_DAYS:
            types.append("long")
        elif length < SHORT_DAYS:
            types.append("short")
        if prev is not None and abs(length - prev) >= JUMP_DAYS:
            types.append("jump")
        for t in types:
            events.append({"type": t, "date": str(start.date()), "length_days": int(length),
                           "first_time": t not in seen})
            seen.add(t)
        prev = length
    return events[-MAX_EVENTS:]


def cycle_series(df: pd.DataFrame) -> pd.DataFrame:
    """Cycle start, length and rolling SD (for the chart). Drops cycles without a length."""
    d = df.dropna(subset=["cycle_length"]).sort_values("cycle_start").copy()
    d["cycle_length"] = d["cycle_length"].astype(float)
    d["rolling_sd"] = d["cycle_length"].rolling(RECENT_WINDOW, min_periods=3).std()
    return d[["cycle_start", "cycle_length", "rolling_sd"]].reset_index(drop=True)


def compute_stats(df: pd.DataFrame) -> dict:
    d = df.sort_values("cycle_start")
    L = d["cycle_length"].dropna().astype(float).to_numpy()
    n = len(L)
    out = {
        "n_cycles": n,
        "first_cycle": str(d["cycle_start"].min().date()) if len(d) else None,
        "last_cycle": str(d["cycle_start"].max().date()) if len(d) else None,
        "low_confidence": n < MIN_CYCLES,
        "age": _r(d["age"].dropna().iloc[-1], 0) if d["age"].notna().any() else None,
    }
    if n == 0:
        return out

    out |= {"mean_length": _r(L.mean()), "median_length": _r(np.median(L)), "sd_length": _r(_sd(L)),
            "min_length": _r(L.min(), 0), "max_length": _r(L.max(), 0)}

    # Trend: least-squares slope of length against cycle number.
    slope = float(np.polyfit(np.arange(n), L, 1)[0]) if n >= 3 else None
    out["trend_days_per_cycle"] = _r(slope, 2)
    out["trend_total_change_days"] = _r(slope * (n - 1)) if slope is not None else None

    # Recent window vs earlier baseline.
    recent, base = L[-RECENT_WINDOW:], L[:-RECENT_WINDOW]
    if len(base) >= MIN_BASELINE:
        out |= {"baseline_mean": _r(base.mean()), "baseline_sd": _r(_sd(base)),
                "recent_mean": _r(recent.mean()), "recent_sd": _r(_sd(recent)),
                "mean_change": _r(recent.mean() - base.mean()), "sd_change": _r(_sd(recent) - _sd(base))}
    else:
        out |= {k: None for k in ("baseline_mean", "baseline_sd", "recent_mean", "recent_sd",
                                  "mean_change", "sd_change")}

    # Flag counts.
    jumps = np.abs(np.diff(L))
    out |= {"short_cycles": int((L < SHORT_DAYS).sum()), "long_cycles": int((L > LONG_DAYS).sum()),
            "skipped_cycles": int((L >= SKIPPED_DAYS).sum()),
            "consecutive_jumps": int((jumps >= JUMP_DAYS).sum()) if len(jumps) else 0}

    out["events"] = cycle_events(d)

    # Period length and flow, when present.
    pl = pd.to_numeric(d["period_length"], errors="coerce").dropna()
    out["mean_period_length"] = _r(pl.mean()) if len(pl) else None
    fl = d["flow"].dropna()
    out["flow_share"] = ({k: _r(v * 100, 0) for k, v in fl.value_counts(normalize=True).items()}
                         if len(fl) else None)
    return out
