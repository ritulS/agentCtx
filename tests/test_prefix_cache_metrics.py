"""Cache measurements, compression alignment and CSV export without inference."""
import csv
import io
import json
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

import pytest

from agentctx.compression.cache_metrics import cache_usage, compression_cache_comparisons

ROOT = Path(__file__).resolve().parents[1]


def call(step, prompt=1000, cached=900, completion=50, **kwargs):
    usage = {"prompt_tokens": prompt, "prompt_tokens_details": {"cached_tokens": cached}}
    return {"step": step, "status": "ok", "prompt_tokens": prompt, "completion_tokens": completion,
            **cache_usage(usage), **kwargs}


@pytest.mark.parametrize("cached,status", [(None, "unavailable"), (0, "available"),
    (-1, "invalid"), (101, "invalid"), (True, "invalid"), (1.5, "invalid"), ("10", "invalid")])
def test_absent_zero_and_invalid_counts_are_distinct(cached, status):
    result = cache_usage({"prompt_tokens": 100, "prompt_tokens_details": {"cached_tokens": cached}})
    assert result["cache_usage_status"] == status
    assert result["cached_tokens"] == (0 if status == "available" else None)


def test_missing_details_and_zero_denominator():
    for details in (None, {}, [], "unknown"):
        assert cache_usage({"prompt_tokens_details": details})["cached_tokens"] is None
    assert cache_usage({"prompt_tokens": 0, "prompt_tokens_details": {"cached_tokens": 0}})["cache_hit_rate"] is None


def test_comparison_signs_and_grouping():
    log = {"compression_event_steps": [1], "online_trc_flags": [{"step": 1}],
           "model_call_records": [call(1), call(2, 500, 100)]}
    row, = compression_cache_comparisons(log)
    assert (row["before_step"], row["after_step"]) == (1, 2)
    assert row["compression_kinds"] == ["budget", "online_trc"]
    assert row["compression_count"] == 2
    assert row["cached_tokens_drop"] == 800
    assert row["cache_hit_rate_drop_pp"] == pytest.approx(70)
    assert row["uncached_prompt_tokens_increase"] == 300
    assert row["before_completion_tokens"] == 50
    assert row["before_processed_tokens"] == 1050   # prompt + completion of call 1
    assert row["reuse_ratio_vs_before_processed"] == pytest.approx(100 / 1050)
    log["model_call_records"] = [call(1, 500, 100), call(2)]
    assert compression_cache_comparisons(log)[0]["cached_tokens_drop"] == -800


def test_reuse_ratio_needs_a_completed_before_call_with_valid_counts():
    log = {"compression_event_steps": [1],
           "model_call_records": [call(1, completion=None), call(2, 500, 100)]}
    row, = compression_cache_comparisons(log)
    assert row["status"] == "available"
    assert row["before_processed_tokens"] is None
    assert row["reuse_ratio_vs_before_processed"] is None
    log["model_call_records"][0] = call(1, prompt=0, cached=0, completion=0)
    row, = compression_cache_comparisons(log)
    assert row["before_processed_tokens"] == 0
    assert row["reuse_ratio_vs_before_processed"] is None
    # A rejected completion never enters the history, so a failed call is no baseline
    # even though its usage is valid.
    log["model_call_records"][0] = call(1, status="format_error")
    row, = compression_cache_comparisons(log)
    assert row["status"] == "available" and row["cached_tokens_drop"] == 800
    assert row["before_processed_tokens"] is None
    assert row["reuse_ratio_vs_before_processed"] is None


def test_reuse_ratio_may_exceed_one():
    # Hits can come from other requests' blocks; the ratio is not capped.
    log = {"compression_event_steps": [1],
           "model_call_records": [call(1, 100, 50, completion=10), call(2, 500, 400)]}
    row, = compression_cache_comparisons(log)
    assert row["reuse_ratio_vs_before_processed"] == pytest.approx(400 / 110)


@pytest.mark.parametrize("primitive,kinds", [("truncation", ["budget"]),
    ("online_trc", ["budget", "online_trc"])])
def test_real_agent_hooks_persist_comparison(tmp_path, primitive, kinds):
    # Same DefaultAgent hook is used by both SWE-Bench and Harbor.
    sys.path.insert(0, str(ROOT))
    import memory
    from minisweagent.agents.default import DefaultAgent
    from test_truncation import history

    class Model:
        calls = 0

        def query(self, messages):
            self.calls += 1
            if self.calls == 2:
                pending = json.loads(log_path.read_text())["compression_cache_comparisons"]
                assert pending[0]["status"] == "missing_after_call"
            return {"role": "assistant", "content": "command", "extra": {"response": {"usage": {
                "prompt_tokens": 1000 if self.calls == 1 else 500,
                "completion_tokens": 10,
                "prompt_tokens_details": {"cached_tokens": 900 if self.calls == 1 else 100},
            }}}}

    log_path = tmp_path / "token_log.json"
    with patch.dict(os.environ, {"MSWEA_TOKEN_LOG_PATH": str(log_path)}, clear=True):
        model = Model()
        agent = DefaultAgent(model, object(), cost_limit=0, system_template="system", instance_template="task")
        agent.add_messages(*history(10))
        agent.query()
        os.environ.update(MSWEA_PRIMITIVE=primitive, MSWEA_TOKEN_BUDGET="100")
        agent.query()
        log = json.loads(log_path.read_text())
        assert log == memory.token_log_dict(agent)
    assert model.calls == 2
    assert [r["cached_tokens"] for r in log["model_call_records"]] == [900, 100]
    assert [r["cache_hit_rate"] for r in log["model_call_records"]] == [0.9, 0.2]
    assert [r["uncached_prompt_tokens"] for r in log["model_call_records"]] == [100, 400]
    row, = log["compression_cache_comparisons"]
    assert row["compression_kinds"] == kinds
    assert row["after_step"] == 2
    assert row["cached_tokens_drop"] == 800
    assert row["before_processed_tokens"] == 1010
    assert row["reuse_ratio_vs_before_processed"] == pytest.approx(100 / 1010)


def test_cli_exports_old_unknowns_skips_truncated_and_deduplicates_paths(tmp_path):
    known, old, broken = tmp_path / "known", tmp_path / "old", tmp_path / "broken"
    for d in (known, old, broken):
        d.mkdir()
    (known / "token_log.json").write_text(json.dumps({"compression_event_steps": [1],
        "model_call_records": [call(1), call(2, 500, 100)]}))
    (old / "token_log.json").write_text(json.dumps({"compression_event_steps": [1],
        "model_call_records": [{"step": 1}, {"step": 2}]}))
    (broken / "token_log.json").write_text('{"compression_event_steps": [1], "model_call_')  # killed mid-write
    result = subprocess.run([sys.executable, str(ROOT / "analysis/compare_compression_cache.py"),
        str(tmp_path), str(known)], capture_output=True, text=True, check=True)
    rows = list(csv.DictReader(io.StringIO(result.stdout)))
    assert len(rows) == 2
    assert rows[0]["cached_tokens_drop"] == "800"
    assert rows[0]["reuse_ratio_vs_before_processed"] == str(100 / 1050)
    assert rows[1]["cached_tokens_drop"] == ""
    assert rows[1]["status"] == "missing_cache_usage"
    assert "skipping unreadable token log" in result.stderr and "broken" in result.stderr
    assert "3 logs (1 skipped)" in result.stderr
    assert "1 with comparable cache counts" in result.stderr


def test_litellm_format_error_retains_cache_and_transport_error_is_unknown(tmp_path):
    from litellm import ModelResponse
    from minisweagent.agents.default import DefaultAgent
    from minisweagent.exceptions import FormatError
    from minisweagent.models.litellm_textbased_model import LitellmTextbasedModel

    log_path = tmp_path / "token_log.json"
    with patch.dict(os.environ, {"MSWEA_TOKEN_LOG_PATH": str(log_path)}, clear=True):
        model = LitellmTextbasedModel(model_name="hosted_vllm/test", cost_tracking="ignore_errors")
        agent = DefaultAgent(model, object(), cost_limit=0, system_template="system", instance_template="task")
        agent.add_messages({"role": "user", "content": "task"})
        response = ModelResponse(model="test", choices=[{"finish_reason": "length",
            "message": {"role": "assistant", "content": "no command"}}], usage={
                "prompt_tokens": 1000, "completion_tokens": 10, "total_tokens": 1010,
                "prompt_tokens_details": {"cached_tokens": 900}})
        with patch.object(model, "_query", return_value=response), patch.object(
            model, "_calculate_cost", return_value={"cost": 0}
        ):
            with pytest.raises(FormatError):
                agent.query()
        with patch.object(model, "query", side_effect=RuntimeError("transport error")):
            with pytest.raises(RuntimeError):
                agent.query()
    log = json.loads(log_path.read_text())
    records = log["model_call_records"]
    assert [r["cached_tokens"] for r in records] == [900, None]
    assert [r["status"] for r in records] == ["format_error", "error"]
    assert [r["cache_hit_rate"] for r in records] == [0.9, None]
    assert [r["cache_usage_status"] for r in records] == ["available", "unavailable"]


def test_hook_survives_missing_agentctx_collector(tmp_path):
    # mini-swe-agent must still run when agentCtx's src is not on the path.
    import builtins
    from minisweagent.agents.default import DefaultAgent

    class Model:
        def query(self, messages):
            return {"role": "assistant", "content": "command", "extra": {"response": {"usage": {
                "prompt_tokens": 10, "completion_tokens": 1, "prompt_tokens_details": {"cached_tokens": 5}}}}}

    real_import = builtins.__import__

    def blocked(name, *args, **kwargs):
        if name.startswith("agentctx.compression.cache_metrics"):
            raise ImportError(name)
        return real_import(name, *args, **kwargs)

    with patch.dict(os.environ, {}, clear=True), patch.object(builtins, "__import__", blocked):
        agent = DefaultAgent(Model(), object(), cost_limit=0, system_template="system", instance_template="task")
        agent.add_messages({"role": "user", "content": "task"})
        agent.query()
    record, = agent._mem_model_call_records
    assert record["prompt_tokens"] == 10
    assert record["cache_usage_status"] == "collector_unavailable"
    assert "cached_tokens" not in record
