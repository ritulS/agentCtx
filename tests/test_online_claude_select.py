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
            ('drop m00099', None),                   # nothing to drop: ignored
            ('keep m00003\ndrop m00099\ndrop m00004', None),
            ('keep m00001', 'unknown_uid'),          # outside the window's id range, not declared known
            ('keep m00003\nkeep m00001\nkeep m00004', 'unknown_uid'),
            ('keep m00003 L1-2', None),              # assistant message: range ignored, kept whole
            ('keep m00004 L9-12', None),            # end clamped to the message
            ('keep m00004 L11', 'range_out_of_bounds'),
            ('keep m00004 L0-3', 'range_out_of_bounds'),
            ('none', None),                          # keeping nothing is a decision, not an error
        ]:
            sel, got = memory.parse_selection(body, self.window)
            self.assertEqual(got, why, body)
        sel, _ = memory.parse_selection('keep m00004 L9-12', self.window)
        self.assertEqual(sel, {'m00004': [(9, 10)]})
        sel, _ = memory.parse_selection('keep m00003\ndrop m00099\ndrop m00004', self.window)
        self.assertEqual(sel, {'m00003': None})
        sel, _ = memory.parse_selection('keep m00003 L1-2', self.window)
        self.assertEqual(sel, {'m00003': None})
        # keep of a protected id (declared via known_uids) or of a gap inside the window's id range is ignored
        sel, why = memory.parse_selection('keep m00001\nkeep m00003', self.window, known_uids={'m00001', 'm00002'})
        self.assertEqual((why, sel), (None, {'m00003': None}))
        ids = sorted(m['extra']['uid'] for m in self.window)
        gap_window = [m for m in self.window if m['extra']['uid'] != ids[1]] if len(ids) > 2 else None
        if gap_window:
            sel, why = memory.parse_selection(f'keep {ids[0]}\nkeep {ids[1]}', gap_window)
            self.assertEqual((why, sel), (None, {ids[0]: None}))

    def test_anchored_capped_selection(self):
        # Two window messages; the cap admits only part of them. Reply 1 keeps both
        # (over budget) -> rejected with a correction appended; reply 2 fits.
        full = [msg('system', 'system', 'm00001'), msg('user', 'fix the bug', 'm00002')] + self.window \
             + [msg('assistant', 'THOUGHT\n```bash\nls\n```', 'm00007'), msg('user', 'x\ny', 'm00008')]
        context = full[:2] + [self.window[0], self.window[1]] + full[-2:]   # previous step kept m00003 + m00004 only
        selector = FakeSelector([selection('keep m00003\nkeep m00004\nkeep m00005\nkeep m00006'),
                                 selection('keep m00004 L1-2')])
        selector.settings['provider'] = 'openrouter'
        cap = memory.count_tokens(full[:2]) + memory.count_tokens(full[-2:]) + 30
        env = {'MSWEA_SELECT_ANCHOR': '1', 'MSWEA_SELECT_CAP': str(cap), 'MSWEA_EXTRACT_PREFILL': '1'}
        with patch.object(claude_extract, 'get_extract_model', return_value=selector), \
             patch.dict(os.environ, env), tempfile.TemporaryDirectory() as d, \
             patch.dict(os.environ, {'MSWEA_SUMMARY_ATTEMPT_LOG': str(Path(d) / 'a.jsonl')}):
            new, saved, pt, ct, lat = memory.online_claude_select(full, context, selector, keep_recent=1)
            attempts = [json.loads(l) for l in (Path(d) / 'a.jsonl').read_text().splitlines()]
        # prompt 1: tags on every history block, anchor paragraph, budget line, prefill last
        p1 = selector.prompts[0]
        self.assertIn('in context last step', p1[0]['content'])
        self.assertIn('Your selection must total at most 30 tokens', p1[0]['content'])
        heads = [b['text'].split('\n')[0] for b in p1[1]['content'][1:-1]]
        self.assertTrue(heads[0].startswith('[m00003 assistant; ') and heads[0].endswith('tokens, in context last step]'), heads[0])
        self.assertTrue(heads[2].startswith('[m00005 assistant; ') and heads[2].endswith('tokens, not in context last step]'), heads[2])
        self.assertIn('Selection budget: 30 tokens.', p1[1]['content'][-1]['text'])
        self.assertEqual(p1[-1]['role'], 'assistant')
        # attempt 1 rejected over budget; prompt 2 carries the correction before the prefill
        self.assertEqual([a['rejected'] for a in attempts], ['over_budget', None])
        p2 = selector.prompts[1]
        self.assertEqual(p2[-1]['role'], 'assistant')
        self.assertIn('the budget is 30 tokens', p2[-2]['content'])
        self.assertEqual(p2[-2]['role'], 'user')
        # result: protected + the partial keep + the kept tail; record carries the stability counts
        self.assertEqual([m['extra']['uid'] for m in new], ['m00001', 'm00002', 'm00004', 'm00007', 'm00008'])
        rec = memory.pop_summary_outcome()['flags']['selection']
        self.assertEqual((rec['anchor'], rec['cap'], rec['budget_window']), (True, cap, 30))
        self.assertLessEqual(rec['selected_tokens'], 30)
        self.assertEqual((rec['carried'], rec['added'], rec['removed']), (1, 0, 1))   # m00004 kept, m00003 dropped

    def test_trailing_anchor_keeps_system_and_history_blocks_stable(self):
        # MSWEA_SELECT_ANCHOR=trailing: the per-message tag is the token count only and the
        # previous-context uids and the budget number live in the trailing block, so two
        # calls with different previous contexts and budgets share every block but the last.
        full = [msg('system', 'system', 'm00001'), msg('user', 'fix the bug', 'm00002')] + self.window \
             + [msg('assistant', 'THOUGHT\n```bash\nls\n```', 'm00007'), msg('user', 'x\ny', 'm00008')]
        prompts = []
        for context, cap in ((full[:2] + [self.window[0], self.window[1]] + full[-2:], 500),
                             (full[:2] + [self.window[3]] + full[-2:], 400)):
            selector = FakeSelector([selection('keep m00004')])
            env = {'MSWEA_SELECT_ANCHOR': 'trailing', 'MSWEA_SELECT_CAP': str(cap), 'MSWEA_EXTRACT_PREFILL': ''}
            with patch.object(claude_extract, 'get_extract_model', return_value=selector), \
                 patch.dict(os.environ, env):
                memory.online_claude_select(full, context, selector, keep_recent=1)
            rec = memory.pop_summary_outcome()['flags']['selection']
            self.assertEqual((rec['anchor'], rec['anchor_style'], rec['cap']), (True, 'trailing', cap))
            prompts.append(selector.prompts[0])
        p1, p2 = prompts
        self.assertEqual(p1[0]['content'], p2[0]['content'])                       # system prompt identical
        self.assertNotIn('in context last step', p1[0]['content'])
        self.assertNotIn('500', p1[0]['content'])
        self.assertEqual(p1[1]['content'][:-1], p2[1]['content'][:-1])             # task + history blocks identical
        heads = [b['text'].split('\n')[0] for b in p1[1]['content'][1:-1]]
        self.assertTrue(heads[0].startswith('[m00003 assistant; ') and heads[0].endswith(' tokens]'), heads[0])
        self.assertTrue(all('context' not in h for h in heads))
        tail1, tail2 = p1[1]['content'][-1]['text'], p2[1]['content'][-1]['text']
        self.assertIn('In the agent\'s context at the previous step: m00003, m00004 (every other message was not).', tail1)
        self.assertIn('In the agent\'s context at the previous step: m00006 (every other message was not).', tail2)
        self.assertIn('Selection budget: ', tail1)
        self.assertNotEqual(tail1, tail2)
        with patch.dict(os.environ, {'MSWEA_SELECT_ANCHOR': 'trailing'}):
            self.assertEqual(memory._select_settings()[2], 'trailing')
        with patch.dict(os.environ, {'MSWEA_SELECT_ANCHOR': '1'}):
            self.assertEqual(memory._select_settings()[2], 'header')
        with self.assertRaises(ValueError):
            memory._select_prompt(FakeSelector([]), 'fix', self.window, tags={}, anchor_style='sideways')

    def test_plain_selection_prompt_has_no_anchor_or_budget(self):
        selector = FakeSelector([selection('keep m00003')])
        full = [msg('system', 'system', 'm00001'), msg('user', 'fix', 'm00002')] + self.window
        with patch.object(claude_extract, 'get_extract_model', return_value=selector), \
             patch.dict(os.environ, {'MSWEA_SELECT_ANCHOR': '', 'MSWEA_SELECT_CAP': '', 'MSWEA_EXTRACT_PREFILL': ''}):
            memory.online_claude_select(full, list(full), selector, keep_recent=1)
        p = selector.prompts[0]
        self.assertNotIn('in context last step', p[0]['content'])
        self.assertNotIn('budget', p[0]['content'].lower())
        self.assertTrue(all('; ' not in b['text'].split('\n')[0] for b in p[1]['content'][1:-1]))
        rec = memory.pop_summary_outcome()['flags']['selection']
        self.assertNotIn('anchor', rec)
        for bad in ({'MSWEA_SELECT_ANCHOR': 'maybe'}, {'MSWEA_SELECT_CAP': '-5'}):
            with patch.dict(os.environ, bad):
                with self.assertRaises(ValueError):
                    memory._select_settings()

    def test_select_source_setting_and_prompt_wording(self):
        with patch.dict(os.environ, {'MSWEA_SELECT_SOURCE': ''}):
            self.assertEqual(memory.select_source(), 'full')
        with patch.dict(os.environ, {'MSWEA_SELECT_SOURCE': 'context'}):
            self.assertEqual(memory.select_source(), 'context')
        with patch.dict(os.environ, {'MSWEA_SELECT_SOURCE': 'history'}):
            with self.assertRaises(ValueError):
                memory.select_source()
        selector = FakeSelector([])
        full_p = memory._select_prompt(selector, 'fix', self.window)[0]['content']
        ctx_p  = memory._select_prompt(selector, 'fix', self.window, source='context')[0]['content']
        self.assertIn('complete history', full_p)
        self.assertNotIn('complete history', ctx_p)
        self.assertIn('context it had at the previous step', ctx_p)
        self.assertIn('removed for good', ctx_p)
        with self.assertRaises(ValueError):
            memory.online_claude_select(self.window, self.window, selector, source='history')

    def test_prefill_setting(self):
        anthropic = FakeSelector([]); anthropic.settings['provider'] = 'anthropic'
        openrouter = FakeSelector([]); openrouter.settings['provider'] = 'openrouter'
        with patch.dict(os.environ, {'MSWEA_EXTRACT_PREFILL': ''}):
            self.assertEqual(memory._select_prefill(openrouter), '')
        with patch.dict(os.environ, {'MSWEA_EXTRACT_PREFILL': '1'}):
            self.assertEqual(memory._select_prefill(openrouter), memory.SEL_OPEN_MARKER + '\n')
            with self.assertRaises(ValueError):
                memory._select_prefill(anthropic)
        with patch.dict(os.environ, {'MSWEA_EXTRACT_PREFILL': 'maybe'}):
            with self.assertRaises(ValueError):
                memory._select_prefill(openrouter)

    def test_prefill_is_restored_in_front_of_the_reply(self):
        # The model continues the prefilled open-marker line; the reply alone has no open marker.
        model = FakeSelector([('keep m00003\n' + memory.SEL_CLOSE_MARKER, 'stop')])
        prompt = [{'role': 'system', 'content': 's'}, {'role': 'user', 'content': 'u'},
                  {'role': 'assistant', 'content': memory.SEL_OPEN_MARKER + '\n'}]
        with tempfile.TemporaryDirectory() as d:
            log = Path(d) / 'attempts.jsonl'
            with patch.dict(os.environ, {'MSWEA_SUMMARY_ATTEMPT_LOG': str(log)}):
                text, flags, *_ = memory.request_summary(model, prompt, memory.SEL_OPEN_MARKER, memory.SEL_CLOSE_MARKER)
            rec = json.loads(log.read_text().splitlines()[-1])
        self.assertEqual(text, f'{memory.SEL_OPEN_MARKER}\nkeep m00003\n{memory.SEL_CLOSE_MARKER}')   # accepted, markers restored
        self.assertTrue(flags.get('had_open_marker'))
        self.assertEqual(rec['prefill'], memory.SEL_OPEN_MARKER + '\n')
        self.assertEqual(rec['content'], 'keep m00003\n' + memory.SEL_CLOSE_MARKER)   # the model's own text
        self.assertEqual(model.prompts[0][-1]['role'], 'assistant')                    # prefill was sent
        # Without a prefilled prompt a reply lacking the open marker is still rejected.
        model = FakeSelector([('keep m00003\n' + memory.SEL_CLOSE_MARKER, 'stop')])
        text, flags, *_ = memory.request_summary(model, prompt[:2], memory.SEL_OPEN_MARKER, memory.SEL_CLOSE_MARKER, max_attempts=1)
        self.assertIsNone(text)


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

    def test_incremental_source_selects_from_the_current_context(self):
        # MSWEA_SELECT_SOURCE=context (online-claude-select-incremental): the selector is
        # shown the agent's current context, not the complete history, so a trimmed output
        # is shown trimmed (line numbers of the trimmed text) and a dropped message is
        # gone: a later `keep` of its uid is an unknown uid.
        os.environ['MSWEA_SELECT_SOURCE'] = 'context'
        selector = FakeSelector([
            selection('keep m00003\nkeep m00004 L4-5'),   # before call 3: window [a1, obs1]
            selection('keep m00004 L2\nkeep m00006'),      # before call 4: window [a1, obs1', a2, obs2]
            selection('keep m00003'),                      # before call 5: a1 was dropped -> unknown_uid
            selection('keep m00004\nkeep m00006\nkeep m00009'),   # retry: obs1'', obs2, obs3 (uids skip one per event)
        ])
        agent = self.agent()
        self.run_steps(agent, selector, 5)
        full = [m['extra']['uid'] for m in agent._full_messages]
        # Prompt 1 is the plain window; the prompt text describes the incremental source.
        self.assertIn('context it had at the previous step', selector.prompts[0][0]['content'])
        self.assertNotIn('complete history', selector.prompts[0][0]['content'])
        self.assertTrue(selector.blocks(0)[2].startswith('[m00004 user, 7 lines]'))
        self.assertNotIn('; ', selector.blocks(0)[2].split('\n')[0])   # no anchor tags
        # Prompt 2 shows obs1 as trimmed by selection 1 (4 lines: marker, 2 kept lines, marker).
        blocks2 = selector.blocks(1)
        self.assertTrue(blocks2[2].startswith('[m00004 user, 4 lines]'), blocks2[2])
        self.assertIn('2| line1-2', blocks2[2])
        self.assertNotIn('line1-1', blocks2[2])
        self.assertIn('[m00003 assistant]', blocks2[1])
        self.assertIn('[m00006 user', ''.join(blocks2))
        # Prompt 3 no longer contains a1 (dropped by selection 2); its uid is rejected.
        self.assertNotIn('[m00003', ''.join(selector.blocks(2)))
        attempts = [json.loads(l) for l in (self.directory / 'summary_attempts.jsonl').read_text().splitlines()]
        self.assertEqual([a['rejected'] for a in attempts], [None, None, 'unknown_uid', None])
        # Context before call 5 (then a5/obs5 appended by step 5):
        # [system, task, obs1'' (line 2 of the trimmed text), obs2, obs3 (m00008), a4, obs4, a5, obs5]
        uids = [m['extra']['uid'] for m in agent.messages]
        self.assertEqual(uids, full[:2] + [full[3], full[5], full[7]] + full[8:])
        self.assertEqual(agent.messages[2]['content'].split('\n')[1], 'line1-2')
        self.assertEqual(len(agent.messages[2]['content'].split('\n')), 3)
        self.assertIs(agent.messages[3], agent._full_messages[5])
        # The complete history is still recorded, untouched.
        self.assertEqual(len(agent._full_messages), 12)
        self.assertNotIn('omitted', agent._full_messages[3]['content'])
        log = self.log()
        recs = log['online_claude_select_events']
        self.assertEqual([r['step'] for r in recs], [2, 3, 4])
        self.assertEqual([r['source'] for r in recs], ['context'] * 3)
        self.assertEqual([r['accepted'] for r in recs], [True, True, True])
        self.assertEqual(recs[1]['selection']['source'], 'context')
        self.assertEqual(recs[1]['selection']['window'], 4)
        self.assertEqual(recs[1]['selection']['lines_total'], 3 + 4 + 3 + 7)   # a1 (3) + obs1 trimmed (4) + a2 (3) + obs2 (7)
        self.assertIn('tokens_full', recs[1])
        self.assertGreater(recs[1]['tokens_full'], recs[1]['tokens_before'])   # history > context
        events = [json.loads(l) for l in (self.directory / 'compression_events.jsonl').read_text().splitlines()]
        self.assertEqual([e['step'] for e in events], [2, 3, 4])
        self.assertEqual(events[1]['replaced'][0]['uid'], 'm00004')
        self.assertIn('m00003', events[1]['dropped'])

    def test_invalid_replies_are_retried_then_leave_the_context_unchanged(self):
        selector = FakeSelector([
            selection('keep m00003\nThe agent should now edit foo.py'),   # prose -> unparseable_line
            selection('keep m00099'),                                      # unknown uid
            selection('keep m00004 L0'),                                   # range out of bounds
            selection('keep m00004 L1'),                                   # accepted
        ])
        agent = self.agent()
        self.run_steps(agent, selector, 4)
        attempts = [json.loads(l) for l in (self.directory / 'summary_attempts.jsonl').read_text().splitlines()]
        self.assertEqual([a['rejected'] for a in attempts],
                         ['unparseable_line', 'unknown_uid', 'range_out_of_bounds', None])
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

    def test_fire_above_gates_the_selector_on_context_size(self):
        # MSWEA_EXTRACT_FIRE_ABOVE: a due call fires only while the context exceeds the
        # threshold. 'none' drops the whole window, so after a firing the context is back
        # to [system, task, newest turn] and grows again until the next firing.
        threshold = 150
        os.environ['MSWEA_EXTRACT_FIRE_ABOVE'] = str(threshold)
        selector = FakeSelector([selection('none')] * 10)
        agent = self.agent()
        self.run_steps(agent, selector, 12)
        events = self.log()['online_claude_select_events']
        self.assertTrue(events)
        self.assertLess(len(events), 11)                                   # not every due call fired
        self.assertGreater(events[0]['step'], 2)                           # the small early context did not fire
        self.assertTrue(all(e['tokens_before'] > threshold for e in events))
        self.assertTrue(all(e['tokens_after'] <= threshold for e in events))
        steps = [e['step'] for e in events]
        self.assertEqual(steps, sorted(set(steps)))
        self.assertTrue(all(b - a > 1 for a, b in zip(steps, steps[1:])))  # the context must regrow first
        self.assertEqual(len(selector.prompts), len(events))             # no call when gated
        os.environ['MSWEA_EXTRACT_FIRE_ABOVE'] = '-1'
        with self.assertRaises(ValueError):
            self.run_steps(self.agent(), FakeSelector([]), 2)

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




class LongOutputEnvironment(Environment):
    """40-line outputs (~250 cl100k tokens), so a small MSWEA_OUTPUT_EXTRACT_ABOVE is crossed."""
    def execute(self, action):
        self.commands.append(action['command'])
        n = len(self.commands)
        out = '\n'.join(f'line{n}-{i} ' + 'x' * 20 for i in range(1, 41))
        return {'output': out, 'returncode': 0, 'exception_info': None}


class OutputExtractTests(unittest.TestCase):
    """Per-output pre-extraction (MSWEA_OUTPUT_EXTRACT_ABOVE, memory.extract_tool_output,
    DefaultAgent._output_extract; the ocstx condition): a new tool output above the
    threshold is trimmed in place, in the context and the complete history at once."""
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
        os.environ['MSWEA_OUTPUT_EXTRACT_ABOVE'] = '100'      # the 42-line observations are ~250 tokens
        os.environ['MSWEA_EXTRACT_FIRE_ABOVE'] = '100000'     # the threshold selector never fires unless lowered
        attempts = patch.object(sys.modules['agentctx.compression.primitives'], 'SUMMARY_MAX_ATTEMPTS', 2)
        attempts.start()
        self.addCleanup(attempts.stop)
        self.model = LitellmTextbasedModel(model_name='hosted_vllm/test', cost_tracking='ignore_errors')
        self.cost = patch.object(self.model, '_calculate_cost', return_value={'cost': 0.0})
        self.cost.start()
        self.addCleanup(self.cost.stop)
        self.environment = LongOutputEnvironment()

    agent = OnlineClaudeSelectTests.agent
    response = OnlineClaudeSelectTests.response
    log = OnlineClaudeSelectTests.log
    run_steps = OnlineClaudeSelectTests.run_steps

    def events(self, name):
        return [json.loads(l) for l in (self.directory / name).read_text().splitlines() if l.strip()]

    def test_long_output_is_trimmed_in_place_in_context_and_history(self):
        # uids: m00001 system, m00002 task, m00003 a1, m00004 obs1; the compression event that
        # trims obs1 takes seq 5, so a2 m00006, obs2 m00007 (kept whole: no event), a3 m00008,
        # obs3 m00009. Observation lines: 1 <returncode>, 2 <output>, 3-42 the 40 output lines
        # (42 closes </output>).
        selector = FakeSelector([
            selection('keep m00004 L1-2, L5-6'),   # obs1: trimmed
            selection('keep m00007'),              # obs2: kept whole
            selection('none'),                     # obs3: removed
        ])
        agent = self.agent()
        self.run_steps(agent, selector, 3)
        self.assertEqual(len(selector.prompts), 3)
        # The prompt: system + [task (cached), the issuing message, the numbered output, instructions].
        system = selector.prompts[0][0]['content']
        self.assertIn('deleted for good', system)
        self.assertIn('keep <id> L<a>-<b>', system)
        blocks = selector.prompts[0][1]['content']
        self.assertTrue(blocks[0]['text'].startswith('Task statement'))
        self.assertIn('fix the bug in foo.py', blocks[0]['text'])
        self.assertEqual(blocks[0]['cache_control'], {'type': 'ephemeral'})
        self.assertIn('[m00003 assistant]', blocks[1]['text'])
        self.assertIn('echo step0', blocks[1]['text'])
        self.assertIn('[m00004 user, 42 lines]', blocks[2]['text'])
        self.assertIn(' 5| line1-3 ', blocks[2]['text'])
        self.assertIn('Reply with directives only', blocks[3]['text'])
        # obs1: the note, the kept lines, omission markers; the same object in both lists.
        obs1 = agent.messages[3]
        self.assertIs(obs1, agent._full_messages[3])
        lines = obs1['content'].split('\n')
        self.assertEqual(lines[0], memory.OUTPUT_EXTRACT_NOTE_FMT.format(kept=4, total=42))
        self.assertEqual(lines[1:], ['<returncode>0</returncode>', '<output>', '[... 2 lines omitted ...]',
                                     'line1-3 ' + 'x' * 20, 'line1-4 ' + 'x' * 20, '[... 36 lines omitted ...]'])
        self.assertNotIn('line1-10', obs1['content'])
        self.assertNotIn('raw_output', obs1['extra'])                      # no copy in the metadata either
        self.assertNotIn('line1-10', json.dumps(agent._full_messages))
        self.assertNotIn('line1-10', (self.directory / 'trajectory.json').read_text())
        self.assertEqual(obs1['extra']['output_extract']['outcome'], 'trimmed')
        self.assertEqual(obs1['extra']['output_extract']['keep'], [[1, 2], [5, 6]])
        self.assertEqual(obs1['extra']['output_extract']['step'], 1)
        # obs2: untouched (no note), obs3: only the note and one marker.
        obs2, obs3 = agent.messages[5], agent.messages[7]
        self.assertTrue(obs2['content'].startswith('<returncode>0</returncode>'))
        self.assertNotIn('output_extract', obs2['extra'])
        self.assertEqual(obs3['content'], memory.OUTPUT_EXTRACT_NOTE_FMT.format(kept=0, total=42)
                         + '\n[... 42 lines omitted ...]')
        self.assertEqual(obs3['extra']['output_extract']['outcome'], 'removed')
        # The log.
        log = self.log()
        ev = log['output_extract_events']
        self.assertEqual([e['outcome'] for e in ev], ['trimmed', 'kept_whole', 'removed'])
        self.assertEqual([e['uid'] for e in ev], ['m00004', 'm00007', 'm00009'])
        self.assertEqual([e['step'] for e in ev], [1, 2, 3])
        self.assertTrue(all(e['accepted'] and e['error'] is None for e in ev))
        self.assertEqual([e['lines_kept'] for e in ev], [4, 42, 0])
        self.assertTrue(ev[0]['tokens_before'] > 100 >= ev[0]['tokens_after'])
        self.assertEqual(ev[1]['tokens_after'], ev[1]['tokens_before'])
        self.assertEqual(log['output_extract_threshold'], 100)
        self.assertEqual((log['output_extract_accepted'], log['output_extract_trimmed'],
                          log['output_extract_removed'], log['output_extract_errors']), (3, 1, 1, 0))
        self.assertEqual(log['output_extract_total_tokens_saved'],
                         sum(e['tokens_before'] - e['tokens_after'] for e in ev))
        self.assertIn('extract_model', log)
        self.assertEqual([o['primitive'] for o in log['summary_outcomes']], ['output_extract'] * 3)
        self.assertEqual(log['summary_outcomes'][0]['flags']['output_extract']['outcome'], 'trimmed')
        self.assertEqual(log['online_claude_select_events'], [])      # the threshold selector did not fire
        # events.jsonl holds the raw observation; compression_events.jsonl the in-place replacement.
        added = {e['uid']: e['message'] for e in self.events('events.jsonl')}
        self.assertIn('line1-10', added['m00004']['content'])
        self.assertNotIn('pre-extracted', added['m00004']['content'])
        comp = self.events('compression_events.jsonl')
        self.assertEqual([c['kind'] for c in comp], ['output_extract', 'output_extract'])
        self.assertEqual([c['uid'] for c in comp], ['m00004', 'm00009'])
        self.assertEqual(comp[0]['before_uids'], comp[0]['after_uids'])
        self.assertEqual(comp[0]['dropped'], [])
        self.assertEqual([r['uid'] for r in comp[0]['replaced']], ['m00004'])
        self.assertEqual(comp[0]['replaced'][0]['new_content'], obs1['content'])
        self.assertEqual(comp[0]['keep'], [[1, 2], [5, 6]])
        self.assertEqual(comp[0]['threshold'], 100)
        from scripts.maintenance.reconstruct_context import Replay
        replay = Replay(self.directory)
        self.assertEqual(replay.mismatches, [])
        replay.verify()
        self.assertEqual([m['content'] for m in replay.final_messages()],
                         [m['content'] for m in agent.messages])

    def test_threshold_selector_sees_only_the_trimmed_output(self):
        # With the threshold selector firing (small MSWEA_EXTRACT_FIRE_ABOVE), its history
        # prompt shows the trimmed obs1 (note + markers): the omitted lines are gone from
        # the complete history it selects from, so they cannot be revived.
        # Before call 2 the context already exceeds the threshold but the window is empty
        # (keep_recent 1 widened to the only turn), so the first selection is before call 3.
        os.environ['MSWEA_EXTRACT_FIRE_ABOVE'] = '150'
        selector = FakeSelector([
            selection('keep m00004 L1-30'),       # step 1: obs1 pre-extracted (~270 tokens stay)
            selection('keep m00007 L3'),          # step 2: obs2 pre-extracted (a2 m00006, obs2 m00007)
            selection('keep m00004'),             # before call 3: threshold selection over [a1, obs1]
            selection('none'),                    # step 3: obs3 (a3 m00010, obs3 m00011)
        ])
        agent = self.agent()
        self.run_steps(agent, selector, 3)
        sel_events = self.log()['online_claude_select_events']
        self.assertEqual(len(sel_events), 1)
        self.assertEqual(sel_events[0]['step'], 2)
        self.assertTrue(sel_events[0]['accepted'])
        self.assertGreater(sel_events[0]['tokens_before'], 150)
        hist_blocks = selector.blocks(2)
        obs1_block = next(b for b in hist_blocks if b.startswith('[m00004 '))
        self.assertIn('pre-extracted: 30 of 42 lines kept', obs1_block)
        self.assertIn('[... 12 lines omitted ...]', obs1_block)
        self.assertIn('line1-28 ', obs1_block)
        self.assertNotIn('line1-35', obs1_block)
        self.assertNotIn('line1-35', json.dumps(selector.prompts[2]))
        self.assertEqual([_m['extra']['uid'] for _m in agent.messages],     # a1 dropped by the selection
                         ['m00001', 'm00002', 'm00004', 'm00006', 'm00007', 'm00010', 'm00011'])
        # The pre-extraction's compression events and the selection interleave in seq order.
        kinds = [c['kind'] for c in self.events('compression_events.jsonl')]
        self.assertEqual(kinds, ['output_extract', 'output_extract', 'online_claude_select', 'output_extract'])

    def test_below_threshold_and_off(self):
        os.environ['MSWEA_OUTPUT_EXTRACT_ABOVE'] = '100000'
        selector = FakeSelector([])
        agent = self.agent()
        self.run_steps(agent, selector, 2)
        self.assertEqual(selector.prompts, [])
        self.assertEqual(self.log()['output_extract_events'], [])
        self.assertEqual(self.log()['output_extract_threshold'], 100000)
        self.assertTrue(agent.messages[3]['content'].startswith('<returncode>'))
        del os.environ['MSWEA_OUTPUT_EXTRACT_ABOVE']
        agent = self.agent()
        self.run_steps(agent, FakeSelector([]), 1)
        self.assertEqual(self.log()['output_extract_threshold'], 0)
        self.assertNotIn('extract_model', self.log())
        os.environ['MSWEA_OUTPUT_EXTRACT_ABOVE'] = '-5'
        with self.assertRaises(ValueError):
            self.run_steps(self.agent(), FakeSelector([]), 1)

    def test_keep_all_and_rejected_replies(self):
        # No compression event until obs3, so the uids stay contiguous: obs2 m00006, obs3 m00008.
        selector = FakeSelector([
            selection('keep all'),                              # tolerated as keep <id>
            ('no markers at all', 'stop'), selection('keep m00006 L50-60'),  # rejected twice -> unchanged
            selection('keep m00008 L1\nsome prose'), selection('keep m00008 L1-2'),  # retry then accepted
        ])
        agent = self.agent()
        self.run_steps(agent, selector, 3)
        ev = self.log()['output_extract_events']
        self.assertEqual([e['outcome'] for e in ev], ['kept_whole', 'unchanged', 'trimmed'])
        self.assertEqual([e['accepted'] for e in ev], [True, False, True])
        self.assertTrue(agent.messages[5]['content'].startswith('<returncode>'))   # obs2 raw
        self.assertNotIn('output_extract', agent.messages[5]['extra'])
        outcomes = self.log()['summary_outcomes']
        self.assertEqual(outcomes[1]['rejections'], ['missing_marker', 'range_out_of_bounds'])
        self.assertEqual(outcomes[1]['fallback'], 'unchanged')
        self.assertEqual(outcomes[2]['rejections'], ['unparseable_line'])
        self.assertEqual(len(self.events('compression_events.jsonl')), 1)   # only obs3 changed

    def test_errors_are_logged_then_raised_after_the_cap(self):
        selector = FakeSelector([RuntimeError('boom')] * 3)
        agent = self.agent()
        with self.assertRaises(RuntimeError):
            self.run_steps(agent, selector, 3)
        ev = self.log()['output_extract_events']
        self.assertEqual(len(ev), 3)
        self.assertTrue(all(e['error'] == 'RuntimeError: boom' and not e['accepted'] for e in ev))
        self.assertEqual(self.log()['output_extract_errors'], 3)
        self.assertTrue(agent.messages[3]['content'].startswith('<returncode>'))   # left untouched
        # A success in between resets the count.
        selector = FakeSelector([RuntimeError('boom'), RuntimeError('boom'), selection('none'),
                                 RuntimeError('boom'), RuntimeError('boom')])
        agent = self.agent()
        self.run_steps(agent, selector, 5)
        self.assertEqual(self.log()['output_extract_errors'], 4)


def verdict(body):
    return (f'{memory.PHASE_OPEN_MARKER}\n{body}\n{memory.PHASE_CLOSE_MARKER}', 'stop')


class PhaseVerdictParseTests(unittest.TestCase):
    """parse_phase_verdict() / phase_gate_config() without an agent."""
    def test_grammar(self):
        for body, want in [
            ('boundary', ('boundary', None)),
            ('continue', ('continue', None)),
            ('Boundary.', ('boundary', None)),
            ('verdict: continue', ('continue', None)),
            ('boundary\nreason: the fix is applied and the tests pass', ('boundary', 'the fix is applied and the tests pass')),
            ('continue\nstill reading the file\nin pieces', ('continue', 'still reading the file in pieces')),
        ]:
            rec, why = memory.parse_phase_verdict(body)
            self.assertIsNone(why, body)
            self.assertEqual((rec['verdict'], rec['reason']), want, body)
        for body, why in [('', 'empty_verdict'), ('   \n', 'empty_verdict'),
                          ('maybe', 'unparseable_verdict'), ('boundary soon', 'unparseable_verdict'),
                          ('The agent should continue', 'unparseable_verdict'),
                          ('reason: done\nboundary', 'unparseable_verdict')]:
            rec, got = memory.parse_phase_verdict(body)
            self.assertEqual((rec, got), (None, why), body)

    def test_config(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(memory.phase_gate_config(15000))
            self.assertIsNone(memory.phase_gate_config(0))
        with patch.dict(os.environ, {'MSWEA_PHASE_GATE': '1'}):
            self.assertEqual(memory.phase_gate_config(15000), {'fire_above': 15000, 'force_above': 30000})
            with self.assertRaises(ValueError):          # needs the threshold firing
                memory.phase_gate_config(0)
        with patch.dict(os.environ, {'MSWEA_PHASE_GATE': '1', 'MSWEA_PHASE_GATE_FORCE_ABOVE': '0'}):
            self.assertEqual(memory.phase_gate_config(15000)['force_above'], 0)
        with patch.dict(os.environ, {'MSWEA_PHASE_GATE': '1', 'MSWEA_PHASE_GATE_FORCE_ABOVE': '40000'}):
            self.assertEqual(memory.phase_gate_config(15000)['force_above'], 40000)
        for force in ('15000', '12000', '-1', 'x'):
            with patch.dict(os.environ, {'MSWEA_PHASE_GATE': '1', 'MSWEA_PHASE_GATE_FORCE_ABOVE': force}), \
                 self.assertRaises(ValueError):
                memory.phase_gate_config(15000)
        with patch.dict(os.environ, {'MSWEA_PHASE_GATE': 'maybe'}), self.assertRaises(ValueError):
            memory.phase_gate_config(15000)


class PhaseGateTests(unittest.TestCase):
    """Phase-boundary gate on the threshold firing (MSWEA_PHASE_GATE, memory.judge_phase_boundary,
    DefaultAgent._phase_gate; the ocstx15p condition): above the firing threshold the extractor
    model is asked whether the newest turn is a phase boundary, and the selector fires only on
    boundary (or above the force ceiling, or when the judge cannot answer)."""
    THRESHOLD = 150

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
        os.environ['MSWEA_EXTRACT_FIRE_ABOVE'] = str(self.THRESHOLD)
        os.environ['MSWEA_PHASE_GATE'] = '1'
        os.environ['MSWEA_PHASE_GATE_FORCE_ABOVE'] = '0'          # no ceiling unless a test sets one
        attempts = patch.object(sys.modules['agentctx.compression.primitives'], 'SUMMARY_MAX_ATTEMPTS', 2)
        attempts.start()
        self.addCleanup(attempts.stop)
        self.model = LitellmTextbasedModel(model_name='hosted_vllm/test', cost_tracking='ignore_errors')
        self.cost = patch.object(self.model, '_calculate_cost', return_value={'cost': 0.0})
        self.cost.start()
        self.addCleanup(self.cost.stop)
        self.environment = Environment()

    agent = OnlineClaudeSelectTests.agent
    response = OnlineClaudeSelectTests.response
    log = OnlineClaudeSelectTests.log
    run_steps = OnlineClaudeSelectTests.run_steps

    def first_due_step(self):
        """The first call (n_calls) at which the context exceeds the threshold with the
        gate off, i.e. where the judge is first consulted with it on."""
        with tempfile.TemporaryDirectory() as d, \
             patch.dict(os.environ, {'MSWEA_PHASE_GATE': '0', 'MSWEA_EVENT_LOG_DIR': d,
                                     'MSWEA_TOKEN_LOG_PATH': str(Path(d) / 'token_log.json')}):
            selector = FakeSelector([selection('none')] * 10)
            self.run_steps(self.agent(), selector, 12)
            return json.loads((Path(d) / 'token_log.json').read_text())['online_claude_select_events'][0]['step']

    def test_continue_defers_and_boundary_fires(self):
        due = self.first_due_step()
        selector = FakeSelector([
            verdict('continue\nreason: reading the file in pieces'),   # due step: deferred
            verdict('continue'),                                        # due + 1: deferred again
            verdict('boundary\nthe edit is applied and confirmed'),    # due + 2: fires
            selection('none'),                                          # the selection itself
        ] + [verdict('continue')] * 10)
        agent = self.agent()
        self.run_steps(agent, selector, due + 4)
        log = self.log()
        ev = log['phase_judge_events']
        self.assertEqual([e['step'] for e in ev][:3], [due, due + 1, due + 2])
        self.assertEqual([e['verdict'] for e in ev][:3], ['continue', 'continue', 'boundary'])
        self.assertEqual([e['fired'] for e in ev][:3], [False, False, True])
        self.assertEqual([e['outcome'] for e in ev][:3], ['accepted'] * 3)
        self.assertEqual(ev[0]['reason'], 'reading the file in pieces')
        self.assertEqual(ev[2]['reason'], 'the edit is applied and confirmed')
        self.assertTrue(all(e['tokens'] > self.THRESHOLD for e in ev))
        self.assertTrue(all(not e['forced'] and e['accepted'] and not e['error'] for e in ev))
        self.assertEqual(ev[0]['prompt_tokens'], 500)
        sel = log['online_claude_select_events']
        self.assertEqual([s['step'] for s in sel], [due + 2])            # the selector fired once, at the boundary
        self.assertTrue(sel[0]['accepted'])
        # between the deferred steps the context kept growing (append-only, untouched)
        self.assertLess(ev[0]['tokens'], ev[1]['tokens'])
        self.assertLess(ev[1]['tokens'], ev[2]['tokens'])
        # after the firing the context is small again, so the judge is not asked until it regrows
        self.assertTrue(all(e['step'] > due + 2 for e in ev[3:]))
        self.assertEqual(log['phase_judge_config'], {'fire_above': self.THRESHOLD, 'force_above': 0})
        self.assertEqual((log['phase_judge_calls'], log['phase_judge_boundary'], log['phase_judge_forced'],
                          log['phase_judge_errors']), (len(ev), 1, 0, 0))
        self.assertEqual(log['phase_judge_continue'], len(ev) - 1)
        outcomes = [o for o in log['summary_outcomes'] if o['primitive'] == 'phase_judge']
        self.assertEqual(len(outcomes), len(ev))
        self.assertEqual(outcomes[0]['flags']['phase_judge']['verdict'], 'continue')
        self.assertEqual(log['summarization_prompt_tokens'], 500 * (len(ev) + 1))
        self.assertIn('extract_model', log)
        # the judge saw the task and the current context, asked the fixed question, and nothing
        # of it reached the agent
        p0 = selector.prompts[0]
        self.assertIn('phase boundary', p0[0]['content'])
        self.assertIn(memory.PHASE_OPEN_MARKER, p0[0]['content'])
        blocks = selector.blocks(0)
        self.assertTrue(blocks[0].startswith('Task statement (for reference only):\n'))
        self.assertIn('fix the bug in foo.py', blocks[0])
        self.assertTrue(blocks[1].startswith('[m00003 assistant]'))
        self.assertIn('Is the newest turn a phase boundary', blocks[-1])
        self.assertEqual(p0[1]['content'][-2].get('cache_control'), {'type': 'ephemeral'})
        self.assertEqual(len(blocks) - 2, 2 * due)                      # every message after the prefix, at call `due`
        self.assertNotIn('phase', json.dumps([m['content'] for m in agent.messages]).lower())
        # only compression events of the selector, none for the judge
        comp = [json.loads(l) for l in (self.directory / 'compression_events.jsonl').read_text().splitlines()]
        self.assertEqual([c['kind'] for c in comp], ['online_claude_select'])

    def test_force_ceiling_fires_without_asking(self):
        due = self.first_due_step()
        # measure the context at the due step, then set the ceiling just above it: the judge is
        # asked while the context is between threshold and ceiling, and skipped above the ceiling
        probe = FakeSelector([verdict('continue')] * 20)
        self.run_steps(self.agent(), probe, due + 1)
        ev = self.log()['phase_judge_events']
        ceiling = ev[0]['tokens'] + 1
        os.environ['MSWEA_PHASE_GATE_FORCE_ABOVE'] = str(ceiling)
        selector = FakeSelector([verdict('continue'), selection('none')] + [verdict('continue')] * 20)
        self.run_steps(self.agent(), selector, due + 3)
        log = self.log()
        ev = log['phase_judge_events']
        self.assertEqual([e['step'] for e in ev][:2], [due, due + 1])
        self.assertEqual((ev[0]['forced'], ev[0]['verdict'], ev[0]['fired']), (False, 'continue', False))
        self.assertEqual((ev[1]['forced'], ev[1]['verdict'], ev[1]['fired'], ev[1]['outcome']),
                         (True, None, True, 'forced'))
        self.assertGreater(ev[1]['tokens'], ceiling)
        self.assertEqual((ev[1]['prompt_tokens'], ev[1]['accepted']), (0, False))
        self.assertEqual([s['step'] for s in log['online_claude_select_events']][:1], [due + 1])
        self.assertEqual(log['phase_judge_config']['force_above'], ceiling)
        self.assertEqual(log['phase_judge_forced'], sum(1 for e in ev if e['forced']))
        self.assertGreaterEqual(log['phase_judge_forced'], 1)
        # a forced firing made one selector call and no judge call at that step
        self.assertEqual(len(selector.prompts), log['phase_judge_calls'] + len(log['online_claude_select_events']))

    def test_rejected_replies_are_corrected_then_fire_on_fallback(self):
        due = self.first_due_step()
        selector = FakeSelector([
            ('I think the agent is done with exploration.', 'stop'),           # no marker -> rejected
            verdict('maybe'),                                                   # unparseable -> rejected (2 attempts)
            selection('none'),                                                  # fallback fires the selector
        ] + [verdict('continue')] * 20)
        self.run_steps(self.agent(), selector, due + 2)
        log = self.log()
        ev = log['phase_judge_events']
        self.assertEqual((ev[0]['verdict'], ev[0]['outcome'], ev[0]['fired'], ev[0]['accepted']),
                         (None, 'fallback', True, False))
        self.assertEqual([s['step'] for s in log['online_claude_select_events']][:1], [due])
        outcome = next(o for o in log['summary_outcomes'] if o['primitive'] == 'phase_judge')
        self.assertEqual((outcome['attempts'], outcome['accepted'], outcome['fallback']), (2, False, 'fire'))
        self.assertEqual(outcome['rejections'], ['missing_marker', 'unparseable_verdict'])
        # the second attempt's prompt carries the correction after the original two messages
        p1 = selector.prompts[1]
        self.assertEqual([m['role'] for m in p1], ['system', 'user', 'user'])
        self.assertIn('boundary or continue', p1[-1]['content'])
        self.assertIsInstance(p1[1]['content'], list)

    def test_errors_fire_then_raise_after_the_cap(self):
        due = self.first_due_step()
        selector = FakeSelector([RuntimeError('judge down'), selection('none')] + [verdict('continue')] * 20)
        self.run_steps(self.agent(), selector, due + 2)
        log = self.log()
        ev = log['phase_judge_events']
        self.assertEqual((ev[0]['outcome'], ev[0]['fired'], ev[0]['verdict']), ('error', True, None))
        self.assertTrue(ev[0]['error'].startswith('RuntimeError'))
        self.assertEqual(log['phase_judge_errors'], 1)
        self.assertEqual([s['step'] for s in log['online_claude_select_events']][:1], [due])
        os.environ['MSWEA_EXTRACT_MAX_CONSECUTIVE_ERRORS'] = '2'
        selector = FakeSelector([RuntimeError('a'), selection('none'), RuntimeError('b')] + [verdict('continue')] * 5)
        # after the first error the context was compacted; the second error comes at the next due step
        with self.assertRaises(RuntimeError):
            self.run_steps(self.agent(), selector, due + 12)
        self.assertEqual(self.log()['phase_judge_errors'], 2)

    def test_gate_needs_the_threshold_and_is_off_by_default(self):
        os.environ['MSWEA_EXTRACT_FIRE_ABOVE'] = '0'
        with self.assertRaises(ValueError):
            self.run_steps(self.agent(), FakeSelector([selection('none')] * 5), 3)
        del os.environ['MSWEA_PHASE_GATE']
        os.environ['MSWEA_EXTRACT_FIRE_ABOVE'] = str(self.THRESHOLD)
        selector = FakeSelector([selection('none')] * 10)
        self.run_steps(self.agent(), selector, 8)
        log = self.log()
        self.assertEqual(log['phase_judge_events'], [])
        self.assertIsNone(log['phase_judge_config'])
        self.assertTrue(log['online_claude_select_events'])

    def test_prefill_uses_the_phase_marker(self):
        due = self.first_due_step()
        os.environ['MSWEA_EXTRACT_PREFILL'] = '1'
        selector = FakeSelector([('continue\n' + memory.PHASE_CLOSE_MARKER, 'stop')] + [verdict('continue')] * 20)
        selector.settings['provider'] = 'openrouter'
        self.run_steps(self.agent(), selector, due + 1)
        p0 = selector.prompts[0]
        self.assertEqual(p0[-1], {'role': 'assistant', 'content': memory.PHASE_OPEN_MARKER + '\n'})
        self.assertEqual(self.log()['phase_judge_events'][0]['verdict'], 'continue')


if __name__ == '__main__':
    unittest.main()
