"""Foundational data sanity checks (F1-F14) for Review1.csv.

Runs the integrity / definition / distribution / confounder / representativeness
checks proposed in the planning discussion. Output: console + sanity_report.md.
"""

import json
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

ROOT     = Path(__file__).parent.parent
REVIEW   = Path(__file__).parent
REPORT   = REVIEW / "sanity_report.md"
ABL_FILE = ROOT / "results/ablations/tasks.json"
P100_NEW_FILE = ROOT / "task_lists/p100_new_tasks.json"
CSV      = REVIEW / "Review1.csv"

# ── Setup ─────────────────────────────────────────────────────────────────────
abl_tasks = json.load(open(ABL_FILE))
p100_new  = json.load(open(P100_NEW_FILE))
ABL_IDS   = set(t["instance_id"] for t in abl_tasks)
P100_NEW_IDS = set(t["instance_id"] for t in p100_new)
P100_IDS  = ABL_IDS | P100_NEW_IDS  # 100-task cohort
REPOS_OF  = {t["instance_id"]: t["repo"] for t in abl_tasks + p100_new}
N_TASKS   = len(P100_IDS)
N_PER_CELL = N_TASKS * 2  # 2 runs per task

df = pd.read_csv(CSV)
df = df[df.depth == 0.5].copy()  # scope to canonical depth — depth-grid lives in depth_analysis.py
df["resolved_bool"]   = df["resolved"].astype(str) == "True"
df["patch_bool"]      = df["patch_generated"].astype(str) == "True"

PRIMITIVES = sorted(df.primitive.unique())
BUDGET_PRIMS = [p for p in PRIMITIVES if p not in ("FC", "OTRC")]
INF_PRIMS    = ["FC", "OTRC"]
BUDGETS      = [10000, 15000, 20000]

# Report buffer
report = ["# Review1 sanity report\n"]
def out(s=""):
    print(s)
    report.append(s)

def status(ok: bool, warn=False) -> str:
    if warn:  return "⚠️ "
    return "✅ " if ok else "❌ "

# ════════════════════════════════════════════════════════════════════════════
# F1: New primitives — did they actually execute their intended algorithm?
# ════════════════════════════════════════════════════════════════════════════
out("\n## F1 — New primitive correctness invariants\n")

f1_checks = []

# (a) SU/SS-partial cells: summarization_prompt_tokens > 0 in most runs
for prim in ["SU-partial", "SS-partial", "OTRC+SU-partial", "OTRC+SS-partial"]:
    if prim in INF_PRIMS or prim not in df.primitive.values:
        continue
    sub = df[df.primitive == prim]
    n_with_call = (sub.summarization_prompt_tokens.astype(float) > 0).sum()
    pct = n_with_call / len(sub) * 100
    note = f"{n_with_call}/{len(sub)} runs ({pct:.0f}%) had summarization_prompt_tokens > 0"
    # Expect non-trivial fraction — not all runs hit budget, so 100% isn't expected
    ok = pct >= 50  # at least half the runs should fire compression
    f1_checks.append(("SU/SS-partial LLM call fired", prim, ok, note))
    out(f"{status(ok)} {prim}: {note}")

# (b) OTRC family: online_trc_clears > 0 in most runs
for prim in ["OTRC", "OTRC+TR", "OTRC+SU-partial", "OTRC+SS-partial"]:
    if prim not in df.primitive.values:
        continue
    sub = df[df.primitive == prim]
    n_with_clear = (sub.online_trc_clears.astype(float) > 0).sum()
    pct = n_with_clear / len(sub) * 100
    note = f"{n_with_clear}/{len(sub)} runs ({pct:.0f}%) had online_trc_clears > 0"
    ok = pct >= 80  # OTRC fires every step after step 5; should be near-universal
    f1_checks.append(("OTRC freeze-window fired", prim, ok, note))
    out(f"{status(ok)} {prim}: {note}")

# (c) TRC+SU/SS: trc_fallback_events should always be 0 (we set fallback_truncate=False)
for prim in ["TRC+SU", "TRC+SS"]:
    sub = df[df.primitive == prim]
    n_nonzero = (sub.trc_fallback_events.astype(float) > 0).sum()
    note = f"{n_nonzero}/{len(sub)} runs had trc_fallback_events > 0  (should always be 0)"
    ok = n_nonzero == 0
    f1_checks.append(("TRC+X has no TR fallback", prim, ok, note))
    out(f"{status(ok)} {prim}: {note}")

# (d) FC and OTRC: compression_events should be 0 (no budget gate)
for prim in INF_PRIMS:
    sub = df[df.primitive == prim]
    n_nonzero = (sub.compression_events.astype(float) > 0).sum()
    note = f"{n_nonzero}/{len(sub)} runs had compression_events > 0  (budget=∞ → should be 0)"
    ok = n_nonzero == 0
    f1_checks.append(("∞-budget primitives don't compress", prim, ok, note))
    out(f"{status(ok)} {prim}: {note}")


# ════════════════════════════════════════════════════════════════════════════
# F2: Cell completeness — 60 runs/cell, no duplicates, sane values
# ════════════════════════════════════════════════════════════════════════════
out("\n## F2 — Cell completeness\n")

# Expected cells: each budget primitive × 3 budgets × N_PER_CELL runs; INF primitives × 1 cell × N_PER_CELL runs
expected_n = N_PER_CELL
issues = []

for prim in BUDGET_PRIMS:
    for b in BUDGETS:
        sub = df[(df.primitive == prim) & (df.token_budget == b)]
        n = len(sub)
        if n != expected_n:
            issues.append(f"{prim}@{b}: {n} rows (expected {expected_n})")
        # uniqueness: each (task, run_num) should appear once
        dups = sub.groupby(["task_name", "run_num"]).size()
        n_dups = (dups > 1).sum()
        if n_dups > 0:
            issues.append(f"{prim}@{b}: {n_dups} duplicate (task,run_num) pairs")
        # task coverage
        uniq_tasks = sub.task_name.nunique()
        if uniq_tasks != N_TASKS:
            issues.append(f"{prim}@{b}: {uniq_tasks}/{N_TASKS} unique tasks")
        # all tasks in P100_IDS?
        outside = set(sub.task_name) - P100_IDS
        if outside:
            issues.append(f"{prim}@{b}: {len(outside)} tasks outside P100 set: {sorted(outside)[:3]}...")

for prim in INF_PRIMS:
    sub = df[df.primitive == prim]
    if len(sub) != expected_n:
        issues.append(f"{prim} (∞): {len(sub)} rows (expected {expected_n})")

if not issues:
    out(f"{status(True)} All 35 cells (11×3 budget + 2 ∞) have exactly {N_PER_CELL} unique (task, run) rows on the {N_TASKS} P100 tasks")
else:
    for i in issues:
        out(f"{status(False)} {i}")

# Check for zero step_count or zero tokens (indicators of broken records)
zero_steps = (df.step_count.astype(float) == 0).sum()
zero_tok   = (df.total_tokens_consumed.astype(float) == 0).sum()
out(f"{status(zero_steps == 0 and zero_tok == 0)} {zero_steps} rows with step_count=0, {zero_tok} rows with total_tokens=0")


# ════════════════════════════════════════════════════════════════════════════
# F3: SWE-bench eval reliability
# ════════════════════════════════════════════════════════════════════════════
out("\n## F3 — Eval-result self-consistency\n")

# Resolved=None should ONLY occur when no patch was generated
res_none      = df[df.resolved.isna() | (df.resolved.astype(str) == "")]
res_none_with_patch = res_none[res_none.patch_bool == True]
out(f"{status(len(res_none_with_patch) == 0)} {len(res_none_with_patch)} rows have resolved=None but patch_generated=True")
if len(res_none_with_patch):
    sample = res_none_with_patch[["task_name","primitive","token_budget","exit_status"]].head(10)
    out(f"   sample:\n{sample.to_string(index=False)}")

# Submitted but no patch — contradiction?
sub_no_patch = df[(df.exit_status == "Submitted") & (df.patch_bool == False)]
out(f"{status(len(sub_no_patch) == 0)} {len(sub_no_patch)} rows have exit_status='Submitted' but patch_generated=False")
if len(sub_no_patch):
    out(f"   sample tasks: {sub_no_patch.task_name.value_counts().head(5).to_dict()}")

# resolved=True should only occur when patch was generated
res_true_no_patch = df[df.resolved_bool & ~df.patch_bool]
out(f"{status(len(res_true_no_patch) == 0)} {len(res_true_no_patch)} rows have resolved=True but patch_generated=False")


# ════════════════════════════════════════════════════════════════════════════
# F4: Cross-validate against previously-reported numbers
# ════════════════════════════════════════════════════════════════════════════
out("\n## F4 — Cross-validation against earlier numbers\n")

# Recompute resolve counts from the SOURCE result files; compare to Review1.csv
sources_to_check = [
    # (source_file, condition, primitive_label_in_csv, budget)
    ("results/qwen3.5-35B-A3B_15k_Fullrun/experiment_results.json", "truncation",        "TR",      15000),
    ("results/qwen3.5-35B-A3B_15k_Fullrun/experiment_results.json", "summarization",     "SU-full", 15000),
    ("results/qwen3.5-35B-A3B_15k_Fullrun/experiment_results.json", "tool-result-clear", "TRC",     15000),
    ("results/qwen3.5-35B-A3B_15k_Fullrun/experiment_results.json", "structured-summarize","SS",    15000),
    ("results/qwen3.5-35B-A3B_15k_Fullrun/experiment_results.json", "full-context",      "FC",      999999999),
    ("results/ablations/timing-10k/experiment_results.json",        "truncation",        "TR",      10000),
    ("results/ablations/timing-20k/experiment_results.json",        "truncation",        "TR",      20000),
    ("results/ablations/stacked-10000/experiment_results.json",     "trc-su",            "TRC+SU",  10000),
    ("results/ablations/stacked-15000/experiment_results.json",     "trc-ss",            "TRC+SS",  15000),
    ("results/ablations/partial-15000/experiment_results.json",     "summarization-partial",       "SU-partial",      15000),
    ("results/ablations/otrc-stacked-15000/experiment_results.json","otrc-su-partial",   "OTRC+SU-partial", 15000),
    ("results/qwen35-a3b_online-trc/experiment_results.json",       "online-trc",        "OTRC",    999999999),
]
all_match = True
for src, cond, prim, budget in sources_to_check:
    p = ROOT / src
    if not p.exists():
        out(f"{status(False)} source missing: {src}"); all_match = False; continue
    runs = json.load(open(p))
    src_resolved = sum(1 for r in runs
                        if r.get("condition") == cond
                        and r.get("instance_id") in ABL_IDS
                        and r.get("resolved") is True)
    # Compare against the ABL portion of the CSV cell (the original 30-task cohort)
    csv_sub = df[(df.primitive == prim) & (df.token_budget == budget) &
                 (df.task_name.isin(ABL_IDS))]
    csv_resolved = csv_sub.resolved_bool.sum()
    ok = src_resolved == csv_resolved
    if not ok: all_match = False
    out(f"{status(ok)} {prim}@{budget if budget < 1e8 else '∞'}: source={src_resolved}, csv(ABL only)={csv_resolved}")

out(f"\n**Overall F4: {'PASS' if all_match else 'FAIL'}** — Review1.csv matches source experiment_results.json")


# ════════════════════════════════════════════════════════════════════════════
# F5: Definitional integrity — what is step_count actually?
# ════════════════════════════════════════════════════════════════════════════
out("\n## F5 — Step count definition\n")

# For LimitsExceeded runs, step_count should be at the step-limit ceiling
le = df[df.exit_status.fillna("").str.contains("Limits", regex=False)]
out(f"LimitsExceeded runs: {len(le)} total")
out(f"  step_count distribution: min={le.step_count.min()}, "
    f"max={le.step_count.max()}, median={le.step_count.median()}")
out(f"  step_count ≥ 100: {(le.step_count >= 100).sum()}/{len(le)} runs")
# Suggests step_limit = 100 (or thereabouts)

# For silent crashes: step distribution
sc = df[df.failure_mode == "silent_crash"]
out(f"\nSilent-crash runs: {len(sc)} total")
out(f"  step_count distribution: min={sc.step_count.min()}, max={sc.step_count.max()}, "
    f"median={sc.step_count.median()}")
# Bimodal? Check
sc_steps = sc.step_count.astype(float).values
early_exit = (sc_steps < 10).sum()
late_exit  = (sc_steps >= 50).sum()
mid        = len(sc_steps) - early_exit - late_exit
out(f"  early-exit (<10 steps): {early_exit} | mid (10-49): {mid} | late (≥50): {late_exit}")


# ════════════════════════════════════════════════════════════════════════════
# F6: Token accounting consistency
# ════════════════════════════════════════════════════════════════════════════
out("\n## F6 — Token accounting consistency\n")

# Sanity: summarization_prompt_tokens <= total_prompt_tokens for every row
df_t = df.copy()
df_t["spt"] = df_t.summarization_prompt_tokens.astype(float)
df_t["tpt"] = df_t.total_prompt_tokens.astype(float)
violations = df_t[df_t.spt > df_t.tpt]
out(f"{status(len(violations) == 0)} {len(violations)} rows have summarization_prompt_tokens > total_prompt_tokens")

# total = prompt + completion (within rounding)?
df_t["tot"] = df_t.total_tokens_consumed.astype(float)
df_t["pc"]  = df_t.tpt + df_t.total_completion_tokens.astype(float)
mismatch = (np.abs(df_t["tot"] - df_t["pc"]) > 1).sum()
out(f"{status(mismatch == 0)} {mismatch} rows where total_tokens != prompt + completion")


# ════════════════════════════════════════════════════════════════════════════
# F8: Within-cell variance — bootstrap CI on resolve rate per cell
# ════════════════════════════════════════════════════════════════════════════
out("\n## F8 — Bootstrap 95% CI per (primitive, budget) cell\n")

rng = np.random.default_rng(42)
def bootstrap_ci(outcomes: np.ndarray, n_iter=2000, alpha=0.05):
    if len(outcomes) == 0:
        return (np.nan, np.nan, np.nan)
    n = len(outcomes)
    idx = rng.integers(0, n, size=(n_iter, n))
    samples = outcomes[idx].mean(axis=1)
    lo = np.quantile(samples, alpha/2)
    hi = np.quantile(samples, 1 - alpha/2)
    return outcomes.mean(), lo, hi

ci_rows = []
for prim in BUDGET_PRIMS:
    for b in BUDGETS:
        sub = df[(df.primitive == prim) & (df.token_budget == b)]
        if not len(sub): continue
        outs = sub.resolved_bool.values.astype(int)
        m, lo, hi = bootstrap_ci(outs)
        ci_rows.append({"primitive": prim, "budget": b, "n": len(outs),
                        "resolve_mean": m, "ci_lo": lo, "ci_hi": hi,
                        "ci_halfwidth": (hi-lo)/2})
for prim in INF_PRIMS:
    sub = df[df.primitive == prim]
    outs = sub.resolved_bool.values.astype(int)
    m, lo, hi = bootstrap_ci(outs)
    ci_rows.append({"primitive": prim, "budget": "∞", "n": len(outs),
                    "resolve_mean": m, "ci_lo": lo, "ci_hi": hi,
                    "ci_halfwidth": (hi-lo)/2})

ci_df = pd.DataFrame(ci_rows)
ci_df["resolve_pct"] = (ci_df.resolve_mean * 100).round(1)
ci_df["ci_pct"]      = "[" + (ci_df.ci_lo*100).round(1).astype(str) + ", " + (ci_df.ci_hi*100).round(1).astype(str) + "]"
ci_df["halfwidth_pp"] = (ci_df.ci_halfwidth * 100).round(1)

out("\n```")
out(f"{'primitive':<18} {'budget':>7} {'resolve%':>9}  {'95% CI':<18} {'halfwidth (pp)':>15}")
out("-"*72)
for _, r in ci_df.iterrows():
    out(f"{r['primitive']:<18} {str(r['budget']):>7} {r['resolve_pct']:>8.1f}%  {r['ci_pct']:<18} {r['halfwidth_pp']:>14.1f}")
out("```")

mean_hw = ci_df.halfwidth_pp.mean()
out(f"\nMean CI half-width across cells: **±{mean_hw:.1f}pp**. "
    "Differences smaller than 2× this width are within sampling noise.")


# ════════════════════════════════════════════════════════════════════════════
# F9: Between-task variance — universally easy / hard tasks
# ════════════════════════════════════════════════════════════════════════════
out("\n## F9 — Per-task resolve rate (across all primitives × budgets × runs)\n")

# Each task appears in many (primitive, budget, run) cells. Compute mean across all.
per_task = df.groupby("task_name").resolved_bool.mean().sort_values(ascending=False)
out(f"Tasks with 100% resolve rate (universally easy): {(per_task == 1.0).sum()}")
out(f"Tasks with 0% resolve rate (universally hard): {(per_task == 0.0).sum()}")
out(f"Tasks with < 10% resolve: {(per_task < 0.1).sum()}")
out(f"Tasks with > 90% resolve: {(per_task > 0.9).sum()}")
out(f"\nTop-5 easiest:")
for t, v in per_task.head(5).items():
    out(f"  {t:<48} {v*100:>5.1f}%")
out(f"\nTop-5 hardest:")
for t, v in per_task.tail(5).items():
    out(f"  {t:<48} {v*100:>5.1f}%")
out(f"\nTask-level resolve rate variance: σ = {per_task.std()*100:.1f}pp")
out(f"Coefficient of variation: {per_task.std()/per_task.mean():.2f}")


# ════════════════════════════════════════════════════════════════════════════
# F11: Repo confounder
# ════════════════════════════════════════════════════════════════════════════
out("\n## F11 — Repo as confounder\n")

df["repo_full"] = df.task_name.map(REPOS_OF)
out("\nResolve rate by repo (all primitives × budgets × runs pooled):\n")
out("```")
out(f"{'repo':<32} {'n':>5} {'resolved':>9} {'resolve%':>9} {'mean steps':>11} {'mean tokens (k)':>16}")
for repo, grp in df.groupby("repo_full"):
    n = len(grp); res = grp.resolved_bool.sum()
    out(f"{repo:<32} {n:>5} {res:>9} {res/n*100:>8.1f}% "
        f"{grp.step_count.astype(float).mean():>11.1f} "
        f"{grp.total_tokens_consumed.astype(float).mean()/1000:>15.1f}")
out("```")

# Per-primitive-per-repo: does best primitive depend on repo?
out("\nPer-primitive resolve rate by repo at 15k:\n")
sub15 = df[df.token_budget == 15000]
piv = sub15.groupby(["primitive", "repo_full"]).resolved_bool.mean().unstack() * 100
out("```")
out(piv.round(0).to_string())
out("```")


# ════════════════════════════════════════════════════════════════════════════
# F13: Run number bias (run_num=1 vs run_num=2)
# ════════════════════════════════════════════════════════════════════════════
out("\n## F13 — Run-number bias (run_1 vs run_2)\n")

by_rn = df.groupby("run_num").resolved_bool.agg(["sum", "count", "mean"])
by_rn["pct"] = (by_rn["mean"]*100).round(1)
out(f"\nrun_num=1: {by_rn.loc[1, 'sum']}/{by_rn.loc[1, 'count']} = {by_rn.loc[1, 'pct']:.1f}%")
out(f"run_num=2: {by_rn.loc[2, 'sum']}/{by_rn.loc[2, 'count']} = {by_rn.loc[2, 'pct']:.1f}%")
out(f"Difference: {(by_rn.loc[1, 'mean'] - by_rn.loc[2, 'mean'])*100:+.1f}pp")
out("(if non-zero with high magnitude, indicates ordering effects in the runner)")


# ════════════════════════════════════════════════════════════════════════════
# F14: Task-selection provenance for the 100-task cohort
# ════════════════════════════════════════════════════════════════════════════
out("\n## F14 — Task-selection provenance\n")
out("Cohort = 30 ABL_TASKS (FC-stratified, original sprint) ∪ 70 P100_NEW_TASKS")
out("(scaled-up cohort, drawn from broader SWE-bench Verified at expansion time).")
out("")
out("**Implications:**")
out("- Original 30 tasks remain FC-biased (selected for FC ≥ 0.5, stratified on compression outcome).")
out("- 70 new tasks were added without the FC-success filter, so the 100-task cohort includes")
out("  genuinely FC-fail cases — paired comparisons against FC are now less FC-favored.")
out("- Result generalizes to: \"100-task SWE-bench Verified subset spanning django, scikit-learn, sympy\".")
out("- Does NOT generalize to: full SWE-bench Verified across all repos.")

# FC-succeeds split, by cohort
fc_per_task = df[df.primitive == "FC"].groupby("task_name").resolved_bool.mean()
fc_abl  = fc_per_task.loc[fc_per_task.index.isin(ABL_IDS)]
fc_new  = fc_per_task.loc[fc_per_task.index.isin(P100_NEW_IDS)]
out("\nFC-success split by cohort:")
out(f"  ABL_TASKS (n={len(fc_abl)}):    FC ≥ 1/2 runs = {(fc_abl >= 0.5).sum()}/{len(fc_abl)}, "
    f"FC = 0/2 = {(fc_abl == 0).sum()}/{len(fc_abl)}")
out(f"  P100_NEW (n={len(fc_new)}):     FC ≥ 1/2 runs = {(fc_new >= 0.5).sum()}/{len(fc_new)}, "
    f"FC = 0/2 = {(fc_new == 0).sum()}/{len(fc_new)}")


# ════════════════════════════════════════════════════════════════════════════
# Save report
# ════════════════════════════════════════════════════════════════════════════
REPORT.write_text("\n".join(report))
out(f"\n---\n\nReport written to {REPORT}")
