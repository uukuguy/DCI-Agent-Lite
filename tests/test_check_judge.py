from __future__ import annotations

import importlib.util
import io
import json
import os
import subprocess
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import ModuleType
from unittest.mock import patch

from tests import SOURCE_ROOT as _SOURCE_ROOT  # noqa: F401
from dci.benchmark.judge import JudgeConfig


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts/check_judge.py"


def synthetic_judge_environment() -> dict[str, str]:
    environment = {
        name: value
        for name, value in os.environ.items()
        if not name.startswith("DCI_EVAL_JUDGE_")
    }
    environment.pop("PYTHONPATH", None)
    environment.update(
        {
            "DCI_EVAL_JUDGE_API_KEY": "synthetic-non-secret-key",
            "DCI_EVAL_JUDGE_API_KEY_ENV": "AF250_UNUSED_JUDGE_KEY",
            "DCI_EVAL_JUDGE_BASE_URL": "https://judge.invalid/v1",
            "DCI_EVAL_JUDGE_API": "chat-completions",
            "DCI_EVAL_JUDGE_MODEL": "synthetic-judge-model",
            "DCI_EVAL_JUDGE_TIMEOUT_SECONDS": "120",
            "DCI_EVAL_JUDGE_MAX_OUTPUT_TOKENS": "1024",
            "DCI_EVAL_JUDGE_JSON_MODE": "true",
            "DCI_EVAL_JUDGE_STRICT_JSON_SCHEMA": "false",
            "DCI_EVAL_JUDGE_RESPONSES_STORE": "false",
            "DCI_EVAL_JUDGE_THINKING": "disabled",
            "DCI_EVAL_JUDGE_INPUT_PRICE_PER_1M": "0",
            "DCI_EVAL_JUDGE_CACHED_INPUT_PRICE_PER_1M": "0",
            "DCI_EVAL_JUDGE_OUTPUT_PRICE_PER_1M": "0",
        }
    )
    return environment


def load_check_judge() -> ModuleType:
    spec = importlib.util.spec_from_file_location("check_judge", SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to import {SCRIPT_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CheckJudgeTests(unittest.TestCase):
    def test_preflight_script_exists(self) -> None:
        self.assertTrue(
            SCRIPT_PATH.is_file(),
            "H-006 requires a standalone judge preflight script",
        )

    def test_preflight_uses_shared_judge_transport(self) -> None:
        check_judge = load_check_judge()
        runner = getattr(check_judge, "run_preflight", None)
        self.assertIsNotNone(runner, "preflight must expose run_preflight")
        config = JudgeConfig(api="responses", api_key="test-key")

        with patch.object(
            check_judge,
            "judge_answer_sync",
            return_value={"is_correct": True},
        ) as judge:
            payload = runner(config)

        judge.assert_called_once_with(
            config=config,
            question="What is 1 + 1?",
            gold_answer="2",
            predicted_answer="2",
        )
        self.assertTrue(payload["is_correct"])

    def test_preflight_rejects_missing_api_key_before_request(self) -> None:
        check_judge = load_check_judge()
        runner = getattr(check_judge, "run_preflight", None)
        self.assertIsNotNone(runner, "preflight must expose run_preflight")
        config = JudgeConfig(api_key_env="TEST_JUDGE_KEY", api_key="")

        with patch.object(check_judge, "judge_answer_sync") as judge:
            with self.assertRaisesRegex(ValueError, "TEST_JUDGE_KEY"):
                runner(config)

        judge.assert_not_called()

    def test_main_outputs_only_safe_result_fields(self) -> None:
        check_judge = load_check_judge()
        main = getattr(check_judge, "main", None)
        config_class = getattr(check_judge, "JudgeConfig", None)
        self.assertIsNotNone(main, "preflight must expose main")
        self.assertIsNotNone(config_class, "preflight must load JudgeConfig")
        config = JudgeConfig(api="chat-completions", api_key="secret-key")
        result = {
            "is_correct": True,
            "usage": {"total_tokens": 3},
            "cost_estimate_usd": {"total_cost": 0.0},
            "raw_response": {"secret": "no"},
        }

        with (
            patch.object(check_judge, "load_project_env"),
            patch.object(config_class, "from_env", return_value=config) as from_env,
            patch.object(check_judge, "run_preflight", return_value=result),
            patch("sys.argv", ["check_judge.py"]),
            redirect_stdout(io.StringIO()) as stdout,
        ):
            self.assertEqual(main(), 0)

        payload = json.loads(stdout.getvalue())
        self.assertEqual(from_env.call_count, 1)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["judge_api"], "chat-completions")
        self.assertNotIn("api_key", payload)
        self.assertNotIn("raw_response", payload)

    def test_key_provenance_reports_dotenv_source(self) -> None:
        check_judge = load_check_judge()
        provenance = getattr(check_judge, "judge_key_provenance", None)
        self.assertIsNotNone(provenance, "preflight must expose key provenance")

        result = provenance(
            JudgeConfig(api_key_env="DEEPSEEK_API_KEY", api_key="dotenv-key"),
            process_environment={},
            dotenv_environment={"DEEPSEEK_API_KEY": "dotenv-key"},
        )

        self.assertEqual(result["judge_api_key_source"], "dotenv")
        self.assertFalse(result["judge_api_key_shadowed_by_environment"])

    def test_key_provenance_reports_process_environment_source(self) -> None:
        check_judge = load_check_judge()
        provenance = getattr(check_judge, "judge_key_provenance", None)
        self.assertIsNotNone(provenance, "preflight must expose key provenance")

        result = provenance(
            JudgeConfig(api_key_env="DEEPSEEK_API_KEY", api_key="process-key"),
            process_environment={"DEEPSEEK_API_KEY": "process-key"},
            dotenv_environment={},
        )

        self.assertEqual(result["judge_api_key_source"], "process-environment")
        self.assertFalse(result["judge_api_key_shadowed_by_environment"])

    def test_key_provenance_warns_when_process_shadows_dotenv(self) -> None:
        check_judge = load_check_judge()
        provenance = getattr(check_judge, "judge_key_provenance", None)
        self.assertIsNotNone(provenance, "preflight must expose key provenance")

        result = provenance(
            JudgeConfig(api_key_env="DEEPSEEK_API_KEY", api_key="process-key"),
            process_environment={"DEEPSEEK_API_KEY": "process-key"},
            dotenv_environment={"DEEPSEEK_API_KEY": "rotated-dotenv-key"},
        )

        self.assertEqual(result["judge_api_key_source"], "process-environment")
        self.assertTrue(result["judge_api_key_shadowed_by_environment"])

    def test_main_outputs_safe_key_provenance(self) -> None:
        check_judge = load_check_judge()
        loader = getattr(check_judge, "load_judge_config_with_provenance", None)
        main = getattr(check_judge, "main", None)
        self.assertIsNotNone(loader, "preflight must load configuration with provenance")
        self.assertIsNotNone(main, "preflight must expose main")
        config = JudgeConfig(api="responses", api_key="secret-key")
        provenance = {
            "judge_api_key_source": "dotenv",
            "judge_api_key_shadowed_by_environment": False,
        }

        with (
            patch.object(
                check_judge,
                "load_judge_config_with_provenance",
                return_value=(config, provenance),
            ),
            patch.object(
                check_judge,
                "run_preflight",
                return_value={"is_correct": True},
            ),
            patch("sys.argv", ["check_judge.py"]),
            redirect_stdout(io.StringIO()) as stdout,
        ):
            self.assertEqual(main(), 0)

        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["judge_api_key_source"], "dotenv")
        self.assertFalse(payload["judge_api_key_shadowed_by_environment"])
        self.assertNotIn("secret-key", stdout.getvalue())

    def test_config_only_skips_preflight_request(self) -> None:
        check_judge = load_check_judge()
        config = JudgeConfig(api="responses", api_key="secret-key")
        provenance = {
            "judge_api_key_source": "dotenv",
            "judge_api_key_shadowed_by_environment": False,
        }

        with (
            patch.object(
                check_judge,
                "load_judge_config_with_provenance",
                return_value=(config, provenance),
            ),
            patch.object(
                check_judge,
                "run_preflight",
                return_value={"is_correct": True},
            ) as preflight,
            patch("sys.argv", ["check_judge.py", "--config-only"]),
            redirect_stdout(io.StringIO()) as stdout,
        ):
            self.assertEqual(check_judge.main(), 0)

        payload = json.loads(stdout.getvalue())
        preflight.assert_not_called()
        self.assertTrue(payload["ok"])
        self.assertFalse(payload["request_performed"])
        self.assertEqual(payload["judge_api_key_source"], "dotenv")
        self.assertNotIn("secret-key", stdout.getvalue())

    def test_make_target_runs_the_preflight_script(self) -> None:
        makefile = (REPO_ROOT / "Makefile").read_text()

        self.assertIn("check-judge:", makefile)
        self.assertIn(
            "PYTHONPATH=src uv run python scripts/check_judge.py", makefile
        )

    def test_make_target_runs_config_only_preflight(self) -> None:
        makefile = (REPO_ROOT / "Makefile").read_text()

        self.assertIn("check-judge-config:", makefile)
        self.assertIn(
            "PYTHONPATH=src uv run python scripts/check_judge.py --config-only",
            makefile,
        )

    def test_make_config_target_is_independently_executable(self) -> None:
        result = subprocess.run(
            ["make", "check-judge-config"],
            cwd=REPO_ROOT,
            env=synthetic_judge_environment(),
            text=True,
            capture_output=True,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout.splitlines()[-1])
        shadowed = payload.pop("judge_api_key_shadowed_by_environment")
        self.assertIsInstance(shadowed, bool)
        self.assertEqual(
            payload,
            {
                "judge_api": "chat-completions",
                "judge_api_key_env": "AF250_UNUSED_JUDGE_KEY",
                "judge_api_key_source": "process-environment",
                "judge_base_url": "https://judge.invalid/v1",
                "judge_cached_input_price_per_1m": 0.0,
                "judge_input_price_per_1m": 0.0,
                "judge_json_mode": True,
                "judge_max_output_tokens": 1024,
                "judge_model": "synthetic-judge-model",
                "judge_output_price_per_1m": 0.0,
                "judge_responses_store": False,
                "judge_strict_json_schema": False,
                "judge_thinking": "disabled",
                "judge_timeout_seconds": 120,
                "ok": True,
                "request_performed": False,
            },
        )
        self.assertNotIn("synthetic-non-secret-key", result.stdout + result.stderr)

    def test_documentation_explains_the_credentialed_preflight(self) -> None:
        readme = (REPO_ROOT / "README.md").read_text()
        template = (REPO_ROOT / ".env.template").read_text()

        self.assertIn("make check-judge", readme)
        self.assertIn("make check-judge", template)

    def test_documentation_explains_key_precedence_and_provenance(self) -> None:
        readme = (REPO_ROOT / "README.md").read_text()
        template = (REPO_ROOT / ".env.template").read_text()

        self.assertIn("process environment", readme)
        self.assertIn("judge_api_key_source", readme)
        self.assertIn("process environment", template)

    def test_environment_template_uses_runtime_first_agent_defaults(self) -> None:
        template = (REPO_ROOT / ".env.template").read_text()

        self.assertIn("DCI_RUNTIME=pi", template)
        self.assertIn("DCI_PROVIDER=openai-codex", template)
        self.assertIn("DCI_MODEL=gpt-5.6-luna", template)
        self.assertIn("local subscription login", template)
        self.assertIn("CLI", template)


if __name__ == "__main__":
    unittest.main()
