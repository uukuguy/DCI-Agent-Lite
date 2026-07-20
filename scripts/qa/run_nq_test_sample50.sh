#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd "$SCRIPT_DIR/../.." && pwd)

uv run python "$REPO_ROOT/scripts/bcplus_eval/run_bcplus_eval.py" \
  --dataset "$REPO_ROOT/data/dci-bench/data/nq/test.jsonl" \
  --output-root "$REPO_ROOT/outputs/qa/openai_nq_test_sample50" \
  --corpus-dir "$REPO_ROOT/corpus/wiki_corpus" \
  --tools read,bash \
  --max-turns 300 \
  --max-concurrency 5 \
  --runtime-context-level level3 \
  --pi-thinking-level high \
  --node-max-old-space-size-mb 8192 \
  "$@"
