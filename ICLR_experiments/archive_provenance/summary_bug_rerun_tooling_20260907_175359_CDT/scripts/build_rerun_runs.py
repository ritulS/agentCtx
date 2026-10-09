"""Build the rerun candidate list from a query-error audit and its review.

Inputs are the output directories of export_query_errors.py (--audit-dir) and
review_unmarked_summary_errors.py (--review-dir). Writes rerun_runs.csv,
rerun_condition_summary.csv and rerun_README.txt into the audit directory.

With --update-cohort, the freshly built rows for one cohort_model_path replace
that cohort's rows in an older audit directory's rerun files (--into). Rows of
other cohorts there are left untouched, so a rerun list can be refreshed for a
cohort whose results changed after the original snapshot.
"""

import argparse
import csv
import shutil
from collections import Counter
from datetime import datetime
from pathlib import Path


RERUN_FIELDS = [
    "benchmark", "section", "cohort_model_path", "cell", "model", "primitive",
    "budget_tokens", "depth", "task", "condition", "run", "rerun_priority",
    "rerun_reason", "summary_marker_errors", "summary_failure_lower_bound",
    "trajectory", "error_response_details",
]
CONDITION_KEY = ("benchmark", "section", "cohort_model_path", "cell", "model", "primitive", "budget_tokens", "depth")
COUNT_FIELDS = [
    "rerun_priority_runs", "rerun_probable_runs", "rerun_recommended_runs",
    "summary_marker_error_runs", "summary_failure_accounting_runs",
    "summary_related_response_runs", "unresolved_runs",
]
PRIORITY = {"summary_marker_error": "priority", "summary_failure_accounting": "priority",
            "summary_related_response": "probable"}


def read_csv(path):
    with path.open() as stream:
        return list(csv.DictReader(stream))


def write_csv(path, fields, rows):
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def build(audit, review):
    runs = read_csv(audit / "runs_with_errors.csv")
    review_csv = next(p for p in (review / "review_unmarked.csv", review / "review_870.csv") if p.exists())
    reviewed = {r["trajectory"]: r for r in read_csv(review_csv)}
    rows = []
    unresolved = Counter()
    for run in runs:
        if "summar" not in run["primitive"]:
            continue
        if int(run["summary_marker_errors"]) > 0:
            reason, lower_bound = "summary_marker_error", ""
        else:
            record = reviewed[run["trajectory"]]
            assert all(record[k] == run[k] for k in CONDITION_KEY + ("task", "condition", "run")), run["trajectory"]
            lower_bound = record["summary_failure_lower_bound"]
            if record["classification"] == "not_established":
                unresolved[tuple(run[k] for k in CONDITION_KEY)] += 1
                continue
            reason = record["classification"]
        rows.append({
            **{k: run[k] for k in CONDITION_KEY + ("task", "condition", "run")},
            "rerun_priority": PRIORITY[reason], "rerun_reason": reason,
            "summary_marker_errors": run["summary_marker_errors"],
            "summary_failure_lower_bound": lower_bound,
            "trajectory": run["trajectory"],
            "error_response_details": str(audit / run["details_file"]),
        })
    per_condition = {}
    for row in rows:
        per_condition.setdefault(tuple(row[k] for k in CONDITION_KEY), Counter())[row["rerun_reason"]] += 1
    conditions = []
    for condition in read_csv(audit / "condition_summary.csv"):
        key = tuple(condition[k] for k in CONDITION_KEY)
        counts = per_condition.get(key)
        if not counts:
            continue
        priority = counts["summary_marker_error"] + counts["summary_failure_accounting"]
        probable = counts["summary_related_response"]
        conditions.append({
            **condition,
            "rerun_priority_runs": priority, "rerun_probable_runs": probable,
            "rerun_recommended_runs": priority + probable,
            "summary_marker_error_runs": counts["summary_marker_error"],
            "summary_failure_accounting_runs": counts["summary_failure_accounting"],
            "summary_related_response_runs": probable,
            "unresolved_runs": unresolved[key],
        })
    return rows, conditions


def readme(rows, conditions, header, extra=""):
    reasons = Counter(r["rerun_reason"] for r in rows)
    priority = reasons["summary_marker_error"] + reasons["summary_failure_accounting"]
    probable = reasons["summary_related_response"]
    return (
        f"{header}\n\n"
        f"Conditions: {len(conditions)}\nPriority reruns: {priority} runs\nAdditional candidates including inferred cases: {probable} runs\n"
        f"Total recommended: {priority + probable} runs\n\n"
        "rerun_condition_summary.csv: Preserves the existing condition_summary.csv columns and adds rerun counts. Includes only conditions with at least one recommended run.\n"
        f"rerun_runs.csv: Lists {priority + probable} target task/condition/run combinations. This does not request rerunning every run in each condition.\n\n"
        f"rerun_priority_runs = summary_marker_error_runs ({reasons['summary_marker_error']}) "
        f"+ summary_failure_accounting_runs ({reasons['summary_failure_accounting']})\n"
        f"rerun_probable_runs = summary_related_response_runs ({probable})\n"
        "rerun_recommended_runs = rerun_priority_runs + rerun_probable_runs\n"
        "unresolved_runs = runs with an unestablished connection. Excluded from the recommended total. This does not mean unaffected.\n"
        "runs_scanned and existing error counts cover each entire condition in the original audit, not just recommended runs.\n"
        "Classifications based on summary markers or response content do not establish the call origin in every case. The original experiment logs are unchanged.\n"
        + extra
    )


def write_outputs(target, rows, conditions, header, extra=""):
    write_csv(target / "rerun_runs.csv", RERUN_FIELDS, rows)
    fields = list(conditions[0]) if conditions else list(read_csv(target / "condition_summary.csv")[0]) + COUNT_FIELDS
    write_csv(target / "rerun_condition_summary.csv", fields, conditions)
    (target / "rerun_README.txt").write_text(readme(rows, conditions, header, extra))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit-dir", type=Path, required=True)
    parser.add_argument("--review-dir", type=Path, required=True)
    parser.add_argument("--update-cohort", default=None,
                        help="cohort_model_path whose rows replace the same cohort's rows in --into")
    parser.add_argument("--into", type=Path, default=None, help="Older audit directory to update in place")
    parser.add_argument("--output-dir", type=Path, default=None,
                        help="Where to write the built files (default: the audit directory)")
    args = parser.parse_args()
    audit = args.audit_dir.resolve(strict=True)
    review = args.review_dir.resolve(strict=True)
    rows, conditions = build(audit, review)
    output = (args.output_dir or audit).resolve()
    output.mkdir(parents=True, exist_ok=True)
    if output != audit:
        shutil.copy2(audit / "condition_summary.csv", output / "condition_summary.csv")
    write_outputs(output, rows, conditions, "Rerun candidates for the summary bug (compiled from a previous audit snapshot)")
    print(f"{output}: {len(rows)} runs, {len(conditions)} conditions")
    if not args.update_cohort:
        return
    assert args.into is not None, "--into is required with --update-cohort"
    target = args.into.resolve(strict=True)
    stamp = datetime.now().astimezone().strftime("%Y%m%d-%H%M")
    old_rows = read_csv(target / "rerun_runs.csv")
    old_conditions = read_csv(target / "rerun_condition_summary.csv")
    for name in ("rerun_runs.csv", "rerun_condition_summary.csv", "rerun_README.txt"):
        shutil.copy2(target / name, target / f"{Path(name).stem}.before-{args.update_cohort}-update-{stamp}{Path(name).suffix}")
    cohort = args.update_cohort
    keep = lambda r: r["cohort_model_path"] != cohort
    new_rows = [r for r in rows if not keep(r)]
    new_conditions = [c for c in conditions if not keep(c)]
    assert new_rows, f"no rows for cohort {cohort} in {audit}"
    # Keep the path-sorted order used by export_query_errors.py.
    merged_rows = sorted([r for r in old_rows if keep(r)] + new_rows, key=lambda r: r["trajectory"].split("/"))
    merged_conditions = sorted([c for c in old_conditions if keep(c)] + new_conditions,
                               key=lambda c: tuple(c[k] for k in CONDITION_KEY))
    old_text = (target / "rerun_README.txt").read_text()
    # Accept the legacy Japanese heading when reading existing audit files.
    history_heading = "\nUpdate history:\n"
    legacy_heading = "\n\u66f4\u65b0\u5c65\u6b74:\n"
    heading = history_heading if history_heading in old_text else legacy_heading
    history = old_text.split(heading, 1)[1] if heading in old_text else ""
    history += (
        f"- {stamp}: cohort_model_path={cohort} rows replaced with rescan results from {audit.name} ({review.name})"
        f" ({sum(1 for r in old_rows if not keep(r))} rows -> {len(new_rows)} rows). Other cohorts retain their original snapshot rows."
        f" Previous files saved as *.before-{cohort}-update-{stamp}.*.\n"
    )
    write_outputs(target, merged_rows, merged_conditions, old_text.splitlines()[0], history_heading + history)
    print(f"{target}: {cohort} rows {sum(1 for r in old_rows if not keep(r))} -> {len(new_rows)}; "
          f"total {len(old_rows)} -> {len(merged_rows)}; conditions {len(old_conditions)} -> {len(merged_conditions)}")


if __name__ == "__main__":
    main()
