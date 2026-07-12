#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -ne 1 ]; then
    echo "Usage: $0 HYPOTHESIS_ID" >&2
    exit 2
fi
if [ "$1" != "H-001" ]; then
    echo "ERROR: train adapter is currently defined only for H-001." >&2
    exit 2
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
run_id="$(date '+%Y%m%d-%H%M%S')-dci-climb-h001"
run_dir="$ROOT/runs/climb/$run_id"
mkdir -p "$run_dir"

cat >"$run_dir/manifest.json" <<EOF
{
  "cycle": 1,
  "hypothesis_id": "H-001",
  "paradigm": "external-git-lock",
  "run_id": "$run_id"
}
EOF

if ! python3 -m unittest tests.test_setup_pi -v >"$run_dir/train.log" 2>&1; then
    echo "ERROR: H-001 setup-policy training/acceptance suite failed; see $run_dir/train.log" >&2
    exit 1
fi
printf '%s\n' "$run_dir"
