"""clm: the agent edits a mirror of its own context; real agent classes, no model server, no container.

Run: venv/bin/python -m unittest discover -s tests -p test_clm.py -v
"""
import json
import os
import re
import stat
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
    import yaml
    from agentctx.compression import clm
    from agentctx.compression.clm import session as clm_session
    from agentctx.experiments.conditions import default_conditions
    from agentctx.experiments.iclr import CONDITION_TO_PRIMITIVE, INFINITE_BUDGET_CONDITIONS
    from litellm import ModelResponse
    from minisweagent.agents.default import DefaultAgent
    from minisweagent.agents.interactive import InteractiveAgent
    from minisweagent.models.litellm_textbased_model import LitellmTextbasedModel
    from scripts.maintenance.reconstruct_context import Replay
except ImportError as exc:
    raise unittest.SkipTest(str(exc))

MIRROR = clm.CTX_FILE
BACKTICKS = ROOT / 'mini-swe-agent/src/minisweagent/config/benchmarks/swebench_backticks.yaml'
OBSERVATION_TEMPLATE = '<returncode>{{output.returncode}}</returncode>\n<output>\n{{ output.output -}}\n</output>'


FILLER = ['alpha', 'beta', 'gamma', 'delta', 'omega']     # one cl100k token each


def words(n, word='alpha'):
    """n cl100k tokens of filler."""
    return ' '.join([word] * n)


class Environment:
    """In-memory task container: holds the mirror file; a command is either a
    registered handler (may edit the mirror) or prints a registered output."""

    def __init__(self):
        self.files = {}
        self.commands = []
        self.mirror_seen = []       # the mirror as each command found it
        self.handlers = {}
        self.outputs = {}

    def get_template_vars(self):
        return {}

    def serialize(self):
        return {}

    def write_file(self, path, text):
        self.files[path] = text

    def read_file(self, path):
        return self.files.get(path)

    def execute(self, action):
        command = action['command']
        self.commands.append(command)
        self.mirror_seen.append(self.files.get(MIRROR))
        if command in self.handlers:
            return self.handlers[command](self)
        return {'output': self.outputs.get(command, 'done'), 'returncode': 0, 'exception_info': None}


def edit(fn, output='', returncode=0):
    """Handler that rewrites the mirror with fn(text)."""
    def handler(env):
        env.files[MIRROR] = fn(env.files[MIRROR])
        return {'output': output, 'returncode': returncode, 'exception_info': None}
    return handler


def collapse_turns(first, last, note):
    """Replace turns first..last (1-based, inclusive) by one assistant turn holding note."""
    def fn(text):
        blocks = [b for b in re.split(r'(?m)^(?=\[\[CTX_TURN )', text) if b]
        kept = blocks[:first - 1] + [f'[[CTX_TURN {first} role=assistant]]\n{note}\n\n'] + blocks[last:]
        return ''.join(kept)
    return fn


class ClmTestCase(unittest.TestCase):
    budget = ''
    extra_env = {}

    def setUp(self):
        self.env_patch = patch.dict(os.environ, {}, clear=True)
        self.env_patch.start()
        self.addCleanup(self.env_patch.stop)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.directory = Path(self.tmp.name)
        self.log_path = self.directory / 'token_log.json'
        os.environ.update({
            'MSWEA_TOKEN_LOG_PATH': str(self.log_path),
            'MSWEA_EVENT_LOG_DIR': str(self.directory),
            'MSWEA_PRIMITIVE': 'clm',
            'MSWEA_TOKEN_BUDGET': str(self.budget),
            # A test that asks for more model calls than it scripted must fail, not back off.
            'MSWEA_MODEL_RETRY_STOP_AFTER_ATTEMPT': '1',
            **self.extra_env,
        })
        self.model = LitellmTextbasedModel(model_name='hosted_vllm/test', cost_tracking='ignore_errors',
                                           observation_template=OBSERVATION_TEMPLATE)
        cost = patch.object(self.model, '_calculate_cost', return_value={'cost': 0.0})
        cost.start()
        self.addCleanup(cost.stop)
        self.environment = Environment()

    def agent(self, agent_class=DefaultAgent, **kwargs):
        agent = agent_class(self.model, self.environment, system_template='system',
                            instance_template='task', output_path=self.directory / 'trajectory.json',
                            **({'cost_limit': 0} | kwargs))
        agent.add_messages({'role': 'system', 'content': 'system'},
                           {'role': 'user', 'content': 'fix the bug in foo.py'})
        return agent

    def response(self, command, pt=100, ct=10):
        # A command may be (command, n, word): the reply then carries n tokens of
        # reasoning. Replies are how these tests grow the context past a limit: an
        # observation cannot, it is capped to the room left under the limit.
        thought = 'next'
        if isinstance(command, tuple):
            command, n, word = command
            thought = words(n, word)
        content = f'THOUGHT: {thought}\n\n```mswea_bash_command\n{command}\n```'
        return ModelResponse(model='test', choices=[{'finish_reason': 'stop',
            'message': {'role': 'assistant', 'content': content}}],
            usage={'prompt_tokens': pt, 'completion_tokens': ct, 'total_tokens': pt + ct})

    def steps(self, agent, commands):
        with patch.object(self.model, '_query', side_effect=[self.response(c) for c in commands]):
            for _ in commands:
                agent.step()
                agent.save(agent.config.output_path)
                agent._write_token_log()

    def log(self):
        return json.loads(self.log_path.read_text())

    def compression_events(self):
        path = self.directory / 'compression_events.jsonl'
        return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []

    def roles(self, agent):
        return [m['role'] for m in agent.messages]


class MirrorTests(ClmTestCase):
    def test_mirror_holds_the_editable_history_without_the_turn_being_executed(self):
        agent = self.agent()
        self.steps(agent, ['echo one', 'echo two'])
        first, second = self.environment.mirror_seen
        # Nothing to edit before the first command: the prefix is hidden and the turn
        # that issues the command is not in its own mirror.
        self.assertEqual(first, '')
        self.assertEqual(second.count('[[CTX_TURN'), 2)
        self.assertIn('[[CTX_TURN 1 role=assistant]]', second)
        self.assertIn('echo one', second)
        self.assertIn('[[CTX_TURN 2 role=user]]', second)
        self.assertNotIn('echo two', second)
        self.assertNotIn('fix the bug in foo.py', second)
        # No edit: the history is untouched and no event is recorded.
        self.assertEqual(self.roles(agent), ['system', 'user', 'assistant', 'user', 'assistant', 'user'])
        self.assertEqual(self.compression_events(), [])
        self.assertEqual(self.log()['clm_edits'], 0)
        # Without a budget there is no readout and no nudge.
        self.assertNotIn('[context:', agent.messages[-1]['content'])
        self.assertEqual(agent._clm.budget_label, "your model's full context window")

    def test_edit_replaces_the_window_and_keeps_the_prefix_and_the_editing_turn(self):
        self.environment.outputs = {'cat big': words(600)}
        self.environment.handlers['compact'] = edit(collapse_turns(1, 4, '[summary: big.txt is filler]'))
        agent = self.agent()
        self.steps(agent, ['cat big', 'echo two', 'compact'])
        prefix_uids = [m['extra']['uid'] for m in agent.messages[:2]]
        self.assertEqual(self.roles(agent), ['system', 'user', 'assistant', 'assistant', 'user'])
        self.assertEqual(agent.messages[1]['content'], 'fix the bug in foo.py')
        self.assertEqual(agent.messages[2]['content'], '[summary: big.txt is filler]')
        self.assertEqual(agent.messages[2]['extra']['origin'], 'clm_edit')
        self.assertIn('compact', agent.messages[3]['content'])       # the turn that made the edit
        self.assertIn('[LIVE_CTX_MAIN.txt: edit applied — context ~', agent.messages[4]['content'])
        self.assertEqual(prefix_uids, ['m00001', 'm00002'])
        log = self.log()
        self.assertEqual((log['clm_edits'], log['clm_edits_real'], log['clm_edits_rejected']), (1, 1, 0))
        self.assertGreater(log['clm_net_tokens_saved'], 500)
        self.assertEqual(log['clm_events'][0]['outcome'], 'applied')
        self.assertEqual((log['clm_events'][0]['turns_before'], log['clm_events'][0]['turns_after']), (4, 1))
        # These are not budget compression events.
        self.assertEqual(log['compression_events'], 0)

    def test_an_edit_is_logged_as_a_replacement_of_the_whole_window_and_replays(self):
        self.environment.outputs = {'cat big': words(600)}
        # Only turn 2 (the big output) is rewritten; turns 1, 3, 4 are left as they are.
        self.environment.handlers['compact'] = edit(
            lambda text: re.sub(r'(\[\[CTX_TURN 2 [^\]]*\]\]).*?(?=\n\[\[CTX_TURN|\Z)',
                                r'\1\n[big.txt: filler]', text, flags=re.S))
        agent = self.agent()
        self.steps(agent, ['cat big', 'echo two', 'compact', 'echo after'])
        (event,) = self.compression_events()
        self.assertEqual((event['kind'], event['primitive']), ('clm_edit', 'clm'))
        # before: system, task, a1, o1, a2, o2, a3(compact). The whole window a1..o2 is
        # dropped, also the three turns the edit did not touch; prefix and a3 stay.
        self.assertEqual(event['dropped'], event['before_uids'][2:6])
        self.assertEqual(event['replaced'], [])
        self.assertEqual(len(event['added']), 4)
        self.assertEqual(event['after_uids'][:2], event['before_uids'][:2])
        self.assertEqual(event['after_uids'][-1], event['before_uids'][-1])
        self.assertTrue(all(a['uid'].startswith('c') for a in event['added']))
        self.assertEqual(event['added'][1]['message']['content'], '[big.txt: filler]')
        Replay(self.directory).verify()
        context = Replay(self.directory).context_at_call(4)
        self.assertEqual([m.get('content') for m in context], [m.get('content') for m in agent.messages[:-2]])

    def test_edit_that_grows_is_rejected_without_a_budget(self):
        self.environment.handlers['grow'] = edit(lambda text: text + '\n' + words(300, 'beta'))
        agent = self.agent()
        self.steps(agent, ['echo one', 'grow'])
        self.assertEqual(self.roles(agent), ['system', 'user', 'assistant', 'user', 'assistant', 'user'])
        self.assertNotIn('beta', json.dumps(agent.messages[:-1]))
        self.assertIn('edit REJECTED', agent.messages[-1]['content'])
        self.assertIn('A compaction must SHRINK context', agent.messages[-1]['content'])
        log = self.log()
        self.assertEqual((log['clm_edits'], log['clm_edits_rejected']), (0, 1))
        self.assertEqual(self.compression_events(), [])

    def test_touching_the_mirror_without_changing_it_is_reported(self):
        touch = f'sed -i s/nothing/x/ {MIRROR}'
        fail = f'python3 broken.py {MIRROR}'
        self.environment.handlers[fail] = lambda env: {'output': 'Traceback', 'returncode': 1,
                                                       'exception_info': None}
        agent = self.agent()
        self.steps(agent, ['echo one', touch, fail])
        self.assertIn('NO change — your edit matched nothing', agent.messages[5]['content'])
        self.assertIn('NO change — your command exited 1', agent.messages[7]['content'])
        self.assertEqual([e['outcome'] for e in self.log()['clm_events']], ['no_change', 'no_change'])

    def test_a_compaction_turn_counts_as_a_step(self):
        self.environment.handlers['compact'] = edit(collapse_turns(1, 2, '[summary]'))
        agent = self.agent(step_limit=2)
        self.steps(agent, ['echo one', 'compact'])
        self.assertEqual(agent.n_calls, 2)
        from minisweagent.exceptions import LimitsExceeded
        with self.assertRaises(LimitsExceeded):
            agent.step()

    def test_interactive_agent_runs_the_same_hooks(self):
        self.environment.handlers['compact'] = edit(collapse_turns(1, 2, '[summary]'))
        agent = self.agent(InteractiveAgent, mode='yolo', confirm_exit=False)
        self.steps(agent, ['echo one', 'compact'])
        self.assertEqual(self.roles(agent), ['system', 'user', 'assistant', 'assistant', 'user'])
        self.assertIn('edit applied', agent.messages[-1]['content'])

    def test_unwritable_mirror_ends_the_run_instead_of_running_as_full_context(self):
        agent = self.agent()
        with patch.object(self.environment, 'write_file', side_effect=RuntimeError('container gone')), \
             patch.object(self.model, '_query', side_effect=[self.response('echo one')]), \
             self.assertRaises(RuntimeError):
            agent.step()
        self.assertEqual(self.environment.commands, [])


class BudgetTests(ClmTestCase):
    budget = 3000
    extra_env = {'MSWEA_CLM_RESERVE_TOKENS': '500', 'MSWEA_CLM_RETRY_MARGIN_TOKENS': '400',
                 'MSWEA_CLM_PERSISTENT_NUDGE': 'none'}

    def test_readout_and_nudge_and_fit_gate(self):
        self.environment.outputs = {'cat a': words(800)}
        self.environment.handlers['grow'] = edit(lambda text: text + '\n' + words(100, 'beta'))
        agent = self.agent()
        self.assertEqual(agent._clm.budget_label, '2500 tokens')
        self.steps(agent, ['cat a', 'echo two'])
        # Readout on the limit (budget - reserve), after the output.
        self.assertRegex(agent.messages[3]['content'][-40:], r'\[context: ~\d+/2500 tokens\]$')
        # 800+ tokens crossed the 25% tier of 3000 before call 2; the tier fires once.
        nudges = [m for m in agent.messages if (m.get('extra') or {}).get('clm') == 'nudge']
        self.assertEqual(len(nudges), 1)
        self.assertIs(nudges[0], agent.messages[4])
        self.assertIn('~25% of your 3000-token budget', nudges[0]['content'])
        self.steps(agent, ['grow'])
        self.assertEqual(self.log()['clm_nudges'], 1)
        # Under the fit gate a growing edit that still fits the limit is kept.
        self.assertIn('edit applied but it GREW', agent.messages[-1]['content'])
        self.assertIn('beta', json.dumps(agent.messages[:-2]))
        self.assertEqual(self.log()['clm_edits_grew'], 1)

    def test_an_output_larger_than_the_room_left_is_capped_not_rolled_back(self):
        self.environment.outputs = {'cat huge': words(5000)}
        agent = self.agent()
        self.steps(agent, ['cat huge', 'echo next'])
        observation = agent.messages[3]['content']
        self.assertIn('tokens elided to respect the 3000-token context cap', observation)
        self.assertLessEqual(memory.count_tokens(agent.messages[:4]), 2500 + 40)   # + readout
        self.assertEqual(self.log()['clm_rollbacks'], 0)


class RollbackTests(ClmTestCase):
    budget = 3000
    extra_env = {'MSWEA_CLM_RESERVE_TOKENS': '500', 'MSWEA_CLM_RETRY_MARGIN_TOKENS': '400',
                 'MSWEA_CLM_PERSISTENT_NUDGE': 'none', 'MSWEA_CLM_NUDGE_RATIOS': ''}

    def test_no_truncation_at_the_limit_but_a_rollback_with_a_pinned_ledger(self):
        agent = self.agent()
        self.steps(agent, [('cat 0', 900, FILLER[0]), ('cat 1', 900, FILLER[1]),
                           ('cat 2', 900, FILLER[2]), 'echo next'])
        # ~2700 tokens of replies > 2500 before call 4: rolled back to <= 2100, never
        # ending on an assistant turn; the ledger sits right after the task.
        log = self.log()
        self.assertEqual(log['clm_rollbacks'], 1)
        self.assertEqual(log['clm_turns_rolled_back'], 2)
        self.assertEqual(log['compression_events'], 0)           # no budget primitive fired
        ledger = agent.messages[2]
        self.assertEqual(ledger['extra']['clm'], 'rollback_ledger')
        self.assertIn('CONTEXT LIMIT HIT (retry 1/50)', ledger['content'])
        self.assertIn('- cat 2', ledger['content'])              # the command whose output overflowed
        self.assertNotIn(FILLER[2], json.dumps(agent.messages))
        self.assertEqual(agent._clm.protect, 3)
        (event,) = self.compression_events()
        self.assertEqual(event['kind'], 'clm_rollback')
        self.assertEqual(len(event['dropped']), 2)
        self.assertEqual([a['uid'] for a in event['added']], [ledger['extra']['uid']])
        # The mirror of the next command hides the ledger with the prefix.
        self.assertNotIn('CONTEXT LIMIT HIT', self.environment.mirror_seen[-1])
        Replay(self.directory).verify()

    def test_second_rollback_updates_the_ledger_in_place(self):
        agent = self.agent()
        self.steps(agent, [('cat 0', 900, FILLER[0]), ('cat 1', 900, FILLER[1]),
                           ('cat 2', 900, FILLER[2]), ('cat 3', 900, FILLER[3]), 'echo next'])
        self.assertEqual(self.log()['clm_rollbacks'], 2)
        events = self.compression_events()
        self.assertEqual([e['kind'] for e in events], ['clm_rollback', 'clm_rollback'])
        self.assertEqual(events[1]['added'], [])
        self.assertEqual([r['uid'] for r in events[1]['replaced']], [agent.messages[2]['extra']['uid']])
        self.assertIn('retry 2/50', agent.messages[2]['content'])
        self.assertEqual(sum(1 for m in agent.messages
                             if (m.get('extra') or {}).get('clm') == 'rollback_ledger'), 1)
        Replay(self.directory).verify()

    def test_compaction_after_a_rollback_keeps_the_ledger(self):
        self.environment.handlers['compact'] = edit(collapse_turns(1, 4, '[summary of 0 and 1]'))
        agent = self.agent()
        self.steps(agent, [('cat 0', 900, FILLER[0]), ('cat 1', 900, FILLER[1]),
                           ('cat 2', 900, FILLER[2]), 'compact'])
        self.assertEqual(self.roles(agent), ['system', 'user', 'user', 'assistant', 'assistant', 'user'])
        self.assertEqual(agent.messages[2]['extra']['clm'], 'rollback_ledger')
        self.assertEqual(agent.messages[3]['content'], '[summary of 0 and 1]')
        self.assertEqual([e['kind'] for e in self.compression_events()], ['clm_rollback', 'clm_edit'])
        Replay(self.directory).verify()


class FinalTurnTests(ClmTestCase):
    budget = 3000
    extra_env = {'MSWEA_CLM_RESERVE_TOKENS': '500', 'MSWEA_CLM_MAX_RETRY_ON_LIMIT': '0',
                 'MSWEA_CLM_PERSISTENT_NUDGE': 'none', 'MSWEA_CLM_NUDGE_RATIOS': ''}

    def test_final_turn_then_the_run_ends_without_a_submission(self):
        agent = self.agent()
        commands = [('cat 0', 1400, FILLER[0]), ('cat 1', 1400, FILLER[1]), 'cat 2']
        with patch.object(self.model, '_query', side_effect=[self.response(c) for c in commands]):
            agent.extra_template_vars['task'] = 'fix the bug in foo.py'
            # agent.run() restarts the history; drive the same loop by hand instead.
            from minisweagent.exceptions import InterruptAgentFlow
            for _ in range(4):
                try:
                    agent.step()
                except InterruptAgentFlow as flow:
                    agent.add_messages(*flow.messages)
                if agent.messages[-1].get('role') == 'exit':
                    break
        # Over the limit before call 3: one final turn (call 3 is made), then stop.
        self.assertEqual(agent.n_calls, 3)
        final = [m for m in agent.messages if (m.get('extra') or {}).get('clm') == 'final_turn']
        self.assertEqual(len(final), 1)
        self.assertIn('This is your FINAL turn', final[0]['content'])
        self.assertEqual(agent.messages[-1]['extra'],
                         {**agent.messages[-1]['extra'], 'exit_status': 'ContextBudgetExceeded',
                          'submission': ''})


class WiringTests(unittest.TestCase):
    def test_condition_and_cell_tag(self):
        (condition,) = [c for c in default_conditions() if c['condition'] == 'clm']
        self.assertEqual(condition['primitive'], 'clm')
        self.assertTrue(Path(condition['config']).is_file())
        self.assertEqual(CONDITION_TO_PRIMITIVE['clm'], 'clm')
        self.assertNotIn('clm', INFINITE_BUDGET_CONDITIONS)       # finite-budget cells: di__b<N>k__clm

    def test_prompt_is_the_benchmark_default_plus_the_context_section(self):
        from jinja2 import StrictUndefined, Template
        template = yaml.safe_load((ROOT / 'configs/config-clm.yaml').read_text())['agent']['system_template']
        default = yaml.safe_load(BACKTICKS.read_text())['agent']['system_template']
        self.assertTrue(template.startswith(default.rstrip('\n') + '\n\n## Managing your context\n'))
        self.assertNotIn('free only', template)
        rendered = Template(template, undefined=StrictUndefined).render(context_budget='12952 tokens')
        self.assertIn('Your context budget is 12952 tokens;', rendered)
        self.assertIn(r'(\[\[CTX_TURN 7 [^\]]*\]\]).*?(?=\n\[\[CTX_TURN|\Z)', rendered)
        self.assertIn(MIRROR, rendered)

    def test_unlimited_sentinel_means_no_budget(self):
        self.assertEqual(clm.ClmSettings.from_env({'MSWEA_TOKEN_BUDGET': '999999999'}).budget_tokens, 0)
        self.assertEqual(clm.ClmSettings.from_env({}).budget_tokens, 0)
        self.assertEqual(clm.ClmSettings.from_env({'MSWEA_TOKEN_BUDGET': '15000'}).budget_tokens, 15000)
        with self.assertRaises(ValueError):
            clm.ClmSettings.from_env({'MSWEA_TOKEN_BUDGET': '2000'})   # not above the 2048 reserve

    def test_other_primitives_do_not_build_a_session(self):
        with patch.dict(os.environ, {'MSWEA_PRIMITIVE': 'truncation'}, clear=True):
            agent = DefaultAgent(SimpleNamespace(), Environment(), system_template='s', instance_template='t')
        self.assertIsNone(agent._clm)


class DockerTransferTests(unittest.TestCase):
    """write_mirror / read_mirror against a stand-in for `docker exec` that runs
    the command on the host (no container)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        directory = Path(self.tmp.name)
        self.calls = directory / 'calls.log'
        executable = directory / 'docker'
        # argv: exec [-i] <container> <command...>
        executable.write_text(
            '#!/usr/bin/env bash\n'
            f'echo "$*" >> {self.calls}\n'
            'shift; [[ "$1" == -i ]] && shift; shift\n'
            'exec "$@"\n')
        executable.chmod(executable.stat().st_mode | stat.S_IXUSR)
        self.env = SimpleNamespace(container_id='abc123', config=SimpleNamespace(executable=str(executable)))
        self.path = str(directory / 'ctx dir' / 'LIVE_CTX_MAIN.txt')

    def test_round_trip_of_a_context_larger_than_one_argument_may_be(self):
        text = "[[CTX_TURN 1 role=user]]\nquotes ' \" $HOME `x` and unicode — é\n" + words(60000)
        self.assertGreater(len(text), 131072)
        clm_session.write_mirror(self.env, self.path, text)
        self.assertEqual(Path(self.path).read_text(encoding='utf-8'), text)
        self.assertEqual(clm_session.read_mirror(self.env, self.path), text)
        first, second = self.calls.read_text().splitlines()
        self.assertTrue(first.startswith('exec -i abc123 bash -c '))
        self.assertTrue(second.startswith('exec abc123 cat '))

    def test_missing_mirror_reads_as_none_and_a_failed_write_raises(self):
        self.assertIsNone(clm_session.read_mirror(self.env, self.path))
        with self.assertRaises(RuntimeError):
            clm_session.write_mirror(self.env, '/proc/nonexistent/dir/file', 'x')
        with self.assertRaises(RuntimeError):
            clm_session.write_mirror(SimpleNamespace(), self.path, 'x')   # no container, no file API


if __name__ == '__main__':
    unittest.main()
