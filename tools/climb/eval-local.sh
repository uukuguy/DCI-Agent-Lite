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

run_rust_dimension() {
    name="$1"
    test_name="$2"
    if cargo test \
        --manifest-path packages/rust/controlled-executor/Cargo.toml \
        --test "$rust_suite" \
        "$test_name" -- --exact >"$RUN_DIR/$name.log" 2>&1; then
        printf '1'
    else
        printf '0'
    fi
}

run_closure_dimension() {
    name="$1"
    check="$2"
    case "$check" in
        operator_binary)
            command=(cargo test --manifest-path packages/rust/controlled-executor/Cargo.toml --test operator)
            ;;
        operator_docs)
            command=(uv run python -m unittest tests.test_climb_tools.ClimbToolTests.test_af050_operator_docs_and_root_verification_targets_exist -v)
            ;;
        root_test_target)
            command=(make test-rust-executor)
            ;;
        root_check_target)
            command=(make check-rust-executor)
            ;;
        assembly_typescript)
            command=(npm --prefix packages/typescript/asterion-runtime test)
            ;;
        assembly_docs)
            command=(uv run python -m unittest tests.test_application_assembly.AssemblyDocumentationTests -v)
            ;;
        assembly_non_execution)
            command=(node --test --test-name-pattern "keeps assembly resolution outside" packages/typescript/asterion-runtime/test/runtime.test.mjs)
            ;;
        assembly_closure)
            command=(uv run python -m unittest tests.test_climb_tools.ClimbToolTests.test_af090_h004_train_runs_full_framework_closure_gate -v)
            ;;
        asterion_closure)
            command=(uv run python -m unittest tests.test_climb_tools.ClimbToolTests.test_af095_h004_train_runs_full_framework_closure_gate -v)
            ;;
        asterion_cli)
            command=(uv run python -m unittest tests.test_distribution_boundaries.SourceDistributionBoundaryTests.test_source_baseline_remains_runnable_without_installation -v)
            ;;
        asterion_examples)
            command=(uv run python -m unittest tests.test_asterion_structure.AsterionStructureTests.test_examples_build_cli_commands_in_an_isolated_repository -v)
            ;;
        asterion_architecture)
            command=(uv run python -m unittest tests.test_asterion_structure.AsterionStructureTests.test_layout_guide_defines_framework_ownership -v)
            ;;
        runner_docs)
            command=(uv run python -m unittest tests.test_application_runner.ApplicationRunnerDocumentationTests.test_guide_documents_the_explicit_plan_runtime_and_service_boundary tests.test_application_runner.ApplicationRunnerDocumentationTests.test_guide_documents_immutable_results_and_safe_failures -v)
            ;;
        runner_boundary)
            command=(uv run python -m unittest tests.test_application_runner.ApplicationRunnerDocumentationTests.test_runner_boundary_excludes_control_plane_and_process_ownership -v)
            ;;
        runner_language)
            command=(uv run python -m unittest tests.test_application_runner.ApplicationRunnerDocumentationTests.test_runner_is_python_owned_without_dci_or_typescript_duplicate -v)
            ;;
        runner_closure)
            command=(uv run python -m unittest tests.test_climb_tools.ClimbToolTests.test_af100_h004_train_runs_full_framework_closure_gate -v)
            ;;
        *)
            echo "ERROR: unknown closure check $check" >&2
            return 2
            ;;
    esac
    if "${command[@]}" >"$RUN_DIR/$name.log" 2>&1; then
        printf '1'
    else
        printf '0'
    fi
}

run_typescript_dimension() {
    name="$1"
    test_name="$2"
    if [ "$test_name" = "public_type_contract" ]; then
        command=(npm --prefix packages/typescript/asterion-runtime run build)
    else
        command=(
            node --test --test-name-pattern "$test_name"
            packages/typescript/asterion-runtime/test/runtime.test.mjs
        )
    fi
    if npm --prefix packages/typescript/asterion-runtime run build >"$RUN_DIR/$name.log" 2>&1 \
        && "${command[@]}" >>"$RUN_DIR/$name.log" 2>&1; then
        printf '1'
    else
        printf '0'
    fi
}

dimension_runner="run_dimension"
rust_suite="authorization"
case "$HYPOTHESIS_ID" in
    AF-050-H-001)
        dimension_runner="run_rust_dimension"
        first_dimension="unknown_program_denial"
        second_dimension="cwd_containment"
        third_dimension="policy_limits"
        fourth_dimension="authorized_values"
        immutable_test="denies_unknown_program_id"
        repeat_test="denies_cwd_escape_and_missing_directory"
        dirty_test="denies_request_limits_outside_trusted_policy"
        override_test="valid_request_produces_only_canonical_bounded_execution_values"
        ;;
    AF-050-H-002)
        dimension_runner="run_rust_dimension"
        rust_suite="process"
        first_dimension="literal_arguments"
        second_dimension="cleared_environment"
        third_dimension="closed_stdin"
        fourth_dimension="canonical_cwd"
        immutable_test="executes_literal_arguments_without_shell_expansion"
        repeat_test="clears_the_child_environment"
        dirty_test="closes_child_stdin"
        override_test="executes_in_the_authorized_canonical_working_directory"
        ;;
    AF-050-H-003)
        dimension_runner="run_rust_dimension"
        rust_suite="process"
        first_dimension="bounded_streams"
        second_dimension="exact_limit"
        third_dimension="deadline_kill_reap"
        fourth_dimension="direct_boundary_regression"
        immutable_test="bounds_stdout_and_stderr_independently_while_draining_to_eof"
        repeat_test="exact_output_limit_is_not_marked_truncated"
        dirty_test="deadline_kills_and_reaps_the_child_before_returning"
        override_test="executes_literal_arguments_without_shell_expansion"
        ;;
    AF-050-H-004)
        dimension_runner="run_rust_dimension"
        rust_suite="service"
        first_dimension="responsive_out_of_order"
        second_dimension="duplicate_id_denial"
        third_dimension="cancel_exactly_once"
        fourth_dimension="safe_parse_error"
        immutable_test="service_keeps_input_responsive_and_emits_out_of_order_results"
        repeat_test="duplicate_in_flight_request_id_is_denied"
        dirty_test="accepted_cancel_emits_ack_and_exactly_one_cancelled_terminal_result"
        override_test="malformed_json_returns_safe_error_without_echoing_input"
        ;;
    AF-050-H-005)
        dimension_runner="run_closure_dimension"
        first_dimension="operator_binary"
        second_dimension="operator_docs"
        third_dimension="root_test_target"
        fourth_dimension="root_check_target"
        immutable_test="operator_binary"
        repeat_test="operator_docs"
        dirty_test="root_test_target"
        override_test="root_check_target"
        ;;
    AF-060-H-001)
        first_dimension="valid_manifest"
        second_dimension="portable_kinds"
        third_dimension="closed_invalid_fixtures"
        fourth_dimension="sorted_unique_edges"
        immutable_test="tests.test_package_composition.PackageManifestTests.test_valid_shared_manifest_fixture_conforms"
        repeat_test="tests.test_package_composition.PackageManifestTests.test_all_package_kinds_are_portable"
        dirty_test="tests.test_package_composition.PackageManifestTests.test_invalid_shared_manifest_fixtures_are_rejected"
        override_test="tests.test_package_composition.PackageManifestTests.test_edge_arrays_must_be_sorted_and_unique"
        ;;
    AF-060-H-002)
        first_dimension="stable_order"
        second_dimension="duplicate_and_ambiguity"
        third_dimension="missing_edges"
        fourth_dimension="cycle_rejection"
        immutable_test="tests.test_package_composition.PackageCompositionTests.test_composition_order_is_stable_under_permuted_input"
        repeat_test="tests.test_package_composition.PackageCompositionTests.test_duplicate_ids_and_ambiguous_capability_providers_are_rejected"
        dirty_test="tests.test_package_composition.PackageCompositionTests.test_missing_capability_policy_event_and_artifact_edges_are_rejected"
        override_test="tests.test_package_composition.PackageCompositionTests.test_dependency_cycles_are_rejected"
        ;;
    AF-060-H-003)
        first_dimension="portable_manifests"
        second_dimension="runtime_parity"
        third_dimension="research_audit_edges"
        fourth_dimension="capability_rejection"
        immutable_test="tests.test_package_composition.DciReferencePackageTests.test_reference_manifests_are_portable_and_closed"
        repeat_test="tests.test_package_composition.DciReferencePackageTests.test_pi_and_claude_compose_the_same_reference_graph"
        dirty_test="tests.test_package_composition.DciReferencePackageTests.test_reference_graph_exposes_research_and_audit_edges"
        override_test="tests.test_package_composition.DciReferencePackageTests.test_reference_graph_rejects_a_runtime_without_required_capabilities"
        ;;
    AF-060-H-004)
        dimension_runner="run_typescript_dimension"
        first_dimension="valid_fixture"
        second_dimension="invalid_fixtures"
        third_dimension="canonical_ordering"
        fourth_dimension="public_type_contract"
        immutable_test="validates the shared package manifest fixture"
        repeat_test="rejects every shared invalid package manifest fixture"
        dirty_test="rejects package edge arrays that are not sorted"
        override_test="public_type_contract"
        ;;
    AF-060-H-005)
        first_dimension="static_boundary"
        second_dimension="manifest_example"
        third_dimension="composer_example"
        fourth_dimension="extension_security"
        immutable_test="tests.test_package_composition.PackageDocumentationTests.test_guide_defines_static_composition_not_execution"
        repeat_test="tests.test_package_composition.PackageDocumentationTests.test_guide_contains_a_portable_manifest_example"
        dirty_test="tests.test_package_composition.PackageDocumentationTests.test_guide_contains_a_reference_composer_example"
        override_test="tests.test_package_composition.PackageDocumentationTests.test_guide_defines_extension_and_security_boundaries"
        ;;
    AF-070-H-001)
        first_dimension="portable_manifests"
        second_dimension="workflow_kind"
        third_dimension="stable_graph"
        fourth_dimension="forbidden_fields"
        immutable_test="tests.test_package_composition.ControlledCodePackageTests.test_controlled_code_manifests_are_portable"
        repeat_test="tests.test_package_composition.ControlledCodePackageTests.test_controlled_code_graph_uses_workflow_kind"
        dirty_test="tests.test_package_composition.ControlledCodePackageTests.test_controlled_code_graph_has_stable_order"
        override_test="tests.test_package_composition.ControlledCodePackageTests.test_controlled_code_manifests_exclude_runtime_fields"
        ;;
    AF-070-H-002)
        first_dimension="runtime_parity"
        second_dimension="permutation_stability"
        third_dimension="portable_outputs"
        fourth_dimension="missing_boundary_rejection"
        immutable_test="tests.test_package_composition.ControlledCodePackageTests.test_pi_and_claude_compose_the_same_controlled_code_graph"
        repeat_test="tests.test_package_composition.ControlledCodePackageTests.test_controlled_code_graph_is_stable_under_permutation"
        dirty_test="tests.test_package_composition.ControlledCodePackageTests.test_controlled_code_graph_exposes_portable_outputs"
        override_test="tests.test_package_composition.ControlledCodePackageTests.test_controlled_code_graph_rejects_every_missing_boundary"
        ;;
    AF-070-H-003)
        dimension_runner="run_typescript_dimension"
        first_dimension="all_reference_manifests"
        second_dimension="canonical_schema"
        third_dimension="public_validator"
        fourth_dimension="no_typescript_composer"
        immutable_test="validates every checked-in reference package manifest"
        repeat_test="validates the shared package manifest fixture"
        dirty_test="public_type_contract"
        override_test="keeps package composition outside the TypeScript host"
        ;;
    AF-070-H-004)
        first_dimension="second_graph_docs"
        second_dimension="static_boundary"
        third_dimension="host_service_boundary"
        fourth_dimension="framework_closure"
        immutable_test="tests.test_package_composition.ControlledCodeDocumentationTests.test_guide_documents_the_second_graph_and_workflow_example"
        repeat_test="tests.test_package_composition.ControlledCodeDocumentationTests.test_guide_defines_static_composition_not_code_execution"
        dirty_test="tests.test_package_composition.ControlledCodeDocumentationTests.test_guide_defines_the_shared_host_service_boundary"
        override_test="tests.test_climb_tools.ClimbToolTests.test_af070_h004_train_runs_full_framework_closure_gate"
        ;;
    AF-080-H-001)
        first_dimension="root_permutation"
        second_dimension="file_order"
        third_dimension="canonical_validation"
        fourth_dimension="non_recursive_filtering"
        immutable_test="tests.test_package_catalog.PackageDiscoveryTests.test_root_permutation_produces_identical_catalog_entries"
        repeat_test="tests.test_package_catalog.PackageDiscoveryTests.test_file_creation_order_does_not_change_reference_order"
        dirty_test="tests.test_package_catalog.PackageDiscoveryTests.test_discovered_manifests_pass_canonical_validation"
        override_test="tests.test_package_catalog.PackageDiscoveryTests.test_discovery_ignores_non_json_and_nested_files"
        ;;
    AF-080-H-002)
        first_dimension="root_boundary"
        second_dimension="document_boundary"
        third_dimension="symlink_boundary"
        fourth_dimension="duplicate_identity"
        immutable_test="tests.test_package_catalog.PackageCatalogBoundaryTests.test_invalid_symlink_and_duplicate_roots_are_rejected"
        repeat_test="tests.test_package_catalog.PackageCatalogBoundaryTests.test_invalid_documents_fail_with_content_free_errors"
        dirty_test="tests.test_package_catalog.PackageCatalogBoundaryTests.test_symlink_manifest_files_are_rejected"
        override_test="tests.test_package_catalog.PackageCatalogBoundaryTests.test_duplicate_exact_identity_is_rejected"
        ;;
    AF-080-H-003)
        first_dimension="exact_selection"
        second_dimension="fresh_manifests"
        third_dimension="graph_integration"
        fourth_dimension="selection_rejection"
        immutable_test="tests.test_package_catalog.PackageSelectionTests.test_exact_selection_is_complete_and_deterministic"
        repeat_test="tests.test_package_catalog.PackageSelectionTests.test_selection_returns_fresh_manifest_copies"
        dirty_test="tests.test_package_catalog.PackageSelectionTests.test_selected_manifests_compose_both_reference_graphs"
        override_test="tests.test_package_catalog.PackageSelectionTests.test_duplicate_and_unknown_exact_selection_is_rejected"
        ;;
    AF-080-H-004)
        first_dimension="catalog_docs"
        second_dimension="filesystem_boundary"
        third_dimension="selection_boundary"
        fourth_dimension="framework_closure"
        immutable_test="tests.test_package_catalog.PackageCatalogDocumentationTests.test_guide_documents_explicit_direct_exact_catalog_contract"
        repeat_test="tests.test_package_catalog.PackageCatalogBoundaryTests.test_invalid_symlink_and_duplicate_roots_are_rejected"
        dirty_test="tests.test_package_catalog.PackageSelectionTests.test_duplicate_and_unknown_exact_selection_is_rejected"
        override_test="tests.test_climb_tools.ClimbToolTests.test_af080_h004_train_runs_full_framework_closure_gate"
        ;;
    AF-090-H-001)
        first_dimension="valid_manifest"
        second_dimension="closed_contract"
        third_dimension="canonical_refs"
        fourth_dimension="canonical_edges"
        immutable_test="tests.test_application_assembly.AssemblyManifestTests.test_valid_shared_assembly_fixture_conforms"
        repeat_test="tests.test_application_assembly.AssemblyManifestTests.test_assembly_contract_is_closed"
        dirty_test="tests.test_application_assembly.AssemblyManifestTests.test_package_refs_must_be_sorted_unique_and_exact"
        override_test="tests.test_application_assembly.AssemblyManifestTests.test_host_edge_arrays_must_be_sorted_unique_strings"
        ;;
    AF-090-H-002)
        first_dimension="runtime_binding"
        second_dimension="catalog_binding"
        third_dimension="capability_separation"
        fourth_dimension="safe_resolution"
        immutable_test="tests.test_application_assembly.AssemblyResolverTests.test_runtime_and_catalog_bind_into_an_immutable_plan"
        repeat_test="tests.test_application_assembly.AssemblyResolverTests.test_unknown_catalog_ref_is_rejected"
        dirty_test="tests.test_application_assembly.AssemblyResolverTests.test_host_service_capability_is_separate_from_runtime_capabilities"
        override_test="tests.test_application_assembly.AssemblyResolverTests.test_resolution_failures_are_safe"
        ;;
    AF-090-H-003)
        first_dimension="dci_plan"
        second_dimension="runtime_parity"
        third_dimension="controlled_plan"
        fourth_dimension="service_separation"
        immutable_test="tests.test_application_assembly.ReferenceAssemblyTests.test_checked_in_reference_assemblies_are_valid"
        repeat_test="tests.test_application_assembly.ReferenceAssemblyTests.test_dci_plan_has_pi_and_claude_runtime_parity"
        dirty_test="tests.test_application_assembly.ReferenceAssemblyTests.test_controlled_code_keeps_executor_as_a_host_service"
        override_test="tests.test_application_assembly.ReferenceAssemblyTests.test_reference_assemblies_contain_no_execution_or_secret_fields"
        ;;
    AF-090-H-004)
        dimension_runner="run_closure_dimension"
        first_dimension="typescript_parity"
        second_dimension="assembly_docs"
        third_dimension="non_execution"
        fourth_dimension="framework_closure"
        immutable_test="assembly_typescript"
        repeat_test="assembly_docs"
        dirty_test="assembly_non_execution"
        override_test="assembly_closure"
        ;;
    AF-095-H-001)
        first_dimension="authoritative_import"
        second_dimension="object_identity"
        third_dimension="dependency_direction"
        fourth_dimension="packaging_compatibility"
        immutable_test="tests.test_asterion_structure.AsterionStructureTests.test_runtime_objects_are_independent_and_wire_compatible"
        repeat_test="tests.test_asterion_structure.AsterionStructureTests.test_runtime_adapters_are_independent_and_capability_compatible"
        dirty_test="tests.test_asterion_structure.AsterionStructureTests.test_asterion_never_imports_dci"
        override_test="tests.test_asterion_structure.AsterionStructureTests.test_only_asterion_has_a_wheel_root"
        ;;
    AF-095-H-002)
        first_dimension="package_extraction"
        second_dimension="assembly_extraction"
        third_dimension="wire_stability"
        fourth_dimension="single_implementation"
        immutable_test="tests.test_asterion_structure.AsterionStructureTests.test_package_and_assembly_objects_are_independent_wire_implementations"
        repeat_test="tests.test_application_assembly.ReferenceAssemblyTests.test_checked_in_reference_assemblies_are_valid"
        dirty_test="tests.test_asterion_structure.AsterionStructureTests.test_extracted_wire_protocol_literals_remain_stable"
        override_test="tests.test_asterion_structure.AsterionStructureTests.test_dci_framework_is_frozen_baseline_owned_behavior"
        ;;
    AF-095-H-003)
        first_dimension="capability_roots"
        second_dimension="application_root"
        third_dimension="cross_language_paths"
        fourth_dimension="identity_stability"
        immutable_test="tests.test_asterion_structure.AsterionStructureTests.test_declarative_assets_have_product_level_owners"
        repeat_test="tests.test_application_assembly.ReferenceAssemblyTests.test_checked_in_reference_assemblies_are_valid"
        dirty_test="tests.test_asterion_structure.AsterionStructureTests.test_cross_language_working_directories_are_asterion_owned"
        override_test="tests.test_package_catalog.PackageSelectionTests.test_selected_manifests_compose_both_reference_graphs"
        ;;
    AF-095-H-004)
        first_dimension="dci_cli_compatibility"
        second_dimension="example_compatibility"
        third_dimension="architecture_boundary"
        fourth_dimension="framework_closure"
        dimension_runner="run_closure_dimension"
        immutable_test="asterion_cli"
        repeat_test="asterion_examples"
        dirty_test="asterion_architecture"
        override_test="asterion_closure"
        ;;
    AF-100-H-001)
        first_dimension="runtime_ownership"
        second_dimension="host_ownership"
        third_dimension="immutable_plan"
        fourth_dimension="no_name_inference"
        immutable_test="tests.test_application_assembly.AssemblyResolverTests.test_runtime_capability_ownership_is_deterministic"
        repeat_test="tests.test_application_assembly.AssemblyResolverTests.test_host_capability_ownership_is_explicit"
        dirty_test="tests.test_application_assembly.AssemblyResolverTests.test_capability_ownership_is_immutable"
        override_test="tests.test_application_assembly.AssemblyResolverTests.test_capability_ownership_is_not_inferred_from_names"
        ;;
    AF-100-H-002)
        first_dimension="portable_request"
        second_dimension="runtime_invocation"
        third_dimension="immutable_events"
        fourth_dimension="artifact_projection"
        immutable_test="tests.test_application_runner.ApplicationRunnerTests.test_plan_runtime_capabilities_become_portable_request"
        repeat_test="tests.test_application_runner.ApplicationRunnerTests.test_explicit_runtime_is_invoked_once"
        dirty_test="tests.test_application_runner.ApplicationRunnerTests.test_successful_result_is_deeply_immutable"
        override_test="tests.test_application_runner.ApplicationRunnerTests.test_artifact_events_are_projected_without_provider_output"
        ;;
    AF-100-H-003)
        first_dimension="runtime_parity"
        second_dimension="cancellation"
        third_dimension="preflight_safety"
        fourth_dimension="error_redaction"
        immutable_test="tests.test_application_runner.ApplicationRunnerTests.test_pi_and_claude_fixture_runtimes_are_protocol_equivalent"
        repeat_test="tests.test_application_runner.ApplicationRunnerTests.test_pre_run_and_in_run_cancellation_are_safe"
        dirty_test="tests.test_application_runner.ApplicationRunnerTests.test_runtime_and_service_mismatches_fail_before_invocation"
        override_test="tests.test_application_runner.ApplicationRunnerTests.test_malformed_streams_and_runtime_errors_are_redacted"
        ;;
    AF-100-H-004)
        dimension_runner="run_closure_dimension"
        first_dimension="runner_docs"
        second_dimension="boundary_integrity"
        third_dimension="language_ownership"
        fourth_dimension="framework_closure"
        immutable_test="runner_docs"
        repeat_test="runner_boundary"
        dirty_test="runner_language"
        override_test="runner_closure"
        ;;
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
    H-019)
        first_dimension="idle_postcondition"
        second_dimension="non_idle_rejection"
        third_dimension="legacy_compatibility"
        fourth_dimension="adapter_integration"
        immutable_test="tests.test_pi_rpc_runner.PiRpcLifecycleTests.test_agent_settled_requires_an_idle_state_postcondition"
        repeat_test="tests.test_pi_rpc_runner.PiRpcLifecycleTests.test_agent_settled_rejects_non_idle_state"
        dirty_test="tests.test_pi_rpc_runner.PiRpcLifecycleTests.test_legacy_agent_end_without_will_retry_is_supported"
        override_test="tests.test_climb_tools.ClimbToolTests.test_h019_train_checks_rpc_settlement_postcondition"
        ;;
    AF-180-H-001)
        first_dimension="configuration_namespace"
        second_dimension="default_isolation"
        third_dimension="dotenv_precedence"
        fourth_dimension="baseline_import_boundary"
        immutable_test="tests.test_asterion_dci_config.AsterionDciConfigTests.test_uses_only_asterion_dci_path_namespace"
        repeat_test="tests.test_asterion_dci_config.AsterionDciConfigTests.test_defaults_never_select_legacy_dci_locations"
        dirty_test="tests.test_asterion_dci_config.AsterionDciConfigTests.test_loads_the_new_product_env_without_overriding_process_values"
        override_test="tests.test_distribution_boundaries.SourceDistributionBoundaryTests.test_asterion_core_never_imports_the_dci_baseline"
        ;;
    AF-180-H-002)
        first_dimension="rpc_lifecycle"
        second_dimension="retry_and_abort"
        third_dimension="native_artifacts"
        fourth_dimension="safe_failure"
        immutable_test="tests.test_asterion_dci_pi_rpc.PiRpcLifecycleTests.test_waits_for_acknowledgement_and_idle_agent_settled_state"
        repeat_test="tests.test_asterion_dci_pi_rpc.PiRpcLifecycleTests.test_retry_discards_partial_text_and_turn_limit_aborts_then_waits"
        dirty_test="tests.test_asterion_dci_run.AsterionDciRunTests.test_completed_run_writes_native_artifacts_and_protocol_projection"
        override_test="tests.test_asterion_dci_run.AsterionDciRunTests.test_rejects_a_nonempty_output_and_keeps_failure_detail_out_of_error"
        ;;
    AF-180-H-003)
        first_dimension="run_option_mapping"
        second_dimension="deferred_feature_rejection"
        third_dimension="generic_cli_neutrality"
        fourth_dimension="safe_prompt_failure"
        immutable_test="tests.test_asterion_dci_cli.AsterionDciCliTests.test_run_maps_original_single_run_options_to_domain_request"
        repeat_test="tests.test_asterion_dci_cli.AsterionDciCliTests.test_cli_rejects_deferred_features_without_calling_pi"
        dirty_test="tests.test_asterion_dci_cli.AsterionDciCliTests.test_product_help_is_separate_from_the_generic_cli"
        override_test="tests.test_asterion_dci_cli.AsterionDciCliTests.test_system_prompt_failure_is_publicly_safe"
        ;;
    AF-180-H-004)
        first_dimension="body_free_projection"
        second_dimension="terminal_result_rejection"
        third_dimension="native_projection_seam"
        fourth_dimension="baseline_independence"
        immutable_test="tests.test_asterion_dci_bridge.AsterionDciBridgeTests.test_projection_preserves_native_references_without_answer_body"
        repeat_test="tests.test_asterion_dci_bridge.AsterionDciBridgeTests.test_projection_rejects_a_noncompleted_native_result"
        dirty_test="tests.test_dci_research_capability.DciResearchCapabilityTests.test_completed_native_run_uses_the_explicit_projection_seam"
        override_test="tests.test_distribution_boundaries.SourceDistributionBoundaryTests.test_asterion_core_never_imports_the_dci_baseline"
        ;;
    *)
        echo "ERROR: no local evaluation contract for $HYPOTHESIS_ID" >&2
        exit 2
        ;;
esac

immutable_resolution="$($dimension_runner "$first_dimension" "$immutable_test")"
repeat_validation="$($dimension_runner "$second_dimension" "$repeat_test")"
dirty_checkout_safety="$($dimension_runner "$third_dimension" "$dirty_test")"
override_compatibility="$($dimension_runner "$fourth_dimension" "$override_test")"
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
