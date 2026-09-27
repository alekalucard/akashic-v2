"""
fairy_profile.py - Stub for akashic_v2

Provides fairy registry access for MCP tools.
Uses directory.DirectoryFairy as the backing store.
"""

from typing import Dict, Any, List, Optional


def get_fairy_registry() -> Dict[str, Any]:
    """Get fairy registry from DirectoryFairy."""
    try:
        from directory import get_directory
        directory = get_directory()

        if not directory:
            return {"_error": "Directory not initialized"}

        registry = {}
        # Use list_fairies() to get all FairyRecords
        for record in directory.list_fairies():
            registry[record.name] = {
                "name": record.name,
                "plane": record.plane,
                "status": record.status,
                "capabilities": list(record.capabilities),
                "channel": record.channel,
                "metadata": record.metadata,
            }
        return registry
    except Exception as e:
        return {"_error": str(e)}


def get_fairy_by_name(name: str) -> Optional[Dict[str, Any]]:
    """Get a specific fairy by name."""
    try:
        from directory import get_directory
        directory = get_directory()

        if not directory:
            return None

        record = directory.get_fairy(name)
        if record:
            return {
                "name": record.name,
                "plane": record.plane,
                "status": record.status,
                "capabilities": list(record.capabilities),
                "channel": record.channel,
                "metadata": record.metadata,
            }
        return None
    except Exception:
        return None


def list_fairy_names() -> List[str]:
    """List all fairy names."""
    try:
        from directory import get_directory
        directory = get_directory()

        if not directory:
            return []

        return [record.name for record in directory.list_fairies()]
    except Exception:
        return []


__all__ = ["get_fairy_registry", "get_fairy_by_name", "list_fairy_names"]
