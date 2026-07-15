ASTERION_PROVIDER ?= dci-agent-lite
ASTERION_ENV_FILE ?= .env
ASTERION_CORPUS_ROOT ?= $(CURDIR)/corpus
ASTERION_VERIFY_OUTPUT_ROOT ?= $(CURDIR)/outputs/asterion-verification

.PHONY: example runtime-example asterion-example asterion-runtime-example asterion-describe asterion-verify-preflight asterion-verify-basic asterion-verify-acceptance asterion-verify-complete check-pi-rpc check-judge check-judge-config test-typescript-host test-rust-executor check-rust-executor codex-example deepseek-example

example:
	bash scripts/examples/dci_basic_example.sh

runtime-example:
	bash scripts/examples/dci_runtime_context_example.sh

asterion-example:
	bash scripts/examples/asterion_dci_basic_example.sh

asterion-runtime-example:
	bash scripts/examples/asterion_dci_runtime_context_example.sh

asterion-describe:
	uv run asterion describe --provider "$(ASTERION_PROVIDER)"

asterion-verify-preflight:
	uv run asterion verify --provider "$(ASTERION_PROVIDER)" --level preflight \
		--env-file "$(ASTERION_ENV_FILE)" --corpus-root "$(ASTERION_CORPUS_ROOT)"

asterion-verify-basic:
	uv run asterion verify --provider "$(ASTERION_PROVIDER)" --level basic \
		--env-file "$(ASTERION_ENV_FILE)" --corpus-root "$(ASTERION_CORPUS_ROOT)" \
		--output-root "$(ASTERION_VERIFY_OUTPUT_ROOT)"

asterion-verify-acceptance:
	uv run asterion verify --provider "$(ASTERION_PROVIDER)" --level acceptance

asterion-verify-complete:
	uv run asterion verify --provider "$(ASTERION_PROVIDER)" --level complete \
		--env-file "$(ASTERION_ENV_FILE)" --corpus-root "$(ASTERION_CORPUS_ROOT)" \
		--output-root "$(ASTERION_VERIFY_OUTPUT_ROOT)"

check-pi-rpc:
	uv run python scripts/check_pi_rpc.py

check-judge:
	PYTHONPATH=src uv run python scripts/check_judge.py

check-judge-config:
	PYTHONPATH=src uv run python scripts/check_judge.py --config-only

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
