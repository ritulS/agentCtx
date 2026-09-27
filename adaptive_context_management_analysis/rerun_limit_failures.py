#!/usr/bin/env python3
"""Re-run only the runs that hit the harness limits, with the limits raised.

Reads a ``failure_causes.csv`` written by ``classify_failure_causes.py``,
selects the rows whose ``cause`` is in ``--causes`` (default:
``timeout,step_limit`` = the 1500 s harness timeout and the 125 step limit),
and re-executes exactly those (task, condition, run_num) triples with a larger
``STEP_LIMIT`` / ``AGENT_TIMEOUT``.

The original runner (``agentctx.experiments.runner``, the module behind
``scripts/run_experiment.py``) is imported unchanged and only its module-level
limits and its result directory are overridden, in the same way
``scripts/run_experiment_iclr.py`` does.  Agent launches go through the
runner's SWE-bench adapter (``agentctx.benchmarks.swe_bench.SweBench._run_agent``),
which is where ``run_experiment.run_agent`` moved.  Nothing under
``ICLR_experiments/`` is touched: results go to a fresh directory under
``results/adaptive_context_management/swebench/reruns/`` (gitignored via
``results/*``) so they never leak into
``analysis/aggregate_benchmark_results.py``, which scans
``ICLR_experiments/swebench/**``.

Typical use (Qwen3.5-35B / full-context, the 82 timeout + step-limit runs):

    # 1. preview the plan, no directories created, nothing launched
    python3 adaptive_context_management_analysis/rerun_limit_failures.py \
        --step-limit 250 --timeout 3600 --dry-run

    # 2. launch (needs vLLM Qwen3.5-35B-A3B on :8000 and the podman socket;
    #    add an entry to Active_runs.md first)
    nohup python3 adaptive_context_management_analysis/rerun_limit_failures.py \
        --step-limit 250 --timeout 3600 --max-workers 8 --with-eval \
        > logs/rerun_qwen35b_fc_limits.log 2>&1 &

    # 3. evaluate later / retry evaluation errors
    python3 adaptive_context_management_analysis/rerun_limit_failures.py \
        --step-limit 250 --timeout 3600 --eval-only

Output directory (default):
    results/adaptive_context_management/swebench/reruns/<model>__<cell>__<causes>__step<S>__t<T>/
        experiment_results.json   same schema as the runner + rerun_of / original_cause
        rerun_manifest.csv        one row per selected run (original cause, dirs)
        rerun_info.json           limits, filters, counts
        <task>/<condition>/run_<n>/{agent.log,trajectory.json,token_log.json}
        preds/ eval/              written by --with-eval / --eval-only

Re-launching with the same arguments resumes: keys already present in the
output ``experiment_results.json`` are skipped unless ``--force`` is given.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import threading
from collections import Counter, OrderedDict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(HERE))

from agentctx.experiments import runner               # noqa: E402
from agentctx.experiments.conditions import CONDITIONS  # noqa: E402
from agentctx.benchmarks import create_benchmark      # noqa: E402
from classify_failure_causes import (                 # noqa: E402
    DIFFICULTY_ALIASES, DIFFICULTY_LABELS, split_list,
)

ORIG_STEP_LIMIT = runner.STEP_LIMIT          # 125
ORIG_AGENT_TIMEOUT = runner.AGENT_TIMEOUT    # 1500 s

DEFAULT_CAUSES_CSV = HERE / "results" / "model=qwen35b__primitive=fc" / "failure_causes.csv"
DEFAULT_OUT_ROOT = ROOT / "results" / "adaptive_context_management" / "swebench" / "reruns"
DEFAULT_AGENT_CONFIG = ROOT / "configs" / "config-qwen-vllm.yaml"


def run_key(instance_id: str, condition: str, run_num: int) -> str:
    """Result-row key, as ``SweBench._run_key`` builds it."""
    return f"{instance_id}__{condition}__r{run_num}"


def run_dir(instance_id: str, condition: str, run_num: int) -> Path:
    """Per-run output directory below the (overridden) result directory."""
    return runner.model_results_dir() / instance_id / condition / f"run_{run_num}"
MANIFEST_COLS = [
    "key", "task", "condition", "run", "model", "cell", "budget", "depth", "difficulty",
    "original_cause", "original_exit_status", "original_returncode", "original_step_count",
    "original_latency_e2e_s", "original_run_dir", "new_run_dir",
]


def rel(path: Path) -> str:
    """Repo-relative if possible, else absolute (e.g. --out-root outside the repo)."""
    try:
        return str(Path(path).resolve().relative_to(ROOT))
    except ValueError:
        return str(Path(path).resolve())


# ── Selection ──────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--causes-csv", default=str(DEFAULT_CAUSES_CSV),
                   help="failure_causes.csv from classify_failure_causes.py "
                        f"(default: {DEFAULT_CAUSES_CSV.relative_to(ROOT)})")
    p.add_argument("--causes", default="timeout,step_limit",
                   help="cause values to re-run, comma-separated (default: timeout,step_limit)")
    p.add_argument("--difficulty", nargs="*", default=None,
                   help="restrict to these difficulties (u15 15m1h 1to4h gt4h or full labels)")
    p.add_argument("--task", nargs="*", default=None, help="restrict to these instance_ids")
    p.add_argument("--run", nargs="*", default=None, help="restrict to these run numbers (1 2 3)")
    p.add_argument("--order", choices=("hard-first", "easy-first", "task"), default="hard-first",
                   help="launch order: hardest difficulty first (default), easiest first, or by task id")
    p.add_argument("--limit", type=int, default=None,
                   help="only the first N selected runs after ordering (smoke test)")

    p.add_argument("--step-limit", type=int, required=True,
                   help=f"new agent step limit (original runs: {ORIG_STEP_LIMIT})")
    p.add_argument("--timeout", type=int, required=True,
                   help=f"new per-run harness timeout in seconds (original runs: {ORIG_AGENT_TIMEOUT})")

    p.add_argument("--out-root", default=str(DEFAULT_OUT_ROOT),
                   help=f"parent of the result directory (default: {DEFAULT_OUT_ROOT.relative_to(ROOT)})")
    p.add_argument("--name", default=None, help="override the auto-generated result directory name")
    p.add_argument("--agent-config", default=str(DEFAULT_AGENT_CONFIG),
                   help=f"agent config YAML (default: {DEFAULT_AGENT_CONFIG.relative_to(ROOT)})")
    p.add_argument("--model-tag", default="qwen35-a3b", help="model tag recorded in preds/eval (default: qwen35-a3b)")
    p.add_argument("--max-workers", type=int, default=8,
                   help="concurrent agent runs against the shared vLLM server (default: 8)")
    p.add_argument("--force", action="store_true", help="re-run keys already present in the output results file")
    p.add_argument("--dry-run", action="store_true", help="print the plan and exit; creates nothing")
    grp = p.add_mutually_exclusive_group()
    grp.add_argument("--with-eval", action="store_true", help="run SWE-bench evaluation after the agent runs")
    grp.add_argument("--eval-only", action="store_true", help="only evaluate existing results in the output dir")
    args = p.parse_args()
    if args.step_limit <= ORIG_STEP_LIMIT and args.timeout <= ORIG_AGENT_TIMEOUT:
        p.error(f"neither limit is raised (current: step {ORIG_STEP_LIMIT}, timeout {ORIG_AGENT_TIMEOUT}s)")
    return args


def norm_difficulties(values) -> set[str] | None:
    if not values:
        return None
    out = set()
    for v in split_list(values):
        if v not in DIFFICULTY_ALIASES:
            raise SystemExit(f"unknown difficulty {v!r}; use one of {sorted(set(DIFFICULTY_ALIASES))}")
        out.add(DIFFICULTY_ALIASES[v])
    return out


def select_rows(args) -> list[dict]:
    path = Path(args.causes_csv)
    if not path.exists():
        raise SystemExit(f"{path} not found; run classify_failure_causes.py first")
    causes = set(split_list([args.causes]))
    diffs = norm_difficulties(args.difficulty)
    tasks = set(split_list(args.task)) if args.task else None
    runs = set(split_list(args.run)) if args.run else None

    rows = []
    with path.open(newline="") as f:
        for r in csv.DictReader(f):
            if r["cause"] not in causes:
                continue
            if diffs and r["difficulty"] not in diffs:
                continue
            if tasks and r["task"] not in tasks:
                continue
            if runs and r["run"] not in runs:
                continue
            rows.append(r)
    rows.sort(key=lambda r: order_key(r, args.order))
    if args.limit is not None:
        rows = rows[: args.limit]
    if not rows:
        raise SystemExit("no runs selected")

    for k in ("model", "cell", "condition", "budget", "depth"):
        vals = {r[k] for r in rows}
        if len(vals) != 1:
            raise SystemExit(f"selected runs span several {k} values {sorted(vals)}; "
                             "re-run one cell at a time (use --causes-csv from a narrower classify run)")
    return rows


def order_key(r: dict, order: str):
    """Sort key for the launch order. Difficulty rank follows DIFFICULTY_LABELS
    (<15 min fix < 15 min - 1 hour < 1-4 hours < >4 hours); unknown labels go last."""
    labels = list(DIFFICULTY_LABELS)
    rank = labels.index(r["difficulty"]) if r["difficulty"] in labels else len(labels)
    tail = (r["task"], r["condition"], int(r["run"]))
    if order == "hard-first":
        return (-rank, *tail)
    if order == "easy-first":
        return (rank, *tail)
    return tail


def condition_spec(condition: str) -> dict:
    for c in CONDITIONS:
        if c["condition"] == condition:
            return c
    raise SystemExit(f"condition {condition!r} is not defined in agentctx.experiments.conditions")


def build_name(args, rows) -> str:
    if args.name:
        return args.name
    r = rows[0]
    causes = "+".join(sorted({x["cause"] for x in rows}))
    parts = [r["model"], r["cell"], causes, f"step{args.step_limit}", f"t{args.timeout}"]
    if args.difficulty:
        parts.append("diff=" + "+".join(sorted(split_list(args.difficulty))))
    if args.run:
        parts.append("run=" + "+".join(sorted(split_list(args.run))))
    if args.task:
        parts.append(f"tasks={len(set(split_list(args.task)))}")
    if args.limit is not None:
        parts.append(f"limit{args.limit}")
    return "__".join(parts)


# ── Plan output ────────────────────────────────────────────────────────────────

def print_plan(rows, out_dir: Path, args) -> None:
    r = rows[0]
    print("=" * 72)
    print("RERUN WITH RAISED LIMITS")
    print(f"  Source csv  : {rel(args.causes_csv)}")
    print(f"  Cell        : {r['model']} / {r['cell']} ({r['condition']}, budget={r['budget']}, depth={r['depth']})")
    print(f"  Causes      : {sorted({x['cause'] for x in rows})}")
    print(f"  Step limit  : {ORIG_STEP_LIMIT} -> {args.step_limit}")
    print(f"  Timeout     : {ORIG_AGENT_TIMEOUT}s -> {args.timeout}s")
    print(f"  Agent cfg   : {args.agent_config}")
    print(f"  Workers     : {args.max_workers}")
    print(f"  Order       : {args.order}")
    print(f"  Output dir  : {out_dir}")
    print(f"  Runs        : {len(rows)} ({len({x['task'] for x in rows})} tasks)")
    print()
    by = Counter((x["difficulty"], x["cause"]) for x in rows)
    causes = sorted({x["cause"] for x in rows})
    print(f"  {'difficulty':<18}" + "".join(f"{c:>14}" for c in causes) + f"{'total':>8}")
    for d in list(DIFFICULTY_LABELS) + sorted({x["difficulty"] for x in rows} - set(DIFFICULTY_LABELS)):
        n = [by.get((d, c), 0) for c in causes]
        if sum(n):
            print(f"  {d:<18}" + "".join(f"{v:>14}" for v in n) + f"{sum(n):>8}")
    print(f"  {'total':<18}" + "".join(f"{sum(by.get((d, c), 0) for d in {x['difficulty'] for x in rows}):>14}" for c in causes)
          + f"{len(rows):>8}")
    print()
    print("  launch order:")
    for i, x in enumerate(rows, 1):
        print(f"  {i:3d}. {x['task']:<40} r{x['run']}  {x['difficulty']:<16} {x['cause']:<10} "
              f"steps={x['step_count']:>4} e2e={float(x['latency_e2e_s'] or 0):7.0f}s")
    print("=" * 72)


def write_manifest(rows, out_dir: Path) -> None:
    with (out_dir / "rerun_manifest.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=MANIFEST_COLS)
        w.writeheader()
        for r in rows:
            w.writerow({
                "key": run_key(r["task"], r["condition"], int(r["run"])),
                "task": r["task"], "condition": r["condition"], "run": r["run"],
                "model": r["model"], "cell": r["cell"], "budget": r["budget"], "depth": r["depth"],
                "difficulty": r["difficulty"],
                "original_cause": r["cause"],
                "original_exit_status": r["exit_status"],
                "original_returncode": r["harness_returncode"],
                "original_step_count": r["step_count"],
                "original_latency_e2e_s": r["latency_e2e_s"],
                "original_run_dir": r["run_dir"],
                "new_run_dir": rel(run_dir(r["task"], r["condition"], int(r["run"]))),
            })


def write_info(rows, out_dir: Path, args) -> None:
    info = {
        "created": datetime.now().isoformat(timespec="seconds"),
        "source_causes_csv": str(args.causes_csv),
        "causes": sorted({x["cause"] for x in rows}),
        "filters": {"difficulty": args.difficulty, "task": args.task, "run": args.run, "limit": args.limit},
        "order": args.order,
        "model": rows[0]["model"], "cell": rows[0]["cell"], "condition": rows[0]["condition"],
        "budget": int(rows[0]["budget"]), "depth": float(rows[0]["depth"]),
        "original_step_limit": ORIG_STEP_LIMIT,
        "original_agent_timeout_s": ORIG_AGENT_TIMEOUT,
        "step_limit": args.step_limit, "agent_timeout_s": args.timeout,
        "agent_config": str(args.agent_config), "model_tag": args.model_tag,
        "max_workers": args.max_workers,
        "n_runs": len(rows), "n_tasks": len({x["task"] for x in rows}),
        "by_difficulty": {d: n for d, n in Counter(x["difficulty"] for x in rows).items()},
        "by_cause": {c: n for c, n in Counter(x["cause"] for x in rows).items()},
        "command": " ".join(sys.argv),
    }
    (out_dir / "rerun_info.json").write_text(json.dumps(info, indent=2))


# ── Execution ──────────────────────────────────────────────────────────────────

def configure_runner(args, out_dir: Path) -> None:
    """Point the imported runner at the new limits / result dir (like run_experiment_iclr.py)."""
    runner.STEP_LIMIT = args.step_limit
    runner.AGENT_TIMEOUT = args.timeout
    runner.MAX_WORKERS = args.max_workers
    runner.MODEL_TAG = args.model_tag
    runner.AGENT_CONFIG = Path(args.agent_config).resolve()
    runner.model_results_dir = lambda: out_dir
    runner.BENCHMARK = create_benchmark(
        "swe-bench", workspace_root=ROOT, model_tag=args.model_tag, results_dir=out_dir,
    )


def run_selected(rows, args) -> list[dict]:
    results = runner.load_existing_results()
    existing = {r["key"] for r in results}
    spec = condition_spec(rows[0]["condition"])
    budget = int(rows[0]["budget"])
    depth = float(rows[0]["depth"])

    work = []
    for r in rows:
        key = run_key(r["task"], r["condition"], int(r["run"]))
        if key in existing and not args.force:
            continue
        work.append((r, key))
    if args.force:
        drop = {k for _, k in work}
        results = [x for x in results if x["key"] not in drop]
        runner.save_results(results)
    print(f"\nAgent runs: {len(rows)} selected ({len(rows) - len(work)} already done, {len(work)} to run)")

    lock = threading.Lock()
    done = [len(rows) - len(work)]

    def _one(item):
        r, key = item
        res = runner.BENCHMARK._run_agent(
            instance_id=r["task"], condition=r["condition"], primitive=spec["primitive"],
            budget=budget, run_num=int(r["run"]),
            agent_config=runner.AGENT_CONFIG,
            step_limit=runner.STEP_LIMIT, agent_timeout=runner.AGENT_TIMEOUT,
            config=spec.get("config"), compression_ratio=depth,
        )
        res["rerun_of"] = r["run_dir"]
        res["original_cause"] = r["cause"]
        res["step_limit"] = args.step_limit
        res["agent_timeout_s"] = args.timeout
        return res

    # Submission order == launch order (hard-first by default); the pool pulls
    # the next item as soon as a worker is free.
    with ThreadPoolExecutor(max_workers=args.max_workers) as pool:
        futs = {pool.submit(_one, it): it for it in work}
        for fut in as_completed(futs):
            res = fut.result()
            with lock:
                done[0] += 1
                results.append(res)
                runner.save_results(results)
                print(f"  [{done[0]:3d}/{len(rows)}] {res['instance_id']} r{res['run_num']} | "
                      f"was={res['original_cause']:<10} now: calls={res['n_calls']} "
                      f"exit={res['exit_status']} e2e={res['e2e_latency_s']:.0f}s")
    return results


def print_outcome_summary(results, rows) -> None:
    orig = {run_key(r["task"], r["condition"], int(r["run"])): r for r in rows}
    tab = Counter()
    for res in results:
        r = orig.get(res["key"])
        if r is None:
            continue
        if res["returncode"] == -1:
            new = "timeout"
        elif res["exit_status"] == "LimitsExceeded":
            new = "step_limit"
        elif res["exit_status"] == "Submitted":
            new = {True: "resolved", False: "submitted_unresolved", None: "submitted_uneval"}[res.get("resolved")]
        else:
            new = f"other:{res['exit_status'] or 'none'}"
        tab[(r["difficulty"], r["cause"], new)] += 1
    if not tab:
        return
    print("\nOutcome after re-run (difficulty, original cause -> new outcome):")
    for (d, c, n), k in sorted(tab.items(), key=lambda kv: (list(DIFFICULTY_LABELS).index(kv[0][0]) if kv[0][0] in DIFFICULTY_LABELS else 99, kv[0])):
        print(f"  {d:<18} {c:<10} -> {n:<22} {k}")


def main() -> None:
    args = parse_args()
    rows = select_rows(args)
    out_dir = Path(args.out_root).resolve() / build_name(args, rows)
    print_plan(rows, out_dir, args)
    if args.dry_run:
        print("dry run: nothing launched, nothing written")
        return

    out_dir.mkdir(parents=True, exist_ok=True)
    configure_runner(args, out_dir)
    write_manifest(rows, out_dir)
    write_info(rows, out_dir, args)

    if args.eval_only:
        results = runner.load_existing_results()
        if not results:
            raise SystemExit("no results to evaluate in " + str(out_dir))
    else:
        results = run_selected(rows, args)

    if args.with_eval or args.eval_only:
        results = runner.BENCHMARK.evaluate_results(results, runner.save_results)
        runner.save_results(results)

    print_outcome_summary(results, rows)
    print(f"\nResults: {out_dir / 'experiment_results.json'}")
    print(f"Manifest: {out_dir / 'rerun_manifest.csv'}")


if __name__ == "__main__":
    main()
