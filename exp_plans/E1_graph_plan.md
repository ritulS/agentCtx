# E1 Graph Redesign Plan

## Context
Redesign `plot_e1_v2.py` to produce 5 clean, publication-ready figures that together tell the E1 metric blindness story. All 897 runs are in `results/experiment_results.json`.

## Key Data Facts
- Full context = truncation at p100 (100% budget, no compression fires). This IS a proper data series. At 100%, truncation and summarization are identical — so the truncation line naturally includes the 100% anchor point.
- Summarization has no 100% data point by design (redundant). Its line spans 25%–75%.
- n=69 per (primitive, budget) cell; n_resolved = 0–5 per cell.
- Tasks that fail at full context can succeed at compressed budget (and vice versa) — fine statistically, shows up in the per-budget mean.

**Budget → Resolve Rate (truncation)**
100%=7%, 75%=4%, 60%=3%, 50%=0%, 40%=1%, 30%=1%, 25%=1%

**Budget → Avg Calls (truncation, ALL vs RESOLVED only)**
100%: all=30.5, res=17.2 | 75%: all=32.9, res=12.3 | 25%: all=40.6, res=7.0

## What E1 Conveys
Three contradictory signals from the same data:
1. Resolve rate: 7% → 1% (declining — bad)
2. Calls per resolved task: 17.2 → 7.0 (appears to *improve* — the trap)
3. Calls across ALL tasks: 30.5 → 40.6 (rising — the truth)

No single metric tells the full story. That's the motivation for WAF.

---

## Figure 1 — Task Outcome Distribution (bar chart)
**Purpose:** Orient the reader. Show how many of the 897 runs fall into each outcome bucket, broken out by budget level.

**Type:** Stacked bar chart
**X-axis:** Token budget levels (25%, 30%, 40%, 50%, 60%, 75%, 100%)
**Y-axis:** Count of runs (69 per cell at 100%; 138 per compressed level across both primitives)
**Stacks:**
- Gray: Failed (no patch generated)
- Orange: Patch generated, not resolved
- Green: Resolved

Both primitives combined per budget level.
**Title:** "Run outcomes by token budget"

---

## Figure 2 — All-Run Metrics: 5 panels (3 top, 2 bottom)
**Purpose:** Show raw system behavior across budgets.

**Layout:** 3 panels top row + 2 panels bottom row (gridspec)

**Top row:** Latency (s), Token Usage (k), Tool Calls
**Bottom row:** Patch Rate (%), Resolve Rate (%)

**Series:**
- Truncation (blue): x = 25, 30, 40, 50, 60, 75, 100 — 100% IS the full context anchor
- Summarization (orange): x = 25, 30, 40, 50, 60, 75
- x=100 tick labeled "100%\n(Full ctx)"

**Styling:** Error bars (95% t-CI), y-only gridlines, simple panel titles, one shared legend
**Title:** "E1 — Agent metrics across token budgets"

---

## Figure 3 — Resolved Runs Only: 3 panels
**Purpose:** Reveal survivorship bias — what a dashboard tracking only successful tasks would show.

**Layout:** 1 row, 3 panels
**Panels:** Tool Calls, Token Usage (k), E2E Latency (s) — resolved runs only
**Styling:** Scatter markers (no line), annotate each point with n=X, skip points where n_resolved=0
**Title:** "Cost of resolved tasks only (survivorship)"

---

## Figure 4 — Exit Status Breakdown
**Purpose:** Show the mechanism — at low budgets, nearly everything hits the step-limit ceiling.

**Type:** Stacked bar chart (grouped by primitive)
**X-axis:** Budget levels, side-by-side bars for truncation and summarization
**Stacks:** Submitted / LimitsExceeded / Timeout / BadRequest
**Insight:** At 25–40% budget, 75–80% of runs hit step limit — agent burns all steps on compressed context.
**Title:** "Exit status breakdown by budget"

---

## Figure 5 — The Metric Blindness Proof (hero figure)
**Purpose:** Show all three contradictory signals on one chart.

**Type:** Single panel, dual Y-axis, truncation only
**Left Y (red):** Resolve rate (%) — solid, declining
**Right Y (dark blue):**
- Solid: Avg calls ALL tasks (rising)
- Dashed: Avg calls RESOLVED tasks only (falling)
- Shaded gap between = hidden cost

**Annotations:** "Resolve rate collapses" / "Per-task cost 'improves'" / "True cost rises"
**Title:** "Three metrics, three contradictory stories"

---

## File to Modify
`/home/rs67788/projects/agentCtx/scripts/plot_e1_v2.py` — complete rewrite

## Output Files
```
figures/e1/fig1_outcomes.png
figures/e1/fig2_all_runs.png
figures/e1/fig3_resolved_only.png
figures/e1/fig4_exit_status.png
figures/e1/fig5_metric_blindness.png
```
