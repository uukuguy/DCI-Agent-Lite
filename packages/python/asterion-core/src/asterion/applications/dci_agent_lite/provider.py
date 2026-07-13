"""First-party DCI application binding shipped with Asterion."""

from __future__ import annotations

from importlib import resources
from pathlib import Path

from asterion.applications.provider import (
    APPLICATION_PROVIDER_PROTOCOL,
    InstalledApplication,
    InstalledApplicationProvider,
)
from asterion.capabilities.dci_research import DciLocalResearchImplementation
from asterion.packages.catalog import PackageRef


def create_provider() -> InstalledApplicationProvider:
    """Return the immutable built-in DCI research application binding."""

    root = Path(str(resources.files("asterion"))).resolve()
    application_root = root / "applications/dci_agent_lite"
    capability_root = root / "capabilities/dci_research"
    return InstalledApplicationProvider(
        protocol=APPLICATION_PROVIDER_PROTOCOL,
        provider_id="dci-agent-lite",
        resource_root=root,
        applications=(
            InstalledApplication(
                application_id="dci.research-capability",
                version="1.0.0",
                assembly_paths=(
                    application_root / "assemblies/dci-research-capability.json",
                ),
                catalog_roots=(capability_root / "manifests",),
                implementations=(
                    (
                        PackageRef("dci.research", "1.0.0"),
                        DciLocalResearchImplementation(),
                    ),
                ),
                runtime_ids=("pi.reference",),
            ),
        ),
    )
