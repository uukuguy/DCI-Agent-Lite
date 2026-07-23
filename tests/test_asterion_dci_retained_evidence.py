from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "docs/status/climb/provider-evidence"


class AsterionDciRetainedEvidenceIntegrationTests(unittest.TestCase):
    def test_tracked_pi_evidence_is_body_free_and_bounded(self) -> None:
        record = json.loads((EVIDENCE / "af-330-h-003.json").read_text())
        self.assertEqual(record["agent_operations"], 1)
        self.assertEqual(record["judge_operations"], 1)
        self.assertEqual(record["tools"], {"grep": 1, "read": 2})
        self.assertTrue(record["corpus_contained"])
        self.assertFalse(record["full_dataset"])
        self.assertNotIn("cobalt lantern", repr(record))

    def test_tracked_claude_evidence_is_body_free_and_bounded(self) -> None:
        record = json.loads((EVIDENCE / "af-330-h-004.json").read_text())
        self.assertEqual(
            record["schema"], "asterion.dci.climb-provider-evidence/v2"
        )
        self.assertEqual(record["source_commit"], "f3e2528")
        self.assertRegex(record["source_sha256"], r"^[0-9a-f]{64}$")
        self.assertEqual(record["agent_provider"], "minimax")
        self.assertEqual(record["agent_model"], "MiniMax-M3")
        self.assertRegex(record["claude_code_version"], r"^\d+\.\d+\.\d+$")
        self.assertEqual(record["agent_operations"], 1)
        self.assertEqual(record["judge_operations"], 1)
        self.assertEqual(record["tools"], {"Glob": 0, "Grep": 1, "Read": 0})
        self.assertTrue(record["corpus_contained"])
        self.assertEqual(record["web_calls"], 0)
        self.assertEqual(record["subagent_calls"], 0)
        self.assertFalse(record["full_dataset"])
        self.assertNotIn("silver compass", repr(record))
        self.assertNotIn("8426", repr(record))


if __name__ == "__main__":
    unittest.main()
