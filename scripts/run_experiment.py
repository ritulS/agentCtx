#!/usr/bin/env python3
"""
E2 Experiment Runner
====================
Design : 30 tasks × 3 conditions × 3 runs = 270 agent runs.

Conditions
----------
  full-context   : no compression (MSWEA_TOKEN_BUDGET = 999999999 sentinel)
  truncation     : compress when context window > FIXED_BUDGET tokens
  summarization  : compress when context window > FIXED_BUDGET tokens

Budget semantics (post-redesign)
---------------------------------
  MSWEA_TOKEN_BUDGET is a CONTEXT WINDOW SIZE threshold, not a cumulative total.
  The hook in default.py fires when count_tokens(messages) > budget — i.e. when
  the history being sent to the model on the next call exceeds the threshold.
  FIXED_BUDGET = 25 000 tokens for both compressed conditions.

Directory layout
----------------
  results/{instance_id}/{condition}/run_{n}/
    trajectory.json   full message history + exit_status + submission patch
    token_log.json    per-step + compression stats
    agent.log         subprocess stdout/stderr

Usage
-----
  python scripts/run_experiment.py            # agents only
  python scripts/run_experiment.py --with-eval
  python scripts/run_experiment.py --eval-only
"""

import argparse
import json
import os
import subprocess
import threading
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

# ── Configuration ──────────────────────────────────────────────────────────────

WORKSPACE_ROOT       = Path(__file__).parent.parent
MINI_SWE_AGENT       = WORKSPACE_ROOT / "mini-swe-agent"
AGENT_CONFIG         = WORKSPACE_ROOT / "config-qwen-vllm.yaml"
TASKS_FILE           = WORKSPACE_ROOT / "task_lists" / "selected_tasks.json"
TASKS_FILE_EXPLICIT  = False
ABLATION_TASKS_FILE  = WORKSPACE_ROOT / "results" / "ablations" / "tasks.json"
RESULTS_DIR          = WORKSPACE_ROOT / "results"

# Set by main() from --model-tag / --ablation; used by run_dir() and results_file_path().
MODEL_TAG: str    = "qwen35-a3b"
ABLATION_NAME: str | None = None   # set by --ablation; overrides MODEL_TAG routing


def model_results_dir() -> Path:
    if ABLATION_NAME:
        return RESULTS_DIR / "ablations" / ABLATION_NAME
    return RESULTS_DIR / MODEL_TAG

REPOS = {
    "django/django":             "django",
    "sympy/sympy":               "sympy",
    "scikit-learn/scikit-learn": "scikit-learn",
}

# Experimental conditions.
# "condition" is used as directory name and result key component.
# primitive   = value passed to MSWEA_PRIMITIVE env var
# budget      = value passed to MSWEA_TOKEN_BUDGET env var (context window tokens)
CONDITIONS = [
    {"condition": "full-context",         "primitive": "truncation",           "budget": 999_999_999},
    {"condition": "truncation",           "primitive": "truncation",           "budget": 15_000},
    {"condition": "summarization",        "primitive": "summarization",        "budget": 15_000},
    {"condition": "structured-summarize", "primitive": "structured_summarize", "budget": 15_000},
    {"condition": "tool-result-clear",    "primitive": "tool_result_clear",    "budget": 15_000},
    # online-trc: freeze-window clearing (k=4), no budget gate
    {"condition": "online-trc", "primitive": "online_trc", "budget": 999_999_999,
     "config": WORKSPACE_ROOT / "config-online-trc.yaml"},
    # Stacked primitives: TRC (KEEP_RECENT=3) fires first; second primitive is fallback
    {"condition": "trc-su",  "primitive": "trc_summarize",           "budget": 15_000},
    {"condition": "trc-ss",  "primitive": "trc_structured_summarize","budget": 15_000},
    # trc-tr = existing tool-result-clear (already has truncation fallback built-in)
    # Partial summary primitives: summarize the head, keep budget-fitting tail verbatim
    {"condition": "summarization-partial",        "primitive": "summarization_partial",        "budget": 15_000},
    {"condition": "structured-summarize-partial", "primitive": "structured_summarize_partial", "budget": 15_000},
    # OTRC stacked variants: per-step freeze-window clearing + budget-triggered fallback.
    # All three reuse config-online-trc.yaml (agent prompts expect cleared tool stubs).
    {"condition": "otrc-tr",         "primitive": "online_trc",                              "budget": 15_000,
     "config": WORKSPACE_ROOT / "config-online-trc.yaml"},
    {"condition": "otrc-su-partial", "primitive": "online_trc_summarize_partial",            "budget": 15_000,
     "config": WORKSPACE_ROOT / "config-online-trc.yaml"},
    {"condition": "otrc-ss-partial", "primitive": "online_trc_structured_summarize_partial", "budget": 15_000,
     "config": WORKSPACE_ROOT / "config-online-trc.yaml"},
    # Staggered: at each compression event, pick one of the oracle-optimal pair (TR + budget-best).
    # Pair is fixed by budget inside default.py: 10k→TR+TRC+SS, 15k→TR+SU-partial, 20k→TR+TRC+SS.
    {"condition": "staggered-alternate", "primitive": "staggered_alternate", "budget": 15_000},
    {"condition": "staggered-random",    "primitive": "staggered_random",    "budget": 15_000},
]

N_TASKS            = 100   # total tasks (~33 per repo); overridden by --n-tasks
N_TASKS_OVERRIDE: int | None = None  # set by --n-tasks; slices ablation task lists too
RUNS_PER_TASK      = 2
COMPRESSION_RATIO  = 0.5   # fraction of budget retained after compression; overridden by --depth
STEP_LIMIT    = 125
AGENT_TIMEOUT = 1500  # 25 min; 125 steps × ~10s/step + headroom
MAX_WORKERS   = 16    # concurrent runs against the shared vLLM server (override with --max-workers)

# SWE-bench evaluation
SWE_BENCH_PYTHON = WORKSPACE_ROOT / "venv" / "bin" / "python"
DOCKER_HOST      = f"unix:///run/user/{os.getuid()}/podman/podman.sock"
DATASET_SUBSET   = "verified"
DATASET_SPLIT    = "test"

# ── Helpers ────────────────────────────────────────────────────────────────────

def run_key(instance_id: str, condition: str, run_num: int) -> str:
    return f"{instance_id}__{condition}__r{run_num}"


def run_dir(instance_id: str, condition: str, run_num: int) -> Path:
    return model_results_dir() / instance_id / condition / f"run_{run_num}"


def results_file_path() -> Path:
    return model_results_dir() / "experiment_results.json"


def load_tasks() -> list[dict]:
    # Ablation mode: default to the fixed 30-task set, unless --tasks-file was passed
    if ABLATION_NAME:
        if TASKS_FILE_EXPLICIT:
            tasks = json.loads(TASKS_FILE.read_text())
            source_desc = f"custom task file {TASKS_FILE}"
        else:
            if not ABLATION_TASKS_FILE.exists():
                print(f"ERROR: ablation task file not found at {ABLATION_TASKS_FILE}")
                raise SystemExit(1)
            tasks = json.loads(ABLATION_TASKS_FILE.read_text())
            source_desc = "fixed 30-task set"
        if N_TASKS_OVERRIDE is not None and N_TASKS_OVERRIDE < len(tasks):
            tasks = tasks[:N_TASKS_OVERRIDE]
            source_desc += f" (sliced to first {N_TASKS_OVERRIDE} via --n-tasks)"
        by_repo = defaultdict(int)
        for t in tasks:
            by_repo[t["repo"]] += 1
        counts = ", ".join(f"{r}={n}" for r, n in sorted(by_repo.items()))
        print(f"Ablation mode ({source_desc}) — {len(tasks)} tasks: {counts}")
        return tasks

    if not TASKS_FILE.exists():
        print(f"ERROR: {TASKS_FILE} not found – run scripts/select_tasks.py first.")
        raise SystemExit(1)
    all_tasks = json.loads(TASKS_FILE.read_text())

    # Take N_TASKS // 3 from each repo (balanced sample).
    # selected_tasks.json uses short repo labels (e.g. "django"), matching REPOS values.
    by_repo: dict[str, list] = defaultdict(list)
    for t in all_tasks:
        by_repo[t["repo"]].append(t)

    # Distribute N_TASKS across repos as evenly as possible, remainder goes to
    # the first repos.  e.g. 20 tasks / 3 repos → 7, 7, 6.
    n_base      = N_TASKS // len(REPOS)
    n_remainder = N_TASKS  % len(REPOS)
    tasks: list[dict] = []
    counts_parts = []
    for i, (repo, label) in enumerate(REPOS.items()):
        n = n_base + (1 if i < n_remainder else 0)
        repo_tasks = by_repo.get(label, [])
        if len(repo_tasks) < n:
            print(f"WARNING: only {len(repo_tasks)} tasks for {repo} (need {n})")
        tasks.extend(repo_tasks[:n])
        counts_parts.append(f"{label}={n}")

    counts = ", ".join(counts_parts)
    print(f"Using {len(tasks)} tasks: {counts}")
    return tasks


def load_existing_results() -> list[dict]:
    p = results_file_path()
    return json.loads(p.read_text()) if p.exists() else []


def save_results(results: list[dict]) -> None:
    p = results_file_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(results, indent=2))


# ── Agent run ──────────────────────────────────────────────────────────────────

def run_agent(instance_id: str, condition: str, primitive: str, budget: int, run_num: int,
              config: Path | None = None, compression_ratio: float = 0.5) -> dict:
    """
    Run mini-swe-agent for one (task, condition, run) combination.

    condition = "full-context" | "truncation" | "summarization" | "online-trc"
    primitive = MSWEA_PRIMITIVE value
    budget    = MSWEA_TOKEN_BUDGET value (999999999 = never fires)
    config    = agent config YAML; defaults to global AGENT_CONFIG
    """
    key = run_key(instance_id, condition, run_num)
    out = run_dir(instance_id, condition, run_num)
    out.mkdir(parents=True, exist_ok=True)

    traj_file      = out / "trajectory.json"
    token_log_file = out / "token_log.json"
    log_file       = out / "agent.log"

    env = os.environ.copy()
    env["MSWEA_COST_TRACKING"]      = "ignore_errors"
    env["MSWEA_PRIMITIVE"]          = primitive
    env["MSWEA_TOKEN_BUDGET"]       = str(budget)
    env["MSWEA_COMPRESSION_RATIO"]  = str(compression_ratio)
    env["MSWEA_TOKEN_LOG_PATH"]     = str(token_log_file)
    env["MSWEA_RUN_KEY"]            = key   # used by staggered_random for reproducible seeding
    env["DOCKER_HOST"]          = DOCKER_HOST

    local_bin = str(Path.home() / ".local" / "bin")
    if local_bin not in env.get("PATH", ""):
        env["PATH"] = local_bin + ":" + env.get("PATH", "")

    # memory.py lives in the repo root; add it to PYTHONPATH so default.py can
    # `import memory` regardless of the cwd the subprocess starts in.
    env["PYTHONPATH"] = str(WORKSPACE_ROOT) + (":" + env["PYTHONPATH"] if "PYTHONPATH" in env else "")

    # Build -c config chain. mini-swe-agent merges configs in order, later overriding earlier.
    # When a condition has a config (e.g. OTRC's prompts), load it first, then layer the user's
    # --agent-config on top so the model section (model_name, api_base) wins.
    config_chain = ["swebench_backticks.yaml"]
    if config is not None:
        config_chain.append(str(config))
        if AGENT_CONFIG and Path(AGENT_CONFIG) != Path(config):
            config_chain.append(str(AGENT_CONFIG))
    else:
        config_chain.append(str(AGENT_CONFIG))
    cmd = [
        str(WORKSPACE_ROOT / "venv" / "bin" / "python"),
        "-m", "minisweagent.run.benchmarks.swebench_single",
        "--subset",   DATASET_SUBSET,
        "--split",    DATASET_SPLIT,
        "--instance", instance_id,
    ]
    for c in config_chain:
        cmd += ["-c", c]
    cmd += [
        "-c", f"agent.step_limit={STEP_LIMIT}",
        "-o", str(traj_file),
        "-y",
        "--exit-immediately",
    ]

    t0 = time.time()
    returncode = -1
    try:
        with open(log_file, "w") as log:
            proc = subprocess.Popen(
                cmd, cwd=MINI_SWE_AGENT, env=env,
                stdout=log, stderr=subprocess.STDOUT,
            )
            proc.wait(timeout=AGENT_TIMEOUT)
            returncode = proc.returncode
    except subprocess.TimeoutExpired:
        proc.kill()
        print(f"    ! Timeout after {AGENT_TIMEOUT}s")
    except Exception as exc:
        print(f"    ! Launch error: {exc}")

    e2e_latency = round(time.time() - t0, 2)

    # ── Parse trajectory ──────────────────────────────────────────────────────
    n_calls = 0; patch_generated = False; submission = ""; exit_status = ""
    if traj_file.exists():
        try:
            traj        = json.loads(traj_file.read_text())
            info        = traj.get("info", {})
            n_calls     = info.get("model_stats", {}).get("api_calls", 0)
            exit_status = info.get("exit_status", "")
            submission  = info.get("submission", "") or ""
            patch_generated = bool(submission.strip())
        except Exception as exc:
            print(f"    ! Trajectory parse error: {exc}")

    # ── Parse token log ───────────────────────────────────────────────────────
    tok: dict = {}
    if token_log_file.exists():
        try:
            tok = json.loads(token_log_file.read_text())
        except Exception:
            pass

    result = {
        "key":          key,
        "instance_id":  instance_id,
        "condition":    condition,
        "primitive":    primitive,
        "budget":             budget,
        "compression_ratio":  compression_ratio,
        "is_baseline":        budget == 999_999_999,
        "run_num":      run_num,
        "timestamp":    datetime.now().isoformat(),
        # process
        "returncode":    returncode,
        "e2e_latency_s": e2e_latency,
        # agent metrics
        "n_calls":        n_calls,
        "exit_status":    exit_status,
        "patch_generated": patch_generated,
        "submission":     submission,
        "resolved":       None,   # filled by SWE-bench eval
        # token log — cumulative totals
        "total_prompt_tokens":     tok.get("total_prompt_tokens", 0),
        "total_completion_tokens": tok.get("total_completion_tokens", 0),
        "total_tokens":            tok.get("total_tokens", 0),
        "llm_latency_s":           tok.get("total_latency_s", 0.0),
        "mean_latency_s":          tok.get("mean_latency_s", 0.0),
        # per-step context window sizes
        "step_prompt_tokens":      tok.get("step_prompt_tokens", []),
        # compression
        "compression_events":             tok.get("compression_events", 0),
        "compression_event_steps":        tok.get("compression_event_steps", []),
        "context_tokens_at_compression":  tok.get("context_tokens_at_compression", []),
        "context_tokens_after_compression": tok.get("context_tokens_after_compression", []),
        "total_tokens_saved":             tok.get("total_tokens_saved", 0),
        "mean_compression_ratio":         tok.get("mean_compression_ratio", 1.0),
        "summarization_prompt_tokens":    tok.get("summarization_prompt_tokens", 0),
        "summarization_latency_s":        tok.get("summarization_latency_s", 0.0),
        "trc_truncation_fallback_events": tok.get("trc_truncation_fallback_events", 0),
        # online-trc specific
        "online_trc_total_tokens_saved": tok.get("online_trc_total_tokens_saved", 0),
        "online_trc_clears":             tok.get("online_trc_clears", 0),
        "online_trc_flags":              tok.get("online_trc_flags", []),
    }

    icon = "P" if patch_generated else "x"
    print(
        f"    [{icon}] e2e={e2e_latency:.0f}s  calls={n_calls:3d}  "
        f"comp_events={result['compression_events']:2d}  "
        f"exit={exit_status}"
    )
    return result


# ── All agent runs ─────────────────────────────────────────────────────────────

def run_all_agents(tasks: list[dict]) -> list[dict]:
    results      = load_existing_results()
    existing_keys = {r["key"] for r in results}

    # Build the full work list: tasks × conditions × runs
    needed = []
    for t in tasks:
        for cond in CONDITIONS:
            for rn in range(1, RUNS_PER_TASK + 1):
                k = run_key(t["instance_id"], cond["condition"], rn)
                if k not in existing_keys:
                    needed.append((t["instance_id"], cond, rn))

    total = len(tasks) * len(CONDITIONS) * RUNS_PER_TASK
    done  = total - len(needed)
    print(f"\nAgent runs: {total} total ({done} done, {len(needed)} remaining)")

    lock      = threading.Lock()
    completed = [done]

    def _run_one(args):
        iid, cond, rn = args
        return run_agent(iid, cond["condition"], cond["primitive"], cond["budget"], rn,
                         config=cond.get("config"), compression_ratio=COMPRESSION_RATIO)

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {pool.submit(_run_one, item): item for item in needed}
        for fut in as_completed(futures):
            r = fut.result()
            with lock:
                completed[0] += 1
                results.append(r)
                existing_keys.add(r["key"])
                save_results(results)
                print(
                    f"  [{completed[0]:4d}/{total}]  {r['condition']:<14} r{r['run_num']} | "
                    f"{r['instance_id']}  calls={r['n_calls']} exit={r['exit_status']}"
                )

    return results


# ── SWE-bench evaluation ───────────────────────────────────────────────────────

def _find_eval_output(predictions_stem: str, run_id: str) -> Path | None:
    eval_dir = model_results_dir() / "eval"
    candidates = [
        eval_dir / f"{MODEL_TAG}.{run_id}.json",
        eval_dir / f"{predictions_stem}.{run_id}.json",
        eval_dir / f"{run_id}.json",
    ]
    for c in candidates:
        if c.exists():
            return c
    for p in eval_dir.glob(f"*{run_id}*.json"):
        return p
    return None


def evaluate_run(result: dict) -> bool | None:
    iid  = result["instance_id"]
    key  = result["key"]

    preds_dir  = model_results_dir() / "preds"
    preds_dir.mkdir(parents=True, exist_ok=True)
    eval_dir   = model_results_dir() / "eval"
    eval_dir.mkdir(parents=True, exist_ok=True)

    preds_stem = f"preds_{key}"
    preds_path = preds_dir / f"{preds_stem}.json"
    preds_path.write_text(json.dumps({
        iid: {
            "model_name_or_path": MODEL_TAG,
            "instance_id":        iid,
            "model_patch":        result["submission"],
        }
    }, indent=2))

    env = os.environ.copy()
    env["DOCKER_HOST"] = DOCKER_HOST

    cmd = [
        str(SWE_BENCH_PYTHON), "-m", "swebench.harness.run_evaluation",
        "--predictions_path", str(preds_path),
        "--max_workers", "1",
        "--instance_ids", iid,
        "--run_id", key,
        "--report_dir", str(eval_dir),
        "--dataset_name", "princeton-nlp/SWE-bench_Verified",
        "--split", DATASET_SPLIT,
    ]
    try:
        subprocess.run(cmd, cwd=eval_dir, env=env, capture_output=True, text=True, timeout=600)
    except subprocess.TimeoutExpired:
        print(f"    ! Eval timeout for {key}")
        return None
    except Exception as exc:
        print(f"    ! Eval error for {key}: {exc}")
        return None

    out_file = _find_eval_output(preds_stem, key)
    if out_file is None:
        print(f"    ! Eval output not found for {key}")
        return None
    try:
        data = json.loads(out_file.read_text())
        return iid in data.get("resolved_ids", [])
    except Exception as exc:
        print(f"    ! Could not parse eval output: {exc}")
        return None


def run_swebench_eval(results: list[dict]) -> list[dict]:
    # Skip seeded stub entries — they lack patch_generated/resolved fields and
    # their upstream eval JSONs are already symlinked into eval/ via p100_seed.py.
    work = [r for r in results if "seeded_from" not in r]

    to_eval  = [r for r in work if r["patch_generated"] and r["resolved"] is None]
    no_patch = sum(1 for r in work if not r["patch_generated"])
    print(f"\nSWE-bench evaluation: {len(to_eval)} runs to evaluate ({no_patch} had no patch); "
          f"{len(results) - len(work)} seeded stubs skipped\n")

    for i, r in enumerate(to_eval, 1):
        print(f"  [{i:4d}/{len(to_eval)}] {r['key']}")
        r["resolved"] = evaluate_run(r)
        print(f"    → {'RESOLVED' if r['resolved'] else ('FAILED' if r['resolved'] is False else 'ERROR')}")
        save_results(results)

    for r in work:
        if not r["patch_generated"]:
            r["resolved"] = False

    return results


# ── Run metadata ───────────────────────────────────────────────────────────────

def _write_run_info(n_tasks: int, total_runs: int, budget: int) -> None:
    """Write run_info.json and run_info.md into the results directory."""
    run_dir = model_results_dir()
    # Extract model name from config yaml if present, else fall back to stem
    try:
        import yaml
        cfg = yaml.safe_load(AGENT_CONFIG.read_text())
        _model_name = cfg.get("model", {}).get("model_name", AGENT_CONFIG.stem)
    except Exception:
        _model_name = AGENT_CONFIG.stem

    info = {
        "run_tag":      MODEL_TAG,
        "model":        _model_name,
        "agent_config": str(AGENT_CONFIG),
        "budget_tokens": budget,
        "n_tasks":      n_tasks,
        "runs_per_task": RUNS_PER_TASK,
        "conditions":   [c["condition"] for c in CONDITIONS],
        "n_conditions": len(CONDITIONS),
        "total_runs":   total_runs,
        "step_limit":   STEP_LIMIT,
        "started":      datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    (run_dir / "run_info.json").write_text(json.dumps(info, indent=2))

    cond_list = "\n".join(f"- {c['condition']} (budget={c['budget']:,})" for c in CONDITIONS)
    md = f"""# Run: {MODEL_TAG}

## Identity
| Field | Value |
|---|---|
| Run tag | `{MODEL_TAG}` |
| Agent config | `{AGENT_CONFIG}` |
| Budget | {budget:,} tokens (context window threshold) |
| Tasks | {n_tasks} |
| Conditions | {len(CONDITIONS)} |
| Runs per task | {RUNS_PER_TASK} |
| Total runs | {total_runs} |
| Step limit | {STEP_LIMIT} LLM calls per run |
| Started | {info['started']} |

## Conditions
{cond_list}

## Results layout
```
results/{MODEL_TAG}/
  run_info.json          ← this file (machine-readable)
  run_info.md            ← this file (human-readable)
  experiment_results.json
  {{instance_id}}/{{condition}}/run_{{n}}/
    trajectory.json
    token_log.json
    agent.log
```
"""
    (run_dir / "run_info.md").write_text(md)


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    global MODEL_TAG, AGENT_CONFIG, N_TASKS, N_TASKS_OVERRIDE, MAX_WORKERS

    parser = argparse.ArgumentParser(description="Experiment runner")
    parser.add_argument("--model-tag",    default="qwen35-a3b",
                        help="Short model identifier used as results subdirectory (default: qwen35-a3b)")
    parser.add_argument("--ablation",     default=None, metavar="NAME",
                        help="Ablation name (e.g. timing-10k). Results go to results/ablations/NAME/; "
                             "fixed 30-task set is used automatically.")
    parser.add_argument("--agent-config", default=None,
                        help="Path to agent config YAML (default: config-qwen-vllm.yaml)")
    parser.add_argument("--otrc-config",  default=None,
                        help="Override the agent config used by OTRC conditions "
                             "(online-trc, otrc-tr, otrc-su-partial, otrc-ss-partial). "
                             "Needed when --agent-config points at a non-Qwen model; "
                             "default is config-online-trc.yaml which targets Qwen port 8000.")
    parser.add_argument("--n-tasks",      type=int, default=None,
                        help="Override number of tasks (default: 100)")
    parser.add_argument("--tasks-file",   default=None,
                        help="Path to tasks JSON file (default: task_lists/selected_tasks.json)")
    parser.add_argument("--budget",       type=int,   default=None,
                        help="Override context-window budget for compressed conditions (default: 15000)")
    parser.add_argument("--depth",        type=float, default=None,
                        help="Compression ratio: fraction of budget retained after compression (default: 0.5)")
    parser.add_argument("--conditions",   nargs="+", default=None, metavar="COND",
                        help="Run only these conditions (e.g. --conditions online-trc full-context)")
    parser.add_argument("--max-workers",  type=int, default=None,
                        help=f"Concurrent agent runs (default: {MAX_WORKERS}). On Albus DP=8 server, 32 saturates.")
    grp = parser.add_mutually_exclusive_group()
    grp.add_argument("--eval-only",  action="store_true")
    grp.add_argument("--with-eval",  action="store_true")
    args = parser.parse_args()

    MODEL_TAG = args.model_tag
    if args.ablation is not None:
        global ABLATION_NAME
        ABLATION_NAME = args.ablation
    if args.tasks_file:
        global TASKS_FILE, TASKS_FILE_EXPLICIT
        TASKS_FILE = Path(args.tasks_file).resolve()
        TASKS_FILE_EXPLICIT = True
    if args.agent_config:
        AGENT_CONFIG = Path(args.agent_config).resolve()
    if args.otrc_config:
        otrc_path = Path(args.otrc_config).resolve()
        for c in CONDITIONS:
            cur = c.get("config")
            if cur is not None and "config-online-trc" in str(cur):
                c["config"] = otrc_path
    if args.n_tasks is not None:
        N_TASKS = args.n_tasks
        N_TASKS_OVERRIDE = args.n_tasks
    if args.max_workers is not None:
        MAX_WORKERS = args.max_workers
    if args.budget is not None:
        for c in CONDITIONS:
            if c["budget"] != 999_999_999:
                c["budget"] = args.budget
    if args.depth is not None:
        global COMPRESSION_RATIO
        COMPRESSION_RATIO = args.depth
    if args.conditions is not None:
        valid = {c["condition"] for c in CONDITIONS}
        unknown = set(args.conditions) - valid
        if unknown:
            print(f"ERROR: unknown conditions: {unknown}. Valid: {valid}")
            raise SystemExit(1)
        CONDITIONS[:] = [c for c in CONDITIONS if c["condition"] in args.conditions]

    model_results_dir().mkdir(parents=True, exist_ok=True)
    tasks = load_tasks()

    total  = len(tasks) * len(CONDITIONS) * RUNS_PER_TASK
    budget = next((c["budget"] for c in CONDITIONS if c["budget"] != 999_999_999), CONDITIONS[0]["budget"])

    print("=" * 72)
    print("EXPERIMENT")
    print(f"  Model tag  : {MODEL_TAG}")
    print(f"  Agent cfg  : {AGENT_CONFIG}")
    print(f"  Results dir: {model_results_dir()}")
    print(f"  Tasks      : {len(tasks)}")
    print(f"  Conditions : {[c['condition'] for c in CONDITIONS]}")
    print(f"  Budget     : {budget:,} tokens context window threshold")
    print(f"  Step limit : {STEP_LIMIT}")
    print(f"  Runs/config: {RUNS_PER_TASK}")
    print(f"  Total runs : {total}")
    print("=" * 72)

    # Write run_info.json and run_info.md for this run
    _write_run_info(len(tasks), total, budget)

    if not args.eval_only:
        results = run_all_agents(tasks)
    else:
        results = load_existing_results()
        if not results:
            print("No existing results. Run without --eval-only first.")
            raise SystemExit(1)

    if args.eval_only or args.with_eval:
        results = run_swebench_eval(results)


if __name__ == "__main__":
    main()
