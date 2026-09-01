#!/usr/bin/env bash
set -euo pipefail

# Publish the generated Terminal-Bench coverage CSV from the main worktree to
# the dedicated data worktree/branch. Intended to be run from cron.
readonly SOURCE_WORKTREE="/home/ak58925/agentCtx"
readonly COVERAGE_BUILDER="${SOURCE_WORKTREE}/dashboard/build_coverage.py"
readonly SOURCE="${SOURCE_WORKTREE}/COVERAGE_TB.csv"
readonly DATA_WORKTREE="/home/ak58925/agentCtx-data"
readonly DATA_BRANCH="akiho-expansion-terminalbench-0829-data"
readonly REMOTE="origin"
readonly LOCK_FILE="/tmp/agentctx-${UID}-coverage-tb-sync.lock"

# cron normally has a minimal PATH.
export PATH="/usr/local/bin:/usr/bin:/bin"

exec 9>"${LOCK_FILE}"
if ! flock -n 9; then
    echo "Another COVERAGE_TB sync is already running; skipping."
    exit 0
fi

if [[ ! -f "${COVERAGE_BUILDER}" ]]; then
    echo "Coverage builder does not exist: ${COVERAGE_BUILDER}" >&2
    exit 1
fi

if [[ ! -d "${DATA_WORKTREE}" ]]; then
    echo "Data worktree does not exist: ${DATA_WORKTREE}" >&2
    exit 1
fi

current_branch="$(git -C "${DATA_WORKTREE}" branch --show-current)"
if [[ "${current_branch}" != "${DATA_BRANCH}" ]]; then
    echo "Unexpected branch in ${DATA_WORKTREE}: ${current_branch:-DETACHED}" >&2
    echo "Expected: ${DATA_BRANCH}" >&2
    exit 1
fi

# Rebuild both coverage files from the latest experiment results. With
# `set -e`, a build failure stops the script before copying or publishing.
echo "Rebuilding COVERAGE_TB.csv from the latest experiment results..."
(
    cd "${SOURCE_WORKTREE}"
    python3 "${COVERAGE_BUILDER}"
)

if [[ ! -f "${SOURCE}" ]]; then
    echo "Coverage builder did not produce: ${SOURCE}" >&2
    exit 1
fi

# Keep the publishing branch fast-forwarded before creating a new commit.
git -C "${DATA_WORKTREE}" pull --ff-only "${REMOTE}" "${DATA_BRANCH}"

destination="${DATA_WORKTREE}/COVERAGE_TB.csv"
if cmp -s "${SOURCE}" "${destination}"; then
    echo "COVERAGE_TB.csv is unchanged; nothing to publish."
    exit 0
fi

install -m 0644 "${SOURCE}" "${destination}"
git -C "${DATA_WORKTREE}" add -- COVERAGE_TB.csv

# Be defensive in case Git attributes or filters make the staged file equal.
if git -C "${DATA_WORKTREE}" diff --cached --quiet -- COVERAGE_TB.csv; then
    echo "No staged change after copying; nothing to publish."
    exit 0
fi

timestamp="$(date -u '+%Y-%m-%d %H:%M UTC')"
git -C "${DATA_WORKTREE}" commit -m "Update COVERAGE_TB.csv (${timestamp})"
git -C "${DATA_WORKTREE}" push "${REMOTE}" "${DATA_BRANCH}"

echo "Published COVERAGE_TB.csv to ${REMOTE}/${DATA_BRANCH}."
