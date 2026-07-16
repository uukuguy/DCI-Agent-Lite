from __future__ import annotations

import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


class AsterionDocumentationTests(unittest.TestCase):
    def test_complete_dci_reference_covers_product_and_evidence(self) -> None:
        relative = "docs/guides/asterion-dci-complete-reference.md"
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
                "packages/python/asterion-core/src/asterion/dci/resources/"
                "batch-profiles.json"
            )
        )["profiles"]
        for profile_id in profiles:
            self.assertIn(profile_id, text)

        launchers = sorted((ROOT / "scripts/asterion").glob("**/run_*.sh"))
        self.assertEqual(len(launchers), 12)
        for launcher in launchers:
            self.assertIn(launcher.relative_to(ROOT).as_posix(), text)

        for source in (
            "../../packages/python/asterion-core/src/asterion/dci/run.py",
            "../../packages/python/asterion-core/src/asterion/dci/artifacts.py",
            "../../packages/python/asterion-core/src/asterion/dci/evaluation.py",
            "../../packages/python/asterion-core/src/asterion/dci/benchmark.py",
            "../../packages/python/asterion-core/src/asterion/dci/analysis.py",
            "../../packages/python/asterion-core/src/asterion/dci/export.py",
        ):
            self.assertIn(source, text)
            self.assertTrue((path.parent / source).resolve().is_file())

        self.assertIn("没有重新运行完整 benchmark 数据集", text)
        self.assertIn("没有重新复现 62.9%", text)
        self.assertNotRegex(
            text,
            re.compile(r"AF-290.{0,30}(?:已经|成功|完整)(?:重跑|复现).{0,30}62\.9%"),
        )


if __name__ == "__main__":
    unittest.main()
