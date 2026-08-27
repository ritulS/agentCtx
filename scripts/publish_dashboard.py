#!/usr/bin/env python3
"""Publish dashboard inputs from the experiment tree to a data worktree.

The destination must be a git worktree checked out on
``akiho-expansion-data``. This script rebuilds COVERAGE.csv, copies the three
files needed by GitHub Pages, and pushes a commit only when they changed.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_WORKTREE = ROOT.with_name(f"{ROOT.name}-data")
PUBLISHED_FILES = (
    Path("COVERAGE.csv"),
    Path("scripts/build_dashboard.py"),
    Path(".github/workflows/dashboard-pages.yml"),
)


def run(*args: str, cwd: Path, capture: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=cwd,
        check=True,
        text=True,
        capture_output=capture,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--worktree",
        type=Path,
        default=DEFAULT_WORKTREE,
        help=f"data-branch worktree (default: {DEFAULT_WORKTREE})",
    )
    parser.add_argument("--branch", default="akiho-expansion-data")
    parser.add_argument("--remote", default="origin")
    parser.add_argument(
        "--skip-coverage-build",
        action="store_true",
        help="publish the existing COVERAGE.csv without regenerating it",
    )
    parser.add_argument(
        "--no-push",
        action="store_true",
        help="copy and commit locally, but do not push",
    )
    return parser.parse_args()


def current_branch(worktree: Path) -> str:
    result = run(
        "git", "branch", "--show-current", cwd=worktree, capture=True
    )
    return result.stdout.strip()


def main() -> None:
    args = parse_args()
    worktree = args.worktree.expanduser().resolve()

    if not (worktree / ".git").exists():
        raise SystemExit(
            f"{worktree} is not a git worktree. Create it first; see "
            "docs/dashboard-pages.md."
        )
    branch = current_branch(worktree)
    if branch != args.branch:
        raise SystemExit(
            f"refusing to publish: {worktree} is on {branch!r}, "
            f"expected {args.branch!r}"
        )

    if not args.skip_coverage_build:
        run(sys.executable, "scripts/build_coverage.py", cwd=ROOT)

    for relative in PUBLISHED_FILES:
        source = ROOT / relative
        if not source.is_file():
            raise SystemExit(f"required source file is missing: {source}")
        destination = worktree / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)

    run("git", "add", "--", *(str(path) for path in PUBLISHED_FILES), cwd=worktree)
    changed = subprocess.run(
        ["git", "diff", "--cached", "--quiet", "--exit-code"], cwd=worktree
    ).returncode != 0
    if not changed:
        print("Dashboard inputs are unchanged; nothing to publish.")
        return

    stamp = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z")
    run("git", "commit", "-m", f"data: update coverage dashboard ({stamp})", cwd=worktree)
    if args.no_push:
        print("Committed dashboard inputs locally (--no-push).")
    else:
        run("git", "push", args.remote, args.branch, cwd=worktree)
        print(f"Published dashboard inputs to {args.remote}/{args.branch}.")


if __name__ == "__main__":
    main()
