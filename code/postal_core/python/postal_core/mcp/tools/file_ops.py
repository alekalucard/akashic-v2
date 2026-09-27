"""
File Operations Tools - Parallel file reading and writing.

These tools provide efficient file operations:
- parallel_files: Read multiple files at once
- parallel_grep: Search multiple patterns across files
- write_file: Write with tracking
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, TYPE_CHECKING
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

if TYPE_CHECKING:
    from ..server import MCPServer


# =============================================================================
# PROJECT ROOT DETECTION
# =============================================================================

def _detect_project_root() -> Path:
    """Find the akashic_v2 project root."""
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "boot_test.py").exists():
            return parent
        if parent.name == "akashic_v2":
            return parent
    return current.parent.parent.parent.parent


PROJECT_ROOT = _detect_project_root()


# =============================================================================
# TOOL IMPLEMENTATIONS
# =============================================================================

def parallel_files(paths: List[str], max_lines: int = 500) -> Dict[str, Any]:
    """
    Read multiple files in parallel.

    Args:
        paths: List of file paths (relative to project root or absolute)
        max_lines: Max lines per file (default 500)

    Returns:
        Dict with file contents keyed by path
    """
    results = {}
    errors = {}

    def read_file(path: str) -> tuple:
        try:
            # Resolve path
            p = Path(path)
            if not p.is_absolute():
                p = PROJECT_ROOT / p

            if not p.exists():
                return path, None, f"File not found: {path}"

            if not p.is_file():
                return path, None, f"Not a file: {path}"

            # Read with line limit
            lines = []
            with open(p, "r", encoding="utf-8", errors="replace") as f:
                for i, line in enumerate(f):
                    if i >= max_lines:
                        lines.append(f"\n... (truncated at {max_lines} lines)")
                        break
                    lines.append(line)

            return path, "".join(lines), None

        except Exception as e:
            return path, None, str(e)

    # Read in parallel
    with ThreadPoolExecutor(max_workers=min(len(paths), 8)) as executor:
        futures = {executor.submit(read_file, p): p for p in paths}
        for future in as_completed(futures):
            path, content, error = future.result()
            if error:
                errors[path] = error
            else:
                results[path] = content

    return {
        "files": results,
        "errors": errors,
        "count": len(results),
        "failed": len(errors),
    }


def parallel_grep(
    patterns: List[str],
    path: str = ".",
    file_pattern: str = "*.py",
    max_matches: int = 50,
    context_lines: int = 2,
) -> Dict[str, Any]:
    """
    Search multiple patterns across files in parallel.

    Args:
        patterns: List of regex patterns to search
        path: Directory to search (relative to project root)
        file_pattern: Glob pattern for files (default *.py)
        max_matches: Max matches per pattern (default 50)
        context_lines: Lines of context around match (default 2)

    Returns:
        Dict with matches keyed by pattern
    """
    # Resolve path
    search_path = Path(path)
    if not search_path.is_absolute():
        search_path = PROJECT_ROOT / path

    if not search_path.exists():
        return {"error": f"Path not found: {path}"}

    # Find files to search
    if search_path.is_file():
        files = [search_path]
    else:
        files = list(search_path.glob(f"**/{file_pattern}"))

    results = {p: [] for p in patterns}
    compiled = {p: re.compile(p, re.IGNORECASE) for p in patterns}

    def search_file(filepath: Path) -> Dict[str, List]:
        file_matches = {p: [] for p in patterns}
        try:
            with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()

            for pattern, regex in compiled.items():
                for i, line in enumerate(lines):
                    if regex.search(line):
                        # Get context
                        start = max(0, i - context_lines)
                        end = min(len(lines), i + context_lines + 1)
                        context = "".join(lines[start:end])

                        file_matches[pattern].append({
                            "file": str(filepath.relative_to(PROJECT_ROOT)),
                            "line": i + 1,
                            "match": line.strip(),
                            "context": context,
                        })

                        if len(file_matches[pattern]) >= max_matches:
                            break

        except Exception:
            pass

        return file_matches

    # Search in parallel
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(search_file, f) for f in files[:100]]  # Limit files
        for future in as_completed(futures):
            file_matches = future.result()
            for pattern, matches in file_matches.items():
                results[pattern].extend(matches)
                # Trim to max
                results[pattern] = results[pattern][:max_matches]

    return {
        "patterns": patterns,
        "results": results,
        "files_searched": len(files),
        "total_matches": sum(len(m) for m in results.values()),
    }


def write_file(
    path: str,
    content: str,
    create_dirs: bool = True,
    backup: bool = True,
) -> Dict[str, Any]:
    """
    Write file with tracking and optional backup.

    Args:
        path: File path (relative to project root or absolute)
        content: Content to write
        create_dirs: Create parent directories if needed
        backup: Create .bak backup if file exists

    Returns:
        Dict with write result
    """
    # Resolve path
    p = Path(path)
    if not p.is_absolute():
        p = PROJECT_ROOT / path

    result = {
        "path": str(p),
        "success": False,
        "backup_created": False,
        "dirs_created": False,
    }

    try:
        # Create parent dirs if needed
        if create_dirs and not p.parent.exists():
            p.parent.mkdir(parents=True, exist_ok=True)
            result["dirs_created"] = True

        # Backup if exists
        if backup and p.exists():
            backup_path = p.with_suffix(p.suffix + ".bak")
            import shutil
            shutil.copy2(p, backup_path)
            result["backup_created"] = True
            result["backup_path"] = str(backup_path)

        # Write file
        with open(p, "w", encoding="utf-8") as f:
            f.write(content)

        result["success"] = True
        result["bytes_written"] = len(content.encode("utf-8"))
        result["timestamp"] = datetime.now().isoformat()

        # Publish to postal if available
        try:
            from directory import get_directory
            directory = get_directory()
            if directory and hasattr(directory, "fabric"):
                directory.fabric.publish("file.written", {
                    "path": str(p),
                    "bytes": result["bytes_written"],
                    "ts": result["timestamp"],
                })
        except Exception:
            pass

    except Exception as e:
        result["error"] = str(e)

    return result


# =============================================================================
# REGISTRATION
# =============================================================================

def register_file_ops_tools(server: "MCPServer") -> None:
    """Register file operations tools with MCP server."""

    @server.tool(category="file_ops")
    def mcp_parallel_files(paths: str, max_lines: int = 500) -> str:
        """
        Read multiple files at once.

        Args:
            paths: JSON array of file paths, e.g. '["file1.py", "file2.py"]'
            max_lines: Max lines per file (default 500)
        """
        import json
        try:
            path_list = json.loads(paths)
            if not isinstance(path_list, list):
                return json.dumps({"error": "paths must be a JSON array"})
            return json.dumps(parallel_files(path_list, max_lines), indent=2)
        except json.JSONDecodeError as e:
            return json.dumps({"error": f"Invalid JSON: {e}"})

    @server.tool(category="file_ops")
    def mcp_parallel_grep(
        patterns: str,
        path: str = ".",
        file_pattern: str = "*.py",
        max_matches: int = 50,
    ) -> str:
        """
        Search multiple patterns across files.

        Args:
            patterns: JSON array of regex patterns, e.g. '["def foo", "class Bar"]'
            path: Directory to search (default ".")
            file_pattern: Glob pattern for files (default "*.py")
            max_matches: Max matches per pattern (default 50)
        """
        import json
        try:
            pattern_list = json.loads(patterns)
            if not isinstance(pattern_list, list):
                return json.dumps({"error": "patterns must be a JSON array"})
            return json.dumps(
                parallel_grep(pattern_list, path, file_pattern, max_matches),
                indent=2,
            )
        except json.JSONDecodeError as e:
            return json.dumps({"error": f"Invalid JSON: {e}"})

    @server.tool(category="file_ops")
    def mcp_write_file(path: str, content: str, backup: bool = True) -> str:
        """
        Write file with tracking.

        Args:
            path: File path (relative to project root or absolute)
            content: Content to write
            backup: Create .bak backup if file exists (default True)
        """
        import json
        return json.dumps(write_file(path, content, backup=backup), indent=2)
