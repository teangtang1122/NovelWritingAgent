"""MCP adapter — bridges ToolRegistry to MCP protocol.

Reads ToolDef entries from the existing registry singleton,
applies permission filtering, and converts to MCP schema format.
Does NOT modify the ToolRegistry.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from app.services.workspace.registry import ToolDef, registry
from app.mcp.schemas import McpTool, McpToolResult, tool_def_to_mcp_tool, make_json_result, make_text_result
from app.mcp.permissions import filter_tools, is_allowed

logger = logging.getLogger(__name__)

# Maximum character count before content is truncated in MCP responses.
_CONTENT_TRUNCATE_LIMIT = 12000


def list_mcp_tools(
    *,
    allowed_tiers: set[str] | None = None,
) -> list[McpTool]:
    """Return MCP-formatted tool list, filtered by permission tier.

    Args:
        allowed_tiers: Tier names to allow. Defaults to {"readonly"}.
    """
    if allowed_tiers is None:
        allowed_tiers = {"readonly"}

    all_defs: list[ToolDef] = []
    for name in registry.all_names():
        td = registry.get(name)
        if td is not None:
            all_defs.append(td)

    allowed_defs = filter_tools(all_defs, allowed_tiers=allowed_tiers)

    result: list[McpTool] = []
    for td in allowed_defs:
        result.append(tool_def_to_mcp_tool(
            name=td.name,
            description=td.description,
            input_schema=td.input_schema,
            required=td.required or None,
        ))
    return result


def get_tool_def(name: str) -> ToolDef | None:
    """Look up a ToolDef by name."""
    return registry.get(name)


def is_tool_allowed(name: str, *, allowed_tiers: set[str] | None = None) -> bool:
    """Check whether a tool is allowed under the given tiers."""
    td = registry.get(name)
    if td is None:
        return False
    return is_allowed(td, allowed_tiers=allowed_tiers)


def _truncate_content(text: str, limit: int = _CONTENT_TRUNCATE_LIMIT) -> str:
    """Truncate content and append a notice if it exceeds the limit."""
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n\n[truncated — {len(text)} chars total]"


def _format_tool_result(raw: dict) -> McpToolResult:
    """Convert an execute_workspace_action result dict into an MCP tool result.

    The workspace handler returns:
        {"tool": str, "status": str, "detail": str, "data": Any, "warnings": list?}

    This function:
    - Wraps it as JSON text in the MCP content array.
    - Truncates large content fields.
    - Marks errors when status indicates failure.
    """
    status = raw.get("status", "ok")
    is_error = status not in ("ok",)

    # Build the MCP-friendly payload
    payload: dict[str, Any] = {
        "status": status,
        "detail": raw.get("detail", ""),
    }
    if "data" in raw and raw["data"] is not None:
        payload["data"] = raw["data"]
    if "warnings" in raw and raw["warnings"]:
        payload["warnings"] = raw["warnings"]

    text = json.dumps(payload, ensure_ascii=False, indent=None)
    text = _truncate_content(text)

    return McpToolResult(
        content=[{"type": "text", "text": text}],
        is_error=is_error,
    )


def _log_mcp_tool_call(
    db: Any,
    project_id: str,
    tool_name: str,
    arguments: dict[str, Any],
    *,
    status: str,
    detail: str,
) -> None:
    """Log an MCP tool call to the run log system.

    Creates a lightweight log entry that records the MCP tool name,
    arguments summary, execution status, and any error details.
    """
    try:
        from app.services.workspace.run_log import start_run_step
        # Create a minimal step log for the MCP tool call
        # We don't have a full AssistantRun context, so we create a standalone log
        args_summary = json.dumps(arguments, ensure_ascii=False)[:500]
        logger.info(
            "MCP tool call: tool=%s project=%s status=%s args=%s",
            tool_name, project_id, status, args_summary,
        )
        # If there's an active assistant run in the session context,
        # we could attach to it. For now, log via the standard logger.
        # The run_log integration will be completed when MCP tools are
        # called from within an assistant conversation.
    except Exception:
        # Logging should never break tool execution
        pass


async def execute_tool(
    db: Any,
    project_id: str,
    tool_name: str,
    arguments: dict[str, Any],
    *,
    allowed_tiers: set[str] | None = None,
) -> McpToolResult:
    """Execute an allowed MCP tool and return a structured MCP result.

    Args:
        db: SQLAlchemy session.
        project_id: Current project ID (from MCP client context).
        tool_name: Name of the tool to call.
        arguments: Tool arguments dict.
        allowed_tiers: Permission tiers to allow.

    Returns:
        McpToolResult with structured content.
    """
    if allowed_tiers is None:
        allowed_tiers = {"readonly"}

    # Validate tool exists
    td = get_tool_def(tool_name)
    if td is None:
        return make_text_result(
            json.dumps({"status": "error", "detail": f"Tool not found: {tool_name}"}),
            is_error=True,
        )

    # Validate permission
    if not is_tool_allowed(tool_name, allowed_tiers=allowed_tiers):
        return make_text_result(
            json.dumps({"status": "denied", "detail": f"Permission denied: {tool_name}"}),
            is_error=True,
        )

    # Check confirmation token for write_confirmed tools
    from app.mcp.permissions import get_tier, validate_confirmation_token
    if get_tier(td) == "write_confirmed":
        token_str = arguments.pop("confirmation_token", "")
        is_valid, reason = validate_confirmation_token(token_str, tool_name)
        if not is_valid:
            return make_text_result(
                json.dumps({
                    "status": "denied",
                    "detail": f"Write confirmation required: {reason}",
                    "reason": reason,
                }),
                is_error=True,
            )

    # Execute through the existing workspace executor
    try:
        from app.services.workspace.executor import execute_workspace_action
        raw_result = await execute_workspace_action(
            db,
            project_id,
            {"tool": tool_name, "arguments": arguments},
        )

        # Log the MCP tool call
        _log_mcp_tool_call(
            db, project_id, tool_name, arguments,
            status=raw_result.get("status", "ok"),
            detail=raw_result.get("detail", ""),
        )

        return _format_tool_result(raw_result)
    except Exception as exc:
        logger.exception("MCP tool execution failed: %s", tool_name)

        # Log the failure
        _log_mcp_tool_call(
            db, project_id, tool_name, arguments,
            status="error",
            detail=str(exc)[:500],
        )

        return make_text_result(
            json.dumps({
                "status": "error",
                "detail": f"Tool execution failed: {type(exc).__name__}",
            }),
            is_error=True,
        )
