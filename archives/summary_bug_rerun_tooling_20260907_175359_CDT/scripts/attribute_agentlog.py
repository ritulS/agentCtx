"""Step 4 of the summary-bug audit: attribute FormatErrors to summary calls using agent.log.

Why agent.log
-------------
trajectory.json is rewritten every step with the *post-compression* message list, so
FormatErrors that happened before a later successful compression are gone from it.
agent.log is the subprocess stdout: InteractiveAgent.add_messages prints every message
as it is added, so it keeps all FormatErrors in order, and every accepted assistant
message is preceded by a header ``mini-swe-agent (step N, $C):`` where N is n_calls.

Attribution rule
----------------
In mini-swe-agent 2.2.6 (bug era) DefaultAgent.query runs compression first, then
``n_calls += 1``, then ``model.query``.  Therefore

* a normal-agent FormatError consumes one step number (no header printed for it);
* a summary FormatError (raised inside summarize() before ``n_calls += 1``) consumes none.

Between two consecutive headers N_prev and N with E "Format error" messages:
    agent_failures   += min(E, N - N_prev - 1)
    summary_failures += max(0, E - (N - N_prev - 1))

What counts as confirmed
------------------------
Console text is not delimited, and models do echo transcripts (rule line, ``User:``,
``Format error:`` ...) in their replies, so structure alone cannot prove that a counted
error is real.  An interval's summary failures are therefore *confirmed* only when the
token log records a compression event at N_prev: after failed summary calls the history is
still over budget, so the next query compresses again, and the compression that finally
succeeds appends ``n_calls`` (= N_prev) to ``compression_event_steps``.  Summary evidence
without that record (``uncorroborated``) is reported but not confirmed.  Known legitimate
source of uncorroborated evidence: the OTRC family clears a tool result online before the
budget check, which can end the over-budget state without any compression event.
Errors after the last header (the tail) are never followed by a recorded event and are not
confirmed either; when the run was killed (no exit status) the saved ``api_calls`` may even
lag the log by one consumed step, so tail evidence is ``tail_unresolved``.

Inputs
------
--audit-dir   directory written by export_query_errors.py / review_unmarked_summary_errors.py /
              build_rerun_runs.py (needs audit-swebench/, rerun-list/, source_file_stats.json;
              review-swebench/ is optional)
--source-root experiment root the audit scanned (default: ICLR_results)
--archive-root (repeatable) roots where audited runs were moved to afterwards, e.g.
              archives/swebench_summary_marker_error_20260907_192635_CDT
              The copy whose trajectory.json AND token_log.json size/mtime equal the audited
              values in source_file_stats.json is used; anything else is ``source_changed``.
--output-dir  fresh directory for the outputs (never writes into the inputs)
--all-conditions also scan non-summary conditions as a self-check of the method: any summary
              evidence there is a method anomaly and is reported, never added to the rerun list.

Outputs
-------
agentlog_attribution.csv          one row per scanned run (all of them, not only runs with errors)
rerun_runs_agentlog_additions.csv rows in rerun_runs.csv schema for summary-condition runs NOT yet in
                                  rerun_runs.csv (append these to rerun_runs.csv);
                                  summary_failure_lower_bound is filled only for summary_confirmed rows
rerun_runs_with_agentlog.csv      rerun_runs.csv rows + additions, with agentlog_* columns appended
                                  (raw computed counts and confirmed counts are separate columns)
agentlog_condition_summary.csv    per-condition verdict counts
method_anomalies.csv              (--all-conditions) non-summary runs with any summary evidence
nonsummary_integrity.csv          (--all-conditions) non-summary runs whose log/trajectory fail the
                                  structure checks (launched twice, inconsistent, changed)
agentlog_README.txt               counts and method notes

Read-only on experiment files. Standard library only.
"""
from __future__ import annotations

import argparse
import csv
import json
import multiprocessing as mp
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

HEADER_RE = re.compile(r"^mini-swe-agent \(step (\d+), \$")
RULE_RE = re.compile(r"^─{8,}")  # rich Rule() printed by InteractiveAgent.step() before every query
BANNER = "This is mini-swe-agent version"
FORMAT_ERROR_LINE = "Format error:"
ERROR_OPEN_LINE = "<error>"
USER_LINE = "User:"
# last line of every message that can precede a real Rule: observation, format-error message,
# instance message.  Measured on 600 logs: 44,965 of 44,967 rules follow one of these.
RULE_PREDECESSORS = ("</output>", "</output_tail>", "after that).", "</instructions>")
LOG_TIME_WINDOW_S = 1800  # agent.log mtime must lie within this window of trajectory.json mtime

RERUN_FIELDS = [
    "benchmark", "section", "cohort_model_path", "cell", "model", "primitive",
    "budget_tokens", "depth", "task", "condition", "run", "rerun_priority",
    "rerun_reason", "summary_marker_errors", "summary_failure_lower_bound",
    "trajectory", "error_response_details",
]
AGENTLOG_FIELDS = [
    "agentlog_verdict", "agentlog_source", "agentlog_log_errors", "agentlog_agent_failures",
    "agentlog_summary_failures_raw", "agentlog_summary_failures_confirmed",
    "agentlog_summary_failures_uncorroborated", "agentlog_tail_unresolved", "agentlog_consistent",
]
METRIC_FIELDS = [
    "banners", "headers", "max_step", "api_calls", "token_log_steps", "compression_events",
    "log_errors", "traj_errors", "agent_failures", "summary_failures_raw", "summary_failures_confirmed",
    "summary_failures_uncorroborated", "tail_errors", "tail_unresolved", "unexplained_steps",
    "fake_headers", "fake_errors", "interleaved_headers", "decode_errors", "log_time_delta_s",
]
FLAG_FIELDS = ["consistent", "monotonic", "single_process", "structure_ok", "log_time_ok"]
ATTRIB_FIELDS = (
    ["benchmark", "section", "cohort_model_path", "cell", "model", "primitive", "budget_tokens", "depth",
     "task", "condition", "run", "summary_condition", "trajectory", "resolved_dir", "source_status", "exit_status"]
    + METRIC_FIELDS + FLAG_FIELDS + ["verdict", "prior_rerun_reason", "prior_classification"]
)
VERDICT_ORDER = ["summary_confirmed", "uncorroborated", "tail_unresolved", "inconsistent", "multi_run_log",
                 "source_changed", "log_missing", "no_summary_evidence"]
ADDITION_RULE = {  # verdict -> (rerun_priority, rerun_reason); summary conditions only
    "summary_confirmed": ("priority", "agentlog_summary_failure"),
    "uncorroborated": ("probable", "agentlog_uncorroborated"),
    "tail_unresolved": ("probable", "agentlog_tail_unresolved"),
    "inconsistent": ("probable", "agentlog_unverifiable"),
    "multi_run_log": ("probable", "agentlog_unverifiable"),
    "source_changed": ("probable", "agentlog_unverifiable"),
    "log_missing": ("probable", "agentlog_unverifiable"),
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


# ── agent.log parsing ──────────────────────────────────────────────────────────

def parse_agent_log(path: Path) -> dict:
    """Return banners, accepted header steps in order, Format errors per interval, and structure counters.

    errors[i] = Format errors printed after header i (errors[0] = before the first header).

    A header or a ``User:`` / ``Format error:`` / ``<error>`` sequence is accepted only directly
    after a Rule line that itself follows the last line of a message (RULE_PREDECESSORS); anything
    else is counted in ``fake_headers`` / ``fake_errors`` and ignored.  This rejects most echoed
    transcripts but cannot reject a fully quoted block; confirmation therefore also needs the
    compression-event corroboration applied in attribute().

    Two processes writing the same file leave interleaved output: backwards step numbers
    (``monotonic`` False), headers glued to the previous line (``interleaved_headers``) and cut
    multi-byte characters (``decode_errors``).
    """
    banners = 0
    steps: list[int] = []
    errors: list[int] = [0]
    fake_headers = fake_errors = interleaved_headers = decode_errors = 0
    after_rule = False          # last non-blank line was a Rule that follows a message end
    prev_nonblank = ""
    expect = None               # None | "format_error" | "error_open"
    monotonic = True
    prev_raw_blank = True
    with path.open(errors="replace") as stream:
        for raw in stream:
            line = raw.rstrip("\n")
            decode_errors += line.count("�")
            if HEADER_RE.match(line) and not prev_raw_blank:
                interleaved_headers += 1
            prev_raw_blank = not line.strip()
            if prev_raw_blank:
                continue
            if expect == "format_error":
                expect = "error_open" if line == FORMAT_ERROR_LINE else None
            elif expect == "error_open":
                if line == ERROR_OPEN_LINE:
                    errors[-1] += 1
                expect = None
            if BANNER in line:
                banners += 1
            m = HEADER_RE.match(line)
            if m:
                if after_rule:
                    step = int(m.group(1))
                    if steps and step <= steps[-1]:
                        monotonic = False
                    steps.append(step)
                    errors.append(0)
                else:
                    fake_headers += 1
            elif line == USER_LINE and after_rule:
                expect = "format_error"
            elif line == FORMAT_ERROR_LINE and expect is None:
                fake_errors += 1
            after_rule = RULE_RE.match(line) is not None and prev_nonblank.endswith(RULE_PREDECESSORS)
            prev_nonblank = line
    return {"banners": banners, "steps": steps, "errors": errors, "monotonic": monotonic,
            "fake_headers": fake_headers, "fake_errors": fake_errors,
            "interleaved_headers": interleaved_headers, "decode_errors": decode_errors}


def attribute(parsed: dict, api_calls: int | None, token_log_steps: int | None,
              event_steps: set[int], exit_status: str) -> dict:
    """Split Format errors into normal-agent failures, confirmed / uncorroborated summary failures, and tail."""
    steps, errors = parsed["steps"], parsed["errors"]
    headers = len(steps)
    max_step = max(steps) if steps else 0
    log_errors = sum(errors)
    tail = errors[-1] if steps else errors[0]
    exit_confirmed = bool(exit_status)

    agent_mid = confirmed = uncorroborated = unexplained = 0
    prev = 0
    for i, step in enumerate(steps):
        e, gap = errors[i], max(0, step - prev - 1)
        a = min(e, gap)
        agent_mid += a
        if prev in event_steps:       # a compression finally succeeded at this call -> real summary retries
            confirmed += e - a
        else:
            uncorroborated += e - a
        unexplained += max(0, gap - e)
        prev = step

    consistent = (
        api_calls is not None and token_log_steps is not None
        and 0 <= headers - token_log_steps <= 1
        and max_step <= api_calls <= max_step + tail + 1
    )
    tail_unresolved = 0
    agent_failures = agent_mid
    if consistent and exit_confirmed:
        consumed = api_calls - max_step
        a = min(tail, consumed)
        agent_failures += a
        uncorroborated += tail - a     # never followed by a recorded compression: not confirmable
        unexplained += max(0, consumed - tail)
    elif consistent:                   # killed: the saved api_calls may lag the log by one step
        consumed = api_calls - max_step
        a = min(tail, consumed)
        agent_failures += a
        tail_unresolved = tail - a
    else:                              # log and trajectory disagree: nothing from the tail is usable
        tail_unresolved = tail

    return {
        "headers": headers, "max_step": max_step, "log_errors": log_errors,
        "agent_failures": agent_failures,
        "summary_failures_raw": confirmed + uncorroborated + tail_unresolved,
        "summary_failures_confirmed": confirmed, "summary_failures_uncorroborated": uncorroborated,
        "tail_errors": tail, "tail_unresolved": tail_unresolved, "unexplained_steps": unexplained,
        "fake_headers": parsed["fake_headers"], "fake_errors": parsed["fake_errors"],
        "interleaved_headers": parsed["interleaved_headers"], "decode_errors": parsed["decode_errors"],
        "consistent": consistent, "monotonic": parsed["monotonic"],
        "single_process": parsed["banners"] == 1 and parsed["monotonic"] and parsed["interleaved_headers"] == 0,
        "structure_ok": parsed["decode_errors"] == 0 and unexplained == 0
        and not (exit_status == "Submitted" and tail > 0),
    }


def verdict_for(row: dict) -> str:
    """Structural doubts first: no confirmation is issued from a log that fails them."""
    if row["source_status"] == "missing" or row["banners"] is None:
        return "log_missing"
    if row["source_status"] != "exact" or not row["log_time_ok"]:
        return "source_changed"      # not (provably) the audited execution
    if not row["single_process"]:
        return "multi_run_log"       # interleaved output of two processes in one directory
    if not row["structure_ok"] or not row["consistent"]:
        return "inconsistent"        # log and trajectory disagree, or the log's step accounting is off
    if row["summary_failures_confirmed"] > 0:
        return "summary_confirmed"
    if row["summary_failures_uncorroborated"] > 0:
        return "uncorroborated"
    if row["tail_unresolved"] > 0:
        return "tail_unresolved"
    return "no_summary_evidence"


# ── per-run worker ─────────────────────────────────────────────────────────────

_CTX: dict = {}


def _init_worker(ctx: dict) -> None:
    _CTX.update(ctx)


def _matches(path: Path, audited: list | None) -> str:
    if not path.exists():
        return "absent"
    if not audited:
        return "unaudited"
    st = path.stat()
    if st.st_size == audited[0] and st.st_mtime_ns == audited[1]:
        return "exact"
    return "changed"


def resolve_run_dir(rel_dir: str) -> tuple[Path | None, str]:
    """Pick the copy of the run whose trajectory.json and token_log.json both equal the audited files."""
    stats = _CTX["stats"]
    candidates = [Path(_CTX["workspace"]) / rel_dir] + [Path(a) / rel_dir for a in _CTX["archives"]]
    existing = [c for c in candidates if (c / "trajectory.json").exists()]
    if not existing:
        return None, "missing"
    for c in existing:
        traj = _matches(c / "trajectory.json", stats.get(f"{rel_dir}/trajectory.json"))
        tok = _matches(c / "token_log.json", stats.get(f"{rel_dir}/token_log.json"))
        if traj == "exact" and tok == "exact":
            return c, "exact"
    return existing[0], "changed"


def process_run(item: tuple[str, dict]) -> dict:
    rel_traj, meta = item
    rel_dir = str(Path(rel_traj).parent)
    row = dict(meta)
    row["trajectory"] = str(Path(_CTX["workspace"]) / rel_traj)
    run_dir, status = resolve_run_dir(rel_dir)
    row["resolved_dir"] = str(run_dir) if run_dir else ""
    row["source_status"] = status
    row.update({k: None for k in METRIC_FIELDS})
    row.update({k: False for k in FLAG_FIELDS})
    row["exit_status"] = ""
    if run_dir is None or not (run_dir / "agent.log").exists():
        row["source_status"] = "missing" if run_dir is None else status + "_no_agent_log"
        row["verdict"] = "log_missing"
        return row

    api_calls = None
    traj_errors = 0
    try:
        traj = json.loads((run_dir / "trajectory.json").read_text())
        info = traj.get("info", {})
        api_calls = info.get("model_stats", {}).get("api_calls")
        row["exit_status"] = info.get("exit_status") or ""
        for msg in traj.get("messages", []):
            content = msg.get("content") or ""
            if isinstance(content, list):
                content = " ".join(b.get("text", "") for b in content if isinstance(b, dict))
            if content.startswith(FORMAT_ERROR_LINE):
                traj_errors += 1
    except Exception:
        pass
    token_log_steps = None
    event_steps: set[int] = set()
    compression_events = None
    try:
        tok = json.loads((run_dir / "token_log.json").read_text())
        token_log_steps = len(tok.get("step_prompt_tokens", []))
        event_steps = set(tok.get("compression_event_steps", []))
        compression_events = tok.get("compression_events")
    except Exception:
        pass
    delta = (run_dir / "agent.log").stat().st_mtime - (run_dir / "trajectory.json").stat().st_mtime

    parsed = parse_agent_log(run_dir / "agent.log")
    row["banners"] = parsed["banners"]
    row["api_calls"] = api_calls
    row["token_log_steps"] = token_log_steps
    row["compression_events"] = compression_events
    row["traj_errors"] = traj_errors
    row["log_time_delta_s"] = round(delta, 1)
    row["log_time_ok"] = abs(delta) <= LOG_TIME_WINDOW_S
    row.update(attribute(parsed, api_calls, token_log_steps, event_steps, row["exit_status"]))
    row["verdict"] = verdict_for(row)
    return row


# ── main ───────────────────────────────────────────────────────────────────────

def load_universe(audit: Path, all_conditions: bool) -> tuple[list[tuple[str, dict]], dict]:
    """Runs the audit scanned (summary conditions, or all), with condition metadata from condition_summary.csv."""
    stats = json.loads((audit / "source_file_stats.json").read_text())
    conditions = {}
    for c in read_csv(audit / "audit-swebench" / "condition_summary.csv"):
        conditions[(c["section"], c["cohort_model_path"], c["cell"])] = c
    items = []
    for rel in stats:
        if not rel.endswith("trajectory.json"):
            continue
        parts = Path(rel).parts  # ICLR_results/swebench/<section>/<cohort>/<cell>/<task>/<condition>/run_n/trajectory.json
        if len(parts) < 9:
            continue
        section, cohort, cell, task, condition, run = parts[2:8]
        cond = conditions.get((section, cohort, cell))
        if cond is None:
            continue
        summary_condition = is_summary_primitive(cond["primitive"])
        if not summary_condition and not all_conditions:
            continue
        items.append((rel, {
            "benchmark": cond["benchmark"], "section": section, "cohort_model_path": cohort, "cell": cell,
            "model": cond["model"], "primitive": cond["primitive"], "budget_tokens": cond["budget_tokens"],
            "depth": cond["depth"], "task": task, "condition": condition, "run": run,
            "summary_condition": summary_condition,
        }))
    return items, stats


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--audit-dir", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, default=Path("ICLR_results"),
                        help="root the audit scanned; its parent is the workspace the audit paths are relative to")
    parser.add_argument("--archive-root", type=Path, action="append", default=[],
                        help="directory holding moved runs under the same workspace-relative paths (repeatable)")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=min(16, os.cpu_count() or 1))
    parser.add_argument("--limit", type=int, default=None, help="scan only the first N runs (testing)")
    parser.add_argument("--all-conditions", action="store_true",
                        help="also scan non-summary conditions as a method self-check (never added to the rerun list)")
    args = parser.parse_args()

    audit = args.audit_dir.resolve()
    workspace = args.source_root.resolve().parent
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)

    items, stats = load_universe(audit, args.all_conditions)
    if args.limit:
        items = items[: args.limit]
    ctx = {"workspace": str(workspace), "archives": [str(a.resolve()) for a in args.archive_root], "stats": stats}
    print(f"scanning {len(items)} runs with {args.workers} workers", file=sys.stderr)
    with mp.Pool(args.workers, initializer=_init_worker, initargs=(ctx,)) as pool:
        rows = []
        for i, row in enumerate(pool.imap_unordered(process_run, items, chunksize=8), 1):
            rows.append(row)
            if i % 2000 == 0:
                print(f"  {i}/{len(items)}", file=sys.stderr)
    rows.sort(key=lambda r: r["trajectory"])

    # prior classifications
    rerun_rows = read_csv(audit / "rerun-list" / "rerun_runs.csv")
    prior_reason = {r["trajectory"]: r["rerun_reason"] for r in rerun_rows}
    details = {}
    runs_with_errors = audit / "audit-swebench" / "runs_with_errors.csv"
    if runs_with_errors.exists():
        details = {r["trajectory"]: r for r in read_csv(runs_with_errors)}
    prior_class = {}
    review_csv = audit / "review-swebench" / "review_unmarked.csv"
    if review_csv.exists():
        prior_class = {r["trajectory"]: r["classification"] for r in read_csv(review_csv)}
    for row in rows:
        row["prior_rerun_reason"] = prior_reason.get(row["trajectory"], "")
        row["prior_classification"] = prior_class.get(row["trajectory"], "")
    write_csv(output / "agentlog_attribution.csv", ATTRIB_FIELDS, rows)

    summary_rows = [r for r in rows if r["summary_condition"]]
    other_rows = [r for r in rows if not r["summary_condition"]]

    # additions in rerun_runs.csv schema: summary conditions only
    additions = []
    for row in summary_rows:
        if row["trajectory"] in prior_reason or row["verdict"] not in ADDITION_RULE:
            continue
        priority, reason = ADDITION_RULE[row["verdict"]]
        err = details.get(row["trajectory"], {})
        additions.append({**{k: row[k] for k in RERUN_FIELDS if k in row},
                          "rerun_priority": priority, "rerun_reason": reason,
                          "summary_marker_errors": err.get("summary_marker_errors", 0),
                          # a lower bound is asserted only when the verdict supports it
                          "summary_failure_lower_bound": (row["summary_failures_confirmed"]
                                                          if row["verdict"] == "summary_confirmed" else ""),
                          "error_response_details": err.get("details_file", "")})
    write_csv(output / "rerun_runs_agentlog_additions.csv", RERUN_FIELDS, additions)

    by_traj = {r["trajectory"]: r for r in rows}

    def agentlog_cols(traj: str) -> dict:
        r = by_traj.get(traj)
        if r is None:
            return {k: "" for k in AGENTLOG_FIELDS} | {"agentlog_verdict": "not_scanned"}
        confirmed = r["summary_failures_confirmed"] if r["verdict"] == "summary_confirmed" else ""
        return {"agentlog_verdict": r["verdict"], "agentlog_source": r["source_status"],
                "agentlog_log_errors": r["log_errors"], "agentlog_agent_failures": r["agent_failures"],
                "agentlog_summary_failures_raw": r["summary_failures_raw"],
                "agentlog_summary_failures_confirmed": confirmed,
                "agentlog_summary_failures_uncorroborated": r["summary_failures_uncorroborated"],
                "agentlog_tail_unresolved": r["tail_unresolved"], "agentlog_consistent": r["consistent"]}
    combined = [{**r, **agentlog_cols(r["trajectory"])} for r in rerun_rows]
    combined += [{**a, **agentlog_cols(a["trajectory"])} for a in additions]
    write_csv(output / "rerun_runs_with_agentlog.csv", RERUN_FIELDS + AGENTLOG_FIELDS, combined)

    # per-condition summary
    cond_key = ("benchmark", "section", "cohort_model_path", "cell", "model", "primitive", "budget_tokens", "depth")
    per_cond: dict[tuple, Counter] = defaultdict(Counter)
    for row in rows:
        c = per_cond[tuple(row[k] for k in cond_key)]
        c["runs_scanned"] += 1
        c[row["verdict"]] += 1
        if row["prior_rerun_reason"]:
            c["prior_recommended"] += 1
    add_by_cond = Counter(tuple(a[k] for k in cond_key) for a in additions)
    cond_rows = [dict(zip(cond_key, key)) | {v: c[v] for v in VERDICT_ORDER}
                 | {"runs_scanned": c["runs_scanned"], "prior_recommended": c["prior_recommended"],
                    "agentlog_additions": add_by_cond[key]}
                 for key, c in sorted(per_cond.items())]
    write_csv(output / "agentlog_condition_summary.csv",
              list(cond_key) + ["runs_scanned", "prior_recommended", "agentlog_additions"] + VERDICT_ORDER, cond_rows)

    # self-check outputs for non-summary conditions
    anomalies = [r for r in other_rows if (r["summary_failures_raw"] or 0) > 0]
    integrity = [r for r in other_rows if r["verdict"] in ("multi_run_log", "inconsistent", "source_changed", "log_missing")]
    if args.all_conditions:
        write_csv(output / "method_anomalies.csv", ATTRIB_FIELDS, anomalies)
        write_csv(output / "nonsummary_integrity.csv", ATTRIB_FIELDS, integrity)

    # README
    verdicts = Counter(r["verdict"] for r in summary_rows)
    by_prior = defaultdict(Counter)
    for r in summary_rows:
        by_prior[r["prior_rerun_reason"] or r["prior_classification"] or "(no trajectory error)"][r["verdict"]] += 1
    lines = [
        "agent.log attribution of FormatErrors (summary call vs normal agent call)",
        f"generated: {datetime.now().isoformat(timespec='seconds')}",
        f"audit dir: {audit}", f"workspace: {workspace}", f"archive roots: {ctx['archives']}",
        "", f"summary-condition runs scanned: {len(summary_rows)}",
        "verdicts: " + ", ".join(f"{v}={verdicts[v]}" for v in VERDICT_ORDER),
        f"additions to rerun_runs.csv: {len(additions)} "
        f"(priority={sum(a['rerun_priority']=='priority' for a in additions)}, "
        f"probable={sum(a['rerun_priority']=='probable' for a in additions)})",
    ]
    if args.all_conditions:
        anomaly_confirmed = sum(r["verdict"] == "summary_confirmed" for r in other_rows)
        lines += [
            f"non-summary runs scanned (self-check): {len(other_rows)}; with any summary evidence (method anomalies):"
            f" {len(anomalies)}; of which verdict summary_confirmed: {anomaly_confirmed} (must be 0);"
            f" failing structure checks: {len(integrity)} -> nonsummary_integrity.csv",
        ]
    lines += ["", "verdict by prior audit classification (summary conditions):"]
    for prior, c in sorted(by_prior.items()):
        lines.append(f"  {prior}: " + ", ".join(f"{v}={c[v]}" for v in VERDICT_ORDER if c[v]))
    lines += [
        "",
        "method: between consecutive headers 'mini-swe-agent (step N, $C):' a normal-agent FormatError consumes",
        "one step number and a summary FormatError consumes none (summarize() raises before n_calls += 1).",
        "Headers and 'User:' / 'Format error:' / '<error>' sequences are accepted only directly after the Rule",
        "line that step() prints before every query, and only when that rule follows the last line of a message;",
        "other occurrences (echoed transcripts) are counted in fake_headers / fake_errors and ignored.",
        "confirmation: an interval's summary failures count as confirmed only when token_log",
        "compression_event_steps contains the interval's starting step (the compression that finally succeeded",
        "after the failed summary calls). Summary evidence without that record is 'uncorroborated' (known",
        "legitimate cause: OTRC online clearing can end the over-budget state without a compression event; a",
        "fully quoted error block in a reply would look the same). Tail errors (after the last header) are never",
        "confirmed: with an exit status they are counted as uncorroborated, without one (killed run, saved",
        "api_calls may lag the log by one step) as tail_unresolved.",
        "same-execution checks: trajectory.json and token_log.json must equal the audited size/mtime",
        f"(source_status == exact) and agent.log mtime must lie within {LOG_TIME_WINDOW_S}s of trajectory.json.",
        "structure checks that block any confirmation: one process (one banner, increasing step numbers, no header",
        "glued to the previous line), no cut multi-byte characters, no step consumed without a printed Format error",
        "(unexplained_steps == 0), no tail errors after a Submitted exit, header count == token_log steps (+-1),",
        "api_calls within [max_step, max_step + tail + 1].",
        "verdicts: summary_confirmed; uncorroborated; tail_unresolved; inconsistent (structure or log/trajectory",
        "disagreement); multi_run_log (interleaved output of two processes: the run was launched twice into the",
        "same directory and its trajectory.json is whichever process saved last, so it is unreliable regardless",
        "of the summary bug); source_changed (not provably the audited execution); log_missing;",
        "no_summary_evidence (no summary FormatError detected; not proof that summaries never failed).",
        "columns: summary_failures_raw = confirmed + uncorroborated + tail_unresolved (computation only);",
        "summary_failure_lower_bound in the additions is filled only for summary_confirmed rows.",
        "additions (summary conditions only): summary_confirmed -> priority/agentlog_summary_failure;",
        "uncorroborated -> probable/agentlog_uncorroborated; tail_unresolved -> probable/agentlog_tail_unresolved;",
        "inconsistent, multi_run_log, source_changed, log_missing -> probable/agentlog_unverifiable.",
        "Non-summary conditions (--all-conditions) are never added; their summary evidence is a method anomaly.",
        "Runs already listed in rerun_runs.csv are annotated in rerun_runs_with_agentlog.csv, never duplicated.",
        "Experiment files were read only.",
    ]
    (output / "agentlog_README.txt").write_text("\n".join(lines) + "\n")
    print("\n".join(lines[5:10]))


if __name__ == "__main__":
    main()
