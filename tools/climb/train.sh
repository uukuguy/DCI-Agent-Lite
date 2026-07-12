#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -ne 1 ]; then
    echo "Usage: $0 HYPOTHESIS_ID" >&2
    exit 2
fi
case "$1" in
    H-001|H-002|H-003) ;;
    *)
        echo "ERROR: train adapter has no acceptance suite for $1." >&2
        exit 2
        ;;
esac

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
slug="$(printf '%s' "$1" | tr '[:upper:]' '[:lower:]' | tr -d '-')"
run_id="$(date '+%Y%m%d-%H%M%S')-dci-climb-$slug"
run_dir="$ROOT/runs/climb/$run_id"
mkdir -p "$run_dir"
paradigm="external-git-lock"
if [ "$1" = "H-003" ]; then
    paradigm="rpc-contract-probe"
fi

cat >"$run_dir/manifest.json" <<EOF
{
  "cycle": null,
  "hypothesis_id": "$1",
  "paradigm": "$paradigm",
  "run_id": "$run_id"
}
EOF

if [ "$1" = "H-003" ]; then
    if ! {
        uv run python -m unittest tests.test_pi_rpc_runner -v
        uv run python scripts/check_pi_rpc.py
    } >"$run_dir/train.log" 2>&1; then
        echo "ERROR: H-003 RPC compatibility probe failed; see $run_dir/train.log" >&2
        exit 1
    fi
elif ! uv run python -m unittest tests.test_setup_pi -v >"$run_dir/train.log" 2>&1; then
    echo "ERROR: $1 setup-policy training/acceptance suite failed; see $run_dir/train.log" >&2
    exit 1
fi
printf '%s\n' "$run_dir"
