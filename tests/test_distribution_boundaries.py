from __future__ import annotations

import re
import os
import subprocess
import tempfile
import tomllib
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ASTERION_PROJECT = ROOT / "asterion"
ASTERION_SOURCE = ASTERION_PROJECT / "src/asterion"
BASELINE_SOURCE = ROOT / "src/dci"


def python_source(root: Path) -> str:
    return "\n".join(
        path.read_text()
        for path in sorted(root.rglob("*.py"))
        if "__pycache__" not in path.parts
    )


class SourceDistributionBoundaryTests(unittest.TestCase):
    def test_paper_context_documentation_names_exact_live_contract_and_evidence(self) -> None:
        paths = (
            ROOT / ".env.template",
            ROOT / "README.md",
            ASTERION_PROJECT / "docs/guides/asterion-dci-complete-reference.md",
            ASTERION_PROJECT / "docs/verification/asterion-dci-validation-guide.md",
        )
        combined = "\n".join(path.read_text(encoding="utf-8") for path in paths)
        for required in (
            "dci.context-profile/v1",
            "level0",
            "level1",
            "level2",
            "level3",
            "level4",
            "50,000",
            "20,000",
            "240,000",
            "12 complete turns",
            "20,000 recent tokens",
            "3 consecutive summary failures",
            "live model context",
            "post-run conversation processing",
            "runtime_context_control` extension",
            "original Pi session",
            "Implemented",
            "Model-free verified",
            "Bounded provider verified",
            "Experiment reproduced",
            "AF-340",
            "tools/verify_original_readme.py",
            "--provider-backed",
            "Provider operations: 0",
            "Full dataset ran: no",
        ):
            self.assertIn(required, combined)
        for stale in (
            "unsupported diagnostic",
            "never converted into a Pi CLI flag",
            "current Pi CLI does not expose a runtime context-management level",
        ):
            self.assertNotIn(stale.lower(), combined.lower())

    def test_asterion_capability_beginner_guide_is_complete(self) -> None:
        guide_path = ASTERION_PROJECT / "docs/guides/asterion-capability-usage.md"
        self.assertTrue(guide_path.is_file())
        text = guide_path.read_text()
        ordered = (
            "## 五分钟开始",
            "## 最少需要哪些配置",
            "## 查看能力：`list` 与 `describe`",
            "## 四种验证级别",
            "### `preflight`：只检查外部准备",
            "### `acceptance`：已安装产品闭包",
            "### `basic`：有界 Agent/Judge 案例",
            "### `complete`：有界路径加安装闭包",
            "## DCI 产品命令",
            "## 费用与完整数据集边界",
            "## 产物与隐私",
            "## 常见问题",
        )
        positions = [text.find(value) for value in ordered]
        self.assertTrue(all(position >= 0 for position in positions), positions)
        self.assertEqual(positions, sorted(positions))
        for required in (
            "asterion describe --provider dci-agent-lite",
            "make test",
            "make promotion-check",
            "make asterion-verify-preflight",
            "make asterion-verify-basic",
            "make asterion-verify-acceptance",
            "make asterion-verify-complete",
            "--level preflight",
            "--level basic",
            "--level acceptance",
            "--level complete",
            "DCI_PROVIDER",
            "DCI_MODEL",
            "DCI_PI_DIR",
            "ASTERION_DCI_RESOURCE_ROOT",
            "DCI_EVAL_JUDGE_*",
            "Full dataset ran: no",
            "../verification/asterion-dci-validation-guide.md",
        ):
            self.assertIn(required, text)
        self.assertNotRegex(
            text,
            re.compile(r"(?:API_KEY|TOKEN|PASSWORD)=(?!<YOUR_)[A-Za-z0-9_-]{12,}"),
        )
        self.assertNotRegex(text, re.compile(r"/(?:Users|home|private)/"))

        readme = (ROOT / "README.md").read_text()
        beginner = readme.find("asterion/docs/guides/asterion-capability-usage.md")
        advanced = readme.find("asterion/docs/verification/asterion-dci-validation-guide.md")
        self.assertGreaterEqual(beginner, 0)
        self.assertGreater(advanced, beginner)
        for required in (
            "make asterion-describe",
            "make asterion-verify-acceptance",
            "make asterion-integration-acceptance",
            "preflight` 和 `acceptance` 不调用模型",
            "basic` 和 `complete` 会运行两个有界 Pi 操作和一个 Judge 操作",
        ):
            self.assertIn(required, readme)

    def test_complete_dci_validation_guide_covers_standalone_and_integration_boundaries(
        self,
    ) -> None:
        guide_path = ASTERION_PROJECT / "docs/verification/asterion-dci-validation-guide.md"
        self.assertTrue(guide_path.is_file())
        text = guide_path.read_text()
        for required in (
            "uv run asterion list",
            "make asterion-verify-acceptance",
            "make test",
            "make check",
            "asterion-dci resume",
            "asterion-dci terminal",
            "asterion-dci evaluate",
            "asterion-dci benchmark",
            "verify_asterion_dci_product.py",
            "538/538",
            "provider-free",
            "bounded provider-backed",
            "Full-dataset execution",
            "ASTERION_DCI_RESOURCE_ROOT",
            "isolated wheel",
            "mixed-repository only",
        ):
            self.assertIn(required, text)

        self.assertNotIn(
            'ASTERION_DCI_CORPUS_ROOT="${ASTERION_DCI_CORPUS_ROOT:-$PWD/corpus}"',
            text,
        )
        self.assertNotIn("wheel-installed generic application", text)

        for launcher in (
            "scripts/bcplus_eval/run_bcplus_eval_openai.sh",
            "scripts/bright/run_bio.sh",
            "scripts/qa/run_hotpotqa_dev_sample50.sh",
            "scripts/beir/benchmark_arguana.sh",
            "tests.test_standalone_launchers",
        ):
            self.assertIn(launcher, text)

        readme = (ROOT / "README.md").read_text()
        self.assertIn(
            "asterion/docs/verification/asterion-dci-validation-guide.md",
            readme,
        )

    def test_validation_guide_preserves_mixed_root_configuration_resolution(
        self,
    ) -> None:
        text = (
            ASTERION_PROJECT / "docs/verification/asterion-dci-validation-guide.md"
        ).read_text()
        for required in (
            "promoted standalone repository",
            "uv sync --frozen",
            "Copy `.env.template` to `.env`",
            "ASTERION_DCI_RESOURCE_ROOT",
            "All fourteen launchers compute their own project root",
            "mixed-repository only",
            "intentionally absent here",
        ):
            self.assertIn(required, text)
        self.assertNotIn("uv run --project asterion", text)
        self.assertNotIn('DCI_ENV_FILE="${DCI_ENV_FILE:-.env}"', text)

    def test_validation_guide_uses_standalone_and_promotion_gates(self) -> None:
        text = (
            ASTERION_PROJECT / "docs/verification/asterion-dci-validation-guide.md"
        ).read_text()
        repository_gates = text.split(
            "### 3. Verify repository and distribution gates", 1
        )[1].split("### 4.", 1)[0]
        for command in (
            "make test",
            "make lint",
            "make docs-check",
            "make build",
            "make check",
        ):
            self.assertIn(command, repository_gates)
        self.assertIn("temporary-copy promotion gate", text)
        self.assertNotIn("discover -s ../tests", text)
        self.assertNotIn("90 project-local", text)
        self.assertNotIn("1230 root", text)

    def test_asterion_core_has_an_independent_project_and_source_root(self) -> None:
        self.assertTrue((ASTERION_PROJECT / "pyproject.toml").is_file())
        self.assertTrue((ASTERION_SOURCE / "__init__.py").is_file())
        self.assertFalse((ROOT / "src/asterion").exists())

    def test_asterion_core_never_imports_the_dci_baseline(self) -> None:
        source = python_source(ASTERION_SOURCE)
        self.assertNotRegex(source, r"(?:from|import)\s+dci(?:\.|\s|$)")

    def test_dci_baseline_never_imports_asterion(self) -> None:
        source = python_source(BASELINE_SOURCE)
        self.assertNotRegex(source, r"(?:from|import)\s+asterion(?:\.|\s|$)")

    def test_root_is_a_non_buildable_workspace_with_one_member(self) -> None:
        pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text())
        self.assertNotIn("build-system", pyproject)
        self.assertTrue(pyproject["tool"]["uv"]["package"] is False)
        self.assertEqual(
            pyproject["tool"]["uv"]["workspace"]["members"],
            ["asterion"],
        )
        self.assertNotIn("scripts", pyproject["project"])

    def test_baseline_framework_modules_are_not_compatibility_reexports(self) -> None:
        framework = python_source(BASELINE_SOURCE / "framework")
        self.assertNotIn("Compatibility exports", framework)
        self.assertNotRegex(framework, re.compile(r"(?:from|import)\s+asterion"))

    def test_asterion_dci_operator_documentation_is_independent_and_scoped(self) -> None:
        environment = (ROOT / ".env.template").read_text()
        readme = (ROOT / "README.md").read_text()
        execution = (ASTERION_PROJECT / "docs/architecture/capability-execution.md").read_text()
        for variable in (
            "ASTERION_DCI_PI_DIR",
            "ASTERION_DCI_PI_PACKAGE_DIR",
            "ASTERION_DCI_PI_AGENT_DIR",
            "ASTERION_DCI_OUTPUT_ROOT",
        ):
            self.assertIn(variable, environment)
        self.assertIn("asterion-dci run", readme)
        self.assertIn("AF-190", readme)
        self.assertIn("AF-220", readme)
        self.assertIn("DciRunResult", execution)
        self.assertIn("project_dci_run", execution)
        self.assertRegex(execution.lower(), r"generic\s+asterion cli")

    def test_claude_runtime_uses_shared_provider_configuration(self) -> None:
        environment = (ROOT / ".env.template").read_text()
        standalone_environment = (ASTERION_PROJECT / ".env.template").read_text()
        readme = (ROOT / "README.md").read_text()

        for required in (
            "DCI_PROVIDER=minimax",
            "DCI_PROVIDER=minimax-cn",
            "MINIMAX_API_KEY=your_minimax_key_here",
            "MINIMAX_CN_API_KEY=your_minimax_cn_key_here",
        ):
            self.assertIn(required, environment)
        self.assertNotIn("ANTHROPIC_AUTH_TOKEN=your_gateway_token_here", environment)
        self.assertIn("Claude Code adapter derives", readme)
        for required in (
            "DCI_PROVIDER=",
            "DCI_MODEL=",
            "# ANTHROPIC_API_KEY=",
            "# MINIMAX_API_KEY=",
            "# MINIMAX_CN_API_KEY=",
        ):
            self.assertIn(required, standalone_environment)

    def test_durable_dci_documentation_names_resume_and_protected_artifacts(self) -> None:
        readme = (ROOT / "README.md").read_text()
        execution = (ASTERION_PROJECT / "docs/architecture/capability-execution.md").read_text()

        self.assertIn("asterion-dci resume", readme)
        self.assertIn("conversation_full.json", readme)
        self.assertIn("immutable", readme)
        self.assertIn("AF-220", readme)
        self.assertIn("latest_model_context.json", execution)
        self.assertIn("conversation_full.json", execution)
        self.assertIn("protected", execution)


    def test_source_baseline_remains_runnable_without_installation(self) -> None:
        environment = os.environ.copy()
        environment["PYTHONPATH"] = str(ROOT / "src")
        completed = subprocess.run(
            ["uv", "run", "python", "-m", "dci.benchmark.pi_rpc_runner", "--help"],
            cwd=ROOT,
            env=environment,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)


class BuiltDistributionBoundaryTests(unittest.TestCase):
    def test_asterion_is_the_only_buildable_wheel(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            subprocess.run(
                ["uv", "build", "--package", "asterion", "--wheel", "--out-dir", temp_dir],
                cwd=ROOT,
                check=True,
                text=True,
                capture_output=True,
            )
            wheels = list(Path(temp_dir).glob("*.whl"))
            self.assertEqual(len(wheels), 1)
            self.assertEqual(self.wheel_top_levels(wheels[0]), {"asterion"})
            self.assertNotIn("Requires-Dist: dci", self.metadata(wheels[0]))
            with zipfile.ZipFile(wheels[0]) as archive:
                names = archive.namelist()
                for prefix in (
                    "asterion/capabilities/dci_research/",
                    "asterion/capabilities/controlled_code/",
                    "asterion/applications/dci_agent_lite/",
                    "asterion/applications/controlled_code/",
                ):
                    self.assertTrue(
                        any(name.startswith(prefix) for name in names), prefix
                    )
                self.assertFalse(
                    any(
                        name.startswith(
                            (
                                "dci/",
                                "examples/",
                                "tests/",
                                "asterion/examples/",
                                "asterion/tests/",
                                "src/",
                            )
                        )
                        for name in names
                    )
                )
                self.assertFalse(
                    any(
                        marker in name
                        for name in names
                        for marker in (
                            "DCI-Agent-Lite",
                            "assets/dci/",
                            "docs/status/",
                            "packages/python/",
                            "scripts/examples/",
                        )
                    )
                )
                self.assertIn("asterion/dci/cli.py", names)
                self.assertIn("asterion/dci/run.py", names)
                self.assertIn("asterion/dci/application_executor.py", names)
                self.assertIn(
                    "asterion/dci/resources/pi/dci-context-extension.ts", names
                )
                self.assertIn(
                    "asterion/dci/resources/pi/context-extension-manifest.json",
                    names,
                )
                self.assertIn(
                    "asterion/applications/dci_agent_lite/provider.py", names
                )
                self.assertNotIn("dci/benchmark/pi_rpc_runner.py", names)
                entry_points = archive.read(
                    next(name for name in names if name.endswith("entry_points.txt"))
                ).decode()
                self.assertIn("asterion-dci = asterion.dci.cli:main", entry_points)
                manifests = [
                    name for name in archive.namelist() if "/dci_research/manifests/" in name
                ]
                controlled_manifests = [
                    name
                    for name in archive.namelist()
                    if "/controlled_code/manifests/" in name
                ]
                assemblies = [
                    name
                    for name in archive.namelist()
                    if "/assemblies/" in name
                ]
            self.assertEqual(len(manifests), 7)
            self.assertEqual(len(manifests), len(set(manifests)))
            self.assertEqual(len(controlled_manifests), 4)
            self.assertEqual(len(controlled_manifests), len(set(controlled_manifests)))
            self.assertEqual(
                {Path(name).name for name in assemblies},
                {
                    "controlled-code-validation.json",
                    "dci-complete-application-claude.json",
                    "dci-complete-application-pi.json",
                    "dci-local-research.json",
                    "dci-research-capability-claude.json",
                    "dci-research-capability.json",
                },
            )
            self.assertEqual(len(assemblies), len(set(assemblies)))

    def test_no_capability_or_baseline_project_remains(self) -> None:
        self.assertFalse((ROOT / "capabilities/dci-research/pyproject.toml").exists())
        pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text())
        self.assertNotEqual(pyproject["project"]["name"], "dci")
        self.assertFalse((ROOT / "capabilities/dci-research/src").exists())

    def wheel_top_levels(self, wheel: Path) -> set[str]:
        with zipfile.ZipFile(wheel) as archive:
            return {
                name.split("/", 1)[0]
                for name in archive.namelist()
                if "/" in name and ".dist-info" not in name.split("/", 1)[0]
            }

    def metadata(self, wheel: Path) -> str:
        with zipfile.ZipFile(wheel) as archive:
            metadata_path = next(
                name for name in archive.namelist() if name.endswith(".dist-info/METADATA")
            )
            return archive.read(metadata_path).decode()


if __name__ == "__main__":
    unittest.main()
