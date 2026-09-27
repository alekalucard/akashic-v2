"""
Test script for Akashic MCP Server
Run this to diagnose why the server might not be starting.

Usage: python test_mcp_server.py

NOTE: This is a TEST file - only runs when executed directly,
NOT during boot import!
"""


def run_diagnostic():
    """Run the MCP server diagnostic."""
    import sys
    import os
    from pathlib import Path
    
    # Dynamic path detection - works from any drive!
    _mcp_dir = Path(__file__).resolve().parent
    _project_root = _mcp_dir.parent.parent
    
    sys.path.insert(0, str(_project_root))
    os.chdir(_mcp_dir)

    print("=" * 60)
    print("Akashic MCP Server Diagnostic")
    print("=" * 60)
    print(f"\nProject root: {_project_root}")
    print(f"MCP dir: {_mcp_dir}")

    # Test 1: Can we import MCP?
    print("\n[1] Testing MCP import...")
    try:
        from mcp.server.fastmcp import FastMCP
        print("    [OK] MCP imported successfully")
    except ImportError as e:
        print(f"    [X] MCP import failed: {e}")
        print("    → Run: pip install mcp")

    # Test 2: Can we import the server module?
    print("\n[2] Testing akashic_mcp_server import...")
    try:
        # Temporarily redirect stderr to catch any import-time errors
        import io
        old_stderr = sys.stderr
        sys.stderr = io.StringIO()
        
        import akashic_mcp_server
        
        stderr_output = sys.stderr.getvalue()
        sys.stderr = old_stderr
        
        print("    [OK] Module imported successfully")
        if stderr_output:
            print(f"    ! Stderr during import:\n{stderr_output[:500]}")
    except Exception as e:
        sys.stderr = old_stderr
        print(f"    [X] Import failed: {e}")
        import traceback
        traceback.print_exc()

    # Test 3: Check feature flags
    print("\n[3] Checking feature availability...")
    try:
        features = {
            "MCP": akashic_mcp_server.HAS_MCP,
            "PyAutoGUI": akashic_mcp_server.HAS_PYAUTOGUI,
            "PIL": akashic_mcp_server.HAS_PIL,
            "Tesseract": akashic_mcp_server.HAS_TESSERACT,
            "Input Monitor": akashic_mcp_server.HAS_INPUT_MONITOR,
            "GetWindow": akashic_mcp_server.HAS_GETWINDOW,
            "Google Drive": akashic_mcp_server.HAS_GOOGLE_DRIVE,
        }
        
        # Additional features from extensions
        for name in ["HAS_COGNITIVE", "HAS_AGENTS", "HAS_CODEX", "HAS_SIM", "HAS_LEARNING", "HAS_SATELLITE", "HAS_HARVESTER"]:
            if hasattr(akashic_mcp_server, name):
                features[name.replace("HAS_", "")] = getattr(akashic_mcp_server, name)
        
        for name, available in features.items():
            status = "[OK]" if available else "[FAIL]"
            print(f"    {status} {name}")
    except Exception as e:
        print(f"    [X] Error checking features: {e}")

    # Test 4: Can we access PROJECT_ROOT?
    print("\n[4] Checking paths...")
    try:
        print(f"    PROJECT_ROOT: {akashic_mcp_server.PROJECT_ROOT}")
        print(f"    Exists: {akashic_mcp_server.PROJECT_ROOT.exists()}")
    except Exception as e:
        print(f"    [X] Error: {e}")

    # Test 5: Test a simple tool
    print("\n[5] Testing a tool (list_directory)...")
    try:
        result = akashic_mcp_server.list_directory(".")
        import json
        data = json.loads(result)
        print(f"    [OK] Got {len(data)} items in current directory")
    except Exception as e:
        print(f"    [X] Tool test failed: {e}")

    # Test 6: Check for PyQt6 (needed for open_chat_window)
    print("\n[6] Testing PyQt6...")
    try:
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtCore import QEvent
        print("    [OK] PyQt6 available")
    except ImportError as e:
        print(f"    ! PyQt6 not available: {e}")
        print("    → Some GUI tools may not work")

    print("\n" + "=" * 60)
    print("Diagnostic complete!")
    print("=" * 60)


# CRITICAL: Only run when executed directly, NOT during boot import!
if __name__ == "__main__":
    run_diagnostic()
