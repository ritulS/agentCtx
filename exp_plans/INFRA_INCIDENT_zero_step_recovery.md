# Infrastructure Incident — Docker Cold-Pull Cascade in `p100-singles` Batches

**Date filed:** 2026-05-06
**Filed by:** main paper-framing chat (handoff to recovery chat)
**Status:** Diagnosed, not yet recovered. Recovery plan below is ready to execute.
**Affects:** ~473 of 7072 runs in `Review1/Review1.csv` (6.7%), heavily concentrated in bare-primitive @20k cells (35–46% per cell).

---

## TL;DR for the recovery chat

A 120-second timeout on `docker run -d` in the `mini-swe-agent` harness caused 473 SWE-bench Verified runs to never start. The runs were recorded in `Review1/Review1.csv` as `step_count == 0`, `failure_mode == 'silent_crash'`, `total_tokens_consumed == 0`, with latency uniformly 122–125 seconds (the timeout signature).

This is **purely infrastructure** — not anything about the compression primitives — but the failures concentrate in the *first batch* to hit fresh Docker images. The bulk of the damage is in `results/ablations/p100-singles-20000/` (398 runs); a smaller amount in `p100-singles-10000/` (~41 runs), and a long tail elsewhere.

**Recovery is straightforward** — pre-warm the affected Docker images, re-run the affected (task, primitive, run) triples, rebuild `Review1.csv`. With images cached, all 473 runs should succeed on retry.

---

## Project context (read this first if new to the repo)

This is the `agentCtx` project — an empirical study of context-compression strategies for LLM agents on SWE-bench Verified. The agent (`mini-swe-agent`, a fork at `mini-swe-agent/`) runs a tool-use loop, and a compression primitive fires when the token budget is exceeded.

Where things live:
- **`mini-swe-agent/src/minisweagent/environments/docker.py`** — the harness's Docker environment wrapper. Houses the 120s timeout on `docker run -d` (line 36).
- **`scripts/run_experiment.py`** — main experiment harness. Conditions are defined in the `CONDITIONS` list. Flags include `--ablation`, `--budget`, `--tasks-file`, `--conditions`, `--workers`, `--eval-only`.
- **`Review1/Review1.csv`** — central data file (7072 rows = 100 tasks × 35 cells × 2 runs). Columns include `task_name`, `primitive`, `token_budget`, `run_num`, `resolved`, `exit_status`, `patch_generated`, `failure_mode`, `step_count`, `total_tokens_consumed`, `latency_e2e_s`, `summarization_latency_s`, etc.
- **`Review1/build_review1.py`** — script that aggregates `results/ablations/<exp>/<task>/<condition>/run_<n>/` into `Review1.csv`.
- **`results/ablations/<exp>/<task>/<condition>/run_<n>/`** — per-run output directories. Each contains `agent.log` and (sometimes) `experiment_results.json`.
- **`Active_runs.md`** — live status of long-running experiments. Always update on launch/kill/completion.
- **`task_lists/`** — pinned task JSONs.
- **`logs/`** — gitignored experiment logs.

Critical project rule — **never commit** `results/`, `logs/`, `archive/`, `temp/`, `Review1/raw/`, `PaperSections/`, `figures/`, `Review1/figures/`. All gitignored.

---

## Root cause

### The signature

All 473 affected runs share the same fingerprint in `Review1.csv`:

| field | value |
|---|---|
| `step_count` | 0 |
| `total_tokens_consumed` | 0 |
| `failure_mode` | `silent_crash` |
| `exit_status` | NaN |
| `latency_e2e_s` | 122.27 – 125.92 (uniform within ±4 seconds) |
| `resolved` | False or NaN |

### The mechanism

`mini-swe-agent` starts each run by issuing `docker run -d ... <swebench_image>` to spin up an evaluation container. The harness wraps this call in a 120-second timeout (`pull_timeout` parameter):

- File — [`mini-swe-agent/src/minisweagent/environments/docker.py`](../mini-swe-agent/src/minisweagent/environments/docker.py)
- Line 36 — `pull_timeout: int = 120` (the default)
- Lines 91–97 — `subprocess.run(..., timeout=self.config.pull_timeout, ...)` wrapping the `docker run -d` call

When the SWE-bench eval image is **not cached locally**, Docker has to pull it from registry. For Django images this takes >2 minutes, especially when 16 worker processes are simultaneously requesting docker pulls (the daemon serializes). The harness gives up at 120s with `TimeoutExpired`, the run dies before the agent ever makes an LLM call, and the row lands in the CSV as zero-step.

### Verified ground truth — sample agent.log traceback

For task `django__django-12276`, condition `truncation`, run_1 in `p100-singles-20000`:

```
TimeoutExpired: Command '['docker', 'run', '-d', '--name',
'minisweagent-c2c88f91', '-w', '/testbed', '--rm',
'docker.io/swebench/sweb.eval.x86_64.django_1776_django-12276:latest', 'sleep',
'2h']' timed out after 120 seconds
```

Agent log size is 9,856 bytes — boilerplate plus the traceback. No tokens consumed, no steps executed.

### Why bare primitives at @20k specifically

Not because of the primitives. Because of **batch ordering**.

Comparing all 10 runs (5 conditions × 2 replicates) for `django__django-12276` at @20k across the three @20k batches:

| batch | run mtimes | log sizes |
|---|---|---|
| `p100-singles-20000` (bare primitives, ran first on these images) | 2026-05-02 19:35–19:37 | All 10 runs: 9,856 bytes (boilerplate + traceback) — every run hit the timeout |
| `p100-trc-20000` (TRC stacks, ran ~28h later) | 2026-05-03 23:58–00:09 | Run 1: 9,856 bytes (timeout). Run 2 minutes later: 95,571 bytes (worked) — image got cached after first failed pull |
| `p100-otrc-20000` (OTRC stacks, ran ~38h later still) | 2026-05-05 12:03–12:04 | All runs 54k–160k bytes — image already in local cache |

The first batch to hit a fresh Docker image always pays the cold-start cost. With 16 workers × 5 conditions × 2 replicates = 160 simultaneous `docker run` calls firing in a tight window, every concurrent attempt on the same task hit the same image-pull bottleneck. By the time TRC ran, images were partially cached. By OTRC, fully cached.

This explains the entire concentration pattern in the data. It is not a property of bare primitives or @20k budgets — it is a property of *which batch ran first against fresh images*.

---

## Scope

### Aggregate

- **Total zero-step runs:** 473 of 7072 (6.7%)
- **Distribution of `silent_crash` rows:**
  - `wall_clock_timeout` (latency ≥ 1400s, 1500s wall hit): 1558 runs — these are real time-limit failures, not the docker-pull issue
  - **`zero_step` (latency 122–125s, the docker-pull timeout): 473 runs ← this is the recovery target**
  - `actual_crash` (latency < 1400s, has steps): 18 runs — separate, ignore for this incident

### Concentration by (primitive, budget) cell

| primitive | budget | zero-step runs | total runs | % zero-step |
|---|---|---|---|---|
| SU-partial | 20000 | 92 | 200 | 46.0% |
| SS-partial | 20000 | 91 | 200 | 45.5% |
| TR | 20000 | 73 | 200 | 36.5% |
| SU-full | 20000 | 72 | 200 | 36.0% |
| SS | 20000 | 70 | 200 | 35.0% |
| TR | 10000 | 10 | 200 | 5.0% |
| SU-partial | 10000 | 10 | 200 | 5.0% |
| SU-full | 10000 | 9 | 200 | 4.5% |
| TRC+SU | 20000 | 7 | 200 | 3.5% |
| SS-partial | 10000 | 6 | 200 | 3.0% |
| OTRC+TR | 10000 | 6 | 200 | 3.0% |
| TRC+SS | 20000 | 6 | 200 | 3.0% |
| SS | 10000 | 6 | 200 | 3.0% |
| OTRC+SS-partial | 10000 | 4 | 200 | 2.0% |
| OTRC+SU-partial | 10000 | 4 | 200 | 2.0% |
| OTRC+SU-partial | 15000 | 2 | 200 | 1.0% |
| OTRC+TR | 15000 | 2 | 200 | 1.0% |
| TRC | 20000 | 2 | 200 | 1.0% |
| OTRC+SS-partial | 15000 | 1 | 200 | 0.5% |

The **5 bare-primitive cells at @20k together account for 398 of the 473 zero-step runs (84%)**. They are the priority target.

### Concentration by task

48 of 100 tasks have at least one zero-step run. The top 10 affected tasks (all Django) account for 154 zero-step runs:

| task | zero-step runs |
|---|---|
| django__django-11433 | 24 |
| django__django-11095 | 23 |
| django__django-11087 | 19 |
| django__django-12276 | 17 |
| django__django-12304 | 17 |
| django__django-12325 | 12 |
| django__django-13809 | 10 |
| django__django-13810 | 10 |
| django__django-12663 | 10 |
| django__django-15368 | 10 |

The "10 zero-step runs per task" mode means *every* (primitive, run_num) at that task in the singles-20000 batch hit the timeout — 5 bare primitives × 2 replicates = 10 runs.

---

## Recovery plan

### Step 0 — Read state

```bash
cd /home/rs67788/projects/agentCtx
git status                      # confirm working tree clean
cat Active_runs.md | head -50   # check no conflicting run is currently active
ls results/ablations/           # confirm the affected directories exist
```

### Step 1 — Generate manifest of affected (task, primitive, run_num, budget) triples

Run this Python snippet to produce a JSON manifest of every zero-step run. The manifest is the source of truth for the rest of the recovery.

```python
# scripts/generate_zero_step_manifest.py  — create me, then run
import pandas as pd, json
df = pd.read_csv("Review1/Review1.csv")
zs = df[df.step_count == 0].copy()

# Map primitive name back to the harness condition name expected by run_experiment.py.
# Inspect scripts/run_experiment.py CONDITIONS list to confirm exact strings.
PRIMITIVE_TO_CONDITION = {
    "TR":              "truncation",
    "SU-full":         "summarization",
    "SU-partial":      "summarization-partial",
    "SS":              "structured-summarize",
    "SS-partial":      "structured-summarize-partial",
    "TRC":             "tool-result-clear",
    "TRC+SU":          "trc-su",
    "TRC+SS":          "trc-ss",
    "OTRC+TR":         "otrc-tr",
    "OTRC+SS-partial": "otrc-ss-partial",
    "OTRC+SU-partial": "otrc-su-partial",
    "FC":              "full-context",
    "OTRC":            "online-trc",
}

manifest = []
for _, row in zs.iterrows():
    manifest.append({
        "task_name":   row["task_name"],
        "primitive":   row["primitive"],
        "condition":   PRIMITIVE_TO_CONDITION[row["primitive"]],
        "token_budget": int(row["token_budget"]),
        "run_num":     int(row["run_num"]),
        "repo":        row["repo"],
    })

with open("scripts/zero_step_manifest.json", "w") as f:
    json.dump(manifest, f, indent=2)
print(f"Manifest written: {len(manifest)} runs")

# Also write a unique-image list for pre-warming
unique_tasks = sorted(set(r["task_name"] for r in manifest))
with open("scripts/zero_step_images.txt", "w") as f:
    for t in unique_tasks:
        # SWE-bench image naming pattern — verify against an existing successful run's agent.log
        # Pattern observed: docker.io/swebench/sweb.eval.x86_64.<repo_slug>__<repo>-<num>:latest
        # Example: docker.io/swebench/sweb.eval.x86_64.django_1776_django-12276:latest
        # The slug comes from task_name. Build the pull command string.
        f.write(t + "\n")
print(f"Unique tasks affected: {len(unique_tasks)}")
```

After running, confirm `scripts/zero_step_manifest.json` has 473 entries and `scripts/zero_step_images.txt` has 48 unique tasks.

**Important verification step before proceeding** — open the agent.log of *any* successful run (not zero-step) and confirm the actual Docker image tag pattern matches what you'll pre-warm. Patterns may vary slightly across repo slugs. Check 2–3 successful runs across different repos (django, sympy, scikit-learn, etc.) to be safe.

### Step 2 — Pre-warm Docker images sequentially

Pull every affected image one at a time. This is slow (each pull is ~1–4 minutes for Django images) but it eliminates the cold-pull cascade. Do this *before* launching any worker pool.

```bash
# Construct image names from task_name. The exact transform is:
#    swebench task name "django__django-11433"
#    → docker tag "docker.io/swebench/sweb.eval.x86_64.django_1776_django-11433:latest"
# (verify the slug transform on a successful run's agent.log first)

# Sequential pull script — generate from zero_step_images.txt
while read task; do
    # Replace double-underscore with the registry slug pattern
    repo_slug=$(echo "$task" | python3 -c "
import sys
t = sys.stdin.read().strip()
# Verify this transform against actual successful agent.log image tag before trusting
owner, repo_id = t.split('__', 1)
print(f'{owner}_1776_{repo_id}'.lower())
")
    image="docker.io/swebench/sweb.eval.x86_64.${repo_slug}:latest"
    echo "[$(date +%T)] pulling $image"
    docker pull "$image" || echo "  FAILED: $image"
done < scripts/zero_step_images.txt 2>&1 | tee logs/zero_step_image_prewarm.log
```

Wall-clock estimate — 48 unique images × ~2 minutes each = ~90–120 minutes sequential. If parallelism is desired, cap at `--jobs 4` to avoid the docker-daemon contention that caused the original incident.

### Step 3 — Defensive fix to the harness (optional but recommended)

Bump the `pull_timeout` in [`mini-swe-agent/src/minisweagent/environments/docker.py`](../mini-swe-agent/src/minisweagent/environments/docker.py) from 120 to 600 seconds before the re-run. This protects against any image still cold-pulling at concurrent-worker time.

```python
# mini-swe-agent/src/minisweagent/environments/docker.py:36
pull_timeout: int = 600   # was 120 — incident 2026-05-06 docker cold-pull cascade
```

If you change this, follow the project's submodule-update discipline (per `CLAUDE.md`):
```bash
cd mini-swe-agent
git checkout agentctx-customizations
git add src/minisweagent/environments/docker.py
git commit -m "Increase pull_timeout 120s→600s (incident 2026-05-06)"
git push
cd ..
git add mini-swe-agent
git commit -m "Bump submodule for pull_timeout fix"
```

### Step 4 — Re-run affected cells

Two viable strategies. **Strategy A** is preferred because it is cell-by-cell and replicates the original run protocol.

**Strategy A — re-run the affected cells via `run_experiment.py` with the manifest as a task filter**

For each unique (`condition`, `token_budget`) pair in the manifest, identify the subset of tasks needing re-run, write a temporary task-list JSON, and re-run with `run_experiment.py`. Rough sketch:

```python
# scripts/relaunch_zero_step.py — create me, then run
import json, subprocess, os
from collections import defaultdict

manifest = json.load(open("scripts/zero_step_manifest.json"))
by_cell = defaultdict(set)
for r in manifest:
    by_cell[(r["condition"], r["token_budget"])].add(r["task_name"])

for (cond, budget), tasks in by_cell.items():
    tasks_list = sorted(tasks)
    out_json = f"task_lists/recovery_{cond}_{budget}.json"
    with open(out_json, "w") as f:
        json.dump([{"task_name": t} for t in tasks_list], f, indent=2)
    print(f"=== {cond} @ {budget} — {len(tasks_list)} tasks ===")
    # Decide on the right --ablation tag here. For p100-singles, use the existing dir name.
    # Verify by checking which results dir holds the original zero-step run for that (cond, budget).
    # Likely mapping:
    #   bare primitives @ 20k → ablation tag "p100-singles" with --budget 20000
    #   etc.
```

**Important** — before launching, *delete* (or move aside) the existing zero-step run directories so the re-run overwrites them cleanly. Otherwise the harness may treat them as already-present and skip. Check `run_experiment.py` for its resume/skip logic.

The exact `run_experiment.py` invocation pattern (verify against `Active_runs.md` history for the original p100 batch):

```bash
python3 scripts/run_experiment.py \
    --ablation p100-singles \
    --budget 20000 \
    --tasks-file task_lists/recovery_truncation_20000.json \
    --conditions truncation \
    --workers 16
```

Repeat for each (cond, budget) pair in the manifest. Total re-run runs = 473 (the zero-step rows). Wall-clock estimate with images pre-warmed and 16 workers — ~1–2 hours per ~100 runs depending on task latency, so total 4–8 hours.

**Strategy B — clean slate re-run of the affected cells** (only if Strategy A is messy)

Re-run each affected (`condition`, `token_budget`) cell from scratch (all 200 runs per cell, not just the zero-step subset). Wasteful but eliminates any state issues. Skip unless Strategy A hits ambiguity.

### Step 5 — Update `Active_runs.md`

Per project rule (per `CLAUDE.md`), `Active_runs.md` must be updated on launch and on completion. Add an entry under "Currently Running" when launching, and move it to "Recently Completed" when done.

### Step 6 — Rebuild `Review1.csv`

```bash
cd /home/rs67788/projects/agentCtx
python3 Review1/build_review1.py
```

This re-aggregates from `results/ablations/` into the CSV. Confirm no errors. Inspect the new CSV row count — it should remain 7072. The previously zero-step rows should now have `step_count > 0`.

### Step 7 — Validation

```python
import pandas as pd
df = pd.read_csv("Review1/Review1.csv")
zs_after = df[df.step_count == 0]
print(f"Zero-step rows after recovery: {len(zs_after)}")
# Target — ≤ ~50 (only the irrecoverable infra failures from other root causes, e.g., the 18 actual mid-run crashes).
# If still hundreds, recovery did not land — debug.
```

Spot-check 5 previously-affected rows by name (e.g. `django__django-12276` at @20k, primitive TR, run_num 1) — they should now have non-zero step_count and a real failure_mode (resolved / submitted_unresolved / limits_exceeded) rather than silent_crash.

Also confirm the bare-primitive @20k cells now have realistic resolve rates (the previously-low resolves were depressed by the zero-step contamination; expect them to climb 5–15pp once the missing runs are filled).

### Step 8 — Re-run downstream analyses

Once `Review1.csv` is clean, re-run:

```bash
cd /home/rs67788/projects/agentCtx
python3 Review1/sanity.py            # F8 sanity report
python3 Review1/paired_analysis.py   # paired CIs + McNemar headline grid
python3 Review1/routing_evidence.py  # M1–M3 heterogeneity
python3 Review1/predictability_sprint.py  # LOO predictability
python3 Review1/winners_table.py
python3 Review1/plot_review1.py
```

Compare key numbers against the pre-recovery values in `Review1/sanity_report.md`, `Review1/paired_analysis_report.md`, `Review1/predictability_report.md`, `Review1/winners_table.md`. Document any meaningful shifts in those reports.

The numbers most expected to shift:

| metric | pre-recovery (contaminated) | post-recovery direction |
|---|---|---|
| Bare-primitive @20k resolve rates | 24.5–29.5% | ↑ (probably +5–15pp once the ~70–92 missing runs per cell land) |
| Per-task heterogeneity rate (54/100 at @20k) | 54 | could shift slightly either direction |
| Oracle-of-11 headroom (+11–17pp) | locked range | likely stable but recompute |
| RQ5 depth finding (+14.5pp partial vs full SU @15k) | locked | should be stable (@15k barely contaminated) |
| RQ5b axis interaction (+20.5pp) | locked | should be stable (OTRC variants not contaminated) |

### Step 9 — Update the paper-spine disclosures

After recovery and re-analysis, two paper-related files need disclosure updates:

- **[`PaperSections/Paper_spine.md`](../PaperSections/Paper_spine.md)** — currently has a §4 "~6.7% zero-step infrastructure failures disclosed" line. Update the disclosure language to reflect *root cause = Docker cold-pull cascade in p100-singles batches; recovered via re-run on 2026-05-XX; final residual zero-step rate = X.X%*.
- **[`exp_plans/CHARACTERIZATION_PAPER_PLAN_100tasks.md`](CHARACTERIZATION_PAPER_PLAN_100tasks.md)** — has a similar disclosure in the "Open knobs / pending decisions" section. Update accordingly.

Do not edit any file inside `PaperSections/` without first showing the diff in chat to the user — this is a standing rule (memory `feedback_paper_edits.md`). The recovery chat should propose the disclosure-update wording in chat, get user approval, then write.

---

## Followup tracking

When this work is complete, return to the main paper-framing chat with:

1. **Final residual zero-step count** (target: < 50, mostly the 18 actual crashes)
2. **Diff summary** of the headline numbers — which moved and which stayed (use the "metrics most expected to shift" table above as the watch list)
3. **Confirmation** that `Active_runs.md` is updated and the recovery batch is logged under "Recently Completed"
4. **Any anomalies** encountered during re-run (new docker issues, vLLM crashes, task-specific failures)

The main chat will then resume the paper-outline framing work, using the cleaned data.

---

## Open questions / things this report does not cover

- **Exact `--ablation` tag mapping.** The manifest groups by (condition, budget), but `run_experiment.py` expects an `--ablation` string that maps to a results-directory name. The mapping for the original p100 batch was likely just `--ablation p100-singles` etc. Verify against `Active_runs.md` history before launching.
- **The slug transform `django__django-12276 → django_1776_django-12276`** in the docker image tag. I observed it in *one* agent.log; it should hold for all SWE-bench tasks but verify against 2–3 different repos (sympy, scikit-learn, sphinx, etc.) before pre-warming everything.
- **Resume vs replace semantics in `run_experiment.py`.** Need to confirm the harness will overwrite an existing zero-step run directory rather than skipping it. If skipping is the default, delete or rename the affected dirs first.
- **The 18 `actual_crash` runs (latency < 1400s, has steps, no submission).** Out of scope for this incident — different root cause. Ignore for recovery; investigate separately if the paper needs them clean.
- **The `vLLM` server state.** Per `Active_runs.md`, vLLM was last restarted 2026-05-05 11:32 CDT. Confirm it is still alive on Dobby before launching the re-run; restart if not.

---

## References

- **Docker timeout source** — [`mini-swe-agent/src/minisweagent/environments/docker.py`](../mini-swe-agent/src/minisweagent/environments/docker.py) lines 36, 91–97
- **Sample failure trace** — `results/ablations/p100-singles-20000/django__django-12276/truncation/run_1/agent.log` (final TimeoutExpired traceback)
- **Original p100 batch history** — [`Active_runs.md`](../Active_runs.md) under "P100 expansion" entry
- **CSV source of truth** — [`Review1/Review1.csv`](../Review1/Review1.csv)
- **CLAUDE.md** — project conventions, two-machine workflow, submodule discipline — [`CLAUDE.md`](../CLAUDE.md)
- **Memory rules to respect** — `feedback_paper_edits.md` (PaperSections approval), `feedback_active_runs_doc.md` (always update Active_runs.md), `feedback_no_cascade.md` and `feedback_no_routing.md` (paper framing)
