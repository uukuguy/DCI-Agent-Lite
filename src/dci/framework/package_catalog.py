"""Deterministic discovery for portable local framework packages."""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

from dci.framework.package_protocol import validate_package_manifest


class PackageCatalogError(ValueError):
    """Raised when local package discovery or selection is ambiguous or invalid."""


@dataclass(frozen=True, order=True)
class PackageRef:
    package_id: str
    version: str


@dataclass(frozen=True)
class CatalogEntry:
    ref: PackageRef
    source: Path
    manifest: Mapping[str, object]


@dataclass(frozen=True)
class PackageCatalog:
    entries: tuple[CatalogEntry, ...]


def discover_packages(roots: Iterable[Path]) -> PackageCatalog:
    """Discover validated direct JSON children under explicit local roots."""

    canonical_roots = sorted(Path(root).resolve(strict=True) for root in roots)
    entries: list[CatalogEntry] = []
    for root in canonical_roots:
        for source in sorted(root.iterdir()):
            if source.suffix != ".json" or not source.is_file():
                continue
            manifest = json.loads(source.read_text())
            if not isinstance(manifest, dict):
                raise PackageCatalogError("package document must be an object")
            validate_package_manifest(manifest)
            package_id = manifest["package_id"]
            version = manifest["version"]
            assert isinstance(package_id, str) and isinstance(version, str)
            entries.append(
                CatalogEntry(
                    ref=PackageRef(package_id, version),
                    source=source.resolve(),
                    manifest=manifest,
                )
            )
    return PackageCatalog(
        entries=tuple(sorted(entries, key=lambda entry: (entry.ref, str(entry.source))))
    )
