# Selected ICLR plot bank

Run from the repository root:

```bash
venv/bin/python ICLR_analysis/Iclr_plot_bank.py
venv/bin/python ICLR_analysis/Iclr_plot_bank.py --list
venv/bin/python ICLR_analysis/Iclr_plot_bank.py --figure intro_01_policy_axes_wrap
venv/bin/python ICLR_analysis/Iclr_plot_bank.py --figure q1_26_knob_execution
venv/bin/python ICLR_analysis/Iclr_plot_bank.py --output-dir /tmp/paper-plots
```

`--figure` accepts multiple names. The default generates exactly the five
selected figures as PDF and PNG, preserving their current filenames and
setup/q1/q3 directories. Q2 remains in q1 for compatibility with existing references.
The bank owns the four results renderers and reuses the intro renderer from
`intro_fig.py`. Older overview and knob
entry points delegate to it. Importing the bank does not render or write files.

## Shared style guide

Edit `plot_style.py` for shared fonts, policy colors, model markers, and export
settings. All selected renderers and `paper_figures.py` use that module.
Use `plt.rc_context(PAPER_STYLE)`; never update global rcParams on import.

- DejaVu Sans, embedded TrueType PDF fonts (type 42), white export background.
- Blue: rule primitives; orange: summarization; green: stacked policies;
  gray: online policies. Shade distinguishes primitives within a family.
- Partial rewrites use hollow markers; in sweep curves they also use dashed
  lines. Model shapes are Qwen circle, Devstral triangle, GLM diamond.
- FC is black, with a star in overview/task-map markers; sweep references are
  neutral dotted lines. OTRC is black and hollow.
- Preserve selected figure sizes: overview 11 × 4.7 inches; knob execution
  12.8 × 5.8; task map 5.5 × 2.25; preferences/design 6.75 × 2.25.
  Dense layouts retain their explicit label sizes; `KNOB_STYLE` holds its
  larger typography. Review at the intended paper placement size.
- Knob-table primitive labels are black. Solid rectangles mark best resolve,
  dashed rectangles lowest cost, and ovals lowest latency, comparing depths
  within each primitive/trigger row. Ties use full-precision values.
- Q3 rank shading uses the shared blue palette; contrast shading uses orange
  for negative and blue for positive changes. Stars mark intervals excluding
  zero. The Q3 winner boxes retain the selected rendering.
- Legends belong above panels; no explanatory footer text under the knob plot.
- Export via `save_figure`; preserve fixed page dimensions (no tight cropping).
  Current PNG resolution is 200 dpi, or 300 dpi for the intro and Q3; PDFs are vector.

## Data and regeneration

The bank computes every figure input from the tracked outcomes tables and
the audited Q3 exports (no untracked analysis exports are needed) and writes
the computed inputs as CSVs next to each figure. The computations reproduce
`q1_frontier.py`, `token_cost_ledger.py`, `q1_knob_execution.py` and the Q3
exports to floating-point precision (validated 2026-09-24); `resolved` is
taken from the outcomes tables, which carry the Qwen re-evaluation.

| Figure | Inputs and generation |
|---|---|
| `intro_01_policy_axes_wrap` | No data inputs. Reuses `intro_fig.make_wrap_figure` to draw context growth and repeated compression with primitive, trigger and depth labels. |
| `q1_24_qwen_overview` | `--outcomes` (default `analysis/outcomes/swebench_outcomes.csv`) and `--tb-outcomes` (default `analysis/outcomes/terminalbench_outcomes_0924.csv`): primary setting (depth 0.5, primary threshold) on P100 / TB-40, `q1_frontier` statistics (paired task bootstrap vs FC, seed 0, B=5000; absolute resolve intervals seed 210926, 10,000 resamples). Writes `q1/q1_frontier[_tb]_qwen35b.csv`. |
| `q1_26_knob_execution` | `--outcomes`: `knob_inputs` = the `q1_knob_execution.py` cell statistics and 45-cell resolve grid on ABL-25 (compression detector at 15% drop, seed 0, B=2000). Writes `q1/q1_knob_execution[_resolve_grid].csv`. |
| `q2_qwen_task_map_only` | `--outcomes` defaults to `analysis/outcomes/swebench_outcomes.csv`; `--tasks` defaults to pinned P100. Uses the validated main-track Qwen 15K loader, three attempts per task/policy. Majority success requires two uncapped resolved attempts. Orders each FC block by descending policy coverage, then task ID. |
| `q3_policy_preferences_and_design` | `--q3-data-dir` (default `ICLR_analysis/plots/q3`): the audited `q3_combined_policy_values.csv` and `q3_combined_design_contrasts.csv`, whose Devstral, GLM and Terminal-Bench rows are reused; the Qwen SWE-bench rows (values, ranks and the four design contrasts) are recomputed from `--outcomes`. The audited files are never overwritten. |

Q3 policy values contain benchmark/model/policy/metric/value/rank/n_tasks;
contrasts contain benchmark/model/policy pair/estimate/lo/hi. Policy ranks
compare resolve (higher better), latency and estimated input cost (lower
better). Design contrasts are paired task resolve-rate differences in pp
with task-bootstrap intervals. The bank validates unique cells and reads
these existing estimates without changing their statistical definitions.

## Interpretation to preserve in captions

Overview resource ratios use uncapped paired tasks; success includes failed
attempts. Costs are estimated billed **input** cost, not observed invoices.
Knob compression-event curves include all attempts; its left cost/latency
curves use completed attempts. Its table includes all 75 attempts per setting,
including failed/limit-exhausted attempts. Depth means fraction removed;
stored experiment depth names encode fraction retained. Qwen load-cohort
and timeout caveats in `ICLR.md` still apply. Q3 resource ranks and resolve
contrasts use different cohorts; retain the original metric definitions.

## Introduction figure

`intro_01_policy_axes_wrap` is the compact Figure 1, 3.2 × 1.9 inches.
Use it at its native width with `\begin{wrapfigure}{R}{3.2in}` and
`\includegraphics[width=\linewidth]{intro_01_policy_axes_wrap.pdf}`.
The PDF has embedded TrueType text; the PNG is for review.

The legend uses Fixed prompt, New history, and Compressed history in one row.
The hatched block is retained compressed history. The dashed threshold marks
when compression fires, curved arrows show the primitive rewriting context,
and the vertical drop shows depth. Only the parenthesized axis letters are
bold. The compact figure has no policy heading, and all text is at least 6.5 pt.

The intro uses the shared blue/green/orange colors to distinguish P/T/D.
These label colors identify axes, rather than primitive families as in the
results plots. Grey is the fixed prompt; blue blocks are newly added history.

## Appendix: Figure 1 at every depth and trigger threshold

`appendix_knob_overview.py` recomputes the Figure 1 statistics
(`q1_frontier.py` definitions) for each (threshold, depth) setting, reading
`analysis/outcomes/*.csv` plus the raw `experiment_results.json` for
online-TRC clear flags. D is the fraction removed (cell `d07` is D=0.3).
The primary setting comes from the main track; all others from the ablation
track on ABL-25 / TB-15, and depth-invariant policies repeat their D=0.5
cell at D=0.3 and 0.7. `--primary-cohort full` reproduces Figure 1 on
P100 / TB-40 (validated to match `q1_frontier[_tb]_qwen35b.csv` exactly).

Default outputs in `ICLR_analysis/plots/appendix/`:
`<model>_{swe,tb}_depth_trigger_ablation_{tight,primary,loose}.png` (one
figure per threshold group, its D settings as rows, the five panels as
columns), plus a `*_values.csv` of every plotted number. Qwen uses the eight
non-primary settings (Figure 1 covers 0.5/primary); other models use all
nine. `--grid`, `--per-setting` and `--stack` restore the older page-wide
grid, one-figure-per-setting and single-column outputs.

```bash
venv/bin/python ICLR_analysis/appendix_knob_overview.py            # Qwen, SWE + TB
venv/bin/python ICLR_analysis/appendix_knob_overview.py --model devstral24b --benchmarks swebench --grid-settings all
venv/bin/python ICLR_analysis/appendix_knob_overview.py --model glm47flash --benchmarks swebench --grid-settings all
```

## Appendix: task map at every depth and trigger threshold

`appendix_task_map.py` redraws `q2_qwen_task_map_only` (Figure 4) for each
(threshold, depth) setting, Qwen on SWE-bench, using the same cells and
cohorts as `appendix_knob_overview.py` (ablation track, ABL-25; the primary
setting also on ABL-25 by default, `--primary-cohort full` gives the P100
Figure 4, validated to match `paper_figures.summarize_q2` counts exactly).
Solved = at least two of three uncapped resolved attempts. Layout differs
from Figure 4 in dropping the title, the row markers and the family rules
in the count columns, and in grouping FC missed with Gained and FC solved
with Lost (legend top left). Outputs:
`ICLR_analysis/plots/appendix/task_specificity/qwen35b_swe_task_map_<threshold>_D<depth>.png`
and `qwen35b_swe_task_map_counts.csv`.

```bash
venv/bin/python ICLR_analysis/appendix_task_map.py
```

### Re-evaluated verdicts

`appendix_depth_trigger_ablation_reeval.py` regenerates the per-threshold
figures for all models from
`ICLR_results/ICLR_analysis/outcome/swebench_outcomes_reeval.csv` (the
canonical outcomes table with the 2026-09-23 Qwen main-track re-evaluation
applied by `analysis/apply_reeval_outcomes.py`; gitignored). Outputs go to
`ICLR_analysis/plots/appendix/depth_trigger_ablation/` as
`<model>_<swe|tb>_<threshold>.png` plus `reeval_<model>_values*.csv`. Only
Qwen SWE-bench changes (FC +12 pp on ABL-25 in every setting; TR, TRC, SU,
SS at the primary threshold); Terminal-Bench, Devstral and GLM are identical
to the canonical figures.

`appendix_task_map_reeval.py` does the same for the task maps: it runs
`appendix_task_map.py` on the re-evaluated table and writes into
`ICLR_analysis/plots/appendix/task_specificity/` (replacing the canonical
maps; rerun `appendix_task_map.py` to restore them).

### Paper Figures 2-5 from the re-evaluated verdicts

The plot bank itself is the pipeline: `Iclr_plot_bank.py` computes the
inputs of Figures 2-5 from `analysis/outcomes/swebench_outcomes.csv`
(which carries the 2026-09-24 Qwen re-evaluation; commit 397c232) and
`analysis/outcomes/terminalbench_outcomes_0924.csv`, writes them as CSVs
next to the figures, and draws. Figure 1 (`intro_01_policy_axes_wrap`)
draws no data. `analysis/apply_reeval_outcomes.py` can still write a
re-evaluated copy of an outcomes table for `--outcomes`.

```bash
venv/bin/python ICLR_analysis/Iclr_plot_bank.py
venv/bin/python ICLR_analysis/Iclr_plot_bank.py --figure q1_26_knob_execution
```

`appendix_depth_trigger_ablation_reeval.py` draws the appendix companion of
Figure 2 at the other depth / trigger-threshold settings in exactly the
Figure 2 layout (it calls `paper_figures_reeval.draw_overview_rows`): one
figure per model, benchmark and threshold with that threshold's depths as
rows (`D = 0.3` etc.), on the ablation cohort (ABL-25 / TB-15), from the
same re-evaluated outcomes table. Qwen gets SWE-bench and Terminal-Bench
and omits the D = 0.5 primary row (Figure 2); Devstral and GLM get
SWE-bench with all three rows. Outputs:
`ICLR_analysis/plots/appendix/depth_trigger_ablation/<model>_<swe|tb>_<threshold>.png`
plus `reeval_<model>_values[_swebench].csv`.

```bash
venv/bin/python ICLR_analysis/appendix_depth_trigger_ablation_reeval.py
venv/bin/python ICLR_analysis/appendix_depth_trigger_ablation_reeval.py --models qwen35b
```

`appendix_task_map_reeval.py` draws the appendix companion of Figure 4 (the
task-coverage map with the Oracle row) at every depth / trigger-threshold
setting, Qwen on SWE-bench, on ABL-25, from the same re-evaluated table:
one figure per threshold with the three depths stacked as bands headed
"D = 0.3" etc. and the legend once on top, drawn with
`paper_figures_reeval.draw_task_map` so the colours and layout match
Figure 4. Outputs:
`ICLR_analysis/plots/appendix/task_specificity/qwen35b_swe_task_map_<threshold>.png`
plus `qwen35b_swe_task_map_counts.csv`.

```bash
venv/bin/python ICLR_analysis/appendix_task_map_reeval.py
```
