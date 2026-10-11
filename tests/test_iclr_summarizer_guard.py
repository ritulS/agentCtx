"""agentctx.experiments.iclr.validate_summarizer: the summarizer is part of a cell's identity.

Run with: uvx --with pyyaml pytest tests/test_iclr_summarizer_guard.py
(or PYTHONPATH=src venv/bin/python -m unittest discover -s tests -v)
"""

import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from agentctx.experiments import iclr  # noqa: E402


class SummarizerGuardTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dest = Path(self.tmp.name) / "d05__b15k__su-full"
        self.dest.mkdir()
        self.cfg_9b = Path(self.tmp.name) / "sum-9b.yaml"
        self.cfg_9b.write_text("model:\n  model_name: hosted_vllm/Qwen/Qwen3.5-9B\n")
        self.cfg_other = Path(self.tmp.name) / "sum-other.yaml"
        self.cfg_other.write_text("model:\n  model_name: hosted_vllm/other\n")
        # The agent's own model with different summarizer settings (thinking off).
        self.agent_cfg = Path(self.tmp.name) / "agent.yaml"
        self.agent_cfg.write_text("model:\n  model_name: hosted_vllm/Qwen/Qwen3.5-35B-A3B\n  model_kwargs: {}\n")
        self.cfg_same_nothink = Path(self.tmp.name) / "sum-35b-nothink.yaml"
        self.cfg_same_nothink.write_text("model:\n  model_name: hosted_vllm/Qwen/Qwen3.5-35B-A3B\n")
        self.cfg_same_short = Path(self.tmp.name) / "sum-35b-short.yaml"
        self.cfg_same_short.write_text("model:\n  model_name: hosted_vllm/Qwen/Qwen3.5-35B-A3B\n")
        self.env = patch.dict(os.environ, {}, clear=False)
        self.env.start()
        os.environ.pop("MSWEA_SUMMARY_MODEL_CONFIG", None)

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def write_rows(self, provenance):
        rows = [dict(instance_id="task0", condition="summarization", budget=15000,
                     compression_ratio=0.5, run_num=1, summarization_model=provenance)]
        (self.dest / "experiment_results.json").write_text(json.dumps(rows))

    def test_section_and_config_must_agree(self):
        with self.assertRaisesRegex(SystemExit, "require a summarizer override"):
            iclr.validate_summarizer("model_ablation", [], self.dest)
        with self.assertRaisesRegex(SystemExit, "override is in effect"):
            iclr.validate_summarizer("main", ["--summary-config", str(self.cfg_9b)], self.dest)
        # The validator exports the option to the environment (as the runner
        # does for its agents); a fresh launch has no such override.
        os.environ.pop("MSWEA_SUMMARY_MODEL_CONFIG", None)
        iclr.validate_summarizer("main", [], self.dest)   # empty cell, self-summarized: ok

    def test_effective_config_is_checked_not_the_argv_spelling(self):
        # Environment override reaches the agents without --summary-config.
        os.environ["MSWEA_SUMMARY_MODEL_CONFIG"] = str(self.cfg_9b)
        with self.assertRaisesRegex(SystemExit, "override is in effect"):
            iclr.validate_summarizer("main", [], self.dest)
        iclr.validate_summarizer("model_ablation", [], self.dest)   # env-driven: ok
        os.environ.pop("MSWEA_SUMMARY_MODEL_CONFIG")
        # --summary-config=x is the same option as --summary-config x.
        with self.assertRaisesRegex(SystemExit, "override is in effect"):
            iclr.validate_summarizer("main", [f"--summary-config={self.cfg_9b}"], self.dest)
        iclr.validate_summarizer("model_ablation", [f"--summary-config={self.cfg_9b}"], self.dest)
        self.assertEqual(iclr.option_value(["--budget=15000"], "--budget"), "15000")
        self.assertEqual(iclr.option_value(["--budget", "15000"], "--budget"), "15000")

    def test_existing_runs_pin_the_summarizer(self):
        self.write_rows({"source": "override", "model_name": "hosted_vllm/Qwen/Qwen3.5-9B"})
        iclr.validate_summarizer("model_ablation", ["--summary-config", str(self.cfg_9b)], self.dest)
        with self.assertRaisesRegex(SystemExit, "recorded summarizer"):
            iclr.validate_summarizer("model_ablation", ["--summary-config", str(self.cfg_other)], self.dest)

    def test_self_summarized_cell_rejects_override_history(self):
        # A cell whose runs recorded an override cannot be continued self-summarized.
        self.write_rows({"source": "override", "model_name": "hosted_vllm/Qwen/Qwen3.5-9B"})
        with self.assertRaisesRegex(SystemExit, "recorded summarizer"):
            iclr.validate_summarizer("main", [], self.dest)
        # Runs without a record (older data) do not constrain the launch.
        self.write_rows(None)
        iclr.validate_summarizer("main", [], self.dest)

    def test_same_model_override_is_admitted_in_self_summarized_sections(self):
        agent = ["--agent-config", str(self.agent_cfg)]
        # Same model as the agent, settings only: admitted in main (and in r2 sections).
        iclr.validate_summarizer("main", [*agent, "--summary-config", str(self.cfg_same_nothink)], self.dest)
        iclr.validate_summarizer("p100_su_free_majority", [*agent, f"--summary-config={self.cfg_same_nothink}"], self.dest)
        # A different model is still refused outside model_ablation.
        with self.assertRaisesRegex(SystemExit, "override is in effect"):
            iclr.validate_summarizer("main", [*agent, "--summary-config", str(self.cfg_9b)], self.dest)
        # Without --agent-config the agent's model is unknown: refused as before.
        with self.assertRaisesRegex(SystemExit, "override is in effect"):
            iclr.validate_summarizer("main", ["--summary-config", str(self.cfg_same_nothink)], self.dest)
        # An agent config without a model name cannot vouch for the override either.
        bare = Path(self.tmp.name) / "bare.yaml"
        bare.write_text("agent:\n  step_limit: 3\n")
        with self.assertRaisesRegex(SystemExit, "override is in effect"):
            iclr.validate_summarizer("main", ["--agent-config", str(bare), "--summary-config", str(self.cfg_same_nothink)], self.dest)

    def test_same_model_override_pins_the_cell_to_its_config(self):
        agent = ["--agent-config", str(self.agent_cfg)]
        same = {"source": "override", "model_name": "hosted_vllm/Qwen/Qwen3.5-35B-A3B",
                "config_path": str(self.cfg_same_nothink)}
        self.write_rows(same)
        iclr.validate_summarizer("main", [*agent, "--summary-config", str(self.cfg_same_nothink)], self.dest)
        # Same model, other settings file: a different summarizer, refused in this cell.
        with self.assertRaisesRegex(SystemExit, "same-model summarizer config"):
            iclr.validate_summarizer("main", [*agent, "--summary-config", str(self.cfg_same_short)], self.dest)
        # ... and the cell cannot be continued self-summarized (the validator
        # exported the last option to the environment; clear it as a fresh launch would).
        os.environ.pop("MSWEA_SUMMARY_MODEL_CONFIG", None)
        with self.assertRaisesRegex(SystemExit, "recorded summarizer"):
            iclr.validate_summarizer("main", agent, self.dest)
        # Conversely a self-summarized cell cannot take the override.
        self.write_rows({"source": "agent_model"})
        with self.assertRaisesRegex(SystemExit, "recorded summarizer"):
            iclr.validate_summarizer("main", [*agent, "--summary-config", str(self.cfg_same_nothink)], self.dest)


if __name__ == "__main__":
    unittest.main()
