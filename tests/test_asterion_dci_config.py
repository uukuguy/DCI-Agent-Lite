from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests import SOURCE_ROOT as _SOURCE_ROOT  # noqa: F401

from asterion.dci.config import (
    ConfigLayers,
    load_asterion_dci_env,
    resolve_asterion_runtime,
    resolve_dci_paths,
    resolve_dci_runtime_options,
)
from asterion.dci.effective_config import AsterionEffectiveConfig
from dci.config import ConfigLayers as OriginalConfigLayers
from dci.config import resolve_original_runtime
from dci.effective_config import OriginalEffectiveConfig


class AsterionDciConfigTests(unittest.TestCase):
    def test_effective_judge_allows_only_valid_body_free_identity_digests(self) -> None:
        runtime = resolve_asterion_runtime({}, ConfigLayers({}, {}))
        judge = {
            "judge_api_key_env": "DEEPSEEK_API_KEY",
            "request_shape_sha256": "a" * 64,
            "prompt_contract_sha256": "b" * 64,
        }

        projected = AsterionEffectiveConfig(runtime=runtime, judge=judge).to_public_dict()

        self.assertEqual(projected["judge"], judge)
        for field in ("request_shape_sha256", "prompt_contract_sha256"):
            for malformed in ("A" * 64, "a" * 63, "not-a-digest"):
                with self.subTest(field=field, malformed=malformed):
                    with self.assertRaisesRegex(ValueError, "unsafe"):
                        AsterionEffectiveConfig(
                            runtime=runtime,
                            judge={field: malformed},
                        ).to_public_dict()
        with self.assertRaisesRegex(ValueError, "unsafe"):
            AsterionEffectiveConfig(
                runtime=runtime,
                judge={"judge_api_key_env": "unsafe env name"},
            ).to_public_dict()
        with self.assertRaisesRegex(ValueError, "unsafe"):
            AsterionEffectiveConfig(
                runtime=runtime,
                judge={"prompt_contract": "private prompt body"},
            ).to_public_dict()

    def test_runtime_resolution_is_runtime_first_and_layered(self) -> None:
        layers = ConfigLayers(
            process={
                "DCI_RUNTIME": "claude-code",
                "DCI_PROVIDER": "minimax",
                "DCI_MODEL": "process-model",
            },
            dotenv={
                "DCI_RUNTIME": "pi",
                "DCI_PROVIDER": "dotenv-provider",
                "DCI_MODEL": "dotenv-model",
            },
        )

        resolved = resolve_asterion_runtime(
            {"runtime": "pi", "model": "invocation-model"}, layers
        )

        self.assertEqual(resolved.runtime, "pi")
        self.assertEqual(resolved.provider, "minimax")
        self.assertEqual(resolved.model, "invocation-model")
        self.assertEqual(resolved.sources["runtime"], "invocation")
        self.assertEqual(resolved.sources["agent.provider"], "environment")
        self.assertEqual(resolved.sources["agent.model"], "invocation")

    def test_pi_defaults_and_claude_subscription_are_runtime_relative(self) -> None:
        pi = resolve_asterion_runtime({}, ConfigLayers({}, {}))
        claude = resolve_asterion_runtime(
            {}, ConfigLayers({"DCI_RUNTIME": "claude-code"}, {})
        )

        self.assertEqual(
            (pi.runtime, pi.provider, pi.model, pi.authentication_mode),
            ("pi", "openai-codex", "gpt-5.6-luna", "saved-auth"),
        )
        self.assertEqual(
            (claude.runtime, claude.provider, claude.model, claude.authentication_mode),
            ("claude-code", None, None, "subscription"),
        )

    def test_exact_installed_runtime_ids_remain_compatible(self) -> None:
        for exact, public in (
            ("pi.reference", "pi"),
            ("claude-code.reference", "claude-code"),
        ):
            with self.subTest(exact=exact):
                resolved = resolve_asterion_runtime(
                    {"runtime": exact}, ConfigLayers({}, {})
                )
                self.assertEqual(resolved.runtime, public)

    def test_empty_optional_timeout_is_preserved_as_omitted(self) -> None:
        resolved = resolve_asterion_runtime(
            {}, ConfigLayers({"DCI_RPC_TIMEOUT_SECONDS": ""}, {})
        )

        self.assertIsNone(resolved.timeout_seconds)
        self.assertEqual(resolved.sources["agent.timeout_seconds"], "environment")

    def test_empty_optional_invocation_overrides_populated_lower_layers(self) -> None:
        resolved = resolve_asterion_runtime(
            {
                "timeout_seconds": "",
                "thinking_level": "",
                "context_profile": "",
            },
            ConfigLayers(
                process={
                    "DCI_RPC_TIMEOUT_SECONDS": "30",
                    "DCI_PI_THINKING_LEVEL": "high",
                    "DCI_RUNTIME_CONTEXT_LEVEL": "level4",
                },
                dotenv={
                    "DCI_RPC_TIMEOUT_SECONDS": "60",
                    "DCI_PI_THINKING_LEVEL": "medium",
                    "DCI_RUNTIME_CONTEXT_LEVEL": "level3",
                },
            ),
        )

        self.assertIsNone(resolved.timeout_seconds)
        self.assertIsNone(resolved.thinking_level)
        self.assertIsNone(resolved.context_profile)
        self.assertEqual(resolved.sources["agent.timeout_seconds"], "invocation")
        self.assertEqual(resolved.sources["agent.thinking_level"], "invocation")
        self.assertEqual(resolved.sources["context.profile"], "invocation")

    def test_whitespace_optional_invocation_is_also_authoritative_omission(self) -> None:
        resolved = resolve_asterion_runtime(
            {
                "timeout_seconds": "  ",
                "thinking_level": "  ",
                "context_profile": "  ",
            },
            ConfigLayers(
                process={
                    "DCI_RPC_TIMEOUT_SECONDS": "30",
                    "DCI_PI_THINKING_LEVEL": "high",
                    "DCI_RUNTIME_CONTEXT_LEVEL": "level4",
                },
                dotenv={},
            ),
        )

        self.assertIsNone(resolved.timeout_seconds)
        self.assertIsNone(resolved.thinking_level)
        self.assertIsNone(resolved.context_profile)

    def test_safe_pi_projection_matches_original_except_product_and_identity(self) -> None:
        invocation = {
            "runtime": "pi",
            "provider": "provider",
            "model": "model",
            "tools": "read,bash",
            "max_turns": 7,
            "timeout_seconds": 12,
            "thinking_level": "high",
            "context_profile": "level3",
        }
        original = OriginalEffectiveConfig(
            resolve_original_runtime(invocation, OriginalConfigLayers({}, {}))
        ).to_public_dict()
        asterion = AsterionEffectiveConfig(
            resolve_asterion_runtime(invocation, ConfigLayers({}, {}))
        ).to_public_dict()

        for projection in (original, asterion):
            projection.pop("product")
            projection.pop("identity_sha256")
        self.assertEqual(asterion, original)

    def test_shared_paths_win_over_compatibility_aliases(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            environment = {
                "DCI_PI_DIR": "shared/pi",
                "DCI_PI_PACKAGE_DIR": "shared/coding-agent",
                "DCI_PI_AGENT_DIR": "shared/pi-agent",
                "ASTERION_DCI_PI_DIR": "vendor/pi",
                "ASTERION_DCI_PI_PACKAGE_DIR": "build/coding-agent",
                "ASTERION_DCI_PI_AGENT_DIR": "state/pi-agent",
                "ASTERION_DCI_OUTPUT_ROOT": "asterion-runs",
            }
            with patch.dict(os.environ, environment, clear=True):
                paths = resolve_dci_paths(root)

        self.assertEqual(paths.pi.repo_dir, root / "shared/pi")
        self.assertEqual(paths.pi.package_dir, root / "shared/coding-agent")
        self.assertEqual(paths.pi.agent_dir, root / "shared/pi-agent")
        self.assertEqual(paths.output_root, root / "asterion-runs")

    def test_compatibility_path_aliases_are_fallbacks(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            with patch.dict(
                os.environ,
                {"ASTERION_DCI_PI_DIR": "compat/pi"},
                clear=True,
            ):
                paths = resolve_dci_paths(root)

        self.assertEqual(paths.pi.repo_dir, root / "compat/pi")

    def test_runtime_options_merge_shared_env_and_explicit_values(self) -> None:
        with patch.dict(
            os.environ,
            {
                "DCI_PROVIDER": "openai",
                "DCI_MODEL": "gpt-test",
                "DCI_RPC_TIMEOUT_SECONDS": "45",
            },
            clear=True,
        ):
            options = resolve_dci_runtime_options({"model": "explicit-model"})

        self.assertEqual(
            (options.provider, options.model, options.timeout_seconds),
            ("openai", "explicit-model", 45.0),
        )

    def test_runtime_options_default_to_pi_openai_codex_and_default_model(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            options = resolve_dci_runtime_options()

        self.assertEqual(
            (options.runtime, options.provider, options.model),
            ("pi", "openai-codex", "gpt-5.6-luna"),
        )

    def test_runtime_aliases_normalize_to_runtime_contract(self) -> None:
        with patch.dict(
            os.environ,
            {
                "DCI_RUNTIME": "pi.reference",
                "DCI_PROVIDER": "openai",
                "DCI_MODEL": "gpt-test",
            },
            clear=True,
        ):
            options = resolve_dci_runtime_options()
        self.assertEqual(options.runtime, "pi")
        self.assertEqual((options.provider, options.model), ("openai", "gpt-test"))

        with patch.dict(
            os.environ,
            {
                "DCI_RUNTIME": "claude-code.reference",
                "DCI_PROVIDER": "minimax",
                "DCI_MODEL": "MiniMax-M2.7",
            },
            clear=True,
        ):
            options = resolve_dci_runtime_options()

        self.assertEqual(options.runtime, "claude-code")
        self.assertEqual((options.provider, options.model), ("minimax", "MiniMax-M2.7"))

    def test_runtime_options_reject_invalid_timeout_and_heap(self) -> None:
        with patch.dict(os.environ, {"DCI_RPC_TIMEOUT_SECONDS": "not-a-number"}, clear=True):
            with self.assertRaises(ValueError):
                resolve_dci_runtime_options()
        with patch.dict(
            os.environ,
            {"DCI_NODE_MAX_OLD_SPACE_SIZE_MB": "0"},
            clear=True,
        ):
            with self.assertRaises(ValueError):
                resolve_dci_runtime_options()

    def test_runtime_options_reject_nonfinite_timeout(self) -> None:
        for value in ("nan", "inf", "-inf"):
            with self.subTest(value=value):
                with patch.dict(
                    os.environ,
                    {"DCI_RPC_TIMEOUT_SECONDS": value},
                    clear=True,
                ):
                    with self.assertRaises(ValueError):
                        resolve_dci_runtime_options()

    def test_runtime_options_reject_unknown_context_profile(self) -> None:
        for value in ("level5", "legacy", " level3"):
            with self.subTest(value=value):
                with patch.dict(
                    os.environ,
                    {"DCI_RUNTIME_CONTEXT_LEVEL": value},
                    clear=True,
                ):
                    with self.assertRaisesRegex(ValueError, "context profile"):
                        resolve_dci_runtime_options()

    def test_defaults_never_select_legacy_dci_locations(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            (root / "pi-mono").mkdir()
            with patch.dict(os.environ, {}, clear=True):
                paths = resolve_dci_paths(root)

        self.assertEqual(paths.pi.repo_dir, root / "pi")
        self.assertEqual(paths.pi.package_dir, root / "pi/packages/coding-agent")
        self.assertEqual(paths.pi.agent_dir, root / "pi/.pi/agent")
        self.assertEqual(paths.output_root, root / "outputs/asterion-dci-runs")

    def test_loads_the_new_product_env_without_overriding_process_values(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            env_path = root / ".env"
            env_path.write_text("ASTERION_DCI_OUTPUT_ROOT=from-file\n")
            with patch.dict(
                os.environ,
                {"ASTERION_DCI_OUTPUT_ROOT": "from-process"},
                clear=True,
            ):
                returned = load_asterion_dci_env(root)
                paths = resolve_dci_paths(root)

        self.assertEqual(returned, env_path)
        self.assertEqual(paths.output_root, root / "from-process")

    def test_explicit_env_file_is_supported_and_missing_file_returns_none(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            explicit = root / "operator.env"
            explicit.write_text("DCI_MODEL=from-explicit\n")
            with patch.dict(os.environ, {}, clear=True):
                loaded = load_asterion_dci_env(root, env_file=explicit)
                model = resolve_dci_runtime_options().model
                missing = load_asterion_dci_env(root, env_file=root / "missing.env")

        self.assertEqual(loaded, explicit)
        self.assertEqual(model, "from-explicit")
        self.assertIsNone(missing)


if __name__ == "__main__":
    unittest.main()
