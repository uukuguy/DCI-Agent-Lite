from __future__ import annotations

import json
import os
import unittest
import urllib.error
from dataclasses import replace
from unittest.mock import patch

from asterion.dci.judge import (
    DciJudgeError,
    JudgeConfig,
    judge_answer_sync,
    judge_request_fingerprint,
)


class AsterionDciJudgeTests(unittest.TestCase):
    def test_configuration_is_public_without_api_key(self) -> None:
        config = JudgeConfig(
            base_url="https://judge.example.test/v1",
            model="fixture-model",
            api_key="secret-key",
        )

        public = config.public_dict()

        self.assertEqual(public["judge_base_url"], "https://judge.example.test/v1")
        self.assertNotIn("api_key", public)
        self.assertNotIn("secret-key", repr(public))

    def test_shared_judge_settings_win_over_asterion_aliases(self) -> None:
        with patch.dict(
            os.environ,
            {
                "DCI_EVAL_JUDGE_BASE_URL": "https://shared.example.test/v1",
                "DCI_EVAL_JUDGE_MODEL": "shared-judge",
                "ASTERION_DCI_JUDGE_MODEL": "compat-judge",
            },
            clear=True,
        ):
            config = JudgeConfig.from_env()

        self.assertEqual(
            (config.base_url, config.model),
            ("https://shared.example.test/v1", "shared-judge"),
        )

    def test_fingerprint_changes_with_complete_request_shape(self) -> None:
        config = JudgeConfig(base_url="https://judge.example.test/v1", model="fixture")
        baseline = judge_request_fingerprint(
            config=config,
            question="question",
            gold_answer="gold",
            predicted_answer="prediction",
        )

        self.assertNotEqual(
            baseline,
            judge_request_fingerprint(
                config=replace(config, strict_json_schema=True),
                question="question",
                gold_answer="gold",
                predicted_answer="prediction",
            ),
        )
        self.assertNotEqual(
            baseline,
            judge_request_fingerprint(
                config=config,
                question="question",
                gold_answer="changed gold",
                predicted_answer="prediction",
            ),
        )

    def test_mocked_response_is_validated_and_normalized(self) -> None:
        response = _Response(
            {
                "output_text": json.dumps(
                    {
                        "is_correct": True,
                        "normalized_prediction": "answer",
                        "reason": "same answer",
                    }
                ),
                "usage": {"input_tokens": 3, "output_tokens": 2},
            }
        )
        with patch("asterion.dci.judge._open_judge_request", return_value=response):
            result = judge_answer_sync(
                config=JudgeConfig(
                    base_url="https://judge.example.test/v1", api_key="secret-key"
                ),
                question="question",
                gold_answer="gold",
                predicted_answer="answer",
            )

        self.assertTrue(result["is_correct"])
        self.assertEqual(result["usage"]["total_tokens"], 5)
        self.assertRegex(str(result["judge_request_fingerprint"]), r"^[0-9a-f]{64}$")
        self.assertNotIn("secret-key", repr(result))

    def test_transport_failure_is_safe_and_does_not_echo_response(self) -> None:
        detail = "provider-secret-response"
        with patch(
            "asterion.dci.judge._open_judge_request",
            side_effect=urllib.error.URLError(detail),
        ):
            with self.assertRaisesRegex(DciJudgeError, "judge transport failed") as raised:
                judge_answer_sync(
                    config=JudgeConfig(base_url="https://judge.example.test/v1"),
                    question="question",
                    gold_answer="gold",
                    predicted_answer="answer",
                )

        self.assertNotIn(detail, str(raised.exception))


class _Response:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload

    def __enter__(self) -> "_Response":
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")


if __name__ == "__main__":
    unittest.main()
