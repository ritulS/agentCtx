"""Write a copy of an outcomes table with re-evaluated SWE-bench verdicts applied.

The canonical tables in analysis/outcomes/ and the result directories under
ICLR_results/swebench are left untouched. The re-evaluation evidence
(ICLR_results/ICLR_reeval/<run>/verdict_comparison.csv, one row per re-run
attempt keyed by cell/task/run) is applied to a copy of the outcomes CSV,
which is written with the same schema so the analysis scripts can take it
through their --outcomes option.

Only `resolved` and its derived `failure_mode` change (a flipped attempt
becomes "resolved", or is re-derived with aggregate_benchmark_results.failure_mode
when a verdict flips to False). Rows are matched on model_key, experiment
section "main", cell, task and run number; every comparison row must match
exactly one outcomes row.

Usage (from the repository root):
    venv/bin/python analysis/apply_reeval_outcomes.py
    venv/bin/python analysis/apply_reeval_outcomes.py --reeval <dir> --model qwen35b --out <csv>
"""
from pathlib import Path
import argparse
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "analysis"))
from aggregate_benchmark_results import failure_mode  # noqa: E402

DEFAULT_REEVAL = ROOT / "ICLR_results/ICLR_reeval/qwen35b_main_review253_20260923"
DEFAULT_OUT = ROOT / "ICLR_results/ICLR_analysis/outcome/swebench_outcomes_reeval.csv"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--outcomes", type=Path, default=ROOT / "analysis/outcomes/swebench_outcomes.csv")
    parser.add_argument("--reeval", type=Path, default=DEFAULT_REEVAL,
                        help="re-evaluation directory holding verdict_comparison.csv")
    parser.add_argument("--model", default="qwen35b", help="model_key the re-evaluation belongs to")
    parser.add_argument("--section", default="main", help="experiment_section the re-evaluation covers")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)
    if args.out.resolve() == args.outcomes.resolve() or ROOT / "analysis/outcomes" in args.out.resolve().parents:
        parser.error("refusing to overwrite the canonical outcomes tables")

    comparison = pd.read_csv(args.reeval / "verdict_comparison.csv")
    if not comparison.status.eq("verified").all():
        parser.error("re-evaluation contains unverified rows")
    comparison["run"] = comparison.key.str.extract(r"__r(\d+)$")[0].astype(int)
    comparison["new"] = comparison.resolved_reeval_20260923.astype(str).str.lower().eq("true")

    d = pd.read_csv(args.outcomes, low_memory=False, dtype={"resolved": "string"})
    scope = d.model_key.eq(args.model) & d.experiment_section.eq(args.section)
    lookup = {(c, t, int(r)): i for i, c, t, r in zip(d.index[scope], d.cell[scope], d.task_name[scope], d.run_num[scope])}
    if len(lookup) != int(scope.sum()):
        parser.error("outcomes rows are not unique on cell/task/run within the re-evaluated scope")

    flips = []
    for row in comparison.itertuples(index=False):
        key = (row.cell, row.task, int(row.run))
        if key not in lookup:
            parser.error(f"no outcomes row for {key}")
        i = lookup[key]
        current = str(d.at[i, "resolved"]).lower() == "true"
        if str(d.at[i, "resolved"]).lower() != str(bool(row.resolved_index_now)).lower():
            parser.error(f"{key}: outcomes verdict differs from resolved_index_now; rebuild the outcomes table first")
        if current == row.new:
            continue
        d.at[i, "resolved"] = "True" if row.new else "False"
        record = d.loc[i].to_dict()
        record["resolved"] = bool(row.new)
        d.at[i, "failure_mode"] = failure_mode(record)
        flips.append((row.cell, row.task, row.run, current, row.new))

    args.out.parent.mkdir(parents=True, exist_ok=True)
    d.to_csv(args.out, index=False)
    up = sum(1 for f in flips if f[4]); down = len(flips) - up
    print(f"Applied {len(flips)} verdict changes ({up} False->True, {down} True->False) "
          f"from {args.reeval.name} to {args.model}/{args.section}; wrote {args.out}")
    per_cell = pd.Series([f[0] for f in flips]).value_counts()
    if len(per_cell):
        print(per_cell.to_string())


if __name__ == "__main__":
    main()
