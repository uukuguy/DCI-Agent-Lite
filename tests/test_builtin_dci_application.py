from __future__ import annotations

import unittest
from importlib import metadata
from pathlib import Path

from asterion.applications.discovery import (
    list_application_providers,
    load_application_provider,
)
from asterion.applications.dci_agent_lite.provider import create_provider
from asterion.packages.catalog import PackageRef


ROOT = Path(__file__).resolve().parents[1]
ASTERION = ROOT / "asterion/src/asterion"


class BuiltinDciApplicationTests(unittest.TestCase):
    def test_provider_binds_the_supplied_native_executor(self) -> None:
        native_executor = object()

        provider = create_provider(native_executor=native_executor)

        implementation = provider.applications[0].implementations[0][1]
        self.assertIs(implementation._native_executor, native_executor)
        self.assertIsNotNone(provider.product)
        self.assertEqual(provider.product.description.product_id, "asterion-dci")

    def test_distribution_registers_the_builtin_dci_provider(self) -> None:
        entries = tuple(metadata.entry_points(group="asterion.applications"))
        metadata_values = list_application_providers(entry_points=entries)
        providers = {item.provider_id: item for item in metadata_values}
        self.assertIn("dci-agent-lite", providers)
        self.assertEqual(providers["dci-agent-lite"].distribution_name, "asterion")

    def test_selected_provider_uses_one_asterion_resource_root(self) -> None:
        provider = load_application_provider("dci-agent-lite")
        self.assertEqual(provider.resource_root, ASTERION.resolve())
        self.assertEqual(len(provider.applications), 1)
        application = provider.applications[0]
        self.assertEqual(
            (application.application_id, application.version),
            ("dci.research-capability", "1.0.0"),
        )
        self.assertEqual(
            application.runtime_ids,
            ("claude-code.reference", "pi.reference"),
        )
        self.assertEqual(
            {path.name for path in application.assembly_paths},
            {
                "dci-research-capability-claude.json",
                "dci-research-capability.json",
            },
        )
        self.assertEqual(
            tuple(ref for ref, _ in application.implementations),
            (PackageRef("dci.research", "1.0.0"),),
        )
        for path in application.assembly_paths + application.catalog_roots:
            self.assertTrue(path.is_relative_to(provider.resource_root))

    def test_generic_application_modules_do_not_name_dci(self) -> None:
        generic_files = [
            ASTERION / "applications/discovery.py",
            ASTERION / "applications/provider.py",
            ASTERION / "applications/selection.py",
            ASTERION / "cli.py",
        ]
        source = "\n".join(path.read_text() for path in generic_files)
        self.assertNotIn("dci-agent-lite", source)
        self.assertNotIn("dci.research", source)
        self.assertNotIn("DciRunExecutor", source)
        self.assertNotIn("answer_artifact_uri", source)


if __name__ == "__main__":
    unittest.main()
