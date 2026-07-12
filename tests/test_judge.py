from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import MagicMock, patch

import dci.benchmark.judge as judge_module
from dci.benchmark.judge import (
    JudgeConfig,
    build_judge_request,
    extract_responses_text,
    judge_answer_sync,
)
from dci.benchmark.pi_rpc_runner import maybe_reuse_existing_eval, parse_args
from dci.config import load_project_env


class JudgeConfigTests(unittest.TestCase):
    def test_deepseek_config_is_loaded_from_environment(self) -> None:
        environment = {
            "DEEPSEEK_API_KEY": "secret-key",
            "DCI_EVAL_JUDGE_BASE_URL": "https://api.deepseek.com/v1/",
            "DCI_EVAL_JUDGE_API": "chat_completions",
            "DCI_EVAL_JUDGE_MODEL": "deepseek-v4-flash",
            "DCI_EVAL_JUDGE_API_KEY_ENV": "DEEPSEEK_API_KEY",
            "DCI_EVAL_JUDGE_TIMEOUT_SECONDS": "45",
            "DCI_EVAL_JUDGE_MAX_OUTPUT_TOKENS": "2048",
            "DCI_EVAL_JUDGE_JSON_MODE": "true",
            "DCI_EVAL_JUDGE_THINKING": "disabled",
            "DCI_EVAL_JUDGE_INPUT_PRICE_PER_1M": "0",
            "DCI_EVAL_JUDGE_CACHED_INPUT_PRICE_PER_1M": "0",
            "DCI_EVAL_JUDGE_OUTPUT_PRICE_PER_1M": "0",
        }
        with patch.dict(os.environ, environment, clear=True):
            config = JudgeConfig.from_env()

        self.assertEqual(config.base_url, "https://api.deepseek.com/v1")
        self.assertEqual(config.api, "chat-completions")
        self.assertEqual(config.model, "deepseek-v4-flash")
        self.assertEqual(config.api_key, "secret-key")
        self.assertEqual(
            config.endpoint, "https://api.deepseek.com/v1/chat/completions"
        )
        self.assertEqual(config.input_price_per_1m, 0)
        self.assertEqual(config.output_price_per_1m, 0)
        self.assertEqual(config.max_output_tokens, 2048)
        self.assertTrue(config.json_mode)
        self.assertEqual(config.effective_thinking, "disabled")
        self.assertNotIn("api_key", config.public_dict())

    def test_cli_style_overrides_take_precedence_over_environment(self) -> None:
        with patch.dict(
            os.environ,
            {
                "DCI_EVAL_JUDGE_BASE_URL": "https://from-env.example/v1",
                "DCI_EVAL_JUDGE_MODEL": "from-env",
            },
            clear=True,
        ):
            config = JudgeConfig.from_env(
                base_url="https://override.example/v1",
                api="responses",
                model="override-model",
            )

        self.assertEqual(config.base_url, "https://override.example/v1")
        self.assertEqual(config.model, "override-model")

    def test_project_env_does_not_override_process_environment(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (root / ".env").write_text(
                "DCI_TEST_EXISTING=from-file\nDCI_TEST_NEW=loaded\n",
                encoding="utf-8",
            )
            with patch.dict(
                os.environ, {"DCI_TEST_EXISTING": "from-process"}, clear=True
            ):
                load_project_env(root)
                self.assertEqual(os.environ["DCI_TEST_EXISTING"], "from-process")
                self.assertEqual(os.environ["DCI_TEST_NEW"], "loaded")

    def test_main_entry_uses_agent_provider_and_model_from_environment(self) -> None:
        with (
            patch.dict(
                os.environ,
                {"DCI_PROVIDER": "custom-provider", "DCI_MODEL": "custom-model"},
                clear=True,
            ),
            patch("sys.argv", ["dci-agent-lite"]),
        ):
            args = parse_args()

        self.assertEqual(args.provider, "custom-provider")
        self.assertEqual(args.model, "custom-model")


class JudgeTransportTests(unittest.TestCase):
    def test_judge_request_fingerprint_is_deterministic_and_endpoint_sensitive(self) -> None:
        self.assertTrue(
            hasattr(judge_module, "judge_request_fingerprint"),
            "Judge requests need a safe cache fingerprint",
        )
        config = JudgeConfig(
            base_url="https://api.deepseek.com/v1",
            api="chat-completions",
            model="deepseek-v4-flash",
        )
        fingerprint = judge_module.judge_request_fingerprint(
            config=config,
            question="Question",
            gold_answer="Gold",
            predicted_answer="Prediction",
        )
        repeated = judge_module.judge_request_fingerprint(
            config=config,
            question="Question",
            gold_answer="Gold",
            predicted_answer="Prediction",
        )
        changed_endpoint = judge_module.judge_request_fingerprint(
            config=JudgeConfig(
                base_url="http://localhost:8000/v1",
                api="chat-completions",
                model="deepseek-v4-flash",
            ),
            question="Question",
            gold_answer="Gold",
            predicted_answer="Prediction",
        )

        self.assertRegex(fingerprint, r"^[0-9a-f]{64}$")
        self.assertEqual(fingerprint, repeated)
        self.assertNotEqual(fingerprint, changed_endpoint)

    def test_chat_completions_request_and_response_are_normalized(self) -> None:
        config = JudgeConfig(
            base_url="https://api.deepseek.com/v1",
            api="chat-completions",
            model="deepseek-v4-flash",
            api_key_env="DEEPSEEK_API_KEY",
            api_key="secret-key",
            input_price_per_1m=1.0,
            cached_input_price_per_1m=0.5,
            output_price_per_1m=2.0,
        )
        response_payload = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "is_correct": True,
                                "normalized_prediction": "Adaku",
                                "reason": "Matches the gold answer.",
                            }
                        )
                    }
                }
            ],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15,
                "prompt_tokens_details": {"cached_tokens": 4},
            },
        }
        response = MagicMock()
        response.__enter__.return_value = response
        response.read.return_value = json.dumps(response_payload).encode("utf-8")

        with patch(
            "dci.benchmark.judge.urllib.request.urlopen", return_value=response
        ) as urlopen:
            result = judge_answer_sync(
                config=config,
                question="Who?",
                gold_answer="Adaku",
                predicted_answer="Adaku /path/to/file",
            )

        request = urlopen.call_args.args[0]
        request_payload = json.loads(request.data.decode("utf-8"))
        self.assertEqual(
            request.full_url, "https://api.deepseek.com/v1/chat/completions"
        )
        self.assertEqual(request.get_header("Authorization"), "Bearer secret-key")
        self.assertEqual(request_payload["model"], "deepseek-v4-flash")
        self.assertIn("messages", request_payload)
        self.assertEqual(request_payload["max_tokens"], 1024)
        self.assertEqual(request_payload["response_format"], {"type": "json_object"})
        self.assertEqual(request_payload["thinking"], {"type": "disabled"})
        self.assertIn("Example JSON", request_payload["messages"][0]["content"])
        self.assertNotIn("reasoning", request_payload)
        self.assertTrue(result["is_correct"])
        self.assertEqual(result["usage"]["input_tokens"], 10)
        self.assertEqual(result["usage"]["output_tokens"], 5)
        self.assertEqual(result["judge_api"], "chat-completions")
        self.assertNotIn("raw_response", result)
        self.assertNotIn("raw_response_text", result)
        self.assertIn("judge_request_fingerprint", result)
        self.assertEqual(
            result["judge_request_fingerprint"],
            judge_module.judge_request_fingerprint(
                config=config,
                question="Who?",
                gold_answer="Adaku",
                predicted_answer="Adaku /path/to/file",
            ),
        )
        self.assertAlmostEqual(result["cost_estimate_usd"]["total_cost"], 0.000018)

    def test_responses_request_keeps_the_common_compatible_subset(self) -> None:
        config = JudgeConfig(api="responses", api_key="key")
        payload = build_judge_request(
            config,
            question="Question",
            gold_answer="Gold",
            predicted_answer="Prediction",
        )
        self.assertIn("input", payload)
        self.assertIn("max_output_tokens", payload)
        self.assertNotIn("reasoning", payload)
        self.assertNotIn("text", payload)

        text = extract_responses_text(
            {
                "output": [
                    {
                        "content": [
                            {
                                "type": "output_text",
                                "text": '{"is_correct": false}',
                            }
                        ]
                    }
                ]
            }
        )
        self.assertEqual(text, '{"is_correct": false}')

    def test_responses_can_opt_into_strict_judge_schema(self) -> None:
        config = JudgeConfig(api="responses", api_key="key")
        self.assertTrue(
            hasattr(config, "strict_json_schema"),
            "JudgeConfig must expose an opt-in strict schema setting",
        )
        object.__setattr__(config, "strict_json_schema", True)
        payload = build_judge_request(
            config,
            question="Question",
            gold_answer="Gold",
            predicted_answer="Prediction",
        )

        schema = payload["text"]["format"]
        self.assertEqual(schema["type"], "json_schema")
        self.assertTrue(schema["strict"])
        self.assertEqual(schema["schema"]["required"], [
            "is_correct",
            "normalized_prediction",
            "reason",
        ])

    def test_strict_schema_is_part_of_public_configuration(self) -> None:
        config = JudgeConfig(api="responses")

        self.assertIn("judge_strict_json_schema", config.public_dict())

    def test_generic_chat_backend_can_omit_optional_compatibility_fields(self) -> None:
        config = JudgeConfig(
            base_url="http://localhost:8000/v1",
            api="chat-completions",
            model="local-model",
            json_mode=False,
            thinking="omit",
        )
        payload = build_judge_request(
            config,
            question="Question",
            gold_answer="Gold",
            predicted_answer="Prediction",
        )

        self.assertEqual(payload["max_tokens"], 1024)
        self.assertNotIn("response_format", payload)
        self.assertNotIn("thinking", payload)

    def test_invalid_structured_output_is_retried_once(self) -> None:
        config = JudgeConfig(
            base_url="https://api.deepseek.com/v1",
            api="chat-completions",
            model="deepseek-v4-flash",
        )
        invalid_payload = {
            "choices": [
                {
                    "finish_reason": "length",
                    "message": {"content": "The prediction appears to match"},
                }
            ]
        }
        valid_payload = {
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {
                        "content": json.dumps(
                            {
                                "is_correct": True,
                                "normalized_prediction": "Adaku",
                                "reason": "Matches the gold answer.",
                            }
                        )
                    },
                }
            ]
        }
        responses = []
        for payload in (invalid_payload, valid_payload):
            response = MagicMock()
            response.__enter__.return_value = response
            response.read.return_value = json.dumps(payload).encode("utf-8")
            responses.append(response)

        with patch(
            "dci.benchmark.judge.urllib.request.urlopen", side_effect=responses
        ) as urlopen:
            result = judge_answer_sync(
                config=config,
                question="Who?",
                gold_answer="Adaku",
                predicted_answer="Adaku /path/to/file",
            )

        self.assertEqual(urlopen.call_count, 2)
        self.assertEqual(result["attempts"], 2)
        self.assertTrue(result["is_correct"])

    def test_http_error_does_not_echo_provider_error_body(self) -> None:
        config = JudgeConfig(api="responses", api_key="test-key")
        http_error = urllib.error.HTTPError(
            config.endpoint,
            401,
            "Unauthorized",
            hdrs=None,
            fp=io.BytesIO(b'{"error":"provider body includes exposed-secret"}'),
        )

        with patch(
            "dci.benchmark.judge.urllib.request.urlopen", side_effect=http_error
        ):
            with self.assertRaisesRegex(RuntimeError, "HTTP 401") as raised:
                judge_answer_sync(
                    config=config,
                    question="Who?",
                    gold_answer="Adaku",
                    predicted_answer="Adaku",
                )

        self.assertIn(config.endpoint, str(raised.exception))
        self.assertNotIn("provider body", str(raised.exception))
        self.assertNotIn("exposed-secret", str(raised.exception))

    def test_invalid_structured_output_error_does_not_echo_provider_body(self) -> None:
        config = JudgeConfig(api="chat-completions")
        invalid_payload = {
            "choices": [
                {
                    "finish_reason": "length",
                    "message": {
                        "content": "provider body includes exposed-secret"
                    },
                }
            ]
        }
        responses = []
        for _ in range(2):
            response = MagicMock()
            response.__enter__.return_value = response
            response.read.return_value = json.dumps(invalid_payload).encode("utf-8")
            responses.append(response)

        with patch(
            "dci.benchmark.judge.urllib.request.urlopen", side_effect=responses
        ):
            with self.assertRaisesRegex(
                ValueError, "invalid structured output twice"
            ) as raised:
                judge_answer_sync(
                    config=config,
                    question="Who?",
                    gold_answer="Adaku",
                    predicted_answer="Adaku",
                )

        self.assertNotIn("provider body", str(raised.exception))
        self.assertNotIn("exposed-secret", str(raised.exception))
        self.assertNotIn("response_excerpt", str(raised.exception))


class JudgeResultReuseTests(unittest.TestCase):
    def test_backend_identity_is_part_of_result_reuse(self) -> None:
        config = JudgeConfig(
            base_url="https://api.deepseek.com/v1",
            api="chat-completions",
            model="deepseek-v4-flash",
        )
        fingerprint = judge_module.judge_request_fingerprint(
            config=config,
            question="Question",
            gold_answer="Gold",
            predicted_answer="Prediction",
        )
        existing = {
            **config.public_dict(),
            "judge_request_fingerprint": fingerprint,
            "question": "Question",
            "gold_answer": "Gold",
            "predicted_answer": "Prediction",
            "is_correct": True,
        }
        with tempfile.TemporaryDirectory() as temporary_directory:
            result_path = Path(temporary_directory) / "eval_result.json"
            result_path.write_text(json.dumps(existing), encoding="utf-8")
            reused = maybe_reuse_existing_eval(
                eval_result_path=result_path,
                judge_config=config,
                question="Question",
                gold_answer="Gold",
                predicted_answer="Prediction",
            )
            changed_backend = maybe_reuse_existing_eval(
                eval_result_path=result_path,
                judge_config=JudgeConfig(
                    base_url="http://localhost:8000/v1",
                    api="chat-completions",
                    model=config.model,
                ),
                question="Question",
                gold_answer="Gold",
                predicted_answer="Prediction",
            )
            strict_schema = maybe_reuse_existing_eval(
                eval_result_path=result_path,
                judge_config=JudgeConfig(
                    base_url=config.base_url,
                    api=config.api,
                    model=config.model,
                    strict_json_schema=True,
                ),
                question="Question",
                gold_answer="Gold",
                predicted_answer="Prediction",
            )
            legacy_path = Path(temporary_directory) / "legacy_eval_result.json"
            legacy_path.write_text(
                json.dumps(
                    {
                        **config.public_dict(),
                        "question": "Question",
                        "gold_answer": "Gold",
                        "predicted_answer": "Prediction",
                        "is_correct": True,
                    }
                ),
                encoding="utf-8",
            )
            legacy = maybe_reuse_existing_eval(
                eval_result_path=legacy_path,
                judge_config=config,
                question="Question",
                gold_answer="Gold",
                predicted_answer="Prediction",
            )
            incomplete_path = Path(temporary_directory) / "incomplete_eval_result.json"
            incomplete_path.write_text(
                json.dumps(
                    {
                        **existing,
                        "is_correct": None,
                    }
                ),
                encoding="utf-8",
            )
            incomplete = maybe_reuse_existing_eval(
                eval_result_path=incomplete_path,
                judge_config=config,
                question="Question",
                gold_answer="Gold",
                predicted_answer="Prediction",
            )

        self.assertEqual(reused, existing)
        self.assertIsNone(changed_backend)
        self.assertIsNone(strict_schema)
        self.assertIsNone(legacy)
        self.assertIsNone(incomplete)


if __name__ == "__main__":
    unittest.main()
