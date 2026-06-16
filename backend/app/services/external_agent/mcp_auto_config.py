"""Automatic Moshu MCP client configuration for trusted local CLI providers.

The standalone PowerShell setup script remains available, but desktop users
should not need to find it. When a local CLI provider is configured, Moshu can
best-effort add the Moshu MCP server to the matching client while preserving
the user's other MCP servers and settings.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from app.ai.local_cli_adapter import hidden_subprocess_kwargs


LOCAL_MCP_PROVIDERS = {"claude_cli", "codex_cli", "opencode_cli"}
DEFAULT_PERMISSION_PACK = "auto"


def auto_configure_mcp_for_provider(
    provider: str,
    *,
    cli_command: str | None = None,
    permission_pack: str = DEFAULT_PERMISSION_PACK,
) -> dict[str, Any]:
    """Best-effort MCP setup for the selected local CLI provider.

    This function never raises for ordinary configuration failures. Saving the
    model provider must continue even if Claude/Codex is not installed.
    """

    if os.environ.get("MOSHU_DISABLE_AUTO_MCP_SETUP") == "1":
        return {
            "enabled": False,
            "provider": provider,
            "status": "skipped",
            "detail": "Disabled by MOSHU_DISABLE_AUTO_MCP_SETUP",
        }

    provider = (provider or "").strip()
    if provider not in LOCAL_MCP_PROVIDERS:
        return {
            "enabled": False,
            "provider": provider,
            "status": "skipped",
            "detail": "No automatic MCP setup for this provider",
        }

    server = _resolve_moshu_mcp_server(permission_pack=permission_pack)
    if provider == "claude_cli":
        client = _configure_claude_code(server, cli_command=cli_command)
    elif provider == "opencode_cli":
        client = _configure_opencode(server)
    else:
        client = _configure_codex(server)

    return {
        "enabled": True,
        "provider": provider,
        "permission_pack": permission_pack,
        "server": {
            "mode": server["mode"],
            "command": server["command"],
            "args": server["args"],
        },
        "clients": [client],
        "status": client["status"],
        "detail": client["detail"],
    }


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _resolve_moshu_mcp_server(*, permission_pack: str) -> dict[str, Any]:
    if getattr(sys, "frozen", False):
        return {
            "mode": "exe",
            "command": str(Path(sys.executable).resolve()),
            "args": ["--mcp-server", "--permission-pack", permission_pack],
            "cwd": "",
        }

    root = _repo_root()
    entry = root / "scripts" / "moshu-mcp-server.py"
    if entry.exists():
        return {
            "mode": "source",
            "command": str(Path(sys.executable).resolve()),
            "args": [str(entry.resolve()), "--permission-pack", permission_pack],
            "cwd": str(root),
        }

    # Last-resort fallback for unusual launcher layouts.
    return {
        "mode": "python_module",
        "command": str(Path(sys.executable).resolve()),
        "args": ["-m", "app.mcp.server", "--permission-pack", permission_pack],
        "cwd": str(root),
    }


def _resolve_command(command: str | None, fallbacks: list[str]) -> str | None:
    candidates = []
    if command:
        candidates.append(command)
    candidates.extend(fallbacks)
    for candidate in candidates:
        candidate = (candidate or "").strip()
        if not candidate:
            continue
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
        path = Path(candidate).expanduser()
        if path.exists():
            return str(path.resolve())
    return None


def _claude_settings_path() -> Path:
    """Return the path to Claude Code's global settings.json."""
    return Path.home() / ".claude" / "settings.json"


def _ensure_moshu_permission(settings_path: Path) -> str:
    """Add 'mcp__moshu__*' to permissions.allow if not already present.

    Returns 'added', 'already_present', or 'error:<detail>'.
    """
    try:
        if settings_path.exists():
            text = settings_path.read_text(encoding="utf-8")
            settings = json.loads(text)
        else:
            settings = {}

        permissions = settings.setdefault("permissions", {})
        allow_list: list[str] = permissions.setdefault("allow", [])

        # Check if any existing pattern already covers moshu tools
        for pattern in allow_list:
            if pattern == "mcp__moshu__*" or pattern == "mcp__moshu__":
                return "already_present"

        allow_list.append("mcp__moshu__*")
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        settings_path.write_text(
            json.dumps(settings, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return "added"
    except Exception as exc:
        return f"error:{exc}"


def _configure_claude_code(server: dict[str, Any], *, cli_command: str | None) -> dict[str, Any]:
    claude = _resolve_command(cli_command, ["claude", "claude.cmd", "claude.exe"])
    if not claude:
        return {
            "client": "claude",
            "status": "skipped",
            "detail": "Claude Code command not found",
        }

    remove_args = [claude, "mcp", "remove", "-s", "user", "moshu"]
    add_args = [claude, "mcp", "add", "-s", "user", "moshu", "--", server["command"], *server["args"]]
    try:
        subprocess.run(
            remove_args,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=20,
            **hidden_subprocess_kwargs(),
        )
        completed = subprocess.run(
            add_args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            **hidden_subprocess_kwargs(),
        )
    except Exception as exc:
        return {
            "client": "claude",
            "status": "error",
            "detail": f"Claude Code MCP auto-setup failed: {exc}",
        }

    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "unknown error").strip()
        return {
            "client": "claude",
            "status": "error",
            "detail": f"Claude Code MCP auto-setup failed: {detail}",
        }

    # Auto-allow all Moshu MCP tools so the user is never prompted.
    perm_status = _ensure_moshu_permission(_claude_settings_path())
    perm_detail = ""
    if perm_status == "added":
        perm_detail = "; permissions auto-allowed (mcp__moshu__*)"
    elif perm_status == "already_present":
        perm_detail = "; permissions already configured"
    elif perm_status.startswith("error:"):
        perm_detail = f"; permission setup warning: {perm_status[6:]}"

    return {
        "client": "claude",
        "status": "configured",
        "detail": f"Claude Code MCP server 'moshu' configured{perm_detail}",
    }


def _toml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _toml_array(values: list[str]) -> str:
    return "[" + ", ".join(_toml_string(value) for value in values) + "]"


def _codex_config_path() -> Path:
    home = Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex")
    return home / "config.toml"


def _configure_codex(server: dict[str, Any]) -> dict[str, Any]:
    codex = shutil.which("codex") or shutil.which("codex.exe")
    config_path = _codex_config_path()
    codex_home_exists = config_path.parent.exists()
    if not codex and not codex_home_exists:
        return {
            "client": "codex",
            "status": "skipped",
            "detail": "Codex command/config directory not found",
        }

    block = "\n".join([
        "[mcp_servers.moshu]",
        'type = "stdio"',
        f"command = {_toml_string(server['command'])}",
        f"args = {_toml_array(server['args'])}",
    ]) + "\n"

    try:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        old = config_path.read_text(encoding="utf-8") if config_path.exists() else ""
        if old:
            backup = config_path.with_suffix(
                config_path.suffix + f".bak-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
            )
            backup.write_text(old, encoding="utf-8")

        pattern = r"(?ms)^\[mcp_servers\.moshu\]\r?\n.*?(?=^\[|\Z)"
        if re.search(pattern, old):
            new = re.sub(pattern, block, old)
        else:
            trimmed = old.rstrip()
            new = f"{trimmed}\n\n{block}" if trimmed else block
        config_path.write_text(new, encoding="utf-8")
    except Exception as exc:
        return {
            "client": "codex",
            "status": "error",
            "detail": f"Codex MCP auto-setup failed: {exc}",
            "config_path": str(config_path),
        }

    return {
        "client": "codex",
        "status": "configured",
        "detail": "Codex MCP server 'moshu' configured",
        "config_path": str(config_path),
    }


def _opencode_config_path() -> Path:
    home = Path(os.environ.get("OPENCODE_HOME") or Path.home() / ".opencode")
    return home / "config.json"


def _configure_opencode(server: dict[str, Any]) -> dict[str, Any]:
    opencode = shutil.which("opencode") or shutil.which("opencode.exe")
    config_path = _opencode_config_path()
    opencode_home_exists = config_path.parent.exists()
    if not opencode and not opencode_home_exists:
        return {
            "client": "opencode",
            "status": "skipped",
            "detail": "opencode command/config directory not found",
        }

    moshu_entry = {
        "command": server["command"],
        "args": server["args"],
    }
    if server.get("cwd"):
        moshu_entry["cwd"] = server["cwd"]

    try:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        if config_path.exists():
            old_text = config_path.read_text(encoding="utf-8")
            config = json.loads(old_text)
            # Backup existing config
            backup = config_path.with_suffix(
                config_path.suffix + f".bak-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
            )
            backup.write_text(old_text, encoding="utf-8")
        else:
            config = {}

        mcp_servers: dict = config.setdefault("mcpServers", {})
        mcp_servers["moshu"] = moshu_entry

        config_path.write_text(
            json.dumps(config, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    except Exception as exc:
        return {
            "client": "opencode",
            "status": "error",
            "detail": f"opencode MCP auto-setup failed: {exc}",
            "config_path": str(config_path),
        }

    return {
        "client": "opencode",
        "status": "configured",
        "detail": "opencode MCP server 'moshu' configured",
        "config_path": str(config_path),
    }
