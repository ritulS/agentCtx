"""Fixtures for the runner-equivalence suite.

The reference code is taken from the remote branches listed in
``REFERENCE_BRANCHES``: ``git fetch`` refreshes the remote-tracking ref, then
``git archive`` extracts that commit's runner sources (``scripts/``, ``src/``
and the root-level modules older trees import, such as ``summary_config.py``)
into a session-scoped temporary directory. Set ``AGENTCTX_TEST_NO_FETCH=1`` to
compare against the already-fetched refs without touching the network.
"""

from __future__ import annotations

import io
import os
import subprocess
import sys
import tarfile
import warnings
from pathlib import Path

import pytest

# PyYAML is a runtime dependency of the runners under test; fail loudly here
# rather than letting both sides crash "equivalently" inside the sandboxes.
import yaml  # noqa: F401

from harness import REPO_ROOT, Tree, current_tree

# The pre-reorganization tree this working tree must stay behaviourally
# identical to. Older branches can be selected with --reference-branch;
# scenarios that need a capability they predate are skipped for them.
REFERENCE_BRANCHES = ("akiho-clean-20260921",)
REMOTE = "origin"
# Paths extracted from a reference commit when they exist there.
REFERENCE_PATHS = ("scripts", "src", "summary_config.py", "memory.py")

if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))


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

    present = _git("ls-tree", "--name-only", commit, "--", *REFERENCE_PATHS).stdout.split()
    if "scripts" not in present:
        pytest.skip(f"{ref} has no scripts/ directory")
    archive = subprocess.run(
        ["git", "archive", commit, *present],
        cwd=REPO_ROOT, check=True, capture_output=True, timeout=120,
    ).stdout
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        try:
            tar.extractall(dest, filter="data")
        except TypeError:  # Python without the extraction-filter API
            tar.extractall(dest)
    return Tree(label=f"{ref}@{commit[:10]}", root=dest)


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
    """Runner sources of one reference branch (selected with --reference-branch), extracted once per session."""
    dest = tmp_path_factory.mktemp(f"reference-{request.param}")
    return checkout_reference(request.param, dest)


@pytest.fixture(scope="session")
def working_tree() -> Tree:
    return current_tree()
