"""F8 follow-up: paired (within-task) CIs and McNemar tests for key primitive comparisons.

The unpaired bootstrap CI on resolve rate is ±12pp because task variance dominates.
Pairing on the same 30 tasks cancels task variance and gives tighter intervals.

For each task t, we have 2 runs per primitive, so the per-task outcome under primitive p
is a count out of 2 (in {0, 1, 2}) — equivalently a resolve-rate in {0, 0.5, 1.0}.
The paired statistic is the difference (rate_A_t − rate_B_t) ∈ {-1, -0.5, 0, +0.5, +1}.

Bootstrap CI on the mean of this 30-element difference vector gives a paired CI on
the resolve-rate gap, in pp.
"""

import json
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd

ROOT   = Path(__file__).parent.parent
REVIEW = Path(__file__).parent
CSV    = REVIEW / "Review1.csv"
OUT_MD = REVIEW / "paired_analysis_report.md"

df = pd.read_csv(CSV)
df["resolved_bool"] = df["resolved"].astype(str) == "True"

# (primitive, budget) → 30-task vector of resolve rates ∈ {0, 0.5, 1.0}
def per_task_rate(prim: str, budget) -> pd.Series:
    if prim in ("FC", "OTRC"):
        sub = df[df.primitive == prim]
    else:
        sub = df[(df.primitive == prim) & (df.token_budget == budget)]
    return sub.groupby("task_name").resolved_bool.mean().sort_index()

rng = np.random.default_rng(42)
def boot_mean_ci(x: np.ndarray, n_iter=5000, alpha=0.05):
    n = len(x)
    idx = rng.integers(0, n, size=(n_iter, n))
    means = x[idx].mean(axis=1)
    return x.mean(), np.quantile(means, alpha/2), np.quantile(means, 1 - alpha/2)

def mcnemar(a: np.ndarray, b: np.ndarray):
    """McNemar test on binary outcomes (per-task best-of-2). Returns (b, c, p)
    where b = #(A_resolved & not B), c = #(not A & B_resolved), p = exact p-value.
    Uses task as 'resolved if either run resolved' (rate > 0)."""
    A = (a > 0); B = (b > 0)
    b_count = int(((A) & (~B)).sum())
    c_count = int(((~A) & (B)).sum())
    n = b_count + c_count
    if n == 0:
        return b_count, c_count, 1.0
    # exact two-sided p-value: 2 * P(X <= min(b,c)) under Binom(n, 0.5)
    from math import comb
    k = min(b_count, c_count)
    p = 2 * sum(comb(n, i) * 0.5**n for i in range(k + 1))
    return b_count, c_count, min(1.0, p)


report = ["# Paired-analysis follow-up to F8\n"]
def out(s=""):
    print(s); report.append(s)


# ────────────────────────────────────────────────────────────────────────────
# Headline comparisons we make in the paper
# ────────────────────────────────────────────────────────────────────────────
HEADLINE = [
    # (label,            primA, budgetA,            primB, budgetB)
    ("Best stacked vs best single @ 20k",
     "TRC+SS", 20000,    "TRC", 20000),
    ("TRC+SU vs OTRC+SU-partial @ 15k (both 65%)",
     "TRC+SU", 15000,    "OTRC+SU-partial", 15000),
    ("TR vs SU-full @ 15k (the silent-crash story)",
     "TR", 15000,        "SU-full", 15000),
    ("TRC+SS vs TRC @ 15k",
     "TRC+SS", 15000,    "TRC", 15000),
    ("SU-partial vs SU-full @ 15k (does partial help?)",
     "SU-partial", 15000, "SU-full", 15000),
    ("OTRC+TR vs OTRC @ ∞ (does adding budget hurt?)",
     "OTRC+TR", 15000,   "OTRC", "∞"),
    ("FC vs TRC+SS @ 20k (no-compression vs best stacked)",
     "FC", "∞",          "TRC+SS", 20000),
    ("OTRC+SS-partial vs SS-partial @ 20k (does OTRC help SS-partial?)",
     "OTRC+SS-partial", 20000, "SS-partial", 20000),
]

out("\n## Headline paired comparisons\n")
out("Each row: paired bootstrap CI on the per-task difference (A − B) on the same 30 tasks,")
out("plus McNemar exact test on per-task best-of-2 outcome.\n")
out("```")
out(f"{'comparison':<55} {'A%':>5} {'B%':>5} {'Δpp':>6}  "
    f"{'paired 95% CI':<18} {'McN p':>7} {'note':<10}")
out("-" * 120)

for label, pA, bA, pB, bB in HEADLINE:
    a = per_task_rate(pA, bA).values
    b = per_task_rate(pB, bB).values
    if len(a) != 30 or len(b) != 30:
        out(f"{label:<55}  SKIP (cell missing)"); continue
    diff = a - b
    mean_diff, lo, hi = boot_mean_ci(diff)
    bc, cc, p = mcnemar(a, b)
    Apct, Bpct = a.mean()*100, b.mean()*100
    ci_str = f"[{lo*100:+.1f}, {hi*100:+.1f}]pp"
    sig    = "*" if (lo > 0 or hi < 0) else ""
    note   = f"({bc} A>B, {cc} B>A)"
    out(f"{label:<55} {Apct:>4.0f}% {Bpct:>4.0f}% {mean_diff*100:+5.1f}pp  "
        f"{ci_str:<18} {p:>6.3f}{sig:>1} {note:<10}")
out("```")
out("\n* = paired 95% CI excludes zero (significant at α=0.05).")


# ────────────────────────────────────────────────────────────────────────────
# Compare unpaired vs paired CI widths for every primitive at 15k
# ────────────────────────────────────────────────────────────────────────────
out("\n## Unpaired vs paired CI half-widths at 15k\n")
out("```")
out(f"{'primitive':<20} {'res%':>5} {'unpaired CI':<18} {'± hw':>6}  "
    f"{'paired Δ vs FC':<18} {'± hw_paired':>12}")
out("-" * 88)

prims_15k = ["TR", "SU-full", "SU-partial", "SS", "SS-partial", "TRC",
             "TRC+SU", "TRC+SS", "OTRC+TR", "OTRC+SU-partial", "OTRC+SS-partial"]
fc_v = per_task_rate("FC", "∞").values

for p in prims_15k:
    rates = per_task_rate(p, 15000)
    if len(rates) != 30: continue
    v = rates.values
    # Unpaired: bootstrap on individual run outcomes (n=60)
    sub = df[(df.primitive == p) & (df.token_budget == 15000)]
    raw = sub.resolved_bool.values.astype(float)
    m_unp, lo_unp, hi_unp = boot_mean_ci(raw)
    hw_unp = (hi_unp - lo_unp) / 2

    # Paired vs FC
    diff = v - fc_v
    m_p, lo_p, hi_p = boot_mean_ci(diff)
    hw_p = (hi_p - lo_p) / 2

    out(f"{p:<20} {m_unp*100:>4.0f}% "
        f"[{lo_unp*100:>4.1f}, {hi_unp*100:>4.1f}] {hw_unp*100:>4.1f}pp  "
        f"{m_p*100:+5.1f} [{lo_p*100:+5.1f}, {hi_p*100:+5.1f}] {hw_p*100:>11.1f}pp")
out("```")


# ────────────────────────────────────────────────────────────────────────────
# Pairwise significance grid at 15k (every pair, paired McNemar)
# ────────────────────────────────────────────────────────────────────────────
out("\n## Pairwise significance grid at 15k (McNemar exact p-value)\n")

prims_for_grid = prims_15k  # 11 primitives at 15k
n = len(prims_for_grid)
vecs = {p: per_task_rate(p, 15000).values for p in prims_for_grid}
grid_p = np.full((n, n), np.nan)
grid_d = np.full((n, n), np.nan)
for i, pA in enumerate(prims_for_grid):
    for j, pB in enumerate(prims_for_grid):
        if i == j: continue
        a, b = vecs[pA], vecs[pB]
        _, _, p = mcnemar(a, b)
        grid_p[i, j] = p
        grid_d[i, j] = (a.mean() - b.mean()) * 100

out("Δ (row − col), in pp; cells with McNemar p < 0.05 marked with *.\n")
out("```")
header = "                 " + "  ".join(f"{p[:7]:>7}" for p in prims_for_grid)
out(header)
out("-" * len(header))
for i, pA in enumerate(prims_for_grid):
    cells = []
    for j, pB in enumerate(prims_for_grid):
        if i == j:
            cells.append(f"{'  -  ':>7}")
        else:
            sig = "*" if grid_p[i, j] < 0.05 else ""
            cells.append(f"{grid_d[i, j]:>+5.0f}{sig:<2}")
    out(f"{pA:<17}" + "  ".join(cells))
out("```")

n_sig = int((grid_p[~np.isnan(grid_p)] < 0.05).sum() / 2)
n_pairs = n * (n - 1) // 2
out(f"\nOf {n_pairs} pairwise comparisons at 15k, {n_sig} are significant at α=0.05 by McNemar.")


# ────────────────────────────────────────────────────────────────────────────
# Save
# ────────────────────────────────────────────────────────────────────────────
OUT_MD.write_text("\n".join(report))
out(f"\n---\n\nReport written to {OUT_MD}")
