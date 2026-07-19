#!/usr/bin/env bash

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && git rev-parse --show-toplevel 2>/dev/null)"
if [ -z "$REPO_ROOT" ]; then
    REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    while [ "$REPO_ROOT" != "/" ] && [ ! -d "$REPO_ROOT/.git" ]; do
        REPO_ROOT="$(dirname "$REPO_ROOT")"
    done
fi
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd "$SCRIPT_DIR/../.." && pwd)

uv run python "$REPO_ROOT/scripts/bcplus_eval/run_bcplus_eval.py" \
  --dataset "$REPO_ROOT/data/bcplus_qa.jsonl" \
  --output-root "$REPO_ROOT/outputs/bcplus_eval/openai_L3" \
  --corpus-dir "$REPO_ROOT/corpus/bc_plus_docs" \
  --tools read,bash \
  --max-turns 300 \
  --max-concurrency 10 \
  --runtime-context-level level3 \
  --pi-thinking-level high \
  --node-max-old-space-size-mb 8192 \
  "$@"
