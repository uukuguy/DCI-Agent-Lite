#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd "$SCRIPT_DIR/../.." && pwd)
level=${1:-"level3"}
if (($# > 0)); then shift; fi
concurrency="10"
node_heap_mb="8192"
thinking_level=""
if (($# > 0)) && [[ "$1" != --* ]]; then thinking_level=$1; shift; fi
output_root="$REPO_ROOT/outputs/bcplus_eval/openai_${level}_concurrency${concurrency}"
if [[ -n "$thinking_level" ]]; then
  output_root="${output_root}_thinking${thinking_level}"
fi

uv run python "$REPO_ROOT/scripts/bcplus_eval/run_bcplus_eval.py" \
  --dataset "$REPO_ROOT/data/bcplus_qa.jsonl" \
  --output-root "$output_root" \
  --corpus-dir "$REPO_ROOT/corpus/bc_plus_docs" \
  --tools read,bash \
  --max-turns 100 \
  --max-concurrency "$concurrency" \
  --pi-thinking-level "$thinking_level" \
  --runtime-context-level "$level" \
  --node-max-old-space-size-mb "$node_heap_mb" \
  "$@"


# bash scripts/bcplus_eval/run_bcplus_eval_openai.sh level0 > logs/bcplus_eval_openai_level0.log 2>&1 &
# bash scripts/bcplus_eval/run_bcplus_eval_openai.sh level1 medium > logs/bcplus_eval_openai_level1_medium.log 2>&1 &
# bash scripts/bcplus_eval/run_bcplus_eval_openai.sh level1 high > logs/bcplus_eval_openai_level1_high.log 2>&1 &
# bash scripts/bcplus_eval/run_bcplus_eval_openai.sh level2 > logs/bcplus_eval_openai_level2.log 2>&1 &
# bash scripts/bcplus_eval/run_bcplus_eval_openai.sh level3 > logs/bcplus_eval_openai_level3.log 2>&1 &
# bash scripts/bcplus_eval/run_bcplus_eval_openai.sh level4 > logs/bcplus_eval_openai_level4.log 2>&1 &
# bash scripts/bcplus_eval/run_bcplus_eval_openai.sh level5 > logs/bcplus_eval_openai_level5.log 2>&1 &
