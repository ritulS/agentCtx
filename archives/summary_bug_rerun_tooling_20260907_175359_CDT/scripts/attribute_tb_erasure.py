"""Step 4 of the summary-bug audit, Terminal-Bench version: which pre-fix runs may hide summary failures.

Why the SWE-bench method (attribute_agentlog.py) does not apply here
--------------------------------------------------------------------
On SWE-bench, scripts/run_experiment.py runs mini-swe-agent as a subprocess and saves its
console output as agent.log; InteractiveAgent prints every message with a step header, so
FormatErrors that a later compression erased from trajectory.json can be recovered and
attributed to summary calls step by step.

On Terminal-Bench the agent is scripts.bench_adapters.harbor_adapter:CompressionAgent, a
DefaultAgent subclass (CheckpointAgent) that prints nothing per step.  The run directory's
agent.log is a copy of Harbor's trial.log (environment/docker messages).  worker.log, added
with the 2026-09-06 zombie fix, only holds the mini-swe-agent banner and tracebacks.  There is
no per-run console record of model calls, and model_stats.api_calls in trajectory.json is the
agent's own n_calls (default.py), not an independent model-call counter.  Erased FormatErrors
are therefore unrecoverable on Terminal-Bench.

What can be established from trajectory.json + token_log.json alone
--------------------------------------------------------------------
A failed summary call (pre-fix) appended a ``Format error`` user message that stays in the
history until something rewrites the compressible window:

* summarization / structured_summarize: a successful summary replaces messages[2:];
* *_partial (incl. online_trc_*_partial): a successful event replaces the head, or falls back to
  truncate() when the tail alone exceeds the budget (no LLM call, summarization_prompt_tokens
  unchanged) -- either way messages are dropped;
* trc_summarize / trc_structured_summarize: stage 1 (TRC) only stubs message *content* and
  keeps ``extra`` (interrupt_type, model_response), so the error stays countable; only the
  stage-2 summary (summarization_prompt_tokens > 0) rewrites the window.
* online TRC likewise stubs content only and keeps ``extra``.

Hence for a summary-condition run:

  erasure_possible = summarization_prompt_tokens > 0
                     or (compression_events > 0 and primitive not TRC-stacked)

* erasure_possible and no established summary failure -> the run *may* have had summary
  failures that left no trace: rerun candidate ``probable`` / ``tb_erasure_possible``
  (analogue of the SWE-bench ``agentlog_unverifiable`` rows; on SWE-bench 48% of the
  error-free summary-condition runs turned out to be confirmed failures).
* not erasure_possible and no retained FormatError -> nothing could have removed a failed
  summary's error message, so no summary call failed (a call killed in flight leaves no
  message either way): ``no_evidence_intact``, not added.
* not erasure_possible and retained errors with prior classification not_established -> all
  errors are still present and call accounting could not attribute them to summary calls:
  ``errors_intact_not_established``, not added (same as before).

The two intact verdicts rely on token_log.json describing the same state as trajectory.json.
Before the 2026-09-06 zombie fix, a Harbor timeout wrote exit_info.json / token_log.json while the
agent thread kept running and saving trajectory.json, so a compression in that tail is missing
from token_log.  Such runs (trajectory.json mtime > token_log.json mtime + 5 s, or
api_calls > len(step_prompt_tokens) + 1) are ``token_log_stale`` -> ``probable`` /
``tb_unverifiable`` instead of intact.

Nothing on Terminal-Bench can be *confirmed*, so no addition gets ``priority``.

Inputs
------
--workspace      runtime tree owning ICLR_results/ and logs/ (default: /home/ak58925/agentCtx)
--archive-root   (repeatable) archive directories holding moved runs under the same
                 workspace-relative paths (default: workspace/archives/*_summary_marker_error_*)
--audit-dir      (repeatable) export_query_errors.py output; later ones override earlier ones per
                 trajectory (the GLM rescan)
--review-dir     (repeatable) review_unmarked_summary_errors.py output (review_unmarked.csv or
                 review_870.csv); later ones override earlier ones
--rerun-list     the rerun_runs.csv to extend
--fix-time       runs whose Harbor started_at is before this are pre-fix (default 2026-09-07T17:23:33-05:00,
                 commit 6b45448 in the runtime tree)
--output-dir     fresh directory for the outputs (never writes into the inputs)
--all-conditions also scan non-summary conditions: summary markers there are method anomalies

Outputs
-------
tb_attribution.csv            one row per scanned pre-fix run
rerun_runs_tb_additions.csv   rows in rerun_runs.csv schema for summary-condition runs NOT yet listed
rerun_runs_with_tb.csv        rerun_runs.csv rows + additions, with tb_* columns appended
tb_condition_summary.csv      per-condition verdict counts
method_anomalies.csv          (--all-conditions) non-summary runs with summary-marker errors
tb_README.txt                 counts and method notes

Read-only on experiment files. Standard library only.
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
import multiprocessing as mp
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_WORKSPACE = Path("/home/ak58925/agentCtx")
DEFAULT_FIX_TIME = "2026-09-07T17:23:33-05:00"
BENCH_DIR = "terminalbench"
SUMMARY_MARKERS = ("[CONTEXT SUMMARY]", "[COMPRESSED HISTORY SUMMARY]")
TRC_STACKED = {"trc_summarize", "trc_structured_summarize"}
STEP_HEADER = "mini-swe-agent (step "
STALE_MTIME_S = 5.0   # trajectory.json saved this much after token_log.json -> token_log is stale
STALE_STEP_GAP = 1    # api_calls may lead step_prompt_tokens by one in-flight call, not more

RERUN_FIELDS = [
    "benchmark", "section", "cohort_model_path", "cell", "model", "primitive",
    "budget_tokens", "depth", "task", "condition", "run", "rerun_priority",
    "rerun_reason", "summary_marker_errors", "summary_failure_lower_bound",
    "trajectory", "error_response_details",
]
TB_FIELDS = ["tb_verdict", "tb_location", "tb_retained_format_errors", "tb_compression_events",
             "tb_summarization_prompt_tokens", "tb_erasure_possible"]
METRIC_FIELDS = [
    "exit_status", "api_calls", "token_log_steps", "compression_events", "summarization_prompt_tokens",
    "online_trc_clears", "retained_format_errors", "marker_errors", "audit_error_events",
    "traj_after_exit_s", "traj_after_token_log_s", "token_log_stale", "worker_log", "worker_log_step_headers", "started_at",
]
ATTRIB_FIELDS = (
    ["benchmark", "section", "cohort_model_path", "cell", "model", "primitive", "budget_tokens", "depth",
     "task", "condition", "run", "summary_condition", "trajectory", "resolved_dir", "location"]
    + METRIC_FIELDS + ["erasure_possible", "verdict", "prior_rerun_reason", "prior_classification"]
)
VERDICT_ORDER = ["already_listed", "erasure_possible", "token_log_stale", "errors_intact_not_established",
                 "no_evidence_intact", "source_changed", "unreadable"]
ADDITION_RULE = {  # verdict -> (rerun_priority, rerun_reason); summary conditions only, never 'priority'
    "erasure_possible": ("probable", "tb_erasure_possible"),
    "token_log_stale": ("probable", "tb_unverifiable"),
    "source_changed": ("probable", "tb_unverifiable"),
    "unreadable": ("probable", "tb_unverifiable"),
}


def read_csv(path: Path) -> list[dict]:
    with path.open(newline="") as stream:
        return list(csv.DictReader(stream))


def write_csv(path: Path, fields: list[str], rows: list[dict]) -> None:
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def is_summary_primitive(primitive: str) -> bool:
    return "summar" in primitive


def parse_time(value: str) -> datetime:
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


# ── per-run worker ─────────────────────────────────────────────────────────────

_CTX: dict = {}


def _init_worker(ctx: dict) -> None:
    _CTX.update(ctx)


def load_json(path: Path):
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


def process_run(item: tuple[str, str, str]) -> dict:
    """item = (root_parent, rel_traj, location); rel_traj is workspace-relative (starts with ICLR_results/)."""
    root_parent, rel_traj, location = item
    run_dir = Path(root_parent) / Path(rel_traj).parent
    rel_parts = Path(rel_traj).parts  # ICLR_results/terminalbench/<section>/<cohort>/<cell>/<task>/<condition>/run_n/trajectory.json
    section, cohort, cell, task, condition, run = rel_parts[2:8]
    cond = _CTX["conditions"].get((section, cohort, cell), {})
    exit_info = load_json(run_dir / "exit_info.json") or {}
    harbor = load_json(run_dir / "harbor_result.json") or {}
    primitive = cond.get("primitive") or exit_info.get("primitive", "")
    row = {
        "benchmark": cond.get("benchmark", BENCH_DIR), "section": section, "cohort_model_path": cohort,
        "cell": cell, "model": cond.get("model") or (harbor.get("config", {}).get("agent", {}) or {}).get("model_name", ""),
        "primitive": primitive, "budget_tokens": cond.get("budget_tokens") or exit_info.get("token_budget", ""),
        "depth": cond.get("depth") or exit_info.get("compression_ratio", ""),
        "task": task, "condition": condition, "run": run,
        "summary_condition": is_summary_primitive(primitive),
        "trajectory": str(Path(_CTX["workspace"]) / rel_traj), "resolved_dir": str(run_dir), "location": location,
        "started_at": harbor.get("started_at", ""),
    }
    row.update({k: None for k in METRIC_FIELDS if k not in row})
    traj = load_json(run_dir / "trajectory.json")
    tok = load_json(run_dir / "token_log.json")
    if traj is None or tok is None:
        row["verdict_hint"] = "unreadable"
        return row
    info = traj.get("info", {})
    row["exit_status"] = info.get("exit_status") or ""
    row["api_calls"] = info.get("model_stats", {}).get("api_calls")
    row["token_log_steps"] = len(tok.get("step_prompt_tokens", []))
    row["compression_events"] = tok.get("compression_events", 0) or 0
    row["summarization_prompt_tokens"] = tok.get("summarization_prompt_tokens", 0) or 0
    row["online_trc_clears"] = len(tok.get("online_trc_flags", []) or [])
    errors = [m for m in traj.get("messages", []) if (m.get("extra") or {}).get("interrupt_type") == "FormatError"]
    row["retained_format_errors"] = len(errors)
    row["marker_errors"] = sum(
        any(mk in str((m.get("extra") or {}).get("model_response", "")) for mk in SUMMARY_MARKERS) for m in errors
    )
    traj_mtime = (run_dir / "trajectory.json").stat().st_mtime
    try:
        row["traj_after_exit_s"] = round(traj_mtime - (run_dir / "exit_info.json").stat().st_mtime, 1)
    except OSError:
        pass
    row["traj_after_token_log_s"] = round(traj_mtime - (run_dir / "token_log.json").stat().st_mtime, 1)
    row["token_log_stale"] = bool(
        row["traj_after_token_log_s"] > STALE_MTIME_S
        or (row["api_calls"] is not None and row["api_calls"] - row["token_log_steps"] > STALE_STEP_GAP)
    )
    # console-log check: the Harbor trial's worker.log (post 2026-09-06 only) must not contain step headers
    trials_dir = (harbor.get("config") or {}).get("trials_dir")
    trial_name = harbor.get("trial_name")
    row["worker_log"] = False
    row["worker_log_step_headers"] = 0
    if trials_dir and trial_name:
        try:
            rel_trial = Path(trials_dir).relative_to(_CTX["workspace"]) / trial_name
            worker_log = Path(root_parent) / rel_trial / "agent" / "worker.log"
            if worker_log.exists():
                row["worker_log"] = True
                with worker_log.open(errors="replace") as stream:
                    row["worker_log_step_headers"] = sum(STEP_HEADER in line for line in stream)
        except ValueError:
            pass
    row["erasure_possible"] = bool(
        row["summarization_prompt_tokens"] > 0
        or (row["compression_events"] > 0 and primitive not in TRC_STACKED)
    )
    return row


def verdict_for(row: dict) -> str:
    if row.get("verdict_hint") == "unreadable":
        return "unreadable"
    if row["prior_rerun_reason"]:
        return "already_listed"
    if row["audit_error_events"] is not None and row["audit_error_events"] != row["retained_format_errors"]:
        return "source_changed"        # the file no longer matches the audited one
    if row["erasure_possible"]:
        return "erasure_possible"
    if row["token_log_stale"]:
        return "token_log_stale"       # token_log predates the final trajectory: intact verdicts are not supported
    if row["retained_format_errors"] > 0:
        return "errors_intact_not_established"
    return "no_evidence_intact"


# ── main ───────────────────────────────────────────────────────────────────────

def discover_runs(workspace: Path, archive_roots: list[Path], fix_time: datetime) -> tuple[list, Counter]:
    """All Terminal-Bench run dirs (workspace + archives) started before fix_time; canonical paths must be unique."""
    counts = Counter()
    items: dict[str, tuple[str, str, str]] = {}
    sources = [(workspace, "workspace")] + [(a, "archive:" + a.name) for a in archive_roots]
    for parent, location in sources:
        pattern = str(parent / "ICLR_results" / BENCH_DIR / "*" / "*" / "*" / "*" / "*" / "run_*" / "trajectory.json")
        for traj in glob.glob(pattern):
            rel = str(Path(traj).relative_to(parent))
            harbor = load_json(Path(traj).with_name("harbor_result.json"))
            started = harbor.get("started_at") if harbor else None
            if started:
                pre_fix = parse_time(started) < fix_time
            else:
                pre_fix = datetime.fromtimestamp(os.path.getmtime(traj), tz=timezone.utc) < fix_time
                counts["no_harbor_result_mtime_fallback"] += 1
            if not pre_fix:
                counts["post_fix_skipped"] += 1
                continue
            if rel in items:
                raise SystemExit(f"run present twice (workspace and archive?): {rel}\n  {items[rel][0]}\n  {parent}")
            items[rel] = (str(parent), rel, location)
            counts[location] += 1
    return list(items.values()), counts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--workspace", type=Path, default=DEFAULT_WORKSPACE)
    parser.add_argument("--archive-root", type=Path, action="append", default=None,
                        help="archive directory (containing ICLR_results/ and logs/); repeatable")
    parser.add_argument("--audit-dir", type=Path, action="append", required=True)
    parser.add_argument("--review-dir", type=Path, action="append", default=[])
    parser.add_argument("--rerun-list", type=Path, required=True)
    parser.add_argument("--fix-time", default=DEFAULT_FIX_TIME)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=min(16, os.cpu_count() or 1))
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--all-conditions", action="store_true")
    args = parser.parse_args()

    workspace = args.workspace.resolve()
    archives = ([a.resolve() for a in args.archive_root] if args.archive_root
                else sorted(Path(p).resolve() for p in glob.glob(str(workspace / "archives" / "*_summary_marker_error_*"))))
    output = args.output_dir.resolve()
    if output.exists() and any(output.iterdir()):
        parser.error(f"output dir must be new or empty: {output}")
    output.mkdir(parents=True, exist_ok=True)
    fix_time = parse_time(args.fix_time)

    conditions: dict[tuple, dict] = {}
    audit_rows: dict[str, dict] = {}
    for audit in args.audit_dir:
        for c in read_csv(audit / "condition_summary.csv"):
            conditions[(c["section"], c["cohort_model_path"], c["cell"])] = c
        for r in read_csv(audit / "runs_with_errors.csv"):
            audit_rows[r["trajectory"]] = {**r, "audit_dir": str(audit.resolve())}
    review_rows: dict[str, dict] = {}
    for review in args.review_dir:
        review_csv = next(p for p in (review / "review_unmarked.csv", review / "review_870.csv") if p.exists())
        for r in read_csv(review_csv):
            review_rows[r["trajectory"]] = r
    rerun_rows = read_csv(args.rerun_list)
    prior_reason = {r["trajectory"]: r["rerun_reason"] for r in rerun_rows}

    items, discovery = discover_runs(workspace, archives, fix_time)
    ctx = {"workspace": str(workspace), "conditions": conditions}
    scan = []
    for parent, rel, location in items:
        section, cohort, cell = Path(rel).parts[2:5]
        cond = conditions.get((section, cohort, cell))
        primitive = cond["primitive"] if cond else (load_json(Path(parent) / Path(rel).parent / "exit_info.json") or {}).get("primitive", "")
        if not is_summary_primitive(primitive) and not args.all_conditions:
            continue
        scan.append((parent, rel, location))
    if args.limit:
        scan = scan[: args.limit]
    print(f"pre-fix runs found: {sum(v for k, v in discovery.items() if k in ('workspace',) or k.startswith('archive:'))}; "
          f"scanning {len(scan)} with {args.workers} workers", file=sys.stderr)
    with mp.Pool(args.workers, initializer=_init_worker, initargs=(ctx,)) as pool:
        rows = list(pool.imap_unordered(process_run, scan, chunksize=8))
    rows.sort(key=lambda r: r["trajectory"])

    for row in rows:
        audit = audit_rows.get(row["trajectory"])
        row["audit_error_events"] = int(audit["query_error_events"]) if audit else None
        row["prior_rerun_reason"] = prior_reason.get(row["trajectory"], "")
        row["prior_classification"] = (review_rows.get(row["trajectory"]) or {}).get("classification", "")
        row["verdict"] = verdict_for(row) if row["summary_condition"] else ("unreadable" if row.get("verdict_hint") else "")
    write_csv(output / "tb_attribution.csv", ATTRIB_FIELDS, rows)

    summary_rows = [r for r in rows if r["summary_condition"]]
    other_rows = [r for r in rows if not r["summary_condition"]]

    additions = []
    for row in summary_rows:
        if row["verdict"] not in ADDITION_RULE:
            continue
        priority, reason = ADDITION_RULE[row["verdict"]]
        audit = audit_rows.get(row["trajectory"])
        additions.append({**{k: row[k] for k in RERUN_FIELDS if k in row},
                          "rerun_priority": priority, "rerun_reason": reason,
                          "summary_marker_errors": row["marker_errors"] or 0,
                          "summary_failure_lower_bound": "",   # nothing can be confirmed without a console log
                          "error_response_details": str(Path(audit["audit_dir"]) / audit["details_file"]) if audit else ""})
    write_csv(output / "rerun_runs_tb_additions.csv", RERUN_FIELDS, additions)

    by_traj = {r["trajectory"]: r for r in rows}

    def tb_cols(traj: str) -> dict:
        r = by_traj.get(traj)
        if r is None:
            return {k: "" for k in TB_FIELDS} | {"tb_verdict": "not_scanned"}
        return {"tb_verdict": r["verdict"], "tb_location": r["location"],
                "tb_retained_format_errors": r["retained_format_errors"], "tb_compression_events": r["compression_events"],
                "tb_summarization_prompt_tokens": r["summarization_prompt_tokens"], "tb_erasure_possible": r["erasure_possible"]}
    combined = [{**r, **tb_cols(r["trajectory"])} for r in rerun_rows]
    combined += [{**a, **tb_cols(a["trajectory"])} for a in additions]
    write_csv(output / "rerun_runs_with_tb.csv", RERUN_FIELDS + TB_FIELDS, combined)

    cond_key = ("benchmark", "section", "cohort_model_path", "cell", "model", "primitive", "budget_tokens", "depth")
    per_cond: dict[tuple, Counter] = defaultdict(Counter)
    for row in summary_rows:
        c = per_cond[tuple(row[k] for k in cond_key)]
        c["runs_scanned"] += 1
        c[row["verdict"]] += 1
    add_by_cond = Counter(tuple(a[k] for k in cond_key) for a in additions)
    cond_rows = [dict(zip(cond_key, key)) | {v: c[v] for v in VERDICT_ORDER}
                 | {"runs_scanned": c["runs_scanned"], "tb_additions": add_by_cond[key],
                    "listed_after_update": c["already_listed"] + add_by_cond[key]}
                 for key, c in sorted(per_cond.items())]
    write_csv(output / "tb_condition_summary.csv",
              list(cond_key) + ["runs_scanned", "tb_additions", "listed_after_update"] + VERDICT_ORDER, cond_rows)

    anomalies = [r for r in other_rows if (r["marker_errors"] or 0) > 0]
    if args.all_conditions:
        write_csv(output / "method_anomalies.csv", ATTRIB_FIELDS, anomalies)

    verdicts = Counter(r["verdict"] for r in summary_rows)
    by_prior = defaultdict(Counter)
    for r in summary_rows:
        by_prior[r["prior_rerun_reason"] or r["prior_classification"] or "(no trajectory error)"][r["verdict"]] += 1
    listed_missing = [t for t in prior_reason if t not in by_traj]
    step_headers = sum(r["worker_log_step_headers"] or 0 for r in rows)
    worker_logs = sum(bool(r["worker_log"]) for r in rows)
    zombie = sum(1 for r in rows if (r["traj_after_exit_s"] or 0) > 60)
    stale = sum(1 for r in summary_rows if r["token_log_stale"])
    lines = [
        "Terminal-Bench: trajectory/token_log attribution of possible erased summary failures",
        f"generated: {datetime.now().isoformat(timespec='seconds')}",
        f"workspace: {workspace}", f"archive roots: {[str(a) for a in archives]}",
        f"audit dirs: {[str(a) for a in args.audit_dir]}", f"review dirs: {[str(r) for r in args.review_dir]}",
        f"rerun list: {args.rerun_list.resolve()} ({len(rerun_rows)} rows)",
        f"fix time: {fix_time.isoformat()} (runs with Harbor started_at before this are pre-fix)",
        "", f"discovery: {dict(discovery)}",
        f"summary-condition pre-fix runs scanned: {len(summary_rows)}",
        "verdicts: " + ", ".join(f"{v}={verdicts[v]}" for v in VERDICT_ORDER),
        f"additions to rerun_runs.csv: {len(additions)} "
        f"(priority={sum(a['rerun_priority'] == 'priority' for a in additions)}, "
        f"probable={sum(a['rerun_priority'] == 'probable' for a in additions)})",
        f"listed runs not found on disk: {len(listed_missing)}",
        f"console-log check: worker.log present for {worker_logs} runs, step headers found in them: {step_headers} (must be 0: "
        "DefaultAgent prints no per-step output, so the SWE-bench agent.log method has nothing to read)",
        f"runs whose trajectory.json was still written >60s after exit_info.json (pre-2026-09-06 zombie agents): {zombie}",
        f"summary-condition runs with a stale token_log (trajectory saved >{STALE_MTIME_S:g}s after token_log.json, or "
        f"api_calls > step_prompt_tokens + {STALE_STEP_GAP}): {stale}; those not already listed or erasure_possible are token_log_stale",
    ]
    if args.all_conditions:
        lines.append(f"non-summary runs scanned (self-check): {len(other_rows)}; with summary-marker errors (method anomalies): "
                     f"{len(anomalies)} (must be 0)")
    lines += ["", "verdict by prior audit classification (summary conditions):"]
    for prior, c in sorted(by_prior.items()):
        lines.append(f"  {prior}: " + ", ".join(f"{v}={c[v]}" for v in VERDICT_ORDER if c[v]))
    lines += [
        "",
        "method: Terminal-Bench has no per-step console log (the agent is a DefaultAgent subclass run by the Harbor",
        "adapter; agent.log in the run dir is Harbor's trial.log), so FormatErrors erased from trajectory.json by a later",
        "compression cannot be recovered or attributed. A failed pre-fix summary call left a 'Format error' user message",
        "that only a successful rewrite of the compressible window removes: a successful summary (summarization_prompt_tokens",
        "> 0), or, for the *_partial variants, any compression event (head summarized, or truncate() fallback without an LLM",
        "call). TRC and online TRC stub message content but keep 'extra' (interrupt_type, model_response), so they never",
        "remove the evidence; for trc_summarize / trc_structured_summarize only the stage-2 summary counts.",
        "erasure_possible = summarization_prompt_tokens > 0 or (compression_events > 0 and primitive not TRC-stacked).",
        "verdicts: already_listed; erasure_possible (no established failure, but evidence may have been erased ->",
        "probable/tb_erasure_possible); token_log_stale (token_log.json predates the final trajectory.json: before the",
        "2026-09-06 zombie fix a Harbor timeout wrote token_log while the agent thread kept running, so a later compression",
        "is not recorded -> probable/tb_unverifiable); errors_intact_not_established (all errors retained, call accounting",
        "could not attribute them; unchanged, not added); no_evidence_intact (no retained error and nothing could have",
        "erased one: no summary call failed, not added); source_changed (retained error count differs from the audited",
        "one -> probable/tb_unverifiable); unreadable (-> probable/tb_unverifiable).",
        "No Terminal-Bench addition is 'priority': nothing can be confirmed without a console log.",
        "summary_marker_errors in the additions is the current retained count (0 for error-free runs);",
        "summary_failure_lower_bound is left empty.",
        "Runs already listed in rerun_runs.csv are annotated in rerun_runs_with_tb.csv, never duplicated.",
        "Post-fix runs (reruns started after the fix) are skipped by Harbor started_at. Experiment files were read only.",
    ]
    (output / "tb_README.txt").write_text("\n".join(lines) + "\n")
    print("\n".join(lines[8:16]))


if __name__ == "__main__":
    main()
