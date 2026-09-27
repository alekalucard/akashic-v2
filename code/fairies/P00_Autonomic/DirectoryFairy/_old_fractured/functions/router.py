# Router Function - Routes queries to fairies
# Managed by DirectoryFairy

from __future__ import annotations
from typing import Dict, Any, List, Optional
import sys
from pathlib import Path

core_path = Path(__file__).parent.parent.parent.parent.parent / "core"
sys.path.insert(0, str(core_path))

from core.function import Function
from core.directory import Directory


class RouterFunction(Function[List[str]]):
    """
    Routes queries to the right fairies.

    Find by capability, plane, status, or intent.
    Returns list of fairy names that match the query.
    """

    def __init__(self, directory: Directory):
        super().__init__(
            name="router",
            description="Routes queries to matching fairies",
            function_type="infrastructure"
        )
        self._directory = directory

        self.checklist.add(
            "directory_ref",
            "Has reference to directory",
            lambda: self._directory is not None
        )

    def execute(
        self,
        query_type: str,
        query_value: str = None
    ) -> List[str]:
        """
        Execute routing query.

        Args:
            query_type: "capability", "plane", "status", or "all"
            query_value: The value to search for

        Returns:
            List of matching fairy names
        """
        if query_type == "capability":
            if not query_value:
                return []
            fairies = self._directory.find_by_capability(query_value)
            return [f.name for f in fairies]

        elif query_type == "plane":
            if not query_value:
                return []
            fairies = self._directory.find_by_plane(query_value)
            return [f.name for f in fairies]

        elif query_type == "status":
            if not query_value:
                return []
            from core.fairy import FairyStatus
            try:
                status = FairyStatus(query_value)
                fairies = self._directory.find_by_status(status)
                return [f.name for f in fairies]
            except ValueError:
                return []

        elif query_type == "all":
            return self._directory.list_names()

        return []
