#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/../../.." && pwd)
if [ -f "$REPO_ROOT/.env" ]; then set -a; source "$REPO_ROOT/.env"; set +a; fi
dataset="$REPO_ROOT/data/bcplus_qa.jsonl"
corpus="$REPO_ROOT/corpus/bc_plus_docs"
[ -f "$dataset" ] || { echo "Asterion DCI dataset is unavailable" >&2; exit 2; }
[ -d "$corpus" ] || { echo "Asterion DCI corpus is unavailable" >&2; exit 2; }
level=${1:-"level3"}
if (($# > 0)); then shift; fi
thinking_level=""
if (($# > 0)) && [[ "$1" != --* ]]; then thinking_level=$1; shift; fi
case "$level" in
  level0|level1|level2|level3|level4|level5|legacy) ;;
  *) echo "Asterion DCI context level is invalid" >&2; exit 2 ;;
esac
case "$thinking_level" in
  ""|off|minimal|low|medium|high|xhigh) ;;
  *) echo "Asterion DCI thinking level is invalid" >&2; exit 2 ;;
esac
output_root="$REPO_ROOT/outputs/asterion/bcplus_eval/openai_${level}_concurrency10"
if [[ -n "$thinking_level" ]]; then output_root="${output_root}_thinking${thinking_level}"; fi
command=(asterion-dci benchmark --profile bcplus.openai --dataset "$dataset" --corpus "$corpus" --output-root "$output_root" --runtime-context-level "$level")
if [[ -n "$thinking_level" ]]; then command+=(--thinking-level "$thinking_level"); fi
if [[ -n "${ASTERION_DCI_BATCH_LIMIT:-}" ]]; then command+=(--limit "$ASTERION_DCI_BATCH_LIMIT"); fi
command+=("$@")
exec "${command[@]}"
