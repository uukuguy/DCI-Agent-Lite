from __future__ import annotations

import json
import unittest
from pathlib import Path

from dci.framework.assembly import AssemblyError, validate_assembly_manifest


FIXTURES = Path(__file__).parent / "fixtures/assembly/v1"


class AssemblyManifestTests(unittest.TestCase):
    def load(self, name: str) -> dict[str, object]:
        return json.loads((FIXTURES / name).read_text())

    def test_valid_shared_assembly_fixture_conforms(self) -> None:
        validate_assembly_manifest(self.load("valid-dci.json"))

    def test_assembly_contract_is_closed(self) -> None:
        with self.assertRaises(AssemblyError):
            validate_assembly_manifest(self.load("invalid-unknown-field.json"))

    def test_package_refs_must_be_sorted_unique_and_exact(self) -> None:
        valid = self.load("valid-dci.json")
        refs = valid["packages"]
        assert isinstance(refs, list)
        invalid = (
            {**valid, "packages": list(reversed(refs))},
            {**valid, "packages": [refs[0], refs[0]]},
            {**valid, "packages": [{"package_id": "dci.research"}]},
        )
        for manifest in invalid:
            with self.subTest(manifest=manifest), self.assertRaises(AssemblyError):
                validate_assembly_manifest(manifest)

    def test_host_edge_arrays_must_be_sorted_unique_strings(self) -> None:
        valid = self.load("valid-dci.json")
        for field in (
            "host_capabilities",
            "host_policies",
            "host_events",
            "host_artifacts",
        ):
            for values in (["z.last", "a.first"], ["same", "same"], [""]):
                with self.subTest(field=field, values=values), self.assertRaises(
                    AssemblyError
                ):
                    validate_assembly_manifest({**valid, field: values})


if __name__ == "__main__":
    unittest.main()
