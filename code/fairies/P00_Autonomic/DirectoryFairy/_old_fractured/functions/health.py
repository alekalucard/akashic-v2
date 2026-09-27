# Health Function - Aggregates system health
# Managed by DirectoryFairy

from __future__ import annotations
from typing import Dict, Any, List
import sys
from pathlib import Path

core_path = Path(__file__).parent.parent.parent.parent.parent / "core"
sys.path.insert(0, str(core_path))

from core.function import Function
from core.directory import Directory
from core.config import get_config


class HealthFunction(Function[Dict[str, Any]]):
    """
    Aggregates system health into a single view.

    Provides:
    - Overall health percentage
    - Fairy counts by status
    - Failed fairy list
    - Dead fairy detection
    """

    def __init__(self, directory: Directory):
        super().__init__(
            name="health",
            description="Aggregates system health",
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
        query_type: str = "summary",
        threshold_seconds: float = None
    ) -> Dict[str, Any]:
        """
        Execute health query.

        Args:
            query_type: "summary", "failed", "dead", or "full"
            threshold_seconds: For dead detection (default from config)

        Returns:
            Health information dict
        """
        if query_type == "summary":
            return self._directory.system_health()

        elif query_type == "failed":
            failed = self._directory.failed_fairies()
            return {
                "count": len(failed),
                "fairies": [f.name for f in failed]
            }

        elif query_type == "dead":
            if threshold_seconds is None:
                config = get_config()
                threshold_seconds = config.get("fairy.dead_threshold_seconds")

            dead = self._directory.dead_fairies(threshold_seconds)
            return {
                "count": len(dead),
                "fairies": dead,
                "threshold_seconds": threshold_seconds
            }

        elif query_type == "full":
            return self._directory.to_dict()

        return {}
