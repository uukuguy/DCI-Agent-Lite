from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import verify_original_readme


def _sample_readme_text(
    *,
    include_override: bool = True,
    missing_level: str | None = None,
) -> str:
    quick_terminal_default = """PYTHONPATH=src uv run python -m dci.benchmark.pi_rpc_runner --terminal \\
  --cwd \"corpus/wiki_corpus\" \\
  --extra-arg=\"--thinking high\""""
    quick_terminal_override = """PYTHONPATH=src uv run python -m dci.benchmark.pi_rpc_runner --terminal \\
  --provider openai \\
  --model gpt-5.4-nano \\
  --cwd \"corpus/wiki_corpus\" \\
  --extra-arg=\"--thinking high\""""
    quick_programmatic_default = """PYTHONPATH=src uv run python -m dci.benchmark.pi_rpc_runner \\
  --cwd \"corpus/wiki_corpus\" \\
  --extra-arg=\"--thinking high\" \\
  \"Answer the following question using only wiki_dump.jsonl in the current directory. Question: In which street did the Great Fire of London originate?\""""
    quick_programmatic_override = """PYTHONPATH=src uv run python -m dci.benchmark.pi_rpc_runner \\
  --provider openai \\
  --model gpt-5.4-nano \\
  --cwd \"corpus/wiki_corpus\" \\
  --extra-arg=\"--thinking high\" \\
  \"Answer the following question using only wiki_dump.jsonl in the current directory. Question: In which street did the Great Fire of London originate?\""""

    override_blocks = ""
    if include_override:
        override_blocks = (
            "\n```bash\n"
            f"{quick_terminal_override}\n"
            "```\n\n```bash\n"
            f"{quick_programmatic_override}\n"
            "```\n"
        )

    context_levels = ["level0", "level1", "level2", "level3", "level4"]
    if missing_level in context_levels:
        context_levels = [level for level in context_levels if level != missing_level]
    if not context_levels:
        raise ValueError("at least one context level must remain in the sample")

    context_blocks = [
        f'--runtime-context-level "{level}" \\\n'
        '  --cwd \"corpus/wiki_corpus\" \\\n'
        "  --max-turns 6 \\\n"
        '"Answer the following question using only wiki_dump.jsonl in the current directory. '
        'Question: In which street did the Great Fire of London originate?"'
        for level in context_levels
    ]
    context_for = " ".join(context_levels)
    context_block = "\n".join(
        [f"for profile in {context_for}; do", "  " + "\n  ".join(context_blocks), "done"]
    )

    return f"""# Sample

## ⚡ Quick Start

```bash
{quick_terminal_default}
```

{override_blocks}

```bash
{quick_programmatic_default}
```

## 🚀 Context Management Strategies

For reproducibility, one short bounded command for each level:

```bash
{context_block}
```
"""


def _write_readme(text: str) -> Path:
    temporary_directory = tempfile.mkdtemp()
    path = Path(temporary_directory) / "README.md"
    path.write_text(text, encoding="utf-8")
    return path


class OriginalReadmeAcceptanceTests(unittest.TestCase):
    def test_readme_contract_passes_for_valid_literal_contract(self) -> None:
        readme = _write_readme(_sample_readme_text())
        try:
            self.assertEqual(
                verify_original_readme.verify_readme_contract(readme),
                ["quick-start contract: ok", "context-management contract: ok"],
            )
        finally:
            shutil.rmtree(readme.parent, ignore_errors=True)

    def test_readme_contract_fails_without_override(self) -> None:
        readme = _write_readme(_sample_readme_text(include_override=False))
        try:
            with self.assertRaises(ValueError):
                verify_original_readme.verify_readme_contract(readme)
        finally:
            shutil.rmtree(readme.parent, ignore_errors=True)

    def test_readme_contract_fails_missing_context_level(self) -> None:
        readme = _write_readme(_sample_readme_text(missing_level="level4"))
        try:
            with self.assertRaises(ValueError):
                verify_original_readme.verify_readme_contract(readme)
        finally:
            shutil.rmtree(readme.parent, ignore_errors=True)

    def test_parse_env_file(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "env"
            path.write_text(
                "\n".join(
                    [
                        "# this is comment",
                        "DCI_PROVIDER=openai-codex",
                        "DCI_MODEL=\"gpt-5.6-luna\"",
                        "export DCI_TOOLS=read,bash",
                    ]
                ),
                encoding="utf-8",
            )
            parsed = verify_original_readme._parse_env_file(path)
            self.assertEqual(
                parsed,
                {
                    "DCI_PROVIDER": "openai-codex",
                    "DCI_MODEL": "gpt-5.6-luna",
                    "DCI_TOOLS": "read,bash",
                },
            )
            self.assertEqual(
                verify_original_readme._parse_env_file(Path(path.parent / "missing")),
                {},
            )

    def test_bounded_contract_uses_expected_original_entrypoint_and_levels(self) -> None:
        readme = _write_readme(_sample_readme_text())
        calls: list[list[str]] = []

        def fake_run_command(
            args: list[str],
            *,
            cwd: Path,
            env: dict[str, str],
            timeout_seconds: int,
        ) -> subprocess.CompletedProcess[str]:
            del cwd, env, timeout_seconds
            calls.append(list(args))
            output_index = args.index("--output-dir")
            output_dir = Path(args[output_index + 1])
            output_dir.mkdir(parents=True, exist_ok=True)
            for name in (
                "question.txt",
                "final.txt",
                "state.json",
                "events.jsonl",
                "conversation_full.json",
                "effective-config.json",
            ):
                output_dir.joinpath(name).write_text("{}", encoding="utf-8")
            return subprocess.CompletedProcess(args, 0, "", "")

        with tempfile.TemporaryDirectory() as temporary_directory:
            output_root = Path(temporary_directory) / "outputs"
            with patch("tools.verify_original_readme._run_command", side_effect=fake_run_command):
                with patch.dict(
                    os.environ,
                    {
                        "DCI_PROVIDER": "openai-codex",
                        "DCI_MODEL": "gpt-5.6-luna",
                        "OPENAI_API_KEY": "fixture",
                    },
                ):
                    report = verify_original_readme.verify_bounded_contract(
                        readme_path=readme,
                        env_file=None,
                        output_root=output_root,
                        repo_root=readme.parent,
                    )
                    shutil.rmtree(readme.parent, ignore_errors=True)

            self.assertEqual(
                report,
                [
                    f"bounded quick-start: {(output_root / 'quick-start').resolve()}",
                    f"bounded level3: {(output_root / 'context-level3').resolve()}",
                    f"bounded level4: {(output_root / 'context-level4').resolve()}",
                ],
            )

        self.assertEqual(len(calls), 3)
        self.assertTrue(
            all("dci.benchmark.pi_rpc_runner" in " ".join(call) for call in calls)
        )
        self.assertTrue(any("--runtime pi" in " ".join(call) for call in calls))
        self.assertEqual(sum("--runtime-context-level" in token for call in calls for token in call), 2)


if __name__ == "__main__":
    unittest.main()
