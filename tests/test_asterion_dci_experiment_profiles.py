from __future__ import annotations

import io
import json
import math
import os
import stat
import tempfile
import unittest
from dataclasses import FrozenInstanceError
from importlib import resources
from pathlib import Path
from unittest import mock

from asterion.dci.cli import main
from asterion.dci.paper_benchmarks import (
    paper_benchmark_inventory_sha256,
    paper_experiment_scope_ids,
    paper_experiment_scopes_sha256,
    resolve_paper_experiment_scope,
)


EXPECTED_PROFILE_IDS = (
    "current-default/pi",
    "current-default/claude-subscription",
    "current-default/claude-minimax",
    "paper-reference/pi",
    "paper-reference/claude-code",
)


class ExperimentProfileTests(unittest.TestCase):
    def test_exact_profiles_bind_runtime_judge_and_paper_values(self) -> None:
        from asterion.dci.experiment_profiles import (
            experiment_profile_ids,
            resolve_experiment_profile,
        )

        self.assertEqual(experiment_profile_ids(), EXPECTED_PROFILE_IDS)
        pi = resolve_experiment_profile("current-default/pi")
        self.assertEqual((pi.runtime, pi.provider, pi.model), ("pi", "openai-codex", "gpt-5.6-luna"))
        self.assertEqual(pi.authentication_mode, "saved-auth-or-provider-key")
        self.assertEqual(pi.judge["model"], "deepseek-v4-flash")
        self.assertEqual(pi.judge["api"], "chat-completions")
        self.assertEqual(pi.judge["base_url"], "https://api.deepseek.com/v1")

        subscription = resolve_experiment_profile("current-default/claude-subscription")
        self.assertEqual(subscription.runtime, "claude-code")
        self.assertIsNone(subscription.provider)
        self.assertIsNone(subscription.model)
        self.assertEqual(subscription.authentication_mode, "local-subscription")

        paper_pi = resolve_experiment_profile("paper-reference/pi")
        paper_claude = resolve_experiment_profile("paper-reference/claude-code")
        self.assertEqual((paper_pi.provider, paper_pi.model, paper_pi.reasoning), ("openai", "gpt-5.4-nano", "high"))
        self.assertEqual((paper_claude.provider, paper_claude.model, paper_claude.reasoning), (None, "claude-sonnet-4-6", "medium"))
        for profile in (paper_pi, paper_claude):
            self.assertEqual(profile.max_turns, 300)
            self.assertEqual(profile.context_profile, "level3")
            self.assertEqual(profile.judge["model"], "gpt-4.1")

    def test_profiles_bind_exact_af320_inventory_scopes_and_selection_provenance(self) -> None:
        from asterion.dci.experiment_profiles import resolve_experiment_profile

        expected_scope_ids = paper_experiment_scope_ids()
        expected_selection_digests = tuple(
            resolve_paper_experiment_scope(scope_id).selected_ids_sha256
            for scope_id in expected_scope_ids
        )
        for profile_id in EXPECTED_PROFILE_IDS:
            kwargs = {}
            if profile_id == "current-default/claude-minimax":
                kwargs = {"invocation_provider": "minimax", "invocation_model": "MiniMax-M3"}
            profile = resolve_experiment_profile(profile_id, **kwargs)
            self.assertEqual(profile.dataset_inventory_sha256, paper_benchmark_inventory_sha256())
            self.assertEqual(profile.experiment_scopes_sha256, paper_experiment_scopes_sha256())
            self.assertEqual(profile.scope_ids, expected_scope_ids)
            self.assertEqual(profile.selected_ids_sha256, expected_selection_digests)
            self.assertEqual(
                profile.paper_unreported_scope_ids,
                tuple(
                    scope_id for scope_id in expected_scope_ids
                    if resolve_paper_experiment_scope(scope_id).selection_seed_status == "paper-unreported"
                ),
            )

    def test_minimax_identity_is_invocation_only_and_fail_closed(self) -> None:
        from asterion.dci.experiment_profiles import resolve_experiment_profile

        with mock.patch.dict(os.environ, {"DCI_PROVIDER": "minimax", "DCI_MODEL": "MiniMax-M3"}):
            with self.assertRaisesRegex(ValueError, "MiniMax invocation identity"):
                resolve_experiment_profile("current-default/claude-minimax")
        with self.assertRaisesRegex(ValueError, "MiniMax invocation identity"):
            resolve_experiment_profile(
                "current-default/claude-minimax",
                invocation_provider="minimax",
                invocation_model="",
            )
        profile = resolve_experiment_profile(
            "current-default/claude-minimax",
            invocation_provider="minimax-cn",
            invocation_model="MiniMax-M3",
        )
        self.assertEqual((profile.provider, profile.model), ("minimax-cn", "MiniMax-M3"))

    def test_profiles_are_frozen_canonical_and_packaged(self) -> None:
        from asterion.dci.experiment_profiles import (
            experiment_profile_sha256,
            resolve_experiment_profile,
        )

        profile = resolve_experiment_profile("current-default/pi")
        with self.assertRaises(FrozenInstanceError):
            profile.runtime = "claude-code"  # type: ignore[misc]
        digests = []
        for profile_id in EXPECTED_PROFILE_IDS:
            kwargs = {}
            if profile_id == "current-default/claude-minimax":
                kwargs = {
                    "invocation_provider": "minimax",
                    "invocation_model": "MiniMax-M3",
                }
            first = experiment_profile_sha256(profile_id, **kwargs)
            second = experiment_profile_sha256(profile_id, **kwargs)
            self.assertEqual(first, second)
            self.assertRegex(first, r"^[0-9a-f]{64}$")
            digests.append(first)
        self.assertEqual(len(set(digests)), 5)
        package = resources.files("asterion.dci.resources")
        payload = json.loads(package.joinpath("experiment-profiles.json").read_text())
        schema = json.loads(package.joinpath("experiment-profile.schema.json").read_text())
        self.assertEqual(tuple(item["profile_id"] for item in payload["profiles"]), EXPECTED_PROFILE_IDS)
        self.assertFalse(schema["additionalProperties"])


class FullExecutionAuthorizationTests(unittest.TestCase):
    def test_authorization_requires_explicit_boolean_finite_budget_and_fresh_private_root(self) -> None:
        from asterion.dci.experiment_profiles import authorize_full_execution

        with tempfile.TemporaryDirectory() as temporary_directory:
            base = Path(temporary_directory)
            cases = (
                (False, 1.0, base / "not-authorized"),
                (True, -1.0, base / "negative"),
                (True, math.inf, base / "infinite"),
                (True, math.nan, base / "nan"),
            )
            with mock.patch.dict(os.environ, {"DCI_AUTHORIZE_FULL": "1", "AUTHORIZE_FULL": "true"}):
                for invocation_authorized, budget, output in cases:
                    with self.subTest(budget=budget, invocation_authorized=invocation_authorized):
                        with self.assertRaises(ValueError):
                            authorize_full_execution("current-default/pi", output, budget, invocation_authorized)

            nonempty = base / "nonempty"
            nonempty.mkdir()
            (nonempty / "cached.json").write_text("{}")
            with self.assertRaisesRegex(ValueError, "fresh"):
                authorize_full_execution("current-default/pi", nonempty, 1.0, True)
            reused_empty = base / "reused-empty"
            reused_empty.mkdir(mode=0o700)
            with self.assertRaisesRegex(ValueError, "fresh"):
                authorize_full_execution("current-default/pi", reused_empty, 1.0, True)
            target = base / "target"
            target.mkdir()
            symlink = base / "symlink"
            symlink.symlink_to(target, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "symlink"):
                authorize_full_execution("current-default/pi", symlink, 1.0, True)

            output = base / "authorized"
            authorization = authorize_full_execution("current-default/pi", output, 0.0, True)
            self.assertTrue(authorization.invocation_authorized)
            self.assertEqual(stat.S_IMODE(output.stat().st_mode), 0o700)
            with self.assertRaises(FrozenInstanceError):
                authorization.estimated_budget_usd = 2.0  # type: ignore[misc]

            from asterion.dci.paper_benchmarks import require_af320_executable_scope
            self.assertIsNone(
                require_af320_executable_scope(
                    "browsecomp-plus.main.all830", authorization
                )
            )

    def test_authorization_rejects_unknown_profile_scope_mismatch_and_cache_only(self) -> None:
        from asterion.dci.experiment_profiles import authorize_full_execution

        with tempfile.TemporaryDirectory() as temporary_directory:
            base = Path(temporary_directory)
            with self.assertRaisesRegex(ValueError, "profile"):
                authorize_full_execution("unknown", base / "unknown", 1.0, True)
            with self.assertRaisesRegex(ValueError, "preflight"):
                authorize_full_execution(
                    "current-default/pi",
                    base / "mismatch",
                    1.0,
                    True,
                    preflight_scope_ids=("wrong",),
                )
            with self.assertRaisesRegex(ValueError, "preflight"):
                authorize_full_execution(
                    "current-default/pi",
                    base / "selection-mismatch",
                    1.0,
                    True,
                    preflight_selected_ids_sha256=("0" * 64,),
                )
            with self.assertRaisesRegex(ValueError, "cache"):
                authorize_full_execution(
                    "current-default/pi", base / "cache", 1.0, True, cache_only=True
                )

    def test_cli_dry_run_is_zero_operation_and_missing_flag_never_authorizes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory, mock.patch(
            "asterion.dci.verification._paper_default_operation_runner"
        ) as runner, mock.patch.dict(os.environ, {"DCI_AUTHORIZE_FULL": "1"}):
            base = Path(temporary_directory)
            stdout = io.StringIO()
            stderr = io.StringIO()
            result = main(
                [
                    "paper", "reproduce", "--profile", "current-default/pi",
                    "--output-root", str(base / "plan-only"),
                    "--estimated-budget-usd", "12.5", "--dry-run",
                ],
                stdout=stdout,
                stderr=stderr,
            )
            self.assertEqual(result, 0, stderr.getvalue())
            self.assertIn("Profile: current-default/pi", stdout.getvalue())
            self.assertIn("Agent operations performed: 0", stdout.getvalue())
            self.assertIn("Judge operations performed: 0", stdout.getvalue())
            self.assertIn("Full dataset authorized: no", stdout.getvalue())
            self.assertFalse((base / "plan-only").exists())
            runner.assert_not_called()

            self.assertEqual(
                main(
                    [
                        "paper", "reproduce", "--profile", "current-default/pi",
                        "--output-root", str(base / "missing-budget"), "--dry-run",
                    ],
                    stdout=io.StringIO(),
                    stderr=io.StringIO(),
                ),
                2,
            )

            for invalid_budget in ("-1", "nan", "inf"):
                with self.subTest(invalid_budget=invalid_budget):
                    self.assertEqual(
                        main(
                            [
                                "paper", "reproduce", "--profile", "current-default/pi",
                                "--output-root", str(base / f"invalid-{invalid_budget}"),
                                "--estimated-budget-usd", invalid_budget,
                                "--authorize-full", "--dry-run",
                            ],
                            stdout=io.StringIO(),
                            stderr=io.StringIO(),
                        ),
                        2,
                    )

            stdout = io.StringIO()
            result = main(
                [
                    "paper", "reproduce", "--profile", "current-default/pi",
                    "--output-root", str(base / "authorized-plan"),
                    "--estimated-budget-usd", "12.5", "--authorize-full", "--dry-run",
                ],
                stdout=stdout,
                stderr=io.StringIO(),
            )
            self.assertEqual(result, 0)
            self.assertIn("Full dataset authorized: yes", stdout.getvalue())
            self.assertFalse((base / "authorized-plan").exists())
            runner.assert_not_called()


if __name__ == "__main__":
    unittest.main()
