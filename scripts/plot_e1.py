"""
E1 Experiment — Publication figures (redesigned for paper first page).

  fig1_paradox.png       — Scatter: tokens saved vs resolve rate (the hook)
  fig2_aggregate_gap.png — 1×2 bars: aggregate resolve rate + tool calls
  fig3_smoking_gun.png   — Resolve rate by compression event count (clean bars)

Run from repo root:
    python3 scripts/plot_e1.py
"""

import json
import math
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

# ── Paths ───────────────────────────────────────────────────────────────────────
ROOT    = Path(__file__).parent.parent
DATA    = ROOT / "results" / "experiment_results.json"
OUT_DIR = ROOT / "results" / "figures"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ── Style ───────────────────────────────────────────────────────────────────────
COLOR_BASE = "#555555"   # grey  — baseline / no compression
COLOR_T    = "#2166ac"   # blue  — truncation
COLOR_S    = "#d6604d"   # red   — summarization

plt.rcParams.update({
    "font.family":       "sans-serif",
    "font.size":         11,
    "axes.spines.top":   False,
    "axes.spines.right": False,
    "axes.grid":         False,
    "figure.dpi":        150,
})

BUDGETS_COMPRESSED = [0.90, 0.80, 0.70, 0.60]

# ── Statistics helpers ──────────────────────────────────────────────────────────

def wilson_ci(k, n, z=1.96):
    if n == 0:
        return 0.0, 0.0
    p = k / n
    center = (p + z**2 / (2*n)) / (1 + z**2 / n)
    margin = z * math.sqrt(p*(1-p)/n + z**2/(4*n**2)) / (1 + z**2/n)
    return max(0.0, center - margin), min(1.0, center + margin)


def mean_ci(values, z=1.96):
    n = len(values)
    if n == 0:
        return 0.0, 0.0, 0.0
    mu = sum(values) / n
    if n == 1:
        return mu, mu, mu
    std = math.sqrt(sum((x - mu)**2 for x in values) / (n - 1))
    margin = z * std / math.sqrt(n)
    return mu, mu - margin, mu + margin

# ── Data loading ────────────────────────────────────────────────────────────────

def load_data():
    return json.loads(DATA.read_text())


def build_cells(results):
    cells = defaultdict(lambda: {"n": 0, "resolved": 0, "patches": 0,
                                  "calls": [], "tok_saved": []})
    for r in results:
        pct  = r.get("budget_pct", 1.0)
        prim = r.get("primitive", "truncation")
        c = cells[(pct, prim)]
        c["n"]        += 1
        c["resolved"] += 1 if r.get("resolved") else 0
        c["patches"]  += 1 if r.get("patch_generated") else 0
        c["calls"].append(r.get("n_calls", 0))
        c["tok_saved"].append(r.get("total_tokens_saved", 0))
    return cells


def build_event_buckets(results):
    buckets = defaultdict(lambda: {"n": 0, "resolved": 0, "calls": []})
    for r in results:
        if r.get("budget_pct", 1.0) == 1.0:
            continue
        ev   = min(r.get("compression_events", 0), 2)
        prim = r.get("primitive", "truncation")
        b = buckets[(ev, prim)]
        b["n"]        += 1
        b["resolved"] += 1 if r.get("resolved") else 0
        b["calls"].append(r.get("n_calls", 0))
    return buckets

# ── Figure 1 — Token Savings Paradox (the hook) ─────────────────────────────────

def fig1_paradox(cells):
    fig, ax = plt.subplots(figsize=(6.5, 5.2))

    for prim, color, label, marker in [
        ("truncation",    COLOR_T, "Truncation",    "o"),
        ("summarization", COLOR_S, "Summarization", "s"),
    ]:
        xs, ys = [], []
        for pct in BUDGETS_COMPRESSED:
            c = cells[(pct, prim)]
            avg_tok = sum(c["tok_saved"]) / len(c["tok_saved"]) / 1000
            res_rate = c["resolved"] / c["n"] * 100
            xs.append(avg_tok)
            ys.append(res_rate)

        ax.plot(xs, ys, color=color, marker=marker, linewidth=2,
                markersize=9, label=label, zorder=4)

        # Label each point with budget %
        budgets_pct = [90, 80, 70, 60]
        for i, (xi, yi, bp) in enumerate(zip(xs, ys, budgets_pct)):
            # Offset labels to avoid overlap
            if prim == "truncation":
                dx, dy = -0.3, 0.6
                ha = "right"
            else:
                dx, dy = 0.3, -0.9
                ha = "left"
            ax.annotate(f"{bp}%", (xi, yi),
                        xytext=(xi + dx, yi + dy),
                        fontsize=8.5, color=color, ha=ha,
                        arrowprops=dict(arrowstyle="-", color=color,
                                        lw=0.6, shrinkA=5, shrinkB=2))

    # Direction arrow along x-axis bottom
    ax.annotate("", xy=(15, 0.6), xytext=(4.5, 0.6),
                arrowprops=dict(arrowstyle="-|>", color="#aaa", lw=1.2))
    ax.text(9.75, 0.0, "budget tightens → compression fires more → more tokens saved",
            ha="center", fontsize=8, color="#999", fontstyle="italic")

    ax.set_xlabel("Avg tokens saved per run  (K tokens)", labelpad=8)
    ax.set_ylabel("Resolve rate  (%)", labelpad=8)
    ax.set_xlim(0, 17)
    ax.set_ylim(-0.5, 18)
    ax.set_title("Saving More Context ≠ Solving More Tasks",
                 fontweight="bold", pad=12)

    leg = ax.legend(fontsize=10, frameon=False, loc="upper right")

    fig.tight_layout()
    out = OUT_DIR / "fig1_paradox.png"
    fig.savefig(out, bbox_inches="tight", dpi=200)
    plt.close(fig)
    print(f"Saved {out}")

# ── Figure 2 — Aggregate Performance Gap (1×2 bars) ────────────────────────────

def fig2_aggregate_gap(cells, results):
    # Aggregate compressed runs per primitive
    def agg(prim):
        all_n = all_k = all_patches = 0
        all_calls = []
        for pct in BUDGETS_COMPRESSED:
            c = cells[(pct, prim)]
            all_n       += c["n"]
            all_k       += c["resolved"]
            all_patches += c["patches"]
            all_calls   += c["calls"]
        return all_n, all_k, all_patches, all_calls

    base = cells[(1.0, "truncation")]
    t_n, t_k, t_patches, t_calls = agg("truncation")
    s_n, s_k, s_patches, s_calls = agg("summarization")

    # Resolve rates
    base_res  = base["resolved"] / base["n"] * 100
    t_res     = t_k / t_n * 100
    s_res     = s_k / s_n * 100
    base_lo, base_hi = wilson_ci(base["resolved"], base["n"])
    t_lo, t_hi       = wilson_ci(t_k, t_n)
    s_lo, s_hi       = wilson_ci(s_k, s_n)

    # Tool calls
    base_calls_mu, base_calls_lo, base_calls_hi = mean_ci(base["calls"])
    t_calls_mu, t_calls_lo, t_calls_hi = mean_ci(t_calls)
    s_calls_mu, s_calls_lo, s_calls_hi = mean_ci(s_calls)

    fig, axes = plt.subplots(1, 2, figsize=(10, 5))
    fig.subplots_adjust(wspace=0.38)

    x      = np.array([0, 1, 2])
    colors = [COLOR_BASE, COLOR_T, COLOR_S]
    labels = ["No compression\n(baseline)", "Truncation\n(compressed)", "Summarization\n(compressed)"]

    # ── Left: resolve rate ──────────────────────────────────────────────────────
    ax = axes[0]
    res_vals = [base_res, t_res, s_res]
    res_elo  = [base_res - base_lo*100, t_res - t_lo*100, s_res - s_lo*100]
    res_ehi  = [base_hi*100 - base_res, t_hi*100 - t_res, s_hi*100 - s_res]

    bars = ax.bar(x, res_vals, color=colors, alpha=0.85, width=0.55,
                  yerr=[res_elo, res_ehi], capsize=5,
                  error_kw={"linewidth": 1.5, "ecolor": "#444"}, zorder=3)

    # Baseline reference line
    ax.axhline(base_res, color=COLOR_BASE, linewidth=1, linestyle="--",
               alpha=0.5, zorder=2)

    # Value labels above bars
    for bar, val, lo, hi in zip(bars, res_vals, res_elo, res_ehi):
        ax.text(bar.get_x() + bar.get_width()/2, val + hi + 0.5,
                f"{val:.1f}%", ha="center", va="bottom",
                fontsize=10, fontweight="bold",
                color=bar.get_facecolor())

    # Annotate T vs S gap
    ax.annotate("",
                xy=(2, s_res), xytext=(2, t_res),
                arrowprops=dict(arrowstyle="<->", color="#333", lw=1.2))
    ax.text(2.32, (t_res + s_res)/2,
            f"−{(t_res - s_res)/t_res*100:.0f}%\nrelative",
            va="center", fontsize=8.5, color="#333")

    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=9.5)
    ax.set_ylabel("Resolve rate  (%)")
    ax.set_ylim(0, 20)
    ax.set_title("(A)  Task resolve rate", fontweight="bold", loc="left")

    # ── Right: tool calls ───────────────────────────────────────────────────────
    ax = axes[1]
    call_vals = [base_calls_mu, t_calls_mu, s_calls_mu]
    call_elo  = [base_calls_mu - base_calls_lo,
                 t_calls_mu - t_calls_lo,
                 s_calls_mu - s_calls_lo]
    call_ehi  = [base_calls_hi - base_calls_mu,
                 t_calls_hi - t_calls_mu,
                 s_calls_hi - s_calls_mu]

    bars2 = ax.bar(x, call_vals, color=colors, alpha=0.85, width=0.55,
                   yerr=[call_elo, call_ehi], capsize=5,
                   error_kw={"linewidth": 1.5, "ecolor": "#444"}, zorder=3)

    for bar, val in zip(bars2, call_vals):
        ax.text(bar.get_x() + bar.get_width()/2, val + 1.5,
                f"{val:.1f}", ha="center", va="bottom",
                fontsize=10, fontweight="bold",
                color=bar.get_facecolor())

    # Highlight T vs S are essentially the same
    delta = abs(t_calls_mu - s_calls_mu)
    ax.text(1.5, max(call_vals) * 0.6,
            f"T vs S: Δ = {delta:.1f} calls\n(indistinguishable)",
            ha="center", fontsize=9, color="#666", fontstyle="italic",
            bbox=dict(boxstyle="round,pad=0.3", facecolor="#f5f5f5",
                      edgecolor="#ccc", linewidth=0.8))

    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=9.5)
    ax.set_ylabel("Avg tool calls per run")
    ax.set_ylim(0, 75)
    ax.set_title("(B)  Tool calls — no signal", fontweight="bold", loc="left")

    fig.suptitle("Standard Monitoring Cannot Detect the Performance Gap",
                 fontweight="bold", fontsize=13, y=1.02)

    fig.tight_layout()
    out = OUT_DIR / "fig2_aggregate_gap.png"
    fig.savefig(out, bbox_inches="tight", dpi=200)
    plt.close(fig)
    print(f"Saved {out}")

# ── Figure 3 — Compression Events × Outcome (clean bars) ────────────────────────

def fig3_smoking_gun(buckets):
    events       = [0, 1, 2]
    event_labels = ["0\ncompressions", "1\ncompression", "2\ncompressions"]
    x  = np.arange(len(events))
    bw = 0.35

    fig, ax = plt.subplots(figsize=(7, 5.2))

    for j, (prim, color, label) in enumerate([
        ("truncation",    COLOR_T, "Truncation"),
        ("summarization", COLOR_S, "Summarization"),
    ]):
        vals, elo, ehi, ns, ks = [], [], [], [], []
        for ev in events:
            b = buckets[(ev, prim)]
            n, k = b["n"], b["resolved"]
            ns.append(n); ks.append(k)
            res = k / n if n else 0
            lo, hi = wilson_ci(k, n)
            vals.append(res * 100)
            elo.append((res - lo) * 100)
            ehi.append((hi - res) * 100)

        offset = (j - 0.5) * bw
        bars = ax.bar(x + offset, vals, width=bw, color=color, alpha=0.82,
                      label=label, yerr=[elo, ehi], capsize=5,
                      error_kw={"linewidth": 1.4}, zorder=3)

        # n= labels at bar base (white text)
        for bar, n, k in zip(bars, ns, ks):
            h = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2,
                    0.35,
                    f"n={n}", ha="center", va="bottom",
                    fontsize=7, color="white", fontweight="bold")

    # Annotate S=0 at ev=2
    s2_center = x[2] + 0.5 * bw
    ax.annotate("0 / 28\nresolved\n(0.0%)",
                xy=(s2_center, 0.25),
                xytext=(s2_center + 0.65, 7.5),
                fontsize=9, color=COLOR_S, fontweight="bold", ha="left",
                arrowprops=dict(arrowstyle="->", color=COLOR_S, lw=1.3))

    # Tool calls text box for ev=2 group
    b_t2 = buckets[(2, "truncation")]
    b_s2 = buckets[(2, "summarization")]
    tc_t = sum(b_t2["calls"]) / len(b_t2["calls"])
    tc_s = sum(b_s2["calls"]) / len(b_s2["calls"])
    ax.text(2.0, 15,
            f"Tool calls  (ev = 2 group)\nTruncation: {tc_t:.0f}   Summarization: {tc_s:.0f}",
            ha="center", fontsize=8.5, color="#444",
            bbox=dict(boxstyle="round,pad=0.4", facecolor="#fff9e6",
                      edgecolor="#ddd", linewidth=0.9))

    ax.set_xticks(x)
    ax.set_xticklabels(event_labels, fontsize=11)
    ax.set_xlabel("Number of compression events fired per run")
    ax.set_ylabel("Resolve rate  (%)")
    ax.set_ylim(0, 22)
    ax.set_title("Catastrophic Failure Leaves No Trace in Tool-Call Counts",
                 fontweight="bold", pad=12)
    ax.legend(fontsize=10, frameon=False, loc="upper right")

    fig.tight_layout()
    out = OUT_DIR / "fig3_smoking_gun.png"
    fig.savefig(out, bbox_inches="tight", dpi=200)
    plt.close(fig)
    print(f"Saved {out}")

# ── Main ────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    results = load_data()
    cells   = build_cells(results)
    buckets = build_event_buckets(results)

    fig1_paradox(cells)
    fig2_aggregate_gap(cells, results)
    fig3_smoking_gun(buckets)

    # Remove old figure files if they exist
    for old in ["fig1_calls_by_budget.png", "fig2_precision_by_budget.png",
                "fig1_metric_blindness.png", "fig2_compression_events.png",
                "fig3_token_paradox.png"]:
        p = OUT_DIR / old
        if p.exists():
            p.unlink()
            print(f"Removed old {p.name}")

    print(f"\nAll figures saved to {OUT_DIR}/")
