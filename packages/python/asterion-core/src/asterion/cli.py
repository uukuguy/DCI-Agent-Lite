"""Generic command line for explicitly selected installed applications."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import TextIO

from asterion.applications.discovery import (
    list_application_providers,
    load_application_provider,
)
from asterion.applications.provider import ApplicationProviderError
from asterion.applications.selection import (
    parse_application_selector,
    select_installed_application,
)
from asterion.assembly.protocol import AssemblyError, resolve_assembly
from asterion.packages.catalog import discover_packages
from asterion.packages.execution import (
    PackageExecutionError,
    validate_implementation_bindings,
)
from asterion.runner.application import ApplicationRunError
from asterion.runner.composed import run_composed_application
from asterion.runtime.factory import (
    RuntimeFactoryContext,
    RuntimeFactoryError,
    RuntimeFactoryRegistry,
)
from asterion.runtime.defaults import default_runtime_factory_registry


def main(
    argv: list[str] | None = None,
    *,
    entry_points: Iterable[object] | None = None,
    runtime_factories: RuntimeFactoryRegistry | None = None,
    stdin: TextIO | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    """Run the generic installed-application CLI."""

    stdin = sys.stdin if stdin is None else stdin
    stdout = sys.stdout if stdout is None else stdout
    stderr = sys.stderr if stderr is None else stderr
    registry = (
        default_runtime_factory_registry()
        if runtime_factories is None
        else runtime_factories
    )
    parser = _parser()
    try:
        args = parser.parse_args(argv)
        if args.command == "list":
            if args.provider is not None:
                provider = load_application_provider(
                    args.provider, entry_points=entry_points
                )
                payload = {
                    "provider_id": provider.provider_id,
                    "applications": [
                        {
                            "application_id": application.application_id,
                            "version": application.version,
                            "selector": (
                                f"{application.application_id}@{application.version}"
                            ),
                            "runtime_ids": list(application.runtime_ids),
                        }
                        for application in sorted(
                            provider.applications,
                            key=lambda item: (item.application_id, item.version),
                        )
                    ],
                }
                stdout.write(json.dumps(payload, sort_keys=True) + "\n")
                return 0
            payload = [
                {
                    "provider_id": item.provider_id,
                    "distribution_name": item.distribution_name,
                    "distribution_version": item.distribution_version,
                }
                for item in list_application_providers(entry_points=entry_points)
            ]
            stdout.write(json.dumps(payload, sort_keys=True) + "\n")
            return 0
        if sum(
            value is not None
            for value in (args.application, args.assembly, args.legacy_assembly)
        ) != 1:
            raise ApplicationProviderError("application selection mode is invalid")
        return asyncio.run(
            _run(
                args,
                entry_points=entry_points,
                registry=registry,
                stdin=stdin,
                stdout=stdout,
            )
        )
    except (
        ApplicationProviderError,
        ApplicationRunError,
        AssemblyError,
        PackageExecutionError,
        RuntimeFactoryError,
        OSError,
        TypeError,
        ValueError,
    ):
        stderr.write("asterion: command failed\n")
        return 2


async def _run(
    args: argparse.Namespace,
    *,
    entry_points: Iterable[object] | None,
    registry: RuntimeFactoryRegistry,
    stdin: TextIO,
    stdout: TextIO,
) -> int:
    provider = load_application_provider(
        args.provider, entry_points=entry_points
    )
    if args.application is not None:
        application = select_installed_application(
            provider, parse_application_selector(args.application)
        )
        assembly_path = application.assembly_paths[0]
    else:
        requested = Path(args.assembly or args.legacy_assembly)
        if requested.is_symlink():
            raise ApplicationProviderError("application assembly is unsafe")
        assembly_path = requested.resolve(strict=True)
        matches = [
            candidate
            for candidate in provider.applications
            if assembly_path in candidate.assembly_paths
        ]
        if len(matches) != 1:
            raise ApplicationProviderError("application assembly selection is invalid")
        application = matches[0]
    if args.runtime not in application.runtime_ids:
        raise ApplicationProviderError("application runtime selection is invalid")
    runtime_binding = registry.select(args.runtime)
    assembly = json.loads(assembly_path.read_text())
    plan = resolve_assembly(
        assembly,
        catalog=discover_packages(application.catalog_roots),
        runtime_manifest=runtime_binding.manifest.to_mapping(),
    )
    validate_implementation_bindings(plan, application.implementations)
    context = RuntimeFactoryContext(
        provider_id=provider.provider_id,
        application_id=application.application_id,
        application_version=application.version,
        runtime_id=args.runtime,
        assembly_path=assembly_path,
        options={},
    )
    runtime = runtime_binding.factory(context)
    input_text = args.input if args.input is not None else stdin.read()
    result = await run_composed_application(
        plan,
        implementations=application.implementations,
        runtime=runtime,
        run_id=args.run_id,
        input_text=input_text,
        host_services={},
    )
    stdout.write(json.dumps(_thaw(result.__dict__), sort_keys=True) + "\n")
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="asterion")
    subparsers = parser.add_subparsers(dest="command", required=True)
    list_command = subparsers.add_parser("list")
    list_command.add_argument("--provider")
    run = subparsers.add_parser("run")
    run.add_argument("--provider", required=True)
    run.add_argument("--runtime", required=True)
    run.add_argument("--run-id", default="asterion-run")
    run.add_argument("--input")
    run.add_argument("--application")
    run.add_argument("--assembly")
    run.add_argument("legacy_assembly", nargs="?")
    return parser


def _thaw(value: object) -> object:
    if isinstance(value, Mapping):
        return {key: _thaw(item) for key, item in value.items()}
    if isinstance(value, (tuple, list, set, frozenset)):
        return [_thaw(item) for item in value]
    return value
