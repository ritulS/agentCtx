#!/usr/bin/env python3
"""Publish dashboard inputs from the experiment tree to a data worktree.

The destination must be a git worktree checked out on
``akiho-expansion-data``. This script builds SWE-Bench coverage locally, reads
Terminal-Bench coverage from its remote data branch, copies the other files
needed by GitHub Pages, and pushes a commit only when they changed. The source
worktree stays untouched.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_WORKTREE = ROOT.with_name(f"{ROOT.name}-data")
DEFAULT_TB_BRANCH = "akiho-expansion-terminalbench-0829-data"
PUBLISHED_FILES = (
    Path("COVERAGE.csv"),
    Path("COVERAGE_TB.csv"),
    Path("dashboard_progress_history.jsonl"),
    Path("dashboard/build_dashboard.py"),
    Path(".github/workflows/dashboard-pages.yml"),
)
COPIED_FILES = PUBLISHED_FILES[3:]
LEGACY_FILES = (Path("scripts/build_dashboard.py"),)


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
        "--tb-branch",
        default=DEFAULT_TB_BRANCH,
        help=f"remote branch containing COVERAGE_TB.csv (default: {DEFAULT_TB_BRANCH})",
    )
    parser.add_argument(
        "--skip-coverage-build",
        action="store_true",
        help="publish the existing local COVERAGE.csv without regenerating it",
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


def copy_remote_file(remote: str, branch: str, repo_path: str, destination: Path) -> None:
    """Copy one file from the latest commit of a remote branch."""
    run("git", "fetch", "--quiet", remote, branch, cwd=ROOT)
    result = run("git", "show", f"FETCH_HEAD:{repo_path}", cwd=ROOT, capture=True)
    temporary = destination.with_name(f".{destination.name}.tmp")
    temporary.write_text(result.stdout, encoding="utf-8")
    temporary.replace(destination)


def main() -> None:
    args = parse_args()
    worktree = args.worktree.expanduser().resolve()

    if not worktree.exists():
        raise SystemExit(
            f"dashboard data worktree does not exist: {worktree}\n"
            "Create it first; see dashboard/README.md."
        )
    if not worktree.is_dir():
        raise SystemExit(f"dashboard data worktree is not a directory: {worktree}")
    if not (worktree / ".git").exists():
        raise SystemExit(
            f"{worktree} is not a git worktree. Create it first; see "
            "dashboard/README.md."
        )
    branch = current_branch(worktree)
    if branch != args.branch:
        raise SystemExit(
            f"refusing to publish: {worktree} is on {branch!r}, "
            f"expected {args.branch!r}"
        )

    coverage_destination = worktree / "COVERAGE.csv"
    tb_coverage_destination = worktree / "COVERAGE_TB.csv"
    if args.skip_coverage_build:
        shutil.copy2(ROOT / "COVERAGE.csv", coverage_destination)
    else:
        with tempfile.TemporaryDirectory(prefix="agentctx-coverage-") as temporary_dir:
            run(
                sys.executable,
                "dashboard/build_coverage.py",
                "--output",
                str(coverage_destination),
                "--tb-output",
                str(Path(temporary_dir) / "COVERAGE_TB.csv"),
                cwd=ROOT,
            )

    copy_remote_file(
        args.remote,
        args.tb_branch,
        "COVERAGE_TB.csv",
        tb_coverage_destination,
    )

    for relative in COPIED_FILES:
        source = ROOT / relative
        if not source.is_file():
            raise SystemExit(f"required source file is missing: {source}")
        destination = worktree / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)

    staged_files = list(PUBLISHED_FILES)
    for relative in LEGACY_FILES:
        legacy = worktree / relative
        if legacy.is_file():
            legacy.unlink()
            staged_files.append(relative)

    # Record after both coverage CSVs and the current builder are in the worktree.
    # GitHub Actions only reads this history, so deployments do not create noise.
    run(sys.executable, "dashboard/build_dashboard.py", "--record-history", cwd=worktree)

    run(
        "git",
        "add",
        "--",
        *(str(path) for path in staged_files),
        cwd=worktree,
    )
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
