"""MSWEA_SELECT_BACKEND=jev: per-message Jev judgements behind online_claude_select, without API calls.
Run: venv/bin/python -m unittest tests/test_jev_select.py -v
"""
import json
import os
import re
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


class ProviderTests(unittest.TestCase):
    def test_typesafe_is_the_only_provider_and_the_base_url_is_overridable(self):
        with patch.dict(os.environ, {'TYPESAFE_BASE_URL': '', 'MSWEA_JEV_MODEL': ''}, clear=False):
            self.assertEqual(jev_select.resolve_provider(), ('typesafe', jev_select.DEFAULT_BASE_URL))
            self.assertEqual(jev_select.jev_settings()['model'], 'jev-latest')
        with patch.dict(os.environ, {'TYPESAFE_BASE_URL': 'https://proxy.example/v1'}, clear=False):
            self.assertEqual(jev_select.resolve_provider(), ('typesafe', 'https://proxy.example/v1'))
        with patch.dict(os.environ, {'TYPESAFE_API_KEY': 'sk-test'}, clear=False):
            self.assertEqual(jev_select.resolve_api_key(), 'sk-test')


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

    def test_select_lines_rebuilds_a_kept_output_as_ranges_in_the_agent(self):
        os.environ['MSWEA_JEV_SELECT_LINES'] = '20'
        os.environ['MSWEA_JEV_LINE_THRESHOLD'] = '0.5'
        self.environment = LongEnvironment()
        transport = SelectLineTransport(probs={'[m00003 ': 0.9, '[m00004 ': 0.9, '[m00005 ': 0.2, '[m00006 ': 0.2},
                                        line_probs={'FAILED': 0.9})
        agent = self.agent()
        self.run_steps(agent, transport, 4)
        # Context after the second selection (before call 4): [system, task, a1, obs1 trimmed, a3, obs3, a4, obs4]
        uids = [m['extra']['uid'] for m in agent.messages]
        self.assertEqual(uids[:4], ['m00001', 'm00002', 'm00003', 'm00004'])
        obs1 = agent.messages[3]
        self.assertIsNot(obs1, agent._full_messages[3])                   # a trimmed copy, same uid
        full_obs1 = agent._full_messages[3]['content']                  # the observation template wraps the output
        self.assertIn('FAILED test_1', obs1['content'])
        self.assertIn('[... 40 lines omitted ...]', obs1['content'])
        self.assertNotIn('noise 1-5', obs1['content'])
        kept = obs1['extra']['selection']
        self.assertEqual(len(kept['kept_lines']), 1)
        self.assertEqual(kept['total_lines'], full_obs1.count('\n') + 1)
        self.assertIn('noise 1-39', full_obs1)                            # the history is untouched
        self.assertNotIn('omitted', full_obs1)
        events = [json.loads(l) for l in (self.directory / 'compression_events.jsonl').read_text().splitlines()]
        self.assertEqual([r['uid'] for r in events[0]['replaced']], ['m00004'])
        self.assertIn('[... 40 lines omitted ...]', events[0]['replaced'][0]['new_content'])
        recs = self.log()['online_claude_select_events']
        sel = recs[1]['selection']
        self.assertEqual((sel['kept_whole'], sel['kept_partial'], sel['dropped']), (1, 1, 2))
        self.assertEqual(sel['keep'], {'m00003': None, 'm00004': kept['kept_lines']})
        self.assertEqual(sel['jev']['select_lines'], 20)
        self.assertEqual(sel['jev']['line_requests'], 1)
        self.assertEqual(sel['jev']['lines']['m00004']['ranges'], kept['kept_lines'])
        outcomes = self.log()['summary_outcomes']
        self.assertEqual(outcomes[1]['attempts'], 4 + 1)                 # message judgements + line request
        judgements = [json.loads(l) for l in (self.directory / 'jev_judgements.jsonl').read_text().splitlines()]
        self.assertEqual([j['kind'] for j in judgements if 'kind' in j], ['select_lines', 'select_lines'])

    def test_backend_setting_is_validated(self):
        os.environ['MSWEA_SELECT_BACKEND'] = 'coinflip'
        with self.assertRaises(ValueError):
            memory.select_backend()


if __name__ == '__main__':
    unittest.main()


class LineTransport:
    """Fake TypeSafe for the line-level extractor: answers every noul question of a
    request by the content of the line it names (``probs`` maps a substring to p)."""
    def __init__(self, probs, default=0.1, script=None):
        self.probs, self.default, self.script = probs, default, list(script or [])
        self.bodies, self.headers = [], []

    def __call__(self, body, headers):
        self.bodies.append(body); self.headers.append(headers)
        if self.script:
            return self.script.pop(0)
        lines = {}
        for raw in body['state'].split('\n'):
            if raw[:1] == 'L' and '| ' in raw[:7]:
                lines[raw.split('|', 1)[0]] = raw.split('| ', 1)[1]
        answers = {}
        for key, q in body['questions'].items():
            ids = re.findall(r'L\d{4}', q['instructions']) or [key]
            lo, hi = int(ids[0][1:]), int(ids[-1][1:])
            p = self.default
            for i in range(lo, hi + 1):            # a block takes the highest p of its lines
                text = lines.get(f'L{i:04d}', '')
                for sub, value in self.probs.items():
                    if sub in text:
                        p = max(p, value)
            answers[key] = {'type': 'noul', 'noul': p}
        return 200, {'model': 'jev-1.14.0', 'request_id': f'req_{len(self.bodies)}', 'answers': answers,
                     'usage': {'input_tokens': 500, 'output_tokens': 0}}, None


class SelectLineTransport:
    """Fake TypeSafe for a selection with MSWEA_JEV_SELECT_LINES: message judgements
    (the ``needed`` question) are answered by candidate substring as FakeTransport does,
    line requests (``L0001``... questions) by line content as LineTransport does."""
    def __init__(self, probs, line_probs, line_default=0.1, line_status=None):
        self.messages = FakeTransport(probs=probs)
        self.lines = LineTransport(line_probs, default=line_default)
        self.line_status = line_status
        self.bodies, self.headers = [], []

    def __call__(self, body, headers):
        self.bodies.append(body); self.headers.append(headers)
        if jev_select.QUESTION_NAME in body['questions']:
            return self.messages(body, headers)
        if self.line_status:
            return self.line_status, {'detail': 'line judge down'}, None
        return self.lines(body, headers)

    @property
    def line_bodies(self):
        return [b for b in self.bodies if jev_select.QUESTION_NAME not in b['questions']]


class SelectLinesTests(unittest.TestCase):
    """jev_select_window() with MSWEA_JEV_SELECT_LINES: kept long observations become line ranges."""
    LONG = '\n'.join(['Collecting pkg', 'Downloading pkg.whl', 'Installed pkg',
                      'FAILED tests/test_x.py::test_a - AssertionError', 'E   assert 1 == 2']
                     + ['noise %d' % i for i in range(60)])

    def setUp(self):
        self.env = patch.dict(os.environ, {'MSWEA_JEV_JUDGEMENT_LOG': '0', 'MSWEA_JEV_SELECT_LINES': '40',
                                           'MSWEA_JEV_LINE_THRESHOLD': '0.5'}, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)
        self.window = [msg('assistant', 'cat foo.py', 'u1'), msg('user', 'def f():\n  return 1', 'u2'),
                       msg('assistant', 'pytest -x', 'u3'), msg('user', self.LONG, 'u4'),
                       msg('assistant', 'pip list', 'u5'), msg('user', self.LONG, 'u6')]
        self.kept = [msg('assistant', 'pytest tests/', 'u7'), msg('user', '1 failed', 'u8')]

    def run_window(self, transport, budget=None):
        client = jev_select.JevClient(SETTINGS, transport=transport)
        return jev_select.jev_select_window(
            'fix f()', self.window, self.kept, set(), budget_tokens=budget,
            render=memory._select_render_message, anchor=False, token_of=lambda m: memory.count_tokens([m]),
            client=client)

    def test_kept_long_observation_is_kept_as_line_ranges(self):
        tr = SelectLineTransport(probs={'[u1 ': 0.9, '[u2 ': 0.9, '[u3 ': 0.9, '[u4 ': 0.9, '[u5 ': 0.2, '[u6 ': 0.2},
                                 line_probs={'FAILED': 0.9, 'assert': 0.8})
        selection, rec, pt, ct, lat, ids = self.run_window(tr)
        self.assertEqual(selection, {'u1': None, 'u2': None, 'u3': None, 'u4': [(4, 5)]})
        # Six message judgements, one line request for u4 only: u2 is short, u6 was dropped.
        self.assertEqual(len(tr.bodies), 7)
        self.assertEqual(len(tr.line_bodies), 1)
        state = tr.line_bodies[0]['state']
        self.assertIn('context window is being rebuilt', state)          # LINE_PREAMBLE_SELECT
        self.assertNotIn('cannot be recovered', state)
        self.assertIn('Task statement:\nfix f()', state)
        self.assertIn('[u3 assistant]\npytest -x', state)                # the command that produced it
        self.assertIn('L0004| FAILED', state)
        self.assertEqual(len(tr.line_bodies[0]['questions']), 65)
        self.assertEqual(rec['select_lines'], 40)
        self.assertEqual(rec['requests'], 6)
        self.assertEqual(rec['line_requests'], 1)
        self.assertEqual((rec['line_trimmed'], rec['line_errors']), (1, 0))
        self.assertEqual(list(rec['lines']), ['u4'])
        u4 = rec['lines']['u4']
        self.assertEqual((u4['ranges'], u4['lines'], u4['kept_lines']), ([[4, 5]], 65, 2))
        self.assertLess(u4['tokens_after'], u4['tokens_before'])
        self.assertIsNone(u4['error'])
        self.assertEqual(pt, 600 + 500)                                   # message + line usage
        self.assertEqual(len(ids), 7)
        rebuilt = memory.apply_selection(self.window, selection)
        self.assertEqual([m['extra']['uid'] for m in rebuilt], ['u1', 'u2', 'u3', 'u4'])
        self.assertEqual(rebuilt[3]['content'],
                         '[... 3 lines omitted ...]\nFAILED tests/test_x.py::test_a - AssertionError\nE   assert 1 == 2\n'
                         '[... 60 lines omitted ...]')

    def test_cap_admits_by_trimmed_size(self):
        tr = SelectLineTransport(probs={'[u1 ': 0.9, '[u2 ': 0.9, '[u3 ': 0.9, '[u4 ': 0.95, '[u5 ': 0.2, '[u6 ': 0.2},
                                 line_probs={'FAILED': 0.9})
        whole = memory.count_tokens([self.window[3]])
        budget = whole - 10                                                # u4 whole does not fit
        selection, rec, *_ = self.run_window(tr, budget=budget)
        self.assertIn('u4', selection)
        self.assertEqual(selection['u4'], [(4, 4)])
        self.assertEqual(rec['capped_out'], [])
        with patch.dict(os.environ, {'MSWEA_JEV_SELECT_LINES': '0'}):
            selection, rec, *_ = self.run_window(tr, budget=budget)
        self.assertNotIn('u4', selection)                                  # whole-message cell: ranked out
        self.assertEqual(rec['capped_out'], ['u4'])
        self.assertNotIn('lines', rec)

    def test_failed_line_judge_keeps_the_output_whole(self):
        tr = SelectLineTransport(probs={'[u': 0.1, '[u4 ': 0.9}, line_probs={}, line_status=400)
        selection, rec, *_ = self.run_window(tr)
        self.assertEqual(selection, {'u4': None})
        self.assertEqual((rec['line_trimmed'], rec['line_errors']), (0, 1))
        self.assertTrue(rec['lines']['u4']['error'].startswith('JevAPIError'))
        self.assertEqual(rec['lines']['u4']['tokens_after'], rec['lines']['u4']['tokens_before'])
        tr = SelectLineTransport(probs={'[u': 0.1, '[u4 ': 0.9}, line_probs={}, line_status=401)
        with self.assertRaises(jev_select.JevAPIError):
            self.run_window(tr)

    def test_turn_unit_trims_its_observation(self):
        tr = SelectLineTransport(probs={'[u': 0.1, '[u3 ': 0.9}, line_probs={'FAILED': 0.9})
        with patch.dict(os.environ, {'MSWEA_JEV_UNIT': 'turn'}):
            selection, rec, *_ = self.run_window(tr)
        self.assertEqual(selection, {'u3': None, 'u4': [(4, 4)]})
        self.assertEqual(rec['units'], 3)
        self.assertEqual(rec['line_requests'], 1)


class LongEnvironment(Environment):
    def execute(self, action):
        self.commands.append(action['command'])
        n = len(self.commands)
        lines = ['FAILED test_%d' % n] + ['noise %d-%d' % (n, i) for i in range(40)]
        return {'output': '\n'.join(lines), 'returncode': 0, 'exception_info': None}


class LineExtractTests(unittest.TestCase):
    """jev_extract_output() and extract_tool_output() under MSWEA_OUTPUT_EXTRACT_BACKEND=jev."""
    OUT = '\n'.join(['Collecting pkg', 'Downloading pkg.whl', 'Installed pkg',
                     'FAILED tests/test_x.py::test_a - AssertionError', 'E   assert 1 == 2',
                     'noise', 'noise', 'def target():', '    return 1', 'noise'])

    def test_lines_are_judged_in_one_request_and_merged_into_ranges(self):
        tr = LineTransport({'FAILED': 0.9, 'assert': 0.8, 'def target': 0.7, 'return 1': 0.6})
        client = jev_select.JevClient(SETTINGS, transport=tr)
        with patch.dict(os.environ, {'MSWEA_JEV_JUDGEMENT_LOG': '0'}, clear=False):
            ranges, rec, pt, ct, lat, ids = jev_select.jev_extract_output('task', '[m1 assistant]\npytest', self.OUT, 'm2', client=client)
        self.assertEqual(ranges, [(4, 5), (8, 9)])
        self.assertEqual(len(tr.bodies), 1)                      # one request for the whole output
        self.assertEqual(len(tr.bodies[0]['questions']), 10)     # one noul per line
        self.assertIn('L0004| FAILED', tr.bodies[0]['state'])
        self.assertIn('Task statement:\ntask', tr.bodies[0]['state'])
        self.assertEqual(rec['kept_lines'], 4)
        self.assertEqual(rec['probs']['L0004'], 0.9)
        self.assertEqual(pt, 500)

    def test_pad_block_and_whole_or_nothing(self):
        tr = LineTransport({'FAILED': 0.9})
        client = jev_select.JevClient(SETTINGS, transport=tr)
        with patch.dict(os.environ, {'MSWEA_JEV_JUDGEMENT_LOG': '0', 'MSWEA_JEV_LINE_PAD': '1'}, clear=False):
            ranges, *_ = jev_select.jev_extract_output('task', '', self.OUT, 'm2', client=client)
        self.assertEqual(ranges, [(3, 5)])
        with patch.dict(os.environ, {'MSWEA_JEV_JUDGEMENT_LOG': '0', 'MSWEA_JEV_LINE_BLOCK': '4'}, clear=False):
            ranges, rec, *_ = jev_select.jev_extract_output('task', '', self.OUT, 'm2', client=client)
        self.assertEqual(rec['blocks'], 3)
        self.assertEqual(ranges, [(1, 4)])                        # the block holding the FAILED line
        with patch.dict(os.environ, {'MSWEA_JEV_JUDGEMENT_LOG': '0', 'MSWEA_JEV_LINE_THRESHOLD': '0.05'}, clear=False):
            ranges, *_ = jev_select.jev_extract_output('task', '', self.OUT, 'm2', client=client)
        self.assertIsNone(ranges)                                 # everything kept -> whole
        with patch.dict(os.environ, {'MSWEA_JEV_JUDGEMENT_LOG': '0', 'MSWEA_JEV_LINE_THRESHOLD': '0.95'}, clear=False):
            ranges, *_ = jev_select.jev_extract_output('task', '', self.OUT, 'm2', client=client)
        self.assertEqual(ranges, [])                              # nothing kept

    def test_failed_request_keeps_its_lines_and_auth_raises(self):
        tr = LineTransport({}, script=[(500, {'detail': 'boom'}, None)] * 3)
        client = jev_select.JevClient(SETTINGS, transport=tr)
        with patch.dict(os.environ, {'MSWEA_JEV_JUDGEMENT_LOG': '0'}, clear=False):
            with self.assertRaises(jev_select.JevAPIError):      # the only request failed -> every request failed
                jev_select.jev_extract_output('task', '', self.OUT, 'm2', client=client)
        tr = LineTransport({}, script=[(401, {'detail': 'nope'}, None)])
        client = jev_select.JevClient(SETTINGS, transport=tr)
        with patch.dict(os.environ, {'MSWEA_JEV_JUDGEMENT_LOG': '0'}, clear=False):
            with self.assertRaises(jev_select.JevAPIError) as cm:
                jev_select.jev_extract_output('task', '', self.OUT, 'm2', client=client)
        self.assertEqual(cm.exception.status, 401)

    def test_extract_tool_output_rewrites_the_observation_through_jev(self):
        tr = LineTransport({'FAILED': 0.9, 'assert': 0.8})
        obs = msg('user', self.OUT, 'm2')
        cmd = msg('assistant', 'pytest -x', 'm1')
        with patch.dict(os.environ, {'MSWEA_OUTPUT_EXTRACT_BACKEND': 'jev', 'MSWEA_JEV_JUDGEMENT_LOG': '0'}, clear=False), \
             patch.object(jev_select, 'get_jev_client', lambda: jev_select.JevClient(SETTINGS, transport=tr)):
            new_content, record, pt, ct, lat = memory.extract_tool_output(obs, cmd, 'task')
        self.assertEqual(record['outcome'], 'trimmed')
        self.assertEqual(record['keep'], [[4, 5]])
        self.assertEqual(record['backend'], 'jev')
        self.assertEqual(record['jev']['requests'], 1)
        self.assertTrue(new_content.startswith(memory.OUTPUT_EXTRACT_NOTE_FMT.format(kept=2, total=10)))
        self.assertIn('FAILED tests/test_x.py', new_content)
        self.assertNotIn('Collecting pkg', new_content)
        self.assertIn('[... 3 lines omitted ...]', new_content)
        outcome = memory.pop_summary_outcome()
        self.assertEqual(outcome['backend'], 'jev')
        self.assertTrue(outcome['accepted'])
        self.assertEqual(outcome['response_ids'], ['req_1'])
