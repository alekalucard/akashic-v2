"""
Quick test to verify the MCP server will start cleanly.
This simulates what Claude Desktop does.

NOTE: This is a TEST file - only runs when executed directly,
NOT during boot import!
"""

def run_startup_test():
    """Run the MCP startup test."""
    import subprocess
    import sys
    import os
    import time

    print("=" * 60)
    print("MCP Server Startup Test")
    print("=" * 60)

    # Dynamic root detection - works from any drive!
    from pathlib import Path
    SCRIPT_DIR = Path(__file__).resolve().parent
    PROJECT_ROOT = SCRIPT_DIR.parents[1]  # Go up from mcp -> P40_Sensory -> ebook

    # Change to the MCP directory
    os.chdir(SCRIPT_DIR)
    print(f"\nWorking directory: {os.getcwd()}")
    print(f"Project root: {PROJECT_ROOT}")

    # Set environment variables like Claude Desktop would
    env = os.environ.copy()
    env["AKASHIC_PROJECT_ROOT"] = str(PROJECT_ROOT)
    env["PYTHONPATH"] = str(PROJECT_ROOT)

    print("\nStarting server process (will timeout after 3 seconds)...")
    print("Watching for stdout output (should be EMPTY for MCP to work)...\n")

    try:
        # Start the server
        proc = subprocess.Popen(
            [sys.executable, "akashic_mcp_server.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            text=True
        )
        
        # Wait a bit for it to output anything
        time.sleep(2)
        
        # Check if it's still running
        poll = proc.poll()
        
        if poll is None:
            # Still running - good! Kill it
            print("[OK] Server is running (no crash)")
            proc.terminate()
            proc.wait(timeout=2)
        else:
            print(f"[X] Server exited with code: {poll}")
        
        # Check stdout - should be EMPTY for MCP to work
        stdout, stderr = proc.communicate(timeout=1)
        
        if stdout.strip():
            print(f"\n[X] PROBLEM: Server printed to stdout (breaks MCP protocol!):")
            print(f"   '{stdout[:200]}...'")
        else:
            print("[OK] No stdout output (good for MCP)")
        
        if stderr.strip():
            print(f"\n! Stderr (errors/warnings):")
            print(f"   {stderr[:500]}")
        else:
            print("[OK] No stderr output")
            
    except subprocess.TimeoutExpired:
        proc.kill()
        print("[OK] Server running without errors (killed after timeout)")
    except Exception as e:
        print(f"[X] Error: {e}")

    print("\n" + "=" * 60)
    print("If you see '[OK] Server is running' and '[OK] No stdout output',")
    print("the server should work with Claude Desktop!")
    print("=" * 60)


# CRITICAL: Only run when executed directly, NOT during import!
if __name__ == "__main__":
    run_startup_test()
