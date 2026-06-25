# Staggered compression — pilot design

Owner: ritul@utexas.edu. Created 2026-05-06.
Status: GATING DOC for the staggered pilot in DOBBY_PLAN.md §1.

---

## 1. Motivation

The n=100 results crystallize a tension:

- **Heterogeneity is real.** Oracle-of-k routing across the 11-primitive set
  saturates around 75% combined resolve rate at 20k — different primitives
  resolve different tasks.
- **Routing is unrecoverable from observables.** Leave-one-out logistic
  regression on problem-statement features hits ≈50% accuracy on the
  TR-vs-TRC+SS partition. We cannot pick the right primitive *a priori*.

Staggering asks a different question. Instead of choosing one primitive per
trajectory, **alternate two primitives across compression events within the
same trajectory**. If the choice of compression operation determines which
state the agent is in for its next reasoning step, exposing the trajectory to
both operations may produce a union of recoverable states — a noisy mixture
that catches resolutions either single primitive misses.

This is *not* routing (no per-task selection) and *not* stacking (no cascade
within one event). It is **temporal mixing**.

## 2. Hypothesis

For tasks where neither TR alone nor the budget-best compressor alone
resolves consistently (resolve rate ∈ {0, 0.5}), a staggered policy that
alternates between them at compression-event time will resolve at least one
run.

A positive pilot is **any task in the 6-task pilot set where a staggered
strategy resolves at least one run while both single-primitive baselines
resolve 0 runs at the same budget**. A negative pilot is staggered ≤
max(single) on every cell.

## 3. Mechanism

Both strategies pick from a budget-specific pair `(TR, budget-best)`:

| Budget | Pair |
|---|---|
| 10k  | `(truncation, trc_structured_summarize)` |
| 15k  | `(truncation, summarization_partial)` |
| 20k  | `(truncation, trc_structured_summarize)` |

The pair is `(TR, predictability-sprint pair-mate at that budget)` — i.e.,
the two primitives the predictability analysis identified as covering
non-overlapping task slices.

**`staggered_alternate`** — deterministic ABABAB. The picked primitive flips
on every compression event. Run-to-run variance comes from LLM stochasticity
only.

**`staggered_random`** — coin flip per compression event. RNG seeded from
`hash(MSWEA_RUN_KEY)`, so the sequence is reproducible per run.

Implementation: [default.py:343-404](../mini-swe-agent/src/minisweagent/agents/default.py#L343-L404).
The dispatch records the picked sequence in `self._staggered_log`, written
to the trajectory metadata for post-hoc analysis.

## 4. Run plan

- **Tasks:** 6 tasks frozen in [task_lists/staggered_pilot.json](../task_lists/staggered_pilot.json)
  (chosen pre-P100 as the hardest by total resolves on Review1.csv n=30).
  Kept unchanged for this pilot.
- **Strategies:** `staggered_alternate`, `staggered_random`.
- **Budgets:** 10k, 15k, 20k (all three).
- **Runs:** 2 per (task, strategy, budget) cell.
- **Total:** 6 × 2 × 3 × 2 = **72 fresh runs**.
- **Wall-clock estimate:** ~75 minutes at 16 workers.
- **Output dirs:** `results/ablations/staggered-pilot-{10000,15000,20000}/`.
- **Log:** `logs/staggered_pilot.log`.
- **Wrapper:** [scripts/run_staggered_pilot.sh](../scripts/run_staggered_pilot.sh)
  (already exists; sweeps all 3 budgets).

## 5. Analysis

After the pilot completes:

1. **Add `fill_staggered()` to [Review1/build_review1.py](../Review1/build_review1.py)**
   to emit `primitive ∈ {staggered-alternate, staggered-random}` rows.
   Mirrors `fill_otrc_stacked()`.
2. **Per-cell readout:** for each (task, budget), compare
   `staggered_alternate`, `staggered_random`, `TR-only`, and `budget-best-only`
   resolve rates side-by-side. Highlight any cell where staggered > both
   singles.
3. **Sequence inspection:** read `_staggered_log` from the trajectory
   metadata for any "lifted" task to identify whether the resolution event
   followed a specific compression-pattern signature.

## 6. Decision criterion

| Outcome | Interpretation |
|---|---|
| ≥1 lifted task across the 18 cells | Mechanism is real on hard cases. Worth scaling to a full ablation (30 or 100 tasks × 3 budgets × 2 strategies). |
| 0 lifted tasks AND staggered ≤ max(single) on all cells | Mechanism inert. Drop staggering as a paper direction. |
| Staggered *worse* than max(single) on most cells | Mixing destroys capability. Negative result with a story (compression timing has memory; alternating breaks invariants the agent depends on). |

Either outcome is publishable as a one-paragraph addition; the kill-or-scale
decision is what this pilot exists for.

## 7. Caveats

- **Power.** 12 trials per (strategy, budget) cell. CIs are wide. This is a
  qualitative gating signal, not a paper figure.
- **Pre-P100 task list.** Some of the 6 tasks may be 0-resolve floor cases
  under n=100, in which case staggering also won't resolve them
  (uninformative). We are betting that ≥1 of the 6 is in the marginal zone.
- **Pair fixed by budget.** This pilot does not test other pairings (e.g.,
  TRC+SS ↔ SU-partial, OTRC ↔ TR). One pair per budget is sufficient for
  the gating decision.
- **`staggered_alternate` has 1 trajectory shape per budget** (always starts
  with TR on event 0). All run-to-run variance comes from LLM stochasticity.
  If we want to test whether starting with the budget-best matters, add a
  second alternate variant in a follow-up.
- **Reproducibility for `staggered_random`** depends on `MSWEA_RUN_KEY`.
  Re-runs with the same key produce the same coin-flip sequence; this is
  intended, not a bug.

## 8. Cross-references

- Implementation: [default.py:343-404](../mini-swe-agent/src/minisweagent/agents/default.py#L343-L404)
- Run wrapper: [scripts/run_staggered_pilot.sh](../scripts/run_staggered_pilot.sh)
- Task set: [task_lists/staggered_pilot.json](../task_lists/staggered_pilot.json)
- Predictability evidence: [Review1/predictability_sprint.py](../Review1/predictability_sprint.py)
- Queue position: [exp_plans/DOBBY_PLAN.md](DOBBY_PLAN.md) §1
