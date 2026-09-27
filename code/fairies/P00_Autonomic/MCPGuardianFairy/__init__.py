"""
MCPGuardianFairy — Server-side MCP tunnel connection guardian.

The bridge between worlds needs a keeper.
"""

from .fairy import MCPGuardianFairy

ACTOR_NAME = "MCPGuardianFairy"
FAIRY_CLASS = MCPGuardianFairy

__all__ = ["MCPGuardianFairy", "FAIRY_CLASS"]
