#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -ne 1 ]; then
    echo "Usage: $0 RUN_DIR" >&2
    exit 2
fi

RUN_DIR="$1"
mkdir -p "$RUN_DIR"
PYTHON_BIN="${PYTHON:-}"
HYPOTHESIS_ID="${DCI_CLIMB_HYPOTHESIS_ID:-H-001}"

run_python() {
    if [ -n "$PYTHON_BIN" ]; then
        "$PYTHON_BIN" "$@"
    else
        uv run python "$@"
    fi
}

run_dimension() {
    name="$1"
    test_name="$2"
    if run_python -m unittest "$test_name" -v >"$RUN_DIR/$name.log" 2>&1; then
        printf '1'
    else
        printf '0'
    fi
}

case "$HYPOTHESIS_ID" in
    H-001)
        first_dimension="immutable_resolution"
        second_dimension="repeat_validation"
        third_dimension="dirty_checkout_safety"
        fourth_dimension="override_compatibility"
        immutable_test="tests.test_setup_pi.PiSetupTests.test_new_checkout_uses_locked_commit"
        repeat_test="tests.test_setup_pi.PiSetupTests.test_built_checkout_at_pin_is_unchanged"
        dirty_test="tests.test_setup_pi.PiSetupTests.test_dirty_mismatched_checkout_fails_without_mutation"
        override_test="tests.test_setup_pi.PiSetupTests.test_revision_override_selects_exact_commit"
        ;;
    H-002)
        first_dimension="immutable_resolution"
        second_dimension="repeat_validation"
        third_dimension="dirty_checkout_safety"
        fourth_dimension="override_compatibility"
        immutable_test="tests.test_setup_pi.PiSetupTests.test_check_mode_rejects_mismatch_without_mutation"
        repeat_test="tests.test_setup_pi.PiSetupTests.test_check_mode_does_not_clone_missing_checkout"
        dirty_test="tests.test_setup_pi.PiSetupTests.test_check_mode_accepts_matching_dirty_checkout_without_mutation"
        override_test="tests.test_setup_pi.PiSetupTests.test_repository_docs_use_the_canonical_revision_lock"
        ;;
    H-003)
        first_dimension="immutable_resolution"
        second_dimension="repeat_validation"
        third_dimension="dirty_checkout_safety"
        fourth_dimension="override_compatibility"
        immutable_test="tests.test_pi_rpc_runner.PiRpcLifecycleTests.test_protocol_probe_validates_get_state_shape"
        repeat_test="tests.test_pi_rpc_runner.PiRpcLifecycleTests.test_protocol_probe_script_exposes_model_free_check"
        dirty_test="tests.test_pi_rpc_runner.PiRpcLifecycleTests.test_protocol_probe_is_documented_as_make_target"
        override_test="tests.test_pi_rpc_runner.PiRpcLifecycleTests.test_waits_for_agent_settled"
        ;;
    H-004)
        first_dimension="immutable_resolution"
        second_dimension="repeat_validation"
        third_dimension="dirty_checkout_safety"
        fourth_dimension="override_compatibility"
        immutable_test="tests.test_pi_rpc_runner.PiRpcLifecycleTests.test_pi_source_provenance_records_commit_lock_and_dirty_state"
        repeat_test="tests.test_pi_rpc_runner.PiRpcLifecycleTests.test_run_artifacts_include_pi_source_provenance"
        dirty_test="tests.test_pi_rpc_runner.PiRpcLifecycleTests.test_pi_source_provenance_is_documented"
        override_test="tests.test_pi_rpc_runner.PiRpcLifecycleTests.test_protocol_probe_validates_get_state_shape"
        ;;
    H-005)
        first_dimension="immutable_resolution"
        second_dimension="repeat_validation"
        third_dimension="dirty_checkout_safety"
        fourth_dimension="override_compatibility"
        immutable_test="tests.test_pi_rpc_runner.PiRpcLifecycleTests.test_pi_source_warning_reports_expected_revision_mismatch"
        repeat_test="tests.test_pi_rpc_runner.PiRpcLifecycleTests.test_pi_source_warning_is_emitted_and_added_to_run_notes"
        dirty_test="tests.test_pi_rpc_runner.PiRpcLifecycleTests.test_pi_source_provenance_records_commit_lock_and_dirty_state"
        override_test="tests.test_pi_rpc_runner.PiRpcLifecycleTests.test_pi_source_provenance_is_documented"
        ;;
    H-006)
        first_dimension="shared_transport"
        second_dimension="missing_key_safety"
        third_dimension="safe_output"
        fourth_dimension="make_and_adapter"
        immutable_test="tests.test_check_judge.CheckJudgeTests.test_preflight_uses_shared_judge_transport"
        repeat_test="tests.test_check_judge.CheckJudgeTests.test_preflight_rejects_missing_api_key_before_request"
        dirty_test="tests.test_check_judge.CheckJudgeTests.test_main_outputs_only_safe_result_fields"
        override_test="tests.test_climb_tools.ClimbToolTests.test_h006_train_runs_the_live_judge_preflight"
        ;;
    H-007)
        first_dimension="dotenv_source"
        second_dimension="process_source"
        third_dimension="shadow_warning"
        fourth_dimension="safe_output"
        immutable_test="tests.test_check_judge.CheckJudgeTests.test_key_provenance_reports_dotenv_source"
        repeat_test="tests.test_check_judge.CheckJudgeTests.test_key_provenance_reports_process_environment_source"
        dirty_test="tests.test_check_judge.CheckJudgeTests.test_key_provenance_warns_when_process_shadows_dotenv"
        override_test="tests.test_check_judge.CheckJudgeTests.test_main_outputs_safe_key_provenance"
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
    "$first_dimension": $immutable_resolution,
    "$second_dimension": $repeat_validation,
    "$third_dimension": $dirty_checkout_safety,
    "$fourth_dimension": $override_compatibility
  }
}
EOF

cat "$RUN_DIR/local-eval.json"
[ "$total" -eq 4 ]
