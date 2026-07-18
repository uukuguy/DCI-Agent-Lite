from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests import SOURCE_ROOT as _SOURCE_ROOT  # noqa: F401
from dci.config import ConfigLayers, resolve_original_runtime
import dci.effective_config as effective_config_module
from dci.effective_config import OriginalEffectiveConfig


class OriginalEffectiveConfigTests(unittest.TestCase):
    def test_public_projection_has_exact_keys_and_canonical_identity(self) -> None:
        runtime = resolve_original_runtime(
            {"provider": "openai-codex", "model": "gpt-5.6-luna"},
            ConfigLayers({}, {}),
        )
        projected = OriginalEffectiveConfig(
            runtime=runtime,
            context={"profile": "level3", "implementation_sha256": "a" * 64},
            judge={"model": "deepseek-v4-flash", "api": "chat-completions"},
            experiment={"dataset": "bcplus", "selection": "limit-1"},
        ).to_public_dict()

        self.assertEqual(
            set(projected),
            {
                "schema",
                "product",
                "runtime",
                "agent",
                "context",
                "judge",
                "experiment",
                "sources",
                "identity_sha256",
            },
        )
        self.assertEqual(projected["schema"], "dci.effective-config/v1")
        self.assertEqual(projected["product"], "original-dci")
        identity_input = dict(projected)
        identity_input.pop("identity_sha256")
        expected = hashlib.sha256(
            json.dumps(
                identity_input,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
        ).hexdigest()
        self.assertEqual(projected["identity_sha256"], expected)

    def test_public_projection_rejects_private_values(self) -> None:
        runtime = resolve_original_runtime({}, ConfigLayers({}, {}))
        unsafe_values = (
            {"api_key": "secret"},
            {"prompt": "private question"},
            {"corpus": "/Users/private/corpus"},
        )
        for experiment in unsafe_values:
            with self.subTest(experiment=experiment):
                with self.assertRaisesRegex(ValueError, "unsafe"):
                    OriginalEffectiveConfig(
                        runtime=runtime,
                        context={},
                        judge={},
                        experiment=experiment,
                    ).to_public_dict()

    def test_public_projection_rejects_sensitive_judge_endpoints(self) -> None:
        runtime = resolve_original_runtime({}, ConfigLayers({}, {}))
        unsafe_endpoints = (
            "https://user:password@judge.example/v1/chat/completions",
            "https://judge.example/v1/chat/completions?api_key=secret",
            "https://judge.example/v1/chat/completions#token=secret",
        )
        for endpoint in unsafe_endpoints:
            with self.subTest(endpoint=endpoint):
                with self.assertRaisesRegex(ValueError, "unsafe judge endpoint"):
                    OriginalEffectiveConfig(
                        runtime=runtime,
                        judge={"endpoint": endpoint},
                    ).to_public_dict()

    def test_serializer_validates_projection_against_checked_in_schema(self) -> None:
        schema = json.loads(
            effective_config_module.SCHEMA_PATH.read_text(encoding="utf-8")
        )
        schema["properties"]["product"]["const"] = "schema-validation-canary"
        runtime = resolve_original_runtime({}, ConfigLayers({}, {}))

        with tempfile.TemporaryDirectory() as temporary_directory:
            schema_path = Path(temporary_directory) / "effective-config.schema.json"
            schema_path.write_text(json.dumps(schema), encoding="utf-8")
            with (
                patch.object(effective_config_module, "SCHEMA_PATH", schema_path),
                self.assertRaisesRegex(ValueError, "schema"),
            ):
                OriginalEffectiveConfig(runtime=runtime).to_public_dict()


if __name__ == "__main__":
    unittest.main()
