#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -ne 1 ]; then
    echo "Usage: $0 HYPOTHESIS_ID" >&2
    exit 2
fi
case "$1" in
    H-001|H-002|H-003|H-004|H-005|H-006|H-007|H-008|H-009|H-010|H-011|H-012|H-013|H-014|H-015|H-016|H-017|H-018|H-019|AF-050-H-001|AF-050-H-002|AF-050-H-003|AF-050-H-004|AF-050-H-005|AF-060-H-001|AF-060-H-002|AF-060-H-003|AF-060-H-004|AF-060-H-005|AF-070-H-001|AF-070-H-002|AF-070-H-003|AF-070-H-004|AF-080-H-001|AF-080-H-002|AF-080-H-003|AF-080-H-004|AF-090-H-001|AF-090-H-002|AF-090-H-003|AF-090-H-004|AF-095-H-001|AF-095-H-002|AF-095-H-003|AF-095-H-004|AF-100-H-001|AF-100-H-002|AF-100-H-003|AF-100-H-004|AF-180-H-001|AF-180-H-002|AF-180-H-003|AF-180-H-004|AF-190-H-001|AF-190-H-002|AF-190-H-003|AF-190-H-004|AF-200-H-001|AF-200-H-002|AF-200-H-003|AF-200-H-004|AF-210-H-001|AF-210-H-002|AF-210-H-003|AF-210-H-004|AF-220-H-001|AF-220-H-002|AF-220-H-003|AF-220-H-004|AF-230-H-001|AF-230-H-002|AF-230-H-003|AF-230-H-004|AF-240-H-001|AF-240-H-002|AF-240-H-003|AF-240-H-004|AF-250-H-001|AF-250-H-002|AF-250-H-003|AF-250-H-004|AF-250-H-005|AF-310-H-001|AF-310-H-002|AF-310-H-003|AF-310-H-004|AF-310-H-005|AF-320-H-001|AF-320-H-002|AF-320-H-003|AF-330-H-001|AF-330-H-002|AF-330-H-003|AF-330-H-004|AF-340-H-001|AF-340-H-002|AF-340-H-003|AF-340-H-004) ;;
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
elif [ "$1" = "AF-230-H-001" ]; then
    paradigm="dci-unified-durable-recorder"
elif [ "$1" = "AF-230-H-002" ]; then
    paradigm="dci-processed-native-evidence"
elif [ "$1" = "AF-230-H-003" ]; then
    paradigm="dci-provenance-resume-safety"
elif [ "$1" = "AF-230-H-004" ]; then
    paradigm="dci-operator-terminal-parity"
elif [ "$1" = "AF-240-H-001" ]; then
    paradigm="dci-dataset-prompt-ir-parity"
elif [ "$1" = "AF-240-H-002" ]; then
    paradigm="dci-concurrent-durable-batch-reuse"
elif [ "$1" = "AF-240-H-003" ]; then
    paradigm="dci-evaluation-aggregate-analysis-parity"
elif [ "$1" = "AF-240-H-004" ]; then
    paradigm="dci-export-launcher-installed-parity"
elif [ "$1" = "AF-250-H-001" ]; then
    paradigm="dci-product-runnable-surface"
elif [ "$1" = "AF-250-H-002" ]; then
    paradigm="dci-product-stable-semantics"
elif [ "$1" = "AF-250-H-003" ]; then
    paradigm="dci-product-installed-independence"
elif [ "$1" = "AF-250-H-004" ]; then
    paradigm="dci-product-final-acceptance"
elif [ "$1" = "AF-250-H-005" ]; then
    paradigm="dci-product-provider-recovery"
elif [ "$1" = "AF-310-H-001" ]; then
    paradigm="dci-paper-context-contract"
elif [ "$1" = "AF-310-H-002" ]; then
    paradigm="dci-paper-live-context-transform"
elif [ "$1" = "AF-310-H-003" ]; then
    paradigm="dci-paper-packaged-context-transport"
elif [ "$1" = "AF-310-H-004" ]; then
    paradigm="dci-paper-context-product-surface"
elif [ "$1" = "AF-310-H-005" ]; then
    paradigm="dci-paper-context-bounded-runtime"
elif [ "$1" = "AF-320-H-001" ]; then
    paradigm="dci-paper-benchmark-inventory"
elif [ "$1" = "AF-320-H-002" ]; then
    paradigm="dci-paper-resolution-metrics"
elif [ "$1" = "AF-320-H-003" ]; then
    paradigm="dci-paper-trajectory-evidence"
elif [ "$1" = "AF-330-H-001" ]; then
    paradigm="dci-complete-application-composition"
elif [ "$1" = "AF-330-H-002" ]; then
    paradigm="dci-application-product-identity"
elif [ "$1" = "AF-330-H-003" ]; then
    paradigm="dci-restricted-pi-application"
elif [ "$1" = "AF-330-H-004" ]; then
    paradigm="dci-restricted-claude-application"
elif [ "$1" = "AF-340-H-001" ]; then
    paradigm="dci-reproduction-evidence"
elif [ "$1" = "AF-340-H-002" ]; then
    paradigm="dci-reproduction-statistics"
elif [ "$1" = "AF-340-H-003" ]; then
    paradigm="dci-reproduction-local-coordinator"
elif [ "$1" = "AF-340-H-004" ]; then
    paradigm="dci-reproduction-bounded-evidence"
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

evidence_kind="capability_acceptance"
candidate_status="tracked"
product_confirmation="true"
if [ "${1#AF-240-H-}" != "$1" ]; then
    evidence_kind="inventory_readiness"
    candidate_status="pending"
    product_confirmation="false"
elif [ "${1#AF-250-H-}" != "$1" ]; then
    evidence_kind="product_matrix_readiness"
    candidate_status="pending"
    product_confirmation="false"
fi

cat >"$run_dir/manifest.json" <<EOF
{
  "cycle": null,
  "hypothesis_id": "$1",
  "paradigm": "$paradigm",
  "run_id": "$run_id",
  "evidence_kind": "$evidence_kind",
  "candidate_status": "$candidate_status",
  "product_confirmation": $product_confirmation
}
EOF

if [ "$1" = "AF-050-H-001" ]; then
    if ! cargo test --manifest-path asterion/packages/rust/controlled-executor/Cargo.toml --test authorization >"$run_dir/train.log" 2>&1; then
        echo "ERROR: AF-050-H-001 request authorization failed; see $run_dir/train.log" >&2
        exit 1
    fi
elif [ "$1" = "AF-050-H-002" ]; then
    if ! cargo test --manifest-path asterion/packages/rust/controlled-executor/Cargo.toml --test process >"$run_dir/train.log" 2>&1; then
        echo "ERROR: AF-050-H-002 direct process boundary failed; see $run_dir/train.log" >&2
        exit 1
    fi
elif [ "$1" = "AF-050-H-003" ]; then
    if ! cargo test --manifest-path asterion/packages/rust/controlled-executor/Cargo.toml --test process >"$run_dir/train.log" 2>&1; then
        echo "ERROR: AF-050-H-003 bounded process resources failed; see $run_dir/train.log" >&2
        exit 1
    fi
elif [ "$1" = "AF-050-H-004" ]; then
    if ! cargo test --manifest-path asterion/packages/rust/controlled-executor/Cargo.toml --test service >"$run_dir/train.log" 2>&1; then
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
    if ! npm --prefix asterion/packages/typescript/asterion-runtime test >"$run_dir/train.log" 2>&1; then
        echo "ERROR: AF-060-H-004 TypeScript package parity failed; see $run_dir/train.log" >&2
        exit 1
    fi
elif [ "$1" = "AF-060-H-005" ]; then
    if ! {
        uv run python -m unittest discover -s tests -v
        (cd asterion && uv run python -m unittest discover -s tests -v)
        uv run python -m compileall -q src asterion/src/asterion asterion/tests tests tools
        uv run ruff check src asterion/src/asterion asterion/tests tests tools
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
    if ! npm --prefix asterion/packages/typescript/asterion-runtime test >"$run_dir/train.log" 2>&1; then
        echo "ERROR: AF-070-H-003 TypeScript reference manifest parity failed; see $run_dir/train.log" >&2
        exit 1
    fi
elif [ "$1" = "AF-070-H-004" ]; then
    if ! {
        uv run python -m unittest discover -s tests -v
        (cd asterion && uv run python -m unittest discover -s tests -v)
        uv run python -m compileall -q src asterion/src/asterion asterion/tests tests tools
        uv run ruff check src asterion/src/asterion asterion/tests tests tools
        npm --prefix asterion/packages/typescript/asterion-runtime ci
        npm --prefix asterion/packages/typescript/asterion-runtime test
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
        uv run python -m unittest discover -s tests -v
        (cd asterion && uv run python -m unittest discover -s tests -v)
        uv run python -m compileall -q src asterion/src/asterion asterion/tests tests tools
        uv run ruff check src asterion/src/asterion asterion/tests tests tools
        npm --prefix asterion/packages/typescript/asterion-runtime ci
        npm --prefix asterion/packages/typescript/asterion-runtime test
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
        uv run python -m unittest discover -s tests -v
        (cd asterion && uv run python -m unittest discover -s tests -v)
        uv run python -m compileall -q src asterion/src/asterion asterion/tests tests tools
        uv run ruff check src asterion/src/asterion asterion/tests tests tools
        npm --prefix asterion/packages/typescript/asterion-runtime ci
        npm --prefix asterion/packages/typescript/asterion-runtime test
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
        npm --prefix asterion/packages/typescript/asterion-runtime test
        cargo test --manifest-path asterion/packages/rust/controlled-executor/Cargo.toml
    } >"$run_dir/train.log" 2>&1; then
        echo "ERROR: AF-095-H-003 product directory separation failed; see $run_dir/train.log" >&2
        exit 1
    fi
elif [ "$1" = "AF-095-H-004" ]; then
    if ! {
        uv run python -m unittest discover -s tests -v
        (cd asterion && uv run python -m unittest discover -s tests -v)
        uv run python -m compileall -q src asterion/src/asterion asterion/tests tests tools
        uv run ruff check src asterion/src/asterion asterion/tests tests tools
        npm --prefix asterion/packages/typescript/asterion-runtime ci
        npm --prefix asterion/packages/typescript/asterion-runtime test
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
        uv run python -m unittest discover -s tests -v
        (cd asterion && uv run python -m unittest discover -s tests -v)
        uv run python -m compileall -q src asterion/src/asterion asterion/tests tests tools
        uv run ruff check src asterion/src/asterion asterion/tests tests tools
        npm --prefix asterion/packages/typescript/asterion-runtime ci
        npm --prefix asterion/packages/typescript/asterion-runtime test
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
    if ! { uv run python -m unittest tests.test_asterion_dci_cli -v && (cd asterion && uv run python -m unittest tests.test_asterion_cli -v); } >"$run_dir/train.log" 2>&1; then
        echo "ERROR: AF-180-H-003 DCI operator surface failed; see $run_dir/train.log" >&2
        exit 1
    fi
elif [ "$1" = "AF-180-H-004" ]; then
    if ! (cd asterion && uv run python -m unittest tests.test_asterion_dci_bridge tests.test_dci_research_capability -v) >"$run_dir/train.log" 2>&1; then
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
    if ! (cd asterion && uv run python -m unittest tests.test_asterion_dci_bridge -v) >"$run_dir/train.log" 2>&1; then
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
    if ! (cd asterion && uv run python -m unittest tests.test_asterion_dci_benchmark -v) >"$run_dir/train.log" 2>&1; then
        echo "ERROR: AF-200-H-003 benchmark orchestration failed; see $run_dir/train.log" >&2
        exit 1
    fi
elif [ "$1" = "AF-200-H-004" ]; then
    if ! { uv run python -m unittest tests.test_asterion_dci_cli -v && (cd asterion && uv run python -m unittest tests.test_asterion_dci_bridge -v); } >"$run_dir/train.log" 2>&1; then
        echo "ERROR: AF-200-H-004 evaluation operator surface failed; see $run_dir/train.log" >&2
        exit 1
    fi
elif [ "$1" = "AF-210-H-001" ]; then
    if ! uv run python -m unittest tests.test_asterion_dci_application_executor tests.test_asterion_dci_config -v >"$run_dir/train.log" 2>&1; then
        echo "ERROR: AF-210-H-001 native application executor failed; see $run_dir/train.log" >&2
        exit 1
    fi
elif [ "$1" = "AF-210-H-002" ]; then
    if ! (cd asterion && uv run python -m unittest tests.test_dci_research_capability tests.test_asterion_dci_bridge -v) >"$run_dir/train.log" 2>&1; then
        echo "ERROR: AF-210-H-002 Pi application dispatch failed; see $run_dir/train.log" >&2
        exit 1
    fi
elif [ "$1" = "AF-210-H-003" ]; then
    if ! { uv run python -m unittest tests.test_builtin_dci_application tests.test_distribution_boundaries -v && (cd asterion && uv run python -m unittest tests.test_asterion_cli -v); } >"$run_dir/train.log" 2>&1; then
        echo "ERROR: AF-210-H-003 installed application projection failed; see $run_dir/train.log" >&2
        exit 1
    fi
elif [ "$1" = "AF-210-H-004" ]; then
    if ! {
        uv run python -m unittest discover -s tests -v
        (cd asterion && uv run python -m unittest discover -s tests -v)
        uv run python -m compileall -q src asterion/src/asterion asterion/tests tests tools
        uv run ruff check src asterion/src/asterion asterion/tests tests tools
        npm --prefix asterion/packages/typescript/asterion-runtime ci
        npm --prefix asterion/packages/typescript/asterion-runtime test
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
    if ! { uv run python -m unittest tests.test_asterion_dci_cli -v && (cd asterion && uv run python -m unittest tests.test_asterion_dci_benchmark -v); } >"$run_dir/train.log" 2>&1; then
        echo "ERROR: AF-220-H-003 package and batch propagation failed; see $run_dir/train.log" >&2
        exit 1
    fi
elif [ "$1" = "AF-220-H-004" ]; then
    if ! uv run python -m unittest tests.test_asterion_dci_application_executor tests.test_builtin_dci_application tests.test_asterion_dci_cli -v >"$run_dir/train.log" 2>&1; then
        echo "ERROR: AF-220-H-004 installed application and examples failed; see $run_dir/train.log" >&2
        exit 1
    fi
elif [ "$1" = "AF-230-H-001" ]; then
    if ! uv run python -m unittest tests.test_asterion_dci_run tests.test_asterion_dci_artifacts tests.test_asterion_dci_application_executor tests.test_builtin_dci_application -v >"$run_dir/train.log" 2>&1; then
        echo "ERROR: AF-230-H-001 unified recorder acceptance failed; see $run_dir/train.log" >&2
        exit 1
    fi
elif [ "$1" = "AF-230-H-002" ]; then
    if ! uv run python -m unittest tests.test_asterion_dci_artifacts tests.test_asterion_dci_run -v >"$run_dir/train.log" 2>&1; then
        echo "ERROR: AF-230-H-002 native evidence acceptance failed; see $run_dir/train.log" >&2
        exit 1
    fi
elif [ "$1" = "AF-230-H-003" ]; then
    if ! uv run python -m unittest tests.test_asterion_dci_artifacts tests.test_asterion_dci_run -v >"$run_dir/train.log" 2>&1; then
        echo "ERROR: AF-230-H-003 provenance and resume safety failed; see $run_dir/train.log" >&2
        exit 1
    fi
elif [ "$1" = "AF-230-H-004" ]; then
    if ! uv run python -m unittest tests.test_asterion_dci_pi_rpc tests.test_asterion_dci_cli -v >"$run_dir/train.log" 2>&1; then
        echo "ERROR: AF-230-H-004 operator and terminal parity failed; see $run_dir/train.log" >&2
        exit 1
    fi
elif [ "$1" = "AF-240-H-001" ]; then
    if ! uv run python -m unittest \
        tests.test_climb_tools.Af240InventoryTests.test_af240_h001_dataset_mapping_readiness \
        tests.test_climb_tools.Af240InventoryTests.test_af240_h001_prompt_mapping_readiness \
        tests.test_climb_tools.Af240InventoryTests.test_af240_h001_retrieval_mapping_readiness \
        tests.test_climb_tools.Af240InventoryTests.test_af240_h001_ir_metric_mapping_readiness \
        -v >"$run_dir/train.log" 2>&1; then
        echo "ERROR: $1 AF-240 inventory readiness failed; see $run_dir/train.log" >&2
        exit 1
    fi
elif [ "$1" = "AF-240-H-002" ]; then
    if ! uv run python -m unittest \
        tests.test_climb_tools.Af240InventoryTests.test_af240_h002_nested_coordinator_mapping_readiness \
        tests.test_climb_tools.Af240InventoryTests.test_af240_h002_durable_query_mapping_readiness \
        tests.test_climb_tools.Af240InventoryTests.test_af240_h002_reuse_mapping_readiness \
        tests.test_climb_tools.Af240InventoryTests.test_af240_h002_cancellation_mapping_readiness \
        -v >"$run_dir/train.log" 2>&1; then
        echo "ERROR: $1 AF-240 inventory readiness failed; see $run_dir/train.log" >&2
        exit 1
    fi
elif [ "$1" = "AF-240-H-003" ]; then
    if ! uv run python -m unittest \
        tests.test_climb_tools.Af240InventoryTests.test_af240_h003_judge_mapping_readiness \
        tests.test_climb_tools.Af240InventoryTests.test_af240_h003_aggregate_metric_mapping_readiness \
        tests.test_climb_tools.Af240InventoryTests.test_af240_h003_analysis_mapping_readiness \
        tests.test_climb_tools.Af240InventoryTests.test_af240_h003_figure_mapping_readiness \
        -v >"$run_dir/train.log" 2>&1; then
        echo "ERROR: $1 AF-240 inventory readiness failed; see $run_dir/train.log" >&2
        exit 1
    fi
elif [ "$1" = "AF-240-H-004" ]; then
    if ! uv run python -m unittest \
        tests.test_climb_tools.Af240InventoryTests.test_af240_h004_extractor_mapping_readiness \
        tests.test_climb_tools.Af240InventoryTests.test_af240_h004_export_mapping_readiness \
        tests.test_climb_tools.Af240InventoryTests.test_af240_h004_launcher_mapping_readiness \
        tests.test_climb_tools.Af240InventoryTests.test_af240_h004_installed_resource_mapping_readiness \
        -v >"$run_dir/train.log" 2>&1; then
        echo "ERROR: $1 AF-240 inventory readiness failed; see $run_dir/train.log" >&2
        exit 1
    fi
elif [ "$1" = "AF-250-H-001" ]; then
    if ! uv run python -m unittest \
        tests.test_asterion_dci_product_parity.AsterionDciProductParityTests.test_af250_h001_exact_product_row_surface \
        tests.test_asterion_dci_product_parity.AsterionDciProductParityTests.test_af250_h001_source_entry_points_exist \
        tests.test_asterion_dci_product_parity.AsterionDciProductParityTests.test_af250_h001_asterion_entry_points_exist \
        tests.test_asterion_dci_product_parity.AsterionDciProductParityTests.test_af250_h001_local_selectors_resolve \
        -v >"$run_dir/train.log" 2>&1; then
        echo "ERROR: $1 product surface readiness failed; see $run_dir/train.log" >&2
        exit 1
    fi
elif [ "$1" = "AF-250-H-002" ]; then
    if ! uv run python -m unittest \
        tests.test_asterion_dci_product_parity.AsterionDciProductParityTests.test_af250_h002_rows_define_stable_semantics \
        tests.test_asterion_dci_product_parity.AsterionDciProductParityTests.test_af250_h002_products_keep_distinct_entry_points \
        tests.test_asterion_dci_product_parity.AsterionDciProductParityTests.test_af250_h002_batch_row_delegates_to_digest_bound_inventory \
        tests.test_asterion_dci_product_parity.AsterionDciProductParityTests.test_af250_h002_matrix_contains_no_placeholder_text \
        -v >"$run_dir/train.log" 2>&1; then
        echo "ERROR: $1 stable semantics readiness failed; see $run_dir/train.log" >&2
        exit 1
    fi
elif [ "$1" = "AF-250-H-003" ]; then
    if ! uv run python -m unittest \
        tests.test_asterion_dci_product_parity.AsterionDciProductParityTests.test_af250_h003_installed_rows_are_explicit \
        tests.test_asterion_dci_product_parity.AsterionDciProductParityTests.test_af250_h003_wheel_row_names_distribution_boundaries \
        tests.test_asterion_dci_product_parity.AsterionDciProductParityTests.test_af250_h003_application_row_names_bundled_assembly \
        tests.test_asterion_dci_product_parity.AsterionDciProductParityTests.test_af250_h003_installed_evidence_is_model_free \
        -v >"$run_dir/train.log" 2>&1; then
        echo "ERROR: $1 installed independence readiness failed; see $run_dir/train.log" >&2
        exit 1
    fi
elif [ "$1" = "AF-250-H-004" ]; then
    if ! uv run python -m unittest \
        tests.test_asterion_dci_product_parity.AsterionDciProductParityTests.test_af250_h004_all_rows_are_supported \
        tests.test_asterion_dci_product_parity.AsterionDciProductParityTests.test_af250_h004_provider_cases_are_body_free_ids \
        tests.test_asterion_dci_product_parity.AsterionDciProductParityTests.test_af250_h004_local_executor_never_runs_provider_cases \
        tests.test_asterion_dci_product_parity.AsterionDciProductParityTests.test_af250_h004_matrix_schema_and_inventory_are_finalized \
        -v >"$run_dir/train.log" 2>&1; then
        echo "ERROR: $1 final matrix readiness failed; see $run_dir/train.log" >&2
        exit 1
    fi
elif [ "$1" = "AF-250-H-005" ]; then
    if ! uv run python -m unittest \
        tests.test_asterion_dci_product_acceptance.AsterionDciProductAcceptanceTests.test_af250_h005_manifest_is_canonical_and_digest_bound \
        tests.test_asterion_dci_product_acceptance.AsterionDciProductAcceptanceTests.test_af250_h005_all_seven_provider_cases_are_successful \
        tests.test_asterion_dci_product_acceptance.AsterionDciProductAcceptanceTests.test_af250_h005_manifest_rejects_bodies_credentials_and_private_paths \
        tests.test_asterion_dci_product_acceptance.AsterionDciProductAcceptanceTests.test_af250_h005_private_acceptance_recomputes_artifacts_and_semantics \
        -v >"$run_dir/train.log" 2>&1; then
        echo "ERROR: $1 provider recovery readiness failed; see $run_dir/train.log" >&2
        exit 1
    fi
elif [ "$1" = "AF-310-H-001" ]; then
    if ! uv run --project asterion python -m unittest \
        tests.test_asterion_dci_context_profiles \
        tests.test_asterion_dci_config \
        tests.test_asterion_dci_run \
        -v >"$run_dir/train.log" 2>&1; then
        echo "ERROR: $1 context profile contract failed; see $run_dir/train.log" >&2
        exit 1
    fi
elif [ "$1" = "AF-310-H-002" ]; then
    if ! npm --prefix asterion/packages/typescript/dci-context-extension test \
        >"$run_dir/train.log" 2>&1; then
        echo "ERROR: $1 live context policy failed; see $run_dir/train.log" >&2
        exit 1
    fi
elif [ "$1" = "AF-310-H-003" ]; then
    if ! {
        uv run --project asterion python -m unittest \
            tests.test_asterion_dci_context_extension \
            tests.test_asterion_dci_pi_rpc \
            tests.test_asterion_dci_artifacts \
            tests.test_asterion_dci_run -v
        (cd asterion && uv run python -m unittest tests.test_asterion_dci_bridge -v)
    } >"$run_dir/train.log" 2>&1; then
        echo "ERROR: $1 packaged context transport failed; see $run_dir/train.log" >&2
        exit 1
    fi
elif [ "$1" = "AF-310-H-004" ]; then
    if ! {
        uv run --project asterion python -m unittest \
            tests.test_asterion_dci_cli \
            tests.test_asterion_dci_batch \
            tests.test_asterion_dci_application_executor \
            tests.test_asterion_dci_context_extension -v
        (cd asterion && uv run python -m unittest \
            tests.test_dci_research_capability \
            tests.test_asterion_dci_bridge -v)
    } >"$run_dir/train.log" 2>&1; then
        echo "ERROR: $1 context product surface failed; see $run_dir/train.log" >&2
        exit 1
    fi
elif [ "$1" = "AF-310-H-005" ]; then
    if ! uv run --project asterion python -m unittest \
        tests.test_asterion_dci_verification \
        tests.test_asterion_dci_pi_rpc \
        tests.test_asterion_dci_run -v >"$run_dir/train.log" 2>&1; then
        echo "ERROR: $1 bounded context acceptance failed; see $run_dir/train.log" >&2
        exit 1
    fi
elif [ "$1" = "AF-320-H-001" ]; then
    if ! uv run --project asterion python -m unittest \
        tests.test_asterion_dci_paper_benchmarks \
        tests.test_asterion_dci_metrics \
        tests.test_asterion_dci_datasets \
        tests.test_asterion_dci_batch_launchers \
        tests.test_asterion_dci_batch.AsterionDciBatchTests.test_af320_every_bound_paper_profile_fails_before_input_or_provider \
        tests.test_asterion_dci_batch.AsterionDciBatchTests.test_af320_copied_paper_dataset_is_digest_gated_without_profile \
        -v >"$run_dir/train.log" 2>&1; then
        echo "ERROR: $1 paper inventory and BEIR acceptance failed; see $run_dir/train.log" >&2
        exit 1
    fi
elif [ "$1" = "AF-320-H-002" ]; then
    if ! uv run --project asterion python -m unittest \
        tests.test_asterion_dci_resolution_metrics \
        tests.test_asterion_dci_analysis \
        tests.test_asterion_dci_paper_resolution_analysis \
        tests.test_asterion_dci_export \
        -v >"$run_dir/train.log" 2>&1; then
        echo "ERROR: $1 paper resolution metric acceptance failed; see $run_dir/train.log" >&2
        exit 1
    fi
elif [ "$1" = "AF-320-H-003" ]; then
    if ! uv run --project asterion python -m unittest \
        tests.test_asterion_dci_trajectory_resolution \
        tests.test_asterion_dci_artifacts \
        tests.test_asterion_dci_batch \
        -v >"$run_dir/train.log" 2>&1; then
        echo "ERROR: $1 paper trajectory evidence acceptance failed; see $run_dir/train.log" >&2
        exit 1
    fi
elif [ "$1" = "AF-330-H-001" ]; then
    if ! {
        (cd asterion && uv run python -m unittest tests.test_dci_complete_application -v)
        uv run --project asterion python -m unittest \
            tests.test_package_composition \
            tests.test_package_catalog \
            tests.test_application_assembly -v
    } >"$run_dir/train.log" 2>&1; then
        echo "ERROR: $1 complete application composition failed; see $run_dir/train.log" >&2
        exit 1
    fi
elif [ "$1" = "AF-330-H-002" ]; then
    if ! {
        (cd asterion && uv run python -m unittest tests.test_dci_complete_application -v)
        uv run --project asterion python -m unittest \
            tests.test_distribution_boundaries.BuiltDistributionBoundaryTests.test_asterion_is_the_only_buildable_wheel \
            tests.test_asterion_structure.AsterionStructureTests.test_declarative_assets_have_product_level_owners -v
    } >"$run_dir/train.log" 2>&1; then
        echo "ERROR: $1 complete application product identity failed; see $run_dir/train.log" >&2
        exit 1
    fi
elif [ "$1" = "AF-330-H-003" ]; then
    if ! {
        (cd asterion && uv run python -m unittest \
            tests.test_dci_complete_application.DciRestrictedPiEvidenceTests -v)
        uv run --project asterion python -m unittest \
            tests.test_asterion_dci_application_executor.AsterionDciApplicationExecutorTests.test_restricted_executor_honors_closed_request_tool_surface -v
    } >"$run_dir/train.log" 2>&1; then
        echo "ERROR: $1 restricted Pi acceptance failed; see $run_dir/train.log" >&2
        exit 1
    fi
elif [ "$1" = "AF-330-H-004" ]; then
    if [ -z "${AF330_CLAUDE_RUN_DIR:-}" ] || [ -z "${AF330_CLAUDE_CORPUS_DIR:-}" ] || [ -z "${AF330_CLAUDE_REPORT:-}" ]; then
        echo "ERROR: $1 requires retained private Claude evidence paths." >&2
        exit 2
    fi
    if ! {
        uv run python -m unittest tests.test_claude_code_runtime -v
        (cd asterion && uv run python -m unittest \
            tests.test_asterion_claude_runtime \
            tests.test_dci_complete_application.DciCompleteApplicationExecutionTests.test_claude_run_is_judged_and_exports_without_private_bodies \
            tests.test_dci_complete_application.DciRestrictedClaudeEvidenceTests -v)
        uv run python tools/verify_af330_claude_evidence.py \
            --repo-root "$ROOT" \
            --run-dir "$AF330_CLAUDE_RUN_DIR" \
            --corpus-dir "$AF330_CLAUDE_CORPUS_DIR" \
            --report "$AF330_CLAUDE_REPORT" \
            --record "$ROOT/docs/status/climb/provider-evidence/af-330-h-004.json"
    } >"$run_dir/train.log" 2>&1; then
        echo "ERROR: $1 restricted Claude acceptance failed; see $run_dir/train.log" >&2
        exit 1
    fi
elif [ "$1" = "AF-340-H-001" ]; then
    if ! uv run python -m unittest -v \
        tests.test_asterion_dci_reproduction >"$run_dir/train.log" 2>&1; then
        echo "ERROR: $1 normalized reproduction evidence failed; see $run_dir/train.log" >&2
        exit 1
    fi
elif [ "$1" = "AF-340-H-002" ]; then
    if ! uv run python -m unittest -v \
        tests.test_asterion_dci_reproduction \
        tests.test_asterion_dci_paper_resolution_analysis \
        tests.test_asterion_dci_paper_product >"$run_dir/train.log" 2>&1; then
        echo "ERROR: $1 statistical reproduction comparison failed; see $run_dir/train.log" >&2
        exit 1
    fi
elif [ "$1" = "AF-340-H-003" ]; then
    if ! uv run python -m unittest -v \
        tests.test_af340_reproduction_verifier \
        tests.test_original_readme_acceptance \
        tests.test_asterion_documentation >"$run_dir/train.log" 2>&1; then
        echo "ERROR: $1 local reproduction coordinator failed; see $run_dir/train.log" >&2
        exit 1
    fi
elif [ "$1" = "AF-340-H-004" ]; then
    : "${AF340_RESOURCE_ROOT:?set AF340_RESOURCE_ROOT to the exact bounded resource tree}"
    : "${AF340_PI_REPORT:?set AF340_PI_REPORT to the retained Pi bounded report}"
    : "${AF340_CLAUDE_MINIMAX_REPORT:?set AF340_CLAUDE_MINIMAX_REPORT to the retained Claude MiniMax report}"
    if ! uv run python tools/verify_af340_reproduction.py inspect \
        --resource-root "$AF340_RESOURCE_ROOT" \
        --report "$AF340_PI_REPORT" \
        --report "$AF340_CLAUDE_MINIMAX_REPORT" \
        >"$run_dir/train.log" 2>&1; then
        echo "ERROR: $1 bounded reproduction evidence failed; see $run_dir/train.log" >&2
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
