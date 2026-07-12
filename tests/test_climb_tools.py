from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class ClimbToolTests(unittest.TestCase):
    def test_regen_tree_serializes_tracked_hypothesis_state(self) -> None:
        result = subprocess.run(
            ["python3", "tools/climb/regen-tree.py"],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        tree = json.loads(
            (REPO_ROOT / "docs/status/climb/research-tree.json").read_text()
        )
        self.assertEqual(tree["active"][0]["id"], "H-001")
        self.assertEqual(len(tree["active"]), 3)


if __name__ == "__main__":
    unittest.main()
