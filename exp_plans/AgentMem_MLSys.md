# AgentMem: Co-Designed Memory Management for LLM Agent Serving

**Target venue:** MLSys
**Status:** Direction proposal, pre-commitment
**Last updated:** 2026-04-26

---

## One-line pitch

Agent context management (in the harness layer) and KV cache management (in the inference engine layer) are designed independently. The coupling losses are large and measurable. AgentMem is a unified memory hierarchy across the harness/engine boundary that delivers throughput, memory, and cost wins.

---

## The problem nobody has named

Two layers manage memory for LLM agents, and they don't talk to each other:

- **Agent harness layer** (mini-swe-agent, LangChain, Claude Code, etc.): manages message history. Implements TRC, summarization, truncation. Decides what content the agent "sees."
- **Inference engine layer** (vLLM, TensorRT-LLM, SGLang, etc.): manages KV cache. Implements paging, prefix caching, eviction. Decides what tokens are computed-once vs recomputed.

These layers see the same content through different lenses, and their independence creates concrete waste:

| # | Coupling loss | Concrete cost |
|---|---|---|
| 1 | **Stranded KV cache** | When the harness clears a tool output (TRC), vLLM still holds KV pages for those exact tokens. We pay HBM for content the agent has discarded. |
| 2 | **Compression destroys cache hits** | Harness summarization rewrites the prompt prefix; vLLM's prefix cache hit rate drops to zero on the next call. We pay full recompute for content that was already cached. |
| 3 | **Re-execution instead of replay** | Agent re-runs `cat foo.py` after clearing it. vLLM may still have warm KV for the original output. We pay tool execution + recompute when we could have replayed for free. |
| 4 | **No multi-tenant deduplication** | Multiple agents working on the same repo independently fetch/store identical content. No cross-agent sharing of cache or content. |
| 5 | **Engine-level eviction is semantically blind** | vLLM's KV eviction (LRU, attention sinks) doesn't know which tokens are load-bearing agent content vs cold tool output. It evicts uniformly when the harness has the semantic signal. |

**Back-of-envelope cost** from our existing data (Qwen3.5-35B-A3B online-TRC runs):
- 75 clears per run × ~2300 tokens cleared per event × 16 concurrent agents
- Stranded KV cache estimate: **2-3 GB of HBM** held by content the harness has logically discarded.

Nobody has published a coordinated solution. Every lab serving agents (Anthropic, OpenAI, Cursor, Replit, Cognition) hits this.

---

## The contribution

A unified memory hierarchy with three coordinated operations spanning both layers:

| Operation | Direction | What it does |
|---|---|---|
| **Coordinated evict** | Harness → engine | Harness emits a tombstone when content is cleared; engine immediately frees the corresponding KV pages |
| **Cache-aware compress** | Engine → harness | Engine exposes per-prefix cache state to harness; harness preferentially compresses tokens that are already cache-cold |
| **Pooled recall** | Engine ↔ population | Shared content store across agents; recall hits the store before re-executing tools; deduplication across agent tenants |

Three operations, one hierarchy, two layers redesigned to cooperate.

---

## Why this is top MLSys

- **Classic cross-layer co-design** — the kind of contribution MLSys reviewers light up for. Memory management split across abstraction boundaries with measurable losses; we propose the right boundary redesign.
- **Measurable wins on every axis MLSys cares about**: HBM utilization, request throughput, P99 latency, $/successful-task, multi-tenant fairness.
- **Real production problem** — every lab serving agents hits this. None have published a coordinated solution.
- **Builds on real infrastructure** — vLLM is open source; we can implement on top of it. The artifact is reproducible and reusable.
- **Has theoretical content** — joint memory hierarchy optimization is a well-studied problem (cache hierarchies, virtual memory). Applied to a new substrate where the layer boundaries are unconventional.
- **Generalizes broadly** — engine side is model-agnostic (any vLLM-served model); harness side is harness-agnostic (any Python agent loop).

---

## Paper structure

```
1. Introduction
   - The layer-split problem
   - The cost (back-of-envelope + workload measurement)
   - The contribution

2. Workload Characterization
   - Per-step KV cache utilization in real agent workloads
   - Compression event distribution (when, what, how much)
   - Multi-tenant content overlap (how much shared content across agents)
   - Idle/active ratios (fraction of wall time spent in tool execution vs LLM)
   - Recall opportunity rate (re-executions that could have been replays)

3. System Design — AgentMem
   - Tombstone protocol (harness → engine eviction signal)
   - Cache-state API (engine → harness coordination)
   - Pooled content store (multi-tenant)
   - Recall protocol (agent-controlled re-inflation)
   - Consistency model (handling environment mutations between snapshot and recall)

4. Implementation
   - vLLM extension (KV page management hooks; cache-state introspection API)
   - Harness integration (tombstone emission; cache-aware compression policy)
   - Content store (content-addressed; per-tenant ACLs; eviction policy)
   - Recall mechanism (agent prompt format; interception in step loop)

5. Evaluation
   - Microbenchmarks: KV cache savings, recall hit rate, dedup ratio, tombstone latency
   - Macro: throughput, latency, $/task on SWE-bench (+ ideally WebArena), vs uncoordinated baselines
   - Multi-tenant scaling: how AgentMem scales with concurrent agents (16, 64, 256)
   - Sensitivity: cache size, recall window, tenant overlap

6. Related Work
   - vLLM, SGLang, TensorRT-LLM (engine-only memory mgmt)
   - MemGPT, A-MEM (harness-only memory mgmt)
   - Neural Garbage Collection (model-internal KV eviction)
   - Position: AgentMem operates at the layer boundary none of these address

7. Discussion / Limitations
   - Consistency challenges with mutable environments
   - Multi-engine deployments (model parallelism, replicas)
   - Privacy / isolation concerns in multi-tenant pooling

8. Conclusion
```

---

## Headline numbers we'd target

| Metric | Target | Source of plausibility |
|---|---|---|
| **HBM savings from coordinated eviction** | 2-4× | Our online-TRC data: 75 clears × 2300 tok = ~170K tokens cleared per run. At 16 concurrent agents and ~100 KB/page that's GB-scale stranded KV. |
| **Throughput in multi-tenant serving** | 30-60% improvement | Dedup + pooled recall reduce engine work for repeated content; common dev workloads have high tenant overlap (same repo, same files). |
| **$/successful-task reduction** | 15-30% | Recall replacing re-execution skips both tool execution time and LLM reprocessing cost. |
| **Accuracy regression vs best baseline** | None (within noise) | The coordination is purely structural; doesn't change what content the agent sees, only how it's stored/served. |

If half these numbers hold, it's a strong MLSys submission.

---

## Sprint 0 — Workload Characterization (2-3 weeks)

Before we commit to building anything, measure the gap. Goal: produce evidence-backed estimates for the headline numbers above.

### Measurements on existing data

From the 990-run main experiment + 198-run online-TRC + soon-to-complete stacked ablation:

1. **Stranded KV cache estimate**: total tokens cleared by harness compression × estimated KV size per token × concurrency factor.
2. **Compression-induced cache misses**: per compression event, count tokens whose KV would have been retained but is now invalidated by prompt prefix change.
3. **Re-execution rate**: fraction of agent steps where the bash command is identical to a prior step's command. Proxy for recall opportunity.
4. **Cross-task content overlap**: hash file contents, command outputs, search results across all 990 trajectories. Compute Jaccard / dedup ratio.

### New measurements (require harness instrumentation)

5. **vLLM cache state during agent runs**: poll `/metrics` endpoint mid-run; record `kv_cache_usage_perc`, `prompt_tokens_recomputed_total`, prefix cache hit rate.
6. **Idle/active ratio**: instrument the harness to log time-in-LLM-call vs time-in-bash-execution per step. Quantify the speculative-prefetch opportunity.
7. **Concurrent-agent contention**: launch N=16, 32, 64 agents simultaneously on overlapping task sets; measure throughput, P99 latency, KV pressure.

### Output

A 5-page workload-characterization tech report — could double as paper Section 2. Decision-rule afterward:

| Stranded KV ratio | Recall opportunity rate | Verdict |
|---|---|---|
| > 30% | > 20% | **Commit to AgentMem; build the system** |
| 15-30% | 10-20% | **Borderline; sharpen scope to strongest sub-contribution** |
| < 15% | < 10% | **Pivot — gap not large enough for a top paper** |

---

## Build phase (3-4 months, after Sprint 0 vindicates the direction)

| Phase | Duration | Deliverable |
|---|---|---|
| Workload measurement (Sprint 0) | 2-3 weeks | Tech report with go/no-go evidence |
| Tombstone protocol + vLLM hooks | 4 weeks | Coordinated eviction working end-to-end |
| Cache-aware compression | 3 weeks | Harness queries engine; biased eviction policy |
| Pooled recall + multi-tenant store | 4 weeks | Shared content store across concurrent agents |
| Evaluation infrastructure | 3 weeks | Throughput / latency / cost harness for multi-tenant |
| Macro experiments + paper writing | 4 weeks | Full evaluation across SWE-bench (+ WebArena) |

**Total scope:** ~3-4 months for one strong systems engineer + ML researcher.
**Compute scope:** moderate — multi-tenant evaluation needs concurrent agent runs but we already have that infra.

---

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| Workload characterization shows the gap is small | Sprint 0 surfaces this in 2-3 weeks before any system build |
| vLLM internals are too brittle to hook | Prototype the tombstone protocol on a vLLM fork early; if it's a nightmare, consider SGLang as alt substrate |
| Multi-tenant pooling raises privacy concerns | Per-tenant ACLs in the content store; restrict pooling to within-tenant by default; cross-tenant as opt-in |
| Consistency model under mutation is hard | Initial version: recall returns snapshot, agent decides if stale; future work invalidates on writes |
| WebArena infrastructure adds months | Start with SWE-bench only; add WebArena if pace allows |
| Reviewer push: "this is just caching" | Be explicit about the layer-coordination novelty; cite vLLM/SGLang and show they don't expose the necessary cross-layer hooks |
| NGC reviewers ask: "why not just do RL?" | NGC is model-internal; AgentMem is system-level. Different abstraction, different deployment story (inference-time, no fine-tuning) |

---

## Open decision points

1. **vLLM access**: do we have the engineering bandwidth to extend vLLM, or do we need a collaborator with deep vLLM expertise?
2. **Second benchmark**: WebArena (or similar) elevates the paper from "SWE-bench specific" to "agent serving generally." Worth the extra month?
3. **Multi-tenant scope**: do we evaluate with single-tenant only (simpler, less impressive) or push to true multi-tenant (harder, much stronger story)?
4. **Privacy story**: how aggressive on cross-tenant pooling? The strongest dedup wins require it; the safest deployment story restricts it.

---

## Position vs prior work

| Work | Layer | Operation | Setting | Relationship |
|---|---|---|---|---|
| vLLM, SGLang, TensorRT-LLM | Engine only | KV management, prefix caching | Single-call serving | We extend their cross-layer interfaces |
| MemGPT, A-MEM | Harness only | Long-term memory, retrieval | Agent harness | Complementary; we co-design rather than replace |
| Neural Garbage Collection (Li et al. 2026) | Model internal | Learned KV eviction | Single-pass reasoning | Substrate optimization within the engine; orthogonal to layer coordination |
| Anthropic Claude Code TRC | Harness only | Reactive tool-output clearing | Coding agent | A specific harness primitive; AgentMem makes it engine-aware |
| Our own existing primitives (TRC, online-TRC, stacked) | Harness only | Various compression | Coding agent | Becomes the harness side of AgentMem; no longer a standalone story |

---

## Why I'm recommending this over the NeurIPS direction

1. **Fits what we've actually built.** Our work is fundamentally systems-flavored (primitives, harnesses, runners). The MLSys frame plays to that.
2. **Larger empirical foothold.** We already have 990 runs to mine for workload characterization. NeurIPS would have required new behavioral evaluations and theoretical work we don't have.
3. **Lower risk.** Systems wins are easier to demonstrate convincingly than cognitive/behavioral claims. Reviewers either believe the throughput numbers or they don't.
4. **Industry pickup.** A vLLM-extending artifact gets used. A behavioral-failure taxonomy gets cited.
5. **NGC doesn't threaten this at all.** They're substrate-internal; we're cross-layer. Completely orthogonal.
6. **Faster to ship.** 3-4 months including system build vs 4-6 months for the NeurIPS version with theoretical risk.

The NeurIPS direction (counterfactual ablation, working memory, behavioral failures) remains a strong follow-up paper for a different venue or a future cycle. It is not lost — it's deferred.
