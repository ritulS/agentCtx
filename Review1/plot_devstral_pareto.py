"""Devstral Pareto plots (resolve vs tokens / latency) at 15k, 20k, 24k budgets.

Reads from results/ablations/devstral-2-budgeted-{15000,20000,24000}/experiment_results.json
plus results/ablations/devstral-2-inf/experiment_results.json for unbounded baselines.

Outputs under Review1/figures_n100/devstral/:
  pareto_15k_combined.png
  pareto_20k_combined.png
  pareto_24k_combined.png
  pareto_triptych_tokens.png       — 3 budgets side-by-side, tokens only
"""
from __future__ import annotations
from pathlib import Path
import json
import statistics
import collections

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from adjustText import adjust_text

ROOT = Path(__file__).parent.parent
RES  = ROOT / "results" / "ablations"
OUT  = Path(__file__).parent / "figures_n100" / "devstral"
OUT.mkdir(parents=True, exist_ok=True)

PRIM_MAP = {
    "truncation":                              "TR",
    "tool_result_clear":                       "TRC",
    "summarization":                           "SU-full",
    "summarization_partial":                   "SU-partial",
    "structured_summarize":                    "SS",
    "structured_summarize_partial":            "SS-partial",
    "trc_summarize":                           "TRC+SU",
    "trc_structured_summarize":                "TRC+SS",
    "online_trc":                              "OTRC+TR",
    "online_trc_summarize_partial":            "OTRC+SU-partial",
    "online_trc_structured_summarize_partial": "OTRC+SS-partial",
}

RULE_BASED    = {"TR", "TRC"}
LLM_BASED     = {"SU-full", "SU-partial", "SS", "SS-partial"}
STACK_THRESH  = {"TRC+SU", "TRC+SS"}
STACK_ONLINE  = {"OTRC+TR", "OTRC+SU-partial", "OTRC+SS-partial"}

FAMILY = {}
for p in RULE_BASED:   FAMILY[p] = "rule"
for p in LLM_BASED:    FAMILY[p] = "llm"
for p in STACK_THRESH: FAMILY[p] = "stack_thresh"
for p in STACK_ONLINE: FAMILY[p] = "stack_online"
FAMILY["FC@∞"]   = "baseline"
FAMILY["OTRC@∞"] = "baseline"

FAMILY_COLOR = {
    "rule":         "#2563EB",
    "llm":          "#DC2626",
    "stack_thresh": "#7C3AED",
    "stack_online": "#059669",
    "baseline":     "#374151",
}
FAMILY_MARKER = {
    "rule":         "o",
    "llm":          "^",
    "stack_thresh": "s",
    "stack_online": "D",
    "baseline":     "X",
}

PARETO_LABEL = {
    "SU-partial":      "SU-p",
    "SS-partial":      "SS-p",
    "OTRC+TR":         "TRC/St+TR",
    "OTRC+SU-partial": "TRC/St+SU-p",
    "OTRC+SS-partial": "TRC/St+SS-p",
}

DISPLAY_ORDER = [
    "TR", "TRC",
    "SU-full", "SU-partial", "SS", "SS-partial",
    "TRC+SU", "TRC+SS",
    "OTRC+TR", "OTRC+SU-partial", "OTRC+SS-partial",
]


def load_budget(budget: int) -> dict[str, dict]:
    path = RES / f"devstral-2-budgeted-{budget}" / "experiment_results.json"
    with open(path) as f:
        data = json.load(f)
    cells = collections.defaultdict(list)
    for r in data:
        prim = PRIM_MAP.get(r["primitive"])
        if prim is None:
            continue
        cells[prim].append(r)
    return {prim: _agg(recs) for prim, recs in cells.items()}


def load_baselines() -> dict[str, dict]:
    path = RES / "devstral-2-inf" / "experiment_results.json"
    with open(path) as f:
        data = json.load(f)
    out = {}
    for prim_raw, label in [("truncation", "FC@∞"), ("online_trc", "OTRC@∞")]:
        recs = [r for r in data if r["primitive"] == prim_raw]
        if recs:
            out[label] = _agg(recs)
    return out


def _agg(recs: list[dict]) -> dict:
    n = len(recs)
    resolve = sum(1 for r in recs if r["resolved"]) / n * 100
    toks = statistics.mean(r["total_prompt_tokens"] for r in recs if r["total_prompt_tokens"])
    lat  = statistics.mean(r["e2e_latency_s"]      for r in recs if r["e2e_latency_s"])
    return {"resolve": resolve, "tokens": toks, "latency": lat, "n": n}


def _draw_panel(ax, cells: dict[str, dict], baselines: dict[str, dict],
                x_key: str, x_label: str, x_scale: float) -> None:
    plotted = []
    for prim in DISPLAY_ORDER:
        s = cells.get(prim)
        if not s:
            continue
        fam = FAMILY[prim]
        ax.scatter(s[x_key] / x_scale, s["resolve"],
                   marker=FAMILY_MARKER[fam], color=FAMILY_COLOR[fam],
                   s=130, edgecolor="white", linewidth=1.0, zorder=3)
        plotted.append((PARETO_LABEL.get(prim, prim), s[x_key] / x_scale, s["resolve"]))

    for label, s in baselines.items():
        fam = FAMILY[label]
        ax.scatter(s[x_key] / x_scale, s["resolve"],
                   marker=FAMILY_MARKER[fam], color=FAMILY_COLOR[fam],
                   s=170, edgecolor="white", linewidth=1.0, zorder=3)
        plotted.append((label, s[x_key] / x_scale, s["resolve"]))

    x_min, x_max = ax.get_xlim()
    ax.set_xlim(x_min - (x_max - x_min) * 0.12, x_max + (x_max - x_min) * 0.10)
    y_min, y_max = ax.get_ylim()
    ax.set_ylim(y_min - (y_max - y_min) * 0.12, y_max + (y_max - y_min) * 0.12)

    texts = [ax.text(x, y, label, fontsize=15, color="#1F2937", zorder=4)
             for label, x, y in plotted]
    adjust_text(
        texts, ax=ax,
        arrowprops=dict(arrowstyle="-", color="#D1D5DB", lw=0.5, shrinkA=2, shrinkB=6),
        expand_text=(1.75, 1.85),
        expand_points=(2.30, 2.50),
        force_text=(1.3, 1.7),
        force_points=(1.6, 1.9),
        only_move={"points": "xy", "text": "xy"},
        max_move=(100, 100),
    )

    ax.set_xlabel(x_label, fontsize=18)
    ax.tick_params(axis="both", labelsize=15)
    ax.grid(alpha=0.25, linestyle="--", linewidth=0.5)


def _legend_handles():
    return [plt.Line2D([0], [0], marker=FAMILY_MARKER[f], color="w",
                       markerfacecolor=FAMILY_COLOR[f], markersize=14,
                       label=lbl, markeredgecolor="white")
            for f, lbl in [("rule", "Rule-based"),
                           ("llm", "LLM-based"),
                           ("stack_thresh", "Stacked (threshold)"),
                           ("stack_online", "Stacked (per-step)"),
                           ("baseline", "Unbounded")]]


def fig_pareto_combined(budget: int, cells: dict, baselines: dict) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(15.5, 6.0), sharey=True,
                             gridspec_kw={"wspace": 0.16})
    _draw_panel(axes[0], cells, baselines, "tokens",  "Total prompt tokens (K)", 1000.0)
    _draw_panel(axes[1], cells, baselines, "latency", "End-to-end latency (s)",  1.0)

    axes[0].set_ylabel("Resolve rate (%)", fontsize=18)
    axes[1].tick_params(axis="y", labelleft=True, labelsize=15)

    fig.legend(handles=_legend_handles(), loc="upper center",
               bbox_to_anchor=(0.5, 1.03), ncol=5, fontsize=16,
               frameon=False, handletextpad=0.4, columnspacing=1.2)
    fig.suptitle(f"Devstral-Small-2-24B at {budget // 1000}k budget (depth 0.5)",
                 fontsize=18, y=1.10)

    plt.tight_layout(rect=[0, 0, 1, 0.90])
    out = OUT / f"pareto_{budget // 1000}k_combined.png"
    plt.savefig(out, dpi=200, bbox_inches="tight")
    plt.close()
    print(f"wrote {out}")


def fig_pareto_triptych_tokens(budgets: list[int], all_cells: dict, baselines: dict) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(21, 6.0), sharey=True,
                             gridspec_kw={"wspace": 0.14})
    for ax, b in zip(axes, budgets):
        _draw_panel(ax, all_cells[b], baselines, "tokens", "Total prompt tokens (K)", 1000.0)
        ax.set_title(f"{b // 1000}k budget", fontsize=17)

    axes[0].set_ylabel("Resolve rate (%)", fontsize=18)
    for ax in axes[1:]:
        ax.tick_params(axis="y", labelleft=True, labelsize=15)

    fig.legend(handles=_legend_handles(), loc="upper center",
               bbox_to_anchor=(0.5, 1.02), ncol=5, fontsize=16,
               frameon=False, handletextpad=0.4, columnspacing=1.2)
    fig.suptitle("Devstral-Small-2-24B — Pareto across budgets (depth 0.5)",
                 fontsize=18, y=1.08)

    plt.tight_layout(rect=[0, 0, 1, 0.92])
    out = OUT / "pareto_triptych_tokens.png"
    plt.savefig(out, dpi=200, bbox_inches="tight")
    plt.close()
    print(f"wrote {out}")


def main():
    budgets = [15000, 20000, 24000]
    baselines = load_baselines()
    all_cells = {b: load_budget(b) for b in budgets}

    for b in budgets:
        fig_pareto_combined(b, all_cells[b], baselines)
    fig_pareto_triptych_tokens(budgets, all_cells, baselines)


if __name__ == "__main__":
    main()
