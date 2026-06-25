# Characterization Paper — Framing v1

**Date:** 2026-05-01
**Status:** Spine locked. Abstract drafted. Awaiting n=100 expansion to finalize numbers.
**Supersedes:** prior framings (long-context, signal-curation, compression-beats-FC, smaller-models-benefit-more, routing-as-takeaway, cascade-as-mechanism — all rejected).

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

## Cross-references

- `exp_plans/FULL_TASK_EXPANSION_INSTRUCTIONS.md` — P100 expansion handover
- `Active_runs.md` — live status of long-running experiments
- `Review1/Review1.csv` — current n=30 results
- `Review1/winners_table.py`, `Review1/plot_review1.py` — analyses already implemented
- Memory: `project_p100_expansion.md`, `feedback_no_cascade.md`, `feedback_no_routing.md`, `feedback_paper_edits.md`
