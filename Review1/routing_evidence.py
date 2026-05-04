"""Evidence that primitives have non-overlapping competence sets.

Three artefacts:
  M1: pairwise disagreement matrix (11×11 at 15k + FC, OTRC) — heatmap
  M2: Δ-mean vs disagreement scatter — the punchline: disagreement isn't predicted by mean gap
  M3: oracle-of-k gap: as routing scope grows from 1 to 12 primitives, what resolve % can be reached?

Outputs to Review1/figures/ and prints summary numbers.
"""

import json
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

ROOT   = Path(__file__).parent.parent
REVIEW = Path(__file__).parent
OUT    = REVIEW / "figures"
OUT.mkdir(parents=True, exist_ok=True)

df = pd.read_csv(REVIEW / "Review1.csv")
df["resolved_bool"] = df["resolved"].astype(str) == "True"

# Primitives @ 15k + FC, OTRC at ∞
BUDGET_PRIMS = ["TR", "SU-full", "SU-partial", "SS", "SS-partial", "TRC",
                "TRC+SU", "TRC+SS", "OTRC+TR", "OTRC+SU-partial", "OTRC+SS-partial"]
INF_PRIMS    = ["FC", "OTRC"]
ALL_PRIMS    = BUDGET_PRIMS + INF_PRIMS  # 13 total

# Per-task best-of-2 binary resolved indicator under each primitive
def solved_set(prim: str) -> set:
    if prim in INF_PRIMS:
        sub = df[df.primitive == prim]
    else:
        sub = df[(df.primitive == prim) & (df.token_budget == 15000)]
    return set(sub.groupby("task_name").resolved_bool.max()[lambda s: s].index)

solve = {p: solved_set(p) for p in ALL_PRIMS}
mean_rate = {p: len(solve[p]) / 30 * 100 for p in ALL_PRIMS}
TASKS = sorted(set().union(*solve.values()) |
               set(df.task_name.unique()))   # all 30 tasks

# ────────────────────────────────────────────────────────────────────────────
# M1: pairwise disagreement matrix
# ────────────────────────────────────────────────────────────────────────────
n = len(ALL_PRIMS)
disagree = np.zeros((n, n))
for i, a in enumerate(ALL_PRIMS):
    for j, b in enumerate(ALL_PRIMS):
        if i == j:
            disagree[i, j] = 0
            continue
        # symmetric difference between solved sets
        disagree[i, j] = len(solve[a].symmetric_difference(solve[b]))

print(f"\n=== M1: pairwise disagreement (out of 30 tasks) ===")
print("(symmetric_diff of resolved-task sets — high = primitives win different tasks)\n")
hdr = "                 " + "".join(f"{p[:8]:>9}" for p in ALL_PRIMS)
print(hdr)
print("-" * len(hdr))
for i, p in enumerate(ALL_PRIMS):
    row = "".join(f"{int(disagree[i, j]):>9}" for j in range(n))
    print(f"{p:<17}" + row)

# Mean disagreement summary
upper = [disagree[i, j] for i in range(n) for j in range(n) if i < j]
print(f"\nMean pairwise disagreement: {np.mean(upper):.1f}/30 = {np.mean(upper)/30*100:.0f}%")
print(f"Range: [{int(np.min(upper))}, {int(np.max(upper))}]/30")

# Plot M1
fig, ax = plt.subplots(figsize=(10, 8.5))
im = ax.imshow(disagree, cmap="Reds", vmin=0, vmax=30)
ax.set_xticks(range(n)); ax.set_yticks(range(n))
ax.set_xticklabels(ALL_PRIMS, rotation=45, ha="right", fontsize=9)
ax.set_yticklabels(ALL_PRIMS, fontsize=9)
for i in range(n):
    for j in range(n):
        v = int(disagree[i, j])
        if i == j:
            txt = "—"
        else:
            txt = f"{v}"
        ax.text(j, i, txt, ha="center", va="center", fontsize=8,
                color="white" if v > 15 else "black")
cbar = fig.colorbar(im, ax=ax, fraction=0.04, pad=0.02)
cbar.set_label("Tasks with disagreeing outcome (out of 30)", fontsize=10)
ax.set_title("Pairwise per-task disagreement matrix\n"
             "(15k budget; FC and OTRC at no-threshold) — "
             "high values mean the two primitives solve different tasks",
             fontsize=11, fontweight="bold", pad=12)
plt.tight_layout()
plt.savefig(OUT / "fig_M1_disagreement_matrix.png", dpi=200, bbox_inches="tight")
plt.close()
print(f"\nsaved {OUT / 'fig_M1_disagreement_matrix.png'}")


# ────────────────────────────────────────────────────────────────────────────
# M2: Δ-mean vs disagreement (the punchline)
# ────────────────────────────────────────────────────────────────────────────
print(f"\n=== M2: |Δ mean| vs disagreement, all 78 pairs ===")
records = []
for i, j in combinations(range(n), 2):
    a, b = ALL_PRIMS[i], ALL_PRIMS[j]
    d_mean = abs(mean_rate[a] - mean_rate[b])
    d_set  = disagree[i, j]
    records.append((a, b, d_mean, d_set))

# Pairs with large disagreement but small Δ-mean: routing-relevant
sorted_records = sorted(records, key=lambda r: (-r[3] / max(1, r[2]+1)))
print("\nTop 10 'routing-relevant' pairs (high disagreement / small Δ-mean):\n")
print(f"{'pair':<45} {'|Δmean|pp':>10} {'disagree':>10} {'ratio':>7}")
print("-" * 75)
for a, b, dm, ds in sorted_records[:10]:
    print(f"{a + ' vs ' + b:<45} {dm:>9.1f}pp {int(ds):>10} {ds/max(1,dm+1):>6.2f}")

# Plot M2
fig, ax = plt.subplots(figsize=(8.5, 6.0))
xs = [r[2] for r in records]
ys = [r[3] for r in records]
ax.scatter(xs, ys, s=60, alpha=0.6, color="#3B82F6", edgecolor="white", linewidth=0.5)

# Annotate notable pairs (high disagreement, low Δmean) and (high Δmean for context)
notables = []
# pick pairs with ds > 12 and dm < 8 (high disagreement, similar mean)
for a, b, dm, ds in records:
    if ds >= 12 and dm <= 6:
        notables.append((a, b, dm, ds))
for a, b, dm, ds in notables[:6]:
    ax.annotate(f"{a} vs {b}", (dm, ds), fontsize=7,
                xytext=(5, 4), textcoords="offset points", color="#1F2937")

# Reference line: minimum possible disagreement given Δ-mean (= |Δ-mean| × 30/100)
xs_line = np.linspace(0, 50, 100)
ax.plot(xs_line, xs_line * 30 / 100, linestyle="--", color="#9CA3AF",
        alpha=0.7, label="Min possible disagreement = |Δmean| × 30/100\n(if one primitive's solved-set ⊂ the other's)")

ax.set_xlabel("|Δ mean resolve rate|  (pp, between primitive pair)", fontsize=11)
ax.set_ylabel("Pairwise per-task disagreement (out of 30 tasks)", fontsize=11)
ax.set_title("Disagreement is NOT predicted by mean-resolve gap\n"
             "Pairs above the dashed line have non-overlapping competence sets — routing has a job",
             fontsize=11, fontweight="bold", pad=10)
ax.legend(loc="lower right", frameon=False, fontsize=9)
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)
ax.grid(alpha=0.3, linestyle="--", linewidth=0.5)
ax.set_axisbelow(True)
plt.tight_layout()
plt.savefig(OUT / "fig_M2_disagreement_vs_meandiff.png", dpi=200, bbox_inches="tight")
plt.close()
print(f"\nsaved {OUT / 'fig_M2_disagreement_vs_meandiff.png'}")


# ────────────────────────────────────────────────────────────────────────────
# M3: Oracle-of-k routing scope, ONE LINE PER BUDGET
# ────────────────────────────────────────────────────────────────────────────
print(f"\n=== M3: Oracle-of-k per budget ===")

def solved_set_at(prim: str, budget) -> set:
    """Per-task best-of-2 solved set, scoped to a specific (primitive, budget)."""
    sub = df[(df.primitive == prim) & (df.token_budget == budget)]
    return set(sub.groupby("task_name").resolved_bool.max()[lambda s: s].index)

def best_k_subset(cells_dict, k):
    best = (0, None)
    names = list(cells_dict.keys())
    for combo in combinations(names, k):
        u = set()
        for p in combo:
            u |= cells_dict[p]
        if len(u) > best[0]:
            best = (len(u), combo)
    return best

# Build per-budget cells
budgets = [10000, 15000, 20000]
budget_cells = {b: {p: solved_set_at(p, b) for p in BUDGET_PRIMS} for b in budgets}

# FC and OTRC reference lines (no-threshold baselines)
fc_solved   = solve["FC"]
otrc_solved = solve["OTRC"]

curves = {}
for b in budgets:
    cells = budget_cells[b]
    n_prims = len(cells)
    series = []
    print(f"\nBudget {b//1000}k:")
    print(f"  {'k':>2} {'oracle':>10} {'best subset':<60}")
    for k in range(1, n_prims + 1):
        n_solved, combo = best_k_subset(cells, k)
        series.append((k, n_solved))
        print(f"  {k:>2} {n_solved:>4}/30 ({n_solved/30*100:>3.0f}%) "
              f"{', '.join(combo):<60}")
    curves[b] = series

# Plot
fig, ax = plt.subplots(figsize=(10, 5.7))

BUDGET_STYLES = {
    10000: dict(color="#C0392B", marker="o", linestyle="--",  linewidth=2.5, markersize=8,
                markerfacecolor="white", markeredgewidth=2),
    15000: dict(color="#E59500", marker="s", linestyle="-",   linewidth=2.5, markersize=7),
    20000: dict(color="#15803D", marker="^", linestyle="-",   linewidth=2.5, markersize=8),
}

# Tiny x-offsets so identical curves don't fully eclipse one another
X_OFFSET = {10000: -0.06, 15000: 0.0, 20000: +0.06}

# Y-stagger so identical 10k/15k labels don't fall on top of each other
Y_STAGGER = {10000: -3.0, 15000: +3.0, 20000: 0.0}

best_pairs_table = []   # for the inset table
for b in budgets:
    xs_base = [k for k, n in curves[b]]
    xs = [x + X_OFFSET[b] for x in xs_base]
    ys = [n / 30 * 100 for k, n in curves[b]]
    style = BUDGET_STYLES[b]
    cells_b = budget_cells[b]
    ax.plot(xs, ys, label=f"{b // 1000}k budget", **style)
    # ONE label per curve — at saturation point, vertically staggered
    sat_x = xs[1]                # saturation hits at k=2 for every budget
    sat_y = ys[1]
    ax.text(sat_x + 0.25, sat_y + Y_STAGGER[b], f"{sat_y:.0f}%",
            ha="left", va="center",
            fontsize=9.5, fontweight="bold", color=style["color"])
    # Capture for the inset table
    best_1_name  = best_k_subset(cells_b, 1)[1][0]
    best_2_combo = best_k_subset(cells_b, 2)[1]
    best_pairs_table.append((b, ys[0], best_1_name, ys[1], " + ".join(best_2_combo)))

# Reference: FC and OTRC at ∞
fc_pct   = len(fc_solved)   / 30 * 100
otrc_pct = len(otrc_solved) / 30 * 100
ax.axhline(fc_pct, color="#1F2937", linestyle=":", linewidth=1.5, alpha=0.7,
           label=f"FC (no compression): {fc_pct:.0f}%")
ax.axhline(otrc_pct, color="#F97316", linestyle="--", linewidth=1.5, alpha=0.7,
           label=f"OTRC (no threshold): {otrc_pct:.0f}%")

ax.set_xlabel("Routing scope: k primitives available to a perfect oracle (within budget)",
              fontsize=11)
ax.set_ylabel("Oracle-routed resolve rate  (%)", fontsize=11)
ax.set_title("Oracle-of-k by budget — saturation at k=2 across all budgets",
             fontsize=11, fontweight="bold", pad=10)
ax.set_xticks(range(1, 12))
ax.set_xlim(0.5, 11.5)
ax.set_ylim(0, 100)
ax.legend(loc="lower right", frameon=False, fontsize=10)

# Inset text table: the optimal singles and pairs
table_lines = ["Best single (k=1)  →  best pair (k=2)"]
for b, y1, p1, y2, pair in best_pairs_table:
    table_lines.append(f"  {b // 1000}k:  {p1}  ({y1:.0f}%)  →  {pair}  ({y2:.0f}%)")
ax.text(0.025, 0.32, "\n".join(table_lines),
        transform=ax.transAxes, fontsize=9, va="top", ha="left",
        family="monospace",
        bbox=dict(boxstyle="round,pad=0.5", facecolor="white",
                  edgecolor="#999", linewidth=0.7, alpha=0.95))
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)
ax.grid(alpha=0.3, linestyle="--", linewidth=0.5)
ax.set_axisbelow(True)
plt.tight_layout()
plt.savefig(OUT / "fig_M3_oracle_of_k.png", dpi=200, bbox_inches="tight")
plt.close()
print(f"\nsaved {OUT / 'fig_M3_oracle_of_k.png'}")

# Print summary
print(f"\n=== M3 summary: routing headroom by budget ===")
for b in budgets:
    s = curves[b]
    best1 = s[0][1]
    sat   = s[-1][1]
    print(f"  {b//1000}k: best-single = {best1}/30 ({best1/30*100:.0f}%)  "
          f"oracle-of-{len(s)} = {sat}/30 ({sat/30*100:.0f}%)  "
          f"routing headroom = +{sat - best1} tasks (+{(sat - best1)/30*100:.0f}pp)")


# ────────────────────────────────────────────────────────────────────────────
# Summary numbers
# ────────────────────────────────────────────────────────────────────────────
print(f"\n=== Headline numbers for the paper ===")
n_avg_eq_pairs = sum(1 for r in records if r[2] <= 6)
n_high_disagree_avg_eq = sum(1 for r in records if r[2] <= 6 and r[3] >= 12)
print(f"Of {len(records)} primitive pairs:")
print(f"  - {n_avg_eq_pairs} have |Δmean| ≤ 6pp ('average-equivalent')")
print(f"  - of those, {n_high_disagree_avg_eq} have ≥ 40% per-task disagreement")
print(f"  → average-equivalent primitives are NOT solving the same tasks {n_high_disagree_avg_eq}/{n_avg_eq_pairs} of the time")

# (per-budget headroom already printed above in the M3 summary)
