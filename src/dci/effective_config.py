from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Iterable, Literal, Mapping, MutableMapping

from dotenv import dotenv_values

ValueSource = Literal["invocation", "environment", "runtime-default"]

PI_DEFAULT_PROVIDER = "openai-codex"
PI_DEFAULT_MODEL = "gpt-5.6-luna"
DCI_EFFECTIVE_CONFIG_SCHEMA = "dci.effective-config/v1"
TOP_LEVEL_KEYS = (
    "schema",
    "product",
    "runtime",
    "agent",
    "context",
    "judge",
    "experiment",
    "sources",
    "identity_sha256",
)


def _as_mapping(value: Mapping[str, Any]) -> Mapping[str, Any]:
    return MappingProxyType(dict(value))


def _strip_empty(value: object) -> object:
    if value is None:
        return None
    if isinstance(value, str):
        value = value.strip()
        if value == "":
            return None
        return value
    return value


def _to_int(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        if value < 0:
            raise ValueError("max_turns must be >= 0")
        return value
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None
        converted = int(value)
        if converted < 0:
            raise ValueError("max_turns must be >= 0")
        return converted
    raise TypeError("max_turns must be an int")


def _to_float(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, (float, int)):
        converted = float(value)
    else:
        if not isinstance(value, str):
            raise TypeError("timeout_seconds must be a number")
        value = value.strip()
        if not value:
            return None
        converted = float(value)
    if converted < 0:
        raise ValueError("timeout_seconds must be >= 0")
    return converted


def _canonical_json_bytes(value: Mapping[str, object]) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _canonicalize_sources(value: Mapping[str, ValueSource]) -> Mapping[str, ValueSource]:
    return MappingProxyType({str(key): str(source) for key, source in value.items()})


def _check_no_private_keys(value: Mapping[str, object]) -> None:
    forbidden_key_terms = (
        "api_key",
        "api-key",
        "password",
        "secret",
        "private_key",
        "credential",
        "token",
        "prompt",
        "answer",
        "body",
        "tool_result",
        "tool_results",
    )

    def walk(prefix: str, payload: Any) -> None:
        if isinstance(payload, Mapping):
            for key, nested in payload.items():
                key_lower = str(key).lower().replace("-", "_")
                forbidden = False
                for term in forbidden_key_terms:
                    if term in key_lower:
                        forbidden = True
                        if term == "api_key" and key_lower.endswith("_env"):
                            forbidden = False
                        break
                if forbidden:
                    # Explicitly allow key-name metadata when the value is an env-var holder.
                    raise ValueError(f"private key-like field is not allowed: {key}")
                walk(f"{prefix}.{key}" if prefix else str(key), nested)
        elif isinstance(payload, list):
            for item in payload:
                walk(prefix, item)
        elif isinstance(payload, str):
            if payload.startswith(("/", "C:\\", "\\\\")):
                raise ValueError(f"absolute private path is not allowed: {prefix}")
    walk("", value)


def _check_top_level_fields(payload: Mapping[str, object]) -> None:
    unknown = set(payload.keys()) - set(TOP_LEVEL_KEYS)
    if unknown:
        raise ValueError(f"unexpected top-level keys in effective config: {sorted(unknown)}")
    missing = set(TOP_LEVEL_KEYS) - set(payload.keys())
    if missing:
        raise ValueError(f"effective config is missing keys: {sorted(missing)}")
    if payload["schema"] != DCI_EFFECTIVE_CONFIG_SCHEMA:
        raise ValueError("effective config schema must be dci.effective-config/v1")
    if not isinstance(payload.get("runtime"), Mapping):
        raise ValueError("runtime must be an object")
    if not isinstance(payload.get("agent"), Mapping):
        raise ValueError("agent must be an object")
    if not isinstance(payload.get("context"), Mapping):
        raise ValueError("context must be an object")
    if not isinstance(payload.get("judge"), Mapping):
        raise ValueError("judge must be an object")
    if not isinstance(payload.get("experiment"), Mapping):
        raise ValueError("experiment must be an object")
    if not isinstance(payload.get("sources"), Mapping):
        raise ValueError("sources must be an object")
    if not all(
        source in ("invocation", "environment", "runtime-default")
        for source in payload["sources"].values()
    ):
        raise ValueError("invalid source value in effective config")


@dataclass(frozen=True)
class ConfigLayers:
    process: Mapping[str, str]
    dotenv: Mapping[str, str]

    @classmethod
    def from_repo(
        cls, repo_root: Path, process_environment: Mapping[str, str] | None = None
    ) -> "ConfigLayers":
        process = dict(os.environ if process_environment is None else process_environment)
        loaded = dotenv_values(Path(repo_root) / ".env")
        dotenv = {key: value for key, value in loaded.items() if value is not None}
        return cls(process=_as_mapping(process), dotenv=_as_mapping(dotenv))

    def resolve(self, name: str, invocation: object, default: object) -> tuple[object, ValueSource]:
        if invocation not in (None, ""):
            return invocation, "invocation"
        if name in self.process:
            return self.process[name], "environment"
        if name in self.dotenv:
            return self.dotenv[name], "environment"
        return default, "runtime-default"

    def materialize(self, target: MutableMapping[str, str]) -> None:
        for key, value in self.dotenv.items():
            target.setdefault(key, value)


@dataclass(frozen=True)
class OriginalRuntimeConfig:
    runtime: str
    provider: str
    model: str
    tools: str
    max_turns: int | None
    timeout_seconds: float | None
    thinking_level: str | None
    context_profile: str | None
    sources: Mapping[str, ValueSource]

    def _to_payload_without_identity(
        self,
        *,
        judge: Mapping[str, object] | None = None,
        experiment: Mapping[str, object] | None = None,
    ) -> dict[str, object]:
        judge_payload = _as_mapping(judge or {})
        experiment_payload = _as_mapping(experiment or {})
        return {
            "schema": DCI_EFFECTIVE_CONFIG_SCHEMA,
            "product": "original-dci",
            "runtime": {
                "runtime": self.runtime,
            },
            "agent": {
                "provider": self.provider,
                "model": self.model,
                "tools": self.tools,
                "max_turns": self.max_turns,
                "timeout_seconds": self.timeout_seconds,
                "thinking_level": self.thinking_level,
                "context_profile": self.context_profile,
            },
            "context": {
                "context_profile": self.context_profile,
                "thinking_level": self.thinking_level,
            },
            "judge": dict(judge_payload),
            "experiment": dict(experiment_payload),
            "sources": dict(_canonicalize_sources(self.sources)),
        }

    def to_public_dict(
        self,
        *,
        judge: Mapping[str, object] | None = None,
        experiment: Mapping[str, object] | None = None,
    ) -> dict[str, object]:
        payload = self._to_payload_without_identity(judge=judge, experiment=experiment)
        payload["identity_sha256"] = hashlib.sha256(_canonical_json_bytes(payload)).hexdigest()
        _check_top_level_fields(payload)
        _check_no_private_keys(payload)
        return payload


def _resolve_text(
    layers: ConfigLayers, layers_name: str, invocation: object, default: str | None
) -> tuple[str | None, ValueSource]:
    value, source = layers.resolve(layers_name, _strip_empty(invocation), default)
    if value is None:
        return None, source
    if isinstance(value, str):
        normalized = value.strip()
        if normalized == "" and default is not None:
            return default, "runtime-default"
        return normalized, source
    raise TypeError(f"{layers_name} must be a string")


def _resolve_int(
    layers: ConfigLayers, layers_name: str, invocation: object, default: int | None
) -> tuple[int | None, ValueSource]:
    value, source = layers.resolve(layers_name, _strip_empty(invocation), default)
    if value is None:
        return default, source
    converted = _to_int(value)
    if converted is None:
        if default is None:
            return None, source
        return default, "runtime-default"
    return converted, source


def _resolve_float(
    layers: ConfigLayers, layers_name: str, invocation: object, default: float | None
) -> tuple[float | None, ValueSource]:
    value, source = layers.resolve(layers_name, _strip_empty(invocation), default)
    if value is None:
        return default, source
    converted = _to_float(value)
    if converted is None:
        if default is None:
            return None, source
        return default, "runtime-default"
    return converted, source


def _resolve_source_override(
    invocation_keys: Iterable[str], invocation: Mapping[str, object], layers: ConfigLayers, env_name: str, default: object
) -> tuple[object, ValueSource]:
    value = None
    for name in invocation_keys:
        value = invocation.get(name)
        if value is not None:
            break
    value = _strip_empty(value)
    return layers.resolve(env_name, value, default)


def _resolve_optional_setting(
    layers: ConfigLayers,
    invocation: Mapping[str, object],
    invocation_keys: Iterable[str],
    env_name: str,
    default: str | None,
) -> tuple[str | None, ValueSource]:
    value, source = _resolve_source_override(invocation_keys, invocation, layers, env_name, default)
    if value is None:
        return None, source
    if isinstance(value, str):
        normalized = value.strip()
        if normalized == "":
            return None, "runtime-default" if default is None else "runtime-default"
        return normalized, source
    return str(value), source


def resolve_original_runtime(
    invocation: Mapping[str, object], layers: ConfigLayers
) -> OriginalRuntimeConfig:
    runtime, runtime_source = _resolve_text(
        layers=layers,
        layers_name="DCI_RUNTIME",
        invocation=invocation.get("runtime"),
        default="pi",
    )
    if runtime is None:
        runtime = "pi"
        runtime_source = "runtime-default"
    if runtime != "pi":
        raise ValueError(
            f"Original DCI runtime is unsupported: {runtime_source}:{runtime}"
        )

    provider, provider_source = _resolve_text(
        layers=layers,
        layers_name="DCI_PROVIDER",
        invocation=invocation.get("provider"),
        default=PI_DEFAULT_PROVIDER,
    )
    if provider is None:
        provider = PI_DEFAULT_PROVIDER
        provider_source = "runtime-default"

    model, model_source = _resolve_text(
        layers=layers,
        layers_name="DCI_MODEL",
        invocation=invocation.get("model"),
        default=PI_DEFAULT_MODEL,
    )
    if model is None:
        model = PI_DEFAULT_MODEL
        model_source = "runtime-default"

    tools, tools_source = _resolve_text(
        layers=layers,
        layers_name="DCI_PI_TOOLS",
        invocation=invocation.get("tools"),
        default="read,bash",
    )
    if tools is None:
        tools = "read,bash"
        tools_source = "runtime-default"

    max_turns, max_turns_source = _resolve_int(
        layers=layers,
        layers_name="DCI_MAX_TURNS",
        invocation=invocation.get("max_turns"),
        default=None,
    )
    timeout_seconds, timeout_source = _resolve_float(
        layers=layers,
        layers_name="DCI_RPC_TIMEOUT_SECONDS",
        invocation=invocation.get("rpc_timeout_seconds"),
        default=3600.0,
    )

    thinking_level, thinking_source = _resolve_optional_setting(
        layers=layers,
        invocation=invocation,
        invocation_keys=("thinking_level",),
        env_name="DCI_PI_THINKING_LEVEL",
        default=None,
    )
    context_profile, context_source = _resolve_optional_setting(
        layers=layers,
        invocation=invocation,
        invocation_keys=("runtime_context_level", "context_profile"),
        env_name="DCI_RUNTIME_CONTEXT_LEVEL",
        default=None,
    )

    sources = {
        "runtime": runtime_source,
        "agent.provider": provider_source,
        "agent.model": model_source,
        "agent.tools": tools_source,
        "agent.max_turns": max_turns_source,
        "agent.timeout_seconds": timeout_source,
        "agent.thinking_level": thinking_source,
        "agent.context_profile": context_source,
    }

    return OriginalRuntimeConfig(
        runtime=runtime,
        provider=provider,
        model=model,
        tools=tools,
        max_turns=max_turns,
        timeout_seconds=timeout_seconds,
        thinking_level=thinking_level,
        context_profile=context_profile,
        sources=MappingProxyType(sources),
    )
