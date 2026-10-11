"""request_summary() keeps every summarizer reply, rejected ones included, in
MSWEA_EVENT_LOG_DIR/summary_attempts.jsonl (or MSWEA_SUMMARY_ATTEMPT_LOG).

Run with: uvx --with pyyaml pytest tests/test_summary_attempt_log.py
"""

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

from agentctx.compression import primitives as memory  # noqa: E402

OPEN, CLOSE = memory.SU_OPEN_MARKER, memory.SU_CLOSE_MARKER


class FakeSummaryModel:
    """Returns the scripted replies in order, as mini-swe-agent's query() would."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = 0

    def query(self, messages):
        self.calls += 1
        content, finish_reason, reasoning = self.replies.pop(0)
        message = {"role": "assistant", "content": content}
        if reasoning is not None:
            message["reasoning"] = reasoning
        return {
            "role": "assistant", "content": content,
            "extra": {"response": {
                "id": f"chatcmpl-{self.calls}",
                "choices": [{"finish_reason": finish_reason, "message": message}],
                "usage": {"prompt_tokens": 100 + self.calls, "completion_tokens": 10 * self.calls},
            }},
        }


class SummaryAttemptLogTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.env = patch.dict(os.environ, {"MSWEA_EVENT_LOG_DIR": self.tmp.name}, clear=False)
        self.env.start()
        self.addCleanup(self.env.stop)
        os.environ.pop("MSWEA_SUMMARY_ATTEMPT_LOG", None)

    def read_log(self, path=None):
        path = path or Path(self.tmp.name) / "summary_attempts.jsonl"
        return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]

    def test_rejected_and_accepted_replies_are_kept_verbatim(self):
        model = FakeSummaryModel([
            ("I will summarize now but forget the markers.", "stop", "thinking about it"),
            (f"{OPEN}\nStarted the summary but ran out of", "length", None),
            (f"{OPEN}\nTask: fix the bug. Files: a.py.\n{CLOSE}", "stop", None),
        ])
        text, flags, pt, ct, latency = memory.request_summary(model, [{"role": "user", "content": "summarize"}],
                                                              OPEN, CLOSE, max_attempts=5)
        self.assertTrue(text.startswith(OPEN))
        rows = self.read_log()
        self.assertEqual([(r["attempt"], r["accepted"], r["rejected"], r["outcome"]) for r in rows], [
            (1, False, "missing_marker", "retry"),
            (2, False, "truncated", "retry"),
            (3, True, None, "accepted"),
        ])
        self.assertEqual(rows[0]["content"], "I will summarize now but forget the markers.")
        self.assertEqual(rows[0]["reasoning"], "thinking about it")
        self.assertEqual(rows[1]["finish_reason"], "length")
        self.assertTrue(rows[1]["had_open_marker"])
        self.assertFalse(rows[1]["had_close_marker"])
        self.assertIsNone(rows[1]["summary"])
        self.assertEqual(rows[2]["summary"], text)
        self.assertEqual([r["response_id"] for r in rows], ["chatcmpl-1", "chatcmpl-2", "chatcmpl-3"])
        self.assertEqual([r["attempts_allowed"] for r in rows], [5, 5, 5])
        self.assertEqual(len({r["request_seq"] for r in rows}), 1)
        self.assertEqual([r["completion_tokens"] for r in rows], [10, 20, 30])
        self.assertEqual(ct, 60)

    def test_exhausted_attempts_are_marked_fallback_and_requests_are_numbered(self):
        model = FakeSummaryModel([("no markers", "stop", None), ("still none", "stop", None),
                                  (f"{OPEN}\nok\n{CLOSE}", "stop", None)])
        text, *_ = memory.request_summary(model, [], OPEN, CLOSE, max_attempts=2)
        self.assertIsNone(text)
        text2, *_ = memory.request_summary(model, [], OPEN, CLOSE, max_attempts=2)
        self.assertIsNotNone(text2)
        rows = self.read_log()
        self.assertEqual([r["outcome"] for r in rows], ["retry", "fallback", "accepted"])
        self.assertEqual(rows[1]["attempt"], rows[1]["attempts_allowed"])
        self.assertEqual(rows[0]["request_seq"], rows[1]["request_seq"])
        self.assertEqual(rows[2]["request_seq"], rows[1]["request_seq"] + 1)

    def test_explicit_path_and_off_switch(self):
        other = Path(self.tmp.name) / "elsewhere" / "attempts.jsonl"
        os.environ["MSWEA_SUMMARY_ATTEMPT_LOG"] = str(other)
        memory.request_summary(FakeSummaryModel([(f"{OPEN}\nok\n{CLOSE}", "stop", None)]), [], OPEN, CLOSE)
        self.assertEqual(len(self.read_log(other)), 1)
        self.assertFalse((Path(self.tmp.name) / "summary_attempts.jsonl").exists())
        os.environ["MSWEA_SUMMARY_ATTEMPT_LOG"] = "0"
        memory.request_summary(FakeSummaryModel([(f"{OPEN}\nok\n{CLOSE}", "stop", None)]), [], OPEN, CLOSE)
        self.assertEqual(len(self.read_log(other)), 1)
        self.assertFalse((Path(self.tmp.name) / "summary_attempts.jsonl").exists())
        os.environ.pop("MSWEA_SUMMARY_ATTEMPT_LOG")
        os.environ.pop("MSWEA_EVENT_LOG_DIR")
        self.assertIsNone(memory.summary_attempt_log_path())
        memory.request_summary(FakeSummaryModel([(f"{OPEN}\nok\n{CLOSE}", "stop", None)]), [], OPEN, CLOSE)
        self.assertFalse((Path(self.tmp.name) / "summary_attempts.jsonl").exists())


if __name__ == "__main__":
    unittest.main()
