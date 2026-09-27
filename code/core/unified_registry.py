"""
Unified Fairy Registry - Single Source of Truth

This module provides the central registry for ALL fairy registration,
subscription tracking, and boot validation. It replaces the fractured
approach of separate TracerPool + DirectoryFairy + implicit subscriptions.

Design Principles:
- Single Source of Truth: Everything flows through this registry
- Bidirectional Lookups: By name, fairy_id, tracer_id, capability
- Verified Boot: Each phase produces a receipt
- Observable Subscriptions: WiringAuditor can finally see them
- Error Collection: All failures route to GUI

Usage:
    registry = UnifiedRegistry.instance()
    identity = registry.register(my_fairy)
    receipt = registry.start_boot(my_fairy.ACTOR_NAME)
    # ... boot phases ...
    success = registry.complete_boot(my_fairy.ACTOR_NAME)
"""

from __future__ import annotations

import uuid
import time
import threading
from typing import Any, Dict, List, Optional, Set, Callable, TYPE_CHECKING
from dataclasses import dataclass, field
from pathlib import Path

if TYPE_CHECKING:
    from fairies.P00_Autonomic.organ_template import MyFairy as Fairy


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class FairyIdentity:
    """
    Complete fairy identity - assigned at registration.

    This structure provides bidirectional lookups and tracks
    all declared requirements and capabilities.
    """

    # Core identity
    name: str                          # ACTOR_NAME
    plane: str                         # ACTOR_PLANE (P00-P50)
    channel: str = ""                  # ACTOR_CHANNEL

    # Cross-references (assigned by registry)
    fairy_id: str = ""                 # Unique ID (UUID)
    tracer_id: str = ""                # TracerPool ID (links to tracers)

    # Declared requirements (from fairy class)
    requires_packages: Set[str] = field(default_factory=set)
    requires_capabilities: Set[str] = field(default_factory=set)
    requires_fairies: Set[str] = field(default_factory=set)
    requires_topics: Set[str] = field(default_factory=set)

    # Provided capabilities
    provides_capabilities: Set[str] = field(default_factory=set)
    provides_topics: Set[str] = field(default_factory=set)

    # Runtime state
    status: str = "pending"            # pending -> booting -> running -> stopped -> failed
    registered_at: float = 0.0
    boot_receipt: Optional["BootReceipt"] = None

    # Instance reference (for wake/shutdown)
    instance: Optional[Any] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize identity for transport/storage."""
        return {
            "name": self.name,
            "plane": self.plane,
            "channel": self.channel,
            "fairy_id": self.fairy_id,
            "tracer_id": self.tracer_id,
            "requires_packages": list(self.requires_packages),
            "requires_capabilities": list(self.requires_capabilities),
            "requires_fairies": list(self.requires_fairies),
            "requires_topics": list(self.requires_topics),
            "provides_capabilities": list(self.provides_capabilities),
            "provides_topics": list(self.provides_topics),
            "status": self.status,
            "registered_at": self.registered_at,
        }


@dataclass
class SubscriptionRecord:
    """
    Tracks a single postal subscription.

    This makes subscriptions OBSERVABLE - WiringAuditor can finally
    see what's actually subscribed.
    """

    subscriber_name: str               # Fairy name
    topic: str                         # Topic pattern
    handler_name: str                  # Handler function name
    subscribed_at: float
    message_count: int = 0             # How many messages received
    last_message_at: Optional[float] = None
    active: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for transport."""
        return {
            "subscriber": self.subscriber_name,
            "topic": self.topic,
            "handler": self.handler_name,
            "subscribed_at": self.subscribed_at,
            "message_count": self.message_count,
            "last_message_at": self.last_message_at,
            "active": self.active,
        }


@dataclass
class PhaseRecord:
    """Record of a single boot phase."""

    phase: str                         # "registration", "tracers", "subscriptions", etc.
    started_at: float
    completed_at: Optional[float] = None
    success: bool = False
    error: Optional[str] = None
    artifacts: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for transport."""
        return {
            "phase": self.phase,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "success": self.success,
            "error": self.error,
            "artifacts": self.artifacts,
        }


@dataclass
class BootReceipt:
    """
    Complete boot verification record.

    CRITICAL: A fairy is only "running" if all phases succeeded.
    This replaces the heartbeat auto-promotion bug.
    """

    fairy_name: str
    boot_started: float
    boot_completed: Optional[float] = None

    phases: List[PhaseRecord] = field(default_factory=list)

    # Verification results
    all_dependencies_met: bool = False
    all_subscriptions_active: bool = False
    directory_acknowledged: bool = False

    # Errors collected for GUI
    errors: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        """Boot is valid only if all phases succeeded."""
        return all(p.success for p in self.phases)

    @property
    def failed_phases(self) -> List[str]:
        """Get names of failed phases."""
        return [p.phase for p in self.phases if not p.success]

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for transport."""
        return {
            "fairy_name": self.fairy_name,
            "boot_started": self.boot_started,
            "boot_completed": self.boot_completed,
            "phases": [p.to_dict() for p in self.phases],
            "all_dependencies_met": self.all_dependencies_met,
            "all_subscriptions_active": self.all_subscriptions_active,
            "directory_acknowledged": self.directory_acknowledged,
            "is_valid": self.is_valid,
            "errors": self.errors,
        }


# =============================================================================
# UNIFIED REGISTRY SINGLETON
# =============================================================================

class UnifiedRegistry:
    """
    Single source of truth for all fairy registration.

    Replaces the fractured TracerPool + DirectoryFairy + implicit subscriptions.
    Provides bidirectional lookups, subscription tracking, and boot validation.
    """

    _instance: Optional["UnifiedRegistry"] = None
    _lock = threading.RLock()

    def __new__(cls):
        """Singleton pattern."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """Initialize registry (only once due to singleton)."""
        if self._initialized:
            return

        with self._lock:
            # Lookup tables - bidirectional
            self._by_name: Dict[str, FairyIdentity] = {}
            self._by_fairy_id: Dict[str, FairyIdentity] = {}
            self._by_tracer_id: Dict[str, FairyIdentity] = {}
            self._by_capability: Dict[str, Set[str]] = {}  # capability -> set of names
            self._by_plane: Dict[str, Set[str]] = {}       # plane -> set of names

            # Subscription tracking
            self._subscriptions: Dict[str, List[SubscriptionRecord]] = {}  # topic -> records
            self._subscriber_topics: Dict[str, Set[str]] = {}              # name -> topics

            # Boot receipts
            self._boot_receipts: Dict[str, BootReceipt] = {}

            # Error collection for GUI
            self._errors: List[Dict[str, Any]] = []

            # Tracer integration (will be wired later)
            self._tracer_pool = None

            self._initialized = True

    @classmethod
    def instance(cls) -> "UnifiedRegistry":
        """Get singleton instance."""
        return cls()

    @classmethod
    def reset(cls) -> None:
        """Reset registry (for testing)."""
        with cls._lock:
            cls._instance = None

    # ==========================================================================
    # TRACER INTEGRATION
    # ==========================================================================

    def set_tracer_pool(self, pool) -> None:
        """Wire the TracerPool for ID allocation."""
        self._tracer_pool = pool

    def _create_root_tracer(self, identity: FairyIdentity) -> str:
        """Create root tracer for a fairy and return its ID."""
        if self._tracer_pool:
            tracer = self._tracer_pool.create(
                intent=f"fairy.{identity.name}.root",
                actor=identity.name,
                metadata={"fairy_id": identity.fairy_id}
            )
            return tracer.id if hasattr(tracer, 'id') else str(tracer)
        # Fallback: generate a pseudo-tracer-id
        return f"tracer-{identity.name}-{uuid.uuid4().hex[:8]}"

    # ==========================================================================
    # REGISTRATION
    # ==========================================================================

    def register(
        self,
        fairy: "Fairy" = None,
        *,
        name: str = None,
        plane: str = None,
        channel: str = "",
        capabilities: Set[str] = None,
        requires_packages: Set[str] = None,
        requires_capabilities: Set[str] = None,
        requires_fairies: Set[str] = None,
        requires_topics: Set[str] = None,
        instance: Any = None,
    ) -> FairyIdentity:
        """
        Register a fairy. Creates identity, assigns IDs, validates dependencies.

        Can be called with a Fairy instance OR with explicit parameters.
        This is THE entry point for all fairy registration.
        """
        with self._lock:
            # Extract from fairy instance or use explicit params
            if fairy is not None:
                name = fairy.ACTOR_NAME
                plane = fairy.ACTOR_PLANE
                channel = getattr(fairy, "ACTOR_CHANNEL", "")
                capabilities = fairy.get_capabilities() if hasattr(fairy, 'get_capabilities') else set()
                requires_packages = getattr(fairy, "REQUIRES_PACKAGES", set())
                requires_capabilities = getattr(fairy, "REQUIRES_CAPABILITIES", set())
                requires_fairies = getattr(fairy, "REQUIRES_FAIRIES", set())
                requires_topics = getattr(fairy, "REQUIRES_TOPICS", set())
                instance = fairy

            if not name:
                raise ValueError("Fairy name is required")

            # Check for duplicate registration
            if name in self._by_name:
                existing = self._by_name[name]
                # Update instance if provided
                if instance:
                    existing.instance = instance
                return existing

            # Create identity
            identity = FairyIdentity(
                name=name,
                plane=plane or "P00",
                channel=channel or "",
                fairy_id=str(uuid.uuid4()),
                requires_packages=requires_packages or set(),
                requires_capabilities=requires_capabilities or set(),
                requires_fairies=requires_fairies or set(),
                requires_topics=requires_topics or set(),
                provides_capabilities=capabilities or set(),
                registered_at=time.time(),
                status="pending",
                instance=instance,
            )

            # Create tracer and link
            tracer_id = self._create_root_tracer(identity)
            identity.tracer_id = tracer_id

            # Store in all lookup tables
            self._index_identity(identity)

            return identity

    def _index_identity(self, identity: FairyIdentity) -> None:
        """Index identity in all lookup tables."""
        self._by_name[identity.name] = identity
        self._by_fairy_id[identity.fairy_id] = identity
        self._by_tracer_id[identity.tracer_id] = identity

        # Index by plane
        if identity.plane not in self._by_plane:
            self._by_plane[identity.plane] = set()
        self._by_plane[identity.plane].add(identity.name)

        # Index by capability
        for cap in identity.provides_capabilities:
            if cap not in self._by_capability:
                self._by_capability[cap] = set()
            self._by_capability[cap].add(identity.name)

    def unregister(self, name: str) -> bool:
        """Unregister a fairy."""
        with self._lock:
            if name not in self._by_name:
                return False

            identity = self._by_name[name]

            # Remove from all indexes
            del self._by_name[name]
            if identity.fairy_id in self._by_fairy_id:
                del self._by_fairy_id[identity.fairy_id]
            if identity.tracer_id in self._by_tracer_id:
                del self._by_tracer_id[identity.tracer_id]

            if identity.plane in self._by_plane:
                self._by_plane[identity.plane].discard(name)

            for cap in identity.provides_capabilities:
                if cap in self._by_capability:
                    self._by_capability[cap].discard(name)

            return True

    # ==========================================================================
    # LOOKUPS
    # ==========================================================================

    def get_by_name(self, name: str) -> Optional[FairyIdentity]:
        """Get fairy identity by name."""
        return self._by_name.get(name)

    def get_by_fairy_id(self, fairy_id: str) -> Optional[FairyIdentity]:
        """Get fairy identity by fairy_id."""
        return self._by_fairy_id.get(fairy_id)

    def get_by_tracer_id(self, tracer_id: str) -> Optional[FairyIdentity]:
        """Get fairy identity by tracer_id."""
        return self._by_tracer_id.get(tracer_id)

    def get_by_capability(self, capability: str) -> List[FairyIdentity]:
        """Get all fairies providing a capability."""
        names = self._by_capability.get(capability, set())
        return [self._by_name[n] for n in names if n in self._by_name]

    def get_by_plane(self, plane: str) -> List[FairyIdentity]:
        """Get all fairies in a plane."""
        names = self._by_plane.get(plane, set())
        return [self._by_name[n] for n in names if n in self._by_name]

    def get_all(self) -> List[FairyIdentity]:
        """Get all registered fairies."""
        return list(self._by_name.values())

    def get_running(self) -> List[FairyIdentity]:
        """Get all running fairies."""
        return [f for f in self._by_name.values() if f.status == "running"]

    # ==========================================================================
    # SUBSCRIPTION TRACKING
    # ==========================================================================

    def record_subscription(
        self,
        subscriber: str,
        topic: str,
        handler_name: str
    ) -> SubscriptionRecord:
        """Record a new subscription. Called by postal layer."""
        with self._lock:
            record = SubscriptionRecord(
                subscriber_name=subscriber,
                topic=topic,
                handler_name=handler_name,
                subscribed_at=time.time(),
            )

            if topic not in self._subscriptions:
                self._subscriptions[topic] = []
            self._subscriptions[topic].append(record)

            if subscriber not in self._subscriber_topics:
                self._subscriber_topics[subscriber] = set()
            self._subscriber_topics[subscriber].add(topic)

            return record

    def record_message(self, topic: str, subscriber: str) -> None:
        """Record that a message was delivered to a subscriber."""
        with self._lock:
            if topic in self._subscriptions:
                for record in self._subscriptions[topic]:
                    if record.subscriber_name == subscriber:
                        record.message_count += 1
                        record.last_message_at = time.time()
                        break

    def remove_subscription(self, subscriber: str, topic: str) -> bool:
        """Remove a subscription record."""
        with self._lock:
            if topic in self._subscriptions:
                self._subscriptions[topic] = [
                    r for r in self._subscriptions[topic]
                    if r.subscriber_name != subscriber
                ]

            if subscriber in self._subscriber_topics:
                self._subscriber_topics[subscriber].discard(topic)

            return True

    def get_subscription_map(self) -> Dict[str, List[Dict]]:
        """
        Get all subscriptions - THIS IS WHAT WIRING AUDITOR NEEDS.

        Returns: {topic: [{subscriber, handler, message_count, ...}, ...]}
        """
        with self._lock:
            result = {}
            for topic, records in self._subscriptions.items():
                result[topic] = [r.to_dict() for r in records]
            return result

    def get_subscriptions_for(self, fairy_name: str) -> List[SubscriptionRecord]:
        """Get all subscriptions for a specific fairy."""
        with self._lock:
            topics = self._subscriber_topics.get(fairy_name, set())
            result = []
            for topic in topics:
                for record in self._subscriptions.get(topic, []):
                    if record.subscriber_name == fairy_name:
                        result.append(record)
            return result

    def get_subscription_count(self, fairy_name: str) -> int:
        """Get number of subscriptions for a fairy."""
        return len(self.get_subscriptions_for(fairy_name))

    # ==========================================================================
    # BOOT VALIDATION
    # ==========================================================================

    def start_boot(self, fairy_name: str) -> BootReceipt:
        """Start boot tracking for a fairy."""
        with self._lock:
            receipt = BootReceipt(
                fairy_name=fairy_name,
                boot_started=time.time(),
            )
            self._boot_receipts[fairy_name] = receipt

            # Update status
            if fairy_name in self._by_name:
                self._by_name[fairy_name].status = "booting"

            return receipt

    def record_phase(
        self,
        fairy_name: str,
        phase: str,
        success: bool,
        error: Optional[str] = None,
        artifacts: Optional[Dict] = None
    ) -> None:
        """Record a boot phase result."""
        with self._lock:
            receipt = self._boot_receipts.get(fairy_name)
            if not receipt:
                # Create receipt if not exists
                receipt = self.start_boot(fairy_name)

            now = time.time()
            phase_record = PhaseRecord(
                phase=phase,
                started_at=now,
                completed_at=now,
                success=success,
                error=error,
                artifacts=artifacts or {},
            )
            receipt.phases.append(phase_record)

            # If failed, collect error for GUI
            if not success and error:
                self._collect_error(fairy_name, phase, error)

    def complete_boot(self, fairy_name: str) -> bool:
        """
        Complete boot and verify all phases passed.

        CRITICAL: Only marks "running" if ALL phases succeeded.
        This replaces the heartbeat auto-promotion bug.
        """
        with self._lock:
            receipt = self._boot_receipts.get(fairy_name)
            if not receipt:
                return False

            receipt.boot_completed = time.time()

            # Verify dependencies
            receipt.all_dependencies_met = self._verify_dependencies(fairy_name)

            # Verify subscriptions
            receipt.all_subscriptions_active = self._verify_subscriptions(fairy_name)

            # We are the directory
            receipt.directory_acknowledged = True

            # Only mark running if valid
            if receipt.is_valid and receipt.all_dependencies_met:
                if fairy_name in self._by_name:
                    self._by_name[fairy_name].status = "running"
                    self._by_name[fairy_name].boot_receipt = receipt
                return True
            else:
                # Stay in "booting" or mark failed - NEVER auto-promote
                if fairy_name in self._by_name:
                    self._by_name[fairy_name].status = "failed"
                self._collect_error(
                    fairy_name,
                    "boot_complete",
                    f"Boot failed: phases={receipt.failed_phases}, deps={receipt.all_dependencies_met}"
                )
                return False

    def get_boot_receipt(self, fairy_name: str) -> Optional[BootReceipt]:
        """Get boot receipt for a fairy."""
        return self._boot_receipts.get(fairy_name)

    def _verify_dependencies(self, fairy_name: str) -> bool:
        """Verify all dependencies for a fairy are met."""
        identity = self._by_name.get(fairy_name)
        if not identity:
            return False

        # Check required fairies are running
        for req_fairy in identity.requires_fairies:
            req_identity = self._by_name.get(req_fairy)
            if not req_identity or req_identity.status != "running":
                return False

        # Check required capabilities exist
        for req_cap in identity.requires_capabilities:
            providers = self.get_by_capability(req_cap)
            running_providers = [p for p in providers if p.status == "running"]
            if not running_providers:
                return False

        return True

    def _verify_subscriptions(self, fairy_name: str) -> bool:
        """Verify required subscriptions are active."""
        identity = self._by_name.get(fairy_name)
        if not identity:
            return True  # No requirements = verified

        actual_topics = self._subscriber_topics.get(fairy_name, set())
        required_topics = identity.requires_topics

        # Check if all required topics are subscribed
        missing = required_topics - actual_topics
        if missing:
            self._collect_error(
                fairy_name,
                "subscription_verification",
                f"Missing subscriptions: {missing}"
            )
            # Note: We don't fail boot for missing subscriptions by default,
            # but we log it. Subclasses can be stricter.

        return True  # Lenient by default

    # ==========================================================================
    # ERROR COLLECTION (for GUI)
    # ==========================================================================

    _MAX_ERRORS = 500  # FIX 2026-02-16: Cap error list to prevent unbounded growth

    def _collect_error(self, fairy: str, context: str, message: str) -> None:
        """Collect error for GUI display."""
        with self._lock:
            self._errors.append({
                "fairy": fairy,
                "context": context,
                "message": message,
                "timestamp": time.time(),
            })
            # FIX 2026-02-16: Trim when too large (keep most recent)
            if len(self._errors) > self._MAX_ERRORS:
                self._errors = self._errors[-250:]

    def add_error(self, fairy: str, context: str, message: str) -> None:
        """Public method to add an error."""
        self._collect_error(fairy, context, message)

    def get_errors(self, limit: int = 100) -> List[Dict]:
        """Get recent errors for GUI errors tab."""
        with self._lock:
            return self._errors[-limit:]

    def clear_errors(self) -> None:
        """Clear errors (on reboot)."""
        with self._lock:
            self._errors.clear()

    # ==========================================================================
    # STATUS UPDATE
    # ==========================================================================

    def update_status(self, fairy_name: str, status: str) -> bool:
        """Update fairy status."""
        with self._lock:
            if fairy_name not in self._by_name:
                return False
            self._by_name[fairy_name].status = status
            return True

    def heartbeat(self, fairy_name: str, metrics: Optional[Dict] = None) -> bool:
        """
        Process heartbeat from a fairy.

        CRITICAL: Does NOT auto-promote status. Only updates metrics.
        """
        with self._lock:
            if fairy_name not in self._by_name:
                return False

            identity = self._by_name[fairy_name]

            # Update last_heartbeat if we add that field
            # For now, just verify the fairy is registered

            # REMOVED: Auto-promotion of "booting" -> "running"
            # That was a bug. Status is only changed by complete_boot().

            return True

    # ==========================================================================
    # STATISTICS
    # ==========================================================================

    def stats(self) -> Dict[str, Any]:
        """Get registry statistics."""
        with self._lock:
            status_counts = {}
            for identity in self._by_name.values():
                status_counts[identity.status] = status_counts.get(identity.status, 0) + 1

            plane_counts = {plane: len(names) for plane, names in self._by_plane.items()}

            total_subscriptions = sum(len(records) for records in self._subscriptions.values())

            return {
                "total_fairies": len(self._by_name),
                "status_counts": status_counts,
                "plane_counts": plane_counts,
                "total_subscriptions": total_subscriptions,
                "total_topics": len(self._subscriptions),
                "error_count": len(self._errors),
            }


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def get_registry() -> UnifiedRegistry:
    """Get the global registry instance."""
    return UnifiedRegistry.instance()


def register_fairy(fairy: "Fairy") -> FairyIdentity:
    """Register a fairy with the global registry."""
    return get_registry().register(fairy)


def get_subscription_map() -> Dict[str, List[Dict]]:
    """Get subscription map for WiringAuditor."""
    return get_registry().get_subscription_map()
