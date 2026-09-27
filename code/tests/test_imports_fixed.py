#!/usr/bin/env python3
"""
Quick test to verify all MCP tool imports work after the path fix.

NOTE: This is a TEST file - only runs when executed directly,
NOT during boot import!
"""


def run_import_tests():
    """Run the import tests."""
    import sys
    from pathlib import Path

    # Replicate the same path setup as akashic_mcp_server.py
    _mcp_dir = Path(__file__).parent
    _project_root = _mcp_dir.parent.parent
    sys.path.insert(0, str(_project_root))
    sys.path.insert(0, str(_mcp_dir))

    print(f"Project root: {_project_root}")
    print(f"MCP dir: {_mcp_dir}")
    print(f"Testing imports...\n")

    modules_to_test = [
        ("agent_tools_async", "register_async_agent_tools"),
        ("somatic_tools", "register_somatic_tools"),
        ("session_memory_tools", "register_session_memory_tools"),
        ("working_memory_tools", "register_working_memory_tools"),
        ("companion_tools", "register_companion_tools"),
        ("boot_observer_tools", "register_boot_observer_tools"),
        ("consciousness_monitor_tools", "register_consciousness_monitor_tools"),
        ("batch_tools", "batch_execute"),
    ]

    results = []
    for module_name, func_name in modules_to_test:
        try:
            module = __import__(module_name)
            has_func = hasattr(module, func_name)
            results.append((module_name, "[OK]" if has_func else f"[WARN] Missing {func_name}"))
        except ImportError as e:
            results.append((module_name, f"[FAIL] ImportError: {e}"))
        except Exception as e:
            results.append((module_name, f"[FAIL] {type(e).__name__}: {e}"))

    print("=" * 60)
    print("Import Test Results:")
    print("=" * 60)
    for module_name, status in results:
        print(f"  {module_name:35} {status}")

    passed = sum(1 for _, s in results if s.startswith("[OK]"))
    print(f"\n{passed}/{len(results)} modules imported successfully")

    if passed == len(results):
        print("\n*** All imports working! MCP server should boot cleanly now. ***")
    else:
        print("\n*** Some imports still failing - check individual errors above. ***")


# CRITICAL: Only run when executed directly, NOT during boot import!
if __name__ == "__main__":
    run_import_tests()
