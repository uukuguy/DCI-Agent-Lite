#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PI_REPO_URL="${DCI_PI_REPO_URL:-https://github.com/earendil-works/pi.git}"
PI_DIR="${DCI_PI_DIR:-$PROJECT_ROOT/pi}"
case "$PI_DIR" in
    /*) ;;
    *) PI_DIR="$PROJECT_ROOT/${PI_DIR#./}" ;;
esac

PI_LOCK_FILE="$PROJECT_ROOT/pi-revision.txt"
PI_REVISION="${DCI_PI_REVISION:-}"
if [ -z "$PI_REVISION" ]; then
    if [ ! -f "$PI_LOCK_FILE" ]; then
        echo "ERROR: Missing Pi revision lock: $PI_LOCK_FILE" >&2
        exit 2
    fi
    PI_REVISION="$(tr -d '[:space:]' < "$PI_LOCK_FILE")"
    case "$PI_REVISION" in
        ""|*[!0-9a-fA-F]*)
            echo "ERROR: $PI_LOCK_FILE must contain one full 40-character Git commit." >&2
            exit 2
            ;;
    esac
    if [ "${#PI_REVISION}" -ne 40 ]; then
        echo "ERROR: $PI_LOCK_FILE must contain one full 40-character Git commit." >&2
        exit 2
    fi
fi

source_changed=0
cloned=0
if [ ! -e "$PI_DIR" ]; then
    echo "==> Cloning Pi into $PI_DIR without selecting a moving branch..."
    mkdir -p "$(dirname "$PI_DIR")"
    git clone --no-checkout "$PI_REPO_URL" "$PI_DIR"
    cloned=1
elif ! git -C "$PI_DIR" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    echo "ERROR: DCI_PI_DIR is not a Git worktree: $PI_DIR" >&2
    exit 2
fi

desired_commit="$(
    git -C "$PI_DIR" rev-parse --verify "$PI_REVISION^{commit}" 2>/dev/null || true
)"
if [ -z "$desired_commit" ]; then
    echo "==> Fetching requested Pi revision $PI_REVISION..."
    if ! git -C "$PI_DIR" fetch --no-tags origin "$PI_REVISION"; then
        echo "ERROR: Cannot fetch Pi revision $PI_REVISION from $PI_REPO_URL." >&2
        exit 2
    fi
    desired_commit="$(
        git -C "$PI_DIR" rev-parse --verify "FETCH_HEAD^{commit}" 2>/dev/null || true
    )"
fi
if [ -z "$desired_commit" ]; then
    echo "ERROR: Cannot resolve Pi revision $PI_REVISION in $PI_DIR." >&2
    exit 2
fi

current_commit="$(git -C "$PI_DIR" rev-parse --verify HEAD 2>/dev/null || true)"
if [ "$cloned" -eq 1 ]; then
    git -C "$PI_DIR" checkout --detach "$desired_commit"
    source_changed=1
elif [ "$current_commit" != "$desired_commit" ]; then
    if [ -n "$(git -C "$PI_DIR" status --porcelain)" ]; then
        echo "ERROR: Pi checkout is dirty at $current_commit; refusing to switch to $desired_commit." >&2
        echo "       Preserve or commit those changes, or set DCI_PI_DIR to another checkout." >&2
        exit 3
    fi
    echo "==> Switching clean Pi checkout from $current_commit to $desired_commit..."
    git -C "$PI_DIR" checkout --detach "$desired_commit"
    source_changed=1
elif [ -n "$(git -C "$PI_DIR" status --porcelain)" ]; then
    echo "WARN: Pi is at the requested commit but contains local changes; leaving them untouched." >&2
fi

PI_CLI="$PI_DIR/packages/coding-agent/dist/cli.js"
if [ "$source_changed" -eq 1 ] || [ ! -f "$PI_CLI" ]; then
    echo "==> Installing Pi dependencies (npm install)..."
    (cd "$PI_DIR" && npm install)
    echo "==> Building Pi (coding-agent and its dependencies only)..."
    (cd "$PI_DIR/packages/tui" && npm run build)
    (cd "$PI_DIR/packages/ai" && npm run build)
    (cd "$PI_DIR/packages/agent" && npm run build)
    (cd "$PI_DIR/packages/coding-agent" && npm run build)
else
    echo "==> Pi CLI already built at verified commit $desired_commit; skipping build."
fi
