# Directory - The Map
# Knows everything. Auto-routes. Single source of truth.
#
# The Directory is where fairies register themselves.
# It provides discovery, routing, and health aggregation.

from __future__ import annotations
from typing import Dict, Any, Optional, List, Set
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import threading

from .fairy import Fairy, FairyStatus
from .function import Function, FunctionStatus
from .checklist import Checklist, ChecklistResult


class DirectoryStatus(Enum):
    """Status of the directory itself."""
    INITIALIZING = "initializing"
    READY = "ready"
    DEGRADED = "degraded"  # Some fairies failing
    FAILED = "failed"


@dataclass
class FairyRecord:
    """Record of a fairy in the directory."""
    fairy: Fairy
    registered_at: datetime = field(default_factory=datetime.now)
    last_seen: datetime = field(default_factory=datetime.now)
    capabilities: Set[str] = field(default_factory=set)

    def touch(self):
        """Update last_seen timestamp."""
        self.last_seen = datetime.now()

    @property
    def age_seconds(self) -> float:
        return (datetime.now() - self.registered_at).total_seconds()

    @property
    def silence_seconds(self) -> float:
        """How long since we heard from this fairy."""
        return (datetime.now() - self.last_seen).total_seconds()


class Directory:
    """
    The central directory of all fairies and their capabilities.

    Features:
    - Fairy registration and discovery
    - Capability-based routing
    - Health aggregation
    - Dead fairy detection

    Usage:
        directory = get_directory()

        # Register a fairy
        directory.register(my_fairy, capabilities={"memory_storage", "recall"})

        # Find by capability
        memory_fairies = directory.find_by_capability("memory_storage")

        # Get system health
        health = directory.system_health()
    """

    def __init__(self):
        self._fairies: Dict[str, FairyRecord] = {}
        self._by_capability: Dict[str, Set[str]] = {}  # capability -> set of fairy names
        self._by_plane: Dict[str, Set[str]] = {}  # plane -> set of fairy names
        self._lock = threading.RLock()
        self._status = DirectoryStatus.INITIALIZING
        self._created_at = datetime.now()

        # Checklist for the directory itself
        self.checklist = Checklist("directory_checklist", owner=self)
        self._add_base_checks()

    def _add_base_checks(self):
        """Add standard checks for directory."""
        self.checklist.add(
            "has_fairies",
            "At least one fairy registered",
            lambda: len(self._fairies) > 0,
            required=False  # Can start empty
        )

    # ═══════════════════════════════════════════════════════════════════════
    # REGISTRATION
    # ═══════════════════════════════════════════════════════════════════════

    def register(
        self,
        fairy: Fairy,
        capabilities: Set[str] = None
    ) -> bool:
        """
        Register a fairy with the directory.

        Args:
            fairy: The fairy to register
            capabilities: What this fairy can do (for routing)

        Returns:
            True if registered successfully
        """
        capabilities = capabilities or set()

        with self._lock:
            if fairy.name in self._fairies:
                # Already registered - update
                self._fairies[fairy.name].fairy = fairy
                self._fairies[fairy.name].touch()
                return True

            # New registration
            record = FairyRecord(
                fairy=fairy,
                capabilities=capabilities
            )
            self._fairies[fairy.name] = record

            # Index by capability
            for cap in capabilities:
                if cap not in self._by_capability:
                    self._by_capability[cap] = set()
                self._by_capability[cap].add(fairy.name)

            # Index by plane
            if fairy.plane not in self._by_plane:
                self._by_plane[fairy.plane] = set()
            self._by_plane[fairy.plane].add(fairy.name)

            print(f"[Directory] Registered: {fairy.name} ({fairy.plane}) caps={capabilities}")
            return True

    def unregister(self, fairy_name: str) -> bool:
        """Remove a fairy from the directory."""
        with self._lock:
            if fairy_name not in self._fairies:
                return False

            record = self._fairies[fairy_name]

            # Remove from capability index
            for cap in record.capabilities:
                if cap in self._by_capability:
                    self._by_capability[cap].discard(fairy_name)

            # Remove from plane index
            if record.fairy.plane in self._by_plane:
                self._by_plane[record.fairy.plane].discard(fairy_name)

            del self._fairies[fairy_name]
            print(f"[Directory] Unregistered: {fairy_name}")
            return True

    def touch(self, fairy_name: str):
        """Update last_seen for a fairy (call this on message receive)."""
        with self._lock:
            if fairy_name in self._fairies:
                self._fairies[fairy_name].touch()

    # ═══════════════════════════════════════════════════════════════════════
    # DISCOVERY & ROUTING
    # ═══════════════════════════════════════════════════════════════════════

    def get(self, fairy_name: str) -> Optional[Fairy]:
        """Get a fairy by name."""
        with self._lock:
            record = self._fairies.get(fairy_name)
            return record.fairy if record else None

    def find_by_capability(self, capability: str) -> List[Fairy]:
        """Find all fairies with a given capability."""
        with self._lock:
            names = self._by_capability.get(capability, set())
            return [self._fairies[n].fairy for n in names if n in self._fairies]

    def find_by_plane(self, plane: str) -> List[Fairy]:
        """Find all fairies in a given plane."""
        with self._lock:
            names = self._by_plane.get(plane, set())
            return [self._fairies[n].fairy for n in names if n in self._fairies]

    def find_by_status(self, status: FairyStatus) -> List[Fairy]:
        """Find all fairies with a given status."""
        with self._lock:
            return [r.fairy for r in self._fairies.values() if r.fairy.status == status]

    def list_all(self) -> List[Fairy]:
        """List all registered fairies."""
        with self._lock:
            return [r.fairy for r in self._fairies.values()]

    def list_names(self) -> List[str]:
        """List all fairy names."""
        with self._lock:
            return list(self._fairies.keys())

    def list_capabilities(self) -> List[str]:
        """List all known capabilities."""
        with self._lock:
            return list(self._by_capability.keys())

    def list_planes(self) -> List[str]:
        """List all known planes."""
        with self._lock:
            return sorted(self._by_plane.keys())

    # ═══════════════════════════════════════════════════════════════════════
    # HEALTH & STATUS
    # ═══════════════════════════════════════════════════════════════════════

    def system_health(self) -> Dict[str, Any]:
        """Get aggregate system health."""
        with self._lock:
            total = len(self._fairies)
            awake = sum(1 for r in self._fairies.values() if r.fairy.status == FairyStatus.AWAKE)
            sleeping = sum(1 for r in self._fairies.values() if r.fairy.status == FairyStatus.SLEEPING)
            failed = sum(1 for r in self._fairies.values() if r.fairy.status == FairyStatus.FAILED)

            if total == 0:
                health_pct = 100.0
            else:
                health_pct = (awake / total) * 100

            return {
                "status": self._calculate_status().value,
                "health_percent": health_pct,
                "fairies_total": total,
                "fairies_awake": awake,
                "fairies_sleeping": sleeping,
                "fairies_failed": failed,
                "capabilities_count": len(self._by_capability),
                "planes_count": len(self._by_plane),
                "uptime_seconds": self.uptime_seconds
            }

    def _calculate_status(self) -> DirectoryStatus:
        """Calculate overall directory status."""
        with self._lock:
            if len(self._fairies) == 0:
                return DirectoryStatus.INITIALIZING

            awake_count = sum(1 for r in self._fairies.values() if r.fairy.status == FairyStatus.AWAKE)
            failed_count = sum(1 for r in self._fairies.values() if r.fairy.status == FairyStatus.FAILED)
            total = len(self._fairies)

            if failed_count == total:
                return DirectoryStatus.FAILED
            elif failed_count > 0:
                return DirectoryStatus.DEGRADED
            elif awake_count == total:
                return DirectoryStatus.READY
            else:
                return DirectoryStatus.DEGRADED

    def failed_fairies(self) -> List[Fairy]:
        """Get list of failed fairies."""
        return self.find_by_status(FairyStatus.FAILED)

    def dead_fairies(self, silence_threshold_seconds: float = 60.0) -> List[str]:
        """Find fairies that haven't been heard from in a while."""
        with self._lock:
            return [
                name for name, record in self._fairies.items()
                if record.silence_seconds > silence_threshold_seconds
            ]

    # ═══════════════════════════════════════════════════════════════════════
    # REPORTING
    # ═══════════════════════════════════════════════════════════════════════

    @property
    def status(self) -> DirectoryStatus:
        return self._calculate_status()

    @property
    def uptime_seconds(self) -> float:
        return (datetime.now() - self._created_at).total_seconds()

    def to_dict(self) -> Dict[str, Any]:
        """Serialize directory state."""
        with self._lock:
            return {
                "status": self.status.value,
                "health": self.system_health(),
                "fairies": {
                    name: {
                        "status": record.fairy.status.value,
                        "plane": record.fairy.plane,
                        "capabilities": list(record.capabilities),
                        "age_seconds": record.age_seconds,
                        "silence_seconds": record.silence_seconds
                    }
                    for name, record in self._fairies.items()
                },
                "by_plane": {plane: list(names) for plane, names in self._by_plane.items()},
                "by_capability": {cap: list(names) for cap, names in self._by_capability.items()}
            }

    def fairy_table(self) -> str:
        """ASCII table of all fairies for dashboard."""
        lines = [
            "=" * 80,
            f"{'FAIRY':<30} {'PLANE':<8} {'STATUS':<12} {'FUNCTIONS':<10} {'SILENCE':<10}",
            "-" * 80
        ]
        with self._lock:
            for name, record in sorted(self._fairies.items()):
                fairy = record.fairy
                fn_count = len(fairy.list_functions())
                silence = f"{record.silence_seconds:.0f}s"
                lines.append(
                    f"{name:<30} {fairy.plane:<8} {fairy.status.value:<12} {fn_count:<10} {silence:<10}"
                )
        lines.append("=" * 80)
        return "\n".join(lines)

    def __repr__(self) -> str:
        return f"Directory(fairies={len(self._fairies)}, status={self.status.value})"


# ═══════════════════════════════════════════════════════════════════════════
# SINGLETON
# ═══════════════════════════════════════════════════════════════════════════

_DIRECTORY: Optional[Directory] = None
_DIR_LOCK = threading.Lock()


def get_directory() -> Directory:
    """Get the global directory singleton."""
    global _DIRECTORY

    if _DIRECTORY is None:
        with _DIR_LOCK:
            if _DIRECTORY is None:
                _DIRECTORY = Directory()

    return _DIRECTORY


def reset_directory():
    """Reset the directory singleton (for testing)."""
    global _DIRECTORY
    with _DIR_LOCK:
        _DIRECTORY = None
