from __future__ import annotations

import json
import unittest
from pathlib import Path

from tests import SOURCE_ROOT as _SOURCE_ROOT  # noqa: F401
from dci.framework.executor_protocol import ExecutorProtocolError, validate_message


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = ROOT / "asterion/tests/fixtures/executor/v1"


class ExecutorProtocolTests(unittest.TestCase):
    def test_valid_request_and_response_fixtures_conform(self) -> None:
        names = (
            "valid-execute-request.json",
            "valid-cancel-request.json",
            "valid-execution-result.json",
            "valid-cancel-acknowledged.json",
        )

        for name in names:
            with self.subTest(name=name):
                validate_message(json.loads((FIXTURE_DIR / name).read_text()))

    def test_invalid_request_fixtures_are_rejected(self) -> None:
        names = (
            "invalid-execute-unknown-field.json",
            "invalid-execute-deadline.json",
        )

        for name in names:
            with self.subTest(name=name), self.assertRaises(ExecutorProtocolError):
                validate_message(json.loads((FIXTURE_DIR / name).read_text()))


if __name__ == "__main__":
    unittest.main()
