"""Fixtures for the runner-equivalence suite.

The reference code is taken from the remote branches listed in
``REFERENCE_BRANCHES``: ``git fetch`` refreshes the remote-tracking ref, then
``git archive`` extracts that commit's ``scripts/`` into a session-scoped
temporary directory. Set ``AGENTCTX_TEST_NO_FETCH=1`` to compare against the
already-fetched refs without touching the network.
"""

from __future__ import annotations

import io
import os
import subprocess
import tarfile
import warnings
from pathlib import Path

import pytest

# PyYAML is a runtime dependency of the runners under test; fail loudly here
# rather than letting both sides crash "equivalently" inside the sandboxes.
import yaml  # noqa: F401

from harness import REPO_ROOT, Tree, current_tree

REFERENCE_BRANCHES = ("akiho-expansion", "akiho-expansion-terminalbench-0829")
REMOTE = "origin"


def _git(*args: str, check: bool = True, timeout: int = 120) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=REPO_ROOT, check=check, capture_output=True, text=True, timeout=timeout
    )


def fetch_reference(branch: str) -> None:
    if os.environ.get("AGENTCTX_TEST_NO_FETCH") == "1":
        return
    try:
        _git("fetch", "--quiet", REMOTE, branch)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        detail = getattr(exc, "stderr", "") or str(exc)
        warnings.warn(
            f"git fetch {REMOTE} {branch} failed; comparing against the local "
            f"remote-tracking ref instead: {detail.strip()}"
        )


def checkout_reference(branch: str, dest: Path) -> Tree:
    fetch_reference(branch)
    ref = f"{REMOTE}/{branch}"
    resolved = _git("rev-parse", "--verify", f"{ref}^{{commit}}", check=False)
    if resolved.returncode:
        pytest.skip(f"{ref} is not available locally; run `git fetch {REMOTE} {branch}`")
    commit = resolved.stdout.strip()

    archive = subprocess.run(
        ["git", "archive", commit, "scripts"],
        cwd=REPO_ROOT, check=True, capture_output=True, timeout=120,
    ).stdout
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        try:
            tar.extractall(dest, filter="data")
        except TypeError:  # Python without the extraction-filter API
            tar.extractall(dest)
    return Tree(label=f"{ref}@{commit[:10]}", scripts_dir=dest / "scripts", src_dir=None)


def pytest_addoption(parser) -> None:
    parser.addoption(
        "--reference-branch",
        action="append",
        default=None,
        metavar="BRANCH",
        help=(
            f"compare against {REMOTE}/BRANCH only; repeat to compare against several. "
            f"Default: {', '.join(REFERENCE_BRANCHES)}"
        ),
    )


def selected_branches(config) -> list[str]:
    chosen = config.getoption("reference_branch") or list(REFERENCE_BRANCHES)
    return [branch.removeprefix(f"{REMOTE}/") for branch in chosen]


def pytest_generate_tests(metafunc) -> None:
    if "reference_tree" in metafunc.fixturenames:
        branches = selected_branches(metafunc.config)
        metafunc.parametrize("reference_tree", branches, ids=branches, indirect=True, scope="session")


@pytest.fixture(scope="session")
def reference_tree(request, tmp_path_factory) -> Tree:
    """Scripts of one reference branch (selected with --reference-branch), extracted once per session."""
    dest = tmp_path_factory.mktemp(f"reference-{request.param}")
    return checkout_reference(request.param, dest)


@pytest.fixture(scope="session")
def working_tree() -> Tree:
    return current_tree()
