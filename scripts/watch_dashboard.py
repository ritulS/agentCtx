#!/usr/bin/env python3
"""Rebuild COVERAGE.csv and DASHBOARD.html at a regular interval.

Run from anywhere in the repository with:

    venv/bin/python scripts/watch_dashboard.py

Use ``--interval-seconds 10`` for a quick test, or ``--interval-hours 2``
to rebuild every two hours.

Stop the watcher with Ctrl-C.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def rebuild() -> bool:
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n[{stamp}] Rebuilding coverage dashboard...", flush=True)

    coverage = subprocess.run(
        [sys.executable, "scripts/build_coverage.py"], cwd=ROOT, check=False
    )
    if coverage.returncode != 0:
        print("Coverage build failed; keeping the previous dashboard.", flush=True)
        return False

    dashboard = subprocess.run(
        [sys.executable, "scripts/build_dashboard.py"], cwd=ROOT, check=False
    )
    if dashboard.returncode != 0:
        print("Dashboard build failed.", flush=True)
        return False

    print("Dashboard is up to date.", flush=True)
    return True


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    interval = parser.add_mutually_exclusive_group()
    interval.add_argument(
        "--interval-seconds",
        type=float,
        help="seconds between rebuilds",
    )
    interval.add_argument(
        "--interval-minutes",
        type=float,
        help="minutes between rebuilds",
    )
    interval.add_argument(
        "--interval-hours",
        type=float,
        help="hours between rebuilds (default: 1)",
    )
    parser.add_argument(
        "--no-initial-build",
        action="store_true",
        help="wait for the first interval instead of building at startup",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.interval_seconds is not None:
        interval_seconds = args.interval_seconds
        interval_label = f"{args.interval_seconds:g} second(s)"
    elif args.interval_minutes is not None:
        interval_seconds = args.interval_minutes * 60
        interval_label = f"{args.interval_minutes:g} minute(s)"
    else:
        interval_hours = args.interval_hours if args.interval_hours is not None else 1.0
        interval_seconds = interval_hours * 60 * 60
        interval_label = f"{interval_hours:g} hour(s)"

    if interval_seconds <= 0:
        raise SystemExit("the interval must be greater than zero")

    if not args.no_initial_build:
        rebuild()

    print(
        f"Rebuilding every {interval_label} (Ctrl-C to stop)...",
        flush=True,
    )
    try:
        while True:
            time.sleep(interval_seconds)
            rebuild()
    except KeyboardInterrupt:
        print("\nWatcher stopped.")


if __name__ == "__main__":
    main()
