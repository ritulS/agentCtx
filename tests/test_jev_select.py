"""MSWEA_SELECT_BACKEND=jev: per-message Jev judgements behind online_claude_select, without API calls.
Run: venv/bin/python -m unittest tests/test_jev_select.py -v
"""
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
    from agentctx.compression import jev_select
    from litellm import ModelResponse
    from minisweagent.agents.default import DefaultAgent
    from minisweagent.models.litellm_textbased_model import LitellmTextbasedModel
except ImportError as exc:
    raise unittest.SkipTest(str(exc))


def msg(role, content, uid):
    return {'role': role, 'content': content, 'extra': {'uid': uid}}


class FakeTransport:
    """Scripted (status, payload) per request; records bodies and headers. ``probs``
    maps a substring of the candidate text to the noul returned (default 0.5);
    ``script`` is a list of (status, payload) consumed first, one per request."""
    def __init__(self, probs=None, script=None):
        self.probs = probs or {}
        self.script = list(script or [])
        self.bodies = []
        self.headers = []

    def __call__(self, body, headers):
        self.bodies.append(body)
        self.headers.append(headers)
        if self.script:
            return self.script.pop(0)
        candidate = body['state'].split('Candidate history message to judge:\n', 1)[-1]
        p = 0.5
        for key, value in self.probs.items():
            if key in candidate:
                p = value
        return 200, {'model': 'jev-1.14.0', 'request_id': f'req_{len(self.bodies)}',
                     'answers': {'needed': {'type': 'noul', 'noul': p}},
                     'usage': {'input_tokens': 100, 'output_tokens': 1}}, None


SETTINGS = {'provider': 'typesafe', 'model': 'jev-latest', 'base_url': 'x', 'threshold': 0.5,
            'anchor_bonus': 0.15, 'context_turns': 1, 'workers': 4, 'timeout_s': 5.0,
            'max_retries': 2, 'long_context': 'header'}


class DecideTests(unittest.TestCase):
    def rec(self, uid, p, index):
        return {'uid': uid, 'p': p, 'index': index, 'error': None if p is not None else 'x'}

    def test_threshold_bonus_and_errors(self):
        judgements = [self.rec('a', 0.9, 0), self.rec('b', 0.4, 1), self.rec('c', 0.4, 2), self.rec('d', None, 3)]
        sel, extras = jev_select.decide(judgements, {'c'}, 0.5, 0.15, None, token_of=lambda r: 1)
        self.assertEqual(list(sel), ['a', 'c', 'd'])         # b below; c lifted by the bonus; d errored -> kept
        self.assertEqual(extras['scores'], {'a': 0.9, 'b': 0.4, 'c': 0.55, 'd': None})
        self.assertEqual(extras['errors'], 1)
        sel, _ = jev_select.decide(judgements, set(), 0.5, 0.15, None, token_of=lambda r: 1)
        self.assertEqual(list(sel), ['a', 'd'])              # no previous context: no bonus

    def test_cap_ranks_by_score_newer_first_and_skips_what_does_not_fit(self):
        judgements = [self.rec('a', 0.6, 0), self.rec('b', 0.9, 1), self.rec('c', 0.6, 2), self.rec('d', 0.95, 3)]
        tokens = {'a': 10, 'b': 50, 'c': 10, 'd': 30}
        sel, extras = jev_select.decide(judgements, set(), 0.5, 0.0, 45, token_of=lambda r: tokens[r['uid']])
        # ranked d(0.95, 30) b(0.9, 50: does not fit) c(0.6, newer) a(0.6): d + c = 40, a = 50 > 45
        self.assertEqual(list(sel), ['c', 'd'])              # window order in the selection
        self.assertEqual(extras['capped_out'], ['b', 'a'])
        self.assertEqual(extras['kept_by_threshold'], 4)


class ClientTests(unittest.TestCase):
    def test_retries_then_succeeds_and_auth_fails_at_once(self):
        ok = (200, {'answers': {'needed': {'noul': 0.7}}, 'usage': {'input_tokens': 5, 'output_tokens': 0}, 'model': 'jev-1'}, 'r1')
        transport = FakeTransport(script=[(429, {'detail': 'slow down'}, None), (503, {}, None), ok])
        client = jev_select.JevClient(SETTINGS, transport=transport)
        with patch.object(jev_select.time, 'sleep') as sleep:
            reply = client.system_one('S', jev_select.needed_question())
        self.assertEqual(reply['answers']['needed']['noul'], 0.7)
        self.assertEqual(reply['attempts'], 3)
        self.assertEqual(reply['request_id'], 'r1')
        self.assertEqual([c.args[0] for c in sleep.call_args_list], [1, 2])
        self.assertEqual(transport.bodies[0]['model'], 'jev-latest')
        self.assertEqual(transport.bodies[0]['questions']['needed']['type'], 'noul')
        client = jev_select.JevClient(SETTINGS, transport=FakeTransport(script=[(401, {'detail': 'bad key'}, None)]))
        with self.assertRaises(jev_select.JevAPIError) as ctx:
            client.system_one('S', jev_select.needed_question())
        self.assertEqual(ctx.exception.status, 401)

    def test_transport_errors_are_exhausted(self):
        def boom(body, headers):
            raise ConnectionError('down')
        client = jev_select.JevClient(SETTINGS, transport=boom)
        with patch.object(jev_select.time, 'sleep'):
            with self.assertRaises(jev_select.JevAPIError) as ctx:
                client.system_one('S', jev_select.needed_question())
        self.assertIn('3 attempts', str(ctx.exception))

    def test_settings_validation_and_truncation(self):
        with patch.dict(os.environ, {'MSWEA_JEV_KEEP_THRESHOLD': '1.5'}):
            with self.assertRaises(ValueError):
                jev_select.jev_settings()
        with patch.dict(os.environ, {'MSWEA_JEV_LONG_CONTEXT': 'maybe'}):
            self.assertIn('error', jev_select.jev_model_info())
        with patch.dict(os.environ, {}, clear=True):
            s = jev_select.jev_settings()
        self.assertEqual((s['model'], s['threshold'], s['anchor_bonus'], s['workers']), ('jev-latest', 0.5, 0.15, 8))
        text, removed = jev_select._truncate_to('x' * 1000, 300)
        self.assertLessEqual(len(text.encode()), 300)
        self.assertIn('characters of this message are not shown', text)
        self.assertEqual(removed, 1000 - (len(text) - len(jev_select.TRUNCATED_NOTE.format(n=removed)) - 2))
        self.assertEqual(jev_select._truncate_to('short', 300), ('short', 0))


class WindowTests(unittest.TestCase):
    """jev_select_window() on a hand-built window: state content, parallel judgements, record."""
    def setUp(self):
        self.env = patch.dict(os.environ, {'MSWEA_JEV_JUDGEMENT_LOG': '0'}, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)
        self.window = [msg('assistant', 'cat foo.py', 'u1'), msg('user', 'def f():\n  return 1', 'u2'),
                       msg('assistant', 'ls', 'u3'), msg('user', 'a.py\nb.py\n' * 50, 'u4')]
        self.kept = [msg('assistant', 'pytest tests/', 'u5'), msg('user', '1 failed', 'u6')]

    def run_window(self, transport, prev=(), budget=None, anchor=True):
        client = jev_select.JevClient(SETTINGS, transport=transport)
        return jev_select.jev_select_window(
            'fix f()', self.window, self.kept, set(prev), budget_tokens=budget,
            render=memory._select_render_message, anchor=anchor, token_of=lambda m: memory.count_tokens([m]),
            client=client)

    def test_state_has_task_activity_and_one_candidate_each(self):
        transport = FakeTransport(probs={'[u1 ': 0.9, '[u2 ': 0.8, '[u3 ': 0.2, '[u4 ': 0.3})
        selection, rec, pt, ct, lat, ids = self.run_window(transport)
        self.assertEqual(list(selection), ['u1', 'u2'])
        self.assertEqual(len(transport.bodies), 4)
        states = sorted(b['state'] for b in transport.bodies)
        for state in states:
            self.assertIn('Task statement:\nfix f()', state)
            self.assertIn("The agent's newest turn", state)
            self.assertIn('[u5 assistant]\npytest tests/', state)          # the kept turn is the activity
            self.assertIn('[u6 user, 1 lines]', state)
            self.assertEqual(state.count('Candidate history message to judge:'), 1)
        self.assertTrue(any('[u4 user, 101 lines]' in s for s in states))
        self.assertTrue(all(h == {} for h in transport.headers))              # small: no long-context header
        self.assertEqual((pt, ct), (400, 4))
        self.assertEqual(rec['requests'], 4)
        self.assertEqual(rec['probs'], {'u1': 0.9, 'u2': 0.8, 'u3': 0.2, 'u4': 0.3})
        self.assertEqual(rec['resolved_model'], 'jev-1.14.0')
        self.assertEqual(sorted(ids), ['req_1', 'req_2', 'req_3', 'req_4'])
        self.assertEqual(rec['anchor_bonus'], 0.15)

    def test_anchor_bonus_cap_and_context_turns(self):
        transport = FakeTransport(probs={'[u1 ': 0.4, '[u2 ': 0.4, '[u3 ': 0.9, '[u4 ': 0.9})
        selection, rec, *_ = self.run_window(transport, prev={'u2'})
        self.assertEqual(list(selection), ['u2', 'u3', 'u4'])                  # u2 lifted to 0.55
        selection, rec, *_ = self.run_window(transport, prev={'u2'}, anchor=False)
        self.assertEqual(list(selection), ['u3', 'u4'])
        self.assertEqual(rec['anchor_bonus'], 0.0)
        # cap: u4 (0.9, ~300 tokens) does not fit in 60 tokens; u3 does; u2 (0.55) does
        selection, rec, *_ = self.run_window(transport, prev={'u2'}, budget=60)
        self.assertEqual(list(selection), ['u2', 'u3'])
        self.assertEqual(rec['capped_out'], ['u4'])
        with patch.dict(os.environ, {'MSWEA_JEV_CONTEXT_TURNS': '0'}):
            transport = FakeTransport()
            self.run_window(transport)
        self.assertNotIn("The agent's newest turn", transport.bodies[0]['state'])

    def test_long_context_header_or_truncation(self):
        big = [msg('user', 'x' * 40000, 'big')]
        self.window = big
        transport = FakeTransport()
        self.run_window(transport)
        self.assertEqual(transport.headers[0], {jev_select.LONG_CONTEXT_HEADER: 'true'})
        self.assertGreater(len(transport.bodies[0]['state']), 40000)
        with patch.dict(os.environ, {'MSWEA_JEV_LONG_CONTEXT': 'truncate'}):
            transport = FakeTransport()
            _, rec, *_ = self.run_window(transport)
        self.assertEqual(transport.headers[0], {})
        self.assertLess(len(transport.bodies[0]['state'].encode()), jev_select.LONG_CONTEXT_BYTES + 100)
        self.assertEqual(rec['truncated'], 1)

    def test_errors_keep_the_message_and_total_failure_raises(self):
        calls = {'n': 0}
        def flaky(body, headers):
            calls['n'] += 1
            if '[u3 ' in body['state']:
                return 400, {'detail': 'bad'}, None            # not retried, not fatal
            return 200, {'answers': {'needed': {'noul': 0.1}}, 'usage': {'input_tokens': 1}}, None
        selection, rec, *_ = self.run_window(flaky)
        self.assertEqual(list(selection), ['u3'])                             # errored -> kept; the rest drop
        self.assertEqual(rec['errors'], 1)
        self.assertEqual(rec['probs']['u3'], None)
        with patch.object(jev_select.time, 'sleep'):
            with self.assertRaises(jev_select.JevAPIError) as ctx:
                self.run_window(lambda b, h: (401, {'detail': 'no'}, None))
        self.assertIn('authentication', str(ctx.exception))
        with patch.object(jev_select.time, 'sleep'):
            with self.assertRaises(jev_select.JevAPIError) as ctx:
                self.run_window(lambda b, h: (400, {'detail': 'no'}, None))
        self.assertIn('every Jev judgement failed', str(ctx.exception))


class Environment:
    def __init__(self):
        self.commands = []

    def get_template_vars(self):
        return {}

    def serialize(self):
        return {}

    def execute(self, action):
        self.commands.append(action['command'])
        n = len(self.commands)
        return {'output': '\n'.join(f'line{n}-{i}' for i in range(1, 6)), 'returncode': 0, 'exception_info': None}


class AgentJevSelectTests(unittest.TestCase):
    """online_claude_select with MSWEA_SELECT_BACKEND=jev inside DefaultAgent."""
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
        os.environ['MSWEA_PRIMITIVE'] = 'online_claude_select'
        os.environ['MSWEA_SELECT_BACKEND'] = 'jev'
        os.environ['MSWEA_TOKEN_BUDGET'] = ''
        self.model = LitellmTextbasedModel(model_name='hosted_vllm/test', cost_tracking='ignore_errors')
        cost = patch.object(self.model, '_calculate_cost', return_value={'cost': 0.0})
        cost.start()
        self.addCleanup(cost.stop)
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

    def run_steps(self, agent, transport, n):
        cmds = [self.response(f'```mswea_bash_command\necho step{i}\n```') for i in range(n)]
        client = jev_select.JevClient(SETTINGS, transport=transport)
        with patch.object(jev_select, 'get_jev_client', return_value=client), \
             patch.object(self.model, '_query', side_effect=cmds):
            for _ in range(n):
                agent.step()

    def test_context_is_rebuilt_from_jev_judgements_and_everything_is_logged(self):
        # uids: m00001 system, m00002 task, m00003 a1, m00004 obs1, m00005 a2, m00006 obs2, ...
        # Before call 3 the window is [a1, obs1]; before call 4 [a1, obs1, a2, obs2] (uids skip
        # one per compression event: a3 is m00008).
        transport = FakeTransport(probs={'[m00003 ': 0.9, '[m00004 ': 0.2, '[m00005 ': 0.3, '[m00006 ': 0.7})
        agent = self.agent()
        self.run_steps(agent, transport, 4)
        full = [m['extra']['uid'] for m in agent._full_messages]
        self.assertEqual(len(transport.bodies), 2 + 4)
        # Context after the second selection (before call 4), then a4/obs4 appended by step 4:
        # [system, task, a1, obs2, a3, obs3, a4, obs4]; whole original objects, no line ranges.
        uids = [m['extra']['uid'] for m in agent.messages]
        self.assertEqual(uids, full[:2] + [full[2], full[5]] + full[6:])
        self.assertIs(agent.messages[2], agent._full_messages[2])
        self.assertIs(agent.messages[3], agent._full_messages[5])
        events = [json.loads(l) for l in (self.directory / 'compression_events.jsonl').read_text().splitlines()]
        self.assertEqual([e['kind'] for e in events], ['online_claude_select'] * 2)
        self.assertEqual(events[0]['dropped'], ['m00004'])
        self.assertEqual(events[0]['replaced'], [])
        self.assertEqual(events[1]['dropped'], ['m00005'])     # relative to the context before the event: obs1 was already out
        log = self.log()
        recs = log['online_claude_select_events']
        self.assertEqual([r['step'] for r in recs], [2, 3])
        self.assertTrue(all(r['accepted'] for r in recs))
        self.assertEqual((recs[0]['prompt_tokens'], recs[0]['completion_tokens']), (200, 2))
        sel = recs[1]['selection']
        self.assertEqual(sel['backend'], 'jev')
        self.assertEqual((sel['kept_whole'], sel['kept_partial'], sel['dropped']), (2, 0, 2))
        self.assertEqual(sel['keep'], {'m00003': None, 'm00006': None})
        self.assertEqual(sel['jev']['probs'], {'m00003': 0.9, 'm00004': 0.2, 'm00005': 0.3, 'm00006': 0.7})
        self.assertEqual(sel['jev']['requests'], 4)
        self.assertEqual(sel['jev']['threshold'], 0.5)
        self.assertEqual(sel['jev']['anchor_bonus'], 0.0)                 # not anchored here
        self.assertNotIn('anchor', sel)
        self.assertEqual(log['select_backend'], 'jev')
        self.assertEqual(log['jev_model']['model'], 'jev-latest')
        outcomes = log['summary_outcomes']
        self.assertEqual([o['primitive'] for o in outcomes], ['online_claude_select'] * 2)
        self.assertEqual([o['attempts'] for o in outcomes], [2, 4])
        self.assertEqual(outcomes[0]['rejections'], [])
        self.assertEqual(len(outcomes[1]['response_ids']), 4)
        judgements = [json.loads(l) for l in (self.directory / 'jev_judgements.jsonl').read_text().splitlines()]
        self.assertEqual(len(judgements), 6)
        self.assertEqual({j['uid'] for j in judgements[2:]}, {'m00003', 'm00004', 'm00005', 'm00006'})
        self.assertTrue(all(j['error'] is None for j in judgements))
        self.assertFalse((self.directory / 'summary_attempts.jsonl').exists())   # no generative reply to log

    def test_anchored_capped_cell_settings_apply(self):
        os.environ['MSWEA_SELECT_ANCHOR'] = '1'
        os.environ['MSWEA_SELECT_CAP'] = '100000'
        transport = FakeTransport(probs={'[m00003 ': 0.9, '[m00004 ': 0.3, '[m00005 ': 0.4, '[m00006 ': 0.7})
        agent = self.agent()
        self.run_steps(agent, transport, 4)
        recs = self.log()['online_claude_select_events']
        sel0, sel1 = recs[0]['selection'], recs[1]['selection']
        # Step 2: nothing was compressed yet, so every window message was "in context last
        # step" and gets the bonus: a1 1.05 kept, obs1 0.45 dropped.
        self.assertEqual(sel0['keep'], {'m00003': None})
        self.assertEqual(sel0['jev']['scores'], {'m00003': 1.05, 'm00004': 0.45})
        # Step 3: obs1 was out of context -> 0.3, dropped again; a2 was in (kept tail) -> 0.55, kept.
        self.assertEqual(sel1['keep'], {'m00003': None, 'm00005': None, 'm00006': None})
        self.assertEqual(sel1['jev']['anchor_bonus'], 0.15)
        self.assertEqual(sel1['jev']['scores'], {'m00003': 1.05, 'm00004': 0.3, 'm00005': 0.55, 'm00006': 0.85})
        self.assertTrue(sel1['anchor'])
        self.assertEqual(sel1['cap'], 100000)
        self.assertEqual((sel1['carried'], sel1['added'], sel1['removed']), (3, 0, 0))
        self.assertIsNotNone(sel1['budget_window'])

    def test_errors_are_logged_then_raised_after_the_cap(self):
        os.environ['MSWEA_EXTRACT_MAX_CONSECUTIVE_ERRORS'] = '2'
        agent = self.agent()
        with patch.object(jev_select.time, 'sleep'):
            with self.assertRaises(jev_select.JevAPIError):
                self.run_steps(agent, lambda b, h: (500, {'detail': 'down'}, None), 4)
        log = self.log()
        recs = log['online_claude_select_events']
        self.assertEqual(len(recs), 2)
        self.assertTrue(all(r['error'].startswith('JevAPIError') for r in recs))
        self.assertEqual(log['online_claude_select_errors'], 2)
        self.assertEqual(len(agent.messages), len(agent._full_messages))      # context untouched

    def test_backend_setting_is_validated(self):
        os.environ['MSWEA_SELECT_BACKEND'] = 'coinflip'
        with self.assertRaises(ValueError):
            memory.select_backend()


if __name__ == '__main__':
    unittest.main()
