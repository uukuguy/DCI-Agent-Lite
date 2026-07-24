"""Provider-free setup and validation of external Asterion DCI resources."""

from __future__ import annotations

import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from asterion.dci.export import export_bcplus


class ResourceSetupError(RuntimeError):
    """A body-free resource setup failure."""


@dataclass(frozen=True)
class ResourceSpec:
    resource_id: str
    source_repo: str
    source_path: str
    destination: str
    conversion: str


@dataclass(frozen=True)
class ResourceSetupResult:
    profile: str
    status: str
    prepared: tuple[str, ...]
    present: tuple[str, ...]
    missing: tuple[str, ...]


BASIC_RESOURCES = (
    ResourceSpec(
        resource_id="corpus.bc-plus",
        source_repo="DCI-Agent/corpus",
        source_path="browsecomp_plus",
        destination="corpus/bc_plus_docs",
        conversion="bcplus",
    ),
    ResourceSpec(
        resource_id="corpus.wiki",
        source_repo="DCI-Agent/corpus",
        source_path="wiki",
        destination="corpus/wiki_corpus",
        conversion="copy",
    ),
)


def _absolute_without_resolving(path: Path) -> Path:
    return Path(os.path.abspath(path.expanduser()))


def _reject_symlink(path: Path, *, label: str) -> None:
    if path.is_symlink():
        raise ResourceSetupError(f"{label} must not be a symlink")


def _destination(root: Path, relative: str) -> Path:
    logical = PurePosixPath(relative)
    if logical.is_absolute() or ".." in logical.parts or not logical.parts:
        raise ResourceSetupError("resource destination is unsafe")
    destination = root.joinpath(*logical.parts)
    current = root
    for part in logical.parts:
        current = current / part
        _reject_symlink(current, label="resource destination")
    try:
        destination.relative_to(root)
    except ValueError as error:  # pragma: no cover - guarded by PurePosixPath
        raise ResourceSetupError("resource destination escapes resource root") from error
    return destination


def _complete_directory(path: Path) -> bool:
    if not path.is_dir():
        return False
    return any(item.is_file() for item in path.rglob("*"))


def _local_source(source_root: Path, spec: ResourceSpec) -> Path:
    _reject_symlink(source_root, label="resource source root")
    source = source_root.joinpath(*PurePosixPath(spec.source_path).parts)
    if source.is_symlink() or not source.is_dir():
        raise ResourceSetupError(
            f"{spec.resource_id} source {spec.source_path} is unavailable"
        )
    return source


def _network_source(spec: ResourceSpec, staging_root: Path) -> Path:
    try:
        from huggingface_hub import snapshot_download
    except ImportError as error:
        raise ResourceSetupError(
            "resource download support is missing; run uv sync --extra setup"
        ) from error
    try:
        snapshot_download(
            repo_id=spec.source_repo,
            repo_type="dataset",
            local_dir=staging_root,
            allow_patterns=[f"{spec.source_path}/**"],
        )
    except Exception as error:
        raise ResourceSetupError(
            f"{spec.resource_id} could not be fetched from {spec.source_repo}; "
            "authenticate with Hugging Face and retry"
        ) from error
    source = staging_root.joinpath(*PurePosixPath(spec.source_path).parts)
    if not source.is_dir():
        raise ResourceSetupError(
            f"{spec.resource_id} path {spec.source_path} is absent from "
            f"{spec.source_repo}"
        )
    return source


def _materialize(spec: ResourceSpec, source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(
            prefix=f".asterion-{spec.resource_id.replace('.', '-')}-",
            dir=destination.parent,
        )
    )
    try:
        if spec.conversion == "copy":
            shutil.copytree(source, staging, dirs_exist_ok=True)
        elif spec.conversion == "bcplus":
            export_bcplus(source, staging)
        else:  # pragma: no cover - immutable built-in manifest
            raise ResourceSetupError("resource conversion is unsupported")
        if not _complete_directory(staging):
            raise ResourceSetupError(
                f"{spec.resource_id} produced no files for {spec.destination}"
            )
        if destination.exists():
            raise ResourceSetupError(
                f"{spec.resource_id} destination {spec.destination} is incomplete; "
                "move it aside and retry"
            )
        os.replace(staging, destination)
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def prepare_resources(
    *,
    profile: str,
    resource_root: Path,
    source_root: Path | None = None,
    check_only: bool = False,
) -> ResourceSetupResult:
    """Prepare or check one external resource profile."""

    if profile != "basic":
        raise ResourceSetupError(f"unknown resource profile: {profile}")
    root = _absolute_without_resolving(resource_root)
    _reject_symlink(root, label="resource root")
    destinations = tuple(
        (spec, _destination(root, spec.destination)) for spec in BASIC_RESOURCES
    )
    present = tuple(
        spec.resource_id
        for spec, destination in destinations
        if _complete_directory(destination)
    )
    missing_specs = tuple(
        (spec, destination)
        for spec, destination in destinations
        if spec.resource_id not in present
    )
    if check_only:
        missing = tuple(spec.resource_id for spec, _ in missing_specs)
        return ResourceSetupResult(
            profile=profile,
            status="PASS" if not missing else "FAIL",
            prepared=(),
            present=present,
            missing=missing,
        )

    prepared: list[str] = []
    local_root = (
        None if source_root is None else _absolute_without_resolving(source_root)
    )
    for spec, destination in missing_specs:
        with tempfile.TemporaryDirectory(
            prefix=".asterion-resource-download-"
        ) as temporary:
            source = (
                _local_source(local_root, spec)
                if local_root is not None
                else _network_source(spec, Path(temporary))
            )
            _materialize(spec, source, destination)
        prepared.append(spec.resource_id)
    return ResourceSetupResult(
        profile=profile,
        status="PASS",
        prepared=tuple(prepared),
        present=present,
        missing=(),
    )
