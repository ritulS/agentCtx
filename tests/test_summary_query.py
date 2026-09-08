"""Regression coverage for prose summaries through mini-swe-agent v2 models.

Run with: PYTHONPATH=src:mini-swe-agent/src python -m unittest discover -s tests -p test_summary_query.py -v
"""

import os
import unittest
from unittest.mock import patch

from litellm import ModelResponse
from minisweagent.exceptions import FormatError
from minisweagent.models.litellm_textbased_model import LitellmTextbasedModel

from agentctx.compression import primitives


class SummaryQueryTests(unittest.TestCase):
    def setUp(self):
        env = patch.dict(os.environ, {
            "MSWEA_SUMMARY_MODEL_CONFIG": "",
            "MSWEA_SUMMARY_MODEL_NAME": "",
            "MSWEA_SUMMARY_API_BASE": "",
        })
        env.start()
        self.addCleanup(env.stop)
        cache = patch.object(primitives, "_SUMMARY_MODEL", None)
        cache.start()
        self.addCleanup(cache.stop)
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

    def test_all_variants_use_override_but_format_history_for_agent(self):
        summary_model = LitellmTextbasedModel(
            model_name="hosted_vllm/test-summary", cost_tracking="ignore_errors"
        )
        with patch.dict(os.environ, {"MSWEA_SUMMARY_MODEL_NAME": "hosted_vllm/test-summary"}), patch(
            "minisweagent.models.get_model", return_value=summary_model
        ) as factory:
            for primitive in (
                primitives.summarize, primitives.structured_summarize,
                primitives.summarize_partial, primitives.structured_summarize_partial,
            ):
                with self.subTest(primitive=primitive.__name__), patch.object(
                    summary_model, "_query", return_value=self.response("Prose summary.")
                ) as api, patch.object(
                    summary_model, "_calculate_cost", return_value={"cost": 0.0}
                ), patch.object(
                    summary_model, "format_message", wraps=summary_model.format_message
                ) as summary_format, patch.object(
                    self.agent, "format_message", wraps=self.agent.format_message
                ) as agent_format, patch.object(self.agent, "query") as agent_query:
                    result, _, pt, ct, _ = primitive(self.messages, self.agent, 200)
                    api.assert_called_once()
                    agent_query.assert_not_called()
                    self.assertEqual(summary_format.call_count, 2)
                    agent_format.assert_called_once()
                    self.assertIn("Prose summary.", result[2]["content"])
                    self.assertEqual((pt, ct), (321, 27))
                    with self.assertRaises(FormatError):
                        summary_model.query(self.messages)
            factory.assert_called_once()

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
