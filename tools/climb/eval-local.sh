#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -ne 1 ]; then
    echo "Usage: $0 RUN_DIR" >&2
    exit 2
fi

RUN_DIR="$1"
mkdir -p "$RUN_DIR"
PYTHON_BIN="${PYTHON:-python3}"
HYPOTHESIS_ID="${DCI_CLIMB_HYPOTHESIS_ID:-H-001}"

run_dimension() {
    name="$1"
    test_name="$2"
    if "$PYTHON_BIN" -m unittest "$test_name" -v >"$RUN_DIR/$name.log" 2>&1; then
        printf '1'
    else
        printf '0'
    fi
}

case "$HYPOTHESIS_ID" in
    H-001)
        immutable_test="tests.test_setup_pi.PiSetupTests.test_new_checkout_uses_locked_commit"
        repeat_test="tests.test_setup_pi.PiSetupTests.test_built_checkout_at_pin_is_unchanged"
        dirty_test="tests.test_setup_pi.PiSetupTests.test_dirty_mismatched_checkout_fails_without_mutation"
        override_test="tests.test_setup_pi.PiSetupTests.test_revision_override_selects_exact_commit"
        ;;
    H-002)
        immutable_test="tests.test_setup_pi.PiSetupTests.test_check_mode_rejects_mismatch_without_mutation"
        repeat_test="tests.test_setup_pi.PiSetupTests.test_check_mode_does_not_clone_missing_checkout"
        dirty_test="tests.test_setup_pi.PiSetupTests.test_check_mode_accepts_matching_dirty_checkout_without_mutation"
        override_test="tests.test_setup_pi.PiSetupTests.test_repository_docs_use_the_canonical_revision_lock"
        ;;
    *)
        echo "ERROR: no local evaluation contract for $HYPOTHESIS_ID" >&2
        exit 2
        ;;
esac

immutable_resolution="$(run_dimension immutable_resolution "$immutable_test")"
repeat_validation="$(run_dimension repeat_validation "$repeat_test")"
dirty_checkout_safety="$(run_dimension dirty_checkout_safety "$dirty_test")"
override_compatibility="$(run_dimension override_compatibility "$override_test")"
total=$((immutable_resolution + repeat_validation + dirty_checkout_safety + override_compatibility))

cat >"$RUN_DIR/local-eval.json" <<EOF
{
  "hypothesis_id": "$HYPOTHESIS_ID",
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
