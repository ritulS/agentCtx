"""Summary responses are cleaned and structurally tagged before entering history.

Regression for the 2026-09-08 audit (ICLR_experiments/open_issues/
resume_audit_20260908): structured summaries carried the model's inline
``</think>`` preamble, which hid the marker line from the prefix check of the
(since removed) tool-result clearing, so the summary was cleared as tool
output, and put summarisation prose in front of the agent. The SS marker
pair below is the one those summaries carried; clean_summary_text() takes
any marker pair, and SU-free is the only summarizer primitive left.

Needs tiktoken (imported by the primitives module):
    uvx --with tiktoken --with pyyaml pytest tests/test_summary_cleaning.py
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

try:
    from agentctx.compression import primitives as memory
except ImportError as exc:  # pragma: no cover - depends on the installed env
    raise unittest.SkipTest(f"primitives dependencies not installed: {exc}")


PREAMBLE = (
    "The user wants me to compress the agent's working memory into a structured "
    "summary. Let me analyze the conversation history:\n\n1. The agent examined "
    "/testbed/django/db/models/constraints.py\n\nLet me create the summary.\n"
    "</think>\n\n"
)
SS_OPEN_MARKER = "[CONTEXT SUMMARY]"       # markers of the removed SS primitives
SS_CLOSE_MARKER = "[END CONTEXT SUMMARY]"  # (clean_summary_text is marker-agnostic)
SS_BODY = (
    "[CONTEXT SUMMARY]\n## Task\nFix CheckConstraint SQL.\n\n## Files Modified\nNone\n\n"
    "## Files Examined\n/testbed/django/db/models/constraints.py — builds the SQL\n\n"
    "## Execution Anchors\nNone\n\n## Current State\nNext: edit constraints.py\n"
    "[END CONTEXT SUMMARY]"
)


SU_BODY = f"{memory.SU_OPEN_MARKER}\nExamined file0.py through file5.py.\n{memory.SU_CLOSE_MARKER}"


class FakeModel:
    """Minimal mini-swe-agent model: format_message + query returning content.

    ``reply`` may be a list; successive queries return successive entries and
    the last entry repeats.
    """

    def __init__(self, reply):
        self.replies = list(reply) if isinstance(reply, list) else [reply]
        self.calls = 0

    def format_message(self, **kwargs):
        return dict(kwargs)

    def query(self, messages, **kwargs):
        reply = self.replies[min(self.calls, len(self.replies) - 1)]
        self.calls += 1
        return {
            "role": "assistant",
            "content": reply,
            "extra": {"response": {"usage": {"prompt_tokens": 100, "completion_tokens": 20}}},
        }


def history(n_steps: int = 6) -> list[dict]:
    msgs = [
        {"role": "system", "content": "Solve the task with bash commands."},
        {"role": "user", "content": "Fix the CheckConstraint SQL bug."},
    ]
    for i in range(n_steps):
        msgs.append({"role": "assistant", "content": f"```bash\ncat file{i}.py\n```"})
        msgs.append({"role": "user", "content": f"line {i} of file{i}.py\n" * 40})
    return msgs


class CleanSummaryTextTests(unittest.TestCase):
    def test_think_preamble_is_dropped_and_block_extracted(self):
        raw = PREAMBLE + SS_BODY + "\n\nHope this helps!"
        text, flags = memory.clean_summary_text(raw, SS_OPEN_MARKER, SS_CLOSE_MARKER)
        self.assertEqual(text, SS_BODY)
        self.assertEqual(
            flags,
            {"had_think_preamble": True, "had_open_marker": True, "had_close_marker": True,
             "finish_reason": None, "raw_chars": len(raw), "rejected": None},
        )

    def test_missing_close_marker_is_rejected(self):
        # Until 2026-09-29 the body ran to the end of the response and the
        # close marker was appended. The r2 P30S run1 audit found a 133,948
        # character transcript copy accepted that way (history 15k -> 31k).
        body = SS_BODY.replace("\n[END CONTEXT SUMMARY]", "")
        text, flags = memory.clean_summary_text(
            PREAMBLE + body, SS_OPEN_MARKER, SS_CLOSE_MARKER
        )
        self.assertIsNone(text)
        self.assertEqual(flags["rejected"], "missing_close_marker")
        self.assertTrue(flags["had_open_marker"])
        self.assertFalse(flags["had_close_marker"])

    def test_length_cut_response_is_rejected_even_with_both_markers(self):
        # finish_reason=length means the generation was cut off; the block may
        # look complete when the model had started a second one.
        raw = SS_BODY + "\n\n[CONTEXT SUMMARY]\n## Task\nFix Check"
        text, flags = memory.clean_summary_text(
            raw, SS_OPEN_MARKER, SS_CLOSE_MARKER, finish_reason="length"
        )
        self.assertIsNone(text)
        self.assertEqual(flags["rejected"], "truncated")
        self.assertEqual(flags["finish_reason"], "length")
        self.assertTrue(flags["had_open_marker"] and flags["had_close_marker"])
        self.assertEqual(flags["raw_chars"], len(raw))
        # The same text with finish_reason=stop (or unknown) is accepted.
        for reason in ("stop", None):
            text, flags = memory.clean_summary_text(
                raw, SS_OPEN_MARKER, SS_CLOSE_MARKER, finish_reason=reason
            )
            self.assertEqual(text, SS_BODY)
            self.assertEqual(flags["finish_reason"], reason)

    def test_unmarked_prose_without_think_is_rejected(self):
        # Until 2026-09-27 this was accepted as an "unformatted body". With a
        # server-side reasoning parser the reply carries no </think>, so the
        # marker line is the only evidence that the model wrote a summary.
        text, flags = memory.clean_summary_text(
            "Examined constraints.py; nothing edited yet.",
            memory.SU_OPEN_MARKER, memory.SU_CLOSE_MARKER,
        )
        self.assertIsNone(text)
        self.assertEqual(flags["rejected"], "missing_marker")
        self.assertFalse(flags["had_open_marker"])
        self.assertFalse(flags["had_think_preamble"])

    def test_agent_continuation_without_marker_is_rejected(self):
        # Verbatim shape of the r2 P30S su-free failures (reasoning stripped by
        # vLLM's qwen3 parser): the summarizer answers as the agent instead.
        for raw in (
            "\n\n```mswea_bash_command\ncd /testbed && python test_reproduce.py\n```",
            "\n\n```mswea_bash_command\nls -la /testbed/tests/settings.py\n```\n\n[user]:\n"
            "<returncode>0</returncode>\n<output>\n-rw-r--r-- 1 root root 1006 settings.py\n</output>",
        ):
            text, flags = memory.clean_summary_text(raw, memory.SU_OPEN_MARKER, memory.SU_CLOSE_MARKER)
            self.assertIsNone(text, raw)
            self.assertEqual(flags["rejected"], "missing_marker")

    def test_close_marker_alone_is_not_enough(self):
        text, flags = memory.clean_summary_text(
            f"Examined constraints.py.\n{memory.SU_CLOSE_MARKER}",
            memory.SU_OPEN_MARKER, memory.SU_CLOSE_MARKER,
        )
        self.assertIsNone(text)
        self.assertEqual(flags["rejected"], "missing_marker")
        self.assertTrue(flags["had_close_marker"])

    def test_unmarked_prose_after_reasoning_is_rejected_as_ambiguous(self):
        # Review round 3: no marker line + </think> is undecidable, so it goes
        # to retry / fallback instead of being guessed at.
        text, flags = memory.clean_summary_text(
            PREAMBLE + "Examined constraints.py; nothing edited yet.",
            memory.SU_OPEN_MARKER, memory.SU_CLOSE_MARKER,
        )
        self.assertIsNone(text)
        self.assertEqual(flags["rejected"], "ambiguous_reasoning")
        self.assertTrue(flags["had_think_preamble"])

    def test_clean_response_is_unchanged(self):
        text, flags = memory.clean_summary_text(
            SS_BODY, SS_OPEN_MARKER, SS_CLOSE_MARKER
        )
        self.assertEqual(text, SS_BODY)
        self.assertFalse(flags["had_think_preamble"])

    def test_literal_think_close_inside_marked_body_is_kept(self):
        # Review case 1: a literal </think> in Execution Anchors must not turn
        # the sections before it into "preamble".
        body = SS_BODY.replace(
            "## Execution Anchors\nNone",
            '## Execution Anchors\nHandle the literal "</think>" in logs.',
        )
        text, flags = memory.clean_summary_text(
            PREAMBLE + body, SS_OPEN_MARKER, SS_CLOSE_MARKER
        )
        self.assertEqual(text, body)
        self.assertIn("## Task", text)
        self.assertIn('literal "</think>"', text)
        self.assertTrue(flags["had_think_preamble"])

    def test_literal_think_close_in_marked_body_after_reasoning_is_kept(self):
        # Reasoning, then a marked body that quotes </think>: only the first
        # </think> (before the marker line) is the reasoning end.
        body = 'Grep for "</think>" in parser.py returned 3 hits.'
        text, flags = memory.clean_summary_text(
            f"thinking...</think>\n{memory.SU_OPEN_MARKER}\n{body}\n{memory.SU_CLOSE_MARKER}",
            memory.SU_OPEN_MARKER, memory.SU_CLOSE_MARKER,
        )
        self.assertEqual(text, f"{memory.SU_OPEN_MARKER}\n{body}\n{memory.SU_CLOSE_MARKER}")
        self.assertIsNone(flags["rejected"])

    def test_marked_su_body_with_literal_think_close_and_no_preamble(self):
        # Review round 2, case 2: a normal SU reply (now marked) that quotes
        # "</think>" must not lose the text before the quote.
        body = 'Fixed parser.py and added regression tests. Search for "</think>" in logs next.'
        raw = f"{memory.SU_OPEN_MARKER}\n{body}\n{memory.SU_CLOSE_MARKER}"
        text, flags = memory.clean_summary_text(raw, memory.SU_OPEN_MARKER, memory.SU_CLOSE_MARKER)
        self.assertEqual(text, raw)
        self.assertFalse(flags["had_think_preamble"])

    def test_unmarked_body_with_literal_think_close_is_rejected_not_truncated(self):
        # No marker line at all + "</think>" cannot be told apart from reasoning
        # followed by an unformatted body. Instead of guessing (which used to
        # keep only '" in logs next.'), the response is rejected.
        text, flags = memory.clean_summary_text(
            'Fixed parser.py. Search for "</think>" in logs next.',
            memory.SU_OPEN_MARKER, memory.SU_CLOSE_MARKER,
        )
        self.assertIsNone(text)
        self.assertEqual(flags["rejected"], "ambiguous_reasoning")

    def test_indented_markers_with_empty_body_are_rejected(self):
        # Review round 3 bug: offsets came from the line start, so indentation
        # shifted the cut and an empty block was accepted with a damaged marker.
        raw = "Preface\n  [CONTEXT SUMMARY]\n\n  [END CONTEXT SUMMARY]"
        text, flags = memory.clean_summary_text(raw, SS_OPEN_MARKER, SS_CLOSE_MARKER)
        self.assertIsNone(text)
        self.assertEqual(flags["rejected"], "empty_body")
        self.assertTrue(flags["had_open_marker"] and flags["had_close_marker"])

    def test_indented_markers_are_rewrapped_canonically(self):
        raw = "Preface\n    [CONTEXT SUMMARY]\n    ## Task\n    Fix the bug\n\t[END CONTEXT SUMMARY]\ntrailer"
        text, flags = memory.clean_summary_text(raw, SS_OPEN_MARKER, SS_CLOSE_MARKER)
        self.assertEqual(
            text, f"{SS_OPEN_MARKER}\n## Task\n    Fix the bug\n{SS_CLOSE_MARKER}"
        )
        self.assertTrue(text.startswith(SS_OPEN_MARKER))
        self.assertTrue(text.endswith(SS_CLOSE_MARKER))

    def test_crlf_marker_lines_are_recognised(self):
        raw = PREAMBLE.replace("\n", "\r\n") + SS_BODY.replace("\n", "\r\n")
        text, flags = memory.clean_summary_text(raw, SS_OPEN_MARKER, SS_CLOSE_MARKER)
        self.assertEqual(text, SS_BODY)
        self.assertTrue(flags["had_open_marker"] and flags["had_close_marker"])
        self.assertNotIn("\r", text)

    def test_marker_mentioned_inline_in_reasoning_is_not_the_body_start(self):
        # Review round 2, case 1a.
        raw = (
            "I must use [CONTEXT SUMMARY] and include all five sections.\n"
            "Let me inspect each file.\n</think>\n" + SS_BODY
        )
        text, flags = memory.clean_summary_text(raw, SS_OPEN_MARKER, SS_CLOSE_MARKER)
        self.assertEqual(text, SS_BODY)
        self.assertTrue(flags["had_think_preamble"])

    def test_marker_block_quoted_inside_reasoning_is_skipped(self):
        # Review round 2, case 1c: the reasoning reproduces the whole format on
        # its own lines before closing; the real block follows </think>.
        quoted = "The format is:\n[CONTEXT SUMMARY]\n## Task\n<one sentence>\n[END CONTEXT SUMMARY]\nNow write it.\n</think>\n"
        text, flags = memory.clean_summary_text(quoted + SS_BODY, SS_OPEN_MARKER, SS_CLOSE_MARKER)
        self.assertEqual(text, SS_BODY)

    def test_unterminated_think_containing_marker_is_rejected(self):
        # Review round 2, case 1b.
        raw = "<think>Draft:\n[CONTEXT SUMMARY]\n## Task\nFix the bug\n[END CONTEXT SUMMARY]\nbut I should double-check"
        text, flags = memory.clean_summary_text(raw, SS_OPEN_MARKER, SS_CLOSE_MARKER)
        self.assertIsNone(text)
        self.assertEqual(flags["rejected"], "unterminated_reasoning")

    def test_marker_not_on_its_own_line_is_not_a_marker(self):
        # A marker glued to other text on the same line is not a marker line;
        # without a marker line the reply is rejected (retried) since 2026-09-27.
        raw = "[CONTEXT SUMMARY] ## Task\nFix the bug\n[END CONTEXT SUMMARY]"
        text, flags = memory.clean_summary_text(raw, SS_OPEN_MARKER, SS_CLOSE_MARKER)
        self.assertFalse(flags["had_open_marker"])
        self.assertTrue(flags["had_close_marker"])
        self.assertIsNone(text)
        self.assertEqual(flags["rejected"], "missing_marker")

    def test_trailing_text_after_close_marker_is_dropped(self):
        text, _ = memory.clean_summary_text(
            SS_BODY + "\n\nHope this helps!", SS_OPEN_MARKER, SS_CLOSE_MARKER
        )
        self.assertEqual(text, SS_BODY)

    def test_reasoning_only_response_is_rejected(self):
        # Review case 2a: "thinking...</think>" would otherwise become an empty
        # marker pair that replaces the history.
        text, flags = memory.clean_summary_text(
            "Let me think about the summary...</think>\n",
            SS_OPEN_MARKER, SS_CLOSE_MARKER,
        )
        self.assertIsNone(text)
        self.assertEqual(flags["rejected"], "empty_body")

    def test_empty_marked_block_is_rejected(self):
        text, flags = memory.clean_summary_text(
            f"{SS_OPEN_MARKER}\n\n{SS_CLOSE_MARKER}",
            SS_OPEN_MARKER, SS_CLOSE_MARKER,
        )
        self.assertIsNone(text)
        self.assertEqual(flags["rejected"], "empty_body")

    def test_unterminated_reasoning_is_rejected(self):
        # Review case 2b: an open <think> that never closes (e.g. max_tokens hit).
        text, flags = memory.clean_summary_text(
            "<think>Still working out which files were touched and",
            SS_OPEN_MARKER, SS_CLOSE_MARKER,
        )
        self.assertIsNone(text)
        self.assertEqual(flags["rejected"], "unterminated_reasoning")

    def test_whitespace_only_response_is_rejected(self):
        text, flags = memory.clean_summary_text("  \n", memory.SU_OPEN_MARKER, memory.SU_CLOSE_MARKER)
        self.assertIsNone(text)
        self.assertEqual(flags["rejected"], "empty_body")


class SummaryPrimitiveTests(unittest.TestCase):
    def assert_tagged_summary(self, msg, open_marker):
        self.assertEqual(msg["role"], "user")
        self.assertTrue(msg["content"].startswith(open_marker), msg["content"][:80])
        self.assertNotIn("</think>", msg["content"])
        self.assertNotIn("Let me analyze", msg["content"])
        self.assertEqual(msg["extra"]["kind"], memory.SUMMARY_KIND)
        self.assertTrue(msg["extra"]["summary_format"]["had_think_preamble"])
        self.assertTrue(memory.is_summary_message(msg))

    def test_summarize_free_cleans_and_tags(self):
        model = FakeModel(PREAMBLE + SU_BODY)
        msgs = history()
        result, saved, pt, ct, _ = memory.summarize_free(msgs, model, 400)
        self.assertEqual(result[:2], msgs[:2])
        self.assertEqual(len(result), 3)
        self.assert_tagged_summary(result[2], memory.SU_OPEN_MARKER)
        self.assertEqual(result[2]["content"], SU_BODY)
        self.assertIn("Examined file0.py", result[2]["content"])
        self.assertEqual(result[2]["content"].count(memory.SU_OPEN_MARKER), 1)
        self.assertGreater(saved, 0)
        self.assertEqual((pt, ct), (100, 20))

    def test_ambiguous_reply_is_retried_then_accepted(self):
        marked = f"{memory.SU_OPEN_MARKER}\nExamined file0.py.\n{memory.SU_CLOSE_MARKER}"
        model = FakeModel([PREAMBLE + "Examined file0.py.", marked])
        result, *_ = memory.summarize_free(history(), model, 400)
        self.assertEqual(model.calls, 2)
        self.assertEqual(result[2]["content"], marked)
        self.assertEqual(result[2]["extra"]["summary_format"]["attempts"], 2)

    def test_su_prompt_requests_markers(self):
        model = FakeModel(f"{memory.SU_OPEN_MARKER}\nok\n{memory.SU_CLOSE_MARKER}")
        seen = {}
        original = model.query

        def spy(messages, **kw):
            seen["prompt"] = messages[-1]["content"]
            return original(messages, **kw)

        model.query = spy
        memory.summarize_free(history(), model, 400)
        self.assertIn(memory.SU_OPEN_MARKER, seen["prompt"])
        self.assertIn(memory.SU_CLOSE_MARKER, seen["prompt"])

    def test_rejected_first_attempt_is_retried_once(self):
        model = FakeModel(["Let me think...</think>", PREAMBLE + SU_BODY])
        msgs = history()
        result, saved, pt, ct, _ = memory.summarize_free(msgs, model, 400)
        self.assertEqual(model.calls, 2)
        self.assertEqual(result[2]["content"], SU_BODY)
        self.assertEqual(result[2]["extra"]["summary_format"]["attempts"], 2)
        self.assertEqual((pt, ct), (200, 40))  # usage summed over attempts
        self.assertGreater(saved, 0)

    def test_all_attempts_rejected_falls_back_to_truncate(self):
        model = FakeModel("<think>never finishes")
        msgs = history()
        result, saved, pt, ct, _ = memory.summarize_free(msgs, model, 400)
        self.assertEqual(model.calls, memory.SUMMARY_MAX_ATTEMPTS)
        self.assertEqual(result[:2], msgs[:2])
        # No summary was inserted; the oldest complete turns were dropped instead
        # (truncate_oldest_turns: protected head + the latest turn always stay).
        self.assertFalse(any(memory.is_summary_message(m) for m in result))
        self.assertTrue(all(m in msgs for m in result))
        self.assertEqual(result[-2:], msgs[-2:])
        self.assertLess(len(result), len(msgs))
        self.assertGreater(saved, 0)
        self.assertEqual(pt, 100 * memory.SUMMARY_MAX_ATTEMPTS)

    def test_outcome_record_after_fallback(self):
        memory.pop_summary_outcome()  # clear
        model = FakeModel(["<think>never finishes", "...</think>"])
        memory.summarize_free(history(), model, 400)
        outcome = memory.pop_summary_outcome()
        self.assertEqual(outcome["attempts"], memory.SUMMARY_MAX_ATTEMPTS)
        self.assertFalse(outcome["accepted"])
        # Two scripted replies; FakeModel repeats the last one for the remaining attempts.
        expected = (["unterminated_reasoning", "empty_body"] + ["empty_body"] * memory.SUMMARY_MAX_ATTEMPTS)
        self.assertEqual(outcome["rejections"], expected[:memory.SUMMARY_MAX_ATTEMPTS])
        self.assertEqual(outcome["fallback"], "truncate")
        self.assertIsNone(memory.pop_summary_outcome())  # popped once only

    def test_outcome_record_after_retry_success(self):
        memory.pop_summary_outcome()
        memory.summarize_free(
            history(8),
            FakeModel(["...</think>", f"{memory.SU_OPEN_MARKER}\nok\n{memory.SU_CLOSE_MARKER}"]),
            900,
        )
        outcome = memory.pop_summary_outcome()
        self.assertEqual(outcome["attempts"], 2)
        self.assertTrue(outcome["accepted"])
        self.assertEqual(outcome["rejections"], ["empty_body"])
        self.assertIsNone(outcome["fallback"])
        self.assertTrue(outcome["flags"]["had_open_marker"])

    def test_outcome_records_response_id_per_attempt(self):
        class IdModel(FakeModel):
            def query(self, messages, **kwargs):
                msg = super().query(messages, **kwargs)
                if self.calls == 1:   # first attempt: provider reply without an id
                    return msg
                msg["extra"]["response"]["id"] = f"chatcmpl-{self.calls}"
                return msg

        memory.pop_summary_outcome()
        memory.summarize_free(
            history(8),
            IdModel(["...</think>", f"{memory.SU_OPEN_MARKER}\nok\n{memory.SU_CLOSE_MARKER}"]),
            900,
        )
        outcome = memory.pop_summary_outcome()
        self.assertEqual(outcome["attempts"], 2)
        self.assertEqual(outcome["response_ids"], [None, "chatcmpl-2"])

    def test_outcome_keeps_ids_when_a_later_attempt_raises(self):
        class FlakyModel(FakeModel):
            def query(self, messages, **kwargs):
                if self.calls == 1:
                    self.calls += 1
                    raise RuntimeError("transport failed")
                msg = super().query(messages, **kwargs)
                msg["extra"]["response"]["id"] = f"chatcmpl-{self.calls}"
                return msg

        memory.pop_summary_outcome()
        with self.assertRaisesRegex(RuntimeError, "transport failed"):
            memory.summarize_free(history(8), FlakyModel(["...</think>"]), 900)
        outcome = memory.pop_summary_outcome()
        self.assertEqual(outcome["response_ids"], ["chatcmpl-1"])
        self.assertEqual(outcome["attempts"], 1)
        self.assertFalse(outcome["accepted"])
        self.assertEqual(outcome["rejections"], ["empty_body"])
        self.assertEqual(outcome["interrupted"], "RuntimeError")
        self.assertEqual(outcome["interrupted_attempt"], 2)

    def test_request_summary_retries_after_length_cut_response(self):
        # The provider's finish_reason travels in extra.response (as the
        # LiteLLM models store it); a cut-off reply is retried, not accepted.
        class FinishModel(FakeModel):
            def __init__(self, replies, reasons):
                super().__init__(replies)
                self.reasons = reasons

            def query(self, messages, **kwargs):
                reason = self.reasons[min(self.calls, len(self.reasons) - 1)]
                msg = super().query(messages, **kwargs)
                msg["extra"]["response"]["choices"] = [{"finish_reason": reason}]
                return msg

        open_only = SS_BODY.replace("\n[END CONTEXT SUMMARY]", "") + "\n[user]:\nline 1 of file"
        model = FinishModel([open_only, SS_BODY, SS_BODY], ["length", "stop"])
        text, flags, pt, ct, _ = memory.request_summary(
            model, [], SS_OPEN_MARKER, SS_CLOSE_MARKER
        )
        self.assertEqual(text, SS_BODY)
        self.assertEqual(model.calls, 2)
        self.assertEqual(flags["attempts"], 2)
        self.assertEqual(flags["finish_reason"], "stop")
        self.assertEqual((pt, ct), (200, 40))  # usage summed over both attempts
        outcome = memory.pop_summary_outcome()
        self.assertEqual(outcome["rejections"], ["truncated"])
        self.assertTrue(outcome["accepted"])

    def test_no_outcome_without_summary_request(self):
        memory.pop_summary_outcome()
        memory.truncate_oldest_turns(history(), 1)
        self.assertIsNone(memory.pop_summary_outcome())

    def test_token_log_dict_reports_summary_outcomes(self):
        class Agent:  # the _mem_* accumulators token_log_dict reads
            _mem_prompt_tokens = _mem_completion_tokens = 0
            _mem_total_latency = 0.0
            _mem_call_latencies = []
            _mem_compression_events = 0
            _mem_compression_event_steps = []
            _mem_context_tokens_at_compression = []
            _mem_context_tokens_after_compression = []
            _mem_tokens_saved = 0
            _mem_compression_ratios = []
            _mem_step_prompt_tokens = []
            _mem_step_completion_tokens = []
            _mem_summarization_prompt_tokens = 0
            _mem_summarization_latency_s = 0.0
            _mem_summary_outcomes = [
                {"step": 12, "primitive": "summarization_free", "attempts": 2,
                 "accepted": False, "rejections": ["empty_body", "ambiguous_reasoning"],
                 "fallback": "truncate"},
                {"step": 30, "primitive": "summarization_free", "attempts": 1,
                 "accepted": True, "rejections": [], "fallback": None},
            ]

        data = memory.token_log_dict(Agent())
        self.assertEqual(data["summary_fallback_events"], 1)
        self.assertEqual(len(data["summary_outcomes"]), 2)
        del Agent._mem_summary_outcomes  # agents predating the field
        self.assertEqual(memory.token_log_dict(Agent())["summary_fallback_events"], 0)

    def test_token_log_dict_reports_net_savings_separately_from_clamped_total(self):
        # Primitives clamp per-event savings at 0, so total_tokens_saved hides
        # an event that grew the history. net_tokens_saved is the signed sum of
        # the recorded before/after counts (r2 P30S run1 audit, finding 2).
        class Agent:
            _mem_prompt_tokens = _mem_completion_tokens = 0
            _mem_total_latency = 0.0
            _mem_call_latencies = []
            _mem_compression_events = 3
            _mem_compression_event_steps = [10, 20, 30]
            _mem_context_tokens_at_compression = [16000, 15123, 31777]
            _mem_context_tokens_after_compression = [2000, 31684, 1773]
            _mem_tokens_saved = 14000 + 0 + 30004
            _mem_compression_ratios = []
            _mem_step_prompt_tokens = []
            _mem_step_completion_tokens = []
            _mem_summarization_prompt_tokens = 0
            _mem_summarization_latency_s = 0.0

        data = memory.token_log_dict(Agent())
        self.assertEqual(data["total_tokens_saved"], 44004)
        self.assertEqual(data["net_tokens_saved"], 44004 - 16561)
        self.assertEqual(data["growth_events"], 1)

    def test_max_attempts_override(self):
        model = FakeModel("...</think>")
        text, flags, *_ = memory.request_summary(
            model, [], SS_OPEN_MARKER, SS_CLOSE_MARKER, max_attempts=3
        )
        self.assertIsNone(text)
        self.assertEqual(model.calls, 3)
        self.assertEqual(flags["attempts"], 3)
        self.assertEqual(flags["rejected"], "empty_body")

    def test_summary_tag_survives_agent_uid_tagging(self):
        # default.py merges uid fields into an existing extra dict; make sure a
        # pre-populated extra from format_message is merged, not replaced.
        class ExtraModel(FakeModel):
            def format_message(self, **kwargs):
                return {**kwargs, "extra": {"uid": "u00042"}}

        result, *_ = memory.summarize_free(history(), ExtraModel(SU_BODY), 400)
        self.assertEqual(result[2]["extra"]["uid"], "u00042")
        self.assertEqual(result[2]["extra"]["kind"], memory.SUMMARY_KIND)


class IsSummaryMessageTests(unittest.TestCase):
    """is_summary_message(): the structural tag, then the legacy marker prefixes
    (what the removed tool-result clearing used to decide what it may clear)."""

    def test_tagged_summary_is_recognised_even_without_marker(self):
        self.assertTrue(memory.is_summary_message(
            {"role": "user", "content": "free-form summary text", "extra": {"kind": memory.SUMMARY_KIND}}
        ))

    def test_legacy_marker_summaries_are_recognised(self):
        self.assertTrue(memory.is_summary_message({"role": "user", "content": SS_BODY}))
        self.assertTrue(memory.is_summary_message(
            {"role": "user", "content": f"{memory.SU_OPEN_MARKER}\nold prose\n{memory.SU_CLOSE_MARKER}"}
        ))

    def test_new_pipeline_summary_is_recognised(self):
        result, *_ = memory.summarize_free(history(), FakeModel(PREAMBLE + SU_BODY), 400)
        self.assertTrue(memory.is_summary_message(result[2]))

    def test_untagged_preamble_summary_is_the_old_bug(self):
        # Documents the failure mode the cleaning removes: without the tag and
        # with the preamble, the summary reads as ordinary tool output.
        self.assertFalse(memory.is_summary_message({"role": "user", "content": PREAMBLE + SS_BODY}))
        self.assertFalse(memory.is_summary_message({"role": "user", "content": "ls output"}))


if __name__ == "__main__":
    unittest.main()
