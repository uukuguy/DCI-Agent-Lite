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
    H-008)
        first_dimension="config_only_safety"
        second_dimension="dotenv_source"
        third_dimension="shadow_warning"
        fourth_dimension="make_and_adapter"
        immutable_test="tests.test_check_judge.CheckJudgeTests.test_config_only_skips_preflight_request"
        repeat_test="tests.test_check_judge.CheckJudgeTests.test_key_provenance_reports_dotenv_source"
        dirty_test="tests.test_check_judge.CheckJudgeTests.test_key_provenance_warns_when_process_shadows_dotenv"
        override_test="tests.test_check_judge.CheckJudgeTests.test_make_target_runs_config_only_preflight"
        ;;
    H-009)
        first_dimension="strict_schema_shape"
        second_dimension="default_compatibility"
        third_dimension="cache_identity"
        fourth_dimension="adapter_integration"
        immutable_test="tests.test_judge.JudgeTransportTests.test_responses_can_opt_into_strict_judge_schema"
        repeat_test="tests.test_judge.JudgeTransportTests.test_responses_request_keeps_the_common_compatible_subset"
        dirty_test="tests.test_judge.JudgeResultReuseTests.test_backend_identity_is_part_of_result_reuse"
        override_test="tests.test_climb_tools.ClimbToolTests.test_h009_train_checks_strict_schema"
        ;;
    H-010)
        first_dimension="fingerprint_shape"
        second_dimension="result_persistence"
        third_dimension="reuse_contract"
        fourth_dimension="adapter_integration"
        immutable_test="tests.test_judge.JudgeTransportTests.test_judge_request_fingerprint_is_deterministic_and_endpoint_sensitive"
        repeat_test="tests.test_judge.JudgeTransportTests.test_chat_completions_request_and_response_are_normalized"
        dirty_test="tests.test_judge.JudgeResultReuseTests.test_backend_identity_is_part_of_result_reuse"
        override_test="tests.test_climb_tools.ClimbToolTests.test_h010_train_checks_request_fingerprints"
        ;;
    H-011)
        first_dimension="invalid_response_redaction"
        second_dimension="http_error_redaction"
        third_dimension="retry_contract"
        fourth_dimension="adapter_integration"
        immutable_test="tests.test_judge.JudgeTransportTests.test_invalid_structured_output_error_does_not_echo_provider_body"
        repeat_test="tests.test_judge.JudgeTransportTests.test_http_error_does_not_echo_provider_error_body"
        dirty_test="tests.test_judge.JudgeTransportTests.test_invalid_structured_output_is_retried_once"
        override_test="tests.test_climb_tools.ClimbToolTests.test_h011_train_checks_malformed_response_redaction"
        ;;
    H-012)
        first_dimension="safe_result_projection"
        second_dimension="invalid_error_redaction"
        third_dimension="http_error_redaction"
        fourth_dimension="adapter_integration"
        immutable_test="tests.test_judge.JudgeTransportTests.test_chat_completions_request_and_response_are_normalized"
        repeat_test="tests.test_judge.JudgeTransportTests.test_invalid_structured_output_error_does_not_echo_provider_body"
        dirty_test="tests.test_judge.JudgeTransportTests.test_http_error_does_not_echo_provider_error_body"
        override_test="tests.test_climb_tools.ClimbToolTests.test_h012_train_checks_judge_artifact_privacy"
        ;;
    H-013)
        first_dimension="matching_identity_reuse"
        second_dimension="legacy_rejection"
        third_dimension="incomplete_rejection"
        fourth_dimension="adapter_integration"
        immutable_test="tests.test_judge.JudgeResultReuseTests.test_backend_identity_is_part_of_result_reuse"
        repeat_test="tests.test_judge.JudgeResultReuseTests.test_backend_identity_is_part_of_result_reuse"
        dirty_test="tests.test_judge.JudgeResultReuseTests.test_backend_identity_is_part_of_result_reuse"
        override_test="tests.test_climb_tools.ClimbToolTests.test_h013_train_checks_complete_judge_cache_results"
        ;;
    H-014)
        first_dimension="input_text_redaction"
        second_dimension="result_fingerprint"
        third_dimension="cache_reuse"
        fourth_dimension="adapter_integration"
        immutable_test="tests.test_judge.JudgeTransportTests.test_chat_completions_request_and_response_are_normalized"
        repeat_test="tests.test_judge.JudgeTransportTests.test_judge_request_fingerprint_is_deterministic_and_endpoint_sensitive"
        dirty_test="tests.test_judge.JudgeResultReuseTests.test_backend_identity_is_part_of_result_reuse"
        override_test="tests.test_climb_tools.ClimbToolTests.test_h014_train_checks_judge_input_privacy"
        ;;
    H-015)
        first_dimension="credential_rejection"
        second_dimension="query_rejection"
        third_dimension="fragment_rejection"
        fourth_dimension="adapter_integration"
        immutable_test="tests.test_judge.JudgeConfigTests.test_base_url_rejects_embedded_credentials_or_query_data"
        repeat_test="tests.test_judge.JudgeConfigTests.test_base_url_rejects_embedded_credentials_or_query_data"
        dirty_test="tests.test_judge.JudgeConfigTests.test_base_url_rejects_embedded_credentials_or_query_data"
        override_test="tests.test_climb_tools.ClimbToolTests.test_cycle_adapter_shell_scripts_pass_syntax_validation"
        ;;
    H-016)
        first_dimension="origin_rejection"
        second_dimension="existing_url_safety"
        third_dimension="compatible_http_origins"
        fourth_dimension="adapter_integration"
        immutable_test="tests.test_judge.JudgeConfigTests.test_base_url_requires_an_absolute_http_origin"
        repeat_test="tests.test_judge.JudgeConfigTests.test_base_url_rejects_embedded_credentials_or_query_data"
        dirty_test="tests.test_judge.JudgeConfigTests.test_base_url_requires_an_absolute_http_origin"
        override_test="tests.test_climb_tools.ClimbToolTests.test_h016_train_checks_judge_origin_validation"
        ;;
    H-017)
        first_dimension="redirect_rejection"
        second_dimension="safe_redirect_error"
        third_dimension="normal_transport"
        fourth_dimension="adapter_integration"
        immutable_test="tests.test_judge.JudgeTransportTests.test_judge_transport_rejects_automatic_redirects"
        repeat_test="tests.test_judge.JudgeTransportTests.test_http_error_does_not_echo_provider_error_body"
        dirty_test="tests.test_judge.JudgeTransportTests.test_chat_completions_request_and_response_are_normalized"
        override_test="tests.test_climb_tools.ClimbToolTests.test_h017_train_checks_judge_redirect_containment"
        ;;
    H-018)
        first_dimension="storage_default"
        second_dimension="storage_opt_in_and_identity"
        third_dimension="compatible_payload"
        fourth_dimension="adapter_integration"
        immutable_test="tests.test_judge.JudgeTransportTests.test_official_responses_disable_server_storage_by_default"
        repeat_test="tests.test_judge.JudgeTransportTests.test_official_responses_disable_server_storage_by_default"
        dirty_test="tests.test_judge.JudgeTransportTests.test_compatible_responses_request_omits_storage_control"
        override_test="tests.test_climb_tools.ClimbToolTests.test_h018_train_checks_official_responses_retention"
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
