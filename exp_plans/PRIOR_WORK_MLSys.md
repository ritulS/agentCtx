# Prior-work analysis — MLSys direction

**Purpose:** living document. Maintain the prior-work landscape for the MLSys
submission here. Add papers as found; date every entry batch. The older
position table in AgentMem_MLSys.md (2026-04-26; deleted 2026-08-19, in git history) is
superseded by this file.

**Last updated:** 2026-08-17

---

## Our two candidate contributions (context)

- **Option 1 — cache-aware compression:** measure the KV/prefix-cache damage
  each compression policy causes at the serving layer; build prefix-stable
  variants of our primitives.
- **Option 2 — compression as a capacity lever:** measure concurrent agents
  per GPU as a function of compression policy, jointly with task resolve rate.
  Claim: "the compression policy sets the accuracy-vs-capacity frontier of an
  agent fleet."

---

## Tier 1 — direct overlap

### TokenPilot (arXiv 2606.17016, June 2026)
*Cache-Efficient Context Management for LLM Agents*

- **What it does:** names the exact trade-off "text sparsity vs prompt cache
  continuity" — compression mutates the prompt, prefix mismatches invalidate
  the KV cache. Fix is dual-granularity: (a) global prefix stabilization
  (byte-identical prefix; volatile fields replaced with placeholders) +
  in-place observation reduction with an on-demand recovery tool; (b) local
  lifecycle-aware eviction (active → completed → evictable segments, judged by
  a Qwen3.5-35B estimator, batch-triggered every 3 turns).
- **Evaluation:** PinchBench (123 tasks) + Claw-Eval (161 tasks); backbone
  GPT-5.4-mini (closed API). Reports accuracy, cache-hit/miss tokens, dollar
  cost. 10 baselines incl. truncation, summarization, LLMLingua-2, MemOS.
- **Impact on us:** **kills the headline of Option 1.** "Compression breaks
  the cache; prefix-stable compression fixes it" is published.
- **Remaining gaps we can use:**
  1. Closed API model; dollar cost only — no TTFT, no prefill compute, no
     throughput on self-hosted serving.
  2. One context manager vs baselines — no policy design space (no
     primitive/trigger/depth axes, no budget sweep).
  3. No coding agents, no SWE-bench.
  4. Single agent — nothing on fleet capacity.
- **How to use it:** cite as the cache-hostility motivation; implement
  prefix-stabilization as one primitive *inside our axes* → their method
  becomes a baseline in our grid.

### Parallel Context Compaction (arXiv 2605.23296, 2026)
*Parallel Context Compaction for Long-Horizon LLM Agent Serving*

- **What it does:** makes the compaction step itself fast: split history into
  fixed-size blocks, summarize blocks concurrently on vLLM with a
  prefix-aware target-at-end layout that preserves prefix caching during the
  compaction call. Sequential summarization shown to eat up to 62% of
  end-to-end wall time.
- **Evaluation:** HotpotQA + LoCoMo (QA-style, no tool use, no coding);
  Llama-3.1-8B → gpt-oss-120B; accuracy via LLM judge, wall time, compaction
  throughput, output stability (CV).
- **Impact on us:** owns "the compaction call is a serving bottleneck; make
  it parallel and cache-friendly." Does NOT study the cache damage the
  *rewritten history* causes on subsequent agent steps, fleet capacity, or
  coding agents.

### TokenCake (arXiv 2510.18586, v3 2026)
*A KV-Cache-centric Serving Framework for LLM-based Multi-Agent Applications*

- **What it does:** no compression at all. Keeps full KV; temporal scheduler
  offloads idle caches to CPU during tool calls (event-driven + predictive
  upload); spatial scheduler reserves GPU memory for critical-path agents in
  a multi-agent DAG. vs vLLM: −47% e2e latency, +16.9pp GPU memory
  utilization.
- **Evaluation:** Qwen2.5-14B/32B/72B on A100/H20; synthetic multi-agent apps
  (Code-Writer, Deep-Research); **no task accuracy measured**; no
  agents-per-GPU scaling curve.
- **Impact on us:** adjacent to Option 2 but orthogonal mechanism
  (scheduling/offload, not context reduction). Cite as "serving-layer-only
  optimization for a fixed context policy."

---

## Tier 2 — scheduling/cache neighbors (no compression, no accuracy)

| Work | Mechanism | Relation |
|---|---|---|
| Continuum (arXiv 2511.02230) | KV cache time-to-live for multi-turn agent scheduling | Engine-side retention policy; context text untouched |
| KVFlow (arXiv 2507.07400) | Workflow-aware prefix-cache eviction for agent workflows | Engine-side; needs workflow structure |
| Autellix | Program-level scheduling (PLAS); end-of-turn eviction | Scheduling only; ignores cache retention value |
| InferCept (ICML'24) | Retain/swap/discard KV during tool-call interception | Per-request; cost model on tool duration |
| Parrot (OSDI'24) | Semantic variables over static app DAGs | Static workflows; no dynamic agents |
| KAIROS (arXiv 2604.16682) | Power-efficient stateful agent serving | Orthogonal objective (energy) |
| TokenDance (arXiv 2604.03143) | Collective KV sharing across multi-agent | Cross-agent sharing, not compression |
| ForkKV (arXiv 2604.06370) | Copy-on-write disaggregated KV for multi-LoRA agents | Orthogonal |

Common shape: all manage the KV cache *around* an unmodified context; none
change what the agent sees; none measure task success; none sweep context
policies.

---

## The empty triangle (our position)

No published work connects all three of:

1. **compression policy choice** (a design space, not one method),
2. **task success** (resolve rate on a real coding benchmark),
3. **serving capacity** (agents/GPU, throughput, TTFT on self-hosted stack).

TokenPilot has (1-partially, 2) without (3). TokenCake/Continuum/KVFlow have
(3) without (1) or (2). Parallel Context Compaction has (2-weakly, 3-partially)
for one mechanism. Our 33-policy × resolve-rate grid already supplies (1)+(2);
adding the capacity axis on Albus/vLLM completes the triangle.

**Recommended framing (2026-08-03):** lead with Option 2 extended with
accuracy — "compression policy sets the accuracy-vs-capacity frontier of an
agent fleet." Fold Option 1 in as a measurement section (per-policy cache
damage) plus prefix-stabilization as one primitive in the grid, with
TokenPilot as baseline — not as the headline.

**Note on AgentMem_MLSys.md:** its coupling-loss table (esp. #2 "compression
destroys cache hits") is now partially claimed by TokenPilot; coordinated
evict (#1) and pooled recall (#3/#4) remain unclaimed as of this scan.

---

## Tier 0 — production motivation (added 2026-08-03)

### Copilot traces study (MSR Azure Research, July 2026)
*Agentic Coding in the Wild: Characterizing GitHub Copilot at Production
Scale* — Liu, Qiu, Goiri, Fonseca, Bianchini, Choukse.
[PDF](https://www.microsoft.com/en-us/research/wp-content/uploads/2026/08/ghcp_traces-6.pdf)

- First production-scale trace study of a coding agent: 13.5M sessions, 3.2M
  users, 761M LLM calls, 95T tokens (one week, June 2026).
- **Compaction is named a "third structural cache event"** (with turn
  boundaries and model switches): fires in 7.8% of sessions but those
  sessions carry **44.2% of all tokens**; median event drops 72.8% of prompt
  tokens and **66.1% of cache hit rate**; 34.3% of events erase ≥90% of cache
  hits, 21% erase ≥99%. Compaction call itself costs median 22% (P90 34%) of
  turn wall time, on the critical path.
- Cache economics: median call = 68K prompt tokens, 63K cached; intra-turn
  hit rate plateaus 92–94%; a cache miss for Deep-loop users = median 1.1M
  token re-prefill.
- **Takeaway 10 is an explicit open call for our mechanism:** "Incremental,
  prefix-preserving compaction strategies could maintain partial cache
  continuity."
- What they cannot see (our lane): no prompt content, no task outcomes → no
  accuracy axis, no policy comparison. Their telemetry cannot say whether
  compaction hurts task success or which policy to use.
- **Watch (resolved 2026-08-03):** Sutradhara scanned — no collision, see
  Tier 2 entry. SAGA and Pythia still unscanned (workflow-aware scheduling;
  low collision risk by description).

### Sutradhara (arXiv 2601.12967, Microsoft, 2026) — scanned, no collision
*An Intelligent Orchestrator-Engine Co-design for Tool-based Agentic
Inference*

- Three optimizations over vLLM via a thin orchestrator↔engine API:
  (1) tool-aware prompt splitting — overlap tool execution with prefill of
  the next call; (2) streaming tool dispatch during decode; (3)
  orchestrator-aware cache management — semantic tags, pinning, hint-aware
  eviction to stop LRU thrashing across agent iterations.
- Results: up to 77% higher load at same median first-token-rendered
  latency; up to 15% median FTR reduction. Cache management alone
  contributes only ~1.8%.
- **No compression, no compaction, no KV editing, no accuracy measurement.**
  It never modifies context; it schedules and protects intact caches.
- **Useful to us as precedent:** it legitimizes a thin cross-layer API on
  vLLM at the exact harness/engine boundary our edit primitive crosses.
  Their hints say "keep these blocks"; our calls say "edit these blocks."
  Cite as the co-design neighbor; position our work as the first co-design
  that crosses the boundary with *content edits* rather than scheduling
  hints. Their production finding (tool calls = 30–85% of final-answer
  latency; cache hit collapse across iterations) reinforces Tier 0
  motivation.

## Tier 3 — KV-reuse-under-mismatch neighborhood (added 2026-08-03)

Relevant to the "free deletion / cheap context edits" direction. Both papers
reuse KV computed in the *wrong context* and repair with selective recompute.
Both are concatenation-only; neither supports deletion/replacement mid-history;
neither faces repeated sequential edits; neither measures agent task success.

- **CacheBlend (EuroSys'25, arXiv 2405.16444):** RAG chunk fusion. Cached
  chunk KV lacks cross-attention to preceding text. Fix: recompute ~15% of
  tokens — those with highest KV deviation, identified dynamically via
  layer-1 recompute, then recomputed across all layers. Quality preserved;
  TTFT 2.2–3.3×; selection overhead 16–64% of TTFT, still O(N²).
- **EPIC / LegoLink (arXiv 2410.15332):** position-independent caching.
  Chunks compiled at position 0 → chunk-initial tokens act as spurious
  attention sinks and absorb attention. Fix: statically recompute only first
  k≤32 tokens of each non-first chunk + query tokens, at correct positions,
  all layers. ≤7% accuracy loss, up to 3× faster than CacheBlend, O(kN).
- **StreamingLLM (arXiv 2309.17453):** attention-sink discovery; cache
  positions decoupled from text positions (rolling cache with re-assigned
  positions). Basis for our position re-rotation step.

**Delta for our direction:** their error is *missing* attention (chunk saw too
little context); ours is *absorbed* attention (retained tokens saw deleted
content). Their position fix applies fresh positions to recomputed tokens
only; we must shift positions of non-recomputed tokens (delta re-rotation).
Open: is post-deletion KV deviation concentrated (CacheBlend-like) and
structurally predictable (LegoLink-like), and does error compound over ~75
sequential edits per run?

## Tier 3a — direct collisions on cache editing (added 2026-08-06)

Deep scan for the Free Deletion direction. Verdict: **partially scooped.**
The page-free + position-shift machinery exists for MLA models. The
contamination repair on standard-attention models is still unclaimed. So is
any accuracy contract, and so is the sequential-edit question.

### Leyline (arXiv 2606.01065, May 2026) — the closest collision

- Declarative "KV cache directives": a policy can remove or replace a span
  of cached content and continue without re-prefilling the tail. Kernel
  frees the span's KV, prefills the replacement, applies closed-form
  delta-rotation to downstream position keys. ~200-line SGLang RadixCache
  patch. Debug-gym agent tasks: +14.3pp solve, +11.2pp cache-hit.
- **Limits that leave us room:** MLA-only (DeepSeek-V2-Lite, Moonlight-16B,
  GLM-4.7-Flash) — the position/content key split does not exist in
  GQA/MHA-RoPE models (Llama, Qwen). **No repair of contamination** — they
  accept stale downstream states and redefine the contract around it.
- Only paper with repeated-edit numerics: 100 chained delta-rotations →
  2.6e-2 rel-L2, sub-linear growth; they concede periodic re-prefill is
  warranted. Rotation numerics only — not attention contamination.
- Companion: **Irminsul (2605.05696)** — MLA position-independent reuse,
  content-hash chunking, delta-rotation of the rotary component only.

### KVEraser (arXiv 2606.17034, June 2026)

- Same problem statement ("localized context erasing" with cache reuse),
  different route: replaces the erased span's KV with **learned steering
  states** (trained eraser). No rotation, no page freeing, no recompute.
  Near-full-recompute quality at +24% latency. Requires training per model.
- Their intro names our contamination problem explicitly and picks the
  learned route over the surgical route. Cite as the alternative family.

### KV-Splice, inside HUOZIIME (arXiv 2604.14159)

- Our exact math — position-offset map, phase-shift of retained suffix
  keys, selective recompute of injected + tail tokens — but for **insertion**
  of memory facts in an on-device IME. Application subsystem, not a
  standalone contribution. No deletion, no agents, no accuracy study.

### Online KV Cache Compaction for LLM Agents (arXiv 2608.00902, Aug 2026)

- Empirical study of per-turn token-eviction compaction operating on the
  cache directly. Validates the motivation (delayed compaction beats
  immediate). No deletion-repair mechanism.

### Mechanics settled by the 2026-08-06 deep read

- **CacheBlend details:** deviation ranking seeded at a cheap check layer,
  then a per-layer shrinking set ("gradual filtering"); recompute ratio
  r* = 15%; selected tokens get fresh K and V via masked attention over the
  full spliced cache; quality flat for r in 5–18%. CacheBlend **already
  re-rotates chunk keys to new positions closed-form** — position error is
  exact to fix; recompute exists only for cross-attention error. Shipped in
  LMCache as "blending", currently in the deprecated in-process mode.
- **EPIC/LegoLink details:** v3 recomputes first k≤32 tokens of each
  non-initial chunk + all query tokens, full depth, O(kN); accuracy loss
  0–7%; does **not** re-rotate retained keys at all — absorbs position error
  via sink-breaking recompute. (v1 "AttnLink" differs; cite v3.)
- **In-place key re-rotation precedents:** HF SinkCache (angle-subtraction
  identities, in-place, later removed — fragile in practice); OpenVINO
  GenAI cache-eviction rotation (production, linear-RoPE only, off by
  default). Compose multiple shifts into one delta before applying —
  limits fp16 drift (no published drift study exists; open gap).
- **Error accumulation across sequential surgical edits: unmeasured
  anywhere.** Leyline covers rotation numerics only. This gap is ours.

### Remaining unclaimed lane (2026-08-06)

Free pages + delta-rotation + **selective recompute of contamination** on
**standard GQA/RoPE models**, across **policy-driven deletions**, with an
**accuracy contract** (resolve rate vs exact) and **sequential-edit**
analysis, tied to a **policy design space**. Nobody packages this. Leyline
owns the systems shell for MLA; KVEraser owns the learned alternative;
CacheBlend/EPIC own concatenation repair. Move fast — three of these
appeared May–Aug 2026.

## Tier 4 — agent-side context management (added 2026-08-17, ICLR direction)

Scan for the "working set of an agent" direction (causal account of what an
agent must hold in context: presence / position / freshness decomposition +
cost ledger). Verdict: **method lane crowded; science lane open.** Many
methods now implicitly bet on "keep decisions, drop/archive observations,
recover on demand" — none measures the bet causally.

### TRACE (arXiv 2608.06503, Aug 2026) — closest neighbor, read fully
*Toward Reliable Context Compression for Long-Horizon Agents*

- Chooses AppWorld **deliberately because observations are re-queryable** —
  recoverability is central to its motivation, not a passing remark.
- **Measures refetch/replay** (repeated exact action signatures) after
  compaction: compressed context induces +0.031 refetch at step 1, rising
  after. Shows compaction weakens recent-interaction influence → blocked
  actions, repeated exploration, run instability.
- Method: verifier-guided compaction-prompt optimization via paired
  closed-loop continuations at compression boundaries.
- **Claims part of our E2** (re-acquisition exists, counted). Does NOT:
  price faults (tokens/steps/success), classify content by class, run
  matched-volume knockouts, test position, or explain a policy space.
  AppWorld only, no SWE-bench.

### CoACT (arXiv 2607.02911) — our "keep dirty" rule as a method

- Trains a compressor with a **next-action-preservation** reward: compressed
  observation must induce the same next action. SWE-bench Verified, 3 agent
  models, −33% tokens at ~equal resolve.
- Embodies the clean/dirty bet (preserve action-relevant, compress
  observation bulk) as a training signal. **No causal analysis of why**, no
  recoverability measurement, no position, no matched-volume control.

### ARC — Addressable Recall Compaction (arXiv 2607.25066)

- Append-only ID-addressable log of tool observations; old observations
  replaced by citations; agent recalls by ID without re-running tools.
  NIAH 99.4% vs 88.1% baseline; Qwen3-8B/32B. Operationalizes "observations
  are archivable, not memory" — via archive, not environment. No cost or
  causal analysis.

### ACON (arXiv 2510.00615) + AgentDiet (arXiv 2509.23586) — planned E4 baselines

- ACON: LLM-optimized natural-language compression guidelines from
  paired success/failure trajectories; −26–54% peak tokens, up to +46% for
  small LMs "by mitigating context distraction" (= our interference term,
  named but not isolated).
- AgentDiet: reflection module removes "useless, redundant, expired"
  content at inference; −40–60% input tokens on coding agents.
- Both are learned/heuristic implicit working-set policies. Neither
  decomposes why they work.

### Rest of the neighborhood (abstract-level scan)

| Work | Bet it embodies |
|---|---|
| Beyond Compaction (2606.11213) | Typed, dependency-linked episodes; deterministic priority eviction |
| Context as a Tool / CAT (2512.22087) | Context ops as plannable agent tools (SWE agents) |
| VISTA (2606.30005) | Context-state dashboard + lossless archive/recovery |
| Self-GC (2607.00692), CORVUS (2607.22711), ACM (2607.21503) | Self-governed / lifecycle context reduction |
| Context rot in long-horizon search (2606.29718) | Degradation with length; premature-termination diagnosis |
| When Attention Closes (2605.12922) | Multi-turn thread loss (behavioral) |
| Position-bias theory (2603.10123) | U-shape intrinsic to causal decoders |
| STALE (2605.06527) | Benchmark: can agents detect invalidated memories? Synthetic personal-memory conflicts — not coding, not compression |
| Less Context, Better Agents (2606.10209) | Observes stale values "actively detrimental"; qualitative, method-oriented |
| ProcCtrlBench (2605.20251) | Names "ghost context" (redundant/outdated retained content) as defect class |
| MemTX (2607.23929) | Transactional versioned agent memory middleware — external memory, not in-context |
| Mitigating Context Interference (2608.10743) | Names interference in search agents; mitigation method, no causal isolation |

### The open lane (2026-08-17)

Nobody has: (1) token-level **content-class accounting** of agent context
(recoverable vs trajectory-exclusive) at scale; (2) **matched-volume causal
knockouts** by content class; (3) the **presence/position/freshness
three-way** (copy vs re-run vs remove-filler) separation; (4) **white-box
attention evidence** for any of it (all behavioral; we self-host); (5) a
**cost ledger** (interference removed − fault cost − dirty losses) fit on a
policy design space and tested against the method zoo above; (6) the F2
anomaly. TRACE counts faults; nobody prices them. CoACT bets the boundary;
nobody measures it.

## Scan log

- **2026-08-17 (later)** — coherence/staleness collision scan for the
  adopted "Context Coherence" direction (see
  [HANDOFF_COHERENCE.md](HANDOFF_COHERENCE.md)). Added STALE, Less Context
  Better Agents, ProcCtrlBench, MemTX, 2608.10743 to the Tier 4 table.
  Verdict: phenomenon named, mechanism unmeasured — lineages, causal
  isolation, invalidation-driven compression, and the cross-model reversal
  all unclaimed. Also verified from disk: Devstral reversal (FC@∞ 71.7% vs
  OTRC@∞ 38.3%, n=60/arm) and staleness prevalence (~25% of observation
  chars stale, 45% of test results superseded; 25-trajectory probe).
- **2026-08-17** — agent-side context-management sweep for the ICLR
  "working set" direction. Added Tier 4 (TRACE, CoACT, ARC, ACON, AgentDiet,
  + neighborhood table). Verdict: method lane crowded, causal/ledger lane
  open. E2 must price faults, not count them (TRACE counts); E3 must be
  positioned against CoACT's next-action-preservation bet.
- **2026-08-10** — **Free Deletion direction archived by user decision**
  (see ARCHIVED_FREE_DELETION.md in ~/agentCtx_attic/exp_plans/); next MLSys
  direction TBD. This file stays live — Tiers 0–3a remain the landscape
  reference for whatever direction replaces it.
- **2026-08-06** — deep read for healing v1: CacheBlend mechanics, EPIC v3,
  StreamingLLM/SinkCache/OpenVINO position handling, scoop sweep. Added
  Tier 3a (Leyline, Irminsul, KVEraser, KV-Splice, 2608.00902). SAGA and
  Pythia scanned — scheduling only, no collision (closes the 2026-08-03
  watch item). Verdict: partially scooped; repair lane still open.
- **2026-08-03** — searched: TokenCake, TokenPilot, prefix-cache invalidation
  from compression, agent-serving capacity, Autellix/InferCept/Parrot
  neighborhood. Added Tier 1 (3 papers) + Tier 2 (8 works). Trigger: MLSys
  pivot after ARR meta-review (resubmit).
