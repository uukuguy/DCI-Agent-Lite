"""OpenAI-compatible benchmark judge configuration and transport."""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


DEFAULT_JUDGE_BASE_URL = "https://api.openai.com/v1"
DEFAULT_JUDGE_API = "responses"
DEFAULT_JUDGE_MODEL = "gpt-5.4-nano"
DEFAULT_JUDGE_TIMEOUT_SECONDS = 120
DEFAULT_JUDGE_INPUT_PRICE_PER_1M = 0.20
DEFAULT_JUDGE_CACHED_INPUT_PRICE_PER_1M = 0.02
DEFAULT_JUDGE_OUTPUT_PRICE_PER_1M = 1.25
JUDGE_ENV_PREFIX = "DCI_EVAL_JUDGE_"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _env_int(name: str, default: int) -> int:
    raw_value = os.environ.get(name)
    if raw_value is None or not raw_value.strip():
        return default
    try:
        return int(raw_value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer, got {raw_value!r}") from exc


def _env_float(name: str, default: float) -> float:
    raw_value = os.environ.get(name)
    if raw_value is None or not raw_value.strip():
        return default
    try:
        return float(raw_value)
    except ValueError as exc:
        raise ValueError(f"{name} must be a number, got {raw_value!r}") from exc


def normalize_judge_api(value: str) -> str:
    normalized = value.strip().lower().replace("_", "-")
    aliases = {
        "response": "responses",
        "responses": "responses",
        "chat": "chat-completions",
        "chat-completion": "chat-completions",
        "chat-completions": "chat-completions",
        "completions": "chat-completions",
    }
    try:
        return aliases[normalized]
    except KeyError as exc:
        raise ValueError(
            f"Unsupported judge API {value!r}; expected 'responses' or 'chat-completions'"
        ) from exc


@dataclass(frozen=True)
class JudgeConfig:
    base_url: str = DEFAULT_JUDGE_BASE_URL
    api: str = DEFAULT_JUDGE_API
    model: str = DEFAULT_JUDGE_MODEL
    timeout_seconds: int = DEFAULT_JUDGE_TIMEOUT_SECONDS
    input_price_per_1m: float = DEFAULT_JUDGE_INPUT_PRICE_PER_1M
    cached_input_price_per_1m: float = DEFAULT_JUDGE_CACHED_INPUT_PRICE_PER_1M
    output_price_per_1m: float = DEFAULT_JUDGE_OUTPUT_PRICE_PER_1M
    api_key_env: str = "OPENAI_API_KEY"
    api_key: str = field(default="", repr=False)

    def __post_init__(self) -> None:
        base_url = self.base_url.strip().rstrip("/")
        model = self.model.strip()
        api_key_env = self.api_key_env.strip()
        if not base_url:
            raise ValueError("Judge base URL must not be empty")
        if not model:
            raise ValueError("Judge model must not be empty")
        if self.timeout_seconds <= 0:
            raise ValueError("Judge timeout must be greater than zero")
        if (
            min(
                self.input_price_per_1m,
                self.cached_input_price_per_1m,
                self.output_price_per_1m,
            )
            < 0
        ):
            raise ValueError("Judge token prices must not be negative")
        object.__setattr__(self, "base_url", base_url)
        object.__setattr__(self, "api", normalize_judge_api(self.api))
        object.__setattr__(self, "model", model)
        object.__setattr__(self, "api_key_env", api_key_env)

    @classmethod
    def from_env(
        cls,
        *,
        base_url: Optional[str] = None,
        api: Optional[str] = None,
        model: Optional[str] = None,
        timeout_seconds: Optional[int] = None,
        input_price_per_1m: Optional[float] = None,
        cached_input_price_per_1m: Optional[float] = None,
        output_price_per_1m: Optional[float] = None,
        api_key_env: Optional[str] = None,
    ) -> "JudgeConfig":
        resolved_base_url = (
            base_url
            if base_url is not None
            else os.environ.get(f"{JUDGE_ENV_PREFIX}BASE_URL", DEFAULT_JUDGE_BASE_URL)
        )
        uses_official_openai = (
            resolved_base_url.strip().rstrip("/") == DEFAULT_JUDGE_BASE_URL
        )
        default_input_price = (
            DEFAULT_JUDGE_INPUT_PRICE_PER_1M if uses_official_openai else 0.0
        )
        default_cached_input_price = (
            DEFAULT_JUDGE_CACHED_INPUT_PRICE_PER_1M if uses_official_openai else 0.0
        )
        default_output_price = (
            DEFAULT_JUDGE_OUTPUT_PRICE_PER_1M if uses_official_openai else 0.0
        )
        resolved_api_key_env = api_key_env or os.environ.get(
            f"{JUDGE_ENV_PREFIX}API_KEY_ENV", "OPENAI_API_KEY"
        )
        api_key = os.environ.get(f"{JUDGE_ENV_PREFIX}API_KEY", "").strip()
        if not api_key and resolved_api_key_env:
            api_key = os.environ.get(resolved_api_key_env, "").strip()

        return cls(
            base_url=resolved_base_url,
            api=api
            if api is not None
            else os.environ.get(f"{JUDGE_ENV_PREFIX}API", DEFAULT_JUDGE_API),
            model=model
            if model is not None
            else os.environ.get(f"{JUDGE_ENV_PREFIX}MODEL", DEFAULT_JUDGE_MODEL),
            timeout_seconds=timeout_seconds
            if timeout_seconds is not None
            else _env_int(
                f"{JUDGE_ENV_PREFIX}TIMEOUT_SECONDS", DEFAULT_JUDGE_TIMEOUT_SECONDS
            ),
            input_price_per_1m=input_price_per_1m
            if input_price_per_1m is not None
            else _env_float(
                f"{JUDGE_ENV_PREFIX}INPUT_PRICE_PER_1M",
                default_input_price,
            ),
            cached_input_price_per_1m=cached_input_price_per_1m
            if cached_input_price_per_1m is not None
            else _env_float(
                f"{JUDGE_ENV_PREFIX}CACHED_INPUT_PRICE_PER_1M",
                default_cached_input_price,
            ),
            output_price_per_1m=output_price_per_1m
            if output_price_per_1m is not None
            else _env_float(
                f"{JUDGE_ENV_PREFIX}OUTPUT_PRICE_PER_1M",
                default_output_price,
            ),
            api_key_env=resolved_api_key_env,
            api_key=api_key,
        )

    @property
    def endpoint(self) -> str:
        suffix = "responses" if self.api == "responses" else "chat/completions"
        return f"{self.base_url}/{suffix}"

    def public_dict(self) -> Dict[str, Any]:
        """Return safe-to-persist configuration without the API key."""

        return {
            "judge_base_url": self.base_url,
            "judge_api": self.api,
            "judge_model": self.model,
            "judge_api_key_env": self.api_key_env,
            "judge_timeout_seconds": self.timeout_seconds,
            "judge_input_price_per_1m": self.input_price_per_1m,
            "judge_cached_input_price_per_1m": self.cached_input_price_per_1m,
            "judge_output_price_per_1m": self.output_price_per_1m,
        }


def estimate_judge_cost(usage: Dict[str, Any], config: JudgeConfig) -> Dict[str, float]:
    input_tokens = float(usage.get("input_tokens", 0) or 0)
    output_tokens = float(usage.get("output_tokens", 0) or 0)
    input_details = usage.get("input_tokens_details") or {}
    cached_input_tokens = float(input_details.get("cached_tokens", 0) or 0)
    non_cached_input_tokens = max(0.0, input_tokens - cached_input_tokens)
    input_cost = (non_cached_input_tokens / 1_000_000.0) * config.input_price_per_1m
    cached_input_cost = (
        cached_input_tokens / 1_000_000.0
    ) * config.cached_input_price_per_1m
    output_cost = (output_tokens / 1_000_000.0) * config.output_price_per_1m
    return {
        "input_cost": input_cost,
        "cached_input_cost": cached_input_cost,
        "output_cost": output_cost,
        "total_cost": input_cost + cached_input_cost + output_cost,
    }


def extract_responses_text(response_payload: Dict[str, Any]) -> str:
    output_text = response_payload.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        return output_text.strip()

    texts: List[str] = []
    for item in response_payload.get("output", []):
        if not isinstance(item, dict):
            continue
        content = item.get("content", [])
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict):
                continue
            text_value = block.get("text")
            if isinstance(text_value, str):
                texts.append(text_value)
            elif isinstance(text_value, dict) and isinstance(
                text_value.get("value"), str
            ):
                texts.append(text_value["value"])
    return "\n".join(part.strip() for part in texts if part and part.strip()).strip()


def extract_chat_completions_text(response_payload: Dict[str, Any]) -> str:
    choices = response_payload.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        return ""
    message = choices[0].get("message")
    if not isinstance(message, dict):
        return ""
    content = message.get("content")
    if isinstance(content, str):
        return content.strip()
    if not isinstance(content, list):
        return ""

    texts: List[str] = []
    for block in content:
        if isinstance(block, str):
            texts.append(block)
        elif isinstance(block, dict):
            text_value = block.get("text")
            if isinstance(text_value, str):
                texts.append(text_value)
            elif isinstance(text_value, dict) and isinstance(
                text_value.get("value"), str
            ):
                texts.append(text_value["value"])
    return "\n".join(part.strip() for part in texts if part and part.strip()).strip()


def extract_json_object(text: str) -> Dict[str, Any]:
    try:
        payload = json.loads(text)
        if isinstance(payload, dict):
            return payload
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not match:
        raise ValueError("Judge response did not contain a JSON object")
    payload = json.loads(match.group(0))
    if not isinstance(payload, dict):
        raise ValueError("Judge response JSON was not an object")
    return payload


def normalize_usage(raw_usage: Any) -> Dict[str, Any]:
    if not isinstance(raw_usage, dict):
        return {}
    input_tokens = raw_usage.get("input_tokens", raw_usage.get("prompt_tokens", 0)) or 0
    output_tokens = (
        raw_usage.get("output_tokens", raw_usage.get("completion_tokens", 0)) or 0
    )
    input_details = (
        raw_usage.get(
            "input_tokens_details", raw_usage.get("prompt_tokens_details", {})
        )
        or {}
    )
    usage = dict(raw_usage)
    usage["input_tokens"] = input_tokens
    usage["output_tokens"] = output_tokens
    usage["total_tokens"] = (
        raw_usage.get("total_tokens", input_tokens + output_tokens) or 0
    )
    if input_details:
        usage["input_tokens_details"] = input_details
    return usage


def _judge_prompts(
    question: str, gold_answer: str, predicted_answer: str
) -> tuple[str, str]:
    system_prompt = (
        "You are grading a question-answer benchmark. "
        "Mark the prediction correct only if it identifies the same final answer as the gold answer. "
        "Ignore case, surrounding punctuation, whitespace, and extra explanation or supporting file paths. "
        "Do not give partial credit. Return exactly one compact JSON object."
    )
    user_prompt = (
        f"Question:\n{question}\n\n"
        f"Gold answer:\n{gold_answer}\n\n"
        f"Predicted answer:\n{predicted_answer or '[empty]'}\n\n"
        'Return JSON with keys "is_correct" (boolean), "normalized_prediction" (string), and "reason" (string).'
    )
    return system_prompt, user_prompt


def build_judge_request(
    config: JudgeConfig, *, question: str, gold_answer: str, predicted_answer: str
) -> Dict[str, Any]:
    system_prompt, user_prompt = _judge_prompts(question, gold_answer, predicted_answer)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    if config.api == "responses":
        return {
            "model": config.model,
            "max_output_tokens": 180,
            "input": messages,
        }
    return {
        "model": config.model,
        "max_tokens": 180,
        "messages": messages,
    }


def judge_answer_sync(
    *,
    config: JudgeConfig,
    question: str,
    gold_answer: str,
    predicted_answer: str,
) -> Dict[str, Any]:
    request_payload = build_judge_request(
        config,
        question=question,
        gold_answer=gold_answer,
        predicted_answer=predicted_answer,
    )
    headers = {"Content-Type": "application/json"}
    if config.api_key:
        headers["Authorization"] = f"Bearer {config.api_key}"
    request = urllib.request.Request(
        config.endpoint,
        data=json.dumps(request_payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )

    try:
        with urllib.request.urlopen(
            request, timeout=config.timeout_seconds
        ) as response:
            response_payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"Judge request to {config.endpoint} failed with HTTP {exc.code}: {error_body}"
        ) from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Judge request to {config.endpoint} failed: {exc}") from exc

    response_text = (
        extract_responses_text(response_payload)
        if config.api == "responses"
        else extract_chat_completions_text(response_payload)
    )
    if not response_text:
        raise ValueError(f"Judge {config.api} response did not contain text")
    parsed = extract_json_object(response_text)
    is_correct = parsed.get("is_correct")
    if not isinstance(is_correct, bool):
        raise ValueError('Judge response field "is_correct" was not a boolean')
    usage = normalize_usage(response_payload.get("usage"))

    return {
        "judge_model": config.model,
        "judge_base_url": config.base_url,
        "judge_api": config.api,
        "judged_at": _utc_now(),
        "question": question,
        "gold_answer": gold_answer,
        "predicted_answer": predicted_answer,
        "is_correct": is_correct,
        "normalized_prediction": str(parsed.get("normalized_prediction", "")),
        "reason": str(parsed.get("reason", "")),
        "usage": usage,
        "cost_estimate_usd": estimate_judge_cost(usage, config),
        "raw_response_text": response_text,
        "raw_response": response_payload,
    }
