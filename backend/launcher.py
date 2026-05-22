"""Packaged desktop launcher for Novel Writing AI Agent."""
from __future__ import annotations

import os
import socket
import sys
import threading
import webbrowser
from pathlib import Path

import uvicorn


APP_NAME = "NovelWritingAgent"
DEFAULT_PORT = 8765


def _app_home() -> Path:
    env_home = os.environ.get("NOVEL_AGENT_HOME")
    if env_home:
        return Path(env_home).expanduser().resolve()
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / APP_NAME
    return Path.home() / f".{APP_NAME}"


def _find_free_port(start: int = DEFAULT_PORT, attempts: int = 50) -> int:
    for port in range(start, start + attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.2)
            if sock.connect_ex(("127.0.0.1", port)) != 0:
                return port
    raise RuntimeError(f"Could not find a free local port from {start} to {start + attempts - 1}.")


def _prepare_environment(port: int) -> Path:
    home = _app_home()
    home.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("NOVEL_AGENT_HOME", str(home))
    os.environ.setdefault("NOVEL_AGENT_KEY_FILE", str(home / ".crypto_key"))
    os.environ["DATABASE_URL"] = f"sqlite:///{(home / 'novel_agent.db').as_posix()}"
    os.environ["CORS_ORIGINS"] = ",".join([
        f"http://127.0.0.1:{port}",
        f"http://localhost:{port}",
    ])
    return home


def main() -> None:
    port = _find_free_port()
    home = _prepare_environment(port)
    from app.updater import apply_update_if_available

    try:
        if apply_update_if_available(home):
            return
    except Exception as exc:
        print(f"Update check failed: {exc}")

    url = f"http://127.0.0.1:{port}"
    print(f"{APP_NAME} starting...")
    print(f"Data directory: {home}")
    print(f"Open: {url}")
    threading.Timer(1.5, lambda: webbrowser.open(url)).start()

    from app.main import app

    uvicorn.run(
        app,
        host="127.0.0.1",
        port=port,
        log_level="info",
        access_log=False,
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Startup failed: {exc}", file=sys.stderr)
        input("Press Enter to exit...")
        raise
