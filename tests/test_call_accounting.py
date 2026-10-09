"""Failed-response accounting and durable compression logs, without API calls.

Run: venv/bin/python -m unittest discover -s tests -p test_call_accounting.py -v
"""
import itertools
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
for entry in (ROOT, ROOT / 'src', ROOT / 'mini-swe-agent/src'):
    sys.path.insert(0, str(entry))
try:
    import memory
    from litellm import ModelResponse
    from minisweagent.agents.default import DefaultAgent
    from minisweagent.exceptions import FormatError
    from minisweagent.models.litellm_textbased_model import LitellmTextbasedModel
except ImportError as exc:
    raise unittest.SkipTest(str(exc))


class Environment:
    def __init__(self):
        self.commands = []

    def get_template_vars(self):
        return {}

    def serialize(self):
        return {}

    def execute(self, action):
        self.commands.append(action['command'])
        return {'output': 'done', 'returncode': 0, 'exception_info': None}


class CallAccountingTests(unittest.TestCase):
    def setUp(self):
        self.env_patch = patch.dict(os.environ, {}, clear=True)
        self.env_patch.start()
        self.addCleanup(self.env_patch.stop)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.directory = Path(self.tmp.name)
        self.log_path = self.directory / 'token_log.json'
        os.environ['MSWEA_TOKEN_LOG_PATH'] = str(self.log_path)
        os.environ['MSWEA_EVENT_LOG_DIR'] = str(self.directory)
        self.model = LitellmTextbasedModel(model_name='hosted_vllm/test', cost_tracking='ignore_errors')
        self.cost = patch.object(self.model, '_calculate_cost', return_value={'cost': 0.75})
        self.cost.start()
        self.addCleanup(self.cost.stop)
        self.environment = Environment()

    def agent(self, *, seed_history=True, **kwargs):
        agent = DefaultAgent(self.model, self.environment, system_template='system',
                             instance_template='task', output_path=self.directory / 'trajectory.json',
                             **({'cost_limit': 0} | kwargs))
        if seed_history:
            agent.add_messages({'role': 'system', 'content': 'system'},
                               {'role': 'user', 'content': 'task'})
        return agent

    def response(self, content='', pt=123, ct=47, finish='stop'):
        return ModelResponse(model='test', choices=[{'finish_reason': finish,
            'message': {'role': 'assistant', 'content': content, 'reasoning_content': 'reasoning'}}],
            usage={'prompt_tokens': pt, 'completion_tokens': ct, 'total_tokens': pt + ct})

    def log(self):
        return json.loads(self.log_path.read_text())

    def test_rejected_response_retains_usage_finish_reason_and_reasoning(self):
        response = self.response(finish='length')
        with patch.object(self.model, '_query', return_value=response):
            with self.assertRaises(FormatError) as caught:
                self.model.query([{'role': 'user', 'content': 'task'}])
        metadata = caught.exception.model_response['extra']
        self.assertEqual(metadata['response']['usage']['completion_tokens'], 47)
        self.assertEqual(metadata['response']['choices'][0]['finish_reason'], 'length')
        self.assertEqual(metadata['response']['choices'][0]['message']['reasoning_content'], 'reasoning')
        self.assertEqual(metadata['cost'], 0.75)
        self.assertNotIn('actions', metadata)

    def test_format_error_then_success_count_once_and_preserve_step_alignment(self):
        agent = self.agent()
        responses = [self.response(), self.response('```mswea_bash_command\necho ok\n```', pt=200, ct=30)]
        with patch.object(self.model, '_query', side_effect=responses), patch(
            'minisweagent.agents.default.time.time', side_effect=itertools.count(1000)
        ):
            with self.assertRaises(FormatError) as caught:
                agent.query()
            agent.add_messages(*caught.exception.messages)
            agent.query()
        log = self.log()
        self.assertEqual(log['step_prompt_tokens'], [123, 200])
        self.assertEqual(log['step_completion_tokens'], [47, 30])
        self.assertEqual((log['total_prompt_tokens'], log['total_completion_tokens']), (323, 77))
        self.assertEqual(agent.cost, 1.5)
        self.assertEqual(agent.n_calls, 2)
        self.assertEqual([r['step'] for r in log['model_call_records']], [1, 2])
        self.assertEqual([r['status'] for r in log['model_call_records']], ['format_error', 'ok'])
        self.assertEqual([r['response_id'] for r in log['model_call_records']],
                         [response.id for response in responses])
        self.assertGreater(log['step_latency_s'][0], 0)
        self.assertEqual(log['total_latency_s'], sum(log['step_latency_s']))
        self.assertEqual(sum(m['role'] == 'assistant' for m in agent.messages), 1)
        self.assertEqual(agent.messages[2]['extra']['response']['usage']['prompt_tokens'], 123)
        prepared = self.model._prepare_messages_for_api(agent.messages)
        self.assertTrue(all('extra' not in m for m in prepared))

    def test_real_run_final_format_error_saves_usage_and_feedback(self):
        agent = self.agent(seed_history=False, step_limit=1)
        with patch.object(self.model, '_query', return_value=self.response()):
            result = agent.run('task')
        self.assertEqual(result['exit_status'], 'LimitsExceeded')
        self.assertEqual(self.environment.commands, [])
        self.assertEqual(self.log()['total_tokens'], 170)
        trajectory = json.loads((self.directory / 'trajectory.json').read_text())
        self.assertEqual(trajectory['info']['model_stats']['instance_cost'], 0.75)
        events = [json.loads(l) for l in (self.directory / 'events.jsonl').read_text().splitlines()]
        errors = [e for e in events if e['message'].get('extra', {}).get('interrupt_type') == 'FormatError']
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0]['message']['extra']['response']['usage']['total_tokens'], 170)

    def test_last_compression_before_format_error_survives_step_limit_exit(self):
        from scripts.maintenance.reconstruct_context import Replay

        os.environ['MSWEA_PRIMITIVE'] = 'tool_result_clear'
        os.environ['MSWEA_TOKEN_BUDGET'] = '1000'
        agent = self.agent(seed_history=False, step_limit=3)
        valid = self.response('```mswea_bash_command\necho ok\n```')
        with patch.object(self.model, '_query', side_effect=[valid, valid, self.response()]), patch.object(
            self.environment, 'execute', return_value={
                'output': 'output ' * 600, 'returncode': 0, 'exception_info': None,
            }
        ):
            result = agent.run()
        self.assertEqual(result['exit_status'], 'LimitsExceeded')
        log = self.log()
        self.assertEqual(log['compression_events'], 1)
        self.assertEqual(log['compression_event_steps'], [2])
        self.assertLessEqual(log['context_tokens_after_compression'][0], 1000)
        self.assertEqual(log['step_prompt_tokens'], [123, 123, 123])
        self.assertEqual(log['model_call_records'][-1]['status'], 'format_error')
        Replay(self.directory).verify()

    def test_format_error_cost_counts_toward_existing_cost_limit(self):
        agent = self.agent(seed_history=False, step_limit=5, cost_limit=0.5)
        with patch.object(self.model, '_query', return_value=self.response()) as query:
            self.assertEqual(agent.run()['exit_status'], 'LimitsExceeded')
        query.assert_called_once()
        self.assertEqual(agent.n_calls, 1)

    def test_every_budget_compression_is_saved_before_failed_query(self):
        for primitive in ['tool_result_clear', 'truncation', 'summarization_free', 'structured_summarize_free']:
            with self.subTest(primitive=primitive):
                os.environ['MSWEA_PRIMITIVE'] = primitive
                os.environ['MSWEA_TOKEN_BUDGET'] = '100'
                agent = self.agent()
                for i in range(6):
                    agent.add_messages({'role': 'assistant', 'content': f'command {i}'},
                                       {'role': 'user', 'content': 'output ' * 100,
                                        'extra': {'raw_output': 'output', 'returncode': 0}})
                def fail(messages):
                    # Runs before the error handler: survives even an abrupt kill here.
                    log = self.log()
                    self.assertEqual(log['compression_events'], 1)
                    self.assertEqual(log['context_tokens_after_compression'], [memory.count_tokens(messages)])
                    raise RuntimeError('transport failed')
                def summary(messages, model, target):
                    out = messages[:2] + [{'role': 'user', 'content': 'summary', 'extra': {'kind': 'summary'}}]
                    return out, memory.count_tokens(messages) - memory.count_tokens(out), 10, 5, 0.2
                with patch.object(memory, 'summarize_free', side_effect=summary), patch.object(
                    memory, 'structured_summarize_free', side_effect=summary
                ), patch.object(self.model, 'query', side_effect=fail):
                    with self.assertRaisesRegex(RuntimeError, 'transport failed'):
                        agent.query()
                record = self.log()['model_call_records'][-1]
                self.assertEqual(record['status'], 'error')
                self.assertIsNone(record['prompt_tokens'])
                self.assertIsNone(record['completion_tokens'])

    def test_interrupted_summarizer_keeps_response_ids(self):
        os.environ['MSWEA_PRIMITIVE'] = 'summarization'
        os.environ['MSWEA_TOKEN_BUDGET'] = '100'
        agent = self.agent()
        for i in range(6):
            agent.add_messages({'role': 'assistant', 'content': f'command {i}'},
                               {'role': 'user', 'content': 'output ' * 100,
                                'extra': {'raw_output': 'output', 'returncode': 0}})
        # Patch query(), not _query(): the model retries transport errors with
        # backoff, and the summarizer copies the model so it shares the patch.
        calls = itertools.count(1)
        def query(messages, **kwargs):
            if next(calls) > 1:
                raise RuntimeError('transport failed')
            return {'role': 'assistant', 'content': '',   # empty body: rejected, then retried
                    'extra': {'response': {'id': 'chatcmpl-first',
                                           'usage': {'prompt_tokens': 10, 'completion_tokens': 1}}}}
        with patch.object(self.model, 'query', side_effect=query):
            with self.assertRaisesRegex(RuntimeError, 'transport failed'):
                agent.query()
        self.assertIsNotNone(agent._mem_active_compression)
        agent._write_token_log()         # what run()'s finally does
        self.assertIsNone(agent._mem_active_compression)
        outcomes = self.log()['summary_outcomes']
        self.assertEqual(len(outcomes), 1)
        self.assertEqual(outcomes[0]['response_ids'], ['chatcmpl-first'])
        self.assertEqual(outcomes[0]['interrupted'], 'RuntimeError')
        self.assertEqual(outcomes[0]['interrupted_attempt'], 2)
        self.assertFalse(outcomes[0]['accepted'])
        self.assertEqual(outcomes[0]['primitive'], 'summarization')
        agent._write_token_log()         # idempotent: no duplicate entry
        self.assertEqual(len(self.log()['summary_outcomes']), 1)

    def test_completed_summary_event_records_ids_once(self):
        os.environ['MSWEA_PRIMITIVE'] = 'summarization'
        os.environ['MSWEA_TOKEN_BUDGET'] = '100'
        agent = self.agent()
        for i in range(6):
            agent.add_messages({'role': 'assistant', 'content': f'command {i}'},
                               {'role': 'user', 'content': 'output ' * 100,
                                'extra': {'raw_output': 'output', 'returncode': 0}})
        summary = self.response(f'{memory.SU_OPEN_MARKER}\nsummary\n{memory.SU_CLOSE_MARKER}')
        summary.id = 'chatcmpl-summary'
        step = self.response('```mswea_bash_command\necho ok\n```')
        step.id = 'chatcmpl-step'
        with patch.object(self.model, '_query', side_effect=[summary, step]):
            agent.query()
        agent._write_token_log()
        log = self.log()
        self.assertEqual([o['response_ids'] for o in log['summary_outcomes']], [['chatcmpl-summary']])
        self.assertNotIn('interrupted', log['summary_outcomes'][0])
        self.assertEqual([r['response_id'] for r in log['model_call_records']], ['chatcmpl-step'])
        self.assertIsNone(agent._mem_active_compression)

    def test_run_finally_flushes_even_if_trajectory_save_fails(self):
        agent = self.agent(seed_history=False, step_limit=1)
        def step():
            agent._mem_tokens_saved = 19
            raise RuntimeError('tool failed')
        with patch.object(agent, 'step', side_effect=step), patch.object(
            agent, 'save', side_effect=OSError('trajectory write failed')
        ):
            with self.assertRaisesRegex(OSError, 'trajectory write failed'):
                agent.run()
        self.assertEqual(self.log()['total_tokens_saved'], 19)

    def test_keyboard_interrupt_is_recorded_and_reraised(self):
        agent = self.agent()
        with patch.object(self.model, 'query', side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                agent.query()
        self.assertEqual(self.log()['model_call_records'][0]['error_type'], 'KeyboardInterrupt')
        self.assertEqual(agent.n_calls, 1)

    def test_atomic_write_preserves_previous_log_if_replace_fails(self):
        agent = self.agent()
        memory.write_token_log(agent)
        before = self.log_path.read_text()
        agent._mem_tokens_saved = 42
        with patch.object(memory.os, 'replace', side_effect=OSError('replace failed')):
            with self.assertRaisesRegex(OSError, 'replace failed'):
                memory.write_token_log(agent)
        self.assertEqual(self.log_path.read_text(), before)
        self.assertEqual(list(self.directory.glob('.token_log.json.*.tmp')), [])
        memory.write_token_log(agent)
        self.assertEqual(self.log()['total_tokens_saved'], 42)

    def test_full_context_probe_includes_rejected_call_and_status(self):
        os.environ['MSWEA_FULL_CONTEXT_LOG_DIR'] = str(self.directory)
        agent = self.agent()
        with patch.object(self.model, '_query', return_value=self.response()):
            with self.assertRaises(FormatError):
                agent.query()
        record = json.loads((self.directory / 'full_context_log.jsonl').read_text())
        self.assertEqual(record['step'], 1)
        self.assertEqual(record['recorded_prompt_tokens'], 123)
        self.assertEqual(record['response_status'], 'format_error')


if __name__ == '__main__':
    unittest.main()
