from __future__ import annotations

import json
import unittest
from pathlib import Path

from dci.framework.package_protocol import PackageProtocolError, validate_package_manifest


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = REPO_ROOT / "tests/fixtures/packages/v1"


class PackageManifestTests(unittest.TestCase):
    def load(self, name: str) -> dict[str, object]:
        return json.loads((FIXTURE_DIR / name).read_text())

    def test_valid_shared_manifest_fixture_conforms(self) -> None:
        validate_package_manifest(self.load("valid-capability.json"))

    def test_all_package_kinds_are_portable(self) -> None:
        manifest = self.load("valid-capability.json")

        for kind in (
            "capability",
            "workflow",
            "policy",
            "memory",
            "observability",
            "evaluation",
        ):
            with self.subTest(kind=kind):
                validate_package_manifest({**manifest, "kind": kind})

    def test_invalid_shared_manifest_fixtures_are_rejected(self) -> None:
        names = (
            "invalid-unknown-field.json",
            "invalid-duplicate-edge.json",
            "invalid-package-id.json",
            "invalid-forbidden-command.json",
        )

        for name in names:
            with self.subTest(name=name), self.assertRaises(PackageProtocolError):
                validate_package_manifest(self.load(name))

    def test_edge_arrays_must_be_sorted_and_unique(self) -> None:
        manifest = self.load("valid-capability.json")

        with self.assertRaises(PackageProtocolError):
            validate_package_manifest(
                {**manifest, "provides_capabilities": ["z.last", "a.first"]}
            )


if __name__ == "__main__":
    unittest.main()
