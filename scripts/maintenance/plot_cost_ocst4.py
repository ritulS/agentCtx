#!/usr/bin/env python3
"""Cost per run at Claude Haiku 5.5 list price on the ocst4 pilot tasks: full
context vs OCSA vs OCST, stacked by token class.

Token classes per run (agent model, Devstral served locally; priced AS IF it were
Claude Haiku 5.5 at list price, prompts <= 100k tokens, 2026-11-12:
cache read $0.01 / MTok, uncached input $0.10 / MTok, output $0.50 / MTok):
  cache read      prompt tokens served from the prefix cache (estimate from
                  scripts/maintenance/estimate_uncached_prompt.py: longest common
                  message prefix with any earlier prompt of the run, 16-token blocks)
  uncached input  the rest of the prompt tokens (same estimate)
  output          sum of step_completion_tokens of the run (experiment_results.json;
                  total_completion_tokens also counts the selector's completions)
  selector        the OCSA / OCST selector's own calls (DeepSeek via OpenRouter),
                  priced at the same Haiku 5.5 rates from summary_attempts.jsonl's
                  usage (cache_read_input_tokens / uncached_input_tokens /
                  completion_tokens, every attempt including rejected ones)
Mean of the runs per task (FC 3, OCSA 2, OCST 2).

Usage: venv/bin/python scripts/maintenance/plot_cost_ocst4.py [--out PNG]
"""
from __future__ import annotations
import argparse, csv, json, statistics as st, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
P30S = ROOT / "data/r2/swebench/p30s"
CELLS = {  # label -> (cell dir, estimator per_run.csv, cell letter in that csv)
    "Full context": (P30S / "devstral24b-iso-fc20/di__binf__fc", ROOT / "data/r2/probes/uncached_prompt_estimate/per_run.csv", "b"),
    "OCSA":         (P30S / "devstral24b-iso-fc20-dsflash/di__binf__ocsa", ROOT / "data/r2/probes/uncached_prompt_estimate/per_run.csv", "a"),
    "OCST":         (P30S / "devstral24b-iso-fc20-dsflash/di__binf__ocst", ROOT / "data/r2/probes/uncached_prompt_estimate_ocst/per_run.csv", "a"),
}
TASKS = ["scikit-learn__scikit-learn-10297", "django__django-15278", "sympy__sympy-14531", "sympy__sympy-12419"]
PRICE = {"cache_read": 0.01 / 1e6, "uncached": 0.10 / 1e6, "output": 0.50 / 1e6}
SEGS = ["cache_read", "uncached", "output", "selector"]


def run_rows(label: str) -> dict[tuple[str, int], dict]:
    cell, est, letter = CELLS[label]
    rows: dict[tuple[str, int], dict] = {}
    for r in csv.DictReader(open(est)):
        if r["cell"] == letter and r["instance_id"] in TASKS:
            p, u = float(r["prompt_tokens"]), float(r["uncached_any"])
            rows[(r["instance_id"], int(r["run"]))] = {"cache_read": p - u, "uncached": u}
    for x in json.load(open(cell / "experiment_results.json")):
        k = (x.get("instance_id"), int(x.get("run_num") or 0))
        if k in rows:
            # the agent's own output: total_completion_tokens also counts the
            # selector's completions in the OCSA / OCST cells
            rows[k]["output"] = float(sum(x.get("step_completion_tokens") or []) or x.get("total_completion_tokens") or 0)
            rows[k]["resolved"] = bool(x.get("resolved"))
    for k, v in rows.items():
        v["selector"] = 0.0
        for sa in cell.glob(f"{k[0]}/*/run_{k[1]}/summary_attempts.jsonl"):
            for line in open(sa):
                u = (json.loads(line).get("usage") or {})
                v["selector"] += (PRICE["cache_read"] * (u.get("cache_read_input_tokens") or 0)
                                  + PRICE["uncached"] * (u.get("uncached_input_tokens") or u.get("prompt_tokens") or 0)
                                  + PRICE["output"] * (u.get("completion_tokens") or 0))
    return rows


def short(t: str) -> str:
    repo, num = t.split("__")[1].rsplit("-", 1)
    return f"{repo.replace('scikit-learn', 'sklearn')}-{num}"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=ROOT / "data/r2/probes/uncached_prompt_estimate_ocst/cost_per_run_ocst4.png")
    args = ap.parse_args()
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    data = {lab: run_rows(lab) for lab in CELLS}
    # per task, per cell: mean cost per segment ($)
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
    with open(args.out.with_suffix(".csv"), "w", newline="") as f:
        w = csv.writer(f); w.writerow(["instance_id", "condition", "runs", "resolved", *SEGS, "total"])
        for t in TASKS:
            for lab in CELLS:
                c = table[t][lab]
                w.writerow([t, lab, c["runs"], c["resolved"], *[f"{c[s]:.5f}" for s in SEGS], f"{sum(c[s] for s in SEGS):.5f}"])

    base = {"Full context": "#9A9890", "OCSA": "#E8641B", "OCST": "#2A7F9E"}
    shade = {"cache_read": 0.30, "uncached": 0.65, "output": 1.0, "selector": 1.0}   # alpha per segment
    ink, muted = "#1F1F1F", "#6B6B6B"
    from matplotlib.patches import Patch
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 5.8), gridspec_kw={"width_ratios": [1, 1], "wspace": 0.30})
    panels = [("Agent model only (cache read | uncached input | output)", SEGS[:3]),
              ("Agent model + selector calls", SEGS)]
    h, gap = 0.24, 0.02
    for ax, (ptitle, segs) in zip(axes, panels):
        ylabels, yticks = [], []
        for ti, t in enumerate(TASKS):
            y0 = ti * 1.0
            yticks.append(y0 + h + gap); ylabels.append(short(t))
            for ci, lab in enumerate(CELLS):
                y = y0 + ci * (h + gap)
                c = table[t][lab]; left = 0.0
                for seg in segs:
                    kw = dict(color=base[lab], alpha=shade[seg], edgecolor="white", linewidth=0.4)
                    if seg == "selector":
                        kw.update(color="white", edgecolor=base[lab], hatch="////", linewidth=0.8, alpha=1.0)
                    ax.barh(y, c[seg], h, left=left, **kw)
                    left += c[seg]
                ax.text(left, y, f" ${left:.3f} ({c['resolved']}/{c['runs']})", va="center", fontsize=7.5, color=ink)
        ax.set_yticks(yticks); ax.set_yticklabels(ylabels, fontsize=9); ax.invert_yaxis()
        xmax = max(sum(table[t][l][sg] for sg in segs) for t in TASKS for l in CELLS)
        ax.set_xlim(0, xmax * 1.30)
        ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"${v:.2f}"))
        ax.set_title(ptitle, fontsize=9.5, color=ink, loc="left")
        for sp in ("top", "right"):
            ax.spines[sp].set_visible(False)
        ax.spines["left"].set_color("#DDDDDD"); ax.spines["bottom"].set_color("#DDDDDD")
        ax.tick_params(axis="x", colors=muted, labelsize=8); ax.grid(axis="x", color="#EEEEEE", lw=0.8); ax.set_axisbelow(True)
        means = {l: np.mean([sum(table[t][l][sg] for sg in segs) for t in TASKS]) for l in CELLS}
        ax.set_xlabel("Cost per run (mean over runs; label = resolved / runs)\n"
                      "mean per run: " + "   ".join(f"{l} ${v:.3f}" for l, v in means.items()) + ("   ← lower is better" if ax is axes[0] else ""),
                      color=muted, fontsize=8.5)
    cond = [Patch(color=base[l], label=l) for l in CELLS]
    segs_h = [Patch(color="#555555", alpha=shade["cache_read"], label="cache read ($0.01/M)"),
              Patch(color="#555555", alpha=shade["uncached"], label="uncached input ($0.10/M)"),
              Patch(color="#555555", alpha=1.0, label="output ($0.50/M)"),
              Patch(facecolor="white", edgecolor="#555555", hatch="////", label="selector calls (same rates)")]
    fig.legend(handles=cond + segs_h, loc="lower center", bbox_to_anchor=(0.5, 0.0), ncol=7, frameon=False, fontsize=8.5, columnspacing=1.2)
    means_all = {l: np.mean([sum(table[t][l][sg] for sg in SEGS) for t in TASKS]) for l in CELLS}
    means_agent = {l: np.mean([sum(table[t][l][sg] for sg in SEGS[:3]) for t in TASKS]) for l in CELLS}
    fc = means_agent["Full context"]
    fig.suptitle(f"Threshold-fired selection costs {means_agent['OCST']/fc:.1f}× full context on the agent model "
                 f"({means_all['OCST']/fc:.1f}× with the selector); per-step selection {means_agent['OCSA']/fc:.1f}× ({means_all['OCSA']/fc:.0f}×)",
                 x=0.01, y=0.985, ha="left", fontsize=11.5, fontweight="bold", color=ink)
    fig.text(0.01, 0.93, "SWE-bench Verified, the 4 ocst4 pilot tasks (Full context: 3 runs, OCSA: 2, OCST: 2). Devstral-Small-2-24B priced as if it were Claude Haiku 5.5, list price for prompts ≤ 100k tokens:\n"
             "$0.10 / MTok uncached input, $0.01 cache read, $0.50 output. Cache read vs uncached = prefix-cache estimate (longest common prefix with any earlier prompt of the run).\n"
             "Selector = the DeepSeek V4.1 Flash selector's own calls priced at the same rates (its OpenRouter cache_read / uncached / completion usage, every attempt).",
             ha="left", va="top", fontsize=8, color=muted, linespacing=1.4)
    fig.subplots_adjust(top=0.78, bottom=0.21, left=0.09, right=0.97)
    fig.savefig(args.out, dpi=160)
    print(f"wrote {args.out} and {args.out.with_suffix('.csv')}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
