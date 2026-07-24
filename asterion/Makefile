UV_BIN ?= uv
ASTERION_PROVIDER ?= dci-agent-lite
ASTERION_ARGS ?=
DCI_ARGS ?=

.DEFAULT_GOAL := help

.PHONY: help sync build test lint docs-check check promotion-check setup-pi check-pi
.PHONY: setup-resources-basic check-resources-basic
.PHONY: setup-resources-benchmark check-resources-benchmark
.PHONY: doctor
.PHONY: asterion-list asterion-describe asterion-verify-preflight
.PHONY: asterion-verify-basic asterion-verify-acceptance asterion-verify-complete
.PHONY: asterion-run
.PHONY: dci-system-prompt dci-run dci-terminal dci-resume dci-evaluate
.PHONY: dci-benchmark dci-export dci-ablation dci-paper
.PHONY: test-typescript test-rust check-rust

help:
	@echo "provider-free lifecycle: sync build test lint docs-check check promotion-check"
	@echo "provider-free framework: asterion-list asterion-describe asterion-verify-acceptance"
	@echo "bounded provider-backed: asterion-verify-preflight asterion-verify-basic asterion-verify-complete asterion-run"
	@echo "DCI passthrough: dci-system-prompt dci-run dci-terminal dci-resume dci-evaluate dci-benchmark dci-export dci-ablation dci-paper"
	@echo "Cross-language provider-free: test-typescript test-rust check-rust"
	@echo "Cost boundary: full execution requires separate authorization"
	@echo "Arguments: ASTERION_ARGS='...' or DCI_ARGS='...'"

sync:
	$(UV_BIN) sync --frozen

build:
	$(UV_BIN) build .

test:
	$(UV_BIN) run python -m unittest discover -s tests -v

lint:
	$(UV_BIN) run python -m compileall -q src tests tools
	$(UV_BIN) run ruff check src tests tools

docs-check:
	$(UV_BIN) run python tools/check_docs.py

check: test lint docs-check test-typescript check-rust build

promotion-check:
	$(UV_BIN) run python tools/check_promotion.py

setup-pi:
	bash scripts/setup_pi.sh

check-pi:
	bash scripts/setup_pi.sh --check

setup-resources-basic:
	$(UV_BIN) run --extra setup python tools/setup_resources.py --profile basic

check-resources-basic:
	$(UV_BIN) run python tools/setup_resources.py --profile basic --check

setup-resources-benchmark:
	$(UV_BIN) run --extra setup python tools/setup_resources.py --profile benchmark

check-resources-benchmark:
	$(UV_BIN) run python tools/setup_resources.py --profile benchmark --check

doctor:
	$(UV_BIN) run asterion verify --provider $(ASTERION_PROVIDER) --level preflight $(ASTERION_ARGS)

asterion-list:
	$(UV_BIN) run asterion list $(ASTERION_ARGS)

asterion-describe:
	$(UV_BIN) run asterion describe --provider $(ASTERION_PROVIDER) $(ASTERION_ARGS)

asterion-verify-preflight:
	$(UV_BIN) run asterion verify --provider $(ASTERION_PROVIDER) --level preflight $(ASTERION_ARGS)

asterion-verify-basic:
	$(UV_BIN) run asterion verify --provider $(ASTERION_PROVIDER) --level basic $(ASTERION_ARGS)

asterion-verify-acceptance:
	$(UV_BIN) run asterion verify --provider $(ASTERION_PROVIDER) --level acceptance $(ASTERION_ARGS)

asterion-verify-complete:
	$(UV_BIN) run asterion verify --provider $(ASTERION_PROVIDER) --level complete $(ASTERION_ARGS)

asterion-run:
	$(UV_BIN) run asterion run $(ASTERION_ARGS)

dci-system-prompt:
	$(UV_BIN) run asterion-dci system-prompt $(DCI_ARGS)

dci-run:
	$(UV_BIN) run asterion-dci run $(DCI_ARGS)

dci-terminal:
	$(UV_BIN) run asterion-dci terminal $(DCI_ARGS)

dci-resume:
	$(UV_BIN) run asterion-dci resume $(DCI_ARGS)

dci-evaluate:
	$(UV_BIN) run asterion-dci evaluate $(DCI_ARGS)

dci-benchmark:
	$(UV_BIN) run asterion-dci benchmark $(DCI_ARGS)

dci-export:
	$(UV_BIN) run asterion-dci export $(DCI_ARGS)

dci-ablation:
	$(UV_BIN) run asterion-dci ablation $(DCI_ARGS)

dci-paper:
	$(UV_BIN) run asterion-dci paper $(DCI_ARGS)

test-typescript:
	npm ci --prefix packages/typescript/asterion-runtime
	npm test --prefix packages/typescript/asterion-runtime
	npm test --prefix packages/typescript/dci-context-extension

test-rust:
	cargo test --manifest-path packages/rust/controlled-executor/Cargo.toml

check-rust: test-rust
	cargo fmt --manifest-path packages/rust/controlled-executor/Cargo.toml -- --check
	cargo clippy --manifest-path packages/rust/controlled-executor/Cargo.toml -- -D warnings
