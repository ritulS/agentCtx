# Coverage dashboard on GitHub Pages

The dashboard uses two branches:

- `akiho-expansion` contains the experiment code and local/raw results.
- `akiho-expansion-data` receives the generated `COVERAGE.csv`,
  `COVERAGE_TB.csv`, dashboard builder, and Pages workflow.

The local machine can see the gitignored SWE-Bench experiment results, so it
generates `COVERAGE.csv` directly in the data worktree. Terminal-Bench runs on
another machine; the publisher fetches the latest commit of
`origin/akiho-expansion-terminalbench-0829-data` and takes `COVERAGE_TB.csv`
from that commit. The normal `akiho-expansion` worktree is not modified. GitHub
Actions only renders and deploys the inputs from the combined data branch.

## One-time setup

First commit and push the workflow, publishing script, and this documentation
on `akiho-expansion`. Then create the data worktree beside this repository:

```bash
cd /home/ak58925/agentCtx
git worktree add -b akiho-expansion-data \
  /home/ak58925/agentCtx-data akiho-expansion
python dashboard/publish.py
```

If `origin/akiho-expansion-data` already exists on another machine, use this
instead of `-b`:

```bash
git fetch origin akiho-expansion-data
git worktree add -b akiho-expansion-data \
  /home/ak58925/agentCtx-data origin/akiho-expansion-data
```

In the GitHub repository settings, select **Settings → Pages → Source: GitHub
Actions**. The first push to `akiho-expansion-data` starts the deployment.

The workflow publishes below this long, unlisted path (configured directly in
`dashboard-pages.yml` because repository-secret administration is unavailable):

```text
DASHBOARD_PATH: dashboard-7f4c2a91e8b653d0
```

The dashboard URL will be:

```text
https://rituls.github.io/agentCtx/dashboard-7f4c2a91e8b653d0/
```

The site root has no index page, `robots.txt` disallows crawling, and the
dashboard itself carries a `noindex` directive. This is obscurity rather than
authentication: anyone who learns the URL can still open it, and the path is
visible to anyone inspecting the public repository's workflow.

## Run every 30 minutes

Open the user's crontab with `crontab -e` and add one line (replace the Python
path if this checkout uses a different virtual environment):

```cron
0,30 * * * * /home/ak58925/agentCtx/dashboard/publish_cron.sh
```

The wrapper writes to `logs/dashboard-pages.log` and uses `flock` to prevent
overlapping publications. The publisher runs `dashboard/build_coverage.py`
against this machine's local data to create `COVERAGE.csv`, then fetches
`COVERAGE_TB.csv` from the Terminal-Bench data branch. It records each progress
bar's timestamped run count in `dashboard_progress_history.jsonl`, retaining 14
days. The dashboard uses those snapshots to show average throughput over the
last three hours. Finally, it copies the builder and workflow, and commits and
pushes only if their content changed.

Run it manually at any time with:

```bash
python dashboard/publish.py
```

The GitHub Actions workflow builds `DASHBOARD.html` from both coverage CSVs,
puts it below the configured `DASHBOARD_PATH`, and deploys that artifact to
GitHub Pages.

Priority 1 tracks all three runs per task (`run_1`–`run_3`), including the
first two runs, across the P100 main cells and ABL-25 ablation cells. Its
total target is 7,800 runs. Main and Ablation have separate progress bars. Progress history uses
`p1a_all_runs_v3` and `p1b_abl25_v4` so throughput
is not compared with older snapshots that counted only the additional run.

SWE-Bench ablations use `task_lists/ablation_25tasks.json`, a strict subset of
ABL-30. Coverage counts only those 25 task IDs, including existing runs from
ABL-30/P100 cells. Each model has a 3,900-run ablation target; Priority 2 totals
15,600 runs and the summarizer ablation totals 480 runs including Terminal-Bench
(TB:ABL-15 × 3 runs × 2 primitives × 2 summarizers = 180 runs).
Priority 5 (prefix-cache ablation) totals 1,560 runs: Qwen3.5-35B-A3B as agent
and summarizer, every primitive at depth 0.5/DI and the primary budget plus
FC/OTRC at ∞, on SB:ABL-25 at 15K with vLLM prefix caching ON (5.a, 975 runs)
and on TB:ABL-15 at 3K with it OFF (5.b, 585 runs) — the opposite of each benchmark's production serving.
Coverage counts only runs below `ICLR_results/<benchmark>/prefix_cache_ablation/`;
they become separate cells with a non-empty `prefix_cache` column (`ON`/`OFF`)
and never merge into the production cell of the same primitive, budget and
depth. Model directories there are named `<agent>-prefixcache` or
`<agent>-noprefixcache`. Its history key is `p5_prefix_cache_v1`.
Regenerate `COVERAGE.csv` before rendering: old ABL-30 totals cannot be
converted proportionally. The affected history keys are `p1b_abl25_v4`,
`p2c_abl25_v2`, `p2d_abl25_v2`, `p2_abl25_v2`, and `p4_abl25_tbabl15_v3`.
