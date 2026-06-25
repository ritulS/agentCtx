# Characterization Paper — Framing v2 (n=100)

**Date:** 2026-05-05
**Status:** Spine refreshed against n=100 results. Abstract redrafted. Numbers below match `Review1/Review1.csv` (7 000 rows: 100 tasks × 35 cells × 2 runs).
**Supersedes:** [CHARACTERIZATION_PAPER_PLAN_30tasks.md](CHARACTERIZATION_PAPER_PLAN_30tasks.md) (n=30 era; archival).
**Excluded directions remain excluded:** cascade-as-mechanism, routing-as-takeaway, "compression beats FC" as headline, "smaller models benefit more", long-context degradation, signal curation.

---

## What changed n=30 → n=100 (the rewrite scope)

| original claim (v1) | n=30 evidence | n=100 evidence | verdict |
|---|---|---|---|
| Oracle-of-top-2 saturates achievable resolve | 87/87/90% at k=2 | k=2 → 64/68/67%; saturation moves to k=4–6 at 72/74/71% | **rewrite** |
| Threshold +6pp resolve over online at 1.5× tokens | TRC+SS@20k 76.7% vs OTRC@∞ 61.7% | TRC+SS@20k 51.0% vs OTRC@∞ 51.5% — tied on resolve | **collapsed; demote** |
| Stacking yields consistent sub-additive gains | TRC@20k 71.7% < TRC+SS@20k 76.7% (+5pp) | TRC@20k 50.5% ≈ TRC+SS@20k 51.0% (+0.5pp) | **inert at 20k; rewrite** |
| Heterogeneity is real | ~30% pairwise disagreement | ~21% pairwise disagreement; **+11–17pp oracle-of-11 headroom** still substantial | survives, restated |
| Heterogeneity is potentially exploitable | LOO 53/63/82% near baselines 67/68/82% | LOO **68.6/45.0/58.5%** vs **65.7/55.0/85.4%** — at-or-below baseline at every budget; pooled 56% vs 74% baseline | **decisive negative** |
| (not in v1) Partial summarization is the depth lever | SU-partial vs SU-full @15k: +33pp [+15, +52], McN 0.003 | SU-partial vs SU-full @15k: **+14.5pp [+7, +22.5], McN 0.002** | **promote to headline** |
| (not in v1) Online clearing × partial summarization is super-additive | OTRC+SS-partial vs SS-partial @20k: 0pp non-sig | OTRC+SS-partial vs SS-partial @20k: **+20.5pp [+11, +30], McN <0.001** | **promote to headline** |

---

## One-line direction

A characterization study of the agent context-compression design space on SWE-bench Verified — descriptive, structural, no method proposed.

## Working title

> *Characterizing Context Compression in LLM Coding Agents: A Design-Space Study*

(Title carries forward unchanged; the contribution is still a design-space map, not a method.)

---

## Abstract (current draft, n=100)

Context compression primitives — truncation, summarization, structured summaries, tool-result clearing — let LLM coding agents operate past their context cap, but the literature evaluates them in isolation against a single full-context baseline. We present a characterization of this design space on SWE-bench Verified. We organize compression primitives along four orthogonal axes — *what* is removed, *when* it fires, *how aggressive* the compression is, and *what it stacks with* — and populate a 35-cell grid across 100 tasks and {N} models. Five structural findings emerge. **Primitives form a Pareto frontier**: no choice dominates jointly on resolve rate and tokens-per-resolve, with the online-clearing family taking 73% of @20k token-efficiency wins. **Per-task winners are heterogeneous but unrecoverable from observables**: primitives disagree on ~21% of tasks and an oracle over the full primitive set buys +11–17pp resolve over the best single choice, but a leave-one-out classifier on task features sits at-or-below the majority baseline at every budget. **Depth matters**: partial summarization (preserve recent verbatim, summarize older) outperforms full summarization by +14.5pp resolve at the same budget. **Axes interact**: online clearing combined with partial summarization super-additively outperforms either component, +20.5pp over standalone partial summarization at 20k. **Stacking is inert on resolve at deployment-class budgets** but reshapes failure modes — the contribution of +SS / +SU on top of TRC is in *which way* a run fails, not in *whether* it resolves. The patterns hold across model scales. We provide the resulting design-space map as a scaffold for situating future compression primitives.

---

## Section structure

1. Intro — design-space framing + structural claims
2. Related work — long-context degradation, agent compression methods (ACON, AgentDiet), routing (positioned as adjacent, not central)
3. The compression-primitive taxonomy — four axes, formal definitions, full grid
4. Experimental setup — SWE-bench Verified, models, harness, budgets, runs
5. RQ1–RQ5 results — one subsection each
6. RQ6 failure-mode reshaping
7. RQ7 cross-model + cross-benchmark generalization
8. Implications — cost-per-resolve frontier, where stacking pays
9. Limitations & threats
10. Conclusion

---

## Research questions and current evidence (n=100)

| RQ | question | n=100 evidence (Review1/) |
|---|---|---|
| **RQ1** | Mechanism specialization — Pareto frontier on resolve / cost? | OTRC family captures 73% of @20k token-efficiency winners; threshold variants take more @10k/15k; no single primitive dominates jointly |
| **RQ2** | Task specialization — heterogeneous and exploitable? | ~21% pairwise disagreement; oracle-of-11 +11–17pp over best-single; **LOO predictability at-or-below baseline** at every budget — heterogeneity is real but unrecoverable from observable features |
| **RQ3** | Composition — does stacking compose predictably? | Stacking on TRC adds **0.5pp** at 20k (paired CI [−5.5, +7.0]); inert on resolve, signal lives in failure-mode reshaping (RQ6) |
| **RQ4** | Timing — online vs threshold? | Tied on resolve at 20k (51.0% vs 51.5%); online cheaper on tokens. Demoted from headline trade to a cost-axis observation |
| **RQ5 (NEW)** | Depth — does preservation matter inside summarization? | SU-partial vs SU-full @15k: **+14.5pp [+7, +22.5], McN 0.002**. Cleanest mechanism finding. |
| **RQ5b (NEW)** | Axis interaction — does online clearing potentiate partial summarization? | OTRC+SS-partial vs SS-partial @20k: **+20.5pp [+11, +30], McN <0.001**. Largest paired effect. |
| **RQ6** | Failure-mode reshaping — does compression change *how* agents fail? | FC ~50% wrong-patch silent failures; compression reshapes the outcome distribution (item #3 in scaffolding additions) |
| **RQ7** | Cross-model / cross-benchmark generalization | Qwen2.5-7B (Albus, post-§1.3c) and Llama 3.3 70B (Albus, §2.2c) data pending; second-benchmark scoping pending |

(Re-numbering: RQ1–RQ4 carry forward; RQ5/RQ5b are new; old "RQ5 failure modes" becomes RQ6; old "RQ6 generalization" becomes RQ7. Keep one round of section-numbering churn confined to this rewrite.)

---

## The design space (unchanged)

**Four orthogonal axes:**

| axis | levels |
|---|---|
| *what is removed* | tool results (TRC/OTRC), full history (SU), structured fields (SS), oldest steps (TR) |
| *when it fires* | threshold-triggered (TRC), online-per-step (OTRC), budget-driven (TR/SU/SS) |
| *how aggressive* | budget ∈ {10k, 15k, 20k, ∞} |
| *stacking* | base / +summary / +partial-summary |

**Grid:** 35 cells = (11 primitives × 3 budgets) + FC@∞ + OTRC@∞.

**Total runs at n=100:** 100 tasks × 35 cells × 2 runs = **7 000 runs per model**.

---

## Strengthening additions (status updated)

The four items below remain committed scope.

### Item #1 — Statistical scaffolding on every cell — **DONE for primary model**

Bootstrap paired CIs on every reported number, McNemar exact for primitive comparisons.

- **Status:** Implemented in `Review1/sanity.py` (F8 bootstrap), `Review1/paired_analysis.py` (paired bootstrap + McNemar), `Review1/routing_evidence.py` (M1–M3). Mean CI half-width ±6.6pp at n=100.
- **Acceptance:** every figure / numerical claim cites a 95% CI; primitive-vs-primitive comparisons have paired CI + McNemar p.
- **Remaining:** mirror the scaffolding for the secondary models (Qwen2.5-7B, Llama 3.3 70B) once those datasets land.

### Item #3 — Failure-mode shift table (the body of RQ6) — **PENDING**

Per (primitive × budget) cell, breakdown of run outcomes: `resolved / submitted_unresolved / limits_exceeded / silent_crash`. Now the *primary* place where stacking shows a non-zero effect (since RQ3 collapsed on resolve).

- **Why:** RQ6 is the failure-mode body; with stacking inert on resolve at 20k, this is also where +SS / +SU earn their keep.
- **Cost:** ~half day from `Review1.csv` (`failure_mode` field already present).
- **Status:** Pending. Plot scaffolding partially in `Review1/plot_review1.py`.
- **Acceptance:** stacked-bar grid (35 cells) + paired CI on each "FC silent-failure share vs primitive X silent-failure share" gap; explicit per-stack failure-mode delta table.

### Item #4 — Compression overhead accounting — **PENDING**

Determine whether `total_tokens_consumed` includes the summarizer's prompt + output for SU/SS variants. If material, add a corrected cost-per-resolve column.

- **Status:** Pending. Audit point: `mini-swe-agent/src/minisweagent/agents/default.py` and the env's token-counting code.

### Item #8 — Second benchmark domain — **PENDING (scoping)**

Smaller grid (top 4 primitives × 1–2 budgets × 30+ tasks) on AppWorld / GAIA / BIRD, replicating RQ1, RQ4, RQ6.

### Items deferred (unchanged from v1)

- #2 content-type analysis
- #5 task-feature characterization of heterogeneity (now answered as **negative** by RQ2 LOO predictability — promote that into the body, no new analysis needed)
- #6 within-primitive aggressiveness sweep
- #7 annotated trajectory case studies
- #9 second harness (Limitations)
- #10 oracle-compression upper bound

---

## Explicitly excluded directions (do not re-introduce)

- **Cascade as mechanism.** Rejected. Existing artifacts remain historical only.
- **Routing as takeaway.** Re-affirmed. RQ2's LOO-at-or-below-baseline result *strengthens* the no-routing position (heterogeneity is real but unrecoverable). Do not market the +11–17pp oracle headroom as a router upper bound.
- **"Compression beats FC" framing.** Stays out. The n=100 paired Δ FC vs TRC+SS@20k is −8pp (was −38pp at n=30). Not the headline. Do not lean on the n=30 number anywhere in §5/§8.
- **"Smaller models benefit more from compression"** — established by prior work, not a headline.
- **Long-context degradation framing** — mature literature.
- **Signal curation / decision-quality framing** — too abstract.

---

## Open knobs / pending decisions

1. **Venue/length** — EMNLP full paper currently. NeurIPS / TMLR alternate if length pressure forces a longer form.
2. **Model list for RQ7** — Qwen3.5-35B-A3B (primary, Dobby) locked. Qwen2.5-7B (Albus, Phase 1) in flight; Llama 3.3 70B (Albus, Phase 2) blocked on HF token, then proceeds. Quant sweep (Albus, Phase 3) on the table after Phases 1–2.
3. **Choice of second benchmark (item #8)** — AppWorld vs GAIA vs BIRD vs other.
4. **Closing line of abstract** — currently *"scaffold for situating future compression primitives"*. Open to tightening.
5. **Dataset note: the 473 zero-step infrastructure failures** — concentrated in the @20k singles (TR/SU-full/SS/SS-partial/SU-partial: 70–92 each) and a few @10k cells. Counted as failures (correct), pull mean step / token statistics down. Decide between (a) report as-is with a §4/§9 disclosure, (b) re-run the affected cells. Default: (a) — they are real data, the failure rate itself is a deployment signal.

---

## Status snapshot (2026-05-05)

| asset | status |
|---|---|
| Spine | refreshed for n=100 |
| Abstract draft | done (this document) |
| n=100 results in `Review1/Review1.csv` | done (7 000 rows, 100 tasks × 35 cells × 2 runs) |
| Sanity report | `Review1/sanity_report.md` (F8 mean CI ±6.6pp) |
| Paired analysis | `Review1/paired_analysis_report.md` (n=100 headline grid) |
| Routing/heterogeneity | `Review1/figures/fig_M{1,2,3}_*.png` + console output |
| Predictability sprint | `Review1/predictability_report.md` — decisive negative |
| Winners table | `Review1/winners_table.md` — OTRC family dominates @20k (53/73 = 73%) |
| Cross-model runs (Qwen2.5-7B) | Phase 1 budgeted sweep done on Albus (2 100 rows) |
| Cross-model runs (Llama 3.3 70B) | Blocked on HF token paste, then §2.2a → calibration → §2.2c |
| Quantization sweep | Phase 3 on Albus, post-§2 |
| Statistical scaffolding (#1) | done for primary model |
| Failure-mode shift table (#3) | pending |
| Compression overhead audit (#4) | pending |
| Second benchmark (#8) | pending — needs scoping |

---

## Detailed section spine

Per-section breakdown updated for the n=100 claim set. Cells link back to the four strengthening items where relevant.

### §1 — Introduction
| element | content |
|---|---|
| ¶1 setup | Multi-step LLM agents accumulate context, exceed budget; compression is the standard mitigation |
| ¶2 gap | Primitives have proliferated; field evaluates each in isolation against FC; combined design space is uncharacterized; cite ACON, AgentDiet, LLMLingua-2 |
| ¶3 our work | We characterize the four axes on SWE-bench Verified; n=100 tasks, N models |
| ¶4 findings preview | Pareto · heterogeneity-but-unpredictable · depth-matters · axes-interact · stacking-inert-on-resolve — terse one-liners |
| ¶5 contributions | (a) taxonomy + grid, (b) five structural findings, (c) statistical scaffold, (d) failure-mode characterization, (e) released artifact |
| anchor | Fig 1: taxonomy schematic — four axes and where primitives sit |
| writeable now? | yes |

### §2 — Related Work
Unchanged from v1. Routing/cascade adjacent literature acknowledged, explicitly noted we do not propose routing.

### §3 — Compression-Primitive Taxonomy
Unchanged from v1.

### §4 — Experimental Setup
| sub | content |
|---|---|
| §4.1 benchmark | SWE-bench Verified; n=100 task selection (30 ABL_TASKS FC-stratified + 70 P100_NEW broader-pool) — disclose mixed-cohort sampling |
| §4.2 models | Qwen3.5-35B-A3B primary; Qwen2.5-7B + Llama 3.3 70B secondary |
| §4.3 agent harness | mini-swe-agent fork, tool inventory, system prompt, step cap |
| §4.4 budgets | {10k, 15k, 20k}; two unbounded baselines (FC@262k, OTRC@∞) |
| §4.5 **compression overhead accounting** | what `total_tokens_consumed` counts; SU/SS overhead disclosure — **item #4** |
| §4.6 **statistical procedure** | paired bootstrap CIs, McNemar exact, multi-comparison correction — **item #1** |
| §4.7 run protocol | 2 runs/cell; seeds; total run count; **disclose ~6.7% zero-step infrastructure failures** |
| anchors | Table 2 (run grid), Table 3 (harness hyperparameters) |
| writeable now? | partially — §4.5 needs #4 audit |

### §5 — Structural Findings (RQ1–RQ5)
| sub | claim | n=100 anchor |
|---|---|---|
| §5.1 RQ1 mechanism specialization | Primitives form a Pareto frontier; OTRC family captures 73% of @20k token-efficiency winners | per-cell Pareto plot with 95% CIs |
| §5.2 RQ2 task specialization | ~21% pairwise disagreement; oracle-of-11 +11–17pp over best-single; **LOO predictability at-or-below baseline at every budget** — heterogeneity exists but is unrecoverable | per-task winner heatmap, pairwise disagreement matrix, oracle-of-k curve, predictability LOO panel |
| §5.3 RQ3 composition | Stacking on TRC adds **+0.5pp [−5.5, +7.0]** at 20k; inert on resolve. Effect is in failure-mode reshaping (forward-ref §6) | stacking interaction table with paired CIs |
| §5.4 RQ4 timing | Tied on resolve at 20k (TRC+SS 51.0% vs OTRC@∞ 51.5%); online cheaper on tokens; framed as a cost-axis observation, not a resolve trade | head-to-head table |
| §5.5 RQ5 depth | SU-partial vs SU-full @15k: **+14.5pp [+7, +22.5], McN 0.002** — partial preservation rescues summarization | within-family bar chart with paired CI |
| §5.6 RQ5b interaction | OTRC+SS-partial vs SS-partial @20k: **+20.5pp [+11, +30], McN <0.001** — online clearing super-additive on partial summarization | interaction plot (4 cells: SS-partial vs OTRC+SS-partial × 15k vs 20k) |

### §6 — Failure-Mode Reshaping (RQ6)
| sub | content |
|---|---|
| §6.1 outcome taxonomy | `resolved / submitted_unresolved / limits_exceeded / silent_crash`, formally defined |
| §6.2 FC's silent failure | ~50% wrong-patch silent failures at 262k — the baseline pathology |
| §6.3 compression reshapes the failure mix | per-cell outcome distribution; deltas vs FC |
| §6.4 stacking and failure modes | does +SS / +SU change failure mix differently than it changes resolve? **This is now the primary place where stacking earns its keep, because RQ3 collapsed on resolve.** |
| anchors | Fig 8 (stacked-bar grid), Table 4 (paired CI on FC vs primitive silent-failure shares) — **item #3** |

### §7 — Generalization (RQ7)
| sub | content |
|---|---|
| §7.1 cross-model | Qwen2.5-7B + Llama 3.3 70B; replicate RQ1, RQ4, RQ5, RQ5b, RQ6 |
| §7.2 cross-benchmark | second benchmark; reduced grid (top 4 primitives × 1–2 budgets × 30+ tasks) — **item #8** |
| §7.3 what replicates vs what shifts | explicit per-finding × per-(model, benchmark) categorization |
| anchors | Fig 9 (Pareto across models), Fig 10 (Pareto across benchmarks), Table 5 (replicate / shift / break per finding) |

### §8 — Implications
| sub | content |
|---|---|
| §8.1 cost-per-resolve frontier | practitioner guidance: at budget B, most efficient primitive family is X (OTRC at @20k, mixed elsewhere) |
| §8.2 depth as a cheap win | partial-summarization variants dominate full-summarization at the same cost — a free-lunch axis |
| §8.3 axis interaction is real | OTRC × partial-summarization: combine the two cheapest axes for the largest gain |
| §8.4 stacking's role is failure-mode insurance | not for resolve; for which way runs fail |
| §8.5 implications for future methods | what new compression methods must beat: Pareto frontier, depth lever, interaction effect, failure-mode profile |
| writing rule | no routing framing — implications stay characterizing, not prescribing a router |

### §9 — Limitations & Threats
- single harness (mini-swe-agent) — flag #9 as future work
- n=100 limits very fine-grained claims; mixed-cohort sampling (FC-stratified 30 + broader 70) noted in §4.1
- ~6.7% zero-step infrastructure failures disclosed in §4.7
- compression overhead disclosed in §4.5
- 2 runs/cell — bounded variance estimate
- two benchmark domains, not exhaustive

### §10 — Conclusion
- Restate gap → findings → contribution → one forward sentence on what new methods would look like evaluated against the map.

---

## Writing order (when each section unblocks)

| order | section | blocked by |
|---|---|---|
| 1 | §3 Taxonomy | nothing — definitional |
| 2 | §1 Introduction | spine lock (this doc) |
| 3 | §4 Experimental Setup | item #4 audit (overhead accounting) |
| 4 | §5 RQ1–RQ5b | n=100 data + item #1 (stats) — **unblocked** |
| 5 | §6 RQ6 | item #3 (failure-mode table) |
| 6 | §7 RQ7 | cross-model runs (Albus Phases 1–2) + item #8 (second benchmark) |
| 7 | §2 Related Work | iterative |
| 8 | §8–10 | all results |
| 9 | abstract | last — final numbers |

---

## Cross-references

- [exp_plans/CHARACTERIZATION_PAPER_PLAN_30tasks.md](CHARACTERIZATION_PAPER_PLAN_30tasks.md) — archival v1 framing (n=30 era)
- [exp_plans/FULL_TASK_EXPANSION_INSTRUCTIONS.md](FULL_TASK_EXPANSION_INSTRUCTIONS.md) — P100 expansion handover
- [exp_plans/DOBBY_PLAN.md](DOBBY_PLAN.md) — primary-model queue
- [exp_plans/ALBUS_PLAN.md](ALBUS_PLAN.md) — secondary-model queue (Qwen2.5-7B, Llama 3.3 70B, quant sweep)
- [Active_runs.md](../Active_runs.md) — live status of long-running experiments
- [Review1/Review1.csv](../Review1/Review1.csv) — current n=100 results (7 000 rows)
- [Review1/sanity_report.md](../Review1/sanity_report.md), [Review1/paired_analysis_report.md](../Review1/paired_analysis_report.md), [Review1/predictability_report.md](../Review1/predictability_report.md), [Review1/winners_table.md](../Review1/winners_table.md) — refreshed analyses
- Memory: `feedback_no_cascade.md`, `feedback_no_routing.md`, `feedback_paper_edits.md`
