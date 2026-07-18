"""Credential- and body-free effective configuration evidence for original DCI."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import Mapping

from dci.config import OriginalRuntimeConfig, ValueSource


SCHEMA = "dci.effective-config/v1"
PRODUCT = "original-dci"
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


def _safe_mapping(value: Mapping[str, object], *, location: str) -> dict[str, object]:
    cloned = json.loads(json.dumps(dict(value), ensure_ascii=False))

    def validate(item: object, path: str) -> None:
        if isinstance(item, dict):
            for key, nested in item.items():
                if _UNSAFE_KEY.search(str(key)):
                    raise ValueError(f"unsafe effective configuration field at {path}.{key}")
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
        return projection
