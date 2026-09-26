"""The three main paper figures and their shared style, in one source file.

Run from the repo root (Python with numpy, pandas, matplotlib):
    venv/bin/python ICLR_analysis/paper_figures.py
    venv/bin/python ICLR_analysis/paper_figures.py --figure q2 --output-dir /tmp/figs
    venv/bin/python ICLR_analysis/paper_figures.py --figure q1-qwen-overview
    venv/bin/python ICLR_analysis/paper_figures.py --help

Outputs (PDF + PNG, default ICLR_analysis/plots/q1):
    q1_20_o1_frontier, q1_21_o2_bill_latency,
    q2_qwen_task_map_and_endings
The optional q1-qwen-overview target exports a wide 2x5 Qwen overview and
two 5.5-inch companion figures (token comparisons and success comparisons).
It also requires resolve, time_lo, time_hi in the Qwen frontier exports and
token_cost_ledger[_tb]_qwen35b.csv (policy, task, resolved) to bootstrap
absolute resolve-rate intervals. Paired difference intervals are not reused
as absolute resolve-rate intervals.

Data are read only and are NOT bundled in this plotting source. Supply the
following existing analysis exports locally, or via the CLI paths:
* --data-dir: q1_frontier[_tb]_<model>.csv for qwen35b, devstral24b,
  glm47flash. Required columns: policy, usage, time, dres, dres_lo,
  dres_hi, bill, bill_lo, bill_hi. FC plus all 12 policies are required.
* --data-dir: q1_step_factor.csv. Required columns: benchmark, model,
  policy, leg, steps, per_step, per_step_lo, per_step_hi. Uses SWE e2e rows.
* --outcomes: analysis/outcomes/swebench_outcomes.csv, exported by
  analysis/aggregate_benchmark_results.py. --tasks: the pinned P100 JSON,
  a list of objects with instance_id. See load_q2_runs for the CSV schema.
* --tb-outcomes: analysis/outcomes/terminalbench_outcomes.csv; --tb-tasks:
  task_lists/tbench_p40.json. Terminal-Bench censoring reads Harbor results
  beneath --run-root, falling back to CancelledError/empty exit status.
The Q1 exports come from q1_frontier.py and q1_step_factor.py; neither is
imported or run here. Q2 is computed directly, with no scratch-file inputs.
--figure q2 needs both benchmarks' outcomes and pinned task lists, plus Harbor
records where available; Q1 needs only its exports.
--audit-dir optionally exports Q2 task order and all displayed numerical values.

Conventions:
* Q1 preserves the supplied task-bootstrap intervals. Success includes capped
  runs as unresolved; resource ratios use uncapped runs paired by task with FC.
  The billing metric is estimated billed INPUT cost, as in the selected plot.
* Q2 uses Qwen main-track SWE 15K and Terminal-Bench 3K, depth 0.5;
  FC/OTRC are budget-free references.
  Each policy must have exactly runs 1,2,3 on every pinned task (100 SWE, 40 TB).
  Success requires >=2/3 resolved attempts; >=1500 s or missing verdict means
  unresolved. Both FC blocks show EVERY task, ordered by policy coverage then ID.
  Terminal-Bench uses TB-40 runs 1--3 and Harbor per-task timeout flags.
* Steps: successful attempts on tasks both policies solve, averaged within each
  task, then across paired tasks. Ratio of means, marginal 95% paired-task
  bootstrap (10,000 resamples, seed 210926 independently for each policy).
  The two step panels have different axis ranges. Each policy/benchmark uses
  its own shared-solved tasks; n reports their count. These selected subsets
  do not identify a causal effect of extra steps on failures.

Reuse the style without producing files or changing global rcParams on import:
    from pathlib import Path
    import matplotlib.pyplot as plt
    from ICLR_analysis.paper_figures import PAPER_STYLE, pcol, pmark, save_figure
    with plt.rc_context(PAPER_STYLE):
        fig, ax = plt.subplots(figsize=(5.5, 2.3))
        pmark(ax, 1.0, 0.8, "SU-p", "o")
        save_figure(fig, Path("my_plots"), "new_figure")

Style: 5.5 inch ICLR width; DejaVu Sans; embedded TrueType PDF fonts;
ColorBrewer blue=rule, orange=LLM, green=stacked, gray=step-triggered.
Shade distinguishes primitives; hollow markers denote partial rewrite;
OTRC is black/hollow. Model shapes: Qwen circle, Devstral triangle, GLM diamond.
The task map uses policy colors plus explicit symbols; consult labels as well
as colors. Its existing output filename is retained for paper references.
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
from matplotlib.colors import to_rgba
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

ROOT = Path(__file__).resolve().parent.parent
try:
    from .plot_style import (PAPER_STYLE, Q2_STYLE, MODELS, MK, ORDER, PDARK,
                             PLIGHT, PSTYLE, pcol, pmark, prim_handles,
                             model_handles, save_figure)
except ImportError:  # Direct script invocation.
    from plot_style import (PAPER_STYLE, Q2_STYLE, MODELS, MK, ORDER, PDARK,
                            PLIGHT, PSTYLE, pcol, pmark, prim_handles,
                            model_handles, save_figure)


def read_csv(path, required):
    """Fail explicitly on missing inputs/columns rather than drawing partial plots."""
    path = Path(path)
    if not path.is_file():
        raise ValueError(f"Missing input: {path}. See this script's data requirements.")
    frame = pd.read_csv(path, low_memory=False)
    missing = set(required) - set(frame.columns)
    if missing:
        raise ValueError(f"{path}: missing columns {sorted(missing)}")
    return frame


def load_q1(data_dir, need_steps):
    columns = ["policy", "usage", "time", "dres", "dres_lo", "dres_hi",
               "bill", "bill_lo", "bill_hi"]
    frontiers = {}
    for benchmark, tag in [("swebench", ""), ("terminalbench", "tb_")]:
        for model, _, _ in MODELS:
            path = data_dir / f"q1_frontier_{tag}{model}.csv"
            frame = read_csv(path, columns).set_index("policy", verify_integrity=True)
            if set(ORDER + ["FC"]) - set(frame.index):
                raise ValueError(f"{path}: expected FC and all 12 policies")
            frame = frame.loc[["FC"] + ORDER]
            if not np.isfinite(frame[columns[1:]].to_numpy(float)).all():
                raise ValueError(f"{path}: non-finite plotted values")
            for metric in ("dres", "bill"):
                if not ((frame[metric + "_lo"] <= frame[metric]) &
                        (frame[metric] <= frame[metric + "_hi"])).all():
                    raise ValueError(f"{path}: {metric} interval does not enclose estimate")
            frontiers[benchmark, model] = frame
    factors = None
    if need_steps:
        factors = read_csv(data_dir / "q1_step_factor.csv", [
            "benchmark", "model", "policy", "leg", "steps", "per_step",
            "per_step_lo", "per_step_hi"])
        factors = factors[factors.benchmark.eq("swebench") & factors.leg.eq("e2e")]
        factors = factors.set_index(["model", "policy"], verify_integrity=True)
        expected = pd.MultiIndex.from_product([[m for m, _, _ in MODELS], ORDER])
        if len(expected.difference(factors.index)):
            raise ValueError("q1_step_factor.csv: missing SWE e2e model/policy rows")
        factors = factors.loc[expected]
        cols = ["steps", "per_step", "per_step_lo", "per_step_hi"]
        if not np.isfinite(factors[cols].to_numpy(float)).all():
            raise ValueError("q1_step_factor.csv: non-finite plotted values")
        if not ((factors.per_step_lo <= factors.per_step) &
                (factors.per_step <= factors.per_step_hi)).all():
            raise ValueError("q1_step_factor.csv: interval does not enclose estimate")
    return frontiers, factors


# Q1: preserve the two selected figures' layouts, annotations, and encodings.
def fig_o1(frontiers):
    """Return the resolve-rate / resource-use figure from indexed summary tables."""
    fig, ax = plt.subplots(2, 2, figsize=(5.5, 3.5))
    for r, (bench, bname) in enumerate([("swebench", "SWE-bench"), ("terminalbench", "Terminal-Bench")]):
        F = {m: frontiers[bench, m] for m, _, _ in MODELS}
        for c, (leg, xlab) in enumerate([("usage", "token usage / full context"), ("time", "wall-clock / full context")]):
            a = ax[r, c]
            a.axhline(0, color="#999999", lw=0.6, ls="--", zorder=0)
            a.axvline(1, color="#999999", lw=0.6, ls="--", zorder=0)
            for m, _, _ in MODELS:
                f = F[m]
                for p in ORDER:
                    if p not in f.index: continue
                    q = f.loc[p]
                    a.errorbar(q[leg], q.dres, yerr=[[q.dres - q.dres_lo], [q.dres_hi - q.dres]],
                               fmt="none", ecolor="#dedede", elinewidth=0.5, capsize=0, zorder=1)
                    pmark(a, q[leg], q.dres, p, MK[m])
            a.scatter(1, 0, marker="*", s=90, color="black", zorder=5)
            a.set_title(f"{bname}, {'token usage' if leg == 'usage' else 'latency'}", loc="left", pad=3)
            if r == 1: a.set_xlabel(xlab)
            a.grid(alpha=0.2, lw=0.5)
            if c == 0: a.set_ylabel("success vs FC (pp)")
        # the two diagnostic pairs named in the prose (SWE row)
        if bench == "swebench":
            f = F["qwen35b"]; a = ax[0, 0]
            ys = [f.loc[p].dres for p in ["TRC", "TRC+SU", "SU"]]; xs = [f.loc[p].usage for p in ["TRC", "TRC+SU", "SU"]]
            xb = max(xs) + 0.03
            a.plot([xb, xb], [min(ys), max(ys)], color="#333333", lw=0.7)
            a.plot([xb - 0.008, xb], [min(ys)] * 2, color="#333333", lw=0.7); a.plot([xb - 0.008, xb], [max(ys)] * 2, color="#333333", lw=0.7)
            a.annotate("same tokens\nQwen TRC, TRC+SU, SU", xy=(xb, np.mean(ys)), xytext=(0.70, -21), fontsize=6.5,
                       ha="left", va="center", arrowprops=dict(arrowstyle="-", color="#999999", lw=0.5, shrinkB=2))
            f = F["devstral24b"]; a = ax[0, 1]
            xs = [f.loc[p].time for p in ["TR", "SS-p"]]; ys = [f.loc[p].dres for p in ["TR", "SS-p"]]
            yb = max(ys) + 4
            a.plot([min(xs), max(xs)], [yb, yb], color="#333333", lw=0.7)
            a.plot([min(xs)] * 2, [yb - 1, yb], color="#333333", lw=0.7); a.plot([max(xs)] * 2, [yb - 1, yb], color="#333333", lw=0.7)
            a.text(max(xs) + 0.03, yb, "Devstral TR, SS-p\nsame success", va="center", ha="left", fontsize=6.5)
    ax[0, 0].set_xlim(0.3, 1.06); ax[0, 1].set_xlim(0.72, 1.58)
    ax[1, 0].set_xlim(0.05, 1.06); ax[1, 1].set_xlim(0.9, 2.6)
    for r in range(2):
        lo = min(a.get_ylim()[0] for a in ax[r]); hi = max(a.get_ylim()[1] for a in ax[r])
        for a in ax[r]: a.set_ylim(lo, hi)
    # one legend, two rows of eight: models and FC first, then the primitives (matplotlib fills column-major)
    allh = model_handles() + [Line2D([], [], marker="*", ls="", color="black", ms=8, label="full context")] + prim_handles()
    row1, row2 = allh[:8], allh[8:]
    fig.legend(handles=[h for pair in zip(row1, row2) for h in pair], loc="upper center", ncol=8, frameon=False,
               handletextpad=0.2, columnspacing=0.8, fontsize=6, bbox_to_anchor=(0.5, 1.0))
    fig.tight_layout(rect=(0, 0, 1, 0.925), h_pad=0.6)
    return fig


def fig_o2_bill(frontiers, step_factors):
    """Compact 1x3: SWE and TB billing, then the original SWE latency factor panel.

    Reuses O1's primitive colors, model markers, and two-row shared legend.
    Billing panels share limits; gray shading denotes bills above full context.
    """
    S = step_factors
    fig = plt.figure(figsize=(5.5, 2.3))
    # The two billing panels share a y label and ticks, leaving more room for
    # the third panel's distinct y label without increasing the figure height.
    ax = [fig.add_axes([0.090, 0.185, 0.255, 0.575]),
          fig.add_axes([0.375, 0.185, 0.255, 0.575]),
          fig.add_axes([0.725, 0.185, 0.265, 0.575])]

    for i, (bench, bname) in enumerate([("swebench", "SWE-bench"), ("terminalbench", "Terminal-Bench")]):
        a = ax[i]
        a.axhspan(1, 1.6, color="#f1f1f1", zorder=-1)
        a.plot([0, 1.1], [0, 1.1], color="#999999", lw=0.6, ls=":", zorder=0)
        a.axhline(1, color="#999999", lw=0.6, ls="--", zorder=0)
        for m, _, k in MODELS:
            f = frontiers[bench, m]
            for p in ORDER:
                if p not in f.index: continue
                q = f.loc[p]
                a.errorbar(q.usage, q.bill, yerr=[[q.bill - q.bill_lo], [q.bill_hi - q.bill]],
                           fmt="none", ecolor="#e4e4e4", elinewidth=0.5, capsize=0, zorder=1)
                pmark(a, q.usage, q.bill, p, k, s=18)
        a.scatter(1, 1, marker="*", s=60, color="black", zorder=5)
        a.set_xlim(0.05, 1.08); a.set_ylim(0.3, 1.6); a.grid(alpha=0.2, lw=0.5)
        a.set_xticks([0.2, 0.6, 1.0]); a.set_yticks([0.5, 1.0, 1.5])
        a.set_xlabel("token usage / FC", labelpad=2)
        a.set_title(f"({chr(97 + i)}) {bname}", loc="left", pad=3)
        a.text(1.04, 1.565, "higher bill", fontsize=6, color="#777777", style="italic", ha="right", va="top")
    ax[0].set_ylabel("billed input cost / FC", labelpad=3)
    ax[1].tick_params(axis="y", labelleft=False)

    # Highlight the Qwen inversion, keeping the callout in the
    # empty shaded area and connecting the two actual plotted coordinates.
    a = ax[0]; f = frontiers["swebench", "qwen35b"]
    before, after = f.loc["TRC"], f.loc["OTRC+TR"]
    for p, q in [("TRC", before), ("OTRC+TR", after)]:
        a.scatter(q.usage, q.bill, marker=MK["qwen35b"], s=25, color=pcol(p),
                  edgecolors="#333333", linewidths=0.65, zorder=5)
    a.annotate("", xy=(after.usage, after.bill), xytext=(before.usage, before.bill),
               arrowprops=dict(arrowstyle="->", color="#333333", lw=0.85,
                               shrinkA=3, shrinkB=3), zorder=6)
    a.annotate("Qwen: TRC → OTRC+TR\nfewer tokens, higher bill",
               xy=(after.usage, after.bill), xytext=(0.105, 1.36), fontsize=6,
               ha="left", va="center", linespacing=1.4,
               arrowprops=dict(arrowstyle="-", color="#999999", lw=0.5, shrinkB=4))

    a = ax[2]
    xx = np.linspace(0.55, 1.45, 200); a.plot(xx, 1 / xx, color="#999999", lw=0.6, ls=":", zorder=0)
    a.axhline(1, color="#dddddd", lw=0.5, zorder=0); a.axvline(1, color="#dddddd", lw=0.5, zorder=0)
    for m, _, k in MODELS:
        for p in ORDER:
            if (m, p) not in S.index: continue
            q = S.loc[(m, p)]
            a.errorbar(q.steps, q.per_step, yerr=[[q.per_step - q.per_step_lo], [q.per_step_hi - q.per_step]],
                       fmt="none", ecolor="#e4e4e4", elinewidth=0.5, capsize=0, zorder=1)
            pmark(a, q.steps, q.per_step, p, k, s=18, force_hollow=(m == "glm47flash" and p in {"SU", "SS"}))
    a.scatter(1, 1, marker="*", s=60, color="black", zorder=5)
    a.set_xlim(0.62, 1.38); a.set_ylim(0.6, 1.9); a.grid(alpha=0.2, lw=0.5)
    a.set_xticks([0.8, 1.0, 1.2]); a.set_yticks([0.6, 1.0, 1.4, 1.8])
    a.set_xlabel("model calls / FC", labelpad=2); a.set_ylabel("seconds per call / FC", labelpad=3)
    a.set_title("(c) SWE-bench latency", loc="left", pad=3)
    a.text(0.78, 1 / 0.78 + 0.03, "same latency\nas FC", fontsize=5.5, color="#666666", ha="left", va="bottom")
    a.text(1.37, 1.86, "slower", fontsize=6, color="#666666", style="italic", ha="right", va="top")
    a.text(1.37, 0.62, "faster", fontsize=6, color="#666666", style="italic", ha="right", va="bottom")
    q = S.loc[("qwen35b", "OTRC+TR")]
    a.annotate("Qwen\nstep-triggered", xy=(q.steps, q.per_step), xytext=(0.80, 0.78), fontsize=5.5, ha="center",
               va="center", arrowprops=dict(arrowstyle="-", color="#999999", lw=0.5, shrinkB=4))
    q = S.loc[("devstral24b", "OTRC+TR")]
    a.annotate("Devstral\nstep-triggered", xy=(q.steps, q.per_step), xytext=(1.20, 1.55), fontsize=5.5, ha="center",
               va="center", arrowprops=dict(arrowstyle="-", color="#999999", lw=0.5, shrinkB=4))
    # Exactly the legend order, primitive encoding, and typography used by O1.
    allh = model_handles() + [Line2D([], [], marker="*", ls="", color="black", ms=8, label="full context")] + prim_handles()
    row1, row2 = allh[:8], allh[8:]
    fig.legend(handles=[h for pair in zip(row1, row2) for h in pair], loc="upper center", ncol=8, frameon=False,
               handletextpad=0.2, columnspacing=0.8, fontsize=6, bbox_to_anchor=(0.5, 1.0))
    return fig


def load_qwen_overview(data_dir, resamples=10000, seed=210926):
    """Preserve Q1 estimates and add genuine absolute-success intervals."""
    frames = {}
    columns = ["policy", "resolve", "dres", "dres_lo", "dres_hi", "usage",
               "bill", "bill_lo", "bill_hi", "time", "time_lo", "time_hi"]
    for benchmark, tag in [("swebench", ""), ("terminalbench", "tb_")]:
        path = data_dir / f"q1_frontier_{tag}qwen35b.csv"
        frame = read_csv(path, columns).set_index("policy", verify_integrity=True)
        missing = set(["FC"] + ORDER) - set(frame.index)
        if missing:
            raise ValueError(f"{path}: missing policies {sorted(missing)}")
        frame = frame.loc[["FC"] + ORDER].copy()
        if not np.isfinite(frame[columns[1:]].to_numpy(float)).all():
            raise ValueError(f"{path}: non-finite plotted values")
        for metric in ["dres", "bill", "time"]:
            if not ((frame[metric + "_lo"] <= frame[metric]) &
                    (frame[metric] <= frame[metric + "_hi"])).all():
                raise ValueError(f"{path}: invalid {metric} intervals")

        ledger_path = data_dir / f"token_cost_ledger_{tag}qwen35b.csv"
        ledger = read_csv(ledger_path, ["policy", "task", "resolved"])
        if ledger.resolved.isna().any() or not ledger.resolved.isin([True, False, 0, 1]).all():
            raise ValueError(f"{ledger_path}: resolved must contain nonmissing boolean values")
        ledger["success"] = ledger.resolved.astype(float)
        for policy in frame.index:
            values = ledger[ledger.policy.eq(policy)].groupby("task").success.mean().to_numpy()
            if not len(values) or not np.isclose(values.mean() * 100, frame.loc[policy, "resolve"], atol=1e-6):
                raise ValueError(f"{ledger_path}: {policy} success differs from {path.name}; use matched exports")
            # All runs, including capped runs as unresolved, as in q1_frontier.
            rng = np.random.default_rng(seed)
            idx = rng.integers(0, len(values), (resamples, len(values)))
            lo, hi = np.percentile(values[idx].mean(axis=1) * 100, [2.5, 97.5])
            frame.loc[policy, "resolve_lo"] = lo
            frame.loc[policy, "resolve_hi"] = hi
            frame.loc[policy, "n_success_tasks"] = len(values)
        frames[benchmark] = frame
    return frames


def fig_qwen_overview(frames, columns=(0, 1, 2, 3, 4)):
    """Compatibility entry point; selected figure code lives in the plot bank."""
    try:
        from .Iclr_plot_bank import fig_qwen_overview as draw
    except ImportError:
        from Iclr_plot_bank import fig_qwen_overview as draw
    return draw(frames, columns)


# Q2: reconstruct memberships and successful-run steps on shared solved tasks.
QWEN_CELLS = {
    "d05__b15k__tr": "TR", "di__b15k__trc": "TRC",
    "d05__b15k__su-full": "SU", "d05__b15k__su-partial": "SU-p",
    "d05__b15k__ss": "SS", "d05__b15k__ss-partial": "SS-p",
    "di__b15k__trc-su": "TRC+SU", "di__b15k__trc-ss": "TRC+SS",
    "di__b15k__otrc-tr": "OTRC+TR", "di__b15k__otrc-su-partial": "OTRC+SU-p",
    "di__b15k__otrc-ss-partial": "OTRC+SS-p",
    "di__binf__otrc": "OTRC", "di__binf__fc": "FC",
}
ROWS = ORDER + ["FC"]


def load_q2_runs(outcomes_path, tasks_path, benchmark="swebench", run_root=ROOT):
    """Load the fixed main-track cohort, retaining missing verdicts as unresolved."""
    required = ["benchmark", "experiment_section", "model_key", "cell", "task_name",
                "run_num", "resolved", "exit_status", "step_count", "latency_e2e_s"]
    is_tb = benchmark == "terminalbench"
    if is_tb:
        required += ["source_file", "condition"]
    d = read_csv(outcomes_path, required)
    manifest = json.loads(tasks_path.read_text())
    pinned = manifest["tasks"] if is_tb else [row["instance_id"] for row in manifest]
    n_tasks = 40 if is_tb else 100
    if len(pinned) != n_tasks or len(set(pinned)) != n_tasks:
        raise ValueError(f"Q2 expects the pinned {n_tasks}-task {benchmark} cohort")
    cells = {cell.replace("b15k", "b3k") if is_tb else cell: policy
             for cell, policy in QWEN_CELLS.items()}
    d = d[d.benchmark.eq(benchmark) & d.experiment_section.eq("main") &
          d.model_key.eq("qwen35b") & d.cell.isin(cells) &
          d.task_name.isin(pinned) & d.run_num.isin([1, 2, 3])].copy()
    d = d.rename(columns={"task_name": "task", "run_num": "run"})
    d["policy"] = d.cell.map(cells)
    expected = pd.MultiIndex.from_product([sorted(pinned), ROWS, [1, 2, 3]],
                                          names=["task", "policy", "run"])
    actual = pd.MultiIndex.from_frame(d[["task", "policy", "run"]])
    if actual.has_duplicates or len(expected.difference(actual)):
        raise ValueError(f"Q2 requires exactly three unique runs per task/policy ({n_tasks*39} rows)")
    verdict = d.resolved.astype("string").str.lower()
    if not (verdict.isna() | verdict.isin(["true", "false"])).all():
        raise ValueError("Q2 resolved values must be True, False, or missing")
    if is_tb:
        caps = []
        for row in d.itertuples():
            path = (run_root / Path(row.source_file).parent / row.task /
                    row.condition / f"run_{int(row.run)}" / "harbor_result.json")
            info = {}
            if path.is_file():
                info = json.loads(path.read_text()).get("exception_info") or {}
            status = "" if pd.isna(row.exit_status) else row.exit_status
            caps.append(info.get("exception_type") == "AgentTimeoutError" if info
                        else status in ("CancelledError", ""))
        d["capped"] = caps
    else:
        if not np.isfinite(d.latency_e2e_s.to_numpy(float)).all():
            raise ValueError("Q2 latency is missing/non-finite; cannot determine timeout flags")
        d["capped"] = d.latency_e2e_s.ge(1500)
    d["res"] = verdict.eq("true").fillna(False) & ~d.capped
    successful_steps = d.loc[d.res, "step_count"].to_numpy(float)
    if not (np.isfinite(successful_steps) & (successful_steps > 0)).all():
        raise ValueError("Q2 successful attempts require positive, finite step counts")
    return d


def summarize_q2(d, resamples=10000, seed=210926):
    """Return task membership and paired statistics; resample tasks, not runs."""
    k = d.groupby(["task", "policy"]).res.sum().unstack().loc[:, ROWS].astype(int)
    solved = k.ge(2)
    means = d[d.res].groupby(["task", "policy"]).step_count.mean().unstack()
    rows = []
    for policy in ORDER:
        common = solved.FC & solved[policy]
        gained = ~solved.FC & solved[policy]
        lost = solved.FC & ~solved[policy]
        pairs = means.loc[common, [policy, "FC"]]
        if pairs.empty or pairs.isna().any().any():
            raise ValueError(f"{policy}: no complete successful-run step pairs")
        a, f = pairs[policy].to_numpy(), pairs.FC.to_numpy()
        # Reset per policy so adding another plot/policy never changes existing CIs.
        rng = np.random.default_rng(seed)
        ix = rng.integers(0, len(pairs), (resamples, len(pairs)))
        boots = a[ix].mean(axis=1) / f[ix].mean(axis=1)
        lo, hi = np.quantile(boots, [.025, .975])
        if int(solved[policy].sum()) != int(solved.FC.sum() + gained.sum() - lost.sum()):
            raise ValueError(f"{policy}: inconsistent task partition")
        rows.append(dict(policy=policy, cohort_tasks=len(k), fc_solved=int(solved.FC.sum()),
                         solved=int(solved[policy].sum()), gained=int(gained.sum()), lost=int(lost.sum()),
                         n_tasks=int(common.sum()), policy_steps=a.mean(), fc_steps=f.mean(),
                         policy_runs=int((d.res & d.task.isin(pairs.index) & d.policy.eq(policy)).sum()),
                         fc_runs=int((d.res & d.task.isin(pairs.index) & d.policy.eq("FC")).sum()),
                         ratio=a.mean()/f.mean(), ratio_lo=lo, ratio_hi=hi))
    summary = pd.DataFrame(rows).set_index("policy")
    coverage = solved[ORDER].sum(axis=1)
    meta = pd.DataFrame({"fc": solved.FC, "coverage": coverage,
                         "task": solved.index}, index=solved.index).rename_axis("task_index")
    missed = meta[~meta.fc].sort_values(["coverage", "task"], ascending=[False, True]).index.tolist()
    shared = meta[meta.fc].sort_values(["coverage", "task"], ascending=[False, True]).index.tolist()
    return solved, summary, missed, shared


def fig_q2(solved, summary, missed, shared, tb_summary):
    """Qwen SWE task map, then paired successful steps on SWE and Terminal-Bench."""
    n_tasks = len(solved)
    fig = plt.figure(figsize=(5.5,2.25))
    bottom, height = .17, .58
    totals = fig.add_axes([.144,bottom,.044,height])
    cell_width = .217 / n_tasks
    missed_width, solved_width = len(missed)*cell_width, len(shared)*cell_width
    miss_ax = fig.add_axes([.208,bottom,missed_width,height],sharey=totals)
    gain_left = .208 + missed_width + .016
    gain_ax = fig.add_axes([gain_left,bottom,.042,height],sharey=totals)
    shared_ax = fig.add_axes([gain_left+.061,bottom,solved_width,height],sharey=totals)
    loss_ax = fig.add_axes([.518,bottom,.037,height],sharey=totals)
    n_ax = fig.add_axes([.580,bottom,.031,height],sharey=totals)
    step_ax = fig.add_axes([.630,bottom,.145,height],sharey=totals)
    tb_n_ax = fig.add_axes([.801,bottom,.031,height],sharey=totals)
    tb_step_ax = fig.add_axes([.849,bottom,.139,height],sharey=totals)
    map_axes = [totals,miss_ax,gain_ax,shared_ax,loss_ax]
    all_axes = map_axes+[n_ax,step_ax,tb_n_ax,tb_step_ax]

    fig.text(.144,.95,'(a) Qwen · SWE-bench',fontsize=7.2)
    fig.text(.580,.95,'(b) Steps to solve · Qwen',fontsize=7.2)
    map_handles = [Line2D([],[],marker='s',ls='',mfc='#525252',mec='none',ms=3.5,label='Solved'),
                   Line2D([],[],marker='x',ls='',color='#666666',ms=3.5,mew=.6,label='Lost'),
                   Patch(facecolor='#f4f4f4',edgecolor='#cccccc',lw=.3,label='Neither')]
    map_legend = fig.legend(handles=map_handles,ncol=3,loc='upper left',bbox_to_anchor=(.144,.923),
                           frameon=False,fontsize=5.9,handlelength=1.0,handletextpad=.3,columnspacing=.7,borderaxespad=0)
    right_handles = [Line2D([],[],marker='o',ms=2.5,color='#666666',lw=.7,
                            label='95% CI; n = shared solved tasks')]
    right_legend = fig.legend(handles=right_handles,ncol=1,loc='upper left',bbox_to_anchor=(.580,.923),
                             frameon=False,fontsize=5.25,handlelength=1.5,handletextpad=.4,borderaxespad=0)

    for ax,tasks,is_missed in [(miss_ax,missed,True),(shared_ax,shared,False)]:
        pixels = np.ones((len(ROWS),len(tasks),4))
        for j,p in enumerate(ROWS):
            for i,t in enumerate(tasks):
                if solved.loc[t,p]:pixels[j,i] = to_rgba(pcol(p))
                elif is_missed:pixels[j,i] = to_rgba('#f4f4f4')
        ax.imshow(pixels,interpolation='nearest',aspect='auto',extent=[-.5,len(tasks)-.5,len(ROWS)-.5,-.5])
        for x in np.arange(-.5,len(tasks)):ax.axvline(x,color='white',alpha=.45,lw=.18,zorder=2)
        for y in np.arange(.5,len(ROWS)):ax.axhline(y,color='white',lw=.55,zorder=3)
        ax.set_xlim(-.5,len(tasks)-.5)
    for j,p in enumerate(ROWS):
        lost = [i for i,t in enumerate(shared) if not solved.loc[t,p]]
        shared_ax.scatter(lost,[j]*len(lost),marker='x',s=4,color='#666666',linewidths=.4,zorder=4)
        hollow = p!='FC' and PSTYLE[p][2]
        totals.scatter(-.15,j,s=15 if p=='FC' else 10,marker='*' if p=='FC' else 'o',
                       facecolors='white' if hollow else pcol(p),edgecolors=pcol(p),linewidths=.8,
                       clip_on=False,transform=totals.get_yaxis_transform(),zorder=5)
        count = int(solved[p].sum())
        if count>solved.FC.sum():totals.axhspan(j-.44,j+.44,xmin=.02,xmax=.98,facecolor='#eaf2e5',edgecolor='none')
        totals.text(.5,j,str(count),ha='center',va='center',fontsize=6.2,
                    fontweight='bold' if count>solved.FC.sum() else 'normal',color='#333333')
        gain = int((~solved.FC&solved[p]).sum())
        loss = int((solved.FC&~solved[p]).sum())
        gain_ax.text(.5,j,f'+{gain}',ha='center',va='center',fontsize=6.2,color='#333333')
        loss_ax.text(.5,j,f'−{loss}' if loss else '0',ha='center',va='center',fontsize=6.2,color='#333333')
    for ax in map_axes+[n_ax,tb_n_ax]:
        ax.set_xticks([])
        for spine in ax.spines.values():spine.set_visible(False)
    for ax in all_axes:
        if ax is not totals:ax.tick_params(axis='y',left=False,labelleft=False)
        for boundary in [1.5,5.5,7.5,10.5,11.5]:
            ax.axhline(boundary,color='white' if ax in [miss_ax,shared_ax] else '#e5e5e5',
                       lw=1.4 if ax in [miss_ax,shared_ax] else .35,zorder=3 if ax in [miss_ax,shared_ax] else 0)
    totals.set_ylim(len(ROWS)-.4,-.6)
    totals.set_yticks(np.arange(len(ROWS)),ROWS)
    totals.tick_params(axis='y',length=0,pad=11,labelsize=6.1)
    for ax in [totals,gain_ax,loss_ax,n_ax,tb_n_ax]:ax.set_xlim(0,1)
    headers = [(totals,'Solved'),(miss_ax,f'FC missed\n{len(missed)} tasks'),
               (gain_ax,'Gained'),(shared_ax,f'FC solved\n{len(shared)} tasks'),(loss_ax,'Lost'),
               (n_ax,'n'),(step_ax,'SWE-bench'),(tb_n_ax,'n'),(tb_step_ax,'Terminal-Bench')]
    for ax,header in headers:
        ax.text(.5,1.025,header,transform=ax.transAxes,ha='center',va='bottom',fontsize=5.65)

    for ax,counts,table in [(step_ax,n_ax,summary),(tb_step_ax,tb_n_ax,tb_summary)]:
        for j,p in enumerate(ORDER):
            r = table.loc[p]
            mean,lo,hi = [(r[c]-1)*100 for c in ['ratio','ratio_lo','ratio_hi']]
            hollow = PSTYLE[p][2]
            ax.errorbar(mean,j,xerr=[[mean-lo],[hi-mean]],fmt='o',ms=3.1,color=pcol(p),
                        mfc='white' if hollow else pcol(p),mec=pcol(p),mew=.7,lw=.75,capsize=1.4,zorder=4)
            counts.text(.5,j,str(int(r.n_tasks)),ha='center',va='center',fontsize=5.9,color='#555555')
        counts.text(.5,len(ORDER),'—',ha='center',va='center',fontsize=6,color='#777777')
        ax.scatter(0,len(ORDER),marker='*',s=17,color='black',zorder=5)
        ax.axvline(0,color='#777777',ls='--',lw=.6,zorder=1)
        ax.set_xlabel('Change from FC (%)',fontsize=5.0,labelpad=2)
    step_ax.set_xlim(-23,36)
    step_ax.set_xticks([-20,0,20],['−20','0','+20'])
    tb_step_ax.set_xlim(-40,360)
    tb_step_ax.set_xticks([0,150,300],['0','+150','+300'])
    for ax in [step_ax,tb_step_ax]:
        ax.spines[['top','right','left']].set_visible(False)
        ax.tick_params(axis='x',labelsize=5.4,length=2,pad=2)
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    boxes = [legend.get_window_extent(renderer) for legend in [map_legend,right_legend]]
    for b in boxes:assert b.x0>=0 and b.x1<=fig.bbox.width and b.y1<=fig.bbox.height
    assert boxes[0].x1<boxes[1].x0
    for ax in [step_ax,tb_step_ax]:
        assert ax.xaxis.label.get_window_extent(renderer).y0>=0
    for row in range(len(ROWS)):
        assert np.ptp([ax.transData.transform((0,row))[1] for ax in all_axes])<1e-6
    return fig


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--figure", choices=["all", "q1-o1", "q1-o2", "q1-qwen-overview", "q2"], default="all")
    parser.add_argument("--data-dir", type=Path, default=ROOT / "ICLR_analysis")
    parser.add_argument("--outcomes", type=Path, default=ROOT / "analysis/outcomes/swebench_outcomes.csv")
    parser.add_argument("--tasks", type=Path, default=ROOT / "task_lists/p100_all_100_tasks.json")
    parser.add_argument("--tb-outcomes", type=Path, default=ROOT / "analysis/outcomes/terminalbench_outcomes.csv")
    parser.add_argument("--tb-tasks", type=Path, default=ROOT / "task_lists/tbench_p40.json")
    parser.add_argument("--run-root", type=Path, default=ROOT, help="Root for outcome source_file paths and Harbor records")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "ICLR_analysis/plots/q1")
    parser.add_argument("--audit-dir", type=Path, help="Optional directory for Q2 values and task-order CSVs")
    parser.add_argument("--resamples", type=int, default=10000, help="Q2 and Qwen overview task-bootstrap resamples")
    parser.add_argument("--seed", type=int, default=210926, help="Bootstrap seed, reset for each policy")
    args = parser.parse_args()
    if args.resamples < 1000 or args.seed < 0:
        parser.error("Use at least 1000 bootstrap resamples and a non-negative seed")
    try:
        # Read/validate requested inputs before creating any figures.
        if args.figure in ["all", "q1-o1", "q1-o2"]:
            frontiers, factors = load_q1(args.data_dir, args.figure in ["all", "q1-o2"])
        if args.figure == "q1-qwen-overview":
            overview = load_qwen_overview(args.data_dir, args.resamples, args.seed)
        if args.figure in ["all", "q2"]:
            d = load_q2_runs(args.outcomes, args.tasks)
            solved, summary, missed, shared = summarize_q2(d, args.resamples, args.seed)
            tb = load_q2_runs(args.tb_outcomes, args.tb_tasks, "terminalbench", args.run_root)
            _, tb_summary, _, _ = summarize_q2(tb, args.resamples, args.seed)
        with plt.rc_context(PAPER_STYLE):
            if args.figure == "q1-qwen-overview":
                for columns, suffix in [((0, 1, 2, 3, 4), ""), ((0, 1, 2), "_tokens"), ((3, 4), "_success")]:
                    fig = fig_qwen_overview(overview, columns)
                    save_figure(fig, args.output_dir, "q1_24_qwen_overview" + suffix)
                    plt.close(fig)
                if args.audit_dir:
                    args.audit_dir.mkdir(parents=True, exist_ok=True)
                    pd.concat(overview, names=["benchmark", "policy"]).to_csv(args.audit_dir / "q1_24_qwen_overview_values.csv")
            if args.figure in ["all", "q1-o1"]:
                fig = fig_o1(frontiers)
                save_figure(fig, args.output_dir, "q1_20_o1_frontier")
                plt.close(fig)
            if args.figure in ["all", "q1-o2"]:
                fig = fig_o2_bill(frontiers, factors)
                save_figure(fig, args.output_dir, "q1_21_o2_bill_latency")
                plt.close(fig)
        if args.figure in ["all", "q2"]:
            with plt.rc_context(Q2_STYLE):
                fig = fig_q2(solved, summary, missed, shared, tb_summary)
                save_figure(fig, args.output_dir, "q2_qwen_task_map_and_endings", dpi=300)
                plt.close(fig)
            if args.audit_dir:
                args.audit_dir.mkdir(parents=True, exist_ok=True)
                summary.to_csv(args.audit_dir / "q2_plotted_values.csv")
                tb_summary.to_csv(args.audit_dir / "q2_tb_plotted_values.csv")
                task_order = pd.DataFrame({"task": missed + shared,
                                           "block": ["FC missed"]*len(missed) + ["FC solved"]*len(shared)})
                task_order.to_csv(args.audit_dir / "q2_task_order.csv", index=False)
            print(f"Q2: {len(missed)} FC-missed + {len(shared)} FC-solved task columns; "
                  "majority >=2/3, capped and missing verdicts unresolved.")
        print(f"Wrote {args.figure} figures (PDF + PNG) to {args.output_dir}")
    except (OSError, ValueError, KeyError) as exc:
        parser.exit(2, f"Input/plot error: {exc}\n")


if __name__ == "__main__":
    main()
