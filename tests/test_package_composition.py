from __future__ import annotations

import json
import unittest
from pathlib import Path

from dci.framework.package_protocol import PackageProtocolError, validate_package_manifest
from dci.framework.packages import PackageCompositionError, compose_packages


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


class PackageCompositionTests(unittest.TestCase):
    def package(
        self,
        package_id: str,
        *,
        kind: str = "capability",
        provides: tuple[str, ...] = (),
        requires: tuple[str, ...] = (),
        policies: tuple[str, ...] = (),
        emits: tuple[str, ...] = (),
        consumes_events: tuple[str, ...] = (),
        produces: tuple[str, ...] = (),
        consumes_artifacts: tuple[str, ...] = (),
    ) -> dict[str, object]:
        return {
            "protocol": "dci.package/v1",
            "package_id": package_id,
            "version": "1.0.0",
            "kind": kind,
            "provides_capabilities": sorted(provides),
            "requires_capabilities": sorted(requires),
            "requires_policies": sorted(policies),
            "emits_events": sorted(emits),
            "consumes_events": sorted(consumes_events),
            "produces_artifacts": sorted(produces),
            "consumes_artifacts": sorted(consumes_artifacts),
        }

    def test_composition_order_is_stable_under_permuted_input(self) -> None:
        source = self.package("source", provides=("data.read",))
        consumer = self.package("consumer", requires=("data.read",))

        first = compose_packages([consumer, source])
        second = compose_packages([source, consumer])

        self.assertEqual(first.package_ids, ("source", "consumer"))
        self.assertEqual(first, second)
        self.assertEqual(first.provided_capabilities, ("data.read",))

    def test_duplicate_ids_and_ambiguous_capability_providers_are_rejected(self) -> None:
        one = self.package("one", provides=("data.read",))
        duplicate = self.package("one")
        two = self.package("two", provides=("data.read",))

        with self.assertRaises(PackageCompositionError):
            compose_packages([one, duplicate])
        with self.assertRaises(PackageCompositionError):
            compose_packages([one, two])

    def test_missing_capability_policy_event_and_artifact_edges_are_rejected(self) -> None:
        consumers = (
            self.package("capability-consumer", requires=("missing.capability",)),
            self.package("policy-consumer", policies=("policy.missing",)),
            self.package("event-consumer", consumes_events=("event.missing",)),
            self.package(
                "artifact-consumer",
                consumes_artifacts=("application/missing",),
            ),
        )

        for consumer in consumers:
            with self.subTest(package=consumer["package_id"]), self.assertRaises(
                PackageCompositionError
            ):
                compose_packages([consumer])

    def test_host_edges_satisfy_external_requirements(self) -> None:
        consumer = self.package(
            "consumer",
            requires=("filesystem.read",),
            policies=("policy.local",),
            consumes_events=("run.started",),
            consumes_artifacts=("text/plain",),
        )

        composition = compose_packages(
            [consumer],
            host_capabilities={"filesystem.read"},
            host_policies={"policy.local"},
            host_events={"run.started"},
            host_artifacts={"text/plain"},
        )

        self.assertEqual(composition.package_ids, ("consumer",))

    def test_dependency_cycles_are_rejected(self) -> None:
        first = self.package(
            "first", provides=("first.output",), requires=("second.output",)
        )
        second = self.package(
            "second", provides=("second.output",), requires=("first.output",)
        )

        with self.assertRaises(PackageCompositionError):
            compose_packages([first, second])


if __name__ == "__main__":
    unittest.main()
