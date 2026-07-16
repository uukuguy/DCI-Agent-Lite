#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/../../.." && pwd)
if [ -f "$REPO_ROOT/.env" ]; then set -a; source "$REPO_ROOT/.env"; set +a; fi
dataset="$REPO_ROOT/data/dci-bench/data/bamboogle/test.jsonl"; corpus="$REPO_ROOT/corpus/wiki_corpus"
[ -f "$dataset" ] || { echo "Asterion DCI dataset is unavailable" >&2; exit 2; }; [ -d "$corpus" ] || { echo "Asterion DCI corpus is unavailable" >&2; exit 2; }
command=(asterion-dci benchmark --profile qa.bamboogle --dataset "$dataset" --corpus "$corpus"); if [[ -n "${ASTERION_DCI_BATCH_LIMIT:-}" ]]; then command+=(--limit "$ASTERION_DCI_BATCH_LIMIT"); fi; command+=("$@"); exec "${command[@]}"
