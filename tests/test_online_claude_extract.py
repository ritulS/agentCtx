"""online_claude_extract: Claude-written extract before every model call, without API calls.

Run: venv/bin/python -m unittest discover -s tests -p test_online_claude_extract.py -v
"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
for entry in (ROOT, ROOT / 'src', ROOT / 'mini-swe-agent/src'):
    sys.path.insert(0, str(entry))
try:
    import memory
    from agentctx.compression import claude_extract
    from litellm import ModelResponse
    from minisweagent.agents.default import DefaultAgent
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


class FakeExtractor(claude_extract.ClaudeExtractModel):
    """Replies scripted per call; records the prompts it was given."""

    def __init__(self, replies):
        super().__init__(settings={'model': 'fake', 'effort': 'low', 'max_tokens': 10,
                                   'timeout_s': 1.0, 'fallbacks': False}, client=object())
        self.replies = list(replies)
        self.prompts = []

    def query(self, messages, **kwargs):
        self.prompts.append(messages)
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        text, finish = reply
        return {'role': 'assistant', 'content': text,
                'extra': {'response': {'id': f'msg_{len(self.prompts)}',
                                       'usage': {'prompt_tokens': 500, 'completion_tokens': 50},
                                       'choices': [{'finish_reason': finish}]}}}

    def window(self, i):
        """The conversation-history part of the i-th prompt's user message."""
        return self.prompts[i][1]['content'].split('Conversation history:\n', 1)[1]


def extract(body):
    return (f'{memory.EX_OPEN_MARKER}\n{body}\n{memory.EX_CLOSE_MARKER}', 'stop')


class OnlineClaudeExtractTests(unittest.TestCase):
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
        os.environ['MSWEA_PRIMITIVE'] = 'online_claude_extract'
        os.environ['MSWEA_TOKEN_BUDGET'] = ''
        # The production default became 1 on 2026-10-25 (newest turn kept verbatim);
        # these tests pin the original window semantics and set 1 where they test it.
        os.environ['MSWEA_EXTRACT_KEEP_RECENT'] = '0'
        # SUMMARY_MAX_ATTEMPTS is read at import time; cap retries for the fake extractor.
        attempts = patch.object(sys.modules['agentctx.compression.primitives'], 'SUMMARY_MAX_ATTEMPTS', 2)
        attempts.start()
        self.addCleanup(attempts.stop)
        self.model = LitellmTextbasedModel(model_name='hosted_vllm/test', cost_tracking='ignore_errors')
        self.cost = patch.object(self.model, '_calculate_cost', return_value={'cost': 0.0})
        self.cost.start()
        self.addCleanup(self.cost.stop)
        self.environment = Environment()

    def agent(self, **kwargs):
        agent = DefaultAgent(self.model, self.environment, system_template='system',
                             instance_template='task', output_path=self.directory / 'trajectory.json',
                             **({'cost_limit': 0} | kwargs))
        agent.add_messages({'role': 'system', 'content': 'system'},
                           {'role': 'user', 'content': 'fix the bug in foo.py'})
        return agent

    def response(self, content, pt=100, ct=10):
        return ModelResponse(model='test', choices=[{'finish_reason': 'stop',
            'message': {'role': 'assistant', 'content': content}}],
            usage={'prompt_tokens': pt, 'completion_tokens': ct, 'total_tokens': pt + ct})

    def log(self):
        return json.loads(self.log_path.read_text())

    def run_steps(self, agent, extractor, n):
        cmds = [self.response(f'```mswea_bash_command\necho step{i}\n```') for i in range(n)]
        with patch.object(claude_extract, 'get_extract_model', return_value=extractor), \
             patch.object(self.model, '_query', side_effect=cmds):
            for _ in range(n):
                agent.step()

    def test_extract_fires_before_each_call_and_covers_the_newest_observation(self):
        extractor = FakeExtractor([extract('E1'), extract('E2')])
        agent = self.agent()
        self.run_steps(agent, extractor, 3)
        # Call 1 had nothing to extract. Before call 2 the window was [a1, obs1] -> E1;
        # before call 3 it was [E1, a2, obs2] -> E2. After step 3: [system, task, E2, a3, obs3].
        self.assertEqual([m['role'] for m in agent.messages], ['system', 'user', 'user', 'assistant', 'user'])
        self.assertEqual(agent.messages[1]['content'], 'fix the bug in foo.py')
        self.assertTrue(agent.messages[2]['content'].startswith(memory.EX_OPEN_MARKER))
        self.assertIn('E2', agent.messages[2]['content'])
        self.assertIn('echo step2', agent.messages[3]['content'])
        self.assertTrue(memory.is_summary_message(agent.messages[2]))
        self.assertEqual(agent.messages[2]['extra']['summary_format']['extract'], True)
        # The extractor sees the task as reference, never the system prompt, and the
        # window ends with the newest observation; from the second extraction on it
        # starts with the previous extract and no longer contains the raw old turns.
        first_user = extractor.prompts[0][1]['content']
        self.assertIn('fix the bug in foo.py', first_user)
        self.assertNotIn('[system]:', first_user)
        w0, w1 = extractor.window(0), extractor.window(1)
        self.assertIn('echo step0', w0)
        self.assertIn('done', w0)                       # observation 1 is extracted, not kept raw
        self.assertIn('E1', w1)
        self.assertIn('echo step1', w1)
        self.assertNotIn('echo step0', w1)
        # Context sent to call 3 was exactly [system, task, E2].
        events = [json.loads(l) for l in (self.directory / 'compression_events.jsonl').read_text().splitlines()]
        self.assertEqual([e['kind'] for e in events], ['online_claude_extract'] * 2)
        self.assertEqual([e['step'] for e in events], [1, 2])    # fires before call step+1
        self.assertEqual(len(events[1]['after_uids']), 3)
        log = self.log()
        self.assertEqual([e['step'] for e in log['online_claude_extract_events']], [1, 2])
        self.assertTrue(all(e['accepted'] for e in log['online_claude_extract_events']))
        self.assertEqual(log['online_claude_extract_accepted'], 2)
        self.assertEqual(log['summarization_prompt_tokens'], 1000)
        self.assertEqual(log['total_prompt_tokens'], 300 + 1000)
        self.assertEqual([o['primitive'] for o in log['summary_outcomes']], ['online_claude_extract'] * 2)
        self.assertEqual(log['summary_outcomes'][0]['response_ids'], ['msg_1'])
        self.assertEqual(log['extract_model']['model'], 'claude-opus-5-5')
        self.assertEqual(log['compression_events'], 0)           # no budget event
        self.assertEqual(log['compression_cache_comparisons'][0]['compression_kinds'], ['online_claude_extract'])
        self.assertEqual(log['compression_cache_comparisons'][0]['after_step'], 2)

    def test_rejected_replies_leave_history_unchanged(self):
        extractor = FakeExtractor([('no markers here', 'stop'), ('', 'refusal')])
        agent = self.agent()
        self.run_steps(agent, extractor, 2)
        self.assertEqual([m['role'] for m in agent.messages],
                         ['system', 'user', 'assistant', 'user', 'assistant', 'user'])
        self.assertIn('echo step0', agent.messages[2]['content'])
        log = self.log()
        self.assertEqual(log['online_claude_extract_events'][0]['accepted'], False)
        self.assertEqual(log['online_claude_extract_events'][0]['prompt_tokens'], 1000)   # both attempts billed
        self.assertEqual(log['summary_outcomes'][0]['fallback'], 'unchanged')
        self.assertEqual(log['summary_outcomes'][0]['attempts'], 2)
        self.assertFalse((self.directory / 'compression_events.jsonl').exists())

    def test_keep_recent_keeps_whole_turns_and_every_sets_cadence(self):
        os.environ['MSWEA_EXTRACT_KEEP_RECENT'] = '1'
        os.environ['MSWEA_EXTRACT_EVERY'] = '2'
        extractor = FakeExtractor([extract('E2'), extract('E4')])
        agent = self.agent()
        self.run_steps(agent, extractor, 5)
        log = self.log()
        self.assertEqual([e['step'] for e in log['online_claude_extract_events']], [2, 4])
        # keep_recent=1 would keep obs2 alone; the kept span is widened to the turn's
        # assistant message, so before call 3 the window is [a1, obs1] and [a2, obs2] stays.
        self.assertIn('echo step0', extractor.window(0))
        self.assertNotIn('echo step1', extractor.window(0))
        # Before call 5: window [E2, a2, obs2, a3, obs3], kept [a4, obs4].
        self.assertIn('E2', extractor.window(1))
        self.assertIn('echo step2', extractor.window(1))
        self.assertNotIn('echo step3', extractor.window(1))
        contents = [m['content'] for m in agent.messages]
        self.assertTrue(contents[2].startswith(memory.EX_OPEN_MARKER))
        self.assertIn('echo step3', contents[3])
        self.assertEqual(len(agent.messages), 7)   # system, task, E4, a4, obs4, a5, obs5

    def test_errors_are_logged_then_raised_after_the_cap(self):
        os.environ['MSWEA_EXTRACT_MAX_CONSECUTIVE_ERRORS'] = '2'
        extractor = FakeExtractor([RuntimeError('boom 1'), RuntimeError('boom 2')])
        agent = self.agent()
        cmds = [self.response('```mswea_bash_command\necho ok\n```') for _ in range(3)]
        with patch.object(claude_extract, 'get_extract_model', return_value=extractor), \
             patch.object(self.model, '_query', side_effect=cmds):
            agent.step()                       # nothing to extract yet
            agent.step()                       # first error: logged, run continues
            with self.assertRaisesRegex(RuntimeError, 'boom 2'):
                agent.step()
        log = self.log()
        self.assertEqual([e['error'] for e in log['online_claude_extract_events']],
                         ['RuntimeError: boom 1', 'RuntimeError: boom 2'])
        self.assertEqual(log['online_claude_extract_errors'], 2)
        self.assertEqual([o['interrupted'] for o in log['summary_outcomes']], ['RuntimeError'] * 2)
        self.assertIsNone(agent._mem_active_compression)

    def test_adaptive_schedule_advances_on_extract_events(self):
        schedule = self.directory / 'schedule.json'
        schedule.write_text(json.dumps([
            {'primitive': 'online_claude_extract', 'step_interval': 2},
            {'primitive': 'truncation', 'budget': 100},
        ]))
        os.environ['MSWEA_ADAPTIVE_SCHEDULE'] = str(schedule)
        os.environ['MSWEA_PRIMITIVE'] = 'adaptive'
        extractor = FakeExtractor([extract('E2')])
        agent = self.agent()
        self.run_steps(agent, extractor, 4)
        # step_interval=2: the first extraction waits for call 3 (n_calls=2); that event
        # advances the schedule to truncation, so no second extraction is requested.
        self.assertEqual(len(extractor.prompts), 1)
        log = self.log()
        self.assertEqual([e['step'] for e in log['online_claude_extract_events']], [2])
        kinds = [e['kind'] for e in log['adaptive_events']]
        self.assertEqual(kinds[0], 'online_claude_extract')
        self.assertEqual(log['adaptive_events'][0]['next_config']['primitive'], 'truncation')
        self.assertEqual(agent._memory_config.primitive, 'truncation')

    def test_empty_window_after_turn_widening_is_not_an_event(self):
        # keep_recent=1 with a single turn: the kept tail widens to [a1, obs1], the
        # window is empty, and no extractor request is made. That must not count as a
        # (rejected) extraction nor advance an adaptive schedule.
        schedule = self.directory / 'schedule.json'
        schedule.write_text(json.dumps([
            {'primitive': 'online_claude_extract', 'step_interval': 1},
            {'primitive': 'truncation', 'budget': 100},
        ]))
        os.environ['MSWEA_ADAPTIVE_SCHEDULE'] = str(schedule)
        os.environ['MSWEA_PRIMITIVE'] = 'adaptive'
        os.environ['MSWEA_EXTRACT_KEEP_RECENT'] = '1'
        extractor = FakeExtractor([extract('E2')])
        agent = self.agent()
        self.run_steps(agent, extractor, 2)           # before call 2 the window is empty
        self.assertEqual(extractor.prompts, [])
        self.assertEqual(agent._memory_config.primitive, 'online_claude_extract')
        self.assertEqual(agent._mem_adaptive_events, [])
        self.assertEqual(self.log()['online_claude_extract_events'], [])
        self.assertIsNone(agent._mem_active_compression)
        # With two turns the window is [a1, obs1] and the extraction happens.
        with patch.object(claude_extract, 'get_extract_model', return_value=extractor), \
             patch.object(self.model, '_query', return_value=self.response('```mswea_bash_command\necho x\n```')):
            agent.step()
        self.assertEqual(len(extractor.prompts), 1)
        self.assertEqual([e['step'] for e in self.log()['online_claude_extract_events']], [2])
        self.assertEqual(agent._memory_config.primitive, 'truncation')

    def test_usage_of_attempts_before_a_transport_error_is_kept(self):
        os.environ['MSWEA_EXTRACT_MAX_CONSECUTIVE_ERRORS'] = '5'
        extractor = FakeExtractor([('no markers', 'stop'), RuntimeError('socket closed')])
        agent = self.agent()
        self.run_steps(agent, extractor, 2)           # extraction before call 2: reject, then error
        log = self.log()
        event = log['online_claude_extract_events'][0]
        self.assertEqual(event['error'], 'RuntimeError: socket closed')
        self.assertEqual((event['prompt_tokens'], event['completion_tokens']), (500, 50))
        outcome = log['summary_outcomes'][0]
        self.assertEqual(outcome['interrupted'], 'RuntimeError')
        self.assertEqual(outcome['interrupted_attempt'], 2)
        self.assertEqual(outcome['response_ids'], ['msg_1'])
        self.assertEqual((outcome['prompt_tokens'], outcome['completion_tokens']), (500, 50))
        self.assertEqual(log['summarization_prompt_tokens'], 500)
        self.assertEqual(log['total_prompt_tokens'], 200 + 500)   # 2 agent calls + 1 completed attempt
        self.assertEqual(log['total_completion_tokens'], 20 + 50)
        self.assertGreaterEqual(log['summarization_latency_s'], 0.0)

    def test_history_text_renders_tool_calls_and_keep_split_respects_turns(self):
        window = [
            {'role': 'assistant', 'content': 'THOUGHT: look',
             'tool_calls': [{'id': 'call_1', 'function': {'name': 'bash', 'arguments': '{"command": "ls"}'}}]},
            {'role': 'tool', 'tool_call_id': 'call_1', 'content': 'a.py  b.py'},
        ]
        text = memory._extract_history_text(window)
        self.assertIn('[tool_call call_1] bash({"command": "ls"})', text)
        self.assertIn('[tool result for call_1]:\na.py  b.py', text)
        self.assertEqual(memory._extract_history_text([{'role': 'user', 'content': 'x'}]),
                         memory._history_text([{'role': 'user', 'content': 'x'}]))
        turns = [{'role': 'assistant', 'content': 'a1'}, {'role': 'user', 'content': 'o1'},
                 {'role': 'assistant', 'content': 'a2'}, {'role': 'user', 'content': 'o2'}]
        self.assertEqual(memory._extract_keep_split(turns, 0), 4)
        self.assertEqual(memory._extract_keep_split(turns, 1), 2)   # widened to a2
        self.assertEqual(memory._extract_keep_split(turns, 2), 2)
        self.assertEqual(memory._extract_keep_split(turns, 3), 0)   # widened to a1
        self.assertEqual(memory._extract_keep_split(turns, 9), 0)

    def test_request_shape_and_usage_for_anthropic(self):
        model = claude_extract.ClaudeExtractModel(
            settings={'model': 'claude-opus-5-5', 'effort': 'medium', 'max_tokens': 16000,
                      'timeout_s': 600.0, 'fallbacks': True}, client=object())
        request = model._request([{'role': 'system', 'content': 'S'}, {'role': 'user', 'content': 'U'}])
        self.assertEqual(request['system'], [{'type': 'text', 'text': 'S', 'cache_control': {'type': 'ephemeral'}}])
        self.assertEqual(request['messages'], [{'role': 'user', 'content': 'U'}])
        self.assertEqual(request['thinking'], {'type': 'adaptive'})
        self.assertEqual(request['output_config'], {'effort': 'medium'})
        self.assertEqual(request['betas'], ['server-side-fallback-2026-07-01'])
        self.assertEqual(request['extra_body'], {'fallbacks': 'default'})
        self.assertNotIn('temperature', request)
        # usage: Anthropic's input_tokens excludes cache reads/writes; prompt_tokens is the total
        fake_response = SimpleNamespace(
            id='msg_x', model='claude-opus-5-5', stop_reason='end_turn', stop_details=None,
            content=[SimpleNamespace(type='thinking', thinking=''), SimpleNamespace(type='text', text='hello')],
            usage=SimpleNamespace(input_tokens=100, output_tokens=7,
                                  cache_read_input_tokens=2000, cache_creation_input_tokens=300))
        client = SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(create=lambda **kw: fake_response)))
        model._client = client
        reply = model.query([{'role': 'user', 'content': 'U'}])
        self.assertEqual(reply['content'], 'hello')
        usage = reply['extra']['response']['usage']
        self.assertEqual(usage['prompt_tokens'], 2400)
        self.assertEqual(usage['uncached_input_tokens'], 100)
        self.assertEqual(usage['completion_tokens'], 7)
        self.assertEqual(reply['extra']['response']['choices'][0]['finish_reason'], 'stop')
        fake_response.stop_reason = 'refusal'
        reply = model.query([{'role': 'user', 'content': 'U'}])
        self.assertEqual(reply['content'], '')
        self.assertEqual(reply['extra']['response']['choices'][0]['finish_reason'], 'refusal')

    def test_settings_and_key_file(self):
        os.environ['MSWEA_EXTRACT_EFFORT'] = 'low'
        os.environ['MSWEA_EXTRACT_FALLBACKS'] = '0'
        self.assertEqual(claude_extract.extract_settings()['effort'], 'low')
        self.assertFalse(claude_extract.extract_settings()['fallbacks'])
        key_file = self.directory / 'key'
        key_file.write_text('sk-test\n')
        os.environ['AGENTCTX_ANTHROPIC_API_KEY_FILE'] = str(key_file)
        self.assertEqual(claude_extract.resolve_api_key(), 'sk-test')
        os.environ['ANTHROPIC_API_KEY'] = 'sk-env'
        self.assertEqual(claude_extract.resolve_api_key(), 'sk-env')
        os.environ['MSWEA_EXTRACT_EFFORT'] = 'ultra'
        with self.assertRaises(ValueError):
            claude_extract.extract_settings()


if __name__ == '__main__':
    unittest.main()
