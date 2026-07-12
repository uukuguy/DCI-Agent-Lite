from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from dci.framework.package_catalog import PackageRef, discover_packages
from dci.framework.package_protocol import validate_package_manifest


class PackageDiscoveryTests(unittest.TestCase):
    def manifest(self, package_id: str, version: str = "1.0.0") -> dict[str, object]:
        return {
            "protocol": "dci.package/v1",
            "package_id": package_id,
            "version": version,
            "kind": "capability",
            "provides_capabilities": [],
            "requires_capabilities": [],
            "requires_policies": [],
            "emits_events": [],
            "consumes_events": [],
            "produces_artifacts": [],
            "consumes_artifacts": [],
        }

    def write_manifest(
        self, directory: Path, filename: str, package_id: str, version: str = "1.0.0"
    ) -> Path:
        path = directory / filename
        path.write_text(json.dumps(self.manifest(package_id, version)))
        return path

    def test_root_permutation_produces_identical_catalog_entries(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            first_root = root / "first"
            second_root = root / "second"
            first_root.mkdir()
            second_root.mkdir()
            self.write_manifest(first_root, "z.json", "catalog.z")
            self.write_manifest(second_root, "a.json", "catalog.a")

            first = discover_packages([first_root, second_root])
            second = discover_packages([second_root, first_root])

            self.assertEqual(first.entries, second.entries)
            self.assertEqual(
                tuple(entry.ref for entry in first.entries),
                (PackageRef("catalog.a", "1.0.0"), PackageRef("catalog.z", "1.0.0")),
            )

    def test_file_creation_order_does_not_change_reference_order(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            forward = root / "forward"
            reverse = root / "reverse"
            forward.mkdir()
            reverse.mkdir()
            for package_id in ("catalog.a", "catalog.z"):
                self.write_manifest(forward, f"{package_id}.json", package_id)
            for package_id in ("catalog.z", "catalog.a"):
                self.write_manifest(reverse, f"{package_id}.json", package_id)

            forward_refs = tuple(
                entry.ref for entry in discover_packages([forward]).entries
            )
            reverse_refs = tuple(
                entry.ref for entry in discover_packages([reverse]).entries
            )

            self.assertEqual(forward_refs, reverse_refs)

    def test_discovered_manifests_pass_canonical_validation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.write_manifest(root, "one.json", "catalog.one")
            self.write_manifest(root, "two.json", "catalog.two", "2.0.0")

            catalog = discover_packages([root])

            for entry in catalog.entries:
                validate_package_manifest(entry.manifest)
                self.assertEqual(entry.source, entry.source.resolve())

    def test_discovery_ignores_non_json_and_nested_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            nested = root / "nested"
            nested.mkdir()
            self.write_manifest(root, "direct.json", "catalog.direct")
            (root / "notes.txt").write_text("not a package")
            (nested / "invalid.json").write_text("not json")

            catalog = discover_packages([root])

            self.assertEqual(
                tuple(entry.ref for entry in catalog.entries),
                (PackageRef("catalog.direct", "1.0.0"),),
            )


if __name__ == "__main__":
    unittest.main()
