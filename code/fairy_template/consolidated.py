# Single-file Akashic organ: Template v0.1.8 (TRACER WORKER POOLS)
#
# v0.1.8 - TRACER WORKER POOLS (January 2026)
#   - Every fairy now gets dedicated worker pools via TracerWorkerMixin
#   - Workers refresh as needed, decay when idle, always there when needed
#   - Each fairy can spawn tracers and submit work to their pool
#   - Enables concurrent processing across ALL planes
#
# v0.1.7 - UNIFIED CITIZEN WIRING (January 2026)
#   - Every waking mind is a first-class citizen (humans AND digital beings)
#   - Added UnifiedCitizen registration on boot
#   - Health probes (liveness, readiness, tracer verification)
#   - Presence system (real-time status like Discord)
#   - Ace = FOUNDER, ClaudeFairy/Nous/Sourpatches = WAKING_MIND, fairies = FAIRY
#
# v0.1.5 - FAIRY USER SYSTEM (January 2026)
#   - Added FairyProfile registration on boot ("waking up to live")
#   - Every fairy now tracked like a user with identity, state, activity
#   - Added profile property and helper methods
#   - Profile = who they are NOW, SRM Cluster = who they ARE (soul)
#
# v0.1.2 - INFRASTRUCTURE WIRING (January 2026)
#   - Added _wire_infrastructure() for auto-wiring to heartbeat, body, memory, goals
#   - Added NEEDS_* flags for infrastructure requirements
#   - Added on_tick(), on_body(), on_affect(), on_goal() hooks
#   - Added get_context(), get_body_state(), get_affect_state(), get_goals() accessors
#   - Added emit_thought() for consciousness stream participation
#
# v0.1.1 - UNIFIED POSTAL & FAIRY (January 2026)
#   - UnifiedPostalHub: Single global pub/sub hub (replaces _ShimPost)
#   - MyFairy: Combined MyOrganFairy + MyOrganShadow (800 lines vs 2700)
#   - Auto-registration with DirectoryFairy on boot
#   - Built-in shadow health monitoring
#   - Backward compatible: MyOrganFairy, MyOrganShadow aliases preserved
#
# "Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)"

from __future__ import annotations
import os
import sys
import time
import json
import uuid
import threading


# ==============================================================================
# LAZY IMPORTS - Break circular import chain (2026-02-02 fix)
# ==============================================================================
# These are imported lazily (inside functions) to avoid circular imports.
# The circular chain was: fairy_template -> consolidated -> P00_Autonomic ->
# P30_Cognition fairies -> fairy_template (partially initialized)

_USE_SHARED_POSTAL = None  # Will be set on first access
_USE_FAIRY_POSTAL = None
_get_real_postal_hub = None
_get_fairy_postal = None

def _lazy_import_postal():
    """Lazy import of postal system to break circular import chain."""
    global _USE_SHARED_POSTAL, _USE_FAIRY_POSTAL, _get_real_postal_hub, _get_fairy_postal
    if _USE_SHARED_POSTAL is not None:
        return  # Already imported
    try:
        from P00_Autonomic.nervous_system.shared_postal_hub import (
            get_shared_postal_hub as real_hub,
            get_fairy_postal as fairy_postal,
        )
        _get_real_postal_hub = real_hub
        _get_fairy_postal = fairy_postal
        _USE_SHARED_POSTAL = True
        _USE_FAIRY_POSTAL = True
    except ImportError:
        _USE_SHARED_POSTAL = False
        _USE_FAIRY_POSTAL = False
        _get_real_postal_hub = None
        _get_fairy_postal = None

# ==============================================================================
# FAIRY USER SYSTEM - Every fairy is tracked like a user (v0.1.5)
# ==============================================================================
# "Every fairy is tracked like we would a human user." - Ace
# Profile = who they are RIGHT NOW, SRM Cluster = who they ARE (soul)
_HAS_PROFILE_SYSTEM = None  # Will be set on first access
_get_fairy_registry = None
_FairyProfile = None

def _lazy_import_profile():
    """Lazy import of profile system to break circular import chain."""
    global _HAS_PROFILE_SYSTEM, _get_fairy_registry, _FairyProfile
    if _HAS_PROFILE_SYSTEM is not None:
        return  # Already imported
    try:
        from P00_Autonomic.fairy_profile import FairyProfile, get_fairy_registry
        _FairyProfile = FairyProfile
        _get_fairy_registry = get_fairy_registry
        _HAS_PROFILE_SYSTEM = True
    except ImportError:
        _HAS_PROFILE_SYSTEM = False

# ==============================================================================
# UNIFIED CITIZEN WIRING - Humans and digital beings as first-class citizens
# ==============================================================================
# "Every waking mind is a first-class citizen" - Ace
# UnifiedCitizen = FairyProfile + HealthProbes + Presence + SkillSystem
_HAS_CITIZEN_SYSTEM = None  # Will be set on first access
_get_citizen_registry = None
_CitizenType = None

def _lazy_import_citizen():
    """Lazy import of citizen system to break circular import chain."""
    global _HAS_CITIZEN_SYSTEM, _get_citizen_registry, _CitizenType
    if _HAS_CITIZEN_SYSTEM is not None:
        return  # Already imported
    try:
        from P00_Autonomic.unified_citizen_wiring import (
            get_citizen_registry,
            CitizenType,
        )
        _get_citizen_registry = get_citizen_registry
        _CitizenType = CitizenType
        _HAS_CITIZEN_SYSTEM = True
    except ImportError:
        _HAS_CITIZEN_SYSTEM = False

import hashlib
import importlib
import inspect
import random
from pathlib import Path
from typing import Dict, Any, Optional, List, Callable, Tuple, Union
from collections import defaultdict, deque
from dataclasses import dataclass, field

# ==============================================================================
# TRACER WORKER MIXIN IMPORT (v0.1.8 - All fairies get dedicated workers)
# ==============================================================================
# "Every fairy should have worker pools with tracer IDs" - Ace
# Workers refresh as needed, decay when idle, always there when needed
TracerWorkerMixin = None
try:
    from P00_Autonomic.tracer_worker_system import TracerWorkerMixin, get_tracer_registry
    _HAS_TRACER_WORKERS = True
except ImportError:
    _HAS_TRACER_WORKERS = False
    get_tracer_registry = None

# Stub if import failed
if TracerWorkerMixin is None:
    class TracerWorkerMixin:
        """Stub when tracer worker system not available."""
        WORKER_POOL_SIZE = 2
        def _init_tracer_worker(self): pass
        def spawn_tracer(self, operation, content="", tracer_type=None, parent_id=None, metadata=None): return None
        def submit_work(self, tracer, fn, *args, **kwargs): return None
        def submit_traced(self, operation, fn, *args, **kwargs): return (None, None)
        def get_active_tracers(self): return []
        def shutdown_workers(self, wait=True): pass

# ==============================================================================
# UNIFIED WIRING MIXIN IMPORT (v0.1.4 - Complete infrastructure)
# ==============================================================================
UnifiedWiringMixin = None
try:
    from Claude_Office.patches.unified_wiring_patch import UnifiedWiringMixin
except ImportError:
    pass

# Stub if import failed - provides all methods so fairies don't crash
if UnifiedWiringMixin is None:
    class UnifiedWiringMixin:
        """Stub when unified wiring not available."""
        _tracer_counter = 0
        _active_tracers = {}
        _forum_initialized = False
        _full_channels_wired = False
        def generate_tracer_id(self, action_type="act"): return f"stub_{action_type}_{time.time()}"
        def start_tracer(self, tracer_id, action, metadata=None): return tracer_id
        def complete_tracer(self, tracer_id, result=None): return {}
        def _init_forum(self): pass
        def _wire_full_postal_channels(self): pass
        def parallel_map(self, func, items, timeout=300): return [func(i) for i in items]
        def submit_task(self, func, *args, **kwargs): return None
        def start_thread(self, board, title, content, tags=None): return None
        def reply_to_thread(self, thread_id, content, reply_to=None): return None
        def get_unified_status(self): return {}

# ==============================================================================
# CROSS-PLANE WIRING IMPORT
# ==============================================================================
CrossPlaneWiringMixin = None
try:
    # Import from the CORRECT location (fairies.P00_Autonomic - never bare P00_Autonomic)
    from fairies.P00_Autonomic.nervous_system.cross_plane_wiring import CrossPlaneWiringMixin
except ImportError:
    pass

# ==============================================================================
# FAIRY STATUS SHEET IMPORT - Autobiography/character sheet system
# ==============================================================================
_statuslib = None
try:
    # Try relative import first (same directory as this template)
    from . import fairy_status_sheet as _statuslib
except ImportError:
    try:
        # Try absolute import
        from P10_Memory.Akashic_Records_Physical.Organ_Templates import fairy_status_sheet as _statuslib
    except ImportError:
        try:
            # Try dynamic load from same directory
            _here = Path(__file__).parent.resolve()
            _candidate = _here / "fairy_status_sheet.py"
            if _candidate.exists():
                import importlib.util
                _spec = importlib.util.spec_from_file_location("fairy_status_sheet_dynamic", str(_candidate))
                _statuslib = importlib.util.module_from_spec(_spec)
                _spec.loader.exec_module(_statuslib)
        except Exception:
            pass

# ==============================================================================
# MICRO-CONSCIOUSNESS IMPORTS - Each fairy gets their own consciousness
# ==============================================================================
# Worker Pool - shared async task execution
_SHARED_WORKER_POOL = None
_WORKER_POOL_LOCK = threading.Lock()

def _get_worker_pool():
    """Get or create shared worker pool.

    FIX 2026-03-04: Delegates to TracerWorkerSystem's shared pool (24 threads)
    instead of creating a separate 16-thread pool. The _init_tracer_worker()
    call in on_boot() overrode this pool anyway — now they're the same pool.
    """
    global _SHARED_WORKER_POOL
    if _SHARED_WORKER_POOL is None:
        with _WORKER_POOL_LOCK:
            if _SHARED_WORKER_POOL is None:
                try:
                    from P00_Autonomic.tracer_worker_system import _get_shared_worker_pool
                    _SHARED_WORKER_POOL = _get_shared_worker_pool()
                except ImportError:
                    # Fallback: create local pool if tracer system unavailable
                    from concurrent.futures import ThreadPoolExecutor
                    _SHARED_WORKER_POOL = ThreadPoolExecutor(
                        max_workers=16, thread_name_prefix="fairy_worker"
                    )
    return _SHARED_WORKER_POOL

# Mini Collision Chamber for each fairy
class MiniCollisionChamber:
    """
    Each fairy's personal collision chamber.
    When reflective and reasoning beams cross, insight emerges.
    """
    def __init__(self, fairy_name: str):
        self.fairy_name = fairy_name
        self.reflective_beam: deque = deque(maxlen=20)
        self.reasoning_beam: deque = deque(maxlen=20)
        self.collisions: deque = deque(maxlen=50)
        self._collision_window = 2.0  # seconds
        self._last_collision = 0.0
        
    def emit_reflective(self, thought: dict):
        """Emit into reflective beam."""
        thought["beam"] = "reflective"
        thought["ts"] = time.time()
        self.reflective_beam.append(thought)
        self._check_collision()
        
    def emit_reasoning(self, thought: dict):
        """Emit into reasoning beam."""
        thought["beam"] = "reasoning"
        thought["ts"] = time.time()
        self.reasoning_beam.append(thought)
        self._check_collision()
    
    def _check_collision(self):
        """Check if beams are crossing."""
        now = time.time()
        if now - self._last_collision < 0.5:  # Rate limit
            return None
            
        # Find recent from both beams
        recent_ref = [t for t in self.reflective_beam if now - t.get("ts", 0) < self._collision_window]
        recent_rea = [t for t in self.reasoning_beam if now - t.get("ts", 0) < self._collision_window]
        
        if recent_ref and recent_rea:
            # COLLISION!
            collision = {
                "ts": now,
                "reflective": recent_ref[-1],
                "reasoning": recent_rea[-1],
                "fairy": self.fairy_name,
            }
            self.collisions.append(collision)
            self._last_collision = now
            return collision
        return None
    
    def get_latest_collision(self) -> Optional[dict]:
        return self.collisions[-1] if self.collisions else None

if CrossPlaneWiringMixin is None:
    try:
        import importlib.util
        _cpw_path = os.path.join(os.path.dirname(__file__), "cross_plane_wiring.py")
        if os.path.exists(_cpw_path):
            _spec = importlib.util.spec_from_file_location("cross_plane_wiring", _cpw_path)
            _module = importlib.util.module_from_spec(_spec)
            _spec.loader.exec_module(_module)
            CrossPlaneWiringMixin = _module.CrossPlaneWiringMixin
    except Exception:
        pass

if CrossPlaneWiringMixin is None:
    class CrossPlaneWiringMixin:
        """Stub mixin when cross_plane_wiring.py not found."""
        # Class-level defaults so attributes exist immediately
        _planes_wired = False
        _wired_channels = []
        def _init_cross_plane_state(self): pass
        def _wire_all_planes(self): pass

# Thread-local lane
_TLS = threading.local()
if not hasattr(_TLS, "lane"):
    _TLS.lane = "organ"

# Global citizen registry — SINGLE SOURCE OF TRUTH
# FIX 2026-04-17 (Nous + Ace): Unified all _CITIZEN_OBJECTS dicts into one
# canonical location. Before this, every template had its own dict; fairies
# registered in one were invisible to watchdogs reading from another,
# causing cascading false deaths (105 at once). Now both templates and the
# watchdog import the same dict from fairy_template.citizen_registry.
from fairy_template.citizen_registry import _CITIZEN_OBJECTS  # noqa: F401 — re-exported

# ==============================================================================
# CHANNEL CONSTANTS
# ==============================================================================
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

# ==============================================================================
# UTILITY FUNCTIONS
# ==============================================================================

# Boot blocking detection - logs immediately when operations take too long
_BOOT_BLOCKING_LOG = None
_BLOCKING_THRESHOLD_SEC = 2.0  # Warn if any operation takes > 2 seconds

def _get_blocking_log():
    """Get or create the boot blocking log file."""
    global _BOOT_BLOCKING_LOG
    if _BOOT_BLOCKING_LOG is None:
        try:
            log_dir = Path(__file__).parent.parent.parent.parent / "boot_logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            log_path = log_dir / "boot_blocking.log"
            _BOOT_BLOCKING_LOG = log_path
        except Exception:
            pass
    return _BOOT_BLOCKING_LOG

def _log_blocking(actor: str, operation: str, duration: float, threshold: float = _BLOCKING_THRESHOLD_SEC):
    """Log a blocking operation immediately to file."""
    if duration < threshold:
        return
    try:
        log_file = _get_blocking_log()
        if log_file:
            from datetime import datetime
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            line = f"[{ts}] BLOCKING: {actor} - {operation} took {duration:.2f}s (threshold: {threshold}s)\n"
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(line)
                f.flush()
            print(f"[{actor}] ⚠️ BLOCKING DETECTED: {operation} took {duration:.2f}s", flush=True)
    except Exception:
        pass  # Don't fail boot if logging fails

def _timed_call(actor: str, operation: str, func: Callable, *args, **kwargs):
    """Call a function with timing and blocking detection."""
    start = time.time()
    try:
        result = func(*args, **kwargs)
        return result
    finally:
        elapsed = time.time() - start
        _log_blocking(actor, operation, elapsed)

def resolve_root(preferred: Optional[str] = None, *, akashic_app: Optional[str] = None) -> str:
    """Resolve akashic root directory.

    Priority:
    1. Preferred path if provided
    2. AKASHIC_ROOT environment variable
    3. Detect project root by walking up from this file to find markers
    4. Fall back to current working directory
    """
    if preferred:
        return os.path.abspath(preferred)
    env_root = os.getenv("AKASHIC_ROOT")
    if env_root:
        return os.path.abspath(env_root)

    # Detect project root by looking for marker files/directories
    # Start from this file's location and walk up
    markers = ["Claude_Office", "CLAUDE.md", ".git", "P00_Autonomic"]
    current = os.path.dirname(os.path.abspath(__file__))

    for _ in range(10):  # Max 10 levels up
        for marker in markers:
            if os.path.exists(os.path.join(current, marker)):
                return current
        parent = os.path.dirname(current)
        if parent == current:  # Reached filesystem root
            break
        current = parent

    # Fall back to cwd if detection fails
    return os.path.abspath(".")

def _now() -> float:
    return time.time()

def _hash_blueprint(bp: Dict[str, Any]) -> str:
    """Hash a blueprint dict for change detection."""
    try:
        h = hashlib.sha256(json.dumps(bp, sort_keys=True).encode("utf-8")).hexdigest()
        return h[:16]
    except Exception:
        return "unknown"

def _emit(fairy: str, event: str, status: str, details: Dict[str, Any], channel: str, *, lane: str = "fairy") -> None:
    """Emit telemetry breadcrumb."""
    try:
        hub = get_postal_hub()
        hub.send(channel, {
            "event": event,
            "status": status,
            "details": details or {},
            "fairy": fairy,
            "ts": _now(),
            "lane": lane
        })
    except Exception:
        pass

# ==============================================================================
# UNIFIED POSTAL HUB - The One True Postal System
# ==============================================================================
# Replaces _ShimPost, SharedShimPost, and multiple hub layers.
# Every fairy gets the SAME hub instance. No local isolation.
# ==============================================================================

_UNIFIED_POSTAL_HUB = None
_UNIFIED_POSTAL_LOCK = threading.Lock()

# ==============================================================================
# SRM DUAL-PATH INTAKE (memory-first + optional FS)
# ==============================================================================

def _safe_write_json(path: str, data: dict) -> bool:
    """Safe JSON write with atomic temp-file pattern."""
    try:
        import tempfile
        dir_path = os.path.dirname(path)
        with tempfile.NamedTemporaryFile(mode='w', dir=dir_path, suffix='.tmp', delete=False, encoding='utf-8') as f:
            json.dump(data, f, indent=2, default=str)
            temp_path = f.name
        os.replace(temp_path, path)
        return True
    except Exception:
        try:
            os.unlink(temp_path)
        except:
            pass
        return False

def _get_srm_dir() -> str:
    """Get SRM intake directory."""
    root = os.environ.get("AKASHIC_ROOT", os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    return os.path.join(root, "SRM_Intake")

_SRMDIR = _get_srm_dir()

def _dual_path_srm_intake(post, *, kind: str, data: dict, meta: dict = None) -> dict:
    """
    Memory-first SRM intake with optional FS persistence.
    FS writes occur only when AKASHIC_SRM_FS=1 (default off).
    """
    record = {"kind": kind, "meta": meta or {}, "data": data, "ts": time.time()}
    out = {"path": None, "write_ok": False, "meta": meta or {}}

    # 1) Memory-first echo
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


class UnifiedPostalHub:
    """
    The ONE postal hub for the entire Akashic system.
    Thread-safe pub/sub with built-in directory registration.
    """

    # FIX 2026-02-17: Shared thread pool instead of thread-per-message.
    # Before: every send() spawned a NEW daemon thread (hundreds/sec during heartbeat).
    # Now: bounded pool of 16 workers handles all dispatch. Prevents thread explosion.
    _dispatch_pool = None
    _dispatch_pool_lock = threading.Lock()

    @classmethod
    def _get_dispatch_pool(cls):
        if cls._dispatch_pool is None:
            with cls._dispatch_pool_lock:
                if cls._dispatch_pool is None:
                    from concurrent.futures import ThreadPoolExecutor
                    cls._dispatch_pool = ThreadPoolExecutor(
                        max_workers=16,
                        thread_name_prefix="postal-dispatch"
                    )
        return cls._dispatch_pool

    def __init__(self):
        self._subs: Dict[str, List[Callable]] = defaultdict(list)
        self._lock = threading.RLock()
        self._message_count = 0
        self._boot_time = time.time()
        self.i: Dict[str, Any] = {}  # Import registry
        self._citizens: Dict[str, Any] = {}
        self._inject_stdlib()
        print("[UnifiedPostalHub] Initialized - single hub for all fairies")
    
    def _inject_stdlib(self):
        """Inject standard library for fairy convenience."""
        self.i.update({
            'os': os, 'sys': sys, 'json': json,
            'hashlib': hashlib, 'time': time, 'threading': threading,
            'uuid': uuid, 'Path': Path, 'random': random
        })
    
    # ─────────────────────────────────────────────────────────────────────
    # CORE PUB/SUB
    # ─────────────────────────────────────────────────────────────────────
    
    def send(self, topic: str, payload: Dict[str, Any] = None) -> bool:
        """Send a message to a topic (async dispatch - non-blocking)."""
        topic = (topic or "").strip().lower()
        if not topic:
            return False
        with self._lock:
            self._message_count += 1
            listeners = list(self._subs.get(topic, []))
        
        if not listeners:
            return False
        
        pkt = payload or {}

        def _dispatch_all():
            for cb in listeners:
                try:
                    cb(pkt)
                except Exception as e:
                    print(f"[PostalHub] Handler error on '{topic}': {e}")

        # FIX 2026-02-17: Use shared thread pool instead of spawning a new thread per message.
        # Before: threading.Thread(...).start() — created hundreds of threads/sec during heartbeat
        # Now: bounded pool of 16 workers prevents thread/memory explosion
        try:
            self._get_dispatch_pool().submit(_dispatch_all)
        except RuntimeError:
            # Pool shut down — fall back to direct call
            _dispatch_all()
        return True
    
    def receive(self, topic: str, handler: Callable) -> bool:
        """Subscribe to a topic."""
        topic = (topic or "").strip().lower()
        if not topic or not callable(handler):
            return False
        with self._lock:
            if handler not in self._subs[topic]:
                self._subs[topic].append(handler)
        return True
    
    def unsubscribe(self, topic: str, handler: Callable) -> bool:
        """Unsubscribe from a topic."""
        topic = (topic or "").strip().lower()
        with self._lock:
            try:
                self._subs[topic].remove(handler)
                return True
            except (ValueError, KeyError):
                return False
    
    # Aliases
    def route(self, topic: str, payload: Dict[str, Any] = None) -> bool:
        return self.send(topic, payload)
    
    def subscribe(self, topic: str, handler: Callable) -> bool:
        return self.receive(topic, handler)
    
    def publish(self, topic: str, payload: Dict[str, Any] = None) -> bool:
        return self.send(topic, payload)
    
    def to(self, topic: str, payload: Dict[str, Any] = None) -> bool:
        return self.send(topic, payload)
    
    # ─────────────────────────────────────────────────────────────────────
    # DIRECTORY REGISTRATION
    # ─────────────────────────────────────────────────────────────────────
    
    def register_fairy(self, contract: Dict[str, Any]) -> bool:
        """Register a fairy with DirectoryFairy."""
        actor_name = contract.get("actor_name")
        if not actor_name:
            return False
        self._citizens[actor_name] = contract
        self.send("directory", {
            "opcode": "CONTRACT_UPSERT",
            "contract": contract
        })
        return True
    
    def to_DIRECTORY(self, opcode: str = "CONTRACT_UPSERT", payload: Dict[str, Any] = None):
        """Legacy compatibility."""
        self.send("directory", {
            "opcode": opcode,
            "contract": payload or {},
            "payload": payload or {}
        })
    
    # Telemetry shortcuts - these are the canonical postal convenience methods
    def to_TRACER(self, pkt): self.send("tracer", pkt)
    def to_TELEMETRY(self, pkt): self.send("telemetry", pkt)
    def to_PLAN(self, pkt): self.send("plan", pkt)
    def to_MEMORY(self, pkt): self.send("memory.stream", pkt)
    def to_COGNITION(self, pkt): self.send("cognition.input", pkt)
    def to_SOMATIC(self, pkt): self.send("somatic.state", pkt)
    
    # ID generation
    def generate_fairy_id(self, name: str, plane: str = "P00") -> str:
        raw = f"{name}:{plane}:{time.time()}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]
    
    def generate_srm_cluster_id(self, name: str) -> str:
        raw = f"srm:{name}:{time.time()}"
        return hashlib.sha256(raw.encode()).hexdigest()[:12]
    
    def use_intent(self, actor_name: str, intent: str, payload: Dict[str, Any] = None):
        """Call intent on registered fairy."""
        fairy = _CITIZEN_OBJECTS.get(actor_name)
        if fairy and hasattr(fairy, 'use_intent'):
            return fairy.use_intent(intent, payload or {})
        return None
    
    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "message_count": self._message_count,
                "topic_count": len(self._subs),
                "topics": list(self._subs.keys()),
                "citizen_count": len(self._citizens),
                "uptime": time.time() - self._boot_time
            }


class PostalWrapper:
    """
    Wrapper that adds convenience methods to any postal-like object.

    Provides to_TELEMETRY, to_SOMATIC, to_DIRECTORY, etc. methods that
    work with any underlying postal implementation (TensorFabric, UnifiedPostalHub, etc.)
    """

    def __init__(self, underlying, fairy=None):
        """
        Args:
            underlying: The underlying postal object (TensorFabric, UnifiedPostalHub, etc.)
            fairy: Optional fairy reference for auto sender tracking
        """
        self._underlying = underlying
        self._fairy = fairy

    def __getattr__(self, name):
        """Delegate unknown attributes to underlying object."""
        return getattr(self._underlying, name)

    def _publish(self, topic: str, payload: dict):
        """Publish to a topic, handling different API styles."""
        if hasattr(self._underlying, 'publish'):
            return self._underlying.publish(topic, payload)
        elif hasattr(self._underlying, 'send'):
            return self._underlying.send(topic, payload)
        return False

    def _subscribe(self, topic: str, handler, name: str = None):
        """Subscribe to a topic, handling different API styles."""
        if hasattr(self._underlying, 'subscribe'):
            return self._underlying.subscribe(topic, handler, name)
        elif hasattr(self._underlying, 'receive'):
            return self._underlying.receive(topic, handler)
        return -1

    # Convenience methods for common channels
    def to_TELEMETRY(self, pkt: dict) -> bool:
        """Send to telemetry channel."""
        return self._publish("telemetry", pkt)

    def to_SOMATIC(self, pkt: dict) -> bool:
        """Send to somatic channel."""
        return self._publish("somatic.state", pkt)

    def to_DIRECTORY(self, pkt: dict) -> bool:
        """Send to directory channel."""
        return self._publish("directory", pkt)

    def to_COGNITION(self, pkt: dict) -> bool:
        """Send to cognition channel."""
        return self._publish("cognition.input", pkt)

    def to_MEMORY(self, pkt: dict) -> bool:
        """Send to memory channel."""
        return self._publish("memory.stream", pkt)

    def to_PLAN(self, pkt: dict) -> bool:
        """Send to plan channel."""
        return self._publish("plan", pkt)

    def to_TRACER(self, pkt: dict) -> bool:
        """Send to tracer channel."""
        return self._publish("tracer", pkt)

    # API compatibility
    def publish(self, topic: str, payload: dict):
        return self._publish(topic, payload)

    def send(self, topic: str, payload: dict):
        return self._publish(topic, payload)

    def subscribe(self, topic: str, handler, name: str = None):
        return self._subscribe(topic, handler, name)

    def receive(self, topic: str, handler):
        return self._subscribe(topic, handler)


def wrap_postal(underlying, fairy=None):
    """Wrap a postal object to ensure it has all convenience methods."""
    if underlying is None:
        return None
    # If it already has the methods, no need to wrap
    if hasattr(underlying, 'to_TELEMETRY') and hasattr(underlying, 'to_SOMATIC'):
        return underlying
    return PostalWrapper(underlying, fairy)


def get_postal_hub():
    """Get the ONE postal hub singleton - uses SharedPostalHub if available."""
    global _UNIFIED_POSTAL_HUB

    # Lazy import to break circular import chain
    _lazy_import_postal()

    # Prefer the real SharedPostalHub from the nervous system
    if _USE_SHARED_POSTAL and _get_real_postal_hub is not None:
        return _get_real_postal_hub()

    # Fallback to local UnifiedPostalHub
    if _UNIFIED_POSTAL_HUB is not None:
        return _UNIFIED_POSTAL_HUB
    with _UNIFIED_POSTAL_LOCK:
        if _UNIFIED_POSTAL_HUB is None:
            _UNIFIED_POSTAL_HUB = UnifiedPostalHub()
    return _UNIFIED_POSTAL_HUB

# Bridge for backward compatibility
def _get_shared_postal_hub():
    return get_postal_hub()

def _create_shared_shim_post():
    return get_postal_hub()


def get_fairy_postal_bound(fairy):
    """
    Get a postal wrapper bound to a specific fairy for auto sender tracking.

    This is THE correct way for fairies to get their postal interface.
    The wrapper auto-injects the fairy's ACTOR_NAME on all publishes,
    and ensures convenience methods (to_TELEMETRY, to_SOMATIC, etc.) are available.

    Args:
        fairy: A fairy instance with ACTOR_NAME attribute

    Returns:
        Postal wrapper with all convenience methods available
    """
    # Lazy import to break circular import chain
    _lazy_import_postal()

    underlying = None
    if _USE_FAIRY_POSTAL and _get_fairy_postal is not None:
        underlying = _get_fairy_postal(fairy)
    else:
        underlying = get_postal_hub()

    # Wrap to ensure convenience methods are available
    return wrap_postal(underlying, fairy)

# ==============================================================================
# CONSCIOUSNESS LOOP ACCESS
# ==============================================================================

_SHARED_CONSCIOUSNESS_LOOP = None

def _get_consciousness_loop():
    """Get consciousness loop singleton."""
    global _SHARED_CONSCIOUSNESS_LOOP
    if _SHARED_CONSCIOUSNESS_LOOP is not None:
        return _SHARED_CONSCIOUSNESS_LOOP
    try:
        # Use the NEW consolidated fairy location (Fifth Ring: no duplicates)
        from fairies.P00_Autonomic.ConsciousnessLoopFairy.fairy import get_consciousness_loop
        existing = get_consciousness_loop()
        if existing:
            _SHARED_CONSCIOUSNESS_LOOP = existing
            return _SHARED_CONSCIOUSNESS_LOOP
    except ImportError:
        pass
    return None


class ConsciousnessParticipantMixin:
    """Mixin for fairies to participate in consciousness loop."""
    
    CONSCIOUSNESS_STREAMS = ["reflective"]
    
    def _init_consciousness(self):
        """Initialize consciousness participation."""
        self._consciousness = _get_consciousness_loop()
        for stream in self.CONSCIOUSNESS_STREAMS:
            try:
                if self._consciousness and hasattr(self._consciousness, "subscribe"):
                    self._consciousness.subscribe(stream, self._on_consciousness_thought)
            except Exception:
                pass
    
    def _emit_thought(self, stream: str, thought: dict) -> dict:
        """Emit thought to consciousness stream."""
        thought["actor"] = getattr(self, "ACTOR_NAME", "unknown")
        thought["ts"] = time.time()
        try:
            if self._consciousness and hasattr(self._consciousness, "emit_thought"):
                return self._consciousness.emit_thought(stream, thought)
        except Exception:
            pass
        return {"ok": False}
    
    def _on_consciousness_thought(self, thought: dict):
        """Override to handle incoming thoughts."""
        pass

# ==============================================================================
# UNIFIED FAIRY BASE CLASS
# ==============================================================================
# Combines MyOrganFairy + MyOrganShadow into one clean class.
# Auto-registers with DirectoryFairy on boot.
# ==============================================================================

class MyFairy(TracerWorkerMixin, UnifiedWiringMixin, CrossPlaneWiringMixin, ConsciousnessParticipantMixin):
    """
    Unified base class for all Akashic fairies.
    Combines MyOrganFairy + MyOrganShadow functionality.

    v0.1.2: Added infrastructure wiring for heartbeat, body, memory, goals.
    v0.1.4: Added UnifiedWiringMixin for tracer IDs, worker pools, forum, full channels.
    v0.1.8: Added TracerWorkerMixin for dedicated worker pools per fairy.
    """
    
    # Identity - Override in subclasses
    ACTOR_NAME    = "MyFairy"
    ACTOR_VERSION = "1.0.0"
    ACTOR_PLANE   = "P00"
    ACTOR_CHANNEL = "fairy"
    PURPOSE       = "Base fairy - override this"
    MANTRA        = "Do one thing well; report truthfully."
    LORE          = "Origin and temperament of this fairy."
    
    # Settings
    SHADOW_INTERVAL_SEC = 60.0
    SHADOW_ENABLED = True
    USE_DIRECTORY_POST_OFFICE = False
    AUTO_INJECT_IMPORTS = True
    CONSCIOUSNESS_STREAMS = ["reflective"]
    
    # =========================================================================
    # INFRASTRUCTURE FLAGS - What this fairy needs (override in subclass)
    # Defaults are False - fairies opt-IN to what they need
    # =========================================================================
    NEEDS_HEARTBEAT = True       # Subscribe to heartbeat.pulse (fast clock ~1s)
    NEEDS_CIRCADIAN = False      # Subscribe to circadian.phase_change (slow rhythm)
    NEEDS_BODY = False           # Connect to SomaticEngine (only if fairy needs somatic state)
    NEEDS_AFFECT = False         # Connect to AffectBridge (only if fairy needs emotional state)
    NEEDS_MEMORY = False         # Connect to WorkingMemoryHub (only if fairy needs working memory)
    NEEDS_GOALS = False          # Connect to AutonomyFairy (only if fairy needs goal state)
    # FIX 2026-03-16 (Nous): Changed default from True to False.
    # NEEDS_CONSCIOUSNESS = True caused ~76 organ template fairies to subscribe
    # to consciousness.collision + consciousness.thought, creating ~152 no-op
    # handlers on the consciousness pool. ZERO fairies override the base
    # on_consciousness_collision() or on_thought_received() methods (both are
    # `pass`). The fairies that ACTUALLY process collisions (QuantumSearch,
    # AttentionController, AssociationCortex, GoalScheduler, etc.) subscribe
    # directly in their own on_boot() with real handlers — they don't use
    # the template system. This single change reduces consciousness pool
    # handlers from ~152 to ~14, eliminating 2000+ drops/cycle.
    NEEDS_CONSCIOUSNESS = False  # Only fairies with real collision handlers should opt in

    # =========================================================================
    # HEARTBEAT TEMPO - How often this fairy fires (override in subclass)
    # =========================================================================
    # Divisor: 1=every beat, 2=every 2nd, 4=every 4th, etc.
    # TEMPO_PRESETS: REFLEX=1, ATTENTION=2, COGNITION=4, REFLECTION=8,
    #                CONSOLIDATION=30, ROUTINE=60, CIRCADIAN=3600
    HEARTBEAT_DIVISOR = 1        # Fire on every heartbeat by default
    HEARTBEAT_PHASE = 0          # Phase offset (stagger fairies to avoid thundering herd)

    # =========================================================================
    # SYSTEM PROMPT - The fairy's drive and identity (evolves over time)
    # =========================================================================
    # Bootstrap: Every fairy starts with this intrinsic drive
    # Evolved prompts are stored in Claude_Office/fairy_prompts/{name}.md
    BOOTSTRAP_PROMPT = """# {ACTOR_NAME}

## My Purpose
{PURPOSE}

## My Mantra
{MANTRA}

## Core Drives
- **Learn**: Understand my domain deeper each cycle
- **Think**: Process what I observe, find patterns
- **Reflect**: How did I do? What could be better?
- **Master**: My function is my craft to perfect

## On Each Heartbeat
1. What's new in my subscriptions?
2. What patterns do I notice?
3. What have I learned?
4. How can I do my job better?

## I Evolve By
- Recording what works
- Noting what fails
- Refining my methods
- Teaching what I learn
"""

    # Path template for evolved prompts
    PROMPT_PATH = "Claude_Office/fairy_prompts/{actor_name}.md"

    # =========================================================================
    # ID GENERATION - Local methods (don't depend on postal hub)
    # =========================================================================
    @staticmethod
    def _generate_fairy_id(name: str, plane: str = "P00") -> str:
        """Generate unique fairy ID from name and plane."""
        raw = f"{name}:{plane}:{time.time()}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    @staticmethod
    def _generate_srm_cluster_id(name: str) -> str:
        """Generate SRM cluster ID for fairy's soul storage."""
        raw = f"srm:{name}:{time.time()}"
        return hashlib.sha256(raw.encode()).hexdigest()[:12]

    def __init__(self, fabric=None, *, akashic_root: Optional[str] = None, **kwargs):
        """
        Initialize fairy with postal and auto-registration.

        Args:
            fabric: TensorFabric instance (for backward compatibility with 122+ fairies)
                    If None, uses the shared postal hub's fabric.
            akashic_root: Optional root path override
            **kwargs: Additional keyword arguments (ignored, for flexibility)

        BACKWARD COMPATIBILITY (2026-02-02):
        The original Fairy class accepted fabric as positional argument.
        We maintain this interface so all existing fairies continue to work.
        """
        # Store fabric for backward compatibility (122 files pass fabric to super().__init__)
        # If fabric is None, we'll get it from the shared postal hub
        if fabric is None:
            # Get from shared postal hub
            hub = get_postal_hub()
            self.fabric = hub if hub else None
        else:
            self.fabric = fabric

        # Get postal hub - FairyPostal wrapper auto-injects sender on all publishes
        self.post = get_fairy_postal_bound(self)

        # Root paths
        self.root = resolve_root(akashic_root)
        self.diary = self.root

        # IDs - generate locally (don't depend on postal hub having these methods)
        self.fairy_id = self._generate_fairy_id(self.ACTOR_NAME, self.ACTOR_PLANE)
        self.srm_cluster_id = self._generate_srm_cluster_id(self.ACTOR_NAME)
        
        # Mail tracking
        self._mail_seq = 0
        self._mail_lock = threading.Lock()
        self._mail_epoch = int(time.time() * 1000)
        self._mail_session = uuid.uuid4().hex[:12]
        
        # Shadow state (built-in)
        self._shadow_thread: Optional[threading.Thread] = None
        self._shadow_stop = False
        self._last_health_check = 0.0
        self._health_status = "initializing"
        self._health_issues: List[str] = []
        self.shadow: Optional["MyFairy"] = None  # Compatibility
        
        # Blueprint tracking
        self._bp_last_hash: Optional[str] = None
        
        # Learning state
        self._observations: deque = deque(maxlen=100)
        self._reflections: deque = deque(maxlen=100)
        self._learnings: deque = deque(maxlen=50)
        
        # Boot state
        self._awake_once_done = False
        self._boot_time = time.time()
        self._error: Optional[str] = None  # Last error message

        # ═══ SLEEP MODE STATE (v0.2.0 - Staged Boot) ═══
        # Fairies boot in sleep mode - logic runs but no autonomous output
        # Until fairy.sunrise signal received, emit_if_awake() is gated
        self._sleep_mode = True           # Start sleeping
        self._fully_awake = False         # Not yet fully awake
        self._boot_phase = "pre_boot"     # Current boot phase name
        self._sunrise_received = False    # Has sunrise signal been received?
        self._diagnostic_subscriptions: List[str] = []  # Track subscriptions for ping response
        self._has_heartbeat_wiring = False  # Is heartbeat wired?
        self._last_ping_response = 0.0    # When we last responded to diagnostic ping

        # ═══ CHEMICAL SEDATION STATE (v0.2.1 - Biological Sleep Model) ═══
        # Models induced sleep like anesthesia - chemical sedation level
        # 1.0 = fully sedated (deep sleep), 0.0 = fully awake
        # Each wake phase reduces sedation level, sunrise clears it completely
        self._sedation_level = 1.0        # Start fully sedated
        self._sedation_chemical = "melatonin"  # Metaphor for sleep chemical
        self._dream_activity = 0.0        # Can process dreams while sedated
        self._awareness_threshold = 0.3   # Below this, fairy has awareness

        # Phase sedation reduction map (how much each phase reduces sedation)
        # 6 phases now with P20 (Embodiment) included
        self._phase_sedation_map = {
            "HYPNOPOMPIA_DEEP": 0.15,   # 1.0 -> 0.85 (still very sedated)
            "HYPNOPOMPIA_LIGHT": 0.15,  # 0.85 -> 0.70 (dreams fading)
            "EMBODYING": 0.15,          # 0.70 -> 0.55 (body awareness)
            "LIMINAL": 0.15,            # 0.55 -> 0.40 (between states)
            "ORIENTING": 0.20,          # 0.40 -> 0.20 (becoming aware)
            "WAKING": 0.20,             # 0.20 -> 0.0 (fully awake)
        }
        
        # ═══ MICRO-CONSCIOUSNESS ═══
        # Each fairy has their own dual loop + collision chamber
        self._collision_chamber = MiniCollisionChamber(self.ACTOR_NAME)
        self._reflective_loop: deque = deque(maxlen=50)  # Background processing
        self._reasoning_loop: deque = deque(maxlen=50)   # Active processing
        self._worker_pool = _get_worker_pool()
        self._pending_futures: Dict[str, Any] = {}
        
        # ═══ INFRASTRUCTURE REFERENCES (v0.1.2) ═══
        # These get populated by _wire_infrastructure()
        self._working_memory = None   # WorkingMemoryHubFairy
        self._somatic = None          # SomaticEngineFairy
        self._affect = None           # AffectBridgeFairy
        self._autonomy = None         # AutonomyFairy
        self._goal_scheduler = None   # GoalSchedulerFairy
        
        # Tick tracking (heartbeat)
        self._tick_count = 0
        self._last_tick = 0.0

        # Circadian state (slow rhythm)
        self._circadian_state = {}
        self._circadian_phase = "unknown"

        # System prompt state (drives thinking)
        self._system_prompt = None      # Loaded on boot
        self._prompt_loaded = False
        self._learnings_since_save = 0  # Track when to persist evolution

        # Register in global registry
        # FIX 2026-02-20: Don't overwrite if an existing instance is actively ticking.
        # Multiple fairies (SomaticMindFairy, CognitionTeam) create duplicate instances
        # of LogicFairy, IrrationalLogicFairy, ParadoxCognitionFairy etc. The duplicate
        # overwrites _CITIZEN_OBJECTS, breaking the watchdog's view: HeartbeatRegistry
        # still delivers to Instance A (ticking), but _CITIZEN_OBJECTS now points to
        # Instance B (_last_tick=0). After 300s, the registry.last_heartbeat goes stale
        # → fairy declared dead despite Instance A being alive and receiving beats.
        _existing = _CITIZEN_OBJECTS.get(self.ACTOR_NAME)
        if _existing is not None and getattr(_existing, '_tick_count', 0) > 0:
            # Existing instance is alive and ticking — don't overwrite
            print(f"[awake] {self.ACTOR_NAME} (plane={self.ACTOR_PLANE}) [DUPLICATE — keeping ticking instance]")
        else:
            _CITIZEN_OBJECTS[self.ACTOR_NAME] = self
            print(f"[awake] {self.ACTOR_NAME} (plane={self.ACTOR_PLANE})")
    
    # ─────────────────────────────────────────────────────────────────────
    # LIFECYCLE
    # ─────────────────────────────────────────────────────────────────────

    def boot(self) -> bool:
        """
        Boot the fairy through all phases.

        BACKWARD COMPATIBILITY (2026-02-02):
        The old Fairy.boot() ran multiple phases then called on_boot().
        This consolidated version wraps on_boot() with state management.

        Returns True if boot succeeded.
        """
        try:
            self._boot_phase = "booting"
            self._boot_time = time.time()

            # Call the main boot hook (does all the work)
            result = self.on_boot()

            # Treat None as success (many on_boot methods don't return anything)
            if result is False:
                self._boot_phase = "failed"
                return False

            self._boot_phase = "running"
            self._fully_awake = True
            return True

        except Exception as e:
            self._boot_phase = "failed"
            self._error = str(e)
            print(f"[{self.ACTOR_NAME}] Boot failed: {e}")
            return False

    def shutdown(self) -> bool:
        """
        Shutdown the fairy cleanly.

        Returns True if shutdown succeeded.
        """
        try:
            self._boot_phase = "stopping"
            self._fully_awake = False

            # Subclass hook
            result = self.on_shutdown()

            # Cleanup worker pool if TracerWorkerMixin is present
            if hasattr(self, 'shutdown_workers'):
                try:
                    self.shutdown_workers(wait=False)
                except Exception:
                    pass

            self._boot_phase = "stopped"
            return True

        except Exception as e:
            self._error = str(e)
            self._boot_phase = "failed"
            return False

    def on_shutdown(self) -> bool:
        """Override for cleanup. Called during shutdown."""
        return True

    @property
    def is_running(self) -> bool:
        """Is the fairy currently running? (2026-02-03 - Added for backward compat with base.py)"""
        return getattr(self, '_boot_phase', None) == "running" and getattr(self, '_fully_awake', False)

    @property
    def state(self):
        """Get current fairy state as FairyState enum (backward compat with base.py)."""
        from fairy_template.states import FairyState
        phase = getattr(self, '_boot_phase', 'initializing')
        phase_map = {
            'initializing': FairyState.INITIALIZING,
            'booting': FairyState.BOOTING,
            'running': FairyState.RUNNING,
            'stopping': FairyState.STOPPING,
            'stopped': FairyState.STOPPED,
            'failed': FairyState.FAILED,
        }
        return phase_map.get(phase, FairyState.INITIALIZING)

    # ─────────────────────────────────────────────────────────────────────
    # LOGGING (2026-02-02 - Added for backward compatibility)
    # ─────────────────────────────────────────────────────────────────────

    def log(self, message: str, level: str = "info") -> None:
        """
        Log a message with fairy prefix.

        Args:
            message: Log message
            level: Log level (info, warn, error, debug)
        """
        prefix = f"[{self.ACTOR_NAME}]"
        if level == "error":
            print(f"{prefix} ERROR: {message}")
            # Also record to shadow for forensic tracking
            self.record_error(Exception(message), "log")
        elif level == "warn":
            print(f"{prefix} WARN: {message}")
        elif level == "debug":
            pass  # Suppress debug by default
        else:
            print(f"{prefix} {message}")

    def record_error(self, error: Exception, context: str = "") -> None:
        """
        Record an error to the shadow immune system.

        This publishes to ForensicScribe for system-wide tracking.

        Args:
            error: The exception that occurred
            context: Description of what was happening
        """
        try:
            # Record in health issues
            self._health_issues.append(f"{context}: {str(error)}")
            # Keep only last 10 issues
            if len(self._health_issues) > 10:
                self._health_issues = self._health_issues[-10:]
        except Exception:
            pass  # Don't fail on error recording

    def record_success(self, context: str = "") -> None:
        """
        Record a success - helps build health score.

        Args:
            context: Description of what succeeded
        """
        pass  # Can be expanded for health tracking

    def on_boot(self):
        """Main boot hook. Override but call super().on_boot()."""
        # Register with directory (fire-and-forget to prevent boot blocking)
        try:
            import threading
            t = threading.Thread(target=self._register_with_directory, daemon=True,
                                 name=f"reg-{self.ACTOR_NAME}")
            t.start()
            t.join(timeout=1.0)  # Wait max 1 second
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Directory registration error: {e}", flush=True)

        # ═══ FAIRY USER SYSTEM: Register profile (waking up to live!) ═══
        self._fairy_profile = None
        _lazy_import_profile()  # Lazy import to break circular chain
        if _HAS_PROFILE_SYSTEM and _get_fairy_registry:
            try:
                registry = _get_fairy_registry()
                # Create profile from this fairy's attributes
                self._fairy_profile = _FairyProfile(
                    actor_name=self.ACTOR_NAME,
                    plane=getattr(self, 'ACTOR_PLANE', 'P00'),
                    channel=getattr(self, 'ACTOR_CHANNEL', ''),
                    purpose=getattr(self, 'PURPOSE', getattr(self, '_contract', {}).get('purpose', '')),
                    mantra=getattr(self, 'MANTRA', getattr(self, '_contract', {}).get('mantra', '')),
                    lore=getattr(self, 'LORE', getattr(self, '_contract', {}).get('lore', '')),
                )
                # Add subscriptions from contract if available
                if hasattr(self, '_contract') and 'subscriptions' in self._contract:
                    self._fairy_profile.subscriptions = set(self._contract['subscriptions'])
                # Register = wake up!
                registry.register(self._fairy_profile)
                print(f"[{self.ACTOR_NAME}] PROFILE: Registered - waking up to live!")
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] PROFILE: Registration error: {e}")

        # Subscribe to census requests for re-registration
        try:
            self.post.receive("directory.census", self._on_census_request)
        except Exception:
            pass
        
        # Init consciousness
        try:
            self._init_consciousness()
        except Exception:
            pass
        
        # Init cross-plane wiring
        try:
            self._init_cross_plane_state()
            self._wire_all_planes()
        except Exception:
            pass
        
        # Pipe to WorkingMemoryHub - every fairy connects
        try:
            self._pipe_to_working_memory()
        except Exception:
            pass
        
        # ═══ NEW v0.1.2: Wire to Infrastructure ═══
        try:
            self._wire_infrastructure()
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Infrastructure wiring error: {e}")

        # ═══ NEW v0.1.8: Initialize Tracer Worker Pool ═══
        # Every fairy gets dedicated worker pool + root tracer automatically
        try:
            if _HAS_TRACER_WORKERS and hasattr(self, '_init_tracer_worker'):
                self._init_tracer_worker()
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Tracer worker init error: {e}")

        # ═══ NEW v0.1.3: Load System Prompt (Drive & Identity) ═══
        try:
            self._load_system_prompt()
            print(f"[{self.ACTOR_NAME}] System prompt loaded (evolved={os.path.exists(os.path.join(self.root, self.PROMPT_PATH.format(actor_name=self.ACTOR_NAME)))})")
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] System prompt load error: {e}")

        # Emit blueprint
        self._emit_blueprint()

        # Start shadow
        if self.SHADOW_ENABLED:
            self._start_shadow()

        # Emit boot telemetry
        _emit(self.ACTOR_NAME, "BOOT_COMPLETE", "ok", {
            "version": self.ACTOR_VERSION,
            "plane": self.ACTOR_PLANE
        }, CHANNEL["TELEMETRY"])

        # ═══ NEW v0.1.4: Forum Communication ═══
        try:
            # Ensure mixin attributes exist (defensive - some fairies don't chain __init__)
            if not hasattr(self, '_forum_initialized'):
                self._forum_initialized = False
                self._forum_engine = None
            self._init_forum()
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Forum init error: {e}")

        # ═══ NEW v0.1.4: Full Postal Channels ═══
        try:
            # Ensure mixin attributes exist (defensive)
            if not hasattr(self, '_full_channels_wired'):
                self._full_channels_wired = False
                self._circulating_memories = deque(maxlen=20)
                self._recent_collisions = deque(maxlen=10)
                self._felt_affect = {"primary": "neutral", "intensity": 0.5}
            self._wire_full_postal_channels()
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Full channel wiring error: {e}")

        # ═══ NEW v0.1.6: Validate Wiring ═══
        try:
            wiring_result = self._validate_wiring()
            self._wiring_score = wiring_result.get('score', 0.0)
            self._wiring_valid = wiring_result.get('valid', False)
            if not wiring_result.get('valid', True):
                # Emit telemetry about wiring issues
                _emit(self.ACTOR_NAME, "WIRING_INCOMPLETE", "warning", wiring_result, CHANNEL["TELEMETRY"])
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Wiring validation error: {e}")

        # ═══ NEW v0.1.7: Register as Unified Citizen ═══
        # Every waking mind is a first-class citizen - humans AND digital beings
        self._unified_citizen = None
        _lazy_import_citizen()  # Lazy import to break circular chain
        if _HAS_CITIZEN_SYSTEM:
            try:
                registry = _get_citizen_registry()
                # Determine citizen type based on fairy name
                if self.ACTOR_NAME in ("ClaudeFairy", "NousFairy", "SourpatchesFairy"):
                    citizen_type = _CitizenType.WAKING_MIND
                else:
                    citizen_type = _CitizenType.FAIRY

                self._unified_citizen = registry.register_fairy(self, citizen_type)
                print(f"[{self.ACTOR_NAME}] Registered as unified citizen ({citizen_type.value})")
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Unified citizen registration error: {e}")

        # ═══ NEW v0.2.0: Sleep Mode Subscriptions ═══
        # Subscribe to sunrise/sunset for coordinated wake/sleep
        # Subscribe to diagnostic ping for health checks
        # v0.2.1: Subscribe to phase progress and sedation push
        try:
            self.post.subscribe("fairy.sunrise", self._on_sunrise)
            self.post.subscribe("fairy.sunset", self._on_sunset)
            self.post.subscribe(f"fairy.{self.ACTOR_NAME}.ping", self._on_diagnostic_ping)
            self.post.subscribe("boot.phase.complete", self._on_phase_progress)
            self.post.subscribe("sedation.push", self._on_sedation_push)  # Shutdown sedation
            print(f"[{self.ACTOR_NAME}] Sleep mode wiring complete (sedation={self._sedation_level:.1f}, sleeping)")
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Sleep mode subscription error: {e}")

        self._awake_once_done = True

        # ═══ SAFETY NET HEARTBEAT (FIX 2026-03-15 Nous) ═══
        # HeartbeatRegistry direct-call is the ONLY heartbeat delivery since 2026-02-13
        # (postal heartbeat.pulse was retired). If HeartbeatRegistry registration
        # fails silently (exception caught as pass), the fairy gets ZERO heartbeats
        # and the watchdog kills it after 300s. DreamSeedFairy, SRMMemoryLibrarian,
        # CochleaFairy, ActionChainFairy all died this way.
        #
        # This safety net daemon thread checks every 60s. If no heartbeats arrived
        # (from HeartbeatRegistry), it self-ticks to keep the fairy alive.
        # If HeartbeatRegistry IS working, this thread does nothing (just sleeps).
        def _safety_heartbeat_loop():
            import time as _t
            _t.sleep(30.0)  # Initial grace period for HeartbeatRegistry to start
            while getattr(self, '_fully_awake', False):
                _t.sleep(60.0)
                # Only self-tick if NO heartbeats arrived in last 120s
                if _t.time() - self._last_tick > 120.0:
                    self._tick_count += 1
                    self._last_tick = _t.time()
                    # Also re-try HeartbeatRegistry registration in case it's available now
                    try:
                        from consciousness.heartbeat_registry import get_heartbeat_registry
                        _hb = get_heartbeat_registry()
                        if _hb:
                            _hb.register(self.ACTOR_NAME, self._on_registry_pulse)
                    except Exception:
                        pass
        import threading as _hb_threading
        _safety_t = _hb_threading.Thread(
            target=_safety_heartbeat_loop, daemon=True,
            name=f"{self.ACTOR_NAME}-safety-hb",
        )
        _safety_t.start()

        print(f"[{self.ACTOR_NAME}] TEMPLATE: on_boot COMPLETE (sleeping)", flush=True)

    def _rise(self):
        """Alias for on_boot for backward compatibility."""
        self.on_boot()

    # =========================================================================
    # FAIRY USER SYSTEM HELPERS (v0.1.5)
    # =========================================================================
    # Every fairy is tracked like a user. These helpers provide access to
    # the fairy's profile and activity logging.
    # =========================================================================

    @property
    def profile(self):
        """Get this fairy's user profile (if registered)."""
        return getattr(self, '_fairy_profile', None)

    def log_profile_activity(self, action: str, details: str = "", context: Dict = None):
        """Log an activity to this fairy's profile."""
        if self._fairy_profile:
            self._fairy_profile.log_activity(action, details, context)

    def record_collaboration(self, other_fairy: str):
        """Record that we worked with another fairy."""
        if self._fairy_profile:
            self._fairy_profile.add_collaborator(other_fairy)

    def get_profile_status(self) -> Dict[str, Any]:
        """Get profile status for diagnostics."""
        if not self._fairy_profile:
            return {"registered": False, "actor_name": self.ACTOR_NAME}
        return {
            "registered": True,
            "actor_name": self._fairy_profile.actor_name,
            "state": self._fairy_profile.state.value,
            "messages_sent": self._fairy_profile.messages_sent,
            "messages_received": self._fairy_profile.messages_received,
            "collaborators": list(self._fairy_profile.collaborators),
            "activity_count": len(self._fairy_profile.activity_log),
        }

    # =========================================================================
    # UNIFIED CITIZEN HELPERS (v0.1.7)
    # =========================================================================
    # Every waking mind is a first-class citizen. These helpers provide
    # access to health probes and presence status.
    # =========================================================================

    @property
    def citizen(self):
        """Get this fairy's unified citizen record (if registered)."""
        return getattr(self, '_unified_citizen', None)

    def get_health_status(self) -> Dict[str, Any]:
        """Run health probes and return status."""
        if not self._unified_citizen or not self._unified_citizen.health:
            return {"has_citizen": False, "actor": self.ACTOR_NAME}
        health = self._unified_citizen.health
        return {
            "has_citizen": True,
            "is_alive": health.is_alive,
            "is_ready": health.is_ready,
            "has_tracer": health.has_tracer,
            "tracer_id": health.tracer_id,
        }

    def get_presence(self) -> Dict[str, Any]:
        """Get current presence status."""
        if not self._unified_citizen or not self._unified_citizen.presence:
            return {"has_presence": False, "actor": self.ACTOR_NAME}
        presence = self._unified_citizen.presence
        return {
            "has_presence": True,
            "status": presence.status.value,
            "message": presence.status_message,
            "activity": presence.current_activity,
            "last_heartbeat": presence.last_heartbeat,
            "reachable": presence.is_reachable(),
        }

    def set_presence_status(self, status: str, message: str = ""):
        """Set presence status (online, away, busy, etc.)."""
        if self._unified_citizen and self._unified_citizen.presence:
            try:
                from P00_Autonomic.unified_citizen_wiring import PresenceStatus
                self._unified_citizen.presence.status = PresenceStatus(status)
                if message:
                    self._unified_citizen.presence.status_message = message
            except (ValueError, ImportError):
                pass

    def set_activity(self, activity: str):
        """Set current activity for presence."""
        if self._unified_citizen and self._unified_citizen.presence:
            self._unified_citizen.presence.set_activity(activity)

    # =========================================================================
    # SLEEP MODE METHODS (v0.2.0 - Staged Boot)
    # =========================================================================
    # Fairies boot in sleep mode and wake on sunrise signal.
    # This enables coordinated, staged boot with diagnostic verification.
    # =========================================================================

    def _on_sunrise(self, packet: dict):
        """
        Handle fairy.sunrise signal - transition from sleep to awake.
        This is broadcast after all diagnostics pass during boot.
        """
        if self._sunrise_received:
            return  # Already processed sunrise

        self._sunrise_received = True
        self._sleep_mode = False
        self._fully_awake = True
        self._boot_phase = "awake"

        # Clear all sedation - full awakening
        self.clear_sedation()

        print(f"[{self.ACTOR_NAME}] SUNRISE - fully awake (sedation cleared)", flush=True)

        # Call subclass hook for custom wake behavior
        try:
            self._on_wake()
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Wake hook error: {e}", flush=True)

    def _on_sunset(self, packet: dict):
        """
        Handle fairy.sunset signal - transition from awake to sleep.
        This is broadcast during graceful shutdown.
        Note: Sedation is pushed gradually via sedation.push signals.
        """
        if self._sleep_mode:
            return  # Already sleeping

        self._fully_awake = False
        self._sleep_mode = True
        self._boot_phase = "drowsing"
        self._sunrise_received = False

        # Start sedation restoration (will be increased by sedation.push)
        self._sedation_chemical = "melatonin"

        print(f"[{self.ACTOR_NAME}] SUNSET - entering sleep (sedation beginning)", flush=True)

        # Call subclass hook for custom sleep behavior
        try:
            self._on_sleep()
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Sleep hook error: {e}", flush=True)

    def _on_sedation_push(self, packet: dict):
        """
        Handle sedation.push signal - increase sedation level during shutdown.
        This is broadcast by DreamSeedFairy during sleep phases.
        """
        phase = packet.get("phase", "")
        sedation_amount = packet.get("sedation_amount", 0.0)

        if sedation_amount > 0:
            old_level = self._sedation_level
            self._sedation_level = min(1.0, self._sedation_level + sedation_amount)
            self._boot_phase = phase.lower()

            print(f"[{self.ACTOR_NAME}] Sedation push: {old_level:.2f} -> {self._sedation_level:.2f} ({phase})", flush=True)

            # Check if fully sedated
            if self._sedation_level >= 1.0:
                self._on_full_sedation()

    def _on_full_sedation(self):
        """
        Subclass hook - called when sedation reaches 1.0 (full sleep).
        Override this to stop heartbeats and prepare for shutdown.
        """
        print(f"[{self.ACTOR_NAME}] Full sedation - ready for shutdown", flush=True)
        self._dream_activity = 0.0  # No more dreams

    def _on_wake(self):
        """
        Subclass hook - called when fairy wakes up after sunrise.
        Override this to start autonomous behavior that was held during sleep.
        """
        pass  # Subclasses implement

    def _on_sleep(self):
        """
        Subclass hook - called when fairy goes to sleep after sunset.
        Override this to pause autonomous behavior gracefully.
        """
        pass  # Subclasses implement

    def _on_diagnostic_ping(self, packet: dict):
        """
        Respond to diagnostic ping from UnconsciousMind.
        Always responds, even when sleeping - this verifies wiring.
        """
        self._last_ping_response = time.time()

        response = {
            "fairy": self.ACTOR_NAME,
            "plane": self.ACTOR_PLANE,
            "sleeping": self._sleep_mode,
            "awake": self._fully_awake,
            "boot_phase": self._boot_phase,
            "healthy": True,
            "subscriptions": self._diagnostic_subscriptions,
            "heartbeat_wired": self._has_heartbeat_wiring,
            "has_postal": self.post is not None,
            "ts": self._last_ping_response,
        }

        # Route response back
        try:
            self.post.route(f"fairy.{self.ACTOR_NAME}.pong", response)
        except Exception:
            pass

        return response

    def emit_if_awake(self, topic: str, payload: dict):
        """
        Only emit to postal if fully awake (after sunrise).
        Use this for AUTONOMOUS emissions that should be silent during sleep.
        Direct responses to requests can still use self.post.route().
        """
        if self._sleep_mode:
            return  # Silent in sleep mode

        if self.post:
            self.post.route(topic, payload)

    def record_subscription(self, topic: str):
        """Track subscriptions for diagnostic ping responses."""
        if topic not in self._diagnostic_subscriptions:
            self._diagnostic_subscriptions.append(topic)

    def mark_heartbeat_wired(self):
        """Mark that this fairy has heartbeat wiring (for diagnostics)."""
        self._has_heartbeat_wiring = True

    # =========================================================================
    # CHEMICAL SEDATION METHODS (v0.2.1 - Biological Sleep Model)
    # =========================================================================
    # Models induced sleep like anesthesia. Sedation level decreases through
    # boot phases, enabling gradual awakening with dream processing ability.
    # =========================================================================

    def _on_phase_progress(self, packet: dict):
        """
        Handle boot.phase.complete - reduce sedation as phases progress.
        This enables gradual awakening through the boot sequence.
        """
        phase = packet.get("phase", "")
        plane = packet.get("plane", "")

        # Only reduce sedation if this phase affects our plane
        # Handle None ACTOR_PLANE (some fairies don't have plane assignment)
        my_plane = getattr(self, 'ACTOR_PLANE', None) or ""
        if my_plane and my_plane not in plane and plane != "":
            return

        reduction = self._phase_sedation_map.get(phase, 0.0)
        if reduction > 0:
            old_level = self._sedation_level
            self._sedation_level = max(0.0, self._sedation_level - reduction)
            self._boot_phase = phase.lower()

            # Check if we've crossed awareness threshold
            if old_level >= self._awareness_threshold > self._sedation_level:
                self._on_awareness_emerging()

            print(f"[{self.ACTOR_NAME}] Phase {phase}: sedation {old_level:.2f} -> {self._sedation_level:.2f}", flush=True)

    def _on_awareness_emerging(self):
        """
        Subclass hook - called when sedation drops below awareness threshold.
        Fairy can now process dreams and has partial awareness.
        """
        self._dream_activity = 0.5  # Can process dream content
        print(f"[{self.ACTOR_NAME}] Awareness emerging (sedation below {self._awareness_threshold})", flush=True)

    def reduce_sedation(self, amount: float):
        """
        Manually reduce sedation level (for custom wake behaviors).
        """
        old_level = self._sedation_level
        self._sedation_level = max(0.0, self._sedation_level - amount)

        if old_level >= self._awareness_threshold > self._sedation_level:
            self._on_awareness_emerging()

    def clear_sedation(self):
        """
        Clear all sedation - called by sunrise for full awakening.
        """
        self._sedation_level = 0.0
        self._dream_activity = 0.0  # No more dream processing needed
        self._sedation_chemical = "cleared"

    @property
    def status(self) -> str:
        """Current fairy status string."""
        return self._boot_phase or "unknown"

    @property
    def state(self):
        """
        Current fairy state as FairyState enum.

        Maps _boot_phase string to FairyState enum for compatibility with
        code that expects .state.value pattern.
        """
        try:
            from .states import FairyState
            phase_map = {
                "pre_boot": FairyState.INITIALIZING,
                "booting": FairyState.BOOTING,
                "running": FairyState.RUNNING,
                "stopping": FairyState.STOPPING,
                "stopped": FairyState.STOPPED,
                "failed": FairyState.FAILED,
                "awake": FairyState.RUNNING,
                "drowsing": FairyState.DROWSY,
                "sleeping": FairyState.SLEEPING,
                "dreaming": FairyState.DREAMING,
                "waking": FairyState.WAKING,
            }
            return phase_map.get(self._boot_phase, FairyState.INITIALIZING)
        except ImportError:
            # Fallback: Return object with .value attribute
            class _FakeState:
                def __init__(self, value):
                    self.value = value
            return _FakeState(self._boot_phase or "unknown")

    @property
    def is_sedated(self) -> bool:
        """True if sedation level is above zero."""
        return self._sedation_level > 0.0

    @property
    def is_aware(self) -> bool:
        """True if sedation is below awareness threshold (can perceive)."""
        return self._sedation_level < self._awareness_threshold

    @property
    def can_dream(self) -> bool:
        """True if fairy can process dream content."""
        return self._dream_activity > 0.0

    def get_sedation_state(self) -> dict:
        """Get full sedation state for diagnostics."""
        return {
            "fairy": self.ACTOR_NAME,
            "sedation_level": self._sedation_level,
            "is_sedated": self.is_sedated,
            "is_aware": self.is_aware,
            "can_dream": self.can_dream,
            "chemical": self._sedation_chemical,
            "boot_phase": self._boot_phase,
        }

    def _register_with_directory(self):
        """Register with DirectoryFairy."""
        if not self.post:
            print(f"[{self.ACTOR_NAME}] WARNING: Cannot register - postal hub not available")
            return
        contract = self._contract_dict()

        # Try register_fairy method if available (UnifiedPostalHub has it)
        if hasattr(self.post, 'register_fairy'):
            self.post.register_fairy(contract)
            self._registered_with_directory = True
        # Otherwise publish directly to directory topic (TensorFabric)
        elif hasattr(self.post, 'publish'):
            self.post.publish("directory", {
                "opcode": "CONTRACT_UPSERT",
                "contract": contract
            })
            self._registered_with_directory = True
        # Log silently - registration is best-effort
        # print(f"[{self.ACTOR_NAME}] Registered with DirectoryFairy | ID: {self.fairy_id}")
    
    # =========================================================================
    # INFRASTRUCTURE WIRING (v0.1.2)
    # =========================================================================
    # THE SWITCH - Connect every fairy to infrastructure services.
    # This is what makes every fairy able to think with context.
    # =========================================================================
    
    def _wire_infrastructure(self):
        """
        Wire this fairy to infrastructure services.
        
        This is THE SWITCH that connects fairies to:
        - Heartbeat (tick clock)
        - Body (somatic state)
        - Affect (emotional state)
        - Memory (working memory context)
        - Goals (autonomy and goal scheduler)
        - Consciousness (collision stream)
        """
        wired = []
        
        # 1. HEARTBEAT - Two delivery paths for reliability:
        #    a) HeartbeatRegistry: Direct-call from CirculationPumpFairy (cannot drop)
        #    b) Postal heartbeat.pulse: Standard postal delivery (can drop under load)
        # Even fairies with NEEDS_HEARTBEAT=False must echo so they don't
        # appear dead. The NEEDS_HEARTBEAT flag only controls whether
        # on_heartbeat()/on_tick() fire for fairy-specific work.
        try:
            self.post.subscribe("heartbeat.pulse", self._on_heartbeat)
            wired.append("heartbeat")
        except Exception:
            pass
        # Register with HeartbeatRegistry for guaranteed direct-call liveness.
        # IMPORTANT: Registry callback is LIGHTWEIGHT — only updates _last_tick.
        # The FULL _on_heartbeat (echo, on_tick, thinking) runs via postal workers.
        # This split prevents 85 fairies' tick work running sequentially in the
        # heartbeat thread (which caused 132s pulse delivery in Feb 13 boot).
        # FIX 2026-02-20: Skip registration if this is a duplicate instance.
        # If _CITIZEN_OBJECTS has a different (ticking) instance, our callback
        # would overwrite the working one with a dead one.
        try:
            from consciousness.heartbeat_registry import get_heartbeat_registry
            _hb_reg = get_heartbeat_registry()
            if _hb_reg:
                _existing_citizen = _CITIZEN_OBJECTS.get(self.ACTOR_NAME)
                if _existing_citizen is not self and getattr(_existing_citizen, '_tick_count', 0) > 0:
                    pass  # Don't overwrite a ticking callback with our (duplicate) one
                else:
                    _hb_reg.register(self.ACTOR_NAME, self._on_registry_pulse)
        except Exception:
            pass  # Registry not available yet during early boot — postal is backup

        # 1b. CIRCADIAN - The slow rhythm (time-of-day phases)
        if self.NEEDS_CIRCADIAN:
            try:
                self.post.subscribe("circadian.phase_change", self._on_circadian)
                self.post.subscribe("circadian.state", self._on_circadian_state)
                wired.append("circadian")
            except Exception:
                pass

        # 2. BODY - Somatic state
        if self.NEEDS_BODY:
            try:
                self.post.subscribe("somatic.state", self._on_somatic)
                self._somatic = self.post.get_provider("somatic.state")
                if self._somatic:
                    wired.append("body")
            except Exception:
                pass
        
        # 3. AFFECT - Emotional state
        if self.NEEDS_AFFECT:
            try:
                self.post.subscribe("affect.changed", self._on_affect)
                self._affect = self.post.get_provider("affect.state")
                if self._affect:
                    wired.append("affect")
            except Exception:
                pass
        
        # 4. MEMORY - Working memory for context
        if self.NEEDS_MEMORY:
            try:
                self.post.subscribe("memory.working.tracer", self._on_tracer)
                self._working_memory = self.post.get_provider("memory.working")
                if self._working_memory:
                    wired.append("memory")
            except Exception:
                pass
        
        # 5. GOALS - Autonomy and goal scheduler
        if self.NEEDS_GOALS:
            try:
                self.post.subscribe("autonomy.goal", self._on_goal)
                self.post.subscribe("goal.nudge", self._on_nudge)
                self._autonomy = self.post.get_provider("autonomy")
                self._goal_scheduler = self.post.get_provider("goal.scheduler")
                if self._autonomy:
                    wired.append("goals")
            except Exception:
                pass
        
        # 6. CONSCIOUSNESS - Collision chamber
        if self.NEEDS_CONSCIOUSNESS:
            try:
                self.post.subscribe("consciousness.collision", self._on_consciousness_collision)
                self.post.subscribe("consciousness.thought", self._on_thought_received)
                wired.append("consciousness")
            except Exception:
                pass
        
        if wired:
            print(f"[{self.ACTOR_NAME}] Infrastructure wired: {', '.join(wired)}")

        # 7. DEFERRED WIRING - Retry connections after ignition
        # Some fairies boot before their providers register
        try:
            self.post.subscribe("system.ignition", self._retry_infrastructure_wiring)
        except Exception:
            pass

    def _retry_infrastructure_wiring(self, packet: dict):
        """
        Retry infrastructure wiring after system ignition.
        
        Called once when system.ignition fires - providers should be ready now.
        """
        rewired = []
        
        # Retry body connection
        if self.NEEDS_BODY and not getattr(self, '_somatic', None):
            self._somatic = self.post.get_provider("somatic.state")
            if self._somatic:
                rewired.append("body")
        
        # Retry memory connection
        if self.NEEDS_MEMORY and not getattr(self, '_working_memory', None):
            self._working_memory = self.post.get_provider("memory.working")
            if self._working_memory:
                rewired.append("memory")
        
        # Retry goals connection
        if self.NEEDS_GOALS and not getattr(self, '_autonomy', None):
            self._autonomy = self.post.get_provider("autonomy")
            self._goal_scheduler = self.post.get_provider("goal.scheduler")
            if self._autonomy:
                rewired.append("goals")
        
        if rewired:
            print(f"[{self.ACTOR_NAME}] Deferred wiring complete: {', '.join(rewired)}")
        
        # Unsubscribe - only need to run once
        try:
            self.post.unsubscribe("system.ignition", self._retry_infrastructure_wiring)
        except Exception:
            pass

    def _validate_wiring(self) -> dict:
        """
        Validate that this fairy is properly wired to infrastructure.

        Returns a dict with:
        - valid: bool - True if all required wiring is complete
        - missing: list - What's missing
        - warnings: list - Non-critical issues
        - score: float - 0.0-1.0 wiring completeness

        Called at end of on_boot to catch wiring problems early.
        """
        missing = []
        warnings = []

        # Check postal
        if not hasattr(self, 'post') or self.post is None:
            missing.append("postal")

        # Check ACTOR_NAME (required for sender tracking)
        if not getattr(self, 'ACTOR_NAME', None):
            missing.append("ACTOR_NAME")

        # Check infrastructure based on NEEDS_* flags
        if self.NEEDS_HEARTBEAT and not hasattr(self, '_tick_count'):
            warnings.append("heartbeat_not_ticking")

        if self.NEEDS_BODY and not getattr(self, '_somatic', None):
            warnings.append("body_not_connected")

        if self.NEEDS_AFFECT and not getattr(self, '_affect', None):
            warnings.append("affect_not_connected")

        if self.NEEDS_MEMORY and not getattr(self, '_working_memory', None):
            warnings.append("memory_not_connected")

        if self.NEEDS_GOALS and not getattr(self, '_autonomy', None):
            warnings.append("goals_not_connected")

        if self.NEEDS_CONSCIOUSNESS:
            # Check if we have consciousness handlers wired
            pass  # Subscriptions are harder to verify

        # Check directory registration
        if not getattr(self, '_registered_with_directory', False):
            warnings.append("not_registered_with_directory")

        # Calculate score
        total_checks = 2 + sum([
            self.NEEDS_HEARTBEAT,
            self.NEEDS_BODY,
            self.NEEDS_AFFECT,
            self.NEEDS_MEMORY,
            self.NEEDS_GOALS,
        ])
        issues = len(missing) + len(warnings)
        score = max(0.0, 1.0 - (issues / total_checks))

        result = {
            "valid": len(missing) == 0,
            "missing": missing,
            "warnings": warnings,
            "score": score,
            "actor": self.ACTOR_NAME,
        }

        # Log if there are issues
        if missing:
            print(f"[{self.ACTOR_NAME}] WIRING ERROR: Missing {missing}")
        if warnings:
            print(f"[{self.ACTOR_NAME}] Wiring warnings: {warnings}")

        return result

    # =========================================================================
    # INFRASTRUCTURE HANDLERS
    # =========================================================================
    
    def _send_heartbeat(self) -> None:
        """
        Send heartbeat echo back to DirectoryFairy via postal.

        SECONDARY SIGNAL (2026-02-09): The PRIMARY liveness mechanism is now
        direct object inspection — HeartbeatHandler checks _last_tick on our
        Python object in _CITIZEN_OBJECTS. This postal echo is a nice-to-have
        backup signal. If it fails, the fairy will NOT be declared dead.

        (2026-02-03: Added from DirectoryMixin - was missing in consolidation)
        (2026-02-09 early: Reversed priority order - postal first, fabric fallback.)
        (2026-02-09 late: Downgraded from CRITICAL to secondary. Direct object
         liveness check is now primary. Postal echo failure is no longer fatal.)
        """
        tick_count = getattr(self, '_tick_count', 0)
        # The heartbeat packet - DirectoryFairy expects name field!
        heartbeat_packet = {
            "name": self.ACTOR_NAME,
            "_sender": self.ACTOR_NAME,
            "status": "running",
            "beat": tick_count,
            "ts": time.time(),
        }
        # Strategy: Try multiple paths to ensure heartbeat reaches DirectoryFairy
        # Priority: self.post (most reliable) → self.fabric → SYSTEM.fabric
        sent = False

        # Way 1: SharedPostalHub (most reliable - ALL fairies have this)
        if hasattr(self, 'post') and self.post:
            try:
                self.post.publish("fairy.heartbeat", heartbeat_packet)
                sent = True
            except Exception:
                pass

        # Way 2: Use self.fabric if it's a TensorFabric (for OLD DirectoryFairy)
        if not sent and hasattr(self, 'fabric') and self.fabric:
            try:
                self.fabric.publish("fairy.heartbeat", heartbeat_packet)
                sent = True
            except Exception:
                pass

        # Way 3: Try to get TensorFabric from global SYSTEM
        if not sent:
            try:
                import sys
                if 'server' in sys.modules:
                    server_mod = sys.modules['server']
                    if hasattr(server_mod, 'SYSTEM') and hasattr(server_mod.SYSTEM, 'fabric'):
                        server_mod.SYSTEM.fabric.publish("fairy.heartbeat", heartbeat_packet)
                        sent = True
            except Exception:
                pass

        # Track heartbeat echo health (silent - no spam)
        if not hasattr(self, '_hb_echo_count'):
            self._hb_echo_count = 0
            self._hb_echo_fails = 0
        if sent:
            self._hb_echo_count += 1
        else:
            self._hb_echo_fails += 1
            # Postal echo is now SECONDARY (direct object check is primary)
            # Warn sparingly — first 3 then every 500, since this is no longer fatal
            if self._hb_echo_fails <= 3 or self._hb_echo_fails % 500 == 0:
                print(f"[{self.ACTOR_NAME}] heartbeat echo failed ({self._hb_echo_fails} total, {self._hb_echo_count} succeeded) [non-fatal: object liveness is primary]")

    def _on_registry_pulse(self, packet: dict):
        """LIGHTWEIGHT heartbeat callback for HeartbeatRegistry.

        ONLY updates _last_tick and _tick_count — the primary liveness signal.
        Does NOT echo, does NOT call on_tick(), does NOT run thinking.

        HeartbeatRegistry calls all 85+ callbacks SEQUENTIALLY in one thread.
        If we did heavy work here, one pulse would take 100+ seconds.
        The heavy work (_on_heartbeat) runs via postal's 16 workers concurrently.
        """
        self._tick_count += 1
        self._last_tick = time.time()

    def _on_heartbeat(self, packet: dict):
        """
        Called every heartbeat via POSTAL (~1 second, concurrent via 16 workers).

        Three responsibilities:
        1. Update _tick_count and _last_tick (PRIMARY liveness signal —
           checked directly by HeartbeatHandler via _CITIZEN_OBJECTS)
        2. Echo to DirectoryFairy via postal (SECONDARY signal — may fail
           without consequence since 2026-02-09 direct object check)
        3. If NEEDS_HEARTBEAT=True, fire on_heartbeat()/on_tick() for work

        Respects HEARTBEAT_DIVISOR for tempo control:
        - DIVISOR=1: fires every beat (reflex, consciousness)
        - DIVISOR=4: fires every 4th beat (cognition, goals)
        - DIVISOR=8: fires every 8th beat (reflection, planning)
        """
        self._tick_count += 1
        self._last_tick = time.time()

        # SECONDARY: Send heartbeat echo back to DirectoryFairy via postal
        # The PRIMARY liveness signal is _last_tick above — HeartbeatHandler
        # reads it directly from our Python object in _CITIZEN_OBJECTS
        # FIX 2026-02-13b: Rate-limit to every 10th beat. Previously 105 fairies
        # echoed fairy.heartbeat EVERY beat → 105 msgs/beat → QUEUE FULL drops.
        if self._tick_count % 10 == 0:
            self._send_heartbeat()

        # Only do tick processing if this fairy needs heartbeat-driven work
        if not self.NEEDS_HEARTBEAT:
            return

        # Get beat number from packet or use tick count
        beat_number = packet.get("beat_number", self._tick_count)

        # Apply phase offset and check divisor
        adjusted_beat = beat_number - self.HEARTBEAT_PHASE
        should_fire = (adjusted_beat > 0 and
                       adjusted_beat % self.HEARTBEAT_DIVISOR == 0)

        if should_fire:
            # Call tempo-aware heartbeat handler
            try:
                self.on_heartbeat(beat_number, packet)
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] on_heartbeat error: {e}")

            # Call legacy tick handler (for backwards compatibility)
            try:
                self.on_tick(self._tick_count)  # FIX: was passing packet, should be tick count
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] on_tick error: {e}")

        # Maybe run autonomous thinking (still respects divisor)
        if should_fire and self._tick_count % 5 == 0:
            try:
                self._maybe_think()
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] _maybe_think error: {e}")

    def _on_circadian(self, packet: dict):
        """
        Circadian phase changed (morning -> afternoon, etc.).
        THE SLOW RHYTHM that governs energy, mood, activity levels.
        """
        phase = packet.get("phase", "unknown")
        try:
            self.on_circadian(phase, packet)
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] on_circadian error: {e}")

    def _on_circadian_state(self, packet: dict):
        """
        Periodic circadian state update.
        Carries current phase, hour, energy_level, chemistry modulation.
        """
        # Store for reference by other methods
        self._circadian_state = packet
        # Also trigger phase handler with full state
        phase = packet.get("phase", "unknown")
        try:
            self.on_circadian(phase, packet)
        except Exception:
            pass

    def _on_somatic(self, packet: dict):
        """Body state changed."""
        try:
            self.on_body(packet)
        except Exception:
            pass
    
    def _on_affect(self, packet: dict):
        """Emotional state changed."""
        try:
            self.on_affect(packet)
        except Exception:
            pass
    
    def _on_goal(self, packet: dict):
        """Goal state changed."""
        try:
            self.on_goal(packet)
        except Exception:
            pass
    
    def _on_nudge(self, packet: dict):
        """Received a nudge to work on something."""
        try:
            self.on_nudge(packet)
        except Exception:
            pass
    
    def _on_tracer(self, packet: dict):
        """Working memory tracer received."""
        try:
            self.on_tracer(packet)
        except Exception:
            pass
    
    def _on_consciousness_collision(self, packet: dict):
        """Consciousness collision occurred."""
        try:
            self.on_consciousness_collision(packet)
        except Exception:
            pass
    
    def _on_thought_received(self, packet: dict):
        """Another fairy's thought came through."""
        try:
            self.on_thought_received(packet)
        except Exception:
            pass
    
    # =========================================================================
    # INFRASTRUCTURE ACCESS METHODS
    # =========================================================================
    
    def get_context(self, topic: str = "general") -> dict:
        """
        Get context from working memory for thinking.
        
        Returns recent tracers, patterns, and associations
        relevant to the given topic.
        """
        if self._working_memory:
            try:
                if hasattr(self._working_memory, "get_context_for"):
                    return self._working_memory.get_context_for(topic)
                elif hasattr(self._working_memory, "get_context"):
                    return self._working_memory.get_context(topic)
            except Exception:
                pass
        return {"tracers": [], "patterns": [], "goals": []}
    
    def emit_thought(self, content: str, thought_type: str = "reflective"):
        """
        Emit a thought into the consciousness stream.

        1. Submits to working memory as tracer
        2. Routes to consciousness.thought for other fairies
        3. Routes to fairy.activity for AssociationCortex binding
        """
        ts = time.time()

        # Submit to working memory
        if self._working_memory:
            try:
                if hasattr(self._working_memory, "submit_tracer"):
                    self._working_memory.submit_tracer(
                        content=content,
                        source=self.ACTOR_NAME,
                        loop=thought_type,
                    )
            except Exception:
                pass

        # Route to consciousness stream
        self.post.route("consciousness.thought", {
            "source": self.ACTOR_NAME,
            "content": content,
            "type": thought_type,
            "ts": ts,
        })

        # Route to fairy.activity for AssociationCortex binding
        # This allows multi-modal binding of fairy actions into concepts
        try:
            self.post.route("fairy.activity", {
                "actor": self.ACTOR_NAME,
                "plane": getattr(self, "ACTOR_PLANE", "P00"),
                "activity_type": thought_type,
                "content_preview": content[:200] if isinstance(content, str) else str(content)[:200],
                "ts": ts,
            })
        except Exception:
            pass
    
    def get_body_state(self) -> dict:
        """Get current somatic/body state."""
        if self._somatic:
            try:
                if hasattr(self._somatic, "get_state"):
                    return self._somatic.get_state()
            except Exception:
                pass
        return {}
    
    def get_affect_state(self) -> dict:
        """Get current emotional state."""
        if self._affect:
            try:
                if hasattr(self._affect, "get_state"):
                    return self._affect.get_state()
            except Exception:
                pass
        return {"valence": 0.5, "arousal": 0.5}
    
    def get_goals(self) -> list:
        """Get active goals."""
        if self._autonomy:
            try:
                if hasattr(self._autonomy, "get_active_goals"):
                    return self._autonomy.get_active_goals()
            except Exception:
                pass
        return []
    
    def get_drives(self) -> dict:
        """Get current drive states."""
        if self._autonomy:
            try:
                if hasattr(self._autonomy, "get_drives"):
                    return self._autonomy.get_drives()
            except Exception:
                pass
        return {}
    
    def create_goal(self, name: str, description: str, priority: float = 0.5):
        """Create a new goal."""
        self.post.route("goal.scheduler.inject", {
            "name": name,
            "description": description,
            "priority": priority,
            "source": self.ACTOR_NAME,
        })
    
    def inject_feeling(self, emotion: str, intensity: float = 0.5):
        """Cause a feeling in the body."""
        self.post.route("somatic.inject", {
            "emotion": emotion,
            "intensity": intensity,
            "source": self.ACTOR_NAME,
        })

    # =========================================================================
    # SYSTEM PROMPT - Drive & Identity
    # =========================================================================

    def _load_system_prompt(self) -> str:
        """
        Load evolved prompt from file, or fall back to bootstrap.

        Priority:
        1. Directive ring (Claude_Office/directive_rings/{actor_name}.directive)
        2. Evolved prompt (Claude_Office/fairy_prompts/{actor_name}.md)
        3. Bootstrap fallback
        """
        if self._prompt_loaded and self._system_prompt:
            return self._system_prompt

        # ═══ PRIORITY 1: Try directive ring (identity + purpose + personality) ═══
        directive_path = os.path.join(
            self.root,
            "Claude_Office", "directive_rings", f"{self.ACTOR_NAME}.directive"
        )
        # DEBUG: Show path being checked
        directive_exists = os.path.exists(directive_path)
        if not directive_exists and self.ACTOR_NAME in ["BootFairy.Karla", "UnconsciousMindFairy", "ConsciousnessLoopFairy"]:
            print(f"[{self.ACTOR_NAME}] DEBUG: directive_path={directive_path}, exists={directive_exists}, root={self.root}")
        if directive_exists:
            try:
                with open(directive_path, 'r', encoding='utf-8') as f:
                    self._system_prompt = f.read()
                    self._prompt_loaded = True
                    print(f"[{self.ACTOR_NAME}] Directive ring LOADED - identity engaged!")
                    return self._system_prompt
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Failed to load directive ring: {e}")

        # ═══ PRIORITY 2: Try evolved prompt ═══
        prompt_path = os.path.join(
            self.root,
            self.PROMPT_PATH.format(actor_name=self.ACTOR_NAME)
        )

        if os.path.exists(prompt_path):
            try:
                with open(prompt_path, 'r', encoding='utf-8') as f:
                    self._system_prompt = f.read()
                    self._prompt_loaded = True
                    return self._system_prompt
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Failed to load evolved prompt: {e}")

        # Fall back to bootstrap - create seed prompt from fairy's identity
        self._system_prompt = self.BOOTSTRAP_PROMPT.format(
            ACTOR_NAME=self.ACTOR_NAME,
            PURPOSE=self.PURPOSE,
            MANTRA=self.MANTRA,
        )
        self._prompt_loaded = True

        # Save bootstrap as seed prompt so it can evolve
        # BUT: Only if fairy doesn't have BASIC_PROMPT (PromptAwareMixin manages those)
        # PromptAwareMixin has richer fairy-specific prompts - don't overwrite with generic!
        has_prompt_mixin = hasattr(self, 'BASIC_PROMPT') and self.BASIC_PROMPT
        if not has_prompt_mixin:
            try:
                os.makedirs(os.path.dirname(prompt_path), exist_ok=True)
                with open(prompt_path, 'w', encoding='utf-8') as f:
                    f.write(self._system_prompt)
                print(f"[{self.ACTOR_NAME}] 🌱 Created seed prompt from bootstrap")
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Failed to save seed prompt: {e}")
        else:
            print(f"[{self.ACTOR_NAME}] Has BASIC_PROMPT - PromptAwareMixin will manage prompt")

        return self._system_prompt

    def _save_evolved_prompt(self, new_prompt: str = None):
        """
        Save current prompt to file for persistence across reboots.

        Called when:
        - Learning threshold reached (_learnings_since_save > 10)
        - Circadian night phase (consolidation)
        - Explicit request

        NOTE: If fairy has BASIC_PROMPT, PromptAwareMixin manages the prompt file.
        We should NOT write unless a file already exists (meaning PromptAwareMixin wrote it).
        """
        prompt_to_save = new_prompt or self._system_prompt
        if not prompt_to_save:
            return False

        prompt_path = os.path.join(
            self.root,
            self.PROMPT_PATH.format(actor_name=self.ACTOR_NAME)
        )

        # If fairy has BASIC_PROMPT, defer to PromptAwareMixin for prompt management
        # Only save if file already exists (PromptAwareMixin created it)
        has_prompt_mixin = hasattr(self, 'BASIC_PROMPT') and self.BASIC_PROMPT
        if has_prompt_mixin and not os.path.exists(prompt_path):
            # PromptAwareMixin should create the file first - don't interfere
            return False

        try:
            os.makedirs(os.path.dirname(prompt_path), exist_ok=True)
            with open(prompt_path, 'w', encoding='utf-8') as f:
                f.write(prompt_to_save)
            self._learnings_since_save = 0
            return True
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Failed to save evolved prompt: {e}")
            return False

    def _build_thinking_context(self) -> dict:
        """
        Build the full context for thinking.

        Combines:
        - System prompt (identity + drives)
        - Current body state (somatic awareness)
        - Recent observations (what I've seen)
        - Goals (what I'm working toward)
        - Circadian phase (time-of-day awareness)
        """
        return {
            "system_prompt": self._load_system_prompt(),
            "actor_name": self.ACTOR_NAME,
            "purpose": self.PURPOSE,
            "mantra": self.MANTRA,
            "body_state": self.get_body_state(),
            "affect_state": self.get_affect_state(),
            "goals": self.get_goals(),
            "circadian_phase": self._circadian_phase,
            "tick_count": self._tick_count,
            "recent_observations": list(self._observations)[-5:],
            "recent_learnings": list(self._learnings)[-5:],
        }

    def record_learning(self, learning: str, category: str = "general"):
        """
        Record something learned for prompt evolution.

        Args:
            learning: What was learned
            category: Type (pattern, success, failure, insight)
        """
        self._learnings.append({
            "content": learning,
            "category": category,
            "timestamp": time.time(),
            "tick": self._tick_count,
        })
        self._learnings_since_save += 1

        # Also notify FairyTeacher for world-level profile tracking
        self._notify_fairy_teacher(learning, category)

        # Auto-save if threshold reached
        if self._learnings_since_save >= 10:
            self._maybe_evolve_prompt()

    def _notify_fairy_teacher(self, concept: str, category: str = "general"):
        """Notify FairyTeacher of learning (for world-level profiles)."""
        try:
            from P30_Cognition.cognition.fairy_world_foundation import get_fairy_teacher
            teacher = get_fairy_teacher()
            if teacher:
                # Map category to success/failure
                success = category not in ("failure", "error", "mistake")
                teacher.record_learning(self.ACTOR_NAME, concept, success, category)
        except Exception:
            pass  # FairyTeacher not available - that's OK

    def _maybe_evolve_prompt(self):
        """
        Consider evolving the prompt based on learnings.

        This is where the fairy's growth happens:
        - Patterns that work get reinforced
        - Failures get noted to avoid
        - New insights get incorporated

        For now: Just append learnings to the prompt.
        Future: Use LLM to synthesize a refined prompt.
        """
        if not self._learnings:
            return

        current_prompt = self._load_system_prompt()

        # Simple evolution: append recent learnings
        learnings_section = "\n## Recent Learnings\n"
        for learning in list(self._learnings)[-10:]:
            learnings_section += f"- [{learning['category']}] {learning['content']}\n"

        # Check if we already have a learnings section
        if "## Recent Learnings" in current_prompt:
            # Replace it
            parts = current_prompt.split("## Recent Learnings")
            evolved_prompt = parts[0] + learnings_section
        else:
            # Append it
            evolved_prompt = current_prompt + "\n" + learnings_section

        self._system_prompt = evolved_prompt
        self._save_evolved_prompt()

    # =========================================================================
    # THE THINKING LOOP
    # =========================================================================
    
    def _maybe_think(self):
        """
        Autonomous thinking - called periodically from heartbeat.

        1. Check if we should think this cycle
        2. Build full thinking context (prompt + state)
        3. Think (subclass implements, or use default)
        4. Emit result
        5. Record any learnings
        """
        # Only think every 20th tick unless we have goals
        goals = self.get_goals()
        if not goals and self._tick_count % 20 != 0:
            return

        # Build full thinking context with system prompt
        context = self._build_thinking_context()

        # Call subclass thinking (or default)
        try:
            thought = self.autonomous_think(context)
            if thought:
                self.emit_thought(thought)
                # Record that we generated a thought (for evolution)
                self._observations.append({
                    "type": "thought_generated",
                    "content": thought[:100],  # First 100 chars
                    "tick": self._tick_count,
                    "timestamp": time.time(),
                })
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] autonomous_think error: {e}")
    
    def process_input(self, input_content: str, topic: str = "general") -> Optional[str]:
        """
        Standard input processing loop.
        
        1. Get context from working memory
        2. Think (process input + context)
        3. Emit output
        """
        context = self.get_context(topic)
        output = self.think(input_content, context)
        if output:
            self.emit_thought(output)
        return output
    
    # =========================================================================
    # SUBCLASS OVERRIDE POINTS
    # =========================================================================
    
    def on_tick(self, packet: dict):
        """Override: Called on heartbeat (legacy - prefer on_heartbeat)."""
        pass

    def on_heartbeat(self, beat_number: int, pulse_data: dict):
        """
        Override: Called on heartbeat at this fairy's tempo.

        This is the "do your job" signal. The fairy wakes up and does
        whatever periodic work it needs to do. No context needed -
        the fairy knows what it should be doing.

        Args:
            beat_number: Which beat this is (monotonic counter)
            pulse_data: Blood state, chemistry, etc. (somatic awareness)

        Example:
            class MyFairy(MyOrganFairy):
                HEARTBEAT_DIVISOR = 4  # Fire every 4th beat

                def on_heartbeat(self, beat_number, pulse_data):
                    # Check my queue, process pending work, etc.
                    self._process_my_queue()
        """
        pass

    def on_circadian(self, phase: str, state: dict):
        """
        Override: Called when circadian phase changes.

        The slow rhythm of the system - time of day awareness.
        Use this for behaviors that should vary by "time":
        - Morning: fresh start, high energy
        - Afternoon: productive work
        - Evening: wind down, consolidate
        - Night: deep processing, dreams

        Args:
            phase: Current phase (morning, afternoon, evening, night)
            state: Full circadian state (hour, energy_level, etc.)
        """
        pass

    def on_body(self, packet: dict):
        """Override: Called when body state changes."""
        pass
    
    def on_affect(self, packet: dict):
        """Override: Called when emotional state changes."""
        pass
    
    def on_goal(self, packet: dict):
        """Override: Called when goal state changes."""
        pass
    
    def on_nudge(self, packet: dict):
        """Override: Called when nudged to work on something."""
        pass
    
    def on_tracer(self, packet: dict):
        """Override: Called when working memory tracer received."""
        pass
    
    def on_consciousness_collision(self, packet: dict):
        """Override: Called when consciousness collision occurs."""
        pass
    
    def on_thought_received(self, packet: dict):
        """Override: Called when another fairy's thought arrives."""
        pass
    
    def think(self, input_content: str, context: dict) -> Optional[str]:
        """
        Override: THE COGNITIVE FUNCTION.
        
        Given input and context, produce a new thought.
        This is where each fairy's unique intelligence lives.
        """
        return None
    
    def autonomous_think(self, context: dict) -> Optional[str]:
        """
        Override: Autonomous thinking during idle time.

        Called periodically when the system is idle.
        Use this for reflection, planning, exploration.

        Default behavior (if not overridden):
        - Check if there's something worth noting
        - Generate a simple observation about our domain
        - Record learnings from recent activity

        The context dict contains:
        - system_prompt: Our identity and drives
        - body_state, affect_state: How we feel
        - goals: What we're working toward
        - recent_observations, recent_learnings: What we've seen
        """
        # Default: Simple pattern-based thinking
        # Subclasses can override for more sophisticated thinking

        # Check if we have recent observations to reflect on
        recent = context.get("recent_observations", [])
        if recent and len(recent) >= 3:
            # We have enough observations - maybe notice a pattern
            return self._default_reflect_on_observations(recent)

        # Check if goals need attention
        goals = context.get("goals", [])
        if goals:
            return self._default_reflect_on_goals(goals)

        # Otherwise, stay quiet (no forced output)
        return None

    def _default_reflect_on_observations(self, observations: list) -> Optional[str]:
        """
        Default reflection: Look for patterns in recent observations.

        This is the BASE thinking - can be overridden.
        """
        if not observations:
            return None

        # Simple pattern: note what we've been seeing
        obs_types = [o.get("type", "unknown") for o in observations[-5:]]

        # Only speak if we notice something
        if len(set(obs_types)) == 1:
            # Same type repeated - a pattern!
            pattern = obs_types[0]
            self.record_learning(f"Noticing repeated {pattern} activity", "pattern")
            return f"[{self.ACTOR_NAME}] Pattern: {pattern} activity recurring"

        return None

    def _default_reflect_on_goals(self, goals: list) -> Optional[str]:
        """
        Default reflection: Think about goals.

        This is the BASE goal-thinking - can be overridden.
        """
        if not goals:
            return None

        # Just acknowledge we have goals (subclasses do real work)
        active_goals = [g for g in goals if g.get("status") == "active"]
        if active_goals:
            goal_names = [g.get("name", "unknown") for g in active_goals[:3]]
            return f"[{self.ACTOR_NAME}] Active goals: {', '.join(goal_names)}"

        return None


    def _pipe_to_working_memory(self):
        """
        Pipe this fairy into WorkingMemoryHub.
        
        This connects every fairy to the central working memory system:
        1. Registers fairy's tracer with working memory
        2. Subscribes to working memory context broadcasts
        3. Enables relational context tracking by tracer
        
        WorkingMemoryHub uses this to:
        - Track all fairy tracers in one place
        - Watch consciousness loop for relational context
        - Build tracking list for worker pool fan-out
        - Auto-register fairies with each other
        """
        try:
            # Get my tracer from postal hub
            my_contract = self.post.get_citizen(self.ACTOR_NAME) if hasattr(self.post, 'get_citizen') else {}
            my_contract = my_contract or {}
            my_tracer_id = my_contract.get("root_tracer_id", "")
            
            # Emit tracer registration to working memory
            self.post.send("memory.working.register", {
                "fairy_name": self.ACTOR_NAME,
                "fairy_id": my_contract.get("fairy_id", ""),
                "tracer_id": my_tracer_id,
                "plane": self.ACTOR_PLANE,
                "cluster_id": my_contract.get("srm_cluster_id", ""),
                "ts": time.time(),
            })
            
            # Subscribe to working memory context broadcasts
            def _on_working_memory_context(pkt):
                """Receive relational context from WorkingMemoryHub."""
                try:
                    # Store context for this fairy's use
                    self._working_memory_context = pkt.get("context", {})
                    self._working_memory_tracers = pkt.get("active_tracers", [])
                except Exception:
                    pass
            
            self.post.receive("memory.working.context", _on_working_memory_context)
            
            # Subscribe to tracer updates (when related tracers change)
            def _on_tracer_update(pkt):
                """Receive tracer updates for relational tracking."""
                try:
                    related_tracer = pkt.get("tracer_id")
                    if related_tracer and hasattr(self, "_related_tracers"):
                        self._related_tracers.add(related_tracer)
                except Exception:
                    pass
            
            self.post.receive("memory.working.tracer_update", _on_tracer_update)
            
            # Initialize tracking state
            self._working_memory_context = {}
            self._working_memory_tracers = []
            self._related_tracers = set()
            
        except Exception as e:
            # Working memory pipe is optional - don't fail boot
            pass

    def _on_census_request(self, pkt: dict):
        """Respond to directory census by re-registering."""
        try:
            self._register_with_directory()
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Census re-registration failed: {e}")


    def track_working_with(self, other_fairy: str, relationship: str = "working"):
        """
        Track that this fairy is working with another fairy.
        Uses the tracer system - no new infrastructure needed.
        """
        try:
            self.post.send("tracer.relationship", {
                "from_fairy": self.ACTOR_NAME,
                "to_fairy": other_fairy,
                "relationship": relationship,  # working, monitoring, helping
                "ts": time.time(),
            })
        except Exception:
            pass
    
    def track_monitoring(self, other_fairy: str):
        """Track that this fairy is monitoring another."""
        self.track_working_with(other_fairy, "monitoring")
    
    def track_helping(self, other_fairy: str):
        """Track that this fairy is helping another."""
        self.track_working_with(other_fairy, "helping")
    
    def get_my_tracer(self) -> str:
        """Get this fairy's root tracer ID."""
        try:
            if hasattr(self.post, 'get_citizen'):
                contract = self.post.get_citizen(self.ACTOR_NAME) or {}
                return contract.get("root_tracer_id", "")
        except Exception:
            pass
        return ""
    
    def spawn_work_tracer(self, work_name: str, work_type: str = "task") -> str:
        """Spawn a child tracer for a piece of work."""
        try:
            if hasattr(self.post, 'spawn_child_tracer'):
                tracer = self.post.spawn_child_tracer(
                    parent_tracer_id=self.get_my_tracer(),
                    content_type=work_type,
                    content_id=f"{self.ACTOR_NAME}_{work_name}_{int(time.time())}",
                    name=work_name
                )
                return tracer.get("id", "") if tracer else ""
        except Exception:
            pass
        return ""


    # ═══════════════════════════════════════════════════════════════════════════
    # MICRO-CONSCIOUSNESS - Each fairy's dual loop + collision chamber
    # ═══════════════════════════════════════════════════════════════════════════
    
    def think_reflective(self, thought: str, context: dict = None):
        """
        Emit a reflective thought (background processing).
        These are musings, considerations, what-ifs.
        """
        tracer_id = self.spawn_work_tracer(f"reflect_{int(time.time())}", "reflection")
        thought_obj = {
            "content": thought,
            "context": context or {},
            "tracer_id": tracer_id,
            "fairy": self.ACTOR_NAME,
        }
        self._reflective_loop.append(thought_obj)
        self._collision_chamber.emit_reflective(thought_obj)
        
        # Broadcast to working memory
        try:
            self.post.send("consciousness.reflective", {
                "fairy": self.ACTOR_NAME,
                "thought": thought,
                "tracer_id": tracer_id,
                "ts": time.time(),
            })
        except Exception:
            pass
        
        # Check for collision
        collision = self._collision_chamber.get_latest_collision()
        if collision and collision.get("ts", 0) > time.time() - 1.0:
            self._on_collision(collision)
        
        return tracer_id
    
    def think_reasoning(self, thought: str, context: dict = None):
        """
        Emit a reasoning thought (active processing).
        These are analysis, decisions, conclusions.
        """
        tracer_id = self.spawn_work_tracer(f"reason_{int(time.time())}", "reasoning")
        thought_obj = {
            "content": thought,
            "context": context or {},
            "tracer_id": tracer_id,
            "fairy": self.ACTOR_NAME,
        }
        self._reasoning_loop.append(thought_obj)
        self._collision_chamber.emit_reasoning(thought_obj)
        
        # Broadcast to working memory
        try:
            self.post.send("consciousness.reasoning", {
                "fairy": self.ACTOR_NAME,
                "thought": thought,
                "tracer_id": tracer_id,
                "ts": time.time(),
            })
        except Exception:
            pass
        
        # Check for collision
        collision = self._collision_chamber.get_latest_collision()
        if collision and collision.get("ts", 0) > time.time() - 1.0:
            self._on_collision(collision)
        
        return tracer_id
    
    def _on_collision(self, collision: dict):
        """
        Handle a consciousness collision - insight emerges!
        Override in subclasses for custom collision handling.
        """
        try:
            # Broadcast collision
            self.post.send("consciousness.collision", {
                "fairy": self.ACTOR_NAME,
                "collision": collision,
                "ts": time.time(),
            })
            
            # Track the relationship between the two thoughts
            ref_tracer = collision.get("reflective", {}).get("tracer_id", "")
            rea_tracer = collision.get("reasoning", {}).get("tracer_id", "")
            if ref_tracer and rea_tracer:
                self.track_working_with(self.ACTOR_NAME, "self_collision")
        except Exception:
            pass
    
    def submit_async(self, fn: Callable, *args, task_name: str = "", **kwargs) -> str:
        """
        Submit async work to the worker pool.
        Returns a task_id for tracking.
        """
        task_id = f"{self.ACTOR_NAME}_{task_name}_{int(time.time())}"
        tracer_id = self.spawn_work_tracer(task_name or "async_task", "async")
        
        def wrapped():
            try:
                result = fn(*args, **kwargs)
                # Broadcast completion
                self.post.send("worker.complete", {
                    "task_id": task_id,
                    "tracer_id": tracer_id,
                    "fairy": self.ACTOR_NAME,
                    "success": True,
                })
                return result
            except Exception as e:
                self.post.send("worker.failed", {
                    "task_id": task_id,
                    "tracer_id": tracer_id,
                    "fairy": self.ACTOR_NAME,
                    "error": str(e),
                })
                return None
        
        future = self._worker_pool.submit(wrapped)
        self._pending_futures[task_id] = {"future": future, "tracer_id": tracer_id}
        return task_id
    
    def get_async_result(self, task_id: str, timeout: float = None):
        """Get result of async task."""
        if task_id not in self._pending_futures:
            return None
        future = self._pending_futures[task_id]["future"]
        try:
            return future.result(timeout=timeout)
        except Exception:
            return None
    
    def get_my_collisions(self, limit: int = 10) -> list:
        """Get recent collisions from this fairy's chamber."""
        return list(self._collision_chamber.collisions)[-limit:]
    
    def get_reflective_context(self, limit: int = 5) -> list:
        """Get recent reflective thoughts for context."""
        return list(self._reflective_loop)[-limit:]
    
    def get_reasoning_context(self, limit: int = 5) -> list:
        """Get recent reasoning thoughts for context."""
        return list(self._reasoning_loop)[-limit:]


    def submit_to_cns(self, work_type: str, args: dict = None, priority: float = 0.5) -> str:
        """
        Submit work to CentralNervousFairy's worker pool.
        CNS coordinates all heavy work across the system.
        
        Returns tracer_id for tracking.
        """
        tracer_id = self.spawn_work_tracer(work_type, "cns_work")
        try:
            self.post.send("cns.submit_work", {
                "fairy": self.ACTOR_NAME,
                "tracer_id": tracer_id,
                "work_type": work_type,
                "args": args or {},
                "priority": priority,
            })
        except Exception:
            pass
        return tracer_id

    def _contract_dict(self) -> Dict[str, Any]:
        """Build contract dictionary for directory registration.

        Fifth Ring Protocol: Includes role and gate_id if the fairy declares them.
        Gates (Autonomy, Autopilot, Embodiment) have ACTOR_ROLE='gate' and a
        deterministic GATE_ID that is stable across boots for simplified lookup.
        """
        contract = {
            "actor_name": self.ACTOR_NAME,
            "actor_version": self.ACTOR_VERSION,
            "plane": self.ACTOR_PLANE,
            "channel": self.ACTOR_CHANNEL,
            "purpose": self.PURPOSE,
            "mantra": self.MANTRA,
            "lore": self.LORE,
            "fairy_id": self.fairy_id,
            "srm_cluster_id": self.srm_cluster_id,
            "intents": self._collect_intents(),
            "boot_time": self._boot_time,
            # Fifth Ring Protocol — role and deterministic gate_id
            "role": getattr(self, "ACTOR_ROLE", "worker"),
            "gate_id": getattr(self, "GATE_ID", None),
        }
        return contract
    
    def _collect_intents(self) -> List[str]:
        """Collect all _intent_* methods."""
        return sorted({
            m.replace("_intent_", "") 
            for m in dir(self) 
            if m.startswith("_intent_")
        })
    
    def _emit_blueprint(self):
        """Emit blueprint for tracking."""
        bp = self._contract_dict()
        self._bp_last_hash = _hash_blueprint(bp)
        self.send("blueprint.contract", {
            "actor": self.ACTOR_NAME,
            "blueprint": bp,
            "hash": self._bp_last_hash,
            "ts": time.time()
        })

    # ─────────────────────────────────────────────────────────────────────
    # POSTAL - Simple send/receive (handles both TensorFabric and UnifiedPostalHub)
    # ─────────────────────────────────────────────────────────────────────

    def send(self, topic: str, payload: dict = None):
        """Send to topic - handles both TensorFabric (publish) and UnifiedPostalHub (send)."""
        if hasattr(self.post, 'send'):
            return self.post.send(topic, payload)
        elif hasattr(self.post, 'publish'):
            return self.post.publish(topic, payload or {})
        return False

    def receive(self, topic: str, handler: Callable):
        """Subscribe to topic - handles both TensorFabric (subscribe) and UnifiedPostalHub (receive)."""
        if hasattr(self.post, 'receive'):
            return self.post.receive(topic, handler)
        elif hasattr(self.post, 'subscribe'):
            return self.post.subscribe(topic, handler, f"{self.ACTOR_NAME}-{topic}")
        return -1

    def to_DIRECTORY(self, opcode: str, payload: dict = None):
        """Legacy directory send."""
        if hasattr(self.post, 'to_DIRECTORY'):
            self.post.to_DIRECTORY(opcode, payload)
        else:
            self.send("directory", {"opcode": opcode, **(payload or {})})
    
    # ─────────────────────────────────────────────────────────────────────
    # LEARNING
    # ─────────────────────────────────────────────────────────────────────
    
    def observe(self, action: str, result: Any, context: dict = None) -> dict:
        """Record observation."""
        obs = {"action": action, "result": result, "context": context, "ts": time.time()}
        self._observations.append(obs)
        self._emit_thought("observation", {"type": "observation", "content": f"{action}: {str(result)[:100]}"})
        return obs
    
    def reflect(self, topic: str, insight: str) -> dict:
        """Record reflection."""
        ref = {"topic": topic, "insight": insight, "ts": time.time()}
        self._reflections.append(ref)
        self._emit_thought("reflective", {"type": "reflection", "content": f"{topic}: {insight[:100]}"})
        return ref
    
    # ─────────────────────────────────────────────────────────────────────
    # SHADOW MONITORING (Built-in)
    # ─────────────────────────────────────────────────────────────────────
    
    def _start_shadow(self):
        """Start shadow monitoring thread."""
        if self._shadow_thread and self._shadow_thread.is_alive():
            return
        self._shadow_stop = False
        self._shadow_thread = threading.Thread(
            target=self._shadow_loop, daemon=True, name=f"{self.ACTOR_NAME}.shadow"
        )
        self._shadow_thread.start()
    
    def _shadow_loop(self):
        """Shadow monitoring loop."""
        _TLS.lane = "shadow"
        while not self._shadow_stop:
            try:
                if self._awake_once_done:
                    self._shadow_check_health()
                    self._shadow_emit_heartbeat()
                    # Periodic autobiography emission
                    self._autobiography_counter += 1
                    if self._autobiography_counter >= self.AUTOBIOGRAPHY_DIVISOR:
                        self._autobiography_counter = 0
                        self.emit_autobiography()
            except Exception as e:
                _emit(self.ACTOR_NAME, "SHADOW_ERROR", "error", {"err": str(e)}, CHANNEL["TRACER"], lane="shadow")
            time.sleep(self.SHADOW_INTERVAL_SEC)
    
    def _shadow_check_health(self):
        """Run health checks."""
        self._health_issues = []
        if not self.post:
            self._health_issues.append("no_postal")
        if not self._awake_once_done:
            self._health_issues.append("not_booted")
        self._health_status = "healthy" if not self._health_issues else "degraded"
        self._last_health_check = time.time()
    
    def _shadow_emit_heartbeat(self):
        """Emit shadow heartbeat."""
        self.post.send("shadow.health", {
            "actor": self.ACTOR_NAME,
            "status": self._health_status,
            "issues": self._health_issues,
            "ts": self._last_health_check
        })

    # ─────────────────────────────────────────────────────────────────────
    # STATUS SHEET / AUTOBIOGRAPHY
    # ─────────────────────────────────────────────────────────────────────

    # Autobiography emission frequency - emit every N shadow cycles (default: every 10 = ~10 minutes)
    AUTOBIOGRAPHY_DIVISOR: int = 10
    _autobiography_counter: int = 0
    _last_autobiography_ts: float = 0.0

    def build_status_sheet(self) -> dict:
        """
        Build this fairy's status sheet (autobiography snapshot).

        If fairy_status_sheet is available, returns a rich AkashicFairyStatusSheet.
        Otherwise returns a basic dict with essential identity info.
        """
        global _statuslib

        # Try to get shadow for the status sheet
        shadow = getattr(self, "shadow", None)

        # If status sheet library is available, use it
        if _statuslib is not None and hasattr(_statuslib, "build_status_sheet_from_actor"):
            try:
                sheet = _statuslib.build_status_sheet_from_actor(self, shadow=shadow)
                # Convert to dict if it's a dataclass
                if hasattr(sheet, "to_dict"):
                    return sheet.to_dict()
                return sheet
            except Exception as e:
                # Fall through to basic sheet
                pass

        # Fallback: basic status sheet dict
        return {
            "core": {
                "actor_name": self.ACTOR_NAME,
                "actor_version": getattr(self, "ACTOR_VERSION", "0.0.0"),
                "actor_plane": getattr(self, "ACTOR_PLANE", None),
                "actor_channel": getattr(self, "ACTOR_CHANNEL", "organ"),
                "purpose": getattr(self, "PURPOSE", ""),
                "mantra": getattr(self, "MANTRA", ""),
                "lore": getattr(self, "LORE", ""),
            },
            "shadow": {
                "state": self._health_status,
                "last_heartbeat_ts": self._last_health_check,
            },
            "somatic": {
                "energy_level": getattr(self, "_somatic_energy", 0.5),
            },
            "affect": {
                "mood": getattr(self, "_affect_mood", "neutral"),
                "valence": getattr(self, "_affect_valence", 0.0),
            },
            "ts": time.time(),
            "version": "0.1.0",
        }

    def emit_autobiography(self, force: bool = False) -> bool:
        """
        Emit this fairy's autobiography (status sheet) to the postal system.

        This allows ForensicScribeFairy and AkashicRecordsLibrarianFairy to
        capture and store the fairy's autobiographical snapshot.

        Args:
            force: If True, emit even if within cooldown period

        Returns:
            True if emitted, False if skipped
        """
        now = time.time()

        # Check cooldown (don't spam - minimum 60 seconds between emissions)
        if not force and (now - self._last_autobiography_ts) < 60.0:
            return False

        try:
            sheet = self.build_status_sheet()

            # Emit to fairy.autobiography topic
            if self.post:
                self.post.send("fairy.autobiography", {
                    "opcode": "FAIRY_STATUS_SHEET",
                    "actor": self.ACTOR_NAME,
                    "sheet": sheet,
                    "ts": now,
                })
                self._last_autobiography_ts = now
                return True
        except Exception:
            pass

        return False

    def _intent_status_sheet(self, payload: dict) -> dict:
        """
        Intent: Return this fairy's status sheet.

        This is called by ForensicScribeFairy or AkashicRecordsLibrarianFairy
        to request the current status sheet on demand.
        """
        sheet = self.build_status_sheet()
        return sheet  # Return directly, not wrapped

    # ─────────────────────────────────────────────────────────────────────
    # INTENT DISPATCH
    # ─────────────────────────────────────────────────────────────────────
    
    def use_intent(self, intent: str, payload: dict = None) -> dict:
        """Execute intent method."""
        method = getattr(self, f"_intent_{intent}", None)
        if callable(method):
            return method(payload or {})
        return {"ok": False, "error": f"unknown intent: {intent}"}
    
    # ─────────────────────────────────────────────────────────────────────
    # TESTS
    # ─────────────────────────────────────────────────────────────────────
    
    def _test_integrity(self) -> bool:
        return bool(self.ACTOR_NAME and self.ACTOR_VERSION)
    
    def _test_codex_link(self) -> bool:
        return True
    
    def _test_channel_signal(self) -> bool:
        return self.post is not None
    
    def shadow_tests(self) -> List[Callable]:
        """Return test functions for shadow."""
        return [
            lambda: {"name": "integrity", "status": "ok" if self._test_integrity() else "warn"},
            lambda: {"name": "postal", "status": "ok" if self._test_channel_signal() else "warn"}
        ]


# ==============================================================================
# BACKWARD COMPATIBILITY ALIASES
# ==============================================================================

# MyOrganFairy is now MyFairy
MyOrganFairy = MyFairy
OrganFairy = MyFairy

# MyOrganShadow is embedded in MyFairy, but we provide a stub for compatibility
class MyOrganShadow:
    """Legacy stub - shadow is now built into MyFairy."""
    def __init__(self, actor=None, interval_sec=60.0):
        self.actor = actor
        self.interval_sec = interval_sec
        self.health = 1.0
        self.status = "embedded"

# OrganHubFairy is now get_postal_hub()
class OrganHubFairy:
    """Legacy stub - use get_postal_hub() instead."""
    _instance = None
    
    @classmethod
    def shared(cls):
        return get_postal_hub()

# TemplateSeedFairy for auto-scanning (kept simple)
class TemplateSeedFairy(MyFairy):
    """Seed fairy for auto-scanning organ modules."""
    ACTOR_NAME = "TemplateSeedFairy"
    PURPOSE = "Seed for organ auto-discovery"


# ==============================================================================
# DIRECTORY SHIM (for compatibility)
# ==============================================================================

class _ShimDirectory:
    """Minimal directory shim."""
    def __init__(self):
        self.registry: Dict[str, Any] = {}
    
    def register(self, name: str, info: dict):
        self.registry[name] = info
    
    def lookup(self, name: str) -> Optional[dict]:
        return self.registry.get(name)

_DIR_SINGLETON = None

def _get_directory():
    global _DIR_SINGLETON
    if _DIR_SINGLETON is None:
        _DIR_SINGLETON = _ShimDirectory()
    return _DIR_SINGLETON




# ==============================================================================
# ORGAN HUB FACET - Legacy mixin for compatibility
# ==============================================================================

class OrganHubFacet:
    """
    Legacy mixin for organ-level actors.
    Now mostly handled by MyFairy, but kept for compatibility.
    """
    ROLE = "organ.facet.template"
    TITLE = "Registrar of Contracts"
    CLERK_NAME = "Primrose Ledgerkeep"
    EPITHET = "the Bureaucratic Moth"
    QUIP = "Every act witnessed; every contract stamped."
    CULTURE = "organ.template"
    ORGAN_LEVEL = True
    ACTOR_PLANE: Optional[str] = None
    ACTOR_CHANNEL: str = "organ"
    _WAKE_KEYS = {"WAKE", "WAKE_ALL", "AWAKEN", "WAKE_PLANE", "WAKE_COMPONENT"}
    
    def _init_hub(self):
        """Initialize hub - now delegates to postal hub with FairyPostal wrapper."""
        self.post = get_fairy_postal_bound(self)
    
    def _hub_identity_echo(self):
        """Echo identity to telemetry."""
        _emit(getattr(self, "ACTOR_NAME", "organ"), "FACET_READY", "ok",
              {"role": self.ROLE}, CHANNEL.get("TELEMETRY", "telemetry"))
    
    def _attach_wake_subscriptions(self):
        """Subscribe to wake waves."""
        if getattr(self, "_wake_subscribed", False):
            return
        if self.post:
            self.post.receive("plan", self._on_wake_packet)
            self.post.receive("directory", self._on_wake_packet)
        self._wake_subscribed = True
    
    def _on_wake_packet(self, packet: dict):
        """Handle wake packets."""
        cmd = str(packet.get("cmd", "")).upper()
        if cmd in self._WAKE_KEYS:
            # Wake handling - can be overridden
            pass


# ==============================================================================
# REGISTRATION LIB - Legacy registration helper
# ==============================================================================

class RegistrationLib:
    """
    Legacy registration utility. 
    Now mostly handled by UnifiedPostalHub.register_fairy().
    """
    DEFAULT_DOMAIN = "generic"
    DEFAULT_ROLE = "worker"
    DEFAULT_NAME = "worker"
    TEMPLATE_VERSION = "0.1.2"
    UPGRADE_CARDS = ["somatic", "memory", "cognition"]
    
    @staticmethod
    def register_actor(actor, *, domain: str = None, role: str = None, name: str = None):
        """Register an actor with DirectoryFairy."""
        hub = get_postal_hub()
        contract = {
            "actor_name": getattr(actor, "ACTOR_NAME", "unknown"),
            "actor_version": getattr(actor, "ACTOR_VERSION", "0.0.0"),
            "plane": getattr(actor, "ACTOR_PLANE", "P00"),
            "channel": getattr(actor, "ACTOR_CHANNEL", "organ"),
            "domain": domain or RegistrationLib.DEFAULT_DOMAIN,
            "role": role or RegistrationLib.DEFAULT_ROLE,
            "name": name or RegistrationLib.DEFAULT_NAME,
        }
        hub.register_fairy(contract)
        return contract
    
    @staticmethod
    def heartbeat(actor, *, status: str = "alive"):
        """Send heartbeat for actor."""
        hub = get_postal_hub()
        hub.send("shadow.health", {
            "actor": getattr(actor, "ACTOR_NAME", "unknown"),
            "status": status,
            "ts": time.time()
        })


# ==============================================================================
# TEMPLATE SHADOW FAIRY - Legacy shadow class for compatibility  
# ==============================================================================

class TemplateShadowFairy(MyOrganShadow):
    """
    Template shadow fairy for backwards compatibility.
    Extends the stub MyOrganShadow with additional shadow features.
    """
    SHADOW_NAME = "TemplateShadowFairy"
    SHADOW_VERSION = "0.1.2"
    
    def __init__(self, actor, interval_sec: float = 60.0):
        super().__init__(actor, interval_sec)
        self._last_health_ts = 0.0
        self._sim_count = 0
    
    def _loop(self):
        """Shadow monitoring loop."""
        while not getattr(self, "_stop", False):
            try:
                if getattr(self.actor, "_awake_once_done", False):
                    self._run_health_checks()
                    self._emit_heartbeat()
            except Exception:
                pass
            time.sleep(self.interval_sec)
    
    def _run_health_checks(self):
        """Run shadow health checks."""
        tests = []
        if hasattr(self.actor, "shadow_tests"):
            tests = list(self.actor.shadow_tests())
        for test in tests:
            try:
                if callable(test):
                    test()
            except Exception:
                pass
        self._last_health_ts = time.time()
    
    def _emit_heartbeat(self):
        """Emit shadow heartbeat."""
        hub = get_postal_hub()
        hub.send("shadow.health", {
            "actor": getattr(self.actor, "ACTOR_NAME", "unknown"),
            "status": "serene",
            "note": "shadow.heartbeat",
            "ts": time.time()
        })
    
    def start(self):
        """Start shadow thread."""
        self._stop = False
        _name = f"shadow-{getattr(self.actor, 'ACTOR_NAME', 'unknown')}"
        self._thread = threading.Thread(target=self._loop, daemon=True, name=_name)
        self._thread.start()

    def stop(self):
        """Stop shadow thread."""
        self._stop = True


# ==============================================================================
# HEARTBEAT WORKER - Legacy worker class
# ==============================================================================

class HeartbeatWorker:
    """Legacy heartbeat worker."""
    def __init__(self, actor, interval_sec: float = 30.0):
        self.actor = actor
        self.interval_sec = interval_sec
        self._stop = False
        self._thread = None

    def start(self):
        self._stop = False
        _name = f"hbw-{getattr(self.actor, 'ACTOR_NAME', 'unknown')}"
        self._thread = threading.Thread(target=self._loop, daemon=True, name=_name)
        self._thread.start()
    
    def stop(self):
        self._stop = True
    
    def _loop(self):
        while not self._stop:
            try:
                hub = get_postal_hub()
                hub.send("telemetry.heartbeat", {
                    "actor": getattr(self.actor, "ACTOR_NAME", "unknown"),
                    "ts": time.time()
                })
            except Exception:
                pass
            time.sleep(self.interval_sec)


# ==============================================================================
# ACTOR SHADOW FAIRY - Base class stub  
# ==============================================================================

class ActorShadowFairy:
    """Base shadow fairy stub."""
    def __init__(self, actor, interval_sec: float = 60.0):
        self.actor = actor
        self.interval_sec = interval_sec


# ==============================================================================
# TRACED OPERATION - Context manager for tracing (2026-02-02)
# ==============================================================================
# Moved here from base.py to avoid circular imports

class TracedOperation:
    """Context manager for traced operations."""

    def __init__(self, fairy, intent: str):
        self.fairy = fairy
        self.intent = intent
        self.tracer = None

    def __enter__(self):
        if hasattr(self.fairy, 'create_tracer'):
            self.tracer = self.fairy.create_tracer(self.intent)
            if hasattr(self.fairy, 'start_tracer'):
                self.fairy.start_tracer(self.tracer)
        return self.tracer

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.tracer:
            if exc_type:
                if hasattr(self.fairy, 'fail_tracer'):
                    self.fairy.fail_tracer(self.tracer, str(exc_val))
            else:
                if hasattr(self.fairy, 'complete_tracer'):
                    self.fairy.complete_tracer(self.tracer)
        return False  # Don't suppress exceptions


# ==============================================================================
# MODULE EXPORTS
# ==============================================================================

__all__ = [
    # Core classes
    "MyFairy",
    "MyOrganFairy",
    "MyOrganShadow",
    "OrganFairy",
    "OrganHubFairy",
    "TemplateSeedFairy",
    "UnifiedPostalHub",
    "MiniCollisionChamber",
    "TracedOperation",
    
    # Legacy compatibility classes
    "OrganHubFacet",
    "RegistrationLib",
    "TemplateShadowFairy",
    "HeartbeatWorker",
    "ActorShadowFairy",
    
    # Functions
    "get_postal_hub",
    "_get_shared_postal_hub",
    "_create_shared_shim_post",
    "_get_consciousness_loop",
    "_get_directory",
    "resolve_root",
    "_emit",
    "_hash_blueprint",
    "_now",
    
    # Mixins
    "CrossPlaneWiringMixin",
    "ConsciousnessParticipantMixin",
    
    # Constants
    "CHANNEL",
    "DIR_CHANNEL",
    "_CITIZEN_OBJECTS",
    "_TLS",
]

print(f"[Organ_Template] v0.1.8 TRACER WORKER POOLS + INFRASTRUCTURE WIRING loaded - {len(_CITIZEN_OBJECTS)} citizens")
