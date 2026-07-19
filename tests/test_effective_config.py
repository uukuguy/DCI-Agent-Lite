from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from dci.effective_config import (
    DCI_EFFECTIVE_CONFIG_SCHEMA,
    ConfigLayers,
    TOP_LEVEL_KEYS,
    _canonical_json_bytes,
    resolve_original_runtime,
)


class EffectiveConfigLayerTests(unittest.TestCase):
    def test_original_runtime_precedence_and_sources(self) -> None:
        layers = ConfigLayers(
            process={"DCI_PROVIDER": "environment-provider"},
            dotenv={
                "DCI_PROVIDER": "dotenv-provider",
                "DCI_MODEL": "dotenv-model",
                "DCI_RPC_TIMEOUT_SECONDS": "12",
            },
        )
        resolved = resolve_original_runtime(
            {"provider": "invocation-provider", "model": None, "max_turns": None},
            layers,
        )
        self.assertEqual(resolved.runtime, "pi")
        self.assertEqual(resolved.provider, "invocation-provider")
        self.assertEqual(resolved.model, "dotenv-model")
        self.assertEqual(resolved.sources["agent.provider"], "invocation")
        self.assertEqual(resolved.sources["agent.model"], "environment")
        self.assertEqual(resolved.sources["agent.max_turns"], "runtime-default")
        self.assertEqual(resolved.timeout_seconds, 12.0)
        self.assertEqual(resolved.sources["agent.timeout_seconds"], "environment")

    def test_original_runtime_rejects_claude_code(self) -> None:
        layers = ConfigLayers(process={"DCI_RUNTIME": "pi"}, dotenv={})
        with self.assertRaisesRegex(
            ValueError,
            "Original DCI runtime is unsupported",
        ):
            resolve_original_runtime({"runtime": "claude-code"}, layers)

    def test_from_repo_prefers_process_environment(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            env_file = root / ".env"
            env_file.write_text(
                "DCI_PROVIDER=dotenv-provider\n"
                "DCI_MODEL=dotenv-model\n"
                "DCI_RPC_TIMEOUT_SECONDS=30\n",
                encoding="utf-8",
            )

            process = {
                "DCI_PROVIDER": "process-provider",
                "DCI_RPC_TIMEOUT_SECONDS": "20",
            }
            layers = ConfigLayers.from_repo(root, process_environment=process)
            resolved = resolve_original_runtime(
                {"provider": None, "model": None, "max_turns": None},
                layers,
            )
            self.assertEqual(resolved.provider, "process-provider")
            self.assertEqual(resolved.model, "dotenv-model")
            self.assertEqual(resolved.timeout_seconds, 20.0)

            public_config = resolved.to_public_dict()
            self.assertEqual(
                set(public_config.keys()),
                set(TOP_LEVEL_KEYS),
            )
            self.assertEqual(public_config["product"], "original-dci")
            self.assertEqual(public_config["schema"], DCI_EFFECTIVE_CONFIG_SCHEMA)
            self.assertRegex(public_config["identity_sha256"], r"^[0-9a-f]{64}$")
            expected_fields = {
                "schema",
                "product",
                "runtime",
                "agent",
                "context",
                "judge",
                "experiment",
                "sources",
            }
            payload_without_identity = {
                key: public_config[key]
                for key in expected_fields
            }
            expected_hash = hashlib.sha256(
                _canonical_json_bytes(payload_without_identity)
            ).hexdigest()
            self.assertEqual(public_config["identity_sha256"], expected_hash)
            with self.assertRaisesRegex(ValueError, "private key-like field"):
                resolved.to_public_dict(experiment={"api_key": "nope"})
            with self.assertRaisesRegex(ValueError, "absolute private path"):
                resolved.to_public_dict(experiment={"input_path": "/tmp/sneak"})


if __name__ == "__main__":
    unittest.main()
