"""The reorganized runners must behave exactly like the reference branch.

``scripts/run_experiment.py``, ``scripts/run_experiment_iclr.py`` and the FC
calibration launchers from the working tree are run side by side with the same
scripts taken from each reference branch (see ``conftest.REFERENCE_BRANCHES``),
inside sandboxes that differ only in the code under test. Every command line in
a scenario must exit with the same status, print the same lines, and leave the
same files under ``results/``, ``ICLR_results/`` and ``logs/``, including the
exact agent/Harbor invocation captured by the fakes.

Scenarios that need a capability a reference branch predates (Terminal-Bench,
``--summary-config``, verdict handling, the calibration launchers) are skipped
for that branch.
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
CAL_TB = "run_budget_calibration_tb.py"
CAL_SB = "run_budget_calibration_sb.py"
TB = frozenset({"terminal-bench"})
TB_VERDICTS = TB | {"tb-verdicts"}
SUMMARY = frozenset({"summary-config"})
SECTIONS = frozenset({"iclr-sections"})
TB_CALIBRATION = TB_VERDICTS | {"tb-calibration"}
SB_CALIBRATION = frozenset({"sb-calibration"})
INF = "999999999"


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
        # run_info.json must survive an evaluation-only pass unchanged.
        [RUN, "--ablation", "eq-eval", "--n-tasks", "3",
         "--conditions", "truncation", "full-context", "--eval-only",
         "--agent-config", "configs/config-alt-agent.yaml"],
    ),
    scenario(
        # Explicit task file + ablation: only this launch's tasks are evaluated,
        # rows of the larger historical cohort are preserved untouched.
        "swe-ablation-tasks-file-selective-eval",
        [RUN, "--ablation", "eq-sel", "--conditions", "truncation",
         "--runs-per-task", "1", "--max-workers", "1"],
        [RUN, "--ablation", "eq-sel", "--tasks-file", "task_lists/custom_tasks.json",
         "--conditions", "truncation", "--runs-per-task", "1", "--max-workers", "1",
         "--with-eval"],
        [RUN, "--ablation", "eq-sel", "--tasks-file", "task_lists/custom_tasks.json",
         "--conditions", "truncation", "--eval-only"],
    ),
    scenario(
        "swe-summary-config",
        [RUN, "--ablation", "eq-sum", "--tasks-file", "task_lists/custom_tasks.json",
         "--conditions", "summarization", "trc-su", "otrc-su-partial",
         "--summary-config", "configs/config-summary-b.yaml",
         "--runs-per-task", "1", "--max-workers", "1"],
        requires=SUMMARY,
    ),
    scenario(
        "swe-summary-config-missing",
        failing([RUN, "--ablation", "eq-sum-missing", "--conditions", "summarization",
                 "--summary-config", "configs/does-not-exist.yaml"]),
        requires=SUMMARY,
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
        "iclr-swe-option-equals-form",
        [ICLR, "--iclr-section", "main", "--iclr-model", "eqmodel",
         "--iclr-cell", "d07__b20k__ss", "--n-tasks", "2",
         "--conditions", "structured-summarize", "--budget=20000", "--depth=0.7",
         "--runs-per-task", "1", "--max-workers", "1"],
        requires=SECTIONS,
    ),
    scenario(
        "iclr-swe-di-binf-fc-default-ablation-tasks",
        [ICLR, "--iclr-section", "ablation", "--iclr-model", "eqmodel",
         "--iclr-cell", "di__binf__fc", "--n-tasks", "2",
         "--conditions", "full-context", "--budget", INF, "--depth", "0.5",
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
        "iclr-swe-model-ablation-summary-config",
        [ICLR, "--iclr-section", "model_ablation", "--iclr-model", "eqmodel-sum-b",
         "--iclr-cell", "d05__b15k__su-full", "--tasks-file", "task_lists/custom_tasks.json",
         "--conditions", "summarization", "--budget", "15000", "--depth", "0.5",
         "--summary-config", "configs/config-summary-b.yaml",
         "--runs-per-task", "1", "--max-workers", "1"],
        # Same cell, different summarizer: refused because the existing rows
        # recorded model-b.
        failing([ICLR, "--iclr-section", "model_ablation", "--iclr-model", "eqmodel-sum-b",
                 "--iclr-cell", "d05__b15k__su-full", "--tasks-file", "task_lists/custom_tasks.json",
                 "--conditions", "summarization", "--budget", "15000", "--depth", "0.5",
                 "--summary-config=configs/config-summary-c.yaml",
                 "--runs-per-task", "1", "--max-workers", "1"]),
        requires=SECTIONS | SUMMARY,
    ),
    scenario(
        "iclr-swe-main-rejects-summary-config",
        failing([ICLR, "--iclr-section", "main", "--iclr-model", "eqmodel",
                 "--iclr-cell", "d05__b15k__su-full", "--conditions", "summarization",
                 "--budget", "15000", "--depth", "0.5",
                 "--summary-config", "configs/config-summary-b.yaml"]),
        requires=SECTIONS | SUMMARY,
    ),
    scenario(
        "iclr-swe-model-ablation-requires-summary-config",
        failing([ICLR, "--iclr-section", "model_ablation", "--iclr-model", "eqmodel-sum-b",
                 "--iclr-cell", "d05__b15k__su-full", "--conditions", "summarization",
                 "--budget", "15000", "--depth", "0.5"]),
        requires=SECTIONS | SUMMARY,
    ),
    scenario(
        "iclr-swe-prefix-cache-ablation-section",
        [ICLR, "--iclr-section", "prefix_cache_ablation", "--iclr-model", "eqmodel-prefixcache",
         "--iclr-cell", "di__b15k__trc", "--n-tasks", "2",
         "--conditions", "tool-result-clear", "--budget", "15000", "--depth", "0.5",
         "--runs-per-task", "1", "--max-workers", "1"],
        requires=SECTIONS,
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
        # The dataset holds a retryable failure (-envfail): it is re-run up to
        # TB_MAX_BATCH_ATTEMPTS times with the earlier attempts kept aside.
        "tb-all-dataset-tasks",
        [RUN, "--benchmark", "terminal-bench", "--model-tag", "tbmodel",
         "--conditions", "truncation", "full-context", "online-trc",
         "--runs-per-task", "1", "--max-workers", "2"],
        requires=TB_VERDICTS,
    ),
    scenario(
        "tb-tasks-file-resume",
        [RUN, "--benchmark", "terminal-bench", "--model-tag", "tbmodel2",
         "--tasks-file", "task_lists/tb_tasks.json", "--conditions", "tool-result-clear",
         "--budget", "20000", "--depth", "0.7", "--runs-per-task", "1", "--max-workers", "1"],
        [RUN, "--benchmark", "terminal-bench", "--model-tag", "tbmodel2",
         "--tasks-file", "task_lists/tb_tasks.json", "--conditions", "tool-result-clear",
         "--budget", "20000", "--depth", "0.7", "--runs-per-task", "2", "--max-workers", "1"],
        # --eval-only only reports rows without a verdict.
        [RUN, "--benchmark", "terminal-bench", "--model-tag", "tbmodel2",
         "--tasks-file", "task_lists/tb_tasks.json", "--conditions", "tool-result-clear",
         "--budget", "20000", "--depth", "0.7", "--runs-per-task", "2", "--eval-only"],
        requires=TB_VERDICTS,
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
        "tb-summary-config",
        [RUN, "--benchmark", "terminal-bench", "--model-tag", "tbmodel-sum", "--n-tasks", "2",
         "--conditions", "summarization-partial",
         "--summary-config", "configs/config-summary-b.yaml",
         "--runs-per-task", "1", "--max-workers", "1"],
        requires=TB | SUMMARY,
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
    # ── FC calibration launchers ──────────────────────────────────────────────
    scenario(
        "calibration-tb-fc-run1-then-subset-run2",
        [CAL_TB, "--model-key", "qwen35b", "--agent-config", "configs/config-qwen-vllm.yaml",
         "--expected-tasks", "6", "--n-concurrent", "1", "--skip-postprocess"],
        [CAL_TB, "--model-key", "qwen35b", "--agent-config", "configs/config-qwen-vllm.yaml",
         "--expected-tasks", "6", "--n-concurrent", "1", "--skip-postprocess",
         "--run-num", "2", "--tasks-file", "task_lists/tb_tasks.json",
         "--verifier-timeout-multiplier", "2.0", "--result-scope", "p80_rootless"],
        failing([CAL_TB, "--model-key", "qwen35b", "--agent-config", "configs/config-qwen-vllm.yaml",
                 "--expected-tasks", "6", "--n-concurrent", "1", "--skip-postprocess",
                 "--task-name", "no-such-task"]),
        requires=TB_CALIBRATION,
    ),
    scenario(
        "calibration-sb-fc-run1",
        [CAL_SB, "--model-key", "qwen35b", "--agent-config", "configs/config-qwen-vllm.yaml",
         "--tasks-file", "task_lists/custom_tasks.json", "--max-workers", "1",
         "--skip-postprocess"],
        requires=SB_CALIBRATION,
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
    assert all(row["summarization_model"] == {"source": "agent_model"} for row in rows if row["returncode"] == 0)
    info = json.loads((sandbox.root / "results/ablations/eq-resume/run_info.json").read_text())
    assert info["summarization_model"] == {"source": "agent_model"} and info["summary_config"] is None


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
    # The --eval-only pass (with a different --agent-config) must not rewrite run_info.
    info = json.loads((sandbox.root / "results/ablations/eq-eval/run_info.json").read_text())
    assert info["agent_config"].endswith("config-qwen-vllm.yaml")


def test_swe_selective_eval_covers_harness_verdicts(working_tree: Tree, tmp_path):
    sandbox = build_sandbox(tmp_path, working_tree)
    execute(sandbox, _scenario("swe-ablation-tasks-file-selective-eval"))
    rows = {row["instance_id"]: row for row in _rows(sandbox.root, "results/ablations/eq-sel/experiment_results.json")}

    assert len(rows) == 4 + 5  # default ablation tasks + custom tasks
    # Only the custom tasks were evaluated; the historical rows keep resolved=null.
    assert all(rows[iid]["resolved"] is None for iid in ("django__django-10001", "scikit-learn__scikit-learn-30001"))
    assert rows["django__django-10004-applyfail"]["resolved"] is False   # patch did not apply
    assert rows["sympy__sympy-20004-evalerr"]["resolved"] is None        # harness error, no verdict
    assert isinstance(rows["django__django-10003"]["resolved"], bool)
    assert isinstance(rows["sympy__sympy-20002"]["resolved"], bool)


def test_swe_summary_config_reaches_agents_and_metadata(working_tree: Tree, tmp_path):
    sandbox = build_sandbox(tmp_path, working_tree)
    execute(sandbox, _scenario("swe-summary-config"))
    rows = _rows(sandbox.root, "results/ablations/eq-sum/experiment_results.json")
    config = str(sandbox.root / "configs" / "config-summary-b.yaml")

    submitted = [row for row in rows if row["returncode"] == 0]
    assert submitted and all(row["summarization_model"]["config_path"] == config for row in submitted)
    invocation = json.loads(
        (sandbox.root / "results/ablations/eq-sum/django__django-10003/summarization/run_1/invocation.json").read_text()
    )
    assert invocation["env"]["MSWEA_SUMMARY_MODEL_CONFIG"] == config
    info = json.loads((sandbox.root / "results/ablations/eq-sum/run_info.json").read_text())
    assert info["summary_config"] == config
    assert info["summarization_model"]["source"] == "override"


def test_tb_scenario_exercises_harbor_outcomes(working_tree: Tree, tmp_path):
    if not TB_VERDICTS <= working_tree.features:
        pytest.skip("working tree has no Terminal-Bench verdict handling")
    sandbox = build_sandbox(tmp_path, working_tree)
    execute(sandbox, _scenario("tb-all-dataset-tasks"))
    rows = _rows(sandbox.root, "results/tbmodel/experiment_results.json")

    assert len(rows) == 6 * 3
    assert {row["resolved"] for row in rows} == {True, False, None}
    assert {row["verdict_source"] for row in rows} == {"verifier", "verifier_reward_file", "none"}
    assert {row["exit_status"] for row in rows} == {"Submitted", "AgentTimeoutError", "missing_exit_info"}
    assert {row["is_baseline"] for row in rows} == {True, False}
    by_task = {}
    for row in rows:
        by_task.setdefault(row["instance_id"], []).append(row)
    recovered = by_task["zeta-task-vtimeout"]
    assert all(row["resolved"] is True and row["harbor_exception"] == "VerifierTimeoutError" for row in recovered)
    assert all("reward_file" in row for row in recovered)
    retried = by_task["epsilon-task-envfail"]
    assert all(row["attempts"] == 3 and len(row["previous_attempts"]) == 2 for row in retried)
    assert all(row["superseded_dir"] == "run_1.superseded.2" for row in retried)
    assert (sandbox.root / "results/tbmodel/epsilon-task-envfail/truncation/run_1.superseded.1").is_dir()
    not_retried = by_task["gamma-task-timeout"]
    assert all(row["attempts"] == 1 and row["resolved"] is None for row in not_retried)
    copied = sandbox.root / "results/tbmodel/alpha-task/truncation/run_1"
    assert {p.name for p in copied.iterdir()} >= {
        "trajectory.json", "token_log.json", "exit_info.json", "agent.log", "harbor_result.json",
    }
    jobs = sorted(p.name for p in (sandbox.root / "logs/harbor_jobs/terminalbench/tbmodel").iterdir())
    assert sum(name.endswith("-a2") for name in jobs) == 3 and sum(name.endswith("-a3") for name in jobs) == 3


def test_tb_calibration_writes_canonical_cell(working_tree: Tree, tmp_path):
    if not TB_CALIBRATION <= working_tree.features:
        pytest.skip("working tree has no Terminal-Bench calibration launcher")
    sandbox = build_sandbox(tmp_path, working_tree)
    execute(sandbox, _scenario("calibration-tb-fc-run1-then-subset-run2"))
    cell = sandbox.root / "ICLR_results/terminalbench/main/qwen35b/di__binf__fc"
    rows = _rows(sandbox.root, "ICLR_results/terminalbench/main/qwen35b/di__binf__fc/experiment_results.json")

    assert len(rows) == 6 and {row["run_num"] for row in rows} == {1}
    assert all(row["condition"] == "full-context" and row["is_baseline"] for row in rows)
    assert all(row["key"] == f"{row['instance_id']}__full-context__r1" for row in rows)
    assert {row["resolved"] for row in rows} == {True, False, None}
    assert all(row["verifier_timeout_multiplier"] == 1.0 for row in rows)
    manifest = json.loads((cell / "ICLR_CELL_MANIFEST.json").read_text())
    assert manifest["complete"] and manifest["completed_tasks"] == 6
    subset = _rows(sandbox.root, "ICLR_results/terminalbench/main/p80_rootless/qwen35b/di__binf__fc/experiment_results.json")
    assert sorted(row["instance_id"] for row in subset) == sorted(TB_TASK_LIST_TASKS)
    assert all(row["run_num"] == 2 and row["verifier_timeout_multiplier"] == 2.0 for row in subset)


TB_TASK_LIST_TASKS = ["alpha-task", "beta-task-fail", "zeta-task-vtimeout"]


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


def test_current_calibration_invocation_targets_agentctx_package(working_tree: Tree, tmp_path):
    if not TB_CALIBRATION <= working_tree.features:
        pytest.skip("working tree has no Terminal-Bench calibration launcher")
    sandbox = build_sandbox(tmp_path, working_tree)
    execute(sandbox, _scenario("calibration-tb-fc-run1-then-subset-run2"))
    invocations = sorted((sandbox.root / "logs").rglob("invocation.json"))
    assert invocations, "no Harbor invocation was recorded"
    for path in invocations:
        invocation = json.loads(path.read_text())
        argv = invocation["argv"]
        assert argv[argv.index("--agent") + 1] == "agentctx.benchmarks.harbor_adapter:CompressionAgent"
        entries = invocation["env"]["PYTHONPATH"].split(":")
        assert entries[0] == str(sandbox.root / "src")
