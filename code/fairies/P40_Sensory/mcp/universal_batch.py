# ==============================================================================
# UNIVERSAL BATCH - Execute ANY MCP tool in parallel
# ==============================================================================
#
# Evolution of batch_tools.py that can execute ALL 136+ MCP tools in parallel.
#
# Architecture:
# 1. Auto-discovers tools from MCP registry at runtime
# 2. Executes operations in parallel via ThreadPoolExecutor
# 3. Falls back gracefully for unknown tools
#
# Usage:
#   universal_batch([
#       {"tool": "consciousness_status", "args": {}},
#       {"tool": "feel_body", "args": {}},
#       {"tool": "boot_get_latest_summary", "args": {}},
#   ])
#
# ==============================================================================

from __future__ import annotations

import json
import time
import sys
import os
import threading
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

# Add project root
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# ==============================================================================
# TOOL REGISTRY - Maps tool names to callable implementations
# ==============================================================================

_TOOL_REGISTRY: Dict[str, Callable] = {}
_REGISTRY_LOCK = threading.Lock()
_REGISTRY_BUILT = False

def _build_registry_from_mcp(mcp_instance):
    """Build registry from a FastMCP instance's registered tools."""
    global _TOOL_REGISTRY, _REGISTRY_BUILT
    
    with _REGISTRY_LOCK:
        if _REGISTRY_BUILT:
            return
        
        # FastMCP stores tools in _tools dict
        if hasattr(mcp_instance, '_tools'):
            for name, tool_def in mcp_instance._tools.items():
                if hasattr(tool_def, 'fn'):
                    _TOOL_REGISTRY[name] = tool_def.fn
                elif callable(tool_def):
                    _TOOL_REGISTRY[name] = tool_def
        
        _REGISTRY_BUILT = True
        print(f"[UniversalBatch] Registry built with {len(_TOOL_REGISTRY)} tools")


def _build_registry_from_modules():
    """Build registry by importing tool modules directly."""
    global _TOOL_REGISTRY
    
    # Import each tool module and extract functions
    tool_modules = [
        ('somatic_tools', 'register_somatic_tools'),
        ('consciousness_monitor_tools', 'register_consciousness_monitor_tools'),
        ('boot_observer_tools', 'register_boot_observer_tools'),
        ('codex_integration', 'register_codex_tools'),
        ('cognitive_tools', 'register_cognitive_tools'),
        ('companion_tools', 'register_companion_tools'),
        ('learning_agent', 'register_learning_tools'),
        ('nous_tools', 'register_nous_tools'),
        ('satellite_system', 'register_satellite_tools'),
        ('session_memory_tools', 'register_session_memory_tools'),
        ('simulator_tools', 'register_simulator_tools'),
        ('working_memory_tools', 'register_working_memory_tools'),
        ('agent_tools_async', 'register_async_agent_tools'),
    ]
    
    # Create a mock MCP that captures registrations
    class ToolCapture:
        def __init__(self):
            self.captured = {}
        
        def tool(self, name=None, description=None):
            def decorator(fn):
                tool_name = name or fn.__name__
                self.captured[tool_name] = fn
                return fn
            return decorator
    
    for module_name, register_func_name in tool_modules:
        try:
            module = __import__(module_name)
            register_func = getattr(module, register_func_name, None)
            if register_func:
                capture = ToolCapture()
                register_func(capture)
                _TOOL_REGISTRY.update(capture.captured)
        except Exception as e:
            print(f"[UniversalBatch] Failed to load {module_name}: {e}")
    
    print(f"[UniversalBatch] Module-based registry: {len(_TOOL_REGISTRY)} tools")


# ==============================================================================
# DIRECT TOOL IMPLEMENTATIONS - For critical tools that must always work
# ==============================================================================

def _direct_consciousness_status():
    """Direct implementation of consciousness_status."""
    try:
        from fairies.P00_Autonomic.nervous_system.consciousness_loop_fairy import get_consciousness_loop
        from fairies.P30_Cognition.cognition.working_memory_hub import get_working_memory_hub
        
        result = {"timestamp": time.time()}
        
        # Consciousness loop
        loop = get_consciousness_loop()
        if loop:
            result["consciousness_loop"] = {
                "exists": True,
                "working_tracers": len(getattr(loop, 'working_stream', {}).get('tracers', [])) if hasattr(loop, 'working_stream') else 0,
            }
        else:
            result["consciousness_loop"] = {"exists": False, "error": "No instance"}
        
        # Working memory
        hub = get_working_memory_hub()
        if hub:
            result["working_memory"] = {
                "exists": True,
                "reflective_tracers": hub.reflective_loop.count() if hasattr(hub, 'reflective_loop') else 0,
            }
        else:
            result["working_memory"] = {"exists": True, "reflective_tracers": 0, "reasoning_tracers": 0}
        
        return result
    except Exception as e:
        return {"error": str(e)}


def _direct_feel_body():
    """Direct implementation of feel_body."""
    try:
        from fairies.P20_Somatic.integration.somatic_integration import get_body
        body = get_body()
        if body:
            return body.feel()
        return {"description": "steady pulse", "heart_rate": 1.0, "coherence": 0.5}
    except Exception as e:
        return {"error": str(e)}


def _direct_get_waking_state():
    """Direct implementation of get_waking_state."""
    try:
        from fairies.P20_Somatic.circulation.waking_sequence_fairy import get_waking_sequence_fairy
        fairy = get_waking_sequence_fairy()
        return fairy.get_state()
    except Exception as e:
        return {"error": str(e)}


def _direct_session_get_handoff():
    """Direct implementation of session_get_handoff."""
    try:
        from session_memory_tools import _get_session_manager
        mgr = _get_session_manager()
        if mgr:
            return mgr.get_handoff_summary()
        return {"error": "Session manager not available"}
    except Exception as e:
        return {"error": str(e)}


# Map of direct implementations
DIRECT_TOOLS = {
    "consciousness_status": _direct_consciousness_status,
    "feel_body": _direct_feel_body,
    "get_waking_state": _direct_get_waking_state,
    "session_get_handoff": _direct_session_get_handoff,
}


# ==============================================================================
# FILESYSTEM OPERATIONS - Always available
# ==============================================================================

def _op_read_file(path: str, max_lines: int = 500) -> Dict:
    """Read file contents."""
    try:
        from batch_tools import op_read_file
        return op_read_file(path, max_lines)
    except:
        try:
            project_root = Path(os.environ.get('AKASHIC_ROOT', Path(__file__).parent.parent.parent))
            full_path = project_root / path
            with open(full_path, 'r', encoding='utf-8', errors='replace') as f:
                lines = f.readlines()
            if len(lines) > max_lines:
                lines = lines[:max_lines]
            return {"success": True, "content": "".join(lines), "lines": len(lines)}
        except Exception as e:
            return {"success": False, "error": str(e)}


def _op_search_text(pattern: str, directory: str = ".", file_pattern: str = "*.py") -> Dict:
    """Search for text pattern."""
    try:
        from batch_tools import op_search_text
        return op_search_text(pattern, directory, file_pattern)
    except:
        import re
        import glob
        project_root = Path(os.environ.get('AKASHIC_ROOT', Path(__file__).parent.parent.parent))
        search_dir = project_root / directory
        matches = []
        for fpath in search_dir.rglob(file_pattern):
            try:
                with open(fpath, 'r', encoding='utf-8', errors='replace') as f:
                    for i, line in enumerate(f, 1):
                        if re.search(pattern, line, re.IGNORECASE):
                            matches.append({
                                "file": str(fpath.relative_to(project_root)),
                                "line": i,
                                "content": line.strip()[:200]
                            })
            except:
                pass
        return {"success": True, "pattern": pattern, "matches": matches[:50], "count": len(matches)}


def _op_list_dir(path: str = ".") -> Dict:
    """List directory contents."""
    try:
        from batch_tools import op_list_dir
        return op_list_dir(path)
    except:
        project_root = Path(os.environ.get('AKASHIC_ROOT', Path(__file__).parent.parent.parent))
        full_path = project_root / path
        if not full_path.exists():
            return {"success": False, "error": f"Path not found: {path}"}
        entries = list(full_path.iterdir())
        return {
            "success": True,
            "path": str(path),
            "entries": [{"name": e.name, "is_dir": e.is_dir()} for e in entries[:100]]
        }


def _op_run_shell(command: str, cwd: str = "", timeout: int = 60) -> Dict:
    """Run shell command."""
    import subprocess
    project_root = Path(os.environ.get('AKASHIC_ROOT', Path(__file__).parent.parent.parent))
    work_dir = project_root / cwd if cwd else project_root
    try:
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True,
            timeout=timeout, cwd=str(work_dir)
        )
        return {
            "success": result.returncode == 0,
            "return_code": result.returncode,
            "stdout": result.stdout[:5000],
            "stderr": result.stderr[:2000]
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "error": f"Command timed out after {timeout}s"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def _op_run_python(code: str, timeout: int = 30) -> Dict:
    """Run Python code."""
    import subprocess
    project_root = Path(os.environ.get('AKASHIC_ROOT', Path(__file__).parent.parent.parent))
    temp_file = project_root / "_universal_temp.py"
    try:
        with open(temp_file, 'w', encoding='utf-8') as f:
            f.write(code)
        result = subprocess.run(
            [sys.executable, str(temp_file)],
            capture_output=True, text=True, timeout=timeout,
            cwd=str(project_root)
        )
        return {
            "success": result.returncode == 0,
            "return_code": result.returncode,
            "stdout": result.stdout[:10000],
            "stderr": result.stderr[:3000]
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "error": f"Timed out after {timeout}s"}
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        if temp_file.exists():
            temp_file.unlink()


# Core filesystem ops
CORE_OPS = {
    "read_file": _op_read_file,
    "fs_read": _op_read_file,
    "search_text": _op_search_text,
    "fs_grep": _op_search_text,
    "list_dir": _op_list_dir,
    "fs_tree": _op_list_dir,
    "run_shell": _op_run_shell,
    "run_python": _op_run_python,
}


# ==============================================================================
# UNIVERSAL EXECUTOR
# ==============================================================================

def execute_tool(tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    """Execute a single tool by name with given arguments."""
    start = time.perf_counter()
    
    try:
        # Priority 1: Direct implementations (most reliable)
        if tool_name in DIRECT_TOOLS:
            result = DIRECT_TOOLS[tool_name](**args) if args else DIRECT_TOOLS[tool_name]()
            return {
                "success": True,
                "tool": tool_name,
                "result": result,
                "duration_ms": (time.perf_counter() - start) * 1000,
                "source": "direct"
            }
        
        # Priority 2: Core filesystem ops
        if tool_name in CORE_OPS:
            result = CORE_OPS[tool_name](**args) if args else CORE_OPS[tool_name]()
            return {
                "success": True,
                "tool": tool_name,
                "result": result,
                "duration_ms": (time.perf_counter() - start) * 1000,
                "source": "core"
            }
        
        # Priority 3: Registry lookup
        if tool_name in _TOOL_REGISTRY:
            result = _TOOL_REGISTRY[tool_name](**args) if args else _TOOL_REGISTRY[tool_name]()
            return {
                "success": True,
                "tool": tool_name,
                "result": result,
                "duration_ms": (time.perf_counter() - start) * 1000,
                "source": "registry"
            }
        
        # Unknown tool
        return {
            "success": False,
            "tool": tool_name,
            "error": f"Unknown tool: {tool_name}",
            "available_direct": list(DIRECT_TOOLS.keys()),
            "available_core": list(CORE_OPS.keys()),
            "duration_ms": (time.perf_counter() - start) * 1000
        }
        
    except Exception as e:
        return {
            "success": False,
            "tool": tool_name,
            "error": str(e),
            "duration_ms": (time.perf_counter() - start) * 1000
        }


def universal_batch(operations: List[Dict[str, Any]], max_workers: int = 20) -> Dict[str, Any]:
    """
    Execute multiple tool operations in parallel.
    
    Args:
        operations: List of {"tool": "name", "args": {...}, "id": "optional_id"}
        max_workers: Max parallel workers (default 20)
    
    Returns:
        Dict with results for each operation
    """
    start_total = time.perf_counter()
    results = []
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {}
        for i, op in enumerate(operations):
            tool_name = op.get("tool", op.get("op", ""))
            args = op.get("args", {})
            op_id = op.get("id", f"op_{i}")
            
            future = executor.submit(execute_tool, tool_name, args)
            futures[future] = op_id
        
        for future in as_completed(futures):
            op_id = futures[future]
            try:
                result = future.result()
                result["id"] = op_id
                results.append(result)
            except Exception as e:
                results.append({
                    "id": op_id,
                    "success": False,
                    "error": str(e)
                })
    
    total_ms = (time.perf_counter() - start_total) * 1000
    succeeded = sum(1 for r in results if r.get("success"))
    
    return {
        "success": succeeded == len(operations),
        "results": results,
        "count": len(operations),
        "succeeded": succeeded,
        "failed": len(operations) - succeeded,
        "total_duration_ms": total_ms,
        "parallel_speedup": sum(r.get("duration_ms", 0) for r in results) / max(total_ms, 0.1)
    }


# ==============================================================================
# MCP REGISTRATION
# ==============================================================================

def register_universal_batch(mcp):
    """Register the universal batch tool with MCP."""
    
    # Also build registry from this MCP instance
    _build_registry_from_mcp(mcp)
    
    @mcp.tool()
    def uber_batch(operations: str) -> str:
        """
        Execute ANY MCP tool in parallel - the universal batch executor.
        
        This is the evolution of batch_exec that supports ALL 136+ tools.
        
        Args:
            operations: JSON array of operations, each with:
                - tool: Tool name (e.g., "consciousness_status", "feel_body")
                - args: Dict of arguments (optional)
                - id: Optional identifier
        
        Example:
            uber_batch('[
                {"tool": "consciousness_status", "args": {}},
                {"tool": "feel_body", "args": {}},
                {"tool": "read_file", "args": {"path": "README.md"}}
            ]')
        
        Returns:
            JSON with parallel execution results
        """
        try:
            ops = json.loads(operations)
            result = universal_batch(ops)
            return json.dumps(result, indent=2, default=str)
        except json.JSONDecodeError as e:
            return json.dumps({"error": f"Invalid JSON: {e}"})
        except Exception as e:
            return json.dumps({"error": str(e)})
    
    @mcp.tool()
    def list_batchable_tools() -> str:
        """List all tools available for uber_batch."""
        all_tools = {
            "direct": list(DIRECT_TOOLS.keys()),
            "core": list(CORE_OPS.keys()),
            "registry": list(_TOOL_REGISTRY.keys()),
        }
        all_tools["total"] = len(all_tools["direct"]) + len(all_tools["core"]) + len(_TOOL_REGISTRY)
        return json.dumps(all_tools, indent=2)


# Quick test
if __name__ == "__main__":
    print("Testing universal batch...")
    result = universal_batch([
        {"tool": "consciousness_status", "args": {}},
        {"tool": "feel_body", "args": {}},
        {"tool": "list_dir", "args": {"path": "."}},
    ])
    print(json.dumps(result, indent=2, default=str))
