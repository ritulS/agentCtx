#!/usr/bin/env bash
# setup.sh — Run once after cloning to prepare the repo for experiments.
#
# What this does:
#   1. Initialises / updates the mini-swe-agent submodule
#   2. Applies patches/default_memory_hook.patch to mini-swe-agent's default.py
#      (adds the context-window memory primitive hook to DefaultAgent.query)
#   3. Creates a Python venv and installs all dependencies
#
# Usage:
#   bash setup.sh           # full setup (venv + patch)
#   bash setup.sh --patch   # re-apply patch only (skip venv creation)

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"
SUBMODULE="$REPO_ROOT/mini-swe-agent"
PATCH_FILE="$REPO_ROOT/patches/default_memory_hook.patch"
TARGET_FILE="$SUBMODULE/src/minisweagent/agents/default.py"
VENV_DIR="$REPO_ROOT/venv"

# ── colours ───────────────────────────────────────────────────────────────────
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
info()  { echo -e "${GREEN}[setup]${NC} $*"; }
warn()  { echo -e "${YELLOW}[setup]${NC} $*"; }
error() { echo -e "${RED}[setup]${NC} $*" >&2; exit 1; }

PATCH_ONLY=false
for arg in "$@"; do [[ "$arg" == "--patch" ]] && PATCH_ONLY=true; done

# ── 1. Submodule ──────────────────────────────────────────────────────────────
info "Initialising submodules..."
git -C "$REPO_ROOT" submodule update --init --recursive

# ── 2. Patch default.py ───────────────────────────────────────────────────────
info "Checking memory hook patch..."

# Idempotency check — if the hook is already present, skip
if grep -q "MSWEA_TOKEN_BUDGET" "$TARGET_FILE" 2>/dev/null; then
    warn "Patch already applied — skipping."
else
    info "Applying patches/default_memory_hook.patch..."
    git -C "$SUBMODULE" apply "$PATCH_FILE" \
        || error "Patch failed. The upstream default.py may have changed. Re-generate the patch with: cd mini-swe-agent && git diff > ../patches/default_memory_hook.patch"
    info "Patch applied successfully."
fi

[[ "$PATCH_ONLY" == true ]] && { info "Done (patch only)."; exit 0; }

# ── 3. Python venv ────────────────────────────────────────────────────────────
info "Creating venv at $VENV_DIR ..."
python3 -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"

info "Installing mini-swe-agent (editable) + litellm + tiktoken ..."
pip install --quiet --upgrade pip
pip install --quiet -e "$SUBMODULE"
pip install --quiet litellm tiktoken

info "Setup complete."
echo ""
echo "  Activate the venv:  source venv/bin/activate"
echo "  Start vLLM server:  bash scripts/run_full_experiment.sh  (see README)"
echo "  Run experiments:    python scripts/run_experiment.py"
