from __future__ import annotations

import importlib
import json
import unittest
from importlib import resources
from pathlib import Path


EXPECTED = {
    "level0": (None, None, None, None, None),
    "level1": (50_000, None, None, None, None),
    "level2": (20_000, None, None, None, None),
    "level3": (20_000, 240_000, 12, None, None),
    "level4": (20_000, 240_000, 12, 20_000, 3),
}


def context_profiles_module(test: unittest.TestCase):
    try:
        return importlib.import_module("asterion.dci.context_profiles")
    except ModuleNotFoundError:
        test.fail("asterion.dci.context_profiles is not implemented")


class AsterionDciContextProfileTests(unittest.TestCase):
    def test_original_readme_verifier_does_not_import_asterion(self) -> None:
        source = Path("tools/verify_original_readme.py").read_text(encoding="utf-8")
        self.assertNotIn("import asterion", source)
        self.assertNotIn("from asterion", source)

    def test_exact_closed_profile_names_and_thresholds(self) -> None:
        module = context_profiles_module(self)

        self.assertEqual(module.context_profile_names(), tuple(EXPECTED))
        for name, expected in EXPECTED.items():
            with self.subTest(profile=name):
                profile = module.resolve_context_profile(name)
                self.assertEqual(profile.name, name)
                self.assertEqual(profile.contract_version, "dci.context-profile/v1")
                self.assertEqual(
                    (
                        profile.tool_result_character_cap,
                        profile.compaction_character_trigger,
                        profile.retained_turns,
                        profile.summary_recent_token_target,
                        profile.summary_failure_limit,
                    ),
                    expected,
                )

    def test_identity_payload_is_complete_and_stable(self) -> None:
        module = context_profiles_module(self)

        profile = module.resolve_context_profile("level4")

        self.assertEqual(
            profile.identity_payload(),
            {
                "profile": "level4",
                "contract_version": "dci.context-profile/v1",
                "tool_result_character_cap": 20_000,
                "compaction_character_trigger": 240_000,
                "retained_turns": 12,
                "summary_recent_token_target": 20_000,
                "summary_failure_limit": 3,
            },
        )

    def test_none_is_unselected_and_invalid_aliases_fail_closed(self) -> None:
        module = context_profiles_module(self)

        self.assertIsNone(module.resolve_context_profile(None))
        for value in ("", " level3", "level3 ", "LEVEL3", "level5", "legacy", True, 3):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "context profile"):
                    module.resolve_context_profile(value)

    def test_packaged_contract_matches_python_profiles_exactly(self) -> None:
        module = context_profiles_module(self)
        resource = resources.files("asterion.dci.resources").joinpath(
            "context-profiles.json"
        )
        self.assertTrue(resource.is_file(), "canonical context profile resource is missing")

        payload = json.loads(resource.read_text(encoding="utf-8"))

        self.assertEqual(payload["schema"], "dci.context-profile/v1")
        self.assertEqual(tuple(payload["profiles"]), tuple(EXPECTED))
        self.assertEqual(
            payload["profiles"],
            {
                name: module.resolve_context_profile(name).identity_payload()
                for name in EXPECTED
            },
        )

    def test_schema_is_closed_and_requires_every_identity_field(self) -> None:
        resource = resources.files("asterion.dci.resources").joinpath(
            "context-profile.schema.json"
        )
        self.assertTrue(resource.is_file(), "context profile schema is missing")

        schema = json.loads(resource.read_text(encoding="utf-8"))
        profile_schema = schema["$defs"]["profile"]

        self.assertFalse(schema["additionalProperties"])
        self.assertFalse(profile_schema["additionalProperties"])
        self.assertEqual(
            set(profile_schema["required"]),
            {
                "profile",
                "contract_version",
                "tool_result_character_cap",
                "compaction_character_trigger",
                "retained_turns",
                "summary_recent_token_target",
                "summary_failure_limit",
            },
        )


if __name__ == "__main__":
    unittest.main()
