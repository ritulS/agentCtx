"""Adaptive policies exercise the real query hook without external model calls."""
import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT, ROOT / 'src', ROOT / 'mini-swe-agent' / 'src'):
    sys.path.insert(0, str(path))

from agentctx.compression.adaptive import (
    CompressionConfig as Config, CompressionSchedule, resolve_policy,
)

try:
    import memory
    from minisweagent.agents.default import DefaultAgent
    from test_truncation import RecordingModel, history
except ImportError as exc:
    raise unittest.SkipTest(str(exc)) from exc


class AdaptiveCompressionTests(unittest.TestCase):
    def setUp(self):
        env = patch.dict(os.environ, {}, clear=True)
        env.start()
        self.addCleanup(env.stop)

    def agent(self, config=None, policy=None, messages=None):
        model = RecordingModel()
        agent = DefaultAgent(model, object(), system_template='system', instance_template='task',
                             cost_limit=0, memory_config=config, memory_policy=policy)
        agent.add_messages(*copy.deepcopy(history() if messages is None else messages))
        return agent, model

    def test_switch_primitive_budget_and_depth_on_next_query(self):
        configs = [Config('truncation', 1100, .7), Config('summarization', 700, .3),
                   Config('tool_result_clear', 800, .9)]
        agent, model = self.agent(policy=CompressionSchedule(configs), messages=history(16))
        agent.query()
        self.assertEqual(agent._mem_tr_events[0]['target_tokens'], 770)
        self.assertEqual(len(agent._mem_adaptive_events), 1)  # no immediate cascade
        agent.add_messages(*history(4)[2:])
        before = memory.count_tokens(agent.messages)
        def summarize(messages, model, target):
            self.assertEqual(target, int(before * .3))
            return messages[:2] + messages[-2:], 100, 0, 0, 0.0
        with patch.object(memory, 'summarize', side_effect=summarize) as summary:
            agent.query()
            summary.assert_called_once()
        agent.add_messages(*history(6)[2:])
        agent.query()
        self.assertEqual(agent._mem_trc_events[-1]['budget_tokens'], 800)
        self.assertEqual([e['config'] for e in agent._mem_adaptive_events],
                         [c.to_dict() for c in configs])
        self.assertEqual(agent._memory_config, configs[-1])
        self.assertEqual(len(model.inputs), 3)

    def test_new_budget_changes_next_trigger_and_equality_does_not_fire(self):
        seen = []
        initial = Config('truncation', 1)
        def policy(event):
            seen.append(event)
            return Config('truncation', event.tokens_after, .7)
        agent, _ = self.agent(initial, policy)
        agent.query()
        agent.messages.pop()  # remove model response to test exact trigger boundary
        agent.query()  # history is exactly at new budget
        self.assertEqual(len(seen), 1)
        agent.add_messages(*history(1)[2:])
        agent.query()
        self.assertEqual(len(seen), 2)
        self.assertEqual(seen[1].config.depth, .7)

    def test_no_callback_without_trigger(self):
        agent, _ = self.agent(Config('truncation', 999999), lambda e: self.fail('unexpected trigger'))
        agent.query()
        self.assertEqual(agent._mem_adaptive_events, [])

    def test_none_retains_config_and_event_history_is_isolated(self):
        config = Config('truncation', 1)
        events = []
        def policy(event):
            events.append(event)
            event.messages[0]['content'] = 'mutated'
            event.messages[0]['extra']['uid'] = 'mutated'
        agent, model = self.agent(config, policy)
        agent.query()
        agent.query()
        self.assertEqual(agent._memory_config, config)
        self.assertEqual([e.index for e in events], [1, 2])
        self.assertEqual(events[0].tokens_saved, events[0].tokens_before - events[0].tokens_after)
        self.assertEqual(model.inputs[0][0]['content'], 'system')
        self.assertNotEqual(model.inputs[0][0]['extra']['uid'], 'mutated')

    def test_agent_settings_do_not_leak_to_another_agent_or_globals(self):
        global_ratio = memory.COMPRESSION_RATIO
        schedule = CompressionSchedule([Config('truncation', 1100, .3), Config('truncation', 800, .7)])
        first, _ = self.agent(policy=schedule, messages=history(16))
        second, _ = self.agent(policy=schedule, messages=history(16))
        first.query()
        self.assertEqual(second._memory_config, schedule.initial)
        second.query()
        self.assertEqual(first._mem_tr_events[0]['target_tokens'], 330)
        self.assertEqual(second._mem_tr_events[0]['target_tokens'], 330)
        self.assertEqual(memory.COMPRESSION_RATIO, global_ratio)
        self.assertNotIn('MSWEA_PRIMITIVE', os.environ)

    def test_online_trigger_and_switch_out_of_online_family(self):
        events = []
        def policy(event):
            events.append(event)
            return Config('truncation', 100000)
        agent, _ = self.agent(Config('online_trc', 100000, freeze_k=1), policy, history(2))
        agent.query()
        self.assertEqual([e.kind for e in events], ['online_trc'])
        agent.add_messages(*history(4)[2:])
        agent.query()
        self.assertEqual(len(events), 1)

    def test_switch_into_online_family_uses_new_freeze_window(self):
        agent, _ = self.agent(policy=CompressionSchedule([
            Config('truncation', 1), Config('online_trc', 100000, freeze_k=0),
        ]))
        agent.query()
        self.assertEqual(len(agent._mem_online_trc_flags), 0)
        agent.query()
        self.assertEqual(len(agent._mem_online_trc_flags), 1)
        self.assertEqual(agent._mem_adaptive_events[-1]['kind'], 'online_trc')

    def test_online_and_budget_events_keep_query_snapshot(self):
        first = Config('online_trc', 100, .7, freeze_k=1)
        second = Config('summarization', 100000, .3)
        third = Config('truncation', 200000, .9)
        agent, _ = self.agent(policy=CompressionSchedule([first, second, third]))
        with patch.object(memory, 'summarize', side_effect=AssertionError('premature switch')):
            agent.query()
        events = agent._mem_adaptive_events
        self.assertEqual(len(events), 1)
        self.assertEqual([e['kind'] for e in events[0]['events']], ['online_trc', 'budget'])
        self.assertEqual(events[0]['config'], first.to_dict())
        self.assertEqual(events[0]['next_config'], second.to_dict())
        self.assertEqual(agent._memory_config, second)

    def test_stacked_summary_uses_local_depth(self):
        agent, _ = self.agent(Config('trc_structured_summarize', 10, .3))
        def summarize(messages, model, target):
            self.assertEqual(target, max(1, int(memory.count_tokens(messages) * .3)))
            return messages[:2] + messages[-2:], 100, 0, 0, 0.0
        with patch.object(memory, 'structured_summarize', side_effect=summarize) as summary:
            agent.query()
            summary.assert_called_once()

    def test_zero_savings_still_advances_and_logs_before_failed_query(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'token_log.json'
            os.environ['MSWEA_TOKEN_LOG_PATH'] = str(path)
            os.environ['MSWEA_EVENT_LOG_DIR'] = directory
            config = Config('truncation', 1)
            next_config = Config('truncation', 100000, .7)
            agent, model = self.agent(policy=CompressionSchedule([config, next_config]), messages=history(1))
            def fail(messages):
                data = json.loads(path.read_text())
                self.assertEqual(data['adaptive_events'][0]['tokens_saved'], 0)
                self.assertEqual(data['adaptive_config'], next_config.to_dict())
                self.assertEqual(data['compression_events'], 1)
                raise RuntimeError('model failed')
            model.query = fail
            with self.assertRaisesRegex(RuntimeError, 'model failed'):
                agent.query()
            record = json.loads((Path(directory) / 'adaptive_events.jsonl').read_text())
            self.assertEqual(record['status'], 'ok')
            compression = json.loads((Path(directory) / 'compression_events.jsonl').read_text())
            self.assertEqual(compression['adaptive_config'], config.to_dict())

    def test_policy_failure_and_invalid_return_preserve_completed_event(self):
        def broken(event):
            raise ValueError('policy failed')
        for policy, error in ((broken, ValueError), (lambda e: {}, TypeError)):
            with self.subTest(policy=policy), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / 'token_log.json'
                os.environ['MSWEA_TOKEN_LOG_PATH'] = str(path)
                config = Config('truncation', 1)
                agent, model = self.agent(config, policy)
                with self.assertRaises(error):
                    agent.query()
                data = json.loads(path.read_text())
                self.assertEqual(data['compression_events'], 1)
                self.assertEqual(data['adaptive_events'][0]['status'], 'error')
                self.assertEqual(data['adaptive_config'], config.to_dict())
                self.assertEqual(model.inputs, [])

    def test_environment_json_schedule_and_hold_last(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'schedule.json'
            configs = [Config('truncation', 1, .3), Config('tool_result_clear', 1)]
            path.write_text(json.dumps([c.to_dict() for c in configs]))
            os.environ['MSWEA_ADAPTIVE_SCHEDULE'] = str(path)
            agent, _ = self.agent()
            for _ in range(3):
                agent.query()
            self.assertEqual([e['config']['primitive'] for e in agent._mem_adaptive_events],
                             ['truncation', 'tool_result_clear', 'tool_result_clear'])

    def test_environment_python_policy(self):
        # Import an actual user-supplied module as a worker process would.
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, 'test_user_adaptive_policy.py').write_text(
                'from dataclasses import replace\n'
                'def choose(event):\n'
                '    return replace(event.config, budget=12345, depth=.7)\n')
            sys.path.insert(0, directory)
            self.addCleanup(sys.path.remove, directory)
            self.addCleanup(sys.modules.pop, 'test_user_adaptive_policy', None)
            os.environ.update(MSWEA_ADAPTIVE_POLICY='test_user_adaptive_policy:choose',
                              MSWEA_PRIMITIVE='truncation', MSWEA_TOKEN_BUDGET='1',
                              MSWEA_COMPRESSION_RATIO='.3')
            agent, _ = self.agent()
            agent.query()
            self.assertEqual(agent._mem_adaptive_events[0]['config']['depth'], .3)
            self.assertEqual(agent._memory_config, Config('truncation', 12345, .7))

    def test_online_does_not_require_a_token_budget(self):
        agent, _ = self.agent(Config('online_trc', freeze_k=0), messages=history(1))
        agent.query()
        self.assertEqual([e['kind'] for e in agent._mem_adaptive_events], ['online_trc'])
        self.assertEqual(agent._mem_compression_events, 0)
        with self.assertRaisesRegex(ValueError, 'budget is required'):
            Config('truncation')

    def test_online_step_interval_changes_after_each_trigger(self):
        agent, _ = self.agent(policy=CompressionSchedule([
            Config('online_trc', freeze_k=0, step_interval=3),
            Config('online_trc', freeze_k=0, step_interval=2),
            Config('truncation', 100000),
        ]))
        for _ in range(8):
            agent.query()
            agent.add_messages(*history(1)[2:])
        events = agent._mem_adaptive_events
        self.assertEqual([e['step'] for e in events], [3, 5])
        self.assertEqual([e['config']['step_interval'] for e in events], [3, 2])
        self.assertEqual(len(agent._mem_online_trc_flags), 2)
        self.assertEqual(agent._memory_config.primitive, 'truncation')

    def test_switch_to_online_counts_steps_from_previous_trigger(self):
        agent, _ = self.agent(policy=CompressionSchedule([
            Config('truncation', 1), Config('online_trc', step_interval=3, freeze_k=0),
        ]))
        agent.n_calls = 7
        agent.query()  # budget trigger at 7; online scheduled for 10
        agent.query()
        agent.query()
        self.assertEqual(len(agent._mem_adaptive_events), 1)
        agent.query()
        self.assertEqual([e['step'] for e in agent._mem_adaptive_events], [7, 10])

    def test_online_step_trigger_with_no_eligible_results_and_none_policy(self):
        with tempfile.TemporaryDirectory() as directory:
            os.environ['MSWEA_EVENT_LOG_DIR'] = directory
            os.environ['MSWEA_TOKEN_LOG_PATH'] = str(Path(directory, 'token_log.json'))
            agent, _ = self.agent(Config('online_trc', step_interval=2), messages=history(0))
            for _ in range(5):
                agent.query()
            self.assertEqual([e['step'] for e in agent._mem_adaptive_events], [2, 4])
            self.assertTrue(all(e['tokens_saved'] == 0 for e in agent._mem_adaptive_events))
            self.assertEqual(agent._mem_online_trc_flags, [])
            self.assertFalse(Path(directory, 'compression_events.jsonl').exists())
            records = [json.loads(line) for line in
                       Path(directory, 'adaptive_events.jsonl').read_text().splitlines()]
            self.assertEqual([r['step'] for r in records], [2, 4])
            token_log = json.loads(Path(directory, 'token_log.json').read_text())
            self.assertEqual(token_log['adaptive_events'], records)
            self.assertTrue(all(r['events'][0]['skipped_reason'] == 'no_eligible_result'
                                for r in records))

    def test_actual_online_clear_with_zero_savings_still_has_compression_record(self):
        with tempfile.TemporaryDirectory() as directory:
            os.environ['MSWEA_EVENT_LOG_DIR'] = directory
            agent, _ = self.agent(Config('online_trc', step_interval=1, freeze_k=0),
                                  messages=history(1))
            # Simulate equal token counts despite the content replacement.
            with patch.object(memory, 'count_tokens', return_value=100):
                agent.query()
                agent.query()
            record = json.loads(Path(directory, 'compression_events.jsonl').read_text())
            self.assertEqual(record['kind'], 'online_trc')
            self.assertIsNotNone(record['cleared_index'])
            self.assertEqual(record['tokens_before'], record['tokens_after'])
            self.assertEqual(len(agent._mem_online_trc_flags), 1)
            self.assertNotIn('skipped_reason', agent._mem_adaptive_events[0]['events'][0])

    def test_noop_online_with_budget_fallback_logs_only_budget_compression(self):
        with tempfile.TemporaryDirectory() as directory:
            os.environ['MSWEA_EVENT_LOG_DIR'] = directory
            agent, _ = self.agent(Config('online_trc', budget=1, step_interval=1),
                                  messages=history(0))
            agent.query()
            agent.query()
            records = [json.loads(line) for line in
                       Path(directory, 'compression_events.jsonl').read_text().splitlines()]
            self.assertEqual([r['kind'] for r in records], ['budget', 'budget'])
            operations = agent._mem_adaptive_events[-1]['events']
            self.assertEqual([e['kind'] for e in operations], ['online_trc', 'budget'])
            self.assertEqual(operations[0]['skipped_reason'], 'no_eligible_result')

    def test_online_budget_fallback_can_trigger_before_scheduled_step(self):
        agent, _ = self.agent(Config('online_trc', budget=1, step_interval=3))
        agent.query()
        self.assertEqual([e['kind'] for e in agent._mem_adaptive_events], ['budget'])
        self.assertEqual(agent._mem_online_trc_flags, [])

    def test_budget_fallback_does_not_postpone_online_steps(self):
        seen = []
        def policy(event):
            seen.append(event)
            return event.config  # same interval must preserve the online clock
        agent, _ = self.agent(Config('online_trc', budget=1, step_interval=3), policy)
        for _ in range(7):
            agent.query()
        self.assertEqual([e.step for e in seen if 'online_trc' in e.kinds], [3, 6])
        self.assertEqual(len(seen), 7)  # never twice for the same query
        self.assertEqual(seen[3].kinds, ('online_trc', 'budget'))
        self.assertEqual(seen[3].tokens_after, memory.count_tokens(seen[3].messages))

    def test_step_interval_json_and_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory, 'schedule.json')
            path.write_text('[{"primitive": "online_trc", "step_interval": 2}]')
            os.environ['MSWEA_ADAPTIVE_SCHEDULE'] = str(path)
            agent, _ = self.agent(messages=history(0))
            for _ in range(3):
                agent.query()
            self.assertEqual([e['step'] for e in agent._mem_adaptive_events], [2])
        for interval in (0, -1, True, 1.5):
            with self.subTest(interval=interval), self.assertRaises(ValueError):
                Config('online_trc', step_interval=interval)
        with self.assertRaisesRegex(ValueError, 'only supported by online'):
            Config('truncation', 1000, step_interval=2)

    def test_runner_manifest_reaches_agent_and_token_log(self):
        from agentctx.compression.selection import build_selection, snapshot_selection
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            schedule = root / 'schedule.json'
            schedule.write_text('[{"primitive":"online_trc","step_interval":1}]')
            selection = build_selection(schedule=schedule)
            manifest = snapshot_selection(selection, root)
            os.environ['MSWEA_ADAPTIVE_MANIFEST'] = str(manifest)
            os.environ['MSWEA_TOKEN_LOG_PATH'] = str(root / 'token_log.json')
            os.environ['MSWEA_PRIMITIVE'] = 'adaptive'
            agent, _ = self.agent(messages=history(0))
            agent.query()
            agent.query()
            data = json.loads((root / 'token_log.json').read_text())
            self.assertEqual(data['adaptive']['sha256'], selection['sha256'])
            self.assertEqual(data['adaptive_events'][0]['step'], 1)

    def test_validate_inputs(self):
        for kwargs in ({'primitive': 'typo'}, {'budget': 0}, {'budget': 1.5}, {'budget': True},
                       {'depth': 0}, {'depth': 1.1}, {'depth': float('nan')},
                       {'depth': float('inf')}, {'depth': True}, {'freeze_k': -1},
                       {'freeze_k': 1.5}, {'primitive': 'staggered_alternate', 'budget': 42}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                Config(**({'primitive': 'truncation', 'budget': 100} | kwargs))
        with self.assertRaises(ValueError):
            CompressionSchedule([])
        with self.assertRaises(TypeError):
            resolve_policy(object(), Config('truncation', 1))
        os.environ.update(MSWEA_ADAPTIVE_POLICY='x:y', MSWEA_ADAPTIVE_SCHEDULE='x.json')
        with self.assertRaisesRegex(ValueError, 'only one'):
            resolve_policy()
        # Explicit Python API overrides environment configuration.
        self.assertEqual(resolve_policy(config=Config('truncation', 1))[1], Config('truncation', 1))


if __name__ == '__main__':
    unittest.main()
