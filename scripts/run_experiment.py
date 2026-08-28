#!/usr/bin/env python3
"""Run context-compression experiments across tasks and conditions.

Benchmark-specific behavior lives in ``scripts/datasets/``. This module owns
only experiment expansion, parallel execution, metrics, and result persistence.

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
  python scripts/run_experiment_expansion.py
  python scripts/run_experiment_expansion.py --with-eval
  python scripts/run_experiment_expansion.py --eval-only
"""

import argparse
import json
import os
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

from bench_adapters import BENCHMARKS, create_benchmark

# ── Configuration ──────────────────────────────────────────────────────────────

WORKSPACE_ROOT       = Path(__file__).parent.parent
MINI_SWE_AGENT       = WORKSPACE_ROOT / "mini-swe-agent"
AGENT_CONFIG         = WORKSPACE_ROOT / "configs/config-qwen-vllm.yaml"
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
     "config": WORKSPACE_ROOT / "configs/config-online-trc.yaml"},
    # Stacked primitives: TRC (KEEP_RECENT=3) fires first; second primitive is fallback
    {"condition": "trc-su",  "primitive": "trc_summarize",           "budget": 15_000},
    {"condition": "trc-ss",  "primitive": "trc_structured_summarize","budget": 15_000},
    # trc-tr = existing tool-result-clear (already has truncation fallback built-in)
    # Partial summary primitives: summarize the head, keep budget-fitting tail verbatim
    {"condition": "summarization-partial",        "primitive": "summarization_partial",        "budget": 15_000},
    {"condition": "structured-summarize-partial", "primitive": "structured_summarize_partial", "budget": 15_000},
    # OTRC stacked variants: per-step freeze-window clearing + budget-triggered fallback.
    # All three reuse configs/config-online-trc.yaml (agent prompts expect cleared tool stubs).
    {"condition": "otrc-tr",         "primitive": "online_trc",                              "budget": 15_000,
     "config": WORKSPACE_ROOT / "configs/config-online-trc.yaml"},
    {"condition": "otrc-su-partial", "primitive": "online_trc_summarize_partial",            "budget": 15_000,
     "config": WORKSPACE_ROOT / "configs/config-online-trc.yaml"},
    {"condition": "otrc-ss-partial", "primitive": "online_trc_structured_summarize_partial", "budget": 15_000,
     "config": WORKSPACE_ROOT / "configs/config-online-trc.yaml"},
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

# Selected in main(). All benchmark-specific operations go through this adapter.
BENCHMARK = None

# ── Helpers ────────────────────────────────────────────────────────────────────

def run_key(instance_id: str, condition: str, run_num: int) -> str:
    return f"{instance_id}__{condition}__r{run_num}"


def run_dir(instance_id: str, condition: str, run_num: int) -> Path:
    return model_results_dir() / instance_id / condition / f"run_{run_num}"


def results_file_path() -> Path:
    return model_results_dir() / "experiment_results.json"


def load_tasks() -> list[dict]:
    return BENCHMARK.load_tasks(
        TASKS_FILE,
        tasks_file_explicit=TASKS_FILE_EXPLICIT,
        ablation_name=ABLATION_NAME,
        ablation_tasks_file=ABLATION_TASKS_FILE,
        n_tasks=N_TASKS,
        n_tasks_override=N_TASKS_OVERRIDE,
    )


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
    env.update(BENCHMARK.agent_environment())

    local_bin = str(Path.home() / ".local" / "bin")
    if local_bin not in env.get("PATH", ""):
        env["PATH"] = local_bin + ":" + env.get("PATH", "")

    # memory.py lives in the repo root; add it to PYTHONPATH so default.py can
    # `import memory` regardless of the cwd the subprocess starts in.
    env["PYTHONPATH"] = str(WORKSPACE_ROOT) + (":" + env["PYTHONPATH"] if "PYTHONPATH" in env else "")

    # Build -c config chain. mini-swe-agent merges configs in order, later overriding earlier.
    # When a condition has a config (e.g. OTRC's prompts), load it first, then layer the user's
    # --agent-config on top so the model section (model_name, api_base) wins.
    config_chain = []
    if config is not None:
        config_chain.append(str(config))
        if AGENT_CONFIG and Path(AGENT_CONFIG) != Path(config):
            config_chain.append(str(AGENT_CONFIG))
    else:
        config_chain.append(str(AGENT_CONFIG))
    cmd = BENCHMARK.build_agent_command(instance_id, config_chain, traj_file, STEP_LIMIT)

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

    # The adapter translates its native trajectory into result fields.
    outcome = BENCHMARK.empty_outcome()
    if traj_file.exists():
        try:
            outcome = BENCHMARK.parse_trajectory(traj_file)
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
    result.update(outcome)

    icon = "P" if outcome["submission_generated"] else "x"
    print(
        f"    [{icon}] e2e={e2e_latency:.0f}s  calls={outcome['n_calls']:3d}  "
        f"comp_events={result['compression_events']:2d}  "
        f"exit={outcome['exit_status']}"
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
        "benchmark":    BENCHMARK.name,
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
    global MODEL_TAG, AGENT_CONFIG, N_TASKS, N_TASKS_OVERRIDE, MAX_WORKERS, RUNS_PER_TASK, BENCHMARK

    parser = argparse.ArgumentParser(description="Experiment runner")
    parser.add_argument("--benchmark", choices=sorted(BENCHMARKS), default="swe-bench",
                        help="Benchmark adapter to use (default: swe-bench)")
    parser.add_argument("--model-tag",    default="qwen35-a3b",
                        help="Short model identifier used as results subdirectory (default: qwen35-a3b)")
    parser.add_argument("--ablation",     default=None, metavar="NAME",
                        help="Ablation name (e.g. timing-10k). Results go to results/ablations/NAME/; "
                             "fixed 30-task set is used automatically.")
    parser.add_argument("--agent-config", default=None,
                        help="Path to agent config YAML (default: configs/config-qwen-vllm.yaml)")
    parser.add_argument("--otrc-config",  default=None,
                        help="Override the agent config used by OTRC conditions "
                             "(online-trc, otrc-tr, otrc-su-partial, otrc-ss-partial). "
                             "Needed when --agent-config points at a non-Qwen model; "
                             "default is configs/config-online-trc.yaml which targets Qwen port 8000.")
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
    parser.add_argument("--runs-per-task", type=int, default=None,
                        help=f"Override runs per (task, condition) (default: {RUNS_PER_TASK}). "
                             "Existing runs already recorded in experiment_results.json are skipped, "
                             "so raising this resumes by adding only the missing run numbers.")
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
    if args.runs_per_task is not None:
        RUNS_PER_TASK = args.runs_per_task
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
    BENCHMARK = create_benchmark(
        args.benchmark,
        workspace_root=WORKSPACE_ROOT,
        model_tag=MODEL_TAG,
        results_dir=model_results_dir(),
    )
    tasks = load_tasks()

    total  = len(tasks) * len(CONDITIONS) * RUNS_PER_TASK
    budget = next((c["budget"] for c in CONDITIONS if c["budget"] != 999_999_999), CONDITIONS[0]["budget"])

    print("=" * 72)
    print("EXPERIMENT")
    print(f"  Benchmark  : {BENCHMARK.name}")
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
        results = BENCHMARK.evaluate_results(results, save_results)


if __name__ == "__main__":
    main()
