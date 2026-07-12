#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -ne 1 ]; then
    echo "Usage: $0 RUN_DIR" >&2
    exit 2
fi

RUN_DIR="$1"
cp "$RUN_DIR/local-eval.json" "$RUN_DIR/verification-artifact.json"
echo "[climb] local verification artifact ready: $RUN_DIR/verification-artifact.json"
