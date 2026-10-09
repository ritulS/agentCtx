#!/usr/bin/env bash
# Machine profiles for the shell launchers: one name that fixes how many GPUs
# the Qwen3.5-35B-A3B server takes and how many agent runs the SWE-bench
# launchers drive against it. Nothing changes unless AGENTCTX_PROFILE is set,
# so Dobby's production serving (GPUs 0-3, TP=4, 16 workers) stays the default.
#
#   AGENTCTX_PROFILE=albus-swe   Albus (8x A6000 48 GB): the server on all 8 GPUs
#                                (--tensor-parallel-size 8) and 8 concurrent runs
#                                (--max-workers 8) in the r2 SWE-bench launchers.
#
# Usage (after `source .../lib/logpaths.sh`):
#     source "$(dirname "${BASH_SOURCE[0]}")/../lib/profiles.sh"
#     agentctx_profile
#     CUDA_DEVICES="${PROFILE_CUDA_DEVICES:-0,1,2,3}"     # serving scripts
#     TP_SIZE="${PROFILE_TP_SIZE:-4}"
#     MAX_WORKERS="${MAX_WORKERS:-${PROFILE_MAX_WORKERS:-16}}"   # launchers
#
# An explicit MAX_WORKERS still wins over the profile. An unknown profile name
# is an error, so a typo cannot silently fall back to the Dobby defaults.

agentctx_profile() {
    PROFILE="${AGENTCTX_PROFILE:-}"
    PROFILE_CUDA_DEVICES=""
    PROFILE_TP_SIZE=""
    PROFILE_MAX_WORKERS=""
    case "$PROFILE" in
        "") ;;
        albus-swe)
            PROFILE_CUDA_DEVICES="0,1,2,3,4,5,6,7"
            PROFILE_TP_SIZE=8
            PROFILE_MAX_WORKERS=8
            ;;
        *)
            echo "[ERROR] unknown AGENTCTX_PROFILE '$PROFILE'; known: albus-swe (or unset for the Dobby defaults)" >&2
            return 1
            ;;
    esac
}

profile_status() {
    if [[ -n "$PROFILE" ]]; then
        echo "profile $PROFILE (GPUs ${PROFILE_CUDA_DEVICES}, TP=${PROFILE_TP_SIZE}, ${PROFILE_MAX_WORKERS} workers)"
    else
        echo "no profile (Dobby defaults)"
    fi
}
