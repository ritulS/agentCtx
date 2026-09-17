"""run_experiment_iclr.validate_summarizer: the summarizer is part of a cell's identity.

Run with: PYTHONPATH=. venv/bin/python -m unittest discover -s tests -v
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
sys.path.insert(0, str(ROOT / "scripts"))

import run_experiment_iclr as iclr  # noqa: E402


class SummarizerGuardTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dest = Path(self.tmp.name) / "d05__b15k__su-full"
        self.dest.mkdir()
        self.cfg_9b = Path(self.tmp.name) / "sum-9b.yaml"
        self.cfg_9b.write_text("model:\n  model_name: hosted_vllm/Qwen/Qwen3.5-9B\n")
        self.cfg_other = Path(self.tmp.name) / "sum-other.yaml"
        self.cfg_other.write_text("model:\n  model_name: hosted_vllm/other\n")
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


if __name__ == "__main__":
    unittest.main()
