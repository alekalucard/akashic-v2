"""
MCP Tools - Organized tool modules.

Categories:
- introspection: Self-awareness and system understanding
- file_ops: File and directory operations
- memory: Memory search and session management
- fairy: Fairy management and monitoring
- unconscious: UnconsciousMindFairy access (helix, pain, diagnostics)
- wiring: Postal system inspection (in introspection)
"""

from .introspection import register_introspection_tools
from .file_ops import register_file_ops_tools
from .memory import register_memory_tools
from .fairy import register_fairy_tools
from .unconscious import register_unconscious_tools


def register_all_tools(server) -> None:
    """Register all tool categories with an MCP server."""
    register_introspection_tools(server)
    register_file_ops_tools(server)
    register_memory_tools(server)
    register_fairy_tools(server)
    register_unconscious_tools(server)


__all__ = [
    "register_introspection_tools",
    "register_file_ops_tools",
    "register_memory_tools",
    "register_fairy_tools",
    "register_unconscious_tools",
    "register_all_tools",
]
