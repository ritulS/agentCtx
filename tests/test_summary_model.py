"""Summary model configuration, lazy initialization, and runner propagation."""

import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from agentctx import summary_config
from agentctx.benchmarks.harbor_results import normalize_trial
from agentctx.benchmarks.swe_bench import SweBench
from agentctx.compression import primitives
from harness import build_sandbox, runner_environment


@pytest.fixture(autouse=True)
def clean_summary_settings(monkeypatch):
    for key in (
        "MSWEA_SUMMARY_MODEL_CONFIG", "MSWEA_SUMMARY_MODEL_NAME", "MSWEA_SUMMARY_API_BASE",
    ):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(primitives, "_SUMMARY_MODEL", None)


def test_default_does_not_create_a_model(monkeypatch):
    factory = Mock()
    monkeypatch.setattr("minisweagent.models.get_model", factory)
    agent = object()
    assert summary_config.summary_model_config() is None
    assert summary_config.summary_model_info() == {"source": "agent_model"}
    assert primitives.get_summary_model(agent) is agent
    factory.assert_not_called()


def test_file_settings_and_environment_precedence(tmp_path, monkeypatch):
    config = tmp_path / "summary.yaml"
    config.write_text("""agent:
  step_limit: 1
model:
  model_name: hosted_vllm/file-model
  model_class: litellm
  model_kwargs:
    api_base: http://localhost:8001/v1
    temperature: 0.3
""")
    monkeypatch.setenv("MSWEA_SUMMARY_MODEL_CONFIG", str(config))
    assert summary_config.summary_model_config() == {
        "model_name": "hosted_vllm/file-model",
        "model_class": "litellm",
        "model_kwargs": {"api_base": "http://localhost:8001/v1", "temperature": 0.3},
        "cost_tracking": "ignore_errors",
    }
    monkeypatch.setenv("MSWEA_SUMMARY_MODEL_NAME", "hosted_vllm/env-model")
    monkeypatch.setenv("MSWEA_SUMMARY_API_BASE", "http://localhost:8002/v1")
    cfg = summary_config.summary_model_config()
    assert cfg["model_name"] == "hosted_vllm/env-model"
    assert cfg["model_kwargs"] == {"api_base": "http://localhost:8002/v1", "temperature": 0.3}
    assert summary_config.summary_model_info() == {
        "source": "override", "config_path": str(config),
        "model_name": "hosted_vllm/env-model", "api_base": "http://localhost:8002/v1",
    }


def test_relative_config_resolves_from_agent_working_directory(tmp_path, monkeypatch):
    (tmp_path / "configs").mkdir()
    (tmp_path / "configs/summary.yaml").write_text("model:\n  model_name: hosted_vllm/summary\n")
    (tmp_path / "mini-swe-agent").mkdir()
    monkeypatch.setattr(summary_config, "WORKSPACE_ROOT", tmp_path)
    monkeypatch.chdir(tmp_path / "mini-swe-agent")
    monkeypatch.setenv("MSWEA_SUMMARY_MODEL_CONFIG", "configs/summary.yaml")
    assert summary_config.summary_model_config()["model_name"] == "hosted_vllm/summary"


def test_invalid_overrides_fail_explicitly(tmp_path, monkeypatch):
    monkeypatch.setenv("MSWEA_SUMMARY_MODEL_CONFIG", str(tmp_path / "missing.yaml"))
    with pytest.raises(FileNotFoundError, match="missing file"):
        summary_config.summary_model_config()
    monkeypatch.delenv("MSWEA_SUMMARY_MODEL_CONFIG")
    monkeypatch.setenv("MSWEA_SUMMARY_API_BASE", "http://localhost:8001/v1")
    with pytest.raises(ValueError, match="no model_name"):
        summary_config.summary_model_config()


def test_override_is_lazy_and_shared_across_threads(monkeypatch):
    monkeypatch.setenv("MSWEA_SUMMARY_MODEL_NAME", "hosted_vllm/summary")
    factory = Mock(return_value=object())
    monkeypatch.setattr("minisweagent.models.get_model", factory)
    for primitive in (primitives.summarize, primitives.structured_summarize):
        primitive([], object(), 200)
    summary_config.summary_model_info()
    factory.assert_not_called()
    with ThreadPoolExecutor(max_workers=8) as pool:
        models = list(pool.map(primitives.get_summary_model, [object()] * 16))
    assert all(model is factory.return_value for model in models)
    factory.assert_called_once_with(config={
        "model_name": "hosted_vllm/summary", "model_class": "litellm_textbased",
        "cost_tracking": "ignore_errors",
    })


@pytest.mark.parametrize("benchmark", ["swe-bench", "terminal-bench"])
@pytest.mark.parametrize("use_iclr", [False, True])
def test_cli_summary_config_reaches_workers_and_metadata(tmp_path, working_tree, benchmark, use_iclr):
    sandbox = build_sandbox(tmp_path, working_tree)
    script = "run_experiment_iclr.py" if use_iclr else "run_experiment.py"
    args = [script, "--benchmark", benchmark, "--conditions", "summarization",
            "--summary-config", "configs/config-alt-agent.yaml", "--n-tasks", "1",
            "--runs-per-task", "1", "--max-workers", "1", "--budget", "10000", "--depth", "0.5"]
    if use_iclr:
        args += ["--iclr-benchmark", benchmark, "--iclr-section", "main",
                 "--iclr-model", "testmodel", "--iclr-cell", "d05__b10k__su-full"]
    result = sandbox.run(args)
    assert result.returncode == 0, result.stdout + result.stderr
    info_paths = list(sandbox.root.rglob("run_info.json"))
    assert len(info_paths) == 1
    info = json.loads(info_paths[0].read_text())
    config_path = str(sandbox.root / "configs/config-alt-agent.yaml")
    assert info["summary_config"] == config_path
    assert info["summary_model"] == "hosted_vllm/test/model-b"
    assert info["model"] == "hosted_vllm/test/model-a"
    assert info["summarization_model"] == {
        "source": "override", "config_path": config_path,
        "model_name": "hosted_vllm/test/model-b", "api_base": "http://localhost:8001/v1",
    }
    invocations = list(sandbox.root.rglob("invocation.json"))
    assert invocations
    for path in invocations:
        assert json.loads(path.read_text())["env"]["MSWEA_SUMMARY_MODEL_CONFIG"] == config_path


def test_runner_environment_only_override(tmp_path, working_tree, monkeypatch):
    sandbox = build_sandbox(tmp_path, working_tree)
    env = runner_environment()
    env.update({"MSWEA_SUMMARY_MODEL_NAME": "hosted_vllm/env-summary",
                "MSWEA_SUMMARY_API_BASE": "http://localhost:8002/v1"})
    monkeypatch.setattr("harness.runner_environment", lambda: env)
    result = sandbox.run(["run_experiment.py", "--n-tasks", "1", "--runs-per-task", "1",
                          "--conditions", "summarization"])
    assert result.returncode == 0, result.stderr
    info = json.loads(next(sandbox.root.rglob("run_info.json")).read_text())
    assert info["summary_config"] is None
    assert info["summary_model"] == "hosted_vllm/env-summary"
    invocation = json.loads(next(sandbox.root.rglob("invocation.json")).read_text())
    assert invocation["env"]["MSWEA_SUMMARY_MODEL_NAME"] == "hosted_vllm/env-summary"
    assert invocation["env"]["MSWEA_SUMMARY_API_BASE"] == "http://localhost:8002/v1"


def test_cli_missing_summary_config_stops_before_launch(tmp_path, working_tree):
    sandbox = build_sandbox(tmp_path, working_tree)
    result = sandbox.run(["run_experiment.py", "--summary-config", "missing.yaml"])
    assert result.returncode != 0
    assert "--summary-config not found:" in result.stderr
    assert not list(sandbox.root.rglob("invocation.json"))


def test_summary_provenance_survives_token_log_and_both_result_adapters(tmp_path, monkeypatch):
    monkeypatch.setenv("MSWEA_SUMMARY_MODEL_NAME", "hosted_vllm/summary")
    # DefaultAgent initializes the real compression counters without making a model call.
    from minisweagent.agents.default import DefaultAgent

    agent = DefaultAgent(Mock(), Mock(), system_template="System", instance_template="{{task}}")
    token_log = primitives.token_log_dict(agent)
    expected = {"source": "override", "config_path": None,
                "model_name": "hosted_vllm/summary", "api_base": None}
    assert token_log["summarization_model"] == expected

    def launch(command, *, env, **kwargs):
        Path(env["MSWEA_TOKEN_LOG_PATH"]).write_text(json.dumps(token_log))
        return SimpleNamespace(wait=lambda **kwargs: None, returncode=0)

    monkeypatch.setattr("agentctx.benchmarks.swe_bench.subprocess.Popen", launch)
    benchmark = SweBench(workspace_root=tmp_path, model_tag="agent", results_dir=tmp_path / "swe")
    row = benchmark._run_agent(
        instance_id="test", condition="summarization", primitive="summarization",
        budget=10000, run_num=1, agent_config=tmp_path / "agent.yaml", step_limit=10, agent_timeout=10,
    )
    assert row["summarization_model"] == expected

    trial = tmp_path / "trial"
    (trial / "agent").mkdir(parents=True)
    (trial / "result.json").write_text(json.dumps({"task_name": "test"}))
    (trial / "agent/token_log.json").write_text(json.dumps(token_log))
    row = normalize_trial(trial, tmp_path / "tb", "agent", 1,
                          condition={"condition": "summarization", "primitive": "summarization",
                                     "budget": 10000}, compression_ratio=0.5)
    assert row["summarization_model"] == expected
