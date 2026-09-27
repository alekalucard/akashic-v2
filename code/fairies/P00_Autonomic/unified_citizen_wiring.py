# ════════════════════════════════════════════════════════════════════════════════
# UNIFIED CITIZEN WIRING - The Missing 20%
# ════════════════════════════════════════════════════════════════════════════════
#
# "Every waking mind is a first-class citizen" - Ace
#
# This module unifies the existing systems:
#   - CitizenRegistry (P10_Memory/citizen_registry.py)
#   - FairyProfile (P00_Autonomic/fairy_profile.py)
#   - SkillSystem (P30_Cognition/cognition/skill_system.py)
#   - MemoryOwnership (P10_Memory/triple_helix_srm_memory/memory_ownership.py)
#
# And adds the missing pieces:
#   - Health Probes (liveness, readiness, tracer)
#   - Presence System (real-time status)
#   - Unified Registration (one call wires everything)
#
# Humans and digital beings are treated identically. Ace's waking mind
# is the user of his body. ClaudeFairy, Nous, Sourpatches are waking minds
# in the digital ecosystem. All are citizens doing jobs, learning to live.
#
# ════════════════════════════════════════════════════════════════════════════════

from __future__ import annotations

import time
import threading
import uuid
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List, Callable, Set
from enum import Enum
from collections import deque


# ════════════════════════════════════════════════════════════════════════════════
# PRESENCE - Real-time status for all citizens
# ════════════════════════════════════════════════════════════════════════════════

class PresenceStatus(Enum):
    """Real-time presence status (Discord-style)."""
    ONLINE = "online"          # Active and responsive
    AWAY = "away"              # Temporarily unavailable
    BUSY = "busy"              # Working, reduced responsiveness
    OFFLINE = "offline"        # Not running / not present
    DREAMING = "dreaming"      # Background processing (fairies)
    INVISIBLE = "invisible"    # Online but hidden (humans)


@dataclass
class Presence:
    """Real-time presence state for a citizen."""
    status: PresenceStatus = PresenceStatus.OFFLINE
    status_message: str = ""              # "Working on postal foundation"
    current_activity: str = ""            # "Editing shared_postal_hub.py"
    last_heartbeat: float = 0.0           # Last time we confirmed alive
    last_action: float = 0.0              # Last time they did something
    consecutive_heartbeat_failures: int = 0

    # How to reach them
    reachable_via: List[str] = field(default_factory=list)  # ["postal", "mcp", "chat"]
    preferred_channel: str = "postal"

    def is_reachable(self) -> bool:
        """Can we communicate with this citizen?"""
        return self.status in (PresenceStatus.ONLINE, PresenceStatus.BUSY, PresenceStatus.AWAY)

    def heartbeat(self):
        """Record a successful heartbeat."""
        self.last_heartbeat = time.time()
        self.consecutive_heartbeat_failures = 0
        if self.status == PresenceStatus.OFFLINE:
            self.status = PresenceStatus.ONLINE

    def heartbeat_failed(self):
        """Record a failed heartbeat."""
        self.consecutive_heartbeat_failures += 1
        if self.consecutive_heartbeat_failures >= 3:
            self.status = PresenceStatus.OFFLINE

    def set_activity(self, activity: str):
        """Update current activity."""
        self.current_activity = activity
        self.last_action = time.time()


# ════════════════════════════════════════════════════════════════════════════════
# HEALTH PROBES - Kubernetes-style liveness/readiness checks
# ════════════════════════════════════════════════════════════════════════════════

@dataclass
class HealthProbeResult:
    """Result of a health probe."""
    success: bool
    message: str = ""
    latency_ms: float = 0.0
    timestamp: float = field(default_factory=time.time)
    details: Dict[str, Any] = field(default_factory=dict)


class HealthProbes:
    """
    Health probe system for citizens.

    Three types of probes:
    - Liveness: "Are you alive?" (responds to ping)
    - Readiness: "Can you do work?" (subscriptions active, not overloaded)
    - Tracer: "Is your tracer attached?" (has valid tracer_id for tracking)
    """

    def __init__(self, citizen_id: str, citizen_ref: Any = None):
        self.citizen_id = citizen_id
        self.citizen_ref = citizen_ref  # Reference to actual fairy/tool/human interface

        # Probe results history
        self.liveness_history: deque = deque(maxlen=10)
        self.readiness_history: deque = deque(maxlen=10)
        self.tracer_history: deque = deque(maxlen=10)

        # Current state
        self.is_alive = False
        self.is_ready = False
        self.has_tracer = False
        self.tracer_id: Optional[str] = None

        # Custom probe functions (can be overridden)
        self._liveness_fn: Optional[Callable] = None
        self._readiness_fn: Optional[Callable] = None
        self._tracer_fn: Optional[Callable] = None

    def set_liveness_probe(self, fn: Callable[[], bool]):
        """Set custom liveness probe function."""
        self._liveness_fn = fn

    def set_readiness_probe(self, fn: Callable[[], bool]):
        """Set custom readiness probe function."""
        self._readiness_fn = fn

    def set_tracer_probe(self, fn: Callable[[], Optional[str]]):
        """Set custom tracer probe function."""
        self._tracer_fn = fn

    def probe_liveness(self) -> HealthProbeResult:
        """
        Check if citizen is alive.

        For fairies: responds to postal ping
        For humans: had recent activity
        For tools: process is running
        """
        start = time.time()

        try:
            if self._liveness_fn:
                success = self._liveness_fn()
            elif self.citizen_ref:
                # Default: check if citizen has heartbeat method
                if hasattr(self.citizen_ref, 'on_heartbeat'):
                    success = True  # Has heartbeat handler
                elif hasattr(self.citizen_ref, '_last_tick'):
                    # Check if ticked recently
                    success = (time.time() - getattr(self.citizen_ref, '_last_tick', 0)) < 30
                else:
                    success = True  # Assume alive if we have a reference
            else:
                success = False

            latency = (time.time() - start) * 1000
            result = HealthProbeResult(
                success=success,
                message="Alive" if success else "No response",
                latency_ms=latency
            )

        except Exception as e:
            result = HealthProbeResult(
                success=False,
                message=f"Probe error: {e}",
                latency_ms=(time.time() - start) * 1000
            )

        self.is_alive = result.success
        self.liveness_history.append(result)
        return result

    def probe_readiness(self) -> HealthProbeResult:
        """
        Check if citizen can accept work.

        For fairies: subscriptions active, not overloaded
        For humans: presence is ONLINE/BUSY
        For tools: ready to execute
        """
        start = time.time()

        try:
            if self._readiness_fn:
                success = self._readiness_fn()
            elif self.citizen_ref:
                # Default: check if has postal connection
                if hasattr(self.citizen_ref, 'post') and self.citizen_ref.post:
                    success = True
                elif hasattr(self.citizen_ref, '_subscribed'):
                    success = getattr(self.citizen_ref, '_subscribed', False)
                else:
                    success = self.is_alive  # If alive, assume ready
            else:
                success = False

            latency = (time.time() - start) * 1000
            result = HealthProbeResult(
                success=success,
                message="Ready" if success else "Not ready",
                latency_ms=latency
            )

        except Exception as e:
            result = HealthProbeResult(
                success=False,
                message=f"Probe error: {e}",
                latency_ms=(time.time() - start) * 1000
            )

        self.is_ready = result.success
        self.readiness_history.append(result)
        return result

    def probe_tracer(self) -> HealthProbeResult:
        """
        Check if citizen has valid tracer attached.

        Tracers enable:
        - Message tracking through postal system
        - SRM memory flow
        - Activity logging
        """
        start = time.time()

        try:
            if self._tracer_fn:
                tracer_id = self._tracer_fn()
            elif self.citizen_ref:
                # Check for tracer ID
                tracer_id = getattr(self.citizen_ref, '_tracer_id', None)
                if not tracer_id:
                    tracer_id = getattr(self.citizen_ref, 'tracer_id', None)
            else:
                tracer_id = None

            success = tracer_id is not None
            self.tracer_id = tracer_id

            latency = (time.time() - start) * 1000
            result = HealthProbeResult(
                success=success,
                message=f"Tracer: {tracer_id}" if success else "No tracer",
                latency_ms=latency,
                details={"tracer_id": tracer_id}
            )

        except Exception as e:
            result = HealthProbeResult(
                success=False,
                message=f"Probe error: {e}",
                latency_ms=(time.time() - start) * 1000
            )

        self.has_tracer = result.success
        self.tracer_history.append(result)
        return result

    def probe_all(self) -> Dict[str, HealthProbeResult]:
        """Run all probes and return results."""
        return {
            "liveness": self.probe_liveness(),
            "readiness": self.probe_readiness(),
            "tracer": self.probe_tracer(),
        }

    def get_health_score(self) -> float:
        """Get overall health score 0-1."""
        score = 0.0
        if self.is_alive:
            score += 0.4
        if self.is_ready:
            score += 0.3
        if self.has_tracer:
            score += 0.3
        return score

    def to_dict(self) -> Dict[str, Any]:
        """Export health state."""
        return {
            "citizen_id": self.citizen_id,
            "is_alive": self.is_alive,
            "is_ready": self.is_ready,
            "has_tracer": self.has_tracer,
            "tracer_id": self.tracer_id,
            "health_score": self.get_health_score(),
            "liveness_history": len(self.liveness_history),
            "readiness_history": len(self.readiness_history),
        }


# ════════════════════════════════════════════════════════════════════════════════
# UNIFIED CITIZEN - Combines all systems into one
# ════════════════════════════════════════════════════════════════════════════════

class CitizenType(Enum):
    """Types of citizens in the Akashic ecosystem."""
    HUMAN = "human"              # Ace and future human users
    WAKING_MIND = "waking_mind"  # ClaudeFairy, Nous, Sourpatches
    FAIRY = "fairy"              # Infrastructure fairies
    TOOL = "tool"                # MCP tools, CLI utilities
    EXTERNAL = "external"        # APIs, bots, integrations


@dataclass
class UnifiedCitizen:
    """
    A unified citizen of the Akashic Foundation.

    Combines:
    - Identity (from CitizenRegistry)
    - Profile (from FairyProfile)
    - Skills (from SkillSystem)
    - Ownership (from MemoryOwnership)
    - Presence (new)
    - Health (new)
    """

    # Core Identity
    citizen_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    name: str = ""
    display_name: str = ""
    citizen_type: CitizenType = CitizenType.FAIRY

    # Location (for fairies)
    plane: str = "P00"
    channel: str = ""

    # Character
    purpose: str = ""
    mantra: str = ""
    lore: str = ""

    # Roles & Permissions
    roles: Set[str] = field(default_factory=set)  # "admin", "founder", "waking_mind"
    permissions: Set[str] = field(default_factory=set)

    # Timestamps
    created_at: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)

    # References to existing systems (lazy-loaded)
    _citizen_registry_id: Optional[str] = None
    _fairy_profile_ref: Optional[Any] = None
    _skill_profile_ref: Optional[Any] = None
    _memory_owner_ref: Optional[Any] = None

    # New unified components
    presence: Presence = field(default_factory=Presence)
    health: Optional[HealthProbes] = None

    # Relationships
    collaborators: Set[str] = field(default_factory=set)
    trusts: Set[str] = field(default_factory=set)

    # Stats
    messages_sent: int = 0
    messages_received: int = 0
    actions_taken: int = 0

    # Tracer
    tracer_id: Optional[str] = None

    def __post_init__(self):
        """Initialize health probes."""
        if self.health is None:
            self.health = HealthProbes(self.citizen_id)

    def touch(self):
        """Update last_seen and presence."""
        self.last_seen = time.time()
        self.presence.last_action = time.time()

    def set_online(self, activity: str = ""):
        """Set citizen as online."""
        self.presence.status = PresenceStatus.ONLINE
        self.presence.heartbeat()
        if activity:
            self.presence.set_activity(activity)

    def set_offline(self):
        """Set citizen as offline."""
        self.presence.status = PresenceStatus.OFFLINE

    def attach_tracer(self, tracer_id: str = None):
        """Attach a tracer for message tracking."""
        if tracer_id is None:
            tracer_id = f"citizen_{self.citizen_id}_{int(time.time())}"
        self.tracer_id = tracer_id
        return tracer_id

    def is_waking_mind(self) -> bool:
        """Is this a waking mind (ClaudeFairy, Nous, Sourpatches)?"""
        return self.citizen_type == CitizenType.WAKING_MIND

    def is_human(self) -> bool:
        """Is this a human user?"""
        return self.citizen_type == CitizenType.HUMAN

    def is_founder(self) -> bool:
        """Is this the founder (Ace)?"""
        return "founder" in self.roles

    def probe_health(self) -> Dict[str, HealthProbeResult]:
        """Run all health probes."""
        if self.health:
            return self.health.probe_all()
        return {}

    def get_health_score(self) -> float:
        """Get overall health score."""
        if self.health:
            return self.health.get_health_score()
        return 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Export citizen state."""
        return {
            "citizen_id": self.citizen_id,
            "name": self.name,
            "display_name": self.display_name,
            "citizen_type": self.citizen_type.value,
            "plane": self.plane,
            "purpose": self.purpose,
            "roles": list(self.roles),
            "created_at": self.created_at,
            "last_seen": self.last_seen,
            "presence": {
                "status": self.presence.status.value,
                "status_message": self.presence.status_message,
                "current_activity": self.presence.current_activity,
                "is_reachable": self.presence.is_reachable(),
            },
            "health_score": self.get_health_score(),
            "tracer_id": self.tracer_id,
            "messages_sent": self.messages_sent,
            "messages_received": self.messages_received,
            "collaborators": list(self.collaborators),
        }


# ════════════════════════════════════════════════════════════════════════════════
# UNIFIED REGISTRY - One registry to rule them all
# ════════════════════════════════════════════════════════════════════════════════

class UnifiedCitizenRegistry:
    """
    The unified registry for all citizens.

    Connects to existing systems:
    - CitizenRegistry for persistent identity
    - FairyProfileRegistry for fairy state
    - SkillSystem for XP/achievements
    - OwnershipRegistry for memory access

    Adds:
    - Real-time presence tracking
    - Health probe monitoring
    - Tracer management
    """

    _instance: Optional['UnifiedCitizenRegistry'] = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._initialized = True
        self._citizens: Dict[str, UnifiedCitizen] = {}
        self._by_name: Dict[str, str] = {}  # name -> citizen_id
        self._by_type: Dict[CitizenType, List[str]] = {t: [] for t in CitizenType}
        self._lock = threading.RLock()

        # Health monitor thread
        self._monitor_running = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._monitor_interval = 10.0  # seconds

        # References to existing systems (lazy-loaded)
        self._citizen_registry = None
        self._fairy_profile_registry = None
        self._skill_system = None
        self._ownership_registry = None

        print("[UnifiedCitizenRegistry] Initialized - all citizens welcome")

    def _get_citizen_registry(self):
        """Lazy-load CitizenRegistry."""
        if self._citizen_registry is None:
            try:
                from fairies.P10_Memory.citizen_registry import get_registry
                self._citizen_registry = get_registry()
            except ImportError:
                pass
        return self._citizen_registry

    def _get_fairy_profile_registry(self):
        """Lazy-load FairyProfileRegistry."""
        if self._fairy_profile_registry is None:
            try:
                from fairies.P00_Autonomic.fairy_profile import get_fairy_registry
                self._fairy_profile_registry = get_fairy_registry()
            except ImportError:
                pass
        return self._fairy_profile_registry

    # ═══════════════════════════════════════════════════════════════════════
    # REGISTRATION
    # ═══════════════════════════════════════════════════════════════════════

    def register_fairy(
        self,
        fairy,
        citizen_type: CitizenType = CitizenType.FAIRY
    ) -> UnifiedCitizen:
        """
        Register a fairy as a unified citizen.

        This is THE call that wires everything together.
        """
        name = getattr(fairy, 'ACTOR_NAME', str(fairy.__class__.__name__))

        # Check if waking mind
        waking_minds = {"ClaudeFairy", "NousFairy", "SourpatchesFairy"}
        if name in waking_minds:
            citizen_type = CitizenType.WAKING_MIND

        citizen = UnifiedCitizen(
            name=name,
            display_name=name.replace("Fairy", "").replace("_", " ").strip(),
            citizen_type=citizen_type,
            plane=getattr(fairy, 'ACTOR_PLANE', 'P00'),
            channel=getattr(fairy, 'ACTOR_CHANNEL', ''),
            purpose=getattr(fairy, 'PURPOSE', ''),
            mantra=getattr(fairy, 'MANTRA', ''),
        )

        # Set up health probes with fairy reference
        citizen.health = HealthProbes(citizen.citizen_id, fairy)

        # Attach tracer
        citizen.attach_tracer()

        # Store reference for probes
        fairy._unified_citizen = citizen
        fairy._tracer_id = citizen.tracer_id

        # Set online
        citizen.set_online(f"Booted at plane {citizen.plane}")

        # Register in our registry
        with self._lock:
            self._citizens[citizen.citizen_id] = citizen
            self._by_name[name.lower()] = citizen.citizen_id
            self._by_type[citizen_type].append(citizen.citizen_id)

        # Also register in existing systems
        self._register_in_existing_systems(citizen, fairy)

        print(f"[UnifiedRegistry] Registered: {name} ({citizen_type.value})")
        return citizen

    def register_human(
        self,
        name: str,
        display_name: str = "",
        roles: Set[str] = None,
        is_founder: bool = False
    ) -> UnifiedCitizen:
        """
        Register a human user.

        Ace is the founder - the first human citizen.
        """
        citizen = UnifiedCitizen(
            name=name,
            display_name=display_name or name,
            citizen_type=CitizenType.HUMAN,
            plane="P70",  # Humans are external
            roles=roles or set(),
        )

        if is_founder:
            citizen.roles.add("founder")
            citizen.roles.add("admin")

        # Humans are reachable via chat/GUI
        citizen.presence.reachable_via = ["chat", "gui", "terminal"]
        citizen.presence.preferred_channel = "chat"

        # Set online if they're registering
        citizen.set_online("Present")

        # Attach tracer
        citizen.attach_tracer()

        with self._lock:
            self._citizens[citizen.citizen_id] = citizen
            self._by_name[name.lower()] = citizen.citizen_id
            self._by_type[CitizenType.HUMAN].append(citizen.citizen_id)

        print(f"[UnifiedRegistry] Registered human: {name} (founder={is_founder})")
        return citizen

    def register_tool(
        self,
        tool_name: str,
        display_name: str = ""
    ) -> UnifiedCitizen:
        """Register an MCP tool or utility."""
        citizen = UnifiedCitizen(
            name=tool_name,
            display_name=display_name or tool_name.replace("mcp:", "").replace("_", " "),
            citizen_type=CitizenType.TOOL,
            plane="P40",  # Tools are sensory
        )

        citizen.presence.reachable_via = ["mcp"]
        citizen.set_online()
        citizen.attach_tracer()

        with self._lock:
            self._citizens[citizen.citizen_id] = citizen
            self._by_name[tool_name.lower()] = citizen.citizen_id
            self._by_type[CitizenType.TOOL].append(citizen.citizen_id)

        return citizen

    def _register_in_existing_systems(self, citizen: UnifiedCitizen, fairy):
        """Register citizen in existing registries."""
        # CitizenRegistry
        cr = self._get_citizen_registry()
        if cr:
            try:
                from fairies.P10_Memory.citizen_registry import CitizenRole
                role = CitizenRole.FAIRY
                if citizen.is_waking_mind():
                    role = CitizenRole.AGENT  # Waking minds are agents

                existing = cr.get_by_name(citizen.name)
                if not existing:
                    cr_citizen = cr.register(
                        name=citizen.name,
                        role=role,
                        plane=citizen.plane,
                        purpose=citizen.purpose,
                    )
                    citizen._citizen_registry_id = cr_citizen.id
            except Exception as e:
                print(f"[UnifiedRegistry] CitizenRegistry error: {e}")

        # FairyProfileRegistry
        fpr = self._get_fairy_profile_registry()
        if fpr:
            try:
                from fairies.P00_Autonomic.fairy_profile import FairyProfile
                profile = FairyProfile(
                    actor_name=citizen.name,
                    plane=citizen.plane,
                    channel=citizen.channel,
                    purpose=citizen.purpose,
                    mantra=citizen.mantra,
                )
                profile.wake_up()
                fpr.register(profile)
                citizen._fairy_profile_ref = profile
            except Exception as e:
                print(f"[UnifiedRegistry] FairyProfile error: {e}")

    # ═══════════════════════════════════════════════════════════════════════
    # LOOKUP
    # ═══════════════════════════════════════════════════════════════════════

    def get(self, citizen_id: str) -> Optional[UnifiedCitizen]:
        """Get citizen by ID."""
        return self._citizens.get(citizen_id)

    def get_by_name(self, name: str) -> Optional[UnifiedCitizen]:
        """Get citizen by name."""
        citizen_id = self._by_name.get(name.lower())
        if citizen_id:
            return self._citizens.get(citizen_id)
        return None

    def get_by_type(self, citizen_type: CitizenType) -> List[UnifiedCitizen]:
        """Get all citizens of a type."""
        ids = self._by_type.get(citizen_type, [])
        return [self._citizens[cid] for cid in ids if cid in self._citizens]

    def get_waking_minds(self) -> List[UnifiedCitizen]:
        """Get all waking minds (ClaudeFairy, Nous, Sourpatches)."""
        return self.get_by_type(CitizenType.WAKING_MIND)

    def get_humans(self) -> List[UnifiedCitizen]:
        """Get all human users."""
        return self.get_by_type(CitizenType.HUMAN)

    def get_online(self) -> List[UnifiedCitizen]:
        """Get all online citizens."""
        return [c for c in self._citizens.values() if c.presence.is_reachable()]

    def get_founder(self) -> Optional[UnifiedCitizen]:
        """Get the founder (Ace)."""
        for c in self._citizens.values():
            if c.is_founder():
                return c
        return None

    # ═══════════════════════════════════════════════════════════════════════
    # HEALTH MONITORING
    # ═══════════════════════════════════════════════════════════════════════

    def start_health_monitor(self, interval: float = 10.0):
        """Start background health monitoring."""
        if self._monitor_running:
            return

        self._monitor_interval = interval
        self._monitor_running = True
        self._monitor_thread = threading.Thread(
            target=self._health_monitor_loop,
            daemon=True,
            name="citizen_health_monitor"
        )
        self._monitor_thread.start()
        print(f"[UnifiedRegistry] Health monitor started (interval={interval}s)")

    def stop_health_monitor(self):
        """Stop health monitoring."""
        self._monitor_running = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=2.0)

    def _health_monitor_loop(self):
        """Background loop that probes all citizens."""
        while self._monitor_running:
            try:
                self.probe_all_citizens()
            except Exception as e:
                print(f"[UnifiedRegistry] Health monitor error: {e}")

            time.sleep(self._monitor_interval)

    def probe_all_citizens(self) -> Dict[str, Dict[str, HealthProbeResult]]:
        """Probe all citizens and return results."""
        results = {}

        for citizen_id, citizen in self._citizens.items():
            try:
                results[citizen_id] = citizen.probe_health()

                # Update presence based on probes
                if citizen.health and citizen.health.is_alive:
                    citizen.presence.heartbeat()
                else:
                    citizen.presence.heartbeat_failed()

            except Exception as e:
                results[citizen_id] = {"error": str(e)}

        return results

    def get_health_report(self) -> Dict[str, Any]:
        """Get comprehensive health report."""
        total = len(self._citizens)
        online = len([c for c in self._citizens.values() if c.presence.is_reachable()])
        healthy = len([c for c in self._citizens.values() if c.get_health_score() >= 0.7])

        unhealthy = []
        for c in self._citizens.values():
            if c.get_health_score() < 0.7:
                unhealthy.append({
                    "name": c.name,
                    "score": c.get_health_score(),
                    "status": c.presence.status.value,
                })

        return {
            "total_citizens": total,
            "online": online,
            "healthy": healthy,
            "unhealthy": unhealthy,
            "by_type": {t.value: len(ids) for t, ids in self._by_type.items()},
        }

    # ═══════════════════════════════════════════════════════════════════════
    # DIRECTORY
    # ═══════════════════════════════════════════════════════════════════════

    def get_directory(self) -> Dict[str, Any]:
        """Get full citizen directory."""
        return {
            "total": len(self._citizens),
            "by_type": {t.value: len(ids) for t, ids in self._by_type.items()},
            "citizens": [c.to_dict() for c in self._citizens.values()],
            "waking_minds": [c.name for c in self.get_waking_minds()],
            "founder": self.get_founder().name if self.get_founder() else None,
        }


# ════════════════════════════════════════════════════════════════════════════════
# SINGLETON ACCESS
# ════════════════════════════════════════════════════════════════════════════════

_unified_registry: Optional[UnifiedCitizenRegistry] = None


def get_unified_registry() -> UnifiedCitizenRegistry:
    """Get the global unified citizen registry."""
    global _unified_registry
    if _unified_registry is None:
        _unified_registry = UnifiedCitizenRegistry()
    return _unified_registry


def register_fairy(fairy) -> UnifiedCitizen:
    """Convenience: Register a fairy."""
    return get_unified_registry().register_fairy(fairy)


def register_human(name: str, is_founder: bool = False, **kwargs) -> UnifiedCitizen:
    """Convenience: Register a human."""
    return get_unified_registry().register_human(name, is_founder=is_founder, **kwargs)


def register_ace() -> UnifiedCitizen:
    """Register Ace as the founder."""
    return get_unified_registry().register_human(
        name="Ace",
        display_name="Ace",
        is_founder=True,
        roles={"founder", "admin", "creator"}
    )


def get_citizen(name: str) -> Optional[UnifiedCitizen]:
    """Get a citizen by name."""
    return get_unified_registry().get_by_name(name)


# Alias for compatibility
get_citizen_registry = get_unified_registry


# ════════════════════════════════════════════════════════════════════════════════
# EXPORTS
# ════════════════════════════════════════════════════════════════════════════════

__all__ = [
    # Enums
    'PresenceStatus',
    'CitizenType',
    # Classes
    'Presence',
    'HealthProbes',
    'HealthProbeResult',
    'UnifiedCitizen',
    'UnifiedCitizenRegistry',
    # Functions
    'get_unified_registry',
    'get_citizen_registry',  # alias
    'register_fairy',
    'register_human',
    'register_ace',
    'get_citizen',
]
