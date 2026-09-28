"""Explicit adaptive runner selection, isolation, provenance and safe resume."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from agentctx.compression.adaptive import resolve_policy
from agentctx.compression.selection import (
    ADAPTIVE_ENV, build_selection, condition_environment, load_selection,
    prepare_run, snapshot_selection, selection_metadata,
)
from harness import build_sandbox, current_tree


class AdaptiveRunnerTests(unittest.TestCase):
    def schedule(self, root, budget=1000):
        path = root / 'schedule.json'
        path.write_text(json.dumps([{'primitive': 'truncation', 'budget': budget}]))
        return path

    def test_manifest_is_snapshot_not_live_schedule(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            schedule = self.schedule(root)
            selected = build_selection(schedule=schedule)
            path = snapshot_selection(selected, root / 'results')
            self.schedule(root, 2000)
            with patch.dict(os.environ, {'MSWEA_ADAPTIVE_MANIFEST': str(path)}, clear=True):
                policy, initial = resolve_policy()
            self.assertEqual(initial.budget, 1000)
            self.assertEqual(policy.initial, initial)
            self.assertEqual(load_selection(path)['sha256'], selected['sha256'])

    def test_protect_baseline_and_fixed_conditions_from_ambient_env(self):
        env = {key: 'unwanted' for key in ADAPTIVE_ENV}
        env['KEEP_ME'] = 'yes'
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ('full-context', 'truncation'):
                clean = condition_environment(env, {'condition': name}, root)
                self.assertEqual(clean, {'KEEP_ME': 'yes'})
            selected = build_selection(schedule=self.schedule(root))
            with self.assertRaisesRegex(ValueError, 'dedicated adaptive'):
                condition_environment(env, {'condition': 'full-context', 'adaptive': selected}, root)
            self.assertEqual(env['MSWEA_ADAPTIVE_SCHEDULE'], 'unwanted')

    def test_resume_checks_launch_manifest_even_without_result_rows(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = build_selection(schedule=self.schedule(root))
            conditions = [{'condition': 'adaptive', 'adaptive': first}]
            prepare_run(conditions, [], root / 'results')
            prepare_run(conditions, [], root / 'results')
            second = build_selection(schedule=self.schedule(root, 2000))
            with self.assertRaisesRegex(ValueError, 'saved launch'):
                prepare_run([{'condition': 'adaptive', 'adaptive': second}], [], root / 'results')

    def test_resume_rejects_missing_or_changed_result_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            selected = build_selection(schedule=self.schedule(root))
            conditions = [{'condition': 'adaptive', 'adaptive': selected}]
            for metadata in (None, {'sha256': 'wrong', 'spec': selected['spec']}):
                row = {'condition': 'adaptive', 'adaptive': metadata}
                with self.assertRaisesRegex(ValueError, 'saved results'):
                    prepare_run(conditions, [row], root / 'results')

    def test_python_policy_snapshot_and_source_change_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            module = root / 'adaptive_runner_test_policy.py'
            module.write_text('def choose(event):\n    return None\n')
            initial = root / 'initial.json'
            initial.write_text('{"primitive":"online_trc", "step_interval":2}')
            sys.path.insert(0, directory)
            self.addCleanup(sys.path.remove, directory)
            self.addCleanup(sys.modules.pop, 'adaptive_runner_test_policy', None)
            selected = build_selection(policy='adaptive_runner_test_policy:choose', initial=initial)
            path = snapshot_selection(selected, root / 'results')
            self.assertEqual(load_selection(path)['policy_source'], module.read_text())
            with patch.dict(os.environ, {'MSWEA_ADAPTIVE_MANIFEST': str(path)}, clear=True):
                policy, config = resolve_policy()
                self.assertIsNone(policy(None))
                self.assertEqual(config.step_interval, 2)
                module.write_text('def choose(event):\n    return event.config\n')
                with self.assertRaisesRegex(ValueError, 'source changed'):
                    resolve_policy()

    def test_cli_swe_and_tb_adaptive_baseline_and_resume(self):
        for benchmark in ('swe-bench', 'terminal-bench'):
            with self.subTest(benchmark=benchmark), tempfile.TemporaryDirectory() as directory:
                sandbox = build_sandbox(Path(directory), current_tree())
                schedule = self.schedule(sandbox.root)
                argv = ['run_experiment.py', '--benchmark', benchmark, '--model-tag', 'adaptive-test',
                        '--adaptive-schedule', str(schedule), '--conditions', 'adaptive', 'full-context',
                        '--n-tasks', '1', '--runs-per-task', '1', '--max-workers', '1']
                env = {key: '/not/a/real/file' for key in ADAPTIVE_ENV}
                result = sandbox.run(argv, extra_env=env)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                output = sandbox.root / 'results/adaptive-test'
                path = output / 'experiment_results.json'
                rows = json.loads(path.read_text())
                adaptive = next(r for r in rows if r['condition'] == 'adaptive')
                baseline = next(r for r in rows if r['condition'] == 'full-context')
                self.assertFalse(adaptive['is_baseline'])
                self.assertTrue(baseline['is_baseline'])
                self.assertNotIn('adaptive', baseline)
                self.assertEqual(adaptive['adaptive']['spec']['configs'][0]['budget'], 1000)
                info = json.loads((output / 'run_info.json').read_text())
                self.assertEqual(info['adaptive_conditions']['adaptive'], adaptive['adaptive'])
                invocations = [json.loads(p.read_text()) for p in sandbox.root.rglob('invocation.json')]
                self.assertEqual(len(invocations), 2)
                self.assertEqual(sum('MSWEA_ADAPTIVE_MANIFEST' in i['env'] for i in invocations), 1)
                for invocation in invocations:
                    self.assertNotIn('MSWEA_ADAPTIVE_POLICY', invocation['env'])
                    self.assertNotIn('MSWEA_ADAPTIVE_SCHEDULE', invocation['env'])
                result = sandbox.run(argv, extra_env=env)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(json.loads(path.read_text()), rows)
                resumed_info = (output / 'run_info.json').read_text()
                self.schedule(sandbox.root, 2000)
                result = sandbox.run(argv, extra_env=env)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('Adaptive settings differ', result.stderr)
                self.assertEqual(json.loads(path.read_text()), rows)
                self.assertEqual((output / 'run_info.json').read_text(), resumed_info)

    def test_cli_policy_and_default_adaptive_only(self):
        with tempfile.TemporaryDirectory() as directory:
            sandbox = build_sandbox(Path(directory), current_tree())
            module = sandbox.root / 'src/runner_test_policy.py'
            module.write_text('def choose(event):\n    return None\n')
            initial = sandbox.root / 'initial.json'
            initial.write_text('{"primitive":"online_trc", "step_interval":2}')
            argv = ['run_experiment.py', '--model-tag', 'policy-test',
                    '--adaptive-policy', 'runner_test_policy:choose',
                    '--adaptive-initial-config', str(initial), '--n-tasks', '1',
                    '--runs-per-task', '1', '--max-workers', '1']
            result = sandbox.run(argv)
            self.assertEqual(result.returncode, 0, result.stderr)
            rows = json.loads((sandbox.root / 'results/policy-test/experiment_results.json').read_text())
            self.assertEqual({r['condition'] for r in rows}, {'adaptive'})
            self.assertEqual(rows[0]['adaptive']['spec']['initial']['step_interval'], 2)
            self.assertNotIn('policy_source', rows[0]['adaptive'])
            module.write_text('def choose(event):\n    return event.config\n')
            result = sandbox.run(argv)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('Adaptive settings differ', result.stderr)


if __name__ == '__main__':
    unittest.main()
