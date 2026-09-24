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
