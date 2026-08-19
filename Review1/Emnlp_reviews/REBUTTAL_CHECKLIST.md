# EMNLP 2026 (ARR May) — Rebuttal Checklist

**Deadline: July 14, 2026 AoE** (author discussion closes; meta-review follows).
Scores: EERa 3.0 · hX3S 3.0 · Axo9 2.5 · zCqe 2.5 → avg 2.75, borderline Findings.
Target: move Axo9/zCqe soundness & overall via statistics + hygiene fixes.
Data check: `Review1.csv` has 2 runs × 100 tasks for every (primitive, budget, depth) cell — **all Tier 1 items computable with zero new runs.**

---

## Tier 1 — Compute from Review1.csv, cite in response (do first, 1–2 days)

| # | Item | Answers | Status |
|---|------|---------|--------|
| 1 | **Paired bootstrap CIs** on headline comparisons: TRC+SU vs TR (18pp spread), the 3 trigger pairs, best-policy vs FC. Resample tasks, paired across policies. | Axo9, zCqe, hX3S | ☐ |
| 2 | **Same-policy solve-set disagreement**: run1 vs run2 disagreement per policy; show between-policy disagreement > within-policy. Defends the oracle/heterogeneity finding with data. | hX3S (exact ask) | ☐ |
| 3 | **Conservative oracle bound**: recompute 67% oracle using only tasks solved in *both* runs; report liberal + conservative. | hX3S | ☐ |
| 4 | **Characterize policy-dependent tasks** using `step_count`, `compression_events`, `repo`, `failure_mode` — what distinguishes the 53% mixed-outcome tasks. | Axo9 (suggestion) | ☐ |

## Tier 2 — Text-only, zero compute (fold into responses)

| # | Item | Answers | Status |
|---|------|---------|--------|
| 5 | **Model-naming table**: exact HF checkpoint for main model, Devstral, Qwen2.5-Coder, quant base. Quant base (Qwen3-30B-A3B-Instruct-2507) is a genuinely different model — say so explicitly. ⚠️ *Confirm correct names first.* | hX3S, Axo9 | ☐ |
| 6 | **Adaptive-selector answer**: report predictability-sprint result ("feature-based selection does not recover the oracle gap") and weaken claim to "headroom," as hX3S offers. Honest negative > vague promise. ⚠️ *Pull numbers from `predictability_sprint.py` output.* | EERa, Axo9, hX3S | ☐ |
| 7 | **Budget realism**: 10–20K is the compression *trigger threshold*, not total consumption — agents consume 460–716K prompt tokens per task. Small budgets are the regime where policy choice matters (Takeaway #4). | zCqe | ☐ |
| 8 | **Summarizer confound**: scope main-text claims to "self-summarization, same-class model"; commit to cross-summarizer ablation in revision. | EERa, Axo9 | ☐ |
| 9 | **Artifact commitment**: promise harness fork, task split, prompts, Review1.csv. Paste SU/SS prompt text inline in response (links forbidden; inline text OK). | all (Repro ≤2, link says "TBD") | ☐ |
| 10 | **Presentation commitments**: FC row in Table 2 (numbers quotable from CSV now), Figure 2 redesign, replace Figure 4 with table, remove "Example Appendix" header, fix typos (settin/sever/primtive). | zCqe | ☐ |

## Tier 3 — New runs (only after Tiers 1–2; mostly revision/resubmission scope)

| # | Item | Answers | Status |
|---|------|---------|--------|
| 11 | **Complete trigger factorial**: missing cells (e.g., TRC+SU-partial/Th) on ABL-30 to de-confound trigger vs partial/full. Small Dobby run — maybe feasible in window. | hX3S | ☐ |
| 12 | **Cross-summarizer ablation** (separate summarizer model, Albus). | EERa, Axo9 | ☐ |
| 13 | **Second harness / benchmark**. Resubmission only; for now narrow claims in response. | EERa, Axo9, zCqe | ☐ |

---

## Response mechanics (ARR rules)

- Text-only Official Comments on OpenReview; **no links, no PDF revision** during discussion.
- Keep each response short — ACs read ≤2 author responses per thread.
- Focus on soundness + reproducibility, not excitement.
- One review may still arrive; poll OpenReview.
- Review-issue reports due July 17 AoE (separate from discussion).

## Sequence

1. Run Tier 1 analyses (items 1–4) as one pass against Review1.csv.
2. Draft 4 per-reviewer responses weaving in the numbers + Tier 2 commitments.
3. Decide on item 11 (small run) only if time remains before July 14.

**Open questions for author:**
- Correct model names for item 5 (which name on p.3 is the error?).
- Green-light item 6 framing (predictability-negative + weaken to headroom).
