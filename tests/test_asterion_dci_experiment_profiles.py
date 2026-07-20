from __future__ import annotations

import io
import copy
import json
import os
import stat
import tempfile
import unittest
from dataclasses import replace
from importlib import resources
from pathlib import Path
from unittest import mock

from asterion.dci.experiment_profiles import (
    FullExecutionAuthorization,
    authorize_full_execution,
    experiment_profile_ids,
    experiment_profile_sha256,
    resolve_experiment_profile,
)
from asterion.dci.paper_benchmarks import (
    paper_benchmark_inventory_sha256,
    paper_experiment_scopes_sha256,
    require_af320_executable_scope,
    resolve_paper_benchmark,
    resolve_paper_experiment_scope,
)
from asterion.dci.verification import paper_reproduce_main


_EXPECTED_PROFILE_IDS = (
    "current-default/pi",
    "current-default/claude-subscription",
    "current-default/claude-minimax",
    "paper-reference/pi",
    "paper-reference/claude-code",
)
_EXPECTED_RUNTIME_BY_PROFILE = {
    "current-default/pi": ("pi", "openai-codex", "gpt-5.6-luna", False),
    "current-default/claude-subscription": (
        "claude-code",
        None,
        None,
        False,
    ),
    "current-default/claude-minimax": (
        "claude-code",
        "minimax",
        "MiniMax-M3",
        False,
    ),
    "paper-reference/pi": ("pi", "openai-codex", "gpt-5.4-nano", False),
    "paper-reference/claude-code": (
        "claude-code",
        "anthropic",
        "claude-sonnet-4.6",
        False,
    ),
}
_EXPECTED_POLICY_BY_PROFILE = {
    "current-default/pi": (
        "default",
        "level4",
        "dci.paper-answer-judge/deepseek-v4-flash/v1",
    ),
    "current-default/claude-subscription": (
        "default",
        "level4",
        "dci.paper-answer-judge/deepseek-v4-flash/v1",
    ),
    "current-default/claude-minimax": (
        "high",
        "level4",
        "dci.paper-answer-judge/deepseek-v4-flash/v1",
    ),
    "paper-reference/pi": (
        "high",
        "level3",
        "dci.paper-answer-judge/gpt-4.1/v1",
    ),
    "paper-reference/claude-code": (
        "medium",
        "level3",
        "dci.paper-answer-judge/gpt-4.1/v1",
    ),
}


class PaperExperimentProfileTests(unittest.TestCase):
    def test_expected_profiles_are_immutable_and_complete(self) -> None:
        ids = experiment_profile_ids()
        self.assertEqual(ids, _EXPECTED_PROFILE_IDS)
        for profile_id in _EXPECTED_PROFILE_IDS:
            profile = resolve_experiment_profile(profile_id)
            runtime_id, provider, model, model_from_invocation = (
                _EXPECTED_RUNTIME_BY_PROFILE[profile_id]
            )
            self.assertEqual(profile.profile_id, profile_id)
            self.assertEqual(profile.runtime_id, runtime_id)
            self.assertEqual(profile.runtime_provider, provider)
            self.assertEqual(profile.runtime_model, model)
            self.assertEqual(profile.runtime_model_from_invocation, model_from_invocation)
            self.assertIn(
                profile.runtime_authentication_mode,
                {"provider", "subscription", "minimax-coding-plan", "native"},
            )
            reasoning, context_level, judge_contract = _EXPECTED_POLICY_BY_PROFILE[
                profile_id
            ]
            self.assertEqual(profile.reasoning, reasoning)
            self.assertEqual(profile.runtime_context_level, context_level)
            self.assertEqual(profile.judge_contract, judge_contract)
            self.assertEqual(profile.max_turns, 300)
            self.assertEqual(profile.judge_api, "chat-completions")
            self.assertIsInstance(profile.executable_if_authorized, bool)
            self.assertTrue(profile.executable_if_authorized)
            self.assertEqual(len(profile.paper_scope_ids), 16)
            self.assertEqual(len(profile.paper_scope_dataset_ids), 13)
            self.assertGreater(profile.identity_sha256, "")
            self.assertRegex(profile.identity_sha256, r"^[0-9a-f]{64}$")
            self.assertEqual(profile.profile_id, profile_id)
            self.assertEqual(profile.identity_sha256, experiment_profile_sha256(profile_id))

    def test_profile_identity_binds_af320_dataset_scope_and_selection_contracts(self) -> None:
        for profile_id in _EXPECTED_PROFILE_IDS:
            with self.subTest(profile_id=profile_id):
                mapping = resolve_experiment_profile(profile_id).to_mapping()
                self.assertEqual(
                    mapping["paper_benchmark_inventory_sha256"],
                    paper_benchmark_inventory_sha256(),
                )
                self.assertEqual(
                    mapping["paper_experiment_scopes_sha256"],
                    paper_experiment_scopes_sha256(),
                )
                contracts = mapping["scope_contracts"]
                self.assertEqual(len(contracts), 16)
                self.assertTrue(
                    any(
                        item["selection_seed_status"] == "paper-unreported"
                        for item in contracts
                    )
                )
                for item in contracts:
                    scope = resolve_paper_experiment_scope(item["scope_id"])
                    dataset = resolve_paper_benchmark(scope.dataset_id)
                    self.assertEqual(item["scope_identity_sha256"], scope.identity_sha256)
                    self.assertEqual(item["selected_ids_sha256"], scope.selected_ids_sha256)
                    self.assertEqual(item["dataset_identity_sha256"], dataset.identity_sha256)
                    self.assertEqual(item["corpus_path"], dataset.corpus_path)
                    self.assertEqual(item["metric"], dataset.metric)
                    self.assertEqual(item["aggregation"], "mean-over-selected-queries/v1")

    def test_profile_schema_and_payload_are_package_resources(self) -> None:
        root = resources.files("asterion.dci.resources")
        schema = json.loads(root.joinpath("experiment-profile.schema.json").read_text())
        payload = json.loads(root.joinpath("experiment-profiles.json").read_text())
        self.assertEqual(schema["$id"], "dci.experiment-profile/v1")
        self.assertEqual(payload["schema"], schema["$id"])
        self.assertEqual(
            tuple(item["profile_id"] for item in payload["profiles"]),
            _EXPECTED_PROFILE_IDS,
        )

    def test_profile_loader_rejects_schema_drift(self) -> None:
        import asterion.dci.experiment_profiles as module

        root = resources.files("asterion.dci.resources")
        schema = json.loads(root.joinpath("experiment-profile.schema.json").read_text())
        payload = json.loads(root.joinpath("experiment-profiles.json").read_text())
        mutated = copy.deepcopy(schema)
        mutated["$defs"]["profile"]["properties"].pop("runtime_context_level")

        def load_resource(name: str) -> dict[str, object]:
            if name == "experiment-profile.schema.json":
                return mutated
            if name == "experiment-profiles.json":
                return payload
            raise AssertionError(name)

        module._profiles.cache_clear()
        try:
            with mock.patch.object(module, "_load_json_resource", load_resource):
                with self.assertRaisesRegex(RuntimeError, "contract is invalid"):
                    module.experiment_profile_ids()
        finally:
            module._profiles.cache_clear()

    def test_profile_identity_is_canonical_sha256(self) -> None:
        from asterion.dci.experiment_profiles import canonical_sha256

        first = experiment_profile_sha256("current-default/pi")
        second = experiment_profile_sha256("current-default/pi")
        self.assertEqual(first, second)
        profile = resolve_experiment_profile("current-default/pi")
        self.assertEqual(first, canonical_sha256(profile.to_mapping()))

    def test_authorize_full_execution_rejects_insecure_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            with self.assertRaisesRegex(
                ValueError, "estimated_budget_usd is invalid"
            ):
                authorize_full_execution(
                    "current-default/pi", root / "full", -1.0, True
                )
            with self.assertRaisesRegex(
                ValueError, "estimated_budget_usd is invalid"
            ):
                authorize_full_execution(
                    "current-default/pi", root / "full", float("nan"), True
                )
            with self.assertRaisesRegex(ValueError, "invalid"):  # unknown profile
                authorize_full_execution(
                    "missing/profile", root / "full", 0.0, True
                )
            with self.assertRaisesRegex(ValueError, "not authorized"):
                authorize_full_execution(
                    "current-default/pi", root / "full", 0.0, False
                )
            with self.assertRaisesRegex(
                ValueError, "estimated_budget_usd is invalid"
            ):
                authorize_full_execution(
                    "current-default/pi", root / "full", float("inf"), True
                )

    def test_authorize_full_execution_restricts_to_fresh_private_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            output = root / "run"
            output.mkdir()
            with self.assertRaisesRegex(ValueError, "invalid"):
                authorize_full_execution(
                    "current-default/pi", output, 0.0, True
                )
            link = root / "link"
            link.symlink_to(root)
            with self.assertRaisesRegex(ValueError, "invalid"):
                authorize_full_execution(
                    "current-default/pi", root / "link" / "run", 0.0, True
                )
            fresh = root / "new-run"
            auth = authorize_full_execution(
                "current-default/pi", fresh, 0.0, True
            )
            self.assertIsInstance(auth, FullExecutionAuthorization)
            self.assertTrue(fresh.is_dir())
            self.assertEqual(auth.profile_id, "current-default/pi")
            self.assertEqual(auth.estimated_budget_usd, 0.0)
            self.assertTrue(auth.invocation_authorized)
            self.assertEqual(stat.S_IMODE(fresh.stat().st_mode), 0o700)
            authorization_file = fresh / "paper-full-authorization.json"
            self.assertEqual(stat.S_IMODE(authorization_file.stat().st_mode), 0o600)

            require_af320_executable_scope(
                "beir.arguana.main.random50", authorization=auth
            )
            with self.assertRaisesRegex(ValueError, "authorization"):
                require_af320_executable_scope(
                    "beir.arguana.main.random50",
                    authorization=replace(auth, profile_id="paper-reference/pi"),
                )
            with self.assertRaisesRegex(ValueError, "authorization"):
                require_af320_executable_scope(
                    "beir.arguana.main.random50",
                    authorization=type(
                        "ForgedAuthorization",
                        (),
                        {"invocation_authorized": True},
                    )(),
                )

    def test_paper_reproduce_plan_is_body_free_and_never_env_authorized(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            output = Path(temporary_directory) / "not-created"
            stdout = io.StringIO()
            stderr = io.StringIO()
            with mock.patch.dict(os.environ, {"DCI_AUTHORIZE_FULL": "1"}):
                status_code = paper_reproduce_main(
                    [
                        "--profile",
                        "current-default/pi",
                        "--output-root",
                        str(output),
                        "--estimated-budget-usd",
                        "12.5",
                        "--dry-run",
                    ],
                    stdout=stdout,
                    stderr=stderr,
                )
            self.assertEqual(status_code, 0)
            self.assertEqual(stderr.getvalue(), "")
            self.assertFalse(output.exists())
            self.assertNotIn(str(output), stdout.getvalue())
            self.assertIn("reproduction_authorized=no", stdout.getvalue())
            self.assertIn("operation_count=0", stdout.getvalue())

    def test_paper_reproduce_rejects_nonfinite_budget_before_output_creation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            output = Path(temporary_directory) / "not-created"
            stdout = io.StringIO()
            stderr = io.StringIO()
            status_code = paper_reproduce_main(
                [
                    "--profile",
                    "current-default/pi",
                    "--output-root",
                    str(output),
                    "--estimated-budget-usd",
                    "inf",
                    "--dry-run",
                ],
                stdout=stdout,
                stderr=stderr,
            )
            self.assertEqual(status_code, 2)
            self.assertFalse(output.exists())
            self.assertEqual(stdout.getvalue(), "")
            self.assertEqual(stderr.getvalue(), "DCI paper reproduction plan failed\n")

    def test_authorized_dry_run_creates_only_private_authorization_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            output = Path(temporary_directory).resolve() / "authorized"
            stdout = io.StringIO()
            stderr = io.StringIO()
            status_code = paper_reproduce_main(
                [
                    "--profile",
                    "current-default/pi",
                    "--output-root",
                    str(output),
                    "--estimated-budget-usd",
                    "12.5",
                    "--authorize-full",
                    "--dry-run",
                ],
                stdout=stdout,
                stderr=stderr,
            )
            self.assertEqual(status_code, 0)
            self.assertEqual(stderr.getvalue(), "")
            self.assertNotIn(str(output), stdout.getvalue())
            self.assertIn("reproduction_authorized=yes", stdout.getvalue())
            self.assertIn("operation_count=0", stdout.getvalue())
            self.assertEqual(
                {path.name for path in output.iterdir()},
                {"paper-full-authorization.json"},
            )
