from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from asterion.services.controlled_executor import ControlledExecutorError
from asterion.services.managed_controlled_executor import (
    OperatorExecutorConfig,
    load_operator_executor_config,
)


def validation_payload() -> dict[str, object]:
    return {
        "program_id": "check",
        "argument_prefix": ["--fixed"],
        "cwd": "workspace",
        "deadline_ms": 1000,
        "max_output_bytes": 4096,
    }


class OperatorExecutorConfigTests(unittest.TestCase):
    def test_loads_three_canonical_operator_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            binary = root / "executor"
            policy = root / "policy.json"
            validation = root / "validation.json"
            binary.write_text("fixture")
            policy.write_text(json.dumps({"workspace_root": "workspace"}))
            validation.write_text(json.dumps(validation_payload()))

            config = load_operator_executor_config(binary, policy, validation)

        self.assertIsInstance(config, OperatorExecutorConfig)
        self.assertEqual(config.validation_config.program_id, "check")
        self.assertEqual(config.validation_config.argument_prefix, ("--fixed",))

    def test_rejects_symlink_directory_malformed_or_unsafe_configuration_without_echo(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            binary = root / "executor"
            policy = root / "policy.json"
            validation = root / "validation.json"
            binary.write_text("fixture")
            policy.write_text("{}")
            validation.write_text(json.dumps(validation_payload()))
            link = root / "SECRET-link"
            link.symlink_to(binary)
            validation.write_text('{"program_id": "SECRET"}')
            for values in (
                (link, policy, validation),
                (binary, root, validation),
                (binary, policy, validation),
                (binary, policy, root / "missing.json"),
            ):
                with self.subTest(values=values):
                    with self.assertRaises(ControlledExecutorError) as caught:
                        load_operator_executor_config(*values)
                    self.assertNotIn("SECRET", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
