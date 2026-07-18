from __future__ import annotations

import io
import json
import math
import os
import stat
import copy
import gc
import tempfile
import unittest
from dataclasses import FrozenInstanceError, replace
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


def _preflight(profile_id: str = "current-default/pi") -> dict[str, object]:
    from asterion.dci.experiment_profiles import (
        experiment_profile_sha256,
        resolve_experiment_profile,
    )

    profile = resolve_experiment_profile(profile_id)
    return {
        "preflight_profile_sha256": experiment_profile_sha256(profile_id),
        "preflight_dataset_inventory_sha256": profile.dataset_inventory_sha256,
        "preflight_experiment_scopes_sha256": profile.experiment_scopes_sha256,
        "preflight_scope_ids": profile.scope_ids,
        "preflight_selected_ids_sha256": profile.selected_ids_sha256,
    }


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
    def test_registry_strongly_retains_issuer_without_integer_identity_trust(self) -> None:
        import asterion.dci.experiment_profiles as module

        scope = "browsecomp-plus.main.all830"
        with tempfile.TemporaryDirectory() as temporary_directory:
            authorization = module.authorize_full_execution(
                "current-default/pi",
                Path(temporary_directory) / "issued",
                1.0,
                True,
                **_preflight(),
            )
            token = authorization._issuance_token
            record = module._AUTHORIZATION_REGISTRY[token]
            self.assertTrue(hasattr(record, "issuer"))
            self.assertIs(record.issuer, authorization)
            self.assertFalse(hasattr(record.snapshot, "capability_identity"))

            forged = copy.copy(authorization)
            with self.assertRaisesRegex(ValueError, "authorization"):
                module.consume_full_execution_authorization(forged, scope)

            del authorization
            gc.collect()
            self.assertIs(module._AUTHORIZATION_REGISTRY[token].issuer, record.issuer)
            self.assertIsNone(
                module.consume_full_execution_authorization(record.issuer, scope)
            )

    def test_registry_snapshot_is_independent_and_rejects_every_field_tamper(self) -> None:
        import asterion.dci.experiment_profiles as module

        scope = "browsecomp-plus.main.all830"
        with tempfile.TemporaryDirectory() as temporary_directory:
            base = Path(temporary_directory)
            probe = module.authorize_full_execution(
                "current-default/pi", base / "probe", 1.0, True, **_preflight()
            )
            record = module._AUTHORIZATION_REGISTRY[probe._issuance_token]
            self.assertIsNot(record, probe)
            self.assertFalse(hasattr(record, "authorization"))

            replacements = {
                "profile_id": "paper-reference/pi",
                "profile_sha256": "0" * 64,
                "dataset_inventory_sha256": "0" * 64,
                "experiment_scopes_sha256": "0" * 64,
                "authorized_scope_ids": (scope,),
                "selected_ids_sha256": ("0" * 64,),
                "output_root": base / "other",
                "output_root_device": -1,
                "output_root_inode": -1,
                "estimated_budget_usd": 2.0,
                "invocation_authorized": False,
                "_issuance_token": "0" * 64,
            }
            for index, (field, replacement) in enumerate(replacements.items()):
                with self.subTest(field=field):
                    authorization = module.authorize_full_execution(
                        "current-default/pi",
                        base / f"tampered-{index}",
                        1.0,
                        True,
                        **_preflight(),
                    )
                    original = getattr(authorization, field)
                    object.__setattr__(authorization, field, replacement)
                    with self.assertRaisesRegex(ValueError, "authorization"):
                        module.consume_full_execution_authorization(
                            authorization, scope
                        )
                    object.__setattr__(authorization, field, original)
                    self.assertIsNone(
                        module.consume_full_execution_authorization(
                            authorization, scope
                        )
                    )

    def test_authorization_cannot_be_manually_constructed_copied_or_replaced(self) -> None:
        from asterion.dci.experiment_profiles import (
            FullExecutionAuthorization,
            authorize_full_execution,
            consume_full_execution_authorization,
        )

        with self.assertRaises(TypeError):
            FullExecutionAuthorization(  # type: ignore[call-arg]
                "current-default/pi", Path("out"), 1.0, True
            )
        with tempfile.TemporaryDirectory() as temporary_directory:
            authorization = authorize_full_execution(
                "current-default/pi",
                Path(temporary_directory) / "issued",
                1.0,
                True,
                **_preflight(),
            )
            forged = copy.copy(authorization)
            with self.assertRaisesRegex(ValueError, "authorization"):
                consume_full_execution_authorization(
                    forged, "browsecomp-plus.main.all830"
                )
            with self.assertRaises(TypeError):
                replace(authorization, estimated_budget_usd=2.0)

    def test_authorized_scopes_are_consumed_once_and_cross_scope_fails(self) -> None:
        from asterion.dci.experiment_profiles import (
            authorize_full_execution,
            consume_full_execution_authorization,
            resolve_experiment_profile,
        )

        profile = resolve_experiment_profile("current-default/pi")
        scopes = profile.scope_ids[:2]
        digests = profile.selected_ids_sha256[:2]
        preflight = _preflight()
        preflight["preflight_scope_ids"] = scopes
        preflight["preflight_selected_ids_sha256"] = digests
        with tempfile.TemporaryDirectory() as temporary_directory:
            authorization = authorize_full_execution(
                "current-default/pi", Path(temporary_directory) / "issued", 1.0, True,
                **preflight,
            )
            self.assertIsNone(consume_full_execution_authorization(authorization, scopes[0]))
            with self.assertRaisesRegex(ValueError, "replay"):
                consume_full_execution_authorization(authorization, scopes[0])
            self.assertIsNone(consume_full_execution_authorization(authorization, scopes[1]))
            with self.assertRaisesRegex(ValueError, "scope"):
                consume_full_execution_authorization(authorization, profile.scope_ids[2])

    def test_root_identity_symlink_replacement_recreation_and_mode_drift_fail(self) -> None:
        from asterion.dci.experiment_profiles import (
            authorize_full_execution,
            consume_full_execution_authorization,
        )

        scope = "browsecomp-plus.main.all830"
        cases = ("symlink", "recreated", "permissions")
        for case in cases:
            with self.subTest(case=case), tempfile.TemporaryDirectory() as temporary_directory:
                base = Path(temporary_directory)
                root = base / "issued"
                authorization = authorize_full_execution(
                    "current-default/pi", root, 1.0, True, **_preflight()
                )
                if case == "permissions":
                    root.chmod(0o755)
                else:
                    moved = base / "moved"
                    root.rename(moved)
                    if case == "symlink":
                        root.symlink_to(moved, target_is_directory=True)
                    else:
                        root.mkdir(mode=0o700)
                with self.assertRaisesRegex(ValueError, "output root"):
                    consume_full_execution_authorization(authorization, scope)

    def test_execution_lock_revalidates_authorized_root_before_any_write(self) -> None:
        from asterion.dci.benchmark import DciBenchmarkError, _BatchLock
        from asterion.dci.experiment_profiles import authorize_full_execution

        with tempfile.TemporaryDirectory() as temporary_directory:
            base = Path(temporary_directory).resolve()
            root = base / "issued"
            authorization = authorize_full_execution(
                "current-default/pi", root, 1.0, True, **_preflight()
            )
            moved = base / "moved"
            root.rename(moved)
            root.mkdir(mode=0o755)
            with self.assertRaisesRegex(DciBenchmarkError, "identity changed"):
                _BatchLock.acquire(
                    root,
                    expected_identity=(
                        authorization.output_root_device,
                        authorization.output_root_inode,
                    ),
                )
            self.assertEqual(tuple(root.iterdir()), ())
            self.assertEqual(stat.S_IMODE(root.stat().st_mode), 0o755)
            self.assertEqual(tuple(moved.iterdir()), ())

    def test_execution_lock_never_recreates_a_missing_authorized_root(self) -> None:
        from asterion.dci.benchmark import DciBenchmarkError, _BatchLock
        from asterion.dci.experiment_profiles import authorize_full_execution

        with tempfile.TemporaryDirectory() as temporary_directory:
            base = Path(temporary_directory).resolve()
            root = base / "issued"
            authorization = authorize_full_execution(
                "current-default/pi", root, 1.0, True, **_preflight()
            )
            root.rename(base / "moved")
            with self.assertRaises(DciBenchmarkError):
                _BatchLock.acquire(
                    root,
                    expected_identity=(
                        authorization.output_root_device,
                        authorization.output_root_inode,
                    ),
                )
            self.assertFalse(root.exists())

    def test_preflight_bindings_are_mandatory_and_exact(self) -> None:
        from asterion.dci.experiment_profiles import authorize_full_execution

        with tempfile.TemporaryDirectory() as temporary_directory:
            with self.assertRaises(TypeError):
                authorize_full_execution(
                    "current-default/pi", Path(temporary_directory) / "missing", 1.0, True
                )
            for field in (
                "preflight_profile_sha256",
                "preflight_dataset_inventory_sha256",
                "preflight_experiment_scopes_sha256",
                "preflight_selected_ids_sha256",
            ):
                values = _preflight()
                values[field] = ("0" * 64,) if field == "preflight_selected_ids_sha256" else "0" * 64
                with self.subTest(field=field), self.assertRaisesRegex(ValueError, "preflight"):
                    authorize_full_execution(
                        "current-default/pi",
                        Path(temporary_directory) / field,
                        1.0,
                        True,
                        **values,
                    )

    def test_profile_schema_and_safe_nested_identity_are_closed(self) -> None:
        from asterion.dci.experiment_profiles import resolve_experiment_profile

        schema = json.loads(
            resources.files("asterion.dci.resources")
            .joinpath("experiment-profile.schema.json")
            .read_text()
        )
        profile_schema = schema["$defs"]["profile"]
        self.assertFalse(profile_schema["additionalProperties"])
        self.assertFalse(profile_schema["properties"]["judge"]["additionalProperties"])
        comparison = profile_schema["properties"]["comparison"]
        self.assertFalse(comparison["additionalProperties"])
        self.assertIn("oneOf", comparison)

        for profile_id in EXPECTED_PROFILE_IDS:
            kwargs = {}
            if profile_id == "current-default/claude-minimax":
                kwargs = {"invocation_provider": "minimax", "invocation_model": "MiniMax-M3"}
            profile = resolve_experiment_profile(profile_id, **kwargs)
            self.assertEqual(
                set(profile.judge),
                {
                    "base_url", "api", "model", "key_source", "thinking",
                    "json_object", "request_shape_sha256", "output_shape_identity",
                    "prompt_contract", "prompt_contract_sha256", "pricing_identity",
                },
            )
            self.assertRegex(str(profile.judge["prompt_contract_sha256"]), r"^[0-9a-f]{64}$")
            rendered = json.dumps(profile.to_canonical_dict())
            for forbidden in ("api_key", "credential", "prompt_body", "answer", "private_path"):
                self.assertNotIn(f'"{forbidden}"', rendered)
        minimax = resolve_experiment_profile(
            "current-default/claude-minimax",
            invocation_provider="minimax-cn",
            invocation_model="MiniMax-M3",
        )
        self.assertEqual(minimax.compatible_config_key, "MINIMAX_CN_API_KEY")

    def test_schema_and_nested_profile_mutations_fail_loader_validation(self) -> None:
        import asterion.dci.experiment_profiles as module

        package = resources.files("asterion.dci.resources")
        original_schema = json.loads(
            package.joinpath("experiment-profile.schema.json").read_text()
        )
        original_payload = json.loads(
            package.joinpath("experiment-profiles.json").read_text()
        )
        mutations = (
            ("schema-comparison-open", lambda schema, _payload: schema["$defs"]["profile"]["properties"]["comparison"].__setitem__("additionalProperties", True)),
            ("comparison-extra", lambda _schema, payload: payload["profiles"][0]["comparison"].__setitem__("extra", True)),
            ("judge-key-source", lambda _schema, payload: payload["profiles"][0]["judge"].__setitem__("key_source", "OTHER_KEY")),
            ("minimax-key-on-base", lambda _schema, payload: payload["profiles"][2].__setitem__("compatible_config_key", "MINIMAX_API_KEY")),
        )
        for name, mutate in mutations:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary_directory:
                root = Path(temporary_directory)
                schema = copy.deepcopy(original_schema)
                payload = copy.deepcopy(original_payload)
                mutate(schema, payload)
                (root / "experiment-profile.schema.json").write_text(json.dumps(schema))
                (root / "experiment-profiles.json").write_text(json.dumps(payload))
                with mock.patch.object(module.resources, "files", return_value=root):
                    module._profiles.cache_clear()
                    with self.assertRaisesRegex(RuntimeError, "contract is invalid"):
                        module.experiment_profile_ids()
        module._profiles.cache_clear()

    def test_benchmark_prepare_consumes_real_scope_authorization_once(self) -> None:
        from asterion.dci.benchmark import BenchmarkRequest, DciBenchmarkError, _prepare
        from asterion.dci.config import DciRuntimeOptions
        from asterion.dci.experiment_profiles import authorize_full_execution, resolve_experiment_profile
        from asterion.dci.judge import JudgeConfig
        from asterion.dci.paper_benchmarks import published_scope_selected_ids

        scope = "qa.nq.main.random50"
        selected = published_scope_selected_ids(scope)
        profile = resolve_experiment_profile("current-default/pi")
        index = profile.scope_ids.index(scope)
        preflight = _preflight()
        preflight["preflight_scope_ids"] = (scope,)
        preflight["preflight_selected_ids_sha256"] = (profile.selected_ids_sha256[index],)
        with tempfile.TemporaryDirectory() as temporary_directory:
            base = Path(temporary_directory)
            dataset = base / "dataset.jsonl"
            dataset.write_text("\n".join(
                json.dumps({"query_id": query_id, "query": "q", "answer": "a"})
                for query_id in selected
            ) + "\n")
            output = base / "full-output"
            authorization = authorize_full_execution(
                "current-default/pi", output, 1.0, True, **preflight
            )
            request = BenchmarkRequest(
                dataset=dataset, output_root=authorization.output_root, cwd=base,
                judge_config=JudgeConfig(), runtime_options=DciRuntimeOptions(None, None),
                profile="qa.nq", max_turns=300,
                full_execution_authorization=authorization,
            )
            rows, *_rest = _prepare(request)
            self.assertEqual(len(rows), 50)
            with self.assertRaisesRegex(DciBenchmarkError, "replay"):
                _prepare(request)

            limited_output = base / "limited-full-authorization"
            limited_authorization = authorize_full_execution(
                "current-default/pi", limited_output, 1.0, True, **preflight
            )
            with self.assertRaisesRegex(
                DciBenchmarkError, "paper scope does not match its profile"
            ):
                _prepare(
                    replace(
                        request,
                        output_root=limited_authorization.output_root,
                        limit=1,
                        full_execution_authorization=limited_authorization,
                    )
                )
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
                            authorize_full_execution(
                                "current-default/pi", output, budget,
                                invocation_authorized, **_preflight()
                            )

            nonempty = base / "nonempty"
            nonempty.mkdir()
            (nonempty / "cached.json").write_text("{}")
            with self.assertRaisesRegex(ValueError, "fresh"):
                authorize_full_execution(
                    "current-default/pi", nonempty, 1.0, True, **_preflight()
                )
            reused_empty = base / "reused-empty"
            reused_empty.mkdir(mode=0o700)
            with self.assertRaisesRegex(ValueError, "fresh"):
                authorize_full_execution(
                    "current-default/pi", reused_empty, 1.0, True, **_preflight()
                )
            target = base / "target"
            target.mkdir()
            symlink = base / "symlink"
            symlink.symlink_to(target, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "symlink"):
                authorize_full_execution(
                    "current-default/pi", symlink, 1.0, True, **_preflight()
                )

            output = base / "authorized"
            authorization = authorize_full_execution(
                "current-default/pi", output, 0.0, True, **_preflight()
            )
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
                authorize_full_execution(
                    "unknown", base / "unknown", 1.0, True, **_preflight()
                )
            with self.assertRaisesRegex(ValueError, "preflight"):
                authorize_full_execution(
                    "current-default/pi",
                    base / "mismatch",
                    1.0,
                    True,
                    **{
                        **_preflight(),
                        "preflight_scope_ids": ("wrong",),
                        "preflight_selected_ids_sha256": ("0" * 64,),
                    },
                )
            with self.assertRaisesRegex(ValueError, "preflight"):
                authorize_full_execution(
                    "current-default/pi",
                    base / "selection-mismatch",
                    1.0,
                    True,
                    **{
                        **_preflight(),
                        "preflight_selected_ids_sha256": ("0" * 64,),
                    },
                )
            with self.assertRaisesRegex(ValueError, "cache"):
                authorize_full_execution(
                    "current-default/pi", base / "cache", 1.0, True,
                    cache_only=True, **_preflight()
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
            self.assertIn("Full authorization requested: no", stdout.getvalue())
            self.assertIn("Full authorization issued: no", stdout.getvalue())
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
            self.assertIn("Full authorization requested: yes", stdout.getvalue())
            self.assertIn("Full authorization issued: no", stdout.getvalue())
            self.assertNotIn("Full dataset authorized: yes", stdout.getvalue())
            self.assertFalse((base / "authorized-plan").exists())
            runner.assert_not_called()

            issued_stdout = io.StringIO()
            issued_root = base / "issued"
            self.assertEqual(
                main(
                    [
                        "paper", "reproduce", "--profile", "current-default/pi",
                        "--output-root", str(issued_root),
                        "--estimated-budget-usd", "12.5", "--authorize-full",
                    ],
                    stdout=issued_stdout,
                    stderr=io.StringIO(),
                ),
                0,
            )
            self.assertIn("Full authorization issued: yes", issued_stdout.getvalue())
            self.assertNotIn("Full authorization issued: no", issued_stdout.getvalue())
            self.assertTrue(issued_root.is_dir())
            runner.assert_not_called()


if __name__ == "__main__":
    unittest.main()
