from __future__ import annotations

import unittest
from importlib import metadata
from pathlib import Path

from asterion.applications.discovery import (
    list_application_providers,
    load_application_provider,
)
from asterion.packages.catalog import PackageRef


ROOT = Path(__file__).resolve().parents[1]
ASTERION = ROOT / "packages/python/asterion-core/src/asterion"


class BuiltinDciApplicationTests(unittest.TestCase):
    def test_distribution_registers_one_builtin_dci_provider(self) -> None:
        entries = tuple(metadata.entry_points(group="asterion.applications"))
        metadata_values = list_application_providers(entry_points=entries)
        self.assertEqual([item.provider_id for item in metadata_values], ["dci-agent-lite"])
        self.assertEqual(metadata_values[0].distribution_name, "asterion")

    def test_selected_provider_uses_one_asterion_resource_root(self) -> None:
        provider = load_application_provider("dci-agent-lite")
        self.assertEqual(provider.resource_root, ASTERION.resolve())
        self.assertEqual(len(provider.applications), 1)
        application = provider.applications[0]
        self.assertEqual(
            (application.application_id, application.version),
            ("dci.research-capability", "1.0.0"),
        )
        self.assertEqual(application.runtime_ids, ("pi.reference",))
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


if __name__ == "__main__":
    unittest.main()
