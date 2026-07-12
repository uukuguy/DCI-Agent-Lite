#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -ne 1 ]; then
    echo "Usage: $0 HYPOTHESIS_ID" >&2
    exit 2
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
STATE_DIR="$ROOT/docs/status/climb"
JOURNAL="$ROOT/docs/status/JOURNAL.md"
HYPOTHESIS_ID="$1"

python3 "$ROOT/tools/project_scope_check.py" --climb-hypothesis "$HYPOTHESIS_ID"

_sync_state() {
    python3 "$ROOT/tools/climb/regen-tree.py"
    set +e
    python3 "$ROOT/tools/climb/check-target.py"
    target_status=$?
    set -e
    if [ "$target_status" -eq 10 ]; then
        echo "[climb] target met; hard pause required." >&2
        exit 10
    fi
    return "$target_status"
}

cycle="$(python3 -c 'import json; print(json.load(open("docs/status/climb/session-state.json"))["last_cycle"] + 1)' )"
run_dir="$(bash "$ROOT/tools/climb/train.sh" "$HYPOTHESIS_ID")"
DCI_CLIMB_HYPOTHESIS_ID="$HYPOTHESIS_ID" \
    bash "$ROOT/tools/climb/eval-local.sh" "$run_dir" >/dev/null
python3 "$ROOT/tools/climb/decision-gate.py" \
    --local-eval-json "$run_dir/local-eval.json" >"$run_dir/decision.json"
decision="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["decision"])' "$run_dir/decision.json")"
if [ "$decision" = "PUSH" ]; then
    bash "$ROOT/tools/climb/push.sh" "$run_dir"
fi

python3 "$ROOT/tools/climb/record-cycle.py" \
    --state-dir "$STATE_DIR" \
    --journal "$JOURNAL" \
    --hypothesis-id "$HYPOTHESIS_ID" \
    --run-id "$(basename "$run_dir")" \
    --run-dir "$run_dir" \
    --cycle "$cycle"
_sync_state
