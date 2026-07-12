#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -ne 1 ]; then
    echo "Usage: $0 RUN_DIR" >&2
    exit 2
fi

RUN_DIR="$1"
mkdir -p "$RUN_DIR"
PYTHON_BIN="${PYTHON:-python3}"

run_dimension() {
    name="$1"
    test_name="$2"
    if "$PYTHON_BIN" -m unittest "$test_name" -v >"$RUN_DIR/$name.log" 2>&1; then
        printf '1'
    else
        printf '0'
    fi
}

immutable_resolution="$(run_dimension immutable_resolution tests.test_setup_pi.PiSetupTests.test_new_checkout_uses_locked_commit)"
repeat_validation="$(run_dimension repeat_validation tests.test_setup_pi.PiSetupTests.test_built_checkout_at_pin_is_unchanged)"
dirty_checkout_safety="$(run_dimension dirty_checkout_safety tests.test_setup_pi.PiSetupTests.test_dirty_mismatched_checkout_fails_without_mutation)"
override_compatibility="$(run_dimension override_compatibility tests.test_setup_pi.PiSetupTests.test_revision_override_selects_exact_commit)"
total=$((immutable_resolution + repeat_validation + dirty_checkout_safety + override_compatibility))

cat >"$RUN_DIR/local-eval.json" <<EOF
{
  "total": $total,
  "per_task": {
    "immutable_resolution": $immutable_resolution,
    "repeat_validation": $repeat_validation,
    "dirty_checkout_safety": $dirty_checkout_safety,
    "override_compatibility": $override_compatibility
  }
}
EOF

cat "$RUN_DIR/local-eval.json"
[ "$total" -eq 4 ]
