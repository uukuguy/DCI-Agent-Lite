from __future__ import annotations

import hashlib
import json
import unittest

from tests import SOURCE_ROOT as _SOURCE_ROOT  # noqa: F401
from dci.config import ConfigLayers, resolve_original_runtime
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


if __name__ == "__main__":
    unittest.main()
