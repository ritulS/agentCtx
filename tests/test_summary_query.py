"""Regression coverage for prose summaries through mini-swe-agent v2 models.

Run with: PYTHONPATH=src:mini-swe-agent/src python -m unittest discover -s tests -p test_summary_query.py -v
"""

import unittest
from unittest.mock import patch

from litellm import ModelResponse
from minisweagent.exceptions import FormatError
from minisweagent.models.litellm_textbased_model import LitellmTextbasedModel

from agentctx.compression import primitives


class SummaryQueryTests(unittest.TestCase):
    def setUp(self):
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
            primitives.summarize,
            primitives.structured_summarize,
            primitives.summarize_partial,
            primitives.structured_summarize_partial,
        )
        for primitive in variants:
            with self.subTest(primitive=primitive.__name__):
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
                    # Regular agent queries must still require an action.
                    with self.assertRaises(FormatError):
                        self.agent.query(self.messages)

    def test_summary_does_not_extract_commands_embedded_in_history(self):
        prose = "Previously ran:\n```mswea_bash_command\nls\n```"
        with patch.object(
            LitellmTextbasedModel, "_query", return_value=self.response(prose)
        ), patch.object(
            LitellmTextbasedModel, "_calculate_cost", return_value={"cost": 0.0}
        ):
            summary = primitives.query_summary(self.agent, self.messages)
            self.assertEqual(summary["extra"]["actions"], [])
            action = self.agent.query(self.messages)
            self.assertEqual(action["extra"]["actions"], [{"command": "ls"}])

    def test_model_without_action_parser_keeps_query_behavior(self):
        class ProseModel:
            def query(self, messages):
                self.messages = messages
                return {"content": "Summary text"}

        model = ProseModel()
        self.assertEqual(
            primitives.query_summary(model, self.messages), {"content": "Summary text"}
        )
        self.assertIs(model.messages, self.messages)


if __name__ == "__main__":
    unittest.main()
