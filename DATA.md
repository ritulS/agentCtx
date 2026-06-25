# Data — what's tracked, what isn't, and how to get it

Code lives in git. **Experiment data does not** — it's too large (~9 GB of
raw trajectories) and append-mostly, so it would bloat the repo permanently.
This file explains the split and how to obtain or regenerate the data.

## What IS in git

- All code (`scripts/`, `Review1/*.py`, `memory.py`, the `mini-swe-agent`
  submodule).
- **`Review1/Review1.csv`** — the central, distilled analysis file. This is the
  one data artifact that *is* tracked, because it's small and is what the
  analysis/plotting scripts consume.
- Per-model aggregated CSVs that have been explicitly force-added when stable
  (`Review1/Review1_qwen25-7b.csv`, `Review1/Review1_qwen3-30b-a3b-quant.csv`,
  …). Note `Review1/Review1_*.csv` is gitignored by default; add stable ones
  with `git add -f`.
- Plans, task lists, and status docs.

**You do not need the raw trajectories to continue the project.** A fresh clone
has the code, the submodule, and `Review1.csv` — enough to run new experiments
and reproduce every figure/table. The raw trajectories matter only if you want
to *regenerate* `Review1.csv` or do new raw-level analysis.

## What is NOT in git (gitignored)

| Path | Size | Note |
|------|------|------|
| `results/` | ~8.8 GB | Raw run outputs — 21k+ `trajectory.json` files. |
| `venv/` | ~11 GB | Python env; recreate locally (see README). |
| `logs/`, `archive/`, `temp/` | varies | Run logs and scratch. |
| `Review1/raw/`, `Review1/figures*/`, `figures/`, `PaperSections/` | varies | Regeneratable / paper-local. |
| `*.csv.bak.*` | — | Local timestamped CSV snapshots. |

See [.gitignore](.gitignore) for the authoritative list.

## Getting the raw data onto another machine (rsync)

Results are transferred machine-to-machine with rsync, not git. Template:

```bash
# Pull results from the machine that produced them (run on the destination):
rsync -avhP --info=progress2 \
    <user>@<source-host>:/path/to/agentCtx/results/ \
    /path/to/agentCtx/results/

# Logs, if needed for debugging:
rsync -avhP <user>@<source-host>:/path/to/agentCtx/logs/ ./logs/
```

`-a` preserves structure/timestamps; `--partial` (`-P`) makes interrupted
transfers of the many small files resumable. Pull only the subdirs you need
(e.g. `results/ablations/p100-singles-15000/`) to keep transfers small.

## Regenerating Review1.csv from raw

Once `results/` is present locally:

```bash
source venv/bin/activate
python Review1/build_review1.py        # walks results/ablations/* → Review1/Review1.csv
```

Per-model aggregations on Albus use `Review1/build_review1_albus.py`.

## Archiving for reproducibility (optional)

For a paper artifact or off-machine backup, snapshot `results/` out-of-band —
do **not** push it to GitHub (100 MB/file and ~2 GB/push limits, and it would
bloat history for everyone who clones):

```bash
tar -czf agentctx-results-$(date +%Y%m%d).tar.gz results/
```

Then upload to durable storage. For a citable paper artifact, **Zenodo** is a
good fit (free, gives a DOI). For working backups, institutional/cloud storage
(S3, Google Drive) is fine. Avoid Git-LFS here — 21k tiny files is its weak
case and GitHub's LFS quotas are small. Record the archive location below when
you create one.

<!-- Archive locations:
  - results YYYY-MM-DD: <url/DOI>
-->
