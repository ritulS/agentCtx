"""TRC contract and real DefaultAgent hook tests; no model server required.

Run with: venv/bin/python -m unittest discover -s tests -p test_trc.py
"""
import copy
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT, ROOT / 'src', ROOT / 'mini-swe-agent' / 'src'):
    sys.path.insert(0, str(path))

try:
    import memory
    from minisweagent.agents.default import DefaultAgent
except ImportError as exc:
    raise unittest.SkipTest(str(exc))


def history(n=8, result_words=100, assistant_words=1):
    messages = [{'role': 'system', 'content': 'system'}, {'role': 'user', 'content': 'task'}]
    # The agent tags each message with the 1-based call index it was added at
    # (extra["uid_step"]); result i follows call i + 1.
    for i in range(n):
        messages.extend([
            {'role': 'assistant', 'content': f'command {i} ' * assistant_words,
             'extra': {'actions': [{'command': f'echo {i}'}]}},
            {'role': 'user', 'content': f'output {i} ' * result_words,
             'extra': {'raw_output': f'raw {i}', 'returncode': 0, 'uid_step': i + 1}},
        ])
    return messages


class TrcTests(unittest.TestCase):
    def test_clears_all_old_results_even_after_budget_is_met(self):
        messages = history()
        original = copy.deepcopy(messages)
        budget = memory.count_tokens(messages) - 1
        stats = {}
        out, saved, fallback = memory.tool_result_clear(messages, budget, stats=stats)
        self.assertEqual(messages, original)
        self.assertEqual(out[:2], messages[:2])
        self.assertEqual(out[-6:], messages[-6:])
        self.assertEqual(stats['cleared_results'], 5)
        self.assertFalse(fallback)
        self.assertEqual(saved, memory.count_tokens(messages) - memory.count_tokens(out))
        self.assertEqual(stats['clearing_tokens_saved'], saved)
        for i in range(8):
            self.assertEqual(out[2 + 2*i], messages[2 + 2*i])
            self.assertEqual(out[3 + 2*i]['content'].startswith('[TOOL OUTPUT CLEARED'), i < 5)

    def test_early_returns_always_have_three_values(self):
        for messages, budget in [(history(0), 100), (history(0), 1), (history(), 99999), ([], 1)]:
            with self.subTest(length=len(messages), budget=budget):
                out, saved, fallback = memory.tool_result_clear(messages, budget)
                self.assertEqual(out, messages)
                self.assertEqual(saved, 0)
                self.assertEqual(fallback, memory.count_tokens(messages) > budget)

    def test_exact_budget_does_not_trigger(self):
        messages = history()
        out, saved, fallback = memory.tool_result_clear(messages, memory.count_tokens(messages))
        self.assertEqual(out, messages)
        self.assertEqual((saved, fallback), (0, False))

    def test_only_tool_results_count_towards_keep(self):
        messages = history(6)
        feedback = {'role': 'user', 'content': 'bad format', 'extra': {'interrupt_type': 'FormatError'}}
        summary = {'role': 'user', 'content': 'summary', 'extra': {'kind': 'summary'}}
        messages.insert(4, feedback)
        messages.insert(5, summary)
        messages.extend([feedback, summary, {'role': 'user', 'content': 'human clarification'}])
        stats = {}
        out, _, _ = memory.tool_result_clear(messages, 1, False, stats=stats)
        self.assertEqual(stats['cleared_results'], 3)
        self.assertEqual(out[4:6], messages[4:6])
        self.assertEqual(out[-3:], messages[-3:])
        retained = [m for m in out if m.get('extra', {}).get('raw_output') and not m['content'].startswith('[TOOL OUTPUT CLEARED')]
        self.assertEqual([m['extra']['raw_output'] for m in retained], ['raw 3', 'raw 4', 'raw 5'])

    def test_legacy_alternating_history_is_supported(self):
        messages = history(5)
        for msg in messages:
            msg.pop('extra', None)
        stats = {}
        out, _, _ = memory.tool_result_clear(messages, 1, False, stats=stats)
        self.assertEqual(stats['cleared_results'], 2)
        self.assertIn('step unknown]', out[3]['content'])

    def test_original_step_survives_truncation_and_feedback(self):
        messages = history(8)
        for i, msg in enumerate(messages[2:]):
            msg['extra']['uid_step'] = 115 + i // 2
        # Remove three oldest turns, then insert parser feedback. Neither the
        # new position nor alternating-message arithmetic identifies the step.
        retained = messages[:2] + messages[8:]
        messages, _ = memory.truncate_oldest_turns(messages, memory.count_tokens(retained))
        self.assertEqual(messages, retained)
        messages.insert(2, {'role': 'user', 'content': 'retry',
                            'extra': {'interrupt_type': 'FormatError'}})
        original = copy.deepcopy(messages)
        out, _, _ = memory.tool_result_clear(messages, 1, False)
        cleared = [m for m in out if m['content'].startswith('[TOOL OUTPUT CLEARED')]
        self.assertEqual([m['extra']['uid_step'] for m in cleared], [118, 119])
        for msg, step in zip(cleared, (118, 119)):
            self.assertIn(f'step {step}]', msg['content'])
        self.assertEqual(messages, original)

    def test_repeated_clearing_is_idempotent_and_counts_stubs_in_window(self):
        messages = history(6)
        # A previously cleared recent result still occupies a result slot.
        messages[-1]['content'] = '[tool-result cleared — online-trc]'
        first_stats = {}
        first, _, _ = memory.tool_result_clear(messages, 1, False, stats=first_stats)
        second_stats = {}
        second, saved, _ = memory.tool_result_clear(first, 1, False, stats=second_stats)
        self.assertEqual(first_stats['cleared_results'], 3)
        self.assertEqual(first, second)
        self.assertEqual(saved, 0)
        self.assertEqual(second_stats['cleared_results'], 0)

    def test_short_results_report_net_growth(self):
        messages = history(6, result_words=0)
        stats = {}
        out, saved, _ = memory.tool_result_clear(messages, 1, False, stats=stats)
        self.assertLess(saved, 0)
        self.assertEqual(saved, memory.count_tokens(messages) - memory.count_tokens(out))
        self.assertEqual(saved, stats['clearing_tokens_saved'])

    def test_fallback_stops_at_budget_and_preserves_pairs(self):
        messages = history(6, assistant_words=80)
        cleared, _, _ = memory.tool_result_clear(messages, 1, False)
        # Exactly one complete old turn has to go.
        expected = cleared[:2] + cleared[4:]
        budget = memory.count_tokens(expected)
        stats = {}
        out, saved, fallback = memory.tool_result_clear(messages, budget, stats=stats)
        self.assertEqual(out, expected)
        self.assertTrue(fallback)
        self.assertGreater(stats['truncation_tokens_saved'], 0)
        self.assertEqual(saved, stats['clearing_tokens_saved'] + stats['truncation_tokens_saved'])

    def test_fallback_can_retain_fewer_than_three_results(self):
        messages = history(6)
        expected = messages[:2] + messages[-2:]
        stats = {}
        out, _, fallback = memory.tool_result_clear(messages, memory.count_tokens(expected), stats=stats)
        self.assertTrue(fallback)
        self.assertEqual(out, expected)
        self.assertFalse(stats['budget_exceeded_after_trc'])

    def test_unattainable_budget_preserves_latest_pair_and_reports_overflow(self):
        messages = history(6)
        stats = {}
        out, _, fallback = memory.tool_result_clear(messages, 1, stats=stats)
        self.assertTrue(fallback)
        self.assertEqual(out, messages[:2] + messages[-2:])
        self.assertTrue(stats['budget_exceeded_after_trc'])

    def test_parallel_tool_results_are_removed_with_their_call(self):
        messages = history(0)
        for turn in range(3):
            ids = [f'{turn}-{i}' for i in range(2)]
            messages.append({'role': 'assistant', 'content': f'call {turn}',
                             'tool_calls': [{'id': id_} for id_ in ids]})
            messages.extend({'role': 'tool', 'tool_call_id': id_, 'content': 'output ' * 100} for id_ in ids)
        feedback = {'role': 'user', 'content': 'bad format', 'extra': {'interrupt_type': 'FormatError'}}
        messages.insert(5, feedback)
        expected = messages[:2] + messages[-3:]
        out, _, _ = memory.tool_result_clear(messages, memory.count_tokens(expected))
        self.assertEqual(out, expected)
        self.assertEqual([m['tool_call_id'] for m in out if m['role'] == 'tool'], ['2-0', '2-1'])

    def test_multiblock_result_is_cleared(self):
        messages = history(5)
        messages[3]['content'] = [{'type': 'text', 'text': 'large output ' * 100}]
        out, _, _ = memory.tool_result_clear(messages, 1, False)
        self.assertTrue(out[3]['content'].startswith('[TOOL OUTPUT CLEARED'))

    def test_leading_summary_and_format_feedback_do_not_split_pairs(self):
        messages = history(3)
        messages.insert(2, {'role': 'user', 'content': 'summary', 'extra': {'kind': 'summary'}})
        messages.insert(5, {'role': 'user', 'content': 'retry', 'extra': {'interrupt_type': 'FormatError'}})
        expected = messages[:2] + messages[-2:]
        out, _ = memory.truncate_oldest_turns(messages, memory.count_tokens(expected))
        self.assertEqual(out, expected)


class RecordingModel:
    def __init__(self):
        self.inputs = []

    def query(self, messages):
        self.inputs.append(copy.deepcopy(messages))
        return {'role': 'assistant', 'content': 'next command', 'extra': {'cost': 0}}


class TrcAgentTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {}, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)
        os.environ['MSWEA_PRIMITIVE'] = 'tool_result_clear'

    def agent(self, messages, budget):
        os.environ['MSWEA_TOKEN_BUDGET'] = str(budget)
        model = RecordingModel()
        agent = DefaultAgent(model, object(), system_template='system', instance_template='task', cost_limit=0)
        agent.add_messages(*copy.deepcopy(messages))
        return agent, model

    def test_hook_ignores_ratio_and_logs_separate_stages(self):
        messages = history(6, assistant_words=80)
        cleared, _, _ = memory.tool_result_clear(messages, 1, False)
        budget = memory.count_tokens(cleared[:2] + cleared[4:])
        contexts = []
        for ratio in (0.3, 0.5, 0.7):
            agent, model = self.agent(messages, budget)
            with patch.object(memory, 'COMPRESSION_RATIO', ratio):
                agent.query()
            contexts.append(model.inputs[0])
            log = memory.token_log_dict(agent)
            self.assertEqual(log['trc_truncation_fallback_events'], 1)
            self.assertEqual(log['trc_clear_only_events'], 0)
            self.assertEqual(log['total_tokens_saved'], log['trc_clearing_tokens_saved'] + log['trc_truncation_tokens_saved'])
            self.assertEqual(log['context_tokens_after_compression'], [budget])
        self.assertEqual(contexts[0], contexts[1])
        self.assertEqual(contexts[1], contexts[2])

    def test_clear_only_does_not_truncate_to_half(self):
        messages = history(6, assistant_words=80)
        cleared, _, _ = memory.tool_result_clear(messages, 1, False)
        budget = memory.count_tokens(cleared)
        self.assertGreater(budget, memory.count_tokens(messages) // 2)
        agent, model = self.agent(messages, budget)
        agent.query()
        self.assertEqual(len(model.inputs[0]), len(messages))
        log = memory.token_log_dict(agent)
        self.assertEqual(log['trc_clear_only_events'], 1)
        self.assertEqual(log['trc_truncation_fallback_events'], 0)

    def test_impossible_budget_continues_with_latest_turn_and_logs_overflow(self):
        with tempfile.TemporaryDirectory() as directory:
            os.environ['MSWEA_TOKEN_LOG_PATH'] = str(Path(directory) / 'tokens.json')
            os.environ['MSWEA_EVENT_LOG_DIR'] = directory
            messages = history(6)
            agent, model = self.agent(messages, 1)
            expected = copy.deepcopy(agent.messages[:2] + agent.messages[-2:])
            agent.query()
            self.assertEqual(model.inputs, [expected])
            self.assertEqual(agent.n_calls, 1)
            self.assertEqual(agent.messages[-1]['content'], 'next command')
            log = json.loads((Path(directory) / 'tokens.json').read_text())
            self.assertTrue(log['trc_events'][0]['budget_exceeded_after_trc'])
            self.assertEqual(log['trc_truncation_fallback_events'], 1)
            self.assertEqual(log['trc_clear_only_events'], 0)
            event = json.loads((Path(directory) / 'compression_events.jsonl').read_text())
            self.assertEqual(event['target_tokens'], 1)
            self.assertTrue(event['trc_stats']['budget_exceeded_after_trc'])
            self.assertEqual(event['trc_stats']['tokens_after_trc'], log['context_tokens_after_compression'][0])

    def test_overflow_is_persisted_even_if_model_call_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            log_path = Path(directory) / 'tokens.json'
            os.environ['MSWEA_TOKEN_LOG_PATH'] = str(log_path)
            messages = history(6)
            agent, model = self.agent(messages, 1)
            expected = copy.deepcopy(agent.messages[:2] + agent.messages[-2:])
            with patch.object(model, 'query', side_effect=RuntimeError('model request failed')) as query:
                with self.assertRaisesRegex(RuntimeError, 'model request failed'):
                    agent.query()
            query.assert_called_once_with(expected)
            log = json.loads(log_path.read_text())
            self.assertTrue(log['trc_events'][0]['budget_exceeded_after_trc'])
            self.assertEqual(log['compression_events'], 1)

    def test_stacked_policies_share_clear_all_and_skip_unneeded_summary(self):
        messages = history(6, assistant_words=80)
        cleared, _, _ = memory.tool_result_clear(messages, 1, False)
        budget = memory.count_tokens(cleared)
        for primitive, summary_fn in [('trc_summarize', 'summarize'), ('trc_structured_summarize', 'structured_summarize')]:
            with self.subTest(primitive=primitive):
                agent, model = self.agent(messages, budget)
                os.environ['MSWEA_PRIMITIVE'] = primitive
                with patch.object(memory, summary_fn) as summarize:
                    agent.query()
                summarize.assert_not_called()
                self.assertEqual(len(model.inputs[0]), len(messages))
                self.assertEqual(agent._mem_trc_events[0]['cleared_results'], 3)

    def test_stacked_summary_receives_cleared_history_when_still_over_budget(self):
        messages = history(6, assistant_words=80)
        for primitive, summary_fn in [('trc_summarize', 'summarize'), ('trc_structured_summarize', 'structured_summarize')]:
            with self.subTest(primitive=primitive):
                agent, model = self.agent(messages, 100)
                os.environ['MSWEA_PRIMITIVE'] = primitive
                def summarize(msgs, model, target):
                    self.assertEqual(sum(m['content'].startswith('[TOOL OUTPUT CLEARED') for m in msgs), 3)
                    result = msgs[:2] + [{'role': 'user', 'content': '[CONTEXT SUMMARY] compact'}]
                    return result, memory.count_tokens(msgs) - memory.count_tokens(result), 0, 0, 0.0
                with patch.object(memory, summary_fn, side_effect=summarize) as summarizer:
                    agent.query()
                summarizer.assert_called_once()
                self.assertEqual(agent._mem_trc_fallback_events, 0)
                self.assertTrue(agent._mem_trc_events[0]['budget_exceeded_after_trc'])


if __name__ == '__main__':
    unittest.main()
