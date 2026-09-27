"""
claude_fairy.py - Stub for akashic_v2

This is a compatibility stub for MCP tools that expect ebook's ClaudeFairy.
In akashic_v2, the Claude interface is handled differently.

TODO: Implement proper Claude fairy for akashic_v2
"""

from typing import Optional
from pathlib import Path


class ClaudeFairy:
    """Stub ClaudeFairy for akashic_v2 compatibility."""

    def __init__(self):
        self.name = "ClaudeFairy"
        self.plane = "P60"
        self._thoughts_emitted = 0

    def emit_thought(self, thought: str):
        """Emit a thought (stub)."""
        self._thoughts_emitted += 1
        print(f"[ClaudeFairy] Thought: {thought}")

    def get_status(self) -> dict:
        return {
            "name": self.name,
            "plane": self.plane,
            "thoughts_emitted": self._thoughts_emitted,
            "source": "akashic_v2_stub",
        }


_instance: Optional[ClaudeFairy] = None


def get_claude_fairy() -> ClaudeFairy:
    """Get or create ClaudeFairy singleton."""
    global _instance
    if _instance is None:
        _instance = ClaudeFairy()
    return _instance


# File location for self-reflection tools
CLAUDE_FAIRY_FILE = Path(__file__)


__all__ = ["ClaudeFairy", "get_claude_fairy", "CLAUDE_FAIRY_FILE"]
