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

The bank renders existing analysis exports; it does not silently recompute
experiments or refresh statistical estimates. No `/tmp` inputs are needed.

| Figure | Inputs and generation |
|---|---|
| `intro_01_policy_axes_wrap` | No data inputs. Reuses `intro_fig.make_wrap_figure` to draw context growth and repeated compression with primitive, trigger and depth labels. |
| `q1_24_qwen_overview` | `--data-dir` (default `ICLR_analysis`): Qwen `q1_frontier[_tb]_qwen35b.csv` and `token_cost_ledger[_tb]_qwen35b.csv`. Existing loader validates success estimates and bootstraps absolute resolve intervals with 10,000 task resamples, seed 210926. Upstream: `q1_frontier.py`, `token_cost_ledger.py`. |
| `q1_26_knob_execution` | `--data-dir`: `q1_knob_execution.csv` and `q1_knob_execution_resolve_grid.csv`. Refresh both from canonical raw records with `venv/bin/python ICLR_analysis/q1_knob_execution.py`. |
| `q2_qwen_task_map_only` | `--outcomes` defaults to `analysis/outcomes/swebench_outcomes.csv`; `--tasks` defaults to pinned P100. Uses the validated main-track Qwen 15K loader, three attempts per task/policy. Majority success requires two uncapped resolved attempts. Orders each FC block by descending policy coverage, then task ID. |
| `q3_policy_preferences_and_design` | `--q3-data-dir` defaults to `ICLR_analysis/plots/q3`, containing `q3_combined_policy_values.csv` and `q3_combined_design_contrasts.csv`. These are the audited numerical exports used for the selected figure, not temporary plot inputs. Preserve them with the analysis snapshot. |

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

`paper_figures_reeval.py` re-renders the four selected figures (paper
Figures 2-5: overview, tuning, task map, policy preferences) with every
input recomputed from
`ICLR_results/ICLR_analysis/outcome/swebench_outcomes_reeval.csv`
(Terminal-Bench from `analysis/outcomes/terminalbench_outcomes_0924.csv`,
unchanged). It reproduces the `q1_frontier.py`, `load_qwen_overview`,
`q1_knob_execution.py` and Q3 definitions, taking `resolved` from the
outcomes table, and calls the unchanged plot-bank drawing functions. For
Q3 only the Qwen SWE-bench rows are recomputed; Devstral, GLM and
Terminal-Bench rows are copied from the audited exports in `plots/q3/`.
Run with `--outcomes analysis/outcomes/swebench_outcomes.csv` it reproduces
the canonical exports to floating-point precision (validated 2026-09-24).
Figure 1 (`intro_01_policy_axes`) draws no data and is not affected.
The overview (Figure 2) is drawn by a revised copy of `fig_qwen_overview`
carrying the reviewer notes: no "Qwen" heading, larger fonts and markers,
black arrows in each panel pointing toward the better direction of both
axes, both axes include 0, no y=x guide in the third column, one benchmark
heading per row instead of panel titles, FC is a black square instead of a
star. In every figure the script draws, the OTRC family gets purple hues
instead of greys (OTRC+TR blue-leaning purple, filled; OTRC+SU-p red-leaning
purple and OTRC+SS-p light blue-leaning purple, hollow) so its members are
not confused with each other or with hollow-black OTRC; the plot-bank
palette itself is unchanged.
The tuning figure (Figure 3) is drawn by Ritul's 2026-09-24 local revision
of `fig_knob_execution` (larger fonts, yellow highest-resolve and green
lowest-cost cells, oval lowest latency, winner legend), carried in the
script until it is committed, with the sweep x-axis labels shortened to
"D" and "Threshold", compressions starting at 0, and billed input and
latency plotted as ratios to FC on a range around 1.
The policy-preference figure (Figure 5) is drawn by a revised copy of
`fig_policy_preferences`: panel (a) uses the Figure 3(c) table encoding
(grey boxed triplets per model, yellow highest resolve, green lowest cost,
oval lowest latency, bold winners, winner legend) with black policy labels
and no rank shading or rank colour bar, and the panel titles are just "(a)" and "(b)" centred
under each panel.
The task map (Figure 4) gains an `Oracle` row directly above FC: a task
counts as solved when any of the thirteen policies (the twelve compression
policies or FC) solves it (per-policy majority of three runs), i.e. the
resolve reachable if the best policy were known per task; Gained is
relative to FC as in every other row and Lost is 0 by construction. The script carries its own copy of `fig_task_map` with
the row list as a parameter; the plot-bank renderer is untouched. The copy
also applies the reviewer notes: no "Qwen · SWE-bench · 15K" heading (state
it in the caption), centred legend closer to the map, slightly larger fonts,
one-line column headers, and no row markers except FC's black square (the
same FC marker as Figure 2).
Outputs go to `ICLR_analysis/plots/reeval/` as PNG under the plot-bank filenames,
with the recomputed inputs as CSVs beside them.

```bash
venv/bin/python ICLR_analysis/paper_figures_reeval.py
venv/bin/python ICLR_analysis/paper_figures_reeval.py --figure overview tuning
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
