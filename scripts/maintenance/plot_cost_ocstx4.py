#!/usr/bin/env python3
"""Cost per run at Claude Haiku 5.5 list price on the ocst4 pilot tasks, agent
model only: full context vs OCSA vs OCST vs OCSTX (ocst + per-output
pre-extraction), stacked by token class. The single-panel sibling of
plot_cost_ocst4.py (same prices, estimator and segments; see its docstring),
with the ocstx cell added. The selector / extractor calls are costed into the
CSV (column `selector`) but not drawn.

Needs the estimator output of the ocstx cell:
  venv/bin/python scripts/maintenance/estimate_uncached_prompt.py \\
      --cell-a data/r2/swebench/p30s/devstral24b-iso-fc20-dsflash/di__binf__ocstx \\
      --cell-b data/r2/swebench/p30s/devstral24b-iso-fc20/di__binf__fc --label-a OCSTX \\
      --out data/r2/probes/uncached_prompt_estimate_ocstx --no-plot
Usage: venv/bin/python scripts/maintenance/plot_cost_ocstx4.py [--out PNG]
"""
from __future__ import annotations
import argparse, csv, statistics as st, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import plot_cost_ocst4 as base   # noqa: E402

ROOT, P30S, TASKS, PRICE, SEGS = base.ROOT, base.P30S, base.TASKS, base.PRICE, base.SEGS
base.CELLS["OCSTX"] = (P30S / "devstral24b-iso-fc20-dsflash/di__binf__ocstx",
                       ROOT / "data/r2/probes/uncached_prompt_estimate_ocstx/per_run.csv", "a")
CELLS = base.CELLS


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=ROOT / "data/r2/probes/uncached_prompt_estimate_ocstx/cost_per_run_ocstx4.png")
    args = ap.parse_args()
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch
    import numpy as np

    data = {lab: base.run_rows(lab) for lab in CELLS}
    table: dict[str, dict[str, dict[str, float]]] = {}
    for t in TASKS:
        table[t] = {}
        for lab, rows in data.items():
            rs = [v for (ti, _), v in rows.items() if ti == t and "output" in v]
            table[t][lab] = {
                "cache_read": st.mean(PRICE["cache_read"] * v["cache_read"] for v in rs),
                "uncached":   st.mean(PRICE["uncached"] * v["uncached"] for v in rs),
                "output":     st.mean(PRICE["output"] * v["output"] for v in rs),
                "selector":   st.mean(v["selector"] for v in rs),
                "runs": len(rs), "resolved": sum(v["resolved"] for v in rs),
            }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with open(args.out.with_suffix(".csv"), "w", newline="") as f:
        w = csv.writer(f); w.writerow(["instance_id", "condition", "runs", "resolved", *SEGS, "agent_total", "total"])
        for t in TASKS:
            for lab in CELLS:
                c = table[t][lab]
                w.writerow([t, lab, c["runs"], c["resolved"], *[f"{c[s]:.5f}" for s in SEGS],
                            f"{sum(c[s] for s in SEGS[:3]):.5f}", f"{sum(c[s] for s in SEGS):.5f}"])

    agent_segs = SEGS[:3]
    color = {"Full context": "#9A9890", "OCSA": "#E8641B", "OCST": "#2A7F9E", "OCSTX": "#5B9E3A"}
    shade = {"cache_read": 0.30, "uncached": 0.65, "output": 1.0}
    ink, muted = "#1F1F1F", "#6B6B6B"
    fig, ax = plt.subplots(figsize=(8.6, 6.8))
    h, gap = 0.19, 0.02
    ylabels, yticks = [], []
    for ti, t in enumerate(TASKS):
        y0 = ti * 1.0
        yticks.append(y0 + 1.5 * (h + gap)); ylabels.append(base.short(t))
        for ci, lab in enumerate(CELLS):
            y = y0 + ci * (h + gap)
            c = table[t][lab]; left = 0.0
            for seg in agent_segs:
                ax.barh(y, c[seg], h, left=left, color=color[lab], alpha=shade[seg], edgecolor="white", linewidth=0.4)
                left += c[seg]
            ax.text(left, y, f" ${left:.3f} ({c['resolved']}/{c['runs']})", va="center", fontsize=7.5, color=ink)
    ax.set_yticks(yticks); ax.set_yticklabels(ylabels, fontsize=9); ax.invert_yaxis()
    xmax = max(sum(table[t][l][sg] for sg in agent_segs) for t in TASKS for l in CELLS)
    ax.set_xlim(0, xmax * 1.30)
    ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"${v:.2f}"))
    ax.set_title("Agent model only (cache read | uncached input | output)", fontsize=9.5, color=ink, loc="left")
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    ax.spines["left"].set_color("#DDDDDD"); ax.spines["bottom"].set_color("#DDDDDD")
    ax.tick_params(axis="x", colors=muted, labelsize=8); ax.grid(axis="x", color="#EEEEEE", lw=0.8); ax.set_axisbelow(True)
    means = {l: np.mean([sum(table[t][l][sg] for sg in agent_segs) for t in TASKS]) for l in CELLS}
    means_sel = {l: np.mean([table[t][l]["selector"] for t in TASKS]) for l in CELLS}
    ax.set_xlabel("Cost per run (mean over runs; label = resolved / runs)\n"
                  "mean per run: " + "   ".join(f"{l} \\${v:.3f}" for l, v in means.items()) + "   ← lower is better",
                  color=muted, fontsize=8.5)
    cond = [Patch(color=color[l], label=l) for l in CELLS]
    segs_h = [Patch(color="#555555", alpha=shade["cache_read"], label="cache read ($0.01/M)"),
              Patch(color="#555555", alpha=shade["uncached"], label="uncached input ($0.10/M)"),
              Patch(color="#555555", alpha=1.0, label="output ($0.50/M)")]
    fig.legend(handles=cond + segs_h, loc="lower center", bbox_to_anchor=(0.5, 0.0), ncol=4, frameon=False, fontsize=8.5, columnspacing=1.2)
    fc = means["Full context"]
    fig.suptitle(f"Threshold selection + per-output pre-extraction costs {means['OCSTX']/fc:.1f}× full context on the agent model\n"
                 f"(threshold selection alone {means['OCST']/fc:.1f}×, per-step selection {means['OCSA']/fc:.1f}×)",
                 x=0.01, y=0.99, ha="left", va="top", fontsize=10.5, fontweight="bold", color=ink, linespacing=1.3)
    fig.text(0.01, 0.905,
             "SWE-bench Verified, the 4 ocst4 pilot tasks (Full context: 3 runs, OCSA / OCST / OCSTX: 2). Devstral-Small-2-24B priced as if\n"
             "it were Claude Haiku 5.5, list price for prompts ≤ 100k tokens: \\$0.10 / MTok uncached input, \\$0.01 cache read, \\$0.50 output.\n"
             "Cache read vs uncached = prefix-cache estimate (longest common prefix with any earlier prompt of the run).\n"
             "OCSTX = OCST plus every new tool output above 1000 tokens trimmed in place by the DeepSeek extractor.\n"
             "Not drawn: the selector / extractor calls at the same rates, mean per run "
             + ", ".join(f"{l} \\${v:.3f}" for l, v in means_sel.items() if l != "Full context") + ".",
             ha="left", va="top", fontsize=7.6, color=muted, linespacing=1.4)
    fig.subplots_adjust(top=0.745, bottom=0.20, left=0.13, right=0.97)
    fig.savefig(args.out, dpi=160)
    print(f"wrote {args.out} and {args.out.with_suffix('.csv')}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
