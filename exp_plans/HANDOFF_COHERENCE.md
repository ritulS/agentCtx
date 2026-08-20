# Handoff — "Context Coherence" (ICLR 2027)

**Date:** 2026-08-17. **Owner:** Ritul. **Deadline:** abstract Sept 18, paper Sept 25 (~4.5 weeks).
**Supersedes:** HANDOFF_WORKING_SET.md (recovery angle dropped by user decision) and the framing in ICLR_ONEPAGER.md — both retired to `~/agentCtx_attic/exp_plans/` on 2026-08-19. **Landscape:** [PRIOR_WORK_MLSys.md](PRIOR_WORK_MLSys.md) Tiers 0–4.

## Problem statement

Agents act on the environment they observe, and their own actions invalidate their own observations. A file read is true until the agent edits that file. A test result is true until the code changes. Every compression policy today selects survivors by age, size, or summary quality — none knows which observations are still true. Full context retains contradictory versions of the world; aggressive clearing deletes valid and invalid state alike.

## Research question

Does superseded environment state in an agent's context causally harm its decisions, and does compression that targets invalidated state outperform compression that targets old or large state?

- **RQ1 (measure):** how much invalid state does each policy expose?
- **RQ2 (cause):** at matched volume and position, does a stale version alongside the current one change the agent's next actions and outcomes?
- **RQ3 (method + explanation):** does invalidation-driven clearing beat FC/TRC/OTRC/SU — and do per-model staleness sensitivities explain the cross-model reversal?

## Verified evidence in hand (2026-08-17, from disk)

- **Cross-model reversal at unlimited budget** (clearing effect = OTRC@∞ − FC@∞): Qwen3.5-35B-A3B **+8.5pp** (43.0→51.5, n=200/arm, Review1.csv); Devstral-Small-2-24B **−33.4pp** (71.7→38.3, n=60/arm, `devstral-2-inf`); Qwen2.5-Coder-32B 0pp at floor (10.0/10.0, uninformative); Llama 3.3 70B OTRC arm missing (one cheap Albus run to complete).
- **Staleness prevalence probe** (25 FC@∞ trajectories, conservative file-level regexes): 29% of read/test observations stale by trajectory end (34% by volume); 45% of test results superseded by a later edit; stale content ≈ 25% of all observation characters. True numbers likely higher (probe misses Python-script edits, git apply, heredocs). **Gate 1 passed.**

## The three parts

1. **Lineage measurement (zero GPU, start now).** Build version lineages for reads, searches, tests, edits over stored trajectories (~2,000 runs, 33 policies). Conservative rules: any code edit invalidates all prior test results; file-level matching for reads. Robustness under rule variants + 50-observation manual audit. Output: per-policy stale-exposure figure; per-task stale exposure vs F3 flips (explains heterogeneity mechanistically, no routing framing).
2. **Causal version-conflict test (RQ2 — Gate 2).** Branch continuations from replayed checkpoints (verify replay by output hash; report screening rate). Arms, all length- and position-matched: current state only / current + stale version / current + duplicated current (volume control) / stale only. Measure next-command divergence, edit correctness, short-horizon progress; final resolution on a subset. **Pilot: 20 checkpoints, local metrics only. Continue only if conflict arms separate.** Run on Qwen and Devstral; per-model sensitivity to (stale added) vs (valid removed) is the tested explanation for the reversal — a two-parameter hypothesis, stated as prediction, not assumption.
3. **Coherence-aware compression (RQ3).** New primitive in `memory.py` dispatch: on environment mutation, invalidate superseded observations; preserve valid ones regardless of age. Compare at 15k / P100 / 2 runs vs existing grid cells (FC, TRC, OTRC, SU — **baselines already run; only new conditions execute**). Decisive market is Devstral: recovering part of the −33.4pp at comparable token savings is the headline. Power accordingly (seed expansion on Devstral cells, not Qwen).

## Prior-work positioning (scan 2026-08-17)

Phenomenon is named, mechanism unmeasured. STALE (2605.06527): memory invalidation, synthetic personal-memory conflicts — not coding, not compression. Less Context, Better Agents (2606.10209): observes stale values "actively detrimental" — qualitative. ProcCtrlBench (2605.20251): names "ghost context." MemTX (2607.23929): versioned agent memory middleware. AgentDiet's "expired" category = heuristic cousin of our invalidation. Nobody: mechanical lineages on real coding trajectories, causal isolation at matched volume/position, invalidation-driven compression, or the cross-model reversal. One deliberate related-work paragraph required.

## Adopted ICLR execution additions (2026-08-20)

1. **Name the phenomenon once.** Use this sentence at the start of the introduction: "Tool-using agents make parts of their own context stale when their actions change the environment those observations describe." Use the cross-model reversal as evidence in the abstract, after the problem is established. Close the related-work distinction with: "Prior work often treats age as a proxy for staleness, but old context can remain valid and recent context can already be stale."
2. **Name the RQ2 volume control.** Call the duplicated-current arm **CURRENT-COPY**. It places a second copy of the current observation in the same role, position, and token volume as the stale observation in the conflict arm. A stale-vs-CURRENT-COPY contrast separates version conflict from added volume and repetition. Report this control in the main RQ2 figure.
3. **Add a reliability subset, but do not claim the axis.** TRACE already reports compression reliability with Pass-squared and Pass-at-two. Lost in Conversation follow-ups also reuse its reliability framing. The subset is reviewer defense, not a novelty claim. Before launching all 1,200 runs, run a zero-GPU metric simulation and a small trajectory pilot. If the metrics are informative, run ABL-30 x {FC, TR, TRC, OTRC} x 10 repetitions at one fixed operating point. Report per-task solve probability, consistent-solve rate, consistent-failure rate, and unstable-task rate. Do not copy the A90 and U90-10 percentiles as the primary metrics because SWE-bench outcomes are binary and those percentiles are coarse at N=10.
4. **State the study scale in the abstract.** Use 33 policies, about 19,000 trajectories, three model families, and two benchmarks. Recompute every count from the final analysis table before submission.
5. **Use the old grid as evidence, not as the contribution.** The 33-policy study establishes the reversal and the scale of the unexplained behavior. RQ1 and RQ2 supply the mechanism that the EMNLP version lacked. RQ3 tests the resulting design rule.
6. **Keep claims conditional on the gates.** The abstract can state the verified scale, prevalence, and reversal now. Causal-effect and coherence-aware-policy sentences retain result placeholders until Gate 2 and RQ3 finish.

## Direction history (do not relitigate)

Free Deletion (KV editing): archived 2026-08-10. Working-set / page-fault + fault-pricing: dropped 2026-08-17 — recovery angle vetoed; recovery-free residue was only a content taxonomy. Positional "Lost in the Trajectory": absorbed lessons (matched volume + position discipline); not the headline. Context-tolerance dose-response: superseded by this (mechanism-thin). Cross-layer forgetting stack: possible follow-up program, not this paper.

## Week plan

- **Wk 1:** Part 1 tooling (extend the probe), stale-exposure figure v0; build checkpoint replay; restore Devstral serving on Albus; complete Llama OTRC arm; commit/push tree (two-machine rule).
- **Wk 2:** Part 2 pilot (20 checkpoints, Gate 2). Go/no-go. Implement coherence-clear primitive.
- **Wk 3:** Part 2 full (40–60 checkpoints, both models); launch Part 3 runs.
- **Wk 4–6:** seeds on Devstral cells, Terminal-Bench transfer check if time, stats, figures, writing. Update `Active_runs.md` on every launch/kill/completion.

## Standing constraints

No routing/selectors, no cascade, no temporal mixing, no silent→visible framing, no recovery/fault framing, Free Deletion stays archived. Paper prose: no colons, no punchy openers, one job per sentence. Show PaperSections drafts in chat first. Chat style: ASD-STE100.
