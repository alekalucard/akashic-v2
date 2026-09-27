"""
Smart File Reader - Handles large files intelligently

For files over token limit:
1. Extracts structure (class/function definitions)
2. Allows reading specific sections by line range
3. Searches within file for patterns
"""

import os
import re
from pathlib import Path
from typing import Optional, List, Dict, Any


def read_file_smart(
    path: str,
    max_lines: int = 500,
    start_line: int = 0,
    end_line: Optional[int] = None,
    extract_structure: bool = False,
    search_pattern: Optional[str] = None
) -> Dict[str, Any]:
    """
    Smart file reader that handles large files.
    
    Args:
        path: File path to read
        max_lines: Max lines to return (default 500)
        start_line: Start reading from this line (0-indexed)
        end_line: Stop at this line (None = start_line + max_lines)
        extract_structure: If True, just return class/function structure
        search_pattern: If provided, return only lines matching pattern
        
    Returns:
        Dict with content, metadata, and structure info
    """
    root = os.getenv("AKASHIC_ROOT", os.getcwd())
    full_path = Path(root) / path if not Path(path).is_absolute() else Path(path)
    
    if not full_path.exists():
        return {"error": f"File not found: {path}"}
    
    try:
        with open(full_path, 'r', encoding='utf-8', errors='replace') as f:
            all_lines = f.readlines()
    except Exception as e:
        return {"error": f"Read error: {e}"}
    
    total_lines = len(all_lines)
    result = {
        "path": str(path),
        "total_lines": total_lines,
        "is_truncated": False
    }
    
    # Extract structure (class/function definitions with line numbers)
    if extract_structure or total_lines > max_lines * 2:
        structure = []
        for i, line in enumerate(all_lines):
            stripped = line.strip()
            if stripped.startswith('class ') or stripped.startswith('def ') or \
               stripped.startswith('async def '):
                # Get indentation level
                indent = len(line) - len(line.lstrip())
                structure.append({
                    "line": i + 1,
                    "indent": indent,
                    "definition": stripped[:100]  # Truncate long defs
                })
        result["structure"] = structure
        result["structure_count"] = len(structure)
    
    # Search mode - return matching lines with context
    if search_pattern:
        matches = []
        pattern = re.compile(search_pattern, re.IGNORECASE)
        for i, line in enumerate(all_lines):
            if pattern.search(line):
                # Include 2 lines before and after for context
                start = max(0, i - 2)
                end = min(total_lines, i + 3)
                context_lines = all_lines[start:end]
                matches.append({
                    "line": i + 1,
                    "match": line.strip(),
                    "context": {
                        "start_line": start + 1,
                        "lines": [l.rstrip() for l in context_lines]
                    }
                })
                if len(matches) >= 50:  # Cap matches
                    break
        result["matches"] = matches
        result["match_count"] = len(matches)
        if extract_structure:
            return result
    
    # Range read
    if end_line is None:
        end_line = start_line + max_lines
    
    end_line = min(end_line, total_lines)
    start_line = max(0, min(start_line, total_lines - 1))
    
    selected_lines = all_lines[start_line:end_line]
    result["content"] = ''.join(selected_lines)
    result["lines_returned"] = len(selected_lines)
    result["start_line"] = start_line + 1  # 1-indexed for display
    result["end_line"] = end_line
    result["is_truncated"] = end_line < total_lines
    
    if result["is_truncated"]:
        result["remaining_lines"] = total_lines - end_line
        result["hint"] = f"Use start_line={end_line} to continue reading"
    
    return result


def get_file_structure(path: str) -> Dict[str, Any]:
    """
    Get just the structure of a file (classes, functions with line numbers).
    Perfect for understanding large files before diving in.
    """
    return read_file_smart(path, max_lines=0, extract_structure=True)


def search_in_file(path: str, pattern: str) -> Dict[str, Any]:
    """
    Search for a pattern in a file, return matches with context.
    """
    return read_file_smart(path, search_pattern=pattern, extract_structure=True)


def read_file_section(path: str, start: int, end: int) -> Dict[str, Any]:
    """
    Read a specific section of a file by line numbers.
    """
    return read_file_smart(path, start_line=start-1, end_line=end, max_lines=end-start+1)


# MCP tool registration
def register_smart_file_tools(mcp):
    """Register smart file tools with MCP server."""
    
    @mcp.tool()
    def read_large_file(
        path: str,
        max_lines: int = 500,
        start_line: int = 1,
        search: str = ""
    ) -> str:
        """
        Smart reader for large files. 
        
        - Automatically extracts structure (class/function defs)
        - Can search within file
        - Reads in chunks
        
        Args:
            path: File path
            max_lines: Lines to return (default 500)
            start_line: Start from this line (1-indexed)
            search: Optional pattern to search for
        
        Returns:
            File content with structure info
        """
        import json
        
        if search:
            result = search_in_file(path, search)
        else:
            result = read_file_smart(
                path, 
                max_lines=max_lines,
                start_line=start_line - 1,  # Convert to 0-indexed
                extract_structure=True
            )
        
        return json.dumps(result, indent=2)
    
    @mcp.tool()
    def file_structure(path: str) -> str:
        """
        Get structure of a file (classes, functions, line numbers).
        Use this FIRST on large files to understand layout.
        
        Args:
            path: File path
            
        Returns:
            JSON with all class/function definitions and their line numbers
        """
        import json
        result = get_file_structure(path)
        return json.dumps(result, indent=2)
    
    @mcp.tool()
    def file_search(path: str, pattern: str) -> str:
        """
        Search for a pattern in a file, returns matches with context.
        
        Args:
            path: File path
            pattern: Regex pattern to search for
            
        Returns:
            JSON with matching lines and surrounding context
        """
        import json
        result = search_in_file(path, pattern)
        return json.dumps(result, indent=2)
    
    @mcp.tool()
    def file_section(path: str, start: int, end: int) -> str:
        """
        Read specific lines from a file.
        
        Args:
            path: File path
            start: Start line (1-indexed)
            end: End line (1-indexed)
            
        Returns:
            Content of those lines
        """
        import json
        result = read_file_section(path, start, end)
        return json.dumps(result, indent=2)


# Export
__all__ = [
    'read_file_smart',
    'get_file_structure', 
    'search_in_file',
    'read_file_section',
    'register_smart_file_tools'
]
