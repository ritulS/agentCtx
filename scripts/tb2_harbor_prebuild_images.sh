#!/usr/bin/env bash
# Prebuild Terminal-Bench 2.0 main/sidecar images with rootless Podman.
#
# Unlike tb_harbor_prebuild_images.sh, this entry point never rewrites the
# source dataset. It creates a Harbor-ready working copy and changes only that
# copy's task.toml/docker-compose.yaml files to reference the prebuilt images.
#
# Usage:
#   TB2_HARBOR_SOURCE_DATASET=/path/to/terminal-bench-2 \
#     bash scripts/tb2_harbor_prebuild_images.sh [task-id ...]
#
# Defaults:
#   working copy: data/tb2-harbor-prebuilt-2.0
#   images:       localhost/tb2-<task>-<service>:latest
#
# Set TB2_REFRESH_WORKING_COPY=1 to replace the working copy from the source.
# This is intentionally refused when the destination was not created by this
# script.
set -euo pipefail

WS="${AGENTCTX_WS:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
SOURCE_DATASET="${TB2_HARBOR_SOURCE_DATASET:-}"
WORK_DATASET="${TB2_HARBOR_WORK_DATASET:-$WS/data/tb2-harbor-prebuilt-2.0}"
REFRESH="${TB2_REFRESH_WORKING_COPY:-0}"
MARKER=".agentctx-tb2-working-copy"

if [[ -z "$SOURCE_DATASET" ]]; then
    echo "[ERROR] Set TB2_HARBOR_SOURCE_DATASET to the downloaded terminal-bench@2.0 task directory." >&2
    exit 1
fi
if [[ ! -d "$SOURCE_DATASET" ]]; then
    echo "[ERROR] Source dataset not found: $SOURCE_DATASET" >&2
    exit 1
fi
if [[ "$REFRESH" != "0" && "$REFRESH" != "1" ]]; then
    echo "[ERROR] TB2_REFRESH_WORKING_COPY must be 0 or 1" >&2
    exit 1
fi

SOURCE_DATASET="$(cd "$SOURCE_DATASET" && pwd)"
if [[ -e "$WORK_DATASET" ]]; then
    WORK_DATASET="$(cd "$WORK_DATASET" && pwd)"
    if [[ "$SOURCE_DATASET" == "$WORK_DATASET" ]]; then
        echo "[ERROR] Source and working dataset must be different directories." >&2
        exit 1
    fi
    if [[ "$REFRESH" == "1" ]]; then
        if [[ ! -f "$WORK_DATASET/$MARKER" ]]; then
            echo "[ERROR] Refusing to replace an unmanaged directory: $WORK_DATASET" >&2
            exit 1
        fi
        rm -rf -- "$WORK_DATASET"
    fi
fi

if [[ ! -e "$WORK_DATASET" ]]; then
    parent="$(dirname "$WORK_DATASET")"
    mkdir -p "$parent"
    staging="$(mktemp -d "$parent/.tb2-harbor-copy.XXXXXX")"
    trap 'rm -rf -- "$staging"' EXIT
    cp -a "$SOURCE_DATASET/." "$staging/"
    : > "$staging/$MARKER"
    mv "$staging" "$WORK_DATASET"
    trap - EXIT
    echo "[INFO] Created TB2 working copy: $WORK_DATASET"
else
    if [[ ! -f "$WORK_DATASET/$MARKER" ]]; then
        echo "[ERROR] Existing working directory is not managed by this script: $WORK_DATASET" >&2
        exit 1
    fi
    echo "[INFO] Reusing TB2 working copy: $WORK_DATASET"
fi

export TB_HARBOR_DATASET="$WORK_DATASET"
export TB_IMAGE_PREFIX="${TB_IMAGE_PREFIX:-tb2}"
export TB_PREBUILD_LOG="${TB_PREBUILD_LOG:-$WS/logs/tb2_harbor_prebuild.log}"

exec bash "$WS/scripts/tb_harbor_prebuild_images.sh" "$@"
