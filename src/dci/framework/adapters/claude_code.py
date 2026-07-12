"""Compatibility exports for the Asterion Claude Code protocol adapter."""

from asterion.adapters.claude_code import (
    CLAUDE_CAPABILITY_MAP,
    ClaudeCodeProtocolAdapter,
    map_claude_capabilities,
)

__all__ = (
    "CLAUDE_CAPABILITY_MAP",
    "ClaudeCodeProtocolAdapter",
    "map_claude_capabilities",
)
