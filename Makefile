ASTERION_PROVIDER ?= dci-agent-lite
ASTERION_ENV_FILE ?= .env
ASTERION_CORPUS_ROOT ?= $(CURDIR)/corpus
ASTERION_VERIFY_OUTPUT_ROOT ?= $(CURDIR)/outputs/asterion-verification

.PHONY: example runtime-example asterion-example asterion-runtime-example asterion-describe asterion-verify-preflight asterion-verify-basic asterion-verify-acceptance asterion-verify-complete asterion-integration-acceptance check-pi-rpc check-judge check-judge-config test-typescript-host test-rust-executor check-rust-executor codex-example deepseek-example

example:
	bash scripts/examples/dci_basic_example.sh

runtime-example:
	bash scripts/examples/dci_runtime_context_example.sh

asterion-example:
	bash scripts/examples/asterion_dci_basic_example.sh

asterion-runtime-example:
	bash scripts/examples/asterion_dci_runtime_context_example.sh

asterion-describe:
	$(MAKE) -C asterion asterion-describe \
		ASTERION_PROVIDER="$(ASTERION_PROVIDER)" ASTERION_ARGS=""

asterion-verify-preflight:
	$(MAKE) -C asterion asterion-verify-preflight \
		ASTERION_PROVIDER="$(ASTERION_PROVIDER)" \
		ASTERION_ARGS='--env-file "$(ASTERION_ENV_FILE)" --corpus-root "$(ASTERION_CORPUS_ROOT)"'

asterion-verify-basic:
	$(MAKE) -C asterion asterion-verify-basic \
		ASTERION_PROVIDER="$(ASTERION_PROVIDER)" \
		ASTERION_ARGS='--env-file "$(ASTERION_ENV_FILE)" --corpus-root "$(ASTERION_CORPUS_ROOT)" --output-root "$(ASTERION_VERIFY_OUTPUT_ROOT)"'

asterion-verify-acceptance:
	$(MAKE) -C asterion asterion-verify-acceptance \
		ASTERION_PROVIDER="$(ASTERION_PROVIDER)" ASTERION_ARGS=""

asterion-verify-complete:
	$(MAKE) -C asterion asterion-verify-complete \
		ASTERION_PROVIDER="$(ASTERION_PROVIDER)" \
		ASTERION_ARGS='--env-file "$(ASTERION_ENV_FILE)" --corpus-root "$(ASTERION_CORPUS_ROOT)" --output-root "$(ASTERION_VERIFY_OUTPUT_ROOT)"'

asterion-integration-acceptance:
	uv run python tools/verify_asterion_dci_product.py

check-pi-rpc:
	uv run python scripts/check_pi_rpc.py

check-judge:
	PYTHONPATH=src uv run python scripts/check_judge.py

check-judge-config:
	PYTHONPATH=src uv run python scripts/check_judge.py --config-only

test-typescript-host:
	npm --prefix asterion/packages/typescript/asterion-runtime test

test-rust-executor:
	cargo test --manifest-path asterion/packages/rust/controlled-executor/Cargo.toml

check-rust-executor:
	cargo fmt --manifest-path asterion/packages/rust/controlled-executor/Cargo.toml --check
	cargo clippy --manifest-path asterion/packages/rust/controlled-executor/Cargo.toml --all-targets -- -D warnings

codex-example:
	bash scripts/examples/dci_basic_openai_codex_example.sh

deepseek-example:
	bash scripts/examples/dci_basic_deepseek_example.sh
