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
