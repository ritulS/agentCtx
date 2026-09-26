# Why the FC∞ / "15 min – 1 hour" runs did not resolve (2026-09-10)

Scope: the 165 runs (55 tasks × 3) of `ICLR_results/swebench/main/qwen35b/di__binf__fc`
whose SWE-bench Verified difficulty is "15 min - 1 hour" (`tasks55.txt`).
`causes.csv` has one row per run with `outcome`, `cause`, `failing_test`, `detail`, and
timing/format-error columns. Nothing under `ICLR_results/swebench` was modified.

| cause | runs | meaning |
|---|---|---|
| resolved | 67 | |
| harness_timeout_1500s (+_inflight_hang) | 31 + 14 | `AGENT_TIMEOUT=1500` in `scripts/run_experiment.py` killed the agent mid-exploration (median 74 steps). `_inflight_hang`: the last LLM call had been pending >120 s when killed. |
| wrong_fix:* | 26 | patch applied, hidden tests fail (sub-category from patch-vs-gold review) |
| step_limit_wandering / step_limit_loop | 7 / 3 | 125-step limit; loop = same command ≥20× in the last 40 steps |
| eval_false_negative | 7 | canonical eval errored/missing, but the byte-identical patch is `resolved=True` in other eval dirs |
| submission_not_a_diff | 4 | agent's final command printed a code excerpt instead of `git diff` |
| eval_evidence_missing | 4 | no eval evidence anywhere; `resolved=False` unverified |
| eval_infra_error | 2 | docker "container name already in use" (sklearn-14710) |

Key facts behind the timeout rows: time is almost entirely LLM latency (mean 1317 s of 1337 s
recorded); per-step latency at equal prompt size was ~2× higher in the 2026-05-03 and 2026-08-28
batches than in 2026-03-30/31 (timeout rate 44% / 31% vs 7%); every assistant message carries
the model's thinking text (`</think>` present, no reasoning parser on the vLLM side), so
full-context prompts reach 30–60k tokens; 42 of the 45 timed-out runs also lost 153 steps to
"Expected exactly 1 action, found 0" format errors.

Provenance mismatch (2 runs): django-11734 r2 and sympy-12419 r1 have result records from the
2026-03-30 timed-out run but `trajectory.json` from a 2026-04-16 rerun that Submitted a
(never evaluated) patch.

Needs re-evaluation / result sync on a machine with docker access (15 runs):
the 7 eval_false_negative, 2 eval_infra_error, 4 eval_evidence_missing, and the 2 provenance-mismatch
patches. See `causes.csv` for the keys.

Scripts: `analyze.py` (last commands / loops), `timing.py` (per-step timing decomposition),
`evals2.py` (report lookup + gold-file overlap), `build_causes.py` (writes `causes.csv`; expects a
`diagnoses.tsv` next to `tasks55.txt`). Patch-vs-gold diagnoses were produced by a reviewing
subagent from bundles of problem statement, eval report, gold patch, and agent patch.
