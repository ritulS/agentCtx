"""Paper Figures 2-5 from the re-evaluated verdicts.

Re-renders the four data figures of the selected plot bank
(Iclr_plot_bank.py: q1_24_qwen_overview, q1_26_knob_execution,
q2_qwen_task_map_only, q3_policy_preferences_and_design) with every input
recomputed from an outcomes table, by default the one carrying the
2026-09-23 Qwen main-track re-evaluation
(ICLR_results/ICLR_analysis/outcome/swebench_outcomes_reeval.csv, written by
analysis/apply_reeval_outcomes.py). Figure 1 (the introduction's policy-axes
sketch, intro_01_policy_axes) draws no data and is unaffected.

The plot bank itself reads existing analysis exports (q1_frontier_*.csv,
q1_knob_execution*.csv, plots/q3/q3_combined_*.csv) that were computed from
the raw records, whose `resolved` flags predate the re-evaluation. This
script recomputes those exports with the same definitions, taking `resolved`
from the outcomes table, and passes them to the unchanged drawing
functions:

  * Figure 2 (overview): q1_frontier.py statistics (paired task bootstrap vs
    FC, seed 0, B=5000, policies in q1_frontier order so the intervals
    reproduce the export bit for bit) plus the absolute resolve-rate
    intervals of paper_figures.load_qwen_overview (seed 210926, 10,000
    resamples). Per-run quantities come from appendix_knob_overview.load_runs
    (the token_cost_ledger port). SWE-bench on P100, Terminal-Bench on TB-40
    from --tb-outcomes (unchanged by the re-evaluation). Drawn by a revised
    copy of fig_qwen_overview: no "Qwen" heading, larger fonts and
    markers, black arrows marking the better direction of each axis, both
    axes include 0, no y=x guide in the third column, one benchmark heading
    per row instead of panel titles, and FC drawn as a black square instead
    of a star. In every figure this script draws, the OTRC family gets
    purple hues instead of greys (OTRC+TR blue-leaning purple, filled;
    OTRC+SU-p red-leaning purple and OTRC+SS-p light blue-leaning purple,
    hollow) so the members are not confused with each other or with
    hollow-black OTRC.
  * Figure 3 (tuning): q1_knob_execution.py cell statistics and the 45-cell
    resolve grid on ABL-25 (compression detector at 15% drop, seed 0, B=2000,
    completed-run cost/latency on the left, all-attempt table on the right).
    Drawn by Ritul's 2026-09-24 local revision of fig_knob_execution (larger
    fonts, yellow/green winner cells, oval lowest latency), carried here until
    it is committed, with the sweep x-axis labels shortened to "D" and
    "Threshold", compressions starting at 0, and billed input and latency
    shown as ratios to FC on a range around 1.
  * Figure 4 (task map): Iclr_plot_bank's own loader on the outcomes table,
    plus an 'Oracle' row directly above FC: a task counts as solved when
    any of the thirteen policies (twelve compression policies or FC)
    solves it (per-policy majority of three runs), i.e. the resolve
    reachable if the best policy were known per task. Gained is relative
    to FC like every other row; Lost is 0 by construction. The renderer is a copy of fig_task_map that takes
    the row list as a parameter.
  * Figure 5 (policy preferences): the Qwen SWE-bench policy values
    (resolve, latency and billed-input ratios = the Figure 2 statistics,
    ranks by average method) and the four Qwen SWE-bench design contrasts
    (paired task resolve-rate differences, one fresh stream per pair, seed
    0, B=2000) are recomputed; every other row (Devstral, GLM,
    Terminal-Bench) is copied unchanged from the audited exports in
    --q3-data-dir, which the re-evaluation does not touch. Drawn by the
    plot bank's fig_policy_preferences: panel (a) uses the Figure 3(c)
    table encoding (grey boxed triplets, yellow highest resolve, green lowest
    cost, oval lowest latency, bold winners) with black policy labels and no
    rank shading or rank colour bar, and the panel titles are "(a)" and
    "(b)" centred under each panel.

With --outcomes analysis/outcomes/swebench_outcomes.csv the recomputed
exports reproduce Ritul's q1_frontier_*.csv, q1_knob_execution*.csv and
q3_combined_*.csv to floating-point precision (validated 2026-09-24).

Outputs (default ICLR_analysis/plots/reeval/): the four figures as PNG
under the plot-bank filenames, plus every recomputed input:
q1_frontier_qwen35b.csv, q1_frontier_tb_qwen35b.csv,
q1_24_qwen_overview_values.csv, q1_knob_execution.csv,
q1_knob_execution_resolve_grid.csv, q2_task_map_counts.csv,
q3_combined_policy_values.csv, q3_combined_design_contrasts.csv.

Usage (from the repository root):
    venv/bin/python ICLR_analysis/paper_figures_reeval.py
    venv/bin/python ICLR_analysis/paper_figures_reeval.py --figure overview tuning
    venv/bin/python ICLR_analysis/paper_figures_reeval.py --outcomes analysis/outcomes/swebench_outcomes.csv \
        --output-dir /tmp/canonical      # reproduces the canonical exports
"""
from pathlib import Path
import argparse
import json

import numpy as np
import pandas as pd
import matplotlib
if __name__ == "__main__":
    matplotlib.use("Agg")
import matplotlib.pyplot as plt

try:
    from .plot_style import PAPER_STYLE, ORDER
    from .Iclr_plot_bank import (fig_qwen_overview, draw_overview_rows, overview_legend,
                                 overview_figure, fig_knob_execution, fig_task_map,
                                 draw_task_map, task_map_legend, fig_policy_preferences,
                                 ORACLE, TASK_MAP_ROWS, ROWS, DT)
    from .paper_figures import load_q2_runs
    from .appendix_knob_overview import (load_runs, budget_levels, panel_runs, read_tasks,
                                         raw_fields, fresh_cached, per_task, ratio_ci, diff_ci,
                                         SWE_TIMEOUT, MODEL_NAMES)
except ImportError:
    from plot_style import PAPER_STYLE, ORDER
    from Iclr_plot_bank import (fig_qwen_overview, draw_overview_rows, overview_legend,
                                overview_figure, fig_knob_execution, fig_task_map,
                                draw_task_map, task_map_legend, fig_policy_preferences,
                                ORACLE, TASK_MAP_ROWS, ROWS, DT)
    from paper_figures import load_q2_runs
    from appendix_knob_overview import (load_runs, budget_levels, panel_runs, read_tasks,
                                        raw_fields, fresh_cached, per_task, ratio_ci, diff_ci,
                                        SWE_TIMEOUT, MODEL_NAMES)

ROOT = Path(__file__).resolve().parent.parent
# The re-evaluated table: the local copy written by analysis/apply_reeval_outcomes.py
# when present, otherwise the canonical table, which carries the same
# re-evaluation since commit 397c232 (2026-09-24) and is tracked in git.
_REEVAL_COPY = ROOT / "ICLR_results/ICLR_analysis/outcome/swebench_outcomes_reeval.csv"
CANONICAL_OUTCOMES = ROOT / "analysis/outcomes/swebench_outcomes.csv"
REEVAL_OUTCOMES = _REEVAL_COPY if _REEVAL_COPY.is_file() else CANONICAL_OUTCOMES
TB_OUTCOMES = ROOT / "analysis/outcomes/terminalbench_outcomes_0924.csv"
Q3_DATA_DIR = ROOT / "ICLR_analysis/plots/q3"
OUTPUT_DIR = ROOT / "ICLR_analysis/plots/reeval"
FIGURES = {"overview": "q1_24_qwen_overview", "tuning": "q1_26_knob_execution",
           "task_map": "q2_qwen_task_map_only", "preferences": "q3_policy_preferences_and_design"}
# q1_frontier.py iterates policies in this order with one bootstrap stream.
Q1_ORDER = ["FC", "OTRC", "TR", "SU", "SU-p", "SS", "SS-p", "TRC", "TRC+SU", "TRC+SS",
            "OTRC+TR", "OTRC+SU-p", "OTRC+SS-p"]
Q3_MODELS = ["qwen35b", "devstral24b", "glm47flash"]
Q3_PAIRS = [("SS-p", "SS"), ("TRC+SS", "SS"), ("OTRC", "TRC"), ("OTRC+SS-p", "OTRC")]
Q3_METRICS = [("resolve", "resolve", False), ("latency_ratio", "time", True),
              ("billed_input_ratio", "bill", True)]


# ------------------------------------------------------------ Figure 2 inputs
def q1_frontier(df, B=5000, seed=0, resolve_resamples=10000, resolve_seed=210926):
    """q1_frontier.py statistics from one setting's attempts (panel_runs frame),
    plus load_qwen_overview's absolute resolve-rate intervals."""
    rng = np.random.default_rng(seed)
    R = per_task(df, "res", False)          # resolve uses all attempts
    U = per_task(df, "usage", True)
    C = per_task(df, "bill", True)
    L = per_task(df, "e2e", True)
    rows = []
    for p in Q1_ORDER:
        rr = diff_ci(R, p, B, rng) if p != "FC" else (0.0, 0.0, 0.0, int(R["FC"].notna().sum()))
        u = ratio_ci(U, p, B, rng); c = ratio_ci(C, p, B, rng); l = ratio_ci(L, p, B, rng)
        values = R[p].dropna().to_numpy()
        brng = np.random.default_rng(resolve_seed)
        idx = brng.integers(0, len(values), (resolve_resamples, len(values)))
        lo, hi = np.percentile(values[idx].mean(axis=1) * 100, [2.5, 97.5])
        rows.append(dict(policy=p, resolve=values.mean() * 100,
                         dres=rr[0], dres_lo=rr[1], dres_hi=rr[2],
                         usage=u[0], usage_lo=u[1], usage_hi=u[2],
                         bill=c[0], bill_lo=c[1], bill_hi=c[2],
                         time=l[0], time_lo=l[1], time_hi=l[2], n_shared=l[3],
                         resolve_lo=lo, resolve_hi=hi, n_success_tasks=len(values),
                         n_attempts=int(df.policy.eq(p).sum())))
    frame = pd.DataFrame(rows).set_index("policy")
    for metric in ("dres", "bill", "time", "usage", "resolve"):
        if not ((frame[metric + "_lo"] <= frame[metric] + 1e-12) &
                (frame[metric] <= frame[metric + "_hi"] + 1e-12)).all():
            raise ValueError(f"{metric}: interval does not enclose estimate")
    return frame.loc[["FC"] + ORDER]


def primary_setting(benchmark, model, outcomes_path):
    """All attempts of the primary setting (depth 0.5, primary threshold) on the
    full cohort: main-track cells, FC and OTRC as references."""
    runs, dropped = load_runs(benchmark, model, outcomes_path)
    budgets = budget_levels(runs)
    tasks, label = read_tasks(benchmark, "full")
    df = panel_runs(runs, tasks, 0.5, "primary", budgets)
    print(f"{benchmark}/{model}: {label}, primary budget {budgets['primary']}, "
          f"{len(df)} attempts ({dropped} dropped with <2 model calls)")
    return df


# ------------------------------------------------------------ Figure 3 inputs
def removed_tokens(P):
    """q1_knob_execution.removed: context removed by detected compressions."""
    tot = 0.0
    for t in range(1, len(P)):
        drop = P[t - 1] - P[t]
        if drop >= max(1000, 0.15 * P[t - 1]):
            tot += drop
    return tot


def knob_settings():
    """(track, cell, policy, sweep, x) in q1_knob_execution.load order, then the
    45-cell grid in load_resolve_grid order."""
    sweep = [("main", "di__binf__fc", "FC", "primary", 0.0)]
    for prim, pol in DT.items():
        for b in (10, 15, 20):
            sweep.append(("main" if b == 15 else "ablation", f"d05__b{b}k__{prim}", pol,
                          "primary" if b == 15 else "threshold", float(b)))
        for keep in (7, 3):
            sweep.append(("ablation", f"d{keep:02d}__b15k__{prim}", pol, "depth", (10 - keep) / 10))
    grid = [(pol, budget, depth, "main" if (budget, depth) == (15, .5) else "ablation",
             f"d{int(round(10 * (1 - depth))):02d}__b{budget}k__{prim}")
            for prim, pol in DT.items() for budget in (10, 15, 20) for depth in (.3, .5, .7)]
    grid.append(("FC", None, None, "main", "di__binf__fc"))
    return sweep, grid


def knob_cell(outcomes, raw, track, cell, tasks):
    """Per-attempt quantities of token_cost_ledger.per_run for one cell on
    ABL-25, runs 1-3, with `resolved` taken from the outcomes table."""
    g = outcomes[outcomes.experiment_section.eq(track) & outcomes.cell.eq(cell)]
    if len(g) != len(tasks) * 3 or not g.groupby("task_name").size().eq(3).all():
        raise ValueError(f"{track}/{cell}: expected {len(tasks) * 3} attempts, found {len(g)}")
    if g.duplicated(["task_name", "run_num"]).any():
        raise ValueError(f"{track}/{cell}: duplicate attempts")
    verdict = g.resolved.astype("string").str.lower()
    if not (verdict.isna() | verdict.isin(["true", "false"])).all():
        raise ValueError(f"{cell}: resolved must be True, False, or missing")
    rows = []
    for r, res in zip(g.itertuples(index=False), verdict.eq("true").fillna(False)):
        P = json.loads(r.step_prompt_tokens) if isinstance(r.step_prompt_tokens, str) else []
        if len(P) < 2:
            raise ValueError(f"{cell} {r.task_name} run {r.run_num}: fewer than two model calls")
        C = json.loads(r.step_completion_tokens) if isinstance(r.step_completion_tokens, str) else []
        totP, totC = float(r.total_prompt_tokens), float(r.total_completion_tokens)
        flagged, summP = raw[(r.source_file, r.task_name, int(r.run_num))]
        sumP = float(sum(P))
        if abs(totP - sumP - summP) > 1:
            raise ValueError(f"{cell} {r.task_name} run {r.run_num}: prompt accounting mismatch")
        Cbar = (float(sum(C)) if C else totC) / len(P)
        e2e = float(r.latency_e2e_s)
        if not np.isfinite(e2e):
            raise ValueError(f"{cell} {r.task_name} run {r.run_num}: missing latency")
        rows.append(dict(task=r.task_name, run=int(r.run_num), resolved=bool(res),
                         n_calls=len(P), sumP=sumP, summP=summP,
                         compression_events=int(r.compression_events), e2e=e2e,
                         capped=e2e >= SWE_TIMEOUT, R_hi=fresh_cached(P, flagged, Cbar),
                         removed=removed_tokens(P)))
    df = pd.DataFrame(rows)
    df["bill"] = df.R_hi + 0.1 * (df.sumP - df.R_hi) + df.summP
    return df


def knob_inputs(outcomes_path, B=2000, seed=0):
    """q1_knob_execution.csv and q1_knob_execution_resolve_grid.csv."""
    tasks, label = read_tasks("swebench", "ablation")
    d = pd.read_csv(outcomes_path, low_memory=False)
    d = d[d.benchmark.eq("swebench") & d.model_key.eq("qwen35b") & d.task_name.isin(tasks) &
          d.run_num.isin([1, 2, 3])].copy()
    sweep, grid = knob_settings()
    cells = {(track, cell) for track, cell, *_ in sweep} | {(track, cell) for _, _, _, track, cell in grid}
    d = d[[(t, c) in cells for t, c in zip(d.experiment_section, d.cell)]]
    raw = raw_fields(sorted(d.source_file.unique()))
    per_cell = {(track, cell): knob_cell(d, raw, track, cell, tasks) for track, cell in sorted(cells)}
    if not per_cell[("main", "di__binf__fc")].removed.eq(0).all():
        raise ValueError("compression detector fires on FC attempts")

    rng = np.random.default_rng(seed)

    def ci(v, task):
        m = pd.DataFrame({"v": v, "t": task}).groupby("t").v.mean().values
        bs = m[rng.integers(0, len(m), (B, len(m)))].mean(1)
        return np.percentile(bs, 2.5), np.percentile(bs, 97.5)

    rows = []
    for track, cell, pol, sweep_name, x in sweep:
        g = per_cell[(track, cell)]
        c = g[~g.capped]
        lo, hi = ci(g.n_calls.values, g.task.values)
        rlo, rhi = ci(g.resolved.values.astype(float), g.task.values)
        rows.append(dict(policy=pol, sweep=sweep_name, x=x, n=len(g),
                         events=g.compression_events.mean(), removed=g.removed.mean(),
                         calls=g.n_calls.mean(), calls_lo=lo, calls_hi=hi,
                         resolve_lo=rlo, resolve_hi=rhi,
                         bill=c.bill.mean(), e2e=c.e2e.mean(), n_completed=len(c),
                         capped=g.capped.mean(), stepcap=g.n_calls.ge(125).mean(),
                         resolve=g.resolved.mean()))
    S = pd.DataFrame(rows)

    records = []
    for pol, budget, depth, track, cell in grid:
        runs = per_cell[(track, cell)]
        success = runs.resolved
        completed = ~runs.capped
        records.append(dict(policy=pol, threshold_k=budget, depth_removed=depth, track=track, cell=cell,
                            n_attempts=len(runs), n_success=int(success.sum()), resolve=success.mean(),
                            events=runs.compression_events.mean(), n_completed=int(completed.sum()),
                            resolve_excl_time_caps=success[completed].mean(),
                            bill_all=runs.bill.mean(), bill_completed=runs.bill[completed].mean(),
                            latency_all=runs.e2e.mean(), latency_completed=runs.e2e[completed].mean()))
    resolve_grid = pd.DataFrame(records)
    fc_bill = resolve_grid.loc[resolve_grid.policy.eq("FC"), "bill_all"].iloc[0]
    resolve_grid["bill_vs_fc"] = resolve_grid.bill_all / fc_bill
    if len(resolve_grid) != 46 or resolve_grid.duplicated(["policy", "threshold_k", "depth_removed"]).any():
        raise ValueError("Knob grid must contain 45 distinct settings plus FC")
    print(f"tuning: {label}, {len(S)} sweep cells, {len(resolve_grid)} grid rows, "
          f"FC resolve {100 * S.loc[S.policy.eq('FC'), 'resolve'].iloc[0]:.1f}%")
    return S, resolve_grid


# ------------------------------------------------------------ Figure 5 inputs
def q3_inputs(frame, df, baseline_dir, model="qwen35b", B=2000, seed=0):
    """Qwen SWE-bench policy values and design contrasts recomputed from the
    outcomes table (the only Q3 rows the re-evaluation touches); every other
    row (Devstral, GLM, Terminal-Bench) copied from the audited exports."""
    values = pd.read_csv(baseline_dir / "q3_combined_policy_values.csv")
    contrasts = pd.read_csv(baseline_dir / "q3_combined_design_contrasts.csv")
    for name, table, keys in [("policy values", values, ["benchmark", "model_key", "policy", "metric"]),
                              ("design contrasts", contrasts, ["benchmark", "model_key", "p", "q"])]:
        if table.duplicated(keys).any():
            raise ValueError(f"Duplicate Q3 {name} in {baseline_dir}")
        if set(table.model_key) != set(Q3_MODELS) or set(table.benchmark) != {"SWE-bench", "Terminal-Bench"}:
            raise ValueError(f"Q3 {name} in {baseline_dir}: expected three models on both benchmarks")
    pol = ["FC"] + ORDER
    value_rows, contrast_rows = [], []
    for metric, col, ascending in Q3_METRICS:
        v = frame.loc[pol, col]
        rank = v.round(6).rank(ascending=ascending, method="average")
        for p in pol:
            # Resolve counts every task; the paired ratios count uncapped shared tasks.
            n_tasks = int(frame.loc[p, "n_success_tasks" if metric == "resolve" else "n_shared"])
            value_rows.append(dict(benchmark="SWE-bench", model_key=model, policy=p, metric=metric,
                                   value=float(v[p]), rank=float(rank[p]), n_tasks=n_tasks))
    R = per_task(df, "res", False)
    for p, q in Q3_PAIRS:
        m = R[[p, q]].dropna()
        d = ((m[p] - m[q]) * 100).to_numpy()
        rng = np.random.default_rng(seed)        # one fresh stream per pair
        boots = d[rng.integers(0, len(d), (B, len(d)))].mean(1)
        contrast_rows.append(dict(benchmark="SWE-bench", model_key=model, p=p, q=q,
                                  estimate=d.mean(), lo=np.percentile(boots, 2.5),
                                  hi=np.percentile(boots, 97.5), n_tasks=len(d),
                                  p_attempts=int(df.policy.eq(p).sum()),
                                  q_attempts=int(df.policy.eq(q).sum())))
    keep = lambda t: ~(t.benchmark.eq("SWE-bench") & t.model_key.eq(model))
    values = pd.concat([pd.DataFrame(value_rows), values[keep(values)]], ignore_index=True)
    contrasts = pd.concat([pd.DataFrame(contrast_rows), contrasts[keep(contrasts)]], ignore_index=True)
    return values, contrasts


# ------------------------------------------------------------ driver
def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--figure", nargs="+", choices=["all", *FIGURES], default=["all"])
    parser.add_argument("--outcomes", type=Path, default=REEVAL_OUTCOMES,
                        help="SWE-bench outcomes table (default: the re-evaluated copy)")
    parser.add_argument("--tb-outcomes", type=Path, default=TB_OUTCOMES)
    parser.add_argument("--tasks", type=Path, default=ROOT / "task_lists/p100_all_100_tasks.json")
    parser.add_argument("--q3-data-dir", type=Path, default=Q3_DATA_DIR,
                        help="audited Q3 exports; their Terminal-Bench rows are reused")
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args(argv)
    if not args.outcomes.is_file():
        parser.error(f"missing {args.outcomes}")
    selected = list(FIGURES) if "all" in args.figure else list(dict.fromkeys(args.figure))
    out = args.output_dir
    out.mkdir(parents=True, exist_ok=True)

    frames, settings = {}, {}
    if "overview" in selected or "preferences" in selected:
        settings["qwen35b"] = primary_setting("swebench", "qwen35b", args.outcomes)
        frames["qwen35b"] = q1_frontier(settings["qwen35b"])
        frames["qwen35b"].to_csv(out / "q1_frontier_qwen35b.csv")
    for name in selected:
        with plt.rc_context(PAPER_STYLE):
            if name == "overview":
                tb = q1_frontier(primary_setting("terminalbench", "qwen35b", args.tb_outcomes))
                tb.to_csv(out / "q1_frontier_tb_qwen35b.csv")
                overview = {"swebench": frames["qwen35b"], "terminalbench": tb}
                pd.concat(overview, names=["benchmark", "policy"]).to_csv(out / "q1_24_qwen_overview_values.csv")
                fig = fig_qwen_overview(overview)
            elif name == "tuning":
                S, grid = knob_inputs(args.outcomes)
                S.to_csv(out / "q1_knob_execution.csv", index=False)
                grid.to_csv(out / "q1_knob_execution_resolve_grid.csv", index=False)
                fig = fig_knob_execution(S, grid)
            elif name == "task_map":
                runs = load_q2_runs(args.outcomes, args.tasks)
                solved = runs.groupby(["task", "policy"]).res.sum().unstack().loc[:, ROWS].ge(2)
                solved[ORACLE] = solved[ROWS].any(axis=1)
                solved = solved.loc[:, TASK_MAP_ROWS]
                missed = sorted(solved.index[~solved.FC], key=lambda t: (-solved.loc[t, ORDER].sum(), t))
                shared = sorted(solved.index[solved.FC], key=lambda t: (-solved.loc[t, ORDER].sum(), t))
                counts = pd.DataFrame({"solved": solved.sum(),
                                       "gained": (~solved.FC.to_numpy()[:, None] & solved).sum(),
                                       "lost": (solved.FC.to_numpy()[:, None] & ~solved).sum()}).loc[TASK_MAP_ROWS]
                counts.index.name = "policy"
                counts.to_csv(out / "q2_task_map_counts.csv")
                print(f"task map: FC solved {int(solved.FC.sum())}/{len(solved)}; "
                      f"oracle over {len(ROWS)} policies solves {int(solved[ORACLE].sum())}; "
                      f"{len(missed)} FC-missed + {len(shared)} FC-solved columns")
                fig = fig_task_map(solved, missed, shared)
            else:
                values, contrasts = q3_inputs(frames["qwen35b"], settings["qwen35b"], args.q3_data_dir)
                values.to_csv(out / "q3_combined_policy_values.csv", index=False)
                contrasts.to_csv(out / "q3_combined_design_contrasts.csv", index=False)
                fig = fig_policy_preferences(values, contrasts)
            try:
                fig.savefig(out / f"{FIGURES[name]}.png", dpi=300 if name == "preferences" else 200)
            finally:
                plt.close(fig)
        print(f"Wrote {out / FIGURES[name]}.png", flush=True)


if __name__ == "__main__":
    main()
