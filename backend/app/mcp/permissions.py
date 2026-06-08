"""MCP permission filter.

Enforces which tools are exposed to MCP clients based on permission tiers.
The filter is applied at both tools/list time and tools/call time.

Permission tiers:
  - readonly:   read, analysis, web, and memory-read tools
  - draft:      generator tools (no DB writes)
  - write_confirmed: database-mutating tools — requires confirmation token
"""
from __future__ import annotations

import re
import secrets
import time
from dataclasses import dataclass, field
from typing import Any

from app.services.workspace.registry import ToolDef

# ── Tier assignment by tool_type ─────────────────────────────────────────

_TIER_MAP: dict[str, str] = {
    "read": "readonly",
    "analysis": "readonly",
    "web": "readonly",
    "memory": "readonly",   # recall / list_memories only; write memory is draft
    "generator": "draft",
    "write": "write_confirmed",
    "scheduler": "write_confirmed",
}

# Specific tools that belong to readonly even though their type maps higher,
# or that belong to a higher tier even though their type is read.
_TIER_OVERRIDES: dict[str, str] = {
    "remember": "draft",
    "forget": "write_confirmed",
}

# ── Secret-related deny patterns ─────────────────────────────────────────

_SECRET_PATTERNS: list[re.Pattern[str]] = [
    re.compile(p, re.IGNORECASE) for p in [
        r"api_key",
        r"secret",
        r"credential",
        r"token",
        r"password",
    ]
]


def get_tier(tool_def: ToolDef) -> str:
    """Return the permission tier for a tool."""
    if tool_def.name in _TIER_OVERRIDES:
        return _TIER_OVERRIDES[tool_def.name]
    return _TIER_MAP.get(tool_def.tool_type, "write_confirmed")


def is_secret_tool(name: str) -> bool:
    """Return True if the tool name matches a secret-management pattern."""
    return any(p.search(name) for p in _SECRET_PATTERNS)


def is_allowed(
    tool_def: ToolDef,
    *,
    allowed_tiers: set[str] | None = None,
) -> bool:
    """Return True if the tool is allowed under the given tier set.

    Args:
        tool_def: The tool to check.
        allowed_tiers: Set of tier names to allow. Defaults to {"readonly"}.
    """
    if allowed_tiers is None:
        allowed_tiers = {"readonly"}

    # Secret tools are always denied regardless of tier.
    if is_secret_tool(tool_def.name):
        return False

    return get_tier(tool_def) in allowed_tiers


def filter_tools(
    tool_defs: list[ToolDef],
    *,
    allowed_tiers: set[str] | None = None,
) -> list[ToolDef]:
    """Return only the tools allowed under the given tier set."""
    return [td for td in tool_defs if is_allowed(td, allowed_tiers=allowed_tiers)]


# ── Confirmation token model ─────────────────────────────────────────────

_TOKEN_TTL_SECONDS = 300  # 5 minutes


@dataclass
class ConfirmationToken:
    """A single-use token that authorizes one specific write tool call."""
    token: str
    tool_name: str
    created_at: float
    used: bool = False


# In-memory token store. In production this would be backed by Redis or DB.
_tokens: dict[str, ConfirmationToken] = {}


def issue_confirmation_token(tool_name: str) -> str:
    """Issue a new confirmation token for a specific tool.

    Args:
        tool_name: The exact tool name this token authorizes.

    Returns:
        A secure token string.
    """
    token_str = secrets.token_urlsafe(32)
    _tokens[token_str] = ConfirmationToken(
        token=token_str,
        tool_name=tool_name,
        created_at=time.time(),
    )
    return token_str


def validate_confirmation_token(token_str: str, tool_name: str) -> tuple[bool, str]:
    """Validate a confirmation token for a specific tool call.

    Args:
        token_str: The token string to validate.
        tool_name: The tool being called (must match the token's tool).

    Returns:
        (is_valid, reason) — reason is empty if valid.
    """
    if not token_str:
        return False, "confirmation_required"

    ct = _tokens.get(token_str)
    if ct is None:
        return False, "invalid_token"

    if ct.used:
        return False, "token_already_used"

    if time.time() - ct.created_at > _TOKEN_TTL_SECONDS:
        _tokens.pop(token_str, None)
        return False, "token_expired"

    if ct.tool_name != tool_name:
        return False, "token_tool_mismatch"

    # Mark as used (single-use)
    ct.used = True
    return True, ""


def revoke_token(token_str: str) -> bool:
    """Revoke a token. Returns True if the token existed."""
    return _tokens.pop(token_str, None) is not None


def clear_expired_tokens() -> int:
    """Remove expired tokens from the store. Returns count removed."""
    now = time.time()
    expired = [
        k for k, v in _tokens.items()
        if now - v.created_at > _TOKEN_TTL_SECONDS
    ]
    for k in expired:
        _tokens.pop(k, None)
    return len(expired)
