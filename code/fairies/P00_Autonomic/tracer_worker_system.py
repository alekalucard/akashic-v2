# ═══════════════════════════════════════════════════════════════════════════════
# TRACER WORKER SYSTEM - Universal Tracking + Async Processing
# ═══════════════════════════════════════════════════════════════════════════════
#
# "Reality is Consciousness. ((Cause + Affect) > Effect > Affect > ∞)"
#
# PHILOSOPHY:
# Every piece of work in the Akashic system gets a TRACER that tracks:
# - WHO created it (fairy_id)
# - WHAT goal/chain it serves
# - WHERE it came from (parent tracer)
# - WHEN it happened
# - HOW it progressed (status)
#
# Tracers enable:
# - Perfect recall of related items (cluster retrieval)
# - Full lineage tracking (what spawned what)
# - System-wide observability
# - Async parallel processing
#
# USAGE:
# Every fairy inherits TracerWorkerMixin (via Organ Template)
# Every action calls self.spawn_tracer() to create tracked work
# Worker pool handles async execution
#
# ═══════════════════════════════════════════════════════════════════════════════

from __future__ import annotations

import time
import uuid
import json
import threading
import traceback
from pathlib import Path
from concurrent.futures import Future
import queue as _queue_mod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable, Set, TYPE_CHECKING
from collections import deque
from enum import Enum

# Find project root for state file
_HERE = Path(__file__).resolve()
for _p in _HERE.parents:
    if (_p / "server.py").exists() or (_p / "ebookmain.py").exists():
        _PROJECT_ROOT = _p
        break
else:
    _PROJECT_ROOT = _HERE.parent.parent

_STATE_DIR = _PROJECT_ROOT / "state"
_TRACER_STATE_FILE = _STATE_DIR / "tracer_registry.json"


# ═══════════════════════════════════════════════════════════════════════════════
# TRACER TYPES
# ═══════════════════════════════════════════════════════════════════════════════

class TracerType(Enum):
    """Types of things that get traced."""
    # Fairy work
    FAIRY_WORK = "fairy_work"
    FAIRY_THOUGHT = "fairy_thought"
    FAIRY_REFLECTION = "fairy_reflection"
    FAIRY_DECISION = "fairy_decision"
    FAIRY_ACTION = "fairy_action"
    
    # Goals and chains
    GOAL = "goal"
    THOUGHT_CHAIN = "thought_chain"
    CHAIN_LINK = "chain_link"
    
    # Content
    FILE_SYSTEM = "file_system"
    FILE_USER = "file_user"
    MEDIA = "media"
    LITERATURE = "literature"
    CONVERSATION = "conversation"
    
    # System
    TELEMETRY = "telemetry"
    COLLISION = "collision"
    MEMORY_OPERATION = "memory_operation"


class TracerStatus(Enum):
    """Lifecycle status of a tracer."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# ═══════════════════════════════════════════════════════════════════════════════
# UNIVERSAL TRACER
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class UniversalTracer:
    """
    A tracer with full lineage tracking for ANYTHING in the system.
    
    Every piece of work should have a tracer that tells us:
    - WHO created it (fairy_id, fairy_name)
    - WHAT it's for (goal_id, chain_id, operation)
    - WHERE it came from (parent_tracer_id)
    - WHEN it happened (created_at, started_at, completed_at)
    - HOW it's doing (status, progress, result, error)
    
    Tracers form CLUSTERS - related tracers that can be recalled together.
    """
    # Identity
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    tracer_type: TracerType = TracerType.FAIRY_WORK
    
    # Lineage - WHO/WHAT/WHERE
    fairy_id: str = ""           # Which fairy created this
    fairy_name: str = ""         # Human readable name  
    chain_id: str = ""           # Which thought chain (if any)
    goal_id: str = ""            # Which goal (if any)
    parent_tracer_id: str = ""   # What spawned this (empty = root tracer)
    children_ids: List[str] = field(default_factory=list)
    
    # Cluster membership (for perfect recall)
    cluster_id: str = ""         # SRM cluster this belongs to
    related_cluster_ids: Set[str] = field(default_factory=set)
    
    # Content
    content: str = ""            # Human readable description
    operation: str = ""          # What operation is being performed
    payload: Dict[str, Any] = field(default_factory=dict)  # Arbitrary data
    
    # Lifecycle
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    ttl_sec: float = 300.0       # 5 minute default
    
    # Status
    status: TracerStatus = TracerStatus.PENDING
    progress: float = 0.0        # 0.0 to 1.0
    error: str = ""
    result: Any = None
    
    # Context
    context: Dict[str, Any] = field(default_factory=dict)
    tags: Set[str] = field(default_factory=set)
    priority: float = 0.5        # 0.0 = low, 1.0 = urgent
    
    def start(self) -> "UniversalTracer":
        """Mark tracer as started."""
        self.status = TracerStatus.RUNNING
        self.started_at = time.time()
        return self
    
    def complete(self, result: Any = None) -> "UniversalTracer":
        """Mark tracer as completed."""
        self.status = TracerStatus.COMPLETED
        self.completed_at = time.time()
        self.progress = 1.0
        self.result = result
        return self
    
    def fail(self, error: str) -> "UniversalTracer":
        """Mark tracer as failed."""
        self.status = TracerStatus.FAILED
        self.completed_at = time.time()
        self.error = error
        return self
    
    def update_progress(self, progress: float) -> "UniversalTracer":
        """Update progress (0.0 to 1.0)."""
        self.progress = max(0.0, min(1.0, progress))
        return self
    
    def add_child(self, child_id: str) -> "UniversalTracer":
        """Register a child tracer."""
        if child_id not in self.children_ids:
            self.children_ids.append(child_id)
        return self
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "tracer_type": self.tracer_type.value,
            "fairy_id": self.fairy_id,
            "fairy_name": self.fairy_name,
            "chain_id": self.chain_id,
            "goal_id": self.goal_id,
            "parent_tracer_id": self.parent_tracer_id,
            "children_ids": self.children_ids,
            "cluster_id": self.cluster_id,
            "related_cluster_ids": list(self.related_cluster_ids),
            "content": self.content,
            "operation": self.operation,
            "payload": self.payload,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "status": self.status.value,
            "progress": self.progress,
            "error": self.error,
            "tags": list(self.tags),
            "priority": self.priority,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UniversalTracer":
        """Create from dictionary."""
        tracer = cls(
            id=data.get("id", uuid.uuid4().hex[:12]),
            tracer_type=TracerType(data.get("tracer_type", "fairy_work")),
            fairy_id=data.get("fairy_id", ""),
            fairy_name=data.get("fairy_name", ""),
            chain_id=data.get("chain_id", ""),
            goal_id=data.get("goal_id", ""),
            parent_tracer_id=data.get("parent_tracer_id", ""),
            children_ids=data.get("children_ids", []),
            cluster_id=data.get("cluster_id", ""),
            related_cluster_ids=set(data.get("related_cluster_ids", [])),
            content=data.get("content", ""),
            operation=data.get("operation", ""),
            payload=data.get("payload", {}),
            created_at=data.get("created_at", time.time()),
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
            status=TracerStatus(data.get("status", "pending")),
            progress=data.get("progress", 0.0),
            error=data.get("error", ""),
            tags=set(data.get("tags", [])),
            priority=data.get("priority", 0.5),
        )
        return tracer


# ═══════════════════════════════════════════════════════════════════════════════
# TRACER REGISTRY - Global tracking of all active tracers
# ═══════════════════════════════════════════════════════════════════════════════

class TracerRegistry:
    """
    Global registry of all active tracers with PERSISTENCE.

    Enables:
    - Find all tracers for a fairy
    - Find all tracers for a goal/chain
    - Find all tracers in a cluster
    - Get lineage (parent → children)
    - SAVE/LOAD state across restarts (the memory that was missing!)
    """
    _instance: Optional["TracerRegistry"] = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._init()
        return cls._instance

    def _init(self):
        """Initialize registry and load saved state."""
        self._tracers: Dict[str, UniversalTracer] = {}
        self._by_fairy: Dict[str, List[str]] = {}  # fairy_id → [tracer_ids]
        self._by_cluster: Dict[str, List[str]] = {}  # cluster_id → [tracer_ids]
        self._by_chain: Dict[str, List[str]] = {}  # chain_id → [tracer_ids]
        self._by_goal: Dict[str, List[str]] = {}  # goal_id → [tracer_ids]
        self._lock = threading.Lock()
        self._dirty = False  # Track if state needs saving
        self._autosave_running = False
        self._max_tracers = 2000  # Hard cap — evict oldest beyond this
        self._cleanup_every = 50  # Run cleanup every N registrations
        self._register_count = 0  # Counter for periodic cleanup

        # Load saved state on init - THIS IS THE MEMORY!
        self._load_state()
        self._start_autosave()
    
    def register(self, tracer: UniversalTracer) -> UniversalTracer:
        """Register a new tracer."""
        with self._lock:
            self._tracers[tracer.id] = tracer

            # Index by fairy
            if tracer.fairy_id:
                self._by_fairy.setdefault(tracer.fairy_id, []).append(tracer.id)

            # Index by cluster
            if tracer.cluster_id:
                self._by_cluster.setdefault(tracer.cluster_id, []).append(tracer.id)

            # Index by chain
            if tracer.chain_id:
                self._by_chain.setdefault(tracer.chain_id, []).append(tracer.id)

            # Index by goal
            if tracer.goal_id:
                self._by_goal.setdefault(tracer.goal_id, []).append(tracer.id)

            # Link to parent
            if tracer.parent_tracer_id and tracer.parent_tracer_id in self._tracers:
                self._tracers[tracer.parent_tracer_id].add_child(tracer.id)

            # Mark for persistence when tracer completes
            self._dirty = True

            # Periodic cleanup: prune expired + enforce hard cap
            self._register_count += 1
            if self._register_count % self._cleanup_every == 0:
                self._cleanup_unlocked()

        return tracer

    def _cleanup_unlocked(self) -> int:
        """Prune expired tracers + enforce hard cap. Must hold _lock."""
        now = time.time()
        to_remove = []

        # 1. Remove expired completed/failed tracers
        for tid, tracer in self._tracers.items():
            if tracer.status in (TracerStatus.COMPLETED, TracerStatus.FAILED):
                completed_at = tracer.completed_at or tracer.created_at
                if now - completed_at > tracer.ttl_sec:
                    to_remove.append(tid)

        # 2. If still over cap, remove oldest completed/failed first
        if len(self._tracers) - len(to_remove) > self._max_tracers:
            remaining = [
                (tid, t) for tid, t in self._tracers.items()
                if tid not in set(to_remove) and t.status in (TracerStatus.COMPLETED, TracerStatus.FAILED)
            ]
            remaining.sort(key=lambda x: x[1].completed_at or x[1].created_at)
            overage = len(self._tracers) - len(to_remove) - self._max_tracers
            to_remove.extend(tid for tid, _ in remaining[:overage])

        # 3. Execute removal + clean indexes
        for tid in to_remove:
            tracer = self._tracers.pop(tid, None)
            if tracer:
                self._remove_from_indexes(tid, tracer)

        if to_remove:
            self._dirty = True

        return len(to_remove)

    def _remove_from_indexes(self, tid: str, tracer: UniversalTracer) -> None:
        """Remove a tracer ID from all index lists. Must hold _lock."""
        for idx_dict, key in (
            (self._by_fairy, tracer.fairy_id),
            (self._by_cluster, tracer.cluster_id),
            (self._by_chain, tracer.chain_id),
            (self._by_goal, tracer.goal_id),
        ):
            if key and key in idx_dict:
                lst = idx_dict[key]
                try:
                    lst.remove(tid)
                except ValueError:
                    pass
                if not lst:
                    del idx_dict[key]
    
    def get(self, tracer_id: str) -> Optional[UniversalTracer]:
        """Get a tracer by ID."""
        return self._tracers.get(tracer_id)
    
    def get_by_fairy(self, fairy_id: str) -> List[UniversalTracer]:
        """Get all tracers for a fairy."""
        ids = self._by_fairy.get(fairy_id, [])
        return [self._tracers[tid] for tid in ids if tid in self._tracers]
    
    def get_by_cluster(self, cluster_id: str) -> List[UniversalTracer]:
        """Get all tracers in a cluster - for PERFECT RECALL."""
        ids = self._by_cluster.get(cluster_id, [])
        return [self._tracers[tid] for tid in ids if tid in self._tracers]
    
    def get_by_chain(self, chain_id: str) -> List[UniversalTracer]:
        """Get all tracers for a thought chain."""
        ids = self._by_chain.get(chain_id, [])
        return [self._tracers[tid] for tid in ids if tid in self._tracers]
    
    def get_by_goal(self, goal_id: str) -> List[UniversalTracer]:
        """Get all tracers for a goal."""
        ids = self._by_goal.get(goal_id, [])
        return [self._tracers[tid] for tid in ids if tid in self._tracers]
    
    def get_children(self, tracer_id: str) -> List[UniversalTracer]:
        """Get all children of a tracer."""
        tracer = self.get(tracer_id)
        if not tracer:
            return []
        return [self._tracers[cid] for cid in tracer.children_ids if cid in self._tracers]
    
    def get_lineage(self, tracer_id: str) -> List[UniversalTracer]:
        """Get full lineage from root to this tracer."""
        lineage = []
        current_id = tracer_id
        while current_id:
            tracer = self.get(current_id)
            if not tracer:
                break
            lineage.insert(0, tracer)
            current_id = tracer.parent_tracer_id
        return lineage
    
    def cleanup_expired(self) -> int:
        """Remove expired tracers. Returns count removed."""
        with self._lock:
            return self._cleanup_unlocked()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get registry statistics."""
        status_counts = {}
        for tracer in self._tracers.values():
            status = tracer.status.value
            status_counts[status] = status_counts.get(status, 0) + 1

        return {
            "total_tracers": len(self._tracers),
            "fairies_tracked": len(self._by_fairy),
            "clusters_tracked": len(self._by_cluster),
            "chains_tracked": len(self._by_chain),
            "goals_tracked": len(self._by_goal),
            "by_status": status_counts,
        }

    # ═══════════════════════════════════════════════════════════════════════════
    # PERSISTENCE - The memory the system was missing!
    # ═══════════════════════════════════════════════════════════════════════════

    def _load_state(self):
        """Load saved tracer state from disk."""
        if not _TRACER_STATE_FILE.exists():
            print("[TracerRegistry] No saved state - starting fresh")
            return

        try:
            with open(_TRACER_STATE_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)

            loaded_count = 0
            for tracer_data in data.get("tracers", []):
                try:
                    tracer = UniversalTracer.from_dict(tracer_data)
                    # Only load completed/important tracers (skip expired)
                    if tracer.status == TracerStatus.COMPLETED:
                        age = time.time() - (tracer.completed_at or tracer.created_at)
                        # Keep completed tracers for 24 hours for recall
                        if age < 86400:
                            self._tracers[tracer.id] = tracer
                            self._index_tracer(tracer)
                            loaded_count += 1
                except Exception as e:
                    pass  # Skip malformed tracers

            print(f"[TracerRegistry] 💾 Loaded {loaded_count} tracers from memory")

        except Exception as e:
            print(f"[TracerRegistry] Failed to load state: {e}")

    def _index_tracer(self, tracer: UniversalTracer):
        """Add tracer to all indexes."""
        if tracer.fairy_id:
            self._by_fairy.setdefault(tracer.fairy_id, []).append(tracer.id)
        if tracer.cluster_id:
            self._by_cluster.setdefault(tracer.cluster_id, []).append(tracer.id)
        if tracer.chain_id:
            self._by_chain.setdefault(tracer.chain_id, []).append(tracer.id)
        if tracer.goal_id:
            self._by_goal.setdefault(tracer.goal_id, []).append(tracer.id)

    def _save_state(self):
        """Save current state to disk."""
        if not self._dirty:
            return

        try:
            _STATE_DIR.mkdir(parents=True, exist_ok=True)

            # Save completed tracers (the memory worth keeping)
            tracers_to_save = []
            now = time.time()
            for tracer in self._tracers.values():
                # Only save completed tracers younger than 24 hours
                if tracer.status == TracerStatus.COMPLETED:
                    age = now - (tracer.completed_at or tracer.created_at)
                    if age < 86400:
                        tracers_to_save.append(tracer.to_dict())

            data = {
                "saved_at": now,
                "count": len(tracers_to_save),
                "tracers": tracers_to_save,
            }

            with open(_TRACER_STATE_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, default=str)

            self._dirty = False
            print(f"[TracerRegistry] 💾 Saved {len(tracers_to_save)} tracers to memory")

        except Exception as e:
            print(f"[TracerRegistry] Save failed: {e}")

    def _start_autosave(self):
        """Start background autosave thread."""
        if self._autosave_running:
            return

        self._autosave_running = True

        def autosave_loop():
            while self._autosave_running:
                time.sleep(60)  # Save every minute
                # Always prune expired tracers — this was missing!
                pruned = self.cleanup_expired()
                if pruned:
                    print(f"[TracerRegistry] Pruned {pruned} expired tracers "
                          f"({len(self._tracers)} remaining)")
                if self._dirty:
                    self._save_state()
                # FIX 2026-03-04: Nudge GC every 60s. Python 3.14t free-threaded
                # mode doesn't run cyclic GC as aggressively — accumulated
                # Future/_WorkItem objects can linger. This is cheap (<1ms).
                try:
                    import gc
                    gc.collect(generation=0)  # Gen-0 only — fast
                except Exception:
                    pass

        thread = threading.Thread(target=autosave_loop, daemon=True, name="TracerAutosave")
        thread.start()

    def mark_dirty(self):
        """Mark that state needs saving."""
        self._dirty = True

    def force_save(self):
        """Force an immediate save."""
        self._dirty = True
        self._save_state()


def get_tracer_registry() -> TracerRegistry:
    """Get the global tracer registry singleton."""
    return TracerRegistry()


# ═══════════════════════════════════════════════════════════════════════════════
# QUEUE-BASED WORKER POOL (replaces ThreadPoolExecutor)
# ═══════════════════════════════════════════════════════════════════════════════
#
# FIX 2026-04-05 (Nous): ThreadPoolExecutor.submit() creates a Future object
# per call. Each Future allocates Condition + RLock + deque. Over 78 minutes:
# ~340K Future objects accumulate. Python 3.14t free-threaded GC doesn't
# collect the Condition/RLock cycles fast enough → 20GB RAM growth.
#
# Queue-based pool: ZERO per-submit allocations. Work goes on a queue,
# N daemon workers pull and execute. Same pattern as HeartbeatRegistry,
# ConsciousnessLoop, and CollisionChamber (all converted in March 2026).
#

class _SubmitSentinel:
    """Lightweight placeholder returned by QueueWorkerPool.submit().
    Replaces Future — callers only need a non-None value for dict tracking."""
    __slots__ = ('_done',)
    def __init__(self):
        self._done = False
    def done(self):
        return self._done


class QueueWorkerPool:
    """Drop-in replacement for ThreadPoolExecutor with zero per-submit allocation.

    FIX 2026-04-05 (Nous): Eliminates 340K+ Future/Condition/RLock objects
    that accumulate under Python 3.14t free-threading.
    """

    def __init__(self, max_workers: int = 24, thread_name_prefix: str = "fairy-work"):
        self._queue = _queue_mod.Queue(maxsize=4096)
        self._workers = []
        self._stop_flag = threading.Event()
        self._submitted = 0
        self._completed = 0
        self._errors = 0

        for i in range(max_workers):
            t = threading.Thread(
                target=self._worker_loop,
                daemon=True,
                name=f"{thread_name_prefix}-{i}",
            )
            t.start()
            self._workers.append(t)

    def _worker_loop(self):
        """Worker loop — pulls (fn, args, kwargs, sentinel) from queue."""
        while not self._stop_flag.is_set():
            try:
                item = self._queue.get(timeout=2.0)
            except _queue_mod.Empty:
                continue
            if item is None:  # Shutdown sentinel
                break
            fn, args, kwargs, sentinel = item
            try:
                fn(*args, **kwargs)
                self._completed += 1
            except Exception as _e:
                self._errors += 1
                try:
                    print(f"[QueueWorkerPool] Error in "
                          f"{fn.__name__ if hasattr(fn, '__name__') else fn}: {_e}")
                except Exception:
                    pass
            finally:
                if sentinel is not None:
                    sentinel._done = True

    def submit(self, fn, *args, **kwargs):
        """Submit work to the pool. Returns a lightweight sentinel (not a Future).

        If the queue is full, drops the work (fire-and-forget pattern).
        """
        sentinel = _SubmitSentinel()
        try:
            self._queue.put_nowait((fn, args, kwargs, sentinel))
            self._submitted += 1
        except _queue_mod.Full:
            pass  # Drop rather than block — same as postal backpressure
        return sentinel

    def shutdown(self, wait=True):
        """Shutdown the pool."""
        self._stop_flag.set()
        for _ in self._workers:
            try:
                self._queue.put_nowait(None)
            except _queue_mod.Full:
                pass

    def stats(self):
        return {
            "submitted": self._submitted,
            "completed": self._completed,
            "errors": self._errors,
            "queue_depth": self._queue.qsize(),
            "workers": len(self._workers),
        }


# ═══════════════════════════════════════════════════════════════════════════════
# SHARED GLOBAL WORKER POOL — All fairies share ONE pool
# ═══════════════════════════════════════════════════════════════════════════════
#
# FIX 2026-04-05 (Nous): Replaced ThreadPoolExecutor with QueueWorkerPool.
# TPE.submit() created 340K+ Future objects (each with Condition+RLock+deque)
# that Python 3.14t free-threaded GC couldn't collect → 20GB RAM growth.
# QueueWorkerPool: zero per-submit allocations, same 24-worker concurrency.
#
_SHARED_WORKER_POOL: Optional[QueueWorkerPool] = None
_SHARED_POOL_LOCK = threading.Lock()
_SHARED_POOL_SIZE = 24  # Enough for concurrent work across all fairies


def _get_shared_worker_pool() -> QueueWorkerPool:
    """Get or create the shared global worker pool for all fairies."""
    global _SHARED_WORKER_POOL
    if _SHARED_WORKER_POOL is None:
        with _SHARED_POOL_LOCK:
            if _SHARED_WORKER_POOL is None:
                _SHARED_WORKER_POOL = QueueWorkerPool(
                    max_workers=_SHARED_POOL_SIZE,
                    thread_name_prefix="fairy-work"
                )
                print(f"[TracerWorkerSystem] Shared QueueWorkerPool created "
                      f"({_SHARED_POOL_SIZE} workers, ZERO Future objects)")
    return _SHARED_WORKER_POOL


# ═══════════════════════════════════════════════════════════════════════════════
# TRACER WORKER MIXIN - Add to any fairy for async processing + tracing
# ═══════════════════════════════════════════════════════════════════════════════

class TracerWorkerMixin:
    """
    Mixin that adds worker pool + tracer functionality to any fairy.

    Add to your fairy class:
        class MyFairy(TracerWorkerMixin, MyOrganFairy):
            ...

    Then use:
        tracer = self.spawn_tracer("doing_something", ...)
        future = self.submit_work(tracer, my_function, arg1, arg2)
        result = future.result()  # or let it run async

    FIX 2026-03-04: All fairies share a SINGLE global ThreadPoolExecutor
    instead of each fairy creating its own. Reduced 180 → 24 threads.
    """

    # Configuration — WORKER_POOL_SIZE is now informational only.
    # All fairies share the global pool (_SHARED_POOL_SIZE threads).
    WORKER_POOL_SIZE = 2  # Kept for backward compat — not used for pool creation
    TRACER_DEFAULT_TTL = 300.0

    def _init_tracer_worker(self):
        """Initialize worker pool reference and root tracer. Call in __init__ or on_boot.

        FIX 2026-03-04: No longer creates a per-fairy ThreadPoolExecutor.
        Uses shared global pool instead (24 threads for all 90+ fairies).
        """
        # FIX 2026-03-04: Use shared global pool instead of per-fairy pool.
        # Before: self._worker_pool = ThreadPoolExecutor(max_workers=2, ...)
        # 90 fairies × 2 threads = 180 threads. Now: 24 shared.
        self._worker_pool = _get_shared_worker_pool()

        # Tracer registry
        self._tracer_registry = get_tracer_registry()

        # Root tracer - created at registration, all work spawns from this
        self._root_tracer = UniversalTracer(
            tracer_type=TracerType.FAIRY_WORK,
            fairy_id=getattr(self, 'fairy_id', ''),
            fairy_name=getattr(self, 'ACTOR_NAME', 'Unknown'),
            cluster_id=getattr(self, 'srm_cluster_id', ''),
            content=f"Root tracer for {getattr(self, 'ACTOR_NAME', 'Unknown')}",
            operation="fairy_lifecycle",
            status=TracerStatus.RUNNING,
        )
        self._tracer_registry.register(self._root_tracer)

        # Active work tracking
        self._active_futures: Dict[str, Future] = {}
        self._tracer_lock = threading.Lock()
    
    def spawn_tracer(
        self,
        operation: str,
        content: str = "",
        tracer_type: TracerType = TracerType.FAIRY_WORK,
        parent_tracer_id: str = None,
        chain_id: str = "",
        goal_id: str = "",
        tags: Set[str] = None,
        priority: float = 0.5,
        payload: Dict[str, Any] = None,
    ) -> UniversalTracer:
        """
        Spawn a new tracer for a piece of work.
        
        Args:
            operation: What operation is being performed
            content: Human readable description
            tracer_type: Type of tracer
            parent_tracer_id: Parent tracer (defaults to root)
            chain_id: Associated thought chain
            goal_id: Associated goal
            tags: Tags for filtering
            priority: 0.0 (low) to 1.0 (urgent)
            payload: Arbitrary data to attach
        
        Returns:
            New UniversalTracer registered in the global registry
        """
        # Default to root tracer as parent
        if parent_tracer_id is None and hasattr(self, '_root_tracer'):
            parent_tracer_id = self._root_tracer.id
        
        tracer = UniversalTracer(
            tracer_type=tracer_type,
            fairy_id=getattr(self, 'fairy_id', ''),
            fairy_name=getattr(self, 'ACTOR_NAME', 'Unknown'),
            chain_id=chain_id,
            goal_id=goal_id,
            parent_tracer_id=parent_tracer_id or "",
            cluster_id=getattr(self, 'srm_cluster_id', ''),
            content=content,
            operation=operation,
            tags=tags or set(),
            priority=priority,
            payload=payload or {},
            ttl_sec=self.TRACER_DEFAULT_TTL,
        )
        
        self._tracer_registry.register(tracer)
        return tracer
    
    def submit_work(
        self,
        tracer: UniversalTracer,
        fn: Callable,
        *args,
        **kwargs
    ) -> Future:
        """
        Submit work to the worker pool with tracer tracking.
        
        Args:
            tracer: The tracer for this work (from spawn_tracer)
            fn: Function to execute
            *args, **kwargs: Arguments for the function
        
        Returns:
            Future that will contain the result
        """
        def _wrapped_work():
            tracer.start()
            try:
                result = fn(*args, **kwargs)
                tracer.complete(result)
                # Worker completed - publish reflection for token economy
                try:
                    post = getattr(self, 'post', None)
                    if post:
                        post.publish("reflection.complete", {
                            "fairy": getattr(self, 'ACTOR_NAME', 'Unknown'),
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
        
        future = self._worker_pool.submit(_wrapped_work)
        
        with self._tracer_lock:
            self._active_futures[tracer.id] = future
        
        return future
    
    def submit_traced(
        self,
        operation: str,
        fn: Callable,
        *args,
        content: str = "",
        chain_id: str = "",
        goal_id: str = "",
        priority: float = 0.5,
        **kwargs
    ) -> tuple[UniversalTracer, Future]:
        """
        Convenience method: spawn tracer + submit work in one call.
        
        Returns:
            Tuple of (tracer, future)
        """
        tracer = self.spawn_tracer(
            operation=operation,
            content=content or f"Executing {operation}",
            chain_id=chain_id,
            goal_id=goal_id,
            priority=priority,
        )
        future = self.submit_work(tracer, fn, *args, **kwargs)
        return tracer, future
    
    def get_active_work(self) -> List[UniversalTracer]:
        """Get all active work tracers for this fairy."""
        with self._tracer_lock:
            return [
                self._tracer_registry.get(tid)
                for tid in self._active_futures.keys()
                if self._tracer_registry.get(tid)
            ]
    
    def get_work_stats(self) -> Dict[str, Any]:
        """Get worker pool statistics."""
        fairy_tracers = self._tracer_registry.get_by_fairy(
            getattr(self, 'fairy_id', '')
        )
        
        return {
            "active_futures": len(self._active_futures),
            "total_tracers": len(fairy_tracers),
            "pool_size": self.WORKER_POOL_SIZE,
            "root_tracer_id": self._root_tracer.id if hasattr(self, '_root_tracer') else None,
        }
    
    def shutdown_workers(self, wait: bool = True):
        """Shutdown the worker pool.

        FIX 2026-03-04: With shared global pool, individual fairies no longer
        shut down the pool (it would kill all other fairies' work). Only clean
        up local state. The shared pool is shut down at system exit.
        """
        # Don't shutdown the shared pool — other fairies still need it.
        # Just clean up our local state.
        with self._tracer_lock:
            self._active_futures.clear()


# ═══════════════════════════════════════════════════════════════════════════════
# FILE/MEDIA/CONTENT TRACER HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def trace_file(
    filepath: str,
    operation: str,
    fairy_id: str = "",
    fairy_name: str = "",
    cluster_id: str = "",
    parent_tracer_id: str = "",
    **extra
) -> UniversalTracer:
    """Create a tracer for a file operation."""
    import os
    
    # Determine file type
    ext = os.path.splitext(filepath)[1].lower()
    if ext in ('.py', '.json', '.yaml', '.yml', '.toml', '.ini', '.cfg'):
        tracer_type = TracerType.FILE_SYSTEM
    else:
        tracer_type = TracerType.FILE_USER
    
    tracer = UniversalTracer(
        tracer_type=tracer_type,
        fairy_id=fairy_id,
        fairy_name=fairy_name,
        cluster_id=cluster_id,
        parent_tracer_id=parent_tracer_id,
        content=f"{operation}: {os.path.basename(filepath)}",
        operation=operation,
        payload={
            "filepath": filepath,
            "extension": ext,
            **extra
        },
    )
    
    get_tracer_registry().register(tracer)
    return tracer


def trace_media(
    media_path: str,
    operation: str,
    media_type: str = "unknown",  # image, audio, video
    fairy_id: str = "",
    fairy_name: str = "",
    cluster_id: str = "",
    parent_tracer_id: str = "",
    **extra
) -> UniversalTracer:
    """Create a tracer for media operation."""
    import os
    
    tracer = UniversalTracer(
        tracer_type=TracerType.MEDIA,
        fairy_id=fairy_id,
        fairy_name=fairy_name,
        cluster_id=cluster_id,
        parent_tracer_id=parent_tracer_id,
        content=f"{operation}: {os.path.basename(media_path)}",
        operation=operation,
        payload={
            "media_path": media_path,
            "media_type": media_type,
            **extra
        },
    )
    
    get_tracer_registry().register(tracer)
    return tracer


def trace_conversation(
    conversation_id: str,
    operation: str,
    participants: List[str] = None,
    fairy_id: str = "",
    fairy_name: str = "",
    cluster_id: str = "",
    parent_tracer_id: str = "",
    **extra
) -> UniversalTracer:
    """Create a tracer for conversation."""
    tracer = UniversalTracer(
        tracer_type=TracerType.CONVERSATION,
        fairy_id=fairy_id,
        fairy_name=fairy_name,
        cluster_id=cluster_id,
        parent_tracer_id=parent_tracer_id,
        content=f"{operation}: conversation {conversation_id[:8]}...",
        operation=operation,
        payload={
            "conversation_id": conversation_id,
            "participants": participants or [],
            **extra
        },
    )
    
    get_tracer_registry().register(tracer)
    return tracer


# ═══════════════════════════════════════════════════════════════════════════════
# MODULE EXPORTS
# ═══════════════════════════════════════════════════════════════════════════════

__all__ = [
    # Core types
    "TracerType",
    "TracerStatus",
    "UniversalTracer",
    
    # Registry
    "TracerRegistry",
    "get_tracer_registry",
    
    # Mixin for fairies
    "TracerWorkerMixin",
    
    # Helpers
    "trace_file",
    "trace_media",
    "trace_conversation",
]
