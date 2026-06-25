"""Depth-axis paired analysis for RQ5 (SU-partial > SU-full as a depth lever)
and RQ5b (OTRC + partial-summarization super-additivity across depth).

Uses the 100-task n=100 depth-grid at 15k budget: 3 depths × {singles, otrc}.
For SU-partial vs SU-full we additionally include depth=0.3 @ 10k (bonus data).

For each comparison we compute:
  - per-task paired difference vector (rate_A − rate_B) ∈ {-1, -0.5, 0, +0.5, +1}
  - paired bootstrap 95 % CI on the mean (pairing cancels task variance)
  - McNemar exact test on the binary best-of-2 outcomes

Output: Review1/depth_analysis_report.md
"""
from math import comb
from pathlib import Path

import numpy as np
import pandas as pd

ROOT   = Path(__file__).parent.parent
REVIEW = Path(__file__).parent
CSV    = REVIEW / "Review1.csv"
OUT_MD = REVIEW / "depth_analysis_report.md"

df = pd.read_csv(CSV)
df["resolved_bool"] = df["resolved"].astype(str) == "True"

DEPTHS = (0.3, 0.5, 0.7)
DEPTH_LABEL = {0.3: "depth=0.3", 0.5: "depth=0.5", 0.7: "depth=0.7"}


def per_task_rate(prim: str, depth: float, budget: int = 15000) -> pd.Series:
    """100-task vector of resolve rates ∈ {0, 0.5, 1.0} for (prim, depth, budget)."""
    sub = df[(df.primitive == prim) & (df.depth == depth) & (df.token_budget == budget)]
    return sub.groupby("task_name").resolved_bool.mean().sort_index()


rng = np.random.default_rng(42)

def boot_mean_ci(x: np.ndarray, n_iter=5000, alpha=0.05):
    n = len(x)
    idx = rng.integers(0, n, size=(n_iter, n))
    means = x[idx].mean(axis=1)
    return x.mean(), np.quantile(means, alpha / 2), np.quantile(means, 1 - alpha / 2)


def mcnemar(a: np.ndarray, b: np.ndarray):
    A = a > 0; B = b > 0
    b_count = int(((A) & (~B)).sum())
    c_count = int(((~A) & (B)).sum())
    n = b_count + c_count
    if n == 0:
        return b_count, c_count, 1.0
    k = min(b_count, c_count)
    p = 2 * sum(comb(n, i) * 0.5 ** n for i in range(k + 1))
    return b_count, c_count, min(1.0, p)


report = ["# Depth-axis paired analysis (RQ5 / RQ5b)\n"]
def out(s=""):
    print(s); report.append(s)


def paired_compare(prim_a: str, depth_a: float, prim_b: str, depth_b: float,
                   budget: int = 15000, label: str = "") -> dict:
    a = per_task_rate(prim_a, depth_a, budget)
    b = per_task_rate(prim_b, depth_b, budget)
    common = a.index.intersection(b.index)
    a, b = a.loc[common].to_numpy(), b.loc[common].to_numpy()
    diff = a - b
    mean, lo, hi = boot_mean_ci(diff)
    b_only, c_only, p = mcnemar(a, b)
    return {
        "label":   label,
        "primA":   prim_a, "depthA": depth_a,
        "primB":   prim_b, "depthB": depth_b,
        "budget":  budget,
        "n":       len(common),
        "rateA":   100 * a.mean(),
        "rateB":   100 * b.mean(),
        "deltaPP": 100 * mean,
        "ciLoPP":  100 * lo,
        "ciHiPP":  100 * hi,
        "mcnemar_b": b_only,
        "mcnemar_c": c_only,
        "mcnemar_p": p,
    }


def print_row(r: dict):
    sig = "*" if r["mcnemar_p"] < 0.05 else " "
    out(f"| {r['label']:<48} | {r['n']:>3} | {r['rateA']:>5.1f}% | {r['rateB']:>5.1f}% | "
        f"{r['deltaPP']:+5.1f} | [{r['ciLoPP']:+5.1f}, {r['ciHiPP']:+5.1f}] | "
        f"{r['mcnemar_b']:>3}/{r['mcnemar_c']:<3} | {r['mcnemar_p']:.3f}{sig} |")


# ============================================================================
# Section 1 — Primitive × depth resolve rate matrix (orientation)
# ============================================================================
out("## §1 Primitive × depth resolve rates @ 15k\n")
out("Each cell = mean over 200 (task, run) records (100 tasks × 2 runs).\n")
out("| primitive          | depth=0.3 | depth=0.5 | depth=0.7 |")
out("|--------------------|----------:|----------:|----------:|")
SINGLES = ["TR", "SU-full", "SU-partial", "SS", "SS-partial"]
OTRC    = ["OTRC+TR", "OTRC+SU-partial", "OTRC+SS-partial"]
for prim in SINGLES + OTRC:
    cells = []
    for d in DEPTHS:
        v = per_task_rate(prim, d, 15000)
        cells.append(f"{100 * v.mean():.1f}% (n={len(v)})" if len(v) else "—")
    out(f"| {prim:<18} | {cells[0]:>10} | {cells[1]:>10} | {cells[2]:>10} |")
out("")


# ============================================================================
# Section 2 — RQ5 paired tests: SU-partial vs SU-full at each depth
# ============================================================================
out("## §2 RQ5 — SU-partial vs SU-full at each depth (paired @ 15k)\n")
out("Within-depth McNemar + paired bootstrap CI. Positive Δ = SU-partial > SU-full.\n")
out("| comparison                                       |   n | rateA | rateB |   Δpp |       95% CI | b/c    |  p     |")
out("|--------------------------------------------------|----:|------:|------:|------:|-------------:|:-------|:-------|")
rq5_within = []
for d in DEPTHS:
    r = paired_compare("SU-partial", d, "SU-full", d, 15000,
                       f"SU-partial vs SU-full @ {DEPTH_LABEL[d]} @ 15k")
    print_row(r); rq5_within.append(r)
out("")
out("**Depth-lever read:** the SU-partial − SU-full gap by depth at 15k = "
    + ", ".join(f"{r['deltaPP']:+.1f}pp ({DEPTH_LABEL[r['depthA']]})" for r in rq5_within) + ".\n")


# 10k tail-depth rows: depth=0.3 @ 10k (P100 bonus from prior aborted run)
# and depth=0.7 @ 10k (ABL-30 backfill, 2026-05-15). Different cohorts → n
# differs: P100 → n=100, ABL-30 → n=30.
out("### §2b SU-partial vs SU-full at tail depths @ 10k\n")
out("| comparison                                       |   n | rateA | rateB |   Δpp |       95% CI | b/c    |  p     |")
out("|--------------------------------------------------|----:|------:|------:|------:|-------------:|:-------|:-------|")
r = paired_compare("SU-partial", 0.3, "SU-full", 0.3, 10000,
                   "SU-partial vs SU-full @ depth=0.3 @ 10k (P100)")
print_row(r)
r = paired_compare("SU-partial", 0.7, "SU-full", 0.7, 10000,
                   "SU-partial vs SU-full @ depth=0.7 @ 10k (ABL-30)")
print_row(r)
out("")


# ============================================================================
# Section 3 — RQ5b paired tests: OTRC+SS-partial vs SS-partial across depths
#   plus OTRC+SS-partial vs OTRC+TR (the inner-primitive lever)
# ============================================================================
out("## §3 RQ5b — Stacking lift (OTRC + partial-summary) across depths @ 15k\n")
out("OTRC+SS-partial vs SS-partial isolates the OTRC online-clearing contribution\n"
    "on top of partial-summary. Positive Δ = OTRC adds lift over bare SS-partial.\n")
out("| comparison                                       |   n | rateA | rateB |   Δpp |       95% CI | b/c    |  p     |")
out("|--------------------------------------------------|----:|------:|------:|------:|-------------:|:-------|:-------|")
rq5b_stack = []
for d in DEPTHS:
    r = paired_compare("OTRC+SS-partial", d, "SS-partial", d, 15000,
                       f"OTRC+SS-partial vs SS-partial @ {DEPTH_LABEL[d]} @ 15k")
    print_row(r); rq5b_stack.append(r)
out("")
out("**Stacking-lift read:** OTRC+SS-partial − SS-partial gap by depth = "
    + ", ".join(f"{r['deltaPP']:+.1f}pp ({DEPTH_LABEL[r['depthA']]})" for r in rq5b_stack) + ".\n")

out("### §3b Inner-primitive lever (OTRC+SS-partial vs OTRC+TR) by depth @ 15k\n")
out("Positive Δ = stacking SS-partial inside OTRC beats stacking bare TR.\n")
out("| comparison                                       |   n | rateA | rateB |   Δpp |       95% CI | b/c    |  p     |")
out("|--------------------------------------------------|----:|------:|------:|------:|-------------:|:-------|:-------|")
for d in DEPTHS:
    r = paired_compare("OTRC+SS-partial", d, "OTRC+TR", d, 15000,
                       f"OTRC+SS-partial vs OTRC+TR @ {DEPTH_LABEL[d]} @ 15k")
    print_row(r)
out("")


# ============================================================================
# Section 4 — Within-primitive across-depth (does depth itself move the needle?)
# ============================================================================
out("## §4 Within-primitive depth comparisons @ 15k (Δ = tight − loose)\n")
out("Asks: holding primitive fixed, does cranking depth down (more aggressive\n"
    "compression) help or hurt? Positive Δ = depth=0.3 beats depth=0.7.\n")
out("| primitive            |   n | rate@0.3 | rate@0.7 |   Δpp |       95% CI | b/c    |  p     |")
out("|----------------------|----:|---------:|---------:|------:|-------------:|:-------|:-------|")
for prim in SINGLES + OTRC:
    r = paired_compare(prim, 0.3, prim, 0.7, 15000, prim)
    sig = "*" if r["mcnemar_p"] < 0.05 else " "
    out(f"| {prim:<20} | {r['n']:>3} | {r['rateA']:>7.1f}% | {r['rateB']:>7.1f}% | "
        f"{r['deltaPP']:+5.1f} | [{r['ciLoPP']:+5.1f}, {r['ciHiPP']:+5.1f}] | "
        f"{r['mcnemar_b']:>3}/{r['mcnemar_c']:<3} | {r['mcnemar_p']:.3f}{sig} |")
out("")


OUT_MD.write_text("\n".join(report) + "\n")
print(f"\nReport written to {OUT_MD}")
