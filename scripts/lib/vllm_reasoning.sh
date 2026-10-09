#!/usr/bin/env bash
# Reasoning-parser argument for the vLLM servers in scripts/serving/.
#
# Thinking models (Qwen3.5, GLM-4.7-Flash) emit their reasoning inline as
# "<think> ... </think>" and, without a parser, vLLM returns all of it in
# message.content. mini-swe-agent stores content verbatim, so the agent's
# history, the token-budget trigger (count_tokens on content) and the
# summarizer's input all carried the thinking text, and summarizer replies
# arrived with a "...</think>" preamble (experiments/r2/EXPERIMENT_LOG.md,
# 2026-09-26). With --reasoning-parser the server splits the reasoning into
# message.reasoning_content and leaves only the answer in content. The chat
# templates read reasoning_content back the same way they read inline think
# tags, so the prompt the model sees is unchanged.
#
# Usage (after `source .../lib/logpaths.sh`):
#     source "$(dirname "${BASH_SOURCE[0]}")/../lib/vllm_reasoning.sh"
#     reasoning_parser_args qwen3        # default parser for this server
#     ... "${REASONING_ARGS[@]}" ...     # in the vllm command line
#
# REASONING_PARSER=<name> overrides the default; REASONING_PARSER=none disables
# the parser (the pre-r2 / iclr26 serving behaviour). Parser names are the keys
# of vllm.reasoning's registry: qwen3 (Qwen3 / Qwen3.5, vLLM >= 0.17), glm47 or
# glm45 (GLM-4.5/4.6/4.7, vLLM >= 0.28). Devstral and Gemma-4 (thinking off in
# its template) do not need one.

reasoning_parser_args() {
    local default="${1:?reasoning_parser_args: pass the default parser name, or none}"
    REASONING_PARSER="${REASONING_PARSER:-$default}"
    REASONING_ARGS=()
    if [[ "$REASONING_PARSER" != "none" ]]; then
        REASONING_ARGS=(--reasoning-parser "$REASONING_PARSER")
    fi
}
