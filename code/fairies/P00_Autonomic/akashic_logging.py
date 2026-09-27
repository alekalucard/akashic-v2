"""
Akashic Logging - MCP-Safe Unified Logging

All output must go to stderr when MCP is active (stdout = JSON-RPC protocol).
This module provides a drop-in replacement for print() that respects MCP mode.

Usage:
    from fairies.P00_Autonomic.akashic_logging import alog, aprint
    
    alog("MyFairy", "Initialized successfully")  # -> [MyFairy] Initialized successfully
    aprint("Plain message")                       # -> Plain message

The module auto-detects MCP mode via:
1. AKASHIC_MCP_MODE=1 environment variable
2. Detection of MCP server in call stack
3. stdout not being a real TTY

"""

from __future__ import annotations

import os
import sys
import re
from typing import Optional
from datetime import datetime

# ============================================================================
# MCP MODE DETECTION
# ============================================================================

_mcp_mode: Optional[bool] = None

def is_mcp_mode() -> bool:
    """
    Detect if we're running inside MCP server context.
    
    Returns True if output should go to stderr to protect stdout.
    """
    global _mcp_mode
    
    if _mcp_mode is not None:
        return _mcp_mode
    
    # Check explicit environment variable
    if os.environ.get("AKASHIC_MCP_MODE") == "1":
        _mcp_mode = True
        return True
    
    # Check if stdout is redirected (MCP does this)
    if hasattr(sys.stdout, '_StderrRedirector') or \
       (hasattr(sys.stdout, '__class__') and 'Redirector' in sys.stdout.__class__.__name__):
        _mcp_mode = True
        return True
    
    # Check for MCP in module names (MCP server imported)
    for name in sys.modules:
        if 'mcp.server' in name or 'fastmcp' in name:
            _mcp_mode = True
            return True
    
    # Default: not MCP mode
    _mcp_mode = False
    return False


def set_mcp_mode(enabled: bool):
    """Explicitly set MCP mode (call early in MCP server startup)."""
    global _mcp_mode
    _mcp_mode = enabled


# ============================================================================
# ANSI COLOR HANDLING
# ============================================================================

# ANSI escape code pattern
_ANSI_PATTERN = re.compile(r'\x1b\[[0-9;]*m')

def strip_ansi(text: str) -> str:
    """Remove ANSI color codes from text."""
    return _ANSI_PATTERN.sub('', text)


# ============================================================================
# CORE LOGGING FUNCTIONS
# ============================================================================

def _get_output_stream():
    """Get the appropriate output stream based on mode."""
    if is_mcp_mode():
        return sys.stderr
    return sys.stdout


def aprint(*args, sep=' ', end='\n', flush=True, force_stderr=False, file=None):
    """
    MCP-safe print replacement.
    
    In MCP mode: writes to stderr
    Otherwise: writes to stdout
    
    Args:
        *args: Items to print
        sep: Separator between items
        end: End character
        flush: Whether to flush after write
        force_stderr: Always use stderr regardless of mode
        file: Output stream (for compatibility with builtins.print;
              if provided, overrides normal stream selection)
    """
    # If explicit file is provided (e.g., from traceback module), use it
    if file is not None:
        stream = file
    else:
        stream = sys.stderr if force_stderr else _get_output_stream()
    
    text = sep.join(str(arg) for arg in args)
    
    # Strip ANSI in MCP mode (can cause JSON parse errors)
    if is_mcp_mode():
        text = strip_ansi(text)
    
    try:
        stream.write(text + end)
        if flush:
            stream.flush()
    except Exception:
        # Failsafe - try stderr
        try:
            sys.stderr.write(text + end)
            sys.stderr.flush()
        except Exception:
            pass  # Give up silently


def alog(source: str, message: str, level: str = "INFO"):
    """
    Structured log message with source tag.
    
    Args:
        source: Source identifier (fairy name, module, etc.)
        message: Log message
        level: Log level (INFO, WARN, ERROR, DEBUG)
    
    Example:
        alog("ClaudeFairy", "Initialized")
        # -> [ClaudeFairy] Initialized
    """
    # Format: [Source] Message
    formatted = f"[{source}] {message}"
    aprint(formatted)


def alog_debug(source: str, message: str):
    """Debug-level log (only shown if AKASHIC_DEBUG=1)."""
    if os.environ.get("AKASHIC_DEBUG") == "1":
        alog(source, f"(debug) {message}", "DEBUG")


def alog_error(source: str, message: str):
    """Error-level log (always to stderr)."""
    formatted = f"[{source}] ERROR: {message}"
    aprint(formatted, force_stderr=True)


def alog_warn(source: str, message: str):
    """Warning-level log."""
    alog(source, f"⚠ {message}", "WARN")


# ============================================================================
# BOOT WAVE LOGGING (special formatting for boot sequence)
# ============================================================================

def boot_log(plane: str, fairy: str, status: str, time_ms: Optional[float] = None):
    """
    Log boot wave progress.
    
    Args:
        plane: Plane identifier (P00, P10, etc.)
        fairy: Fairy name
        status: Status (OK, FAIL, SKIP, etc.)
        time_ms: Optional timing in milliseconds
    """
    time_str = f" ({time_ms:.1f}ms)" if time_ms is not None else ""
    alog("boot-wave", f"{plane}/{fairy}: {status}{time_str}")


# ============================================================================
# CONTEXT MANAGER FOR TEMPORARY MCP MODE
# ============================================================================

class mcp_safe_output:
    """
    Context manager that temporarily enables MCP-safe output.
    
    Usage:
        with mcp_safe_output():
            print("This goes to stderr")
    """
    def __init__(self):
        self._old_mode = None
    
    def __enter__(self):
        global _mcp_mode
        self._old_mode = _mcp_mode
        _mcp_mode = True
        return self
    
    def __exit__(self, *args):
        global _mcp_mode
        _mcp_mode = self._old_mode


# ============================================================================
# MONKEY-PATCH HELPER (use sparingly!)
# ============================================================================

_original_print = None

def patch_builtin_print():
    """
    Replace builtin print() with aprint().
    
    WARNING: This is aggressive. Only call this in MCP server startup.
    """
    global _original_print
    import builtins
    
    if _original_print is None:
        _original_print = builtins.print
    
    builtins.print = aprint


def restore_builtin_print():
    """Restore original print() function."""
    global _original_print
    import builtins
    
    if _original_print is not None:
        builtins.print = _original_print
        _original_print = None


# ============================================================================
# AUTO-SETUP ON IMPORT
# ============================================================================

# Check mode on import (caches result)
_detected = is_mcp_mode()
