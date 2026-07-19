from __future__ import annotations

import json
import os
import asyncio
import threading
import unittest
import urllib.error
from dataclasses import replace
from unittest.mock import patch

from asterion.dci.judge import (
    build_judge_request,
    DciJudgeError,
    JudgeConfig,
    judge_answer_sync,
    judge_answer_async,
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

    def test_judge_rejects_malformed_shared_or_alias_boolean(self) -> None:
        for environment_name in (
            "DCI_EVAL_JUDGE_JSON_MODE",
            "ASTERION_DCI_JUDGE_JSON_MODE",
        ):
            with self.subTest(environment_name=environment_name):
                with patch.dict(
                    os.environ, {environment_name: "sometimes"}, clear=True
                ):
                    with self.assertRaises(ValueError):
                        JudgeConfig.from_env()

    def test_judge_rejects_nonfinite_price(self) -> None:
        for value in ("nan", "inf", "-inf"):
            with self.subTest(value=value):
                with patch.dict(
                    os.environ,
                    {"DCI_EVAL_JUDGE_INPUT_PRICE_PER_1M": value},
                    clear=True,
                ):
                    with self.assertRaises(ValueError):
                        JudgeConfig.from_env()

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

    def test_fingerprint_is_stable_against_api_key_value_or_name_changes(self) -> None:
        baseline = judge_request_fingerprint(
            config=JudgeConfig(
                base_url="https://judge.example.test/v1",
                model="fixture",
                api="responses",
                api_key_env="DEEPSEEK_API_KEY",
                api_key="one",
            ),
            question="question",
            gold_answer="gold",
            predicted_answer="prediction",
        )
        with_env_name = judge_request_fingerprint(
            config=JudgeConfig(
                base_url="https://judge.example.test/v1",
                model="fixture",
                api="responses",
                api_key_env="CUSTOM_JUDGE_KEY",
                api_key="two",
            ),
            question="question",
            gold_answer="gold",
            predicted_answer="prediction",
        )

        self.assertEqual(baseline, with_env_name)

    def test_every_public_request_shaping_field_changes_fingerprint(self) -> None:
        baseline_config = _config()
        baseline = judge_request_fingerprint(
            config=baseline_config, question="q", gold_answer="g", predicted_answer="p"
        )
        changes = {
            "base_url": "https://other.example.test/v2",
            "api": "responses",
            "model": "other",
            "timeout_seconds": 9,
            "max_output_tokens": 99,
            "json_mode": False,
            "strict_json_schema": True,
            "responses_store": True,
            "thinking": "disabled",
            "input_price_per_1m": 9.0,
            "cached_input_price_per_1m": 8.0,
            "output_price_per_1m": 7.0,
        }
        for field_name, value in changes.items():
            with self.subTest(field_name=field_name):
                changed = replace(baseline_config, **{field_name: value})
                self.assertNotEqual(
                    baseline,
                    judge_request_fingerprint(
                        config=changed,
                        question="q",
                        gold_answer="g",
                        predicted_answer="p",
                    ),
                )

    def test_responses_and_chat_requests_include_configured_shaping(self) -> None:
        responses = build_judge_request(
            replace(
                _config(),
                api="responses",
                strict_json_schema=True,
                responses_store=True,
            ),
            question="q",
            gold_answer="g",
            predicted_answer="p",
        )
        chat = build_judge_request(
            replace(_config(), api="chat", thinking="disabled"),
            question="q",
            gold_answer="g",
            predicted_answer="p",
        )
        self.assertEqual(responses["text"]["format"]["type"], "json_schema")
        self.assertIs(responses["store"], True)
        self.assertEqual(chat["response_format"], {"type": "json_object"})
        self.assertEqual(chat["thinking"], {"type": "disabled"})

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
                    base_url="https://judge.example.test/v1",
                    api="responses",
                    api_key="secret-key",
                ),
                question="question",
                gold_answer="gold",
                predicted_answer="answer",
            )

        self.assertTrue(result["is_correct"])
        self.assertEqual(result["usage"]["total_tokens"], 5)
        self.assertEqual(result["cost_estimate_usd"]["total_cost"], 0.0)
        self.assertRegex(str(result["judge_request_fingerprint"]), r"^[0-9a-f]{64}$")
        self.assertNotIn("secret-key", repr(result))

    def test_transport_failure_is_safe_and_does_not_echo_response(self) -> None:
        detail = "provider-secret-response"
        with patch(
            "asterion.dci.judge._open_judge_request",
            side_effect=urllib.error.URLError(detail),
        ) as opened:
            with patch("asterion.dci.judge._wait_before_retry"):
                with self.assertRaisesRegex(
                    DciJudgeError, "judge transport failed"
                ) as raised:
                    judge_answer_sync(
                        config=JudgeConfig(base_url="https://judge.example.test/v1"),
                        question="question",
                        gold_answer="gold",
                        predicted_answer="answer",
                    )

        self.assertNotIn(detail, str(raised.exception))
        self.assertEqual(opened.call_count, 3)

    def test_invalid_and_retryable_failures_share_one_three_request_budget(
        self,
    ) -> None:
        good = _Response(
            {
                "output_text": json.dumps(
                    {"is_correct": True, "normalized_prediction": "a", "reason": "ok"}
                )
            }
        )
        failures = [
            _Response({"output_text": "not-json"}),
            urllib.error.HTTPError(
                "https://judge.example.test", 429, "limited", {"Retry-After": "0"}, None
            ),
            good,
        ]
        with patch(
            "asterion.dci.judge._open_judge_request", side_effect=failures
        ) as opened:
            with patch("asterion.dci.judge._wait_before_retry"):
                result = judge_answer_sync(
                    config=replace(_config(), api="responses"),
                    question="q",
                    gold_answer="g",
                    predicted_answer="a",
                )
        self.assertEqual(opened.call_count, 3)
        self.assertEqual(result["attempts"], 3)

    def test_terminal_http_error_is_not_retried(self) -> None:
        error = urllib.error.HTTPError(
            "https://judge.example.test", 400, "bad", {}, None
        )
        with patch(
            "asterion.dci.judge._open_judge_request", side_effect=error
        ) as opened:
            with self.assertRaises(DciJudgeError):
                judge_answer_sync(
                    config=_config(),
                    question="q",
                    gold_answer="g",
                    predicted_answer="a",
                )
        self.assertEqual(opened.call_count, 1)

    def test_http_retry_taxonomy_has_exact_request_counts(self) -> None:
        for status in (408, 409, 429, 500, 599):
            with self.subTest(status=status):
                errors = [
                    urllib.error.HTTPError(
                        "https://judge.example.test", status, "x", {}, None
                    )
                    for _ in range(3)
                ]
                with patch(
                    "asterion.dci.judge._open_judge_request", side_effect=errors
                ) as opened:
                    with patch("asterion.dci.judge._wait_before_retry"):
                        with self.assertRaises(DciJudgeError):
                            judge_answer_sync(
                                config=_config(),
                                question="q",
                                gold_answer="g",
                                predicted_answer="p",
                            )
                self.assertEqual(opened.call_count, 3)
        for status in (301, 302, 400, 401, 403, 404, 422):
            with self.subTest(status=status):
                error = urllib.error.HTTPError(
                    "https://judge.example.test", status, "x", {}, None
                )
                with patch(
                    "asterion.dci.judge._open_judge_request", side_effect=error
                ) as opened:
                    with self.assertRaises(DciJudgeError):
                        judge_answer_sync(
                            config=_config(),
                            question="q",
                            gold_answer="g",
                            predicted_answer="p",
                        )
                self.assertEqual(opened.call_count, 1)

    def test_retry_after_is_bounded_and_invalid_values_use_fallback(self) -> None:
        for value in ("999999", "nonsense"):
            with self.subTest(value=value):
                error = urllib.error.HTTPError(
                    "https://judge.example.test",
                    503,
                    "busy",
                    {"Retry-After": value},
                    None,
                )
                with patch(
                    "asterion.dci.judge._open_judge_request",
                    side_effect=[error, error, error],
                ):
                    with patch("asterion.dci.judge._wait_before_retry") as waited:
                        with self.assertRaises(DciJudgeError):
                            judge_answer_sync(
                                config=_config(),
                                question="q",
                                gold_answer="g",
                                predicted_answer="a",
                            )
                self.assertTrue(
                    all(call.args[0] <= 30 for call in waited.call_args_list)
                )

    def test_async_cancellation_drains_started_http_and_stops_retry(self) -> None:
        started = threading.Event()
        release = threading.Event()
        calls: list[int] = []

        def blocking(*_args: object, **_kwargs: object) -> object:
            calls.append(1)
            started.set()
            release.wait(2)
            raise urllib.error.URLError("closed")

        async def scenario() -> None:
            with patch("asterion.dci.judge._open_judge_request", side_effect=blocking):
                task = asyncio.create_task(
                    judge_answer_async(
                        config=_config(),
                        question="q",
                        gold_answer="g",
                        predicted_answer="a",
                    )
                )
                await asyncio.to_thread(started.wait, 1)
                task.cancel()
                await asyncio.sleep(0)
                self.assertFalse(task.done())
                task.cancel()
                await asyncio.sleep(0)
                self.assertFalse(task.done())
                release.set()
                with self.assertRaises(asyncio.CancelledError):
                    await task

        asyncio.run(scenario())
        self.assertEqual(len(calls), 1)

    def test_scripts_bcplus_eval_run_bcplus_eval_py_function_judge_answer_async(
        self,
    ) -> None:
        self.test_async_cancellation_drains_started_http_and_stops_retry()

    def test_scripts_bcplus_eval_run_bcplus_eval_py_function_load_judge_config_from_args(
        self,
    ) -> None:
        self.test_shared_judge_settings_win_over_asterion_aliases()


class _Response:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload

    def __enter__(self) -> "_Response":
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")


def _config() -> JudgeConfig:
    return JudgeConfig(base_url="https://judge.example.test/v1", model="fixture")


if __name__ == "__main__":
    unittest.main()
