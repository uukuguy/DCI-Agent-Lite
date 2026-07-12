#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -ne 1 ]; then
    echo "Usage: $0 HYPOTHESIS_ID" >&2
    exit 2
fi
case "$1" in
    H-001|H-002|H-003|H-004|H-005|H-006|H-007|H-008|H-009|H-010|H-011|H-012|H-013|H-014|H-015|H-016|H-017|H-018|H-019|AF-050-H-001|AF-050-H-002|AF-050-H-003) ;;
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
    if ! cargo test --manifest-path packages/rust/executor/Cargo.toml --test authorization >"$run_dir/train.log" 2>&1; then
        echo "ERROR: AF-050-H-001 request authorization failed; see $run_dir/train.log" >&2
        exit 1
    fi
elif [ "$1" = "AF-050-H-002" ]; then
    if ! cargo test --manifest-path packages/rust/executor/Cargo.toml --test process >"$run_dir/train.log" 2>&1; then
        echo "ERROR: AF-050-H-002 direct process boundary failed; see $run_dir/train.log" >&2
        exit 1
    fi
elif [ "$1" = "AF-050-H-003" ]; then
    if ! cargo test --manifest-path packages/rust/executor/Cargo.toml --test process >"$run_dir/train.log" 2>&1; then
        echo "ERROR: AF-050-H-003 bounded process resources failed; see $run_dir/train.log" >&2
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
