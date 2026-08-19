#!/bin/bash
# Prebuild terminal-bench task images natively with podman (workaround for
# docker-buildx-over-rootless-podman failing on this machine; see
# results/tbench/STATUS.md). For each task:
#   1. podman-compose build with the env vars tb's harness would set
#   2. bake the static `uv` binary + $HOME/.local/bin/env into the image so
#      tests/setup-uv-pytest.sh works without apt (single-UID userns: apt's
#      privilege drop to _apt fails, but the script tolerates it if uv exists)
#   3. retag as tb__<task>__client (+ docker.io/library alias) so
#      `tb run --no-rebuild` picks it up
# Usage: tb_prebuild_images.sh <task_id> [<task_id> ...]
set -u

DATASET_DIR="$HOME/.cache/terminal-bench/terminal-bench-core/0.1.1"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PODMAN_COMPOSE="$REPO_ROOT/venv-tb/bin/podman-compose"
UV_BIN="$HOME/.local/bin/uv"
SCRATCH="${TMPDIR:-/tmp}/tb-prebuild-$$"
mkdir -p "$SCRATCH"
trap 'rm -rf "$SCRATCH"' EXIT

FAILED=()
OK=()

# Userns-workaround payload injected into every Dockerfile stage (see loop).
SHIM_B64=$(base64 -w0 <<'SHIMS'
# Wrap chown/chgrp in place (dpkg maintainer scripts use a fixed PATH that
# skips /usr/local, so PATH shims are not enough). Failures are tolerated:
# in a single-UID userns most uids/gids are unmappable and files staying
# root-owned is fine for these containers.
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
mkdir -p /etc/apt/apt.conf.d
echo 'APT::Sandbox::User "root";' > /etc/apt/apt.conf.d/99-agentctx-userns.conf
SHIMS
)

for TASK in "$@"; do
    SRC_DIR="$DATASET_DIR/$TASK"
    if [ ! -f "$SRC_DIR/docker-compose.yaml" ]; then
        echo "[$TASK] SKIP: no docker-compose.yaml"
        FAILED+=("$TASK")
        continue
    fi

    # Build from a scratch copy with apt privilege-dropping disabled after
    # every FROM (apt's seteuid to _apt fails in a single-UID userns; keeping
    # apt as root is infra-only and preserves task semantics).
    TASK_DIR="$SCRATCH/ctx-$TASK"
    rm -rf "$TASK_DIR"
    cp -a "$SRC_DIR" "$TASK_DIR"
    # Injected after every FROM (single RUN, payload base64-encoded to dodge
    # Dockerfile/sed quoting):
    #  - apt: don't drop privileges (seteuid to _apt unmappable in single-UID ns)
    #  - chown/chgrp shims that tolerate failure (dpkg postinst scripts chown
    #    to users/groups whose uids are unmappable; files stay root-owned,
    #    which is what the container effectively runs as anyway)
    find "$TASK_DIR" -name "Dockerfile*" -type f | while read -r DF; do
        awk -v inj="RUN echo $SHIM_B64 | base64 -d | sh || true" \
            '{print} /^FROM /{print inj}' "$DF" > "$DF.tmp" && mv "$DF.tmp" "$DF"
    done

    export T_BENCH_TASK_DOCKER_CLIENT_IMAGE_NAME="tb__${TASK}__client"
    export T_BENCH_TASK_DOCKER_NAME_PREFIX="tb__${TASK}"
    export T_BENCH_TASK_DOCKER_CLIENT_CONTAINER_NAME="prebuild-${TASK}"
    export T_BENCH_TEST_DIR="/tests"
    export T_BENCH_CONTAINER_LOGS_PATH="/logs"
    export T_BENCH_CONTAINER_AGENT_LOGS_PATH="/agent-logs"
    export T_BENCH_TASK_LOGS_PATH="$SCRATCH/logs"
    export T_BENCH_TASK_AGENT_LOGS_PATH="$SCRATCH/logs"
    mkdir -p "$SCRATCH/logs"

    echo "[$TASK] building..."
    if ! "$PODMAN_COMPOSE" -f "$TASK_DIR/docker-compose.yaml" build >"$SCRATCH/$TASK.build.log" 2>&1; then
        echo "[$TASK] BUILD FAILED (see $SCRATCH/$TASK.build.log tail below)"
        tail -5 "$SCRATCH/$TASK.build.log"
        FAILED+=("$TASK")
        continue
    fi

    # Derived layer: bake uv so test setup does not need apt/curl.
    BAKE_DIR="$SCRATCH/bake-$TASK"
    mkdir -p "$BAKE_DIR"
    cp "$UV_BIN" "$BAKE_DIR/uv"
    cat > "$BAKE_DIR/env" <<'EOF'
#!/bin/sh
export PATH="$HOME/.local/bin:$PATH"
EOF
    cat > "$BAKE_DIR/Dockerfile" <<EOF
FROM localhost/tb__${TASK}__client:latest
COPY uv /root/.local/bin/uv
COPY env /root/.local/bin/env
RUN chmod +x /root/.local/bin/uv && ln -sf /root/.local/bin/uv /usr/local/bin/uv \\
    && mkdir -p /etc/apt/apt.conf.d \\
    && echo 'APT::Sandbox::User "root";' > /etc/apt/apt.conf.d/99-agentctx-userns.conf
EOF
    if ! podman build -q -t "tb__${TASK}__client:latest" "$BAKE_DIR" >"$SCRATCH/$TASK.bake.log" 2>&1; then
        echo "[$TASK] BAKE FAILED"
        tail -5 "$SCRATCH/$TASK.bake.log"
        FAILED+=("$TASK")
        continue
    fi
    podman tag "localhost/tb__${TASK}__client:latest" "docker.io/library/tb__${TASK}__client:latest" 2>/dev/null

    echo "[$TASK] OK"
    OK+=("$TASK")
done

echo
echo "prebuilt OK (${#OK[@]}): ${OK[*]:-none}"
echo "failed (${#FAILED[@]}): ${FAILED[*]:-none}"
[ ${#FAILED[@]} -eq 0 ]
