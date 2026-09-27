# Registry Function - Stores fairy registrations
# Managed by DirectoryFairy

from __future__ import annotations
from typing import Dict, Any, Optional, Set
import sys
from pathlib import Path

core_path = Path(__file__).parent.parent.parent.parent.parent / "core"
sys.path.insert(0, str(core_path))

from core.function import Function
from core.directory import Directory


class RegistryFunction(Function[bool]):
    """
    Stores all fairy registrations.

    This is the core registration logic - the Directory uses this
    to actually store and index fairies.
    """

    def __init__(self, directory: Directory):
        super().__init__(
            name="registry",
            description="Stores fairy registrations and maintains indexes",
            function_type="infrastructure"
        )
        self._directory = directory

        # Add specific checks
        self.checklist.add(
            "directory_ref",
            "Has reference to directory",
            lambda: self._directory is not None
        )

    def execute(
        self,
        action: str,
        fairy = None,
        name: str = None,
        capabilities: Set[str] = None
    ) -> bool:
        """
        Execute registry operation.

        Args:
            action: "register", "unregister", or "touch"
            fairy: Fairy instance (for register)
            name: Fairy name (for unregister/touch)
            capabilities: Set of capabilities (for register)

        Returns:
            True if operation succeeded
        """
        if action == "register":
            if fairy is None:
                return False
            return self._directory.register(fairy, capabilities or set())

        elif action == "unregister":
            if name is None:
                return False
            return self._directory.unregister(name)

        elif action == "touch":
            if name is None:
                return False
            self._directory.touch(name)
            return True

        return False
