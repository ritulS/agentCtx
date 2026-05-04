# Abstract — "No Free Compression: Cost Displacement and Adaptive Intervention in LLM Agents"

> **Version history:** update notes at bottom of file.

---

## Current Abstract

Long-horizon LLM agents routinely exhaust their context window, and compression — whether by truncation or learned summarization — has become standard infrastructure for extending agent operation. The dominant evaluation framework for these methods asks two questions: how much does it reduce token usage, and does it maintain task performance? We argue this framework is incomplete in a way that matters at deployment scale. Using 990 controlled agent runs on SWE-bench tasks, we show that compression does not eliminate resource cost — it displaces it onto operational dimensions the standard metrics do not measure: step consumption, wall-clock time, and a cascade failure mode in which repeated compression events drive runs to exhaustion. Gross token savings of 40–58% collapse to **14–42% net** once this waste is accounted for, and 68–73% of compression-induced failures occur on tasks the uncompressed agent handles successfully — ruling out task difficulty as an explanation. The failure mode is predictable from design choice: deterministic methods reliably exhaust step budgets while LLM-based methods reliably exhaust wall-clock time — a distinction that has direct implications for which deployment constraints a compression strategy puts at risk. Trigger timing, not strategy, is the dominant predictor of failure (Cohen's d = 1.61). These findings suggest that evaluating context compression by accuracy-on-completion alone systematically underestimates operational risk and that a broader evaluation surface — capturing net savings, cascade rate, and the resource dimension each strategy exhausts — is necessary to make informed deployment decisions.

---

## Version History

| Version | Date | Change |
|---|---|---|
| v1 | 2026-04-06 | Initial draft (3 conditions: FC, TR, SU). Net savings: TR 15.6%, SU 38.3%. |
| v2 | 2026-04-07 | Added circuit-breaker paragraph and CIS framing. |
| v3 | 2026-04-13 | Full rewrite for 5 conditions (990 runs). Outward-facing framing: evaluation framework critique replaces solution narrative. Net savings updated: TR 13.8%, SU 35.0%, SS 42.0%, TRC 39.7%. CIS and circuit-breaker removed from abstract. Mechanism sentence replaced with predictability framing (Option A). |
