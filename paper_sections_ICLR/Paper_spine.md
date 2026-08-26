# Paper spine — ICLR 2027

**Status** ADOPTED 2026-08-26 (locked by Ritul after the framing bake-off and
venue-precedent review). Deadlines — abstract Sept 18, paper Sept 25, 2026.
Supersedes the 2026-08-21 transfer spine, which is absorbed as contribution 3.
Retired alternatives live in `~/agentCtx_attic/exp_plans/`.

**Evidence trail** `results/deep_dive_2026-08-25/` — findings with runnable
code, 10 adversarial verifier re-derivations, `verdicts_full.json`, and the
2026-08-26 cross-model addendum. Handoff `exp_plans/HANDOFF_COST_LEVER.md`.
Dossier artifact https://claude.ai/code/artifact/7425f8d7-48ad-4283-b39f-b4bd8b26bd30.
Every number below survived independent adversarial re-derivation.

## One-line claim

Reaching the cost frontier of context compression is easy, and the quality
competition between policies is mostly unmeasurable as practiced. In both
models we test, a training-free policy matches full-context resolve rate at
56 to 75 percent of the token cost — but which policy sits on that frontier
is model-specific, the residual within-model policy structure is about four
points, and comparison designs of the field's current size cannot select on
it. ("Cost lever, not quality lever" survives as the conclusion's summary
line, not the headline. Reframed 2026-08-26 twice — first after Ritul's
collision objection, then after the parity-frontier check showed universal
parity is too strong.)

## Research question

When a coding agent compresses its context, what changes robustly, and what
only appears to change?

1. Which reported effects of compression policy on resolve rate survive
   rollout noise, outcome-selected task cohorts, and harness censoring?
2. How large is the cost benefit at matched resolve rate, and does it hold on
   unselected tasks and on a second benchmark?
3. Do the surviving quality effects belong to the policy or to the model?

## Contributions

1. **An audit of agent-compression evaluation.** Five mechanisms that
   manufacture spurious policy findings — selection-on-noise oracles,
   noise-level task disagreement, outcome-stratified task cohorts, an inert
   configuration knob, and asymmetric harness censoring — each demonstrated
   and corrected on about 19,000 trajectories, including our own prior claims.
   The audit separates effects that are absent from effects that current
   designs cannot identify.
2. **The cost result — a cheap parity frontier.** In each model at least one
   training-free policy is statistically indistinguishable from full context
   at 56 to 75 percent of token cost on unselected tasks, and at 27 to 41
   percent on Terminal-Bench. Clearing tool results sits on the frontier in
   both models; truncation and online clearing join it in the main model.
   Cost-at-parity is therefore not evidence for any particular method. The
   mechanism is prefill. Roughly half of policy settings do pay a detectable
   quality price at tight budgets, and the audit machinery is what tells the
   two groups apart.
3. **The model owns the quality axis.** Primitive rankings are reliable within
   a model and uncorrelated across models. The effect of clearing tool results
   reverses sign between models. Interaction tests on the log-odds scale with
   task-clustered inference.
4. **The survivor list, and how cross-model screening shrinks it.** Within the
   main model a short list of effects replicates. Partial summarization beats
   full summarization, and full-history summarization is the only primitive
   below full context after correction. Cross-model screening removes even
   these. Exactly one rule survives in both models — clearing tool results
   before summarizing helps.
5. **Reporting guidance.** Paired designs, split-half selection tests, noise
   nulls, censoring sensitivity, and the (model, policy) pair as the unit of
   evaluation.

## Paper skeleton

| § | Working title | Carries | Key exhibits |
|---|---|---|---|
| 1 | Introduction | phenomenon sentence, what survives vs what dissolves, contributions | — |
| 2 | The corpus | agent loop, 11 primitives + FC/OTRC at ∞, budgets 10/15/20k, depth grid, ABL-30 vs NEW-70, models, Terminal-Bench | Fig 1 design map; Table 1 corpus counts |
| 3 | What does not survive | audit mechanisms 3.1 selection-on-noise oracles, 3.2 task disagreement = noise, 3.3 cohort stratification flips signs, 3.4 inert depth knob, 3.5 asymmetric censoring | Fig 2 oracle vs null + honest split-half; Table 2 variance decomposition; Fig 3 cohort-flip forest; Table 3 censoring by family |
| 4 | What survives — cost | parity at fraction of cost on NEW-70 and Terminal-Bench, FC window failure, prefill mechanism | Fig 4 cost-at-parity + prefill share; cache-adjusted cost bound |
| 5 | What survives — the model owns quality | interaction LR, within/cross-model rank reliability, sign reversals, survivor screening incl. Devstral SU rows | Fig 5 rank scatter + reversal forest; Table 4 survivor screening |
| 6 | How to evaluate compression | the reporting protocol (contribution 5) | protocol box + power curve (runs vs detectable effect) |
| 7 | Related work | audit-lane precedents, compression method lane, positioning | — |
| 8 | Limitations | two informative models, ±7pp parity bounds, one agent loop, one repo family, capability scope, SU-full mechanism open | — |

Appendix — floor models, precision sweep, depth-grid detail, censoring
sensitivity, per-cell tables, prompt texts.

## Abstract (target prose)

Long-horizon coding agents compress their context to stay within a token
budget. Published comparisons of compression policies report which policy
resolves more tasks, which tasks favor which policy, and how aggressive the
compression should be. We audit these comparisons on about 19,000 SWE-bench
Verified trajectories from 33 policies on one fixed agent loop. Most of the
reported quality structure does not survive. Per-task policy selection gains
are reproduced by rollout noise. Cross-policy task disagreement is reproduced
by rollout noise. A common depth knob has no effect on the realized
compression of full-history summarizers. A task cohort stratified on outcomes
reverses the sign of a headline result. Two harness limits censor outcomes
unequally across policy families. After correction, primitive choice explains
about one percent of outcome variance within a model, and only a short list
of effects replicates. A real task-by-policy interaction of about four
points remains, and split-half tests show designs of this size cannot select
on it. The effect that transfers is cost. In every setting we test, some
training-free policy preserves full-context resolve rate, at 56 to 75
percent of the token cost on unselected tasks and 27 to 41 percent on
Terminal-Bench, though which policy does so depends on the model. The quality
effects that remain belong to the model. Primitive rankings are reliable
within a model and uncorrelated across two models, and the effect of clearing
tool results on its own reverses sign between them. One rule holds in both
models. Clearing tool results before summarizing helps. We conclude that
cost savings at parity should be treated as the default property of
compression rather than as evidence for a method, and that any quality claim
about a compression policy must name the model.

## Problem statement (target prose)

Evaluations of context compression for agents follow one pattern. A set of
policies is run on a set of tasks. Cell means are compared. Per-task
differences are read as structure. This pattern has three weaknesses. The
outcomes are binary and noisy. The task cohorts are small and are often
selected on outcomes. The harness imposes limits that interact with the
policy. Each weakness can produce a finding that is not there. We show that
each one did so in our own prior results. We then ask what remains. The
remaining effects are cost effects. The remaining quality effects vary with
the model.

## Models and data

- **Main model** Qwen3.5-35B-A3B, full grid, `Review1/Review1.csv` (12,533
  rows). Two cohorts. ABL-30 was stratified on FC and compression outcomes at
  selection and is not representative for compression-vs-FC contrasts. NEW-70
  is unselected. Headline resolve claims use NEW-70 or cohort-split forms only.
- **Devstral-Small-2-24B**, ABL-30 × {15k, 20k, 24k, ∞}, 60 runs per cell.
  Second informative model for all interaction tests. CAUTION — the 20k
  d=0.3/0.7 cells look like an infra batch anomaly (flagged 2026-08-26); use
  d=0.5 cells only until triaged. The FC@∞ + OTRC@∞ run on NEW-70 (~280
  runs, Albus) is REQUIRED for the headline (promoted from optional
  2026-08-26 after red-team) — it puts the clearing reversal and the parity
  frontier on the unselected cohort. Note ABL-30 was stratified on the main
  model's outcomes, so for Devstral it is misaligned selection rather than
  direct selection; state this in §2.
- **Floor models.** Qwen2.5-7B (0.2 percent resolve), Qwen2.5-Coder-32B (7 to
  12 percent, ranking reliability 0.07), Llama 3.3 70B (FC@∞ only, 3 percent).
  Reported as capability-floor observations. They cannot support or refute a
  policy contrast, and they stay out of abstract claim sentences.
- **Precision sweep**, Qwen3-30B-A3B-Instruct-2507 at fp16/fp8/gptq/awq on
  ABL-30. Precision main effect is real, policy × precision interaction is not
  detectable at this floor. Appendix.
- **Terminal-Bench**, 20 frozen tasks × {FC, TR, TRC, SS} × 3 runs, plus the
  32k/100k window contrast on 5 overflow tasks. Supporting exhibit for the
  cost result and for FC failure on long-horizon tasks. Not a ranking
  benchmark.

## Must-match numbers

| Claim | Number | Source |
|---|---|---|
| Oracle gain, same-run vs noise null | +21/+25pp vs +22.7pp [19.5, 26.0] | verify oracle-noise |
| Honest split-half selection gain | 15k −2.3pp, 10k −9.0pp, 20k −3.2pp, never significantly positive | verify oracle-noise |
| Task disagreement vs null | 68/100 observed vs 63.9 [60, 67] null; real structure ≤4–5 tasks | verify oracle-noise |
| Variance shares at 15k | task 52.3, primitive 1.0, noise 20.0 percent; genuine interaction ~4pp | verify noise-structure |
| Cell SE, task-clustered | ~4.4pp; Bonferroni-surviving pairwise orderings 7/6/2 of 55 per budget | verify noise-structure |
| Clearing effect at ∞ by cohort | ABL-30 +23.3pp; NEW-70 +2.1pp, CI [−5.2, +9.4] | verify cohort-fragility |
| TRC+SS@20k vs FC@∞ by cohort | ABL-30 +38.3pp; NEW-70 −2.1pp; interaction p<1e-4 | verify cohort-fragility |
| Cost at parity, NEW-70 | OTRC@∞ 55.7 percent of FC tokens (p=1e-9); TRC+SS@20k 71 percent | verify cost-lever |
| Parity frontier, Qwen NEW-70 | TRC@15k −2.1pp CI[−8.6,+4.3] at 60.8 percent; TRC@20k −2.1pp CI[−10.0,+5.7] at 72.2; TR@15k −4.3pp CI[−10.7,+2.1] at 68.4; OTRC@∞ +2.1pp CI[−5.0,+9.3] at 55.7 | addendum parity-frontier |
| Parity frontier, Devstral ABL-30 | TR@20k +0.0pp CI[−5.0,+5.0] at 73.6 percent; TRC@20k +3.3pp CI[−5.0,+11.7] at 74.9; TRC@15k −3.3pp CI[−13.3,+5.0] at 60.3 | addendum parity-frontier |
| Detectable deficits, Qwen NEW-70 | SU-full −13.6pp @15k and −14.3pp @20k, CIs exclude 0 (harm replicates on unselected cohort); OTRC+SU-partial −16.4pp @15k; CI-compatible-with-FC count 7/11 @15k, 6/11 @20k, all budgeted point estimates negative | addendum parity-frontier |
| Terminal-Bench | TR/TRC/SS 31/31/29 vs FC 28 of 60 at 27–41 percent cost; FC@100k 0/15 on overflow tasks, TR 5/15 | verify cost-lever |
| Prefill share | prompt tokens 96.8–98.9 percent of spend in every cell | verify cost-lever |
| Depth knob, realized slope | TR 0.954, TRC 0.986, partials ~0.49, SU-full −0.049, SS −0.035 | verify depth-knob-dead |
| Wall-clock censoring | 3,076/12,460 runs; SS-partial 39.4 vs TRC 9.2 percent; joint with step cap TR 42, SS 45.5, TRC 22.8, FC 27.5 percent | verify wallclock-censoring |
| Model × primitive interaction | LR=39.3, df=10, p=2.2e-05; clustered p=1.2e-03 | verify cross-model-transfer |
| Clearing effect log-odds | +0.95 Qwen vs −1.40 Devstral; interaction p=8.9e-06, clustered 3.6e-05 | verify cross-model-transfer |
| Ranking reliability vs transfer | within-model rho 0.82 / 0.76; cross-model rho 0.06 | verify cross-model-transfer |
| TR vs SU-partial reversal at 15k | Qwen +23.3pp (p=0.024); Devstral −20.0pp (p=0.012) | verify cross-model-transfer |
| SU-partial vs SU-full (Qwen) | +8.7pp, p=1.8e-5, both cohorts and runs | verify survivor-effects |
| SU-partial vs SU-full (Devstral) | +0.0pp @15k; −18.3pp @20k (d=0.5, ABL-30) — Qwen effect does not transfer | addendum sufull-cross-model |
| SU-full vs FC@∞ (Qwen) | only primitive significantly below FC after Bonferroni (p=0.0043, corrected 0.048); on Devstral SU-full is below FC but so are most primitives — non-distinctive | verify survivor-effects + addendum |
| TRC+SS vs SS | positive in both models, 4/4; Devstral recheck +23.3/+15.0/+15.0pp at 15/20/24k | verify cross-model-transfer + addendum |
| Truncation churn | TR +17.4 steps vs FC; 29.5 percent hit 125-step cap; cap runs resolve 0.47 percent | verify survivor-effects |

## Venue fit (checked 2026-08-26)

- The audit archetype is established and rewarded at ICLR. Shallow safety
  alignment (audit of common practice + mechanism) won an ICLR 2025
  Outstanding Paper Award. GSM-Symbolic (claims dissolve under instantiation
  variance) was accepted at ICLR 2025. Lost in Conversation (ICLR 2026) leads
  with an unreliability-vs-aptitude decomposition — the same epistemic move as
  our noise nulls and variance decomposition.
- Benchmarking/evaluation was the largest category at ICLR 2026 (71 papers),
  with critical analysis of evaluation methods explicitly valued.
- ACON (closest method-lane ICLR 2026 submission) reports single-point
  figures with no error bars, no repeated runs, no significance tests, and
  magnitude-only model effects. Cite respectfully as the current-practice
  exhibit for contribution 1. Its results do not claim sign reversals — both
  our headlines stay unclaimed.
- Known reception risk — this shape reliably gets in but lands as a poster
  unless the constructive core leads. Lead with what survives.
- Practitioner pre-empt for §2 — TRC (clear old tool results) is the closest
  primitive to deployed compaction defaults, and the one transferable rule
  matches converged practice. The harness caps are not incidental — every
  deployment caps something, and the finding is that caps interact with
  policy family.
- Positioning pre-empt for §7 — single-method cost-at-parity reports (ACON,
  CoACT, the LLMLingua lineage) are consistent with our result and subsumed
  by it. We show parity across 33 policy settings including trivial ones, so
  cost-at-parity cannot differentiate methods, and differentiation claims
  require the machinery of §6.

## Reservations (pre-submission checklist)

1. Negative-result reception. Name the phenomenon in one sentence at the top
   of the introduction. Lead with what survives, then with what did not.
2. Power of the nulls. NEW-70 resolve deltas carry a CI of about ±7pp and
   Terminal-Bench contrasts are null at 20 tasks. State every null as a
   parity bound with its CI, never as absence of an effect.
3. Two informative models only. The Devstral NEW-70 run is now REQUIRED
   (see models and data). A third capable model only if GPUs return before
   Sept 25.
4. ABL-30 provenance. Document the selection procedure exactly and show FC
   and compression outcomes by cohort. The cohort split is itself an exhibit.
5. Censoring sensitivity. Build the two-ceiling analysis (1500s wall clock,
   125 steps) for every resolve comparison. Never report a ranking
   conditional on finishing.
6. Multiple comparisons. The audit is estimation, not testing. Pre-register
   the few headline contrasts and report Bonferroni-surviving orderings only.
7. Depth report cleanup. Pool SU-full and SS depth cells as replicates.
   Re-run or exclude the 61 zero-step OTRC-stack d=0.7 slots. Correct the
   invalidated rows in `Review1/depth_analysis_report.md`.
8. Scoop status. ACON checked 2026-08-26 — favorable (see venue fit). A
   search found no paper doing noise-corrected agent evaluation (harness
   variance of 10–20pp is documented, the correction machinery is unowned).
   Re-sweep arXiv for both headlines in the week before submission.
9. Recompute every count (33 policies, ~19,000 trajectories) from the frozen
   analysis manifest before the abstract.
10. Devstral 20k tail-depth anomaly. Triage exit_status/step_count in the 20k
    d=0.3/0.7 cells before any Devstral tail-depth number is used anywhere.
11. Wording decisions resolved 2026-08-26. Abstract claim sentences say "two
    models"; floor models stay in the body. "33 policies" stays out of the
    one-line claim and appears in the abstract as a scale number, gated on
    reservation 9.
12. Cost unit. Raw tokens is the measured unit and assumes no prefix cache —
    our self-hosted regime. Report the cache-adjusted bound (queued analysis
    1) and state the conditions under which the cost lever holds. Cite the
    Copilot-traces −66 percent cache-hit result and TokenPilot.
13. Capability confound. Re-test the model × primitive interaction with Qwen
    subsampled to Devstral's n (60 runs per cell, ABL-30) so the reversal is
    not an artifact of unequal precision. Add a frontier-capability scope
    sentence to §8 (our models resolve ~40–70 percent).
14. Genericity discipline. Never claim every policy reaches parity. The
    claim is a cheap parity frontier in both models; roughly half of
    settings show detectable deficits at tight budgets. That duality —
    detectable harms, unresolvable rankings — closes §5.
15. SU-full mechanism is explicitly out of scope. One sentence in §8. No
    gesturing at retired investigations.
16. ABL-30-for-Devstral is misaligned selection (stratified on the main
    model's outcomes). Document in §2 alongside reservation 4.

## Queued analyses (data in hand, not yet run)

1. **Cache-adjusted cost bound.** From `step_prompt_tokens` +
   `compression_event_steps` (both already in experiment_results.json).
   Unit — prefill tokens that must be recomputed under an ideal prefix
   cache, each compression event invalidating the prefix. Optional dollar
   weighting as sensitivity. Fills the §4 exhibit. ~1 day.
2. **Closed-form selection null.** Pull the exact oracle operator from the
   F3 audit script, derive the expected best-of-K gain analytically, show it
   matches the simulated +22.7pp band. Small.
3. **Power curve for §6.** Runs per task required to resolve 3/5/8pp policy
   effects at observed noise. Analytic. Small.
4. **Capability-confound subsample** (reservation 13). Small.
5. **Two-ceiling sensitivity applied to the parity-frontier rows**
   (reservation 5 on the new table). Small.
6. **NEW-70 parity-bound paper table** — per primitive × budget, paired Δ,
   CI, cost ratio (computed 2026-08-26, addendum parity-frontier; needs
   table styling only).

## Writing rules (standing, from Ritul)

- No colons in paper prose. Restructure with periods, em-dashes, or
  conjunctions.
- No short punchy paragraph openers. Fuller measured sentences.
- Very simple short sentences. One sentence does one job.
- Lead with the behavioral observation, then the metric ("redundant
  exploration rate", never `frac_near_rerun`).
- Every number in prose must appear in the must-match table.
- Any quality claim names the model.
- Say "33 policy settings (11 primitives across budgets and depths)" on
  first use. Never "33 policies".

## Banned framings (standing)

Routing / per-task selection, cascade, temporal mixing / staggered,
silent→visible failure reshaping, recovery / fault / working-set framing, KV
free deletion. Coherence and progress-state are retired directions in the
attic, not sections of this paper.
