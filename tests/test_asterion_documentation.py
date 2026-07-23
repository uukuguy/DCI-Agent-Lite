from __future__ import annotations

import json
import re
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "asterion"


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


class AsterionDocumentationTests(unittest.TestCase):
    def test_standalone_hub_and_validation_separate_integration_history(self) -> None:
        readme = read("asterion/README.md")
        hub = read("asterion/docs/README.md")
        validation = read(
            "asterion/docs/verification/asterion-dci-validation-guide.md"
        )

        for relative in (
            "guides/asterion-capability-usage.md",
            "guides/asterion-dci-complete-reference.md",
            "architecture/agent-framework.md",
            "architecture/asterion-framework-capability-integration.md",
            "architecture/asterion-standalone-extraction.md",
            "verification/asterion-dci-validation-guide.md",
        ):
            self.assertIn(relative, hub)

        for document in (readme, hub, validation):
            self.assertIn("mixed-repository only", document)
            self.assertIn("538", document)
            self.assertNotIn("../../../docs/superpowers/", document)

        self.assertIn("## Standalone provider-free verification", validation)
        self.assertIn("## Cost-bearing verification", validation)
        self.assertIn("## Mixed-repository integration history", validation)
        self.assertIn("Agent operations: 0", validation)
        self.assertIn("Full dataset ran: no", validation)

    def test_standalone_markdown_checker_passes_from_project_root(self) -> None:
        completed = subprocess.run(
            ["uv", "run", "python", "tools/check_docs.py"],
            cwd=PROJECT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertRegex(
            completed.stdout.strip(),
            r"^checked \d+ markdown files, \d+ local links$",
        )

    def test_complete_reference_covers_standalone_product_surface(self) -> None:
        path = PROJECT / "docs/guides/asterion-dci-complete-reference.md"
        text = path.read_text(encoding="utf-8")
        for required in (
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
        ):
            self.assertIn(required, text)

        for command in (
            "uv run asterion-dci run",
            "uv run asterion-dci terminal",
            "uv run asterion-dci resume",
            "uv run asterion-dci evaluate",
            "uv run asterion-dci benchmark",
            "uv run asterion-dci export",
            "make asterion-verify-acceptance",
        ):
            self.assertIn(command, text)

        profiles = json.loads(
            read("asterion/src/asterion/dci/resources/batch-profiles.json")
        )["profiles"]
        for profile_id in profiles:
            self.assertIn(profile_id, text)

    def test_framework_and_extraction_guides_are_standalone_rooted(self) -> None:
        framework = read("asterion/docs/architecture/agent-framework.md")
        extraction = read(
            "asterion/docs/architecture/asterion-standalone-extraction.md"
        )
        for required in (
            "Runtime Protocol",
            "capability package",
            "application",
            "provider",
            "host service",
            "provider-free acceptance",
        ):
            self.assertIn(required, framework)

        for required in (
            "# Asterion 独立项目拆分指南",
            "standalone repository root after promotion",
            "promote the contents of `asterion/`",
            "uv sync --frozen",
            "uv build .",
            "make check",
            "make promotion-check",
            "isolated wheel",
            "provider-free acceptance",
        ):
            self.assertIn(required, extraction)
        self.assertNotIn("uv run ruff check asterion/src", extraction)
        self.assertNotIn("uv build asterion", extraction)

    def test_root_readme_preserves_af340_execution_authority_boundary(self) -> None:
        root_readme = read("README.md")
        for required in (
            "Pi r14",
            "Claude MiniMax r6",
            "strict paper reproduction",
            "new active work package",
            "superseded by D-053",
            "no current execution route",
            "Full dataset ran: no",
        ):
            self.assertIn(required, root_readme)

        actual_full = tuple(
            match.group("body")
            for match in re.finditer(
                r"```bash\n(?P<body>.*?)```", root_readme, re.DOTALL
            )
            if "verify_af340_reproduction.py full" in match.group("body")
            and "--authorize-full" in match.group("body")
        )
        self.assertTrue(actual_full)
        for body in actual_full:
            self.assertIn("--work-package-id AF-XYZ", body)
            self.assertIn("Full execution authority: AF-340", body)

    def test_current_state_names_the_complete_mixed_root_boundary(self) -> None:
        text = read("docs/status/CURRENT-STATE.md")
        project_root = next(
            line for line in text.splitlines() if line.startswith("- Project root:")
        )
        for retained in (
            "original/cross-product examples and tests",
            "parity/acceptance evidence",
            "shared workspace configuration/tooling",
            "governance",
            "no second Asterion product tree",
        ):
            self.assertIn(retained, project_root)


if __name__ == "__main__":
    unittest.main()
