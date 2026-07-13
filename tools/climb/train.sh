#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -ne 1 ]; then
    echo "Usage: $0 HYPOTHESIS_ID" >&2
    exit 2
fi
case "$1" in
    H-001|H-002|H-003|H-004|H-005|H-006|H-007|H-008|H-009|H-010|H-011|H-012|H-013|H-014|H-015|H-016|H-017|H-018|H-019|AF-050-H-001|AF-050-H-002|AF-050-H-003|AF-050-H-004|AF-050-H-005|AF-060-H-001|AF-060-H-002|AF-060-H-003|AF-060-H-004|AF-060-H-005|AF-070-H-001|AF-070-H-002|AF-070-H-003|AF-070-H-004|AF-080-H-001|AF-080-H-002|AF-080-H-003|AF-080-H-004|AF-090-H-001|AF-090-H-002|AF-090-H-003|AF-090-H-004|AF-095-H-001|AF-095-H-002|AF-095-H-003|AF-095-H-004|AF-100-H-001|AF-100-H-002|AF-100-H-003|AF-100-H-004|AF-180-H-001|AF-180-H-002|AF-180-H-003|AF-180-H-004|AF-190-H-001|AF-190-H-002|AF-190-H-003|AF-190-H-004|AF-200-H-001|AF-200-H-002|AF-200-H-003|AF-200-H-004|AF-210-H-001|AF-210-H-002|AF-210-H-003|AF-210-H-004|AF-220-H-001|AF-220-H-002|AF-220-H-003|AF-220-H-004) ;;
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
if [ "$1" = "AF-050-H-001" ]; then
    paradigm="rust-request-authorization"
elif [ "$1" = "AF-050-H-002" ]; then
    paradigm="rust-process-boundary"
elif [ "$1" = "AF-050-H-003" ]; then
    paradigm="rust-resource-boundary"
elif [ "$1" = "AF-050-H-004" ]; then
    paradigm="rust-jsonl-service"
elif [ "$1" = "AF-050-H-005" ]; then
    paradigm="framework-executor-acceptance"
elif [ "$1" = "AF-060-H-001" ]; then
    paradigm="package-manifest-contract"
elif [ "$1" = "AF-060-H-002" ]; then
    paradigm="python-package-composer"
elif [ "$1" = "AF-060-H-003" ]; then
    paradigm="dci-package-vertical-slice"
elif [ "$1" = "AF-060-H-004" ]; then
    paradigm="typescript-package-parity"
elif [ "$1" = "AF-060-H-005" ]; then
    paradigm="framework-package-acceptance"
elif [ "$1" = "AF-070-H-001" ]; then
    paradigm="controlled-code-package-graph"
elif [ "$1" = "AF-070-H-002" ]; then
    paradigm="controlled-code-graph-boundaries"
elif [ "$1" = "AF-070-H-003" ]; then
    paradigm="typescript-reference-manifest-parity"
elif [ "$1" = "AF-070-H-004" ]; then
    paradigm="controlled-code-framework-acceptance"
elif [ "$1" = "AF-080-H-001" ]; then
    paradigm="local-package-discovery"
elif [ "$1" = "AF-080-H-002" ]; then
    paradigm="local-package-discovery-safety"
elif [ "$1" = "AF-080-H-003" ]; then
    paradigm="exact-package-selection"
elif [ "$1" = "AF-080-H-004" ]; then
    paradigm="local-package-catalog-acceptance"
elif [ "$1" = "AF-090-H-001" ]; then
    paradigm="assembly-manifest-contract"
elif [ "$1" = "AF-090-H-002" ]; then
    paradigm="static-assembly-resolver"
elif [ "$1" = "AF-090-H-003" ]; then
    paradigm="reference-assembly-plans"
elif [ "$1" = "AF-090-H-004" ]; then
    paradigm="static-assembly-acceptance"
elif [ "$1" = "AF-095-H-001" ]; then
    paradigm="asterion-authoritative-package"
elif [ "$1" = "AF-095-H-002" ]; then
    paradigm="framework-module-extraction"
elif [ "$1" = "AF-095-H-003" ]; then
    paradigm="product-directory-separation"
elif [ "$1" = "AF-095-H-004" ]; then
    paradigm="asterion-extraction-acceptance"
elif [ "$1" = "AF-100-H-001" ]; then
    paradigm="plan-capability-ownership"
elif [ "$1" = "AF-100-H-002" ]; then
    paradigm="plan-driven-application-runner"
elif [ "$1" = "AF-100-H-003" ]; then
    paradigm="runner-safety-boundaries"
elif [ "$1" = "AF-100-H-004" ]; then
    paradigm="application-runner-acceptance"
elif [ "$1" = "AF-180-H-001" ]; then
    paradigm="dci-configuration-isolation"
elif [ "$1" = "AF-180-H-002" ]; then
    paradigm="dci-pi-execution-parity"
elif [ "$1" = "AF-180-H-003" ]; then
    paradigm="dci-operator-surface"
elif [ "$1" = "AF-180-H-004" ]; then
    paradigm="dci-capability-projection"
elif [ "$1" = "AF-190-H-001" ]; then
    paradigm="dci-durable-artifacts"
elif [ "$1" = "AF-190-H-002" ]; then
    paradigm="dci-resume-validation"
elif [ "$1" = "AF-190-H-003" ]; then
    paradigm="dci-resume-operator-surface"
elif [ "$1" = "AF-190-H-004" ]; then
    paradigm="dci-durable-projection"
elif [ "$1" = "AF-200-H-001" ]; then
    paradigm="dci-judge-contract"
elif [ "$1" = "AF-200-H-002" ]; then
    paradigm="dci-evaluation-cache"
elif [ "$1" = "AF-200-H-003" ]; then
    paradigm="dci-benchmark-orchestration"
elif [ "$1" = "AF-200-H-004" ]; then
    paradigm="dci-evaluation-operator-surface"
elif [ "$1" = "AF-210-H-001" ]; then
    paradigm="dci-application-native-executor"
elif [ "$1" = "AF-210-H-002" ]; then
    paradigm="dci-pi-application-dispatch"
elif [ "$1" = "AF-210-H-003" ]; then
    paradigm="dci-installed-application-projection"
elif [ "$1" = "AF-210-H-004" ]; then
    paradigm="dci-application-parity-closure"
elif [ "$1" = "AF-220-H-001" ]; then
    paradigm="dci-shared-configuration"
elif [ "$1" = "AF-220-H-002" ]; then
    paradigm="dci-native-pi-controls"
elif [ "$1" = "AF-220-H-003" ]; then
    paradigm="dci-package-batch-propagation"
elif [ "$1" = "AF-220-H-004" ]; then
    paradigm="dci-installed-application-example-parity"
elif [ "$1" = "H-003" ]; then
    paradigm="rpc-contract-probe"
elif [ "$1" = "H-004" ] || [ "$1" = "H-005" ]; then
    paradigm="run-provenance"
elif [ "$1" = "H-006" ]; then
    paradigm="judge-contract-probe"
elif [ "$1" = "H-007" ]; then
    paradigm="judge-config-provenance"
elif [ "$1" = "H-008" ]; then
    paradigm="judge-config-preflight"
elif [ "$1" = "H-009" ]; then
    paradigm="judge-structured-output"
elif [ "$1" = "H-010" ]; then
    paradigm="judge-request-fingerprint"
elif [ "$1" = "H-011" ]; then
    paradigm="judge-error-redaction"
elif [ "$1" = "H-012" ]; then
    paradigm="judge-artifact-privacy"
elif [ "$1" = "H-013" ]; then
    paradigm="judge-cache-completeness"
elif [ "$1" = "H-014" ]; then
    paradigm="judge-input-privacy"
elif [ "$1" = "H-015" ]; then
    paradigm="judge-url-safety"
elif [ "$1" = "H-016" ]; then
    paradigm="judge-url-origin-validation"
elif [ "$1" = "H-017" ]; then
    paradigm="judge-redirect-containment"
elif [ "$1" = "H-018" ]; then
    paradigm="official-responses-retention"
elif [ "$1" = "H-019" ]; then
    paradigm="rpc-settlement-postcondition"
fi

cat >"$run_dir/manifest.json" <<EOF
{
  "cycle": null,
  "hypothesis_id": "$1",
  "paradigm": "$paradigm",
  "run_id": "$run_id"
}
EOF

if [ "$1" = "AF-050-H-001" ]; then
    if ! cargo test --manifest-path packages/rust/controlled-executor/Cargo.toml --test authorization >"$run_dir/train.log" 2>&1; then
        echo "ERROR: AF-050-H-001 request authorization failed; see $run_dir/train.log" >&2
        exit 1
    fi
elif [ "$1" = "AF-050-H-002" ]; then
    if ! cargo test --manifest-path packages/rust/controlled-executor/Cargo.toml --test process >"$run_dir/train.log" 2>&1; then
        echo "ERROR: AF-050-H-002 direct process boundary failed; see $run_dir/train.log" >&2
        exit 1
    fi
elif [ "$1" = "AF-050-H-003" ]; then
    if ! cargo test --manifest-path packages/rust/controlled-executor/Cargo.toml --test process >"$run_dir/train.log" 2>&1; then
        echo "ERROR: AF-050-H-003 bounded process resources failed; see $run_dir/train.log" >&2
        exit 1
    fi
elif [ "$1" = "AF-050-H-004" ]; then
    if ! cargo test --manifest-path packages/rust/controlled-executor/Cargo.toml --test service >"$run_dir/train.log" 2>&1; then
        echo "ERROR: AF-050-H-004 concurrent JSONL service failed; see $run_dir/train.log" >&2
        exit 1
    fi
elif [ "$1" = "AF-050-H-005" ]; then
    if ! {
        make test-rust-executor
        make check-rust-executor
        uv run python -m unittest tests.test_climb_tools.ClimbToolTests.test_af050_operator_docs_and_root_verification_targets_exist -v
    } >"$run_dir/train.log" 2>&1; then
        echo "ERROR: AF-050-H-005 framework closure gate failed; see $run_dir/train.log" >&2
        exit 1
    fi
elif [ "$1" = "AF-060-H-001" ]; then
    if ! uv run python -m unittest tests.test_package_composition -v >"$run_dir/train.log" 2>&1; then
        echo "ERROR: AF-060-H-001 package manifest contract failed; see $run_dir/train.log" >&2
        exit 1
    fi
elif [ "$1" = "AF-060-H-002" ]; then
    if ! uv run python -m unittest tests.test_package_composition.PackageCompositionTests -v >"$run_dir/train.log" 2>&1; then
        echo "ERROR: AF-060-H-002 deterministic package composition failed; see $run_dir/train.log" >&2
        exit 1
    fi
elif [ "$1" = "AF-060-H-003" ]; then
    if ! uv run python -m unittest tests.test_package_composition.DciReferencePackageTests -v >"$run_dir/train.log" 2>&1; then
        echo "ERROR: AF-060-H-003 DCI reference package graph failed; see $run_dir/train.log" >&2
        exit 1
    fi
elif [ "$1" = "AF-060-H-004" ]; then
    if ! npm --prefix packages/typescript/asterion-runtime test >"$run_dir/train.log" 2>&1; then
        echo "ERROR: AF-060-H-004 TypeScript package parity failed; see $run_dir/train.log" >&2
        exit 1
    fi
elif [ "$1" = "AF-060-H-005" ]; then
    if ! {
        uv run python -m unittest discover -v
        uv run python -m compileall -q src tests tools
        uv run ruff check src tests tools
        make test-typescript-host
        make test-rust-executor
        make check-rust-executor
        bash -n tools/climb/train.sh tools/climb/eval-local.sh tools/climb/cycle.sh
        python3 tools/project_scope_check.py --climb-hypothesis AF-060-H-005
        git diff --check
    } >"$run_dir/train.log" 2>&1; then
        echo "ERROR: AF-060-H-005 framework package closure failed; see $run_dir/train.log" >&2
        exit 1
    fi
elif [ "$1" = "AF-070-H-001" ]; then
    if ! uv run python -m unittest tests.test_package_composition.ControlledCodePackageTests -v >"$run_dir/train.log" 2>&1; then
        echo "ERROR: AF-070-H-001 controlled-code manifests failed; see $run_dir/train.log" >&2
        exit 1
    fi
elif [ "$1" = "AF-070-H-002" ]; then
    if ! uv run python -m unittest \
        tests.test_package_composition.ControlledCodePackageTests.test_pi_and_claude_compose_the_same_controlled_code_graph \
        tests.test_package_composition.ControlledCodePackageTests.test_controlled_code_graph_is_stable_under_permutation \
        tests.test_package_composition.ControlledCodePackageTests.test_controlled_code_graph_exposes_portable_outputs \
        tests.test_package_composition.ControlledCodePackageTests.test_controlled_code_graph_rejects_every_missing_boundary \
        -v >"$run_dir/train.log" 2>&1; then
        echo "ERROR: AF-070-H-002 controlled-code graph boundaries failed; see $run_dir/train.log" >&2
        exit 1
    fi
elif [ "$1" = "AF-070-H-003" ]; then
    if ! npm --prefix packages/typescript/asterion-runtime test >"$run_dir/train.log" 2>&1; then
        echo "ERROR: AF-070-H-003 TypeScript reference manifest parity failed; see $run_dir/train.log" >&2
        exit 1
    fi
elif [ "$1" = "AF-070-H-004" ]; then
    if ! {
        uv run python -m unittest discover -v
        uv run python -m compileall -q src tests tools
        uv run ruff check src tests tools
        npm --prefix packages/typescript/asterion-runtime ci
        npm --prefix packages/typescript/asterion-runtime test
        make test-rust-executor
        make check-rust-executor
        bash -n tools/climb/train.sh tools/climb/eval-local.sh tools/climb/cycle.sh
        python3 tools/project_scope_check.py --climb-hypothesis AF-070-H-004
        git diff --check
    } >"$run_dir/train.log" 2>&1; then
        echo "ERROR: AF-070-H-004 controlled-code framework closure failed; see $run_dir/train.log" >&2
        exit 1
    fi
elif [ "$1" = "AF-080-H-001" ]; then
    if ! uv run python -m unittest tests.test_package_catalog.PackageDiscoveryTests -v >"$run_dir/train.log" 2>&1; then
        echo "ERROR: AF-080-H-001 local package discovery failed; see $run_dir/train.log" >&2
        exit 1
    fi
elif [ "$1" = "AF-080-H-002" ]; then
    if ! uv run python -m unittest tests.test_package_catalog.PackageCatalogBoundaryTests -v >"$run_dir/train.log" 2>&1; then
        echo "ERROR: AF-080-H-002 catalog trust boundaries failed; see $run_dir/train.log" >&2
        exit 1
    fi
elif [ "$1" = "AF-080-H-003" ]; then
    if ! uv run python -m unittest tests.test_package_catalog.PackageSelectionTests -v >"$run_dir/train.log" 2>&1; then
        echo "ERROR: AF-080-H-003 exact package selection failed; see $run_dir/train.log" >&2
        exit 1
    fi
elif [ "$1" = "AF-080-H-004" ]; then
    if ! {
        uv run python -m unittest discover -v
        uv run python -m compileall -q src tests tools
        uv run ruff check src tests tools
        npm --prefix packages/typescript/asterion-runtime ci
        npm --prefix packages/typescript/asterion-runtime test
        make test-rust-executor
        make check-rust-executor
        bash -n tools/climb/train.sh tools/climb/eval-local.sh tools/climb/cycle.sh
        python3 tools/project_scope_check.py --climb-hypothesis AF-080-H-004
        git diff --check
    } >"$run_dir/train.log" 2>&1; then
        echo "ERROR: AF-080-H-004 local catalog framework closure failed; see $run_dir/train.log" >&2
        exit 1
    fi
elif [ "$1" = "AF-090-H-001" ]; then
    if ! uv run python -m unittest tests.test_application_assembly.AssemblyManifestTests -v >"$run_dir/train.log" 2>&1; then
        echo "ERROR: AF-090-H-001 assembly manifest contract failed; see $run_dir/train.log" >&2
        exit 1
    fi
elif [ "$1" = "AF-090-H-002" ]; then
    if ! uv run python -m unittest tests.test_application_assembly.AssemblyResolverTests -v >"$run_dir/train.log" 2>&1; then
        echo "ERROR: AF-090-H-002 static assembly resolver failed; see $run_dir/train.log" >&2
        exit 1
    fi
elif [ "$1" = "AF-090-H-003" ]; then
    if ! uv run python -m unittest tests.test_application_assembly.ReferenceAssemblyTests -v >"$run_dir/train.log" 2>&1; then
        echo "ERROR: AF-090-H-003 reference assembly plans failed; see $run_dir/train.log" >&2
        exit 1
    fi
elif [ "$1" = "AF-090-H-004" ]; then
    if ! {
        uv run python -m unittest discover -v
        uv run python -m compileall -q src tests tools
        uv run ruff check src tests tools
        npm --prefix packages/typescript/asterion-runtime ci
        npm --prefix packages/typescript/asterion-runtime test
        make test-rust-executor
        make check-rust-executor
        bash -n tools/climb/train.sh tools/climb/eval-local.sh tools/climb/cycle.sh
        python3 tools/project_scope_check.py --climb-hypothesis AF-090-H-004
        git diff --check
    } >"$run_dir/train.log" 2>&1; then
        echo "ERROR: AF-090-H-004 static assembly framework closure failed; see $run_dir/train.log" >&2
        exit 1
    fi
elif [ "$1" = "AF-095-H-001" ]; then
    if ! uv run python -m unittest tests.test_asterion_structure.AsterionStructureTests -v >"$run_dir/train.log" 2>&1; then
        echo "ERROR: AF-095-H-001 Asterion ownership boundary failed; see $run_dir/train.log" >&2
        exit 1
    fi
elif [ "$1" = "AF-095-H-002" ]; then
    if ! uv run python -m unittest \
        tests.test_asterion_structure.AsterionStructureTests.test_package_and_assembly_objects_are_compatibility_aliases \
        tests.test_asterion_structure.AsterionStructureTests.test_extracted_wire_protocol_literals_remain_stable \
        tests.test_asterion_structure.AsterionStructureTests.test_dci_framework_compatibility_modules_define_no_behavior \
        tests.test_package_composition tests.test_package_catalog tests.test_application_assembly tests.test_executor_protocol \
        -v >"$run_dir/train.log" 2>&1; then
        echo "ERROR: AF-095-H-002 Asterion contract extraction failed; see $run_dir/train.log" >&2
        exit 1
    fi
elif [ "$1" = "AF-095-H-003" ]; then
    if ! {
        uv run python -m unittest \
            tests.test_asterion_structure.AsterionStructureTests.test_declarative_assets_have_product_level_owners \
            tests.test_asterion_structure.AsterionStructureTests.test_cross_language_working_directories_are_asterion_owned \
            tests.test_package_composition tests.test_package_catalog tests.test_application_assembly -v
        npm --prefix packages/typescript/asterion-runtime test
        cargo test --manifest-path packages/rust/controlled-executor/Cargo.toml
    } >"$run_dir/train.log" 2>&1; then
        echo "ERROR: AF-095-H-003 product directory separation failed; see $run_dir/train.log" >&2
        exit 1
    fi
elif [ "$1" = "AF-095-H-004" ]; then
    if ! {
        uv run python -m unittest discover -v
        uv run python -m compileall -q src tests tools
        uv run ruff check src tests tools
        npm --prefix packages/typescript/asterion-runtime ci
        npm --prefix packages/typescript/asterion-runtime test
        make test-rust-executor
        make check-rust-executor
        bash -n scripts/examples/dci_basic_example.sh scripts/examples/dci_runtime_context_example.sh tools/climb/train.sh tools/climb/eval-local.sh tools/climb/cycle.sh
        python3 tools/project_scope_check.py --climb-hypothesis AF-095-H-004
        git diff --check
    } >"$run_dir/train.log" 2>&1; then
        echo "ERROR: AF-095-H-004 Asterion extraction closure failed; see $run_dir/train.log" >&2
        exit 1
    fi
elif [ "$1" = "AF-100-H-001" ]; then
    if ! uv run python -m unittest \
        tests.test_application_assembly.AssemblyResolverTests.test_runtime_capability_ownership_is_deterministic \
        tests.test_application_assembly.AssemblyResolverTests.test_host_capability_ownership_is_explicit \
        tests.test_application_assembly.AssemblyResolverTests.test_capability_ownership_is_immutable \
        tests.test_application_assembly.AssemblyResolverTests.test_capability_ownership_is_not_inferred_from_names \
        -v >"$run_dir/train.log" 2>&1; then
        echo "ERROR: AF-100-H-001 plan capability ownership failed; see $run_dir/train.log" >&2
        exit 1
    fi
elif [ "$1" = "AF-100-H-002" ]; then
    if ! uv run python -m unittest tests.test_application_runner -v >"$run_dir/train.log" 2>&1; then
        echo "ERROR: AF-100-H-002 application runner failed; see $run_dir/train.log" >&2
        exit 1
    fi
elif [ "$1" = "AF-100-H-003" ]; then
    if ! uv run python -m unittest \
        tests.test_application_runner.ApplicationRunnerTests.test_pi_and_claude_fixture_runtimes_are_protocol_equivalent \
        tests.test_application_runner.ApplicationRunnerTests.test_pre_run_and_in_run_cancellation_are_safe \
        tests.test_application_runner.ApplicationRunnerTests.test_runtime_and_service_mismatches_fail_before_invocation \
        tests.test_application_runner.ApplicationRunnerTests.test_malformed_streams_and_runtime_errors_are_redacted \
        -v >"$run_dir/train.log" 2>&1; then
        echo "ERROR: AF-100-H-003 runner safety boundaries failed; see $run_dir/train.log" >&2
        exit 1
    fi
elif [ "$1" = "AF-100-H-004" ]; then
    if ! {
        uv run python -m unittest discover -v
        uv run python -m compileall -q src tests tools
        uv run ruff check src tests tools
        npm --prefix packages/typescript/asterion-runtime ci
        npm --prefix packages/typescript/asterion-runtime test
        make test-rust-executor
        make check-rust-executor
        bash -n scripts/examples/dci_basic_example.sh scripts/examples/dci_runtime_context_example.sh tools/climb/train.sh tools/climb/eval-local.sh tools/climb/cycle.sh
        python3 tools/project_scope_check.py --climb-hypothesis AF-100-H-004
        git diff --check
    } >"$run_dir/train.log" 2>&1; then
        echo "ERROR: AF-100-H-004 application runner closure failed; see $run_dir/train.log" >&2
        exit 1
    fi
elif [ "$1" = "AF-180-H-001" ]; then
    if ! uv run python -m unittest tests.test_asterion_dci_config -v >"$run_dir/train.log" 2>&1; then
        echo "ERROR: AF-180-H-001 DCI configuration isolation failed; see $run_dir/train.log" >&2
        exit 1
    fi
elif [ "$1" = "AF-180-H-002" ]; then
    if ! uv run python -m unittest tests.test_asterion_dci_pi_rpc tests.test_asterion_dci_run -v >"$run_dir/train.log" 2>&1; then
        echo "ERROR: AF-180-H-002 Pi execution parity failed; see $run_dir/train.log" >&2
        exit 1
    fi
elif [ "$1" = "AF-180-H-003" ]; then
    if ! uv run python -m unittest tests.test_asterion_dci_cli tests.test_asterion_cli -v >"$run_dir/train.log" 2>&1; then
        echo "ERROR: AF-180-H-003 DCI operator surface failed; see $run_dir/train.log" >&2
        exit 1
    fi
elif [ "$1" = "AF-180-H-004" ]; then
    if ! uv run python -m unittest tests.test_asterion_dci_bridge tests.test_dci_research_capability -v >"$run_dir/train.log" 2>&1; then
        echo "ERROR: AF-180-H-004 DCI capability projection failed; see $run_dir/train.log" >&2
        exit 1
    fi
elif [ "$1" = "AF-190-H-001" ]; then
    if ! uv run python -m unittest tests.test_asterion_dci_artifacts -v >"$run_dir/train.log" 2>&1; then
        echo "ERROR: AF-190-H-001 durable artifact suite failed; see $run_dir/train.log" >&2
        exit 1
    fi
elif [ "$1" = "AF-190-H-002" ]; then
    if ! uv run python -m unittest tests.test_asterion_dci_run -v >"$run_dir/train.log" 2>&1; then
        echo "ERROR: AF-190-H-002 resume validation suite failed; see $run_dir/train.log" >&2
        exit 1
    fi
elif [ "$1" = "AF-190-H-003" ]; then
    if ! uv run python -m unittest tests.test_asterion_dci_cli -v >"$run_dir/train.log" 2>&1; then
        echo "ERROR: AF-190-H-003 resume operator surface failed; see $run_dir/train.log" >&2
        exit 1
    fi
elif [ "$1" = "AF-190-H-004" ]; then
    if ! uv run python -m unittest tests.test_asterion_dci_bridge -v >"$run_dir/train.log" 2>&1; then
        echo "ERROR: AF-190-H-004 durable projection failed; see $run_dir/train.log" >&2
        exit 1
    fi
elif [ "$1" = "AF-200-H-001" ]; then
    if ! uv run python -m unittest tests.test_asterion_dci_judge -v >"$run_dir/train.log" 2>&1; then
        echo "ERROR: AF-200-H-001 judge contract failed; see $run_dir/train.log" >&2
        exit 1
    fi
elif [ "$1" = "AF-200-H-002" ]; then
    if ! uv run python -m unittest tests.test_asterion_dci_evaluation -v >"$run_dir/train.log" 2>&1; then
        echo "ERROR: AF-200-H-002 evaluation cache failed; see $run_dir/train.log" >&2
        exit 1
    fi
elif [ "$1" = "AF-200-H-003" ]; then
    if ! uv run python -m unittest tests.test_asterion_dci_benchmark -v >"$run_dir/train.log" 2>&1; then
        echo "ERROR: AF-200-H-003 benchmark orchestration failed; see $run_dir/train.log" >&2
        exit 1
    fi
elif [ "$1" = "AF-200-H-004" ]; then
    if ! uv run python -m unittest tests.test_asterion_dci_cli tests.test_asterion_dci_bridge -v >"$run_dir/train.log" 2>&1; then
        echo "ERROR: AF-200-H-004 evaluation operator surface failed; see $run_dir/train.log" >&2
        exit 1
    fi
elif [ "$1" = "AF-210-H-001" ]; then
    if ! uv run python -m unittest tests.test_asterion_dci_application_executor tests.test_asterion_dci_config -v >"$run_dir/train.log" 2>&1; then
        echo "ERROR: AF-210-H-001 native application executor failed; see $run_dir/train.log" >&2
        exit 1
    fi
elif [ "$1" = "AF-210-H-002" ]; then
    if ! uv run python -m unittest tests.test_dci_research_capability tests.test_asterion_dci_bridge -v >"$run_dir/train.log" 2>&1; then
        echo "ERROR: AF-210-H-002 Pi application dispatch failed; see $run_dir/train.log" >&2
        exit 1
    fi
elif [ "$1" = "AF-210-H-003" ]; then
    if ! uv run python -m unittest tests.test_builtin_dci_application tests.test_asterion_cli tests.test_distribution_boundaries -v >"$run_dir/train.log" 2>&1; then
        echo "ERROR: AF-210-H-003 installed application projection failed; see $run_dir/train.log" >&2
        exit 1
    fi
elif [ "$1" = "AF-210-H-004" ]; then
    if ! {
        uv run python -m unittest discover -v
        uv run python -m compileall -q src tests tools
        uv run ruff check src tests tools
        npm --prefix packages/typescript/asterion-runtime ci
        npm --prefix packages/typescript/asterion-runtime test
        make test-rust-executor
        make check-rust-executor
        bash -n tools/climb/train.sh tools/climb/eval-local.sh tools/climb/cycle.sh
        python3 tools/project_scope_check.py
        git diff --check
    } >"$run_dir/train.log" 2>&1; then
        echo "ERROR: AF-210-H-004 application parity closure failed; see $run_dir/train.log" >&2
        exit 1
    fi
elif [ "$1" = "AF-220-H-001" ]; then
    if ! uv run python -m unittest tests.test_asterion_dci_config tests.test_asterion_dci_judge -v >"$run_dir/train.log" 2>&1; then
        echo "ERROR: AF-220-H-001 shared DCI configuration failed; see $run_dir/train.log" >&2
        exit 1
    fi
elif [ "$1" = "AF-220-H-002" ]; then
    if ! uv run python -m unittest tests.test_asterion_dci_pi_rpc tests.test_asterion_dci_run -v >"$run_dir/train.log" 2>&1; then
        echo "ERROR: AF-220-H-002 native Pi controls failed; see $run_dir/train.log" >&2
        exit 1
    fi
elif [ "$1" = "AF-220-H-003" ]; then
    if ! uv run python -m unittest tests.test_asterion_dci_cli tests.test_asterion_dci_benchmark -v >"$run_dir/train.log" 2>&1; then
        echo "ERROR: AF-220-H-003 package and batch propagation failed; see $run_dir/train.log" >&2
        exit 1
    fi
elif [ "$1" = "AF-220-H-004" ]; then
    if ! uv run python -m unittest tests.test_asterion_dci_application_executor tests.test_builtin_dci_application tests.test_asterion_dci_cli -v >"$run_dir/train.log" 2>&1; then
        echo "ERROR: AF-220-H-004 installed application and examples failed; see $run_dir/train.log" >&2
        exit 1
    fi
elif [ "$1" = "H-003" ]; then
    if ! {
        uv run python -m unittest tests.test_pi_rpc_runner -v
        uv run python scripts/check_pi_rpc.py
    } >"$run_dir/train.log" 2>&1; then
        echo "ERROR: H-003 RPC compatibility probe failed; see $run_dir/train.log" >&2
        exit 1
    fi
elif [ "$1" = "H-004" ]; then
    if ! {
        uv run python -m unittest tests.test_pi_rpc_runner -v
        make runtime-example
        latest_run="$(find outputs/runs -mindepth 1 -maxdepth 1 -type d | sort | tail -1)"
        uv run python -c 'import json,sys; p=json.load(open(sys.argv[1]))["pi_source"]; assert p["commit"] and p["lock_match"] is True and isinstance(p["dirty"], bool)' "$latest_run/state.json"
    } >"$run_dir/train.log" 2>&1; then
        echo "ERROR: H-004 run-provenance acceptance failed; see $run_dir/train.log" >&2
        exit 1
    fi
elif [ "$1" = "H-005" ]; then
    if ! uv run python -m unittest tests.test_pi_rpc_runner -v >"$run_dir/train.log" 2>&1; then
        echo "ERROR: H-005 pre-run warning acceptance failed; see $run_dir/train.log" >&2
        exit 1
    fi
elif [ "$1" = "H-006" ]; then
    if ! {
        uv run python -m unittest tests.test_check_judge -v
        make check-judge
    } >"$run_dir/train.log" 2>&1; then
        echo "ERROR: H-006 judge preflight acceptance failed; see $run_dir/train.log" >&2
        exit 1
    fi
elif [ "$1" = "H-007" ]; then
    if ! {
        uv run python -m unittest tests.test_check_judge -v
        env -u DEEPSEEK_API_KEY make check-judge
    } >"$run_dir/train.log" 2>&1; then
        echo "ERROR: H-007 judge provenance acceptance failed; see $run_dir/train.log" >&2
        exit 1
    fi
elif [ "$1" = "H-008" ]; then
    if ! {
        uv run python -m unittest tests.test_check_judge -v
        env -u DEEPSEEK_API_KEY make check-judge-config
    } >"$run_dir/train.log" 2>&1; then
        echo "ERROR: H-008 judge config acceptance failed; see $run_dir/train.log" >&2
        exit 1
    fi
elif [ "$1" = "H-009" ]; then
    if ! uv run python -m unittest tests.test_judge -v >"$run_dir/train.log" 2>&1; then
        echo "ERROR: H-009 strict schema acceptance failed; see $run_dir/train.log" >&2
        exit 1
    fi
elif [ "$1" = "H-010" ]; then
    if ! uv run python -m unittest tests.test_judge -v >"$run_dir/train.log" 2>&1; then
        echo "ERROR: H-010 judge request fingerprint acceptance failed; see $run_dir/train.log" >&2
        exit 1
    fi
elif [ "$1" = "H-011" ]; then
    if ! uv run python -m unittest tests.test_judge -v >"$run_dir/train.log" 2>&1; then
        echo "ERROR: H-011 malformed judge response redaction failed; see $run_dir/train.log" >&2
        exit 1
    fi
elif [ "$1" = "H-012" ]; then
    if ! uv run python -m unittest tests.test_judge -v >"$run_dir/train.log" 2>&1; then
        echo "ERROR: H-012 judge artifact privacy acceptance failed; see $run_dir/train.log" >&2
        exit 1
    fi
elif [ "$1" = "H-013" ]; then
    if ! uv run python -m unittest tests.test_judge -v >"$run_dir/train.log" 2>&1; then
        echo "ERROR: H-013 judge cache completeness acceptance failed; see $run_dir/train.log" >&2
        exit 1
    fi
elif [ "$1" = "H-014" ]; then
    if ! uv run python -m unittest tests.test_judge -v >"$run_dir/train.log" 2>&1; then
        echo "ERROR: H-014 judge input privacy acceptance failed; see $run_dir/train.log" >&2
        exit 1
    fi
elif [ "$1" = "H-015" ]; then
    if ! uv run python -m unittest tests.test_judge -v >"$run_dir/train.log" 2>&1; then
        echo "ERROR: H-015 judge URL safety acceptance failed; see $run_dir/train.log" >&2
        exit 1
    fi
elif [ "$1" = "H-016" ]; then
    if ! uv run python -m unittest tests.test_judge -v >"$run_dir/train.log" 2>&1; then
        echo "ERROR: H-016 judge origin validation acceptance failed; see $run_dir/train.log" >&2
        exit 1
    fi
elif [ "$1" = "H-017" ]; then
    if ! uv run python -m unittest tests.test_judge -v >"$run_dir/train.log" 2>&1; then
        echo "ERROR: H-017 judge redirect containment acceptance failed; see $run_dir/train.log" >&2
        exit 1
    fi
elif [ "$1" = "H-018" ]; then
    if ! uv run python -m unittest tests.test_judge -v >"$run_dir/train.log" 2>&1; then
        echo "ERROR: H-018 official Responses retention acceptance failed; see $run_dir/train.log" >&2
        exit 1
    fi
elif [ "$1" = "H-019" ]; then
    if ! uv run python -m unittest tests.test_pi_rpc_runner -v >"$run_dir/train.log" 2>&1; then
        echo "ERROR: H-019 RPC settlement acceptance failed; see $run_dir/train.log" >&2
        exit 1
    fi
elif ! uv run python -m unittest tests.test_setup_pi -v >"$run_dir/train.log" 2>&1; then
    echo "ERROR: $1 setup-policy training/acceptance suite failed; see $run_dir/train.log" >&2
    exit 1
fi
printf '%s\n' "$run_dir"
