#!/usr/bin/env python3
"""Run a configured judge structured-output preflight."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from dci.benchmark.judge import JudgeConfig, judge_answer_sync
from dci.config import load_project_env


REPO_ROOT = Path(__file__).resolve().parents[1]
PREFLIGHT_QUESTION = "What is 1 + 1?"
PREFLIGHT_ANSWER = "2"


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


def public_preflight_result(config: JudgeConfig, result: dict[str, Any]) -> dict[str, Any]:
    """Project a preflight result without credentials or raw request/response data."""

    return {
        "ok": True,
        **config.public_dict(),
        "is_correct": result["is_correct"],
        "usage": result.get("usage", {}),
        "cost_estimate_usd": result.get("cost_estimate_usd", {}),
    }


def main() -> int:
    load_project_env(REPO_ROOT)
    config = JudgeConfig.from_env()
    try:
        result = run_preflight(config)
    except (RuntimeError, ValueError) as exc:
        print(f"Judge structured-output preflight failed: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(public_preflight_result(config, result), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
