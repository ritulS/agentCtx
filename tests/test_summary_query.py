"""Regression coverage for prose summaries through mini-swe-agent v2 models.

Run with: venv/bin/python -m unittest discover -s tests -v
"""

import os
import unittest
from pathlib import Path
from unittest.mock import patch

from litellm import ModelResponse
from minisweagent.exceptions import FormatError
from minisweagent.models.litellm_textbased_model import LitellmTextbasedModel

import memory


class SummaryQueryTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {}, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)
        self.cache = patch.object(memory, "_SUMMARY_MODEL", None)
        self.cache.start()
        self.addCleanup(self.cache.stop)
        self.agent = LitellmTextbasedModel(
            model_name="hosted_vllm/test-agent", cost_tracking="ignore_errors"
        )
        self.messages = [
            {"role": "system", "content": "Solve the task with bash commands."},
            {"role": "user", "content": "Fix the database routing bug."},
            {"role": "assistant", "content": "Examined management.py. " * 300},
            {"role": "user", "content": "The save call needs using=db. " * 300},
            {"role": "assistant", "content": "Next: apply the fix."},
        ]

    @staticmethod
    def response(content):
        return ModelResponse(
            model="test",
            choices=[{"message": {"role": "assistant", "content": content}}],
            usage={"prompt_tokens": 321, "completion_tokens": 27, "total_tokens": 348},
        )

    def test_all_summary_variants_accept_prose_and_preserve_usage(self):
        variants = (
            memory.summarize,
            memory.structured_summarize,
            memory.summarize_partial,
            memory.structured_summarize_partial,
        )
        for override in (False, True):
            for primitive in variants:
                with self.subTest(override=override, primitive=primitive.__name__):
                    memory._SUMMARY_MODEL = None
                    if override:
                        os.environ["MSWEA_SUMMARY_MODEL_CONFIG"] = str(
                            Path(__file__).resolve().parents[1]
                            / "configs/config-devstral-vllm.yaml"
                        )
                    else:
                        os.environ.pop("MSWEA_SUMMARY_MODEL_CONFIG", None)
                    prose = "The save call in management.py needs using=db."
                    with patch.object(
                        LitellmTextbasedModel, "_query", return_value=self.response(prose)
                    ) as api, patch.object(
                        LitellmTextbasedModel, "_calculate_cost", return_value={"cost": 0.0}
                    ):
                        result, saved, pt, ct, latency = primitive(
                            self.messages, self.agent, 200
                        )
                        api.assert_called_once()
                        self.assertEqual(result[:2], self.messages[:2])
                        self.assertIn(prose, result[2]["content"])
                        self.assertGreater(saved, 0)
                        self.assertEqual((pt, ct), (321, 27))
                        self.assertGreaterEqual(latency, 0)
                        # The shared agent AND cached override must still reject
                        # prose when used for regular agent action queries.
                        for model in (self.agent, memory.get_summary_model(self.agent)):
                            with self.assertRaises(FormatError):
                                model.query(self.messages)

    def test_summary_does_not_extract_commands_embedded_in_history(self):
        prose = "Previously ran:\n```mswea_bash_command\nls\n```"
        with patch.object(
            LitellmTextbasedModel, "_query", return_value=self.response(prose)
        ), patch.object(
            LitellmTextbasedModel, "_calculate_cost", return_value={"cost": 0.0}
        ):
            summary = memory.query_summary(self.agent, self.messages)
            self.assertEqual(summary["extra"]["actions"], [])
            action = self.agent.query(self.messages)
            self.assertEqual(action["extra"]["actions"], [{"command": "ls"}])


if __name__ == "__main__":
    unittest.main()
