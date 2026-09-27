"""
Capability Index - Reverse lookup from capability to fairies.

Provides O(1) lookup for finding fairies by their capabilities.
"""

import threading
from collections import defaultdict
from typing import Dict, List, Set


class CapabilityIndex:
    """
    Reverse index: capability -> [fairy_names]

    Thread-safe index for fast capability lookups.
    Instead of scanning all fairies to find one with a capability,
    we maintain a reverse index for O(1) lookup.
    """

    def __init__(self):
        # capability -> set of fairy names
        self._index: Dict[str, Set[str]] = defaultdict(set)
        # fairy_name -> set of capabilities (for removal)
        self._fairy_capabilities: Dict[str, Set[str]] = {}
        self._lock = threading.RLock()

    def add(self, fairy_name: str, capabilities: Set[str]) -> None:
        """Add a fairy's capabilities to the index."""
        with self._lock:
            # Remove old capabilities first (in case of re-registration)
            self.remove(fairy_name)

            # Add new capabilities
            self._fairy_capabilities[fairy_name] = capabilities.copy()
            for cap in capabilities:
                self._index[cap].add(fairy_name)

    def remove(self, fairy_name: str) -> None:
        """Remove a fairy from the index."""
        with self._lock:
            if fairy_name not in self._fairy_capabilities:
                return

            # Remove from capability index
            for cap in self._fairy_capabilities[fairy_name]:
                if cap in self._index:
                    self._index[cap].discard(fairy_name)
                    # Clean up empty sets
                    if not self._index[cap]:
                        del self._index[cap]

            # Remove from fairy capabilities
            del self._fairy_capabilities[fairy_name]

    def find(self, capability: str) -> List[str]:
        """Find all fairies with a specific capability."""
        with self._lock:
            return list(self._index.get(capability, set()))

    def find_any(self, capabilities: Set[str]) -> List[str]:
        """Find fairies with ANY of the given capabilities."""
        with self._lock:
            result = set()
            for cap in capabilities:
                result.update(self._index.get(cap, set()))
            return list(result)

    def find_all(self, capabilities: Set[str]) -> List[str]:
        """Find fairies with ALL of the given capabilities."""
        with self._lock:
            if not capabilities:
                return []

            # Start with fairies that have the first capability
            caps_list = list(capabilities)
            result = self._index.get(caps_list[0], set()).copy()

            # Intersect with fairies that have the remaining capabilities
            for cap in caps_list[1:]:
                result &= self._index.get(cap, set())
                if not result:
                    break

            return list(result)

    def get_fairy_capabilities(self, fairy_name: str) -> Set[str]:
        """Get all capabilities for a fairy."""
        with self._lock:
            return self._fairy_capabilities.get(fairy_name, set()).copy()

    def list_all_capabilities(self) -> List[str]:
        """List all known capabilities."""
        with self._lock:
            return list(self._index.keys())

    def list_all(self) -> Dict[str, List[str]]:
        """Get the full index: capability -> [fairy_names]."""
        with self._lock:
            return {cap: list(fairies) for cap, fairies in self._index.items()}

    def stats(self) -> Dict[str, int]:
        """Get index statistics."""
        with self._lock:
            return {
                "total_capabilities": len(self._index),
                "total_fairies": len(self._fairy_capabilities),
                "avg_fairies_per_capability": (
                    sum(len(f) for f in self._index.values()) / len(self._index)
                    if self._index else 0
                ),
            }

    def clear(self) -> None:
        """Clear the index (for testing)."""
        with self._lock:
            self._index.clear()
            self._fairy_capabilities.clear()
