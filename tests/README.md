# tests/ — runner equivalence suite and unit tests

## Runner equivalence

`test_runner_equivalence.py` checks that the reorganized entry points

- `scripts/run_experiment.py` (→ `src/agentctx/experiments/runner.py`)
- `scripts/run_experiment_iclr.py` (→ `src/agentctx/experiments/iclr.py`)
- `scripts/calibration/run_budget_calibration_{tb,sb}.py`
  (→ `src/agentctx/benchmarks/harbor_results.py`)

behave exactly like the versions on the reference branch
`origin/akiho-clean-20260921` (the tree just before the `src/agentctx`
reorganization).

### Running

No virtualenv is needed; `uv` is enough:

```bash
uvx --with pyyaml pytest                                   # fetches origin/<branch> first, then compares
AGENTCTX_TEST_NO_FETCH=1 uvx --with pyyaml pytest          # offline: use the refs already fetched
uvx --with pyyaml pytest -k "iclr and tb"                  # subset of scenarios
uvx --with pyyaml pytest --reference-branch akiho-clean-20260903-2   # any branch on origin
```

`--reference-branch` is repeatable and replaces the default list. Scenarios
that need a capability the reference predates (Terminal-Bench, verdict
handling, `--summary-config`, the ICLR sections, the calibration launchers)
are skipped for that branch, so older branches compare only the shared core.

Any interpreter with `pytest` and `pyyaml` works (`python -m pytest`). The
whole suite takes about 30 s. Python 3.10 and 3.12 are both fine.

### How it works

The runners cannot run for real in a test (vLLM, rootless Podman, Harbor).
Everything they need from the outside world is a subprocess, so each side is
executed in a throwaway **sandbox** laid out like the repository root:

```
<sandbox>/
  scripts/                 copied from the tree under test
  src/                     (working tree only) copied from src/
  summary_config.py        (reference tree only) root-level modules it imports
  configs/                 synthetic YAML configs, identical on both sides
  task_lists/, results/ablations/tasks.json, data/tb1-harbor-0.1.1/
  venv/bin/python          → tests/fakes/fake_agent.py   (mini-swe-agent + swebench harness)
  venv-harbor/bin/harbor   → tests/fakes/fake_harbor.py  (harbor run)
  tests/fakes/bin/docker   on PATH                        (docker info → 0)
```

The fakes are pure functions of their argv and the `MSWEA_*` environment and
record the exact invocation (argv, cwd, selected env) next to their output.
For every scenario in `test_runner_equivalence.py` both sandboxes run the same
command lines (a script is looked up as `scripts/<name>` or
`scripts/<group>/<name>`, so the grouping of launchers is transparent), and the
test asserts:

1. identical exit codes (each command declares the code it expects, so a
   scenario in which both sides crash the same way cannot pass by accident);
2. identical stdout/stderr lines after normalization;
3. identical files under `results/`, `ICLR_results/` and `logs/`, including
   `experiment_results.json`, `run_info.{json,md}`, copied Harbor artifacts,
   superseded attempts, calibration manifests and the recorded agent/Harbor
   invocations.

Reference code is obtained with `git fetch origin <branch>` followed by
`git archive <commit> scripts src summary_config.py memory.py` (whichever
exist), once per session.

### Normalization

Rewritten before comparison, in `harness.py`:

- the sandbox path → `<WS>`; Harbor job-name timestamps → `<TS>`;
- `timestamp`, `started`, `e2e_latency_s` values and the `| Started |` row;
- progress counters `[ 3/30]` → `[<N>/30]` and glued progress lines: with
  `--max-workers > 1` `print()` interleaves across threads on both sides;
- rows of `experiment_results.json` are sorted by `key` (completion order
  depends on scheduling).

### Intentional differences

The reorganization moved `memory.py` to `src/agentctx/compression/primitives.py`
(a root-level `memory.py` alias remains for the pinned mini-swe-agent commit)
and the Harbor adapter to `agentctx.benchmarks.harbor_adapter`. Two things
therefore differ on purpose and are normalized away for the equivalence check
but asserted explicitly in their own tests:

| What | reference | working tree |
|---|---|---|
| `PYTHONPATH` handed to the agent / Harbor | `<WS>[:…]` | `<WS>/src:<WS>[:…]` |
| `harbor run --agent` | `scripts.bench_adapters.harbor_adapter:CompressionAgent` (runner) / `tbench.harbor_adapter:CompressionAgent` (calibration) | `agentctx.benchmarks.harbor_adapter:CompressionAgent` |

### Adding a scenario

Append a `scenario(...)` to `SCENARIOS` in `test_runner_equivalence.py`. Use
`failing([...])` for a command that must exit non-zero, and `requires=...`
for capabilities the reference must have (`TB`, `TB_VERDICTS`, `SUMMARY`,
`SECTIONS`, `TB_CALIBRATION`, `SB_CALIBRATION`). Fixture task ids drive the
fakes: SWE-bench ids ending in `-crash` / `-nopatch` / `-applyfail` /
`-evalerr`, Terminal-Bench names ending in `-fail` / `-timeout` / `-envfail` /
`-vtimeout` (see `harness.py`).

## Unit tests

| File | Needs | Covers |
|---|---|---|
| `test_tb_verdict.py` | pyyaml | Terminal-Bench verdict handling, re-run loop, superseded attempts |
| `test_iclr_summarizer_guard.py` | – | `agentctx.experiments.iclr.validate_summarizer` |
| `test_ablation_launch.py` | bash | ABL-25 selection in `run_agent_models_expansion.sh`, selective evaluation |
| `test_summary_query.py` | litellm, mini-swe-agent (`venv`) | prose summaries through mini-swe-agent v2 models |
| `test_harbor_cancellation.py` | Harbor, mini-swe-agent (`venv-harbor`) | worker cancellation in the Harbor adapter |
| `test_replay.py` | Harbor (`venv-harbor`) | trajectory replay re-verification |

The last three skip themselves when their dependencies are missing, so the
plain `uvx --with pyyaml pytest` run stays green; run them with the matching
virtualenv, e.g. `venv-harbor/bin/python -m pytest tests/test_harbor_cancellation.py`.
`pytest.ini` puts `src/` and `mini-swe-agent/src` on the import path.
