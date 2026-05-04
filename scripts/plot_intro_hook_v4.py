"""
Intro hook figures v4 — two panels:

  Fig 1: Per-condition compression-induced task failure rate
          (tasks FC patches but compression never patches)
          with FC-resolved subset overlaid

  Fig 2: Failure rate vs compression event count per condition
          (cascade signal: more events → higher failure rate)
"""

import json
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from collections import defaultdict
from pathlib import Path

RESULTS = Path(__file__).parent.parent / "results/qwen3.5-35B-A3B_15k_Fullrun"
OUT     = Path(__file__).parent.parent / "PaperSections/figures"
OUT.mkdir(parents=True, exist_ok=True)

with open(RESULTS / "experiment_results.json") as f:
    data = json.load(f)

by_task_cond = defaultdict(list)
for r in data:
    by_task_cond[(r["instance_id"], r["condition"])].append(r)

tasks       = list(set(r["instance_id"] for r in data))
fc_patches  = {t for t in tasks if any(r["patch_generated"] for r in by_task_cond[(t, "full-context")])}
fc_resolves = {t for t in tasks if any(r["resolved"]        for r in by_task_cond[(t, "full-context")])}
N_FC = len(fc_patches)   # 84

CONDITIONS = [
    ("tool-result-clear",    "TRC"),
    ("summarization",        "SU"),
    ("truncation",           "TR"),
    ("structured-summarize", "SS"),
]

# ── Fig 1 data ─────────────────────────────────────────────────────────────────
fig1_data = []
for cond, short in CONDITIONS:
    fail_tasks = [t for t in fc_patches
                  if not any(r["patch_generated"] for r in by_task_cond[(t, cond)])]
    resolved_subset = [t for t in fail_tasks if t in fc_resolves]
    fig1_data.append(dict(
        label=short,
        n_fail=len(fail_tasks),
        n_resolved=len(resolved_subset),
        pct_fail=len(fail_tasks) / N_FC * 100,
        pct_resolved=len(resolved_subset) / N_FC * 100,
    ))

# ── Fig 2 data ─────────────────────────────────────────────────────────────────
fig2_data = {}
for cond, short in CONDITIONS:
    runs = [r for r in data if r["condition"] == cond]
    by_ev = defaultdict(list)
    for r in runs:
        by_ev[r["compression_events"]].append(int(r["patch_generated"]))
    xs, ys, ns = [], [], []
    for ev in sorted(by_ev):
        if ev == 0:  # exclude: failures here are not compression-induced
            continue
        arr = by_ev[ev]
        if len(arr) >= 5:
            xs.append(ev)
            ys.append((1 - np.mean(arr)) * 100)
            ns.append(len(arr))
    fig2_data[short] = (xs, ys, ns)

# ══ STYLE ══════════════════════════════════════════════════════════════════════
plt.rcParams.update({
    "font.family": "sans-serif",
    "font.size":   11,
    "axes.spines.top":   False,
    "axes.spines.right": False,
})

COND_COLORS = {
    "TR":  "#4C72B0",
    "SU":  "#DD8452",
    "SS":  "#55A868",
    "TRC": "#C44E52",
}
C_RESOLVE = "#222222"

# ══ Figure 1 ═══════════════════════════════════════════════════════════════════
fig1, ax = plt.subplots(figsize=(6, 3.8))

x = np.arange(len(fig1_data))
bar_w = 0.52

bars = ax.bar(x, [d["pct_fail"] for d in fig1_data], bar_w,
              color=[COND_COLORS[d["label"]] for d in fig1_data],
              alpha=0.85, zorder=3)

# inner dark bar = FC-resolved subset
ax.bar(x, [d["pct_resolved"] for d in fig1_data], bar_w * 0.45,
       color=C_RESOLVE, alpha=0.7, zorder=4, label="FC also resolves")

# count labels on top
for i, d in enumerate(fig1_data):
    ax.text(x[i], d["pct_fail"] + 0.5, f"{d['n_fail']}/{N_FC}",
            ha="center", va="bottom", fontsize=9.5, fontweight="bold",
            color=COND_COLORS[d["label"]])

ax.set_xticks(x)
ax.set_xticklabels([d["label"] for d in fig1_data], fontsize=12)
ax.set_ylabel("Tasks FC patches that compression\nnever patches  (%)", fontsize=10.5)
ax.set_ylim(0, 28)
ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v:.0f}%"))
ax.axhline(0, color="#cccccc", lw=0.8)
ax.set_title("Compression-induced task failure\n(of 84 tasks FC patches)", fontsize=11, pad=8)

from matplotlib.patches import Patch
ax.legend(handles=[Patch(color=C_RESOLVE, alpha=0.7, label="FC also resolves (not just patches)")],
          frameon=False, fontsize=9, loc="upper left")

ax.grid(axis="y", alpha=0.25, zorder=0)
plt.tight_layout()
fig1.savefig(OUT / "fig_failure_rate.png", bbox_inches="tight", dpi=200)
print(f"Saved fig_failure_rate.png")

# ══ Figure 2 ═══════════════════════════════════════════════════════════════════
fig2, ax2 = plt.subplots(figsize=(6, 3.8))

markers = {"TR": "o", "SU": "s", "SS": "^", "TRC": "D"}

offsets = {"TR": 8, "SU": -14, "SS": 8, "TRC": -14}

for short, (xs, ys, ns) in fig2_data.items():
    ax2.plot(xs, ys, color=COND_COLORS[short], marker=markers[short],
             lw=2.0, ms=6, label=short, zorder=3)
    for x, y, n in zip(xs, ys, ns):
        ax2.annotate(f"n={n}", (x, y),
                     textcoords="offset points",
                     xytext=(0, offsets[short]),
                     fontsize=7, color=COND_COLORS[short],
                     ha="center", alpha=0.85)

ax2.set_xlabel("Compression events per run", fontsize=11)
ax2.set_ylabel("Failure rate  (%)", fontsize=11)
ax2.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v:.0f}%"))
ax2.set_ylim(-5, 108)
ax2.set_xticks(range(1, 9))
ax2.set_title("More compression events → higher failure rate", fontsize=11, pad=8)
ax2.legend(frameon=False, fontsize=10, ncol=2, loc="upper left")
ax2.grid(axis="y", alpha=0.25, zorder=0)
ax2.axhline(0,   color="#cccccc", lw=0.8)
ax2.axhline(100, color="#cccccc", lw=0.8, ls="--", alpha=0.6)

plt.tight_layout()
fig2.savefig(OUT / "fig_comp_events.png", bbox_inches="tight", dpi=200)
print(f"Saved fig_comp_events.png")
