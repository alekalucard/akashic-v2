"""
Memory Tools - Access to memory systems.

These tools provide memory access:
- srm_search: Search memory (SRM = Semantic Retrieval Memory)
- session_get_handoff: Get current session context
- session_save: Save session context
"""

from __future__ import annotations

import os
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, TYPE_CHECKING
from datetime import datetime

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

# Memory storage paths
STATE_DIR = PROJECT_ROOT / "state"
HANDOFF_DIR = PROJECT_ROOT.parent.parent / "ebook" / "Claude_Office"
SESSION_FILE = STATE_DIR / "current_session.json"


# =============================================================================
# TOOL IMPLEMENTATIONS
# =============================================================================

def srm_search(
    query: str,
    max_results: int = 10,
    memory_type: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Search semantic retrieval memory.

    Args:
        query: Search query
        max_results: Maximum results to return
        memory_type: Filter by type (session, handoff, learning, etc.)

    Returns:
        Dict with search results
    """
    results = []

    # Search session files
    if STATE_DIR.exists():
        session_files = list(STATE_DIR.glob("*.json"))
        for sf in session_files[:20]:  # Limit files to check
            try:
                with open(sf, "r", encoding="utf-8") as f:
                    data = json.load(f)

                # Simple text search in JSON content
                content_str = json.dumps(data).lower()
                if query.lower() in content_str:
                    results.append({
                        "source": str(sf.name),
                        "type": "session",
                        "snippet": content_str[:200],
                        "relevance": 0.8,
                    })

            except Exception:
                pass

    # Search handoff files
    if HANDOFF_DIR.exists():
        handoff_files = list(HANDOFF_DIR.glob("*.md"))
        for hf in handoff_files[:10]:
            try:
                content = hf.read_text(encoding="utf-8", errors="replace")
                if query.lower() in content.lower():
                    # Find relevant snippet
                    idx = content.lower().find(query.lower())
                    start = max(0, idx - 100)
                    end = min(len(content), idx + 200)
                    snippet = content[start:end]

                    results.append({
                        "source": str(hf.name),
                        "type": "handoff",
                        "snippet": snippet,
                        "relevance": 0.9,
                    })

            except Exception:
                pass

    # Filter by type if specified
    if memory_type:
        results = [r for r in results if r["type"] == memory_type]

    # Sort by relevance and limit
    results.sort(key=lambda x: x["relevance"], reverse=True)
    results = results[:max_results]

    return {
        "query": query,
        "results": results,
        "count": len(results),
        "memory_type": memory_type,
    }


def session_get_handoff() -> Dict[str, Any]:
    """
    Get current session handoff context.

    Returns the most recent handoff file and current session state.
    """
    result = {
        "handoff": None,
        "session": None,
        "timestamp": datetime.now().isoformat(),
    }

    # Find most recent handoff
    if HANDOFF_DIR.exists():
        handoff_files = sorted(
            HANDOFF_DIR.glob("HANDOFF*.md"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if handoff_files:
            try:
                latest = handoff_files[0]
                content = latest.read_text(encoding="utf-8", errors="replace")
                result["handoff"] = {
                    "file": str(latest.name),
                    "content": content[:2000],  # First 2000 chars
                    "modified": datetime.fromtimestamp(
                        latest.stat().st_mtime
                    ).isoformat(),
                }
            except Exception as e:
                result["handoff_error"] = str(e)

    # Get current session state
    if SESSION_FILE.exists():
        try:
            with open(SESSION_FILE, "r", encoding="utf-8") as f:
                result["session"] = json.load(f)
        except Exception as e:
            result["session_error"] = str(e)

    return result


def session_save(
    title: str,
    content: str,
    tags: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Save session context to memory.

    Args:
        title: Session title
        content: Session content/summary
        tags: Optional tags for categorization

    Returns:
        Dict with save result
    """
    # Ensure state directory exists
    STATE_DIR.mkdir(parents=True, exist_ok=True)

    session_data = {
        "title": title,
        "content": content,
        "tags": tags or [],
        "timestamp": datetime.now().isoformat(),
        "version": "v2",
    }

    # Generate filename from title
    safe_title = "".join(c if c.isalnum() or c in "._- " else "_" for c in title)
    safe_title = safe_title[:50].strip()
    filename = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{safe_title}.json"

    filepath = STATE_DIR / filename

    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(session_data, f, indent=2)

        # Also update current session pointer
        with open(SESSION_FILE, "w", encoding="utf-8") as f:
            json.dump({
                "current": str(filepath.name),
                "title": title,
                "saved": session_data["timestamp"],
            }, f, indent=2)

        # Publish to postal if available
        try:
            from directory import get_directory
            directory = get_directory()
            if directory and hasattr(directory, "fabric"):
                directory.fabric.publish("session.saved", {
                    "title": title,
                    "file": str(filepath.name),
                    "ts": session_data["timestamp"],
                })
        except Exception:
            pass

        return {
            "success": True,
            "file": str(filepath.name),
            "path": str(filepath),
            "timestamp": session_data["timestamp"],
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }


def get_memory_pressure() -> Dict[str, Any]:
    """
    Check memory system pressure and status.

    Returns stats about memory usage and health.
    """
    import psutil

    result = {
        "system": {},
        "storage": {},
        "status": "ok",
    }

    # System memory
    try:
        mem = psutil.virtual_memory()
        result["system"] = {
            "total_gb": round(mem.total / (1024**3), 2),
            "available_gb": round(mem.available / (1024**3), 2),
            "percent_used": mem.percent,
        }
        if mem.percent > 90:
            result["status"] = "critical"
        elif mem.percent > 75:
            result["status"] = "elevated"
    except Exception as e:
        result["system_error"] = str(e)

    # Storage usage
    try:
        if STATE_DIR.exists():
            session_files = list(STATE_DIR.glob("*.json"))
            total_size = sum(f.stat().st_size for f in session_files)
            result["storage"] = {
                "session_files": len(session_files),
                "total_bytes": total_size,
                "total_mb": round(total_size / (1024**2), 2),
            }
    except Exception as e:
        result["storage_error"] = str(e)

    return result


# =============================================================================
# REGISTRATION
# =============================================================================

def register_memory_tools(server: "MCPServer") -> None:
    """Register memory tools with MCP server."""

    @server.tool(category="memory")
    def mcp_srm_search(query: str, max_results: int = 10) -> str:
        """
        Search semantic retrieval memory.

        Args:
            query: Search query
            max_results: Maximum results (default 10)
        """
        import json
        return json.dumps(srm_search(query, max_results), indent=2)

    @server.tool(category="memory")
    def mcp_session_get_handoff() -> str:
        """Get current session handoff context."""
        import json
        return json.dumps(session_get_handoff(), indent=2)

    @server.tool(category="memory")
    def mcp_session_save(title: str, content: str, tags: str = "") -> str:
        """
        Save session context to memory.

        Args:
            title: Session title
            content: Session content/summary
            tags: Comma-separated tags
        """
        import json
        tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
        return json.dumps(session_save(title, content, tag_list), indent=2)

    @server.tool(category="memory")
    def mcp_get_memory_pressure() -> str:
        """Check memory system pressure and status."""
        import json
        return json.dumps(get_memory_pressure(), indent=2)
