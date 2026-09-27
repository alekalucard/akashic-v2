"""
Fairy Tools - Fairy management and monitoring.

These tools provide fairy system access:
- fairy_profile: Get detailed fairy profile
- fairy_world_status: Overall system health
- fairy_wake: Wake a sleeping fairy
- fairy_sleep: Put a fairy to sleep
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, TYPE_CHECKING
from datetime import datetime

if TYPE_CHECKING:
    from ..server import MCPServer


# =============================================================================
# TOOL IMPLEMENTATIONS
# =============================================================================

def fairy_profile(name: str) -> Dict[str, Any]:
    """
    Get detailed profile for a specific fairy.

    Args:
        name: Fairy name

    Returns:
        Dict with fairy profile including capabilities, status, metrics
    """
    result = {
        "name": name,
        "found": False,
        "timestamp": datetime.now().isoformat(),
    }

    try:
        from directory import get_directory
        directory = get_directory()
        if not directory:
            result["error"] = "Directory not available"
            return result

        # Get fairy record
        record = directory.get_fairy(name)
        if not record:
            result["error"] = f"Fairy '{name}' not found"
            return result

        result["found"] = True
        result["record"] = {
            "name": record.name,
            "plane": record.plane,
            "channel": record.channel,
            "status": record.status,
            "capabilities": list(record.capabilities) if record.capabilities else [],
            "registered_at": record.registered_at.isoformat() if record.registered_at else None,
            "last_heartbeat": record.last_heartbeat.isoformat() if record.last_heartbeat else None,
        }

        # Try to get fairy instance for more details
        fairy_instance = directory.get_fairy_instance(name) if hasattr(directory, "get_fairy_instance") else None
        if fairy_instance:
            # Get status from instance
            if hasattr(fairy_instance, "status"):
                result["instance_status"] = fairy_instance.status()

            # Get profile if available (UnconsciousMindFairy has this)
            if hasattr(fairy_instance, "profile_status"):
                result["profile"] = fairy_instance.profile_status()

            # Get helix status if available
            if hasattr(fairy_instance, "helix_status"):
                result["helix"] = fairy_instance.helix_status()

    except Exception as e:
        result["error"] = str(e)

    return result


def fairy_world_status() -> Dict[str, Any]:
    """
    Get overall fairy world health status.

    Returns comprehensive system health including all fairies,
    connections, and any issues.
    """
    result = {
        "healthy": False,
        "fairies": [],
        "counts": {},
        "issues": [],
        "timestamp": datetime.now().isoformat(),
    }

    try:
        from directory import get_directory
        directory = get_directory()
        if not directory:
            result["issues"].append("Directory not available")
            return result

        # Get all fairies
        fairies = directory.list_fairies()

        # Count by status
        by_status = {}
        by_plane = {}

        for fairy in fairies:
            # Count by status
            status = fairy.status or "unknown"
            by_status[status] = by_status.get(status, 0) + 1

            # Count by plane
            plane = fairy.plane or "unknown"
            by_plane[plane] = by_plane.get(plane, 0) + 1

            # Build fairy summary
            result["fairies"].append({
                "name": fairy.name,
                "plane": fairy.plane,
                "status": fairy.status,
            })

        result["counts"] = {
            "total": len(fairies),
            "by_status": by_status,
            "by_plane": by_plane,
        }

        # Check for issues
        running = by_status.get("running", 0)
        sleeping = by_status.get("sleeping", 0)
        dead = by_status.get("dead", 0) + by_status.get("failed", 0)

        if dead > 0:
            result["issues"].append(f"{dead} fairies are dead/failed")

        if running == 0 and len(fairies) > 0:
            result["issues"].append("No fairies are running")

        # Get directory health
        if hasattr(directory, "health_check"):
            health = directory.health_check()
            result["directory_health"] = health

        # Determine overall health
        result["healthy"] = len(result["issues"]) == 0 and running > 0

    except Exception as e:
        result["error"] = str(e)
        result["issues"].append(f"Error checking status: {e}")

    return result


def fairy_wake(name: str) -> Dict[str, Any]:
    """
    Wake a sleeping fairy.

    Args:
        name: Fairy name to wake

    Returns:
        Dict with wake result
    """
    result = {
        "name": name,
        "success": False,
        "timestamp": datetime.now().isoformat(),
    }

    try:
        from directory import get_directory
        directory = get_directory()
        if not directory:
            result["error"] = "Directory not available"
            return result

        # Try to wake
        wake_result = directory.wake_fairy(name)
        result.update(wake_result)
        result["success"] = wake_result.get("ok", False)

    except Exception as e:
        result["error"] = str(e)

    return result


def fairy_sleep(name: str) -> Dict[str, Any]:
    """
    Put a fairy to sleep.

    Args:
        name: Fairy name to put to sleep

    Returns:
        Dict with sleep result
    """
    result = {
        "name": name,
        "success": False,
        "timestamp": datetime.now().isoformat(),
    }

    try:
        from directory import get_directory
        directory = get_directory()
        if not directory:
            result["error"] = "Directory not available"
            return result

        # Try to sleep
        sleep_result = directory.sleep_fairy(name)
        result.update(sleep_result)
        result["success"] = sleep_result.get("ok", False)

    except Exception as e:
        result["error"] = str(e)

    return result


def fairy_capabilities(capability: str) -> Dict[str, Any]:
    """
    Find fairies with a specific capability.

    Args:
        capability: Capability to search for (e.g., "memory.store")

    Returns:
        Dict with matching fairies
    """
    result = {
        "capability": capability,
        "fairies": [],
        "timestamp": datetime.now().isoformat(),
    }

    try:
        from directory import get_directory
        directory = get_directory()
        if not directory:
            result["error"] = "Directory not available"
            return result

        # Find fairies with capability
        matching = directory.find_by_capability(capability)
        result["fairies"] = [f.name for f in matching] if matching else []
        result["count"] = len(result["fairies"])

    except Exception as e:
        result["error"] = str(e)

    return result


# =============================================================================
# REGISTRATION
# =============================================================================

def register_fairy_tools(server: "MCPServer") -> None:
    """Register fairy tools with MCP server."""

    @server.tool(category="fairy")
    def mcp_fairy_profile(name: str) -> str:
        """
        Get detailed profile for a specific fairy.

        Args:
            name: Fairy name
        """
        import json
        return json.dumps(fairy_profile(name), indent=2)

    @server.tool(category="fairy")
    def mcp_fairy_world_status() -> str:
        """Get overall fairy world health status."""
        import json
        return json.dumps(fairy_world_status(), indent=2)

    @server.tool(category="fairy")
    def mcp_fairy_wake(name: str) -> str:
        """
        Wake a sleeping fairy.

        Args:
            name: Fairy name to wake
        """
        import json
        return json.dumps(fairy_wake(name), indent=2)

    @server.tool(category="fairy")
    def mcp_fairy_sleep(name: str) -> str:
        """
        Put a fairy to sleep.

        Args:
            name: Fairy name to put to sleep
        """
        import json
        return json.dumps(fairy_sleep(name), indent=2)

    @server.tool(category="fairy")
    def mcp_fairy_capabilities(capability: str) -> str:
        """
        Find fairies with a specific capability.

        Args:
            capability: Capability to search for (e.g., "memory.store")
        """
        import json
        return json.dumps(fairy_capabilities(capability), indent=2)
