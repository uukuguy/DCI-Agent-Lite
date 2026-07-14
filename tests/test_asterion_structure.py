from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class AsterionStructureTests(unittest.TestCase):
    def test_runtime_objects_are_independent_and_wire_compatible(self) -> None:
        from asterion.runtime.host import AgentRuntimeClient as NewClient
        from asterion.runtime.protocol import PROTOCOL_VERSION as new_version
        from dci.framework.host import AgentRuntimeClient as OldClient
        from dci.framework.protocol import PROTOCOL_VERSION as old_version

        self.assertEqual(new_version, "dci.agent-runtime/v1")
        self.assertIsNot(OldClient, NewClient)
        self.assertEqual(old_version, new_version)

    def test_runtime_adapters_are_independent_and_capability_compatible(self) -> None:
        from asterion.adapters.claude_code import (
            ClaudeCodeProtocolAdapter as NewClaudeAdapter,
        )
        from asterion.adapters.pi import PiProtocolAdapter as NewPiAdapter
        from asterion.runtimes.claude_code import run_claude_code as new_run
        from dci.framework.adapters.claude_code import (
            ClaudeCodeProtocolAdapter as OldClaudeAdapter,
        )
        from dci.framework.adapters.pi import PiProtocolAdapter as OldPiAdapter
        from dci.framework.runtimes.claude_code import run_claude_code as old_run

        self.assertIsNot(OldPiAdapter, NewPiAdapter)
        self.assertIsNot(OldClaudeAdapter, NewClaudeAdapter)
        self.assertIsNot(old_run, new_run)
        self.assertEqual(
            OldPiAdapter.__module__, "dci.framework.adapters.pi"
        )
        self.assertEqual(
            NewPiAdapter.__module__, "asterion.adapters.pi"
        )

    def test_asterion_never_imports_dci(self) -> None:
        source_root = ROOT / "packages/python/asterion-core/src/asterion"
        self.assertTrue(source_root.is_dir())
        source = "\n".join(path.read_text() for path in source_root.rglob("*.py"))
        self.assertNotRegex(source, r"(?:from|import)\s+dci(?:\.|\s|$)")

    def test_only_asterion_has_a_wheel_root(self) -> None:
        workspace = (ROOT / "pyproject.toml").read_text()
        core = (ROOT / "packages/python/asterion-core/pyproject.toml").read_text()
        self.assertIn("package = false", workspace)
        self.assertNotIn("[build-system]", workspace)
        self.assertNotIn('packages = ["src/dci"]', workspace)
        self.assertIn('packages = ["src/asterion"]', core)
        self.assertNotIn('"src/dci"', core)

    def test_package_and_assembly_objects_are_independent_wire_implementations(self) -> None:
        from asterion.assembly.protocol import AssemblyPlan as NewPlan
        from asterion.packages.catalog import PackageCatalog as NewCatalog
        from asterion.packages.composition import PackageComposition as NewComposition
        from asterion.services.executor_protocol import ExecutorProtocolError as NewError
        from dci.framework.assembly import AssemblyPlan as OldPlan
        from dci.framework.executor_protocol import ExecutorProtocolError as OldError
        from dci.framework.package_catalog import PackageCatalog as OldCatalog
        from dci.framework.packages import PackageComposition as OldComposition

        self.assertIsNot(OldPlan, NewPlan)
        self.assertIsNot(OldCatalog, NewCatalog)
        self.assertIsNot(OldComposition, NewComposition)
        self.assertIsNot(OldError, NewError)

    def test_dci_framework_is_frozen_baseline_owned_behavior(self) -> None:
        source = "\n".join(
            path.read_text() for path in (ROOT / "src/dci/framework").rglob("*.py")
        )
        self.assertNotIn("Compatibility exports", source)
        self.assertNotRegex(source, r"(?:from|import)\s+asterion(?:\.|\s|$)")
        self.assertIn("class ProtocolError", source)
        self.assertIn("class PiProtocolAdapter", source)

    def test_extracted_wire_protocol_literals_remain_stable(self) -> None:
        from asterion.assembly.protocol import ASSEMBLY_PROTOCOL_VERSION
        from asterion.packages.protocol import PACKAGE_PROTOCOL_VERSION
        from asterion.runtime.protocol import PROTOCOL_VERSION
        from asterion.services.executor_protocol import EXECUTOR_PROTOCOL_VERSION

        self.assertEqual(PROTOCOL_VERSION, "dci.agent-runtime/v1")
        self.assertEqual(PACKAGE_PROTOCOL_VERSION, "dci.package/v1")
        self.assertEqual(ASSEMBLY_PROTOCOL_VERSION, "dci.assembly/v1")
        self.assertEqual(EXECUTOR_PROTOCOL_VERSION, "dci.executor/v1")

    def test_declarative_assets_have_product_level_owners(self) -> None:
        capabilities = ROOT / "capabilities"
        bundled = ROOT / "packages/python/asterion-core/src/asterion"
        if capabilities.exists():
            self.assertEqual({path.name for path in capabilities.iterdir()}, set())
        self.assertEqual(
            {
                path.name
                for path in (bundled / "capabilities").iterdir()
                if path.is_dir() and not path.name.startswith("__")
            },
            {"controlled_code", "dci_research"},
        )
        self.assertTrue(
            (
                bundled
                / "applications/dci_agent_lite/assemblies/dci-local-research.json"
            ).is_file()
        )
        package_ids = set()
        manifest_paths = list(capabilities.rglob("manifests/*.json"))
        manifest_paths.extend(bundled.rglob("manifests/*.json"))
        for path in manifest_paths:
            import json

            package_ids.add(json.loads(path.read_text())["package_id"])
        self.assertEqual(
            package_ids,
            {
                "dci.evaluation",
                "dci.research",
                "evaluation.code-quality",
                "observability.execution-audit",
                "policy.controlled-code-check",
                "policy.local-corpus",
                "protocol.observability",
                "workflow.code-quality",
            },
        )

    def test_cross_language_working_directories_are_asterion_owned(self) -> None:
        self.assertTrue((ROOT / "packages/typescript/asterion-runtime").is_dir())
        self.assertTrue((ROOT / "packages/rust/controlled-executor").is_dir())
        self.assertFalse((ROOT / "packages/typescript/agent-runtime").exists())
        self.assertFalse((ROOT / "packages/rust/executor").exists())

    def test_verified_dci_examples_use_the_source_baseline(self) -> None:
        for name in ("dci_basic_example.sh", "dci_runtime_context_example.sh"):
            source = (ROOT / "scripts/examples" / name).read_text()
            self.assertIn(
                'PYTHONPATH="$REPO_ROOT/src" uv run python -m dci.benchmark.pi_rpc_runner',
                source,
            )
            self.assertIn('source "$REPO_ROOT/.env"', source)

    def test_examples_execute_with_pairwise_semantic_parity(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir).resolve()
            subprocess.run(["git", "init", "-q", str(repo)], check=True)
            (repo / "scripts/examples").mkdir(parents=True)
            (repo / "corpus/wiki_corpus").mkdir(parents=True)
            (repo / "corpus/bc_plus_docs").mkdir(parents=True)
            bin_dir = repo / "bin"
            bin_dir.mkdir()
            uv = bin_dir / "uv"
            uv.write_text(
                '#!/usr/bin/env bash\nprintf "%s\\0" "$@" > "$UV_ARGS_LOG"\n'
            )
            uv.chmod(0o755)
            base_env = {
                **os.environ,
                "PATH": f"{bin_dir}:{os.environ['PATH']}",
                "DCI_PROVIDER": "synthetic-provider",
                "DCI_MODEL": "synthetic-model",
                "ASTERION_DCI_CORPUS_ROOT": str(repo / "corpus"),
            }
            script_names = (
                "dci_basic_example.sh",
                "dci_runtime_context_example.sh",
                "asterion_dci_basic_example.sh",
                "asterion_dci_runtime_context_example.sh",
            )
            commands: dict[str, list[str]] = {}
            for name in script_names:
                shutil.copy(
                    ROOT / "scripts/examples" / name,
                    repo / "scripts/examples" / name,
                )
                log = repo / f"{name}.argv"
                env = {**base_env, "UV_ARGS_LOG": str(log)}
                script_argv = ["bash", str(repo / "scripts/examples" / name)]
                if "runtime_context" in name:
                    script_argv.append("deliberate")
                result = subprocess.run(
                    script_argv,
                    cwd=repo,
                    env=env,
                    text=True,
                    capture_output=True,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertNotIn("synthetic-provider", result.stdout + result.stderr)
                self.assertNotIn("synthetic-model", result.stdout + result.stderr)
                commands[name] = [
                    item.decode() for item in log.read_bytes().split(b"\0") if item
                ]

            basic_question = (
                "Answer the following question using only wiki_dump.jsonl in the "
                "current directory. Do not use web search. Use rg instead of grep for "
                "fast searching. Question: In which street did the Great Fire of "
                "London originate?"
            )
            runtime_question = (
                "Read the files in the current directory. Do not use web search. Use "
                "rg instead of grep when searching. Question: In the Bonang Matheba "
                "interview where the third-to-last question asks about the origin of "
                "the name given to her by radio listeners, what is the interviewer's "
                "first name? Answer with just the first name and one supporting file "
                "path."
            )
            source_prefix = ["run", "python", "-m", "dci.benchmark.pi_rpc_runner"]
            asterion_prefix = ["run", "asterion-dci", "run"]
            wiki = str(repo / "corpus/wiki_corpus")
            bc_plus = str(repo / "corpus/bc_plus_docs")
            self.assertEqual(
                commands["dci_basic_example.sh"],
                source_prefix
                + ["--cwd", wiki, "--extra-arg=--thinking high", basic_question],
            )
            self.assertEqual(
                commands["asterion_dci_basic_example.sh"],
                asterion_prefix
                + ["--cwd", wiki, "--extra-arg=--thinking high", basic_question],
            )
            self.assertEqual(
                commands["dci_runtime_context_example.sh"],
                source_prefix
                + [
                    "--cwd",
                    bc_plus,
                    "--tools",
                    "read,bash",
                    "--show-tools",
                    "--max-turns",
                    "6",
                    "--eval-answer",
                    "Adaku",
                    "--extra-arg=--thinking deliberate",
                    runtime_question,
                ],
            )
            self.assertEqual(
                commands["asterion_dci_runtime_context_example.sh"],
                asterion_prefix
                + [
                    "--cwd",
                    bc_plus,
                    "--tools",
                    "read,bash",
                    "--max-turns",
                    "6",
                    "--thinking-level",
                    "deliberate",
                    "--eval-answer",
                    "Adaku",
                    runtime_question,
                ],
            )

            def option(argv: list[str], name: str) -> str | None:
                if name not in argv:
                    return None
                return argv[argv.index(name) + 1]

            def semantics(argv: list[str]) -> dict[str, str | None]:
                thinking = option(argv, "--thinking-level")
                if thinking is None:
                    thinking_arg = next(
                        item
                        for item in argv
                        if item.startswith("--extra-arg=--thinking ")
                    )
                    thinking = thinking_arg.removeprefix("--extra-arg=--thinking ")
                return {
                    "question": argv[-1],
                    "corpus": option(argv, "--cwd"),
                    "tools": option(argv, "--tools"),
                    "thinking": thinking,
                    "max_turns": option(argv, "--max-turns"),
                    "eval_answer": option(argv, "--eval-answer"),
                }

            self.assertEqual(
                semantics(commands["dci_basic_example.sh"]),
                semantics(commands["asterion_dci_basic_example.sh"]),
            )
            self.assertEqual(
                semantics(commands["dci_runtime_context_example.sh"]),
                semantics(commands["asterion_dci_runtime_context_example.sh"]),
            )

            for name, argv in commands.items():
                if name.startswith("asterion_"):
                    self.assertEqual(argv[:3], asterion_prefix)
                    self.assertNotIn("dci.benchmark.pi_rpc_runner", argv)
                else:
                    self.assertEqual(argv[:4], source_prefix)
                    self.assertNotIn("asterion-dci", argv)

    def test_workspace_does_not_install_baseline_console_scripts(self) -> None:
        pyproject = (ROOT / "pyproject.toml").read_text()
        for command in (
            "dci-agent-lite",
            "dci-run-pi-rpc",
            "dci-print-pi-system-prompt",
        ):
            self.assertNotIn(command, pyproject)

    def test_layout_guide_defines_framework_ownership(self) -> None:
        guide = (ROOT / "docs/architecture/asterion-framework-layout.md").read_text()
        self.assertIn("Asterion owns framework contracts", guide)
        self.assertIn("Asterion must not import the DCI baseline", guide)
        self.assertIn("dci-agent-lite", guide)
        self.assertIn("dci.agent-runtime/v1", guide)


if __name__ == "__main__":
    unittest.main()
