from __future__ import annotations

import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "asterion"


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


class AsterionDocumentationTests(unittest.TestCase):
    def test_architecture_verification_blocks_use_one_mixed_repository_root(
        self,
    ) -> None:
        architecture = PROJECT / "docs/architecture"
        documents = (
            "composable-packages.md",
            "controlled-code-validation-packages.md",
            "local-package-catalog.md",
            "static-application-assembly.md",
            "asterion-framework-layout.md",
        )
        npm_documents = set(documents) - {"composable-packages.md"}

        for name in documents:
            text = (architecture / name).read_text(encoding="utf-8")
            verification = text.rsplit("## Verification", 1)[1]
            self.assertIn(
                "Run these checks from the parent mixed-repository root",
                verification,
                name,
            )
            self.assertNotIn("npm --prefix packages/", verification, name)
            self.assertNotIn("--climb-hypothesis", verification, name)
            if name in npm_documents:
                self.assertIn(
                    "npm --prefix asterion/packages/typescript/asterion-runtime test",
                    verification,
                    name,
                )

    def test_framework_design_baseline_is_a_resolving_mixed_repository_link(
        self,
    ) -> None:
        path = PROJECT / "docs/architecture/agent-framework.md"
        text = path.read_text(encoding="utf-8")
        target = (
            "../../../docs/superpowers/specs/"
            "2026-07-12-agent-framework-governance-design.md"
        )
        self.assertIn("mixed-repository dependency", text)
        self.assertIn(f"]({target})", text)
        self.assertTrue((path.parent / target).resolve().is_file())

    def test_all_project_markdown_links_resolve_locally(self) -> None:
        docs_root = PROJECT / "docs"
        documents = sorted(docs_root.rglob("*.md"))
        self.assertEqual(len(documents), 15)

        missing: list[str] = []
        for document in documents:
            for target in re.findall(r"\[[^]]+\]\(([^)]+)\)", document.read_text()):
                clean = target.strip("<>").split("#", 1)[0]
                if not clean or "://" in clean or clean.startswith("mailto:"):
                    continue
                resolved = (document.parent / clean).resolve()
                if not resolved.exists():
                    missing.append(f"{document.relative_to(PROJECT)}: {target}")
        self.assertEqual(missing, [])

    def test_complete_dci_reference_covers_product_and_evidence(self) -> None:
        relative = "asterion/docs/guides/asterion-dci-complete-reference.md"
        path = ROOT / relative
        self.assertTrue(path.is_file(), relative)
        text = path.read_text(encoding="utf-8")

        required = (
            "# Asterion DCI 完整产品参考",
            "## 证据状态说明",
            "## 配置与依赖",
            "## 单次研究、终端与系统提示词",
            "## 原生产物、隐私与恢复",
            "## Context Management：两个不同层次",
            "## Judge、评测与精确缓存",
            "## Benchmark DCI-Agent-Lite",
            "## 数据集、Profile 与 Launcher",
            "## 指标、分析、图表与导出",
            "## 安装应用与能力包入口",
            "## 完整验证矩阵",
            "Implemented",
            "Verified",
            "External-limited",
            "Not rerun",
            "provider-backed operations",
            "533/533",
            "12/12",
            "runtime_context_control",
        )
        for value in required:
            self.assertIn(value, text)

        for command in (
            "asterion-dci run",
            "asterion-dci terminal",
            "asterion-dci system-prompt",
            "asterion-dci resume",
            "asterion-dci evaluate",
            "asterion-dci benchmark",
            "asterion-dci export",
            "make asterion-verify-preflight",
            "make asterion-verify-basic",
            "make asterion-verify-acceptance",
            "make asterion-verify-complete",
        ):
            self.assertIn(command, text)

        for control in (
            "--conversation-clear-tool-results",
            "--conversation-clear-tool-results-keep-last",
            "--conversation-externalize-tool-results",
            "--conversation-strip-thinking",
            "--conversation-strip-usage",
        ):
            self.assertIn(control, text)

        profiles = json.loads(
            read(
                "asterion/src/asterion/dci/resources/"
                "batch-profiles.json"
            )
        )["profiles"]
        for profile_id in profiles:
            self.assertIn(profile_id, text)

        launchers = sorted((PROJECT / "scripts").glob("**/run_*.sh"))
        self.assertEqual(len(launchers), 12)
        for launcher in launchers:
            self.assertIn(launcher.relative_to(PROJECT).as_posix(), text)
        self.assertIn("11 个主要 launcher", text)
        self.assertIn("run_L3.sh", text)
        self.assertIn("兼容 helper", text)

        readme = read("README.md")
        validation_guide = read(
            "asterion/docs/verification/asterion-dci-validation-guide.md"
        )
        primary_relatives = (
            "bcplus_eval/run_bcplus_eval_openai.sh",
            "qa/run_2wikimultihopqa_dev_sample50.sh",
            "qa/run_bamboogle_test_sample50.sh",
            "qa/run_hotpotqa_dev_sample50.sh",
            "qa/run_musique_dev_sample50.sh",
            "qa/run_nq_test_sample50.sh",
            "qa/run_triviaqa_test_sample50.sh",
            "bright/run_bio.sh",
            "bright/run_earth_science.sh",
            "bright/run_economics.sh",
            "bright/run_robotics.sh",
        )
        for relative in primary_relatives:
            self.assertIn(f"scripts/{relative}", readme)
            self.assertIn(f"asterion/scripts/{relative}", readme)
            self.assertIn(f"scripts/{relative}", text)
            self.assertIn(f"scripts/{relative}", validation_guide)
            self.assertIn(f"asterion/scripts/{relative}", validation_guide)
        for representative in (
            "bash scripts/bcplus_eval/run_bcplus_eval_openai.sh level3 high --limit 1",
            "bash scripts/qa/run_hotpotqa_dev_sample50.sh --limit 1",
            "bash scripts/bright/run_bio.sh --limit 1",
        ):
            self.assertIn(representative, readme)
        self.assertIn("tools/verify_af340_reproduction.py full", readme)
        self.assertIn("is not full execution authorization", readme)
        self.assertIn("primary Asterion batch profiles are runtime-neutral", readme)
        self.assertIn("不携带 provider/model", text)
        self.assertIn("tools/verify_af340_reproduction.py full", validation_guide)
        self.assertIn("is not full execution authorization", validation_guide)
        self.assertIn(
            "primary Asterion batch profiles are runtime-neutral",
            validation_guide,
        )

        for source in (
            "../../src/asterion/dci/run.py",
            "../../src/asterion/dci/artifacts.py",
            "../../src/asterion/dci/evaluation.py",
            "../../src/asterion/dci/benchmark.py",
            "../../src/asterion/dci/analysis.py",
            "../../src/asterion/dci/export.py",
        ):
            self.assertIn(source, text)
            self.assertTrue((path.parent / source).resolve().is_file())

        self.assertIn("没有重新运行完整 benchmark 数据集", text)
        self.assertIn("没有重新复现 62.9%", text)
        self.assertNotRegex(
            text,
            re.compile(r"AF-290.{0,30}(?:已经|成功|完整)(?:重跑|复现).{0,30}62\.9%"),
        )

    def test_framework_guide_explains_layers_and_complete_integration(self) -> None:
        relative = "asterion/docs/architecture/asterion-framework-capability-integration.md"
        path = ROOT / relative
        self.assertTrue(path.is_file(), relative)
        text = path.read_text(encoding="utf-8")

        for required in (
            "# Asterion 框架与能力包接入指南",
            "## 当前仓库与权威目录",
            "## 依赖方向",
            "## Runtime Protocol、Factory 与 Runtime",
            "## Adapter 与标准化边界",
            "## Package、Capability 与实现绑定",
            "## Application、Assembly 与 Provider",
            "## Host Service 与受控执行",
            "## 通用 CLI 与产品 CLI",
            "## 完整接入示例：example.research",
            "## 安全失败与测试清单",
            "src/asterion/capabilities/",
            "src/asterion/applications/",
            "example.policy",
            "example.research",
            "example.observability",
            "example.research-app@1.0.0",
            "asterion list",
            "asterion run",
            "isolated wheel",
        ):
            self.assertIn(required, text)

        ordered = (
            "1. Manifest",
            "2. Implementation binding",
            "3. Assembly",
            "4. Installed provider",
            "5. Python entry point",
            "6. `asterion list`",
            "7. `asterion run`",
            "8. Isolated-wheel test",
        )
        positions = [text.find(value) for value in ordered]
        self.assertTrue(all(position >= 0 for position in positions), positions)
        self.assertEqual(positions, sorted(positions))

        self.assertIn("asterion` 永远不能导入 `src/dci", text)
        self.assertIn("只加载被精确选择的 provider", text)
        self.assertIn("不会加载相邻 provider", text)
        self.assertIn("混合仓库根已不再保留旧的", text)
        self.assertIn("mixed-repository dependency", text)

        for source in (
            "../../src/asterion/runtime/",
            "../../src/asterion/packages/",
            "../../src/asterion/assembly/",
            "../../src/asterion/runner/",
            "../../src/asterion/applications/provider.py",
        ):
            self.assertIn(source, text)
            self.assertTrue((path.parent / source).resolve().exists())

    def test_standalone_extraction_guide_is_complete_and_phased(self) -> None:
        relative = "asterion/docs/architecture/asterion-standalone-extraction.md"
        path = ROOT / relative
        self.assertTrue(path.is_file(), relative)
        text = path.read_text(encoding="utf-8")

        for required in (
            "# Asterion 独立项目拆分指南",
            "## 当前自包含清单",
            "## 外部依赖与明确排除项",
            "## 目标目录树",
            "## 迁移映射表",
            "## Phase 1：冻结边界与基线",
            "## Phase 2：建立独立仓库骨架",
            "## Phase 3：迁移 Python 发行物",
            "## Phase 4：迁移协议与跨语言包",
            "## Phase 5：迁移 DCI 产品与应用",
            "## Phase 6：隔离安装与发布验证",
            "## Phase 7：切换与清理",
            "## DCI 打包决策门",
            "## 发布门禁",
            "## 回滚方案",
            "## 风险与非目标",
            "asterion",
            "packages/typescript/asterion-runtime",
            "packages/rust/controlled-executor",
            "schemas/agent-runtime/v1",
            "tests/fixtures",
            "keep DCI bundled initially",
            "separately versioned plugin decision gate",
            "isolated wheel",
            "provider-free acceptance",
            "bounded Pi examples",
        ):
            self.assertIn(required, text)

        for excluded in (
            "外部 `pi/` checkout",
            "corpora 与 benchmark datasets",
            "credentials 与 `.env`",
            "运行输出与评测 artifacts",
            "`.worktrees/`",
            "旧 `src/dci`",
        ):
            self.assertIn(excluded, text)

        for command in (
            "uv build .",
            "asterion list",
            "asterion verify --provider dci-agent-lite --level acceptance",
            "make asterion-verify-basic",
            "npm test",
            "cargo test",
        ):
            self.assertIn(command, text)

    def test_standalone_verification_command_uses_a_real_provider_free_level(
        self,
    ) -> None:
        text = read("asterion/docs/architecture/asterion-standalone-extraction.md")
        phase_six = text.split("## Phase 6：隔离安装与发布验证", 1)[1].split(
            "## Phase 7：切换与清理", 1
        )[0]
        commands = re.findall(r"^asterion verify .+$", phase_six, re.MULTILINE)
        self.assertEqual(len(commands), 1)
        argv = commands[0].split()
        level = argv[argv.index("--level") + 1]
        self.assertIn(level, {"preflight", "basic", "acceptance", "complete"})
        self.assertEqual(level, "acceptance")

    def test_standalone_extraction_promotes_project_contents_to_repo_root(
        self,
    ) -> None:
        text = read("asterion/docs/architecture/asterion-standalone-extraction.md")
        self.assertIn("current mixed-repository root", text)
        self.assertIn("standalone repository root after promotion", text)
        self.assertIn("promote the contents of `asterion/`", text)
        post_promotion = text.split("## Phase 3：迁移 Python 发行物", 1)[1]
        self.assertIn("uv run ruff check src tests", post_promotion)
        self.assertIn("uv build .", post_promotion)
        self.assertNotIn("uv run ruff check asterion/src", post_promotion)
        self.assertNotIn("uv build asterion", post_promotion)

    def test_current_state_names_the_complete_mixed_root_boundary(self) -> None:
        text = read("docs/status/CURRENT-STATE.md")
        project_root = next(
            line for line in text.splitlines() if line.startswith("- Project root:")
        )
        self.assertNotIn("governance only", project_root)
        for retained in (
            "original/cross-product examples and tests",
            "parity/acceptance evidence",
            "shared workspace configuration/tooling",
            "governance",
            "no second Asterion product tree",
        ):
            self.assertIn(retained, project_root)

    def test_documentation_hub_navigation_and_context_truth(self) -> None:
        hub = read("asterion/docs/README.md")
        root_readme = read("README.md")
        usage = read("asterion/docs/guides/asterion-capability-usage.md")
        validation = read("asterion/docs/verification/asterion-dci-validation-guide.md")
        running = read("assets/docs/running.md")

        documents = (
            "guides/asterion-dci-complete-reference.md",
            "architecture/asterion-framework-capability-integration.md",
            "architecture/asterion-standalone-extraction.md",
        )
        for relative in documents:
            self.assertIn(relative, hub)
            self.assertIn(f"asterion/docs/{relative}", root_readme)

        complete_reference = "asterion-dci-complete-reference.md"
        self.assertIn(complete_reference, usage)
        self.assertIn(complete_reference, validation)

        stale_claim = (
            "The configured Pi checkout supports runtime context-management "
            "profiles"
        )
        self.assertNotIn(stale_claim, running)
        self.assertNotIn('--extra-arg="--context-management-level', running)
        self.assertIn("does not expose a typed `--context-management-level`", running)
        self.assertIn("External-limited", running)
        self.assertIn("conversation artifact compaction", running)

        local_docs = (
            PROJECT / "docs/README.md",
            PROJECT / "docs/guides/asterion-dci-complete-reference.md",
            PROJECT / "docs/architecture/asterion-framework-capability-integration.md",
            PROJECT / "docs/architecture/asterion-standalone-extraction.md",
        )
        for document in local_docs:
            for target in re.findall(r"\[[^]]+\]\(([^)]+)\)", document.read_text()):
                clean = target.strip("<>").split("#", 1)[0]
                if not clean or "://" in clean or clean.startswith("mailto:"):
                    continue
                resolved = (document.parent / clean).resolve()
                self.assertTrue(resolved.exists(), f"{document}: {target}")


if __name__ == "__main__":
    unittest.main()
