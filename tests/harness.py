"""Machinery for the runner-equivalence tests.

The experiment runners cannot be executed for real inside a test: they need a
vLLM server, rootless Podman, and Harbor. Everything that touches those is a
subprocess, though, so each runner is executed in a throwaway *sandbox* whose
``venv/bin/python``, ``venv-harbor/bin/harbor`` and ``docker`` are the
deterministic fakes in ``tests/fakes/``. Two runners given the same command
line therefore leave identical result trees if and only if they ask the fakes
for the same thing.

A sandbox is a plain directory laid out like the repository root: the runner's
``WORKSPACE_ROOT`` resolves to it, so fixtures (configs, task lists, dataset)
live under it and the sandbox path is rewritten to ``<WS>`` before comparison.
"""

from __future__ import annotations

import difflib
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from itertools import zip_longest
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
FAKES_DIR = TESTS_DIR / "fakes"

# ── Trees under test ────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Tree:
    """A copy of the code to exercise: ``scripts/`` plus, when present, ``src/``."""

    label: str
    scripts_dir: Path
    src_dir: Path | None = None

    @property
    def features(self) -> frozenset[str]:
        """Capabilities detected from the tree, used to skip scenarios it predates."""
        features = set()
        terminal_bench_adapters = [self.scripts_dir / "bench_adapters" / "terminal_bench.py"]
        if self.src_dir is not None:
            terminal_bench_adapters.append(
                self.src_dir / "agentctx" / "benchmarks" / "terminal_bench.py"
            )
        if any(path.exists() for path in terminal_bench_adapters):
            features.add("terminal-bench")
        return frozenset(features)


def current_tree() -> Tree:
    return Tree(label="working-tree", scripts_dir=REPO_ROOT / "scripts", src_dir=REPO_ROOT / "src")


# ── Fixture data ────────────────────────────────────────────────────────────────
#
# Instance ids drive the fakes: ``-crash`` exits non-zero without writing a
# trajectory, ``-nopatch`` finishes without a submission, everything else
# submits a patch. Terminal-Bench names use ``-fail`` (reward 0) and
# ``-timeout`` (no verifier result, AgentTimeoutError).

SWE_TASKS_BY_REPO = {
    "django": [
        "django__django-10001",
        "django__django-10002-nopatch",
        "django__django-10003",
    ],
    "sympy": [
        "sympy__sympy-20001-crash",
        "sympy__sympy-20002",
        "sympy__sympy-20003",
    ],
    "scikit-learn": [
        "scikit-learn__scikit-learn-30001",
        "scikit-learn__scikit-learn-30002-nopatch",
        "scikit-learn__scikit-learn-30003-crash",
    ],
}
ABLATION_TASKS = [
    "django__django-10001",
    "django__django-10002-nopatch",
    "sympy__sympy-20001-crash",
    "scikit-learn__scikit-learn-30001",
]
CUSTOM_TASKS = [
    "django__django-10003",
    "sympy__sympy-20002",
    "scikit-learn__scikit-learn-30002-nopatch",
]
TB_TASKS = ["alpha-task", "beta-task-fail", "gamma-task-timeout", "delta-task"]
TB_TASK_LIST = {"tasks": ["beta-task-fail", "alpha-task"]}
TB_TASK_LIST_BAD = ["alpha-task", "zeta-task"]

_MODEL_A = """model:
  model_name: "hosted_vllm/test/model-a"
  model_class: "litellm_textbased"
  model_kwargs:
    api_base: "http://localhost:8000/v1"
    temperature: 0.2
"""
_MODEL_B = """model:
  model_name: "hosted_vllm/test/model-b"
  model_class: "litellm_textbased"
  model_kwargs:
    api_base: "http://localhost:8001/v1"
    temperature: 0.2
"""
_AGENT = """agent:
  step_limit: 125
  cost_limit: 0.0
  cost_tracking: ignore_errors
  mode: yolo
"""
CONFIGS = {
    "config-qwen-vllm.yaml": _AGENT + _MODEL_A,
    "config-online-trc.yaml": _AGENT + "  system_template: online-trc prompts\n" + _MODEL_A,
    "config-tbench.yaml": _AGENT + "  instance_template: terminal-bench prompt\n",
    "config-alt-agent.yaml": _AGENT + _MODEL_B,
    "config-alt-otrc.yaml": _AGENT + "  system_template: alt online-trc prompts\n" + _MODEL_B,
}


def _repo_label(instance_id: str) -> str:
    return instance_id.split("__", 1)[0]


def _swe_task(instance_id: str) -> dict:
    return {"instance_id": instance_id, "repo": _repo_label(instance_id)}


# ── Sandbox ─────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class CommandResult:
    argv: list[str]
    returncode: int
    stdout: str
    stderr: str


@dataclass
class Sandbox:
    root: Path
    tree: Tree
    python: str = field(default_factory=lambda: sys.executable)
    results: list[CommandResult] = field(default_factory=list)

    def run(self, argv: list[str], *, timeout: int = 300) -> CommandResult:
        """Run ``scripts/<argv[0]>`` with the remaining arguments, cwd at the root."""
        script = self.root / "scripts" / argv[0]
        completed = subprocess.run(
            [self.python, str(script), *argv[1:]],
            cwd=self.root,
            env=runner_environment(),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        result = CommandResult(list(argv), completed.returncode, completed.stdout, completed.stderr)
        self.results.append(result)
        return result


def runner_environment() -> dict[str, str]:
    """A controlled environment shared by both sides of a comparison.

    ``PYTHONPATH`` is deliberately absent so the runner's "extend an existing
    PYTHONPATH" branch behaves identically; ``PYTHONHASHSEED`` pins set
    iteration order in error messages that print sets.
    """
    return {
        "PATH": os.pathsep.join((str(FAKES_DIR / "bin"), os.environ.get("PATH", ""))),
        "HOME": os.environ.get("HOME", str(Path.home())),
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "PYTHONHASHSEED": "0",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONUNBUFFERED": "1",
        "PYTHONIOENCODING": "utf-8",
    }


def build_sandbox(root: Path, tree: Tree, *, python: str | None = None) -> Sandbox:
    """Copy ``tree`` into ``root`` and surround it with identical fixtures and fakes."""
    root = root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    python = python or sys.executable

    ignore = shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo")
    shutil.copytree(tree.scripts_dir, root / "scripts", ignore=ignore)
    if tree.src_dir is not None:
        shutil.copytree(tree.src_dir, root / "src", ignore=ignore)

    configs = root / "configs"
    configs.mkdir()
    for name, text in CONFIGS.items():
        (configs / name).write_text(text)

    task_lists = root / "task_lists"
    task_lists.mkdir()
    selected = [_swe_task(iid) for ids in SWE_TASKS_BY_REPO.values() for iid in ids]
    _write_json(task_lists / "selected_tasks.json", selected)
    _write_json(task_lists / "custom_tasks.json", [_swe_task(iid) for iid in CUSTOM_TASKS])
    _write_json(task_lists / "tb_tasks.json", TB_TASK_LIST)
    _write_json(task_lists / "tb_tasks_bad.json", TB_TASK_LIST_BAD)
    _write_json(root / "results" / "ablations" / "tasks.json", [_swe_task(iid) for iid in ABLATION_TASKS])

    dataset = root / "data" / "tb1-harbor-0.1.1"
    for task in TB_TASKS:
        (dataset / task).mkdir(parents=True)
        (dataset / task / "task.toml").write_text(f'name = "{task}"\n')
    (dataset / "README.md").write_text("not a task directory\n")

    (root / "mini-swe-agent").mkdir()
    (root / "mini-swe-agent" / ".keep").write_text("")
    (root / "logs").mkdir()

    _write_wrapper(root / "venv" / "bin" / "python", python, FAKES_DIR / "fake_agent.py")
    _write_wrapper(root / "venv-harbor" / "bin" / "harbor", python, FAKES_DIR / "fake_harbor.py")
    return Sandbox(root=root, tree=tree, python=python)


def _write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2))


def _write_wrapper(path: Path, python: str, fake: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f'#!/bin/sh\nexec "{python}" "{fake}" "$@"\n')
    path.chmod(0o755)


# ── Scenarios ───────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Command:
    argv: tuple[str, ...]
    returncode: int = 0


@dataclass(frozen=True)
class Scenario:
    name: str
    commands: tuple[Command, ...]
    requires: frozenset[str] = frozenset()


def execute(sandbox: Sandbox, scenario: Scenario) -> dict:
    """Run every command of ``scenario`` and return a normalized observation."""
    commands = []
    for command in scenario.commands:
        result = sandbox.run(list(command.argv))
        assert result.returncode == command.returncode, (
            f"{sandbox.tree.label}: {' '.join(command.argv)} exited "
            f"{result.returncode}, expected {command.returncode}\n"
            f"--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"
        )
        commands.append(normalize_result(result, sandbox.root))
    return {"commands": commands, "files": snapshot(sandbox)}


# ── Normalization ───────────────────────────────────────────────────────────────

# Values that legitimately differ between two runs of the same code.
VOLATILE_KEYS = {
    "timestamp": "<TIME>",
    "started": "<TIME>",
    "e2e_latency_s": "<SECONDS>",
}
_HARBOR_JOB_TS = re.compile(r"(-r\d+-)\d{13}")
_E2E = re.compile(r"e2e=\d+s")
_PROGRESS = re.compile(r"\[\s*\d+/(\d+)\]")
_STARTED_ROW = re.compile(r"^\| Started \| .* \|$", re.MULTILINE)
# print() writes the body and the newline separately, so with --max-workers > 1
# two progress lines can land on one physical line followed by a blank one.
# Re-split in front of a progress marker that does not start its line.
_GLUED_PROGRESS = re.compile(r"(?<=\S)(?=\s+\[(?:<N>/\d+\]|[Px]\] e2e=))")

# Deliberate changes introduced by the src/agentctx refactor. They are rewritten
# to one common form here so the equivalence check covers everything else, and
# each is asserted directly in test_runner_equivalence.py.
INTENTIONAL_TEXT_REWRITES = (
    (
        "scripts.bench_adapters.harbor_adapter:CompressionAgent",
        "agentctx.benchmarks.harbor_adapter:CompressionAgent",
    ),
)
INTENTIONAL_PYTHONPATH_ENTRIES = ("<WS>/src",)


def normalize_text(text: str, root: Path) -> str:
    text = text.replace(str(root), "<WS>")
    text = _HARBOR_JOB_TS.sub(r"\1<TS>", text)
    text = _E2E.sub("e2e=<T>s", text)
    text = _PROGRESS.sub(r"[<N>/\1]", text)
    for old, new in INTENTIONAL_TEXT_REWRITES:
        text = text.replace(old, new)
    return text


def normalize_json(value, root: Path):
    if isinstance(value, dict):
        out = {}
        for key, item in value.items():
            if key in VOLATILE_KEYS:
                out[key] = VOLATILE_KEYS[key]
            elif key == "PYTHONPATH" and isinstance(item, str):
                entries = normalize_text(item, root).split(os.pathsep)
                out[key] = os.pathsep.join(
                    entry for entry in entries if entry not in INTENTIONAL_PYTHONPATH_ENTRIES
                )
            else:
                out[key] = normalize_json(item, root)
        return out
    if isinstance(value, list):
        return [normalize_json(item, root) for item in value]
    if isinstance(value, str):
        return normalize_text(value, root)
    return value


def normalize_file(path: Path, root: Path) -> str:
    text = path.read_text()
    if path.suffix == ".json":
        try:
            data = json.loads(text)
        except ValueError:
            pass
        else:
            data = normalize_json(data, root)
            if path.name == "experiment_results.json" and isinstance(data, list):
                # Rows are appended in completion order, which depends on
                # thread scheduling when --max-workers > 1.
                data.sort(key=lambda row: str(row.get("key")))
            return json.dumps(data, indent=1, sort_keys=True)
    text = normalize_text(text, root)
    return _STARTED_ROW.sub("| Started | <TIME> |", text)


def normalize_result(result: CommandResult, root: Path) -> dict:
    # Lines are sorted because worker threads interleave with the main thread.
    return {
        "argv": list(result.argv),
        "returncode": result.returncode,
        "stdout": _normalize_lines(result.stdout, root),
        "stderr": _normalize_lines(result.stderr, root),
    }


def _normalize_lines(text: str, root: Path) -> list[str]:
    text = _GLUED_PROGRESS.sub("\n", normalize_text(text, root))
    return sorted(line.rstrip() for line in text.splitlines() if line.strip())


SNAPSHOT_DIRS = ("results", "ICLR_results", "logs")


def snapshot(sandbox: Sandbox) -> dict[str, str]:
    """Every file the runner wrote, keyed by normalized relative path."""
    files: dict[str, str] = {}
    for top in SNAPSHOT_DIRS:
        base = sandbox.root / top
        if not base.exists():
            continue
        for path in sorted(p for p in base.rglob("*") if p.is_file()):
            key = normalize_text(str(path.relative_to(sandbox.root)), sandbox.root)
            files[key] = normalize_file(path, sandbox.root)
    return files


# ── Comparison ──────────────────────────────────────────────────────────────────


def describe_differences(reference: dict, current: dict, *, max_diff_lines: int = 80) -> str:
    """Human-readable report of where ``current`` deviates from ``reference``; empty if none."""
    lines: list[str] = []

    for index, (ref_cmd, cur_cmd) in enumerate(
        zip_longest(reference["commands"], current["commands"]), start=1
    ):
        if ref_cmd is None or cur_cmd is None:
            lines.append(f"command #{index}: present on one side only")
            continue
        for key in ("argv", "returncode", "stdout", "stderr"):
            if ref_cmd[key] != cur_cmd[key]:
                lines.append(f"command #{index} ({' '.join(ref_cmd['argv'])}): {key} differs")
                lines.extend(_diff(ref_cmd[key], cur_cmd[key], max_diff_lines))

    ref_files, cur_files = reference["files"], current["files"]
    for path in sorted(set(ref_files) - set(cur_files)):
        lines.append(f"only written by reference: {path}")
    for path in sorted(set(cur_files) - set(ref_files)):
        lines.append(f"only written by current: {path}")
    for path in sorted(set(ref_files) & set(cur_files)):
        if ref_files[path] != cur_files[path]:
            lines.append(f"content differs: {path}")
            lines.extend(_diff(ref_files[path], cur_files[path], max_diff_lines))
    return "\n".join(lines)


def _diff(reference, current, max_lines: int) -> list[str]:
    ref_lines = reference.splitlines() if isinstance(reference, str) else [str(x) for x in reference]
    cur_lines = current.splitlines() if isinstance(current, str) else [str(x) for x in current]
    diff = list(
        difflib.unified_diff(ref_lines, cur_lines, "reference", "current", lineterm="", n=2)
    )
    if len(diff) > max_lines:
        diff = diff[:max_lines] + [f"... ({len(diff) - max_lines} more diff lines)"]
    return ["    " + line for line in diff]
