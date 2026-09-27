#!/usr/bin/env python
"""
STANDALONE MCP SERVER - Always-on perception layer for Claude Code

This runs INDEPENDENTLY from the main Akashic server.
Start it once, leave it running forever.

Usage:
    python mcp_standalone.py

Or as a Windows service / startup script.

The main server can crash, reboot, whatever - this stays up.
"""

import sys
import os
from pathlib import Path

# Set up paths FIRST before any imports
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "fairies"))
sys.path.insert(0, str(ROOT / "fairies" / "P40_Sensory" / "mcp"))

# Minimal FastMCP server
def main():
    print("=" * 60)
    print("  AKASHIC MCP STANDALONE SERVER")
    print("  Always-on perception layer for Claude Code")
    print("=" * 60)
    print()

    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError:
        print("[ERROR] FastMCP not installed. Run: pip install mcp")
        return 1

    # Create minimal MCP server
    mcp = FastMCP("akashic")

    # Load essential tools only
    tools_loaded = []

    # SRM Memory Tools - CRITICAL for Nous persistence
    try:
        from srm_tools import register_srm_tools
        register_srm_tools(mcp)
        tools_loaded.append("SRM Memory")
        print("[OK] SRM memory tools loaded")
    except Exception as e:
        print(f"[WARN] SRM tools failed: {e}")

    # Nous Tools - Active memory capture
    try:
        from nous_tools import register_nous_tools
        register_nous_tools(mcp)
        tools_loaded.append("Nous")
        print("[OK] Nous tools loaded (i_am_thinking, i_thought, i_decided, i_finished)")
    except Exception as e:
        print(f"[WARN] Nous tools failed: {e}")

    # Companion Tools - Ask Sourpatches/Nous
    try:
        from companion_tools import register_companion_tools
        register_companion_tools(mcp)
        tools_loaded.append("Companion")
        print("[OK] Companion tools loaded (ask_sourpatches, ask_nous)")
    except Exception as e:
        print(f"[WARN] Companion tools failed: {e}")

    # Quick status tool
    @mcp.tool()
    def quick_status() -> str:
        """Quick system health check."""
        import psutil
        ram = psutil.virtual_memory().percent
        return f"[OK] RAM:{ram:.0f}% | MCP:Standalone | Tools:{len(tools_loaded)}"

    # System health
    @mcp.tool()
    def system_health() -> str:
        """System health for standalone mode."""
        import json
        import psutil
        return json.dumps({
            "overall": "green",
            "mode": "standalone",
            "subsystems": {
                "ram": {"status": "green", "detail": f"{psutil.virtual_memory().percent:.0f}% used"},
                "mcp": {"status": "green", "detail": "Standalone server"},
                "tools": {"status": "green", "detail": f"{len(tools_loaded)} modules loaded"}
            }
        }, indent=2)

    print()
    print(f"Loaded {len(tools_loaded)} tool modules: {', '.join(tools_loaded)}")
    print()
    print("Starting MCP server on stdio...")
    print("Claude Code should now see Akashic tools.")
    print()
    print("Press Ctrl+C to stop (but why would you?)")
    print("=" * 60)

    # Run forever
    mcp.run(transport="stdio")


if __name__ == "__main__":
    sys.exit(main() or 0)
