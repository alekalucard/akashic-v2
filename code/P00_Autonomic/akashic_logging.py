"""
akashic_logging.py - Stub for akashic_v2

Provides MCP-safe print patching stubs.
"""

import sys


def patch_builtin_print():
    """Stub - print patching not implemented in akashic_v2."""
    pass


def set_mcp_mode(enabled: bool):
    """Stub - MCP mode flag not implemented in akashic_v2."""
    pass


class StderrRedirector:
    """Redirect stdout to stderr for MCP safety."""

    def __init__(self):
        self._stderr = sys.stderr

    def write(self, msg):
        self._stderr.write(msg)

    def flush(self):
        self._stderr.flush()


__all__ = ["patch_builtin_print", "set_mcp_mode", "StderrRedirector"]
