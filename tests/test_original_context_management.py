from __future__ import annotations

import json
import unittest

from tests import SOURCE_ROOT as _SOURCE_ROOT  # noqa: F401
from dci.context_management import (
    ModelFreeContextPolicy,
    context_profile_names,
    resolve_context_extension,
    resolve_context_profile,
)


class OriginalContextManagementTests(unittest.TestCase):
    def test_original_resources_are_independent_and_integrity_checked(self) -> None:
        extension = resolve_context_extension()

        self.assertEqual(context_profile_names(), tuple(f"level{i}" for i in range(5)))
        self.assertEqual(extension.contract_version, "dci.context-profile/v1")
        self.assertRegex(extension.sha256, r"^[0-9a-f]{64}$")
        self.assertTrue(extension.path.is_file())
        self.assertNotIn("asterion", extension.path.as_posix())

    def test_model_free_hooks_cover_truncation_compaction_summary_and_suppression(self) -> None:
        level1 = ModelFreeContextPolicy(resolve_context_profile("level1"))
        self.assertEqual(len(level1.tool_result("x" * 60_000)), 50_000)

        level3 = ModelFreeContextPolicy(resolve_context_profile("level3"))
        level3.tool_result("x" * 240_001)
        self.assertTrue(level3.compaction_pending)
        level3.compact(summary_succeeded=None)
        self.assertEqual(level3.compactions, 1)
        self.assertEqual(level3.visible_turn_count(13), 12)

        level4 = ModelFreeContextPolicy(resolve_context_profile("level4"))
        for _ in range(3):
            level4.tool_result("x" * 240_001)
            level4.compact(summary_succeeded=False)
        self.assertEqual(level4.summary_attempts, 3)
        self.assertTrue(level4.summary_suppressed)
        level4.tool_result("x" * 240_001)
        level4.compact(summary_succeeded=None)
        self.assertEqual(level4.summary_attempts, 3)
        self.assertTrue(any(item["event"] == "compaction_complete" for item in level4.telemetry))

    def test_model_free_resume_requires_matching_extension_digest(self) -> None:
        policy = ModelFreeContextPolicy(resolve_context_profile("level4"))
        policy.tool_result("x" * 240_001)
        state = policy.snapshot()

        resumed = ModelFreeContextPolicy.resume(
            resolve_context_profile("level4"), state
        )
        self.assertEqual(resumed.snapshot()["extension_sha256"], state["extension_sha256"])
        changed = dict(state)
        changed["extension_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "resume"):
            ModelFreeContextPolicy.resume(resolve_context_profile("level4"), changed)

    def test_resource_payload_is_closed(self) -> None:
        extension = resolve_context_extension()
        manifest = json.loads(extension.manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(
            set(manifest),
            {"schema", "extension_version", "contract_version", "resource", "byte_length", "sha256"},
        )


if __name__ == "__main__":
    unittest.main()
