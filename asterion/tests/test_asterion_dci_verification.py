from __future__ import annotations

import shutil
import tempfile
import unittest
from importlib import resources
from pathlib import Path
from unittest.mock import patch

from asterion.applications.controlled_code import (
    create_provider as create_controlled_provider,
)
from asterion.applications.dci_agent_lite import create_provider as create_dci_provider
from asterion.applications.product import VerificationRequest
from asterion.applications.provider import validate_installed_provider
from asterion.dci.verification import DciProductVerifier


PROJECT = Path(__file__).resolve().parents[1]
SOURCE = PROJECT / "src/asterion"
EXPECTED_CHECKS = (
    "application-assemblies",
    "application-providers",
    "capability-manifests",
    "context-profiles",
    "paper-benchmarks",
    "paper-scopes",
    "provider-requests",
)


class ExplodingBackend:
    def node_major_version(self) -> int | None:
        raise AssertionError("acceptance called the backend")

    def run_research_case(self, *args, **kwargs):
        del args, kwargs
        raise AssertionError("acceptance called the backend")

    def evaluate_case(self, *args, **kwargs):
        del args, kwargs
        raise AssertionError("acceptance called the backend")


def acceptance_request(*, acceptance_root: Path | None = None) -> VerificationRequest:
    return VerificationRequest(
        level="acceptance",
        env_file=None,
        corpus_root=None,
        output_root=None,
        acceptance_root=acceptance_root,
    )


class InstalledAcceptanceTests(unittest.TestCase):
    def test_builtin_provider_and_resource_closure_has_exact_counts(self) -> None:
        providers = (
            validate_installed_provider(
                create_controlled_provider(), selected_id="controlled-code"
            ),
            validate_installed_provider(
                create_dci_provider(), selected_id="dci-agent-lite"
            ),
        )
        applications = tuple(
            application
            for provider in providers
            for application in provider.applications
        )
        bound_assemblies = tuple(
            path
            for application in applications
            for path in application.assembly_paths
        )
        package_root = Path(str(resources.files("asterion"))).resolve()

        self.assertEqual(len(providers), 2)
        self.assertEqual(len(applications), 3)
        self.assertEqual(len(bound_assemblies), 5)
        self.assertEqual(
            len(tuple((package_root / "applications").glob("*/assemblies/*.json"))),
            6,
        )
        self.assertEqual(
            len(tuple((package_root / "capabilities").glob("*/manifests/*.json"))),
            11,
        )

    def test_acceptance_is_package_owned_exact_and_provider_free(self) -> None:
        verifier = DciProductVerifier(repo_root=PROJECT, backend=ExplodingBackend())

        result = verifier(acceptance_request())

        self.assertEqual(result.status, "PASS")
        self.assertEqual(result.provider_backed_operation_count, 0)
        self.assertFalse(result.full_dataset_ran)
        self.assertEqual(tuple(check.check_id for check in result.checks), EXPECTED_CHECKS)
        self.assertTrue(all(check.status == "PASS" for check in result.checks))
        self.assertEqual(
            {check.check_id: dict(check.counts) for check in result.checks},
            {
                "application-assemblies": {"actual": 6, "expected": 6},
                "application-providers": {"actual": 2, "expected": 2},
                "capability-manifests": {"actual": 11, "expected": 11},
                "context-profiles": {"actual": 5, "expected": 5},
                "paper-benchmarks": {"actual": 13, "expected": 13},
                "paper-scopes": {"actual": 16, "expected": 16},
                "provider-requests": {"actual": 0, "expected": 0},
            },
        )

    def test_acceptance_ignores_source_evidence_path(self) -> None:
        verifier = DciProductVerifier(repo_root=PROJECT, backend=ExplodingBackend())
        with tempfile.TemporaryDirectory() as temp_dir:
            result = verifier(
                acceptance_request(acceptance_root=Path(temp_dir) / "untrusted")
            )

        self.assertEqual(result.status, "PASS")
        self.assertEqual(tuple(check.check_id for check in result.checks), EXPECTED_CHECKS)

    def test_acceptance_fails_when_packaged_manifest_closure_is_incomplete(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            package_root = Path(temp_dir) / "asterion"
            shutil.copytree(SOURCE, package_root)
            next(
                (package_root / "capabilities/dci_research/manifests").glob("*.json")
            ).unlink()
            verifier = DciProductVerifier(
                repo_root=Path(temp_dir), backend=ExplodingBackend()
            )
            with patch("importlib.resources.files", return_value=package_root):
                result = verifier(acceptance_request())

        self.assertEqual(result.status, "FAIL")
        self.assertEqual(result.provider_backed_operation_count, 0)
        self.assertFalse(result.full_dataset_ran)


if __name__ == "__main__":
    unittest.main()
