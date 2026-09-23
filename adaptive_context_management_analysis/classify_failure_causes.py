#!/usr/bin/env python3
"""Classify why each SWE-bench run failed, from swebench_outcomes.csv + run logs.

Failure causes (column `cause`):
  context_limit         vLLM --max-model-len exceeded (litellm BadRequestError /
                        ContextWindowExceededError, "param":"input_tokens","code":400
                        in agent.log). qwen35b=102,400 tok; devstral24b/glm47flash=65,536.
  timeout               harness AGENT_TIMEOUT (1500 s) killed the agent -> returncode -1.
  step_limit            STEP_LIMIT (125 LLM calls) reached without submit (LimitsExceeded).
  submitted_unresolved  agent submitted on its own but the patch failed evaluation
                        (`submit_detail` = wrong_patch | empty_patch).
  other:<exit_status>   e.g. other:InternalServerError.
  unrecorded            no returncode / exit_status recorded anywhere.
  resolved              only with --include-resolved.

Precedence: resolved > Submitted > LimitsExceeded > context_limit (exit_status or
agent.log signature) > timeout (returncode -1) > other > unrecorded. A run that hit the
context limit and then hung until the 1500 s kill is therefore `context_limit` with
`harness_returncode=-1`; `ctx_error_in_log` records the log signal independently.

Filters are AND-ed; every list-valued filter accepts comma-separated values.
Results go to <out-root>/<slug built from the filters>/ :
  failure_causes.csv      one row per run (task, run, model, primitive, budget, depth,
                          cause, ... )
  summary_by_cause.csv    cause -> n_runs, n_tasks
  summary_pivot.csv       (model, section, primitive, budget, depth) x cause
  summary_by_difficulty.csv  difficulty x cause
  args.json               the filters used, resolved cohort/difficulty labels, constants

Example:
  python3 adaptive_context_management_analysis/classify_failure_causes.py \
      --model qwen35b --primitive fc --difficulty u15
"""
import argparse
import csv
import json
import os
import re
import sys
from collections import Counter, OrderedDict, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)

DEFAULT_OUTCOMES = os.path.join(REPO, "analysis", "outcomes", "swebench_outcomes.csv")
DIFFICULTY_JSON = os.path.join(HERE, "swebench_verified_difficulty.json")
DEFAULT_OUT_ROOT = os.path.join(HERE, "results")

STEP_LIMIT = 125       # scripts/run_experiment.py
AGENT_TIMEOUT_S = 1500  # scripts/run_experiment.py
MODEL_CTX_WINDOW = {   # vLLM --max-model-len (ICLR_experiments/budget_calibration_swe.md, scripts/start_vllm_*.sh)
    "qwen35b": 102400,
    "devstral24b": 65536,
    "glm47flash": 65536,
}
CTX_EXIT_STATUSES = {"BadRequestError", "ContextWindowExceededError"}
CTX_LOG_RE = re.compile(
    r'"param":"input_tokens","code":400'
    r"|maximum context length"
    r"|ContextWindowExceededError"
    r"|context_length_exceeded"
)

COHORT_FILES = OrderedDict([
    ("p100", "task_lists/p100_all_100_tasks.json"),
    ("abl30", "task_lists/ablation_30tasks.json"),
    ("abl25", "task_lists/ablation_25tasks.json"),
    ("new70", "task_lists/p100_new_tasks.json"),
])

DIFFICULTY_LABELS = OrderedDict([
    ("<15 min fix", "u15"),
    ("15 min - 1 hour", "15m1h"),
    ("1-4 hours", "1to4h"),
    (">4 hours", "gt4h"),
])
DIFFICULTY_ALIASES = {
    "u15": "<15 min fix", "<15m": "<15 min fix", "lt15m": "<15 min fix", "<15 min fix": "<15 min fix",
    "15m1h": "15 min - 1 hour", "15m-1h": "15 min - 1 hour", "15 min - 1 hour": "15 min - 1 hour",
    "1to4h": "1-4 hours", "1-4h": "1-4 hours", "1-4 hours": "1-4 hours",
    "gt4h": ">4 hours", ">4h": ">4 hours", "4h+": ">4 hours", ">4 hours": ">4 hours",
}

CAUSE_ORDER = ["context_limit", "timeout", "step_limit", "submitted_unresolved",
               "other", "unrecorded", "resolved"]
CAUSE_LABEL = {
    "context_limit": "vLLM context window (max-model-len) exceeded",
    "timeout": f"{AGENT_TIMEOUT_S} s harness timeout",
    "step_limit": f"{STEP_LIMIT} step limit (LimitsExceeded)",
    "submitted_unresolved": "agent submitted, patch did not resolve",
    "other": "other (API error etc.)",
    "unrecorded": "no exit_status / returncode recorded",
    "resolved": "resolved",
}


def split_list(v):
    if v is None:
        return None
    out = []
    for item in v:
        out += [x.strip() for x in item.split(",") if x.strip()]
    return out or None


def load_tasks_arg(values):
    """--task accepts instance ids and/or @file (json list of {instance_id} or ids, or txt)."""
    if not values:
        return None
    ids = set()
    for v in values:
        if v.startswith("@"):
            path = v[1:]
            if path.endswith(".json"):
                data = json.load(open(path))
                for x in data:
                    ids.add(x["instance_id"] if isinstance(x, dict) else x)
            else:
                for line in open(path):
                    line = line.split()
                    if line:
                        ids.add(line[0])
        else:
            ids.add(v)
    return ids


def load_cohorts():
    cohorts = {}
    for name, rel in COHORT_FILES.items():
        path = os.path.join(REPO, rel)
        if os.path.exists(path):
            cohorts[name] = {x["instance_id"] for x in json.load(open(path))}
    return cohorts


def load_difficulty():
    if not os.path.exists(DIFFICULTY_JSON):
        try:
            from datasets import load_dataset  # noqa
            ds = load_dataset("princeton-nlp/SWE-Bench_Verified", split="test")
            m = {ex["instance_id"]: ex["difficulty"] for ex in ds}
            os.makedirs(os.path.dirname(DIFFICULTY_JSON), exist_ok=True)
            json.dump(m, open(DIFFICULTY_JSON, "w"), indent=0, sort_keys=True)
        except Exception as e:  # pragma: no cover
            print(f"! difficulty file missing and HF download failed: {e}", file=sys.stderr)
            return {}
    return json.load(open(DIFFICULTY_JSON))


def run_dir(row):
    return os.path.join(REPO, os.path.dirname(row["source_file"]), row["task_name"],
                        row["condition"], f"run_{row['run_num']}")


def parse_list_col(s):
    try:
        v = json.loads(s) if s else []
        return v if isinstance(v, list) else []
    except Exception:
        return []


def trajectory_exit_status(rdir):
    p = os.path.join(rdir, "trajectory.json")
    if not os.path.exists(p):
        return "", None
    try:
        info = json.load(open(p)).get("info", {})
    except Exception:
        return "", None
    return info.get("exit_status") or "", (info.get("model_stats") or {}).get("api_calls")


def log_has_ctx_error(rdir):
    p = os.path.join(rdir, "agent.log")
    if not os.path.exists(p):
        return None
    try:
        with open(p, errors="replace") as f:
            return bool(CTX_LOG_RE.search(f.read()))
    except Exception:
        return None


def classify(row, scan_logs=True):
    rdir = run_dir(row)
    exit_status = row["exit_status"]
    rc = row["returncode"]
    api_calls = None
    source = "outcomes_csv"
    if not exit_status and rc != "-1":
        # harness recorded nothing -> fall back to trajectory.json. Not done for rc == -1:
        # a run killed at AGENT_TIMEOUT can leave a trajectory whose exit_status says
        # "Submitted" with no patch, and the kill is the real trigger.
        exit_status, api_calls = trajectory_exit_status(rdir)
        source = "trajectory.json" if exit_status else "none"
    resolved = row["resolved"] == "True" or row["failure_mode"] == "resolved"
    patch = row["patch_generated"] == "True"

    ctx_in_log = None
    if exit_status not in ("Submitted", "LimitsExceeded") and not resolved and scan_logs:
        ctx_in_log = log_has_ctx_error(rdir)

    if resolved:
        cause, detail = "resolved", ""
    elif exit_status == "Submitted":
        cause, detail = "submitted_unresolved", "wrong_patch" if patch else "empty_patch"
    elif exit_status == "LimitsExceeded":
        cause, detail = "step_limit", ""
    elif exit_status in CTX_EXIT_STATUSES or ctx_in_log:
        cause = "context_limit"
        detail = exit_status if exit_status in CTX_EXIT_STATUSES else "log_signature"
        if rc == "-1":
            detail += f";hung_until_{AGENT_TIMEOUT_S}s_kill"
    elif rc == "-1":
        cause, detail = "timeout", ""
    elif exit_status:
        cause, detail = f"other:{exit_status}", ""
    else:
        cause, detail = "unrecorded", "no returncode/exit_status in outcomes csv or trajectory"
    return dict(cause=cause, cause_detail=detail, exit_status=exit_status,
                exit_status_source=source, ctx_error_in_log=("" if ctx_in_log is None else str(ctx_in_log)),
                trajectory_api_calls=("" if api_calls is None else api_calls), run_dir=os.path.relpath(rdir, REPO))


def build_slug(args, filters):
    parts = []
    for key in ["model", "section", "primitive", "condition", "cell", "budget", "depth",
                "difficulty", "cohort", "run", "task"]:
        vals = filters.get(key)
        if not vals:
            continue
        if key == "difficulty":
            vals = [DIFFICULTY_LABELS.get(v, v) for v in vals]
        if key == "task":
            vals = [f"{len(vals)}tasks"] if len(vals) > 3 else sorted(vals)
        parts.append(f"{key}={'+'.join(str(v) for v in sorted(vals, key=str))}")
    if args.include_resolved:
        parts.append("incl-resolved")
    slug = "__".join(parts) if parts else "all"
    if args.tag:
        slug += f"__{args.tag}"
    return re.sub(r"[^A-Za-z0-9_.+=\-]", "-", slug)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--outcomes", default=DEFAULT_OUTCOMES)
    ap.add_argument("--out-root", default=DEFAULT_OUT_ROOT)
    ap.add_argument("--name", help="override the auto-generated result directory name")
    ap.add_argument("--tag", help="suffix appended to the auto-generated directory name")
    ap.add_argument("--model", nargs="+", help="model_key: qwen35b devstral24b glm47flash")
    ap.add_argument("--section", nargs="+", help="experiment_section: main ablation")
    ap.add_argument("--primitive", nargs="+", help="fc tr su-full su-partial ss ss-partial trc trc-su trc-ss otrc otrc-tr otrc-su-partial otrc-ss-partial")
    ap.add_argument("--condition", nargs="+", help="condition dir name, e.g. full-context truncation")
    ap.add_argument("--cell", nargs="+", help="cell id, e.g. di__binf__fc d05__b15k__tr")
    ap.add_argument("--budget", nargs="+", help="token_budget, e.g. 15000 (FC = 999999999)")
    ap.add_argument("--depth", nargs="+", help="0.3 0.5 0.7")
    ap.add_argument("--run", nargs="+", help="run_num, e.g. 1 2 3")
    ap.add_argument("--task", nargs="+", help="instance ids and/or @path (json list or txt, first token per line)")
    ap.add_argument("--difficulty", nargs="+", help="u15 | 15m1h | 1to4h | gt4h (or the SWE-bench Verified labels)")
    ap.add_argument("--cohort", nargs="+", choices=list(COHORT_FILES), help="p100 abl30 abl25 new70")
    ap.add_argument("--include-resolved", action="store_true", help="also list resolved runs (cause=resolved)")
    ap.add_argument("--no-log-scan", action="store_true", help="skip reading agent.log for the context-limit signature")
    args = ap.parse_args()

    filters = {k: split_list(getattr(args, k)) for k in
               ["model", "section", "primitive", "condition", "cell", "budget", "depth", "run", "difficulty", "cohort"]}
    filters["task"] = load_tasks_arg(split_list(args.task))
    if filters["difficulty"]:
        bad = [d for d in filters["difficulty"] if d not in DIFFICULTY_ALIASES]
        if bad:
            ap.error(f"unknown difficulty {bad}; use {sorted(set(DIFFICULTY_ALIASES))}")
        filters["difficulty"] = sorted({DIFFICULTY_ALIASES[d] for d in filters["difficulty"]})

    cohorts = load_cohorts()
    difficulty = load_difficulty()

    rows = list(csv.DictReader(open(args.outcomes)))
    sel = []
    for r in rows:
        if filters["model"] and r["model_key"] not in filters["model"]: continue
        if filters["section"] and r["experiment_section"] not in filters["section"]: continue
        if filters["primitive"] and r["primitive"] not in filters["primitive"]: continue
        if filters["condition"] and r["condition"] not in filters["condition"]: continue
        if filters["cell"] and r["cell"] not in filters["cell"]: continue
        if filters["budget"] and r["token_budget"] not in filters["budget"]: continue
        if filters["depth"] and r["depth"] not in filters["depth"]: continue
        if filters["run"] and r["run_num"] not in filters["run"]: continue
        if filters["task"] and r["task_name"] not in filters["task"]: continue
        if filters["difficulty"] and difficulty.get(r["task_name"]) not in filters["difficulty"]: continue
        if filters["cohort"] and not all(r["task_name"] in cohorts.get(c, set()) for c in filters["cohort"]): continue
        if not args.include_resolved and (r["resolved"] == "True" or r["failure_mode"] == "resolved"): continue
        sel.append(r)

    out_rows = []
    for r in sel:
        c = classify(r, scan_logs=not args.no_log_scan)
        spt = parse_list_col(r["step_prompt_tokens"])
        out_rows.append(OrderedDict([
            ("task", r["task_name"]),
            ("run", int(r["run_num"])),
            ("model", r["model_key"]),
            ("section", r["experiment_section"]),
            ("primitive", r["primitive"]),
            ("condition", r["condition"]),
            ("cell", r["cell"]),
            ("budget", r["token_budget"]),
            ("depth", r["depth"]),
            ("difficulty", difficulty.get(r["task_name"], "")),
            ("cohorts", ";".join(n for n, s in cohorts.items() if r["task_name"] in s)),
            ("cause", c["cause"]),
            ("cause_label", CAUSE_LABEL.get(c["cause"].split(":")[0], c["cause"])),
            ("cause_detail", c["cause_detail"]),
            ("resolved", r["resolved"]),
            ("failure_mode", r["failure_mode"]),
            ("exit_status", c["exit_status"]),
            ("exit_status_source", c["exit_status_source"]),
            ("harness_returncode", r["returncode"]),
            ("ctx_error_in_log", c["ctx_error_in_log"]),
            ("model_ctx_window", MODEL_CTX_WINDOW.get(r["model_key"], "")),
            ("step_count", r["step_count"] or c["trajectory_api_calls"]),
            ("max_step_prompt_tokens", max(spt) if spt else ""),
            ("total_tokens", r["total_tokens"]),
            ("latency_e2e_s", r["latency_e2e_s"]),
            ("latency_llm_s", r["latency_llm_s"]),
            ("patch_generated", r["patch_generated"]),
            ("compression_events", r["compression_events"]),
            ("seeded_from", r["seeded_from"]),
            ("run_dir", c["run_dir"]),
        ]))

    out_rows.sort(key=lambda x: (x["model"], x["cell"], x["task"], x["run"]))
    slug = args.name or build_slug(args, filters)
    out_dir = os.path.join(args.out_root, slug)
    os.makedirs(out_dir, exist_ok=True)

    cause_key = lambda x: x["cause"].split(":")[0]
    with open(os.path.join(out_dir, "failure_causes.csv"), "w", newline="") as f:
        if out_rows:
            w = csv.DictWriter(f, fieldnames=list(out_rows[0].keys())); w.writeheader(); w.writerows(out_rows)
        else:
            f.write("")

    by_cause = Counter(x["cause"] for x in out_rows)
    tasks_by_cause = defaultdict(set)
    for x in out_rows:
        tasks_by_cause[x["cause"]].add(x["task"])
    ordered_causes = sorted(by_cause, key=lambda c: (CAUSE_ORDER.index(c.split(":")[0]) if c.split(":")[0] in CAUSE_ORDER else 99, c))
    with open(os.path.join(out_dir, "summary_by_cause.csv"), "w", newline="") as f:
        w = csv.writer(f); w.writerow(["cause", "cause_label", "n_runs", "n_tasks"])
        for c in ordered_causes:
            w.writerow([c, CAUSE_LABEL.get(c.split(":")[0], c), by_cause[c], len(tasks_by_cause[c])])

    groups = defaultdict(Counter)
    for x in out_rows:
        groups[(x["model"], x["section"], x["primitive"], x["budget"], x["depth"])][x["cause"]] += 1
    with open(os.path.join(out_dir, "summary_pivot.csv"), "w", newline="") as f:
        w = csv.writer(f); w.writerow(["model", "section", "primitive", "budget", "depth", "n_runs"] + ordered_causes)
        for g in sorted(groups):
            w.writerow(list(g) + [sum(groups[g].values())] + [groups[g].get(c, 0) for c in ordered_causes])

    diff_groups = defaultdict(Counter)
    diff_tasks = defaultdict(set)
    for x in out_rows:
        diff_groups[x["difficulty"]][x["cause"]] += 1
        diff_tasks[x["difficulty"]].add(x["task"])
    diff_order = list(DIFFICULTY_LABELS) + sorted(d for d in diff_groups if d not in DIFFICULTY_LABELS)
    with open(os.path.join(out_dir, "summary_by_difficulty.csv"), "w", newline="") as f:
        w = csv.writer(f); w.writerow(["difficulty", "n_runs", "n_tasks"] + ordered_causes)
        for d in diff_order:
            if d in diff_groups:
                w.writerow([d, sum(diff_groups[d].values()), len(diff_tasks[d])] + [diff_groups[d].get(c, 0) for c in ordered_causes])

    json.dump({
        "argv": sys.argv[1:], "filters": {k: (sorted(v) if isinstance(v, set) else v) for k, v in filters.items()},
        "include_resolved": args.include_resolved, "log_scan": not args.no_log_scan,
        "outcomes": os.path.relpath(args.outcomes, REPO), "n_runs": len(out_rows),
        "n_tasks": len({x["task"] for x in out_rows}),
        "constants": {"STEP_LIMIT": STEP_LIMIT, "AGENT_TIMEOUT_S": AGENT_TIMEOUT_S, "MODEL_CTX_WINDOW": MODEL_CTX_WINDOW},
    }, open(os.path.join(out_dir, "args.json"), "w"), indent=2, ensure_ascii=False)

    print(f"{len(out_rows)} runs / {len({x['task'] for x in out_rows})} tasks -> {os.path.relpath(out_dir, REPO)}/")
    print(f"{'cause':22s} {'n_runs':>6s} {'n_tasks':>7s}  {'label'}")
    for c in ordered_causes:
        print(f"{c:22s} {by_cause[c]:6d} {len(tasks_by_cause[c]):7d}  {CAUSE_LABEL.get(c.split(':')[0], c)}")


if __name__ == "__main__":
    main()
