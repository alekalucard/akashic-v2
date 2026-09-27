#!/usr/bin/env python
"""
AKASHIC MCP SERVICE - Always-On Windows Service
================================================

This runs the MCP SSE server as a Windows service that:
1. Starts automatically with Windows
2. Runs on port 8765 (configurable)
3. Survives reboots, restarts, crashes
4. Claude Code connects to it via SSE transport

Installation:
    python mcp_service.py install
    python mcp_service.py start

Removal:
    python mcp_service.py stop
    python mcp_service.py remove

Manual run (for testing):
    python mcp_service.py run

Configure Claude Code (claude_desktop_config.json):
    {
        "mcpServers": {
            "akashic": {
                "url": "http://127.0.0.1:8765/sse"
            }
        }
    }
"""

import sys
import os
import time
import socket
import signal
import argparse
from pathlib import Path
from datetime import datetime

# Project root - where this script lives
ROOT = Path(__file__).parent.resolve()
STATE_DIR = ROOT / "state"
STATE_DIR.mkdir(parents=True, exist_ok=True)

# Config
DEFAULT_PORT = 8765
DEFAULT_HOST = "127.0.0.1"
PORT_FILE = STATE_DIR / "mcp_service_port.txt"
LOG_FILE = STATE_DIR / "mcp_service.log"
PID_FILE = STATE_DIR / "mcp_service.pid"

# Setup Python paths BEFORE imports
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "fairies"))
sys.path.insert(0, str(ROOT / "fairies" / "P40_Sensory" / "mcp"))


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
    """Write port file for service discovery."""
    PORT_FILE.write_text(f"{host}:{port}")
    log(f"[MCP-Service] Port file: {PORT_FILE}")


def write_pid_file():
    """Write PID file."""
    PID_FILE.write_text(str(os.getpid()))
    log(f"[MCP-Service] PID file: {PID_FILE} (pid={os.getpid()})")


def cleanup_files():
    """Clean up port and PID files on exit."""
    try:
        PORT_FILE.unlink(missing_ok=True)
        PID_FILE.unlink(missing_ok=True)
    except:
        pass


def run_server(host: str, port: int):
    """Run the SSE MCP server."""
    # Enable MCP debug logging to see validation errors
    import logging
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s %(levelname)s %(name)s: %(message)s',
        handlers=[logging.FileHandler(STATE_DIR / "mcp_debug.log"), logging.StreamHandler(sys.stderr)]
    )
    logging.getLogger("mcp").setLevel(logging.DEBUG)

    log("=" * 60)
    log("  AKASHIC MCP SERVICE")
    log("  Always-on SSE server for Claude Code")
    log("=" * 60)

    # Check if port is already in use
    if is_port_in_use(port, host):
        log(f"[MCP-Service] Port {port} already in use!")
        # Check if it's us (existing instance)
        if PID_FILE.exists():
            existing_pid = PID_FILE.read_text().strip()
            log(f"[MCP-Service] Existing PID: {existing_pid}")
        log("[MCP-Service] Exiting to avoid conflict.")
        return 1

    write_pid_file()
    write_port_file(host, port)

    try:
        import uvicorn
    except ImportError:
        log("[ERROR] uvicorn not installed. Run: pip install uvicorn")
        return 1

    try:
        # Import the MCP server
        from fairies.P40_Sensory.mcp.akashic_mcp_server import get_mcp_sse_app
        app = get_mcp_sse_app()
        log("[MCP-Service] SSE app loaded from akashic_mcp_server")
    except ImportError as e:
        log(f"[ERROR] Failed to import MCP server: {e}")
        import traceback
        traceback.print_exc()
        return 1

    log(f"[MCP-Service] Starting server on http://{host}:{port}/sse")
    log("[MCP-Service] Claude Code should connect to this URL")

    # Configure uvicorn
    config = uvicorn.Config(
        app,
        host=host,
        port=port,
        log_level="warning",
        access_log=False,
        timeout_keep_alive=60,
    )
    server = uvicorn.Server(config)

    try:
        server.run()
    except Exception as e:
        log(f"[MCP-Service] Server error: {e}")
        return 1
    finally:
        cleanup_files()

    return 0


def run_with_autorestart(host: str, port: int, max_retries: int = 100):
    """Run server with auto-restart on crash."""
    retries = 0
    backoff = 1

    while retries < max_retries:
        log(f"[MCP-Service] Starting (attempt {retries + 1}/{max_retries})")

        result = run_server(host, port)

        if result == 0:
            # Clean exit (SIGTERM/SIGINT)
            log("[MCP-Service] Clean shutdown.")
            break

        retries += 1
        if retries < max_retries:
            log(f"[MCP-Service] Restarting in {backoff}s...")
            time.sleep(backoff)
            backoff = min(backoff * 2, 60)  # Exponential backoff, max 60s
        else:
            log(f"[MCP-Service] Max retries ({max_retries}) reached. Giving up.")


# ============================================================================
# WINDOWS SERVICE SUPPORT (using pywin32)
# ============================================================================

try:
    import win32serviceutil
    import win32service
    import win32event
    import servicemanager
    HAS_PYWIN32 = True
except ImportError:
    HAS_PYWIN32 = False


if HAS_PYWIN32:
    class AkashicMCPService(win32serviceutil.ServiceFramework):
        """Windows Service wrapper for Akashic MCP SSE Server."""

        _svc_name_ = "AkashicMCP"
        _svc_display_name_ = "Akashic MCP Server"
        _svc_description_ = "Always-on MCP SSE server for Claude Code integration"

        def __init__(self, args):
            win32serviceutil.ServiceFramework.__init__(self, args)
            self.stop_event = win32event.CreateEvent(None, 0, 0, None)
            self.running = True

        def SvcStop(self):
            """Called when service is stopped."""
            self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
            win32event.SetEvent(self.stop_event)
            self.running = False
            log("[MCP-Service] Stop requested")

        def SvcDoRun(self):
            """Main service entry point."""
            servicemanager.LogMsg(
                servicemanager.EVENTLOG_INFORMATION_TYPE,
                servicemanager.PYS_SERVICE_STARTED,
                (self._svc_name_, '')
            )

            log("[MCP-Service] Windows Service starting...")

            # Run the server in a thread so we can monitor stop_event
            import threading

            server_thread = threading.Thread(
                target=run_with_autorestart,
                args=(DEFAULT_HOST, DEFAULT_PORT),
                daemon=True
            )
            server_thread.start()

            # Wait for stop signal
            while self.running:
                result = win32event.WaitForSingleObject(self.stop_event, 5000)
                if result == win32event.WAIT_OBJECT_0:
                    break

            log("[MCP-Service] Windows Service stopped")
            cleanup_files()


def install_startup_shortcut():
    """Create a VBScript shortcut in Windows Startup folder."""
    try:
        startup_folder = Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"

        if not startup_folder.exists():
            print(f"[ERROR] Startup folder not found: {startup_folder}")
            return False

        vbs_path = startup_folder / "AkashicMCPService.vbs"
        script = ROOT / "mcp_service.py"
        python_exe = sys.executable

        # VBScript to run hidden
        vbs_content = f'''Set oShell = CreateObject("WScript.Shell")
oShell.CurrentDirectory = "{ROOT}"
oShell.Run ""{python_exe}"" ""{script}"" run", 0, False
'''

        vbs_path.write_text(vbs_content)
        print(f"[OK] Startup shortcut created: {vbs_path}")
        print("[INFO] MCP service will start automatically on Windows boot.")
        return True

    except Exception as e:
        print(f"[ERROR] Failed to create startup shortcut: {e}")
        return False


def create_batch_launcher():
    """Create a batch file to manually start the service."""
    batch_path = ROOT / "start_mcp_service.bat"
    python_exe = sys.executable
    batch_content = f'''@echo off
title Akashic MCP Service
cd /d "{ROOT}"
echo Starting Akashic MCP Service...
echo.
echo Claude Code should connect to: http://127.0.0.1:{DEFAULT_PORT}/sse
echo.
"{python_exe}" mcp_service.py run
pause
'''
    batch_path.write_text(batch_content)
    print(f"[OK] Batch launcher created: {batch_path}")


def main():
    parser = argparse.ArgumentParser(description="Akashic MCP Service")
    parser.add_argument("command", nargs="?", default="run",
                        choices=["run", "install", "remove", "start", "stop", "restart",
                                 "install-startup", "create-launcher", "status"],
                        help="Command to execute")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT,
                        help=f"Port (default: {DEFAULT_PORT})")
    parser.add_argument("--host", default=DEFAULT_HOST,
                        help=f"Host (default: {DEFAULT_HOST})")
    parser.add_argument("--no-restart", action="store_true",
                        help="Disable auto-restart on crash")
    args = parser.parse_args()

    if args.command == "run":
        # Manual run mode (foreground)
        signal.signal(signal.SIGINT, lambda s, f: sys.exit(0))
        signal.signal(signal.SIGTERM, lambda s, f: sys.exit(0))

        if args.no_restart:
            return run_server(args.host, args.port)
        else:
            run_with_autorestart(args.host, args.port)
            return 0

    elif args.command == "install-startup":
        install_startup_shortcut()
        create_batch_launcher()
        return 0

    elif args.command == "create-launcher":
        create_batch_launcher()
        return 0

    elif args.command == "status":
        if is_port_in_use(args.port, args.host):
            print(f"[OK] MCP Service is RUNNING on http://{args.host}:{args.port}/sse")
            if PID_FILE.exists():
                print(f"[INFO] PID: {PID_FILE.read_text().strip()}")
            return 0
        else:
            print(f"[--] MCP Service is NOT running on port {args.port}")
            return 1

    elif args.command in ("install", "remove", "start", "stop", "restart"):
        if not HAS_PYWIN32:
            print("[ERROR] pywin32 not installed. Run: pip install pywin32")
            print("[INFO] For a simpler setup, use: python mcp_service.py install-startup")
            return 1

        # Use HandleCommandLine - pywin32 needs the full script path as argv[0]
        script_path = str(Path(__file__).resolve())
        cmd_map = {
            "install": [script_path, "--startup=auto", "install"],
            "remove": [script_path, "remove"],
            "start": [script_path, "start"],
            "stop": [script_path, "stop"],
            "restart": [script_path, "restart"],
        }

        old_argv = sys.argv
        sys.argv = cmd_map[args.command]
        try:
            win32serviceutil.HandleCommandLine(AkashicMCPService)
        finally:
            sys.argv = old_argv
        return 0

    return 0


if __name__ == "__main__":
    # Check if being run as Windows service
    if len(sys.argv) == 1 and HAS_PYWIN32:
        # Might be run by Windows Service Manager
        try:
            servicemanager.Initialize()
            servicemanager.PrepareToHostSingle(AkashicMCPService)
            servicemanager.StartServiceCtrlDispatcher()
        except:
            # Not a service call, run normally
            sys.exit(main() or 0)
    else:
        sys.exit(main() or 0)
