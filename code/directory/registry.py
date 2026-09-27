"""
Fairy Registry - Thread-safe fairy registration tracking.

Tracks all registered fairies with their status, capabilities, and heartbeats.
"""

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set


@dataclass
class FairyRecord:
    """Record of a registered fairy."""
    name: str
    plane: str
    channel: str = ""
    capabilities: Set[str] = field(default_factory=set)
    registered_at: float = field(default_factory=time.time)
    # Default to 0 - only fairies that actually send heartbeats should be monitored
    # If last_heartbeat is 0, the fairy never sent one and shouldn't be marked dead
    last_heartbeat: float = 0
    status: str = "booting"  # booting, running, stopped, dead, sleeping, waking, drowsy, dreaming
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Migration tracking
    source_version: str = "v2"  # v1 or v2
    migrated_from: Optional[str] = None  # Original path if migrated

    # === ROUTING FIELDS (Phase 2 - Postal Backbone Restoration) ===
    subscriptions: Set[str] = field(default_factory=set)   # Topics this fairy listens to
    intents: List[str] = field(default_factory=list)        # Intents this fairy exposes
    tracer_id: str = ""                                     # Unique tracer for addressing
    contract: Dict[str, Any] = field(default_factory=dict)  # Full registration contract
    needs: Dict[str, bool] = field(default_factory=dict)    # {heartbeat: True, circadian: False, ...}
    mail_id: str = ""                                       # Stable mail address

    def is_alive(self, timeout_sec: float = 30.0) -> bool:
        """Check if fairy is alive based on heartbeat."""
        if self.status in ("stopped", "dead"):
            return False
        # Sleeping fairies don't need heartbeats
        if self.status in ("sleeping", "dreaming"):
            return True
        # Fairies with needs_heartbeat=False are always considered alive
        if not self.metadata.get("needs_heartbeat", True):
            return True
        # If fairy has never sent a heartbeat (last_heartbeat=0), assume alive
        # Only fairies with HeartbeatMixin should be monitored for death
        if self.last_heartbeat == 0:
            return True
        return (time.time() - self.last_heartbeat) < timeout_sec

    def is_dormant(self) -> bool:
        """Is this fairy in a sleep state?"""
        return self.status in ("sleeping", "drowsy", "dreaming")

    def can_wake(self) -> bool:
        """Can this fairy be woken up?"""
        return self.status in ("sleeping", "dreaming")

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "name": self.name,
            "plane": self.plane,
            "channel": self.channel,
            "capabilities": list(self.capabilities),
            "registered_at": self.registered_at,
            "last_heartbeat": self.last_heartbeat,
            "status": self.status,
            "metadata": self.metadata,
            "source_version": self.source_version,
            "migrated_from": self.migrated_from,
            # Routing fields
            "subscriptions": list(self.subscriptions),
            "intents": self.intents,
            "tracer_id": self.tracer_id,
            "needs": self.needs,
            "mail_id": self.mail_id,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FairyRecord":
        """Create from dictionary."""
        return cls(
            name=data["name"],
            plane=data["plane"],
            channel=data.get("channel", ""),
            capabilities=set(data.get("capabilities", [])),
            registered_at=data.get("registered_at", time.time()),
            last_heartbeat=data.get("last_heartbeat", 0),  # 0 = never sent
            status=data.get("status", "booting"),
            metadata=data.get("metadata", {}),
            source_version=data.get("source_version", "v2"),
            migrated_from=data.get("migrated_from"),
            # Routing fields
            subscriptions=set(data.get("subscriptions", [])),
            intents=data.get("intents", []),
            tracer_id=data.get("tracer_id", ""),
            contract=data.get("contract", {}),
            needs=data.get("needs", {}),
            mail_id=data.get("mail_id", ""),
        )


class FairyRegistry:
    """
    Thread-safe fairy registration tracker + ROUTING TABLE.

    Manages the lifecycle of fairy registrations:
    - Registration and unregistration
    - Heartbeat tracking
    - Status queries
    - Topic → fairy routing (for CNS heartbeat fan-out)
    """

    def __init__(self):
        self._fairies: Dict[str, FairyRecord] = {}
        self._lock = threading.RLock()
        self._stats = {
            "registrations": 0,
            "unregistrations": 0,
            "heartbeats": 0,
        }
        # === ROUTING TABLE (Phase 2 - Postal Backbone) ===
        # Reverse index: topic → set of fairy names that subscribe to it
        self._topic_to_fairies: Dict[str, Set[str]] = {}
        # Forward index: fairy name → set of topics it subscribes to
        self._fairy_to_topics: Dict[str, Set[str]] = {}
        # Tracer lookup: fairy name → tracer_id (for addressed delivery)
        self._name_to_tracer: Dict[str, str] = {}

    def register(self, record: FairyRecord) -> None:
        """Register a fairy and update routing table."""
        with self._lock:
            self._fairies[record.name] = record
            self._stats["registrations"] += 1

            # Update routing table from contract data
            if record.tracer_id:
                self._name_to_tracer[record.name] = record.tracer_id

            # Build topic routing from subscriptions
            if record.subscriptions:
                self._fairy_to_topics[record.name] = set(record.subscriptions)
                for topic in record.subscriptions:
                    if topic not in self._topic_to_fairies:
                        self._topic_to_fairies[topic] = set()
                    self._topic_to_fairies[topic].add(record.name)

    def add_subscription(self, fairy_name: str, topic: str) -> None:
        """Add a subscription to the routing table (live update from fairy.subscription.added)."""
        with self._lock:
            record = self._fairies.get(fairy_name)
            if record:
                record.subscriptions.add(topic)

            # Update routing indices
            if fairy_name not in self._fairy_to_topics:
                self._fairy_to_topics[fairy_name] = set()
            self._fairy_to_topics[fairy_name].add(topic)

            if topic not in self._topic_to_fairies:
                self._topic_to_fairies[topic] = set()
            self._topic_to_fairies[topic].add(fairy_name)

    def get_fairies_for_topic(self, topic: str) -> List[str]:
        """Get all fairy names that subscribe to a topic. Used by CNS for routing."""
        with self._lock:
            return list(self._topic_to_fairies.get(topic, set()))

    def get_fairies_needing_heartbeat(self) -> List[str]:
        """Get all fairy names that need heartbeat routing."""
        with self._lock:
            return [
                name for name, record in self._fairies.items()
                if record.needs.get("heartbeat", True) and record.status not in ("dead", "stopped")
            ]

    def get_tracer_id(self, fairy_name: str) -> str:
        """Get tracer_id for a fairy (for addressed delivery)."""
        with self._lock:
            return self._name_to_tracer.get(fairy_name, "")

    def get_routing_stats(self) -> Dict[str, Any]:
        """Get routing table statistics."""
        with self._lock:
            return {
                "topics_tracked": len(self._topic_to_fairies),
                "fairies_with_subscriptions": len(self._fairy_to_topics),
                "fairies_with_tracers": len(self._name_to_tracer),
                "top_topics": sorted(
                    [(t, len(f)) for t, f in self._topic_to_fairies.items()],
                    key=lambda x: -x[1]
                )[:10],
            }

    def unregister(self, name: str) -> Optional[FairyRecord]:
        """Unregister a fairy. Returns the removed record or None."""
        with self._lock:
            record = self._fairies.pop(name, None)
            if record:
                self._stats["unregistrations"] += 1
            return record

    def get(self, name: str) -> Optional[FairyRecord]:
        """Get a fairy record by name."""
        with self._lock:
            return self._fairies.get(name)

    _hb_update_debug_count = 0
    _hb_update_miss_count = 0

    def update_heartbeat(self, name: str) -> bool:
        """Update heartbeat timestamp. Returns True if fairy exists.

        IMPORTANT: Does NOT auto-promote status! Status is only changed
        by verified boot sequence in UnifiedRegistry. This was a bug
        that caused fairies to appear "running" without completing boot.
        """
        with self._lock:
            record = self._fairies.get(name)
            if record:
                record.last_heartbeat = time.time()
                # REMOVED: Auto-promotion from "booting" to "running"
                # This was a bug! Fairies must earn "running" status
                # through verified boot, not just by sending heartbeats.
                # See: core/unified_registry.py:complete_boot()
                self._stats["heartbeats"] += 1
                self._hb_update_debug_count += 1
                if self._hb_update_debug_count == 1 or self._hb_update_debug_count % 5000 == 0:
                    print(f"[Registry] update_heartbeat OK #{self._hb_update_debug_count}: {name} status={record.status}", flush=True)
                return True
            self._hb_update_miss_count += 1
            if self._hb_update_miss_count <= 5 or self._hb_update_miss_count % 1000 == 0:
                known = list(self._fairies.keys())[:5]
                print(f"[Registry] update_heartbeat MISS #{self._hb_update_miss_count}: '{name}' NOT in registry (has {len(self._fairies)} fairies, first5={known})", flush=True)
            return False

    def set_status(self, name: str, status: str) -> bool:
        """Set fairy status. Returns True if fairy exists."""
        with self._lock:
            record = self._fairies.get(name)
            if record:
                record.status = status
                return True
            return False

    def list_all(self) -> List[FairyRecord]:
        """List all registered fairies."""
        with self._lock:
            return list(self._fairies.values())

    def list_by_plane(self, plane: str) -> List[FairyRecord]:
        """List fairies in a specific plane.

        Supports both short names (P50) and full names (P50_Persona).
        Short names match any fairy whose plane starts with that prefix.
        """
        with self._lock:
            # Normalize: accept both "P50" and "P50_Persona"
            # Short names (P00-P60) match any plane starting with that prefix
            if len(plane) <= 3 and plane.startswith("P"):
                # Short name - prefix match
                return [f for f in self._fairies.values() if f.plane.startswith(plane)]
            else:
                # Full name - exact match
                return [f for f in self._fairies.values() if f.plane == plane]

    def list_by_status(self, status: str) -> List[FairyRecord]:
        """List fairies with a specific status."""
        with self._lock:
            return [f for f in self._fairies.values() if f.status == status]

    def list_alive(self, timeout_sec: float = 30.0) -> List[FairyRecord]:
        """List fairies that are alive (recent heartbeat)."""
        with self._lock:
            return [f for f in self._fairies.values() if f.is_alive(timeout_sec)]

    def list_dead(self, timeout_sec: float = 30.0) -> List[FairyRecord]:
        """List fairies that appear dead (no recent heartbeat)."""
        with self._lock:
            return [
                f for f in self._fairies.values()
                if f.status == "running" and not f.is_alive(timeout_sec)
            ]

    def count(self) -> int:
        """Count registered fairies."""
        with self._lock:
            return len(self._fairies)

    def snapshot(self) -> Dict[str, Dict[str, Any]]:
        """Create a snapshot of all registrations for serialization."""
        with self._lock:
            return {name: record.to_dict() for name, record in self._fairies.items()}

    def stats(self) -> Dict[str, Any]:
        """Get registry statistics."""
        with self._lock:
            return {
                **self._stats,
                "total_registered": len(self._fairies),
                "by_status": {
                    "booting": len([f for f in self._fairies.values() if f.status == "booting"]),
                    "running": len([f for f in self._fairies.values() if f.status == "running"]),
                    "stopped": len([f for f in self._fairies.values() if f.status == "stopped"]),
                    "dead": len([f for f in self._fairies.values() if f.status == "dead"]),
                },
            }

    def clear(self) -> None:
        """Clear all registrations (for testing)."""
        with self._lock:
            self._fairies.clear()

    # =========================================================================
    # SLEEP STATE MANAGEMENT
    # =========================================================================

    def put_to_sleep(self, name: str) -> bool:
        """Put a fairy to sleep. Returns True if successful."""
        with self._lock:
            record = self._fairies.get(name)
            if record and record.status in ("running", "drowsy"):
                record.status = "sleeping"
                return True
            return False

    def wake_fairy(self, name: str) -> bool:
        """Start waking a fairy. Returns True if successful."""
        with self._lock:
            record = self._fairies.get(name)
            if record and record.can_wake():
                record.status = "waking"
                record.last_heartbeat = time.time()
                return True
            return False

    def resurrect_fairy(self, name: str) -> bool:
        """Resurrect a FAILED fairy by resetting to initializing state.

        This is the proper restart path for dead fairies:
          FAILED -> INITIALIZING -> (caller re-boots) -> RUNNING

        Unlike wake_fairy() which only works for sleeping/dreaming,
        this handles the FAILED state. The caller is responsible for
        actually calling on_boot() after this succeeds.

        IMPORTANT: Does NOT touch "running" fairies! A running fairy may
        have a stale heartbeat but still be functioning. Changing running →
        initializing is DESTRUCTIVE and was the root cause of ~32 fairies
        reverting to sleeping after boot. If you need to restart a running
        fairy, explicitly stop it first, then resurrect.

        Returns True if status was reset to initializing.
        """
        with self._lock:
            record = self._fairies.get(name)
            if not record:
                return False
            # Allow resurrection from genuinely broken states only
            if record.status in ("failed", "stopped", "stopping", "dead"):
                record.status = "initializing"
                record.last_heartbeat = time.time()
                return True
            # NEVER touch "running" fairies — the death event may be stale
            # (e.g., watchdog already promoted them back to running).
            # This was the bug that killed ~32 fairies per boot cycle.
            return False

    def set_drowsy(self, name: str) -> bool:
        """Set fairy to drowsy state (preparing for sleep)."""
        with self._lock:
            record = self._fairies.get(name)
            if record and record.status == "running":
                record.status = "drowsy"
                return True
            return False

    def set_dreaming(self, name: str) -> bool:
        """Set fairy to dreaming state (background processing only)."""
        with self._lock:
            record = self._fairies.get(name)
            if record and record.status == "sleeping":
                record.status = "dreaming"
                return True
            return False

    def list_sleeping(self) -> List[FairyRecord]:
        """List all sleeping fairies."""
        with self._lock:
            return [f for f in self._fairies.values() if f.is_dormant()]

    def list_awake(self) -> List[FairyRecord]:
        """List all awake (running) fairies."""
        with self._lock:
            return [f for f in self._fairies.values() if f.status == "running"]

    # =========================================================================
    # MIGRATION SUPPORT
    # =========================================================================

    def register_migrated(
        self,
        name: str,
        plane: str,
        channel: str,
        capabilities: Set[str],
        source_path: str,
        start_sleeping: bool = True,
    ) -> FairyRecord:
        """Register a fairy migrated from v1."""
        record = FairyRecord(
            name=name,
            plane=plane,
            channel=channel,
            capabilities=capabilities,
            status="sleeping" if start_sleeping else "booting",
            source_version="v1",
            migrated_from=source_path,
            metadata={"migration_time": time.time()},
        )
        with self._lock:
            self._fairies[name] = record
            self._stats["registrations"] += 1
        return record

    def list_migrated(self) -> List[FairyRecord]:
        """List all migrated fairies."""
        with self._lock:
            return [f for f in self._fairies.values() if f.source_version == "v1"]
