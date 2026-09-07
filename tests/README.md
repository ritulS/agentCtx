# tests/ — runner equivalence suite

Checks that the refactored entry points

- `scripts/run_experiment.py` (→ `src/agentctx/experiments/runner.py`)
- `scripts/run_experiment_iclr.py` (→ `src/agentctx/experiments/iclr.py`)

behave exactly like the versions on the reference branches
`origin/akiho-expansion` (SWE-bench only) and
`origin/akiho-expansion-terminalbench-0829` (SWE-bench + Terminal-Bench).

## Running

No virtualenv is needed; `uv` is enough:

```bash
uvx --with pyyaml pytest tests/test_runner_equivalence.py              # fetches origin/<branch> first, then compares
AGENTCTX_TEST_NO_FETCH=1 uvx --with pyyaml pytest tests/test_runner_equivalence.py   # offline: use the refs already fetched
uvx --with pyyaml pytest tests/test_runner_equivalence.py -k "iclr and tb"                                # subset of scenarios
uvx --with pyyaml pytest tests/test_runner_equivalence.py --reference-branch akiho-expansion              # one reference branch only
uvx --with pyyaml pytest tests/test_runner_equivalence.py --reference-branch some-other-branch            # any branch on origin
```

`--reference-branch` is repeatable and replaces the default list. `-k` also
works on the branch id, but note that `-k akiho-expansion` matches both
defaults (substring match); use `-k "akiho-expansion and not terminalbench"`
or, simpler, `--reference-branch`.

Any interpreter with `pytest` and `pyyaml` works (`python -m pytest`). The
whole suite takes about 15 s. Python 3.10 and 3.12 are both fine.

## How it works

The runners cannot run for real in a test (vLLM, rootless Podman, Harbor).
Everything they need from the outside world is a subprocess, so each side is
executed in a throwaway **sandbox** laid out like the repository root:

```
<sandbox>/
  scripts/                 copied from the tree under test
  src/                     (working tree only) copied from src/
  configs/                 synthetic YAML configs, identical on both sides
  task_lists/, results/ablations/tasks.json, data/tb1-harbor-0.1.1/
  venv/bin/python          → tests/fakes/fake_agent.py   (mini-swe-agent + swebench harness)
  venv-harbor/bin/harbor   → tests/fakes/fake_harbor.py  (harbor run)
  tests/fakes/bin/docker   on PATH                        (docker info → 0)
```

The fakes are pure functions of their argv and the `MSWEA_*` environment and
record the exact invocation (argv, cwd, selected env) next to their output.
For every scenario in `test_runner_equivalence.py` both sandboxes run the same
command lines, and the test asserts:

1. identical exit codes (each command declares the code it expects, so a
   scenario in which both sides crash the same way cannot pass by accident);
2. identical stdout/stderr lines after normalization;
3. identical files under `results/`, `ICLR_results/` and `logs/`, including
   `experiment_results.json`, `run_info.{json,md}`, copied Harbor artifacts and
   the recorded agent/Harbor invocations.

Reference code is obtained with `git fetch origin <branch>` followed by
`git archive <commit> scripts`, once per session. Scenarios that need a
capability the reference predates (Terminal-Bench on `akiho-expansion`) are
skipped for that branch.

### Normalization

Rewritten before comparison, in `harness.py`:

- the sandbox path → `<WS>`; Harbor job-name timestamps → `<TS>`;
- `timestamp`, `started`, `e2e_latency_s` values and the `| Started |` row;
- progress counters `[ 3/30]` → `[<N>/30]` and glued progress lines: with
  `--max-workers > 1` `print()` interleaves across threads on both sides;
- rows of `experiment_results.json` are sorted by `key` (completion order
  depends on scheduling).

### Intentional differences

The refactor moved `memory.py` to `src/agentctx/compression/primitives.py`
and the Harbor adapter to `agentctx.benchmarks.harbor_adapter`. Two things
therefore differ on purpose and are normalized away for the equivalence check
but asserted explicitly in their own tests:

| What | reference | working tree |
|---|---|---|
| `PYTHONPATH` handed to the agent / Harbor | `<WS>[:…]` | `<WS>/src:<WS>[:…]` |
| `harbor run --agent` | `scripts.bench_adapters.harbor_adapter:CompressionAgent` | `agentctx.benchmarks.harbor_adapter:CompressionAgent` |

## Adding a scenario

Append a `scenario(...)` to `SCENARIOS` in `test_runner_equivalence.py`. Use
`failing([...])` for a command that must exit non-zero, and
`requires=TB` if it needs the Terminal-Bench adapter. Fixture task ids drive
the fakes: SWE-bench ids ending in `-crash` / `-nopatch`, Terminal-Bench names
ending in `-fail` / `-timeout` (see `harness.py`).

## Summary regression tests

`test_summary_query.py` covers the fix ported from
`cd1716ff194f69871b6665d0e0d9e0a4d4773b0c`: all four summary variants
accept prose and preserve token usage, commands quoted in summaries are not
parsed as actions, and regular agent queries still require commands.

With the runtime dependencies installed, run from the repository root:

```bash
python -m pytest tests/test_summary_query.py
```

The source paths for `agentctx` and the local `mini-swe-agent` submodule are
configured in `pytest.ini`. The lightweight runner environment above does
not include the model dependencies required for these tests.
