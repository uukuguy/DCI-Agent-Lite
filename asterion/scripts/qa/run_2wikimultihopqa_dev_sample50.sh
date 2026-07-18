#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/../../.." && pwd)
dataset="$REPO_ROOT/data/dci-bench/data/2wikimultihopqa/test.jsonl"; corpus="$REPO_ROOT/corpus/wiki_corpus"
[ -f "$dataset" ] || { echo "Asterion DCI dataset is unavailable" >&2; exit 2; }; [ -d "$corpus" ] || { echo "Asterion DCI corpus is unavailable" >&2; exit 2; }
command=(asterion-dci benchmark --profile qa.2wikimultihopqa --dataset "$dataset" --corpus "$corpus"); command+=("$@"); exec "${command[@]}"
