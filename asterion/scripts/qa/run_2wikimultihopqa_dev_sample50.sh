#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/../../.." && pwd)
RESOURCE_ROOT=${ASTERION_DCI_RESOURCE_ROOT:-$REPO_ROOT}
dataset="$RESOURCE_ROOT/data/dci-bench/data/2wikimultihopqa/test.jsonl"; corpus="$RESOURCE_ROOT/corpus/wiki_corpus"
[ -f "$dataset" ] || { echo "Asterion DCI dataset is unavailable" >&2; exit 2; }; [ -d "$corpus" ] || { echo "Asterion DCI corpus is unavailable" >&2; exit 2; }
command=(uv run --project "$REPO_ROOT/asterion" asterion-dci benchmark --profile qa.2wikimultihopqa --dataset "$dataset" --corpus "$corpus"); command+=("$@"); exec "${command[@]}"
