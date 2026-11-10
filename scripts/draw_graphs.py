"""Draw the agent graphs as PNGs for slides: docs/img/graph_minimal.png and graph_full.png."""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Patch

OUT = Path(__file__).resolve().parent.parent / "docs" / "img"
OUT.mkdir(parents=True, exist_ok=True)
C = {"code": "#DCE6F2", "code_e": "#3B6EA5", "llm": "#FDE3C4", "llm_e": "#D9822B",
     "data": "#D5EDE6", "data_e": "#2E8B72", "io": "#EEEEEE", "io_e": "#777777", "ink": "#222222"}


def box(ax, x, y, text, kind, sub="", w=1.7, h=0.8, dashed=False):
    p = FancyBboxPatch((x - w / 2, y - h / 2), w, h, boxstyle="round,pad=0.02,rounding_size=0.12",
                       fc=C[kind], ec=C[kind + "_e"], lw=2, ls="--" if dashed else "-", zorder=3)
    ax.add_patch(p)
    ax.text(x, y + 0.04, text, ha="center", va="center", fontsize=13, fontweight="bold", color=C["ink"], zorder=4)
    if sub:
        ax.text(x, y - h / 2 - 0.12, sub, ha="center", va="top", fontsize=9, color="#444", zorder=4, linespacing=1.25)


def arrow(ax, a, b, rad=0.0, color="#444", label=None, lpos=(0, 0), ls="-"):
    ax.add_patch(FancyArrowPatch(a, b, arrowstyle="-|>", mutation_scale=16, lw=1.8, color=color,
                                 connectionstyle=f"arc3,rad={rad}", linestyle=ls, zorder=2))
    if label:
        mx, my = (a[0] + b[0]) / 2 + lpos[0], (a[1] + b[1]) / 2 + lpos[1]
        ax.text(mx, my, label, ha="center", va="center", fontsize=9, color=color, style="italic",
                bbox=dict(fc="white", ec="none", pad=1.5), zorder=5)


def canvas(w, h, title, subtitle):
    fig, ax = plt.subplots(figsize=(w, h))
    ax.set_xlim(0, w); ax.set_ylim(0, h); ax.axis("off")
    ax.text(0.4, h - 0.45, title, fontsize=20, fontweight="bold", color=C["ink"], va="center")
    ax.text(0.4, h - 0.95, subtitle, fontsize=11, color="#555", va="center")
    return fig, ax


def legend(ax, x, y):
    ax.legend(handles=[Patch(fc=C["code"], ec=C["code_e"], lw=2, label="Plain code (deterministic)"),
                       Patch(fc=C["llm"], ec=C["llm_e"], lw=2, label="LLM (only place text is written)"),
                       Patch(fc=C["data"], ec=C["data_e"], lw=2, label="Data / knowledge store"),
                       Patch(fc=C["io"], ec=C["io_e"], lw=2, label="Input / output")],
              loc="lower left", bbox_to_anchor=(x, y), ncol=4, frameon=False, fontsize=10)


def route(ax, pts, color="#444", ls="-", label=None, lxy=None):
    """Polyline with an arrowhead on the last segment (explicit routing, no curves)."""
    for a, b in zip(pts[:-2], pts[1:-1]):
        ax.plot([a[0], b[0]], [a[1], b[1]], color=color, lw=1.8, ls=ls, zorder=2, solid_capstyle="round")
    ax.add_patch(FancyArrowPatch(pts[-2], pts[-1], arrowstyle="-|>", mutation_scale=16, lw=1.8, color=color,
                                 linestyle=ls, zorder=2, shrinkA=0, shrinkB=0))
    if label:
        ax.text(*lxy, label, ha="center", va="center", fontsize=9.5, color=color, style="italic",
                bbox=dict(fc="white", ec="none", pad=1.5), zorder=5)


def minimal():
    fig, ax = canvas(16, 5.2, "Agent graph: core (MVP)", "Five steps and one validation loop. The LLM never sees raw data and never does arithmetic.")
    y = 2.6
    box(ax, 1.0, y, "Upload", "io", "CSV / JSON\nvia Streamlit", w=1.4)
    xs = [3.1, 5.4, 7.7, 10.0, 12.3]
    names = [("Fetch", "code", "calls FastAPI\n/stats"), ("Analyse", "code", "flag rules\non the stats"),
             ("Retrieve", "data", "RAG: reference ranges,\ninstructions, advice"), ("Write", "llm", "drafts the report from\nstats + retrieved text"),
             ("Check", "code", "numbers in the report\nmatch the stats?")]
    for x, (n, k, sub) in zip(xs, names):
        box(ax, x, y, n, k, sub, w=1.65)
    box(ax, 15.0, y, "Report", "io", "on screen + email", w=1.5)
    arrow(ax, (1.7, y), (xs[0] - 0.83, y))
    for a, b in zip(xs, xs[1:]):
        arrow(ax, (a + 0.83, y), (b - 0.83, y))
    arrow(ax, (xs[4] + 0.83, y), (15.0 - 0.75, y), color="#2E8B72")
    ax.text(13.8, y + 0.3, "all match", ha="center", fontsize=9.5, color="#2E8B72", style="italic")
    route(ax, [(xs[4], y + 0.42), (xs[4], y + 1.0), (xs[3], y + 1.0), (xs[3], y + 0.42)], color="#C0392B",
          label="mismatch: back to Write (max 2 retries)", lxy=((xs[3] + xs[4]) / 2, y + 1.28))
    legend(ax, 0.3, 0.05)
    fig.savefig(OUT / "graph_minimal.png", dpi=200, bbox_inches="tight", facecolor="white")


def full():
    fig, ax = canvas(18.4, 7.8, "Agent graph: extended design", "Adds case triage, dated events, charts, symptoms and a guardrail. Still one LLM step.")
    y = 3.9
    X = dict(up=0.9, fetch=2.8, analyse=4.75, triage=6.7, retr=9.0, write=11.3, check=13.1, guard=15.4, rep=17.3)
    box(ax, X["up"], y, "Upload", "io", "CSV / JSON\n+ optional age", w=1.3)
    box(ax, X["fetch"], y, "Fetch", "code", "FastAPI: /stats\n+ dated events\n+ /symptoms", w=1.55)
    box(ax, X["analyse"], y, "Analyse", "code", "flag rules +\nred-flag check", w=1.55)
    box(ax, X["triage"], y, "Triage", "code", "case: young / typical /\nstable / no period 12m\n/ low data", w=1.55)
    box(ax, X["retr"], y + 1.05, "Retrieve", "data", "case-filtered RAG:\nreference, advice", w=1.7)
    box(ax, X["retr"], y - 1.4, "Chart", "code", "cycle length + events,\nvariability, symptoms", w=1.7)
    box(ax, X["write"], y, "Write", "llm", "template per case,\nonly facts from the\nstats, events, chunks", w=1.55)
    box(ax, X["check"], y, "Check", "code", "numbers and\ndates match?", w=1.4)
    box(ax, X["guard"], y, "Guardrail", "code", "disclaimer, no diagnosis\nor doses, advice cited?", w=1.5)
    box(ax, X["rep"], y, "Report", "io", "text + charts\nUI / email", w=1.2)

    arrow(ax, (X["up"] + 0.65, y), (X["fetch"] - 0.78, y))
    arrow(ax, (X["fetch"] + 0.78, y), (X["analyse"] - 0.78, y))
    arrow(ax, (X["analyse"] + 0.78, y), (X["triage"] - 0.78, y))
    route(ax, [(X["triage"] + 0.78, y + 0.15), (X["retr"] - 0.86, y + 1.05)])
    route(ax, [(X["triage"] + 0.78, y - 0.15), (X["retr"] - 0.86, y - 1.4)])
    ax.text(7.3, y + 0.95, "in parallel", ha="center", fontsize=9.5, color="#444", style="italic")
    route(ax, [(X["retr"] + 0.86, y + 1.05), (X["write"] - 0.78, y + 0.18)])
    route(ax, [(X["retr"] + 0.86, y - 1.4), (X["write"] - 0.78, y - 0.18)])
    # low data: skip retrieval/chart
    route(ax, [(X["triage"], y + 0.42), (X["triage"], y + 2.2), (X["write"] - 0.5, y + 2.2), (X["write"] - 0.5, y + 0.42)],
          color="#888", ls="--", label="low data: short template, skip advice", lxy=(8.9, y + 2.45))
    arrow(ax, (X["write"] + 0.78, y), (X["check"] - 0.72, y))
    arrow(ax, (X["check"] + 0.72, y), (X["guard"] - 0.76, y), color="#2E8B72")
    arrow(ax, (X["guard"] + 0.76, y), (X["rep"] - 0.62, y), color="#2E8B72")
    ax.text(14.25, y + 0.22, "ok", fontsize=9.5, color="#2E8B72", style="italic", ha="center")
    ax.text(16.35, y + 0.22, "ok", fontsize=9.5, color="#2E8B72", style="italic", ha="center")
    # retries (nested, no crossings)
    route(ax, [(X["check"], y + 0.42), (X["check"], y + 0.95), (X["write"] + 0.5, y + 0.95), (X["write"] + 0.5, y + 0.42)], color="#C0392B")
    route(ax, [(X["guard"], y + 0.42), (X["guard"], y + 1.5), (X["write"] + 0.2, y + 1.5), (X["write"] + 0.2, y + 0.42)],
          color="#C0392B", label="fail: back to Write (max 2 retries)", lxy=(13.6, y + 1.78))
    ax.text(X["rep"], y - 1.9, "Only Write uses an LLM.\nEverything that decides,\nmeasures or verifies is\nplain code.", ha="center", fontsize=10, color="#444", style="italic")
    legend(ax, 0.3, 0.05)
    fig.savefig(OUT / "graph_full.png", dpi=200, bbox_inches="tight", facecolor="white")


if __name__ == "__main__":
    minimal(); full(); print("wrote", sorted(p.name for p in OUT.glob("*.png")))
