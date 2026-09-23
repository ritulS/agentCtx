#!/usr/bin/env python3
"""Post an outcome summary of a raised-limit re-run to Slack.

Usage: post_rerun_summary.py <unit> <rerun_limit_failures.py args...>

Runs the planner (``--dry-run``) with the same arguments to find the output
directory, then counts the outcomes in its ``experiment_results.json``.
Meant as the ``--on-success`` hook of ``scripts/notify_run.sh``; best effort.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

WS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WS / "dashboard"))
from notify_slack import post_to_slack  # noqa: E402

RUNNER = WS / "adaptive_context_management_analysis" / "rerun_limit_failures.py"


def outcome(row: dict) -> str:
    if row.get("returncode") == -1:
        return "timeout"
    if row.get("exit_status") == "LimitsExceeded":
        return "step_limit"
    if row.get("exit_status") == "Submitted":
        return {True: "resolved", False: "submitted_unresolved", None: "submitted_uneval"}[row.get("resolved")]
    return f"other:{row.get('exit_status') or 'none'}"


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__, file=sys.stderr)
        return 2
    unit, runner_args = sys.argv[1], [a for a in sys.argv[2:] if a != "--with-eval"]
    plan = subprocess.run([sys.executable, str(RUNNER), *runner_args, "--dry-run"],
                          capture_output=True, text=True, cwd=WS).stdout
    m = re.search(r"Output dir\s*:\s*(\S+)", plan)
    if not m:
        raise SystemExit("could not find output dir in plan")
    res_path = Path(m.group(1)) / "experiment_results.json"
    if not res_path.is_absolute():
        res_path = WS / res_path
    if not res_path.exists():
        raise SystemExit(f"no results at {res_path}")
    rows = json.loads(res_path.read_text())
    counts = Counter(outcome(r) for r in rows)
    lines = "\n".join(f"• {k}: `{v}`" for k, v in sorted(counts.items(), key=lambda kv: -kv[1]))
    shown = res_path.relative_to(WS) if res_path.is_relative_to(WS) else res_path
    post_to_slack(f"📊 *Raised-limit re-run summary* (`{unit}`)\n"
                  f"• runs recorded: `{len(rows)}`\n{lines}\n• results: `{shown}`")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"post_rerun_summary.py: {exc}", file=sys.stderr)
        raise SystemExit(1)
