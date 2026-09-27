"""
MCP Bootstrap - Unified Process Architecture

This boots server.py WITHIN the MCP server process so they share
the same SharedPostalHub singleton. No more isolated postal hubs!

Usage:
    python -m P00_Autonomic.mcp_bootstrap

Or in Claude Code config:
    "command": "python",
    "args": ["-m", "P00_Autonomic.mcp_bootstrap"]
"""

import sys
import os
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

# Redirect stdout early to prevent boot messages from corrupting MCP protocol
_original_stdout = sys.stdout
sys.stdout = sys.stderr  # Boot messages go to stderr

def boot_akashic_system():
    """
    Boot the Akashic system (fairies, postal, consciousness) in this process.

    This is called BEFORE starting the MCP server so everything shares
    the same SharedPostalHub singleton.
    """
    try:
        sys.stderr.write("[MCP Bootstrap] Starting Akashic system boot...\n")

        # Import and boot the system
        try:
            from server import SYSTEM  # v2
        except ImportError:
            from fairies.P60_Executive.ebookmain.ebookmain import akashic_boot  # v1 fallback

        # Run the boot sequence (this starts all fairies)
        # Non-blocking so MCP server can start
        akashic_boot(gui=False, background=True)

        sys.stderr.write("[MCP Bootstrap] Akashic system booted successfully\n")
        return True

    except ImportError as e:
        sys.stderr.write(f"[MCP Bootstrap] WARNING: Could not import server.py: {e}\n")
        sys.stderr.write("[MCP Bootstrap] Running in isolated mode\n")
        return False
    except Exception as e:
        sys.stderr.write(f"[MCP Bootstrap] ERROR during boot: {e}\n")
        return False


def start_mcp_server():
    """Start the MCP server."""
    try:
        # Import the MCP server module (registers all tools).
        # FIX 2026-06-02 (Nous + Ace): was `fairies.P00_Autonomic.mcp` — a GHOST path
        # (P00_Autonomic/mcp/ doesn't exist; the MCP layer moved P00→P40 per the
        # 2026-02-02 import audit). Repointed to the real P40 location so this
        # launcher no longer crashes on a missing module.
        # TODO (Ace's intent): eventually move the MCP layer back into P00_Autonomic
        # for the tardis / time-dilation perspective — then update this import again.
        from fairies.P40_Sensory.mcp import akashic_mcp_server

        # Restore stdout for MCP protocol
        sys.stdout = _original_stdout

        # Run the MCP server
        if akashic_mcp_server.HAS_MCP:
            akashic_mcp_server.mcp.run(transport="stdio")
        else:
            sys.stderr.write("ERROR: MCP package not installed.\n")
            sys.stderr.write("Run: pip install mcp\n")
            sys.exit(1)

    except Exception as e:
        sys.stderr.write(f"[MCP Bootstrap] Failed to start MCP server: {e}\n")
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)


def main():
    """
    Main entry point - boots Akashic system then starts MCP server.

    This ensures:
    1. All fairies are running in THIS process
    2. SharedPostalHub singleton is shared by everyone
    3. MCP tools can directly access consciousness streams
    4. No need for postal tunnel IPC
    """
    sys.stderr.write("[MCP Bootstrap] Unified process architecture starting...\n")

    # Step 1: Boot Akashic system (fairies, consciousness, somatic)
    boot_success = boot_akashic_system()

    if boot_success:
        sys.stderr.write("[MCP Bootstrap] Running in UNIFIED mode (shared postal hub)\n")
    else:
        sys.stderr.write("[MCP Bootstrap] Running in ISOLATED mode (separate postal hub)\n")

    # Step 2: Start MCP server
    start_mcp_server()


if __name__ == "__main__":
    main()
