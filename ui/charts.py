"""Cycle length chart with the 21-35 day reference band and labelled events."""
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

COLORS = {"skipped": "#c0392b", "long": "#e67e22", "short": "#2980b9", "jump": "#8e44ad"}


def cycle_chart(cycles: list[dict], events: list[dict]):
    """cycles: /cycles records; events: /stats events. Returns a matplotlib Figure."""
    df = pd.DataFrame(cycles).dropna(subset=["cycle_length"])
    df["cycle_start"] = pd.to_datetime(df["cycle_start"])
    fig, ax = plt.subplots(figsize=(9, 3.6))
    ax.axhspan(21, 35, color="#2ecc71", alpha=0.12, label="21-35 days (typical range)")
    ax.plot(df["cycle_start"], df["cycle_length"], marker="o", ms=4, lw=1.5, color="#34495e")
    seen = set()
    for e in events:
        if e["type"] == "jump":
            continue  # keep the chart readable: long/short/skipped only
        d = pd.Timestamp(e["date"])
        ax.scatter([d], [e["length_days"]], s=80, color=COLORS[e["type"]], zorder=3,
                   label=e["type"] if e["type"] not in seen else None)
        seen.add(e["type"])
        ax.annotate(f"{e['length_days']} d", (d, e["length_days"]), textcoords="offset points",
                    xytext=(0, 8), ha="center", fontsize=8)
    ax.set_ylabel("Cycle length (days)")
    ax.set_title("Cycle length over time")
    ax.legend(loc="upper left", fontsize=8, frameon=False)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    fig.autofmt_xdate()
    fig.tight_layout()
    return fig
