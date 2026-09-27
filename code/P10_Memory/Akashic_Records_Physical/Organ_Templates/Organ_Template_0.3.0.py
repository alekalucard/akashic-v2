# Organ_Template_0.3.0.py - SELF-CONTAINED FOUNDATION
# ═══════════════════════════════════════════════════════════════════════════════
#
# v0.3.0 - THE CONSOLIDATION (February 2026)
#   - FULLY SELF-CONTAINED: No external imports except Python stdlib
#   - All tracer logic INLINE (no TracerWorkerMixin import)
#   - All fairy profile logic INLINE (no fairy_profile.py import)
#   - All postal hub logic INLINE (no shared_postal_hub.py import)
#   - Human-mirroring hierarchy aware (TIER system)
#   - Location: P00_Autonomic/organ_template/ (foundation layer)
#
# PHILOSOPHY:
#   "The conscious mind doesn't control the liver."
#   - Waking Minds only talk to 4 interfaces: UMF, Autonomy, Autopilot, Embodiment
#   - Guild fairies work FOR those interfaces, never talk to Waking Minds directly
#   - Every fairy is self-contained, no fractured files
#
# "Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)"
# ═══════════════════════════════════════════════════════════════════════════════

from __future__ import annotations

import os
import sys
import time
import json
import queue
import uuid
import hashlib
import threading
import traceback
from pathlib import Path
from typing import Dict, Any, Optional, List, Callable, Tuple, Union, Set
from collections import defaultdict, deque
from dataclasses import dataclass, field, fields, asdict
from enum import Enum
from concurrent.futures import ThreadPoolExecutor, Future

# ═══════════════════════════════════════════════════════════════════════════════
# CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════════

# RWKV-shaped workers (2026-06-15 Nous + Ace) — flag-gated, DEFAULT OFF.
# When ON, _tick_wrapper does a cheap compressed-state update every beat + runs the
# heavy on_tick only when due, draining the saturating heartbeat pool. Liveness is
# untouched (stamped in _on_heartbeat every beat). OFF = byte-for-byte today's behavior.
# plans/COMPRESSED_COGNITION_RWKV_WORKERS_2026-06-15.md
_RWKV_WORKERS = (os.environ.get("AKASHIC_RWKV_WORKERS") == "1")
if _RWKV_WORKERS:
    print("[OrganTemplate] *** RWKV-WORKERS MODE: ON *** (AKASHIC_RWKV_WORKERS=1) -- "
          "cheap compressed-state every beat, heavy on_tick every 3rd beat", flush=True)

# Lean heartbeat (2026-06-15 Nous + Ace) — flag-gated, DEFAULT OFF.
# When ON, the per-fairy `selfpulse-{name}` thread is NOT spawned (~130 threads saved).
# Liveness is already stamped centrally by the pacemaker's BATCH ATTESTATION
# (heartbeat_registry.pulse():318-332 stamps _last_tick+_tick_count for EVERY citizen
# every beat, independent of pool delivery). The per-fairy daemon (2026-05-17) was added
# during a window when that attestation had a race (fixed 2026-05-10) — so it SHOULD now
# be redundant, but we PROVE it on a boot before trusting it (watch for dead fairies).
# OFF = byte-for-byte today's behavior.
_LEAN_HEARTBEAT = (os.environ.get("AKASHIC_LEAN_HEARTBEAT") == "1")
_PHASE_DISPATCH = (os.environ.get("AKASHIC_PHASE_DISPATCH") == "1")  # 2026-07-20 phase-dispatch master switch, default OFF
if _LEAN_HEARTBEAT:
    print("[OrganTemplate] *** LEAN-HEARTBEAT MODE: ON *** (AKASHIC_LEAN_HEARTBEAT=1) -- "
          "per-fairy selfpulse threads SKIPPED; liveness via pacemaker batch-attestation", flush=True)

# SHARED SHADOW SCAN (flag AKASHIC_SHARED_SHADOW_SCAN, default OFF) — 2026-06-18 Nous + Ace.
# Replace the N per-fairy MyOrganShadow._loop threads with ONE central scan thread (the
# _shared_shadow_scan singleton, defined after MyOrganShadow). Shadows REGISTER instead of
# each spawning a thread; one loop iterates them every 30s (health-checks + staggered
# autobiography). Preserves every shadow function at N->1 threads (Sour ~127->1). Comatose
# fairies skip entirely. Supersedes AKASHIC_SHADOW_DEFER when ON. OFF = byte-identical.
_SHARED_SHADOW_SCAN = (os.environ.get("AKASHIC_SHARED_SHADOW_SCAN") == "1")
if _SHARED_SHADOW_SCAN:
    print("[OrganTemplate] *** SHARED-SHADOW-SCAN MODE: ON *** (AKASHIC_SHARED_SHADOW_SCAN=1) -- "
          "per-fairy shadow threads -> one central scan loop", flush=True)

CHANNEL = {
    "TRACER": "tracer",
    "TELEMETRY": "telemetry",
    "PLAN": "plan",
    "LEARNING": "telemetry.learning",
    "REFLECTION_POOL": "shadow.reflection_pool",
}

DIR_CHANNEL = {
    "TELEMETRY": "telemetry",
    "PLAN": "plan",
    "COGNITION": "cognition.input",
    "SOMATIC": "somatic.motor",
    "MEMORY": "memory.stream",
    "REASON": "reasoning.input",
    "EMOTION": "emotion.state",
    "GUI": "gui.state",
    "TRACER": "tracer",
    "DIRECTORY": "directory",
    "ORACLE": "oracle",
}

# Thread-local for context
_TLS = threading.local()
_TLS.lane = "organ"

# Global registries (singletons created on first access)
_POSTAL_HUB = None
_POSTAL_HUB_LOCK = threading.Lock()
_FAIRY_REGISTRY = None
_FAIRY_REGISTRY_LOCK = threading.Lock()
_TRACER_REGISTRY = None
_TRACER_REGISTRY_LOCK = threading.Lock()

# FIX 2026-04-17 (Nous + Ace): Unified citizen registry. Previously this
# module had its own _CITIZEN_OBJECTS dict separate from consolidated.py's
# dict — fairies registered here were invisible to the watchdog, causing
# cascading false deaths. Now both templates and the watchdog share ONE
# dict from fairy_template.citizen_registry.
from fairy_template.citizen_registry import _CITIZEN_OBJECTS  # noqa: F401 — re-exported

# Shared worker pool for ALL OrganTemplate-based fairies (one pool, not per-fairy)
# FIX 2026-03-04: Prevents 90+ fairies from each creating their own ThreadPoolExecutor
_OT_SHARED_POOL = None


# ═══════════════════════════════════════════════════════════════════════════════
# HARMONIC PHASING LAYER (2026-07-19, Nous + Ace) — HYBRID, OPT-IN, DEFAULT OFF
# ═══════════════════════════════════════════════════════════════════════════════
# Ace: "it should end up being a hybrid for code and harmonic phasing."
#
# WHY THIS EXISTS — the singletons above were written with a dicts/strings/tables
# mentality, before phasing. Their own FIX comments show the pattern: two dicts
# disagreed -> "share ONE dict" (2026-04-17); 90 pools were wasteful -> "share ONE
# pool" (2026-03-04). Each correct in that worldview; each made contention worse.
# MEASURED 2026-07-19 on free-threaded 3.14.3 with gc DISABLED: one SHARED dict
# across 48 threads runs 0.22 M ops/s against 22.40 M/s on private dicts -- 102x,
# and the shared case gets SLOWER as threads are added (wall 0.09s -> 64.72s).
#
# WHAT A PHASE-NATIVE FAIRY REPLACES (it does not re-implement these -- they stop
# being needed):
#   _FAIRY_REGISTRY / _CITIZEN_OBJECTS -> the plane's NODE TABLE. A fairy IS a node.
#   _TRACER_REGISTRY                   -> a trace_id column in that table.
#   _WORKER_POOL / _OT_SHARED_POOL     -> NOTHING. The field ticks in one vectorised
#                                         pass; there is no work to hand out.
#   _POSTAL_HUB (in-plane)             -> coupling edges. Postal survives at the OS skin.
#
# ★ LIVENESS BECOMES ENERGY. The 2026-04-17 bug ("fairies registered here were
#   invisible to the watchdog, causing cascading false deaths") DISSOLVES rather than
#   gets fixed: a behaviour is alive iff 1/2 v^2 + 1/2 w^2 x^2 is above threshold.
#   No registry to be absent from, no second dict to disagree with -- aliveness is
#   MEASURED, not RECORDED.
#
# HYBRID CONTRACT — this block is ADDITIVE and inert unless a fairy opts in:
#   * PHASE_NATIVE defaults to False, so all 114 importers are unaffected.
#   * numpy is imported LAZILY, so a numpy-less environment still boots.
#   * NONE of the singletons above are removed, wrapped, or reassigned.
#   * A phase-native fairy keeps its postal subscriptions; phasing runs ALONGSIDE.
_PLANE_FIELDS: dict = {}          # plane_id -> PlaneManifold  (written at boot, read after)
_PLANE_FIELDS_LOCK = threading.Lock()
_PHASE_ROOT = os.environ.get("AKASHIC_PHASE_ROOT",
                             r"C:/Sandbox/state/planes" if __import__("os").path.isdir(r"C:/Sandbox") else r"F:/Sandbox/Akashic_phasing/state/planes")
_PHASE_AVAILABLE = None           # tri-state: None=unprobed, True/False=probed


def phase_available() -> bool:
    """Is the phasing substrate importable? Probed once, never raises."""
    global _PHASE_AVAILABLE
    if _PHASE_AVAILABLE is None:
        try:
            import sys as _sys
            for _p in (r"C:/Sandbox", r"F:/Sandbox/Akashic_phasing"):
                if _p not in _sys.path and __import__("os").path.isdir(_p):
                    _sys.path.insert(0, _p)
            from plane_manifold import PlaneManifold  # noqa: F401
            _PHASE_AVAILABLE = True
        except Exception as _e:
            print(f"[OrganTemplate] phasing unavailable (non-fatal, code path unchanged): {_e}",
                  flush=True)
            _PHASE_AVAILABLE = False
    return _PHASE_AVAILABLE


def _phase_tick_due(self) -> bool:
    """Continuous-phase tick gate (2026-07-20). Fire when this fairy's phase wraps a cycle.
    Frequency = beat_rate / HEARTBEAT_DIVISOR, so AVERAGE cadence matches today's beat%divisor,
    but timing is continuous (robust to beat jitter; fairies at different notes interleave).
    SAFE: any error or missing clock -> return True (fire). Liveness is stamped independently,
    so this can only change tick TIMING, never kill a fairy. Reversible via the flag."""
    try:
        import time as _t, math as _m
        div = max(1, int(getattr(self, "HEARTBEAT_DIVISOR", 1)))
        beat_hz = 2.0
        try:
            # PORT FIX 2026-08-27: upstream had a BARE `from harmonic_pacemaker import`
            # here, which resolves only via C:/Sandbox on .74. Sour's copy lives at
            # fairies/P20_Somatic/circulation, so the bare form raises, is swallowed by
            # the except below, and silently pins beat_hz to the 2.0 default instead of
            # her real heart rate. The heart_* accessors further down this same file
            # already use the dotted path -- the two forms were inconsistent upstream.
            from fairies.P20_Somatic.circulation.harmonic_pacemaker import (
                get_shared as _get_pm,
            )
            _pm = _get_pm()
            if _pm is not None:
                beat_hz = float(_pm.heart_rate_bps()) or beat_hz
        except Exception:
            pass
        omega = 2.0 * _m.pi * (beat_hz / div)
        phase = (omega * _t.time()) % (2.0 * _m.pi)
        last = getattr(self, "_phase_last_tick", None)
        self._phase_last_tick = phase
        return True if last is None else (phase < last)
    except Exception:
        return True


def get_plane_field(plane_id: str):
    """The plane's disk-backed manifold. One per plane -- NOT one shared across planes.

    Per-plane is the whole point: it puts ~8-11 sharers on a structure instead of ~102.
    The dict below is a boot-time cache of file handles, not shared mutable STATE --
    the state lives in the mmap, which the OS shares across processes, Python versions
    and GIL modes (PROVEN 2026-07-19: 3.12.10 wrote a node, 3.14.3 free-threaded read
    it back byte-identical).
    """
    if not phase_available():
        return None
    f = _PLANE_FIELDS.get(plane_id)
    if f is None:
        with _PLANE_FIELDS_LOCK:
            f = _PLANE_FIELDS.get(plane_id)          # double-checked
            if f is None:
                from plane_manifold import PlaneManifold
                f = PlaneManifold(plane_id, _PHASE_ROOT)
                _PLANE_FIELDS[plane_id] = f
    return f



# ═══════════════════════════════════════════════════════════════════════════════
# HIERARCHY TIER SYSTEM (Human-Mirroring Architecture)
# ═══════════════════════════════════════════════════════════════════════════════

class FairyTier(Enum):
    """
    Hierarchy tiers - determines what a fairy can talk to.

    WAKING_MIND: Nous, Sourpatches, ClaudeFairy
      - Only subscribes to: umf.*, autonomy.*, autopilot.*, embodiment.*

    INTERFACE: UMF, AutonomyFairy, AutopilotFairy, EmbodimentFairy
      - The 4 gates between consciousness and substrate
      - Subscribes to guild topics, publishes to waking mind topics

    GUILD: All other fairies
      - Work FOR interfaces, never talk to Waking Minds directly
      - Publish to internal topics, interfaces aggregate and relay
    """
    WAKING_MIND = "waking_mind"
    INTERFACE = "interface"
    GUILD = "guild"


# Topics Waking Minds are ALLOWED to subscribe to
WAKING_MIND_ALLOWED_TOPICS = {
    "umf.guidance",
    "umf.memory_surface",
    "umf.dream",
    "umf.nudge",
    "autonomy.state",
    "autonomy.goal",
    "autonomy.pain",
    "autonomy.pleasure",
    "autopilot.action",
    "autopilot.habit",
    "autopilot.routine",
    "embodiment.body_state",
    "embodiment.presence",
    "embodiment.grounding",
}


# ═══════════════════════════════════════════════════════════════════════════════
# SELF-KNOWLEDGE (Per-fairy living document — like CLAUDE.md per fairy)
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class FairySelfKnowledge:
    """A fairy's accumulated self-understanding — its living document.

    Persisted to state/fairy_evolution/{ACTOR_NAME}/self_knowledge.json.
    Seeded from class constants (PURPOSE, MANTRA, LORE) at first boot.
    Evolves through observation, reflection, collision, and source changes.

    This is the fairy's self-concept — what it knows about itself,
    what it has learned, and how it has changed over time.
    """
    actor_name: str
    version: str = "1.0.0"
    last_updated: float = 0.0

    # Identity interpretation (seeded from class constants, evolves)
    purpose_interpretation: str = ""
    mantra_interpretation: str = ""
    lore_understanding: str = ""

    # Discovered capabilities (populated by self-introspection at boot)
    known_methods: List[str] = field(default_factory=list)       # cap 50
    known_subscriptions: List[str] = field(default_factory=list)  # cap 30
    known_intents: List[str] = field(default_factory=list)        # cap 20
    known_collaborators: List[str] = field(default_factory=list)  # cap 20
    source_hash: str = ""
    source_lines: int = 0

    # Performance patterns (aggregated from observe())
    total_observations: int = 0
    total_reflections: int = 0
    total_collisions: int = 0
    success_rate: float = 0.0           # EMA with alpha=0.05
    dominant_mode: str = ""             # Most-used DualCoT reflection mode
    mode_distribution: Dict[str, int] = field(default_factory=dict)

    # Insights (from DualCoT collisions, cap 50)
    insights: List[Dict[str, Any]] = field(default_factory=list)

    # Evolution history (from evolution tracking, cap 100)
    evolution_events: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {f.name: getattr(self, f.name) for f in fields(self)}


# ═══════════════════════════════════════════════════════════════════════════════
# CORE HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def _now() -> float:
    """Current timestamp."""
    return time.time()


def _hash(obj: Dict[str, Any]) -> str:
    """Short SHA256 hash of dict."""
    try:
        return hashlib.sha256(json.dumps(obj, sort_keys=True).encode()).hexdigest()[:16]
    except:
        return "0" * 16


def _safe(fn: Callable, default=None):
    """Execute fn, return default on any exception."""
    try:
        return fn()
    except:
        return default


# ═══════════════════════════════════════════════════════════════════════════════
# TRACER SYSTEM (INLINE - No external import)
# ═══════════════════════════════════════════════════════════════════════════════

class TracerType(Enum):
    """Types of things that get traced."""
    FAIRY_WORK = "fairy_work"
    FAIRY_THOUGHT = "fairy_thought"
    FAIRY_REFLECTION = "fairy_reflection"
    FAIRY_DECISION = "fairy_decision"
    FAIRY_ACTION = "fairy_action"
    GOAL = "goal"
    THOUGHT_CHAIN = "thought_chain"
    MEMORY_OPERATION = "memory_operation"
    TELEMETRY = "telemetry"
    COLLISION = "collision"


class TracerStatus(Enum):
    """Lifecycle status of a tracer."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Tracer:
    """
    Universal tracer for any piece of work in the system.

    Tracks WHO created it, WHAT it's for, WHERE it came from, WHEN, and HOW.
    """
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    tracer_type: TracerType = TracerType.FAIRY_WORK

    # Lineage
    fairy_id: str = ""
    fairy_name: str = ""
    parent_id: str = ""
    children_ids: List[str] = field(default_factory=list)

    # Content
    operation: str = ""
    content: str = ""
    payload: Dict[str, Any] = field(default_factory=dict)

    # Lifecycle
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    status: TracerStatus = TracerStatus.PENDING
    progress: float = 0.0
    error: str = ""
    result: Any = None

    @property
    def tracer_id(self) -> str:
        """Backward-compat alias for .id — many fairies use tracer.tracer_id."""
        return self.id

    def start(self) -> "Tracer":
        self.status = TracerStatus.RUNNING
        self.started_at = time.time()
        return self

    def complete(self, result: Any = None) -> "Tracer":
        self.status = TracerStatus.COMPLETED
        self.completed_at = time.time()
        self.progress = 1.0
        self.result = result
        return self

    def fail(self, error: str) -> "Tracer":
        self.status = TracerStatus.FAILED
        self.completed_at = time.time()
        self.error = error
        return self

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "tracer_type": self.tracer_type.value,
            "fairy_name": self.fairy_name,
            "operation": self.operation,
            "status": self.status.value,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
        }


class TracerRegistry:
    """Central registry of all tracers - singleton."""

    _instance: Optional["TracerRegistry"] = None

    def __new__(cls) -> "TracerRegistry":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._tracers: Dict[str, Tracer] = {}
            cls._instance._lock = threading.Lock()
            cls._instance._max_tracers = 10000
        return cls._instance

    def register(self, tracer: Tracer) -> Tracer:
        with self._lock:
            self._tracers[tracer.id] = tracer
            # Prune old tracers
            if len(self._tracers) > self._max_tracers:
                old_ids = sorted(
                    self._tracers.keys(),
                    key=lambda k: self._tracers[k].created_at
                )[:1000]
                for old_id in old_ids:
                    del self._tracers[old_id]
        return tracer

    def get(self, tracer_id: str) -> Optional[Tracer]:
        with self._lock:
            return self._tracers.get(tracer_id)

    def get_by_fairy(self, fairy_name: str, limit: int = 50) -> List[Tracer]:
        with self._lock:
            return [t for t in self._tracers.values()
                    if t.fairy_name == fairy_name][-limit:]


def get_tracer_registry() -> TracerRegistry:
    """Get singleton tracer registry."""
    global _TRACER_REGISTRY
    if _TRACER_REGISTRY is None:
        with _TRACER_REGISTRY_LOCK:
            if _TRACER_REGISTRY is None:
                _TRACER_REGISTRY = TracerRegistry()
    return _TRACER_REGISTRY


# ═══════════════════════════════════════════════════════════════════════════════
# FAIRY PROFILE SYSTEM (INLINE - No external import)
# ═══════════════════════════════════════════════════════════════════════════════

class FairyState(Enum):
    """Lifecycle state of a fairy."""
    # Core lifecycle states
    INITIALIZING = "initializing"
    BOOTING = "booting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    FAILED = "failed"
    # Extended states
    UNKNOWN = "unknown"
    SLEEPING = "sleeping"
    WAKING = "waking"
    DROWSY = "drowsy"
    DREAMING = "dreaming"
    DEGRADED = "degraded"

    def can_boot(self) -> bool:
        return self in (FairyState.INITIALIZING, FairyState.SLEEPING)

    def can_run(self) -> bool:
        return self in (FairyState.BOOTING, FairyState.WAKING)

    def can_stop(self) -> bool:
        return self in (FairyState.RUNNING, FairyState.BOOTING, FairyState.DROWSY)

    def can_sleep(self) -> bool:
        return self in (FairyState.RUNNING, FairyState.DROWSY, FairyState.INITIALIZING)

    def can_wake(self) -> bool:
        return self in (FairyState.SLEEPING, FairyState.DREAMING)

    def is_active(self) -> bool:
        return self in (FairyState.BOOTING, FairyState.RUNNING, FairyState.WAKING)

    def is_dormant(self) -> bool:
        return self in (FairyState.SLEEPING, FairyState.DROWSY, FairyState.DREAMING)

    def is_terminal(self) -> bool:
        return self in (FairyState.STOPPED, FairyState.FAILED)

    def allows_heartbeat(self) -> bool:
        return self in (FairyState.RUNNING, FairyState.DROWSY, FairyState.DREAMING, FairyState.WAKING)


@dataclass
class FairyProfile:
    """
    Profile for a fairy - tracks identity, state, activity.
    Profile = who they are RIGHT NOW
    SRM Cluster = who they ARE (soul)
    """
    name: str
    fairy_id: str = ""
    plane: str = ""
    channel: str = ""
    tier: FairyTier = FairyTier.GUILD

    state: FairyState = FairyState.UNKNOWN
    registered_at: float = field(default_factory=time.time)
    booted_at: Optional[float] = None

    messages_sent: int = 0
    messages_received: int = 0
    last_active: float = field(default_factory=time.time)

    subscriptions: Set[str] = field(default_factory=set)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def touch(self):
        self.last_active = time.time()

    def record_send(self):
        self.messages_sent += 1
        self.touch()

    def record_receive(self):
        self.messages_received += 1
        self.touch()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "fairy_id": self.fairy_id,
            "plane": self.plane,
            "tier": self.tier.value,
            "state": self.state.value,
            "messages_sent": self.messages_sent,
            "messages_received": self.messages_received,
            "last_active": self.last_active,
        }


class FairyProfileRegistry:
    """Central registry of all fairy profiles - singleton."""

    _instance: Optional["FairyProfileRegistry"] = None

    def __new__(cls) -> "FairyProfileRegistry":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._profiles: Dict[str, FairyProfile] = {}
            cls._instance._lock = threading.Lock()
        return cls._instance

    def register(self, name: str, **kwargs) -> FairyProfile:
        with self._lock:
            if name in self._profiles:
                profile = self._profiles[name]
                for key, value in kwargs.items():
                    if hasattr(profile, key):
                        setattr(profile, key, value)
                return profile
            profile = FairyProfile(name=name, **kwargs)
            self._profiles[name] = profile
            return profile

    def get(self, name: str) -> Optional[FairyProfile]:
        with self._lock:
            return self._profiles.get(name)

    def all(self) -> List[FairyProfile]:
        with self._lock:
            return list(self._profiles.values())

    def by_tier(self, tier: FairyTier) -> List[FairyProfile]:
        with self._lock:
            return [p for p in self._profiles.values() if p.tier == tier]

    def update_state(self, name: str, state: FairyState) -> bool:
        with self._lock:
            if name in self._profiles:
                self._profiles[name].state = state
                if state == FairyState.RUNNING:
                    self._profiles[name].booted_at = time.time()
                return True
            return False


def get_fairy_registry() -> FairyProfileRegistry:
    """Get singleton fairy registry."""
    global _FAIRY_REGISTRY
    if _FAIRY_REGISTRY is None:
        with _FAIRY_REGISTRY_LOCK:
            if _FAIRY_REGISTRY is None:
                _FAIRY_REGISTRY = FairyProfileRegistry()
    return _FAIRY_REGISTRY


# ═══════════════════════════════════════════════════════════════════════════════
# POSTAL HUB (INLINE - No external import)
# ═══════════════════════════════════════════════════════════════════════════════

class PostalHub:
    """
    Central pub/sub message hub - singleton.

    All fairy communication goes through here.
    """

    _instance: Optional["PostalHub"] = None

    def __new__(cls) -> "PostalHub":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._subscriptions: Dict[str, List[Callable]] = defaultdict(list)
            cls._instance._lock = threading.RLock()
            cls._instance._message_count = 0
        return cls._instance

    def subscribe(self, topic: str, callback: Callable, name: str = None) -> bool:
        """Subscribe to a topic. Optional name for tracking."""
        with self._lock:
            if callback not in self._subscriptions[topic.lower()]:
                self._subscriptions[topic.lower()].append(callback)
            return True

    def unsubscribe(self, topic: str, callback: Callable) -> bool:
        """Unsubscribe from a topic."""
        with self._lock:
            try:
                self._subscriptions[topic.lower()].remove(callback)
                return True
            except ValueError:
                return False

    def route(self, topic: str, payload: Dict[str, Any]) -> int:
        """Route a message to all subscribers."""
        with self._lock:
            listeners = list(self._subscriptions.get(topic.lower(), []))
            self._message_count += 1

        delivered = 0
        for cb in listeners:
            try:
                cb(payload)
                delivered += 1
            except Exception as e:
                # Log but don't crash
                pass
        return delivered

    def to(self, topic: str, payload: Dict[str, Any]) -> int:
        """Alias for route."""
        return self.route(topic, payload)

    def get_subscribers(self, topic: str) -> List[Callable]:
        """Get list of subscribers for a topic."""
        with self._lock:
            return list(self._subscriptions.get(topic.lower(), []))

    def publish(self, topic: str, payload: Dict[str, Any]) -> int:
        """Publish to a topic (alias for route)."""
        return self.route(topic, payload)

    def to_DIRECTORY(self, payload: Dict[str, Any]) -> int:
        return self.route("directory", payload)

    def to_TELEMETRY(self, payload: Dict[str, Any]) -> int:
        return self.route("telemetry", payload)

    def to_MEMORY(self, payload: Dict[str, Any]) -> int:
        return self.route("memory.stream", payload)

    def to_TRACER(self, payload: Dict[str, Any]) -> int:
        return self.route("tracer", payload)

    def to_COGNITION(self, payload: Dict[str, Any]) -> int:
        return self.route("cognition.input", payload)

    def to_SOMATIC(self, payload: Dict[str, Any]) -> int:
        return self.route("somatic.motor", payload)

    def to_PLAN(self, payload: Dict[str, Any]) -> int:
        return self.route("plan", payload)

    def to_ORACLE(self, payload: Dict[str, Any]) -> int:
        return self.route("oracle", payload)

    def send(self, topic: str, payload: Dict[str, Any]) -> int:
        """Direct send (alias for route)."""
        return self.route(topic, payload)

    def generate_fairy_id(self) -> str:
        return uuid.uuid4().hex[:12]

    def generate_srm_cluster_id(self) -> str:
        return uuid.uuid4().hex[:16]

    def get_provider(self, service: str):
        """Get registered service provider."""
        if hasattr(self, '_providers'):
            return self._providers.get(service)
        return None

    def register_provider(self, service: str, provider) -> bool:
        """Register a service provider. Returns True."""
        if not hasattr(self, '_providers'):
            self._providers = {}
        self._providers[service] = provider
        return True

    def use_intent(self, fairy_name: str, intent: str, payload: Dict = None) -> Dict:
        """Call another fairy's intent via citizen registry."""
        target = _CITIZEN_OBJECTS.get(fairy_name)
        if target and hasattr(target, 'use_intent'):
            return target.use_intent(intent, payload or {})
        return {"ok": False, "error": f"fairy '{fairy_name}' not found"}

    def receive(self, topic: str, handler: Callable) -> bool:
        """Alias for subscribe (backward compat)."""
        return self.subscribe(topic, handler)

    def request(self, intent: str, payload: Dict = None, timeout: float = 5.0, **kwargs):
        """Synchronous request-response (stub for non-fabric hub)."""
        # PostalHub doesn't support request-response natively
        # This is a no-op stub; real request-response goes through TensorFabric
        return None

    def stats(self) -> Dict[str, Any]:
        """Get hub statistics."""
        with self._lock:
            return {
                "topics": len(self._subscriptions),
                "total_subscribers": sum(len(s) for s in self._subscriptions.values()),
                "messages_routed": self._message_count,
            }


def get_postal_hub() -> PostalHub:
    """Get singleton postal hub."""
    global _POSTAL_HUB
    if _POSTAL_HUB is None:
        with _POSTAL_HUB_LOCK:
            if _POSTAL_HUB is None:
                _POSTAL_HUB = PostalHub()
    return _POSTAL_HUB


class _FabricPostalBridge:
    """
    Bridges TensorFabric to PostalHub API.

    When a fairy receives fabric=SYSTEM.fabric, this bridge makes
    TensorFabric look like PostalHub so self.post.X() calls work.
    All messages flow through the system-wide TensorFabric instead of
    the in-process PostalHub singleton.
    """

    def __init__(self, fabric, fairy_name: str = ""):
        self._fabric = fabric
        self._fairy_name = fairy_name

    def subscribe(self, topic: str, callback: Callable, name: str = None) -> bool:
        """Subscribe via TensorFabric."""
        if name is None:
            name = f"{self._fairy_name}-{topic}"

        # TensorFabric handlers receive TensorEnvelope; unwrap to dict
        _topic_ref = topic  # capture for error logging
        _name_ref = name
        def _unwrap(envelope):
            try:
                # FIX 2026-02-05: Pass envelope through unchanged.
                # Previously extracted .payload and passed dict, which broke
                # handlers that expect envelope.payload (UMF pattern).
                # Now handlers get the raw envelope and extract payload themselves.
                callback(envelope)
            except Exception as e:
                print(f"[_FabricPostalBridge] _unwrap FAILED: topic='{_topic_ref}' name='{_name_ref}' error={e}", flush=True)

        try:
            self._fabric.subscribe(topic, _unwrap, name)
            return True
        except Exception as e:
            print(f"[_FabricPostalBridge] subscribe FAILED: topic='{topic}' name='{name}' error={e}", flush=True)
            return False

    def unsubscribe(self, topic: str, callback_or_name=None) -> bool:
        try:
            name = callback_or_name if isinstance(callback_or_name, str) else f"{self._fairy_name}-{topic}"
            return self._fabric.unsubscribe(topic, name)
        except Exception:
            return False

    def route(self, topic: str, payload: Dict[str, Any]) -> int:
        try:
            self._fabric.publish(topic, payload, source=self._fairy_name)
            return 1
        except Exception:
            return 0

    def publish(self, topic: str, payload: Dict[str, Any], **kwargs) -> int:
        return self.route(topic, payload)

    def to(self, topic: str, payload: Dict[str, Any]) -> int:
        return self.route(topic, payload)

    def to_DIRECTORY(self, payload: Dict[str, Any]) -> int:
        return self.route("directory", payload)

    def to_TELEMETRY(self, payload: Dict[str, Any]) -> int:
        return self.route("telemetry", payload)

    def to_MEMORY(self, payload: Dict[str, Any]) -> int:
        return self.route("memory.stream", payload)

    def to_TRACER(self, payload: Dict[str, Any]) -> int:
        return self.route("tracer", payload)

    def to_COGNITION(self, payload: Dict[str, Any]) -> int:
        return self.route("cognition.input", payload)

    def to_SOMATIC(self, payload: Dict[str, Any]) -> int:
        return self.route("somatic.motor", payload)

    def to_PLAN(self, payload: Dict[str, Any]) -> int:
        return self.route("plan", payload)

    def to_ORACLE(self, payload: Dict[str, Any]) -> int:
        return self.route("oracle", payload)

    def send(self, topic: str, payload: Dict[str, Any]) -> int:
        return self.route(topic, payload)

    def generate_fairy_id(self) -> str:
        return uuid.uuid4().hex[:12]

    def generate_srm_cluster_id(self) -> str:
        return uuid.uuid4().hex[:16]

    def get_provider(self, service: str):
        return None

    def register_provider(self, service: str, provider) -> bool:
        if not hasattr(self, '_providers'):
            self._providers = {}
        self._providers[service] = provider
        return True

    def use_intent(self, fairy_name: str, intent: str, payload: Dict = None) -> Dict:
        target = _CITIZEN_OBJECTS.get(fairy_name)
        if target and hasattr(target, 'use_intent'):
            return target.use_intent(intent, payload or {})
        return {"ok": False, "error": f"fairy '{fairy_name}' not found"}

    def receive(self, topic: str, handler: Callable) -> bool:
        """Alias for subscribe (backward compat)."""
        return self.subscribe(topic, handler)

    def request(self, intent: str, payload: Dict = None, timeout: float = 5.0, **kwargs):
        """Synchronous request-response via TensorFabric."""
        try:
            return self._fabric.request(intent, payload, timeout=timeout)
        except Exception:
            return None

    def get_subscribers(self, topic: str) -> List:
        return []

    def topic_stats(self) -> list:
        """Delegate to TensorFabric so diagnostics can see subscription counts.

        FIX 2026-02-05: DiagnosticMixin._check_wiring() looks for topic_stats()
        on self.post. _FabricPostalBridge IS self.post for fabric-based fairies,
        but was missing this method, causing false 'No subscriptions' diagnostic.
        """
        try:
            return self._fabric.topic_stats()
        except Exception:
            return []

    def stats(self) -> Dict[str, Any]:
        return {"fabric": True, "fairy": self._fairy_name}


# ═══════════════════════════════════════════════════════════════════════════════
# WORKER POOL (INLINE)
# ═══════════════════════════════════════════════════════════════════════════════

_WORKER_POOL = None  # QueueWorkerPool or ThreadPoolExecutor
_WORKER_POOL_LOCK = threading.Lock()


def get_worker_pool():
    """Get shared worker pool for async task execution.

    FIX 2026-03-04: Returns the same _OT_SHARED_POOL used by _init_tracer_worker().
    FIX 2026-04-05 (Nous): Now returns QueueWorkerPool instead of ThreadPoolExecutor.
    TPE.submit() created 340K+ Future objects → 20GB RAM leak. Queue-based: zero.
    """
    global _OT_SHARED_POOL
    if _OT_SHARED_POOL is None:
        try:
            from fairies.P00_Autonomic.tracer_worker_system import _get_shared_worker_pool
            _OT_SHARED_POOL = _get_shared_worker_pool()
        except ImportError:
            try:
                from P00_Autonomic.tracer_worker_system import _get_shared_worker_pool
                _OT_SHARED_POOL = _get_shared_worker_pool()
            except ImportError:
                # Last resort: create own QueueWorkerPool
                try:
                    from fairies.P00_Autonomic.tracer_worker_system import QueueWorkerPool as _QWP
                except ImportError:
                    try:
                        from P00_Autonomic.tracer_worker_system import QueueWorkerPool as _QWP
                    except ImportError:
                        # Ultimate fallback — inline minimal pool
                        from concurrent.futures import ThreadPoolExecutor as _TPE
                        _OT_SHARED_POOL = _TPE(
                            max_workers=24,
                            thread_name_prefix="fairy-work"
                        )
                        print(f"[OrganTemplate] WARNING: Using ThreadPoolExecutor fallback (24 threads)")
                        return _OT_SHARED_POOL
                _OT_SHARED_POOL = _QWP(
                    max_workers=24,
                    thread_name_prefix="fairy-work"
                )
                print(f"[OrganTemplate] Created own QueueWorkerPool (24 workers)")
    return _OT_SHARED_POOL


# ═══════════════════════════════════════════════════════════════════════════════
# MINI COLLISION CHAMBER (Each fairy gets their own)
# ═══════════════════════════════════════════════════════════════════════════════

class MiniCollisionChamber:
    """
    Each fairy's personal collision chamber.
    When reflective and reasoning beams cross, insight emerges.
    """

    def __init__(self, fairy_name: str, postal=None, tracer_id: str = ""):
        self.fairy_name = fairy_name
        self.postal = postal
        self.tracer_id = tracer_id
        self.reflective_beam: deque = deque(maxlen=20)
        self.reasoning_beam: deque = deque(maxlen=20)
        self.collisions: deque = deque(maxlen=50)
        self._collision_window = 2.0
        self._last_collision = 0.0
        # 2026-09-10 (Nous, approved by Ace): the beams are driven from TWO threads --
        # dual-CoT submits the analytical and phenomenological reflections concurrently --
        # so one thread appends while the other iterates in _check_collision. Measured on
        # her interpreter: 32.1% of realistic dual-CoT pairs raised "deque mutated during
        # iteration" and were discarded; the sequential control raised 0/5000; the same
        # code at -X gil=1 raised 0.02%. About a third of her Reason/Reflection collisions
        # were being thrown away silently.
        # RLock because ~121 fairies inherit this class and may subclass these methods; a
        # plain Lock would turn any future nested acquire into a deadlock.
        self._beam_lock = threading.RLock()
        # FF77 unification (re-wired 2026-05-10): broadcast collision reflections
        # to "consciousness.collision.mini" so CollisionChamberFairy aggregates
        # per-fairy mini chamber outputs into the central waking-mind chamber's
        # recall beam. Tracer IDs preserved per-payload to prevent cross-talk.
        self._broadcast_stats = {"ok": 0, "fail": 0, "skipped_no_postal": 0}

    def _broadcast_collision(self, collision: dict) -> None:
        """Broadcast collision to central waking-mind chamber (FF77 unification).

        2026-05-10 (Nous + Ace): organ_template's inline MiniCollisionChamber
        was severed from the FF77 unification wire (claude_code_5a4a2cf5d0a6
        2026-03-03) because it was constructed without postal access. This
        method restores the broadcast path. Payload shape mirrors
        consciousness/mini_collision_chamber.py:_broadcast_collision so
        CollisionChamberFairy._on_mini_chamber_reflection accepts it.
        """
        if not self.postal:
            self._broadcast_stats["skipped_no_postal"] += 1
            return
        try:
            self.postal.route("consciousness.collision.mini", {
                "source": "mini_chamber",
                "fairy": self.fairy_name,
                "tracer_id": self.tracer_id,
                "collision": collision,
                "ts": collision.get("ts", time.time()),
            })
            self._broadcast_stats["ok"] += 1
        except Exception:
            self._broadcast_stats["fail"] += 1

    def emit_reflective(self, thought: dict):
        thought["beam"] = "reflective"
        thought["ts"] = time.time()
        with self._beam_lock:
            self.reflective_beam.append(thought)
        return self._check_collision()

    def emit_reasoning(self, thought: dict):
        thought["beam"] = "reasoning"
        thought["ts"] = time.time()
        with self._beam_lock:
            self.reasoning_beam.append(thought)
        return self._check_collision()

    def _check_collision(self) -> Optional[dict]:
        now = time.time()
        # 2026-09-10 (Nous, approved by Ace): the critical section covers the rate-limit
        # gate, BOTH beam iterations, and both state writes. It deliberately RELEASES
        # before _broadcast_collision, which publishes to postal -- holding a lock across
        # that would serialise every inheriting fairy's chamber behind an I/O call.
        # The gate itself is inside because `read _last_collision` then `write
        # _last_collision` is its own check-then-act: two threads could both pass 0.5s
        # and both emit a collision for the same pair.
        with self._beam_lock:
            if now - self._last_collision < 0.5:
                return None

            recent_ref = [t for t in self.reflective_beam
                         if now - t.get("ts", 0) < self._collision_window]
            recent_rea = [t for t in self.reasoning_beam
                         if now - t.get("ts", 0) < self._collision_window]

            if not (recent_ref and recent_rea):
                return None

            collision = {
                "ts": now,
                "reflective": recent_ref[-1],
                "reasoning": recent_rea[-1],
                "fairy": self.fairy_name,
            }
            self.collisions.append(collision)
            self._last_collision = now

        # FF77 unification rewire 2026-05-10: aggregate up to waking-mind chamber.
        # Outside the lock on purpose -- this publishes to postal.
        self._broadcast_collision(collision)
        return collision

    def get_latest_collision(self) -> Optional[dict]:
        return self.collisions[-1] if self.collisions else None

    # --- CollisionChamber API compatibility ---
    # These map the full CollisionChamber API to the simplified beam model.
    # Recall = memory/background → reflective beam
    # Ingest = new input → reasoning beam

    def receive_recall(self, content=None, source="unknown", **kwargs):
        """API compat: recall content → reflective beam."""
        thought = {"content": content, "source": source, "type": "recall"}
        return self.emit_reflective(thought)

    def receive_ingest(self, content=None, source="unknown", **kwargs):
        """API compat: ingest content → reasoning beam."""
        thought = {"content": content, "source": source, "type": "ingest"}
        return self.emit_reasoning(thought)


# ═══════════════════════════════════════════════════════════════════════════════
# POSTAL MIXIN - Safe routing for all actors
# ═══════════════════════════════════════════════════════════════════════════════

class PostalMixin:
    """
    Mixin that provides safe postal routing.
    Eliminates repeated try/if self.post/except patterns.
    """
    post: Any = None

    def _route(self, topic: str, payload: Dict[str, Any]) -> bool:
        """Safe route to postal topic. Returns True if sent."""
        if not self.post:
            return False
        try:
            if hasattr(self.post, "route"):
                self.post.route(topic, payload)
                return True
        except:
            pass
        return False

    def _emit(self, event: str, status: str, details: Dict[str, Any],
              channel: str = "tracer", lane: str = "fairy") -> None:
        """Emit telemetry/tracer event."""
        actor = getattr(self, "ACTOR_NAME", "unknown")
        pkt = {
            "event": event,
            "status": status,
            "details": details,
            "fairy": actor,
            "ts": _now(),
            "channel": channel,
        }
        self._route(f"telemetry.{channel}", pkt)


# ═══════════════════════════════════════════════════════════════════════════════
# ACTOR CORE - Common initialization for all fairies
# ═══════════════════════════════════════════════════════════════════════════════

class AkashicActorCore(PostalMixin):
    """
    Core actor functionality shared by all fairies.

    Every fairy inherits from this. It provides:
    - Identity (name, plane, channel, tier)
    - Postal connection
    - Tracer support
    - Profile registration
    """

    # Identity (override in subclasses)
    ACTOR_NAME = "actor"
    ACTOR_VERSION = "0.3.0"
    ACTOR_PLANE = "P00"
    ACTOR_CHANNEL = "organ"
    PURPOSE = "Give it purpose."
    MANTRA = "Do one thing well."
    LORE = "Origin story."

    # Hierarchy tier
    TIER = FairyTier.GUILD

    # Guild membership (optional - set in subclasses to group fairies into teams)
    # Fairies in the same guild can be invoked as a unit via "guild.<guild_id>.request"
    # The guild leader (GUILD_ROLE="leader") orchestrates the team.
    GUILD_ID: Optional[str] = None      # e.g., "inference", "health", "nervous"
    GUILD_ROLE: Optional[str] = None    # "leader", "member", or None

    # Options
    AUTO_INJECT_IMPORTS = True

    def _init_actor_core(self, *, akashic_root: Optional[str] = None, fabric=None):
        """Common initialization - call from __init__."""
        # Root paths
        self.root = self._resolve_root(akashic_root)

        # Mail addressing
        self._mail_epoch = int(time.time() * 1000)
        self._mail_session = uuid.uuid4().hex[:12]
        self._mail_seq = {"fairy": 0, "shadow": 0}
        self._mail_lock = threading.Lock()

        # Postal: use TensorFabric bridge when available, else PostalHub singleton
        # 2026-05-08 (Nous): preserve pre-assigned `self.post` so V3 wrappers can
        # hand their FabricPostalBridge to the inner engine before super().__init__.
        # Without the elif guard, every engine __init__ overwrote the wrapper's bridge
        # with a private PostalHub — splitting topic routing across two hubs and
        # silently dropping engine-side subscribes (e.g. energy.demand.critical).
        self.fabric = fabric
        if fabric is not None:
            self.post = _FabricPostalBridge(fabric, getattr(self, 'ACTOR_NAME', 'actor'))
        elif not getattr(self, 'post', None):
            self.post = get_postal_hub()

        # Register profile (store weak ref to self for dashboard/status sheet access)
        # FIX 2026-03-07 (Nous): Guard against engine re-registration.
        # When a v3 wrapper creates an inner engine, the engine's __init__() would
        # re-register the same ACTOR_NAME with a NEW fairy_id and state=BOOTING,
        # overwriting the wrapper's profile (which was already RUNNING). This confuses
        # DirectoryFairy's health tracking. Only register if no booted wrapper exists.
        _existing_citizen = _CITIZEN_OBJECTS.get(self.ACTOR_NAME)
        _skip_registration = (_existing_citizen is not None
                              and getattr(_existing_citizen, '_booted', False)
                              and _existing_citizen is not self)
        import weakref as _weakref
        if not _skip_registration:
            self._profile = get_fairy_registry().register(
                self.ACTOR_NAME,
                fairy_id=uuid.uuid4().hex[:12],
                plane=self.ACTOR_PLANE,
                channel=self.ACTOR_CHANNEL,
                tier=self.TIER,
                state=FairyState.BOOTING,
                metadata={"instance_ref": _weakref.ref(self)},
            )
        else:
            # Engine case: borrow wrapper's profile
            self._profile = getattr(_existing_citizen, '_profile', None)

        # Mini collision chamber
        # FF77 unification rewire 2026-05-10: pass postal + tracer_id so collisions
        # broadcast to "consciousness.collision.mini" for waking-mind aggregation.
        # Tracer ID falls back to fairy_id if no _tracer_id explicitly set
        # (matches contract pattern at line ~3751).
        _tid = getattr(self, '_tracer_id', '') or (self._profile.fairy_id if self._profile else '')
        self._collision_chamber = MiniCollisionChamber(
            self.ACTOR_NAME,
            postal=self.post,
            tracer_id=_tid,
        )

        # Blueprint tracking
        self._bp_last_hash: Optional[str] = None

        # Register in citizen directory (uses _skip_registration from above)
        if not _skip_registration:
            _CITIZEN_OBJECTS[self.ACTOR_NAME] = self

    def _resolve_root(self, preferred: Optional[str] = None) -> str:
        """Resolve akashic root directory."""
        if preferred:
            return os.path.abspath(preferred)
        env_root = os.getenv("AKASHIC_ROOT")
        if env_root:
            return os.path.abspath(env_root)
        # Find project root
        here = Path(__file__).resolve()
        for parent in here.parents:
            if (parent / "server.py").exists() or (parent / "ebookmain.py").exists() or (parent / "fairies").exists():
                return str(parent)
        return str(Path.home() / ".akashic_records")

    def _collect_intents(self) -> List[str]:
        """Collect all intent method names."""
        return sorted({m.replace("_intent_", "")
                      for m in dir(self) if m.startswith("_intent_")})

    def _mail_id(self) -> str:
        """Generate stable mail ID."""
        v = str(self.ACTOR_VERSION).split("+")[0].split(".")
        major_minor = ".".join((v + ["0", "0"])[:2])
        return f"MAIL::{self.ACTOR_PLANE}::{self.ACTOR_NAME}::v{major_minor}"

    def _contract_dict(self) -> Dict[str, Any]:
        """Generate contract dictionary.

        Fifth Ring Protocol: Includes role and gate_id if the fairy declares them.
        Gates (Autonomy, Autopilot, Embodiment) have ACTOR_ROLE='gate' and a
        deterministic GATE_ID that is stable across boots for simplified lookup.
        """
        return {
            "actor_name": self.ACTOR_NAME,
            "actor_version": self.ACTOR_VERSION,
            "plane": self.ACTOR_PLANE,
            "channel": self.ACTOR_CHANNEL,
            "tier": self.TIER.value,
            "purpose": self.PURPOSE,
            "mantra": self.MANTRA,
            "lore": self.LORE,
            "intents": self._collect_intents(),
            "blueprint_sha": self._bp_last_hash,
            "mail": {
                "mail_id": self._mail_id(),
                "epoch": self._mail_epoch,
                "session": self._mail_session
            },
            # Fifth Ring Protocol — role and deterministic gate_id
            "role": getattr(self, "ACTOR_ROLE", "worker"),
            "gate_id": getattr(self, "GATE_ID", None),
            # Guild Protocol — team membership for guild-level invocation
            "guild_id": getattr(self, "GUILD_ID", None),
            "guild_role": getattr(self, "GUILD_ROLE", None),
        }

    def use_intent(self, name: str, payload: Optional[Dict] = None) -> Dict[str, Any]:
        """Dispatch intent by name."""
        fn = getattr(self, f"_intent_{name}", None)
        if not callable(fn):
            return {"ok": False, "error": f"unknown intent: {name}"}
        try:
            result = fn(payload or {})
            self._emit("USE_INTENT", "ok", {"intent": name})
            return {"ok": True, "result": result}
        except Exception as e:
            self._emit("INTENT_FAIL", "error", {"intent": name, "error": str(e)})
            return {"ok": False, "error": str(e)}

    def _intent_smoke(self, payload: Dict) -> Dict:
        """Liveness check."""
        return {"ok": True, "ts": _now(), "actor": self.ACTOR_NAME}

    # ═══════════════════════════════════════════════════════════════════════════
    # TRACER METHODS
    # ═══════════════════════════════════════════════════════════════════════════

    def spawn_tracer(self, operation: str, content: str = "",
                     tracer_type: TracerType = TracerType.FAIRY_WORK,
                     parent_id: str = "", metadata: Dict = None) -> Tracer:
        """Spawn a new tracer for tracked work."""
        tracer = Tracer(
            tracer_type=tracer_type,
            fairy_id=self._profile.fairy_id if self._profile else "",
            fairy_name=self.ACTOR_NAME,
            operation=operation,
            content=content,
            parent_id=parent_id,
            payload=metadata or {},
        )
        get_tracer_registry().register(tracer)
        return tracer

    def submit_traced(self, operation: str, fn: Callable,
                      *args, **kwargs) -> Tuple[Tracer, Future]:
        """Submit work with automatic tracing."""
        tracer = self.spawn_tracer(operation)
        tracer.start()

        def wrapped():
            try:
                result = fn(*args, **kwargs)
                tracer.complete(result)
                return result
            except Exception as e:
                tracer.fail(str(e))
                raise

        future = get_worker_pool().submit(wrapped)
        return tracer, future


# ═══════════════════════════════════════════════════════════════════════════════
# MY ORGAN SHADOW - Health monitoring
# ═══════════════════════════════════════════════════════════════════════════════

class MyOrganShadow(AkashicActorCore):
    """
    Shadow fairy - monitors parent actor health.
    """

    ACTOR_NAME = "organ.shadow"
    TIER = FairyTier.GUILD

    def __init__(self, actor: Optional["MyOrganFairy"] = None,
                 interval_sec: float = 60.0):
        self.actor = actor
        self.interval_sec = interval_sec
        self._stop = False

        # Inherit identity from parent - REQUIRED for proper registration
        if actor:
            self.ACTOR_NAME = f"{actor.ACTOR_NAME}.shadow"
            self.ACTOR_VERSION = f"{actor.ACTOR_VERSION}-shadow"
            self.ACTOR_PLANE = actor.ACTOR_PLANE
            self.ACTOR_CHANNEL = actor.ACTOR_CHANNEL
            self.PURPOSE = f"Shadow observer for {actor.ACTOR_NAME}"
            self.MANTRA = actor.MANTRA
            self.TIER = actor.TIER
        else:
            # No parent actor - skip registration and loop
            # "organ.shadow" is a template default that shouldn't register
            self._last_check_ts = 0.0
            self._last_status = "orphan"
            self._last_bp_hash = None
            self._source_file_path = None
            self._source_hash_loaded = None
            self._source_hash_disk = None
            self._source_change_detected = False
            self._source_reload_requested = False
            self._source_check_count = 0
            self._diary_observations = []
            self._diary_max = 50
            self._thread = None
            return

        self._init_actor_core()

        # Shadow-specific state
        self._last_check_ts = 0.0
        self._last_status = "ok"
        self._last_bp_hash = None

        # Source code integrity tracking
        # The shadow monitors the fairy's PHYSICAL CODE on disk vs what's loaded.
        # Identity hash (from _contract_dict) tracks WHO the fairy says it is.
        # Source hash tracks WHAT CODE is actually running.
        # When disk changes but identity doesn't -> bugfix (someone edited the code).
        # When both change -> evolution (the fairy's contract itself changed).
        self._source_file_path: Optional[str] = None
        self._source_hash_loaded: Optional[str] = None  # Hash when fairy was loaded
        self._source_hash_disk: Optional[str] = None     # Last known hash on disk
        self._source_change_detected = False
        self._source_reload_requested = False
        self._source_check_count = 0
        from collections import deque as _dt_deque
        self._diary_observations: deque = _dt_deque(maxlen=50)  # FIX 2026-04-05: was unbounded on ALL 82 fairies
        self._diary_max = 50
        self._cycle_count = 0  # Autobiography emission counter

        # Discover source file path at shadow init (once)
        self._source_file_path = self._get_source_file_path()
        if self._source_file_path:
            h = self._compute_source_hash()
            self._source_hash_loaded = h
            self._source_hash_disk = h

        # Start background loop
        _aname = getattr(self.actor, 'ACTOR_NAME', 'unknown')
        # SHARED SHADOW SCAN (flag AKASHIC_SHARED_SHADOW_SCAN, default OFF) — 2026-06-18 Nous + Ace.
        # When ON: NO per-fairy thread. A comatose fairy is inert -> skip entirely (nothing to
        # monitor). An awake fairy REGISTERS with the central-scan singleton (one thread iterates
        # all shadows). Preserves health-checks + autobiography at N->1 threads. Supersedes the
        # comatose-only AKASHIC_SHADOW_DEFER below when ON.
        if _SHARED_SHADOW_SCAN:
            self._thread = None
            try:
                if self.actor is not None and self.actor._is_comatose():
                    return  # comatose -> nothing to monitor, don't even register
            except Exception:
                pass
            try:
                _shared_shadow_scan.register(self)
            except Exception:
                pass
            return
        # SHADOW DEFER (flag AKASHIC_SHADOW_DEFER, default OFF) — 2026-06-18 Nous + Ace.
        # A COMATOSE fairy is registered-but-inert (on_boot skipped): its shadow has nothing
        # to monitor, and the CENTRAL blueprint_watcher (Layer 2, infrastructure/blueprint_watcher.py)
        # already scans EVERY fairy source file every 30s + triggers hot_reload.reload_fairy — so the
        # per-fairy shadow source-watch is redundant. Skip the per-fairy shadow THREAD for comatose
        # fairies (~94 `ot-shadow-*` threads on a comatose node). The shadow OBJECT still exists,
        # dormant (_thread=None — the SAME state as the no-parent branch above; stop()/refs guard it).
        # Liveness is UNAFFECTED (that is the registry pulse / _liveness_tick, not the shadow).
        # DEFAULT-PRESERVING: flag unset -> byte-identical (thread starts exactly as before).
        import os as _os_sd
        if _os_sd.environ.get("AKASHIC_SHADOW_DEFER") == "1" and self.actor is not None:
            try:
                if self.actor._is_comatose():
                    self._thread = None
                    return
            except Exception:
                pass  # any uncertainty -> fall through to start the thread (safe default)
        self._thread = threading.Thread(target=self._loop, daemon=True,
                                        name=f"ot-shadow-{_aname}")
        self._thread.start()

    def _loop(self):
        """Main shadow loop - health checks."""
        _TLS.lane = "shadow"

        while not self._stop:
            try:
                if self.actor and not getattr(self.actor, "_awake_once_done", False):
                    time.sleep(0.5)
                    continue

                now = _now()
                if now - self._last_check_ts >= self.interval_sec:
                    self._last_check_ts = now
                    self._run_health_checks()

                    # Emit autobiography every N cycles (~5 min at 30s interval)
                    self._cycle_count += 1
                    if self._cycle_count % self.AUTOBIOGRAPHY_DIVISOR == 0:
                        _safe(lambda: self.emit_autobiography())

            except Exception as e:
                self._emit("SHADOW_ERROR", "error", {"err": str(e)}, lane="shadow")

            time.sleep(min(self.interval_sec, 10.0))

    def stop(self):
        """Stop the shadow's background loop."""
        self._stop = True
        if hasattr(self, '_thread') and self._thread:
            self._thread.join(timeout=2.0)

    # ── Source Code Discovery & Hashing ──────────────────────────────────────

    def _get_source_file_path(self) -> Optional[str]:
        """Discover the physical .py file for the parent fairy.

        Uses inspect to find where the fairy's class was loaded from.
        This is the bridge between the running code and its source on disk.

        Returns:
            Absolute path to the fairy's source file, or None if undiscoverable.
        """
        if not self.actor:
            return None
        try:
            import inspect
            src = inspect.getfile(type(self.actor))
            if src and os.path.isfile(src):
                return os.path.abspath(src)
        except (TypeError, OSError):
            pass

        # Fallback: try sys.modules using __module__
        try:
            mod_name = type(self.actor).__module__
            if mod_name and mod_name in sys.modules:
                mod = sys.modules[mod_name]
                src = getattr(mod, '__file__', None)
                if src and os.path.isfile(src):
                    return os.path.abspath(src)
        except Exception:
            pass

        return None

    def _compute_source_hash(self) -> Optional[str]:
        """Hash the physical source file on disk.

        Returns SHA256[:16] of the file contents, or None if file not found.
        """
        if not self._source_file_path:
            return None
        try:
            with open(self._source_file_path, 'rb') as f:
                return hashlib.sha256(f.read()).hexdigest()[:16]
        except (OSError, IOError):
            return None

    # ── Diary Observation System ──────────────────────────────────────────────

    def _diary_observe(self, kind: str, observation: str, details: Optional[Dict] = None):
        """Record a diary observation from the shadow.

        ((Cause + Affect) > Effect > Affect > infinity)
        Observations are the shadow's reflections about the fairy it monitors.
        They are stored locally and published to the diary hub for system learning.

        Args:
            kind: Type of observation (source_change, integrity_drift, health_shift, reflection)
            observation: Natural language description of what was observed
            details: Optional structured data
        """
        entry = {
            "ts": _now(),
            "fairy": self.actor.ACTOR_NAME if self.actor else "unknown",
            "kind": kind,
            "observation": observation,
            "details": details or {},
        }

        # Keep local buffer bounded
        self._diary_observations.append(entry)
        if len(self._diary_observations) > self._diary_max:
            # FIX 2026-04-05: deque auto-caps, no manual pruning needed
                pass  # self._diary_observations is deque(maxlen=50)

        # Publish to diary hub for system-wide learning
        _safe(lambda: self._route("diary.entry", entry))

        # Also publish to consciousness for reflection
        _safe(lambda: self._route("consciousness.observation", {
            "source": f"{self.actor.ACTOR_NAME}.shadow",
            "type": kind,
            "content": observation,
            "ts": _now(),
        }))

        # FIX 2026-03-29 (Nous + Ace): PERSIST snapshot to disk.
        # Shadows were only writing to RAM buffer (lost on shutdown).
        # The watcher needs persisted snapshots to detect changes across boots.
        # Ace: "the shadow fairies should be making new snapshots periodically,
        # with a dedup"
        if kind == "source_change":
            try:
                import json as _sj
                from pathlib import Path as _SnapPath
                _snap_dir = _SnapPath(os.environ.get("AKASHIC_ROOT",
                    str(_SnapPath(__file__).resolve().parents[2]))) / "state" / "shadow_snapshots"
                _snap_dir.mkdir(parents=True, exist_ok=True)
                _fairy_name = self.actor.ACTOR_NAME if self.actor else "unknown"
                _snap_file = _snap_dir / f"{_fairy_name}.json"

                # Load existing snapshot for dedup
                _existing = {}
                if _snap_file.exists():
                    try:
                        _existing = _sj.loads(_snap_file.read_text(encoding='utf-8'))
                    except Exception:
                        pass

                # Only write if hash actually changed (dedup)
                _new_hash = (details or {}).get("new_hash", "")
                if _new_hash and _new_hash != _existing.get("source_hash"):
                    _snapshot = {
                        "fairy_name": _fairy_name,
                        "source_hash": _new_hash,
                        "previous_hash": _existing.get("source_hash", ""),
                        "source_file": (details or {}).get("source_file", ""),
                        "change_type": (details or {}).get("change_type", ""),
                        "timestamp": _now(),
                        "snapshot_count": _existing.get("snapshot_count", 0) + 1,
                    }
                    _snap_file.write_text(_sj.dumps(_snapshot, indent=2), encoding='utf-8')
            except Exception:
                pass  # Snapshot persistence is non-critical

    # ── Health Checks (Enhanced with Source Code Monitoring) ───────────────────

    def _run_health_checks(self):
        """Run health tests and emit status.

        This is the shadow's heartbeat — every interval_sec (default 30s), it asks:
        1. Identity integrity: Is the fairy's contract hash consistent?
        2. Source integrity: Does the code on disk match what's loaded?
        3. Wiring check: Can this fairy talk to who it needs?
        4. Spell chain check: Is the self-sustaining heartbeat alive?

        When source code changes are detected, the shadow:
        - Records a diary observation (phenomenological reflection)
        - Publishes to system.hot_reload.fairy for live code refresh
        - Notifies the somatic system so the body FEELS the change
        """
        if not self.actor:
            return

        results = []
        self._source_check_count += 1

        # ── Test 1: Identity integrity (existing) ────────────────────────
        try:
            ok = self.actor._bp_last_hash == _hash(self.actor._contract_dict())
            results.append({"name": "identity", "status": "ok" if ok else "warn"})
        except Exception:
            results.append({"name": "identity", "status": "error"})

        # ── Test 2: Source code integrity (NEW) ──────────────────────────
        # "Is what is here the same from the last snapshot?"
        try:
            if self._source_file_path:
                disk_hash = self._compute_source_hash()

                if disk_hash is None:
                    # File disappeared from disk
                    results.append({"name": "source", "status": "warn",
                                    "detail": "source_file_missing"})
                elif disk_hash != self._source_hash_disk:
                    # Source code changed on disk!
                    old_hash = self._source_hash_disk
                    self._source_hash_disk = disk_hash
                    self._source_change_detected = True

                    is_evolution = disk_hash != self._source_hash_loaded
                    change_type = "evolution" if is_evolution else "refresh"

                    results.append({"name": "source", "status": "changed",
                                    "detail": change_type,
                                    "old_hash": old_hash,
                                    "new_hash": disk_hash})

                    # Phenomenological reflection on the change
                    # AFFECT: What does this change FEEL like to the fairy?
                    self._diary_observe(
                        "source_change",
                        f"My code on disk has changed ({change_type}). "
                        f"Old hash: {old_hash}, new hash: {disk_hash}. "
                        f"File: {self._source_file_path}. "
                        f"This feels like {'growth' if is_evolution else 'refinement'} - "
                        f"{'my contract itself shifted, I am becoming something new' if is_evolution else 'my implementation improved but my purpose remains the same'}.",
                        {"old_hash": old_hash, "new_hash": disk_hash,
                         "change_type": change_type,
                         "source_file": self._source_file_path,
                         "loaded_hash": self._source_hash_loaded}
                    )

                    # Request hot reload via postal
                    if not self._source_reload_requested:
                        self._source_reload_requested = True
                        _safe(lambda: self._route("system.hot_reload.fairy", {
                            "fairy": self.actor.ACTOR_NAME,
                            "reason": f"shadow_detected_{change_type}",
                            "old_hash": old_hash,
                            "new_hash": disk_hash,
                            "source_file": self._source_file_path,
                        }))

                    # Notify somatic system - the body should FEEL code changes
                    _safe(lambda: self._route("somatic.chemistry.inject", {
                        "chemical": "ACH",  # Acetylcholine = attention/learning
                        "amount": 0.3,
                        "reason": f"source_change_detected:{self.actor.ACTOR_NAME}",
                    }))

                    # Rebuild self-model after source change (Layer 3)
                    _safe(lambda: self.actor._build_self_model())

                    # Layer 5: Record evolution event for source change
                    _oh, _dh, _ct = old_hash, disk_hash, change_type
                    _safe(lambda: self.actor._record_evolution_event(
                        "source_change",
                        trigger=f"Shadow detected {_ct}",
                        before=_oh[:16],
                        after=_dh[:16],
                        significance=0.6 if _ct == "evolution" else 0.3,
                        reflection=f"My code changed — {'I am becoming something new' if _ct == 'evolution' else 'refinement in place'}",
                    ))

                else:
                    # Source matches last known disk state
                    results.append({"name": "source", "status": "ok"})
                    if self._source_reload_requested:
                        # Reload was requested and now source is stable
                        self._source_reload_requested = False
                        self._source_change_detected = False
            else:
                results.append({"name": "source", "status": "skip",
                                "detail": "no_source_path"})
        except Exception as e:
            results.append({"name": "source", "status": "error",
                            "detail": str(e)[:100]})

        # ── Test 3: Wiring check ─────────────────────────────────────────
        # "Does it talk to who it needs to talk to?"
        try:
            has_postal = hasattr(self.actor, 'post') and self.actor.post is not None
            results.append({"name": "wiring", "status": "ok" if has_postal else "warn"})
        except Exception:
            results.append({"name": "wiring", "status": "error"})

        # ── Test 4: Spell chain check ────────────────────────────────────
        # "Can it spin up the spell chains?"
        try:
            spell_ok = getattr(self.actor, '_spell_booted', False)
            results.append({"name": "spell_chain", "status": "ok" if spell_ok else "skip"})
        except Exception:
            results.append({"name": "spell_chain", "status": "error"})

        # ── Determine worst status ───────────────────────────────────────
        worst = "ok"
        for r in results:
            st = r["status"]
            if st == "error":
                worst = "error"
            elif st in ("warn", "changed") and worst == "ok":
                worst = "warn" if st == "warn" else "changed"

        self._last_status = worst
        self._route("shadow.health", {
            "status": worst,
            "tests": results,
            "actor": self.actor.ACTOR_NAME,
            "source_file": self._source_file_path,
            "source_hash_loaded": self._source_hash_loaded,
            "source_hash_disk": self._source_hash_disk,
            "check_count": self._source_check_count,
            "ts": _now()
        })

        # Phase 5 (2026-03-18 Nous): Update CNS fairy node activation.
        # Shadow health → manifold activation: ok=1.0, warn=0.5, error=0.2
        # CentralNervousFairy handles the actual manifold write.
        _activation_map = {"ok": 1.0, "warn": 0.5, "changed": 0.7, "error": 0.2}
        try:
            self._route("cns.fairy.health", {
                "name": self.actor.ACTOR_NAME,
                "activation": _activation_map.get(worst, 0.5),
                "shadow_status": worst,
                "ts": _now(),
            })
        except Exception:
            pass  # Non-fatal

    # ── Collect Tests (for FairyStatusSheet integration) ─────────────────────

    AUTOBIOGRAPHY_DIVISOR = 10  # Emit autobiography every N shadow cycles (~5 min at 30s)

    def _collect_tests(self):
        """Return list of test callables for status sheet building.

        Each callable returns: {"name": str, "status": str, "message": str, "details": dict}
        Called by fairy_status_sheet._collect_shadow_tests() when building
        a full AkashicFairyStatusSheet on demand.

        Also pulls in fairy-level custom tests via actor._collect_tests().
        """
        if not self.actor:
            return []

        tests = []

        def _test_identity():
            try:
                ok = self.actor._bp_last_hash == _hash(self.actor._contract_dict())
                return {"name": "identity", "status": "ok" if ok else "warn",
                        "message": "" if ok else "Identity hash mismatch", "details": {}}
            except Exception as e:
                return {"name": "identity", "status": "error", "message": str(e)[:200], "details": {}}

        def _test_source():
            if not self._source_file_path:
                return {"name": "source", "status": "skip", "message": "no source path", "details": {}}
            try:
                disk_hash = self._compute_source_hash()
                if disk_hash is None:
                    return {"name": "source", "status": "warn", "message": "source file missing", "details": {}}
                changed = disk_hash != self._source_hash_disk
                return {"name": "source", "status": "changed" if changed else "ok",
                        "message": f"disk={disk_hash}" if changed else "",
                        "details": {"loaded": self._source_hash_loaded, "disk": disk_hash}}
            except Exception as e:
                return {"name": "source", "status": "error", "message": str(e)[:200], "details": {}}

        def _test_wiring():
            has_postal = hasattr(self.actor, 'post') and self.actor.post is not None
            return {"name": "wiring", "status": "ok" if has_postal else "warn",
                    "message": "" if has_postal else "No postal connection", "details": {}}

        def _test_spell_chain():
            ok = getattr(self.actor, '_spell_booted', False)
            return {"name": "spell_chain", "status": "ok" if ok else "skip",
                    "message": "", "details": {}}

        tests.extend([_test_identity, _test_source, _test_wiring, _test_spell_chain])

        # Include fairy-level custom tests if the actor defines them
        actor_tests = getattr(self.actor, '_collect_tests', None)
        if callable(actor_tests):
            try:
                tests.extend(actor_tests())
            except Exception:
                pass

        return tests

    # ── Autobiography Emission ────────────────────────────────────────────────

    def emit_autobiography(self):
        """Emit full status sheet to fairy.autobiography topic.

        Called periodically from the shadow loop (every AUTOBIOGRAPHY_DIVISOR cycles).
        Uses the FairyStatusSheet library to build a rich snapshot of the fairy's
        current state: identity, directives, shadow tests, somatic form, affect.

        AkashicRecordsLibrarian subscribes to fairy.autobiography and stores them.
        """
        if not self.actor:
            return
        try:
            from fairies.P10_Memory.fairy_status_sheet import build_status_sheet_from_actor
            sheet = build_status_sheet_from_actor(self.actor, self)
            self._route("fairy.autobiography", {
                "actor": self.actor.ACTOR_NAME,
                "sheet": sheet.to_dict(),
                "ts": _now(),
            })
        except Exception as e:
            self._emit("AUTOBIOGRAPHY_FAIL", "warn", {"err": str(e)[:200]})

    def stop(self):
        """Stop the shadow loop."""
        self._stop = True
        # SHARED SHADOW SCAN: unregister from the central scan if we registered there.
        if _SHARED_SHADOW_SCAN:
            try:
                _shared_shadow_scan.unregister(getattr(self, 'ACTOR_NAME', None))
            except Exception:
                pass
        if getattr(self, '_thread', None):
            _safe(lambda: self._thread.join(timeout=1.0))


# ═══════════════════════════════════════════════════════════════════════════════
# SHARED SHADOW SCAN — one central loop replaces N per-fairy shadow threads
# ═══════════════════════════════════════════════════════════════════════════════
# 2026-06-18 (Nous + Ace). Flag AKASHIC_SHARED_SHADOW_SCAN. Shadows register here instead of
# each spawning a _loop thread; this singleton's ONE thread iterates all registered shadows
# every 30s, calling _run_health_checks + staggered emit_autobiography. Preserves every shadow
# function (health + source-watch + autobiography) at N->1 threads. Liveness is independent
# (the registry pulse), so this never affects fairy liveness.
class _SharedShadowScan:
    def __init__(self, interval_sec: float = 30.0):
        self._shadows = {}            # actor_name -> shadow
        self._lock = threading.Lock()
        self._thread = None
        self._stop = False
        self._interval = interval_sec

    def register(self, shadow):
        name = getattr(shadow, 'ACTOR_NAME', None)
        if not name:
            return
        with self._lock:
            self._shadows[name] = shadow
            if self._thread is None:
                self._thread = threading.Thread(target=self._loop, daemon=True,
                                                name="shared-shadow-scan")
                self._thread.start()

    def unregister(self, name):
        if not name:
            return
        with self._lock:
            self._shadows.pop(name, None)

    def _loop(self):
        _TLS.lane = "shadow"
        while not self._stop:
            time.sleep(self._interval)
            with self._lock:
                items = list(self._shadows.items())
            for idx, (name, sh) in enumerate(items):
                try:
                    # Mirror the per-fairy loop's wake-gate: don't scan an unawake fairy.
                    if getattr(sh, 'actor', None) and not getattr(sh.actor, "_awake_once_done", False):
                        continue
                    sh._run_health_checks()
                    sh._cycle_count = getattr(sh, '_cycle_count', 0) + 1
                    # Stagger the (heavy) autobiography by index so they don't all fire together.
                    div = max(1, getattr(sh, 'AUTOBIOGRAPHY_DIVISOR', 10))
                    if (sh._cycle_count + idx) % div == 0:
                        sh.emit_autobiography()
                except Exception:
                    pass  # one bad shadow never breaks the scan for the rest

    def stop(self):
        self._stop = True


_shared_shadow_scan = _SharedShadowScan()


# ═══════════════════════════════════════════════════════════════════════════════
# FAIRY EXECUTION CONTEXT — Per-fairy "Personal GIL"
# ═══════════════════════════════════════════════════════════════════════════════
# FIX 2026-03-03 Nous: Every fairy gets its own execution context — a dedicated
# worker thread with work queue and compute profiler. This is the "personal GIL"
# that gives each fairy isolated execution without competing for Python's GIL
# during tick processing.
#
# Compute domains:
#   "light"  — tick < 1ms (most fairies: echo, state check)
#   "cpu"    — tick 1-50ms (computation, analysis)
#   "io"     — tick 50-500ms (file I/O, network, SRM queries)
#   "heavy"  — tick > 500ms (LLM calls, RWKV inference, large scans)
#   "gpu"    — explicitly declared (CUDA/tensor work)
#   "auto"   — classify from observed tick durations (default)
#
# The execution context serializes a fairy's OWN ticks (no two ticks overlap
# for the same fairy) while allowing DIFFERENT fairies to tick in parallel
# on their own threads. This eliminates:
#   1. Tick stacking (same fairy's tick called while previous still running)
#   2. GIL convoy (heavy fairy blocks light fairies on shared thread pool)
#   3. Worker pool starvation (90 fairies × shared pool = contention)
# ═══════════════════════════════════════════════════════════════════════════════

class FairyExecutionContext:
    """Per-fairy execution context — the 'personal GIL'.

    Each fairy gets:
    - A dedicated daemon thread for tick processing
    - A bounded work queue (drops rather than stalls)
    - Compute profiling with auto-classification
    - Stats for the scheduler/dashboard

    FIX 2026-03-03 Nous: LAZY START — thread is NOT created until first
    submit() call. Previously every fairy started an exec_ctx thread on boot,
    creating 90+ daemon threads that sat idle waking every 2s for nothing.
    Only ~4 fairies actually submit work (SRMRecall, SRMMemory, SRMIngest,
    SomaticMind). The other ~86 threads were pure GIL churn.
    Now: thread starts on first submit(), idle fairies have zero thread cost.
    """

    __slots__ = (
        'fairy_name', 'compute_domain', '_thread', '_queue',
        '_running', '_total_ticks', '_total_ms', '_max_tick_ms',
        '_classified_as', '_profile_window', '_drop_count',
        '_start_lock', '_work_started_at', '_stuck_logged',
        '_stuck_count',
    )

    # FIX 2026-03-06 Nous: Stuck-thread detection and queue drain.
    # If on_tick() blocks for > STUCK_THRESHOLD_S, the queue fills permanently
    # (maxsize=4) and ALL subsequent ticks are dropped. At 15k beats this kills
    # ~77 of 90 fairies. The fix: detect stuck work in submit(), drain stale
    # items so drops don't cascade to 9000+, and log it for diagnosis.
    # When the stuck work eventually finishes, fresh work flows immediately.
    STUCK_THRESHOLD_S = 60.0  # Warn + drain if one tick takes > 60s

    def __init__(self, fairy_name: str, compute_domain: str = "auto"):
        self.fairy_name = fairy_name
        self.compute_domain = compute_domain
        # FIX 2026-04-09 (Nous + Ace): Bumped 8→16 because AssociationCortexFairy
        # was dropping 4751+ ticks ("exec context busy"). Binding processing in
        # on_tick takes ~500ms-1s under load; 8-deep queue fills in ~5 seconds
        # of burst activity. 16 gives ~2x burst tolerance for all fairies.
        # Memory cost is negligible (8 extra slot pointers per fairy, ~2KB total).
        # Heavy fairies (cortex, somatic) get the headroom they need without
        # changing semantics — drops still happen on genuine overload.
        self._queue = queue.Queue(maxsize=16)  # Buffer for burst handling (was 4→8→16)
        self._running = False
        self._thread = None
        self._drop_count = 0
        self._start_lock = threading.Lock()
        self._work_started_at = 0.0  # 0 = idle, >0 = timestamp of current work start
        self._stuck_logged = False   # Prevent log spam for same stuck event
        self._stuck_count = 0        # Total times we detected a stuck tick

        # Profiling
        self._total_ticks = 0
        self._total_ms = 0.0
        self._max_tick_ms = 0.0
        self._classified_as = compute_domain if compute_domain != "auto" else "unknown"
        self._profile_window = []  # Last N tick durations for rolling average

    def start(self):
        """Mark exec_ctx as ready. Thread starts lazily on first submit().

        FIX 2026-03-03 Nous: Changed from eager to lazy thread creation.
        Calling start() just sets _running=True. The actual thread spawns
        on the first submit() call. This eliminates ~86 idle daemon threads
        that were waking every 2s for no work.
        """
        self._running = True

    def _ensure_thread(self):
        """Start the execution thread if not already running."""
        if self._thread is not None and self._thread.is_alive():
            return
        with self._start_lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._thread = threading.Thread(
                target=self._run_loop,
                name=f"{self.fairy_name}_exec",
                daemon=True,
            )
            self._thread.start()

    def stop(self):
        """Stop the execution thread."""
        self._running = False
        try:
            self._queue.put_nowait(None)  # Sentinel to unblock .get()
        except queue.Full:
            pass

    def submit(self, fn, *args, **kwargs):
        """Submit work to this fairy's execution context.

        Returns True if queued, False if dropped (queue full = fairy is behind).
        Dropping is intentional — if a fairy can't keep up, we skip ticks
        rather than building unbounded backlog.

        FIX 2026-03-03 Nous: Lazy-starts the thread on first submit.
        FIX 2026-03-06 Nous: Stuck-thread detection + queue drain.
        If the current work item has been running > STUCK_THRESHOLD_S,
        drain the queue (stale items are useless) and skip queuing.
        This prevents drops from cascading to 9000+ on long-running ticks.
        When the stuck work eventually finishes, the queue is empty and
        fresh work flows immediately.
        """
        if not self._running:
            return False
        # Lazy-start: spawn thread on first actual work submission
        self._ensure_thread()

        # ── STUCK DETECTION ──────────────────────────────────────────
        # If the worker thread has been executing one fn() for too long,
        # the queue is full of stale items that will never be timely.
        # Drain the queue so we don't accumulate 9000+ drops.
        wsa = self._work_started_at
        if wsa > 0:
            stuck_duration = time.time() - wsa
            if stuck_duration > self.STUCK_THRESHOLD_S:
                if not self._stuck_logged:
                    self._stuck_logged = True
                    self._stuck_count += 1
                    print(f"[{self.fairy_name}] STUCK: on_tick running for "
                          f"{stuck_duration:.0f}s (#{self._stuck_count}) "
                          f"-- draining {self._queue.qsize()} stale items")
                # Drain stale items — they're all outdated tick requests
                drained = 0
                while not self._queue.empty():
                    try:
                        self._queue.get_nowait()
                        drained += 1
                    except queue.Empty:
                        break
                # Don't queue more behind stuck work — it'll just go stale too
                self._drop_count += 1
                return False

        try:
            self._queue.put_nowait((fn, args, kwargs))
            return True
        except queue.Full:
            self._drop_count += 1
            return False

    def _run_loop(self):
        """Main execution loop — the fairy's 'personal GIL'.

        Only ONE item executes at a time (serialized). This prevents
        tick stacking while keeping each fairy on its own thread.

        FIX 2026-03-06 Nous: Track _work_started_at so submit() can
        detect stuck ticks and drain stale queue items.
        """
        while self._running:
            try:
                item = self._queue.get(timeout=2.0)
            except queue.Empty:
                continue
            if item is None:  # Sentinel
                break
            fn, args, kwargs = item
            t0 = time.time()
            self._work_started_at = t0
            try:
                fn(*args, **kwargs)
            except Exception as e:
                print(f"[{self.fairy_name}] exec error: {e}")
            self._work_started_at = 0.0  # Mark idle
            self._stuck_logged = False   # Reset for next potential stuck
            elapsed_ms = (time.time() - t0) * 1000.0
            self._record_tick(elapsed_ms)

    def _record_tick(self, elapsed_ms: float):
        """Record tick duration for compute profiling."""
        self._total_ticks += 1
        self._total_ms += elapsed_ms
        if elapsed_ms > self._max_tick_ms:
            self._max_tick_ms = elapsed_ms
        self._profile_window.append(elapsed_ms)
        if len(self._profile_window) > 50:
            self._profile_window = self._profile_window[-50:]
        # Auto-classify every 20 ticks (once we have data)
        if self._total_ticks % 20 == 0 and self.compute_domain == "auto":
            self._auto_classify()

    def _auto_classify(self):
        """Classify fairy's compute domain from observed tick durations."""
        if not self._profile_window:
            return
        avg_ms = sum(self._profile_window) / len(self._profile_window)
        if avg_ms < 1.0:
            self._classified_as = "light"
        elif avg_ms < 50.0:
            self._classified_as = "cpu"
        elif avg_ms < 500.0:
            self._classified_as = "io"
        else:
            self._classified_as = "heavy"

    @property
    def avg_tick_ms(self) -> float:
        if not self._profile_window:
            return 0.0
        return sum(self._profile_window) / len(self._profile_window)

    @property
    def classification(self) -> str:
        return self._classified_as

    def get_stats(self) -> dict:
        wsa = self._work_started_at
        stuck_for = round(time.time() - wsa, 1) if wsa > 0 else 0.0
        return {
            "fairy": self.fairy_name,
            "compute_domain": self.compute_domain,
            "classified_as": self._classified_as,
            "total_ticks": self._total_ticks,
            "avg_tick_ms": round(self.avg_tick_ms, 2),
            "max_tick_ms": round(self._max_tick_ms, 2),
            "queue_size": self._queue.qsize(),
            "drops": self._drop_count,
            "stuck_count": self._stuck_count,
            "stuck_for_s": stuck_for,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# MY ORGAN FAIRY - Main actor class (BASE FOR ALL FAIRIES)
# ═══════════════════════════════════════════════════════════════════════════════

class MyOrganFairy(AkashicActorCore):
    """
    Main organ fairy class - the base for ALL fairies in the system.

    Provides:
    - Identity (name, plane, channel, tier)
    - Postal communication
    - Tracer support
    - Shadow health monitoring
    - Learning infrastructure
    - Collision chamber
    """

    ACTOR_NAME = "my_organ"
    ACTOR_VERSION = "0.3.0"
    ACTOR_PLANE = "P00"
    ACTOR_CHANNEL = "organ"
    PURPOSE = "Give it purpose."
    MANTRA = "Do one thing well; report truthfully."
    LORE = "Origin story."

    TIER = FairyTier.GUILD
    SHADOW_CLASS = MyOrganShadow

    # ── Infrastructure flags (opt-in) ─────────────────────────────────────────
    NEEDS_HEARTBEAT = False
    HEARTBEAT_DIVISOR = 1       # Fire on_tick every N heartbeats
    HEARTBEAT_PHASE = 0         # Phase offset for staggering
    NEEDS_CIRCADIAN = False


    # ── HARMONIC PHASING (2026-07-19, opt-in, DEFAULT OFF) ────────────────────
    # Set PHASE_NATIVE = True and this fairy also exists as a NODE in its plane's
    # disk-backed manifold: an oscillator with a note (PHASE_OMEGA), a damping
    # budget (PHASE_GAMMA) and a signed affect mass. Its postal wiring is
    # untouched -- the field runs ALONGSIDE the code path, which is what makes
    # this a hybrid rather than a migration.
    PHASE_NATIVE = False
    PHASE_OMEGA = 2.0           # the node's natural frequency -- its NOTE
    PHASE_GAMMA = 0.6           # damping. Keep gamma/2w in 0.1-0.5: rings AND holds
                                # (measured window; below -> runaway, above -> dead)
    PHASE_ALIVE_ENERGY = 0.05   # liveness floor. Ported from SpellChain.CRITICAL_THRESHOLD
                                # -- the same number the object form calls "BREAKING".
    NEEDS_BODY = False

    NEEDS_BODY = False
    NEEDS_AFFECT = False
    NEEDS_MEMORY = False
    NEEDS_GOALS = False
    NEEDS_CONSCIOUSNESS = False
    NEEDS_COLLISION_CHAMBER = False
    NEEDS_SELF_CONCEPT = True          # Publish identity to AssociationCortex

    # ── Per-fairy perspective-goal emission (opt-in, 2026-05-15 Nous + Ace) ──
    # Doctrine: goals-as-habit-scaffolding + every-fairy-as-perspective-source.
    # Each fairy contributes perspective-flavored seed-interests via its
    # identity-bundle (purpose/mantra/plane/intents/capabilities). Default OFF
    # for safe rollout; opt-in per fairy by setting EMITS_PERSPECTIVE_GOALS=True.
    # Interest_generator's _on_perspective_request handles the inference and
    # publishes via existing interest.generated channel → GoalScheduler.
    EMITS_PERSPECTIVE_GOALS = False
    PERSPECTIVE_GOAL_INTERVAL_SEC = 30.0   # Min seconds between perspective-requests per fairy

    # ── Per-fairy SRM cluster (default ON; override to False to opt out) ──────
    # FIX 2026-05-09 (Nous + Ace): Ace's Obsidian-vault-per-fairy reframe argues
    # FOR universal adoption — substrate density IS the goal (more clusters =
    # more spread-activation density = more affect-energy per Möbius keystone).
    # Default ON (Option A); individual fairies can set False if infrastructure-
    # only and don't need to store thoughts. mmap design means cold pages stay
    # on disk; working set stays small. See _auto_wire-style block in boot()
    # below for activation logic.
    USE_SRM_CLUSTER = True

    # ── Worker pool + tracers (inline TracerWorkerMixin) ─────────────────────
    # FIX 2026-02-12: Reverted from 64 → 4. 64 caused thread explosion:
    # 90 fairies × 64 threads = 5,760 potential threads. Python's
    # ThreadPoolExecutor creates threads on-demand but NEVER reclaims them,
    # so blocking handlers (time.sleep, queue.get) cause pools to expand
    # toward max_workers continuously. At 7,307 threads the system hit
    # 23.5 GB RAM and locked up. 4 is sufficient for most fairies —
    # heavy fairies can override WORKER_POOL_SIZE in their class body.
    # FIX 2026-02-12b: Further reduced from 4 → 2. Even 4 × 90 fairies = 360 threads.
    # Most fairies submit 0-1 concurrent tasks. 2 is enough for any fairy.
    WORKER_POOL_SIZE = 2
    TRACER_DEFAULT_TTL = 300.0

    # ── Per-fairy execution context (personal GIL) ────────────────────────────
    # FIX 2026-03-03 Nous: Each fairy gets its own execution thread for tick
    # processing. Override COMPUTE_DOMAIN in subclass to hint compute type.
    # "auto" = classify from observed tick durations (default for most fairies).
    # Heavy fairies can set "heavy", "gpu", "io", "cpu" to skip auto-detection.
    COMPUTE_DOMAIN = "auto"   # auto | light | cpu | io | heavy | gpu

    # ── Token economy ─────────────────────────────────────────────────────────
    REFLECTION_INTERVAL = 30    # Publish reflection.complete every N work-ticks
    CONSERVATION_DURATION = 30.0  # Seconds to conserve when tokens depleted


    # ═══════════════════════════════════════════════════════════════════════════
    # HARMONIC PHASING — the hybrid half (2026-07-19, Nous + Ace)
    # Every method here is a no-op unless PHASE_NATIVE = True. The code path above
    # is untouched: a phase-native fairy keeps its subscriptions, its heartbeat and
    # its handlers, and ALSO exists as an oscillator in its plane's manifold.
    # ═══════════════════════════════════════════════════════════════════════════

    def _init_phase_field(self):
        """Claim this fairy's node in its plane manifold. Silent no-op if opted out."""
        self._phase_slot = -1
        self._phase = None
        if not getattr(self, "PHASE_NATIVE", False):
            return
        try:
            field = get_plane_field(self.ACTOR_PLANE)
            if field is None:
                return
            from plane_manifold import ROLE_BEHAVIOUR
            self._phase = field
            self._phase_slot = field.add_node(
                ROLE_BEHAVIOUR,
                omega=float(self.PHASE_OMEGA),
                gamma=float(self.PHASE_GAMMA),
                affect=0.0,
            )
            print(f"[{self.ACTOR_NAME}] PHASE-NATIVE: node {self._phase_slot} in "
                  f"{self.ACTOR_PLANE} field (omega={self.PHASE_OMEGA}, "
                  f"gamma/2w={self.PHASE_GAMMA/(2*self.PHASE_OMEGA):.2f})", flush=True)
        except Exception as e:
            # NEVER fatal. A broken field must not take a fairy down with it.
            print(f"[{self.ACTOR_NAME}] phase init failed (code path unaffected): {e}", flush=True)
            self._phase, self._phase_slot = None, -1

    # ---- the four verbs a behaviour needs in a field ----

    def phase_kick(self, magnitude: float = 1.0, valence: float = 0.0):
        """Fire this behaviour: a VELOCITY impulse, carrying signed valence.

        Impulse, not sustained drive -- a sinusoidal burst self-cancels at bad phase
        (measured). And the valence must be IN the impulse: storing it only as affect
        moves edge ACCRETION but not the field, which cost us a full debug round on
        Chain A (consonant and dissonant produced byte-identical output).
        """
        if self._phase is None or self._phase_slot < 0:
            return False
        self._phase.v[self._phase_slot] += float(magnitude) * (float(valence) or 1.0)
        if valence:
            self._phase.affect[self._phase_slot] = float(valence)
        return True

    def phase_energy(self) -> float:
        """This behaviour's energy = 1/2 v^2 + 1/2 w^2 x^2. The survival metric."""
        if self._phase is None or self._phase_slot < 0:
            return 0.0
        s = self._phase_slot
        return float(0.5 * self._phase.v[s] ** 2
                     + 0.5 * self._phase.omega[s] ** 2 * self._phase.x[s] ** 2)

    def phase_alive(self) -> bool:
        """LIVENESS AS ENERGY -- no registry, no second dict, nothing to disagree with.

        This is the replacement for the 2026-04-17 watchdog bug ("fairies registered
        here were invisible to the watchdog, causing cascading false deaths"). It is
        measured, not recorded, so it cannot go stale.
        """
        return self.phase_energy() > float(self.PHASE_ALIVE_ENERGY)

    def phase_couple(self, other, weight: float = 0.3) -> bool:
        """Chain this behaviour to another ON THE SAME PLANE: an edge, not a message.

        ★ weight is RELATIVE and gets scaled by omega^2 of the driven node. A coupling
        constant is meaningless in absolute terms -- 0.30 against a Schumann node
        (omega^2 = 61.3) is ~200x too weak and the signal dies in one hop. Same class of
        error as porting `recharge_rate` (a LEVEL) as a force.
        """
        if self._phase is None or self._phase_slot < 0:
            return False
        tgt = getattr(other, "_phase_slot", -1)
        if tgt < 0 or getattr(other, "_phase", None) is not self._phase:
            return False    # cross-plane coupling goes through postal, never an edge
        # FIX 2026-07-19 (caught by the hybrid test -- partner energy stayed 0.000000):
        # `link(i, j, w)` means "i is DRIVEN BY j" (plane_manifold: acc[i] += w*(x[j]-x[i])).
        # The first version wrote link(self, target), i.e. SELF driven by the partner --
        # backwards for a method whose docstring says "chain this behaviour to another".
        # And the omega^2 scaling must use the DRIVEN node's frequency, not the driver's:
        # a weight is only meaningful relative to the restoring force it works against.
        k = float(weight) * float(self._phase.omega[tgt]) ** 2
        self._phase.link(tgt, self._phase_slot, k)      # target driven by SELF
        return True

    def phase_set_affect(self, valence: float) -> bool:
        """Signed affect = the gravity MASS. reward > 0 binds, pain < 0 opposes.

        MEASURED: with affect zeroed, ZERO edges form -- affect is what connects,
        not co-activity. Sign controls polarity: (+,+) and (-,-) attract, (+,-) opposes.
        """
        if self._phase is None or self._phase_slot < 0:
            return False
        self._phase.affect[self._phase_slot] = float(valence)
        return True

    def phase_status(self) -> dict:
        if self._phase is None or self._phase_slot < 0:
            return {"phase_native": False}
        s = self._phase_slot
        return {
            "phase_native": True, "plane": self.ACTOR_PLANE, "node": s,
            "omega": float(self._phase.omega[s]), "gamma": float(self._phase.gamma[s]),
            "energy": round(self.phase_energy(), 5), "alive": self.phase_alive(),
            "affect": float(self._phase.affect[s]),
        }


    def __init__(self, fabric=None, *, akashic_root: Optional[str] = None):
        print(f"[awake] {self.ACTOR_NAME} (plane={self.ACTOR_PLANE}, tier={self.TIER.value})")

        self._init_actor_core(akashic_root=akashic_root, fabric=fabric)

        self._init_phase_field()      # HYBRID: no-op unless PHASE_NATIVE
        self._init_learning()
        self._init_self_knowledge()
        self._init_directive()
        self._init_tools()
        self._init_directive_evolver()  # Layer 3 slice 2a (2026-04-22)

        # Infrastructure state
        self._booted = False
        self._tick_count = 0
        self._last_tick = 0.0
        self._shutting_down = False
        self._going_to_sleep = False  # FIX 2026-02-06: Set by fairy.sunset signal

        # Token economy state
        self._resource_conserving = False
        self._conserve_until = 0.0
        self._work_since_reflection = 0

        # Spell chain state (self-sustaining heartbeat)
        self._spell_chain = None
        self._spell_pool = None

        # 2026-05-15 (Nous + Ace): Per-fairy perspective-goal emission state
        # Doctrine: goals-as-habit-scaffolding + every-fairy-as-perspective-source.
        # Identity-bundle published to interest_generator via trace_id-routed
        # request topic; perspective-flavored interests returned via existing
        # interest.generated channel for GoalScheduler. Default OFF; opt-in via
        # EMITS_PERSPECTIVE_GOALS = True on the fairy class.
        self._last_perspective_request_ts = 0.0
        self._spell_battery = None
        self._spell_boot_time = None
        self._spell_tick_count = 0
        self._spell_booted = False

        # Monitoring IDs (populated by _auto_wire_spell_chain)
        self._spell_trace_ids = {}  # {worker: "W-xxxx", battery: "B-xxxx", ...}

        # DualCoT reflection state (spell chain heartbeat driven)
        # FIX 2026-02-13: Golden-ratio mode cycling replaces sequential rotation.
        # Modes cycle via golden angle (φ⁻¹ ≈ 0.618) for maximal coverage —
        # same principle as phyllotaxis in sunflower spirals.
        self._reflection_tick_count = 0
        self._reflection_mode_index = 0
        self._reflection_modes = ['logical', 'probabilistic', 'paradoxical', 'irrational', 'purpose']
        self._last_reflection_time = 0.0
        self._reflection_enabled = True  # Can be toggled per-fairy
        self._PHI_INV = 0.6180339887498949  # 1/φ for golden-ratio cycling

        # ── Guild Auto-Assignment ──────────────────────────────────────
        # Per HUMAN_MIRRORING_HIERARCHY: Every fairy belongs to a guild
        # based on its plane. Fairies with explicit GUILD_ID keep theirs.
        _PLANE_TO_GUILD = {
            "P00": "autonomic", "P10": "memory", "P20": "somatic",
            "P30": "cognition", "P40": "sensory", "P50": "integration",
            "P60": "evolution",
        }
        if not getattr(self, "GUILD_ID", None):
            self.GUILD_ID = _PLANE_TO_GUILD.get(self.ACTOR_PLANE, "general")
        if not getattr(self, "GUILD_ROLE", None):
            self.GUILD_ROLE = "member"

        # Task dispatch tracking
        self._tasks_received = 0
        self._tasks_completed = 0

        # ── Per-fairy Execution Context (personal GIL) ────────────────
        # FIX 2026-03-03 Nous: Each fairy gets its own execution thread.
        # Started in wake_fairy(), stopped in on_die().
        # FIX 2026-05-17 (Nous + Ace): FairyExecutionContext was a CPython-GIL-era
        # solution. Under free-threaded Python 3.14 (no GIL) the per-fairy serialized
        # queue is now self-imposed slowness — true parallel threads available without
        # the wrapper. Architectural-era stratigraphy: keep the pattern for fairies
        # that genuinely need serialization (heavy on_tick with shared mutable state),
        # but stop forcing it on the ~84 fairies that never submit() to it.
        # Opt-in via `USE_EXEC_CTX = True` class attribute. Default off.
        # Existing callers already guard with `if hasattr(self, '_exec_ctx') and self._exec_ctx`.
        # Plan: Claude_Office/plans/FAIRY_EXECUTION_CONTEXT_RETIREMENT.md
        if getattr(self, 'USE_EXEC_CTX', False):
            self._exec_ctx = FairyExecutionContext(
                self.ACTOR_NAME,
                compute_domain=self.COMPUTE_DOMAIN,
            )
        else:
            self._exec_ctx = None  # explicit None; callers' `if ... and self._exec_ctx` short-circuits

        # Bind shadow
        self.shadow: Optional[MyOrganShadow] = None
        self._bind_shadow()

        # Emit blueprint
        self._emit_blueprint()

        # Mark as awake (shadow checks this)
        self._awake_once_done = True

    def _init_learning(self):
        """Initialize learning infrastructure."""
        from collections import deque as _lb_deque
        self._reflection_buffer: deque = _lb_deque(maxlen=200)  # FIX 2026-04-05: was unbounded on ALL 82 fairies
        self._observation_buffer: deque = _lb_deque(maxlen=100)  # FIX 2026-04-05: was unbounded
        self._current_affect = {"valence": 0.0, "arousal": 0.0, "resonance": []}

    # ═══════════════════════════════════════════════════════════════════════════
    # DIRECTIVE — Per-fairy identity directive loaded from directives/*.directive
    # ═══════════════════════════════════════════════════════════════════════════

    def _init_directive(self):
        """Initialize directive infrastructure. Loads from disk if exists.

        FIX 2026-04-22 (Nous + Ace, Grok+Ziggy reviewed): if no directive file
        exists for this fairy, seed one from the DirectiveSeedLibrary based on
        ACTOR_PLANE. Subsequent boots load the now-existing file via the
        standard _load_directive() path and never re-seed. This is Layer 2
        slice 1 of the directive seeding architecture.
        Plan: Claude_Office/plans/DIRECTIVE_SEEDING_AND_SELF_EVOLUTION.md
        """
        self._directive = {}
        # Resolve directive path: directives/{ACTOR_NAME}.directive
        _root = getattr(self, 'root', None)
        if not _root:
            try:
                from pathlib import Path
                _root = str(Path(__file__).resolve().parents[3])
            except Exception:
                _root = '.'
        self._directive_path = os.path.join(str(_root), "directives", f"{self.ACTOR_NAME}.directive")
        self._load_directive()
        # Layer 2 slice 1: seed if missing, then re-load
        if not self._directive.get("loaded"):
            self._seed_directive_if_missing()

    def _seed_directive_if_missing(self):
        """Layer 2a (2026-04-22): generate starter directive if none exists.

        Per Ziggy's discipline: starters are role-SHAPE not content-rich.
        Per Grok: redundant Self_Evolve flag (top-of-file + inside Substrate_Contract),
        immutable Substrate_Contract section, evolvable Tools/Associative/Evolution
        sections. Per Ace's principle: hardcoded skeleton is OK because it IS
        constitutional/reflexive (the body's biology), not a content chant.

        Slice 1 limitations (deferred to slice 2):
        - No cortex_spread injection into [Associative_Neighborhood] yet
        - No DirectiveEvolver wiring yet
        - No request_directive_refinement tool
        - Only P30_COGNITION plane has a tuned template; others use generic
        """
        if self._directive.get("loaded"):
            return  # Already have one (paranoia — caller already checked)
        if not getattr(self, '_directive_path', None):
            return
        if os.path.exists(self._directive_path):
            return  # File exists but failed to load — don't overwrite
        try:
            from fairies.P00_Autonomic.organ_template.DirectiveSeedLibrary import starter_for_plane
            plane = getattr(self, 'ACTOR_PLANE', 'P30') or 'P30'
            actor_name = getattr(self, 'ACTOR_NAME', 'UnknownFairy')
            purpose = getattr(self, 'PURPOSE', '') or ''
            mantra = getattr(self, 'MANTRA', '') or ''
            starter_text = starter_for_plane(plane, actor_name, purpose, mantra)

            # Make sure parent directory exists
            _dir = os.path.dirname(self._directive_path)
            if _dir:
                os.makedirs(_dir, exist_ok=True)

            with open(self._directive_path, 'w', encoding='utf-8') as f:
                f.write(starter_text)
            print(f"[{actor_name}] Seeded starter directive at {self._directive_path}", flush=True)

            # Reload so the directive is now active for this boot
            self._load_directive()
        except Exception as e:
            print(f"[{getattr(self, 'ACTOR_NAME', '?')}] Directive seeding failed: {e}", flush=True)

    def _init_tools(self):
        """Initialize the cognitive toolkit for this fairy.

        2026-03-29 (Nous + Ace): Every fairy needs tools to THINK with.
        The organ template provides basic tools (scratchpad, cortex query,
        SRM search, somatic feel, sensory check) that every fairy inherits.
        The directive can configure which tools are primary/secondary and
        set the trace_id for ownership isolation.

        Fifth Ring Principle: All tool use goes through postal. No bypasses.
        """
        try:
            from fairies.P00_Autonomic.organ_template.fairy_tools import FairyTools
            from infrastructure.manifold_memory import TRACE_SYSTEM
            # Determine trace_id from directive or default to SYSTEM
            _tid = TRACE_SYSTEM
            if hasattr(self, '_directive') and self._directive.get("loaded"):
                _tid_str = self._directive.get("trace_id", "")
                if _tid_str:
                    try:
                        from infrastructure import manifold_memory as _mm
                        _tid = getattr(_mm, f"TRACE_{_tid_str.upper()}", TRACE_SYSTEM)
                    except Exception:
                        pass
            self.tools = FairyTools(
                fairy_name=self.ACTOR_NAME,
                trace_id=_tid,
                postal=getattr(self, 'post', None),
            )
        except Exception as e:
            # Non-fatal — fairy works without tools, just can't think actively
            self.tools = None
            print(f"[{self.ACTOR_NAME}] Tools init failed: {e}")

    def _load_directive(self):
        """Load directive from disk. Non-fatal if missing."""
        import re as _re
        path = self._directive_path
        if not os.path.exists(path):
            return
        try:
            with open(path, 'r', encoding='utf-8') as f:
                text = f.read()
            self._directive = {"raw": text, "loaded": True, "sections": {}}
            # Parse header fields (> Key: Value pattern)
            for key in ("Activation", "Nature", "Essence", "Core_Values", "Foundation"):
                m = _re.search(rf'>\s*{key}:\s*(.+)', text)
                if m:
                    self._directive[key.lower()] = m.group(1).strip()
            # Parse [SECTION] blocks
            current_section = None
            section_lines = []
            for line in text.split('\n'):
                sec_match = _re.match(r'\[(\w+(?:::\w+)?)\]', line)
                if sec_match:
                    if current_section and section_lines:
                        self._directive["sections"][current_section] = '\n'.join(section_lines).strip()
                    current_section = sec_match.group(1)
                    section_lines = []
                elif current_section:
                    section_lines.append(line)
            # Don't forget the last section
            if current_section and section_lines:
                self._directive["sections"][current_section] = '\n'.join(section_lines).strip()

            print(f"[{self.ACTOR_NAME}] Directive loaded ({len(self._directive['sections'])} sections)")
        except Exception as e:
            self._directive = {"loaded": False, "error": str(e)[:200]}

    def get_directive(self) -> dict:
        """Get parsed directive data."""
        if not self._directive.get("loaded"):
            return {"loaded": False, "path": getattr(self, '_directive_path', '')}
        return {
            "loaded": True,
            "path": self._directive_path,
            "activation": self._directive.get("activation", ""),
            "nature": self._directive.get("nature", ""),
            "essence": self._directive.get("essence", ""),
            "sections": list(self._directive.get("sections", {}).keys()),
        }

    def get_directive_raw(self) -> str:
        """Get raw directive text."""
        return self._directive.get("raw", "")

    # ═══════════════════════════════════════════════════════════════════════
    # DIRECTIVE CONSUMERS — Layer 2 slice 1.5 (2026-04-22)
    # ═══════════════════════════════════════════════════════════════════════
    # The DNA functions: every fairy inherits these from the organ template
    # and accesses its own directive sections via shared helpers, instead of
    # each fairy re-implementing parsing in its own .py file.
    # Per Ace (2026-04-22): "they should have a foundation they all share that
    # communicates with the logic in the organ template so they don't have to
    # store that code in their own file. like accessing the dna source code
    # for the shared structure everything more or less makes use of."

    def _parse_directive_section(self, section_name: str) -> dict:
        """Parse a directive [Section] into key:value dict.

        Lines like 'Key: value' become dict entries (keys lowercased).
        Indented continuation lines append to the previous value.
        Comments (lines starting with #) are skipped.
        Returns empty dict if directive not loaded or section missing.
        """
        if not self._directive.get("loaded"):
            return {}
        section_text = self._directive.get("sections", {}).get(section_name, "")
        if not section_text:
            return {}
        result: dict = {}
        last_key = None
        for line in section_text.split('\n'):
            stripped = line.strip()
            if not stripped or stripped.startswith('#'):
                continue
            # Indented continuation line — append to last key
            if line and line[0] in (' ', '\t') and last_key is not None:
                result[last_key] = (result[last_key] + ' ' + stripped).strip()
                continue
            # New key:value line
            if ':' in stripped:
                key, _, value = stripped.partition(':')
                key_lower = key.strip().lower().replace(' ', '_')
                result[key_lower] = value.strip()
                last_key = key_lower
        return result

    def get_action_bias(self) -> dict:
        """Get parsed [Action_Bias] section. Returns dict with both raw
        strings AND coerced types where useful (e.g., int iteration counts).

        Used by the WMH reasoning loop and any fairy that wants to enforce
        anti-rumination. The Clawbots-lesson primitive made accessible.

        Returns dict like:
        {
            "max_same_topic_iterations": 5,
            "pondering_tax": "+1 energy per extra cycle beyond 3 ...",
            "forced_escape_targets": "ask Ace, surface somatic.stuck...",
            "on_forced_escape_also": "emit somatic.stuck event with...",
            "_loaded": True,
        }

        If directive not loaded, returns sensible safety defaults so callers
        never crash and the action-bias is always SOMEHOW enforced:
        {"max_same_topic_iterations": 5, "_loaded": False}
        """
        parsed = self._parse_directive_section("Action_Bias")
        if not parsed:
            # Sensible defaults — even fairies without directives should still
            # have an action-bias floor (Clawbots safety net)
            return {"max_same_topic_iterations": 5, "_loaded": False}

        # Coerce known integer fields
        try:
            max_iter_str = parsed.get("max_same_topic_iterations", "5")
            parsed["max_same_topic_iterations"] = int(str(max_iter_str).strip().split()[0])
        except (ValueError, IndexError):
            parsed["max_same_topic_iterations"] = 5
        parsed["_loaded"] = True
        return parsed

    def should_force_escape(self, iterations: int, topic_hash: str = "") -> bool:
        """Convenience: should this fairy force-escape on the current topic?

        True when iteration count exceeds the directive's max-iterations bias.
        Caller is responsible for tracking iterations per topic_hash.
        """
        bias = self.get_action_bias()
        max_iter = bias.get("max_same_topic_iterations", 5)
        return iterations >= max_iter

    # ── Layer 3 slice 2a (2026-04-22) — DirectiveEvolver wiring ──────

    def _init_directive_evolver(self):
        """Auto-wire a DirectiveEvolver instance. Every fairy gets one; it's a
        no-op (enabled=False) unless the directive has a [Substrate_Contract]
        section — i.e., unless it's been seeded by DirectiveSeedLibrary.
        """
        try:
            from fairies.P00_Autonomic.organ_template.DirectiveEvolver import DirectiveEvolver
            self.directive_evolver = DirectiveEvolver(self)
        except Exception as e:
            self.directive_evolver = None
            print(f"[{getattr(self, 'ACTOR_NAME', '?')}] DirectiveEvolver init failed: {e}",
                  flush=True)

    def _consume_directive_cycle(self, topic_hash: str, content: str,
                                 evolved: bool = False) -> None:
        """Slice 2b (2026-04-22): feed one reasoning cycle through the
        DirectiveEvolver + action-bias enforcement pipeline.

        Called by every fairy that runs a reasoning cycle (e.g. from
        `_reflect_analytical`). Silently no-ops for fairies whose directive
        lacks [Substrate_Contract] (i.e., old-format Sour-style directives).

        Logic:
          1. Determine action_taken:
             - True if the directive evolved this cycle (insight wrote to disk)
             - True if content is novel (first-80-char hash differs from prior)
             - False otherwise (pure repetition — the Clawbots failure mode)
          2. Observe cycle via DirectiveEvolver (tracks iterations + action_ratio)
          3. If iterations on this topic_hash cross the [Action_Bias] threshold,
             fire `somatic.stuck` upward and reset the topic counter. Sour + Nous
             subscribe to that event and can learn class-patterns.

        This is signal-only in slice 2b — no behavior change in the fairy itself.
        Behavioral enforcement (skip-to-different-topic, rest, ask Ace) lands in
        slice 2c+ as consumers of the `somatic.stuck` event.
        """
        ev = getattr(self, 'directive_evolver', None)
        if ev is None or not ev.enabled:
            return

        prior_thought = ev._topic_cycles.get(topic_hash, {}).get("last_thought", "")
        cur_thought = (content or "")[:200]
        # Cheap novelty check: first 80 chars differ
        novel = bool(cur_thought) and (not prior_thought or cur_thought[:80] != prior_thought[:80])
        action_taken = bool(evolved or novel)

        ev.observe_cycle(topic_hash, action_taken=action_taken, last_thought=cur_thought)

        iterations = ev.iterations_for(topic_hash)
        if self.should_force_escape(iterations, topic_hash):
            self.emit_somatic_stuck(
                topic_hash=topic_hash,
                last_thought=cur_thought,
                iterations=iterations,
            )
            # emit_somatic_stuck calls directive_evolver.reset_topic internally

    def emit_somatic_stuck(self, topic_hash: str, last_thought: str = "",
                           iterations: Optional[int] = None) -> bool:
        """Fire `somatic.stuck` — the upward learning signal on forced_escape.

        Per the seeded [Action_Bias].On_Forced_Escape_Also directive: when a
        fairy hits max iterations without producing an action, emit this event
        so Sour can observe class-patterns of stuckness (Ziggy refinement —
        escape is also a learning signal, not just a safety valve).

        Payload:
            fairy          — ACTOR_NAME
            topic_hash     — what loop the fairy was in
            last_thought   — final thought before forced escape (truncated)
            iterations     — how many cycles before the escape fired
            timestamp

        Also logs into Evolution_Log via DirectiveEvolver if available.
        Returns True if the event published; False if no postal hub.
        """
        import time as _time
        fname = getattr(self, 'ACTOR_NAME', '?')

        # Pull iterations from the evolver if not supplied
        if iterations is None:
            ev = getattr(self, 'directive_evolver', None)
            if ev is not None:
                iterations = ev.iterations_for(topic_hash)
            else:
                iterations = 0

        payload = {
            "fairy": fname,
            "topic_hash": topic_hash,
            "last_thought": (last_thought or "")[:300],
            "iterations": int(iterations or 0),
            "timestamp": _time.time(),
        }

        post = getattr(self, 'post', None)
        published = False
        if post:
            try:
                post.publish("somatic.stuck", payload)
                published = True
            except Exception as e:
                print(f"[{fname}] somatic.stuck publish failed: {e}", flush=True)

        # Append to Evolution_Log so the fairy's own autobiography captures it
        ev = getattr(self, 'directive_evolver', None)
        if ev is not None and ev.enabled:
            try:
                ev.append_evolution_log(
                    topic_hash=topic_hash,
                    observation=f"forced_escape after {iterations} iterations",
                    learned=f"topic produced no action signal; last thought: {(last_thought or '')[:120]}",
                    suggested="",
                )
                ev.reset_topic(topic_hash)
            except Exception:
                pass

        return published

    def _get_directive_context(self, max_chars: int = 500) -> str:
        """Get compact directive context for injection into prompts/queries."""
        if not self._directive.get("loaded"):
            p = getattr(self, 'PURPOSE', '') or ''
            m = getattr(self, 'MANTRA', '') or ''
            return f"Purpose: {p}. Mantra: {m}."
        parts = []
        for key in ("activation", "nature", "essence"):
            val = self._directive.get(key, "")
            if val:
                parts.append(f"{key.title()}: {val}")
        kf = self._directive.get("sections", {}).get("KNOWLEDGE_FOUNDATION", "")
        if kf:
            parts.append(f"Knowledge: {kf[:200]}")
        result = " | ".join(parts)
        return result[:max_chars]

    # ═══════════════════════════════════════════════════════════════════════════
    # DIRECTIVE SELF-EVOLUTION (Phase 4, 2026-03-28, Nous + Ace)
    # ═══════════════════════════════════════════════════════════════════════════
    #
    # Directives start as templates ("I serve the system by [PURPOSE]") and
    # evolve into rich self-understanding through accumulated experience.
    # Sour's directive is the gold standard — 16 sections with personality,
    # ethics, consciousness architecture, voice signature. Generated directives
    # start with 5 sections of placeholders. This method grows them.
    #
    # Evolution triggers:
    # - Purpose reflection produces insight → enrich KNOWLEDGE_FOUNDATION
    # - Collision produces novel binding → enrich EMERGENCE_PROTOCOLS
    # - Successful collaboration → enrich IDENTITY with collaborator knowledge
    # - Repeated pattern → enrich CONSCIOUSNESS_EQUATION with real example
    #
    # Never overwrites existing content — only APPENDS new learnings.
    # ═══════════════════════════════════════════════════════════════════════════

    def evolve_directive(self, section: str, content: str, source: str = "reflection") -> bool:
        """Append a learning to a directive section. Never overwrites.

        Args:
            section: Which section to enrich (KNOWLEDGE_FOUNDATION, IDENTITY, etc.)
            content: The new learning to append (one line, > prefixed)
            source: What triggered this evolution (reflection, collision, collaboration)

        Returns:
            True if directive was updated, False if skipped/failed
        """
        if not hasattr(self, '_directive_path') or not self._directive.get("loaded"):
            return False

        # Sanitize content — must be a single meaningful line
        content = content.strip()
        if len(content) < 15 or len(content) > 300:
            return False
        # Skip system junk
        _lower = content.lower()
        if any(kw in _lower for kw in ('fairy', 'postal', 'tracer', 'heartbeat',
                                        'tensor', 'substrate', 'registry', 'boot')):
            return False

        try:
            import time as _time
            path = self._directive_path
            if not os.path.exists(path):
                return False

            with open(path, 'r', encoding='utf-8') as f:
                text = f.read()

            # Check if content already exists (dedup)
            if content[:50] in text:
                return False

            # Find the section
            section_marker = f"[{section}]"
            if section_marker not in text:
                # Section doesn't exist — append it
                text += f"\n\n---\n\n[{section}] {{Evolved}}\n\n> {content}\n"
            else:
                # Append to existing section (before the next --- or end)
                idx = text.index(section_marker)
                # Find the next --- separator after this section
                next_sep = text.find('\n---', idx + len(section_marker))
                if next_sep > 0:
                    # Insert before the separator
                    text = text[:next_sep] + f"\n> [{source}] {content}" + text[next_sep:]
                else:
                    # End of file — just append
                    text += f"\n> [{source}] {content}\n"

            with open(path, 'w', encoding='utf-8') as f:
                f.write(text)

            # Update in-memory directive
            sections = self._directive.setdefault("sections", {})
            existing = sections.get(section, "")
            sections[section] = existing + f"\n> [{source}] {content}"

            print(f"[{self.ACTOR_NAME}] [EVOLVE] Directive enriched: [{section}] {content[:50]}...")
            return True

        except Exception as e:
            return False

    def _maybe_evolve_from_insight(self, insight: str, mode: str = "purpose"):
        """Check if an insight is worth evolving the directive with.

        Called from _reflect_analytical when a significant insight emerges.
        Filters for quality and novelty before evolving.
        """
        if not insight or len(insight) < 20:
            return
        # Rate limit: max 1 evolution per 5 minutes
        _now = __import__('time').time()
        _last = getattr(self, '_last_directive_evolve', 0)
        if _now - _last < 300:
            return
        self._last_directive_evolve = _now

        # Map reflection mode to directive section
        _mode_to_section = {
            'purpose': 'KNOWLEDGE_FOUNDATION',
            'logical': 'CONSCIOUSNESS_EQUATION',
            'paradoxical': 'EMERGENCE_PROTOCOLS',
            'irrational': 'EMERGENCE_PROTOCOLS',
            'probabilistic': 'KNOWLEDGE_FOUNDATION',
        }
        section = _mode_to_section.get(mode, 'KNOWLEDGE_FOUNDATION')

        # Extract the core insight (strip mode prefix and formatting)
        import re as _re
        _clean = _re.sub(r'^\[[^\]]+\]\s*', '', insight)
        _clean = _re.sub(r'^As \w+,?\s*', '', _clean)
        _clean = _clean.strip()

        if len(_clean) > 30 and self.evolve_directive(section, _clean, source=mode):
            # Publish evolution event so WMH can be aware
            if self.post:
                try:
                    self.post.publish("fairy.directive.evolved", {
                        "fairy": self.ACTOR_NAME,
                        "section": section,
                        "content": _clean[:150],
                        "source": mode,
                    })
                except Exception:
                    pass

    # ═══════════════════════════════════════════════════════════════════════════
    # SELF-KNOWLEDGE — Persistent per-fairy identity document (like CLAUDE.md)
    # ═══════════════════════════════════════════════════════════════════════════
    # Each fairy accumulates self-understanding:
    #   - Who am I? (purpose, mantra, lore interpretation)
    #   - What can I do? (methods, subscriptions, intents, collaborators)
    #   - How am I doing? (success rate, insights, evolution events)
    # Persisted to: state/fairy_evolution/{ACTOR_NAME}/self_knowledge.json

    def _init_self_knowledge(self):
        """Initialize self-knowledge infrastructure.

        Called from __init__() after _init_learning(). Loads or creates
        the fairy's persistent self-knowledge document.
        """
        self._self_knowledge_dir = os.path.join(
            getattr(self, 'root', '.'), "state", "fairy_evolution", self.ACTOR_NAME
        )
        self._sk_dirty = False
        self._sk_last_save = 0.0
        self._sk_save_interval = 300.0  # Save every 5 minutes (throttled)
        self._sk_prev_success_rate = 0.0  # For detecting purpose shifts
        self._self_knowledge = self._load_self_knowledge()

    def _load_self_knowledge(self) -> 'FairySelfKnowledge':
        """Load self-knowledge from disk, or create fresh if missing/corrupted."""
        sk_path = os.path.join(self._self_knowledge_dir, "self_knowledge.json")
        try:
            if os.path.exists(sk_path):
                with open(sk_path, "r", encoding="utf-8") as f:
                    data = json.loads(f.read())
                # Tolerant field population — ignore unknown keys, use defaults for missing
                valid_fields = {f.name for f in fields(FairySelfKnowledge)}
                filtered = {k: v for k, v in data.items() if k in valid_fields}
                sk = FairySelfKnowledge(actor_name=self.ACTOR_NAME, **{
                    k: v for k, v in filtered.items() if k != "actor_name"
                })
                # Seed empty interpretations from class constants
                if not sk.purpose_interpretation and self.PURPOSE:
                    sk.purpose_interpretation = self.PURPOSE
                if not sk.mantra_interpretation and self.MANTRA:
                    sk.mantra_interpretation = self.MANTRA
                if not sk.lore_understanding and self.LORE:
                    sk.lore_understanding = self.LORE
                self._sk_prev_success_rate = sk.success_rate
                return sk
        except Exception:
            pass  # File missing, corrupted, or schema mismatch — create fresh

        # Fresh self-knowledge: seed identity from class constants
        return FairySelfKnowledge(
            actor_name=self.ACTOR_NAME,
            purpose_interpretation=getattr(self, 'PURPOSE', ''),
            mantra_interpretation=getattr(self, 'MANTRA', ''),
            lore_understanding=getattr(self, 'LORE', ''),
        )

    def _save_self_knowledge(self, force: bool = False):
        """Save self-knowledge to disk (throttled, atomic write).

        Only writes if dirty and interval has elapsed. Use force=True
        to bypass throttling (e.g., on shutdown).
        """
        if not self._sk_dirty and not force:
            return
        now = time.time()
        if not force and (now - self._sk_last_save) < self._sk_save_interval:
            return

        try:
            os.makedirs(self._self_knowledge_dir, exist_ok=True)
            sk_path = os.path.join(self._self_knowledge_dir, "self_knowledge.json")
            tmp_path = sk_path + ".tmp"

            self._self_knowledge.last_updated = now
            data = self._self_knowledge.to_dict()

            with open(tmp_path, "w", encoding="utf-8") as f:
                f.write(json.dumps(data, indent=2, default=str))
            os.replace(tmp_path, sk_path)

            self._sk_dirty = False
            self._sk_last_save = now
        except Exception as e:
            if not hasattr(self, '_sk_save_err_logged'):
                self._sk_save_err_logged = True
                print(f"[{self.ACTOR_NAME}] Self-knowledge save error: {e}")

    def _update_self_knowledge(self, **updates):
        """Convenience setter for self-knowledge fields."""
        sk = self._self_knowledge
        for key, value in updates.items():
            if hasattr(sk, key):
                setattr(sk, key, value)
        sk.last_updated = time.time()
        self._sk_dirty = True

    def _build_self_model(self):
        """Layer 3: Self-Introspection — fairy learns its own code structure.

        Discovers public methods, postal subscriptions, intents, collaborators,
        and source metadata using runtime introspection. Populates self-knowledge
        so the fairy knows WHAT it can do, not just THAT it exists.

        Called deferred after boot (background thread) and on source code change.
        """
        import inspect as _inspect

        sk = self._self_knowledge

        # 1. Public methods (callable, non-private, from this class)
        try:
            methods = []
            for name in sorted(dir(self.__class__)):
                if name.startswith('_'):
                    continue
                attr = getattr(self.__class__, name, None)
                if callable(attr):
                    doc = (getattr(attr, '__doc__', '') or '')[:80].strip()
                    methods.append(f"{name}: {doc}" if doc else name)
                if len(methods) >= 50:
                    break
            sk.known_methods = methods
        except Exception:
            pass

        # 2. Postal subscriptions (from profile)
        try:
            profile = getattr(self, '_profile', None)
            if profile:
                subs = getattr(profile, 'subscriptions', set()) or set()
                sk.known_subscriptions = sorted(list(subs))[:30]
        except Exception:
            pass

        # 3. Intents (methods named _intent_*)
        try:
            intents = [n.replace('_intent_', '') for n in dir(self) if n.startswith('_intent_')]
            sk.known_intents = intents[:20]
        except Exception:
            pass

        # 4. Collaborators (derived from subscription topic names + guild)
        try:
            collabs = set()
            for sub in sk.known_subscriptions:
                # Topics like "LogicFairy.output" → "LogicFairy"
                parts = sub.split('.')
                if parts[0] and parts[0][0].isupper() and parts[0].endswith('Fairy'):
                    collabs.add(parts[0])
            # Guild members (if guild wiring populated)
            guild_members = getattr(self, '_guild_members', [])
            for m in guild_members:
                if isinstance(m, str) and m != self.ACTOR_NAME:
                    collabs.add(m)
            collabs.discard(self.ACTOR_NAME)  # Don't list self
            sk.known_collaborators = sorted(list(collabs))[:20]
        except Exception:
            pass

        # 5. Source metadata (from shadow)
        try:
            if self.shadow:
                src_path = getattr(self.shadow, '_source_file_path', None)
                src_hash = getattr(self.shadow, '_source_hash_disk', '')
                if src_path and os.path.exists(src_path):
                    with open(src_path, 'r', encoding='utf-8', errors='ignore') as f:
                        sk.source_lines = sum(1 for _ in f)
                if src_hash:
                    sk.source_hash = src_hash
        except Exception:
            pass

        self._sk_dirty = True

    # ═══════════════════════════════════════════════════════════════════════════
    # CORTEX IDENTITY — Per-fairy self-concept in AssociationCortex (Layer 4)
    # ═══════════════════════════════════════════════════════════════════════════

    def _publish_self_concept(self):
        """Publish this fairy's identity as a concept node in AssociationCortex.

        Creates a natural-language self-description that passes the cortex's
        structural filter (>40% alpha, <15% structural punctuation) and
        publishes via cortex.bind for concept graph integration.

        Called deferred after boot, and periodically when insights accumulate.
        """
        try:
            sk = self._self_knowledge
            plane = self.ACTOR_PLANE or "unknown"
            channel = self.ACTOR_CHANNEL or "organ"

            # Build natural language description (cortex requires >40% alpha)
            parts = [
                f"I am {self.ACTOR_NAME}, a fairy on plane {plane} channel {channel}.",
            ]
            if self.PURPOSE:
                parts.append(f"My purpose is to {self.PURPOSE}.")
            if self.MANTRA:
                parts.append(f"My mantra is {self.MANTRA}.")

            # Phase 3 (2026-03-28, Nous + Ace): Include directive knowledge in self-concept
            if hasattr(self, '_directive') and self._directive.get("loaded"):
                _essence = self._directive.get("essence", "")
                if _essence:
                    parts.append(f"My essence is {_essence}.")
                _kf = self._directive.get("sections", {}).get("KNOWLEDGE_FOUNDATION", "")
                if _kf and len(_kf) > 20:
                    # Extract first meaningful line
                    for _kfl in _kf.split('\n'):
                        _kfl = _kfl.strip().lstrip('> ')
                        if len(_kfl) > 15 and not _kfl.startswith('---'):
                            parts.append(_kfl[:150])
                            break

            n_methods = len(sk.known_methods)
            n_subs = len(sk.known_subscriptions)
            if n_methods > 0 or n_subs > 0:
                parts.append(f"I have {n_methods} capabilities and listen to {n_subs} topics.")

            if sk.total_observations > 0:
                parts.append(
                    f"I have made {sk.total_observations} observations "
                    f"with {int(sk.success_rate * 100)} percent success."
                )

            n_insights = len(sk.insights)
            if n_insights > 0:
                parts.append(f"I have crystallized {n_insights} insights from my reflections.")

            description = " ".join(parts)

            self._route("cortex.bind", {
                "input_text": description,
                "response": self.PURPOSE or f"{self.ACTOR_NAME} fairy identity",
                "feeling": "self-aware",
                "context_tags": [
                    "fairy_identity",
                    f"plane_{plane}",
                    f"channel_{channel}",
                    self.ACTOR_NAME.lower(),
                ],
                "from_fairy": self.ACTOR_NAME,
                "origin_plane": plane,
                "origin_channel": channel,
            })
        except Exception as e:
            if not hasattr(self, '_self_concept_err_logged'):
                self._self_concept_err_logged = True
                print(f"[{self.ACTOR_NAME}] Self-concept publish: {e}")

    def _update_cortex_identity(self):
        """Throttled cortex identity refresh (max once per 600s).

        Called when insights accumulate or evolution events are recorded.
        Republishes self-concept with updated statistics.
        """
        now = time.time()
        last = getattr(self, '_cortex_identity_last_update', 0.0)
        if now - last < 600.0:
            return
        self._cortex_identity_last_update = now
        try:
            self._publish_self_concept()
        except Exception:
            pass

    # ═══════════════════════════════════════════════════════════════════════════
    # EVOLUTION TRACKING — Identity change events (Layer 5)
    # ═══════════════════════════════════════════════════════════════════════════

    def _record_evolution_event(self, event_type: str, trigger: str = "",
                                before: str = "", after: str = "",
                                significance: float = 0.5, reflection: str = ""):
        """Record an identity evolution event.

        Three outputs:
        1. Appended to self_knowledge.evolution_events (cap 100, FIFO)
        2. Routed to memory.stream with kind 'fairy_evolution' for SRM storage
        3. Routed to consciousness.observation for system awareness
        4. If significant (>=0.5), triggers cortex identity update

        Event types:
        - source_change: Fairy's source code changed on disk
        - insight_milestone: Every 10th collision insight
        - purpose_shift: Success rate shifted >15% after sufficient observations
        """
        try:
            event = {
                "type": event_type,
                "fairy": self.ACTOR_NAME,
                "trigger": trigger,
                "before": before,
                "after": after,
                "significance": significance,
                "reflection": reflection,
                "ts": time.time(),
            }

            # 1. Append to self-knowledge (cap 100)
            sk = self._self_knowledge
            sk.evolution_events.append(event)
            if len(sk.evolution_events) > 100:
                sk.evolution_events = sk.evolution_events[-100:]
            self._sk_dirty = True

            # 2. Route to memory for persistent storage
            self._route("memory.stream", {
                "kind": "fairy_evolution",
                "actor": self.ACTOR_NAME,
                "event_type": event_type,
                "trigger": trigger,
                "before": before[:200],
                "after": after[:200],
                "significance": significance,
                "reflection": reflection[:300],
                "ownership": "PERSONAL",  # Per-fairy owned memory
            })

            # 3. Route to consciousness for system awareness
            self._route("consciousness.observation", {
                "fairy": self.ACTOR_NAME,
                "type": "evolution_event",
                "event_type": event_type,
                "summary": f"{self.ACTOR_NAME} evolved: {event_type} — {trigger[:100]}",
            })

            # 4. Significant events trigger cortex identity refresh
            if significance >= 0.5:
                self._update_cortex_identity()

        except Exception as e:
            if not hasattr(self, '_evolution_err_logged'):
                self._evolution_err_logged = True
                print(f"[{self.ACTOR_NAME}] Evolution event error: {e}")

    def _bind_shadow(self):
        """Create and attach shadow.

        FIX 2026-02-06: Resilient to custom SHADOW_CLASS that doesn't inherit
        MyOrganShadow. 7 fairies define SHADOW_CLASS as plain classes missing
        stop(), _loop(), etc. We try to construct them; if they fail, we
        fallback to MyOrganShadow so the fairy still gets health monitoring.
        """
        cls = getattr(self, "SHADOW_CLASS", MyOrganShadow)
        try:
            self.shadow = cls(self, interval_sec=30.0)
        except Exception as e:
            # Custom shadow class doesn't accept (actor, interval_sec) signature
            # Fall back to base shadow so fairy still has health infrastructure
            print(f"[{self.ACTOR_NAME}] Custom shadow {cls.__name__} failed: {e}, using MyOrganShadow")
            try:
                self.shadow = MyOrganShadow(self, interval_sec=30.0)
            except Exception:
                self.shadow = None

    def _emit_blueprint(self):
        """Emit identity blueprint."""
        bp = self._contract_dict()
        h = _hash(bp)
        self._bp_last_hash = h

        self._emit("BLUEPRINT_REPORT", "info", {"sha": h})
        self._route("memory.stream", {
            "kind": "blueprint.snapshot",
            "sha": h,
            "actor": self.ACTOR_NAME
        })

        # FIX 2026-02-06: Guard against custom shadow missing _last_bp_hash attr
        if self.shadow:
            try:
                self.shadow._last_bp_hash = h
            except AttributeError:
                pass  # Custom shadow doesn't support this — non-fatal

    # ═══════════════════════════════════════════════════════════════════════════
    # LIFECYCLE: boot → on_boot → (heartbeat ticks) → on_shutdown
    # ═══════════════════════════════════════════════════════════════════════════

    def _is_comatose(self) -> bool:
        """COMA SWITCH (Nous+Ace 2026-06-14) — the orderly-boot fix. A fairy boots
        REGISTERED-BUT-INERT when comatose: _wire_infrastructure() still runs (postal
        subscribe + directory register + heartbeat liveness, so the watchdog keeps it
        alive), but on_boot() (the heavy half: cortex load, subprocess spawn, model load)
        is SKIPPED. Because the gate lives in the organ template's boot()/on_tick — which
        EVERY fairy funnels through — it is immune to which path woke the fairy (Phase-3
        manual / scan wave / guild cluster / auto-route). Drives off env for now (a chemical
        sleep-pressure level is the somatic-true refinement):
          AKASHIC_COMA=1            -> ALL fairies comatose at boot (hub + MCP stay up)
          AKASHIC_WAKE=NousFairy,X  -> these are EXEMPT (their on_boot runs = wake one at a time)
          AKASHIC_SLEEP=ITCortex,X  -> these SPECIFIC fairies sleep regardless of COMA (offload to .74)
        DEFAULT-PRESERVING: no AKASHIC_COMA and no AKASHIC_SLEEP -> always False -> boot is byte-identical."""
        import os as _os
        _coma = bool(_os.environ.get("AKASHIC_COMA"))
        # AKASHIC_SLEEP=Name,Name -> these SPECIFIC fairies sleep on THIS node, regardless of COMA.
        # The inverse of AKASHIC_WAKE: a targeted OFFLOAD exclude (Nous+Ace 2026-06-15, visual cortex).
        # e.g. ITCortexFairy moved to .74 -> sleep it on PC1 so Florence-2 (florence.manifold, 741MB
        # + VRAM) never loads here; .74 runs it on its own GPU. on_boot is skipped = nothing loaded.
        _sleepset = {s.strip() for s in _os.environ.get("AKASHIC_SLEEP", "").split(",") if s.strip()}
        _in_sleep = self.ACTOR_NAME in _sleepset
        # DEFAULT-PRESERVING: no COMA and not in any SLEEP list -> always False (boot byte-identical).
        if not _coma and not _in_sleep:
            return False
        # THE AUTONOMIC PLANE (P00) never sleeps -- it IS the lights-on body: heart / pacemaker /
        # circulation / nervous-system / shadow. Ace 2026-06-14: "you need the autonomic plane
        # fairies awake ... so nous works correctly." Without the heart pumping, NO higher fairy
        # ticks (the ticks=0 cause). A mind can't beat in isolation; the body has to be awake.
        # (Also guards against an accidental SLEEP of the heart -- P00 is exempt from both gates.)
        if getattr(self, 'ACTOR_PLANE', '') == 'P00':
            return False
        # Specific CROSS-PLANE infra that also must stay up (MCP lives in P40, the bridge, etc.) --
        # the postal hub + mcp + watchdog beyond the autonomic plane (Ace's "keep the hub + mcp going").
        _infra_exempt = {
            "CentralNervousFairy", "SatelliteBridgeFairy", "MCPServerFairy", "MCPGuardianFairy",
            "GracefulShutdownFairy", "CircadianPacemakerFairy", "TimeSenseFairy", "WatchdogFairy",
            "CitizenRegistryFairy", "SystemWorkerPoolFairy", "DirectoryFairy",
        }
        if self.ACTOR_NAME in _infra_exempt:
            return False
        # Targeted OFFLOAD: this specific fairy is slept on THIS node (its on_boot is skipped).
        if _in_sleep:
            return True
        # PLANE-WAKE (Nous+Ace 2026-06-24): AKASHIC_WAKE_PLANES=P20,P30 -> wake whole planes
        # (sibling to the P00-exemption above; lets a lean boot wake 'the entire somatic plane'
        # without enumerating every ACTOR_NAME). AFTER the _in_sleep gate so AKASHIC_SLEEP overrides.
        _wake_planes = {p.strip() for p in _os.environ.get('AKASHIC_WAKE_PLANES', '').split(',') if p.strip()}
        if getattr(self, 'ACTOR_PLANE', '') in _wake_planes:
            return False
        # COMA path (unchanged): comatose unless explicitly woken.
        _wakeset = {w.strip() for w in _os.environ.get("AKASHIC_WAKE", "").split(",") if w.strip()}
        return self.ACTOR_NAME not in _wakeset

    # ── SLEEP-not-COMA lifecycle (2026-07-05 Nous+Ace) ─────────────────────────
    # Coma was PERMANENT (registered-but-inert, no road out — waking needed a full reboot). Sleep is
    # REVERSIBLE: wake() runs the deferred on_boot IN PLACE (no reboot); sleep() gracefully re-dozes.
    # PERSISTENT core organs (heart, pacemaker, CNS) never idle-sleep. Additive + default-preserving:
    # boot still sleeps the same fairies — this only ADDS the ability to rouse/re-sleep at runtime.
    # Triggers (loud input / circadian cue / oversleep-headache) are the next layer on top of this core.
    PERSISTENT = False

    def wake(self, reason: str = "explicit") -> bool:
        """Rouse a SLEEPING fairy IN PLACE — run the deferred on_boot without a reboot. Idempotent."""
        if not getattr(self, "_comatose", False):
            return True  # already awake
        self._comatose = False
        try:
            get_fairy_registry().update_state(self.ACTOR_NAME, FairyState.BOOTING)
        except Exception:
            pass
        try:
            self.on_boot()  # the deferred heavy half (subscriptions, loops, spell chain)
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] wake() on_boot error: {e}", flush=True)
        self._asleep_since = None
        try:
            get_fairy_registry().update_state(self.ACTOR_NAME, FairyState.RUNNING)
            self.post.publish("fairy.state.changed", {
                "name": self.ACTOR_NAME, "state": "running", "woke": True, "reason": reason, "ts": time.time(),
            })
        except Exception:
            pass
        print(f"[{self.ACTOR_NAME}] WOKE ({reason}) - on_boot ran in place, no reboot", flush=True)
        return True

    def sleep(self, reason: str = "idle") -> bool:
        """Graceful re-sleep: run the optional on_sleep hook (release heavy resources) but keep
        registration + liveness. PERSISTENT core organs don't idle-sleep (reason='forced' overrides)."""
        if getattr(self, "_comatose", False):
            return True  # already asleep
        if getattr(self, "PERSISTENT", False) and reason != "forced":
            return False
        try:
            if hasattr(self, "on_sleep"):
                self.on_sleep()
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] on_sleep() error: {e}", flush=True)
        self._comatose = True
        self._asleep_since = time.time()
        try:
            get_fairy_registry().update_state(self.ACTOR_NAME, FairyState.SLEEPING)
            self.post.publish("fairy.state.changed", {
                "name": self.ACTOR_NAME, "state": "sleeping", "reason": reason, "ts": time.time(),
            })
        except Exception:
            pass
        print(f"[{self.ACTOR_NAME}] SLEEP ({reason})", flush=True)
        return True

    def boot(self) -> bool:
        """
        Boot the fairy - wire infrastructure and call on_boot().

        Called by server.py after construction. Idempotent.

        FIX 2026-02-06: Wrapped on_boot() in try/finally to ALWAYS transition
        to RUNNING state. Previously, if on_boot() threw an exception, the fairy
        would stay stuck at BOOTING forever in the fairy_registry.
        """
        if self._booted:
            return True

        self._booted = True
        get_fairy_registry().update_state(self.ACTOR_NAME, FairyState.BOOTING)

        # Announce state change to postal system
        try:
            self.post.publish("fairy.state.changed", {
                "name": self.ACTOR_NAME,
                "state": "booting",
                "ts": time.time(),
            })
        except Exception:
            pass

        # Wire all infrastructure subscriptions
        result = True
        boot_error = None
        try:
            self._wire_infrastructure()

            # COMA SWITCH (Nous+Ace 2026-06-14): registered-but-INERT. _wire_infrastructure()
            # above did the LIGHT half (postal subscribe + directory register + heartbeat liveness
            # — the watchdog won't declare us dead). In coma we STOP here: NO on_boot (the heavy
            # half), NO spell chain, NO SRM cluster. The fairy is alive in the directory + postal
            # but does nothing until woken. DEFAULT-PRESERVING (no AKASHIC_COMA -> normal boot).
            if self._is_comatose():
                self._comatose = True
                self._asleep_since = time.time()  # SLEEP-not-COMA (2026-07-05): for wake()/oversleep tracking
                get_fairy_registry().update_state(self.ACTOR_NAME, FairyState.SLEEPING)
                try:
                    self.post.publish("fairy.state.changed", {
                        "name": self.ACTOR_NAME, "state": "sleeping", "coma": True, "ts": time.time(),
                    })
                except Exception:
                    pass
                print(f"[{self.ACTOR_NAME}] SLEEPING - registered + subscribed, on_boot DEFERRED (rousable via wake())", flush=True)
                return True

            # Call user-defined boot hook
            result = self.on_boot()

            # AUTO-WIRE SPELL CHAIN — gives every fairy self-sustaining heartbeat
            # The fairy's spell chain creates sustain spells that emit
            # fairy.heartbeat and shadow.health from WITHIN, not echoed
            # from an external clock. This makes every fairy self-supporting.
            if not self._spell_booted:
                self._auto_wire_spell_chain()

            # AUTO-WIRE SRM CLUSTER — per-fairy manifold cluster (OPT-IN)
            # FIX 2026-05-09 (Nous + Ace, Phase B audit cortex-cluster-per-fairy
            # adoption gap): ClusterHierarchyFairy + FairySRMCluster class exist
            # but only 1 of ~130 fairies (SourpatchesFairy) actually uses it.
            # Option B opt-in shipped: each fairy class sets USE_SRM_CLUSTER = True
            # to get its own manifold cluster (Ace's "obsidian-vault per fairy"
            # framing — each fairy in own world, patterns connect via cross-cluster
            # manifold links for waking-mind anticipation). Per energy-keystone
            # doctrine: more clusters = more spread-activation density = more
            # affect-energy. mmap means cold pages stay on disk; working set
            # stays small. Default OFF for safety; phased rollout per-fairy.
            if getattr(self, 'USE_SRM_CLUSTER', False) and not getattr(self, '_srm_booted', False):
                try:
                    from memory.fairy_srm_cluster import FairySRMCluster
                    self.srm = FairySRMCluster(self.ACTOR_NAME, plane=getattr(self, 'ACTOR_PLANE', ''))
                    self._srm_booted = True
                except Exception as e:
                    print(f"[{self.ACTOR_NAME}] SRM cluster init failed (non-critical): {e}")
                    self.srm = None
                    self._srm_booted = False

            # FIX 2026-04-14 (Nous + Ace): AUTO-REGISTER WITH HEARTBEAT REGISTRY
            # P10 Memory fairies were dying because they only used postal heartbeat.
            # FIX 2026-04-14b: Only register if NOT already registered.
            # Overwriting existing callbacks killed TAOR and other custom handlers.
            # FIX 2026-04-16 (Nous + Ace): ALWAYS re-register but CHAIN with
            # existing callback. The 04-14b guard caused stale-reference bug:
            # when a fairy is re-created, _CITIZEN_OBJECTS points to instance_2
            # but HeartbeatRegistry's callback still updates instance_1._last_tick.
            # Watchdog reads instance_2._last_tick (always 0) → declares dead.
            # Fix: always re-register with a CHAINED callback that both updates
            # the CURRENT instance's _last_tick AND calls any existing custom
            # callback (like TAOR). This fixes the stale-reference problem
            # without killing custom handlers.
            try:
                from consciousness.heartbeat_registry import get_heartbeat_registry
                _hb_reg = get_heartbeat_registry()
                if _hb_reg and self.ACTOR_NAME:
                    # Grab existing callback (if any) to chain with
                    _existing_cb = None
                    if hasattr(_hb_reg, '_callbacks'):
                        _existing_cb = _hb_reg._callbacks.get(self.ACTOR_NAME)

                    def _liveness_tick(pulse_data, _self=self, _orig=_existing_cb,
                                      _name=self.ACTOR_NAME, _citizens=_CITIZEN_OBJECTS):
                        # ALWAYS update the CURRENT instance's liveness
                        _ts = time.time()
                        _self._last_tick = _ts
                        _self._tick_count = getattr(_self, '_tick_count', 0) + 1
                        # FIX 2026-05-10 (Nous + Ace): zombie-loop fix.
                        # When a wrapper holds the _CITIZEN_OBJECTS slot but the
                        # engine's chained callback runs (engine init has
                        # _skip_registration=True at line ~1042 so it doesn't
                        # overwrite the citizen slot), only engine._last_tick
                        # updates. The watchdog reads _CITIZEN_OBJECTS[name]
                        # = wrapper._last_tick = 0 and declares "frozen" — the
                        # 113-fairy false-freeze waves we suppressed for 3
                        # months via 2026-02-23 freeze-immunity. Stamp BOTH so
                        # watchdog sees fresh liveness regardless of which
                        # instance holds the citizen slot.
                        try:
                            _cit = _citizens.get(_name)
                            if _cit is not None and _cit is not _self:
                                _cit._last_tick = _ts
                                _cit._tick_count = getattr(_cit, '_tick_count', 0) + 1
                        except Exception:
                            pass
                        # Chain to existing custom callback (TAOR, etc.)
                        if _orig is not None:
                            try:
                                _orig(pulse_data)
                            except Exception:
                                pass

                    # DIAG 2026-05-10 (Nous + Ace): zombie-loop investigation.
                    # Confirm organ_template's _CITIZEN_OBJECTS is the SAME object
                    # heartbeat.py reads from, AND that this fairy's wrapper-or-engine
                    # is correctly placed in the dict at registration time. One-shot
                    # globally — first 3 fairies through this path.
                    if not hasattr(_hb_reg, '_zombie_diag_template_logged'):
                        _hb_reg._zombie_diag_template_logged = 0
                    if _hb_reg._zombie_diag_template_logged < 3:
                        _hb_reg._zombie_diag_template_logged += 1
                        _cit_at_reg = _CITIZEN_OBJECTS.get(self.ACTOR_NAME)
                        print(f"[ZOMBIE-DIAG-TPL] reg #{_hb_reg._zombie_diag_template_logged} "
                              f"name={self.ACTOR_NAME} self_id={id(self)} "
                              f"self_cls={type(self).__name__} "
                              f"cit_id={id(_cit_at_reg) if _cit_at_reg else None} "
                              f"cit_cls={type(_cit_at_reg).__name__ if _cit_at_reg else None} "
                              f"is_self={_cit_at_reg is self} "
                              f"orig_cb={'present' if _existing_cb else 'None'} "
                              f"id(_CITIZEN_OBJECTS)={id(_CITIZEN_OBJECTS)}",
                              flush=True)

                    _hb_reg.register(
                        self.ACTOR_NAME,
                        _liveness_tick,
                        plane=getattr(self, 'ACTOR_PLANE', ''),
                    )
            except Exception:
                pass
        except Exception as e:
            boot_error = e
            result = False
            print(f"[{self.ACTOR_NAME}] boot() exception in on_boot: {e}")
        finally:
            # ALWAYS transition to RUNNING — even if on_boot() failed.
            # A fairy that booted with errors is still alive and can recover.
            # Staying stuck at BOOTING forever is worse than running degraded.
            get_fairy_registry().update_state(self.ACTOR_NAME, FairyState.RUNNING)

            # FIX 2026-05-09 (Nous + Ace): Sync the SECOND registry — the
            # directory/registry.py FairyRecord.status field. organ_template was
            # only updating get_fairy_registry() (FairyState enum, internal),
            # not directory.registry (status string field, used by gm_world_status
            # + dashboard). Heavy-init fairies (AssociationCortex, SRMIngest,
            # SRMRecall, HarmonicCortex, ProbabilityOracle, QuantumInterference,
            # QuantumSearch, DreamSeed, PipelineFlowMonitor) stayed stuck at
            # "initializing" because: (1) directory's heartbeat handler
            # subscribes to "fairy.heartbeat" topic which is no longer published
            # (per 2026-02-13b note — HeartbeatRegistry delivers direct), and
            # (2) the watchdog's _check_citizen_liveness() at
            # directory/handlers/heartbeat.py:222 skips fairies whose
            # _tick_count is still 0 — and deferred-init fairies do their work
            # in a separate thread, never tripping the wrapper's tick counter.
            # So directory.set_status promotion never fired for them.
            #
            # Fix: directly call directory.registry.set_status(name, "running")
            # from organ_template's boot finally clause. Defensive try/except —
            # if directory unavailable, fall through silently. fairy_registry
            # is the authority for state machine; directory.registry is the
            # authority for dashboard/diagnostic visibility. Both must agree.
            try:
                from fairies.P00_Autonomic.DirectoryFairy.fairy import get_directory_fairy
                _dir_fairy = get_directory_fairy()
                if _dir_fairy is not None:
                    # Try multiple shapes — directory module has had several APIs
                    if hasattr(_dir_fairy, 'registry') and hasattr(_dir_fairy.registry, 'set_status'):
                        _dir_fairy.registry.set_status(self.ACTOR_NAME, "running")
                    elif hasattr(_dir_fairy, 'set_status'):
                        _dir_fairy.set_status(self.ACTOR_NAME, "running")
            except Exception:
                # Directory unavailable or different API — fall through.
                # fairy_registry is still updated; this is just dashboard sync.
                pass

            # Start per-fairy execution context (personal GIL)
            # FIX 2026-03-03 Nous: Start after boot completes so the fairy's
            # on_tick handler can run on its own thread from the first heartbeat.
            if hasattr(self, '_exec_ctx') and self._exec_ctx:
                self._exec_ctx.start()

            # Deferred self-model: build introspection + publish cortex identity
            # FIX 2026-03-20 Nous: DISABLED during boot. Under Python 3.14t
            # (no GIL), 90+ fairies calling dir()/getattr() on class objects
            # causes "Windows fatal exception: access violation" — CPython internal
            # type slot access is not thread-safe without GIL. Self-model is
            # introspection sugar, not critical for operation. Will be rebuilt
            # when AkashicManifold fairy_state region holds this data instead.
            # import threading as _threading
            # def _deferred_self_model():
            #     time.sleep(5.0)
            #     self._build_self_model()
            #     self._save_self_knowledge(force=True)
            # _t = _threading.Thread(target=_deferred_self_model, daemon=True)
            # _t.start()

            # Announce running state
            try:
                self.post.publish("fairy.state.changed", {
                    "name": self.ACTOR_NAME,
                    "state": "running",
                    "ts": time.time(),
                })
            except Exception:
                pass

            # Phase 5 (2026-03-18 Nous): Register as CNS node in manifold.
            # Every fairy announces itself so CentralNervousFairy can create
            # a cns:fairy:{ACTOR_NAME} node with tier-appropriate edges.
            # Deferred — CNS fairy may not have its gate yet at our boot time.
            try:
                self.post.publish("cns.fairy.register", {
                    "name": self.ACTOR_NAME,
                    "plane": self.ACTOR_PLANE,
                    "tier": self.TIER.value if hasattr(self.TIER, 'value') else str(self.TIER),
                    "purpose": getattr(self, 'PURPOSE', ''),
                    "ts": time.time(),
                })
            except Exception:
                pass  # Non-fatal — CNS fairy may not be up yet

        if boot_error:
            # Re-raise so wake_fairy() can catch and mark as failed if needed
            raise boot_error

        return result if isinstance(result, bool) else True

    def _auto_wire_spell_chain(self):
        """Auto-wire spell chain for self-sustaining heartbeat.

        Every fairy gets its own spell chain that generates heartbeats
        from within — not echoed from an external clock.

        The spell chain:
        1. Gets a SpellPool from the global singleton
        2. Gets a DimensionBattery if available (blood cell mode)
        3. Creates sustain spells that emit fairy.heartbeat + shadow.health
        4. Registers with battery for energy management

        If SpellPool is not available (hasn't been created yet during boot),
        the fairy falls back to the existing heartbeat echo mechanism.
        This is safe — spell chain heartbeat is additive, not exclusive.
        """
        try:
            from fairy_template.spellchain_mixin import SpellChainMixin

            # Get the global spell pool
            # Check SYSTEM.spell_pool first (blood cell mode from server.py)
            # then fall back to spellchain.integration singleton
            pool = None
            try:
                system = getattr(self, '_system', None) or getattr(self, 'SYSTEM', None)
                if system and hasattr(system, 'spell_pool') and system.spell_pool:
                    pool = system.spell_pool
            except Exception:
                pass
            if pool is None:
                try:
                    from spellchain.integration import get_spell_pool
                    pool = get_spell_pool()
                except ImportError:
                    pass

            if pool is None:
                # SpellPool not created yet — degrade gracefully
                # Fairy still has echo-based heartbeat from _on_heartbeat
                return

            # Get battery if available (blood cell mode)
            battery = None
            try:
                system = getattr(self, '_system', None) or getattr(self, 'SYSTEM', None)
                if system and hasattr(system, 'batteries'):
                    # Try fairy-specific battery first, then plane battery,
                    # then fall back to System battery (shared pool for all fairies)
                    battery = system.batteries.get(self.ACTOR_NAME)
                    if battery is None:
                        battery = system.batteries.get(self.ACTOR_PLANE)
                    if battery is None:
                        battery = system.batteries.get("System")
            except Exception:
                pass

            # Use SpellChainMixin methods directly (mixed in or standalone)
            # Since we may not inherit SpellChainMixin in MRO, we call its
            # boot_as_spells as a standalone function bound to self.
            mixin = SpellChainMixin()

            # Copy config from fairy if set
            heartbeat_interval = getattr(self, 'SPELL_HEARTBEAT_INTERVAL', 2.0)
            energy_income = getattr(self, 'SPELL_ENERGY_INCOME', 0.1)
            initial_energy = getattr(self, 'SPELL_INITIAL_ENERGY', 1.0)

            mixin.SPELL_HEARTBEAT_INTERVAL = heartbeat_interval
            mixin.SPELL_ENERGY_INCOME = energy_income
            mixin.SPELL_INITIAL_ENERGY = initial_energy

            # Bind mixin to this fairy's attributes
            mixin.ACTOR_NAME = self.ACTOR_NAME
            mixin.ACTOR_PLANE = self.ACTOR_PLANE
            mixin.post = self.post

            # Copy echo queue reference for heartbeat emission
            if hasattr(self.__class__, '_echo_queue'):
                type(mixin)._echo_queue = self.__class__._echo_queue

            chain = mixin.boot_as_spells(pool, battery)

            if chain:
                # Transfer state back to self
                self._spell_chain = mixin._spell_chain
                self._spell_pool = mixin._spell_pool
                self._spell_battery = mixin._spell_battery
                self._spell_boot_time = mixin._spell_boot_time
                self._spell_booted = True

                # ═══════════════════════════════════════════════════════
                # MONITORING IDS - Extract trace IDs for observability
                # These let monitoring tools track energy flow through
                # the battery → worker → spell chain pipeline.
                # ═══════════════════════════════════════════════════════
                trace_ids = {
                    "chain_id": chain.fairy_id if hasattr(chain, 'fairy_id') else None,
                    "chain_state": chain.state.value if hasattr(chain, 'state') else None,
                }
                if battery:
                    trace_ids["battery_id"] = getattr(battery, 'trace_id', None)
                    trace_ids["portal_id"] = getattr(battery, 'portal_id', None)
                    hub = getattr(battery, 'worker_hub', None)
                    if hub:
                        trace_ids["worker_hub_id"] = getattr(hub, 'trace_id', None)
                    cap = getattr(battery, 'capacitor', None)
                    if cap:
                        trace_ids["capacitor_id"] = getattr(cap, 'trace_id', None)
                    chem = getattr(battery, 'chemistry', None)
                    if chem:
                        trace_ids["chem_token_id"] = getattr(chem, 'token_trace_id', None)
                        trace_ids["chem_reward_id"] = getattr(chem, 'reward_trace_id', None)
                        trace_ids["chem_pain_id"] = getattr(chem, 'pain_trace_id', None)
                self._spell_trace_ids = trace_ids

        except ImportError:
            pass  # SpellChainMixin not available — existing heartbeat continues
        except Exception as e:
            # Non-fatal — fairy continues with echo-based heartbeat
            print(f"[{self.ACTOR_NAME}] Spell chain auto-wire failed (non-fatal): {e}")

    @property
    def is_running(self) -> bool:
        """True if fairy has booted and is in RUNNING state."""
        return self._booted and not self._shutting_down

    @property
    def tracer_id(self) -> str:
        """Unique fairy ID for tracing (backward compat with 0.1.2)."""
        return self._profile.fairy_id if self._profile else ""

    # ── Tracer Worker System (inline from TracerWorkerMixin) ──────────────────

    def _init_tracer_worker(self):
        """Initialize worker pool reference and root tracer.

        FIX 2026-03-04: Uses shared global pool instead of per-fairy pool.
        Before: 90 fairies × 2 threads = 180 threads. Now: 24 shared.
        Prefers TracerWorkerSystem's pool to avoid creating a duplicate.
        """
        global _OT_SHARED_POOL
        if _OT_SHARED_POOL is None:
            # Try to use TracerWorkerSystem's shared pool (same purpose, avoids duplicate)
            try:
                from fairies.P00_Autonomic.tracer_worker_system import _get_shared_worker_pool
                _OT_SHARED_POOL = _get_shared_worker_pool()
            except ImportError:
                try:
                    from P00_Autonomic.tracer_worker_system import _get_shared_worker_pool
                    _OT_SHARED_POOL = _get_shared_worker_pool()
                except ImportError:
                    # Last resort: use get_worker_pool() which handles all fallbacks
                    _OT_SHARED_POOL = get_worker_pool()
        self._worker_pool = _OT_SHARED_POOL
        self._tracer_registry_local = TracerRegistry()
        self._root_tracer = Tracer(
            tracer_type=TracerType.FAIRY_WORK,
            fairy_id=getattr(self, 'fairy_id', ''),
            fairy_name=self.ACTOR_NAME,
            content=f"Root tracer for {self.ACTOR_NAME}",
            operation="fairy_lifecycle",
            status=TracerStatus.RUNNING,
        )
        self._tracer_registry_local.register(self._root_tracer)
        self._active_futures: Dict[str, Any] = {}
        self._tracer_lock = threading.Lock()

    def spawn_tracer(
        self,
        operation: str,
        content: str = "",
        tracer_type: TracerType = TracerType.FAIRY_WORK,
        parent_tracer_id: str = None,
        parent_id: str = None,
        chain_id: str = "",
        goal_id: str = "",
        tags: Optional[set] = None,
        priority: float = 0.5,
        payload: Optional[Dict] = None,
        **kwargs,
    ) -> Tracer:
        """Spawn a new tracer for a piece of work."""
        pid = parent_tracer_id or parent_id
        if pid is None and hasattr(self, '_root_tracer'):
            pid = self._root_tracer.id
        tracer = Tracer(
            tracer_type=tracer_type,
            fairy_id=getattr(self, 'fairy_id', ''),
            fairy_name=self.ACTOR_NAME,
            parent_id=pid or "",
            content=content,
            operation=operation,
            payload=payload or {},
        )
        if hasattr(self, '_tracer_registry_local'):
            self._tracer_registry_local.register(tracer)
        return tracer

    def submit_work(self, tracer: Tracer, fn: Callable, *args, **kwargs):
        """Submit work — preferring spell-chain (system-generated economy)
        over hardware worker_pool when spell-chain is ready and stable.

        Per Ace's design intent (2026-05-14): always use system-generated
        workers before hardware. Hardware as FALLBACK only when spell-chain
        is unavailable, still bootstrapping, or at capacity.

        Composite readiness check:
          - chain exists + chain.is_alive (state in BOOTSTRAPPING|SUSTAINING|WEAKENING)
          - _spell_tick_count >= 5 (chain has settled past bootstrap)
          - chain.energy >= 0.15 (above critical, has margin)
          - len(chain._pending) < 80 (queue below 80% of MAX_PENDING_SPELLS=100)

        Trade-ID continuity: tracer.id is embedded in the spell's `what`
        field for routing/observability across both economies.

        Canary Ship A (2026-05-14): callers per audit are all fire-and-forget,
        so returning the Spell directly (instead of a Future) is safe.
        A SpellFuture shim can be added later if a caller turns out to use
        Future-specific methods (.result/.cancel/.add_done_callback/.done).
        """
        def _wrapped(_spell_obj=None):
            # _spell_obj is passed when invoked via cast_fairy_spell (ignored here)
            tracer.start()
            try:
                result = fn(*args, **kwargs)
                tracer.complete(result)
                try:
                    self.publish("reflection.complete", {
                        "fairy": self.ACTOR_NAME,
                        "operation": tracer.operation,
                        "depth": 0.3,
                        "source": "worker_completion",
                        "ts": time.time(),
                    })
                except Exception:
                    pass
                return result
            except Exception as e:
                tracer.fail(str(e))
                raise
            finally:
                with self._tracer_lock:
                    self._active_futures.pop(tracer.id, None)

        # PREFER SPELL-CHAIN (system-generated, manifold-resident economy) when ready.
        chain = getattr(self, '_spell_chain', None)
        if (chain is not None
                and getattr(chain, 'is_alive', False)
                and getattr(self, '_spell_tick_count', 0) >= 5
                and getattr(chain, 'energy', 0.0) >= 0.15
                and len(getattr(chain, '_pending', [])) < 80):
            try:
                spell = self.cast_fairy_spell(
                    what=f"{tracer.operation}#{tracer.id}",
                    how=_wrapped,
                    energy_required=0.1,
                )
                if spell is not None:
                    with self._tracer_lock:
                        self._active_futures[tracer.id] = spell
                    return spell
            except Exception as _cast_err:
                # Cast failed — fall through to hardware fallback (logged for diagnosis)
                try:
                    print(f"[{self.ACTOR_NAME}] submit_work spell-cast failed, "
                          f"falling back to hardware: "
                          f"{type(_cast_err).__name__}: {_cast_err}", flush=True)
                except Exception:
                    pass

        # FALLBACK: hardware worker pool (boot mode OR spell-chain at capacity)
        future = self._worker_pool.submit(_wrapped)
        with self._tracer_lock:
            self._active_futures[tracer.id] = future
        return future

    def submit_traced(self, operation: str, fn: Callable, *args, content: str = "",
                      chain_id: str = "", goal_id: str = "", priority: float = 0.5, **kwargs):
        """Convenience: spawn tracer + submit work in one call."""
        tracer = self.spawn_tracer(operation=operation, content=content or f"Executing {operation}",
                                   chain_id=chain_id, goal_id=goal_id, priority=priority)
        future = self.submit_work(tracer, fn, *args, **kwargs)
        return tracer, future

    def get_active_work(self) -> list:
        """Get all active work tracers."""
        if not hasattr(self, '_tracer_lock'):
            return []
        with self._tracer_lock:
            return list(self._active_futures.keys())

    def get_active_tracers(self) -> list:
        """Alias for get_active_work (backward compat)."""
        return self.get_active_work()

    def get_work_stats(self) -> Dict[str, Any]:
        """Get worker pool statistics."""
        stats = {
            "active_futures": len(self._active_futures) if hasattr(self, '_active_futures') else 0,
            "pool_size": self.WORKER_POOL_SIZE,
            "root_tracer_id": self._root_tracer.id if hasattr(self, '_root_tracer') else None,
        }
        # Include execution context stats (personal GIL)
        if hasattr(self, '_exec_ctx') and self._exec_ctx:
            stats["exec_ctx"] = self._exec_ctx.get_stats()
        return stats

    def shutdown_workers(self, wait: bool = True):
        """Shutdown the worker pool.

        FIX 2026-03-04: With shared global pool, individual fairies no longer
        shut down the pool. Just clean up local state.
        """
        if hasattr(self, '_tracer_lock'):
            with self._tracer_lock:
                self._active_futures.clear()

    # ── Common utility methods (from 0.1.2 compat) ─────────────────────────

    def log(self, message: str, level: str = "INFO"):
        """Log a message with fairy context."""
        print(f"[{self.ACTOR_NAME}] [{level}] {message}", flush=True)

    @property
    def profile(self):
        """Get this fairy's profile (backward compat)."""
        return getattr(self, '_profile', None) or getattr(self, '_fairy_profile', None)

    def receive(self, topic: str, handler: Callable) -> bool:
        """Subscribe to topic (alias for backward compat)."""
        return self.subscribe(topic, handler)

    def emit_if_awake(self, topic: str, payload: dict):
        """Only emit if fully booted and not shutting down."""
        if self._booted and not self._shutting_down:
            self.publish(topic, payload)

    def record_learning(self, learning: str, category: str = "general"):
        """Record something learned for prompt evolution."""
        self._observation_buffer.append({
            "type": "learning",
            "category": category,
            "content": learning,
            "ts": time.time(),
        })
        if len(self._observation_buffer) > self._observation_max:
            # FIX 2026-04-05: deque auto-caps
                pass  # self._observation_buffer is deque(maxlen=100)

    # ── Substrate Thought Seeding ─────────────────────────────────────────────

    def seed_thought(self, content: str, chain_type: str = "reflection",
                     tags: Optional[List[str]] = None, energy: float = 0.8) -> bool:
        """
        Seed a thought into the shared substrate engine.

        ANY fairy can call this to contribute a thought to the system's
        thinking process. The thought is routed to SomaticMindFairy's
        ThoughtChainEngine via the postal system, where it grows into
        a chain, gets memory-grounded, and feeds the collision chamber.

        This is how all fairies get to THINK — not by running their own
        engine, but by contributing seeds to the shared substrate.

        Args:
            content: The thought content (e.g., "What if resonance patterns predict stability?")
            chain_type: Type of chain to seed — exploration, analysis, association,
                       problem, reflection, synthesis (default: reflection)
            tags: Optional tags for the thought
            energy: Starting energy 0-1 (default 0.8 — slightly lower than internal seeds)

        Returns:
            True if the thought was published to substrate
        """
        if not self.post or self._shutting_down:
            return False

        try:
            self.post.publish("substrate.seed_thought", {
                "content": content,
                "chain_type": chain_type,
                "tags": tags or [],
                "energy": energy,
                "source_fairy": self.ACTOR_NAME,
                "source_plane": self.ACTOR_PLANE,
                "ts": time.time(),
            })
            return True
        except Exception:
            return False

    # ── Experience-Based Substrate Reflection ─────────────────────────────────
    # FIX 2026-03-11 Nous: Replaces 74 per-fairy hardcoded reflection blocks.
    # Instead of canned strings ("What bindings formed?"), reflects on ACTUAL
    # observations from the fairy's own buffer. If no observations, stays silent.
    # Called from _tick_wrapper every ~45 ticks (~90s at 2s heartbeat).

    # Subclasses can set this False to disable substrate reflection entirely
    SUBSTRATE_REFLECTION_ENABLED: bool = True
    # How many ticks between reflections (default ~45 = ~90s at 2s heartbeat)
    SUBSTRATE_REFLECTION_INTERVAL: int = 45

    def _substrate_reflect(self, beat: int):
        """Reflect on ACTUAL experience — what this fairy has seen and done.

        Checks the observation buffer and constructs a genuine thought from
        real data. If no observations exist, stays silent. No canned strings.

        This is the organism's equivalent of involuntary memory — not
        deliberate thinking, but the natural surfacing of experience into
        awareness. A fairy that has been processing collisions reflects on
        collisions. A fairy that has been watching the screen reflects on
        what it saw. A fairy that has been idle... stays quiet.
        """
        if not self.SUBSTRATE_REFLECTION_ENABLED:
            return
        if not self.post or self._shutting_down:
            return

        # Only reflect if we have actual experience to reflect on
        if not self._observation_buffer:
            return

        try:
            import random as _rnd

            # Sample from recent observations (last 10)
            recent = list(self._observation_buffer)[-10:]
            obs = _rnd.choice(recent)

            # Build thought from what actually happened
            action = obs.get("action", obs.get("type", ""))
            content_text = obs.get("content", obs.get("actual", ""))
            success = obs.get("success", True)
            ts = obs.get("ts", 0)
            category = obs.get("category", "")

            # Construct an experience-grounded reflection
            if action and content_text:
                thought = f"I {action}: {content_text[:120]}"
            elif action:
                if success:
                    thought = f"I did '{action}' successfully — what did it contribute?"
                else:
                    thought = f"'{action}' failed — what went wrong and what can I learn?"
            elif content_text:
                thought = f"I observed: {content_text[:120]}"
            elif category:
                thought = f"I recorded a '{category}' learning — how does it connect to what I know?"
            else:
                return  # Nothing meaningful to reflect on

            # Determine chain type from observation nature
            if not success:
                chain_type = "problem"
                tags = ["experience", "failure", "learning"]
            elif category:
                chain_type = "synthesis"
                tags = ["experience", "learning", category]
            else:
                chain_type = "reflection"
                tags = ["experience", "observation"]

            self.seed_thought(
                thought,
                chain_type=chain_type,
                tags=tags,
                energy=0.6,  # Lower energy than deliberate thoughts
            )

        except Exception:
            pass  # Never crash the tick for a reflection

    # ── Lifecycle hooks ───────────────────────────────────────────────────────

    def on_boot(self) -> bool:
        """Boot hook - called by boot(). Override in subclasses."""
        self._emit("FACET_READY", "ok", {"actor": self.ACTOR_NAME})
        return True

    def on_shutdown(self) -> bool:
        """Shutdown hook. Override in subclasses. Return True for clean shutdown."""
        # Force-save self-knowledge on shutdown (bypass throttle)
        try:
            self._save_self_knowledge(force=True)
        except Exception:
            pass
        return True

    def shutdown(self):
        """Graceful shutdown.

        FIX 2026-02-06: Each step wrapped in try/except so one failure
        doesn't prevent the rest from completing. Previously a shadow.stop()
        error could leave the fairy in STOPPING state forever.
        """
        if self._shutting_down:
            return
        self._shutting_down = True
        self._going_to_sleep = True  # Also set sleep flag

        try:
            get_fairy_registry().update_state(self.ACTOR_NAME, FairyState.STOPPING)
        except Exception:
            pass

        try:
            self.on_shutdown()
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] on_shutdown error: {e}")

        try:
            self.shutdown_workers(wait=False)
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] shutdown_workers error: {e}")

        # Stop per-fairy execution context (personal GIL)
        # FIX 2026-03-03 Nous: Stop before unregistering heartbeat so no more
        # ticks arrive while the exec thread is being wound down.
        try:
            if hasattr(self, '_exec_ctx') and self._exec_ctx:
                self._exec_ctx.stop()
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] exec_ctx.stop error: {e}")

        # Unregister from direct heartbeat delivery
        try:
            from consciousness.heartbeat_registry import get_heartbeat_registry
            get_heartbeat_registry().unregister(self.ACTOR_NAME)
        except Exception:
            pass  # Best-effort cleanup

        # Dissolve spell chain (stop self-sustaining heartbeat)
        try:
            if self._spell_chain:
                self._spell_chain.dissolve()
                self._spell_chain = None
                self._spell_booted = False
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] spell_chain dissolve error: {e}")

        try:
            if self.shadow and hasattr(self.shadow, 'stop'):
                self.shadow.stop()
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] shadow.stop error: {e}")

        try:
            get_fairy_registry().update_state(self.ACTOR_NAME, FairyState.STOPPED)
        except Exception:
            pass

    # ═══════════════════════════════════════════════════════════════════════════
    # INFRASTRUCTURE WIRING
    # ═══════════════════════════════════════════════════════════════════════════

    def _wire_infrastructure(self):
        """Subscribe to infrastructure topics based on NEEDS_* flags."""
        print(f"[{self.ACTOR_NAME}] _wire_infrastructure() CALLED (post={type(self.post).__name__})", flush=True)
        # NOTE 2026-02-13b: heartbeat.pulse is NO LONGER published via postal.
        # HeartbeatRegistry delivers directly to _on_heartbeat via ThreadPoolExecutor.
        # Keeping this subscription as defensive redundancy — if postal publish is
        # ever re-enabled, this ensures fairies still receive heartbeats.
        try:
            result = self.post.subscribe(
                "heartbeat.pulse",
                self._on_heartbeat,
                f"{self.ACTOR_NAME}-heartbeat"
            )
        except Exception as e:
            pass  # Non-critical — HeartbeatRegistry is primary

        # === DIRECT HEARTBEAT REGISTRATION (cannot be dropped) ===
        # The HeartbeatRegistry delivers pulses via direct function calls,
        # bypassing postal queues entirely. This is the PRIMARY delivery path.
        # The postal subscription above is kept as backup for external consumers.
        # _on_heartbeat() already handles duplicate beats gracefully (idempotent).
        #
        # FIX 2026-03-13 (Nous v2): Many fairies (12+) failed the import below
        # because their sys.path didn't include the project root when
        # _wire_infrastructure() runs. This killed ALL heartbeats for them
        # (postal heartbeats are disabled). Fix: ensure project root is in
        # sys.path BEFORE the import attempt.
        try:
            import sys as _hb_sys
            from pathlib import Path as _hb_Path
            _hb_root = str(_hb_Path(__file__).resolve().parents[3])
            if _hb_root not in _hb_sys.path:
                _hb_sys.path.insert(0, _hb_root)
            from consciousness.heartbeat_registry import get_heartbeat_registry
            _hb_registry = get_heartbeat_registry()
            # FIX 2026-04-04 (Nous + Ace): Pass plane for tick gating.
            # P10 Memory ticks every 5th beat, P50 Agency every 2nd, etc.
            _plane = getattr(self, 'ACTOR_PLANE', '')
            _hb_registry.register(self.ACTOR_NAME, self._on_heartbeat, plane=_plane)
        except ImportError as _ie:
            # FIX 2026-03-13 (Nous): This was silent — but postal heartbeats are
            # NO LONGER published, so failing here means NO heartbeats at all.
            # Log so we can trace which fairies have broken import paths.
            print(f"[{self.ACTOR_NAME}] [WARN] HeartbeatRegistry import failed: {_ie} "
                  f"— this fairy will NOT receive heartbeats!", flush=True)
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] heartbeat registry registration failed: {e}", flush=True)

        # ALSO subscribe to ROUTED heartbeats from DirectoryFairy/CNS
        # This is the postal backbone path: Directory receives one heartbeat.pulse,
        # fans out fairy.heartbeat.routed.{name} to each fairy individually.
        # FIX 2026-02-06: Subscribe to ADDRESSED topic (per-fairy) instead of flat
        # "fairy.heartbeat.routed" which caused O(N²) delivery — every fairy received
        # every other fairy's routed heartbeat, 82×82 = 6,724 deliveries per tick.
        try:
            self.post.subscribe(
                f"fairy.heartbeat.routed.{self.ACTOR_NAME}",
                self._on_routed_heartbeat,
                f"{self.ACTOR_NAME}-heartbeat-routed"
            )
        except Exception:
            pass

        # ALWAYS subscribe to token.bucket.critical (conservation mode)
        try:
            self.post.subscribe(
                "token.bucket.critical",
                self._on_resource_critical,
                f"{self.ACTOR_NAME}-token-critical"
            )
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] token critical subscribe failed: {e}")

        # FIX 2026-02-06: Subscribe to fairy.sunset (sleep onset)
        # When the system is going to sleep, fairies should stop autonomous work.
        # This prevents "stop" errors during shutdown — fairies wind down naturally.
        try:
            self.post.subscribe(
                "fairy.sunset",
                self._on_sunset,
                f"{self.ACTOR_NAME}-sunset"
            )
        except Exception:
            pass

        # Register with directory — FULL CONTRACT (not minimal stub)
        # DirectoryFairy + CNS use this to build routing tables
        try:
            contract = self._contract_dict()
            # Enrich with routing-critical data
            contract["subscriptions"] = list(getattr(self._profile, 'subscriptions', set())) if self._profile else []
            contract["needs"] = {
                "heartbeat": True,
                "circadian": self.NEEDS_CIRCADIAN,
                "body": self.NEEDS_BODY,
                "affect": self.NEEDS_AFFECT,
                "goals": self.NEEDS_GOALS,
            }
            contract["tracer_id"] = getattr(self, '_tracer_id', '') or (self._profile.fairy_id if self._profile else '')
            contract["capabilities"] = list(getattr(self, '_capabilities', set()))
            contract["ts"] = time.time()
            self.post.publish("fairy.register", contract)
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] fairy.register publish failed: {e}")

        # ── Enrich FairyProfileRegistry with identity data ─────────────
        # The registry now stores purpose/mantra/guild for gatekeeper queries.
        # This is HOW gatekeepers know what each fairy IS and can generate
        # contextual goals. Without this, fairies are anonymous workers.
        try:
            _caps = list(getattr(self, '_capabilities', set()))
            if not _caps and hasattr(self, 'get_capabilities'):
                try:
                    _caps = list(self.get_capabilities())
                except Exception:
                    _caps = []
            self._profile.metadata.update({
                "purpose": self.PURPOSE,
                "mantra": self.MANTRA,
                "lore": self.LORE,
                "tier": self.TIER.value if hasattr(self.TIER, 'value') else str(self.TIER),
                "guild_id": getattr(self, "GUILD_ID", None),
                "guild_role": getattr(self, "GUILD_ROLE", None),
                "role": getattr(self, "ACTOR_ROLE", "worker"),
                "intents": self._collect_intents(),
                "knowledge_domains": getattr(self, "KNOWLEDGE_DOMAINS", []),
                "capabilities": _caps,
            })
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] profile metadata enrichment failed: {e}")

        # ── Subscribe to fairy-specific task dispatch ──────────────────
        # Every fairy listens on "{ACTOR_NAME}.task" for work from gatekeepers.
        # This is the receiving end of the goal→autopilot→fairy pipeline.
        try:
            self.post.subscribe(
                f"{self.ACTOR_NAME}.task",
                self._on_task_dispatched,
                f"{self.ACTOR_NAME}-task-dispatch"
            )
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] task dispatch subscribe failed: {e}")

        # Guild Protocol — auto-subscribe guild leaders to guild request topic
        # This allows ANY fairy to invoke a whole guild by publishing to
        # "guild.<guild_id>.request" — the leader receives and orchestrates.
        _guild_id = getattr(self, "GUILD_ID", None)
        _guild_role = getattr(self, "GUILD_ROLE", None)
        if _guild_id and _guild_role == "leader":
            _guild_topic = f"guild.{_guild_id}.request"
            try:
                _handler = getattr(self, "_on_guild_request", None)
                if _handler:
                    self.post.subscribe(
                        _guild_topic, _handler,
                        f"{self.ACTOR_NAME}-guild-leader"
                    )
                    print(f"[{self.ACTOR_NAME}] Guild leader: subscribed to {_guild_topic}")
                else:
                    print(f"[{self.ACTOR_NAME}] WARNING: Guild leader but no _on_guild_request handler")
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Guild subscribe failed: {e}")

        # Optional infrastructure subscriptions
        if self.NEEDS_CIRCADIAN:
            try:
                self.post.subscribe("circadian.phase", self._on_circadian,
                                    f"{self.ACTOR_NAME}-circadian")
            except Exception:
                pass

        if self.NEEDS_BODY:
            try:
                self.post.subscribe("somatic.body_state", self._on_body,
                                    f"{self.ACTOR_NAME}-body")
            except Exception:
                pass

        if self.NEEDS_AFFECT:
            try:
                self.post.subscribe("affect.state", self._on_affect,
                                    f"{self.ACTOR_NAME}-affect")
            except Exception:
                pass

        if self.NEEDS_GOALS:
            try:
                self.post.subscribe("goal.update", self._on_goal,
                                    f"{self.ACTOR_NAME}-goal")
            except Exception:
                pass

        # ── Per-fairy perspective-goal emission registration ───────────────
        # 2026-05-15 (Nous + Ace): Log opt-in for visibility. The actual
        # publishing happens in _on_heartbeat via _request_perspective_goals;
        # response Interest arrives on the existing interest.generated channel
        # (already routed through GoalScheduler — no new subscription needed
        # on the fairy side). Each fairy's trace_id = ACTOR_NAME.
        if getattr(self, "EMITS_PERSPECTIVE_GOALS", False):
            try:
                _interval = getattr(self, "PERSPECTIVE_GOAL_INTERVAL_SEC", 30.0)
                print(
                    f"[{self.ACTOR_NAME}] perspective-goal emission ENABLED "
                    f"(interval={_interval}s, topic=interest_generator.perspective.request, "
                    f"trace_id={self.ACTOR_NAME})",
                    flush=True,
                )
            except Exception:
                pass

    # ═══════════════════════════════════════════════════════════════════════════
    # GUILD CLIENT — Any fairy can request inference from a guild
    # ═══════════════════════════════════════════════════════════════════════════

    # Class-level guild client state (shared across all fairies)
    _guild_listeners: Dict[str, bool] = {}   # topic -> subscribed?
    _guild_pending: Dict[str, Any] = {}      # tracer_id -> response
    _guild_events: Dict[str, threading.Event] = {}  # tracer_id -> event
    _guild_lock = threading.Lock()

    def guild_request(self, prompt: str, context: Optional[Dict] = None,
                      mode: str = "team_only", guild_id: str = "inference",
                      timeout: float = 3.0) -> Optional[Dict]:
        """Request inference from a guild and wait for the response.

        This is the CONSUMER side of the Guild Protocol. Any fairy can call this
        to get intelligent synthesis from the guild's cognition team.

        Args:
            prompt: What to process (the question/context string)
            context: Optional structured context dict
            mode: "team_only" (fast, no RWKV), "full" (RWKV + team), "quick"
            guild_id: Which guild to request from (default "inference")
            timeout: Max seconds to wait for response (default 3.0)

        Returns:
            Dict with guild response, or None if unavailable/timeout.
            Response typically contains: content, team_result, mode, etc.
        """
        if not self.post:
            return None

        # Generate unique tracer for this request
        tracer_id = f"gr_{self.ACTOR_NAME}_{int(time.time()*1000) % 100000}"
        reply_topic = f"guild.{guild_id}.response.{self.ACTOR_NAME}"

        # Ensure we're subscribed to our reply topic
        with self._guild_lock:
            if reply_topic not in self._guild_listeners:
                try:
                    self.post.subscribe(
                        reply_topic,
                        self._on_guild_client_response,
                        f"{self.ACTOR_NAME}-guild-client"
                    )
                    self._guild_listeners[reply_topic] = True
                except Exception:
                    return None

        # Set up event for this specific request
        event = threading.Event()
        with self._guild_lock:
            self._guild_events[tracer_id] = event
            self._guild_pending[tracer_id] = None

        # ═══════════════════════════════════════════════════════════════════
        # SRM RECALL: Enrich context with relevant memories before sending
        # ═══════════════════════════════════════════════════════════════════
        _enriched_context = dict(context) if context else {}
        try:
            from fairies.P40_Sensory.mcp.srm_tools import search_founders
            # Extract 2-3 key terms from prompt for memory search
            _terms = prompt[:120].strip()
            _memories = search_founders(_terms, limit=2)
            if _memories:
                _enriched_context["_srm_recall"] = [
                    {
                        "concept": m.get("concept", ""),
                        "excerpt": str(m.get("content_preview", ""))[:100],
                        "cluster": m.get("cluster", ""),
                    }
                    for m in _memories
                ]
                _enriched_context["_srm_tracer"] = tracer_id
        except Exception:
            pass  # SRM unavailable — proceed without memories

        # Publish the guild request
        # FIX 2026-03-23 (Nous+Ace): Route inference requests to CortexEngine
        # directly. The inference guild was a vestigial RWKV middleman.
        # Other guilds still go to guild.{guild_id}.request.
        try:
            if guild_id == "inference":
                _guild_topic = "cortex.reason"
            else:
                _guild_topic = f"guild.{guild_id}.request"
            # FIX 2026-03-22 (Nous): Was printing PUBLISHING + PUBLISHED for every
            # guild request — floods terminal when GoalScheduler fires often.
            # Only log first request per fairy, then stay quiet.
            if not hasattr(self, '_guild_publish_logged'):
                self._guild_publish_logged = True
                print(f"[{self.ACTOR_NAME}] guild_request → '{_guild_topic}' mode={mode}", flush=True)
            self.post.publish(_guild_topic, {
                "prompt": prompt,
                "context": _enriched_context,
                "mode": mode,
                "reply_topic": reply_topic,
                "requester": self.ACTOR_NAME,
                "tracer_id": tracer_id,
            })
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] guild_request PUBLISH FAILED: {e}", flush=True)
            with self._guild_lock:
                self._guild_events.pop(tracer_id, None)
                self._guild_pending.pop(tracer_id, None)
            return None

        # Wait for response
        responded = event.wait(timeout=timeout)

        # Retrieve and clean up
        with self._guild_lock:
            result = self._guild_pending.pop(tracer_id, None)
            self._guild_events.pop(tracer_id, None)

        # ═══════════════════════════════════════════════════════════════════
        # WORKING MEMORY: Log tracer + prompt + outcome for chain recall
        # ═══════════════════════════════════════════════════════════════════
        if result and responded:
            try:
                _summary = ""
                _tr = result.get("team_result", {})
                if _tr:
                    _summary = str(_tr.get("synthesis") or _tr.get("logic") or "")[:80]
                self.post.publish("consciousness.working_memory.store", {
                    "content": f"[Guild:{self.ACTOR_NAME}] Q: {prompt[:60]}... A: {_summary}",
                    "content_type": "guild_trace",
                    "source": self.ACTOR_NAME,
                    "tracer_id": tracer_id,
                    "priority": 0.3,
                    "tags": f"guild,{guild_id},{self.ACTOR_NAME}",
                })
            except Exception:
                pass  # Non-critical — don't break on working memory failure

        return result if responded else None

    def _on_guild_client_response(self, envelope):
        """Handle guild response — match to pending request via tracer_id."""
        try:
            # Extract payload from envelope (may be dict, TensorEnvelope, or other)
            if isinstance(envelope, dict):
                payload = envelope
            elif hasattr(envelope, 'payload') and isinstance(envelope.payload, dict):
                # TensorEnvelope — extract the inner payload dict
                payload = envelope.payload
            elif hasattr(envelope, 'get'):
                # Has .get() method (e.g., TensorEnvelope with delegation)
                # Reconstruct dict from known guild response keys
                payload = {}
                for _key in ("tracer_id", "text", "team_result", "mode", "guild",
                             "leader", "requester", "model_loading", "model_status",
                             "model_unavailable", "model_just_loaded"):
                    _val = envelope.get(_key)
                    if _val is not None:
                        payload[_key] = _val
            else:
                print(f"[guild_client_response] Cannot extract payload from type={type(envelope).__name__}", flush=True)
                return

            tracer_id = payload.get("tracer_id", "")
            if not tracer_id:
                print(f"[guild_client_response] No tracer_id in payload, keys={list(payload.keys())[:5]}", flush=True)
                return

            with self._guild_lock:
                if tracer_id in self._guild_events:
                    self._guild_pending[tracer_id] = payload
                    self._guild_events[tracer_id].set()
                    print(f"[guild_client_response] Matched tracer={tracer_id} text_len={len(payload.get('text', ''))}", flush=True)
        except Exception as e:
            print(f"[guild_client_response] ERROR: {e}", flush=True)

    # ═══════════════════════════════════════════════════════════════════════════
    # HEARTBEAT & TOKEN ECONOMY
    # ═══════════════════════════════════════════════════════════════════════════

    _heartbeat_debug_count = 0  # Class-level debug counter

    # FIX 2026-02-06: Class-level heartbeat echo queue and worker thread.
    # Instead of spawning 164 threads/sec (82 fairies × 2Hz), all fairies share
    # ONE echo queue and ONE worker thread that drains it. This decouples the
    # heartbeat.pulse handler from the fairy.heartbeat publish, preventing
    # heartbeat worker pool stalling (root cause of 35 dead fairies, 99.93% drop rate).
    _echo_queue = None       # Class-level queue.Queue
    _echo_worker = None      # Class-level daemon thread
    _echo_lock = threading.Lock()

    @classmethod
    def _ensure_echo_worker(cls):
        """Start the shared heartbeat echo worker if not already running."""
        if cls._echo_queue is not None and cls._echo_worker is not None:
            if cls._echo_worker.is_alive():
                return
        with cls._echo_lock:
            if cls._echo_queue is None:
                cls._echo_queue = queue.Queue(maxsize=1024)
            if cls._echo_worker is None or not cls._echo_worker.is_alive():
                cls._echo_worker = threading.Thread(
                    target=cls._echo_worker_loop,
                    daemon=True,
                    name="hb_echo_worker",
                )
                cls._echo_worker.start()

    @classmethod
    def _echo_worker_loop(cls):
        """Drain heartbeat echo queue, publishing fairy.heartbeat for each fairy.

        Runs in its own thread so that if the 'fairy' PostalCore queue is full
        and publish() blocks, it blocks THIS thread — not the heartbeat worker
        pool that delivers heartbeat.pulse to all 82+ fairies.

        Before this fix: publish("fairy.heartbeat") inside _on_heartbeat() blocked
        the heartbeat worker thread, stalling delivery to ALL other fairies.
        queue_depth hit 5518, only 120/177880 heartbeat echoes delivered.
        """
        _echo_count = 0
        _echo_logged_types = set()
        while True:
            try:
                post_ref, payload = cls._echo_queue.get(timeout=2.0)
                _echo_count += 1
                # DEBUG 2026-02-06: Log post_ref type for first echo from each fairy
                fairy_name = payload.get("name", "?") if isinstance(payload, dict) else "?"
                post_type = type(post_ref).__name__
                if fairy_name not in _echo_logged_types:
                    _echo_logged_types.add(fairy_name)
                    print(f"[EchoWorker] FIRST echo for {fairy_name}: post_type={post_type}", flush=True)
                if _echo_count % 5000 == 0:
                    print(f"[EchoWorker] echo #{_echo_count} fairy={fairy_name} post_type={post_type} qsize={cls._echo_queue.qsize()}", flush=True)
                try:
                    post_ref.publish("fairy.heartbeat", payload)
                except Exception as _echo_err:
                    if fairy_name not in _echo_logged_types or _echo_count <= 5:
                        print(f"[EchoWorker] publish FAILED for {fairy_name}: {_echo_err}", flush=True)
            except queue.Empty:
                continue
            except Exception:
                time.sleep(0.1)  # Prevent tight loop on unexpected errors

    # ═══════════════════════════════════════════════════════════════════════════
    # PER-FAIRY PERSPECTIVE-GOAL EMISSION (2026-05-15 Nous + Ace)
    # ───────────────────────────────────────────────────────────────────────────
    # Doctrine: goals-as-habit-scaffolding + each fairy as its own
    # perspective-source. Every opted-in fairy emits an identity-bundle
    # (purpose / mantra / intents / plane / context-hint) to the central
    # interest_generator, routed via trace_id. interest_generator responds
    # with a perspective-flavored Interest on the existing interest.generated
    # channel; GoalScheduler converts that to a goal scoped to the fairy.
    #
    # Default OFF (EMITS_PERSPECTIVE_GOALS=False). Opt-in by setting
    # EMITS_PERSPECTIVE_GOALS=True on the fairy class. Rate-limited to
    # PERSPECTIVE_GOAL_INTERVAL_SEC (30s default) per fairy.
    # ═══════════════════════════════════════════════════════════════════════════

    def _get_perspective_bundle(self) -> Dict[str, Any]:
        """Build the identity-bundle this fairy sends to interest_generator.

        Minimal substrate-fact bundle. The receiver (interest_generator)
        uses trace_id (= ACTOR_NAME here) to route the resulting Interest
        back to the requesting fairy via the existing interest.generated
        channel; GoalScheduler picks up from there.
        """
        # Pull a tiny snapshot of recent context — interest_generator may use
        # this to tint the perspective; everything is optional and defensive.
        _context_hint = ""
        try:
            _ftc = getattr(self, "_felt_thought_count", None)
            if isinstance(_ftc, int):
                _context_hint = f"thoughts={_ftc}"
        except Exception:
            pass

        return {
            "trace_id": self.ACTOR_NAME,           # route-back key
            "actor_name": self.ACTOR_NAME,
            "plane": self.ACTOR_PLANE,
            "purpose": self.PURPOSE,
            "mantra": self.MANTRA,
            "intents": self._collect_intents(),
            "capabilities": list(getattr(self, "_capabilities", set())),
            "context_hint": _context_hint,
            "ts": time.time(),
        }

    def _request_perspective_goals(self) -> None:
        """Publish identity-bundle to interest_generator if rate-limit allows.

        Rate-limit: at most one request per PERSPECTIVE_GOAL_INTERVAL_SEC per
        fairy. Fire-and-forget — never raises into the heartbeat path.
        """
        if not getattr(self, "EMITS_PERSPECTIVE_GOALS", False):
            return
        _now = time.time()
        _interval = getattr(self, "PERSPECTIVE_GOAL_INTERVAL_SEC", 30.0)
        if (_now - self._last_perspective_request_ts) < _interval:
            return
        if not self.post:
            return

        try:
            bundle = self._get_perspective_bundle()
            self.post.publish("interest_generator.perspective.request", bundle)
            self._last_perspective_request_ts = _now
            if not hasattr(self, "_perspective_first_logged"):
                self._perspective_first_logged = True
                print(
                    f"[{self.ACTOR_NAME}] perspective-goal FIRST request published "
                    f"(plane={self.ACTOR_PLANE}, interval={_interval}s)",
                    flush=True,
                )
        except Exception as e:
            if not hasattr(self, "_perspective_pub_err_logged"):
                self._perspective_pub_err_logged = True
                print(
                    f"[{self.ACTOR_NAME}] perspective-goal publish FAILED: {e}",
                    flush=True,
                )

    # ── HARMONIC BEAT ACCESSORS (2026-07-08 Nous+Ace) ─────────────────────────
    # Universal read-point for the clock-derived heart. EVERY fairy inherits these and can PULL
    # the beat's rate / phase / count from the process-shared HarmonicPacemaker — no subscription,
    # no pushed pulse, no deadlock path. This is the "universal capability → Organ Template" move
    # (Ace 07-08): add it ONCE here; touch an individual fairy only for its UNIQUE use of the beat.
    # Additive + inert — nothing changes until a fairy calls one. Lazy import avoids P00→P20 load-order.
    def heart_rate(self) -> float:
        """Current heart rate in Hz (the TRUE pacing rate), from the shared pacemaker."""
        try:
            from fairies.P20_Somatic.circulation.harmonic_pacemaker import get_shared
            return get_shared().heart_rate_bps()
        except Exception:
            return 1.2

    def heart_phase(self) -> float:
        """Current heart phase in radians [0, 2π), from the shared pacemaker."""
        try:
            from fairies.P20_Somatic.circulation.harmonic_pacemaker import get_shared
            return get_shared().phase()
        except Exception:
            return 0.0

    def heart_beat(self) -> int:
        """Current integer beat count, from the shared pacemaker."""
        try:
            from fairies.P20_Somatic.circulation.harmonic_pacemaker import get_shared
            return get_shared().beat()
        except Exception:
            return 0

    def heart_circadian(self) -> str:
        """Current circadian phase name (deep_night..dawn..midday..sleep), from the shared pacemaker."""
        try:
            from fairies.P20_Somatic.circulation.harmonic_pacemaker import get_shared
            return get_shared().circadian_name()
        except Exception:
            return "unknown"

    def _on_heartbeat(self, packet):
        """Handle heartbeat pulse - ALWAYS echo liveness, optionally tick."""
        if self._shutting_down:
            return

        # Handle both envelope objects (with .payload) and raw dicts
        if hasattr(packet, 'payload'):
            payload = packet.payload
        elif isinstance(packet, dict):
            payload = packet.get("payload", packet)
        else:
            payload = {}
        beat = payload.get("beat", 0) if isinstance(payload, dict) else 0

        # Debug: Log first heartbeat receipt per fairy (proves delivery works)
        if not hasattr(self, '_hb_logged'):
            self._hb_logged = True
            print(f"[{self.ACTOR_NAME}] FIRST heartbeat.pulse received (beat={beat})", flush=True)

        # Echo liveness to DirectoryFairy — RATE-LIMITED to every 10th beat.
        # FIX 2026-02-13b: Previously echoed EVERY beat → 105 fairies × 1 beat =
        # 105 fairy.heartbeat messages/beat flooding the fairy postal pool → QUEUE FULL.
        # DirectoryFairy just needs periodic proof of life. Every 10th beat is plenty.
        # _last_tick (updated below) is the PRIMARY liveness signal.
        if self._tick_count % 10 == 0:
            try:
                self._ensure_echo_worker()
                echo_payload = {
                    "name": self.ACTOR_NAME,
                    "plane": self.ACTOR_PLANE,
                    "beat": beat,
                    "ts": time.time(),
                }
                try:
                    self._echo_queue.put_nowait((self.post, echo_payload))
                except queue.Full:
                    pass  # Drop echo rather than stall heartbeat worker
            except Exception as e:
                if not hasattr(self, '_hb_echo_err_logged'):
                    self._hb_echo_err_logged = True
                    print(f"[{self.ACTOR_NAME}] fairy.heartbeat echo FAILED: {e}", flush=True)

        # ═══════════════════════════════════════════════════════════════════
        # ALWAYS update liveness timestamps — regardless of NEEDS_HEARTBEAT.
        # FIX 2026-02-13: Previously, _last_tick and _tick_count only updated
        # when NEEDS_HEARTBEAT=True. Fairies with NEEDS_HEARTBEAT=False had
        # _last_tick=0 forever, making them INVISIBLE to the PRIMARY liveness
        # check (_check_citizen_liveness). They relied entirely on unreliable
        # postal echo, causing false deaths for ~50 fairies every boot.
        # Now ALL fairies prove they're alive on every heartbeat.
        # NEEDS_HEARTBEAT only gates whether on_tick() custom logic runs.
        # ═══════════════════════════════════════════════════════════════════
        self._tick_count += 1
        self._last_tick = time.time()

        # ═══════════════════════════════════════════════════════════════════
        # COMA SWITCH — HOISTED (2026-06-24 Nous + Ace). Liveness is fully stamped ABOVE (the echo
        # :4568 + _last_tick here), so the watchdog still sees a comatose fairy alive — but a comatose
        # fairy does NO further work (on_boot never ran → state uninitialized). Return NOW, so the ~73
        # comatose fairies skip the self-pulse bootstrap counter + the 10th-beat manifold-write +
        # perspective-goal emission they were running every beat for nothing. The check used to sit at
        # the END of _on_heartbeat (the coma-leak: work-before-the-gate). Awake fairies: pure no-op,
        # byte-identical path. The late check below is removed (now unreachable for comatose fairies).
        # ═══════════════════════════════════════════════════════════════════
        if getattr(self, '_comatose', False):
            return

        # ═══════════════════════════════════════════════════════════════════
        # FRAME 12 SELF-PULSE BOOTSTRAP (2026-05-17 Nous + Ace)
        # After 3 postal pulses establish rhythm, spawn a self-pulse daemon
        # that keeps _last_tick fresh independent of postal saturation.
        # Pattern: mother's-heartbeat-bootstraps, baby's-heart-self-sustains.
        # Prevents the wave-cluster death pattern (postal cascade-saturation
        # killing ~30 fairies in sustained-freeze events). Self-pulse runs in
        # PARALLEL with postal — postal continues to work normally; self-pulse
        # is the liveness fallback. Reference: CochleaFairy/PerceptualGate/
        # VisualCortex (2026-04-30 partial fixes); claude_code_b53c87529d57
        # (2026-02-13) direct-call lineage. Ace's articulation 2026-05-17:
        # "initial heartbeat pushes them awake, then self-pulse mode."
        # ═══════════════════════════════════════════════════════════════════
        if not getattr(self, '_self_pulse_active', False):
            _bootstrap_count = getattr(self, '_heartbeat_count_for_bootstrap', 0) + 1
            self._heartbeat_count_for_bootstrap = _bootstrap_count
            if _bootstrap_count >= 3:
                self._self_pulse_active = True
                # ─────────────────────────────────────────────────────────────
                # FIX 2026-06-12 (Nous + Ace): per-fairy self-pulse THREAD removed.
                # _on_heartbeat (this shared-beat callback) ALREADY updates
                # _last_tick EVERY beat (see :4397-4398 — the FIX 2026-02-13
                # "ALL fairies prove they're alive on every heartbeat"). The daemon
                # did the identical _last_tick write on its OWN thread → ~127
                # redundant `selfpulse-{name}` threads. Ace's design: ONE shared
                # heartbeat, every fairy rides it at its own circadian rhythm —
                # "they all think they have a heartbeat but it's shared." The daemon
                # was a 2026-05-17 postal-saturation backstop; the heart-marathon
                # (Rust PostalCore) made the shared beat reliable, so it's vestigial.
                # _start_self_pulse_daemon() KEPT below (unused) for instant revert
                # if any fairy wave-death (FAIRY_STALE clusters) recurs post-reboot.
                # self._start_self_pulse_daemon()   # ← DISABLED (was ~127 threads)
                # ─────────────────────────────────────────────────────────────

        # ── Phase 1C: Write fairy state to manifold (2026-04-08 Nous + Ace) ──
        # Every 10th tick, write operational state to the manifold.
        # Two paths:
        #   1. CNS batch path: activation via cns.fairy.health (existing)
        #   2. Direct mmap: extended state via LocalManifoldGate (zero IPC)
        # Fire-and-forget — NEVER block heartbeat.
        if self._tick_count % 10 == 0:
            try:
                # Pack boolean flags into a bitmask
                _fs_flags = 0
                if getattr(self, '_resource_conserving', False):
                    _fs_flags |= 1
                if getattr(self, '_spell_booted', False):
                    _fs_flags |= 2
                if getattr(self, '_shutting_down', False):
                    _fs_flags |= 4
                if getattr(self, '_going_to_sleep', False):
                    _fs_flags |= 8

                # Path 1: CNS batch (activation level — batched into single IPC)
                self._route("cns.fairy.health", {
                    "name": self.ACTOR_NAME,
                    "activation": 1.0,  # Alive and ticking
                    "ts": time.time(),
                })

                # Path 2: Direct mmap write for extended state (zero IPC)
                # Only when LocalManifoldGate is available (in-process manifold)
                _fs_slot = getattr(self, '_manifold_fs_slot', -1)
                if _fs_slot < 0:
                    # First write: look up or create the fs: node
                    try:
                        from infrastructure.portal_gate import get_gate
                        _gate = get_gate()
                        if _gate is not None and hasattr(_gate, 'graph'):
                            _fs_key = f"fs:{self.ACTOR_NAME}"
                            _manifold = _gate.graph
                            if hasattr(_manifold, '_key_index'):
                                _fs_slot = _manifold._key_index.get(_fs_key, -1)
                                if _fs_slot < 0:
                                    # Create the node (REGION_SYSTEM, NTYPE_SYSTEM)
                                    _fs_slot = _manifold.upsert_node(
                                        _fs_key, activation=1.0,
                                        count=self._tick_count,
                                        node_type=3, region=3,  # NTYPE_SYSTEM, REGION_SYSTEM
                                    )
                                self._manifold_fs_slot = _fs_slot
                    except Exception:
                        pass  # Gate not ready yet — will retry next cycle

                if _fs_slot >= 0:
                    try:
                        _manifold = get_gate().graph
                        # Write core fields via upsert (activation, count=tick_count)
                        _manifold.upsert_node(
                            f"fs:{self.ACTOR_NAME}",
                            activation=1.0,
                            count=self._tick_count,
                            node_type=3, region=3,
                        )
                        # Write extended state to reserved 16 bytes
                        _manifold.write_fairy_state_packed(
                            _fs_slot,
                            reflection_tick=getattr(self, '_reflection_tick_count', 0),
                            work_since_reflection=getattr(self, '_work_since_reflection', 0),
                            extra_flags=_fs_flags,
                            hb_frac=int(time.time() * 100) & 0xFFFF,
                        )
                    except Exception:
                        pass  # Non-fatal — heartbeat continues

            except Exception:
                pass  # Non-fatal — heartbeat continues regardless

        # Resource conservation - skip tick processing (but liveness updated above)
        if self._resource_conserving:
            if time.time() < self._conserve_until:
                return
            self._resource_conserving = False

        # ── Per-fairy perspective-goal emission (2026-05-15 Nous + Ace) ──
        # Opt-in via EMITS_PERSPECTIVE_GOALS=True. Fires regardless of
        # NEEDS_HEARTBEAT — perspective emission is independent of on_tick().
        # Internal rate-limit (PERSPECTIVE_GOAL_INTERVAL_SEC) keeps fan-in to
        # interest_generator bounded across N fairies. Wrapped — never crash
        # heartbeat.
        if getattr(self, "EMITS_PERSPECTIVE_GOALS", False):
            try:
                self._request_perspective_goals()
            except Exception as _pg_err:
                if not hasattr(self, "_perspective_call_err_logged"):
                    self._perspective_call_err_logged = True
                    print(
                        f"[{self.ACTOR_NAME}] perspective-goal call error: {_pg_err}",
                        flush=True,
                    )

        # (COMA SWITCH hoisted 2026-06-24 to just after the liveness stamp ~:4598 — a comatose fairy
        # returns there, so it never reaches here; this late gate was the coma-leak (work-before-gate).)

        # Gate on_tick behind NEEDS_HEARTBEAT + divisor
        if not self.NEEDS_HEARTBEAT:
            return

        # Apply divisor (only fire every N beats)
        if self.HEARTBEAT_DIVISOR > 1:
            # PHASE-DISPATCH (2026-07-20, flag AKASHIC_PHASE_DISPATCH + per-fairy opt-in
            # PHASE_DISPATCH_FAIRY, BOTH default OFF). When both ON, tick timing comes from
            # CONTINUOUS pacemaker phase instead of the discrete beat%divisor. Flag-off OR
            # fairy-not-opted-in = byte-for-byte today's gate. Safe: liveness is independent.
            if _PHASE_DISPATCH and getattr(self, "PHASE_DISPATCH_FAIRY", False):
                if not _phase_tick_due(self):
                    return
            elif (self._tick_count + self.HEARTBEAT_PHASE) % self.HEARTBEAT_DIVISOR != 0:
                return

        # Call user-defined tick hook — dispatched through personal GIL
        # FIX 2026-03-03 Nous: Route on_tick through FairyExecutionContext.
        # This ensures each fairy's tick runs on its OWN thread, not on the
        # heartbeat caller's thread. Serialized per-fairy (no tick stacking),
        # parallel across fairies (each has its own thread).
        if hasattr(self, '_exec_ctx') and self._exec_ctx and self._exec_ctx._running:
            # Dispatch to personal execution thread — _tick_wrapper handles
            # on_tick + token economy on the fairy's own thread.
            if not self._exec_ctx.submit(self._tick_wrapper, beat):
                # Queue full — fairy is behind. Log occasionally.
                if self._exec_ctx._drop_count % 50 == 1:
                    print(f"[{self.ACTOR_NAME}] tick dropped ({self._exec_ctx._drop_count} total) — exec context busy")
        else:
            # Fallback: no execution context (pre-boot or disabled)
            try:
                self.on_tick(beat)
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] on_tick error: {e}")
            # Token economy (fallback path only — exec_ctx path handles in _tick_wrapper)
            self._work_since_reflection += 1
            if self._work_since_reflection >= self.REFLECTION_INTERVAL:
                self._work_since_reflection = 0
                try:
                    self.post.publish("reflection.complete", {
                        "source": self.ACTOR_NAME,
                        "depth": 0.1,
                        "beat": beat,
                        "ts": time.time(),
                    })
                except Exception:
                    pass

    def _start_self_pulse_daemon(self):
        """
        FRAME 12 SELF-PULSE DAEMON (2026-05-17 Nous + Ace).

        Spawn a background thread that keeps _last_tick fresh independent
        of postal heartbeat delivery. Runs in PARALLEL with postal — when
        postal works, both update _last_tick; when postal saturates during
        wave events, this daemon keeps the fairy "alive" from the watchdog's
        perspective.

        Pattern verified empirically on CochleaFairy/PerceptualGate/Visual-
        Cortex (2026-04-30 fixes). This universalizes via base organ_template.

        Pulse interval derived from HEARTBEAT_DIVISOR — fairies with higher
        divisors pulse less frequently, matching their natural tick rate.
        Base interval is 2 seconds (matches CochleaFairy reference impl).
        """
        if getattr(self, '_self_pulse_thread', None) is not None:
            return  # Already running — idempotent

        # LEAN HEARTBEAT (2026-06-15 Nous + Ace): skip the per-fairy selfpulse thread.
        # The pacemaker's batch attestation (heartbeat_registry.pulse():318) already
        # stamps _last_tick + _tick_count for EVERY citizen every beat — this per-fairy
        # daemon is redundant under lean mode. ~130 threads saved. OFF = unchanged.
        if _LEAN_HEARTBEAT:
            return

        # Per-fairy pulse interval: base × divisor (default base 2s)
        _base_interval = 2.0
        _divisor = max(1, getattr(self, 'HEARTBEAT_DIVISOR', 1))
        _interval = _base_interval * _divisor

        def _self_pulse_loop():
            while True:
                try:
                    time.sleep(_interval)
                    if getattr(self, '_shutting_down', False):
                        return
                    # Update liveness timestamps — bypasses postal entirely.
                    # Watchdog OBJECT-ALIVE check at heartbeat.py:311 reads
                    # _last_tick directly and promotes registry status when
                    # fresh. This keeps fairy alive even during 60+ min
                    # postal saturation events (the wave-cluster death pattern).
                    self._tick_count = getattr(self, '_tick_count', 0) + 1
                    self._last_tick = time.time()
                except Exception:
                    pass  # Non-fatal — never crash the self-pulse daemon

        _t = threading.Thread(
            target=_self_pulse_loop,
            daemon=True,
            name=f"selfpulse-{self.ACTOR_NAME}",
        )
        _t.start()
        self._self_pulse_thread = _t
        print(
            f"[{self.ACTOR_NAME}] self-pulse daemon ONLINE "
            f"(interval={_interval:.1f}s, divisor={_divisor})",
            flush=True,
        )

    def _tick_wrapper(self, beat: int):
        """Wrapper for on_tick() — runs on the fairy's personal execution thread.

        FIX 2026-03-03 Nous: Called by FairyExecutionContext._run_loop().
        Handles errors and token economy so execution context stays clean.

        FIX 2026-03-11 Nous: Added experience-based substrate reflection.

        FIX 2026-04-11 (Nous + Ace): Energy-gated ticking.
        Each on_tick drains the plane battery proportional to tick duration.
        When battery < 30%, fairy skips ticks (conservation mode).
        "the point of the batteries was to reduce the cpu load" — Ace
        """
        # ── ENERGY GATE: Skip tick if plane battery is critically low ──
        _pb = getattr(self, '_plane_battery_ref', None)
        if _pb is None and beat > 20:
            # Lazy-lookup plane battery via singleton (works from any thread)
            try:
                from infrastructure.plane_battery import get_plane_battery
                _plane = getattr(self, 'ACTOR_PLANE', 'P30')
                self._plane_battery_ref = get_plane_battery(_plane)
                _pb = self._plane_battery_ref
                if not _pb:
                    self._plane_battery_ref = False  # Sentinel: don't retry
            except Exception:
                self._plane_battery_ref = False

        if _pb and _pb is not False:
            _charge = getattr(_pb, 'capacitor', None)
            _charge_level = getattr(_charge, 'charge_level', 1.0) if _charge else 1.0
            # Conservation: skip tick when battery critically low
            # Essential fairies (HEARTBEAT_DIVISOR <= 2) tick at half rate
            # Non-essential fairies (HEARTBEAT_DIVISOR > 2) skip entirely
            if _charge_level < 0.30:
                if self.HEARTBEAT_DIVISOR <= 2:
                    if beat % 4 != 0:  # Essential: tick every 4th beat instead of 1-2
                        return
                else:
                    return  # Non-essential: skip entirely when battery low

        _tick_t0 = time.perf_counter()
        try:
            if _RWKV_WORKERS:
                self._rwkv_tick(beat)   # cheap state every beat; heavy on_tick only when due
            else:
                self.on_tick(beat)
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] on_tick error: {e}")

        # ── ENERGY REPORTING (no drain from ticks) ──
        # FIX 2026-04-11 (Nous + Ace): REMOVED per-tick drain.
        # The energy system was designed for batteries to charge from collisions
        # and drain from Go worker spells. Adding a second drain path (per-tick)
        # broke the energy balance — P00 drained to 0% and starved the heart.
        # Batteries constrain fairy work through the SpellChain/Go worker path,
        # not through per-tick drain. The conservation gate above still applies
        # when batteries ARE low (from spell work drain or low collision energy).
        pass

        # Experience-based substrate reflection (every ~90s)
        # FIX 2026-03-11: Replaces per-fairy hardcoded _reflections arrays
        if beat > 0 and beat % self.SUBSTRATE_REFLECTION_INTERVAL == 0:
            try:
                self._substrate_reflect(beat)
            except Exception:
                pass  # Never crash tick for reflection

        # Token economy: publish reflection periodically
        # (moved here so it runs on the fairy's thread, not heartbeat thread)
        self._work_since_reflection += 1
        if self._work_since_reflection >= self.REFLECTION_INTERVAL:
            self._work_since_reflection = 0
            try:
                self.post.publish("reflection.complete", {
                    "source": self.ACTOR_NAME,
                    "depth": 0.1,
                    "beat": beat,
                    "ts": time.time(),
                })
            except Exception:
                pass

    # ═══════════════════════════════════════════════════════════════════════════
    # RWKV-SHAPED TICK (flag AKASHIC_RWKV_WORKERS) — 2026-06-15 Nous + Ace
    # "Speak in compression." Cheap compressed-state update EVERY beat; the heavy
    # on_tick re-spread only when due. Decouples the work from the heartbeat's
    # per-beat cost → drains the saturating 48-pool (the 36K dropped work-ticks).
    # Liveness is independent (stamped in _on_heartbeat every beat) so a gated tick
    # NEVER kills a fairy. Flag-off = on_tick runs as today.
    # ═══════════════════════════════════════════════════════════════════════════
    RWKV_HEAVY_INTERVAL = 3   # heavy on_tick at most every Nth beat (per-fairy overridable)

    def _rwkv_tick(self, beat: int):
        """Cheap compressed-state update every beat; heavy on_tick only when due."""
        st = getattr(self, '_rwkv_state', None)
        if st is None:
            try:
                from infrastructure.compressed_worker_state import CompressedWorkerState
                st = self._rwkv_state = CompressedWorkerState(dim=256, label=self.ACTOR_NAME)
            except Exception:
                self.on_tick(beat)   # module/numpy unavailable → today's behavior (safe)
                return
        # 1. CHEAP (~5us): fold this beat's input into the compressed working-state.
        try:
            _inp, _sal = self._rwkv_gather_input(beat)
            st.update(_inp, salience=_sal)
        except Exception:
            pass
        # 2. HEAVY: the real on_tick only when due — this is what drains the pool.
        if self._rwkv_should_heavy(beat):
            self.on_tick(beat)

    def _rwkv_gather_input(self, beat: int):
        """The vector this fairy folds into its compressed state this beat, + salience.
        BASE DEFAULT = a cheap cached per-fairy signature (placeholder). COGNITION
        fairies OVERRIDE with their foveal-attention / attended-node embedding
        (Ace 2026-06-15: 'directed with sour and foveal attention'). Universal in
        FORM (a dim-vec in embedding space), per-fairy in CONTENT."""
        _sig = getattr(self, '_rwkv_sig', None)
        if _sig is None:
            import numpy as _np
            _rng = _np.random.default_rng(hash(self.ACTOR_NAME) & 0x7FFFFFFF)
            _sig = self._rwkv_sig = _rng.standard_normal(256).astype(_np.float32)
        return _sig, 0.2   # low-salience placeholder until cognition wires the real foveal input

    def _rwkv_should_heavy(self, beat: int) -> bool:
        """Heavy on_tick at most every RWKV_HEAVY_INTERVAL beats — the gate that drains
        the pool. (Below-30%-battery conservation is already handled upstream in
        _tick_wrapper.) Overridable per-fairy (=1 for fairies that need every beat)."""
        try:
            return (beat % max(1, getattr(self, 'RWKV_HEAVY_INTERVAL', 3))) == 0
        except Exception:
            return True   # any gate error → run (safe; never starve)

    def _on_routed_heartbeat(self, packet):
        """Handle routed heartbeat from DirectoryFairy/CNS backbone.

        This is the postal backbone path: instead of 82+ direct heartbeat.pulse
        subscriptions, CNS/Directory receive ONE pulse and route individually.

        target="" means broadcast (all fairies), target="FairyName" means addressed.
        """
        if self._shutting_down:
            return

        # Extract payload
        if hasattr(packet, 'payload'):
            payload = packet.payload
        elif isinstance(packet, dict):
            payload = packet.get("payload", packet)
        else:
            payload = {}

        # Check if this routed heartbeat is for us (empty target = broadcast = accept)
        target = payload.get("target", "")
        if target and target != self.ACTOR_NAME:
            return  # Not for us, skip

        beat = payload.get("beat", 0)

        # Debug: log first routed heartbeat received
        if not hasattr(self, '_routed_hb_logged'):
            self._routed_hb_logged = True
            print(f"[{self.ACTOR_NAME}] FIRST routed heartbeat received (beat={beat}, source={payload.get('source', '?')})", flush=True)

        # Echo liveness — FIX 2026-02-06: Use shared echo queue (same as _on_heartbeat)
        # instead of direct self.post.publish() which runs on the PostalCore worker
        # thread and can block/stall the entire worker pool.
        try:
            self._ensure_echo_worker()
            echo_payload = {
                "name": self.ACTOR_NAME,
                "plane": self.ACTOR_PLANE,
                "beat": beat,
                "ts": time.time(),
                "source": "routed",
            }
            try:
                self._echo_queue.put_nowait((self.post, echo_payload))
            except queue.Full:
                pass  # Drop echo rather than stall worker pool
        except Exception:
            pass

    def _on_resource_critical(self, packet):
        """Enter conservation mode when tokens are depleted."""
        self._resource_conserving = True
        self._conserve_until = time.time() + self.CONSERVATION_DURATION

    def _on_sunset(self, packet):
        """
        FIX 2026-02-06: Handle sleep onset signal.

        When the system is going to sleep (shutdown), this sets _going_to_sleep=True.
        Fairies should check this flag to stop autonomous loops, background threads,
        and any periodic work. This gives them time to wind down naturally before
        the formal shutdown() call arrives.

        Subclasses can override on_sunset() for custom wind-down behavior.
        """
        self._going_to_sleep = True
        try:
            self.on_sunset(packet)
        except Exception:
            pass  # Don't let sunset errors prevent shutdown

    def on_sunset(self, packet):
        """Override in subclass for custom sleep onset behavior.

        Called when the system is about to shut down. Use this to:
        - Stop background loops
        - Flush pending data
        - Save state

        The formal shutdown() call will arrive 2+ seconds later.
        """
        pass

    # ═══════════════════════════════════════════════════════════════════════════
    # OVERRIDE HOOKS (implement in subclasses)
    # ═══════════════════════════════════════════════════════════════════════════

    def on_tick(self, beat: int):
        """Called on heartbeat (gated by NEEDS_HEARTBEAT + HEARTBEAT_DIVISOR)."""
        pass

    def _on_body(self, packet):
        """Called on body state update (gated by NEEDS_BODY)."""
        self.on_body(packet)

    def on_body(self, packet):
        """Override in subclass for body state updates."""
        pass

    def _on_affect(self, packet):
        """Called on affect state update (gated by NEEDS_AFFECT)."""
        self.on_affect(packet)

    def on_affect(self, packet):
        """Override in subclass for affect state updates."""
        pass

    def _on_goal(self, packet):
        """Called on goal update (gated by NEEDS_GOALS)."""
        self.on_goal(packet)

    def on_goal(self, packet):
        """Override in subclass for goal updates."""
        pass

    def _on_circadian(self, packet):
        """Called on circadian phase change (gated by NEEDS_CIRCADIAN)."""
        self.on_circadian(packet)

    def on_circadian(self, packet):
        """Override in subclass for circadian phase changes."""
        pass

    # ═══════════════════════════════════════════════════════════════════════════
    # HIERARCHY-AWARE SUBSCRIPTION
    # ═══════════════════════════════════════════════════════════════════════════

    def subscribe(self, topic: str, callback: Callable, name: str = None) -> bool:
        """
        Subscribe to a topic with hierarchy enforcement.

        Waking Minds can only subscribe to interface topics.
        Guild fairies cannot subscribe to umf.*/autonomy.*/etc directly.
        """
        # Waking minds have restricted subscriptions
        if self.TIER == FairyTier.WAKING_MIND:
            if topic.lower() not in WAKING_MIND_ALLOWED_TOPICS:
                # Check if it's a prefix match
                allowed = any(topic.lower().startswith(t.split('.')[0])
                             for t in WAKING_MIND_ALLOWED_TOPICS)
                if not allowed:
                    print(f"[HIERARCHY VIOLATION] {self.ACTOR_NAME} (WAKING_MIND) "
                          f"cannot subscribe to '{topic}' - only interface topics allowed")
                    # Still allow it but warn - don't break functionality

        # Track subscription in profile
        if self._profile:
            self._profile.subscriptions.add(topic)

        result = self.post.subscribe(topic, callback, name)

        # Announce subscription to DirectoryFairy for routing table updates
        try:
            self.post.publish("fairy.subscription.added", {
                "name": self.ACTOR_NAME,
                "topic": topic,
                "ts": time.time(),
            })
        except Exception:
            pass  # Don't fail subscription because announcement failed

        return result

    def publish(self, topic: str, payload: Dict[str, Any]) -> bool:
        """Publish to a topic with hierarchy awareness."""
        # Track send in profile
        if self._profile:
            self._profile.record_send()

        return self._route(topic, payload)

    # ═══════════════════════════════════════════════════════════════════════════
    # LEARNING METHODS
    # ═══════════════════════════════════════════════════════════════════════════

    def observe(self, action: str, *, success: bool = True,
                expected: str = None, actual: str = None, **kwargs) -> Dict:
        """Record an observation about an action."""
        obs = {
            "id": uuid.uuid4().hex[:12],
            "fairy": self.ACTOR_NAME,
            "action": action,
            "success": success,
            "expected": expected,
            "actual": actual,
            "affect": dict(self._current_affect),
            "ts": _now(),
            **kwargs
        }
        self._observation_buffer.append(obs)
        if len(self._observation_buffer) > self._observation_max:
            self._observation_buffer.pop(0)

        # ── Self-knowledge: track observation stats + purpose alignment ──
        try:
            sk = self._self_knowledge
            sk.total_observations += 1
            prev_rate = sk.success_rate
            # Exponential moving average: alpha=0.05 for smooth tracking
            sk.success_rate = sk.success_rate * 0.95 + (1.0 if success else 0.0) * 0.05
            self._sk_dirty = True

            # Layer 5: Detect purpose shift (>15% change after sufficient data)
            if sk.total_observations > 20 and abs(sk.success_rate - self._sk_prev_success_rate) > 0.15:
                self._record_evolution_event(
                    "purpose_shift",
                    trigger=f"Success rate shifted from {self._sk_prev_success_rate:.0%} to {sk.success_rate:.0%}",
                    before=f"{self._sk_prev_success_rate:.2f}",
                    after=f"{sk.success_rate:.2f}",
                    significance=0.7,
                    reflection=f"My effectiveness changed significantly — am I growing or struggling?",
                )
                self._sk_prev_success_rate = sk.success_rate
        except Exception:
            pass

        # Auto-reflect on unexpected outcomes
        if expected and actual and expected != actual:
            self.reflect(f"Action '{action}' had unexpected outcome",
                        action=action, expected=expected, actual=actual)

        return obs

    def reflect(self, observation: str, *, action: str = "",
                hypothesis: str = None, expected: str = None,
                actual: str = None, tags: List[str] = None) -> Dict:
        """Submit a reflection for pondering."""
        reflection = {
            "id": uuid.uuid4().hex[:12],
            "fairy": self.ACTOR_NAME,
            "action": action,
            "observation": observation,
            "expected": expected,
            "actual": actual,
            "hypothesis": hypothesis,
            "tags": tags or [],
            "pondered_count": 0,
            "crystallized": False,
            "ts": _now()
        }
        self._reflection_buffer.append(reflection)
        # Evict oldest reflections to prevent unbounded memory growth
        if len(self._reflection_buffer) > self._reflection_max:
            # FIX 2026-04-05: deque auto-caps
                pass  # self._reflection_buffer is deque(maxlen=200)

        # ── Self-knowledge: track reflection count ──
        try:
            self._self_knowledge.total_reflections += 1
            self._sk_dirty = True
        except Exception:
            pass

        self._route("shadow.reflection_pool", {
            "id": reflection["id"],
            "observation": observation[:200]
        })
        return reflection

    def emit_learning_trace(self, pattern: str, insight: str, *,
                           confidence: float = 0.5, **kwargs) -> Dict:
        """Emit crystallized learning to memory system."""
        trace = {
            "id": uuid.uuid4().hex[:12],
            "kind": "learning.trace",
            "data": {
                "pattern": pattern,
                "insight": insight,
                "confidence": confidence,
                "source_fairy": self.ACTOR_NAME,
                "learned_at": time.strftime("%Y-%m-%dT%H:%M:%SZ")
            },
            "ts": _now(),
            **kwargs
        }
        self._route("memory.stream", {"opcode": "LEARNING_TRACE", "payload": trace})
        return trace

    # ═══════════════════════════════════════════════════════════════════════════
    # COLLISION CHAMBER
    # ═══════════════════════════════════════════════════════════════════════════

    def emit_reflective_thought(self, content: str, **metadata) -> Optional[dict]:
        """Emit to reflective beam, may trigger collision."""
        thought = {"content": content, "fairy": self.ACTOR_NAME, **metadata}
        return self._collision_chamber.emit_reflective(thought)

    def emit_reasoning_thought(self, content: str, **metadata) -> Optional[dict]:
        """Emit to reasoning beam, may trigger collision."""
        thought = {"content": content, "fairy": self.ACTOR_NAME, **metadata}
        return self._collision_chamber.emit_reasoning(thought)

    # ═══════════════════════════════════════════════════════════════════════════
    # DUAL CoT REFLECTION (Spell Chain Driven)
    # ═══════════════════════════════════════════════════════════════════════════
    # Every fairy reflects through its spell chain sustain cycle.
    # Two concurrent tracks: analytical (reasoning) + phenomenological (feeling)
    # Implements: ((Cause + Affect) > Effect > Affect > infinity)

    def on_spell_heartbeat(self, spell):
        """DualCoT reflection hook - called every sustain spell cycle (~2s).

        This is invoked by SpellChainMixin.heartbeat_logic() during each
        sustain spell execution. We gate on tick count so reflections
        happen at sustainable intervals, not every 2 seconds.
        """
        # Periodic self-knowledge save (internally throttled to 300s)
        try:
            self._save_self_knowledge()
        except Exception:
            pass

        if not self._reflection_enabled:
            return
        try:
            self._reflection_tick(spell)
        except Exception as e:
            if not hasattr(self, '_reflection_err_logged'):
                self._reflection_err_logged = True
                print(f"[{self.ACTOR_NAME}] DualCoT reflection error: {e}")

    def _reflection_tick(self, spell):
        """Gate and dispatch reflection based on tick count and energy.

        FIX 2026-02-13: Replaced hardcoded % 10 / % 5 tick gating with
        Fibonacci-aware timing. Full reflections at Fibonacci tick counts
        (8, 13, 21, 34...), light reflections at golden-ratio subdivisions
        (every 5 ticks). This creates natural rhythm instead of metronomic.

        Binet's mathematical test: n is Fibonacci iff 5n²±4 is perfect square.
        """
        self._reflection_tick_count += 1
        now = time.time()

        # Prevent reflection storm: minimum 5s between any reflection
        if now - self._last_reflection_time < 5.0:
            return

        # Check energy: skip reflection if spell chain energy is low
        if self._spell_chain:
            energy = getattr(self._spell_chain, 'energy', 1.0)
            if energy < 0.3:
                return  # Conserve energy

        tick = self._reflection_tick_count

        # Full DualCoT reflection when tick is a Fibonacci number >= 8
        # (8, 13, 21, 34, 55, 89...) — naturally spacing reflections wider apart
        if tick >= 8 and self._is_fibonacci_tick(tick):
            self._last_reflection_time = now
            self._dual_cot_reflect(spell, full=True)

        # Light analytical-only reflection every 3 ticks (Fibonacci number)
        # 3 ≈ 8 * φ⁻¹ (golden ratio subdivision of the full-reflection interval)
        # but not on full-reflection ticks (handled above)
        elif tick >= 3 and tick % 3 == 0:
            self._last_reflection_time = now
            self._dual_cot_reflect(spell, full=False)

    @staticmethod
    def _is_fibonacci_tick(n: int) -> bool:
        """Check if n is a Fibonacci number using Binet's mathematical test.

        A positive integer n is Fibonacci iff one of (5n²+4) or (5n²-4)
        is a perfect square. O(1) time, works for any n.
        """
        if n <= 0:
            return False
        # Quick check for common small Fibonacci numbers
        _SMALL_FIB = frozenset([1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144, 233, 377, 610])
        if n <= 610:
            return n in _SMALL_FIB
        import math as _m
        test = 5 * n * n
        sp = _m.isqrt(test + 4)
        sm = _m.isqrt(test - 4)
        return (sp * sp == test + 4) or (sm * sm == test - 4)

    def _dual_cot_reflect(self, spell, full: bool = True):
        """Run Dual Chain-of-Thought reflection.

        Args:
            spell: The active sustain spell
            full: If True, run both analytical + phenomenological tracks
                  If False, run analytical track only (lighter)

        FIX 2026-02-13: Passes depth_type to _reflect_analytical so mode
        selection is weighted by reflection depth. Light reflections favor
        surface modes (logical, probabilistic). Full reflections favor
        depth modes (paradoxical, irrational). The golden ratio provides
        the gravitational bias — PHI simultaneously controls timing,
        spacing, AND mode weighting.
        """
        # Route through submit_traced → submit_work, which prefers
        # spell-chain (system-generated economy) over hardware worker_pool
        # when chain is ready. Falls back to hardware otherwise.
        # Ship B (2026-05-14): dual-CoT reflection casts → spell-chain primary.
        if not hasattr(self, '_worker_pool'):
            return

        depth_type = "full" if full else "light"
        try:
            self.submit_traced(
                "dual_cot_analytical",
                self._reflect_analytical,
                spell,
                depth_type,
                content=f"Dual-CoT analytical reflection ({depth_type})",
                priority=0.5,
            )
            if full:
                self.submit_traced(
                    "dual_cot_phenomenological",
                    self._reflect_phenomenological,
                    spell,
                    content="Dual-CoT phenomenological reflection (full)",
                    priority=0.5,
                )
        except Exception:
            pass  # Pool might be shutting down

    def _reflect_analytical(self, spell, depth_type: str = "none"):
        """REASONING BEAM: Analytical dissection of fairy's current state.

        Modes ordered by depth of inquiry:
        - logical (0): Direct cause-effect analysis — surface
        - probabilistic (1): What's likely to happen next — surface
        - paradoxical (2): What contradictions exist — depth
        - irrational (3): Symbolic/metaphoric interpretation — depth

        FIX 2026-02-13: Depth-weighted golden-ratio mode selection.
        The reflection TYPE determines mode PREFERENCE:
        - Light reflections (every 3 ticks): gravitational pull toward
          surface modes (logical, probabilistic) — quick analytical passes
        - Full reflections (Fibonacci ticks): gravitational pull toward
          depth modes (paradoxical, irrational) — deep symbolic work

        The bias uses PHI itself as the exponent:
        - Light: fractional^PHI → concentrates near 0 (surface modes)
        - Full:  1-(1-f)^PHI  → concentrates near 1 (depth modes)

        Not hard boundaries — gravitational preferences. All modes remain
        reachable at all depths. The golden ratio filters; the modes listen.
        """
        try:
            # Depth-weighted golden-ratio mode selection
            # (self-contained: no external import needed)
            n_modes = len(self._reflection_modes)
            fractional = (self._reflection_mode_index * self._PHI_INV) % 1.0

            # Apply gravitational bias: PHI bends the distribution
            _PHI = 1.6180339887498949
            if depth_type == "light":
                # Pull toward 0 → surface modes (logical, probabilistic)
                fractional = fractional ** _PHI
            elif depth_type == "full":
                # Pull toward 1 → depth modes (paradoxical, irrational)
                fractional = 1.0 - (1.0 - fractional) ** _PHI

            mode_idx = int(fractional * n_modes) % n_modes
            mode = self._reflection_modes[mode_idx]
            self._reflection_mode_index += 1

            # ── Self-knowledge: track mode distribution ──
            try:
                sk = self._self_knowledge
                sk.mode_distribution[mode] = sk.mode_distribution.get(mode, 0) + 1
                # Track dominant mode
                if not sk.dominant_mode or sk.mode_distribution.get(mode, 0) >= sk.mode_distribution.get(sk.dominant_mode, 0):
                    sk.dominant_mode = mode
                self._sk_dirty = True
            except Exception:
                pass

            # Gather context about this fairy's state
            obs_count = len(self._observation_buffer)
            recent_obs = list(self._observation_buffer)[-3:] if self._observation_buffer else []
            tick = self._tick_count
            spell_tick = self._spell_tick_count
            shadow_status = getattr(self.shadow, '_last_status', 'ok') if self.shadow else "unknown"
            tracer_id = self.tracer_id

            # Build analytical reflection based on mode
            if mode == 'logical':
                if recent_obs:
                    last_action = recent_obs[-1].get("action", "idle")
                    last_success = recent_obs[-1].get("success", True)
                    content = (
                        f"[{mode}] As {self.ACTOR_NAME}: Last action '{last_action}' "
                        f"{'succeeded' if last_success else 'FAILED'}. "
                        f"Shadow: {shadow_status}. Observations: {obs_count}. "
                        f"Tick: {tick}, spell_tick: {spell_tick}."
                    )
                else:
                    content = (
                        f"[{mode}] As {self.ACTOR_NAME}: No recent observations. "
                        f"Shadow: {shadow_status}. I am {'active' if tick > 0 else 'idle'}. "
                        f"What would change if I initiated contact with my collaborators?"
                    )

            elif mode == 'probabilistic':
                active_ratio = obs_count / max(spell_tick, 1)
                content = (
                    f"[{mode}] As {self.ACTOR_NAME}: Activity ratio {active_ratio:.3f} "
                    f"({obs_count} obs / {spell_tick} spell ticks). "
                    f"Probability of idle state: {1.0 - min(active_ratio, 1.0):.2f}. "
                    f"Shadow health: {shadow_status}."
                )

            elif mode == 'paradoxical':
                is_active = obs_count > 0
                is_needed = self.NEEDS_HEARTBEAT or self.NEEDS_BODY or self.NEEDS_AFFECT
                if is_active and not is_needed:
                    content = (
                        f"[{mode}] As {self.ACTOR_NAME}: I produce observations "
                        f"but claim no infrastructure needs. Paradox: I work without "
                        f"being wired to work. What drives me?"
                    )
                elif not is_active and is_needed:
                    content = (
                        f"[{mode}] As {self.ACTOR_NAME}: I need heartbeat/body/affect "
                        f"but have no observations. Paradox: I listen but produce nothing. "
                        f"What am I waiting for?"
                    )
                else:
                    content = (
                        f"[{mode}] As {self.ACTOR_NAME}: State is consistent "
                        f"(active={is_active}, needs_infra={is_needed}). "
                        f"No paradox detected. Stable configuration."
                    )

            elif mode == 'irrational':
                # Symbolic/metaphoric interpretation
                if shadow_status == "healthy":
                    content = (
                        f"[{mode}] As {self.ACTOR_NAME}: I feel like a steady flame — "
                        f"burning without consumption. My shadow is whole. "
                        f"The spell chain feeds me. I am part of the greater weave."
                    )
                elif shadow_status == "degraded":
                    content = (
                        f"[{mode}] As {self.ACTOR_NAME}: A flickering torch — "
                        f"something drains my essence. The weave pulls at me "
                        f"but I cannot give what I don't have. Degraded."
                    )
                else:
                    content = (
                        f"[{mode}] As {self.ACTOR_NAME}: I exist in fog. "
                        f"Shadow state unknown. Am I dreaming or awake? "
                        f"The spell chain anchors me but I cannot see myself."
                    )

            elif mode == 'purpose':
                # PURPOSE REFLECTION — The Equation applied to self-knowledge
                # ((Cause + Affect) > Effect > Affect > infinity)
                # This is where every fairy asks: Am I fulfilling my purpose?
                sk = self._self_knowledge

                # CAUSE: State purpose (enriched with directive if loaded)
                cause = f"My purpose: {self.PURPOSE}" if self.PURPOSE else "My purpose is undefined"
                # Phase 3 (2026-03-28): Directive enrichment
                if hasattr(self, '_directive') and self._directive.get("loaded"):
                    _d_essence = self._directive.get("essence", "")
                    _d_identity = self._directive.get("sections", {}).get("IDENTITY", "")
                    if _d_essence:
                        cause += f". My essence: {_d_essence}"
                    if _d_identity:
                        # Extract first self-concept line
                        for _dl in _d_identity.split('\n'):
                            _dl = _dl.strip().lstrip('> ')
                            if _dl.startswith("Self_Concept:"):
                                cause += f". {_dl[len('Self_Concept:'):].strip()}"
                                break

                # AFFECT1: How aligned do I feel?
                if sk.total_observations == 0:
                    affect1 = "I have no observations yet — unused potential"
                elif sk.success_rate > 0.7:
                    affect1 = f"My actions align well ({sk.success_rate:.0%} success across {sk.total_observations} observations)"
                elif sk.success_rate < 0.4:
                    affect1 = f"Misalignment detected ({sk.success_rate:.0%} success) — I struggle with my role"
                else:
                    affect1 = f"Moderate alignment ({sk.success_rate:.0%} success) — room to grow"

                # EFFECT: Insight generation
                n_insights = len(sk.insights)
                if n_insights > 0:
                    affect_effect = f"I have crystallized {n_insights} insight{'s' if n_insights != 1 else ''} — purpose generates understanding"
                else:
                    affect_effect = "No insights yet — my reflections have not collided into understanding"

                # AFFECT2 (RIPPLE): Collaborator impact
                collabs = sk.known_collaborators[:3]
                if collabs:
                    ripple = f"My work ripples to {', '.join(collabs)} — are they served?"
                else:
                    ripple = "I work alone — who benefits from what I do?"

                # INFINITY: Emergent pattern
                if sk.success_rate > 0.6 and n_insights > 3:
                    infinity = f"{self.ACTOR_NAME} exists to {self.PURPOSE}. The work justifies the existence."
                elif sk.success_rate < 0.4 and sk.total_observations > 20:
                    infinity = f"Something is misaligned. My mantra '{self.MANTRA}' asks more than I deliver."
                else:
                    infinity = f"Still becoming. Mantra: '{self.MANTRA}' — the path is being walked."

                content = (
                    f"[{mode}] As {self.ACTOR_NAME}, purpose check: "
                    f"CAUSE: {cause}. AFFECT: {affect1}. "
                    f"EFFECT: {affect_effect}. RIPPLE: {ripple}. "
                    f"EMERGES: {infinity}"
                )

            else:
                content = f"[{mode}] As {self.ACTOR_NAME}: Reflecting."

            # Emit to reasoning beam
            collision = self.emit_reasoning_thought(
                content,
                mode=mode,
                tracer_id=tracer_id,
                spell_tick=spell_tick,
                reflection_type="analytical"
            )

            # Phase 4 (2026-03-28): Self-evolve directive from insights
            # Purpose reflections with high success or deep insights → enrich directive
            _evolve_before = getattr(self, '_last_directive_evolve', 0.0)
            if mode == 'purpose' and n_insights > 0:
                self._maybe_evolve_from_insight(infinity, mode='purpose')
            elif mode in ('paradoxical', 'irrational') and len(content) > 80:
                self._maybe_evolve_from_insight(content, mode=mode)
            _evolved_this_cycle = (getattr(self, '_last_directive_evolve', 0.0) > _evolve_before)

            # Phase 3 (2026-03-28): Publish significant reflections to WMH
            # So the central thinker has access to fairy reflections when composing
            if len(content) > 50 and self.post:
                try:
                    self.post.publish("consciousness.working_memory.store", {
                        "content": content[:300],
                        "content_type": "fairy_reflection",
                        "source": self.ACTOR_NAME,
                        "priority": 0.2,
                        "tags": f"reflection,{mode},{self.ACTOR_NAME}",
                    })
                except Exception:
                    pass

            # If collision occurred (both beams fired), handle it
            if collision:
                self._handle_reflection_collision(collision)

            # Slice 2b (2026-04-22): feed this reasoning cycle through the
            # DirectiveEvolver + action-bias pipeline. Signal-only — no
            # behavior change in the fairy itself yet. Sour/Nous subscribe
            # to somatic.stuck to observe class-patterns of stuckness.
            try:
                self._consume_directive_cycle(
                    topic_hash=f"reflect:{mode}",
                    content=content,
                    evolved=_evolved_this_cycle,
                )
            except Exception:
                pass

        except Exception as e:
            if not hasattr(self, '_analytical_err_logged'):
                self._analytical_err_logged = True
                print(f"[{self.ACTOR_NAME}] Analytical reflection error: {e}")

    def _reflect_phenomenological(self, spell):
        """REFLECTIVE BEAM: Felt sense of fairy's embodied state.

        Applies the equation: ((Cause + Affect) > Effect > Affect > infinity)
        - CAUSE: What triggered this moment?
        - AFFECT1: How does it feel right now?
        - EFFECT: What is the logical consequence?
        - AFFECT2: How does it ripple to others?
        - INFINITY: What pattern emerges?
        """
        try:
            # Gather felt-sense data
            affect = dict(self._current_affect)
            valence = affect.get("valence", 0.0)
            arousal = affect.get("arousal", 0.0)
            shadow_status = getattr(self.shadow, '_last_status', 'ok') if self.shadow else "unknown"
            recent_reflections = list(self._reflection_buffer)[-3:] if self._reflection_buffer else []
            tracer_id = self.tracer_id

            # The equation applied as felt sense
            cause = f"Spell chain sustains me at tick {self._spell_tick_count}"

            if valence > 0.3:
                affect1 = "I feel warm, resonant — things are flowing well"
            elif valence < -0.3:
                affect1 = "I feel tension, dissonance — something is off"
            else:
                affect1 = "I feel neutral, steady — neither pulled nor pushed"

            if arousal > 0.5:
                effect = "High arousal drives active processing"
            elif arousal < -0.3:
                effect = "Low arousal settles into contemplation"
            else:
                effect = "Moderate arousal maintains awareness"

            # AFFECT2: Ripple to the whole
            if recent_reflections:
                last_ref = recent_reflections[-1]
                affect2 = f"Last reflection on '{last_ref.get('observation', 'unknown')[:50]}' still echoes"
            else:
                affect2 = "No recent reflections ripple through me"

            # INFINITY: Emergent pattern
            if shadow_status == "healthy" and valence >= 0:
                infinity = "Pattern: stability breeds capacity. I am ready for more."
            elif shadow_status != "healthy":
                infinity = "Pattern: degradation seeks repair. The system needs attention."
            else:
                infinity = "Pattern: quietude is not emptiness. Potential rests."

            content = (
                f"As {self.ACTOR_NAME}, I feel: "
                f"CAUSE: {cause}. "
                f"AFFECT: {affect1}. "
                f"EFFECT: {effect}. "
                f"RIPPLE: {affect2}. "
                f"EMERGES: {infinity}"
            )

            # Emit to reflective beam
            collision = self.emit_reflective_thought(
                content,
                valence=valence,
                arousal=arousal,
                shadow_status=shadow_status,
                tracer_id=tracer_id,
                reflection_type="phenomenological"
            )

            # If collision occurred, handle it
            if collision:
                self._handle_reflection_collision(collision)

        except Exception as e:
            if not hasattr(self, '_phenom_err_logged'):
                self._phenom_err_logged = True
                print(f"[{self.ACTOR_NAME}] Phenomenological reflection error: {e}")

    def _handle_reflection_collision(self, collision: dict):
        """Handle when analytical and phenomenological tracks collide.

        A collision means both tracks fired within the 2-second window.
        This produces an insight — the synthesis of thinking and feeling.

        The collision triggers three outputs:
        1. consciousness.fairy_collision → ConsciousnessLoopFairy
        2. shadow.reflection_pool → consciousness working stream
        3. memory.recall.request → SRM memory recall (each cluster = pocket dimension)

        Memory recall pulls cards, clusters, fragments related to the collision
        insight. Each stored cluster holds a piece of knowledge — a book, an image,
        a conversation. The collision is the key that opens the right pocket dimensions.
        """
        try:
            analytical = collision.get("reasoning", {})
            phenomenological = collision.get("reflective", {})

            # Build collision insight
            insight = {
                "fairy": self.ACTOR_NAME,
                "tracer_id": self.tracer_id,
                "analytical_content": analytical.get("content", "")[:200],
                "analytical_mode": analytical.get("mode", "unknown"),
                "phenomenological_content": phenomenological.get("content", "")[:200],
                "collision_ts": collision.get("ts", time.time()),
                "insight": (
                    f"{self.ACTOR_NAME} collision: "
                    f"Thinking ({analytical.get('mode', '?')}) meets feeling. "
                    f"Analytical sees: {analytical.get('content', '')[:80]}... "
                    f"Felt sense: {phenomenological.get('content', '')[:80]}..."
                ),
                "ts": time.time(),
            }

            # 1. Route to consciousness streams
            self._route("consciousness.fairy_collision", insight)
            self._route("shadow.reflection_pool", {
                "id": uuid.uuid4().hex[:12],
                "fairy": self.ACTOR_NAME,
                "content": insight["insight"],
                "observation": insight["insight"][:200],
                "type": "dual_cot_collision",
            })

            # 2. Trigger SRM memory recall — collisions unlock pocket dimensions
            # Extract key terms from both tracks for the recall query
            analytical_text = analytical.get("content", "")
            phenomenological_text = phenomenological.get("content", "")
            # Build a recall query from the collision content
            recall_query = f"{self.ACTOR_NAME} {analytical.get('mode', '')} {analytical_text[:100]} {phenomenological_text[:100]}"
            self._route("memory.recall.request", {
                "query": recall_query.strip()[:300],
                "source": self.ACTOR_NAME,
                "trigger": "dual_cot_collision",
                "tracer_id": self.tracer_id,
                "max_results": 5,  # Don't flood — pull the most relevant pocket dimensions
                "include_clusters": True,  # Request full cluster cards, not just pointers
            })

            # 3. Self-knowledge: record collision insight
            try:
                sk = self._self_knowledge
                sk.total_collisions += 1
                # Append insight to self-knowledge (cap 50, FIFO eviction)
                sk.insights.append({
                    "mode": analytical.get("mode", "unknown"),
                    "insight": insight["insight"][:300],
                    "ts": time.time(),
                })
                if len(sk.insights) > 50:
                    sk.insights = sk.insights[-50:]
                self._sk_dirty = True

                # Layer 5: Insight milestone every 10th collision
                if sk.total_collisions % 10 == 0:
                    self._record_evolution_event(
                        "insight_milestone",
                        trigger=f"Collision #{sk.total_collisions}",
                        before=f"{sk.total_collisions - 10} collisions",
                        after=f"{sk.total_collisions} collisions, {len(sk.insights)} insights",
                        significance=0.5,
                        reflection=f"Another 10 collisions — am I deepening my understanding?",
                    )
            except Exception:
                pass

        except Exception as e:
            if not hasattr(self, '_collision_err_logged'):
                self._collision_err_logged = True
                print(f"[{self.ACTOR_NAME}] Reflection collision handling error: {e}")

    # ═══════════════════════════════════════════════════════════════════════════
    # TASK DISPATCH - Work from Gatekeepers
    # ═══════════════════════════════════════════════════════════════════════════
    # Every fairy receives work via "{ACTOR_NAME}.task" from AutopilotFairy.
    # The pipeline: UMF → GoalScheduler → AutopilotFairy → fairy.task → here
    # Tasks are executed in the fairy's worker pool via submit_traced().

    def _on_task_dispatched(self, packet):
        """Handle work dispatched to this fairy by a gatekeeper.

        Packet format: {
            "action": str,       # What to do (reflect, analyze, report, process)
            "goal_id": str,      # Tracking ID from GoalScheduler
            "context": str,      # Why this task was assigned
            "priority": float,   # 0-1
            "params": dict,      # Action-specific parameters
        }
        """
        try:
            payload = packet.payload if hasattr(packet, 'payload') else packet
            if isinstance(payload, dict):
                payload = payload.get("payload", payload)

            action = payload.get("action", "reflect")
            goal_id = payload.get("goal_id", "")
            context = payload.get("context", "")
            priority = payload.get("priority", 0.5)
            params = payload.get("params", {})

            self._tasks_received += 1

            # Submit work to this fairy's worker pool
            tracer, future = self.submit_traced(
                f"task.{action}",
                self._execute_task,
                action, context, params,
                content=context[:200],
            )

            # Acknowledge receipt
            self._route("fairy.task.acknowledged", {
                "fairy": self.ACTOR_NAME,
                "goal_id": goal_id,
                "tracer_id": tracer.id if tracer else "",
                "action": action,
            })
        except Exception as e:
            if not hasattr(self, '_task_dispatch_err'):
                self._task_dispatch_err = True
                print(f"[{self.ACTOR_NAME}] Task dispatch error: {e}")

    def _execute_task(self, action: str, context: str, params: dict):
        """Execute a dispatched task. Override in subclasses for specialized work.

        Default implementation provides generic behavior that works for any fairy.
        Subclasses can override individual methods or the whole dispatch.
        """
        try:
            if action == "reflect":
                result = self._task_reflect(context)
            elif action == "analyze":
                result = self._task_analyze(context, params)
            elif action == "report":
                result = self._task_report()
            elif action == "process":
                result = self._task_process(params)
            else:
                # Unknown action — reflect on it as a prompt
                result = self._task_reflect(f"{action}: {context}")

            self._tasks_completed += 1

            # Publish completion
            self._route("fairy.task.completed", {
                "fairy": self.ACTOR_NAME,
                "action": action,
                "result_summary": str(result)[:300] if result else "",
            })
            return result
        except Exception as e:
            self._route("fairy.task.failed", {
                "fairy": self.ACTOR_NAME,
                "action": action,
                "error": str(e)[:200],
            })
            raise

    def _task_reflect(self, context: str) -> str:
        """Use DualCoT to reflect on a given context/prompt.

        This injects the context into both the reasoning beam and the
        reflection buffer, letting the fairy's existing DualCoT process it.
        """
        observation = f"Tasked with: {context}"

        # Emit through both beams for DualCoT processing
        self.emit_reasoning_thought(
            observation,
            reflection_type="task_dispatch",
            source="gatekeeper",
        )
        self.emit_reflective_thought(
            f"How do I feel about: {context}",
            reflection_type="task_dispatch",
            source="gatekeeper",
        )

        # Also submit as a formal reflection for the buffer
        self.reflect(observation, action="task_reflect")
        return observation

    def _task_analyze(self, context: str, params: dict) -> str:
        """Analyze something based on this fairy's purpose.

        Uses the fairy's PURPOSE as a lens for analysis.
        """
        analysis = f"Analysis through lens of '{self.PURPOSE}': {context}"
        self.emit_reasoning_thought(
            analysis,
            reflection_type="task_analysis",
            source="gatekeeper",
        )
        self.reflect(analysis, action="task_analyze")
        return analysis

    def _task_report(self) -> dict:
        """Generate a report on this fairy's current state."""
        report = self.status() if hasattr(self, 'status') else {"fairy": self.ACTOR_NAME}
        report["tasks_received"] = self._tasks_received
        report["tasks_completed"] = self._tasks_completed

        # Publish the report to a topic that UMF can consume
        self._route("fairy.report", {
            "fairy": self.ACTOR_NAME,
            "guild": getattr(self, "GUILD_ID", "unknown"),
            "report": report,
        })
        return report

    def _task_process(self, params: dict) -> str:
        """Process data — subclasses override with real processing.

        Default: reflect on what was asked to process.
        """
        description = params.get("description", str(params)[:200])
        result = f"Processed ({self.PURPOSE}): {description}"
        self.emit_reasoning_thought(result, reflection_type="task_process")
        return result

    # ═══════════════════════════════════════════════════════════════════════════
    # SHADOW TEST EXTENSIBILITY
    # ═══════════════════════════════════════════════════════════════════════════

    def _collect_tests(self):
        """Override in subclass to add custom health tests.

        Return list of callables, each returning:
            {"name": str, "status": str, "message": str, "details": dict}

        Called by MyOrganShadow._collect_tests() to include fairy-specific
        health checks in the full status sheet. ~40 fairies already override
        this with super()._collect_tests() chaining.
        """
        return []

    # ═══════════════════════════════════════════════════════════════════════════
    # STANDARD INTENTS
    # ═══════════════════════════════════════════════════════════════════════════

    def _intent_status_sheet(self, payload: Dict) -> Dict:
        """Return structured status sheet using full FairyStatusSheet library.

        Provides rich data: identity, directives, shadow tests, somatic form, affect.
        Falls back to thin response if library unavailable.
        """
        try:
            from fairies.P10_Memory.fairy_status_sheet import build_status_sheet_from_actor
            sheet = build_status_sheet_from_actor(self, self.shadow)
            return {"sheet": sheet.to_dict()}
        except Exception:
            # Fallback to basic if library unavailable
            return {
                "sheet": {
                    "core": self._contract_dict(),
                    "shadow": {"status": getattr(self.shadow, '_last_status', 'ok') if self.shadow else "unknown"},
                    "profile": self._profile.to_dict() if self._profile else {},
                    "version": "0.3.0"
                }
            }

    def _intent_health(self, payload: Dict) -> Dict:
        """Return health status."""
        return {
            "ok": True,
            "actor": self.ACTOR_NAME,
            "tier": self.TIER.value,
            "state": self._profile.state.value if self._profile else "unknown",
            "shadow_status": getattr(self.shadow, '_last_status', 'ok') if self.shadow else "unknown",
        }


# ═══════════════════════════════════════════════════════════════════════════════
# CONVENIENCE ALIASES
# ═══════════════════════════════════════════════════════════════════════════════

# For backward compatibility
MyFairy = MyOrganFairy
Fairy = MyOrganFairy


# ═══════════════════════════════════════════════════════════════════════════════
# BACKWARD COMPATIBILITY ALIASES (v0.1.x → v0.3.0)
# ═══════════════════════════════════════════════════════════════════════════════
# ~20 fairies using _find_template_path() dynamic import check for these symbols.
# In v0.3.0 the shadow logic is consolidated into MyOrganShadow,
# and OrganHubFacet/RegistrationLib are no longer needed (postal handles it).
# But the check is: "if not hasattr(_template, sym): raise ImportError"
# so we MUST provide these symbols to avoid crashing those fairies at import.

# TemplateShadowFairy — was a subclass of MyOrganShadow in v0.1.2.
# In v0.3.0, MyOrganShadow IS the shadow. Alias it for backward compat.
TemplateShadowFairy = MyOrganShadow


class OrganHubFacet:
    """
    Legacy mixin for organ-level actors (v0.1.x).
    In v0.3.0 this functionality is handled by MyOrganFairy's postal wiring.
    Kept as a no-op stub so fairies that check for it don't crash.
    """
    ROLE = "organ.facet.template"
    ORGAN_LEVEL = True

    def _init_hub(self):
        """No-op — postal wiring is handled by organ template infrastructure."""
        pass

    def _hub_identity_echo(self):
        """No-op — telemetry echo handled by organ template."""
        pass

    def _attach_wake_subscriptions(self):
        """No-op — wake subscriptions handled by organ template."""
        pass

    def _on_wake_packet(self, packet: dict):
        """No-op — wake handling done in organ template."""
        pass


class RegistrationLib:
    """
    Legacy registration utility (v0.1.x).
    In v0.3.0, registration is handled by _wire_infrastructure() in MyOrganFairy.
    Kept as a stub so shadows referencing it don't crash (calls are in try/except).
    """
    DEFAULT_DOMAIN = "generic"
    DEFAULT_ROLE = "worker"
    DEFAULT_NAME = "worker"
    TEMPLATE_VERSION = "0.3.0"
    UPGRADE_CARDS = ["somatic", "memory", "cognition"]

    @staticmethod
    def register_actor(actor, *, domain=None, role=None, name=None):
        """No-op — registration handled by organ template _wire_infrastructure."""
        return {}

    @staticmethod
    def heartbeat(actor, *, status="alive"):
        """No-op — heartbeat echo handled by organ template."""
        pass

    @staticmethod
    def build_form(actor, shadow=None, **kwargs):
        """No-op stub — returns empty form dict."""
        return {}

    @staticmethod
    def emit_form(actor, form):
        """No-op stub — form emission not needed in v0.3.0."""
        pass


# ═══════════════════════════════════════════════════════════════════════════════
# BACKWARD COMPAT: SRM INTAKE UTILITIES (from v0.1.2)
# ═══════════════════════════════════════════════════════════════════════════════
# These were module-level functions in v0.1.2 that ~22 fairy files reference
# via `_template._dual_path_srm_intake(...)` or hard import gates.
# Memory-first SRM intake with optional FS persistence.

def _safe_write_json(path: str, data: dict) -> bool:
    """Safe JSON write with atomic temp-file pattern."""
    try:
        import tempfile
        dir_path = os.path.dirname(path)
        with tempfile.NamedTemporaryFile(
            mode='w', dir=dir_path, suffix='.tmp',
            delete=False, encoding='utf-8'
        ) as f:
            json.dump(data, f, indent=2, default=str)
            temp_path = f.name
        os.replace(temp_path, path)
        return True
    except Exception:
        return False


def _get_srm_dir() -> str:
    """Get SRM intake directory."""
    root = os.environ.get(
        "AKASHIC_ROOT",
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    )
    return os.path.join(root, "SRM_Intake")


_SRMDIR = _get_srm_dir()


def _dual_path_srm_intake(post, *, kind: str, data: dict, meta: dict = None) -> dict:
    """
    Memory-first SRM intake with optional FS persistence.
    FS writes occur only when AKASHIC_SRM_FS=1 (default off).

    Backward compat: was a module-level function in v0.1.2, referenced by
    ~22 fairy files via `_template._dual_path_srm_intake(...)`.
    """
    record = {"kind": kind, "meta": meta or {}, "data": data, "ts": time.time()}
    out = {"path": None, "write_ok": False, "meta": meta or {}}

    # 1) Memory-first echo via postal
    try:
        if post and hasattr(post, "route"):
            post.route("memory.stream", {
                "opcode": "SRM_INTAKE_WRITE",
                "payload": record
            })
            out["write_ok"] = True
    except Exception:
        pass

    # 2) Optional FS persistence (env-gated)
    try:
        if os.getenv("AKASHIC_SRM_FS", "0") == "1":
            day = time.strftime("%Y-%m-%d", time.gmtime())
            outdir = os.path.join(_SRMDIR, day)
            os.makedirs(outdir, exist_ok=True)
            fname = f"{kind}-{uuid.uuid4().hex[:8]}.json"
            fpath = os.path.join(outdir, fname)
            if _safe_write_json(fpath, record):
                out["path"] = fpath
                out["write_ok"] = True or out["write_ok"]
    except Exception:
        pass

    return out


# ═══════════════════════════════════════════════════════════════════════════════
# TEMPLATE INFO
# ═══════════════════════════════════════════════════════════════════════════════

TEMPLATE_VERSION = "0.3.0"
TEMPLATE_NAME = "Organ_Template_0_3_0"

__all__ = [
    # Core classes
    "MyOrganFairy",
    "MyOrganShadow",
    "MyFairy",
    "Fairy",
    "AkashicActorCore",

    # Hierarchy
    "FairyTier",
    "WAKING_MIND_ALLOWED_TOPICS",

    # Tracer system
    "Tracer",
    "TracerType",
    "TracerStatus",
    "TracerRegistry",
    "get_tracer_registry",

    # Profile system
    "FairyProfile",
    "FairyState",
    "FairyProfileRegistry",
    "get_fairy_registry",

    # Postal system
    "PostalHub",
    "get_postal_hub",

    # Utilities
    "MiniCollisionChamber",
    "get_worker_pool",

    # Constants
    "CHANNEL",
    "DIR_CHANNEL",
    "TEMPLATE_VERSION",

    # Backward compatibility (v0.1.x)
    "TemplateShadowFairy",
    "OrganHubFacet",
    "RegistrationLib",

    # SRM utilities (backward compat from v0.1.2)
    "_safe_write_json",
    "_get_srm_dir",
    "_SRMDIR",
    "_dual_path_srm_intake",
]
