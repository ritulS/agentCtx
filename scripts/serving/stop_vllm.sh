#!/usr/bin/env bash
# Stop a vLLM server started by scripts/start_vllm_*.sh, including its
# EngineCore and tensor-parallel workers.
#
# `kill "$(cat <pidfile>)"` only signals the API server. If that process dies
# without shutting its engine down, the EngineCore/Worker_TP* processes stay
# alive as orphans and keep their GPU memory, so the next server fails with
# "Free memory on device ... is less than desired GPU memory utilization".
# The start scripts launch the server with `setsid`, so every process of one
# server shares the process group whose id is the PID in the pid file; this
# script signals that whole group and waits for it to disappear.
#
# Usage:  bash scripts/serving/stop_vllm.sh logs/servers/vllm_summarizer_qwen35-9b.pid
#         bash scripts/serving/stop_vllm.sh logs/servers/vllm_qwen35.pid
set -euo pipefail

PID_FILE="${1:-}"
[[ -n "$PID_FILE" && -f "$PID_FILE" ]] || { echo "Usage: $0 <pid file>" >&2; exit 2; }
PGID="$(tr -d '[:space:]' < "$PID_FILE")"
[[ "$PGID" =~ ^[1-9][0-9]*$ ]] || { echo "[ERROR] $PID_FILE does not contain a PID: $PGID" >&2; exit 1; }

members() { ps -eo pid=,pgid= | awk -v g="$PGID" '$2 == g {print $1}'; }

if [[ -z "$(members)" ]]; then
    echo "No process left in group $PGID; removing $PID_FILE."
    rm -f "$PID_FILE"
    exit 0
fi

# Refuse to signal a recycled PID: the group must belong to a vLLM server.
if ! ps -o cmd= -g "$PGID" 2>/dev/null | grep -qi "vllm"; then
    echo "[ERROR] Process group $PGID does not look like a vLLM server:" >&2
    ps -o pid,pgid,cmd -g "$PGID" >&2 || true
    exit 1
fi

echo "Stopping vLLM process group $PGID: $(members | tr '\n' ' ')"
kill -TERM -- "-$PGID" 2>/dev/null || true
for _ in $(seq 1 60); do
    [[ -z "$(members)" ]] && break
    sleep 1
done
if [[ -n "$(members)" ]]; then
    echo "Still alive after 60s, sending KILL: $(members | tr '\n' ' ')"
    kill -KILL -- "-$PGID" 2>/dev/null || true
    sleep 2
fi
[[ -z "$(members)" ]] || { echo "[ERROR] Could not stop: $(members | tr '\n' ' ')" >&2; exit 1; }
rm -f "$PID_FILE"
echo "Stopped. GPU memory now:"
nvidia-smi --query-gpu=index,memory.used --format=csv,noheader
