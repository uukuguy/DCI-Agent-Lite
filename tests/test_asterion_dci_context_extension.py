from __future__ import annotations

import hashlib
import json
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from asterion.dci.context_extension import (
    ContextExtensionError,
    resolve_context_extension,
)


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "asterion/packages/typescript/dci-context-extension"
RESOURCE_PACKAGE = ROOT / "asterion/src/asterion/dci/resources/pi"
SOURCE = PACKAGE / "src/dci-context-extension.ts"


class AsterionDciContextExtensionTests(unittest.TestCase):
    def test_sync_check_proves_source_resource_and_manifest_are_exact(self) -> None:
        completed = subprocess.run(
            ["npm", "--prefix", str(PACKAGE), "run", "check-resource"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        mirrored = RESOURCE_PACKAGE / "dci-context-extension.ts"
        manifest = json.loads(
            (RESOURCE_PACKAGE / "context-extension-manifest.json").read_text()
        )
        source_bytes = SOURCE.read_bytes()
        self.assertEqual(mirrored.read_bytes(), source_bytes)
        self.assertEqual(
            manifest,
            {
                "schema": "dci.context-extension-manifest/v1",
                "extension_version": "0.2.0",
                "contract_version": "dci.context-profile/v1",
                "resource": "dci-context-extension.ts",
                "byte_length": len(source_bytes),
                "sha256": hashlib.sha256(source_bytes).hexdigest(),
            },
        )

    def test_resolver_returns_verified_packaged_identity(self) -> None:
        expected_bytes = SOURCE.read_bytes()

        with resolve_context_extension() as resolved:
            self.assertEqual(resolved.path.read_bytes(), expected_bytes)
            self.assertEqual(resolved.version, "0.2.0")
            self.assertEqual(resolved.contract_version, "dci.context-profile/v1")
            self.assertEqual(
                resolved.sha256, hashlib.sha256(expected_bytes).hexdigest()
            )
            self.assertTrue(resolved.path.is_file())

    def test_isolated_wheel_resolves_the_same_extension_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            wheel_dir = root / "wheel"
            wheel_dir.mkdir()
            subprocess.run(
                [
                    "uv",
                    "build",
                    "--package",
                    "asterion",
                    "--wheel",
                    "--out-dir",
                    str(wheel_dir),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=True,
            )
            environment = root / "venv"
            subprocess.run(
                [
                    "uv",
                    "venv",
                    "--python",
                    "3.10",
                    "--system-site-packages",
                    str(environment),
                ],
                cwd=root,
                text=True,
                capture_output=True,
                check=True,
            )
            python = environment / "bin/python"
            wheel = next(wheel_dir.glob("*.whl"))
            subprocess.run(
                ["uv", "pip", "install", "--python", str(python), str(wheel)],
                cwd=root,
                text=True,
                capture_output=True,
                check=True,
            )
            probe_script = "\n".join(
                (
                    "import hashlib, json, os, sys, types",
                    "from pathlib import Path",
                    "dotenv = types.ModuleType('dotenv')",
                    "dotenv.load_dotenv = lambda *args, **kwargs: False",
                    "sys.modules['dotenv'] = dotenv",
                    "from asterion.applications.dci_agent_lite.provider import create_provider",
                    "from asterion.dci.application_executor import EnvironmentDciRunExecutor",
                    "from asterion.dci.benchmark import _runtime_document",
                    "from asterion.dci.cli import _parser",
                    "from asterion.dci.config import resolve_dci_runtime_options",
                    "from asterion.dci.context_extension import resolve_context_extension",
                    "from asterion.dci.context_profiles import context_profile_names",
                    "from asterion.dci.run import DciRunRequest",
                    "cm = resolve_context_extension()",
                    "extension = cm.__enter__()",
                    "names = context_profile_names()",
                    "parsed = [_parser().parse_args(['run', '--runtime-context-level', name, 'q']).runtime_context_level for name in names]",
                    "documents = [_runtime_document(resolve_dci_runtime_options({'runtime_context_level': name})) for name in names]",
                    "mapped = []",
                    "executor = EnvironmentDciRunExecutor(repo_root=Path.cwd(), run_native=lambda _paths, request: mapped.append(request.runtime_context_level))",
                    "[(os.environ.__setitem__('DCI_RUNTIME_CONTEXT_LEVEL', name), executor.run(DciRunRequest(run_id=name, question='q', cwd=Path.cwd()))) for name in names]",
                    "provider = create_provider(native_executor=executor)",
                    "print(json.dumps({'sha256': extension.sha256, 'bytes': hashlib.sha256(extension.path.read_bytes()).hexdigest(), 'version': extension.version, 'contract': extension.contract_version, 'parsed': parsed, 'mapped': mapped, 'documents': documents, 'provider': provider.provider_id}))",
                    "cm.__exit__(None, None, None)",
                )
            )
            probe = subprocess.run(
                [
                    str(python),
                    "-c",
                    probe_script,
                ],
                cwd=root,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(probe.returncode, 0, probe.stderr)
            identity = json.loads(probe.stdout)
            expected_digest = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
            names = ["level0", "level1", "level2", "level3", "level4"]
            self.assertEqual(identity["sha256"], expected_digest)
            self.assertEqual(identity["bytes"], expected_digest)
            self.assertEqual(identity["version"], "0.2.0")
            self.assertEqual(identity["contract"], "dci.context-profile/v1")
            self.assertEqual(identity["parsed"], names)
            self.assertEqual(identity["mapped"], names)
            self.assertEqual(identity["provider"], "dci-agent-lite")
            self.assertEqual(
                [document["context_policy_identity"]["profile"]["profile"] for document in identity["documents"]],
                names,
            )
            self.assertTrue(
                all(
                    document["context_policy_identity"]["extension_sha256"]
                    == expected_digest
                    for document in identity["documents"]
                )
            )

    def test_resolver_rejects_unsafe_resource_shapes_and_permissions(self) -> None:
        cases = ("missing", "directory", "symlink", "world-writable")
        for case in cases:
            with self.subTest(case=case), tempfile.TemporaryDirectory() as temp_dir:
                package = Path(temp_dir)
                source = package / "dci-context-extension.ts"
                source_bytes = b"export default function extension() {}\n"
                if case == "directory":
                    source.mkdir()
                elif case == "symlink":
                    target = package / "outside.ts"
                    target.write_bytes(source_bytes)
                    source.symlink_to(target)
                elif case != "missing":
                    source.write_bytes(source_bytes)
                    if case == "world-writable":
                        source.chmod(source.stat().st_mode | stat.S_IWOTH)
                self._write_manifest(package, source_bytes)

                with mock.patch(
                    "asterion.dci.context_extension.resources.files",
                    return_value=package,
                ):
                    with self.assertRaisesRegex(
                        ContextExtensionError, "context extension is invalid"
                    ):
                        with resolve_context_extension():
                            pass

    def test_resolver_rejects_digest_drift_and_runtime_imports(self) -> None:
        cases = {
            "digest": b"export default function extension() {}\n",
            "runtime-import": b'import value from "dependency";\nexport default value;\n',
        }
        for case, source_bytes in cases.items():
            with self.subTest(case=case), tempfile.TemporaryDirectory() as temp_dir:
                package = Path(temp_dir)
                (package / "dci-context-extension.ts").write_bytes(source_bytes)
                self._write_manifest(
                    package,
                    source_bytes,
                    sha256=("0" * 64 if case == "digest" else None),
                )

                with mock.patch(
                    "asterion.dci.context_extension.resources.files",
                    return_value=package,
                ):
                    with self.assertRaisesRegex(
                        ContextExtensionError, "context extension is invalid"
                    ):
                        with resolve_context_extension():
                            pass

    def _write_manifest(
        self, package: Path, source_bytes: bytes, *, sha256: str | None = None
    ) -> None:
        manifest = {
            "schema": "dci.context-extension-manifest/v1",
            "extension_version": "0.2.0",
            "contract_version": "dci.context-profile/v1",
            "resource": "dci-context-extension.ts",
            "byte_length": len(source_bytes),
            "sha256": sha256 or hashlib.sha256(source_bytes).hexdigest(),
        }
        (package / "context-extension-manifest.json").write_text(
            json.dumps(manifest), encoding="utf-8"
        )


if __name__ == "__main__":
    unittest.main()
