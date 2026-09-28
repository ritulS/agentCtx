"""Length-free summaries (SU-free / SS-free) never put a word target in the prompt.

Also pins the prompt refactor: summarize() / structured_summarize() build the
same prompt text as before through the shared _su_prompt / _ss_prompt helpers.

Needs tiktoken (imported by the primitives module):
    uvx --with tiktoken --with pyyaml pytest tests/test_summary_free.py
"""

import re
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

try:
    from agentctx.compression import primitives as memory
except ImportError as exc:  # pragma: no cover - depends on the installed env
    raise unittest.SkipTest(f"primitives dependencies not installed: {exc}")


class FakeModel:
    @staticmethod
    def format_message(role, content):
        return {"role": role, "content": content}


def _messages():
    return [
        {"role": "system", "content": "Solve the task with bash commands."},
        {"role": "user", "content": "Fix the database routing bug."},
        {"role": "assistant", "content": "Examined management.py. " * 300},
        {"role": "user", "content": "The save call needs using=db. " * 300},
        {"role": "assistant", "content": "Next: apply the fix."},
        {"role": "user", "content": "Patch applied successfully."},
    ]


def _user_prompt(prompt):
    return prompt[1]["content"]


class SummaryFreeTests(unittest.TestCase):
    def setUp(self):
        self.model = FakeModel()
        self.get_model = patch.object(memory, "get_summary_model", side_effect=lambda m: m)
        self.get_model.start()
        self.addCleanup(self.get_model.stop)

    def _run(self, primitive, target, summary_text):
        captured = {}

        def fake_request(summary_model, summary_prompt, open_marker, close_marker, max_attempts=None):
            captured["prompt"] = summary_prompt
            memory._set_summary_outcome({"attempts": 1, "accepted": summary_text is not None,
                                         "rejections": [], "flags": {}, "fallback": None})
            return summary_text, {"format": "marked"}, 321, 27, 0.01

        with patch.object(memory, "request_summary", side_effect=fake_request):
            result = primitive(_messages(), self.model, target)
        return result, captured["prompt"]

    def test_free_variants_have_no_word_target_and_are_target_invariant(self):
        for primitive, tail in (
            (memory.summarize_free, "concisely. Your summary MUST include all of:"),
            (memory.structured_summarize_free, "Produce a concise structured summary of the agent conversation below. Use EXACTLY"),
        ):
            with self.subTest(primitive=primitive.__name__):
                prompts = []
                for target in (200, 2000, 20000):
                    (result, saved, pt, ct, latency), prompt = self._run(primitive, target, "summary body")
                    prompts.append(_user_prompt(prompt))
                    self.assertEqual(result[:2], _messages()[:2])
                    self.assertEqual(len(result), 3)
                    self.assertEqual(result[2]["content"], "summary body")
                    self.assertEqual(result[2]["extra"]["kind"], memory.SUMMARY_KIND)
                    self.assertTrue(result[2]["extra"]["summary_format"]["length_free"])
                    self.assertGreater(saved, 0)
                    self.assertEqual((pt, ct), (321, 27))
                # Same prompt for every target: compression_ratio never reaches the summarizer.
                self.assertEqual(len(set(prompts)), 1)
                self.assertIn(tail, prompts[0])
                self.assertNotIn("approximately", prompts[0])
                self.assertIsNone(re.search(r"\d+ words", prompts[0]))

    def test_sized_variants_still_carry_the_word_target(self):
        for primitive in (memory.summarize, memory.structured_summarize):
            with self.subTest(primitive=primitive.__name__):
                (_, prompt_lo), (_, prompt_hi) = (
                    self._run(primitive, 400, "summary body"),
                    self._run(primitive, 4000, "summary body"),
                )
                lo = re.search(r"approximately (\d+) words", _user_prompt(prompt_lo))
                hi = re.search(r"approximately (\d+) words", _user_prompt(prompt_hi))
                self.assertIsNotNone(lo)
                self.assertIsNotNone(hi)
                self.assertLess(int(lo.group(1)), int(hi.group(1)))
                self.assertNotIn("length_free", str(prompt_lo))

    def test_free_variants_fall_back_to_complete_turns_at_target(self):
        for primitive in (memory.summarize_free, memory.structured_summarize_free):
            with self.subTest(primitive=primitive.__name__):
                (result, saved, pt, ct, _), _ = self._run(primitive, 200, None)
                expected = _messages()[:2] + _messages()[-2:]
                self.assertEqual(result, expected)
                self.assertGreater(saved, 0)
                self.assertEqual((pt, ct), (321, 27))
                outcome = memory.pop_summary_outcome()
                self.assertEqual(outcome["fallback"], "truncate")


if __name__ == "__main__":
    unittest.main()
