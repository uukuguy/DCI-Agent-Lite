"""Credential- and body-free effective configuration evidence for original DCI."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping
from urllib.parse import urlsplit

from dci.config import OriginalRuntimeConfig, ValueSource


SCHEMA = "dci.effective-config/v1"
PRODUCT = "original-dci"
SCHEMA_PATH = Path(__file__).with_name("effective-config.schema.json")
_UNSAFE_KEY = re.compile(
    r"(^|_)(api_?key|credential|secret|token|password|prompt|answer|body|path|dir)($|_)",
    re.IGNORECASE,
)


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _validate_safe_endpoint(value: str, *, path: str) -> None:
    try:
        parsed = urlsplit(value)
        parsed.port
    except ValueError as exc:
        raise ValueError(f"unsafe judge endpoint at {path}") from exc
    if (
        parsed.scheme not in {"http", "https"}
        or parsed.hostname is None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError(f"unsafe judge endpoint at {path}")


def _matches_schema_type(value: object, expected: str) -> bool:
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "null":
        return value is None
    raise ValueError(f"effective configuration schema uses unsupported type {expected!r}")


def _validate_against_schema(
    value: object, schema: Mapping[str, object], *, path: str
) -> None:
    expected_types = schema.get("type")
    if expected_types is not None:
        type_names = (
            [expected_types] if isinstance(expected_types, str) else expected_types
        )
        if not isinstance(type_names, list) or not all(
            isinstance(item, str) for item in type_names
        ):
            raise ValueError("effective configuration schema has invalid type declaration")
        if not any(_matches_schema_type(value, item) for item in type_names):
            raise ValueError(f"effective configuration schema rejected {path}: invalid type")
    if "const" in schema and value != schema["const"]:
        raise ValueError(f"effective configuration schema rejected {path}: const mismatch")
    enum = schema.get("enum")
    if enum is not None and (not isinstance(enum, list) or value not in enum):
        raise ValueError(f"effective configuration schema rejected {path}: invalid value")

    if isinstance(value, dict):
        required = schema.get("required", [])
        if not isinstance(required, list) or not all(
            isinstance(item, str) for item in required
        ):
            raise ValueError("effective configuration schema has invalid required fields")
        missing = set(required) - value.keys()
        if missing:
            raise ValueError(
                f"effective configuration schema rejected {path}: missing {sorted(missing)}"
            )
        properties = schema.get("properties", {})
        if not isinstance(properties, dict):
            raise ValueError("effective configuration schema has invalid properties")
        additional = schema.get("additionalProperties", True)
        for key, nested in value.items():
            child_schema = properties.get(key)
            if child_schema is None:
                if additional is False:
                    raise ValueError(
                        f"effective configuration schema rejected {path}: unknown field {key}"
                    )
                child_schema = additional if isinstance(additional, dict) else None
            if child_schema is not None:
                if not isinstance(child_schema, dict):
                    raise ValueError("effective configuration schema has invalid property")
                _validate_against_schema(nested, child_schema, path=f"{path}.{key}")

    if isinstance(value, str):
        minimum_length = schema.get("minLength")
        if isinstance(minimum_length, int) and len(value) < minimum_length:
            raise ValueError(f"effective configuration schema rejected {path}: too short")
        pattern = schema.get("pattern")
        if isinstance(pattern, str) and re.search(pattern, value) is None:
            raise ValueError(f"effective configuration schema rejected {path}: pattern")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        minimum = schema.get("minimum")
        if isinstance(minimum, (int, float)) and value < minimum:
            raise ValueError(f"effective configuration schema rejected {path}: minimum")
        exclusive_minimum = schema.get("exclusiveMinimum")
        if isinstance(exclusive_minimum, (int, float)) and value <= exclusive_minimum:
            raise ValueError(
                f"effective configuration schema rejected {path}: exclusive minimum"
            )


def validate_effective_config(value: Mapping[str, object]) -> None:
    try:
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("effective configuration schema could not be loaded") from exc
    if not isinstance(schema, dict):
        raise ValueError("effective configuration schema must be an object")
    _validate_against_schema(dict(value), schema, path="effective-config")


def _safe_mapping(value: Mapping[str, object], *, location: str) -> dict[str, object]:
    cloned = json.loads(json.dumps(dict(value), ensure_ascii=False))

    def validate(item: object, path: str) -> None:
        if isinstance(item, dict):
            for key, nested in item.items():
                if _UNSAFE_KEY.search(str(key)):
                    raise ValueError(f"unsafe effective configuration field at {path}.{key}")
                if key == "endpoint" and isinstance(nested, str):
                    _validate_safe_endpoint(nested, path=f"{path}.{key}")
                validate(nested, f"{path}.{key}")
        elif isinstance(item, list):
            for index, nested in enumerate(item):
                validate(nested, f"{path}[{index}]")
        elif isinstance(item, str) and item.startswith(("/", "~/")):
            raise ValueError(f"unsafe absolute/private path at {path}")

    validate(cloned, location)
    return cloned


@dataclass(frozen=True)
class OriginalEffectiveConfig:
    runtime: OriginalRuntimeConfig
    context: Mapping[str, object] = field(default_factory=dict)
    judge: Mapping[str, object] = field(default_factory=dict)
    experiment: Mapping[str, object] = field(default_factory=dict)
    sources: Mapping[str, ValueSource] = field(default_factory=dict)

    def to_public_dict(self) -> dict[str, object]:
        agent = {
            "provider": self.runtime.provider,
            "model": self.runtime.model,
            "reasoning": self.runtime.thinking_level,
            "tools": self.runtime.tools,
            "max_turns": self.runtime.max_turns,
            "timeout_seconds": self.runtime.timeout_seconds,
        }
        source_values = dict(self.runtime.sources)
        source_values.update(self.sources)
        projection: dict[str, object] = {
            "schema": SCHEMA,
            "product": PRODUCT,
            "runtime": self.runtime.runtime,
            "agent": _safe_mapping(agent, location="agent"),
            "context": _safe_mapping(self.context, location="context"),
            "judge": _safe_mapping(self.judge, location="judge"),
            "experiment": _safe_mapping(self.experiment, location="experiment"),
            "sources": _safe_mapping(source_values, location="sources"),
        }
        projection["identity_sha256"] = hashlib.sha256(
            _canonical_bytes(projection)
        ).hexdigest()
        validate_effective_config(projection)
        return projection
