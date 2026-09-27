"""Summary responses are cleaned and structurally tagged before entering history.

Regression for the 2026-09-08 audit (ICLR_experiments/open_issues/
resume_audit_20260908): structured summaries carried the model's inline
``</think>`` preamble, which hid the marker line from TRC's prefix check so the
summary was cleared as tool output, and put summarisation prose in front of
the agent.

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
SS_BODY = (
    "[CONTEXT SUMMARY]\n## Task\nFix CheckConstraint SQL.\n\n## Files Modified\nNone\n\n"
    "## Files Examined\n/testbed/django/db/models/constraints.py — builds the SQL\n\n"
    "## Execution Anchors\nNone\n\n## Current State\nNext: edit constraints.py\n"
    "[END CONTEXT SUMMARY]"
)


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
        text, flags = memory.clean_summary_text(
            PREAMBLE + SS_BODY + "\n\nHope this helps!",
            memory.SS_OPEN_MARKER, memory.SS_CLOSE_MARKER,
        )
        self.assertEqual(text, SS_BODY)
        self.assertEqual(
            flags,
            {"had_think_preamble": True, "had_open_marker": True, "had_close_marker": True, "rejected": None},
        )

    def test_missing_close_marker_is_appended(self):
        body = SS_BODY.replace("\n[END CONTEXT SUMMARY]", "")
        text, flags = memory.clean_summary_text(
            PREAMBLE + body, memory.SS_OPEN_MARKER, memory.SS_CLOSE_MARKER
        )
        self.assertTrue(text.startswith(memory.SS_OPEN_MARKER))
        self.assertTrue(text.endswith(memory.SS_CLOSE_MARKER))
        self.assertIn("Next: edit constraints.py", text)
        self.assertFalse(flags["had_close_marker"])

    def test_unmarked_prose_without_think_is_wrapped(self):
        text, flags = memory.clean_summary_text(
            "Examined constraints.py; nothing edited yet.",
            memory.SU_OPEN_MARKER, memory.SU_CLOSE_MARKER,
        )
        self.assertEqual(
            text,
            f"{memory.SU_OPEN_MARKER}\nExamined constraints.py; nothing edited yet.\n{memory.SU_CLOSE_MARKER}",
        )
        self.assertFalse(flags["had_open_marker"])

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
            SS_BODY, memory.SS_OPEN_MARKER, memory.SS_CLOSE_MARKER
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
            PREAMBLE + body, memory.SS_OPEN_MARKER, memory.SS_CLOSE_MARKER
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
        text, flags = memory.clean_summary_text(raw, memory.SS_OPEN_MARKER, memory.SS_CLOSE_MARKER)
        self.assertIsNone(text)
        self.assertEqual(flags["rejected"], "empty_body")
        self.assertTrue(flags["had_open_marker"] and flags["had_close_marker"])

    def test_indented_markers_are_rewrapped_canonically(self):
        raw = "Preface\n    [CONTEXT SUMMARY]\n    ## Task\n    Fix the bug\n\t[END CONTEXT SUMMARY]\ntrailer"
        text, flags = memory.clean_summary_text(raw, memory.SS_OPEN_MARKER, memory.SS_CLOSE_MARKER)
        self.assertEqual(
            text, f"{memory.SS_OPEN_MARKER}\n## Task\n    Fix the bug\n{memory.SS_CLOSE_MARKER}"
        )
        self.assertTrue(text.startswith(memory.SS_OPEN_MARKER))
        self.assertTrue(text.endswith(memory.SS_CLOSE_MARKER))

    def test_crlf_marker_lines_are_recognised(self):
        raw = PREAMBLE.replace("\n", "\r\n") + SS_BODY.replace("\n", "\r\n")
        text, flags = memory.clean_summary_text(raw, memory.SS_OPEN_MARKER, memory.SS_CLOSE_MARKER)
        self.assertEqual(text, SS_BODY)
        self.assertTrue(flags["had_open_marker"] and flags["had_close_marker"])
        self.assertNotIn("\r", text)

    def test_marker_mentioned_inline_in_reasoning_is_not_the_body_start(self):
        # Review round 2, case 1a.
        raw = (
            "I must use [CONTEXT SUMMARY] and include all five sections.\n"
            "Let me inspect each file.\n</think>\n" + SS_BODY
        )
        text, flags = memory.clean_summary_text(raw, memory.SS_OPEN_MARKER, memory.SS_CLOSE_MARKER)
        self.assertEqual(text, SS_BODY)
        self.assertTrue(flags["had_think_preamble"])

    def test_marker_block_quoted_inside_reasoning_is_skipped(self):
        # Review round 2, case 1c: the reasoning reproduces the whole format on
        # its own lines before closing; the real block follows </think>.
        quoted = "The format is:\n[CONTEXT SUMMARY]\n## Task\n<one sentence>\n[END CONTEXT SUMMARY]\nNow write it.\n</think>\n"
        text, flags = memory.clean_summary_text(quoted + SS_BODY, memory.SS_OPEN_MARKER, memory.SS_CLOSE_MARKER)
        self.assertEqual(text, SS_BODY)

    def test_unterminated_think_containing_marker_is_rejected(self):
        # Review round 2, case 1b.
        raw = "<think>Draft:\n[CONTEXT SUMMARY]\n## Task\nFix the bug\n[END CONTEXT SUMMARY]\nbut I should double-check"
        text, flags = memory.clean_summary_text(raw, memory.SS_OPEN_MARKER, memory.SS_CLOSE_MARKER)
        self.assertIsNone(text)
        self.assertEqual(flags["rejected"], "unterminated_reasoning")

    def test_marker_not_on_its_own_line_is_not_a_marker(self):
        raw = "[CONTEXT SUMMARY] ## Task\nFix the bug\n[END CONTEXT SUMMARY]"
        text, flags = memory.clean_summary_text(raw, memory.SS_OPEN_MARKER, memory.SS_CLOSE_MARKER)
        self.assertFalse(flags["had_open_marker"])
        self.assertTrue(text.startswith(memory.SS_OPEN_MARKER + "\n"))
        self.assertIn("Fix the bug", text)

    def test_trailing_text_after_close_marker_is_dropped(self):
        text, _ = memory.clean_summary_text(
            SS_BODY + "\n\nHope this helps!", memory.SS_OPEN_MARKER, memory.SS_CLOSE_MARKER
        )
        self.assertEqual(text, SS_BODY)

    def test_reasoning_only_response_is_rejected(self):
        # Review case 2a: "thinking...</think>" would otherwise become an empty
        # marker pair that replaces the history.
        text, flags = memory.clean_summary_text(
            "Let me think about the summary...</think>\n",
            memory.SS_OPEN_MARKER, memory.SS_CLOSE_MARKER,
        )
        self.assertIsNone(text)
        self.assertEqual(flags["rejected"], "empty_body")

    def test_empty_marked_block_is_rejected(self):
        text, flags = memory.clean_summary_text(
            f"{memory.SS_OPEN_MARKER}\n\n{memory.SS_CLOSE_MARKER}",
            memory.SS_OPEN_MARKER, memory.SS_CLOSE_MARKER,
        )
        self.assertIsNone(text)
        self.assertEqual(flags["rejected"], "empty_body")

    def test_unterminated_reasoning_is_rejected(self):
        # Review case 2b: an open <think> that never closes (e.g. max_tokens hit).
        text, flags = memory.clean_summary_text(
            "<think>Still working out which files were touched and",
            memory.SS_OPEN_MARKER, memory.SS_CLOSE_MARKER,
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

    def test_structured_summarize_cleans_and_tags(self):
        model = FakeModel(PREAMBLE + SS_BODY)
        msgs = history()
        result, saved, pt, ct, _ = memory.structured_summarize(msgs, model, 400)
        self.assertEqual(result[:2], msgs[:2])
        self.assertEqual(len(result), 3)
        self.assert_tagged_summary(result[2], memory.SS_OPEN_MARKER)
        self.assertEqual(result[2]["content"], SS_BODY)
        self.assertGreater(saved, 0)
        self.assertEqual((pt, ct), (100, 20))

    def test_summarize_cleans_and_tags(self):
        reply = PREAMBLE + f"{memory.SU_OPEN_MARKER}\nExamined file0.py through file5.py.\n{memory.SU_CLOSE_MARKER}"
        result, *_ = memory.summarize(history(), FakeModel(reply), 400)
        self.assert_tagged_summary(result[2], memory.SU_OPEN_MARKER)
        self.assertIn("Examined file0.py", result[2]["content"])
        self.assertEqual(result[2]["content"].count(memory.SU_OPEN_MARKER), 1)

    def test_ambiguous_reply_is_retried_then_accepted(self):
        marked = f"{memory.SU_OPEN_MARKER}\nExamined file0.py.\n{memory.SU_CLOSE_MARKER}"
        model = FakeModel([PREAMBLE + "Examined file0.py.", marked])
        result, *_ = memory.summarize(history(), model, 400)
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
        memory.summarize(history(), model, 400)
        self.assertIn(memory.SU_OPEN_MARKER, seen["prompt"])
        self.assertIn(memory.SU_CLOSE_MARKER, seen["prompt"])

    def test_partial_variants_keep_tail_and_tag_summary(self):
        for primitive, reply, marker in (
            (memory.structured_summarize_partial, PREAMBLE + SS_BODY, memory.SS_OPEN_MARKER),
            (memory.summarize_partial,
             PREAMBLE + f"{memory.SU_OPEN_MARKER}\nExamined files.\n{memory.SU_CLOSE_MARKER}",
             memory.SU_OPEN_MARKER),
        ):
            with self.subTest(primitive=primitive.__name__):
                msgs = history(8)
                result, saved, *_ = primitive(msgs, FakeModel(reply), 900)
                self.assertEqual(result[:2], msgs[:2])
                self.assert_tagged_summary(result[2], marker)
                self.assertEqual(result[-1], msgs[-1])  # verbatim tail kept
                self.assertGreater(saved, 0)

    def test_rejected_first_attempt_is_retried_once(self):
        model = FakeModel(["Let me think...</think>", PREAMBLE + SS_BODY])
        msgs = history()
        result, saved, pt, ct, _ = memory.structured_summarize(msgs, model, 400)
        self.assertEqual(model.calls, 2)
        self.assertEqual(result[2]["content"], SS_BODY)
        self.assertEqual(result[2]["extra"]["summary_format"]["attempts"], 2)
        self.assertEqual((pt, ct), (200, 40))  # usage summed over attempts
        self.assertGreater(saved, 0)

    def test_all_attempts_rejected_falls_back_to_truncate(self):
        for primitive in (memory.structured_summarize, memory.summarize,
                          memory.structured_summarize_partial, memory.summarize_partial):
            with self.subTest(primitive=primitive.__name__):
                model = FakeModel("<think>never finishes")
                msgs = history()
                result, saved, pt, ct, _ = primitive(msgs, model, 400)
                self.assertEqual(model.calls, memory.SUMMARY_MAX_ATTEMPTS)
                self.assertEqual(result[:2], msgs[:2])
                # No summary was inserted; the history was truncated instead.
                self.assertFalse(any(memory.is_summary_message(m) for m in result))
                self.assertTrue(all(m in msgs for m in result))
                self.assertLessEqual(memory.count_tokens(result), 400)
                self.assertGreater(saved, 0)
                self.assertEqual(pt, 100 * memory.SUMMARY_MAX_ATTEMPTS)

    def test_outcome_record_after_fallback(self):
        memory.pop_summary_outcome()  # clear
        model = FakeModel(["<think>never finishes", "...</think>"])
        memory.structured_summarize(history(), model, 400)
        outcome = memory.pop_summary_outcome()
        self.assertEqual(outcome["attempts"], memory.SUMMARY_MAX_ATTEMPTS)
        self.assertFalse(outcome["accepted"])
        self.assertEqual(outcome["rejections"], ["unterminated_reasoning", "empty_body"][:memory.SUMMARY_MAX_ATTEMPTS])
        self.assertEqual(outcome["fallback"], "truncate")
        self.assertIsNone(memory.pop_summary_outcome())  # popped once only

    def test_outcome_record_after_retry_success(self):
        memory.pop_summary_outcome()
        memory.summarize_partial(
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

    def test_no_outcome_without_summary_request(self):
        memory.pop_summary_outcome()
        memory.tool_result_clear(history(), 1, fallback_truncate=False)
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
            _mem_trc_fallback_events = 0
            _mem_online_trc_flags = []
            _mem_online_trc_tokens_saved = 0
            _mem_summary_outcomes = [
                {"step": 12, "primitive": "structured_summarize", "attempts": 2,
                 "accepted": False, "rejections": ["empty_body", "ambiguous_reasoning"],
                 "fallback": "truncate"},
                {"step": 30, "primitive": "structured_summarize", "attempts": 1,
                 "accepted": True, "rejections": [], "fallback": None},
            ]

        data = memory.token_log_dict(Agent())
        self.assertEqual(data["summary_fallback_events"], 1)
        self.assertEqual(len(data["summary_outcomes"]), 2)
        del Agent._mem_summary_outcomes  # agents predating the field
        self.assertEqual(memory.token_log_dict(Agent())["summary_fallback_events"], 0)

    def test_max_attempts_override(self):
        model = FakeModel("...</think>")
        text, flags, *_ = memory.request_summary(
            model, [], memory.SS_OPEN_MARKER, memory.SS_CLOSE_MARKER, max_attempts=3
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

        result, *_ = memory.structured_summarize(history(), ExtraModel(SS_BODY), 400)
        self.assertEqual(result[2]["extra"]["uid"], "u00042")
        self.assertEqual(result[2]["extra"]["kind"], memory.SUMMARY_KIND)


class TrcProtectionTests(unittest.TestCase):
    """Reproduces the audit's local check: a summary followed by more turns,
    then TRC with an unreachable target, must never clear the summary."""

    def continued(self, summary_msg):
        msgs = history(2)[:2] + [summary_msg]
        for i in range(6):
            msgs.append({"role": "assistant", "content": f"```bash\ncat more{i}.py\n```"})
            msgs.append({"role": "user", "content": f"more{i} output\n" * 40})
        return msgs

    def check_protected(self, summary_msg):
        msgs = self.continued(summary_msg)
        # Unreachable target, no truncate fallback: every eligible output is cleared.
        out, _, used_fallback = memory.tool_result_clear(list(msgs), 1, fallback_truncate=False)
        self.assertFalse(used_fallback)
        self.assertEqual(out[2], summary_msg)
        cleared = [m for m in out[3:] if m["content"].startswith("[TOOL OUTPUT CLEARED")]
        self.assertTrue(cleared, "TRC should still clear ordinary tool output")
        # Scored TRC always falls back to truncate() when clearing is not enough,
        # so give it a target that clearing alone can reach.
        reachable = memory.count_tokens(out)
        out2, _, used_fallback = memory.scored_tool_result_clear(list(msgs), reachable)
        self.assertFalse(used_fallback)
        self.assertEqual(out2[2], summary_msg)
        self.assertTrue(any(m["content"].startswith("[TOOL OUTPUT CLEARED") for m in out2[3:]))

    def test_tagged_summary_is_protected_even_without_marker(self):
        # Structural tag alone protects (e.g. a future format without markers).
        self.check_protected(
            {"role": "user", "content": "free-form summary text", "extra": {"kind": memory.SUMMARY_KIND}}
        )

    def test_legacy_marker_summary_is_protected(self):
        self.check_protected({"role": "user", "content": SS_BODY})
        self.check_protected(
            {"role": "user", "content": f"{memory.SU_OPEN_MARKER}\nold prose\n{memory.SU_CLOSE_MARKER}"}
        )

    def test_new_pipeline_summary_is_protected(self):
        result, *_ = memory.structured_summarize(history(), FakeModel(PREAMBLE + SS_BODY), 400)
        self.check_protected(result[2])

    def test_untagged_preamble_summary_is_the_old_bug(self):
        # Documents the failure mode the cleaning removes: without the tag and
        # with the preamble, both TRC variants treat the summary as tool output.
        msgs = self.continued({"role": "user", "content": PREAMBLE + SS_BODY})
        out, *_ = memory.tool_result_clear(list(msgs), 1, fallback_truncate=False)
        self.assertTrue(out[2]["content"].startswith("[TOOL OUTPUT CLEARED"))


if __name__ == "__main__":
    unittest.main()
