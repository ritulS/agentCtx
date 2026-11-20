# Adaptive primitive, trigger, and depth

A user-supplied policy chooses the next compression configuration after the
current query's compression operations finish. Each agent has its own settings;
the implementation does not mutate the environment or global compression ratio.

## Experiment runner: explicit opt-in

Use `scripts/run_experiment.py` with one of these options:

```bash
# Only the dedicated adaptive condition runs by default.
venv/bin/python scripts/run_experiment.py \
  --model-tag adaptive-example \
  --adaptive-schedule configs/adaptive_schedule.example.json \
  --n-tasks 1 --runs-per-task 1 --max-workers 1

# Include an unchanged full-context baseline in the same experiment.
venv/bin/python scripts/run_experiment.py \
  --model-tag adaptive-comparison \
  --adaptive-schedule configs/adaptive_schedule.example.json \
  --conditions adaptive full-context \
  --n-tasks 1 --runs-per-task 1 --max-workers 1

# Dynamic policy: importable Python function plus initial config JSON object.
venv/bin/python scripts/run_experiment.py \
  --model-tag adaptive-policy \
  --adaptive-policy my_policy:choose_next \
  --adaptive-initial-config configs/my_initial_config.json
```

These flags work for SWE-bench and `--benchmark terminal-bench` in the generic
runner. The fixed-grid ICLR wrapper does not expose adaptive cells; the r2
wrapper (`scripts/run_experiment_r2.py`) accepts `adaptive-<tag>` cells
(`--r2-cell d05__b15k__adaptive-prefix3-tts --conditions adaptive
--adaptive-schedule ...`), checking that every schedule entry carries the
cell's budget and depth (`agentctx.experiments.iclr.validate_adaptive_cell_semantics`);
`scripts/expansions/run_r2_swe_never7_adaptive.sh` is the launcher built on it.
For dynamic policies, `my_policy` must be importable by both the runner and agent worker
(for example under `src/`, or on `PYTHONPATH`). All primitives use the agent
configuration supplied with `--agent-config`; dynamic switching does not switch
agent prompts/model configs. Supply prompts suitable for the chosen primitives.

`adaptive` is a separate condition and is never reported as baseline, even when
its initial budget is unlimited. An online-only initial configuration retains a null
budget in run_info.json and result rows; console/Markdown show `no token budget`.
The worker's MSWEA_TOKEN_BUDGET is empty in that case; its adaptive manifest is
the authoritative configuration. `--budget` and `--depth` still configure fixed
conditions; adaptive settings come entirely from the explicit schedule/initial
config. If `--conditions` is provided with adaptive flags, it must include
`adaptive`. No ordinary condition is converted into an adaptive condition.

Both benchmark adapters strip inherited `MSWEA_ADAPTIVE_*` selection options
from child environments. Exporting a schedule/policy in the shell therefore
cannot silently alter a sweep or its baseline. The adapters pass a saved
manifest only to the dedicated adaptive condition.

Before launching, the runner validates and saves normalized configuration,
its SHA-256, source path, and decision semantics (`query_v1`). Python policies
also have their source module copied and hashed. Saved locations:

- `_adaptive/<sha256>.json`: configuration snapshot, including policy source.
- `adaptive_conditions.json`: persistent launch identity, even if no task finishes.
- `run_info.json`: the selection for this launch.
- Each `experiment_results.json` row and worker `token_log.json`: adaptive metadata,
  with configuration and hash (the Python source text stays in the snapshot).

Workers read the schedule snapshot, so editing the original schedule during a
run does not change later tasks. For Python policies the worker checks that the
importable module source still matches the snapshot and fails if it changed.
The hash covers that source module, not its imported dependencies or external
services/data; pin those separately if the policy uses them.

Resume checks compare the selected configuration/hash with saved launch and
result records **before skipping task keys or overwriting run_info**. Changed
settings or missing adaptive metadata on an existing adaptive row produce an
error requesting a new output directory (`--model-tag` or SWE `--ablation`).
Existing fixed-condition results retain their previous schema and resume logic.
`--eval-only` does not rewrite launch metadata.

## Python callback API

```python
from agentctx.compression.adaptive import CompressionConfig, CompressionEvent
from minisweagent.agents.default import DefaultAgent


def choose_next(event: CompressionEvent) -> CompressionConfig | None:
    if event.index == 1:
        return CompressionConfig("online_claude_select", step_interval=3)
    if event.kind == "online_claude_select":
        return CompressionConfig("summarization_free", budget=20000, depth=0.3)
    return None  # retain the settings


agent = DefaultAgent(
    model, env,
    system_template="...", instance_template="{{task}}",
    memory_config=CompressionConfig("truncation", budget=15000, depth=0.5),
    memory_policy=choose_next,
)
agent.run(task)
```

The callback receives the final post-compression history (`event.messages`, a
deep copy), configuration applied, before/after/saved tokens, step, and a 1-based
policy decision index. `event.kinds` lists the operations in order, e.g.
`("online_claude_select", "budget")`. `event.kind` is the online primitive's name
when that operation ran, otherwise `budget`. `event.tokens_saved` covers the whole compression pipeline.

Return a complete `CompressionConfig`, or use
`dataclasses.replace(event.config, budget=20000)` to modify a field. Return None
to retain the settings. Unknown primitives, invalid budgets/depths/step intervals,
and invalid callback return values fail explicitly. Exceptions propagate before
inference; completed compression and policy-error records are retained.

Primitive names match `MSWEA_PRIMITIVE`; `adaptive.PRIMITIVES` lists all supported
names (`truncation`, `summarization_free`, `online_claude_extract`,
`online_claude_select`; the ICLR-era primitives, CLM and the staggered policies
were removed on 2026-11-19 and schedules naming them are rejected). Stateful policy objects must be separate per agent. Pure functions and
`CompressionSchedule` may be shared; schedule position comes from each agent's
policy decision index.

For direct agent construction outside the experiment runner,
`MSWEA_ADAPTIVE_POLICY=module:function` still uses `MSWEA_PRIMITIVE`,
`MSWEA_TOKEN_BUDGET`, and `MSWEA_COMPRESSION_RATIO` as the initial configuration.
`MSWEA_ADAPTIVE_SCHEDULE=/path/to/schedule.json` supplies its own initial config.
Set only one of these options. A direct Python policy needs a valid initial
primitive; an empty primitive is rejected. Explicit Python arguments take
precedence over environment selections. Experiment sweeps use the CLI above.

## JSON schedule

```json
[
  {"primitive": "truncation", "budget": 15000, "depth": 0.5},
  {"primitive": "summarization_free", "budget": 20000, "depth": 0.3}
]
```

Entry 0 is the initial configuration. Each policy decision advances one entry;
the last entry is held indefinitely. Schedules are finite, not cyclic. In Python,
use `memory_policy=CompressionSchedule([config1, config2, ...])`.

## Trigger and decision timing

1. Capture the active configuration at query start.
2. Run any due online primitive (extract / select), then any required budget
   fallback, using that same configuration.
3. If at least one trigger fired, invoke the policy **once**, after both
   operations. Zero savings still count as a trigger.
4. Apply the selected settings starting with the next model query. There is no
   recursive compression loop when the callback lowers the budget.

Thus an online operation plus fallback produces two operation records but
**one** policy decision and advances a schedule only once. A budget-only fallback still
produces a policy decision. No trigger means no callback. If a custom policy
filters on event.kind, its own counter must count accepted decisions; event.index
continues to count all decisions and is not a filtered schedule index.

`budget` is an absolute estimated context-token threshold (`current > budget`).
`depth` is the existing compression ratio: TR targets `budget * depth`; the
online primitives' budget fallback targets `current * depth`. A successful
SU-free summary has no length target, and depth sizes only its TR fallback. This API does not add arbitrary pre-compression predicate triggers;
`tokens_saved` is available afterward to choose the next settings.

`step_interval=N` of an online primitive is independent of token budget. At
agent initialization its clock starts at 0. At step 3 the check occurs before
query 4. Model-query steps include failed agent queries and exclude extractor /
summarizer calls. With interval 3, online triggers occur at steps 3, 6, 9, etc.
A due trigger whose reply was rejected or errored still invokes the policy
(`skipped_reason` on the operation record).

Budget-only fallbacks **do not reset the online clock**, including when the
callback returns None or an unchanged config. Switching into an online
primitive, or explicitly changing step_interval, starts the new interval at the
current step. Thus a TR event at step 7 selecting an online primitive with
interval 3 schedules it at step 10. Returning interval 2 from the online event
at step 10 schedules the next one at step 12. Omitting step_interval keeps the
default cadence (every query). Switching out of an online primitive disables
its online hook.

An online primitive can omit budget (`None`) to use only online triggers.
Supplying a positive budget also enables the existing budget fallback,
independently of step timing. Other primitives require a positive integer
budget. Depth must be in `(0, 1]`; step_interval is a positive integer supported
only for online primitives. `freeze_k` (default 4) is retained in the config
and manifests for compatibility with the recorded OTRC schedules; since the
OTRC primitives were removed (2026-11-19) it has no effect.

## Diagnostics and tests

`adaptive_events` in token_log.json stores one decision record per query that
triggered, including ordered operation measurements under `events`, applied and
next configs, and status (`pending`, `ok`, or `error`). With MSWEA_EVENT_LOG_DIR,
these records also appear in adaptive_events.jsonl. compression_events.jsonl
continues to record the individual compression operations and their applied
adaptive_config. Online triggers whose reply was rejected or errored appear in
adaptive_events.jsonl and token_log.json with `skipped_reason` (`rejected` /
`error`) on the operation and do not change the history; accepted online
operations are recorded in compression_events.jsonl even when their token
savings are zero.
Logs describe execution; restoring callback state from checkpoints is not implemented.

```bash
venv/bin/python -m unittest discover -s tests -p 'test_adaptive*.py' -v
```
