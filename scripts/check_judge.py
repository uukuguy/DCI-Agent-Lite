#!/usr/bin/env python3
"""Run a configured judge structured-output preflight."""

from __future__ import annotations

import hmac
import json
import os
import sys
from pathlib import Path
from typing import Any, Mapping

from dotenv import dotenv_values
from dci.benchmark.judge import JudgeConfig, judge_answer_sync
from dci.config import load_project_env


REPO_ROOT = Path(__file__).resolve().parents[1]
PREFLIGHT_QUESTION = "What is 1 + 1?"
PREFLIGHT_ANSWER = "2"
DIRECT_JUDGE_API_KEY_ENV = "DCI_EVAL_JUDGE_API_KEY"


def _nonempty(mapping: Mapping[str, object], name: str) -> str:
    return str(mapping.get(name) or "").strip()


def judge_key_provenance(
    config: JudgeConfig,
    *,
    process_environment: Mapping[str, object],
    dotenv_environment: Mapping[str, object],
) -> dict[str, Any]:
    """Describe the active key source without returning key material."""

    direct_process = _nonempty(process_environment, DIRECT_JUDGE_API_KEY_ENV)
    direct_dotenv = _nonempty(dotenv_environment, DIRECT_JUDGE_API_KEY_ENV)
    if direct_process or direct_dotenv:
        key_name = DIRECT_JUDGE_API_KEY_ENV
    else:
        key_name = config.api_key_env

    process_value = _nonempty(process_environment, key_name)
    dotenv_value = _nonempty(dotenv_environment, key_name)
    if process_value:
        source = "process-environment"
    elif dotenv_value:
        source = "dotenv"
    else:
        source = "missing"

    return {
        "judge_api_key_source": source,
        "judge_api_key_shadowed_by_environment": bool(
            process_value
            and dotenv_value
            and not hmac.compare_digest(process_value, dotenv_value)
        ),
    }


def load_judge_config_with_provenance() -> tuple[JudgeConfig, dict[str, Any]]:
    """Load normal configuration while retaining only non-secret source metadata."""

    process_environment = dict(os.environ)
    dotenv_environment = dotenv_values(REPO_ROOT / ".env")
    load_project_env(REPO_ROOT)
    config = JudgeConfig.from_env()
    return config, judge_key_provenance(
        config,
        process_environment=process_environment,
        dotenv_environment=dotenv_environment,
    )


def run_preflight(config: JudgeConfig) -> dict[str, Any]:
    """Send one trivial grading request through the shared judge transport."""

    if not config.api_key:
        raise ValueError(f"Judge API key is missing; set {config.api_key_env}.")

    result = judge_answer_sync(
        config=config,
        question=PREFLIGHT_QUESTION,
        gold_answer=PREFLIGHT_ANSWER,
        predicted_answer=PREFLIGHT_ANSWER,
    )
    if not isinstance(result.get("is_correct"), bool):
        raise ValueError('Judge preflight result field "is_correct" was not a boolean')
    return result


def public_preflight_result(
    config: JudgeConfig,
    result: dict[str, Any],
    provenance: Mapping[str, Any],
) -> dict[str, Any]:
    """Project a preflight result without credentials or raw request/response data."""

    return {
        "ok": True,
        **config.public_dict(),
        **provenance,
        "is_correct": result["is_correct"],
        "usage": result.get("usage", {}),
        "cost_estimate_usd": result.get("cost_estimate_usd", {}),
    }


def main() -> int:
    config, provenance = load_judge_config_with_provenance()
    try:
        result = run_preflight(config)
    except (RuntimeError, ValueError) as exc:
        print(f"Judge structured-output preflight failed: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(public_preflight_result(config, result, provenance), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
