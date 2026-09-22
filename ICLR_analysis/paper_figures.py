"""The three main paper figures and their shared style, in one source file.

Run from the repo root (Python with numpy, pandas, matplotlib):
    venv/bin/python ICLR_analysis/paper_figures.py
    venv/bin/python ICLR_analysis/paper_figures.py --figure q2 --output-dir /tmp/figs
    venv/bin/python ICLR_analysis/paper_figures.py --help

Outputs (PDF + PNG, default ICLR_analysis/plots/q1):
    q1_20_o1_frontier, q1_21_o2_bill_latency,
    q2_qwen_task_map_and_endings

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
The Q1 exports come from q1_frontier.py and q1_step_factor.py; neither is
imported or run here. Q2 is computed directly, with no scratch-file inputs.
--figure q2 needs only the outcomes CSV and task list; Q1 needs only its exports.
--audit-dir optionally exports Q2 task order and all displayed numerical values.

Conventions:
* Q1 preserves the supplied task-bootstrap intervals. Success includes capped
  runs as unresolved; resource ratios use uncapped runs paired by task with FC.
  The billing metric is estimated billed INPUT cost, as in the selected plot.
* Q2 uses Qwen SWE main-track 15K, depth 0.5; FC/OTRC are budget-free references.
  Each policy must have exactly runs 1,2,3 on each of the 100 pinned tasks.
  Success requires >=2/3 resolved attempts; >=1500 s or missing verdict means
  unresolved. Both FC blocks show EVERY task, ordered by policy coverage then ID.
* Steps: successful attempts on tasks both policies solve, averaged within each
  task, then across paired tasks. Ratio of means, marginal 95% paired-task
  bootstrap (10,000 resamples, seed 210926 independently for each policy).
* Endings: FC-solved tasks lost by the policy. Purple requires >=2 unsuccessful
  step/time-limit attempts, teal >=2 submitted, explicitly failed evaluations;
  gray is the remainder. A missing verdict is never called a failed evaluation.
  These are observed memberships and endings, not causal or significance claims.

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
Q2 ending colors encode ending categories, not policy families. The task map
uses policy colors plus explicit symbols; consult labels as well as colors.
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
PAPER_STYLE = {
    "font.family": "DejaVu Sans", "font.size": 7.5, "axes.titlesize": 8,
    "axes.labelsize": 7.5, "xtick.labelsize": 7, "ytick.labelsize": 7,
    "legend.fontsize": 7, "axes.linewidth": 0.6, "pdf.fonttype": 42,
    "savefig.facecolor": "white",
}
Q2_STYLE = {**PAPER_STYLE, "font.size": 6}
MODELS = [("qwen35b", "Qwen", "o"), ("devstral24b", "Devstral", "^"), ("glm47flash", "GLM", "D")]
MK = {m: k for m, _, k in MODELS}
ORDER = ["TR", "TRC", "SU", "SU-p", "SS", "SS-p", "TRC+SU", "TRC+SS", "OTRC+TR", "OTRC+SU-p", "OTRC+SS-p", "OTRC"]
# Hue = policy family; shade = primitive; hollow = partial rewrite.
PDARK = {"rule": "#2171b5", "llm": "#d94801", "stack": "#238b45", "step": "#525252"}
PLIGHT = {"rule": "#6baed6", "llm": "#fd8d3c", "stack": "#74c476", "step": "#969696"}
PSTYLE = {"TR": ("rule", "d", False), "TRC": ("rule", "l", False),
          "SU": ("llm", "d", False), "SU-p": ("llm", "d", True), "SS": ("llm", "l", False), "SS-p": ("llm", "l", True),
          "TRC+SU": ("stack", "d", False), "TRC+SS": ("stack", "l", False),
          "OTRC+TR": ("step", "d", False), "OTRC+SU-p": ("step", "d", True), "OTRC+SS-p": ("step", "l", True),
          "OTRC": ("otrc", "d", True)}
def pcol(p):
    """Policy color shared by all three figures (FC is black)."""
    if p == "FC":
        return "#000000"
    g, shade, _ = PSTYLE[p]
    if g == "otrc":
        return "#000000"
    return PDARK[g] if shade == "d" else PLIGHT[g]


def pmark(ax, x, y, p, marker, s=22, force_hollow=False):
    """Draw a policy marker; marker shape encodes the model."""
    c = pcol(p)
    hollow = PSTYLE[p][2] or force_hollow
    if hollow:
        ax.scatter(x, y, marker=marker, s=s, facecolors="white", edgecolors=c,
                   linewidths=1.0, zorder=3)
    else:
        ax.scatter(x, y, marker=marker, s=s, color=c, edgecolors="#444444",
                   linewidths=0.3, zorder=3)


def prim_handles():
    h = []
    for p in ORDER:
        c = pcol(p); hollow = PSTYLE[p][2]
        h.append(Line2D([], [], marker="o", ls="", ms=4.5, mfc="white" if hollow else c, mec=c, mew=1.0 if hollow else 0.3, label=p))
    return h

def model_handles():
    return [Line2D([], [], marker=k, ls="", color="#555555", ms=5, label=n) for _, n, k in MODELS]



def save_figure(fig, output_dir, name, dpi=200):
    """Write a fixed-size PDF and PNG; preserve the selected layout margins."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    for suffix in ("pdf", "png"):
        fig.savefig(output_dir / f"{name}.{suffix}", dpi=dpi)


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


# Q2: reconstruct memberships, successful-run steps, and ending categories.
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
ENDING_COLORS = {"limit_losses": "#756bb1", "failed_eval_losses": "#5ab4ac",
                 "other_losses": "#d9d9d9"}


def load_q2_runs(outcomes_path, tasks_path):
    """Load the fixed main-track cohort, retaining missing verdicts as unresolved."""
    required = ["benchmark", "experiment_section", "model_key", "cell", "task_name",
                "run_num", "resolved", "exit_status", "step_count", "latency_e2e_s"]
    d = read_csv(outcomes_path, required)
    pinned = [row["instance_id"] for row in json.loads(tasks_path.read_text())]
    if len(pinned) != 100 or len(set(pinned)) != 100:
        raise ValueError("Q2 expects the pinned 100-task SWE cohort, with unique task IDs")
    d = d[d.benchmark.eq("swebench") & d.experiment_section.eq("main") &
          d.model_key.eq("qwen35b") & d.cell.isin(QWEN_CELLS) &
          d.task_name.isin(pinned) & d.run_num.isin([1, 2, 3])].copy()
    d = d.rename(columns={"task_name": "task", "run_num": "run"})
    d["policy"] = d.cell.map(QWEN_CELLS)
    expected = pd.MultiIndex.from_product([sorted(pinned), ROWS, [1, 2, 3]],
                                          names=["task", "policy", "run"])
    actual = pd.MultiIndex.from_frame(d[["task", "policy", "run"]])
    if actual.has_duplicates or len(expected.difference(actual)):
        raise ValueError("Q2 requires exactly three unique runs per task/policy (3900 rows)")
    verdict = d.resolved.astype("string").str.lower()
    if not (verdict.isna() | verdict.isin(["true", "false"])).all():
        raise ValueError("Q2 resolved values must be True, False, or missing")
    if not np.isfinite(d.latency_e2e_s.to_numpy(float)).all():
        raise ValueError("Q2 latency is missing/non-finite; cannot determine timeout flags")
    d["capped"] = d.latency_e2e_s.ge(1500)
    d["res"] = verdict.eq("true").fillna(False) & ~d.capped
    d["limit_failure"] = ~d.res & (d.capped | d.exit_status.eq("LimitsExceeded"))
    d["eval_failure"] = (~d.res & ~d.capped & d.exit_status.eq("Submitted") &
                           verdict.eq("false").fillna(False))
    successful_steps = d.loc[d.res, "step_count"].to_numpy(float)
    if not (np.isfinite(successful_steps) & (successful_steps > 0)).all():
        raise ValueError("Q2 successful attempts require positive, finite step counts")
    return d


def summarize_q2(d, resamples=10000, seed=210926):
    """Return task membership and paired statistics; resample tasks, not runs."""
    k = d.groupby(["task", "policy"]).res.sum().unstack().loc[:, ROWS].astype(int)
    solved = k.ge(2)
    limit_counts = d.groupby(["task", "policy"]).limit_failure.sum().unstack()
    eval_counts = d.groupby(["task", "policy"]).eval_failure.sum().unstack()
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
        limits = int(limit_counts.loc[lost, policy].ge(2).sum())
        evaluated = int(eval_counts.loc[lost, policy].ge(2).sum())
        other = int(lost.sum()) - limits - evaluated
        if other < 0 or int(solved[policy].sum()) != int(solved.FC.sum() + gained.sum() - lost.sum()):
            raise ValueError(f"{policy}: inconsistent task partition")
        rows.append(dict(policy=policy, cohort_tasks=len(k), fc_solved=int(solved.FC.sum()),
                         solved=int(solved[policy].sum()), gained=int(gained.sum()), lost=int(lost.sum()),
                         n_tasks=int(common.sum()), policy_steps=a.mean(), fc_steps=f.mean(),
                         policy_runs=int((d.res & d.task.isin(pairs.index) & d.policy.eq(policy)).sum()),
                         fc_runs=int((d.res & d.task.isin(pairs.index) & d.policy.eq("FC")).sum()),
                         ratio=a.mean()/f.mean(), ratio_lo=lo, ratio_hi=hi,
                         limit_losses=limits, failed_eval_losses=evaluated, other_losses=other))
    summary = pd.DataFrame(rows).set_index("policy")
    coverage = solved[ORDER].sum(axis=1)
    meta = pd.DataFrame({"fc": solved.FC, "coverage": coverage,
                         "task": solved.index}, index=solved.index).rename_axis("task_index")
    missed = meta[~meta.fc].sort_values(["coverage", "task"], ascending=[False, True]).index.tolist()
    shared = meta[meta.fc].sort_values(["coverage", "task"], ascending=[False, True]).index.tolist()
    return solved, summary, missed, shared


def fig_q2(solved, summary, missed, shared):
    """Return the compact Qwen figure, including ALL 100 pinned task columns."""
    steps = summary
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
    n_ax = fig.add_axes([.593,bottom,.045,height],sharey=totals)
    step_ax = fig.add_axes([.658,bottom,.152,height],sharey=totals)
    limit_ax = fig.add_axes([.858,bottom,.130,height],sharey=totals)
    map_axes = [totals,miss_ax,gain_ax,shared_ax,loss_ax]
    all_axes = map_axes+[n_ax,step_ax,limit_ax]

    fig.text(.144,.95,'(a) Qwen · SWE-bench',fontsize=7.2)
    fig.text(.592,.95,'(b) Execution and task losses',fontsize=7.2)
    map_handles = [Line2D([],[],marker='s',ls='',mfc='#525252',mec='none',ms=3.5,label='Solved'),
                   Line2D([],[],marker='x',ls='',color='#666666',ms=3.5,mew=.6,label='Lost'),
                   Patch(facecolor='#f4f4f4',edgecolor='#cccccc',lw=.3,label='Neither')]
    map_legend = fig.legend(handles=map_handles,ncol=3,loc='upper left',bbox_to_anchor=(.144,.923),
                           frameon=False,fontsize=5.9,handlelength=1.0,handletextpad=.3,columnspacing=.7,borderaxespad=0)
    right_handles = [Patch(facecolor=ENDING_COLORS['limit_losses'],edgecolor='none',label='Step/time limit'),
                     Patch(facecolor=ENDING_COLORS['failed_eval_losses'],edgecolor='none',label='Failed eval.'),
                     Patch(facecolor=ENDING_COLORS['other_losses'],edgecolor='#aaaaaa',lw=.3,label='Other')]
    right_legend = fig.legend(handles=right_handles,ncol=3,loc='upper left',bbox_to_anchor=(.592,.923),
                             frameon=False,fontsize=5.25,handlelength=1.0,handletextpad=.3,columnspacing=.6,borderaxespad=0)

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
    for ax in map_axes+[n_ax]:
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
    for ax in [totals,gain_ax,loss_ax,n_ax]:ax.set_xlim(0,1)
    headers = [(totals,'Solved'),(miss_ax,f'FC missed\n{len(missed)} tasks'),
               (gain_ax,'Gained'),(shared_ax,f'FC solved\n{len(shared)} tasks'),(loss_ax,'Lost'),
               (n_ax,'Shared\ntasks'),(step_ax,'Steps to solve\n95% CI'),(limit_ax,'How lost\ntasks end')]
    for ax,header in headers:
        ax.text(.5,1.025,header,transform=ax.transAxes,ha='center',va='bottom',fontsize=5.65)

    for j,p in enumerate(ORDER):
        r = steps.loc[p]
        mean,lo,hi = [(r[c]-1)*100 for c in ['ratio','ratio_lo','ratio_hi']]
        hollow = PSTYLE[p][2]
        step_ax.errorbar(mean,j,xerr=[[mean-lo],[hi-mean]],fmt='o',ms=3.1,color=pcol(p),
                         mfc='white' if hollow else pcol(p),mec=pcol(p),mew=.7,lw=.75,capsize=1.4,zorder=4)
        n_ax.text(.5,j,str(int(r.n_tasks)),ha='center',va='center',fontsize=5.9,color='#555555')
        lost = int(summary.loc[p,'lost'])
        limits = int(summary.loc[p,'limit_losses'])
        incorrect = int(summary.loc[p,'failed_eval_losses'])
        other = int(summary.loc[p,'other_losses'])
        running = 0
        for count,color,text_color in [(limits,ENDING_COLORS['limit_losses'],'white'),(incorrect,ENDING_COLORS['failed_eval_losses'],'#222222'),(other,ENDING_COLORS['other_losses'],'#444444')]:
            limit_ax.barh(j,count,left=running,height=.67,color=color,edgecolor='#999999',lw=.22,zorder=3)
            if count>=2:
                limit_ax.text(running+count/2,j,str(count),ha='center',va='center',fontsize=5.15,
                              color=text_color,zorder=4)
            running += count
        assert running == lost
        limit_ax.text(lost+.5,j,str(lost),ha='left',va='center',fontsize=5.6,color='#333333')
    n_ax.text(.5,len(ORDER),'—',ha='center',va='center',fontsize=6,color='#777777')
    step_ax.scatter(0,len(ORDER),marker='*',s=17,color='black',zorder=5)
    limit_ax.text(0,len(ORDER),'—',ha='left',va='center',fontsize=6,color='#777777')
    step_ax.set_xlim(-23,36)
    step_ax.set_xticks([-20,0,20],['−20','0','+20'])
    limit_ax.set_xlim(0,17)
    limit_ax.set_xticks([0,5,10,15],['0','5','10','15'])
    step_ax.axvline(0,color='#777777',ls='--',lw=.6,zorder=1)
    step_ax.set_xlabel('Change from FC (%)',fontsize=5.5,labelpad=2)
    limit_ax.set_xlabel('Tasks',fontsize=5.5,labelpad=2)
    for ax in [step_ax,limit_ax]:
        ax.spines[['top','right','left']].set_visible(False)
        ax.tick_params(axis='x',labelsize=5.4,length=2,pad=2)
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    boxes = [legend.get_window_extent(renderer) for legend in [map_legend,right_legend]]
    for b in boxes:assert b.x0>=0 and b.x1<=fig.bbox.width and b.y1<=fig.bbox.height
    assert boxes[0].x1<boxes[1].x0
    for ax in [step_ax,limit_ax]:
        assert ax.xaxis.label.get_window_extent(renderer).y0>=0
    for row in range(len(ROWS)):
        assert np.ptp([ax.transData.transform((0,row))[1] for ax in all_axes])<1e-6
    return fig


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--figure", choices=["all", "q1-o1", "q1-o2", "q2"], default="all")
    parser.add_argument("--data-dir", type=Path, default=ROOT / "ICLR_analysis")
    parser.add_argument("--outcomes", type=Path, default=ROOT / "analysis/outcomes/swebench_outcomes.csv")
    parser.add_argument("--tasks", type=Path, default=ROOT / "task_lists/p100_all_100_tasks.json")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "ICLR_analysis/plots/q1")
    parser.add_argument("--audit-dir", type=Path, help="Optional directory for Q2 values and task-order CSVs")
    parser.add_argument("--resamples", type=int, default=10000, help="Q2 paired-task bootstrap resamples")
    parser.add_argument("--seed", type=int, default=210926, help="Q2 bootstrap seed, reset for each policy")
    args = parser.parse_args()
    if args.resamples < 1000 or args.seed < 0:
        parser.error("Use at least 1000 bootstrap resamples and a non-negative seed")
    try:
        # Read/validate requested inputs before creating any figures.
        if args.figure in ["all", "q1-o1", "q1-o2"]:
            frontiers, factors = load_q1(args.data_dir, args.figure in ["all", "q1-o2"])
        if args.figure in ["all", "q2"]:
            d = load_q2_runs(args.outcomes, args.tasks)
            solved, summary, missed, shared = summarize_q2(d, args.resamples, args.seed)
        with plt.rc_context(PAPER_STYLE):
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
                fig = fig_q2(solved, summary, missed, shared)
                save_figure(fig, args.output_dir, "q2_qwen_task_map_and_endings", dpi=300)
                plt.close(fig)
            if args.audit_dir:
                args.audit_dir.mkdir(parents=True, exist_ok=True)
                summary.to_csv(args.audit_dir / "q2_plotted_values.csv")
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
