.PHONY: example runtime-example asterion-example asterion-runtime-example check-pi-rpc check-judge check-judge-config test-typescript-host test-rust-executor check-rust-executor codex-example deepseek-example

example:
	bash scripts/examples/dci_basic_example.sh

runtime-example:
	bash scripts/examples/dci_runtime_context_example.sh

asterion-example:
	bash scripts/examples/asterion_dci_basic_example.sh

asterion-runtime-example:
	bash scripts/examples/asterion_dci_runtime_context_example.sh

check-pi-rpc:
	uv run python scripts/check_pi_rpc.py

check-judge:
	uv run python scripts/check_judge.py

check-judge-config:
	uv run python scripts/check_judge.py --config-only

test-typescript-host:
	npm --prefix packages/typescript/asterion-runtime test

test-rust-executor:
	cargo test --manifest-path packages/rust/controlled-executor/Cargo.toml

check-rust-executor:
	cargo fmt --manifest-path packages/rust/controlled-executor/Cargo.toml --check
	cargo clippy --manifest-path packages/rust/controlled-executor/Cargo.toml --all-targets -- -D warnings

codex-example:
	bash scripts/examples/dci_basic_openai_codex_example.sh

deepseek-example:
	bash scripts/examples/dci_basic_deepseek_example.sh
