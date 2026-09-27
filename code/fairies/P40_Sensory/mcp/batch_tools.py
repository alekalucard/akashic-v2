"""
Batch Execution Tools for MCP

The MCP stdio transport is inherently serial - one request at a time.
This module provides workarounds:

1. batch_execute - Submit multiple operations in ONE tool call
2. background_submit - Fire-and-forget with task_id polling
3. parallel_search - Multiple searches in one call

These enable parallelism WITHIN a single MCP request, working around
the stdio transport limitation without requiring HTTP reconfiguration.

Example usage by Claude:
    Instead of:
        read_file("a.py")   # Wait
        read_file("b.py")   # Wait  
        read_file("c.py")   # Wait
        
    Use:
        batch_execute([
            {"op": "read_file", "args": {"path": "a.py"}},
            {"op": "read_file", "args": {"path": "b.py"}},
            {"op": "read_file", "args": {"path": "c.py"}},
        ])  # All three run in parallel!
"""

import os
import sys
import json
import time
import uuid
import threading
import traceback
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed, Future
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field, asdict

# Import the thread pool
try:
    from .mcp_thread_pool import get_thread_pool, MAX_WORKERS
except ImportError:
    from mcp_thread_pool import get_thread_pool, MAX_WORKERS


# =============================================================================
# OPERATION REGISTRY - Maps operation names to functions
# =============================================================================

_OPERATION_REGISTRY: Dict[str, Callable] = {}


def register_operation(name: str):
    """Decorator to register a function as a batch operation."""
    def decorator(func: Callable) -> Callable:
        _OPERATION_REGISTRY[name] = func
        return func
    return decorator


def get_available_operations() -> List[str]:
    """Get list of registered operation names."""
    return list(_OPERATION_REGISTRY.keys())


# =============================================================================
# BUILT-IN OPERATIONS - Common parallel tasks
# =============================================================================

PROJECT_ROOT = Path(os.getenv("AKASHIC_PROJECT_ROOT", r"F:\Sandbox\ebook"))


@register_operation("read_file")
def op_read_file(path: str, max_lines: int = 500) -> Dict:
    """Read a file's contents."""
    try:
        full_path = PROJECT_ROOT / path if not Path(path).is_absolute() else Path(path)
        if not full_path.exists():
            return {"success": False, "error": f"File not found: {path}"}
        
        with open(full_path, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()
        
        if len(lines) > max_lines:
            content = ''.join(lines[:max_lines])
            content += f"\n... truncated ({len(lines) - max_lines} more lines)"
        else:
            content = ''.join(lines)
        
        return {
            "success": True,
            "path": str(path),
            "content": content,
            "lines": min(len(lines), max_lines),
            "total_lines": len(lines)
        }
    except Exception as e:
        return {"success": False, "error": str(e), "path": str(path)}


@register_operation("file_exists")
def op_file_exists(path: str) -> Dict:
    """Check if a file exists."""
    full_path = PROJECT_ROOT / path if not Path(path).is_absolute() else Path(path)
    return {
        "success": True,
        "path": str(path),
        "exists": full_path.exists(),
        "is_file": full_path.is_file() if full_path.exists() else False,
        "is_dir": full_path.is_dir() if full_path.exists() else False
    }


@register_operation("list_dir")
def op_list_dir(path: str = ".") -> Dict:
    """List directory contents."""
    try:
        full_path = PROJECT_ROOT / path if not Path(path).is_absolute() else Path(path)
        if not full_path.exists():
            return {"success": False, "error": f"Directory not found: {path}"}
        
        items = []
        for item in full_path.iterdir():
            items.append({
                "name": item.name,
                "type": "dir" if item.is_dir() else "file",
                "size": item.stat().st_size if item.is_file() else None
            })
        
        return {
            "success": True,
            "path": str(path),
            "items": items,
            "count": len(items)
        }
    except Exception as e:
        return {"success": False, "error": str(e), "path": str(path)}


@register_operation("search_text")
def op_search_text(pattern: str, directory: str = ".", file_pattern: str = "*.py") -> Dict:
    """Search for text in files."""
    try:
        full_path = PROJECT_ROOT / directory if not Path(directory).is_absolute() else Path(directory)
        matches = []
        
        for py_file in full_path.rglob(file_pattern):
            try:
                content = py_file.read_text(encoding='utf-8', errors='replace')
                for i, line in enumerate(content.splitlines(), 1):
                    if pattern.lower() in line.lower():
                        matches.append({
                            "file": str(py_file.relative_to(PROJECT_ROOT)),
                            "line": i,
                            "content": line.strip()[:200]
                        })
                        if len(matches) >= 50:
                            break
            except Exception:
                continue
            
            if len(matches) >= 50:
                break
        
        return {
            "success": True,
            "pattern": pattern,
            "matches": matches,
            "count": len(matches)
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def _get_clean_env() -> dict:
    """Get clean env without PYTHONPATH that can cause import hangs."""
    env = os.environ.copy()
    env.pop('PYTHONPATH', None)  # Remove to prevent import hangs
    return env


@register_operation("run_python")
def op_run_python(code: str, timeout: int = 30) -> Dict:
    """Execute Python code."""
    import subprocess
    try:
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(PROJECT_ROOT),
            stdin=subprocess.DEVNULL,  # CRITICAL: Close stdin to prevent hangs
            env=_get_clean_env()       # Clean env without PYTHONPATH
        )
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout[:5000] if result.stdout else "",
            "stderr": result.stderr[:2000] if result.stderr else "",
            "return_code": result.returncode
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "error": f"Timeout after {timeout}s"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@register_operation("run_shell")
def op_run_shell(command: str, timeout: int = 60) -> Dict:
    """Execute shell command."""
    import subprocess
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(PROJECT_ROOT),
            stdin=subprocess.DEVNULL,  # CRITICAL: Close stdin to prevent hangs
            env=_get_clean_env()       # Clean env without PYTHONPATH
        )
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout[:5000] if result.stdout else "",
            "stderr": result.stderr[:2000] if result.stderr else "",
            "return_code": result.returncode
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "error": f"Timeout after {timeout}s"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@register_operation("get_fairy_info")
def op_get_fairy_info(fairy_name: str) -> Dict:
    """Get information about a fairy."""
    try:
        # Search for the fairy file
        matches = []
        for py_file in PROJECT_ROOT.rglob("*.py"):
            if fairy_name.lower() in py_file.name.lower():
                matches.append(str(py_file.relative_to(PROJECT_ROOT)))
        
        if not matches:
            return {"success": False, "error": f"No files found matching {fairy_name}"}
        
        # Read the first match
        fairy_file = PROJECT_ROOT / matches[0]
        content = fairy_file.read_text(encoding='utf-8', errors='replace')
        
        # Extract key info
        lines = content.splitlines()
        purpose = ""
        actor_name = ""
        
        for line in lines:
            if "PURPOSE" in line and "=" in line:
                purpose = line.split("=", 1)[1].strip().strip('"\'()')[:200]
            if "ACTOR_NAME" in line and "=" in line:
                actor_name = line.split("=", 1)[1].strip().strip('"\'')
        
        return {
            "success": True,
            "fairy_name": fairy_name,
            "file": matches[0],
            "all_matches": matches[:5],
            "actor_name": actor_name,
            "purpose": purpose,
            "lines": len(lines)
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@register_operation("postal_route")
def op_postal_route(topic: str, payload: Dict) -> Dict:
    """Route a message through the postal system."""
    try:
        from fairies.P00_Autonomic.nervous_system.shared_postal_hub import get_shared_postal_hub
        post = get_shared_postal_hub()
        post.route(topic, payload)
        return {"success": True, "topic": topic, "routed": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


# =============================================================================
# FILESYSTEM OPERATIONS - Work with any path, not just PROJECT_ROOT
# These mirror the Filesystem MCP tools but can run in parallel batches
# =============================================================================

@register_operation("fs_read")
def op_fs_read(path: str, head: int = None, tail: int = None, max_chars: int = 50000) -> Dict:
    """
    Read file from any allowed path (mirrors Filesystem:read_file).
    
    Args:
        path: Absolute or relative path
        head: Only return first N lines
        tail: Only return last N lines  
        max_chars: Max characters to return (default 50k)
    """
    try:
        # Handle both absolute and relative paths
        p = Path(path)
        if not p.is_absolute():
            p = PROJECT_ROOT / path
        
        if not p.exists():
            return {"success": False, "error": f"File not found: {path}"}
        if not p.is_file():
            return {"success": False, "error": f"Not a file: {path}"}
        
        with open(p, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()
        
        total_lines = len(lines)
        
        # Apply head/tail filters
        if head is not None:
            lines = lines[:head]
        elif tail is not None:
            lines = lines[-tail:]
        
        content = ''.join(lines)
        
        # Truncate if too long
        truncated = False
        if len(content) > max_chars:
            content = content[:max_chars]
            truncated = True
        
        return {
            "success": True,
            "path": str(path),
            "content": content,
            "lines_returned": len(lines),
            "total_lines": total_lines,
            "truncated": truncated,
            "size_bytes": p.stat().st_size
        }
    except Exception as e:
        return {"success": False, "error": str(e), "path": str(path)}


@register_operation("fs_read_range")
def op_fs_read_range(path: str, start_line: int = 1, end_line: int = -1) -> Dict:
    """
    Read specific line range from file.
    
    Args:
        path: File path
        start_line: First line (1-indexed)
        end_line: Last line (-1 for end of file)
    """
    try:
        p = Path(path)
        if not p.is_absolute():
            p = PROJECT_ROOT / path
        
        if not p.exists():
            return {"success": False, "error": f"File not found: {path}"}
        
        with open(p, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()
        
        total_lines = len(lines)
        
        # Convert to 0-indexed
        start_idx = max(0, start_line - 1)
        end_idx = total_lines if end_line == -1 else min(end_line, total_lines)
        
        selected = lines[start_idx:end_idx]
        content = ''.join(selected)
        
        return {
            "success": True,
            "path": str(path),
            "content": content,
            "start_line": start_line,
            "end_line": end_idx,
            "lines_returned": len(selected),
            "total_lines": total_lines
        }
    except Exception as e:
        return {"success": False, "error": str(e), "path": str(path)}


@register_operation("fs_tree")
def op_fs_tree(path: str, max_depth: int = 2, include_hidden: bool = False) -> Dict:
    """
    Get directory tree structure.
    
    Args:
        path: Directory path
        max_depth: How deep to recurse (default 2)
        include_hidden: Include hidden files/dirs
    """
    try:
        p = Path(path)
        if not p.is_absolute():
            p = PROJECT_ROOT / path
        
        if not p.exists():
            return {"success": False, "error": f"Path not found: {path}"}
        if not p.is_dir():
            return {"success": False, "error": f"Not a directory: {path}"}
        
        def build_tree(dir_path: Path, depth: int) -> Dict:
            if depth > max_depth:
                return {"name": dir_path.name, "type": "dir", "children": "..."}
            
            result = {"name": dir_path.name, "type": "dir", "children": []}
            
            try:
                items = sorted(dir_path.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
                for item in items:
                    if not include_hidden and item.name.startswith('.'):
                        continue
                    if item.name in ('__pycache__', 'node_modules', '.git', 'venv', '.venv'):
                        continue
                    
                    if item.is_dir():
                        result["children"].append(build_tree(item, depth + 1))
                    else:
                        result["children"].append({
                            "name": item.name,
                            "type": "file",
                            "size": item.stat().st_size
                        })
            except PermissionError:
                result["children"] = "[permission denied]"
            
            return result
        
        tree = build_tree(p, 0)
        
        return {
            "success": True,
            "path": str(path),
            "tree": tree
        }
    except Exception as e:
        return {"success": False, "error": str(e), "path": str(path)}


@register_operation("fs_grep")
def op_fs_grep(pattern: str, path: str, file_glob: str = "*.py", 
               max_matches: int = 100, case_sensitive: bool = False) -> Dict:
    """
    Search for pattern in files (like grep -r).
    
    Args:
        pattern: Text to search for
        path: Directory to search in
        file_glob: File pattern (default *.py)
        max_matches: Max results to return
        case_sensitive: Whether search is case-sensitive
    """
    try:
        p = Path(path)
        if not p.is_absolute():
            p = PROJECT_ROOT / path
        
        if not p.exists():
            return {"success": False, "error": f"Path not found: {path}"}
        
        matches = []
        search_pattern = pattern if case_sensitive else pattern.lower()
        
        glob_iter = p.rglob(file_glob) if p.is_dir() else [p]
        
        for file_path in glob_iter:
            if not file_path.is_file():
                continue
            if '__pycache__' in str(file_path) or '.git' in str(file_path):
                continue
            
            try:
                content = file_path.read_text(encoding='utf-8', errors='replace')
                for line_num, line in enumerate(content.splitlines(), 1):
                    check_line = line if case_sensitive else line.lower()
                    if search_pattern in check_line:
                        matches.append({
                            "file": str(file_path),
                            "line": line_num,
                            "content": line.strip()[:200]
                        })
                        if len(matches) >= max_matches:
                            break
            except Exception:
                continue
            
            if len(matches) >= max_matches:
                break
        
        return {
            "success": True,
            "pattern": pattern,
            "path": str(path),
            "matches": matches,
            "count": len(matches),
            "truncated": len(matches) >= max_matches
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@register_operation("fs_info")
def op_fs_info(path: str) -> Dict:
    """
    Get file/directory metadata.
    
    Args:
        path: Path to inspect
    """
    try:
        p = Path(path)
        if not p.is_absolute():
            p = PROJECT_ROOT / path
        
        if not p.exists():
            return {"success": False, "error": f"Path not found: {path}", "exists": False}
        
        stat = p.stat()
        
        info = {
            "success": True,
            "path": str(path),
            "exists": True,
            "is_file": p.is_file(),
            "is_dir": p.is_dir(),
            "size_bytes": stat.st_size,
            "modified": stat.st_mtime,
            "created": stat.st_ctime,
        }
        
        if p.is_file():
            info["extension"] = p.suffix
            info["name"] = p.name
        elif p.is_dir():
            try:
                info["item_count"] = len(list(p.iterdir()))
            except PermissionError:
                info["item_count"] = -1
        
        return info
    except Exception as e:
        return {"success": False, "error": str(e), "path": str(path)}


@register_operation("fs_find")
def op_fs_find(path: str, name_pattern: str, max_results: int = 50) -> Dict:
    """
    Find files/directories matching a name pattern.
    
    Args:
        path: Starting directory
        name_pattern: Glob pattern for name (e.g., "*fairy*.py")
        max_results: Max results to return
    """
    try:
        p = Path(path)
        if not p.is_absolute():
            p = PROJECT_ROOT / path
        
        if not p.exists():
            return {"success": False, "error": f"Path not found: {path}"}
        
        results = []
        for match in p.rglob(name_pattern):
            if '__pycache__' in str(match) or '.git' in str(match):
                continue
            results.append({
                "path": str(match),
                "name": match.name,
                "type": "dir" if match.is_dir() else "file",
                "size": match.stat().st_size if match.is_file() else None
            })
            if len(results) >= max_results:
                break
        
        return {
            "success": True,
            "path": str(path),
            "pattern": name_pattern,
            "results": results,
            "count": len(results),
            "truncated": len(results) >= max_results
        }
    except Exception as e:
        return {"success": False, "error": str(e)}




# =============================================================================
# WRITE OPERATIONS - File modification in batches
# =============================================================================

@register_operation("write_file")
def op_write_file(path: str, content: str, create_dirs: bool = True) -> Dict:
    """
    Write content to a file (creates or overwrites).
    
    Args:
        path: File path (relative to PROJECT_ROOT or absolute)
        content: Content to write
        create_dirs: Create parent directories if needed
    """
    try:
        p = Path(path)
        if not p.is_absolute():
            p = PROJECT_ROOT / path
        
        if create_dirs:
            p.parent.mkdir(parents=True, exist_ok=True)
        
        with open(p, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return {
            "success": True,
            "path": str(path),
            "bytes_written": len(content.encode('utf-8')),
            "lines": content.count('\n') + 1
        }
    except Exception as e:
        return {"success": False, "error": str(e), "path": str(path)}


@register_operation("append_file")
def op_append_file(path: str, content: str) -> Dict:
    """
    Append content to a file.
    
    Args:
        path: File path
        content: Content to append
    """
    try:
        p = Path(path)
        if not p.is_absolute():
            p = PROJECT_ROOT / path
        
        if not p.exists():
            return {"success": False, "error": f"File not found: {path}"}
        
        with open(p, 'a', encoding='utf-8') as f:
            f.write(content)
        
        return {
            "success": True,
            "path": str(path),
            "bytes_appended": len(content.encode('utf-8'))
        }
    except Exception as e:
        return {"success": False, "error": str(e), "path": str(path)}


@register_operation("edit_file")
def op_edit_file(path: str, old_text: str, new_text: str) -> Dict:
    """
    Replace text in a file (like str_replace).
    
    Args:
        path: File path
        old_text: Text to find (must be unique in file)
        new_text: Text to replace with
    """
    try:
        p = Path(path)
        if not p.is_absolute():
            p = PROJECT_ROOT / path
        
        if not p.exists():
            return {"success": False, "error": f"File not found: {path}"}
        
        with open(p, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check uniqueness
        count = content.count(old_text)
        if count == 0:
            return {"success": False, "error": "old_text not found in file", "path": str(path)}
        if count > 1:
            return {"success": False, "error": f"old_text found {count} times, must be unique", "path": str(path)}
        
        # Replace
        new_content = content.replace(old_text, new_text)
        
        with open(p, 'w', encoding='utf-8') as f:
            f.write(new_content)
        
        return {
            "success": True,
            "path": str(path),
            "old_len": len(old_text),
            "new_len": len(new_text),
            "delta": len(new_text) - len(old_text)
        }
    except Exception as e:
        return {"success": False, "error": str(e), "path": str(path)}


@register_operation("create_file")
def op_create_file(path: str, content: str = "") -> Dict:
    """
    Create a new file (fails if exists).
    
    Args:
        path: File path
        content: Initial content (default empty)
    """
    try:
        p = Path(path)
        if not p.is_absolute():
            p = PROJECT_ROOT / path
        
        if p.exists():
            return {"success": False, "error": f"File already exists: {path}"}
        
        p.parent.mkdir(parents=True, exist_ok=True)
        
        with open(p, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return {
            "success": True,
            "path": str(path),
            "created": True,
            "bytes": len(content.encode('utf-8'))
        }
    except Exception as e:
        return {"success": False, "error": str(e), "path": str(path)}


@register_operation("delete_file")
def op_delete_file(path: str) -> Dict:
    """
    Delete a file.
    
    Args:
        path: File path to delete
    """
    try:
        p = Path(path)
        if not p.is_absolute():
            p = PROJECT_ROOT / path
        
        if not p.exists():
            return {"success": False, "error": f"File not found: {path}"}
        
        if p.is_dir():
            return {"success": False, "error": f"Path is a directory: {path}"}
        
        p.unlink()
        
        return {
            "success": True,
            "path": str(path),
            "deleted": True
        }
    except Exception as e:
        return {"success": False, "error": str(e), "path": str(path)}


@register_operation("copy_file")
def op_copy_file(src: str, dst: str) -> Dict:
    """
    Copy a file.
    
    Args:
        src: Source file path
        dst: Destination file path
    """
    import shutil
    try:
        src_p = Path(src)
        if not src_p.is_absolute():
            src_p = PROJECT_ROOT / src
        
        dst_p = Path(dst)
        if not dst_p.is_absolute():
            dst_p = PROJECT_ROOT / dst
        
        if not src_p.exists():
            return {"success": False, "error": f"Source not found: {src}"}
        
        dst_p.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_p, dst_p)
        
        return {
            "success": True,
            "src": str(src),
            "dst": str(dst),
            "bytes": dst_p.stat().st_size
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


# =============================================================================
# BATCH EXECUTOR - Core parallelism engine
# =============================================================================

@dataclass
class BatchResult:
    """Result of a batch operation."""
    operation_id: str
    operation: str
    success: bool
    result: Any
    duration_ms: float
    error: Optional[str] = None


def execute_single_operation(op_spec: Dict, op_id: str) -> BatchResult:
    """Execute a single operation from a batch."""
    start = time.perf_counter()
    op_name = op_spec.get("op") or op_spec.get("operation")
    args = op_spec.get("args", {})
    
    if not op_name:
        return BatchResult(
            operation_id=op_id,
            operation="unknown",
            success=False,
            result=None,
            duration_ms=0,
            error="No operation specified"
        )
    
    if op_name not in _OPERATION_REGISTRY:
        return BatchResult(
            operation_id=op_id,
            operation=op_name,
            success=False,
            result=None,
            duration_ms=0,
            error=f"Unknown operation: {op_name}. Available: {get_available_operations()}"
        )
    
    try:
        func = _OPERATION_REGISTRY[op_name]
        result = func(**args)
        duration = (time.perf_counter() - start) * 1000
        
        return BatchResult(
            operation_id=op_id,
            operation=op_name,
            success=result.get("success", True) if isinstance(result, dict) else True,
            result=result,
            duration_ms=round(duration, 2)
        )
    except Exception as e:
        duration = (time.perf_counter() - start) * 1000
        return BatchResult(
            operation_id=op_id,
            operation=op_name,
            success=False,
            result=None,
            duration_ms=round(duration, 2),
            error=f"{type(e).__name__}: {e}"
        )


def batch_execute(operations: List[Dict], max_parallel: int = None) -> Dict:
    """
    Execute multiple operations in parallel.
    
    Args:
        operations: List of operation specs, each with:
            - op: Operation name (e.g., "read_file", "search_text")
            - args: Dict of arguments for the operation
            - id: Optional identifier (auto-generated if not provided)
        max_parallel: Max concurrent operations (default: thread pool size)
    
    Returns:
        Dict with:
            - success: True if all succeeded
            - results: List of results in same order as input
            - total_duration_ms: Total wall-clock time
            - parallel_speedup: Estimated speedup vs serial
    
    Example:
        batch_execute([
            {"op": "read_file", "args": {"path": "a.py"}},
            {"op": "read_file", "args": {"path": "b.py"}},
            {"op": "search_text", "args": {"pattern": "fairy", "directory": "P30_Cognition"}},
        ])
    """
    if not operations:
        return {"success": True, "results": [], "total_duration_ms": 0}
    
    start = time.perf_counter()
    pool = get_thread_pool()
    max_p = max_parallel or MAX_WORKERS
    
    # Assign IDs to operations
    for i, op in enumerate(operations):
        if "id" not in op:
            op["id"] = f"op_{i}"
    
    # Submit all to thread pool
    futures: Dict[Future, str] = {}
    for op in operations:
        future = pool.submit(execute_single_operation, op, op["id"])
        futures[future] = op["id"]
    
    # Collect results, preserving order
    results_by_id = {}
    for future in as_completed(futures):
        op_id = futures[future]
        try:
            result = future.result()
            results_by_id[op_id] = result
        except Exception as e:
            results_by_id[op_id] = BatchResult(
                operation_id=op_id,
                operation="unknown",
                success=False,
                result=None,
                duration_ms=0,
                error=str(e)
            )
    
    # Build ordered results
    results = []
    total_individual_time = 0
    for op in operations:
        r = results_by_id.get(op["id"])
        if r:
            results.append(asdict(r))
            total_individual_time += r.duration_ms
    
    total_duration = (time.perf_counter() - start) * 1000
    all_success = all(r.get("success", False) for r in results)
    
    # Calculate speedup
    speedup = total_individual_time / total_duration if total_duration > 0 else 1.0
    
    return {
        "success": all_success,
        "results": results,
        "count": len(results),
        "succeeded": sum(1 for r in results if r.get("success")),
        "failed": sum(1 for r in results if not r.get("success")),
        "total_duration_ms": round(total_duration, 2),
        "sum_individual_ms": round(total_individual_time, 2),
        "parallel_speedup": round(speedup, 2),
        "workers_available": MAX_WORKERS
    }


# =============================================================================
# BACKGROUND TASK SYSTEM - Fire and forget with polling
# =============================================================================

@dataclass 
class BackgroundTask:
    """A background task that can be polled for results."""
    task_id: str
    operations: List[Dict]
    status: str = "pending"  # pending, running, complete, failed
    result: Optional[Dict] = None
    submitted_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None
    error: Optional[str] = None


_BACKGROUND_TASKS: Dict[str, BackgroundTask] = {}
_TASK_LOCK = threading.Lock()


def _run_background_task(task_id: str):
    """Internal function to run a background task."""
    with _TASK_LOCK:
        task = _BACKGROUND_TASKS.get(task_id)
        if not task:
            return
        task.status = "running"
    
    try:
        result = batch_execute(task.operations)
        with _TASK_LOCK:
            task.result = result
            task.status = "complete"
            task.completed_at = time.time()
    except Exception as e:
        with _TASK_LOCK:
            task.error = str(e)
            task.status = "failed"
            task.completed_at = time.time()


def submit_background(operations: List[Dict]) -> Dict:
    """
    Submit operations to run in background.
    Returns immediately with a task_id to poll.
    
    Args:
        operations: Same format as batch_execute
        
    Returns:
        Dict with task_id for polling
    """
    task_id = f"bg_{uuid.uuid4().hex[:8]}"
    task = BackgroundTask(task_id=task_id, operations=operations)
    
    with _TASK_LOCK:
        _BACKGROUND_TASKS[task_id] = task
        # Cleanup old tasks (keep last 100)
        if len(_BACKGROUND_TASKS) > 100:
            oldest = sorted(_BACKGROUND_TASKS.keys())[:-100]
            for old_id in oldest:
                del _BACKGROUND_TASKS[old_id]
    
    # Start in thread pool
    pool = get_thread_pool()
    pool.submit(_run_background_task, task_id)
    
    return {
        "success": True,
        "task_id": task_id,
        "status": "submitted",
        "operation_count": len(operations),
        "message": f"Task submitted. Poll with check_background('{task_id}')"
    }


def check_background(task_id: str) -> Dict:
    """
    Check status of a background task.
    
    Args:
        task_id: ID returned from submit_background
        
    Returns:
        Task status and results if complete
    """
    with _TASK_LOCK:
        task = _BACKGROUND_TASKS.get(task_id)
    
    if not task:
        return {
            "success": False,
            "error": f"Task not found: {task_id}",
            "task_id": task_id
        }
    
    response = {
        "success": True,
        "task_id": task_id,
        "status": task.status,
        "submitted_at": task.submitted_at,
    }
    
    if task.status == "complete":
        response["result"] = task.result
        response["completed_at"] = task.completed_at
        response["duration_sec"] = round(task.completed_at - task.submitted_at, 2)
    elif task.status == "failed":
        response["error"] = task.error
        response["completed_at"] = task.completed_at
    elif task.status == "running":
        response["message"] = "Task still running, check again shortly"
        response["elapsed_sec"] = round(time.time() - task.submitted_at, 2)
    
    return response


def list_background_tasks() -> Dict:
    """List all background tasks."""
    with _TASK_LOCK:
        tasks = []
        for tid, task in _BACKGROUND_TASKS.items():
            tasks.append({
                "task_id": tid,
                "status": task.status,
                "operation_count": len(task.operations),
                "submitted_at": task.submitted_at,
                "completed_at": task.completed_at
            })
    
    return {
        "success": True,
        "tasks": tasks,
        "count": len(tasks)
    }


# =============================================================================
# PARALLEL CONVENIENCE FUNCTIONS
# =============================================================================

def parallel_read_files(paths: List[str], max_lines: int = 500) -> Dict:
    """
    Read multiple files in parallel.
    
    Args:
        paths: List of file paths
        max_lines: Max lines per file
        
    Returns:
        Dict with results keyed by path
    """
    operations = [
        {"op": "read_file", "args": {"path": p, "max_lines": max_lines}, "id": p}
        for p in paths
    ]
    
    result = batch_execute(operations)
    
    # Reshape results to be keyed by path
    files = {}
    for r in result.get("results", []):
        path = r.get("operation_id")
        if r.get("success"):
            files[path] = r.get("result", {}).get("content", "")
        else:
            files[path] = f"ERROR: {r.get('error', 'unknown')}"
    
    return {
        "success": result.get("success", False),
        "files": files,
        "count": len(files),
        "duration_ms": result.get("total_duration_ms", 0),
        "speedup": result.get("parallel_speedup", 1.0)
    }


def parallel_search(patterns: List[str], directory: str = ".", file_pattern: str = "*.py") -> Dict:
    """
    Search for multiple patterns in parallel.
    
    Args:
        patterns: List of search patterns
        directory: Directory to search
        file_pattern: Glob pattern for files
        
    Returns:
        Dict with results keyed by pattern
    """
    operations = [
        {"op": "search_text", "args": {"pattern": p, "directory": directory, "file_pattern": file_pattern}, "id": p}
        for p in patterns
    ]
    
    result = batch_execute(operations)
    
    # Reshape results
    searches = {}
    for r in result.get("results", []):
        pattern = r.get("operation_id")
        if r.get("success"):
            searches[pattern] = r.get("result", {}).get("matches", [])
        else:
            searches[pattern] = []
    
    return {
        "success": result.get("success", False),
        "searches": searches,
        "count": len(searches),
        "duration_ms": result.get("total_duration_ms", 0),
        "speedup": result.get("parallel_speedup", 1.0)
    }


# =============================================================================
# TEST / DEMO
# =============================================================================

if __name__ == "__main__":
    print("Testing batch execution...")
    
    # Test batch read
    result = batch_execute([
        {"op": "read_file", "args": {"path": "P00_Autonomic/directory_fairy.py", "max_lines": 50}},
        {"op": "read_file", "args": {"path": "P10_Memory/__init__.py", "max_lines": 50}},
        {"op": "list_dir", "args": {"path": "P30_Cognition"}},
        {"op": "file_exists", "args": {"path": "server.py"}},
    ])
    
    print(f"\nBatch result:")
    print(f"  Success: {result['success']}")
    print(f"  Count: {result['count']}")
    print(f"  Duration: {result['total_duration_ms']}ms")
    print(f"  Speedup: {result['parallel_speedup']}x")
    
    for r in result["results"]:
        print(f"    - {r['operation_id']}: {'OK' if r['success'] else 'FAIL'} ({r['duration_ms']}ms)")
    
    print("\nAvailable operations:", get_available_operations())
