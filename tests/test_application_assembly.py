from __future__ import annotations

import json
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path
from types import MappingProxyType

from dci.framework.assembly import (
    AssemblyError,
    AssemblyPlan,
    resolve_assembly,
    validate_assembly_manifest,
)
from dci.framework.package_catalog import PackageRef, discover_packages


FIXTURES = Path(__file__).parent / "fixtures/assembly/v1"
ROOT = Path(__file__).resolve().parents[1]
MANIFESTS = (
    ROOT / "asterion/src/asterion/capabilities/dci_research/manifests",
    ROOT / "asterion/src/asterion/capabilities/controlled_code/manifests",
)
ASSEMBLIES = ROOT / "asterion/src/asterion/applications/dci_agent_lite/assemblies"
CONTROLLED_ASSEMBLIES = (
    ROOT / "asterion/src/asterion/applications/controlled_code/assemblies"
)
GUIDE = Path(__file__).resolve().parents[1] / "asterion/docs/architecture/static-application-assembly.md"


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

    def controlled_assembly(self) -> dict[str, object]:
        return {
            **self.assembly(),
            "application_id": "code.quality",
            "packages": [
                {"package_id": "evaluation.code-quality", "version": "1.0.0"},
                {
                    "package_id": "observability.execution-audit",
                    "version": "1.0.0",
                },
                {
                    "package_id": "policy.controlled-code-check",
                    "version": "1.0.0",
                },
                {"package_id": "workflow.code-quality", "version": "1.0.0"},
            ],
            "host_capabilities": ["executor.controlled"],
            "host_events": ["run.started", "tool.result"],
            "host_artifacts": ["text/x-source"],
        }

    def test_runtime_and_catalog_bind_into_an_immutable_plan(self) -> None:
        assembly = self.assembly()
        before = json.loads(json.dumps(assembly))

        plan = resolve_assembly(
            assembly,
            catalog=discover_packages(MANIFESTS),
            runtime_manifest=self.runtime(),
        )

        self.assertIsInstance(plan, AssemblyPlan)
        self.assertEqual(plan.application_id, "dci.local-research")
        self.assertEqual(plan.runtime_id, "pi.reference")
        self.assertEqual(plan.package_refs[0], PackageRef("dci.evaluation", "1.0.0"))
        self.assertEqual(plan.composition.package_ids[0], "policy.local-corpus")
        self.assertEqual(plan.runtime_capabilities, ("filesystem.read", "shell"))
        self.assertEqual(plan.host_capabilities, ())
        self.assertEqual(assembly, before)

    def test_plan_retains_deeply_immutable_manifests_in_execution_order(self) -> None:
        plan = resolve_assembly(
            self.assembly(),
            catalog=discover_packages(MANIFESTS),
            runtime_manifest=self.runtime(),
        )

        self.assertEqual(
            tuple(manifest["package_id"] for manifest in plan.package_manifests),
            plan.composition.package_ids,
        )
        self.assertIsInstance(plan.package_manifests[0], MappingProxyType)
        with self.assertRaises(TypeError):
            plan.package_manifests[0]["kind"] = "workflow"
        required = plan.package_manifests[-1]["requires_capabilities"]
        self.assertIsInstance(required, tuple)

    def test_host_service_capability_is_separate_from_runtime_capabilities(self) -> None:
        assembly = self.controlled_assembly()
        runtime = {
            **self.runtime(),
            "capabilities": ["executor.controlled", "filesystem.read"],
        }

        plan = resolve_assembly(
            assembly,
            catalog=discover_packages(MANIFESTS),
            runtime_manifest=runtime,
        )

        self.assertEqual(plan.composition.package_ids[0], "policy.controlled-code-check")
        self.assertEqual(
            plan.runtime_capabilities,
            ("executor.controlled", "filesystem.read"),
        )
        self.assertEqual(plan.host_capabilities, ("executor.controlled",))

    def test_runtime_capability_ownership_is_deterministic(self) -> None:
        runtime = {**self.runtime(), "capabilities": ["shell", "filesystem.read"]}

        plan = resolve_assembly(
            self.assembly(),
            catalog=discover_packages(MANIFESTS),
            runtime_manifest=runtime,
        )

        self.assertEqual(plan.runtime_capabilities, ("filesystem.read", "shell"))

    def test_host_capability_ownership_is_explicit(self) -> None:
        plan = resolve_assembly(
            self.controlled_assembly(),
            catalog=discover_packages(MANIFESTS),
            runtime_manifest={**self.runtime(), "capabilities": ["filesystem.read"]},
        )

        self.assertEqual(plan.host_capabilities, ("executor.controlled",))

    def test_capability_ownership_is_immutable(self) -> None:
        plan = resolve_assembly(
            self.assembly(),
            catalog=discover_packages(MANIFESTS),
            runtime_manifest=self.runtime(),
        )

        self.assertIsInstance(plan.runtime_capabilities, tuple)
        self.assertIsInstance(plan.host_capabilities, tuple)
        with self.assertRaises(FrozenInstanceError):
            plan.runtime_capabilities = ()

    def test_capability_ownership_is_not_inferred_from_names(self) -> None:
        plan = resolve_assembly(
            self.controlled_assembly(),
            catalog=discover_packages(MANIFESTS),
            runtime_manifest={
                **self.runtime(),
                "capabilities": ["executor.controlled", "filesystem.read"],
            },
        )

        self.assertIn("executor.controlled", plan.runtime_capabilities)
        self.assertIn("executor.controlled", plan.host_capabilities)

    def test_unknown_catalog_ref_is_rejected(self) -> None:
        assembly = {
            **self.assembly(),
            "packages": [{"package_id": "missing.package", "version": "1.0.0"}],
        }

        with self.assertRaises(AssemblyError):
            resolve_assembly(
                assembly,
                catalog=discover_packages(MANIFESTS),
                runtime_manifest=self.runtime(),
            )

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
                    catalog=discover_packages(MANIFESTS),
                    runtime_manifest=runtime,
                )
            self.assertNotIn(sentinel, str(raised.exception))


class ReferenceAssemblyTests(unittest.TestCase):
    def load(self, name: str) -> dict[str, object]:
        return json.loads((ASSEMBLIES / name).read_text())

    def resolve(self, assembly: dict[str, object], runtime_id: str) -> AssemblyPlan:
        return resolve_assembly(
            {**assembly, "runtime_id": runtime_id},
            catalog=discover_packages(MANIFESTS),
            runtime_manifest={
                "protocol": "dci.agent-runtime/v1",
                "runtime_id": runtime_id,
                "capabilities": ["filesystem.read", "shell"],
            },
        )

    def test_checked_in_reference_assemblies_are_valid(self) -> None:
        paths = tuple(ASSEMBLIES.glob("*.json")) + tuple(
            CONTROLLED_ASSEMBLIES.glob("*.json")
        )
        names = {path.name for path in paths}
        self.assertEqual(
            names,
            {
                "controlled-code-validation.json",
                "dci-local-research.json",
                "dci-research-capability.json",
                "dci-research-capability-claude.json",
            },
        )
        for path in paths:
            validate_assembly_manifest(json.loads(path.read_text()))

    def test_dci_plan_has_pi_and_claude_runtime_parity(self) -> None:
        assembly = self.load("dci-local-research.json")
        pi = self.resolve(assembly, "pi.reference")
        claude = self.resolve(assembly, "claude-code.reference")
        self.assertEqual(pi.composition, claude.composition)

    def test_dci_installed_assemblies_differ_only_by_runtime_identity(self) -> None:
        pi = self.load("dci-research-capability.json")
        claude = self.load("dci-research-capability-claude.json")

        self.assertEqual(pi.pop("runtime_id"), "pi.reference")
        self.assertEqual(claude.pop("runtime_id"), "claude-code.reference")
        self.assertEqual(pi, claude)

    def test_controlled_code_keeps_executor_as_a_host_service(self) -> None:
        assembly = json.loads(
            (CONTROLLED_ASSEMBLIES / "controlled-code-validation.json").read_text()
        )
        plan = self.resolve(assembly, "pi.reference")
        self.assertIn("workflow.code-quality", plan.composition.package_ids)
        self.assertEqual(assembly["host_capabilities"], ["executor.controlled"])

    def test_reference_assemblies_contain_no_execution_or_secret_fields(self) -> None:
        forbidden = {"command", "credentials", "model", "prompt", "transport"}
        for path in ASSEMBLIES.glob("*.json"):
            self.assertTrue(forbidden.isdisjoint(self.load(path)))


class AssemblyDocumentationTests(unittest.TestCase):
    def guide(self) -> str:
        return GUIDE.read_text()

    def test_guide_defines_static_planning_and_exact_refs(self) -> None:
        guide = self.guide()
        self.assertIn("Static planning, not execution", guide)
        self.assertIn("package_id@version", guide)
        self.assertIn("AssemblyPlan", guide)

    def test_guide_separates_runtime_and_host_service_capabilities(self) -> None:
        guide = self.guide()
        self.assertIn("Runtime capabilities", guide)
        self.assertIn("Host-service capabilities", guide)
        self.assertIn("executor.controlled", guide)

    def test_guide_documents_safe_failure_and_language_ownership(self) -> None:
        guide = self.guide()
        self.assertIn("fail closed", guide)
        self.assertIn("Python owns resolution", guide)
        self.assertIn("TypeScript validates", guide)

    def test_guide_excludes_runtime_execution_and_secrets(self) -> None:
        guide = self.guide()
        self.assertIn("does not start a runtime", guide)
        self.assertIn("credentials", guide)
        self.assertIn("commands", guide)


if __name__ == "__main__":
    unittest.main()
