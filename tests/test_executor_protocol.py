from __future__ import annotations

import json
import unittest
from pathlib import Path

from dci.framework.executor_protocol import ExecutorProtocolError, validate_message


FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures/executor/v1"


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
