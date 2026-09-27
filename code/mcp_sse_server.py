#!/usr/bin/env python
"""
AKASHIC MCP SSE SERVER - Always-On, Auto-Restart
=================================================

This is the PERMANENT MCP server that starts with Windows and NEVER dies.
Claude Code connects to this via SSE transport.

Features:
- Runs on port 8765 (configurable)
- Auto-restarts on crash
- Writes port file for discovery
- Logs to state/mcp_sse_server.log
- Starts with Windows (via Startup folder)

Usage:
    python mcp_sse_server.py

Installation:
    Run: python mcp_sse_server.py --install-startup
    This creates a shortcut in Windows Startup folder.
"""

import sys
import os
import time
import signal
import socket
import argparse
from pathlib import Path
from datetime import datetime

# Project root - where this script lives
ROOT = Path(__file__).parent.resolve()
STATE_DIR = ROOT / "state"
STATE_DIR.mkdir(parents=True, exist_ok=True)

# Config
DEFAULT_PORT = 8770  # 8765 is used by server.py's PostalTunnelServer/MCP Proxy
DEFAULT_HOST = "127.0.0.1"
PORT_FILE = STATE_DIR / "mcp_sse_port.txt"
LOG_FILE = STATE_DIR / "mcp_sse_server.log"
PID_FILE = STATE_DIR / "mcp_sse_server.pid"

# Setup paths
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "fairies"))
sys.path.insert(0, str(ROOT / "fairies" / "P40_Sensory" / "mcp"))

# ─── TORCH IMPORT BLOCKER ────────────────────────────────────────
# The SSE server should NEVER load PyTorch. It saves ~2.8GB RAM.
# Something in the transitive import chain pulls in torch lazily.
# This fake module prevents the real torch from loading.
import types
_fake_torch = types.ModuleType("torch")
_fake_torch.__version__ = "0.0.0-blocked"
_fake_torch.__file__ = "BLOCKED_BY_SSE_SERVER"
_fake_torch.cuda = types.ModuleType("torch.cuda")
_fake_torch.cuda.is_available = lambda: False
_fake_torch.cuda.device_count = lambda: 0
sys.modules["torch"] = _fake_torch
sys.modules["torch.cuda"] = _fake_torch.cuda


def log(msg: str):
    """Log to file and stderr."""
    timestamp = datetime.now().isoformat()
    line = f"{timestamp} {msg}"
    print(line, file=sys.stderr)
    try:
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(line + "\n")
    except:
        pass


def is_port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    """Check if a port is already in use."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex((host, port)) == 0


def write_port_file(host: str, port: int):
    """Write port file for Claude Code discovery."""
    PORT_FILE.write_text(f"{host}:{port}")
    log(f"[MCP-SSE] Port file written: {PORT_FILE}")


def write_pid_file():
    """Write PID file."""
    PID_FILE.write_text(str(os.getpid()))
    log(f"[MCP-SSE] PID file written: {PID_FILE} (pid={os.getpid()})")


def run_server(host: str, port: int):
    """Run the SSE MCP server."""
    log("=" * 60)
    log("  AKASHIC MCP SSE SERVER")
    log("  Always-on, auto-restart")
    log("=" * 60)

    # Check if port is already in use
    if is_port_in_use(port, host):
        log(f"[MCP-SSE] Port {port} already in use - another instance running?")
        log("[MCP-SSE] Exiting to avoid conflict.")
        return 1

    # Write PID file
    write_pid_file()

    # BLOCK torch/CUDA import — SSE server should NEVER load GPU libraries.
    # This saves ~2.8GB of RAM. The main server.py handles GPU work.
    os.environ["CUDA_VISIBLE_DEVICES"] = ""  # Prevents CUDA init
    os.environ["AKASHIC_NO_TORCH"] = "1"     # Custom flag for lazy guards

    try:
        import uvicorn
    except ImportError:
        log("[ERROR] uvicorn not installed. Run: pip install uvicorn")
        return 1

    try:
        # Import the MCP server and get its SSE app
        from fairies.P40_Sensory.mcp.akashic_mcp_server import get_mcp_sse_app
        app = get_mcp_sse_app()
        log("[MCP-SSE] Got SSE app from akashic_mcp_server")
    except ImportError as e:
        log(f"[ERROR] Failed to import MCP server: {e}")
        log("[MCP-SSE] Falling back to standalone minimal server...")
        app = create_minimal_mcp_app()

    # Write port file
    write_port_file(host, port)

    log(f"[MCP-SSE] Starting server on http://{host}:{port}")
    log("[MCP-SSE] Press Ctrl+C to stop")

    # Configure uvicorn
    config = uvicorn.Config(
        app,
        host=host,
        port=port,
        log_level="warning",
        access_log=False,
        timeout_keep_alive=30,
    )
    server = uvicorn.Server(config)

    try:
        server.run()
    except Exception as e:
        log(f"[MCP-SSE] Server error: {e}")
        return 1

    return 0


def create_minimal_mcp_app():
    """Create a minimal MCP app as fallback."""
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError:
        log("[ERROR] MCP not installed. Run: pip install mcp")
        sys.exit(1)

    mcp = FastMCP("akashic")

    # Load critical tools
    try:
        from srm_tools import register_srm_tools
        register_srm_tools(mcp)
        log("[OK] SRM tools loaded")
    except Exception as e:
        log(f"[WARN] SRM tools failed: {e}")

    try:
        from nous_tools import register_nous_tools
        register_nous_tools(mcp)
        log("[OK] Nous tools loaded")
    except Exception as e:
        log(f"[WARN] Nous tools failed: {e}")

    @mcp.tool()
    def quick_status() -> str:
        """Quick system health check."""
        import psutil
        ram = psutil.virtual_memory().percent
        return f"[OK] RAM:{ram:.0f}% | MCP:SSE-Standalone | Mode:Always-On"

    return mcp.sse_app()


def run_with_autorestart(host: str, port: int, max_retries: int = 10):
    """Run server with auto-restart on crash."""
    retries = 0
    backoff = 1

    while retries < max_retries:
        log(f"[MCP-SSE] Starting (attempt {retries + 1}/{max_retries})")

        result = run_server(host, port)

        if result == 0:
            # Clean exit
            log("[MCP-SSE] Clean shutdown.")
            break

        retries += 1
        if retries < max_retries:
            log(f"[MCP-SSE] Restarting in {backoff}s...")
            time.sleep(backoff)
            backoff = min(backoff * 2, 60)  # Exponential backoff, max 60s
        else:
            log(f"[MCP-SSE] Max retries ({max_retries}) reached. Giving up.")


def install_windows_startup():
    """Install to Windows Startup folder."""
    try:
        import winreg
        import subprocess

        startup_folder = Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"

        if not startup_folder.exists():
            print(f"[ERROR] Startup folder not found: {startup_folder}")
            return False

        # Create a VBScript that runs the server hidden
        vbs_path = startup_folder / "AkashicMCPServer.vbs"
        script = ROOT / "mcp_sse_server.py"

        vbs_content = f'''Set oShell = CreateObject("WScript.Shell")
oShell.CurrentDirectory = "{ROOT}"
oShell.Run """{sys.executable}"" ""{script}""", 0, False
'''

        vbs_path.write_text(vbs_content)
        print(f"[OK] Installed to: {vbs_path}")
        print("[OK] MCP server will start automatically on Windows boot.")
        print("[INFO] To uninstall, delete: {vbs_path}")
        return True

    except Exception as e:
        print(f"[ERROR] Failed to install: {e}")
        return False


def create_batch_launcher():
    """Create a batch file to manually start the server."""
    batch_path = ROOT / "start_mcp_sse.bat"
    batch_content = f'''@echo off
title Akashic MCP SSE Server
cd /d "{ROOT}"
echo Starting Akashic MCP SSE Server...
"{sys.executable}" mcp_sse_server.py
pause
'''
    batch_path.write_text(batch_content)
    print(f"[OK] Created: {batch_path}")
    print("[INFO] Double-click this to manually start the server.")


def main():
    parser = argparse.ArgumentParser(description="Akashic MCP SSE Server")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"Port (default: {DEFAULT_PORT})")
    parser.add_argument("--host", default=DEFAULT_HOST, help=f"Host (default: {DEFAULT_HOST})")
    parser.add_argument("--install-startup", action="store_true", help="Install to Windows Startup folder")
    parser.add_argument("--create-launcher", action="store_true", help="Create batch launcher")
    parser.add_argument("--no-restart", action="store_true", help="Disable auto-restart")
    args = parser.parse_args()

    if args.install_startup:
        install_windows_startup()
        create_batch_launcher()
        return 0

    if args.create_launcher:
        create_batch_launcher()
        return 0

    # Graceful shutdown handler
    def signal_handler(signum, frame):
        log("[MCP-SSE] Received shutdown signal")
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    if args.no_restart:
        return run_server(args.host, args.port)
    else:
        run_with_autorestart(args.host, args.port)
        return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
