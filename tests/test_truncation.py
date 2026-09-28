"""Standalone TR: budget-relative targets and complete-turn retention.

Exercise the actual agent hook without model or environment API calls.
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

import memory
from minisweagent.agents.default import DefaultAgent


def history(n=6):
    messages = [{'role': 'system', 'content': 'system'}, {'role': 'user', 'content': 'task'}]
    for i in range(n):
        messages.extend([
            {'role': 'assistant', 'content': f'command {i} ' * 20},
            {'role': 'user', 'content': f'output {i} ' * 40,
             'extra': {'returncode': 0}},
        ])
    return messages


class RecordingModel:
    def __init__(self):
        self.inputs = []

    def query(self, messages):
        self.inputs.append(copy.deepcopy(messages))
        return {'role': 'assistant', 'content': 'next command', 'extra': {'cost': 0}}


class TruncationTests(unittest.TestCase):
    def setUp(self):
        env = patch.dict(os.environ, {'MSWEA_PRIMITIVE': 'truncation'}, clear=True)
        env.start()
        self.addCleanup(env.stop)

    def agent(self, messages, budget):
        os.environ['MSWEA_TOKEN_BUDGET'] = str(budget)
        model = RecordingModel()
        agent = DefaultAgent(model, object(), system_template='system', instance_template='task', cost_limit=0)
        agent.add_messages(*copy.deepcopy(messages))
        return agent, model

    def test_budget_relative_target_with_large_overshoot_and_event_log(self):
        messages = history(16)
        for ratio in (0.3, 0.5, 0.7):
            with self.subTest(ratio=ratio), tempfile.TemporaryDirectory() as directory:
                os.environ['MSWEA_EVENT_LOG_DIR'] = directory
                budget = 1100
                agent, model = self.agent(messages, budget)
                original = copy.deepcopy(agent.messages)
                target = int(budget * ratio)
                self.assertGreater(memory.count_tokens(original), 2 * budget)
                with patch.object(memory, 'COMPRESSION_RATIO', ratio):
                    agent.query()
                sent = model.inputs[0]
                self.assertLessEqual(memory.count_tokens(sent), target)
                self.assertEqual(sent[:2], original[:2])
                self.assertEqual(sent[2:], original[-(len(sent) - 2):])
                self.assertEqual(sent[2]['role'], 'assistant')
                # The next older complete turn would not fit: no unnecessary loss.
                next_turn = original[-(len(sent) - 2) - 2:-(len(sent) - 2)]
                self.assertGreater(memory.count_tokens(sent + next_turn), target)
                event = json.loads((Path(directory) / 'compression_events.jsonl').read_text())
                self.assertEqual(event['target_tokens'], target)
                self.assertEqual(event['budget'], budget)
                self.assertEqual(agent._mem_tokens_saved,
                                 memory.count_tokens(original) - memory.count_tokens(sent))

    def test_boundary_never_keeps_result_without_its_command(self):
        messages = history(3)
        # Legacy deletion would stop after dropping only the first command.
        target = memory.count_tokens(messages[:2] + messages[3:])
        agent, model = self.agent(messages, target + 1)
        expected = copy.deepcopy(agent.messages[:2] + agent.messages[4:])
        with patch.object(memory, 'COMPRESSION_RATIO', target / (target + 1)):
            agent.query()
        self.assertEqual(model.inputs, [expected])

    def test_parallel_results_and_feedback_travel_with_their_command(self):
        messages = history(0)
        for turn in range(3):
            ids = [f'{turn}-{i}' for i in range(2)]
            messages.append({'role': 'assistant', 'content': f'command {turn}',
                             'tool_calls': [{'id': id_} for id_ in ids]})
            messages.extend({'role': 'tool', 'tool_call_id': id_, 'content': 'output ' * 100}
                            for id_ in ids)
            messages.append({'role': 'user', 'content': 'retry',
                             'extra': {'interrupt_type': 'FormatError'}})
        messages.insert(2, {'role': 'user', 'content': 'summary', 'extra': {'kind': 'summary'}})
        target = memory.count_tokens(messages[:2] + messages[-4:])
        agent, model = self.agent(messages, 2 * target)
        expected = copy.deepcopy(agent.messages[:2] + agent.messages[-4:])
        with patch.object(memory, 'COMPRESSION_RATIO', 0.5):
            agent.query()
        self.assertEqual(model.inputs, [expected])

    def test_unattainable_target_keeps_protected_head_and_latest_turn(self):
        for large_part in (0, 1, -1):
            with self.subTest(large_part=large_part):
                messages = history(3)
                messages[large_part]['content'] = 'large protected content ' * 1000
                agent, model = self.agent(messages, 100)
                expected = copy.deepcopy(agent.messages[:2] + agent.messages[-2:])
                with patch.object(memory, 'COMPRESSION_RATIO', 0.5):
                    agent.query()
                self.assertEqual(model.inputs, [expected])
                self.assertGreater(memory.count_tokens(model.inputs[0]), 100)
                self.assertEqual(agent._mem_compression_events, 1)

    def test_no_deletion_when_only_protected_head_and_latest_turn_remain(self):
        agent, model = self.agent(history(1), 1)
        expected = copy.deepcopy(agent.messages)
        agent.query()
        self.assertEqual(model.inputs, [expected])
        self.assertEqual(agent._mem_tokens_saved, 0)

    def test_at_budget_does_not_trigger_even_if_above_ratio_target(self):
        messages = history(3)
        agent, model = self.agent(messages, memory.count_tokens(messages))
        expected = copy.deepcopy(agent.messages)
        with patch.object(memory, 'COMPRESSION_RATIO', 0.5):
            agent.query()
        self.assertEqual(model.inputs, [expected])
        self.assertEqual(agent._mem_compression_events, 0)

    def test_diagnostic_flags_and_exact_boundaries(self):
        latest_tokens = memory.count_tokens(history(1))
        # All histories have equal-sized turns; the retained latest turn has this size.
        cases = [
            ('exact_target', 3, latest_tokens * 2, (False, False, False)),
            ('target_only', 3, latest_tokens + latest_tokens // 2, (True, False, False)),
            ('exact_budget', 3, latest_tokens, (True, False, False)),
            ('over_budget', 3, latest_tokens - 1, (True, True, False)),
            ('no_progress', 1, latest_tokens - 1, (True, True, True)),
        ]
        for name, turns, budget, flags in cases:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                path = Path(directory)
                os.environ['MSWEA_EVENT_LOG_DIR'] = directory
                os.environ['MSWEA_TOKEN_LOG_PATH'] = str(path / 'token_log.json')
                agent, model = self.agent(history(turns), budget)
                with patch.object(memory, 'COMPRESSION_RATIO', 0.5):
                    agent.query()
                log = json.loads((path / 'token_log.json').read_text())
                self.assertEqual(len(log['tr_events']), 1)
                event = log['tr_events'][0]
                self.assertEqual(event['tokens_after'], latest_tokens)
                self.assertEqual(event['tokens_after'], memory.count_tokens(model.inputs[0]))
                self.assertEqual(event['target_tokens'], budget // 2)
                self.assertEqual(event['budget_tokens'], budget)
                self.assertEqual(event['tokens_saved'], event['tokens_before'] - event['tokens_after'])
                self.assertEqual(event['tokens_saved'], log['total_tokens_saved'])
                for key, expected in zip(('target_not_met', 'budget_exceeded', 'zero_reduction'), flags):
                    self.assertIs(event[key], expected)
                    self.assertEqual(log[f'tr_{key}_events'], int(expected))
                compression = json.loads((path / 'compression_events.jsonl').read_text())
                self.assertEqual(compression['tr_stats'], event)

    def test_diagnostics_saved_before_failed_model_call_and_accumulate(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            os.environ['MSWEA_EVENT_LOG_DIR'] = directory
            os.environ['MSWEA_TOKEN_LOG_PATH'] = str(path / 'token_log.json')
            agent, model = self.agent(history(3), 1)
            def fail(messages):
                # Check durability inside the model call, before failure handling.
                log = json.loads((path / 'token_log.json').read_text())
                event = log['tr_events'][-1]
                self.assertEqual(event['tokens_after'], memory.count_tokens(messages))
                self.assertTrue(event['target_not_met'])
                self.assertTrue(event['budget_exceeded'])
                compression = json.loads((path / 'compression_events.jsonl').read_text().splitlines()[-1])
                self.assertEqual(compression['tr_stats'], event)
                raise RuntimeError('model request failed')
            with patch.object(model, 'query', side_effect=fail):
                for _ in range(2):
                    with self.assertRaisesRegex(RuntimeError, 'model request failed'):
                        agent.query()
            log = json.loads((path / 'token_log.json').read_text())
            self.assertEqual(log['compression_events'], 2)
            self.assertEqual(log['tr_target_not_met_events'], 2)
            self.assertEqual(log['tr_budget_exceeded_events'], 2)
            self.assertEqual(log['tr_zero_reduction_events'], 1)
            self.assertEqual([e['zero_reduction'] for e in log['tr_events']], [False, True])
            self.assertEqual([e['step'] for e in log['tr_events']], [0, 1])

    def test_no_tr_invocation_has_empty_diagnostics(self):
        for primitive in ('truncation', 'tool_result_clear'):
            with self.subTest(primitive=primitive):
                os.environ['MSWEA_PRIMITIVE'] = primitive
                agent, _ = self.agent(history(), 100000 if primitive == 'truncation' else 1)
                agent.query()
                log = memory.token_log_dict(agent)
                self.assertEqual(log['tr_events'], [])
                for key in ('target_not_met', 'budget_exceeded', 'zero_reduction'):
                    self.assertEqual(log[f'tr_{key}_events'], 0)

    def test_other_summary_targets_remain_current_relative(self):
        for primitive, function in [
            ('summarization', 'summarize'),
            ('structured_summarize', 'structured_summarize'),
            ('summarization_partial', 'summarize_partial'),
            ('structured_summarize_partial', 'structured_summarize_partial'),
            ('summarization_free', 'summarize_free'),
            ('structured_summarize_free', 'structured_summarize_free'),
        ]:
            with self.subTest(primitive=primitive):
                os.environ['MSWEA_PRIMITIVE'] = primitive
                agent, _ = self.agent(history(), 300)
                current = memory.count_tokens(agent.messages)
                result = agent.messages[:2] + [{'role': 'user', 'content': 'summary'}]
                with patch.object(memory, 'COMPRESSION_RATIO', 0.5), patch.object(
                    memory, function, return_value=(result, current - memory.count_tokens(result), 0, 0, 0.0)
                ) as summarize:
                    agent.query()
                self.assertEqual(summarize.call_args.args[2], int(current * 0.5))

    def test_online_and_staggered_tr_keep_legacy_deletion_and_targets(self):
        for primitive, budget in [('online_trc', 300), ('staggered_alternate', 10000)]:
            with self.subTest(primitive=primitive):
                os.environ['MSWEA_PRIMITIVE'] = primitive
                messages = history(3)  # Inside online clearing's freeze window.
                messages[2]['content'] = 'large old command ' * 12000
                agent, model = self.agent(messages, budget)
                target = memory.count_tokens(agent.messages) // 2
                expected, _ = memory.truncate(agent.messages, target)
                with patch.object(memory, 'COMPRESSION_RATIO', 0.5), patch.object(
                    memory, 'truncate', wraps=memory.truncate
                ) as truncate:
                    agent.query()
                self.assertEqual(truncate.call_args.args[1], target)
                self.assertEqual(model.inputs, [expected])
                self.assertEqual(expected[2]['role'], 'user')


if __name__ == '__main__':
    unittest.main()
