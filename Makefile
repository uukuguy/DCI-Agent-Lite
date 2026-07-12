.PHONY: example runtime-example check-pi-rpc check-judge codex-example deepseek-example

example:
	bash scripts/examples/dci_basic_example.sh

runtime-example:
	bash scripts/examples/dci_runtime_context_example.sh

check-pi-rpc:
	uv run python scripts/check_pi_rpc.py

check-judge:
	uv run python scripts/check_judge.py

codex-example:
	bash scripts/examples/dci_basic_openai_codex_example.sh

deepseek-example:
	bash scripts/examples/dci_basic_deepseek_example.sh
