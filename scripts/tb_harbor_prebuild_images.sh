#!/usr/bin/env bash
# Prebuild migrated Terminal-Bench 1.0.1 images with rootless Podman.
#
# This bypasses Docker Compose/buildx, which cannot start its privileged
# BuildKit container under the borrowed rootless Podman installation. Main
# task images also receive uv so the verifier does not need apt/curl at
# runtime. By default, the only user-namespace workaround is disabling apt's
# privilege drop to the unmappable _apt uid. The more invasive chown/chgrp
# wrapper is opt-in (see ROOTLESS_CHOWN_WORKAROUND below).
#
# scripts/patch_tb_lchown.py is independent and may be used alongside this
# script. It patches legacy terminal-bench (venv-tb) host-to-container tar
# metadata; this script builds Harbor (venv-harbor) task images and does not
# modify either Python environment.
#
# Usage:
#   bash scripts/tb_harbor_prebuild_images.sh                 # all 80 tasks
#   bash scripts/tb_harbor_prebuild_images.sh hello-world     # selected tasks
#   FORCE=1 bash scripts/tb_harbor_prebuild_images.sh         # rebuild images
#   ROOTLESS_CHOWN_WORKAROUND=1 FORCE=1 \
#     bash scripts/tb_harbor_prebuild_images.sh <task>         # last resort
set -uo pipefail

WS="${AGENTCTX_WS:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
DATASET="${TB_HARBOR_DATASET:-$WS/data/tb1-harbor-0.1.1}"
PODMAN="${TB_PODMAN:-/home/rs67788/.local/bin/podman}"
PYTHON_BIN="${TB_PYTHON_BIN:-$WS/venv-harbor/bin/python}"
UV_BIN="${TB_UV_BIN:-$WS/.tools/uv}"
LOG="${TB_PREBUILD_LOG:-$WS/logs/tb1_harbor_prebuild.log}"
IMAGE_PREFIX="${TB_IMAGE_PREFIX:-tb1}"
FORCE="${FORCE:-0}"
ROOTLESS_CHOWN_WORKAROUND="${ROOTLESS_CHOWN_WORKAROUND:-0}"
SCRATCH="$(mktemp -d "${TMPDIR:-/tmp}/${IMAGE_PREFIX}-harbor-prebuild.XXXXXX")"
trap 'rm -rf "$SCRATCH"' EXIT

mkdir -p "$WS/logs"

for required in "$PODMAN" "$PYTHON_BIN" "$UV_BIN"; do
    if [[ ! -x "$required" ]]; then
        echo "[ERROR] Required executable not found: $required" >&2
        exit 1
    fi
done
if [[ ! -d "$DATASET" ]]; then
    echo "[ERROR] Dataset not found: $DATASET" >&2
    exit 1
fi

export PATH="$(dirname "$PODMAN"):$PATH"
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"

if [[ "$ROOTLESS_CHOWN_WORKAROUND" != "0" && "$ROOTLESS_CHOWN_WORKAROUND" != "1" ]]; then
    echo "[ERROR] ROOTLESS_CHOWN_WORKAROUND must be 0 or 1" >&2
    exit 1
fi

# Minimal default: apt normally drops privileges to _apt while downloading.
# A single-UID rootless user namespace cannot represent that uid, so retain
# root only for apt's download sandbox. This does not alter chown semantics.
APT_SHIM_B64="$(base64 -w0 <<'SHIMS'
mkdir -p /etc/apt/apt.conf.d
echo 'APT::Sandbox::User "root";' > /etc/apt/apt.conf.d/99-agentctx-userns.conf
SHIMS
)"

# Last-resort compatibility mode inherited from tb_prebuild_images.sh. It can
# make package maintainer scripts complete in a single-UID namespace, but it
# changes filesystem ownership semantics and must not be used silently in a
# paper experiment. It is deliberately disabled by default.
CHOWN_SHIM_B64="$(base64 -w0 <<'SHIMS'
for c in chown chgrp; do
  p=$(command -v "$c" 2>/dev/null) || continue
  grep -q agentctx-wrapper "$p" 2>/dev/null && continue
  mv "$p" "$p.agentctx-real" || continue
  {
    echo '#!/bin/sh'
    echo '# agentctx-wrapper'
    echo "$p.agentctx-real \"\$@\" 2>/dev/null || true"
  } > "$p"
  chmod 755 "$p"
done
SHIMS
)"

log() { echo "[$(date)] $*" | tee -a "$LOG"; }

image_exists() {
    [[ "$FORCE" != "1" ]] && "$PODMAN" image exists "$1" >/dev/null 2>&1
}

build_context() {
    local task="$1" service="$2" source_context="$3" dockerfile_rel="$4" image="$5" bake_uv="$6"
    local context="$SCRATCH/${task}-${service}"

    if image_exists "$image"; then
        log "[$task/$service] cached: $image"
        return 0
    fi

    mkdir -p "$context"
    cp -a "$source_context/." "$context/"
    local dockerfile="$context/$dockerfile_rel"
    if [[ ! -f "$dockerfile" ]]; then
        log "[$task/$service] ERROR: Dockerfile not found: $dockerfile_rel"
        return 1
    fi

    # This host deliberately has no unqualified-search registries configured.
    # Make Docker Hub references explicit without changing stage aliases or
    # already-qualified/local image names.
    "$PYTHON_BIN" - "$dockerfile" <<'PY'
import re
import sys
from pathlib import Path

path = Path(sys.argv[1])
text = path.read_text()

def qualify(image: str) -> str:
    if image == "scratch":
        return image
    # A colon in a slashless reference is an image tag (ubuntu:latest), not
    # a registry port. Slashless base-image references are Docker Hub names.
    if "/" not in image:
        return f"docker.io/{image}"
    first = image.split("/", 1)[0]
    if first == "localhost" or "." in first or ":" in first:
        return image
    return f"docker.io/{image}"

lines = []
for line in text.splitlines(keepends=True):
    # Keep the original line ending. re.sub/re.match with ``$`` may match
    # immediately before a trailing newline; rebuilding only the capture
    # groups would then concatenate FROM with the following instruction.
    ending = ""
    if line.endswith("\r\n"):
        line, ending = line[:-2], "\r\n"
    elif line.endswith("\n"):
        line, ending = line[:-1], "\n"

    match = re.match(
        r"^(\s*FROM(?:\s+--platform=\S+)?\s+)(\S+)(.*)$",
        line,
        flags=re.IGNORECASE,
    )
    if match:
        line = f"{match.group(1)}{qualify(match.group(2))}{match.group(3)}"

    def replace_copy(match: re.Match[str]) -> str:
        image = match.group(1)
        # A slash or tag identifies an external image; bare names are usually
        # Dockerfile stage aliases and must not be qualified.
        if "/" not in image and ":" not in image:
            return match.group(0)
        return f"--from={qualify(image)}"

    line = re.sub(r"--from=([^\s]+)", replace_copy, line)
    lines.append(line + ending)

path.write_text("".join(lines))
PY

    awk -v inject="RUN echo $APT_SHIM_B64 | base64 -d | sh" \
        '{print} /^FROM[[:space:]]/{print inject}' "$dockerfile" > "$dockerfile.tmp"
    mv "$dockerfile.tmp" "$dockerfile"

    if [[ "$ROOTLESS_CHOWN_WORKAROUND" == "1" ]]; then
        awk -v inject="RUN echo $CHOWN_SHIM_B64 | base64 -d | sh" \
            '{print} /^FROM[[:space:]]/{print inject}' "$dockerfile" > "$dockerfile.tmp"
        mv "$dockerfile.tmp" "$dockerfile"
    fi

    if [[ "$bake_uv" == "1" ]]; then
        cp "$UV_BIN" "$context/.agentctx-uv"
        {
            echo
            echo '# agentCtx rootless-Podman verifier support'
            echo 'USER root'
            echo 'COPY .agentctx-uv /root/.local/bin/uv'
            echo 'RUN chmod 755 /root/.local/bin/uv && ln -sf /root/.local/bin/uv /usr/local/bin/uv \
    && mkdir -p /etc/apt/apt.conf.d \
    && echo '\''APT::Sandbox::User "root";'\'' > /etc/apt/apt.conf.d/99-agentctx-userns.conf'
            echo 'ENV PATH="/root/.local/bin:${PATH}"'
        } >> "$dockerfile"
    fi

    log "[$task/$service] building: $image"
    if ! "$PODMAN" build --format docker -f "$dockerfile" -t "$image" "$context" \
        >>"$LOG" 2>&1; then
        log "[$task/$service] BUILD FAILED"
        return 1
    fi
    log "[$task/$service] OK"
}

if [[ "$#" -gt 0 ]]; then
    TASKS=("$@")
else
    mapfile -t TASKS < <(find "$DATASET" -mindepth 1 -maxdepth 1 -type d -printf '%f\n' | sort)
fi

if [[ "$ROOTLESS_CHOWN_WORKAROUND" == "1" ]]; then
    log "WARNING: invasive chown/chgrp compatibility mode enabled"
else
    log "rootless mode: apt-only (ownership semantics preserved)"
fi

OK=()
FAILED=()
for task in "${TASKS[@]}"; do
    task_dir="$DATASET/$task"
    env_dir="$task_dir/environment"
    if [[ ! -f "$task_dir/task.toml" || ! -f "$env_dir/Dockerfile" ]]; then
        log "[$task] ERROR: invalid migrated task directory"
        FAILED+=("$task")
        continue
    fi

    main_image="localhost/${IMAGE_PREFIX}-${task}-main:latest"
    service_args=()
    task_failed=0

    if ! build_context "$task" main "$env_dir" Dockerfile "$main_image" 1; then
        task_failed=1
    fi

    compose="$env_dir/docker-compose.yaml"
    if [[ -f "$compose" ]]; then
        while IFS=$'\t' read -r service context dockerfile; do
            [[ -n "$service" ]] || continue
            service_image="localhost/${IMAGE_PREFIX}-${task}-${service}:latest"
            if ! build_context "$task" "$service" "$env_dir/$context" "$dockerfile" "$service_image" 0; then
                task_failed=1
            else
                service_args+=(--service-image "$service=$service_image")
            fi
        done < <("$PYTHON_BIN" - "$compose" <<'PY'
import sys, yaml
payload = yaml.safe_load(open(sys.argv[1])) or {}
for name, service in (payload.get("services") or {}).items():
    if name == "main" or "build" not in service:
        continue
    build = service["build"]
    if isinstance(build, str):
        context, dockerfile = build, "Dockerfile"
    else:
        context = build.get("context", ".")
        dockerfile = build.get("dockerfile", "Dockerfile")
    print(name, context, dockerfile, sep="\t")
PY
        )
    fi

    if [[ "$task_failed" == "0" ]]; then
        "$PYTHON_BIN" "$WS/scripts/configure_tb_harbor_prebuilt.py" \
            --task-dir "$task_dir" --main-image "$main_image" "${service_args[@]}"
        OK+=("$task")
    else
        FAILED+=("$task")
    fi
done

log "prebuilt OK (${#OK[@]}): ${OK[*]:-none}"
log "failed (${#FAILED[@]}): ${FAILED[*]:-none}"
[[ "${#FAILED[@]}" -eq 0 ]]
