from __future__ import annotations

import json
import unittest
from pathlib import Path

from dci.framework.assembly import (
    AssemblyError,
    AssemblyPlan,
    resolve_assembly,
    validate_assembly_manifest,
)
from dci.framework.package_catalog import PackageRef, discover_packages


FIXTURES = Path(__file__).parent / "fixtures/assembly/v1"
MANIFESTS = Path(__file__).resolve().parents[1] / "packages/manifests"


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


class AssemblyResolverTests(unittest.TestCase):
    def assembly(self) -> dict[str, object]:
        return json.loads((FIXTURES / "valid-dci.json").read_text())

    def runtime(self) -> dict[str, object]:
        return {
            "protocol": "dci.agent-runtime/v1",
            "runtime_id": "pi.reference",
            "capabilities": ["filesystem.read", "shell"],
        }

    def test_runtime_and_catalog_bind_into_an_immutable_plan(self) -> None:
        assembly = self.assembly()
        before = json.loads(json.dumps(assembly))

        plan = resolve_assembly(
            assembly,
            catalog=discover_packages([MANIFESTS]),
            runtime_manifest=self.runtime(),
        )

        self.assertIsInstance(plan, AssemblyPlan)
        self.assertEqual(plan.application_id, "dci.local-research")
        self.assertEqual(plan.runtime_id, "pi.reference")
        self.assertEqual(plan.package_refs[0], PackageRef("dci.evaluation", "1.0.0"))
        self.assertEqual(plan.composition.package_ids[0], "policy.local-corpus")
        self.assertEqual(assembly, before)

    def test_host_service_capability_is_separate_from_runtime_capabilities(self) -> None:
        assembly = {
            **self.assembly(),
            "application_id": "code.quality",
            "packages": [
                {"package_id": "evaluation.code-quality", "version": "1.0.0"},
                {"package_id": "observability.execution-audit", "version": "1.0.0"},
                {"package_id": "policy.controlled-code-check", "version": "1.0.0"},
                {"package_id": "workflow.code-quality", "version": "1.0.0"},
            ],
            "host_capabilities": ["executor.controlled"],
            "host_events": ["run.started", "tool.result"],
            "host_artifacts": ["text/x-source"],
        }
        runtime = {**self.runtime(), "capabilities": ["filesystem.read"]}

        plan = resolve_assembly(
            assembly,
            catalog=discover_packages([MANIFESTS]),
            runtime_manifest=runtime,
        )

        self.assertEqual(plan.composition.package_ids[0], "policy.controlled-code-check")
        self.assertNotIn("executor.controlled", runtime["capabilities"])

    def test_resolution_failures_are_safe(self) -> None:
        sentinel = "SECRET-ASSEMBLY-CONTENT"
        cases = (
            ({**self.runtime(), "runtime_id": "other.runtime"}, self.assembly()),
            (
                self.runtime(),
                {
                    **self.assembly(),
                    "packages": [
                        {"package_id": "missing.package", "version": "1.0.0"}
                    ],
                },
            ),
            ({**self.runtime(), "capabilities": []}, self.assembly()),
        )
        for runtime, assembly in cases:
            assembly["host_policies"] = [sentinel]
            with self.subTest(runtime=runtime, assembly=assembly), self.assertRaises(
                AssemblyError
            ) as raised:
                resolve_assembly(
                    assembly,
                    catalog=discover_packages([MANIFESTS]),
                    runtime_manifest=runtime,
                )
            self.assertNotIn(sentinel, str(raised.exception))


if __name__ == "__main__":
    unittest.main()
