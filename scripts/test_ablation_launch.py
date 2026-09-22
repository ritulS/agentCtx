"""Offline checks for ablation task selection and preserving legacy results."""
import contextlib
import copy
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import run_experiment as runner

ROOT = Path(__file__).resolve().parent.parent


class AblationLaunchTests(unittest.TestCase):
    def test_all_model_launches_select_abl25(self):
        ids = lambda name: {r['instance_id'] for r in json.loads((ROOT / 'task_lists' / name).read_text())}
        selected = ids('ablation_25tasks.json')
        self.assertEqual(len(selected), 25)
        self.assertLess(selected, ids('ablation_30tasks.json'))
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            for name in ['scripts/run_experiment_iclr.py', 'task_lists/p100_all_100_tasks.json',
                         'task_lists/ablation_25tasks.json', 'configs/config-devstral-vllm.yaml',
                         'configs/config-glm47flash-vllm.yaml', 'configs/config-qwen-vllm.yaml',
                         'configs/config-online-trc.yaml']:
                p = ws / name
                p.parent.mkdir(parents=True, exist_ok=True)
                p.touch()
            fake = ws / 'fake-python'
            fake.write_text('#!/usr/bin/env python3\nimport json,os,sys\nwith open(os.environ["CAPTURE"], "a") as f: f.write(json.dumps(sys.argv[1:])+"\\n")\n')
            fake.chmod(0o755)
            curl = ws / 'curl'
            curl.write_text('#!/bin/sh\nexit 0\n')
            curl.chmod(0o755)
            for model in ['qwen', 'devstral', 'glm']:
                capture = ws / (model + '.jsonl')
                env = dict(os.environ, AGENTCTX_WS=tmp, PYTHON=str(fake), RUN_EVAL='1',
                           SECTIONS='main ablation', CAPTURE=str(capture), PATH=tmp + ':' + os.environ['PATH'])
                subprocess.run(['bash', str(ROOT / 'scripts/run_agent_models_expansion.sh'), model],
                               env=env, check=True, stdout=subprocess.DEVNULL)
                calls = [json.loads(line) for line in capture.read_text().splitlines()]
                self.assertEqual(len(calls), 130)
                for section, count, filename in [('main', 13, 'p100_all_100_tasks.json'),
                                                  ('ablation', 52, 'ablation_25tasks.json')]:
                    group = [c for c in calls if c[c.index('--iclr-section') + 1] == section]
                    self.assertEqual(len(group), count * 2)
                    self.assertEqual(sum('--eval-only' in c for c in group), count)
                    for c in group:
                        self.assertEqual(Path(c[c.index('--tasks-file') + 1]).name, filename)

    def test_evaluation_preserves_excluded_rows(self):
        for mode in ['--eval-only', '--with-eval']:
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as tmp:
                rows = [dict(key='keep__r1', instance_id='keep', resolved=None),
                        dict(key='legacy__r1', instance_id='legacy', resolved=None)]
                saved = []
                class Benchmark:
                    name = 'swe-bench'
                    def run_experiments(self, **kwargs):
                        return kwargs['existing_results']
                    def evaluate_results(self, selected, save):
                        self_test.assertEqual([r['instance_id'] for r in selected], ['keep'])
                        updated = [dict(selected[0], resolved=True)]
                        save(updated)
                        return updated
                self_test = self
                with patch.object(sys, 'argv', ['runner', '--ablation', 'test', '--tasks-file', 'test.json', mode]), \
                     patch.object(runner, 'model_results_dir', return_value=Path(tmp)), \
                     patch.object(runner, 'create_benchmark', return_value=Benchmark()), \
                     patch.object(runner, 'load_tasks', return_value=[dict(instance_id='keep')]), \
                     patch.object(runner, '_write_run_info'), \
                     patch.object(runner, 'load_existing_results', return_value=rows), \
                     patch.object(runner, 'save_results', side_effect=lambda r: saved.append(copy.deepcopy(r))), \
                     contextlib.redirect_stdout(io.StringIO()):
                    runner.main()
                self.assertTrue(saved)
                for snapshot in saved:
                    self.assertEqual(len(snapshot), 2)
                    self.assertTrue(snapshot[0]['resolved'])
                    self.assertEqual(snapshot[1], dict(key='legacy__r1', instance_id='legacy', resolved=None))


if __name__ == '__main__':
    unittest.main()
