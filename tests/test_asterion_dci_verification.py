from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from asterion.dci.verification import DciProductVerifier, create_dci_product


class FixtureBackend:
    def __init__(self, node_major: int | None = 20) -> None:
        self.node_major = node_major
        self.calls: list[object] = []

    def node_major_version(self) -> int | None:
        return self.node_major


def prepare_root(root: Path) -> Path:
    (root / "pi/packages/coding-agent").mkdir(parents=True)
    (root / "pi/.pi/agent").mkdir(parents=True)
    (root / "pi/packages/coding-agent/package.json").write_text("{}")
    (root / "corpus/wiki_corpus").mkdir(parents=True)
    (root / "corpus/bc_plus_docs").mkdir(parents=True)
    env_file = root / ".env"
    env_file.write_text(
        "DCI_PROVIDER=openai\n"
        "DCI_MODEL=fixture-model\n"
        "OPENAI_API_KEY=SECRET-PROVIDER-VALUE\n"
        "DCI_EVAL_JUDGE_MODEL=fixture-judge\n"
        "DCI_EVAL_JUDGE_API_KEY_ENV=JUDGE_KEY\n"
        "JUDGE_KEY=SECRET-JUDGE-VALUE\n"
    )
    return env_file


class DciDescriptionAndPreflightTests(unittest.TestCase):
    def test_product_describes_plain_functions_configuration_and_four_levels(self) -> None:
        product = create_dci_product(repo_root=Path.cwd(), backend=FixtureBackend())
        description = product.description

        self.assertEqual(description.product_id, "asterion-dci")
        self.assertEqual(
            tuple(function.function_id for function in description.functions),
            (
                "benchmark",
                "evaluate",
                "export",
                "installed-application",
                "research",
                "resume",
                "terminal",
            ),
        )
        self.assertEqual(
            tuple(profile.level for profile in description.profiles),
            ("acceptance", "basic", "complete", "preflight"),
        )
        rendered = repr(description)
        for name in (
            "DCI_PROVIDER",
            "DCI_MODEL",
            "DCI_PI_DIR",
            "DCI_EVAL_JUDGE_MODEL",
        ):
            self.assertIn(name, rendered)
        self.assertNotIn("SECRET-", rendered)

    def test_preflight_passes_without_provider_calls_and_never_returns_secrets_or_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir).resolve()
            env_file = prepare_root(root)
            backend = FixtureBackend()
            verifier = DciProductVerifier(repo_root=root, backend=backend)
            with patch.dict(os.environ, {}, clear=True):
                result = verifier.preflight(env_file=env_file, corpus_root=root / "corpus")

        self.assertEqual(result.status, "PASS")
        self.assertEqual(result.external_request_count, 0)
        self.assertFalse(result.full_dataset_ran)
        self.assertEqual(backend.calls, [])
        public = repr(result)
        self.assertNotIn("SECRET-PROVIDER-VALUE", public)
        self.assertNotIn("SECRET-JUDGE-VALUE", public)
        self.assertNotIn(temp_dir, public)

    def test_preflight_names_missing_prerequisites_without_backend_work(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir).resolve()
            env_file = root / "missing.env"
            backend = FixtureBackend(node_major=19)
            verifier = DciProductVerifier(repo_root=root, backend=backend)
            with patch.dict(os.environ, {}, clear=True):
                result = verifier.preflight(env_file=env_file, corpus_root=root / "corpus")

        self.assertEqual(result.status, "FAIL")
        self.assertEqual(result.external_request_count, 0)
        failed = {check.check_id for check in result.checks if check.status == "FAIL"}
        self.assertIn("environment", failed)
        self.assertIn("node", failed)
        self.assertIn("pi", failed)
        self.assertIn("corpora", failed)
        self.assertEqual(backend.calls, [])


if __name__ == "__main__":
    unittest.main()
