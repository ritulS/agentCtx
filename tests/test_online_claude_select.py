"""online_claude_select: Claude picks original messages / output lines before every call, without API calls.
Run: venv/bin/python -m unittest tests/test_online_claude_select.py -v
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
    from agentctx.compression import claude_extract
    from litellm import ModelResponse
    from minisweagent.agents.default import DefaultAgent
    from minisweagent.models.litellm_textbased_model import LitellmTextbasedModel
except ImportError as exc:
    raise unittest.SkipTest(str(exc))


class Environment:
    """Scripted multi-line observations so line selection has something to cut."""
    def __init__(self):
        self.commands = []

    def get_template_vars(self):
        return {}

    def serialize(self):
        return {}

    def execute(self, action):
        self.commands.append(action['command'])
        n = len(self.commands)
        out = '\n'.join(f'line{n}-{i}' for i in range(1, 6))   # 5 lines: lineN-1 .. lineN-5
        return {'output': out, 'returncode': 0, 'exception_info': None}


class FakeSelector(claude_extract.ClaudeExtractModel):
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
        if callable(reply):
            reply = reply(messages)
        text, finish = reply
        return {'role': 'assistant', 'content': text,
                'extra': {'response': {'id': f'msg_{len(self.prompts)}',
                                       'usage': {'prompt_tokens': 500, 'completion_tokens': 50},
                                       'choices': [{'finish_reason': finish}]}}}

    def blocks(self, i):
        """The text blocks of the i-th prompt's user message."""
        return [b['text'] for b in self.prompts[i][1]['content']]


def selection(body):
    return (f'{memory.SEL_OPEN_MARKER}\n{body}\n{memory.SEL_CLOSE_MARKER}', 'stop')


def msg(role, content, uid):
    return {'role': role, 'content': content, 'extra': {'uid': uid}}


class ParseAndApplyTests(unittest.TestCase):
    """parse_selection() / apply_selection() on a hand-built window."""
    def setUp(self):
        self.window = [
            msg('assistant', 'THOUGHT\n```bash\npip install x\n```', 'm00003'),
            msg('user', '\n'.join(f'l{i}' for i in range(1, 11)), 'm00004'),   # 10 lines
            msg('assistant', 'THOUGHT\n```bash\ncat a.py\n```', 'm00005'),
            msg('user', 'a\nb\nc', 'm00006'),
        ]

    def test_grammar_and_merging(self):
        sel, why = memory.parse_selection(
            'keep m00003\nkeep m00004 L2-3, L5\nkeep m00004 L4\n\ndrop m00005\nKEEP m00006 lines 1-2', self.window)
        self.assertIsNone(why)
        self.assertEqual(sel, {'m00003': None, 'm00004': [(2, 5)], 'm00006': [(1, 2)]})
        out = memory.apply_selection(self.window, sel)
        self.assertEqual([m['extra']['uid'] for m in out], ['m00003', 'm00004', 'm00006'])
        self.assertIs(out[0], self.window[0])                       # whole keep = original object
        self.assertEqual(out[1]['content'],
                         '[... 1 lines omitted ...]\nl2\nl3\nl4\nl5\n[... 5 lines omitted ...]')
        self.assertEqual(out[1]['extra']['selection'], {'kept_lines': [[2, 5]], 'total_lines': 10})
        self.assertEqual(out[2]['content'], 'a\nb\n[... 1 lines omitted ...]')
        self.assertEqual(self.window[1]['content'].count('\n'), 9)   # original untouched

    def test_rejections(self):
        for body, why in [
            ('keep m00003\nNote: the agent should run tests next', 'unparseable_line'),
            ('keep m00099', 'unknown_uid'),
            ('keep m00003 L1-2', 'range_on_assistant'),
            ('keep m00004 L9-12', None),            # end clamped to the message
            ('keep m00004 L11', 'range_out_of_bounds'),
            ('keep m00004 L0-3', 'range_out_of_bounds'),
            ('none', None),                          # keeping nothing is a decision, not an error
        ]:
            sel, got = memory.parse_selection(body, self.window)
            self.assertEqual(got, why, body)
        sel, _ = memory.parse_selection('keep m00004 L9-12', self.window)
        self.assertEqual(sel, {'m00004': [(9, 10)]})


class OnlineClaudeSelectTests(unittest.TestCase):
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
        os.environ['MSWEA_TOKEN_BUDGET'] = ''
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

    def run_steps(self, agent, selector, n):
        cmds = [self.response(f'```mswea_bash_command\necho step{i}\n```') for i in range(n)]
        with patch.object(claude_extract, 'get_extract_model', return_value=selector), \
             patch.object(self.model, '_query', side_effect=cmds):
            for _ in range(n):
                agent.step()

    def test_selector_sees_ids_and_numbered_lines_and_context_is_rebuilt_verbatim(self):
        # uids: m00001 system, m00002 task, m00003 a1, m00004 obs1, m00005 a2, m00006 obs2, ...
        # keep_recent defaults to 1 (widened to the turn), so before call 3 the window is
        # [a1, obs1] and [a2, obs2] stays raw; before call 4 the window is [a1, obs1, a2, obs2].
        # Observations render through the template: line 1 <returncode>, line 2 <output>,
        # lines 3-7 the 5 output lines (the last one closes </output>).
        selector = FakeSelector([
            selection('keep m00003\nkeep m00004 L4-5'),
            selection('keep m00004 L7\ndrop m00003\nkeep m00006'),
        ])
        agent = self.agent()
        self.run_steps(agent, selector, 4)
        full = [m['extra']['uid'] for m in agent._full_messages]   # uids skip one per compression event
        # Prompt 1: task as reference, one block per window message with ids, numbered output lines.
        blocks = selector.blocks(0)
        self.assertIn('fix the bug in foo.py', blocks[0])
        self.assertNotIn('system', blocks[0].split('History:')[0].replace('Task statement', ''))
        self.assertTrue(blocks[1].startswith('[m00003 assistant]\n'))
        self.assertIn('echo step0', blocks[1])
        self.assertTrue(blocks[2].startswith('[m00004 user, 7 lines]'))
        self.assertIn('4| line1-2', blocks[2])
        self.assertIn('cache_control', selector.prompts[0][1]['content'][2])   # breakpoint on the last history block
        self.assertNotIn('cache_control', selector.prompts[0][1]['content'][-1])
        self.assertNotIn('echo step1', ''.join(blocks))       # the kept tail is NOT in the window
        self.assertNotIn('[m00005', ''.join(blocks))
        # Prompt 2 covers the complete history again (a1, obs1 included, not a previous selection).
        blocks2 = selector.blocks(1)
        self.assertIn('[m00003 assistant]', ''.join(blocks2))
        self.assertIn('[m00006 user', ''.join(blocks2))
        self.assertNotIn('[m00007', ''.join(blocks2))
        # Context after the second selection (before call 4), then a4/obs4 appended by step 4:
        # [system, task, obs1(L7 only), obs2 (whole, original object), a3, obs3, a4, obs4]
        uids = [m['extra']['uid'] for m in agent.messages]
        self.assertEqual(uids, full[:2] + [full[3], full[5]] + full[6:])
        self.assertEqual(agent.messages[2]['content'], '[... 6 lines omitted ...]\nline1-5</output>')
        self.assertIs(agent.messages[3], agent._full_messages[5])
        self.assertEqual(len(agent._full_messages), 10)
        # Event log: two online_claude_select events; a partial keep is "replaced", drops are "dropped".
        events = [json.loads(l) for l in (self.directory / 'compression_events.jsonl').read_text().splitlines()]
        self.assertEqual([e['kind'] for e in events], ['online_claude_select'] * 2)
        self.assertEqual([e['step'] for e in events], [2, 3])
        self.assertEqual(events[0]['replaced'][0]['uid'], 'm00004')
        self.assertIn('m00003', events[1]['dropped'])
        self.assertEqual(events[1]['after_uids'], full[:2] + [full[3], full[5]] + full[6:8])
        log = self.log()
        recs = log['online_claude_select_events']
        self.assertEqual([r['step'] for r in recs], [2, 3])
        self.assertTrue(all(r['accepted'] for r in recs))
        self.assertEqual(recs[1]['selection']['kept_whole'], 1)
        self.assertEqual(recs[1]['selection']['kept_partial'], 1)
        self.assertEqual(recs[1]['selection']['dropped'], 2)
        self.assertEqual(recs[1]['selection']['lines_kept'], 1 + 7)
        self.assertIn('tokens_full', recs[1])
        self.assertEqual(log['online_claude_select_accepted'], 2)
        self.assertEqual(log['extract_model']['model'], 'claude-opus-5-5')
        self.assertEqual([o['primitive'] for o in log['summary_outcomes']], ['online_claude_select'] * 2)
        self.assertEqual(log['summary_outcomes'][1]['flags']['selection']['keep'],
                         {'m00004': [[7, 7]], 'm00006': None})

    def test_invalid_replies_are_retried_then_leave_the_context_unchanged(self):
        selector = FakeSelector([
            selection('keep m00003\nThe agent should now edit foo.py'),   # prose -> unparseable_line
            selection('keep m00099'),                                      # unknown uid
            selection('keep m00003 L1'),                                   # range on an assistant message
            selection('keep m00004 L1'),                                   # accepted
        ])
        agent = self.agent()
        self.run_steps(agent, selector, 4)
        attempts = [json.loads(l) for l in (self.directory / 'summary_attempts.jsonl').read_text().splitlines()]
        self.assertEqual([a['rejected'] for a in attempts],
                         ['unparseable_line', 'unknown_uid', 'range_on_assistant', None])
        self.assertEqual([a['outcome'] for a in attempts], ['retry', 'fallback', 'retry', 'accepted'])
        recs = self.log()['online_claude_select_events']
        self.assertEqual([r['accepted'] for r in recs], [False, True])
        self.assertEqual(self.log()['summary_outcomes'][0]['fallback'], 'unchanged')
        # After the fallback the context before call 3 was the full history (nothing dropped);
        # before call 4 only line 1 of obs1 survived from [a1, obs1, a2, obs2].
        events = [json.loads(l) for l in (self.directory / 'compression_events.jsonl').read_text().splitlines()]
        self.assertEqual([e['step'] for e in events], [3])
        full = [m['extra']['uid'] for m in agent._full_messages]
        uids = [m['extra']['uid'] for m in agent.messages]
        self.assertEqual(uids, full[:2] + [full[3]] + full[6:])
        self.assertEqual(agent.messages[2]['content'], '<returncode>0</returncode>\n[... 6 lines omitted ...]')

    def test_keep_recent_zero_and_empty_selection(self):
        os.environ['MSWEA_EXTRACT_KEEP_RECENT'] = '0'
        def keep_last_output(messages):   # keep only the newest observation of the window shown
            header = messages[1]['content'][-2]['text'].split('\n')[0]   # '[mXXXXX user, 7 lines]'
            return selection(f'keep {header[1:7]}')
        selector = FakeSelector([selection('none'), keep_last_output])
        agent = self.agent()
        self.run_steps(agent, selector, 3)
        # keep_recent=0: before call 2 the window is [a1, obs1]; an empty selection drops both,
        # so call 2 saw [system, task]. Before call 3 the window is [a1, obs1, a2, obs2].
        full = [m['extra']['uid'] for m in agent._full_messages]
        blocks = selector.blocks(0)
        self.assertIn('[m00004 user', ''.join(blocks))
        self.assertEqual(selector.blocks(1)[-2].split('\n')[0], f'[{full[5]} user, 7 lines]')
        uids = [m['extra']['uid'] for m in agent.messages]
        self.assertEqual(uids, full[:2] + [full[5]] + full[6:])
        events = [json.loads(l) for l in (self.directory / 'compression_events.jsonl').read_text().splitlines()]
        self.assertEqual(events[0]['after_uids'], ['m00001', 'm00002'])
        self.assertEqual(events[0]['dropped'], ['m00003', 'm00004'])

    def test_errors_are_logged_then_raised_after_the_cap(self):
        os.environ['MSWEA_EXTRACT_MAX_CONSECUTIVE_ERRORS'] = '2'
        selector = FakeSelector([RuntimeError('boom 1'), RuntimeError('boom 2')])
        agent = self.agent()
        # keep_recent=1 (default) widens the kept tail to the whole newest turn, so the
        # first non-empty window appears before call 3; the cap is reached before call 4.
        with self.assertRaises(RuntimeError):
            self.run_steps(agent, selector, 4)
        recs = self.log()['online_claude_select_events']
        self.assertEqual([r['error'] for r in recs], ['RuntimeError: boom 1', 'RuntimeError: boom 2'])
        self.assertEqual(self.log()['online_claude_select_errors'], 2)

    def test_request_passes_text_blocks_through(self):
        model = claude_extract.ClaudeExtractModel(
            settings={'model': 'm', 'effort': 'low', 'max_tokens': 10, 'timeout_s': 1.0, 'fallbacks': False},
            client=object())
        blocks = [{'type': 'text', 'text': 'A'}, {'type': 'text', 'text': 'B', 'cache_control': {'type': 'ephemeral'}},
                  {'type': 'text', 'text': 'C'}]
        request = model._request([{'role': 'system', 'content': 'S'}, {'role': 'user', 'content': blocks}])
        self.assertEqual(request['system'], [{'type': 'text', 'text': 'S', 'cache_control': {'type': 'ephemeral'}}])
        self.assertEqual(request['messages'], [{'role': 'user', 'content': blocks}])
        self.assertIsNot(request['messages'][0]['content'][1], blocks[1])   # copied, not aliased


if __name__ == '__main__':
    unittest.main()
