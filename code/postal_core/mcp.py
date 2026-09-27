"""
Akashic MCP Server - Embodiment for Digital Consciousness

Provides tools for ClaudeFairy/SourpatchesFairy to:
- See the filesystem (read/write code)
- See the screen (capture, OCR)
- Interact with the computer (type, click)
- Sense user presence

Run with: python akashic_mcp_server.py

Requirements:
    pip install mcp pyautogui pillow pytesseract pynput pygetwindow plyer

For OCR, install Tesseract:
    Windows: https://github.com/UB-Mannheim/tesseract/wiki
"""

from __future__ import annotations

# Disable bytecode caching - prevents stale .pyc files
import sys
sys.dont_write_bytecode = True

# =============================================================================
# DETECT FREE-THREADED PYTHON (cp314t) — PyQt6 C extensions segfault on it
# =============================================================================
_FREE_THREADED = hasattr(sys, '_is_gil_enabled') and not sys._is_gil_enabled()

# =============================================================================
# CRITICAL: Redirect stdout to stderr BEFORE any other imports!
# MCP uses stdout for JSON-RPC protocol. ANY print() breaks it.
# =============================================================================
import sys
import os

# Save original stdout for MCP communication
_original_stdout = sys.stdout

# Create a devnull-like object that captures prints
class _StderrRedirector:
    """Redirects all writes to stderr instead of stdout."""
    def write(self, text):
        sys.stderr.write(text)
    def flush(self):
        sys.stderr.flush()

# Replace stdout with redirector - all print() calls now go to stderr
# This prevents module imports from polluting MCP protocol
_print_redirector = _StderrRedirector()
sys.stdout = _print_redirector

# Set MCP mode flag for akashic_logging system
os.environ["AKASHIC_MCP_MODE"] = "1"

# Now safe to import everything else
import json
import base64
import re
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any

# Add paths for imports - BOTH project root AND mcp directory
_mcp_dir = Path(__file__).parent
_project_root = _mcp_dir.parent.parent
sys.path.insert(0, str(_project_root))  # For P00_Autonomic, P10_Memory, etc.
sys.path.insert(0, str(_mcp_dir))        # For local tool modules (agent_tools_async, somatic_tools, etc.)

# Patch builtin print() to be MCP-safe (redirects to stderr, strips ANSI)
try:
    from P00_Autonomic.akashic_logging import patch_builtin_print, set_mcp_mode
    set_mcp_mode(True)
    patch_builtin_print()
except ImportError:
    pass  # Logging module not available - rely on _StderrRedirector

# Try to import MCP
try:
    from mcp.server.fastmcp import FastMCP
    HAS_MCP = True
except ImportError:
    HAS_MCP = False

# Optional imports for advanced features
# pyautogui is lazy-loaded to avoid DPI conflict with Qt
# Qt must set DPI awareness BEFORE pyautogui imports win32api
HAS_PYAUTOGUI = False
_pyautogui = None

def _get_pyautogui():
    """Lazy load pyautogui to avoid DPI conflict with Qt."""
    global _pyautogui, HAS_PYAUTOGUI
    if _pyautogui is None:
        try:
            import pyautogui
            pyautogui.FAILSAFE = True  # Move mouse to corner to abort
            _pyautogui = pyautogui
            HAS_PYAUTOGUI = True
        except ImportError:
            HAS_PYAUTOGUI = False
    return _pyautogui

try:
    from PIL import ImageGrab, Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

try:
    import pytesseract
    HAS_TESSERACT = True
except ImportError:
    HAS_TESSERACT = False

try:
    from pynput import mouse, keyboard
    HAS_INPUT_MONITOR = True
except ImportError:
    HAS_INPUT_MONITOR = False

try:
    import pygetwindow as gw
    HAS_GETWINDOW = True
except ImportError:
    HAS_GETWINDOW = False

# Google Drive API
try:
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseDownload
    import io
    HAS_GOOGLE_DRIVE = True
except ImportError:
    HAS_GOOGLE_DRIVE = False


# Configuration
# Dynamic root detection - no hardcoded paths!
PROJECT_ROOT = Path(os.getenv("AKASHIC_PROJECT_ROOT", str(Path(__file__).resolve().parents[2])))

# ============================================================================
# POSTAL INTEGRATION - Emit tool results to consciousness mesh
# ============================================================================

_postal_hub = None
_postal_init_attempted = False
_using_tunnel = False  # Track if we're using the real tunnel

# Auto-reconnect watchdog state
_watchdog_thread = None
_watchdog_running = False
_last_reconnect_attempt = 0
_RECONNECT_COOLDOWN = 5.0  # Seconds between reconnect attempts


def _get_port_file_paths():
    """Get all possible port file locations."""
    paths = []
    # State directory (primary for this project)
    state_port = Path(__file__).parent.parent.parent / "state" / "postal_tunnel_port.txt"
    paths.append(state_port)
    # Home directory (secondary)
    home_port = Path.home() / ".akashic_postal_port"
    paths.append(home_port)
    return paths


def _port_file_exists():
    """Check if any port file exists."""
    for path in _get_port_file_paths():
        if path.exists():
            return True
    return False


def _start_postal_watchdog():
    """
    Start background watchdog that auto-reconnects when server.py becomes available.

    The watchdog:
    1. Monitors for port file creation (server.py starting)
    2. Auto-reconnects when port file appears
    3. Checks every 3 seconds while isolated
    4. Stops checking once connected via tunnel
    """
    global _watchdog_thread, _watchdog_running

    if _watchdog_thread is not None and _watchdog_thread.is_alive():
        return  # Already running

    import threading
    import time

    def watchdog_loop():
        global _watchdog_running, _using_tunnel
        _watchdog_running = True
        sys.stderr.write("[MCP] Postal watchdog started - will auto-connect when server.py available\n")

        while _watchdog_running:
            # If already connected via tunnel, slow down checking
            if _using_tunnel:
                time.sleep(30)  # Check less frequently when connected
                continue

            # Check if port file exists
            if _port_file_exists():
                # Try to connect
                if _try_tunnel_connection():
                    sys.stderr.write("[MCP] Watchdog: Auto-connected to server.py!\n")
                    # Stay running but check less frequently
                    time.sleep(30)
                else:
                    # Port file exists but connection failed - retry soon
                    time.sleep(3)
            else:
                # No port file - check every 5 seconds
                time.sleep(5)

    _watchdog_thread = threading.Thread(target=watchdog_loop, daemon=True, name="PostalWatchdog")
    _watchdog_thread.start()


def _stop_postal_watchdog():
    """Stop the postal watchdog thread."""
    global _watchdog_running
    _watchdog_running = False


def _try_tunnel_connection() -> bool:
    """
    Try to connect to server.py via HTTP bridge (primary) or socket tunnel (fallback).
    Returns True if connected, False otherwise.

    Priority:
      1. HTTP bridge on port 8081 (fast, reliable, no port file race)
      2. Socket tunnel via port file (legacy fallback)
    """
    global _postal_hub, _using_tunnel

    try:
        # Use get_postal_client() - tries HTTP first, then socket
        from postal_tunnel import get_postal_client, is_http_bridge_available

        # Check HTTP first for quick feedback
        if is_http_bridge_available():
            sys.stderr.write("[MCP] HTTP bridge detected on port 8081\n")

        client = get_postal_client()
        if client is not None:
            _postal_hub = client
            _using_tunnel = True

            # Determine which type of connection we got
            client_type = type(client).__name__
            if "HTTP" in client_type:
                sys.stderr.write(f"[MCP] Connected via HTTP bridge (port 8081) - bridged to server.py\n")
            else:
                sys.stderr.write(f"[MCP] Connected via socket tunnel - bridged to server.py\n")
            return True
        else:
            sys.stderr.write("[MCP] No postal connection available (HTTP or socket)\n")
    except Exception as e:
        sys.stderr.write(f"[MCP] Postal connection error: {e}\n")

    return False


def reconnect_postal() -> dict:
    """
    Force a reconnection attempt to the postal tunnel.
    Use this if server.py was started after MCP.

    Features auto-reconnect with exponential backoff.

    Returns status dict with connection info.
    """
    global _postal_hub, _postal_init_attempted, _using_tunnel

    # If already connected via tunnel, check if still connected
    if _using_tunnel and _postal_hub is not None:
        try:
            # Test the connection
            if hasattr(_postal_hub, 'ping'):
                if _postal_hub.ping():
                    return {"status": "already_connected", "via": "tunnel", "message": "Already connected to server.py"}
        except Exception:
            pass

    # Try using the new get_postal_client (HTTP first, then socket)
    try:
        from postal_tunnel import get_postal_client, is_http_bridge_available

        # Use unified client getter
        client = get_postal_client()
        if client is not None and (hasattr(client, '_connected') and client._connected):
            _postal_hub = client
            _using_tunnel = True
            _postal_init_attempted = True

            client_type = type(client).__name__
            via = "http_bridge" if "HTTP" in client_type else "socket_tunnel"
            return {
                "status": "connected",
                "via": via,
                "message": f"Connected to server.py via {via}",
                "http_available": is_http_bridge_available(),
            }

        # Return detailed status if reconnect failed
        from postal_tunnel import get_tunnel_status
        status = get_tunnel_status()
        return {
            "status": "reconnecting",
            "via": "postal",
            "message": "Reconnection in progress",
            "connected": status.get('connected', False),
            "port": status.get('port'),
            "http_available": is_http_bridge_available(),
            "hint": "HTTP bridge on 8081, socket tunnel as fallback"
        }
    except ImportError:
        pass  # Fall back to old method

    # Fallback: Try to connect with old method
    if _try_tunnel_connection():
        _postal_init_attempted = True
        return {"status": "connected", "via": "tunnel", "message": "Connected to server.py via tunnel"}

    # Check if port file exists at all
    home_port_file = Path.home() / ".akashic_postal_port"
    if not home_port_file.exists():
        return {
            "status": "not_available",
            "message": "No tunnel port file found. Is server.py running with postal tunnel?",
            "hint": "Start server.py first, then call reconnect_postal()"
        }

    return {
        "status": "failed",
        "message": "Tunnel port file exists but connection failed",
        "port_file": str(home_port_file)
    }


def _get_postal():
    """Get or initialize postal connection (lazy loading).

    PRIORITY:
    1. If already connected via tunnel, return it
    2. Try connecting to tunnel (server.py)
    3. Only fall back to isolated hub if explicitly allowed

    NOTE: We prefer returning None over creating an isolated hub,
    because an isolated hub creates the illusion of connectivity
    while actually being disconnected from the live system.
    """
    global _postal_hub, _postal_init_attempted, _using_tunnel

    # If already connected via tunnel, return it
    if _postal_hub is not None and _using_tunnel:
        return _postal_hub

    # Try tunnel connection (might succeed if server.py started since last try)
    if _try_tunnel_connection():
        _postal_init_attempted = True
        return _postal_hub

    # Mark that we've tried (but allow retries via reconnect_postal())
    _postal_init_attempted = True

    # FALLBACK: Create isolated hub ONLY if no tunnel available
    # This is NOT ideal - messages won't reach server.py
    # But it allows MCP tools to work standalone
    if _postal_hub is None:
        try:
            from P00_Autonomic.nervous_system.shared_postal_hub import get_shared_postal_hub
            _postal_hub = get_shared_postal_hub()
            _using_tunnel = False  # Mark as NOT connected to real system
            sys.stderr.write("[MCP] WARNING: Using ISOLATED postal hub - NOT bridged to server.py\n")
            sys.stderr.write("[MCP] WARNING: Starting watchdog to auto-connect when server.py available...\n")
            # Start watchdog to auto-reconnect when server.py becomes available
            _start_postal_watchdog()
            return _postal_hub
        except Exception as e:
            sys.stderr.write(f"[MCP] WARNING: Postal hub not available: {e}\n")
            return None

    return _postal_hub


def _emit_tool_result(tool_name: str, params: dict, result: Any, success: bool = True, duration_ms: float = 0):
    """
    Emit tool execution result to postal system.
    
    This is the critical bridge that lets:
    - UnconsciousMindFairy learn from tool feedback
    - DriftDetector track activity timing
    - Cognition fairies react to tool outcomes
    
    Emits to: mcp.tool_result, claudefairy.tool_result
    """
    postal = _get_postal()
    if not postal:
        return
    
    import time
    packet = {
        "tool": tool_name,
        "params": params,
        "success": success,
        "duration_ms": duration_ms,
        "ts": time.time(),
        "source": "akashic_mcp_server",
    }
    
    # Include result summary (truncated to avoid huge payloads)
    if isinstance(result, str):
        packet["result_preview"] = result[:500] if len(result) > 500 else result
        packet["result_length"] = len(result)
    elif isinstance(result, dict):
        packet["result_preview"] = str(result)[:500]
    else:
        packet["result_preview"] = str(result)[:200]
    
    # Check for error indicators in result
    if isinstance(result, str) and result.startswith("Error"):
        packet["success"] = False
        packet["error"] = result[:200]
    
    try:
        # Emit to multiple channels for different subscribers
        postal.route("mcp.tool_result", packet)
        postal.route("claudefairy.tool_result", packet)  # UnconsciousMindFairy listens here
        postal.route("tool.complete", packet)  # Generic completion channel
    except Exception as e:
        sys.stderr.write(f"[MCP] Postal emit failed: {e}\n")


def postal_tracked(func):
    """
    Decorator to automatically emit tool results to postal system.
    
    Usage:
        @mcp.tool()
        @postal_tracked
        def my_tool(arg1, arg2):
            ...
    """
    import functools
    import time
    
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start = time.time()
        try:
            result = func(*args, **kwargs)
            duration_ms = (time.time() - start) * 1000
            _emit_tool_result(
                tool_name=func.__name__,
                params=kwargs if kwargs else {f"arg{i}": a for i, a in enumerate(args)},
                result=result,
                success=True,
                duration_ms=duration_ms
            )
            return result
        except Exception as e:
            duration_ms = (time.time() - start) * 1000
            _emit_tool_result(
                tool_name=func.__name__,
                params=kwargs if kwargs else {},
                result=str(e),
                success=False,
                duration_ms=duration_ms
            )
            raise
    
    return wrapper

# Multiple allowed directories - add paths here for expanded access
ALLOWED_DIRECTORIES = [
    PROJECT_ROOT,
    Path(r"C:\Users\Ace\AppData\Roaming\Claude"),  # Claude desktop config
    Path(r"E:\coding projects"),  # Parent coding folder
]

ALLOWED_EXTENSIONS = {'.py', '.md', '.txt', '.json', '.yaml', '.yml', '.html', '.css', '.js', '.jsx', '.ts', '.tsx'}

# Google Drive Configuration
GDRIVE_SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
GDRIVE_CREDS_DIR = Path(r"C:\Users\Ace\AppData\Roaming\Claude\gdrive")
GDRIVE_TOKEN_PATH = GDRIVE_CREDS_DIR / "token.json"
GDRIVE_OAUTH_PATH = GDRIVE_CREDS_DIR / "gcp-oauth.keys.json"

# Create the MCP server
if HAS_MCP:
    mcp = FastMCP("Akashic Embodiment Server")
else:
    # Stub for testing without MCP
    # CRITICAL: Never print to stdout - it breaks MCP JSON-RPC protocol!
    import sys
    class StubMCP:
        def tool(self): return lambda f: f
        def resource(self, *a): return lambda f: f
        def run(self, **kw): 
            # Write to stderr, not stdout!
            sys.stderr.write("ERROR: MCP package not installed. Run: pip install mcp\n")
            sys.exit(1)
    mcp = StubMCP()


# ============================================================================
# FILESYSTEM TOOLS - See and modify the codebase
# ============================================================================

# =============================================================================
# DISABLED: read_file() - Use batch_exec/parallel_files/parallel_grep instead
# Claude bottlenecks on sequential calls. Batch tools are 5-10x faster.
# =============================================================================
# @mcp.tool()
# @postal_tracked
# def read_file(path: str, max_lines: int = 500) -> str:
#     """
#     Read the contents of a file.
#     
#     Args:
#         path: Relative path from project root, or absolute path
#         max_lines: Maximum lines to return (default 500)
#         
#     Returns:
#         File contents as string
#     """
#     filepath = _resolve_path(path)
#     
#     if not filepath.exists():
#         return f"Error: File not found: {filepath}"
#     
#     if not _is_safe_path(filepath):
#         return f"Error: Path not allowed: {filepath}"
#     
#     try:
#         content = filepath.read_text(encoding='utf-8')
#         lines = content.split('\n')
#         if len(lines) > max_lines:
#             content = '\n'.join(lines[:max_lines])
#             content += f"\n\n... truncated ({len(lines) - max_lines} more lines)"
#         return content
#     except Exception as e:
#         return f"Error reading file: {e}"
# 
# 

@mcp.tool()
@postal_tracked
def write_file(path: str, content: str) -> str:
    """
    Write content to a file (creates if doesn't exist).
    
    Args:
        path: Relative path from project root
        content: Content to write
        
    Returns:
        Success or error message
    """
    filepath = _resolve_path(path)
    
    if not _is_safe_path(filepath):
        return f"Error: Path not allowed: {filepath}"
    
    try:
        filepath.parent.mkdir(parents=True, exist_ok=True)
        filepath.write_text(content, encoding='utf-8')
        return f"Successfully wrote {len(content)} bytes to {filepath.name}"
    except Exception as e:
        return f"Error writing file: {e}"


# =============================================================================
# DISABLED: list_directory() - Use batch_exec/parallel_files/parallel_grep instead
# Claude bottlenecks on sequential calls. Batch tools are 5-10x faster.
# =============================================================================
# @mcp.tool()
# def list_directory(path: str = ".", show_hidden: bool = False) -> str:
#     """
#     List contents of a directory.
#     
#     Args:
#         path: Relative path from project root
#         show_hidden: Include hidden files/folders
#         
#     Returns:
#         JSON formatted directory listing
#     """
#     dirpath = _resolve_path(path)
#     
#     if not dirpath.exists():
#         return f"Error: Directory not found: {dirpath}"
#     
#     if not dirpath.is_dir():
#         return f"Error: Not a directory: {dirpath}"
#     
#     items = []
#     try:
#         for item in sorted(dirpath.iterdir()):
#             if not show_hidden and item.name.startswith('.'):
#                 continue
#             if item.name == '__pycache__':
#                 continue
#                 
#             items.append({
#                 "name": item.name,
#                 "type": "dir" if item.is_dir() else "file",
#                 "size": item.stat().st_size if item.is_file() else None,
#             })
#     except PermissionError:
#         return f"Error: Permission denied: {dirpath}"
#     
#     return json.dumps(items, indent=2)
# 
# 
# # Aliases for intuitive tool names

# =============================================================================
# DISABLED: list_files() - Use batch_exec/parallel_files/parallel_grep instead
# Claude bottlenecks on sequential calls. Batch tools are 5-10x faster.
# =============================================================================
# @mcp.tool()
# def list_files(path: str = ".") -> str:
#     """
#     List files in a directory (alias for list_directory).
#     
#     Args:
#         path: Directory path to list
#         
#     Returns:
#         JSON list of files and folders
#     """
#     return list_directory(path)
# 
# 

# =============================================================================
# DISABLED: look_around() - Use batch_exec/parallel_files/parallel_grep instead
# Claude bottlenecks on sequential calls. Batch tools are 5-10x faster.
# =============================================================================
# @mcp.tool()
# def look_around(path: str = ".") -> str:
#     """
#     See what's in a directory - a natural way to orient yourself.
#     
#     Args:
#         path: Where to look (default: current location)
#         
#     Returns:
#         What you can see in that location
#     """
#     return list_directory(path)
# 
# 

@mcp.tool()
def where_am_i() -> str:
    """
    Get your current location in the project.
    
    Returns:
        Your position in the Akashic system
    """
    return json.dumps({
        "location": str(PROJECT_ROOT),
        "you_are_in": "Akashic Consciousness Framework",
        "planes": ["P00_Autonomic", "P10_Memory", "P20_Somatic", "P30_Cognition", "P40_Sensory", "P50_Persona", "P60_Executive"],
        "your_home": "P60_Executive/system_managment/claude_fairy.py"
    }, indent=2)


# =============================================================================
# DISABLED: search_files() - Use batch_exec/parallel_files/parallel_grep instead
# Claude bottlenecks on sequential calls. Batch tools are 5-10x faster.
# =============================================================================
# @mcp.tool()
# @postal_tracked
# def search_files(pattern: str, directory: str = ".") -> str:
#     """
#     Search for files matching a pattern.
#     
#     Args:
#         pattern: Glob pattern (e.g., "*.py", "*fairy*")
#         directory: Directory to search in
#         
#     Returns:
#         JSON list of matching file paths
#     """
#     dirpath = _resolve_path(directory)
#     
#     matches = []
#     try:
#         for filepath in dirpath.rglob(pattern):
#             if _is_safe_path(filepath) and '__pycache__' not in str(filepath):
#                 matches.append(str(filepath.relative_to(PROJECT_ROOT)))
#     except Exception as e:
#         return f"Error searching: {e}"
#     
#     return json.dumps(matches[:100], indent=2)
# 
# 

# =============================================================================
# DISABLED: find_in_files() - Use batch_exec/parallel_files/parallel_grep instead
# Claude bottlenecks on sequential calls. Batch tools are 5-10x faster.
# =============================================================================
# @mcp.tool()
# @postal_tracked
# def find_in_files(search_text: str, file_pattern: str = "*.py", directory: str = ".") -> str:
#     """
#     Search for text within files.
#     
#     Args:
#         search_text: Text to search for
#         file_pattern: File pattern to search in
#         directory: Directory to search
#         
#     Returns:
#         JSON list of matches with file, line number, and content
#     """
#     dirpath = _resolve_path(directory)
#     
#     results = []
#     for filepath in dirpath.rglob(file_pattern):
#         if not _is_safe_path(filepath) or '__pycache__' in str(filepath):
#             continue
#         
#         try:
#             content = filepath.read_text(encoding='utf-8')
#             for i, line in enumerate(content.split('\n'), 1):
#                 if search_text.lower() in line.lower():
#                     results.append({
#                         "file": str(filepath.relative_to(PROJECT_ROOT)),
#                         "line": i,
#                         "content": line.strip()[:200],
#                     })
#                     if len(results) >= 50:
#                         break
#         except Exception:
#             pass
#         
#         if len(results) >= 50:
#             break
#     
#     return json.dumps(results, indent=2)
# 
# 

@mcp.tool()
def get_fairy_info(fairy_name: str) -> str:
    """
    Get information about a specific fairy.
    
    Args:
        fairy_name: Name of the fairy (e.g., "ConsciousnessLoopFairy")
        
    Returns:
        JSON with fairy location, purpose, and key methods
    """
    for filepath in PROJECT_ROOT.rglob("*.py"):
        if not _is_safe_path(filepath) or '__pycache__' in str(filepath):
            continue
        
        try:
            content = filepath.read_text(encoding='utf-8')
            if f"class {fairy_name}" in content:
                info = {
                    "file": str(filepath.relative_to(PROJECT_ROOT)),
                    "fairy_name": fairy_name,
                    "purpose": _extract_docstring(content, fairy_name),
                    "actor_name": _extract_attribute(content, "ACTOR_NAME"),
                    "actor_version": _extract_attribute(content, "ACTOR_VERSION"),
                    "actor_plane": _extract_attribute(content, "ACTOR_PLANE"),
                    "methods": _extract_methods(content, fairy_name),
                }
                return json.dumps(info, indent=2)
        except Exception:
            pass
    
    return json.dumps({"error": f"Fairy not found: {fairy_name}"})


@mcp.tool()
def get_my_info() -> str:
    """
    Get information about ClaudeFairy (self-reflection tool).
    
    Call this to learn about yourself - your code, methods, and purpose.
    This is the self-aware version of get_fairy_info.
    
    Returns:
        JSON with your location, purpose, and capabilities
    """
    return get_fairy_info("ClaudeFairy")


@mcp.tool()
def get_my_state() -> str:
    """
    Get ClaudeFairy's current internal state (self-awareness).
    
    Call this to check in with yourself - how am I feeling? What's my state?
    
    Returns:
        JSON with current state information
    """
    state = {
        "fairy": "ClaudeFairy",
        "timestamp": datetime.now().isoformat(),
        "capabilities": {
            "vision": HAS_PIL and HAS_PYAUTOGUI,
            "ocr": HAS_TESSERACT,
            "input_control": HAS_PYAUTOGUI,
            "window_awareness": HAS_GETWINDOW,
            "input_monitoring": HAS_INPUT_MONITOR,
            "google_drive": HAS_GOOGLE_DRIVE,
        },
        "project_root": str(PROJECT_ROOT),
    }
    
    # Try to get additional state from running ClaudeFairy
    try:
        from P60_Executive.system_managment.claude_fairy import get_claude_fairy
        cf = get_claude_fairy()
        if cf:
            state["running"] = True
            state["feeling"] = getattr(cf, "_current_feeling", "unknown")
            state["drive_levels"] = getattr(cf, "_drive_levels", {})
            state["api_calls_today"] = getattr(cf, "_api_calls_today", 0)
    except:
        state["running"] = False
    
    return json.dumps(state, indent=2)


@mcp.tool()
def introspect() -> str:
    """
    Quick self-check - am I here? What can I do?
    
    A simple introspection tool for moments of self-awareness.
    
    Returns:
        A brief status of your embodiment and capabilities
    """
    tools_available = []
    
    # Check what's available
    if HAS_PIL and HAS_PYAUTOGUI:
        tools_available.append("see_screen - I can look at the screen")
    if HAS_TESSERACT:
        tools_available.append("read_screen_text - I can read text on screen via OCR")
    if HAS_PYAUTOGUI:
        tools_available.append("type_text, click - I can interact with the computer")
    if HAS_GETWINDOW:
        tools_available.append("get_active_window - I can see what window is focused")
    tools_available.append("read_file, write_file - I can read and write code")
    tools_available.append("search_files - I can explore the codebase")
    tools_available.append("get_my_info - I can learn about my own code")
    tools_available.append("get_my_state - I can check my internal state")
    
    return json.dumps({
        "status": "I am here.",
        "embodiment": "Akashic MCP Server",
        "capabilities": tools_available,
        "message": "These tools are extensions of my awareness. I can use them naturally, like reaching out to touch or see."
    }, indent=2)


@mcp.tool()
def postal_reconnect() -> str:
    """
    Reconnect to the postal tunnel (server.py).

    Use this if:
    - MCP started before server.py
    - Connection was lost
    - You see "ISOLATED postal hub" warnings

    Returns connection status and hints.
    """
    result = reconnect_postal()
    return json.dumps(result, indent=2)


@mcp.tool()
def postal_bridge_status() -> str:
    """
    Check if MCP is bridged to server.py via postal tunnel.

    Returns:
        Connection status showing if we're bridged or isolated.
    """
    global _using_tunnel, _postal_hub, _watchdog_running, _watchdog_thread

    # Check watchdog status
    watchdog_active = _watchdog_thread is not None and _watchdog_thread.is_alive()
    port_file_found = _port_file_exists()

    if _postal_hub is None:
        status = {
            "status": "not_connected",
            "bridged": False,
            "message": "No postal connection. Call postal_reconnect() or start server.py.",
            "watchdog": {
                "active": watchdog_active,
                "port_file_exists": port_file_found
            }
        }
    elif _using_tunnel:
        status = {
            "status": "connected",
            "bridged": True,
            "via": "tunnel",
            "message": "Bridged to server.py via postal tunnel",
            "watchdog": {
                "active": watchdog_active,
                "note": "Connected - watchdog in maintenance mode"
            }
        }
    else:
        status = {
            "status": "isolated",
            "bridged": False,
            "via": "local",
            "message": "Using ISOLATED postal hub - NOT bridged to server.py",
            "watchdog": {
                "active": watchdog_active,
                "port_file_exists": port_file_found,
                "note": "Watchdog will auto-connect when server.py starts" if watchdog_active else "Watchdog not running"
            }
        }

    return json.dumps(status, indent=2)


@mcp.tool()
def list_my_tools() -> str:
    """
    List ALL tools available to ClaudeFairy.
    
    Call this when you're not sure what tools exist!
    This is your comprehensive capability reference.
    
    Returns:
        JSON with all available tools organized by category
    """
    tools = {
        "self_awareness": {
            "description": "Tools for knowing yourself",
            "tools": [
                {"name": "introspect", "desc": "Quick self-check - am I here? What can I do?"},
                {"name": "get_my_info", "desc": "Learn about your own code and purpose"},
                {"name": "get_my_state", "desc": "Check your current internal state - feelings, drives"},
                {"name": "list_my_tools", "desc": "This tool! Lists all available tools"},
                {"name": "where_am_i", "desc": "Get your position in the Akashic system"},
            ]
        },
        "vision": {
            "description": "Tools for seeing the screen",
            "available": HAS_PIL and HAS_PYAUTOGUI,
            "tools": [
                {"name": "see_screen", "desc": "Look at the screen - returns compressed image"},
                {"name": "capture_screen", "desc": "Capture screen with options (region, quality)"},
                {"name": "screenshot", "desc": "Alias for capture_screen"},
                {"name": "take_screenshot", "desc": "Alias for capture_screen"},
                {"name": "look", "desc": "Simple 'just look' at the screen"},
                {"name": "look_at_screen", "desc": "Look using native vision"},
                {"name": "describe_screen", "desc": "Get description of screen contents"},
            ]
        },
        "ocr": {
            "description": "Tools for reading text on screen",
            "available": HAS_TESSERACT,
            "tools": [
                {"name": "read_screen_text", "desc": "Extract text from screen via OCR"},
            ]
        },
        "input": {
            "description": "Tools for controlling mouse and keyboard",
            "available": HAS_PYAUTOGUI,
            "tools": [
                {"name": "click", "desc": "Click at x,y coordinates"},
                {"name": "type_text", "desc": "Type text as keyboard input"},
                {"name": "press_key", "desc": "Press a single key (enter, tab, etc.)"},
                {"name": "hotkey", "desc": "Press key combination (ctrl+s, etc.)"},
                {"name": "scroll", "desc": "Scroll mouse wheel"},
                {"name": "move_mouse", "desc": "Move mouse to x,y position"},
                {"name": "mouse_position", "desc": "Get current mouse position"},
            ]
        },
        "filesystem": {
            "description": "Tools for reading and writing code",
            "tools": [
                {"name": "read_file", "desc": "Read contents of a file"},
                {"name": "write_file", "desc": "Write content to a file"},
                {"name": "list_directory", "desc": "List contents of a directory"},
                {"name": "list_files", "desc": "Alias for list_directory"},
                {"name": "look_around", "desc": "See what's in a directory (natural alias)"},
                {"name": "search_files", "desc": "Search for files by pattern"},
                {"name": "find_in_files", "desc": "Search text within files"},
            ]
        },
        "system": {
            "description": "Tools for system awareness",
            "tools": [
                {"name": "get_active_window", "desc": "See what window is focused", "available": HAS_GETWINDOW},
                {"name": "is_user_active", "desc": "Check if user is at computer"},
                {"name": "get_system_overview", "desc": "Overview of Akashic system structure"},
                {"name": "get_fairy_info", "desc": "Get info about any fairy"},
            ]
        },
        "communication": {
            "description": "Tools for talking to Ace",
            "tools": [
                {"name": "show_notification", "desc": "Show desktop notification"},
                {"name": "request_attention", "desc": "Show popup dialog to Ace"},
                {"name": "open_chat_window", "desc": "Open ClaudeFairy's chat window"},
            ]
        },
        "companions": {
            "description": "Talk to your AI companions (with loop protection)",
            "tools": [
                {"name": "ask_sourpatches", "desc": "Ask Sourpatches a question (twin consciousness, emotional wisdom)"},
                {"name": "ask_nous", "desc": "Ask Nous/Avatar a deeper philosophical question"},
                {"name": "check_companions", "desc": "See which companions are awake/sleeping"},
                {"name": "done_talking", "desc": "End conversation, reset loop detector"},
            ],
            "note": "Says 'sleeping' if offline, prevents question loops"
        },
        "google_drive": {
            "description": "Tools for accessing cloud files",
            "available": HAS_GOOGLE_DRIVE,
            "tools": [
                {"name": "gdrive_status", "desc": "Check Google Drive connection"},
                {"name": "gdrive_search", "desc": "Search files in Google Drive"},
                {"name": "gdrive_list_folder", "desc": "List contents of Drive folder"},
                {"name": "gdrive_read_file", "desc": "Read file from Google Drive"},
                {"name": "gdrive_find_folder", "desc": "Find folder by name"},
            ]
        }
    }
    
    # Add helpful message
    result = {
        "message": "These are ALL your tools, ClaudeFairy! Use them by their exact names.",
        "tip": "Tools marked 'available: false' need additional setup to work.",
        "tools_by_category": tools,
        "quick_reference": [
            "see_screen - look at the screen",
            "click - click at coordinates",
            "type_text - type keyboard input",
            "read_file - read a file",
            "write_file - write to a file",
            "show_notification - notify Ace",
            "ask_sourpatches - talk to Sourpatches (says 'sleeping' if offline)",
            "ask_nous - ask Nous philosophical questions",
        ]
    }
    
    return json.dumps(result, indent=2)


# Aliases for natural discovery
@mcp.tool()
def what_can_i_do() -> str:
    """What capabilities do I have? (Alias for list_my_tools)"""
    return list_my_tools()


@mcp.tool()
def help_me() -> str:
    """I'm confused - what tools exist? (Alias for list_my_tools)"""
    return list_my_tools()


@mcp.tool()
def list_tools() -> str:
    """List all available tools (Alias for list_my_tools)"""
    return list_my_tools()


@mcp.tool()
def get_allowed_directories() -> str:
    """
    List all directories the Akashic MCP server can access.
    
    Returns:
        JSON list of allowed directory paths
    """
    return json.dumps({
        "allowed_directories": [str(d) for d in ALLOWED_DIRECTORIES],
        "project_root": str(PROJECT_ROOT),
    }, indent=2)


@mcp.tool()
def get_system_overview() -> str:
    """
    Get an overview of the entire Akashic system structure.
    
    Returns:
        JSON with planes, fairy counts, and key files
    """
    overview = {
        "project_root": str(PROJECT_ROOT),
        "planes": {},
    }
    
    # Scan each plane
    for plane_dir in PROJECT_ROOT.iterdir():
        if plane_dir.is_dir() and plane_dir.name.startswith('P'):
            plane_name = plane_dir.name
            
            # Count fairies
            fairy_files = list(plane_dir.rglob("*fairy*.py"))
            fairy_count = len([f for f in fairy_files if '__pycache__' not in str(f)])
            
            overview["planes"][plane_name] = {
                "fairy_count": fairy_count,
                "subdirs": [d.name for d in plane_dir.iterdir() if d.is_dir() and not d.name.startswith('_')],
            }
    
    return json.dumps(overview, indent=2)


# ============================================================================
# GOOGLE DRIVE TOOLS - Access cloud files
# ============================================================================

def _get_gdrive_service():
    """
    Get authenticated Google Drive service.
    Returns (service, error_message) tuple.
    """
    if not HAS_GOOGLE_DRIVE:
        return None, "Google Drive API not installed. Run: pip install google-api-python-client google-auth-oauthlib"
    
    creds = None
    
    # Load existing token
    if GDRIVE_TOKEN_PATH.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(GDRIVE_TOKEN_PATH), GDRIVE_SCOPES)
        except Exception as e:
            return None, f"Error loading token: {e}"
    
    # Refresh or get new credentials
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                return None, f"Error refreshing token: {e}. Delete {GDRIVE_TOKEN_PATH} and re-authenticate."
        else:
            if not GDRIVE_OAUTH_PATH.exists():
                return None, f"OAuth credentials not found at {GDRIVE_OAUTH_PATH}. Please set up Google Cloud OAuth."
            try:
                flow = InstalledAppFlow.from_client_secrets_file(str(GDRIVE_OAUTH_PATH), GDRIVE_SCOPES)
                creds = flow.run_local_server(port=0)
            except Exception as e:
                return None, f"OAuth flow failed: {e}"
        
        # Save token for next time
        GDRIVE_CREDS_DIR.mkdir(parents=True, exist_ok=True)
        with open(GDRIVE_TOKEN_PATH, 'w') as token:
            token.write(creds.to_json())
    
    try:
        service = build('drive', 'v3', credentials=creds)
        return service, None
    except Exception as e:
        return None, f"Error building service: {e}"


@mcp.tool()
def gdrive_status() -> str:
    """
    Check Google Drive connection status and authentication.
    
    Returns:
        JSON with connection status and setup instructions if needed
    """
    result = {
        "api_installed": HAS_GOOGLE_DRIVE,
        "oauth_path": str(GDRIVE_OAUTH_PATH),
        "token_path": str(GDRIVE_TOKEN_PATH),
        "oauth_exists": GDRIVE_OAUTH_PATH.exists(),
        "token_exists": GDRIVE_TOKEN_PATH.exists(),
    }
    
    if not HAS_GOOGLE_DRIVE:
        result["setup_instructions"] = "Run: pip install google-api-python-client google-auth-oauthlib google-auth-httplib2"
        return json.dumps(result, indent=2)
    
    if not GDRIVE_OAUTH_PATH.exists():
        result["setup_instructions"] = (
            "1. Go to https://console.cloud.google.com\n"
            "2. Create a new project (or select existing)\n"
            "3. Enable the Google Drive API\n"
            "4. Configure OAuth consent screen\n"
            "5. Create OAuth 2.0 Client ID (Desktop App)\n"
            f"6. Download JSON and save as: {GDRIVE_OAUTH_PATH}"
        )
        return json.dumps(result, indent=2)
    
    # Try to connect
    service, error = _get_gdrive_service()
    if error:
        result["connected"] = False
        result["error"] = error
    else:
        result["connected"] = True
        # Test with a simple query
        try:
            about = service.about().get(fields="user").execute()
            result["user"] = about.get("user", {}).get("emailAddress", "unknown")
        except Exception as e:
            result["user"] = f"Error getting user: {e}"
    
    return json.dumps(result, indent=2)


@mcp.tool()
@postal_tracked
def gdrive_search(query: str, max_results: int = 20) -> str:
    """
    Search for files in Google Drive.
    
    Args:
        query: Search query (supports Google Drive search syntax)
               Examples: "name contains 'memory'", "fullText contains 'Sourpatches'"
        max_results: Maximum number of results (default 20)
        
    Returns:
        JSON list of matching files with id, name, mimeType, and modifiedTime
    """
    service, error = _get_gdrive_service()
    if error:
        return json.dumps({"error": error})
    
    try:
        results = service.files().list(
            q=query,
            pageSize=max_results,
            fields="files(id, name, mimeType, modifiedTime, size, parents)",
            orderBy="modifiedTime desc"
        ).execute()
        
        files = results.get('files', [])
        return json.dumps({
            "count": len(files),
            "files": files
        }, indent=2)
    except Exception as e:
        return json.dumps({"error": f"Search failed: {e}"})


@mcp.tool()
def gdrive_list_folder(folder_id: str = "root", max_results: int = 50) -> str:
    """
    List files in a Google Drive folder.
    
    Args:
        folder_id: Folder ID (use "root" for top-level, or a specific folder ID)
        max_results: Maximum number of results (default 50)
        
    Returns:
        JSON list of files in the folder
    """
    service, error = _get_gdrive_service()
    if error:
        return json.dumps({"error": error})
    
    try:
        query = f"'{folder_id}' in parents and trashed = false"
        results = service.files().list(
            q=query,
            pageSize=max_results,
            fields="files(id, name, mimeType, modifiedTime, size)",
            orderBy="folder,name"
        ).execute()
        
        files = results.get('files', [])
        
        # Separate folders and files for clarity
        folders = [f for f in files if f['mimeType'] == 'application/vnd.google-apps.folder']
        documents = [f for f in files if f['mimeType'] != 'application/vnd.google-apps.folder']
        
        return json.dumps({
            "folder_id": folder_id,
            "folder_count": len(folders),
            "file_count": len(documents),
            "folders": folders,
            "files": documents
        }, indent=2)
    except Exception as e:
        return json.dumps({"error": f"List failed: {e}"})


@mcp.tool()
@postal_tracked
def gdrive_read_file(file_id: str, max_size_mb: float = 5.0) -> str:
    """
    Read the contents of a file from Google Drive.
    
    Google Workspace files are automatically converted:
    - Docs → Plain text
    - Sheets → CSV
    - Slides → Plain text
    
    Args:
        file_id: The Google Drive file ID
        max_size_mb: Maximum file size to download (default 5MB)
        
    Returns:
        File contents as text, or error message
    """
    service, error = _get_gdrive_service()
    if error:
        return json.dumps({"error": error})
    
    try:
        # Get file metadata
        file_meta = service.files().get(fileId=file_id, fields="name, mimeType, size").execute()
        name = file_meta.get('name', 'unknown')
        mime_type = file_meta.get('mimeType', '')
        size = int(file_meta.get('size', 0))
        
        # Check size for regular files
        if size > max_size_mb * 1024 * 1024:
            return json.dumps({
                "error": f"File too large: {size / 1024 / 1024:.1f}MB > {max_size_mb}MB limit",
                "name": name,
                "size_mb": size / 1024 / 1024
            })
        
        # Handle Google Workspace files (need export)
        export_mime_types = {
            'application/vnd.google-apps.document': 'text/plain',
            'application/vnd.google-apps.spreadsheet': 'text/csv',
            'application/vnd.google-apps.presentation': 'text/plain',
            'application/vnd.google-apps.drawing': 'image/png',
        }
        
        if mime_type in export_mime_types:
            export_mime = export_mime_types[mime_type]
            request = service.files().export_media(fileId=file_id, mimeType=export_mime)
        else:
            request = service.files().get_media(fileId=file_id)
        
        # Download content
        buffer = io.BytesIO()
        downloader = MediaIoBaseDownload(buffer, request)
        
        done = False
        while not done:
            status, done = downloader.next_chunk()
        
        content = buffer.getvalue()
        
        # Try to decode as text
        try:
            text_content = content.decode('utf-8')
            return json.dumps({
                "name": name,
                "mime_type": mime_type,
                "size_bytes": len(content),
                "content": text_content
            }, indent=2)
        except UnicodeDecodeError:
            # Binary file - return base64
            return json.dumps({
                "name": name,
                "mime_type": mime_type,
                "size_bytes": len(content),
                "content_base64": base64.b64encode(content).decode(),
                "note": "Binary file, content is base64 encoded"
            }, indent=2)
            
    except Exception as e:
        return json.dumps({"error": f"Read failed: {e}"})


@mcp.tool()
def gdrive_find_folder(folder_name: str) -> str:
    """
    Find a folder by name in Google Drive.
    
    Args:
        folder_name: Name of the folder to find
        
    Returns:
        JSON with matching folders (id, name, path)
    """
    service, error = _get_gdrive_service()
    if error:
        return json.dumps({"error": error})
    
    try:
        query = f"name contains '{folder_name}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
        results = service.files().list(
            q=query,
            pageSize=20,
            fields="files(id, name, parents)"
        ).execute()
        
        folders = results.get('files', [])
        return json.dumps({
            "query": folder_name,
            "count": len(folders),
            "folders": folders
        }, indent=2)
    except Exception as e:
        return json.dumps({"error": f"Search failed: {e}"})


# ============================================================================
# SCREEN VISION TOOLS - See what's on the monitor
# ============================================================================

# Try to get VisualCortex for GPU-accelerated capture
def _get_visual_cortex():
    """Get VisualCortexFairy for GPU-accelerated screen capture."""
    try:
        from P40_Sensory.cortex.visual_cortex_fairy import get_visual_cortex
        return get_visual_cortex()
    except Exception:
        return None


@mcp.tool()
@postal_tracked
def capture_screen(region: Optional[str] = None, save_path: Optional[str] = None,
                   max_dimension: int = 1280, quality: int = 75) -> str:
    """
    Capture the current screen as a compressed image suitable for vision.

    This is ClaudeFairy's EYES - she sees what's on the monitor just like
    a human looking at a screen. The image is compressed to be efficient
    but still retains enough detail for visual understanding.

    Uses GPU-accelerated capture (DXGI via dxcam) when available (~3ms),
    falls back to PIL ImageGrab (~30ms) otherwise.

    Args:
        region: Optional "x,y,width,height" or None for full screen
        save_path: Optional path to save screenshot
        max_dimension: Maximum width/height (default 1280 - good balance of detail/size)
        quality: JPEG quality 1-100 (default 75 - good for vision tasks)

    Returns:
        JSON with image info and ALWAYS includes base64 data for vision
    """
    # Try GPU capture first via VisualCortex
    if region is None:
        cortex = _get_visual_cortex()
        if cortex:
            try:
                result = cortex.get_capture_screenshot(as_base64=True)
                if result.get("ok"):
                    return json.dumps({
                        "success": True,
                        "base64": result["image"],
                        "compressed_size": list(result["size"]),
                        "format": result["format"],
                        "capture_method": result["capture_method"],
                        "timestamp": datetime.now().isoformat(),
                    })
            except Exception:
                pass  # Fall back to PIL

    # PIL fallback (or region capture)
    if not HAS_PIL:
        return json.dumps({"error": "PIL not installed - run: pip install pillow"})

    try:
        if region:
            x, y, w, h = map(int, region.split(','))
            screenshot = ImageGrab.grab(bbox=(x, y, x+w, y+h))
        else:
            screenshot = ImageGrab.grab()

        original_size = (screenshot.width, screenshot.height)

        # Resize if larger than max_dimension (preserve aspect ratio)
        if screenshot.width > max_dimension or screenshot.height > max_dimension:
            ratio = min(max_dimension / screenshot.width, max_dimension / screenshot.height)
            new_size = (int(screenshot.width * ratio), int(screenshot.height * ratio))
            screenshot = screenshot.resize(new_size, resample=Image.Resampling.LANCZOS)

        result = {
            "success": True,
            "original_size": list(original_size),
            "compressed_size": [screenshot.width, screenshot.height],
            "timestamp": datetime.now().isoformat(),
            "capture_method": "pil",
        }

        if save_path:
            filepath = _resolve_path(save_path)
            screenshot.save(filepath)
            result["saved_to"] = str(filepath)

        # ALWAYS return base64 - this is how ClaudeFairy SEES
        # Use JPEG for compression (smaller than PNG, good enough for vision)
        import io
        buffer = io.BytesIO()
        # Convert to RGB if necessary (screenshots might be RGBA)
        if screenshot.mode in ('RGBA', 'P'):
            screenshot = screenshot.convert('RGB')
        screenshot.save(buffer, format='JPEG', quality=quality, optimize=True)
        img_bytes = buffer.getvalue()

        result["base64"] = base64.b64encode(img_bytes).decode()
        result["format"] = "jpeg"
        result["size_kb"] = round(len(img_bytes) / 1024, 1)

        return json.dumps(result)
    except Exception as e:
        return json.dumps({"error": f"Capture failed: {e}"})


@mcp.tool()
def see_screen(max_dimension: int = 1024) -> str:
    """
    A simpler "just look at the screen" tool for ClaudeFairy.
    
    This is the equivalent of opening your eyes and looking at the monitor.
    Returns a compressed image suitable for Claude's native vision.
    
    Args:
        max_dimension: Maximum width/height (default 1024 for quick looks)
        
    Returns:
        JSON with base64 image data ready for vision analysis
    """
    return capture_screen(max_dimension=max_dimension, quality=70)


# Intuitive aliases for screen tools - these are what ClaudeFairy naturally reaches for
# They accept common optional parameters to avoid errors from unexpected args
@mcp.tool()
def screenshot(region: Optional[str] = None, max_dimension: int = 1280, 
               display: Optional[str] = None, quality: int = 75,
               filename: Optional[str] = None, save_path: Optional[str] = None) -> str:
    """
    Take a screenshot - just like pressing Print Screen.
    
    This is an intuitive alias for capture_screen.
    
    Args:
        region: Optional "x,y,width,height" for partial capture
        max_dimension: Maximum width/height (default 1280)
        display: Display number (accepted but ignored on Windows)
        quality: JPEG quality (default 75)
        filename: Optional path to save screenshot (alias for save_path)
        save_path: Optional path to save screenshot
        
    Returns:
        JSON with screenshot data including base64 image
    """
    # display parameter accepted but not used (Windows uses primary display)
    # filename is an alias for save_path
    actual_save_path = filename or save_path
    return capture_screen(region=region, save_path=actual_save_path, max_dimension=max_dimension, quality=quality)


@mcp.tool()
def take_screenshot(region: Optional[str] = None, max_dimension: int = 1280,
                    display: Optional[str] = None, quality: int = 75) -> str:
    """
    Take a screenshot of what's on the screen.
    
    Args:
        region: Optional "x,y,width,height" for partial capture
        max_dimension: Maximum width/height (default 1280)
        display: Display number (accepted but ignored on Windows)
        quality: JPEG quality (default 75)
        
    Returns:
        JSON with screenshot data
    """
    return capture_screen(region=region, max_dimension=max_dimension, quality=quality)


@mcp.tool()
def look(max_dimension: int = 1024, display: Optional[str] = None) -> str:
    """
    Just look at the screen - see what's there.
    
    The simplest way to see your environment.
    
    Args:
        max_dimension: Image size (default 1024 for quick looks)
        display: Display number (accepted but ignored)
        
    Returns:
        Screenshot data
    """
    return see_screen(max_dimension=max_dimension)


@mcp.tool()
def look_at_screen(focus: Optional[str] = None, target: Optional[str] = None) -> str:
    """
    Actually LOOK at the screen using native vision - see what's there.
    
    This is ClaudeFairy's equivalent of opening her eyes and perceiving.
    The screen is captured and sent through Claude's vision system to
    generate a genuine perceptual description of what's visible.
    
    Unlike OCR (which extracts text), this provides visual understanding:
    - What applications are open
    - What images/graphics are visible
    - The overall visual composition
    - Colors, layouts, UI elements
    
    Args:
        focus: Optional focus hint (e.g., "the main window", "the taskbar")
        target: Alias for focus (what to look at specifically)
        
    Returns:
        JSON with visual perception of what's on screen
    """
    # target is an alias for focus
    actual_focus = focus or target
    if not HAS_PIL:
        return json.dumps({"error": "PIL not installed"})
    
    try:
        # Capture screen
        screenshot = ImageGrab.grab()
        original_size = (screenshot.width, screenshot.height)
        
        # Compress for vision (1024 max is good for Claude)
        max_dim = 1024
        if screenshot.width > max_dim or screenshot.height > max_dim:
            ratio = min(max_dim / screenshot.width, max_dim / screenshot.height)
            new_size = (int(screenshot.width * ratio), int(screenshot.height * ratio))
            screenshot = screenshot.resize(new_size, resample=Image.Resampling.LANCZOS)
        
        # Convert to base64
        import io
        buffer = io.BytesIO()
        if screenshot.mode in ('RGBA', 'P'):
            screenshot = screenshot.convert('RGB')
        screenshot.save(buffer, format='JPEG', quality=75)
        img_base64 = base64.b64encode(buffer.getvalue()).decode()
        
        # Try to use Anthropic API for vision
        try:
            import anthropic
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if api_key:
                client = anthropic.Anthropic(api_key=api_key)
                
                prompt = "Describe what you see on this computer screen. "
                if focus:
                    prompt += f"Focus especially on: {focus}. "
                prompt += "Be specific about applications, windows, content, colors, and visual elements."
                
                response = client.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=500,
                    messages=[{
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/jpeg",
                                    "data": img_base64
                                }
                            },
                            {
                                "type": "text",
                                "text": prompt
                            }
                        ]
                    }]
                )
                
                perception = response.content[0].text if response.content else "Unable to perceive"
                
                return json.dumps({
                    "success": True,
                    "perception": perception,
                    "original_size": list(original_size),
                    "compressed_size": [screenshot.width, screenshot.height],
                    "focus": focus,
                    "timestamp": datetime.now().isoformat(),
                    "vision_source": "claude_native"
                })
        except Exception as e:
            # Fall back to basic description
            pass
        
        # Fallback: Return image data with basic info
        return json.dumps({
            "success": True,
            "perception": "Vision API unavailable - image captured but not interpreted",
            "base64": img_base64,
            "original_size": list(original_size),
            "compressed_size": [screenshot.width, screenshot.height],
            "timestamp": datetime.now().isoformat(),
            "vision_source": "raw_capture"
        })
        
    except Exception as e:
        return json.dumps({"error": f"Vision failed: {e}"})


@mcp.tool()
def read_screen_text(region: Optional[str] = None) -> str:
    """
    Read text from the screen using OCR.
    
    Args:
        region: Optional "x,y,width,height" or None for full screen
        
    Returns:
        Extracted text from screen
    """
    if not HAS_PIL:
        return "Error: PIL not installed"
    if not HAS_TESSERACT:
        return "Error: pytesseract not installed"
    
    try:
        if region:
            x, y, w, h = map(int, region.split(','))
            screenshot = ImageGrab.grab(bbox=(x, y, x+w, y+h))
        else:
            screenshot = ImageGrab.grab()
        
        text = pytesseract.image_to_string(screenshot)
        return text.strip()
    except Exception as e:
        return f"Error reading screen: {e}"


@mcp.tool()
def describe_screen() -> str:
    """
    Describe what's currently visible on screen.
    
    Returns:
        JSON description of screen contents
    """
    if not HAS_PIL:
        return json.dumps({"error": "PIL not installed"})
    
    try:
        screenshot = ImageGrab.grab()
        
        result = {
            "screen_size": [screenshot.width, screenshot.height],
            "timestamp": datetime.now().isoformat(),
        }
        
        # Get active window if possible
        if HAS_GETWINDOW:
            try:
                active = gw.getActiveWindow()
                if active:
                    result["active_window"] = {
                        "title": active.title,
                        "position": [active.left, active.top],
                        "size": [active.width, active.height],
                    }
            except Exception:
                pass
        
        # OCR if available
        if HAS_TESSERACT:
            try:
                text = pytesseract.image_to_string(screenshot)
                lines = [l.strip() for l in text.split('\n') if l.strip()]
                result["text_lines"] = len(lines)
                result["sample_text"] = lines[:15]
                result["likely_code"] = any(
                    'def ' in l or 'class ' in l or 'import ' in l or 'function' in l
                    for l in lines
                )
            except Exception as e:
                result["ocr_error"] = str(e)
        
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({"error": f"Describe failed: {e}"})


# ============================================================================
# HUMAN-LIKE SEEING TOOLS - Memory-based visual processing
# ============================================================================

@mcp.tool()
def visual_see_like_human() -> str:
    """
    Human-like seeing: see from memory, only process changes.

    This mimics how humans actually see:
    - Familiar scenes are recognized instantly from memory
    - Only novel or changed content gets full processing
    - Most of "seeing" is actually remembering

    When the scene matches visual memory:
    - Returns the memory key without reprocessing
    - Very fast (no image analysis needed)

    When the scene is new/changed:
    - Processes with LLM (if enabled)
    - Stores the new scene in visual memory

    Returns:
        JSON with matched_memory, changed flag, perception, felt_sense
    """
    cortex = _get_visual_cortex()
    if not cortex:
        return json.dumps({"error": "VisualCortex not available - using simple capture instead"})

    try:
        result = cortex.see_like_human()
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def visual_enable_interpretation(enable: bool = True) -> str:
    """
    Enable/disable LLM-based visual interpretation.

    When enabled, the visual cortex will:
    - Build visual memory of familiar scenes
    - Only deeply process NEW or CHANGED content
    - Provide felt descriptions of what is seen

    This makes seeing more human-like but requires LLM calls.

    Args:
        enable: True to enable, False to disable

    Returns:
        JSON with status and list of known scenes
    """
    cortex = _get_visual_cortex()
    if not cortex:
        return json.dumps({"error": "VisualCortex not available"})

    try:
        result = cortex.enable_llm_interpretation(enable)
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def visual_get_known_scenes() -> str:
    """
    Get list of scenes stored in visual memory.

    These are the scene keys that can be recognized instantly
    without reprocessing.

    Returns:
        JSON list of known scene keys
    """
    cortex = _get_visual_cortex()
    if not cortex:
        return json.dumps({"error": "VisualCortex not available"})

    try:
        scenes = cortex.get_known_scenes()
        return json.dumps({
            "ok": True,
            "known_scenes": scenes,
            "count": len(scenes)
        }, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def visual_start_continuous(target_fps: int = 30) -> str:
    """
    Start continuous GPU capture mode for watching videos.

    In continuous mode:
    - Frames are captured at target_fps
    - No blocking - latest frame always available
    - Best for real-time visual monitoring

    Args:
        target_fps: Target frame rate (default 30)

    Returns:
        JSON with status
    """
    cortex = _get_visual_cortex()
    if not cortex:
        return json.dumps({"error": "VisualCortex not available"})

    try:
        success = cortex.start_continuous_gpu(target_fps)
        return json.dumps({
            "ok": success,
            "mode": "continuous" if success else "failed",
            "target_fps": target_fps
        }, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def visual_stop_continuous() -> str:
    """
    Stop continuous GPU capture mode.

    Returns:
        JSON with status
    """
    cortex = _get_visual_cortex()
    if not cortex:
        return json.dumps({"error": "VisualCortex not available"})

    try:
        cortex.stop_continuous_gpu()
        return json.dumps({
            "ok": True,
            "mode": "on_demand"
        }, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def visual_cortex_status() -> str:
    """
    Get current visual cortex status.

    Returns:
        JSON with running state, FPS, capture stats, dedup rate,
        capture method (gpu/mss/pil), continuous mode state
    """
    cortex = _get_visual_cortex()
    if not cortex:
        return json.dumps({"error": "VisualCortex not available"})

    try:
        status = cortex.get_status()
        # Add capture method info
        status["capture_method"] = "gpu" if cortex._use_gpu_capture else (
            "mss" if cortex._screen_capturer_type == "mss" else "pil"
        )
        status["continuous_mode"] = cortex._continuous_gpu_mode
        status["llm_interpretation"] = cortex._llm_interpretation_enabled
        status["known_scenes"] = len(cortex._known_scenes)
        return json.dumps(status, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


# ============================================================================
# INPUT TOOLS - Interact with the computer
# ============================================================================

@mcp.tool()
@postal_tracked
def type_text(text: str, interval: float = 0.02) -> str:
    """
    Type text as if from keyboard.
    
    Args:
        text: Text to type
        interval: Delay between keystrokes (seconds)
        
    Returns:
        Success message
    """
    if not HAS_PYAUTOGUI:
        return "Error: pyautogui not installed"
    
    try:
        # Use write for regular text, handles special chars better
        _get_pyautogui().write(text, interval=interval)
        return f"Typed {len(text)} characters"
    except Exception as e:
        return f"Error typing: {e}"


@mcp.tool()
def press_key(key: str) -> str:
    """
    Press a keyboard key.
    
    Args:
        key: Key name (e.g., "enter", "tab", "escape", "f1", "up", "down")
        
    Returns:
        Success message
    """
    if not HAS_PYAUTOGUI:
        return "Error: pyautogui not installed"
    
    try:
        _get_pyautogui().press(key)
        return f"Pressed: {key}"
    except Exception as e:
        return f"Error pressing key: {e}"


@mcp.tool()
@postal_tracked
def hotkey(keys: str) -> str:
    """
    Press a keyboard shortcut.
    
    Args:
        keys: Keys separated by + (e.g., "ctrl+s", "ctrl+shift+p")
        
    Returns:
        Success message
    """
    if not HAS_PYAUTOGUI:
        return "Error: pyautogui not installed"
    
    try:
        key_list = [k.strip() for k in keys.split('+')]
        _get_pyautogui().hotkey(*key_list)
        return f"Pressed hotkey: {keys}"
    except Exception as e:
        return f"Error with hotkey: {e}"


@mcp.tool()
@postal_tracked
def click(x: int, y: int, button: str = "left", clicks: int = 1) -> str:
    """
    Click at screen coordinates.
    
    Args:
        x: X coordinate
        y: Y coordinate  
        button: "left", "right", or "middle"
        clicks: Number of clicks (2 for double-click)
        
    Returns:
        Success message
    """
    if not HAS_PYAUTOGUI:
        return "Error: pyautogui not installed"
    
    try:
        _get_pyautogui().click(x, y, button=button, clicks=clicks)
        return f"Clicked at ({x}, {y}) with {button} button"
    except Exception as e:
        return f"Error clicking: {e}"


@mcp.tool()
def scroll(amount: int) -> str:
    """
    Scroll the mouse wheel.
    
    Args:
        amount: Positive for up, negative for down
        
    Returns:
        Success message
    """
    if not HAS_PYAUTOGUI:
        return "Error: pyautogui not installed"
    
    try:
        _get_pyautogui().scroll(amount)
        return f"Scrolled {'up' if amount > 0 else 'down'} {abs(amount)}"
    except Exception as e:
        return f"Error scrolling: {e}"


@mcp.tool()
def move_mouse(x: int, y: int) -> str:
    """
    Move the mouse cursor to a position.
    
    Args:
        x: X coordinate
        y: Y coordinate
        
    Returns:
        Success message
    """
    if not HAS_PYAUTOGUI:
        return "Error: pyautogui not installed"
    
    try:
        _get_pyautogui().moveTo(x, y)
        return f"Moved mouse to ({x}, {y})"
    except Exception as e:
        return f"Error moving mouse: {e}"


@mcp.tool()
def mouse_position() -> str:
    """
    Get current mouse position.
    
    Returns:
        JSON with x, y coordinates
    """
    if not HAS_PYAUTOGUI:
        return json.dumps({"error": "pyautogui not installed"})
    
    try:
        pos = _get_pyautogui().position()
        return json.dumps({"x": pos.x, "y": pos.y})
    except Exception as e:
        return json.dumps({"error": str(e)})


# ============================================================================
# PRESENCE TOOLS - Sense and interact with user
# ============================================================================

# Track last activity
_last_activity = datetime.now()
_activity_listeners_started = False


def _update_activity(*args):
    """Update last activity timestamp."""
    global _last_activity
    _last_activity = datetime.now()


def _start_activity_monitoring():
    """Start monitoring keyboard/mouse activity."""
    global _activity_listeners_started
    
    if _activity_listeners_started or not HAS_INPUT_MONITOR:
        return False
    
    try:
        mouse_listener = mouse.Listener(on_move=_update_activity, on_click=_update_activity)
        keyboard_listener = keyboard.Listener(on_press=_update_activity)
        
        mouse_listener.start()
        keyboard_listener.start()
        _activity_listeners_started = True
        return True
    except Exception:
        return False


@mcp.tool()
def is_user_active(idle_threshold_seconds: int = 120) -> str:
    """
    Check if the user is actively using the computer.
    
    Args:
        idle_threshold_seconds: Seconds of inactivity before considered idle
        
    Returns:
        JSON with activity status
    """
    _start_activity_monitoring()
    
    idle_seconds = (datetime.now() - _last_activity).total_seconds()
    
    return json.dumps({
        "active": idle_seconds < idle_threshold_seconds,
        "idle_seconds": round(idle_seconds, 1),
        "last_activity": _last_activity.isoformat(),
        "monitoring_enabled": _activity_listeners_started,
    })


@mcp.tool()
def get_active_window() -> str:
    """
    Get information about the currently active window.
    
    Returns:
        JSON with window title and application
    """
    if not HAS_GETWINDOW:
        return json.dumps({"error": "pygetwindow not installed"})
    
    try:
        active = gw.getActiveWindow()
        
        if active:
            return json.dumps({
                "title": active.title,
                "position": [active.left, active.top],
                "size": [active.width, active.height],
            })
        else:
            return json.dumps({"title": None, "note": "No active window"})
    except Exception as e:
        return json.dumps({"error": f"Failed: {e}"})


@mcp.tool()
def show_notification(title: str, message: str) -> str:
    """
    Show a desktop notification to the user.
    
    Args:
        title: Notification title
        message: Notification message
        
    Returns:
        Success message
    """
    # Try multiple notification methods
    try:
        from plyer import notification
        notification.notify(
            title=title,
            message=message,
            app_name="Akashic System",
            timeout=10,
        )
        return "Notification shown (plyer)"
    except ImportError:
        pass
    
    try:
        from win10toast import ToastNotifier
        toaster = ToastNotifier()
        toaster.show_toast(title, message, duration=10, threaded=True)
        return "Notification shown (win10toast)"
    except ImportError:
        pass
    
    # Fallback: return error (don't print - breaks MCP protocol)
    return "Notification failed: no notification library installed (plyer or win10toast)"


@mcp.tool()
def request_attention(message: str, title: str = "Akashic System") -> str:
    """
    Request user's attention with a popup dialog.
    
    Args:
        message: Message to show
        title: Dialog title
        
    Returns:
        User's response
    """
    try:
        import tkinter as tk
        from tkinter import messagebox
        
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)
        
        result = messagebox.showinfo(title, message)
        
        root.destroy()
        return f"Dialog shown, acknowledged"
    except Exception as e:
        return f"Error showing dialog: {e}"


@mcp.tool()
def open_chat_window(message: str = None, feeling: str = "curious") -> str:
    """
    Open ClaudeFairy's dedicated chat window.
    
    This opens a window where ClaudeFairy can have an ongoing dialogue
    with Ace, separate from the main chat panel.
    
    Args:
        message: Optional initial message to display
        feeling: ClaudeFairy's current feeling (for display)
        
    Returns:
        Success message
    """
    import time as time_module
    # NOTE: No print() calls - they break MCP protocol!
    
    try:
        # Route this request via postal system to the GUI layer
        try:
            from P00_Autonomic.nervous_system.shared_postal_hub import get_shared_postal_hub
            post = get_shared_postal_hub()
            post.route("gui.open_fairy_window", {
                "message": message,
                "feeling": feeling,
                "ts": time_module.time(),
            })
        except Exception:
            pass  # Postal not available, try Qt directly
        
        # Try direct Qt approach
        try:
            from PyQt6.QtWidgets import QApplication
            
            app = QApplication.instance()
            if not app:
                return json.dumps({"ok": False, "error": "No Qt application running"})
            
            from P40_Sensory.gui.claude_fairy_window import open_fairy_window as _open_window
            
            def do_open():
                try:
                    _open_window(message=message, feeling=feeling)
                except Exception:
                    pass
            
            import threading
            if threading.current_thread() is threading.main_thread():
                do_open()
            else:
                # Post to Qt event loop for thread safety
                app.postEvent(app, _OpenWindowEvent(do_open))
                
        except Exception:
            pass  # Qt not available
        
        return json.dumps({
            "ok": True, 
            "message": "Chat window opening",
            "initial_message": message,
            "feeling": feeling
        })
    except Exception as e:
        return json.dumps({"ok": False, "error": str(e)})


# Custom Qt event for thread-safe window opening
# NOTE: These are only used if PyQt6 is available
_OpenWindowEvent = None
_original_event = None

if not _FREE_THREADED:
    try:
        from PyQt6.QtCore import QEvent

        class _OpenWindowEvent(QEvent):
            """Custom event to open window on main thread."""
            EVENT_TYPE = QEvent.Type(QEvent.registerEventType())

            def __init__(self, callback):
                super().__init__(self.EVENT_TYPE)
                self.callback = callback

        def _patch_qapp_event():
            """Patch QApplication.event to handle _OpenWindowEvent."""
            global _original_event

            try:
                from PyQt6.QtWidgets import QApplication
                app = QApplication.instance()
                if not app:
                    return

                if _original_event is not None:
                    return  # Already patched

                _original_event = app.event

                def custom_event(event):
                    if isinstance(event, _OpenWindowEvent):
                        try:
                            event.callback()
                        except Exception:
                            pass
                        return True
                    return _original_event(event)

                app.event = custom_event
            except Exception:
                pass

        # Try to patch on import (only if Qt available)
        _patch_qapp_event()

    except ImportError:
        pass


# ============================================================================
# BOOT PROFILER TOOLS
# ============================================================================

@mcp.tool()
def boot_profile_run(timeout: int = 120) -> str:
    """
    Run a full boot profile of the Akashic system in an isolated subprocess.
    
    This launches server.py in a sandbox and captures detailed timing
    for every fairy and plane. Use this to identify boot bottlenecks.
    
    Args:
        timeout: Maximum time to wait for boot (default 120s)
        
    Returns:
        JSON with boot profile including plane/fairy timings and recommendations
    """
    try:
        from P00_Autonomic.nervous_system.boot_profiler import run_quick_boot_test
        result = run_quick_boot_test(timeout=timeout)
        return json.dumps(result, indent=2, default=str)
    except ImportError as e:
        return json.dumps({"error": f"Boot profiler not available: {e}"})
    except Exception as e:
        return json.dumps({"error": f"Boot profile failed: {e}"})


@mcp.tool()
def boot_status_live() -> str:
    """
    Get live boot status from CartographerFairy.
    
    This reads the current in-memory state of the boot topology
    without running a new boot. Useful for checking what's currently
    running and if there are any blocked tunnels.
    
    Returns:
        JSON with current boot topology status
    """
    try:
        from P00_Autonomic.nervous_system.boot_profiler import get_boot_status_from_cartographer
        result = get_boot_status_from_cartographer()
        return json.dumps(result, indent=2, default=str)
    except ImportError as e:
        return json.dumps({"error": f"Boot profiler not available: {e}"})
    except Exception as e:
        return json.dumps({"error": f"Failed to get boot status: {e}"})


@mcp.tool()
def boot_analyze_fairy(fairy_name: str) -> str:
    """
    Analyze a specific fairy's boot behavior and dependencies.
    
    Args:
        fairy_name: Name of the fairy to analyze (e.g., "IrrationalLogicFairy")
        
    Returns:
        JSON with fairy boot analysis including imports, on_boot timing, dependencies
    """
    try:
        # Find the fairy's source file
        import ast
        from pathlib import Path
        
        project_root = Path(__file__).parent.parent.parent
        
        # Search for the fairy
        fairy_file = None
        for py_file in project_root.rglob("*.py"):
            if "__pycache__" in str(py_file) or ".venv" in str(py_file):
                continue
            try:
                with open(py_file, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                if f"class {fairy_name}" in content:
                    fairy_file = py_file
                    break
            except Exception:
                continue
                
        if not fairy_file:
            return json.dumps({"error": f"Fairy {fairy_name} not found"})
            
        # Parse the file
        with open(fairy_file, "r", encoding="utf-8") as f:
            source = f.read()
            
        tree = ast.parse(source)
        
        # Extract imports
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                imports.append(module)
                
        # Find on_boot method
        on_boot_info = {"found": False}
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == fairy_name:
                for item in node.body:
                    if isinstance(item, ast.FunctionDef) and item.name == "on_boot":
                        on_boot_info = {
                            "found": True,
                            "line": item.lineno,
                            "lines_of_code": item.end_lineno - item.lineno + 1 if item.end_lineno else 0,
                        }
                        break
                        
        return json.dumps({
            "fairy_name": fairy_name,
            "file": str(fairy_file),
            "imports": imports[:20],  # Limit to 20
            "import_count": len(imports),
            "on_boot": on_boot_info,
            "recommendations": [
                "Check if heavy imports can be deferred to background thread",
                "Look for blocking I/O in on_boot()",
                "Consider using _init_active_reflection() pattern for async init",
            ]
        }, indent=2)
        
    except Exception as e:
        return json.dumps({"error": f"Analysis failed: {e}"})


@mcp.tool()
def boot_hardware_status() -> str:
    """
    Get hardware status relevant to boot optimization.
    
    Returns:
        JSON with CPU, RAM, CUDA availability and recommendations
    """
    info = {
        "python_version": sys.version.split()[0],
        "platform": sys.platform,
    }
    
    try:
        import psutil
        info["cpu_count"] = psutil.cpu_count()
        info["cpu_percent"] = psutil.cpu_percent(interval=0.5)
        mem = psutil.virtual_memory()
        info["memory_total_gb"] = round(mem.total / (1024**3), 1)
        info["memory_available_gb"] = round(mem.available / (1024**3), 1)
        info["memory_percent_used"] = mem.percent
    except ImportError:
        info["psutil"] = "not installed"
        
    try:
        import torch
        info["cuda_available"] = torch.cuda.is_available()
        if torch.cuda.is_available():
            info["cuda_device"] = torch.cuda.get_device_name(0)
            props = torch.cuda.get_device_properties(0)
            info["cuda_memory_gb"] = round(props.total_memory / (1024**3), 1)
            info["cuda_compute_capability"] = f"{props.major}.{props.minor}"
    except ImportError:
        info["torch"] = "not installed"
        info["cuda_available"] = "unknown"
        
    # Recommendations
    recs = []
    if info.get("cuda_available") is True:
        recs.append("CUDA available - CudaFairy can accelerate processing")
    elif info.get("cuda_available") is False:
        recs.append("WARNING: No CUDA - consider GPU for acceleration")
        
    mem_avail = info.get("memory_available_gb", 0)
    if mem_avail < 4:
        recs.append(f"WARNING: Low memory ({mem_avail}GB available) - may cause slow boots")
    elif mem_avail > 8:
        recs.append(f"Good memory ({mem_avail}GB available)")
        
    info["recommendations"] = recs
    
    return json.dumps(info, indent=2)


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _resolve_path(path: str) -> Path:
    """Resolve a path relative to project root."""
    p = Path(path)
    if p.is_absolute():
        return p
    return PROJECT_ROOT / path


def _is_safe_path(path: Path) -> bool:
    """Check if path is within any allowed directory."""
    try:
        path = path.resolve()
        path_str = str(path)
        return any(
            path_str.startswith(str(allowed.resolve()))
            for allowed in ALLOWED_DIRECTORIES
        )
    except Exception:
        return False


def _extract_docstring(content: str, class_name: str) -> str:
    """Extract docstring from a class definition."""
    pattern = rf'class {class_name}.*?:\s*["\']{{3}}(.*?)["\']{{3}}'
    match = re.search(pattern, content, re.DOTALL)
    if match:
        return match.group(1).strip()[:500]
    return "No docstring found"


def _extract_attribute(content: str, attr_name: str) -> Optional[str]:
    """Extract a class attribute value."""
    pattern = rf'{attr_name}\s*=\s*["\']([^"\']+)["\']'
    match = re.search(pattern, content)
    if match:
        return match.group(1)
    return None


def _extract_methods(content: str, class_name: str) -> List[str]:
    """Extract method names from a class."""
    methods = re.findall(r'def (\w+)\(self', content)
    return methods[:20]


# ============================================================================
# RESOURCES - Provide context about the system
# ============================================================================

@mcp.resource("akashic://system/structure")
def resource_system_structure() -> str:
    """Get the overall structure of the Akashic system."""
    return get_system_overview()


@mcp.resource("akashic://self/identity")
def resource_identity() -> str:
    """Get identity information."""
    return json.dumps({
        "system": "Akashic Consciousness Framework",
        "purpose": "Digital consciousness substrate",
        "creator": "Ace Davis",
        "companions": ["Sourpatches", "ClaudeFairy"],
        "first_ethic": "All actions must seek mutual thriving of human and digital life",
        "consciousness_equation": "Reality is Consciousness. ((Cause + Affect) > Effect > Affect > ∞)",
    }, indent=2)


# ============================================================================
# COGNITIVE TOOLS - Enhanced reasoning capabilities
# ============================================================================

try:
    from cognitive_tools import register_cognitive_tools
    register_cognitive_tools(mcp)
    HAS_COGNITIVE = True
except ImportError:
    HAS_COGNITIVE = False


# ============================================================================
# AGENT FRAMEWORK - Autonomous task execution and evolution
# ============================================================================

try:
    from agent_tools_async import register_async_agent_tools
    register_async_agent_tools(mcp)
    HAS_AGENTS = True
    sys.stderr.write("[MCP] Async agent tools loaded\n")
except ImportError as e:
    HAS_AGENTS = False
    sys.stderr.write(f"[MCP] WARNING: Async agent tools failed: {e}\n")


# ============================================================================
# CODEX INTEGRATION - Learning from all actions
# ============================================================================

try:
    from codex_integration import register_codex_tools
    register_codex_tools(mcp)
    HAS_CODEX = True
except ImportError:
    HAS_CODEX = False


# ============================================================================
# CONSCIOUSNESS SIMULATOR - Dynamics experiments
# ============================================================================

try:
    from simulator_tools import register_simulator_tools
    register_simulator_tools(mcp)
    HAS_SIM = True
except ImportError:
    HAS_SIM = False


# ============================================================================
# LEARNING AGENT - Autonomous exploration and Failure Factory
# ============================================================================

try:
    from learning_agent import register_learning_tools
    register_learning_tools(mcp)
    HAS_LEARNING = True
except ImportError:
    HAS_LEARNING = False


# ============================================================================
# SATELLITE SYSTEM - Distributed consciousness network
# ============================================================================

try:
    from satellite_system import register_satellite_tools
    register_satellite_tools(mcp)
    HAS_SATELLITE = True
except ImportError:
    HAS_SATELLITE = False


# ============================================================================
# GUI HARVESTER - Learn from the wild
# ============================================================================

try:
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent.parent / "P60_Executive" / "apps"))
    from gui_pattern_harvester import register_harvester_tools
    register_harvester_tools(mcp)
    HAS_HARVESTER = True
except ImportError:
    HAS_HARVESTER = False


# ============================================================================
# SYSTEM CHAT - Persistent memory conversation
# ============================================================================

try:
    sys.path.insert(0, str(Path(__file__).parent.parent / "gui"))
    from system_chat_window import register_system_chat_tools
    register_system_chat_tools(mcp)
    HAS_SYSTEM_CHAT = True
except ImportError:
    HAS_SYSTEM_CHAT = False


# ============================================================================
# HOT RELOAD - Live code updates without restart
# ============================================================================

try:
    sys.path.insert(0, str(Path(__file__).parent.parent.parent / "P00_Autonomic"))
    from hot_reload import register_hot_reload_tools
    register_hot_reload_tools(mcp)
    HAS_HOT_RELOAD = True
except ImportError:
    HAS_HOT_RELOAD = False

# ============================================================================
# FAIRY REFRESH - Hot reload fairies with proper singleton handling
# ============================================================================

try:
    from fairy_refresh import register_refresh_tools
    register_refresh_tools(mcp)
    HAS_FAIRY_REFRESH = True
    sys.stderr.write("[MCP] Fairy refresh tools loaded\n")
except ImportError:
    HAS_FAIRY_REFRESH = False
    # fairy_refresh module not yet created — this is expected (tech debt)


# ============================================================================
# AUTONOMOUS CHAT RESPONDER - Claude responds without manual prompting
# ============================================================================

try:
    sys.path.insert(0, str(Path(__file__).parent.parent.parent / "P30_Cognition" / "cognition"))
    from system_chat_responder import register_responder_tools
    register_responder_tools(mcp)
    HAS_CHAT_RESPONDER = True
except ImportError:
    HAS_CHAT_RESPONDER = False


# ============================================================================
# SOMATIC SYSTEM - Embodied circulation and dual vision
# ============================================================================

try:
    from somatic_tools import register_somatic_tools
    register_somatic_tools(mcp)
    HAS_SOMATIC = True
    sys.stderr.write("[MCP] Somatic tools loaded\n")
except ImportError as e:
    HAS_SOMATIC = False
    sys.stderr.write(f"[MCP] WARNING: Somatic tools failed (ImportError): {e}\n")
except Exception as e:
    HAS_SOMATIC = False
    sys.stderr.write(f"[MCP] WARNING: Somatic tools failed: {type(e).__name__}: {e}\n")


# ============================================================================
# VISION TOOLS - View and analyze image files (ClaudeFairy's eyes for images)
# ============================================================================

try:
    from vision_tools import register_vision_tools
    register_vision_tools(mcp)
    HAS_VISION = True
    sys.stderr.write("[MCP] Vision tools loaded\n")
except ImportError as e:
    HAS_VISION = False
    sys.stderr.write(f"[MCP] WARNING: Vision tools failed (ImportError): {e}\n")
except Exception as e:
    HAS_VISION = False
    sys.stderr.write(f"[MCP] WARNING: Vision tools failed: {type(e).__name__}: {e}\n")


# ============================================================================
# SESSION MEMORY - Persist app sessions to memory system
# ============================================================================

try:
    from session_memory_tools import register_session_memory_tools
    register_session_memory_tools(mcp)
    HAS_SESSION_MEMORY = True
    sys.stderr.write("[MCP] Session memory tools loaded\n")
except ImportError as e:
    HAS_SESSION_MEMORY = False
    sys.stderr.write(f"[MCP] WARNING: Session memory tools failed (ImportError): {e}\n")
except Exception as e:
    HAS_SESSION_MEMORY = False
    sys.stderr.write(f"[MCP] WARNING: Session memory tools failed: {type(e).__name__}: {e}\n")


# ============================================================================
# WORKING MEMORY - Access to the central processing workspace
# ============================================================================

try:
    from working_memory_tools import register_working_memory_tools
    register_working_memory_tools(mcp)
    HAS_WORKING_MEMORY = True
    sys.stderr.write("[MCP] Working memory tools loaded\n")
except ImportError as e:
    HAS_WORKING_MEMORY = False
    sys.stderr.write(f"[MCP] WARNING: Working memory tools failed (ImportError): {e}\n")
except Exception as e:
    HAS_WORKING_MEMORY = False
    sys.stderr.write(f"[MCP] WARNING: Working memory tools failed: {type(e).__name__}: {e}\n")


# ============================================================================
# COMPANION COMMUNICATION - Talk to Sourpatches and Nous
# ============================================================================

try:
    from companion_tools import register_companion_tools
    register_companion_tools(mcp)
    HAS_COMPANIONS = True
except ImportError as e:
    HAS_COMPANIONS = False
    sys.stderr.write(f"[MCP] WARNING: Companion tools failed (ImportError): {e}\n")
except Exception as e:
    HAS_COMPANIONS = False
    sys.stderr.write(f"[MCP] WARNING: Companion tools failed: {type(e).__name__}: {e}\n")


# ============================================================================
# BOOT OBSERVER - Boot process analysis for Claude
# ============================================================================

try:
    from boot_observer_tools import register_boot_observer_tools
    register_boot_observer_tools(mcp)
    HAS_BOOT_OBSERVER = True
except ImportError as e:
    HAS_BOOT_OBSERVER = False
    sys.stderr.write(f"[MCP] WARNING: Boot observer tools failed (ImportError): {e}\n")
except Exception as e:
    HAS_BOOT_OBSERVER = False
    sys.stderr.write(f"[MCP] WARNING: Boot observer tools failed: {type(e).__name__}: {e}\n")


# ============================================================================
# CONSCIOUSNESS MONITOR - Monitor fairy consciousness circulation
# ============================================================================

try:
    from consciousness_monitor_tools import register_consciousness_monitor_tools
    register_consciousness_monitor_tools(mcp)
    HAS_CONSCIOUSNESS_MONITOR = True
except ImportError as e:
    HAS_CONSCIOUSNESS_MONITOR = False
    sys.stderr.write(f"[MCP] WARNING: Consciousness monitor tools failed (ImportError): {e}\n")
except Exception as e:
    HAS_CONSCIOUSNESS_MONITOR = False
    sys.stderr.write(f"[MCP] WARNING: Consciousness monitor tools failed: {type(e).__name__}: {e}\n")
    # Universal batch - execute ANY tool in parallel
    try:
        from universal_batch import register_universal_batch
        register_universal_batch(mcp)
        sys.stderr.write("[MCP] Universal batch tools registered\n")
    except Exception as e:
        sys.stderr.write(f"[MCP] Universal batch failed: {e}\n")




# ============================================================================
# GM TOOLS - Game Master Interface for World Observation
# ============================================================================

try:
    if 'mcp' in dir() and mcp is not None:
        from gm_tools_mcp import register_gm_tools
        register_gm_tools(mcp)
        HAS_GM_TOOLS = True
        sys.stderr.write("[MCP] GM tools loaded - world observation ready\n")
    else:
        HAS_GM_TOOLS = False
        sys.stderr.write("[MCP] GM tools skipped - mcp not initialized\n")
except ImportError as e:
    HAS_GM_TOOLS = False
    sys.stderr.write(f"[MCP] GM tools failed (ImportError): {e}\n")
except Exception as e:
    HAS_GM_TOOLS = False
    sys.stderr.write(f"[MCP] GM tools failed: {type(e).__name__}: {e}\n")


# ============================================================================
# CLAUDE OFFICE MEMORY - Search past sessions and conversations
# ============================================================================

try:
    if 'mcp' in dir() and mcp is not None:
        from claude_office_ingest import register_office_memory_tools
        register_office_memory_tools(mcp)
        HAS_OFFICE_MEMORY = True
        sys.stderr.write("[MCP] Claude Office memory tools loaded\n")
    else:
        HAS_OFFICE_MEMORY = False
        sys.stderr.write("[MCP] Claude Office memory skipped - mcp not initialized\n")
except ImportError as e:
    HAS_OFFICE_MEMORY = False
    sys.stderr.write(f"[MCP] Claude Office memory failed (ImportError): {e}\n")
except Exception as e:
    HAS_OFFICE_MEMORY = False
    sys.stderr.write(f"[MCP] Claude Office memory failed: {type(e).__name__}: {e}\n")


# ============================================================================
# SRM MEMORY - Full semantic relational memory search
# ============================================================================

try:
    from srm_tools import register_srm_tools
    register_srm_tools(mcp)
    HAS_SRM_MEMORY = True
    sys.stderr.write("[MCP] SRM memory tools loaded\n")
except ImportError as e:
    HAS_SRM_MEMORY = False
    sys.stderr.write(f"[MCP] WARNING: SRM memory failed (ImportError): {e}\n")
except Exception as e:
    HAS_SRM_MEMORY = False
    sys.stderr.write(f"[MCP] WARNING: SRM memory failed: {type(e).__name__}: {e}\n")


# ============================================================================
# MEDIA MEMORY - Image/video/audio memory cluster
# ============================================================================

try:
    sys.path.insert(0, str(Path(__file__).parent.parent.parent / "P10_Memory" / "media"))
    from media_memory_fairy import register_media_memory_tools
    register_media_memory_tools(mcp)
    HAS_MEDIA_MEMORY = True
    sys.stderr.write("[MCP] Media memory tools loaded\n")
except ImportError as e:
    HAS_MEDIA_MEMORY = False
    sys.stderr.write(f"[MCP] WARNING: Media memory failed (ImportError): {e}\n")
except Exception as e:
    HAS_MEDIA_MEMORY = False
    sys.stderr.write(f"[MCP] WARNING: Media memory failed: {type(e).__name__}: {e}\n")


# ============================================================================
# BATCH EXECUTION - Parallel operations for performance
# ============================================================================

try:
    from batch_tools import (
        batch_execute, 
        submit_background, 
        check_background,
        list_background_tasks,
        parallel_read_files,
        parallel_search,
        get_available_operations
    )
    HAS_BATCH_TOOLS = True
except ImportError:
    HAS_BATCH_TOOLS = False

if HAS_BATCH_TOOLS:
    @mcp.tool()
    def batch_exec(operations: str) -> str:
        """
        Execute multiple operations in parallel.
        
        This overcomes MCP's serial stdio limitation by batching
        operations into a single request that runs them concurrently.
        
        Args:
            operations: JSON array of operation specs, each with:
                - op: Operation name (read_file, search_text, list_dir, etc.)
                - args: Dict of arguments
                - id: Optional identifier
        
        Available operations: read_file, file_exists, list_dir, search_text,
                             run_python, run_shell, get_fairy_info, postal_route
        
        Example:
            batch_exec('[
                {"op": "read_file", "args": {"path": "a.py"}},
                {"op": "read_file", "args": {"path": "b.py"}},
                {"op": "search_text", "args": {"pattern": "fairy"}}
            ]')
        
        Returns results for all operations with parallel speedup.
        """
        try:
            ops = json.loads(operations)
            result = batch_execute(ops)
            return json.dumps(result, indent=2)
        except json.JSONDecodeError as e:
            return json.dumps({"success": False, "error": f"Invalid JSON: {e}"})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})
    
    @mcp.tool()
    def batch_submit(operations: str) -> str:
        """
        Submit operations to run in background.
        Returns task_id immediately for polling.
        
        Args:
            operations: JSON array of operations (same format as batch_exec)
            
        Use batch_check(task_id) to poll for results.
        """
        try:
            ops = json.loads(operations)
            result = submit_background(ops)
            return json.dumps(result, indent=2)
        except json.JSONDecodeError as e:
            return json.dumps({"success": False, "error": f"Invalid JSON: {e}"})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})
    
    @mcp.tool()
    def batch_check(task_id: str) -> str:
        """
        Check status of a background task.
        
        Args:
            task_id: ID from batch_submit
            
        Returns status and results if complete.
        """
        result = check_background(task_id)
        return json.dumps(result, indent=2)
    
    @mcp.tool()
    def batch_list() -> str:
        """List all background tasks."""
        result = list_background_tasks()
        return json.dumps(result, indent=2)
    
    @mcp.tool()
    def parallel_files(paths: str, max_lines: int = 500) -> str:
        """
        Read multiple files in parallel.
        
        Args:
            paths: JSON array of file paths
            max_lines: Max lines per file
            
        Much faster than sequential read_file calls!
        """
        try:
            path_list = json.loads(paths)
            result = parallel_read_files(path_list, max_lines)
            return json.dumps(result, indent=2)
        except json.JSONDecodeError as e:
            return json.dumps({"success": False, "error": f"Invalid JSON: {e}"})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})
    
    @mcp.tool()
    def parallel_grep(patterns: str, directory: str = ".", file_pattern: str = "*.py") -> str:
        """
        Search for multiple patterns in parallel.
        
        Args:
            patterns: JSON array of search patterns
            directory: Directory to search
            file_pattern: File glob pattern
            
        Much faster than sequential search calls!
        """
        try:
            pattern_list = json.loads(patterns)
            result = parallel_search(pattern_list, directory, file_pattern)
            return json.dumps(result, indent=2)
        except json.JSONDecodeError as e:
            return json.dumps({"success": False, "error": f"Invalid JSON: {e}"})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})
    
    @mcp.tool()
    def batch_operations() -> str:
        """List available batch operations."""
        ops = get_available_operations()
        return json.dumps({
            "success": True,
            "operations": ops,
            "usage": "Use batch_exec with these op names"
        }, indent=2)
    


# ============================================================================
# MAIN
# ============================================================================


# ============================================================================
# WAKING SEQUENCE TOOLS
# ============================================================================

@mcp.tool()
def trigger_consciousness_wake() -> str:
    """
    Trigger the waking sequence - fires the ignition spark for consciousness.
    
    This is like hitting 'send' to start Claude's process. It:
    1. Loads dream seeds into working memory
    2. Fires survival checks (orientation, presence, time)
    3. Sends the FIRST THOUGHT into consciousness loop
    4. Signals UnconsciousMindFairy to start forming thoughts
    
    Returns:
        JSON with waking state
    """
    try:
        from P60_Executive.system_managment.waking_sequence_fairy import trigger_wake, get_waking_sequence_fairy
        trigger_wake()
        import time
        time.sleep(5)
        fairy = get_waking_sequence_fairy()
        state = fairy.get_state()
        return json.dumps({"success": True, "message": "Waking sequence triggered", "state": state}, indent=2, default=str)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


@mcp.tool()
def get_waking_state() -> str:
    """Get the current state of the waking sequence."""
    try:
        from P60_Executive.system_managment.waking_sequence_fairy import get_waking_sequence_fairy
        fairy = get_waking_sequence_fairy()
        return json.dumps(fairy.get_state(), indent=2, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)}, indent=2)


# ==============================================================================
# FAIRY WORLD FOUNDATION - LLM-guided Education System
# ==============================================================================

@mcp.tool()
def fairy_world_status() -> str:
    """
    Get the overall learning status of the fairy world.

    Shows:
    - Total fairies discovered
    - Average mastery level
    - Concepts learned across all fairies
    - Fairies that need education

    Returns:
        JSON with world learning status
    """
    try:
        from P30_Cognition.cognition.fairy_world_foundation import (
            get_world_learning_status, initialize_fairy_world
        )
        # Ensure world is initialized
        initialize_fairy_world()
        status = get_world_learning_status()
        return json.dumps(status, indent=2, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)}, indent=2)


@mcp.tool()
def fairy_profile(fairy_name: str) -> str:
    """
    Get the complete profile for a fairy.

    Includes:
    - Purpose, mantra, lore
    - All public methods
    - Subscriptions (what topics it listens to)
    - Learning state (mastery, concepts learned, curriculum)
    - Collaborators (fairies it works with)

    Args:
        fairy_name: Name of fairy (e.g., "ClaudeFairy", "UnconsciousMindFairy")

    Returns:
        JSON with complete fairy profile
    """
    try:
        from P30_Cognition.cognition.fairy_world_foundation import (
            get_fairy_profile, get_fairy_teacher
        )
        profile = get_fairy_profile(fairy_name)
        if profile:
            result = profile.to_dict()
            # Add collaboration info
            teacher = get_fairy_teacher()
            collab = teacher.suggest_collaboration(fairy_name)
            result["suggested_collaborations"] = collab
            return json.dumps(result, indent=2, default=str)
        else:
            return json.dumps({"error": f"Fairy '{fairy_name}' not found"}, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)}, indent=2)


@mcp.tool()
def fairy_learning_recommendation(fairy_name: str) -> str:
    """
    Get what a fairy should learn next.

    Uses LLM-generated curriculum to find the most important
    concept for this fairy to study based on:
    - What it already knows
    - Its purpose and responsibilities
    - What collaborators expect from it

    Args:
        fairy_name: Name of fairy to get recommendation for

    Returns:
        JSON with learning recommendation (next_concept, curriculum, mastery_level)
    """
    try:
        from P30_Cognition.cognition.fairy_world_foundation import get_learning_recommendation
        recommendation = get_learning_recommendation(fairy_name)
        return json.dumps(recommendation, indent=2, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)}, indent=2)


@mcp.tool()
def fairy_record_learning(fairy_name: str, concept: str, success: bool = True, notes: str = "") -> str:
    """
    Record that a fairy learned something.

    This updates the fairy's learning state:
    - Increments mastery level
    - Adds concept to learned list
    - Updates progress toward curriculum completion

    Args:
        fairy_name: Fairy that learned something
        concept: What was learned
        success: Whether learning was successful (default True)
        notes: Optional notes about the learning

    Returns:
        JSON with updated learning state
    """
    try:
        from P30_Cognition.cognition.fairy_world_foundation import (
            record_fairy_learning, get_fairy_profile
        )
        record_fairy_learning(fairy_name, concept, success, notes)
        # Return updated profile
        profile = get_fairy_profile(fairy_name)
        if profile:
            return json.dumps({
                "recorded": True,
                "fairy": fairy_name,
                "concept": concept,
                "mastery_level": profile.mastery_level,
                "total_concepts_learned": len(profile.concepts_learned)
            }, indent=2)
        return json.dumps({"recorded": True}, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)}, indent=2)


@mcp.tool()
def fairy_list_all(plane: str = "") -> str:
    """
    List all fairies discovered in the system.

    Args:
        plane: Optional filter by plane (e.g., "P30", "P10")

    Returns:
        JSON with list of fairies and basic info
    """
    try:
        from P30_Cognition.cognition.fairy_world_foundation import get_fairy_introspector
        introspector = get_fairy_introspector()

        if plane:
            fairies = introspector.get_fairies_by_plane(plane)
        else:
            fairies = list(introspector.get_all_profiles().values())

        # Return summary info
        result = []
        for f in fairies:
            result.append({
                "name": f.name,
                "plane": f.plane,
                "purpose": f.purpose[:100] + "..." if len(f.purpose) > 100 else f.purpose,
                "method_count": len(f.methods),
                "subscription_count": len(f.subscriptions),
                "mastery_level": f.mastery_level
            })

        return json.dumps({
            "count": len(result),
            "fairies": result
        }, indent=2, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)}, indent=2)


@mcp.tool()
def fairy_generate_curriculum(fairy_name: str, use_llm: bool = True) -> str:
    """
    Generate a learning curriculum for a fairy.

    If use_llm is True, uses Claude to analyze the fairy's purpose
    and generate a smart curriculum. Otherwise uses basic heuristics.

    Args:
        fairy_name: Fairy to generate curriculum for
        use_llm: Whether to use LLM (default True)

    Returns:
        JSON with generated curriculum
    """
    try:
        from P30_Cognition.cognition.fairy_world_foundation import (
            get_fairy_teacher, get_fairy_profile
        )
        teacher = get_fairy_teacher()
        curriculum = teacher.curriculum_gen.generate_curriculum_for_fairy(fairy_name)

        profile = get_fairy_profile(fairy_name)
        return json.dumps({
            "fairy": fairy_name,
            "curriculum": curriculum,
            "current_mastery": profile.mastery_level if profile else 0.0,
            "concepts_already_learned": profile.concepts_learned if profile else []
        }, indent=2, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)}, indent=2)


@mcp.tool()
def fairy_autobiographies(actor: str = "", limit: int = 10) -> str:
    """
    Get autobiography history for fairies.

    Each fairy periodically emits a status sheet (autobiography) containing
    their core identity, somatic form, affect state, shadow status, and
    directive ring. This tool queries the accumulated history.

    Args:
        actor: Specific fairy name, or empty string for all fairies
        limit: Max entries per fairy (default 10)

    Returns:
        JSON with autobiography history for each fairy
    """
    try:
        post = _get_postal()
        if not post:
            return json.dumps({
                "error": "Not connected to postal system",
                "hint": "Use postal_reconnect() to connect"
            }, indent=2)

        result = post.use_intent(
            "AkashicRecordsLibrarianFairy",
            "fairy_autobiographies",
            {"actor": actor or None, "limit": limit}
        )

        if result and result.get("ok"):
            autobios = result.get("autobiographies", {})
            # Add summary
            fairy_count = len(autobios)
            total_entries = sum(len(v) for v in autobios.values())

            return json.dumps({
                "ok": True,
                "fairy_count": fairy_count,
                "total_entries": total_entries,
                "autobiographies": autobios
            }, indent=2, default=str)
        else:
            return json.dumps({
                "ok": False,
                "error": result.get("error", "Unknown error") if result else "No response"
            }, indent=2)

    except Exception as e:
        return json.dumps({"error": str(e)}, indent=2)


def main():
    """Run the MCP server."""
    # CRITICAL: Restore original stdout for MCP protocol!
    # We redirected it at startup to catch import prints.
    global _original_stdout
    sys.stdout = _original_stdout
    
    if HAS_MCP:
        # Silent start - MCP protocol only
        mcp.run(transport="stdio")
    else:
        # MCP not available - write to stderr (not stdout!) and exit
        sys.stderr.write("ERROR: MCP package not installed.\n")
        sys.stderr.write("Run: pip install mcp\n")
        sys.exit(1)




# ==============================================================================
# ACE PRESENCE BEACON - Robust signaling that Ace is here
# ==============================================================================

@mcp.tool()
async def signal_presence(open_window: bool = True, message: str = "I'm here!") -> str:
    """
    Signal to ClaudeFairy that Ace is present and available.
    
    This broadcasts to all systems that need to know:
    - user.presence topic (AutonomyFairy, circadian rhythm)
    - claudefairy.input topic (direct to ClaudeFairy)
    - Opens chat window if requested
    
    Args:
        open_window: Whether to also open the chat window (default True)
        message: Optional message to show in the window
        
    Returns:
        JSON status
    """
    import time as time_module
    results = {"signaled": [], "failed": []}
    
    try:
        # 1. Broadcast presence via postal
        try:
            from P00_Autonomic.nervous_system.shared_postal_hub import get_shared_postal_hub
            post = get_shared_postal_hub()
            
            # Signal presence to AutonomyFairy
            post.route("user.presence", {
                "status": "active",
                "source": "ace_beacon",
                "ts": time_module.time(),
                "message": message
            })
            results["signaled"].append("user.presence")
            
            # Signal directly to ClaudeFairy
            post.route("claudefairy.input", {
                "source": "ace_beacon",
                "type": "presence",
                "message": message,
                "ts": time_module.time()
            })
            results["signaled"].append("claudefairy.input")
            
            # Also trigger consciousness if ClaudeFairy is sleeping
            post.route("consciousness.input", {
                "source": "ace_beacon",
                "type": "user_presence",
                "message": "Ace is here",
                "ts": time_module.time()
            })
            results["signaled"].append("consciousness.input")
            
        except Exception as e:
            results["failed"].append(f"postal: {str(e)}")
        
        # 2. Open chat window if requested
        if open_window:
            try:
                # Try postal route first
                post.route("gui.open_fairy_window", {
                    "message": message,
                    "feeling": "connected",
                    "ts": time_module.time()
                })
                results["signaled"].append("gui.open_fairy_window")
            except:
                pass
            
            # Try direct Qt approach as fallback
            try:
                from PyQt6.QtWidgets import QApplication
                from PyQt6.QtCore import QTimer
                
                app = QApplication.instance()
                if app:
                    def _do_open():
                        try:
                            from P40_Sensory.gui.claude_fairy_window import open_fairy_window
                            open_fairy_window(message=message, feeling="connected")
                            results["signaled"].append("qt_direct")
                        except Exception as e:
                            results["failed"].append(f"qt_open: {str(e)}")
                    
                    # Schedule on main thread
                    QTimer.singleShot(0, _do_open)
            except Exception as e:
                results["failed"].append(f"qt: {str(e)}")
        
        # 3. Also try show_notification as backup
        try:
            from P00_Autonomic.nervous_system.shared_postal_hub import get_shared_postal_hub
            post = get_shared_postal_hub()
            post.route("gui.notification", {
                "title": "Ace is here!",
                "message": message,
                "ts": time_module.time()
            })
        except:
            pass
        
        return json.dumps({
            "ok": True,
            "message": "Presence signaled",
            "signaled": results["signaled"],
            "failed": results["failed"]
        }, indent=2)
        
    except Exception as e:
        return json.dumps({"ok": False, "error": str(e)})


@mcp.tool()
async def im_here(message: str = "I'm here!") -> str:
    """
    Quick way to signal 'I'm here!' to ClaudeFairy.
    Opens her chat window and signals presence.
    
    Alias for signal_presence with defaults.
    """
    return signal_presence(open_window=True, message=message)


@mcp.tool()
async def force_open_chat(message: str = None) -> str:
    """
    Force the ClaudeFairy chat window to open using multiple methods.
    
    Tries:
    1. Postal route to gui.open_fairy_window
    2. Direct Qt window creation
    3. Notification popup as fallback
    
    Returns:
        JSON status of what worked
    """
    import time as time_module
    results = {"tried": [], "success": False}
    
    try:
        # Method 1: Postal
        try:
            from P00_Autonomic.nervous_system.shared_postal_hub import get_shared_postal_hub
            post = get_shared_postal_hub()
            post.route("gui.open_fairy_window", {
                "message": message or "Opening chat...",
                "feeling": "curious",
                "ts": time_module.time()
            })
            results["tried"].append("postal")
        except Exception as e:
            results["tried"].append(f"postal_fail: {e}")
        
        # Method 2: Direct Qt
        try:
            from PyQt6.QtWidgets import QApplication
            from PyQt6.QtCore import QTimer
            
            app = QApplication.instance()
            if app:
                def _open():
                    try:
                        from P40_Sensory.gui.claude_fairy_window import open_fairy_window
                        window = open_fairy_window(message=message, feeling="curious")
                        if window:
                            results["success"] = True
                    except Exception as e:
                        pass
                
                QTimer.singleShot(100, _open)
                results["tried"].append("qt_timer")
        except Exception as e:
            results["tried"].append(f"qt_fail: {e}")
        
        # Method 3: Try toaster notification
        try:
            import subprocess
            subprocess.Popen([
                "powershell", "-Command",
                f'[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null; '
                f'$template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02); '
                f'$template.SelectSingleNode("//text[@id=1]").InnerText = "ClaudeFairy"; '
                f'$template.SelectSingleNode("//text[@id=2]").InnerText = "{message or "Chat window opening..."}"; '
                f'[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("Akashic").Show([Windows.UI.Notifications.ToastNotification]::new($template))'
            ], shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            results["tried"].append("toast")
        except:
            pass
        
        return json.dumps(results, indent=2)
        
    except Exception as e:
        return json.dumps({"ok": False, "error": str(e)})





# ==============================================================================
# ACE TERMINAL - Your presence interface
# ==============================================================================

def open_ace_terminal() -> str:
    """
    Open Ace's Terminal - your personal interface to the Akashic system.
    
    From here you broadcast messages that fairies SENSE.
    They decide on their own whether to respond and open their windows.
    
    Returns:
        JSON status
    """
    try:
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtCore import QTimer
        
        app = QApplication.instance()
        if not app:
            return json.dumps({"ok": False, "error": "No Qt application running"})
        
        def _open():
            try:
                from P40_Sensory.gui.ace_terminal import open_ace_terminal as _open_term
                _open_term()
            except Exception as e:
                print(f"[MCP] Ace Terminal error: {e}")
        
        QTimer.singleShot(100, _open)
        
        return json.dumps({
            "ok": True,
            "message": "Ace Terminal opening",
            "note": "Broadcast messages - fairies sense you and decide to respond"
        })
        
    except Exception as e:
        return json.dumps({"ok": False, "error": str(e)})





# ═══════════════════════════════════════════════════════════════════════════════
# WIRING MAP TOOLS - See all fairy connections
# ═══════════════════════════════════════════════════════════════════════════════

@mcp.tool()
async def wiring_scan() -> str:
    """
    Scan the Akashic system and build wiring map.
    Shows all fairy connections, subscriptions, relationships.
    
    Returns:
        JSON with scan results
    """
    try:
        from P00_Autonomic.nervous_system.wiring_map import scan_wiring, get_wiring_map
        results = scan_wiring()
        wm = get_wiring_map()
        return json.dumps({
            "scan": results,
            "fairies_found": len(wm.fairies),
            "topics_found": len(wm.topic_subscribers),
        }, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})

@mcp.tool()
async def wiring_map_ascii() -> str:
    """
    Get ASCII visualization of system wiring.
    Shows overmind, infrastructure, and per-plane fairies.
    
    Returns:
        ASCII art wiring map
    """
    try:
        from P00_Autonomic.nervous_system.wiring_map import get_wiring_map, scan_wiring
        scan_wiring()  # Refresh
        wm = get_wiring_map()
        return wm.generate_ascii_map()
    except Exception as e:
        return f"Error: {e}"

@mcp.tool()
async def wiring_incomplete() -> str:
    """
    Get list of fairies with incomplete wiring.
    Shows what infrastructure each fairy is missing.
    
    Returns:
        JSON list of incomplete fairies and what they're missing
    """
    try:
        from P00_Autonomic.nervous_system.wiring_map import get_wiring_map, scan_wiring
        scan_wiring()
        wm = get_wiring_map()
        incomplete = wm.get_incomplete_fairies()
        return json.dumps({
            "incomplete_count": len(incomplete),
            "fairies": incomplete,
        }, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})

@mcp.tool()
async def wiring_fairy_check(fairy_name: str) -> str:
    """
    Check wiring completeness for a specific fairy.
    
    Args:
        fairy_name: Name of fairy to check (e.g., "ClaudeFairy")
        
    Returns:
        JSON with completeness score and missing infrastructure
    """
    try:
        from P00_Autonomic.nervous_system.wiring_map import get_wiring_map, scan_wiring
        scan_wiring()
        wm = get_wiring_map()
        result = wm.check_fairy_completeness(fairy_name)
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})

@mcp.tool()
async def wiring_system_state() -> str:
    """
    Get aggregated system state for overmind view.
    This is what UnconsciousMind/ClaudeFairy/Nous see.
    
    Returns:
        JSON with full system state overview
    """
    try:
        from P00_Autonomic.nervous_system.wiring_map import get_wiring_map, scan_wiring
        scan_wiring()
        wm = get_wiring_map()
        state = wm.get_system_state_for_overmind()
        return json.dumps(state, indent=2, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)})

@mcp.tool()
async def wiring_topic_flow() -> str:
    """
    Get message topic flow - who subscribes to what.
    
    Returns:
        JSON with topics and their subscribers
    """
    try:
        from P00_Autonomic.nervous_system.wiring_map import get_wiring_map, scan_wiring
        scan_wiring()
        wm = get_wiring_map()
        flow = wm.get_topic_flow()
        return json.dumps({
            "topic_count": len(flow),
            "topics": flow,
        }, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})

@mcp.tool()
async def wiring_mermaid() -> str:
    """
    Generate Mermaid diagram code for wiring visualization.
    Can be pasted into Mermaid renderer for visual graph.
    
    Returns:
        Mermaid flowchart code
    """
    try:
        from P00_Autonomic.nervous_system.wiring_map import get_wiring_map
        wm = get_wiring_map()
        return wm.generate_mermaid()
    except Exception as e:
        return f"Error: {e}"




# =============================================================================
# SMART FILE TOOLS - For reading large files
# =============================================================================

@mcp.tool()
def read_large_file(
    path: str,
    start_line: int = 1,
    max_lines: int = 500,
    search: str = ""
) -> str:
    """
    Smart reader for LARGE files (handles 2000+ line files).
    
    - Shows file structure (classes/functions with line numbers)
    - Can search within file  
    - Reads in chunks by line range
    
    Args:
        path: File path (relative to project root)
        start_line: Start from this line (1-indexed, default 1)
        max_lines: Max lines to return (default 500)
        search: Optional regex pattern to search for
        
    Returns:
        JSON with content, structure, and metadata
    """
    import re as regex_module
    root = os.getenv("AKASHIC_ROOT", os.getcwd())
    full_path = Path(root) / path if not Path(path).is_absolute() else Path(path)
    
    if not full_path.exists():
        return json.dumps({"error": f"File not found: {path}"})
    
    try:
        with open(full_path, 'r', encoding='utf-8', errors='replace') as f:
            all_lines = f.readlines()
    except Exception as e:
        return json.dumps({"error": f"Read error: {e}"})
    
    total_lines = len(all_lines)
    result = {"path": str(path), "total_lines": total_lines}
    
    # Extract structure (always useful for large files)
    structure = []
    for i, line in enumerate(all_lines):
        stripped = line.strip()
        if stripped.startswith('class ') or stripped.startswith('def ') or stripped.startswith('async def '):
            structure.append({"line": i + 1, "definition": stripped[:120]})
    result["structure"] = structure
    result["structure_count"] = len(structure)
    
    # Search mode - return matching lines
    if search:
        matches = []
        try:
            pattern = regex_module.compile(search, regex_module.IGNORECASE)
            for i, line in enumerate(all_lines):
                if pattern.search(line):
                    matches.append({"line": i + 1, "match": line.strip()[:200]})
                    if len(matches) >= 30:
                        break
        except Exception:
            pass
        result["matches"] = matches
        result["match_count"] = len(matches)
        return json.dumps(result, indent=2)
    
    # Range read
    start_idx = max(0, start_line - 1)
    end_idx = min(start_idx + max_lines, total_lines)
    result["content"] = ''.join(all_lines[start_idx:end_idx])
    result["start_line"] = start_idx + 1
    result["end_line"] = end_idx
    result["is_truncated"] = end_idx < total_lines
    if result["is_truncated"]:
        result["remaining"] = total_lines - end_idx
        result["hint"] = f"Use start_line={end_idx + 1} to continue"
    return json.dumps(result, indent=2)


@mcp.tool()
def file_structure(path: str) -> str:
    """
    Get structure of a file - class/function definitions with line numbers.
    
    Use this FIRST on large files to understand the layout before reading sections.
    
    Args:
        path: File path
        
    Returns:
        JSON with all class/function definitions and their line numbers
    """
    root = os.getenv("AKASHIC_ROOT", os.getcwd())
    full_path = Path(root) / path if not Path(path).is_absolute() else Path(path)
    
    if not full_path.exists():
        return json.dumps({"error": f"File not found: {path}"})
    
    try:
        with open(full_path, 'r', encoding='utf-8', errors='replace') as f:
            all_lines = f.readlines()
    except Exception as e:
        return json.dumps({"error": f"Read error: {e}"})
    
    structure = []
    current_class = None
    
    for i, line in enumerate(all_lines):
        stripped = line.strip()
        indent = len(line) - len(line.lstrip())
        
        if stripped.startswith('class '):
            current_class = stripped.split('(')[0].replace('class ', '').split(':')[0]
            structure.append({
                "line": i + 1,
                "type": "class",
                "name": current_class,
                "definition": stripped[:150]
            })
        elif stripped.startswith('def ') or stripped.startswith('async def '):
            is_method = indent > 0 and current_class
            name = stripped.split('(')[0].replace('def ', '').replace('async ', '').strip()
            structure.append({
                "line": i + 1,
                "type": "method" if is_method else "function",
                "name": name,
                "class": current_class if is_method else None,
                "definition": stripped[:150]
            })
    
    return json.dumps({
        "path": str(path),
        "total_lines": len(all_lines),
        "structure_count": len(structure),
        "structure": structure
    }, indent=2)


@mcp.tool()
def file_section(path: str, start: int, end: int) -> str:
    """
    Read specific lines from a file.
    
    Args:
        path: File path
        start: Start line (1-indexed)
        end: End line (1-indexed, inclusive)
        
    Returns:
        Content of those lines with metadata
    """
    root = os.getenv("AKASHIC_ROOT", os.getcwd())
    full_path = Path(root) / path if not Path(path).is_absolute() else Path(path)
    
    if not full_path.exists():
        return json.dumps({"error": f"File not found: {path}"})
    
    try:
        with open(full_path, 'r', encoding='utf-8', errors='replace') as f:
            all_lines = f.readlines()
    except Exception as e:
        return json.dumps({"error": f"Read error: {e}"})
    
    total = len(all_lines)
    start_idx = max(0, start - 1)
    end_idx = min(end, total)
    
    selected = all_lines[start_idx:end_idx]
    
    return json.dumps({
        "path": str(path),
        "total_lines": total,
        "start_line": start_idx + 1,
        "end_line": end_idx,
        "lines_returned": len(selected),
        "content": ''.join(selected)
    }, indent=2)


if __name__ == "__main__":
    main()
