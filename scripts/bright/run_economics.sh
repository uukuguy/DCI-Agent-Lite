#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd "$SCRIPT_DIR/../.." && pwd)

uv run python "$REPO_ROOT/scripts/bcplus_eval/run_bcplus_eval.py" \
  --enable-ir \
  --dataset "$REPO_ROOT/data/dci-bench/data/bright_economics/economics_full.jsonl" \
  --output-root "$REPO_ROOT/outputs/bright/economics" \
  --corpus-dir "$REPO_ROOT/corpus/bright_corpus/economics" \
  --tools read,bash \
  --max-turns 300 \
  --max-concurrency 10 \
  --runtime-context-level level3 \
  --pi-thinking-level high \
  --node-max-old-space-size-mb 8192 \
  "$@"
