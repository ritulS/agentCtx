"""The refactored runners must behave exactly like the reference branches.

``scripts/run_experiment.py`` and ``scripts/run_experiment_iclr.py`` from the
working tree are run side by side with the same scripts taken from each
reference branch (see ``conftest.REFERENCE_BRANCHES``), inside sandboxes that
differ only in the code under test. Every command line in a scenario must
exit with the same status, print the same lines, and leave the same files
under ``results/``, ``ICLR_results/`` and ``logs/``, including the exact
agent/Harbor invocation captured by the fakes.

Scenarios that need a capability a reference branch predates (Terminal-Bench)
are skipped for that branch.
"""

from __future__ import annotations

import json

import pytest

from harness import (
    INTENTIONAL_PYTHONPATH_ENTRIES,
    Command,
    Scenario,
    Tree,
    build_sandbox,
    describe_differences,
    execute,
)

RUN = "run_experiment.py"
ICLR = "run_experiment_iclr.py"
TB = frozenset({"terminal-bench"})


def scenario(name: str, *commands, requires: frozenset[str] = frozenset()) -> Scenario:
    return Scenario(
        name=name,
        commands=tuple(
            cmd if isinstance(cmd, Command) else Command(tuple(cmd)) for cmd in commands
        ),
        requires=requires,
    )


def failing(argv: list[str], returncode: int = 1) -> Command:
    return Command(tuple(argv), returncode)


SCENARIOS = [
    # ── run_experiment.py, SWE-bench ──────────────────────────────────────────
    scenario(
        "swe-ablation-custom-tasks",
        [RUN, "--ablation", "eq-custom", "--tasks-file", "task_lists/custom_tasks.json",
         "--conditions", "truncation", "full-context", "online-trc",
         "--budget", "10000", "--depth", "0.3", "--runs-per-task", "1",
         "--max-workers", "1", "--model-tag", "eqmodel"],
    ),
    scenario(
        "swe-ablation-default-tasks-resume",
        [RUN, "--ablation", "eq-resume", "--conditions", "summarization-partial",
         "--runs-per-task", "1", "--max-workers", "1"],
        # Second launch adds only run 2 for the first three tasks.
        [RUN, "--ablation", "eq-resume", "--conditions", "summarization-partial",
         "--runs-per-task", "2", "--n-tasks", "3", "--max-workers", "2"],
    ),
    scenario(
        "swe-model-tag-balanced-sampling",
        [RUN, "--n-tasks", "4", "--conditions", "tool-result-clear", "trc-ss",
         "--runs-per-task", "1", "--max-workers", "1"],
    ),
    scenario(
        "swe-otrc-and-agent-config-overrides",
        [RUN, "--ablation", "eq-otrc", "--n-tasks", "2",
         "--conditions", "otrc-tr", "otrc-su-partial", "online-trc", "truncation",
         "--otrc-config", "configs/config-alt-otrc.yaml",
         "--agent-config", "configs/config-alt-agent.yaml",
         "--runs-per-task", "1", "--max-workers", "1"],
    ),
    scenario(
        "swe-all-conditions",
        [RUN, "--ablation", "eq-all", "--n-tasks", "2", "--runs-per-task", "1",
         "--max-workers", "4"],
    ),
    scenario(
        "swe-with-eval-then-eval-only",
        [RUN, "--ablation", "eq-eval", "--n-tasks", "3",
         "--conditions", "truncation", "full-context",
         "--runs-per-task", "1", "--max-workers", "1", "--with-eval"],
        [RUN, "--ablation", "eq-eval", "--n-tasks", "3",
         "--conditions", "truncation", "full-context", "--eval-only"],
    ),
    scenario(
        "swe-eval-only-without-results",
        failing([RUN, "--ablation", "eq-empty", "--conditions", "truncation", "--eval-only"]),
    ),
    scenario(
        "swe-unknown-condition",
        failing([RUN, "--ablation", "eq-bad", "--conditions", "truncation", "nope", "bogus"]),
    ),
    # ── run_experiment_iclr.py, SWE-bench ─────────────────────────────────────
    scenario(
        "iclr-swe-d03-b10k-tr",
        [ICLR, "--iclr-section", "main", "--iclr-model", "eqmodel",
         "--iclr-cell", "d03__b10k__tr", "--tasks-file", "task_lists/custom_tasks.json",
         "--conditions", "truncation", "--budget", "10000", "--depth", "0.3",
         "--runs-per-task", "1", "--max-workers", "1"],
    ),
    scenario(
        "iclr-swe-di-binf-fc-default-ablation-tasks",
        [ICLR, "--iclr-section", "ablation", "--iclr-model", "eqmodel",
         "--iclr-cell", "di__binf__fc", "--n-tasks", "2",
         "--conditions", "full-context", "--budget", "999999999", "--depth", "0.5",
         "--runs-per-task", "1", "--max-workers", "1"],
    ),
    scenario(
        "iclr-swe-explicit-ablation-passthrough",
        [ICLR, "--iclr-section", "main", "--iclr-model", "eqmodel",
         "--iclr-cell", "di__b15k__trc-su", "--ablation", "my-abl", "--n-tasks", "2",
         "--conditions", "trc-su", "--budget", "15000", "--depth", "0.5",
         "--runs-per-task", "1", "--max-workers", "1"],
    ),
    scenario(
        "iclr-swe-symbolic-budget-conflict",
        [ICLR, "--iclr-section", "main", "--iclr-model", "glm",
         "--iclr-cell", "di__bA__trc", "--n-tasks", "2",
         "--conditions", "tool-result-clear", "--budget", "12000", "--depth", "0.5",
         "--runs-per-task", "1", "--max-workers", "1"],
        failing([ICLR, "--iclr-section", "main", "--iclr-model", "glm",
                 "--iclr-cell", "di__bA__trc", "--n-tasks", "2",
                 "--conditions", "tool-result-clear", "--budget", "13000", "--depth", "0.5",
                 "--runs-per-task", "1", "--max-workers", "1"]),
    ),
    scenario(
        "iclr-swe-primitive-mismatch",
        failing([ICLR, "--iclr-section", "main", "--iclr-model", "eqmodel",
                 "--iclr-cell", "d05__b10k__tr", "--conditions", "summarization",
                 "--budget", "10000", "--depth", "0.5"]),
    ),
    scenario(
        "iclr-swe-depth-mismatch",
        failing([ICLR, "--iclr-section", "main", "--iclr-model", "eqmodel",
                 "--iclr-cell", "d03__b10k__tr", "--conditions", "truncation",
                 "--budget", "10000", "--depth", "0.5"]),
    ),
    scenario(
        "iclr-swe-bad-cell-grammar",
        failing([ICLR, "--iclr-section", "main", "--iclr-model", "eqmodel",
                 "--iclr-cell", "d05-b10k-tr", "--conditions", "truncation",
                 "--budget", "10000", "--depth", "0.5"]),
    ),
    scenario(
        "iclr-swe-missing-conditions",
        failing([ICLR, "--iclr-section", "main", "--iclr-model", "eqmodel",
                 "--iclr-cell", "d05__b10k__tr", "--budget", "10000", "--depth", "0.5"]),
    ),
    scenario(
        "iclr-swe-bad-model-name",
        failing([ICLR, "--iclr-section", "main", "--iclr-model", "Qwen_35B",
                 "--iclr-cell", "d05__b10k__tr", "--conditions", "truncation",
                 "--budget", "10000", "--depth", "0.5"]),
    ),
    # ── run_experiment.py, Terminal-Bench ─────────────────────────────────────
    scenario(
        "tb-all-dataset-tasks",
        [RUN, "--benchmark", "terminal-bench", "--model-tag", "tbmodel",
         "--conditions", "truncation", "full-context", "online-trc",
         "--runs-per-task", "1", "--max-workers", "2"],
        requires=TB,
    ),
    scenario(
        "tb-tasks-file-resume",
        [RUN, "--benchmark", "terminal-bench", "--model-tag", "tbmodel2",
         "--tasks-file", "task_lists/tb_tasks.json", "--conditions", "tool-result-clear",
         "--budget", "20000", "--depth", "0.7", "--runs-per-task", "1", "--max-workers", "1"],
        [RUN, "--benchmark", "terminal-bench", "--model-tag", "tbmodel2",
         "--tasks-file", "task_lists/tb_tasks.json", "--conditions", "tool-result-clear",
         "--budget", "20000", "--depth", "0.7", "--runs-per-task", "2", "--max-workers", "1"],
        requires=TB,
    ),
    scenario(
        "tb-n-tasks-with-config-overrides",
        [RUN, "--benchmark", "terminal-bench", "--model-tag", "tbmodel3", "--n-tasks", "2",
         "--conditions", "otrc-ss-partial", "summarization",
         "--otrc-config", "configs/config-alt-otrc.yaml",
         "--agent-config", "configs/config-alt-agent.yaml",
         "--runs-per-task", "1", "--max-workers", "1"],
        requires=TB,
    ),
    scenario(
        "tb-ablation-rejected",
        failing([RUN, "--benchmark", "terminal-bench", "--ablation", "x",
                 "--conditions", "truncation"]),
        requires=TB,
    ),
    scenario(
        "tb-unknown-task-in-file",
        failing([RUN, "--benchmark", "terminal-bench", "--tasks-file",
                 "task_lists/tb_tasks_bad.json", "--conditions", "truncation"]),
        requires=TB,
    ),
    # ── run_experiment_iclr.py, Terminal-Bench ────────────────────────────────
    scenario(
        "iclr-tb-di-b15k-trc",
        [ICLR, "--iclr-benchmark", "terminal-bench", "--benchmark", "terminal-bench",
         "--iclr-section", "main", "--iclr-model", "tbmodel",
         "--iclr-cell", "di__b15k__trc", "--conditions", "tool-result-clear",
         "--budget", "15000", "--depth", "0.5", "--n-tasks", "2",
         "--runs-per-task", "1", "--max-workers", "1"],
        requires=TB,
    ),
    scenario(
        "iclr-tb-benchmark-mismatch",
        failing([ICLR, "--iclr-benchmark", "terminal-bench",
                 "--iclr-section", "main", "--iclr-model", "tbmodel",
                 "--iclr-cell", "di__b15k__trc", "--conditions", "tool-result-clear",
                 "--budget", "15000", "--depth", "0.5"]),
        requires=TB,
    ),
]
SCENARIO_IDS = [s.name for s in SCENARIOS]


def _scenario(name: str) -> Scenario:
    return next(s for s in SCENARIOS if s.name == name)


@pytest.mark.parametrize("scenario", SCENARIOS, ids=SCENARIO_IDS)
def test_runner_matches_reference(scenario: Scenario, reference_tree: Tree, working_tree: Tree, tmp_path):
    missing = scenario.requires - reference_tree.features
    if missing:
        pytest.skip(f"{reference_tree.label} predates {sorted(missing)}")

    reference = execute(build_sandbox(tmp_path / "reference", reference_tree), scenario)
    current = execute(build_sandbox(tmp_path / "current", working_tree), scenario)

    report = describe_differences(reference, current)
    assert not report, f"working tree deviates from {reference_tree.label}:\n{report}"


# ── Guards against a vacuous comparison ────────────────────────────────────────
#
# The equivalence test would also pass if both sides failed early in the same
# way, so check on the working tree alone that the fakes really drive the
# runner through its interesting paths.


def _rows(sandbox_root, relative: str) -> list[dict]:
    return json.loads((sandbox_root / relative).read_text())


def test_swe_scenarios_exercise_agent_outcomes(working_tree: Tree, tmp_path):
    sandbox = build_sandbox(tmp_path, working_tree)
    execute(sandbox, _scenario("swe-ablation-default-tasks-resume"))
    rows = _rows(sandbox.root, "results/ablations/eq-resume/experiment_results.json")

    assert len(rows) == 4 + 3  # 4 tasks × run 1, then run 2 for the first 3
    assert {row["exit_status"] for row in rows} >= {"Submitted", "LimitsExceeded", ""}
    assert {row["returncode"] for row in rows} == {0, 3}
    assert all(row["compression_events"] > 0 for row in rows if row["returncode"] == 0)
    assert (sandbox.root / "results/ablations/eq-resume/run_info.json").exists()


def test_swe_with_eval_records_resolution(working_tree: Tree, tmp_path):
    sandbox = build_sandbox(tmp_path, working_tree)
    execute(sandbox, _scenario("swe-with-eval-then-eval-only"))
    rows = _rows(sandbox.root, "results/ablations/eq-eval/experiment_results.json")

    assert len(rows) == 3 * 2
    patched = [row for row in rows if row["patch_generated"]]
    assert patched and {row["resolved"] for row in patched} == {True, False}
    # Inherited quirk, identical in every reference branch: evaluate_results()
    # marks no-patch rows resolved=False only after its last save(), so the
    # value persisted to experiment_results.json stays null.
    assert all(row["resolved"] is None for row in rows if not row["patch_generated"])
    reports = sorted(p.name for p in (sandbox.root / "results/ablations/eq-eval/eval").glob("qwen35-a3b.*.json"))
    assert len(reports) == len(patched)
    assert (sandbox.root / "results/ablations/eq-eval/preds").is_dir()


def test_tb_scenario_exercises_harbor_outcomes(working_tree: Tree, tmp_path):
    if "terminal-bench" not in working_tree.features:
        pytest.skip("working tree has no Terminal-Bench adapter")
    sandbox = build_sandbox(tmp_path, working_tree)
    execute(sandbox, _scenario("tb-all-dataset-tasks"))
    rows = _rows(sandbox.root, "results/tbmodel/experiment_results.json")

    assert len(rows) == 4 * 3
    assert {row["resolved"] for row in rows} == {True, False}
    assert {row["exit_status"] for row in rows} == {"Submitted", "AgentTimeoutError"}
    assert {row["is_baseline"] for row in rows} == {True, False}
    copied = sandbox.root / "results/tbmodel/alpha-task/truncation/run_1"
    assert {p.name for p in copied.iterdir()} >= {
        "trajectory.json", "token_log.json", "exit_info.json", "agent.log", "harbor_result.json",
    }


# ── The intentional differences, asserted rather than ignored ──────────────────


def test_current_agent_invocation_targets_agentctx_package(working_tree: Tree, tmp_path):
    """The refactor moved memory.py into src/agentctx; the agent must be told so."""
    sandbox = build_sandbox(tmp_path, working_tree)
    execute(sandbox, _scenario("swe-ablation-custom-tasks"))
    invocation = json.loads(
        (sandbox.root / "results/ablations/eq-custom/django__django-10003/truncation/run_1/invocation.json").read_text()
    )
    entries = invocation["env"]["PYTHONPATH"].split(":")
    expected = [entry.replace("<WS>", str(sandbox.root)) for entry in INTENTIONAL_PYTHONPATH_ENTRIES]
    assert entries[: len(expected)] == expected
    assert str(sandbox.root) in entries  # the repo root is still importable, as before


def test_current_harbor_invocation_targets_agentctx_package(working_tree: Tree, tmp_path):
    if "terminal-bench" not in working_tree.features:
        pytest.skip("working tree has no Terminal-Bench adapter")
    sandbox = build_sandbox(tmp_path, working_tree)
    execute(sandbox, _scenario("tb-n-tasks-with-config-overrides"))
    invocations = sorted((sandbox.root / "logs").rglob("invocation.json"))
    assert invocations, "no Harbor invocation was recorded"
    for path in invocations:
        invocation = json.loads(path.read_text())
        argv = invocation["argv"]
        assert argv[argv.index("--agent") + 1] == "agentctx.benchmarks.harbor_adapter:CompressionAgent"
        entries = invocation["env"]["PYTHONPATH"].split(":")
        assert entries[0] == str(sandbox.root / "src")
