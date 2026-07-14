#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd); REPO_ROOT=$(cd "$SCRIPT_DIR/../../.." && pwd)
if [ -f "$REPO_ROOT/.env" ]; then set -a; source "$REPO_ROOT/.env"; set +a; fi
dataset="$REPO_ROOT/data/dci-bench/data/bright_economics/economics_full.jsonl"; corpus="$REPO_ROOT/corpus/bright_corpus/economics"
[ -f "$dataset" ] || { echo "Asterion DCI dataset is unavailable" >&2; exit 2; }; [ -d "$corpus" ] || { echo "Asterion DCI corpus is unavailable" >&2; exit 2; }
command=(asterion-dci benchmark --profile bright.economics --dataset "$dataset" --corpus "$corpus"); if [[ -n "${ASTERION_DCI_BATCH_LIMIT:-}" ]]; then command+=(--limit "$ASTERION_DCI_BATCH_LIMIT"); fi; command+=("$@"); exec "${command[@]}"
