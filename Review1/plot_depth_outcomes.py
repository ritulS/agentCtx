"""Per-task outcome heatmaps for the depth ablation (depth-40 and depth-60).

Same layout as fig_l_per_task_heatmap: 30 tasks × 3 primitives (TR, SU, TRC),
each cell split horizontally into run1 / run2. Color: green (resolved) /
orange (submitted-wrong) / red (did-not-submit). Tasks ordered easy → hard
by total resolved across primitives × runs *at this depth*.

Reads results/ablations/depth-{40,60}/experiment_results.json directly.
Saves to Review1/figures/fig_L_depth_{40,60}_heatmap.png.
"""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Patch, Rectangle

ROOT = Path(__file__).parent.parent
OUT  = Path(__file__).parent / "figures"
OUT.mkdir(exist_ok=True)

PRIMITIVES = ["truncation", "summarization", "tool-result-clear"]
PRIM_LABEL = {"truncation": "TR", "summarization": "SU-full", "tool-result-clear": "TRC"}

BUCKET_COLORS = {
    "resolved":        "#3FA34D",
    "submitted_wrong": "#E59500",
    "did_not_submit":  "#C0392B",
}
BUCKET_LABELS = {
    "resolved":        "Resolved",
    "submitted_wrong": "Submitted (wrong)",
    "did_not_submit":  "Did not submit",
}


def failure_mode(r: dict) -> str:
    if r.get("resolved") is True:
        return "resolved"
    if (r.get("exit_status") or "").startswith("LimitsExceeded"):
        return "limits_exceeded"
    if r.get("patch_generated") and r.get("exit_status") == "Submitted":
        return "submitted_unresolved"
    if not r.get("patch_generated"):
        return "silent_crash"
    return "other"


BUCKET_OF_FM = {
    "resolved":             "resolved",
    "submitted_unresolved": "submitted_wrong",
    "silent_crash":         "did_not_submit",
    "limits_exceeded":      "did_not_submit",
    "other":                "did_not_submit",
}


def plot_depth(depth_pct: int):
    src = ROOT / "results" / "ablations" / f"depth-{depth_pct}" / "experiment_results.json"
    rows = json.loads(src.read_text())

    # outcome[task, prim, run_num] -> bucket
    tasks = sorted({r["instance_id"] for r in rows})
    cells = {}                                              # (i_task, j_prim) -> {1:bucket, 2:bucket}
    score = np.zeros(len(tasks))
    for i, t in enumerate(tasks):
        for j, prim in enumerate(PRIMITIVES):
            run_outcomes = {}
            for r in rows:
                if r["instance_id"] != t or r["condition"] != prim: continue
                rn = int(r["run_num"])
                run_outcomes[rn] = BUCKET_OF_FM.get(failure_mode(r), "did_not_submit")
                if r.get("resolved") is True:
                    score[i] += 1
            cells[(i, j)] = run_outcomes

    order = np.argsort(-score)
    tasks_ordered = [tasks[i] for i in order]

    fig, ax = plt.subplots(figsize=(5.5, 12))
    n_rows, n_cols = len(tasks_ordered), len(PRIMITIVES)

    for new_i, old_i in enumerate(order):
        for j in range(n_cols):
            outcomes = cells.get((old_i, j), {})
            for run_num, x_offset in ((1, 0.0), (2, 0.5)):
                bucket = outcomes.get(run_num)
                color  = BUCKET_COLORS[bucket] if bucket else "#FFFFFF"
                ax.add_patch(Rectangle(
                    (j - 0.5 + x_offset, new_i - 0.5), 0.5, 1.0,
                    facecolor=color, edgecolor="white", linewidth=0.4))

    ax.set_xlim(-0.5, n_cols - 0.5)
    ax.set_ylim(n_rows - 0.5, -0.5)
    ax.set_xticks(range(n_cols))
    ax.set_xticklabels([PRIM_LABEL[p] for p in PRIMITIVES], rotation=0, fontsize=10)
    ax.set_yticks(range(n_rows))
    ax.set_yticklabels(tasks_ordered, fontsize=7.5)

    handles = [Patch(facecolor=BUCKET_COLORS[b], label=BUCKET_LABELS[b])
               for b in ["resolved", "submitted_wrong", "did_not_submit"]]
    handles.append(Patch(facecolor="white", edgecolor="#999",
                         label="left = run 1, right = run 2"))
    ax.legend(handles=handles, loc="upper center",
              bbox_to_anchor=(0.5, -0.04), ncol=2, frameon=False, fontsize=9)

    ax.set_title(f"Per-task outcome at depth = 0.{depth_pct}\n"
                 f"(20k budget; {len(rows)} runs; tasks ordered easy → hard)",
                 fontsize=11, fontweight="bold", pad=10)
    ax.set_aspect("auto")

    plt.tight_layout()
    out = OUT / f"fig_L_depth_{depth_pct}_heatmap.png"
    plt.savefig(out, dpi=200, bbox_inches="tight")
    plt.close()

    n_resolved = int(score.sum())
    print(f"depth-{depth_pct}: {n_resolved}/{len(rows)} runs resolved "
          f"({n_resolved/len(rows)*100:.1f}%) -> {out}")


if __name__ == "__main__":
    plot_depth(40)
    plot_depth(60)
