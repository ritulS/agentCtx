# Characterization Paper — Framing v1 (n=30 era — archival)

**Date:** 2026-05-01
**Status:** ARCHIVED. This is the n=30-era framing kept for reference. Several
structural claims here (oracle-of-2 saturation; threshold +6pp resolve over
online at 1.5× tokens; stacking sub-additive-but-positive; LOO-near-baseline
predictability) shifted at n=100. The current paper framing lives in
[CHARACTERIZATION_PAPER_PLAN_100tasks.md](CHARACTERIZATION_PAPER_PLAN_100tasks.md).
**Supersedes:** prior framings (long-context, signal-curation, compression-beats-FC, smaller-models-benefit-more, routing-as-takeaway, cascade-as-mechanism — all rejected).
**Superseded by:** [CHARACTERIZATION_PAPER_PLAN_100tasks.md](CHARACTERIZATION_PAPER_PLAN_100tasks.md) (2026-05-05).

---

## One-line direction

A characterization study of the agent context-compression design space on SWE-bench Verified — descriptive, structural, no method proposed.

## Working title

> *Characterizing Context Compression in LLM Coding Agents: A Design-Space Study*

---

## Abstract (current draft)

Context compression primitives — truncation, summarization, structured summaries, tool-result clearing — let LLM coding agents operate past their context cap, but the literature evaluates them in isolation and against a single full-context baseline. We present a characterization of this design space on SWE-bench Verified. We organize compression primitives along four orthogonal axes — *what* is removed, *when* it fires, *how aggressive* the compression is, and *what it stacks with* — and populate a 35-cell grid across 100 tasks and {N} models. Four structural findings emerge. **Primitives form a Pareto frontier**: no choice dominates jointly on resolve rate and tokens-per-resolve. **Per-task winners are heterogeneous**: primitives disagree on ~30% of tasks, and combining the top two substantially exceeds the resolve rate of any single primitive. **Timing is a clean lever**: threshold-triggered clearing buys ~6 pp resolve over online clearing at 1.5× the tokens, monotone in budget and consistent across all stack variants. **Stacking is sub-additive and reshapes failure modes** more than it shifts headline resolve. The patterns hold across model scales. We provide the resulting design-space map as a scaffold for situating future compression primitives.

---

## Section structure

1. Intro — design-space framing + structural claims
2. Related work — long-context degradation, agent compression methods (ACON, AgentDiet), routing (positioned as adjacent, not central)
3. The compression-primitive taxonomy — four axes, formal definitions, full grid
4. Experimental setup — SWE-bench Verified, models, harness, budgets, runs
5. RQ1–RQ4 results — one subsection each
6. RQ5 failure-mode reshaping
7. RQ6 cross-model + cross-benchmark generalization
8. Implications — cost-per-resolve frontier, where stacking pays
9. Limitations & threats
10. Conclusion

---

## Research questions and current evidence

| RQ | question | current evidence (n=30) | n=100 status |
|---|---|---|---|
| **RQ1** | Mechanism specialization — do primitives separate cleanly along resolve / cost axes? | Clean Pareto; online vs threshold dominant axis | Will sharpen |
| **RQ2** | Task specialization — is the per-task winner heterogeneous? | ~30% pairwise disagreement; top-2 oracle saturates achievable resolve | Per-class samples become decisive |
| **RQ3** | Composition — does stacking compose predictably? | Consistent gains; sub-additive | Needs paired CIs |
| **RQ4** | Timing — how does online vs threshold reshape the trade? | Threshold +6 pp resolve at 1.5× tokens; monotone across budgets and all three stack variants | Direct re-statement |
| **RQ5** | Failure-mode reshaping — does compression change *how* agents fail? | FC has ~50% wrong-patch silent failures; rest TBD | Needs the failure-mode shift table (item #3) |
| **RQ6** | Cross-model / cross-benchmark generalization | Only Qwen3.5-35B-A3B on SWE-bench Verified | Need 1–2 more models + a second benchmark (item #8) |

---

## The design space

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

## Strengthening additions (folded in 2026-05-01)

The four items below are committed scope on top of the spine and the RQ list.

### Item #1 — Statistical scaffolding on every cell

Bootstrap paired confidence intervals on every reported number: resolve rate, mean tokens, cost-per-resolve, family aggregates, head-to-head trades. McNemar's exact test for paired primitive comparisons on shared tasks. Apply to every figure and every claim in the body.

- **Why:** Reviewers will dock a characterization paper for unanchored point estimates. Standard for this venue and topic.
- **Cost:** ~1 day post-processing.
- **Status:** Pending. Can prototype on n=30 first; refresh at n=100.
- **Acceptance criterion:** every figure and every numerical claim in the abstract / body cites a 95% CI; primitive-vs-primitive comparisons have a p-value or BCa interval.

### Item #3 — Failure-mode shift table (the body of RQ5)

Per (primitive × budget) cell, breakdown of run outcomes: `resolved / submitted_unresolved / limits_exceeded / silent_crash`. Headline finding: FC's ~50% wrong-patch silent-failure share. Show how compression primitives reshape this distribution, not just the resolve count. Faceted figure: stacked bars per cell.

- **Why:** RQ5 is currently a stub in the spine. This is its substance.
- **Cost:** ~half day from existing CSV (`Review1.csv` already has `outcome` field).
- **Status:** Pending. Can compute on n=30 immediately.
- **Acceptance criterion:** one stacked-bar grid figure (35 cells); a paired CI on each "FC silent-failure share vs primitive X silent-failure share" gap.

### Item #4 — Compression overhead accounting

Determine and disclose whether `total_tokens_consumed` includes the summarizer's prompt + output for SU/SS variants. If not, measure it separately and present a disclosed-vs-undisclosed comparison. Critical for fair cost-per-resolve claims since SU/SS call the LLM to compress and TR/TRC don't.

- **Why:** Reviewers will ask. If overhead is large, our cost-per-resolve numbers shift; if small, we say so up front.
- **Cost:** ~few hours of code spelunking in `mini-swe-agent` env + sanity-check run.
- **Status:** Pending. Audit in [mini-swe-agent/src/minisweagent/agents/default.py](mini-swe-agent/src/minisweagent/agents/default.py) and the env's token-counting code is the starting point.
- **Acceptance criterion:** explicit statement in §4 (Experimental setup) of what is and is not counted; if material, a corrected cost-per-resolve column added to all efficiency tables.

### Item #8 — Second benchmark domain

Add one additional benchmark to characterize across task domains, not just SWE-bench coding. Candidate: AppWorld (tool-heavy multi-step), GAIA (multi-step web), BIRD (SQL). Goal: a smaller grid (top 4 primitives × 1–2 budgets × 30+ tasks) showing the structural findings transfer.

- **Why:** Biggest single reviewer concern for a characterization paper is workload generalization. Without this, the paper is "characterization in coding"; with it, "characterization across agentic tasks."
- **Cost:** Significant — harness porting, tool definitions, eval pipeline. 1–2 weeks of engineering.
- **Status:** Needs scoping. Choice depends on what works with the existing Qwen3.5-35B-A3B + mini-swe-agent stack.
- **Acceptance criterion:** at least RQ1 (Pareto), RQ4 (online-vs-threshold trade), and RQ5 (failure-mode shift) re-stated on the second benchmark with paired CIs. RQ2 / RQ3 nice-to-have but not required.

### Items deferred

- **#2 content-type analysis** (what each primitive actually removes) — not in scope this round, may revisit if reviewers push on RQ1's mechanism story.
- **#5 task-feature characterization of heterogeneity** — not in scope; depends on RQ2 reception.
- **#6 within-primitive aggressiveness sweep** — deferred.
- **#7 annotated trajectory case studies** — deferred.
- **#9 second harness** — out of scope this round; flagged in Limitations.
- **#10 oracle-compression upper bound** — deferred; flagged as future work.

---

## Explicitly excluded directions (do not re-introduce)

- **Cascade as mechanism.** Rejected 2026-05-01. The rework metric is a dead end as a paper backbone. Existing artifacts (`scripts/canonical_rework.py`, `figures/cascade_*.png`, `rework_metric_design.md`) remain as historical work only.
- **Routing as takeaway.** Rejected 2026-05-01. Per-task heterogeneity stays as a fact (RQ2); do not market it as a router upper bound or motivation. No "routed portfolio" framing, no "task-conditional selection".
- **"Compression beats FC" framing** — established / scooped, not a headline.
- **"Smaller models benefit more from compression" framing** — established by prior work, not a headline.
- **Long-context degradation framing** — mature literature; we are not contributing there.
- **Signal-curation / decision-quality framing** — too abstract, rejected.

---

## Open knobs / pending decisions

1. **Venue/length** — EMNLP full paper currently. (NeurIPS / TMLR alternate if length pressure forces a longer form.)
2. **Model list for RQ6** — Qwen3.5-35B-A3B locked. Llama 3.3-70B + one more was the rough plan; needs confirmation.
3. **Choice of second benchmark (item #8)** — AppWorld vs GAIA vs BIRD vs other.
4. **Closing line of abstract** — currently *"scaffold for situating future compression primitives"*. Open to tightening if a punchier alternative arrives.

---

## Status snapshot (2026-05-01)

| asset | status |
|---|---|
| Spine | locked |
| Abstract draft | done (this document) |
| n=30 results in `Review1.csv` | done (2 100 runs) |
| n=100 expansion | in flight (~3 days wall-clock; details in `exp_plans/FULL_TASK_EXPANSION_INSTRUCTIONS.md`; live status in `Active_runs.md`) |
| Cross-model runs | not yet collected |
| Statistical scaffolding (#1) | pending |
| Failure-mode shift table (#3) | pending |
| Compression overhead audit (#4) | pending |
| Second benchmark (#8) | pending — needs scoping |

---

---

## Detailed section spine

Per-section breakdown: contents, anchoring figure/table, data dependencies, writeable-now status. Cells link back to the four strengthening items where relevant.

### §1 — Introduction
| element | content |
|---|---|
| ¶1 setup | Multi-step LLM agents accumulate context, exceed budget; compression is the standard mitigation |
| ¶2 gap | Primitives have proliferated; field evaluates each in isolation against FC; combined design space is uncharacterized; cite ACON, AgentDiet, LLMLingua-2 |
| ¶3 our work | We characterize the four axes on SWE-bench Verified; n=100 tasks, N models |
| ¶4 findings preview | Pareto · heterogeneity · timing · stacking — terse one-liners |
| ¶5 contributions | (a) taxonomy + grid, (b) four structural findings, (c) statistical scaffold, (d) failure-mode characterization, (e) released artifact |
| anchor | Fig 1: taxonomy schematic — four axes and where primitives sit |
| writeable now? | yes |

### §2 — Related Work
| sub-theme | role |
|---|---|
| long-context evaluation (RULER, lost-in-middle) | brief; explicitly *not* our contribution area |
| single-turn prompt compression (LLMLingua-2, Selective Context) | brief; different problem |
| **agent-loop compression** (ACON, AgentDiet, Reflexion-style summary) | central — position our work as the first design-space characterization, not a method |
| routing/cascade adjacent literature | acknowledge as adjacent; explicitly state we do not propose routing |
| SWE-bench Verified and agent benchmarks | grounding |

### §3 — Compression-Primitive Taxonomy
| sub | content |
|---|---|
| §3.1 four axes | formal definitions of *content*, *trigger*, *aggressiveness*, *interaction* |
| §3.2 the 11 primitives | per-primitive: name, axis coordinates, mechanism, pseudocode, source |
| §3.3 the grid | how primitives populate the axes |
| anchors | Table 1 (primitives × axis coordinates), Fig 2 (axis schematic with primitives placed) |
| writeable now? | yes — definitional |

### §4 — Experimental Setup
| sub | content |
|---|---|
| §4.1 benchmark | SWE-bench Verified; n=100 task selection criteria |
| §4.2 models | Qwen3.5-35B-A3B primary; secondaries TBD |
| §4.3 agent harness | mini-swe-agent fork, tool inventory, system prompt, step cap |
| §4.4 budgets | {10k, 15k, 20k}; two unbounded baselines (FC@262k, OTRC@∞) |
| §4.5 **compression overhead accounting** | what `total_tokens_consumed` counts; SU/SS overhead disclosure — **item #4** |
| §4.6 **statistical procedure** | paired bootstrap CIs, McNemar exact, multi-comparison correction — **item #1** |
| §4.7 run protocol | 2 runs/cell; seeds; total run count |
| anchors | Table 2 (run grid), Table 3 (harness hyperparameters) |
| writeable now? | partially — §4.5 needs #4 audit |

### §5 — Structural Findings (RQ1–RQ4)
| sub | claim | evidence | figure |
|---|---|---|---|
| §5.1 RQ1 mechanism specialization | Primitives form a Pareto frontier; no single primitive dominates | per-cell Pareto plot with 95% CIs | Fig 3 |
| §5.2 RQ2 task specialization | ~30% pairwise disagreement; top-2 oracle saturates achievable resolve | per-task winner heatmap, pairwise disagreement matrix, oracle-of-k curve | Fig 4–5 |
| §5.3 RQ3 composition | Stacking yields consistent but sub-additive gains | stacking interaction table, marginal-gain decomposition, paired CIs | Fig 6 |
| §5.4 RQ4 timing | Threshold +6 pp resolve, online 1.5× cheaper; monotone in budget, consistent across stack variants | head-to-head table (3 pairs × 3 budgets), trade plot, McNemar p-values | Fig 7 |

### §6 — Failure-Mode Reshaping (RQ5)
| sub | content |
|---|---|
| §6.1 outcome taxonomy | `resolved / submitted_unresolved / limits_exceeded / silent_crash`, formally defined |
| §6.2 FC's silent failure | ~50% wrong-patch silent failures at 262k — the baseline pathology |
| §6.3 compression reshapes the failure mix | per-cell outcome distribution; deltas vs FC |
| §6.4 stacking and failure modes | does +SS / +SU change failure mix differently than it changes resolve? |
| anchors | Fig 8 (stacked-bar grid), Table 4 (FC vs primitive silent-failure shares with paired CIs) — **item #3** |

### §7 — Generalization (RQ6)
| sub | content |
|---|---|
| §7.1 cross-model | re-run subset on secondary models; replicate RQ1, RQ4, RQ5 |
| §7.2 cross-benchmark | second benchmark; reduced grid (top 4 primitives × 1–2 budgets × 30+ tasks) — **item #8** |
| §7.3 what replicates vs what shifts | explicit per-finding × per-(model, benchmark) categorization |
| anchors | Fig 9 (Pareto across models), Fig 10 (Pareto across benchmarks), Table 5 (replicate / shift / break per finding) |

### §8 — Implications
| sub | content |
|---|---|
| §8.1 cost-per-resolve frontier | practitioner guidance: at budget B, most efficient primitive is X |
| §8.2 where stacking pays | which stack combinations have favorable cost / risk profiles |
| §8.3 failure-mode-aware deployment | choose primitive by which failure mode is least acceptable |
| §8.4 implications for future methods | what new compression methods must beat: Pareto frontier, online-vs-threshold trade, stacking baseline |
| writing rule | no routing framing — implications stay characterizing, not prescribing a router |

### §9 — Limitations & Threats
- single harness (mini-swe-agent) — flag #9 (second harness) as future work
- n=100 limits very fine-grained claims
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
| 4 | §5 RQ1–4 | n=100 data + item #1 (stats) |
| 5 | §6 RQ5 | item #3 (failure-mode table) |
| 6 | §7 RQ6 | cross-model runs + item #8 (second benchmark) |
| 7 | §2 Related Work | iterative |
| 8 | §8–10 | all results |
| 9 | abstract | last — final numbers |

---

---

## Introduction blueprint

Per-paragraph plan for §1. Each paragraph: goal, key claims, citations to anchor, transition, length, open knobs. Approved 2026-05-01; draft pending after compact.

### ¶1 — The agent context-budget problem (motivation)
- **Goal:** Establish a real, growing context-pressure problem for agents — independent of long-context-degradation framing.
- **Key claims:** Multi-step agents accumulate context across every step (tool calls, observations, intermediate decisions); long-horizon tasks routinely exceed the budget; mechanically distinct from long-context evaluation since trajectories grow with task complexity, not input size.
- **Citations:** SWE-bench Verified, GAIA, AppWorld; agent-harness papers showing trajectory growth.
- **Transition:** *"A growing literature responds with..."*
- **Length:** 4–5 sentences.

### ¶2 — The compression-primitive landscape (state of the field)
- **Goal:** Establish that compression is a dense sub-area; foreshadow the evaluation-pattern gap.
- **Key claims:** Many primitives have been proposed (truncation, summarization, structured/selective deletion, online tool-result reduction); each is typically introduced and evaluated in isolation against full-context; existing work establishes that compression *helps*, not how compression decisions *trade off*.
- **Citations:** ACON, AgentDiet, LLMLingua-2, Reflexion-style summary, agent-harness compression knobs.
- **Transition:** *"This isolation leaves a structural question unanswered..."*
- **Length:** 4–5 sentences.

### ¶3 — The design-space gap (load-bearing)
- **Goal:** Articulate why the *design space* is the right unit of analysis.
- **Key claims:** Compression is not a single dial but a multi-axis design problem; primitives differ along orthogonal axes — what content is removed, when compression fires, how aggressively, how primitives interact; without characterizing the cumulative space, practitioners can't choose and researchers can't situate new methods; the field needs a map.
- **Length:** 4–5 sentences.
- **Open knob:** rhetorical register — measured ("the field accumulates point comparisons") vs sharp ("compression is treated as a single dial when it is a four-axis design problem"). Default: measured.

### ¶4 — Our approach (methods preview)
- **Goal:** State concretely what we did with enough scale signal for a skimmer.
- **Key claims:** 11 compression primitives organized along the four axes; populated 35-cell evaluation grid (three budgets × 11 primitives + two unbounded baselines); 100 SWE-bench Verified tasks across N models; generalization probes on a second benchmark domain; statistical scaffolding (paired CIs, McNemar) throughout.
- **Length:** 3–4 sentences.
- **Open knob:** whether to mention the second benchmark here or save for §7. Default: mention here, strengthens "characterization" framing.

### ¶5 — Findings preview
- **Goal:** Hook with the four structural findings — concrete enough to interest, terse enough to keep reading.
- **Key claims** (one sentence each):
  - **Pareto:** primitives form a frontier on resolve rate vs tokens-per-resolve; no choice dominates jointly.
  - **Heterogeneity:** primitives disagree on ~30% of tasks; top-2 oracle exceeds any single primitive.
  - **Timing:** threshold-triggered clearing buys ~6 pp resolve over online at 1.5× tokens, monotone and consistent.
  - **Stacking:** sub-additive; reshapes failure modes more than it shifts resolve.
- **Length:** 5–6 sentences.
- **Open knob:** include cross-model/benchmark replication line here, or as a separate sentence before ¶6. Default: separate sentence.

### ¶6 — Contributions list
1. A four-axis taxonomy of agent context-compression primitives.
2. The 35-cell evaluation grid populated across 100 tasks and N models, with paired-CI statistical scaffolding.
3. Four structural findings (Pareto, heterogeneity, timing, stacking) anchored with significance tests.
4. A failure-mode characterization showing FC's silent-failure share and how compression reshapes the outcome distribution.
5. A released artifact: the design-space map (data, eval pipeline, scripts) as a scaffold for future compression methods.
- **Open knob:** keep 5, or trim to 3 (taxonomy / findings / artifact). Default: 5.

### ¶7 (optional) — Roadmap
- *"Section 2 surveys related work; Section 3 defines the taxonomy; Section 4 details the experimental setup; Sections 5–7 present results; Section 8 discusses implications."*
- **Length:** 1–2 sentences.
- **Open knob:** include or skip. Default: include.

### Decisions still pending before drafting
1. ¶3 rhetorical register (measured vs sharp)
2. ¶4 — mention second benchmark or save for §7
3. ¶5 — cross-model/benchmark line placement
4. Contributions count (5 or 3)
5. ¶7 roadmap (include or skip)
6. Length target (typical EMNLP intro 200–450 words)

---

## Cross-references

- `exp_plans/FULL_TASK_EXPANSION_INSTRUCTIONS.md` — P100 expansion handover
- `Active_runs.md` — live status of long-running experiments
- `Review1/Review1.csv` — current n=30 results
- `Review1/winners_table.py`, `Review1/plot_review1.py` — analyses already implemented
- Memory: `project_p100_expansion.md`, `feedback_no_cascade.md`, `feedback_no_routing.md`, `feedback_paper_edits.md`
