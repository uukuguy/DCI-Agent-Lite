from __future__ import annotations

import os
import sys
import tempfile
import unittest
import io
import json
from pathlib import Path
from unittest.mock import patch
import asterion.dci.verification as verification_module

from asterion.applications.product import VerificationRequest
from asterion.dci.run import DciRunResult
from asterion.dci.verification import (
    BASIC_CASES,
    DciProductVerifier,
    _load_product_acceptance_runner,
    create_dci_product,
)
from tools.verify_asterion_dci_product import ProductAcceptanceSummary
from tools.verify_dci_context_acceptance import (
    ContextAcceptanceCase,
    ContextAcceptanceReadiness,
    main as context_acceptance_main,
)


class DciContextAcceptanceVerifierTests(unittest.TestCase):
    def test_level3_case_requires_compaction_without_summary(self) -> None:
        valid = ContextAcceptanceCase(
            profile="level3",
            compactions=1,
            summary_attempts=0,
            summary_successes=0,
            summary_suppressed=False,
            preserved_turns=12,
            artifact_digests=(("state.json", "a" * 64),),
        )

        valid.validate()
        with self.assertRaises(ValueError):
            ContextAcceptanceCase(
                **{**valid.__dict__, "compactions": 0}
            ).validate()
        with self.assertRaises(ValueError):
            ContextAcceptanceCase(
                **{**valid.__dict__, "summary_attempts": 1}
            ).validate()

    def test_level4_case_requires_successful_unsuppressed_summary(self) -> None:
        valid = ContextAcceptanceCase(
            profile="level4",
            compactions=1,
            summary_attempts=1,
            summary_successes=1,
            summary_suppressed=False,
            preserved_turns=12,
            artifact_digests=(("state.json", "a" * 64),),
        )

        valid.validate()
        for changes in (
            {"summary_attempts": 0},
            {"summary_successes": 0},
            {"summary_suppressed": True},
            {"preserved_turns": -1},
        ):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                ContextAcceptanceCase(
                    **{**valid.__dict__, **changes}
                ).validate()

    def test_default_mode_is_model_free_and_declares_cost_boundary(self) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()
        calls: list[object] = []

        code = context_acceptance_main(
            [],
            stdout=stdout,
            stderr=stderr,
            provider_runner=lambda *_args: calls.append(_args),
        )

        self.assertEqual(code, 0, stderr.getvalue())
        self.assertEqual(calls, [])
        self.assertIn("PASS", stdout.getvalue())
        self.assertIn("Provider operations: 0", stdout.getvalue())
        self.assertIn("Planned provider operations: 2", stdout.getvalue())
        self.assertIn("API request multiplicity: externally ambiguous", stdout.getvalue())
        self.assertIn("Full dataset ran: no", stdout.getvalue())

    def test_provider_mode_rejects_missing_authority_before_runner(self) -> None:
        calls: list[object] = []
        stderr = io.StringIO()

        code = context_acceptance_main(
            ["--provider-backed"],
            stdout=io.StringIO(),
            stderr=stderr,
            provider_runner=lambda *_args: calls.append(_args),
        )

        self.assertEqual(code, 2)
        self.assertEqual(calls, [])
        self.assertEqual(stderr.getvalue(), "DCI context acceptance preflight failed\n")

    def test_provider_report_is_body_free_digest_bound_and_exactly_two_runs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_root = Path(temp_dir).resolve() / "private-output"
            readiness = ContextAcceptanceReadiness(
                output_root=output_root,
                provider="fixture-provider",
                model="fixture-model",
                pi_revision="a" * 40,
                extension_version="0.1.0",
                extension_sha256="b" * 64,
            )
            calls: list[str] = []

            def run_case(_readiness, profile: str) -> ContextAcceptanceCase:
                calls.append(profile)
                if profile == "level3":
                    return ContextAcceptanceCase(
                        profile=profile,
                        compactions=1,
                        summary_attempts=0,
                        summary_successes=0,
                        summary_suppressed=False,
                        preserved_turns=12,
                        artifact_digests=(("state.json", "c" * 64),),
                    )
                return ContextAcceptanceCase(
                    profile=profile,
                    compactions=1,
                    summary_attempts=1,
                    summary_successes=1,
                    summary_suppressed=False,
                    preserved_turns=None,
                    artifact_digests=(("state.json", "d" * 64),),
                )

            stdout = io.StringIO()
            code = context_acceptance_main(
                [
                    "--provider-backed",
                    "--env-file",
                    str(Path(temp_dir) / "SECRET-CREDENTIAL.env"),
                    "--output-root",
                    str(output_root),
                ],
                stdout=stdout,
                stderr=io.StringIO(),
                readiness_checker=lambda *_args: readiness,
                provider_runner=run_case,
            )

            self.assertEqual(code, 0)
            self.assertEqual(calls, ["level3", "level4"])
            report = json.loads(
                (output_root / "context-acceptance.json").read_text(encoding="utf-8")
            )
            self.assertEqual(report["provider_operations"], 2)
            self.assertEqual(report["user_turns_per_case"], 13)
            self.assertEqual(report["contract_version"], "dci.context-profile/v1")
            self.assertEqual(report["extension_sha256"], "b" * 64)
            self.assertEqual(report["pi_revision"], "a" * 40)
            self.assertEqual(
                [case["profile"] for case in report["cases"]],
                ["level3", "level4"],
            )
            public = json.dumps(report) + stdout.getvalue()
            for canary in (
                "SECRET-CREDENTIAL",
                "SECRET-PROMPT",
                "SECRET-ANSWER",
                "SECRET-TOOL",
                temp_dir,
            ):
                self.assertNotIn(canary, public)

    def test_provider_failure_retains_only_body_free_attempt_count(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_root = Path(temp_dir) / "private-output"
            readiness = ContextAcceptanceReadiness(
                output_root=output_root,
                provider="fixture-provider",
                model="fixture-model",
                pi_revision="a" * 40,
                extension_version="0.2.0",
                extension_sha256="b" * 64,
            )
            calls: list[str] = []

            def fail_second(_readiness, profile: str) -> ContextAcceptanceCase:
                calls.append(profile)
                if profile == "level4":
                    raise RuntimeError("SECRET-PROVIDER-BODY")
                return ContextAcceptanceCase(
                    profile="level3",
                    compactions=1,
                    preserved_turns=12,
                    summary_attempts=0,
                    summary_successes=0,
                    summary_suppressed=False,
                    artifact_digests=(("state.json", "c" * 64),),
                )

            stderr = io.StringIO()
            code = context_acceptance_main(
                ["--provider-backed", "--env-file", "private", "--output-root", str(output_root)],
                stdout=io.StringIO(),
                stderr=stderr,
                readiness_checker=lambda *_args: readiness,
                provider_runner=fail_second,
            )

            self.assertEqual(code, 2)
            self.assertEqual(calls, ["level3", "level4"])
            failure_path = output_root / "context-acceptance-failure.json"
            report = json.loads(failure_path.read_text())
            self.assertEqual(report["attempted_provider_operations"], 2)
            self.assertEqual(failure_path.stat().st_mode & 0o777, 0o600)
            self.assertNotIn("SECRET-", failure_path.read_text() + stderr.getvalue())


class FixtureBackend:
    def __init__(
        self,
        node_major: int | None = 20,
        *,
        fail_case: str | None = None,
        verdict: bool = True,
    ) -> None:
        self.node_major = node_major
        self.fail_case = fail_case
        self.verdict = verdict
        self.calls: list[object] = []

    def node_major_version(self) -> int | None:
        return self.node_major

    def run_research_case(self, paths, request, *, output_dir):
        self.calls.append(("run", request, output_dir))
        if request.run_id == self.fail_case:
            raise RuntimeError("SECRET-PROVIDER-BODY")
        return DciRunResult(
            output_dir=output_dir,
            final_text="SECRET-ANSWER-BODY",
            events=(),
            status="completed",
        )

    def evaluate_case(self, output_dir, *, expected_answer, judge_config):
        self.calls.append(("judge", output_dir, expected_answer, judge_config))
        return self.verdict


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
        self.assertEqual(result.provider_backed_operation_count, 0)
        self.assertFalse(result.full_dataset_ran)
        self.assertEqual(backend.calls, [])

    def test_preflight_accepts_pi_managed_auth_for_openai_codex(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir).resolve()
            prepare_root(root)
            (root / "pi/.pi/agent/auth.json").write_text("{}")
            env_file = root / ".env"
            env_file.write_text(
                "DCI_PROVIDER=openai-codex\n"
                "DCI_MODEL=fixture-model\n"
                "DCI_EVAL_JUDGE_MODEL=fixture-judge\n"
                "DCI_EVAL_JUDGE_API_KEY_ENV=JUDGE_KEY\n"
                "JUDGE_KEY=SECRET-JUDGE-VALUE\n"
            )
            verifier = DciProductVerifier(repo_root=root, backend=FixtureBackend())
            with patch.dict(os.environ, {}, clear=True):
                result = verifier.preflight(env_file=env_file, corpus_root=root / "corpus")

        self.assertEqual(result.status, "PASS")


class DciBasicVerificationTests(unittest.TestCase):
    def test_basic_runs_exactly_two_cases_and_one_judge_in_order(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir).resolve()
            env_file = prepare_root(root)
            backend = FixtureBackend()
            verifier = DciProductVerifier(repo_root=root, backend=backend)
            request = VerificationRequest(
                level="basic",
                env_file=env_file,
                corpus_root=root / "corpus",
                output_root=root / "verification-output",
                acceptance_root=None,
            )
            with patch.dict(os.environ, {}, clear=True):
                result = verifier(request)

        self.assertEqual(result.status, "PASS")
        self.assertEqual(result.provider_backed_operation_count, 3)
        self.assertFalse(result.full_dataset_ran)
        self.assertEqual([call[0] for call in backend.calls], ["run", "run", "judge"])
        first_request = backend.calls[0][1]
        second_request = backend.calls[1][1]
        self.assertEqual(
            (first_request.run_id, second_request.run_id),
            ("basic-corpus-research", "runtime-context-and-judge"),
        )
        self.assertEqual(
            (first_request.cwd.name, second_request.cwd.name),
            ("wiki_corpus", "bc_plus_docs"),
        )
        self.assertEqual((first_request.provider, first_request.model), ("openai", "fixture-model"))
        self.assertEqual(first_request.max_turns, 6)
        self.assertEqual((second_request.max_turns, second_request.thinking_level), (6, "high"))
        self.assertNotEqual(backend.calls[0][2], backend.calls[1][2])
        self.assertEqual(backend.calls[2][2], "Adaku")
        public = repr(result)
        self.assertNotIn("SECRET-ANSWER-BODY", public)
        self.assertNotIn("Adaku", public)
        self.assertNotIn(BASIC_CASES[0].question, public)

    def test_basic_stops_after_first_failed_provider_request(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir).resolve()
            env_file = prepare_root(root)
            backend = FixtureBackend(fail_case="basic-corpus-research")
            verifier = DciProductVerifier(repo_root=root, backend=backend)
            with patch.dict(os.environ, {}, clear=True):
                result = verifier(
                    VerificationRequest(
                        level="basic",
                        env_file=env_file,
                        corpus_root=root / "corpus",
                        output_root=root / "verification-output",
                        acceptance_root=None,
                    )
                )

        self.assertEqual(result.status, "FAIL")
        self.assertEqual(result.provider_backed_operation_count, 1)
        self.assertEqual([call[0] for call in backend.calls], ["run"])
        self.assertNotIn("SECRET-PROVIDER-BODY", repr(result))
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
        self.assertEqual(result.provider_backed_operation_count, 0)
        failed = {check.check_id for check in result.checks if check.status == "FAIL"}
        self.assertIn("environment", failed)
        self.assertIn("node", failed)
        self.assertIn("pi", failed)
        self.assertIn("corpora", failed)
        self.assertEqual(backend.calls, [])


class DciAcceptanceVerificationTests(unittest.TestCase):
    def test_source_checkout_discovery_uses_the_converged_asterion_root(self) -> None:
        root = Path(__file__).resolve().parents[1]
        self.assertEqual(verification_module._trusted_source_checkout_root(), root)

    def test_installed_product_never_loads_acceptance_from_current_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir).resolve()
            package_file = root / "site-packages/asterion/dci/verification.py"
            package_file.parent.mkdir(parents=True)
            package_file.write_text("# installed fixture\n")
            malicious = root / "working/tools/verify_asterion_dci_product.py"
            malicious.parent.mkdir(parents=True)
            marker = root / "executed"
            malicious.write_text(f"from pathlib import Path\nPath({str(marker)!r}).touch()\n")
            with (
                patch.object(verification_module, "__file__", str(package_file)),
                patch("pathlib.Path.cwd", return_value=malicious.parents[1]),
            ):
                product = create_dci_product(backend=FixtureBackend())
                result = product.verifier(
                    VerificationRequest(
                        level="acceptance",
                        env_file=None,
                        corpus_root=None,
                        output_root=None,
                        acceptance_root=None,
                    )
                )
            self.assertEqual(result.status, "NOT RUN")
            self.assertFalse(marker.exists())

    def test_source_acceptance_loader_does_not_depend_on_console_script_sys_path(self) -> None:
        root = Path(__file__).resolve().parents[1]
        previous = {
            name: sys.modules.pop(name)
            for name in tuple(sys.modules)
            if name == "tools" or name.startswith("tools.")
        }
        isolated_path = [
            value
            for value in sys.path
            if Path(value or ".").resolve() != root
        ]
        try:
            with patch.object(sys, "path", isolated_path):
                runner = _load_product_acceptance_runner(root)
            self.assertTrue(callable(runner))
        finally:
            for name in tuple(sys.modules):
                if name == "tools" or name.startswith("tools."):
                    sys.modules.pop(name)
            sys.modules.update(previous)

    def _runner(self, calls):
        def run(root, acceptance_root=None):
            calls.append(("acceptance", root, acceptance_root))
            return ProductAcceptanceSummary(
                product_rows=(8, 8),
                delegated_inventory=(533, 533),
                launcher_pairs=(12, 12),
                batch_extras=(6, 6),
                bounded_acceptance=(7, 7),
                provider_backed_executed=0,
                private_acceptance=None,
            )

        return run

    def test_acceptance_is_provider_free_and_maps_complete_inventory(self) -> None:
        calls = []
        backend = FixtureBackend()
        verifier = DciProductVerifier(
            repo_root=Path.cwd(),
            backend=backend,
            acceptance_runner=self._runner(calls),
            acceptance_source_root=Path.cwd(),
        )
        result = verifier(
            VerificationRequest(
                level="acceptance",
                env_file=None,
                corpus_root=None,
                output_root=None,
                acceptance_root=None,
            )
        )

        self.assertEqual(result.status, "PASS")
        self.assertEqual(result.provider_backed_operation_count, 0)
        self.assertFalse(result.full_dataset_ran)
        self.assertEqual(backend.calls, [])
        self.assertEqual(len(calls), 1)
        counts = {check.check_id: dict(check.counts) for check in result.checks}
        self.assertEqual(counts["product-rows"], {"actual": 8, "expected": 8})
        self.assertEqual(counts["delegated-inventory"], {"actual": 533, "expected": 533})

    def test_complete_runs_preflight_basic_acceptance_and_keeps_three_request_bound(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir).resolve()
            env_file = prepare_root(root)
            backend = FixtureBackend()
            calls = []
            verifier = DciProductVerifier(
                repo_root=root,
                backend=backend,
                acceptance_runner=self._runner(calls),
                acceptance_source_root=root,
            )
            with patch.dict(os.environ, {}, clear=True):
                result = verifier(
                    VerificationRequest(
                        level="complete",
                        env_file=env_file,
                        corpus_root=root / "corpus",
                        output_root=root / "verification-output",
                        acceptance_root=None,
                    )
                )

        self.assertEqual(result.status, "PASS")
        self.assertEqual(result.provider_backed_operation_count, 3)
        self.assertFalse(result.full_dataset_ran)
        self.assertEqual([call[0] for call in backend.calls], ["run", "run", "judge"])
        self.assertEqual(calls[0][0], "acceptance")


if __name__ == "__main__":
    unittest.main()
