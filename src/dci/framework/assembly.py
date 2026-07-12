"""Portable static application assembly contracts."""

from __future__ import annotations

import re
from collections.abc import Mapping


ASSEMBLY_PROTOCOL_VERSION = "dci.assembly/v1"
IDENTIFIER = re.compile(r"^[a-z][a-z0-9]*(?:[.-][a-z0-9]+)*$")
SEMANTIC_VERSION = re.compile(
    r"^(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)$"
)
EDGE_FIELDS = (
    "host_capabilities",
    "host_policies",
    "host_events",
    "host_artifacts",
)
REQUIRED_FIELDS = {
    "protocol",
    "application_id",
    "version",
    "runtime_id",
    "packages",
    *EDGE_FIELDS,
}


class AssemblyError(ValueError):
    """Raised when a static application assembly is invalid or unresolved."""


def validate_assembly_manifest(value: Mapping[str, object]) -> None:
    """Validate one closed canonical dci.assembly/v1 manifest."""

    if not isinstance(value, Mapping) or not all(
        isinstance(key, str) for key in value
    ):
        raise AssemblyError("assembly manifest must be an object")
    if value.keys() != REQUIRED_FIELDS:
        raise AssemblyError("assembly manifest fields are not recognized")
    if value["protocol"] != ASSEMBLY_PROTOCOL_VERSION:
        raise AssemblyError("assembly protocol is not dci.assembly/v1")
    for field in ("application_id", "runtime_id"):
        item = value[field]
        if not isinstance(item, str) or IDENTIFIER.fullmatch(item) is None:
            raise AssemblyError(f"assembly {field} is invalid")
    version = value["version"]
    if not isinstance(version, str) or SEMANTIC_VERSION.fullmatch(version) is None:
        raise AssemblyError("assembly version is invalid")

    packages = value["packages"]
    if not isinstance(packages, list) or not packages:
        raise AssemblyError("assembly packages must be a non-empty array")
    refs: list[tuple[str, str]] = []
    for package in packages:
        if not isinstance(package, Mapping) or package.keys() != {
            "package_id",
            "version",
        }:
            raise AssemblyError("assembly package ref is invalid")
        package_id = package["package_id"]
        package_version = package["version"]
        if (
            not isinstance(package_id, str)
            or IDENTIFIER.fullmatch(package_id) is None
            or not isinstance(package_version, str)
            or SEMANTIC_VERSION.fullmatch(package_version) is None
        ):
            raise AssemblyError("assembly package ref is invalid")
        refs.append((package_id, package_version))
    if refs != sorted(set(refs)):
        raise AssemblyError("assembly package refs must be sorted and unique")

    for field in EDGE_FIELDS:
        edges = value[field]
        if (
            not isinstance(edges, list)
            or any(not isinstance(edge, str) or not edge for edge in edges)
            or edges != sorted(set(edges))
        ):
            raise AssemblyError(f"assembly {field} must be sorted unique strings")
