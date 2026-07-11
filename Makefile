.PHONY: example runtime-example codex-example deepseek-example

example:
	bash scripts/examples/dci_basic_example.sh

runtime-example:
	bash scripts/examples/dci_runtime_context_example.sh

codex-example:
	bash scripts/examples/dci_basic_openai_codex_example.sh

deepseek-example:
	bash scripts/examples/dci_basic_deepseek_example.sh
