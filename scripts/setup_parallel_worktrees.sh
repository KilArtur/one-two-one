#!/bin/bash
set -euo pipefail

INTEGRATION_BRANCH="${1:-integration/arthur-zakhar}"
ARTUR_BRANCH="${2:-dev/artur}"
ZAKHAR_BRANCH="${3:-dev/zakhar}"

ROOT_DIR="$(git rev-parse --show-toplevel)"
PARENT_DIR="$(dirname "$ROOT_DIR")"
REPO_NAME="$(basename "$ROOT_DIR")"

INTEGRATION_DIR="$PARENT_DIR/${REPO_NAME}-integration"
ARTUR_DIR="$PARENT_DIR/${REPO_NAME}-artur"
ZAKHAR_DIR="$PARENT_DIR/${REPO_NAME}-zakhar"

ensure_branch() {
    local branch="$1"
    local start_point="$2"
    if git show-ref --verify --quiet "refs/heads/$branch"; then
        return
    fi
    git branch "$branch" "$start_point"
}

ensure_worktree() {
    local dir="$1"
    local branch="$2"
    if git worktree list --porcelain | grep -Fxq "worktree $dir"; then
        return
    fi
    git worktree add "$dir" "$branch"
}

cd "$ROOT_DIR"

ensure_branch "$INTEGRATION_BRANCH" "main"
ensure_branch "$ARTUR_BRANCH" "$INTEGRATION_BRANCH"
ensure_branch "$ZAKHAR_BRANCH" "$INTEGRATION_BRANCH"

ensure_worktree "$INTEGRATION_DIR" "$INTEGRATION_BRANCH"
ensure_worktree "$ARTUR_DIR" "$ARTUR_BRANCH"
ensure_worktree "$ZAKHAR_DIR" "$ZAKHAR_BRANCH"

cat <<EOF
Created worktrees:
  integration: $INTEGRATION_DIR ($INTEGRATION_BRANCH)
  artur:       $ARTUR_DIR ($ARTUR_BRANCH)
  zakhar:      $ZAKHAR_DIR ($ZAKHAR_BRANCH)

Next:
  1. Push branches:
     git push -u origin $INTEGRATION_BRANCH $ARTUR_BRANCH $ZAKHAR_BRANCH
  2. Work in $ARTUR_DIR and tell Zakhar to work in branch $ZAKHAR_BRANCH.
EOF
