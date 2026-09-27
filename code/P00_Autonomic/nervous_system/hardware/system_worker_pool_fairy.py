"""
SystemWorkerPoolFairy - Parallel Substrate Processing Engine

The unconscious mind processes through ATOMS of thought in parallel.
This fairy manages the worker pool that executes these atoms,
tracking relationships via TracerPool and feeding bindings to
the Association Cortex.

Philosophy:
- Substrate layer = Atoms of thought (parallel, many small units)
- Waking layer = Chain of thought (sequential, connected reasoning)
- Workers are the bridge: they execute atoms and build the relational fabric

The Equation: Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)
"""

from __future__ import annotations

import os
import time
import uuid
import queue
import threading
from concurrent.futures import ThreadPoolExecutor, Future, as_completed
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, TYPE_CHECKING
from enum import Enum
from collections import deque

if TYPE_CHECKING:
    from postal_core.tensor_fabric import TensorFabric

# Add project root for fairy_template import
import sys
from pathlib import Path
ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(ROOT))

from fairies.P00_Autonomic.organ_template import MyFairy as Fairy  # HeartbeatMixin removed - Fifth Ring Principle


# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass
class WorkerPoolConfig:
    """Configuration for the worker pool."""
    # Pool sizes
    io_pool_base: int = 4           # Base I/O workers (always running)
    io_pool_max: int = 16           # Max I/O workers under load
    compute_pool_max: int = 4       # CPU-bound workers (optional)

    # Equilibrium settings
    rebalance_interval_sec: float = 5.0   # How often to rebalance
    idle_reclaim_after_sec: float = 30.0  # Reclaim idle workers after this

    # Allocation limits
    min_allocation: int = 1              # Min workers per fairy
    max_allocation_percent: float = 0.5  # Max % of pool per fairy

    # Tracer integration
    enable_tracing: bool = True          # Track atom relationships
    trace_depth: int = 3                 # How deep to trace connections


# =============================================================================
# THOUGHT ATOM - A unit of substrate processing
# =============================================================================

class AtomType(Enum):
    """Types of thought atoms."""
    INTEREST = "interest"           # Curiosity/wonder
    MEMORY = "memory"               # Memory retrieval/storage
    ASSOCIATION = "association"     # Concept binding
    PATTERN = "pattern"             # Pattern detection
    ANOMALY = "anomaly"             # Anomaly detection
    INFERENCE = "inference"         # Logical inference
    AFFECT = "affect"               # Emotional processing
    SOMATIC = "somatic"             # Body state processing


@dataclass
class ThoughtAtom:
    """
    A single atom of thought - the smallest unit of substrate processing.

    Workers execute these atoms in parallel, tracking their relationships
    via tracers and feeding results to the Association Cortex.
    """
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    atom_type: AtomType = AtomType.INTEREST
    content: Dict[str, Any] = field(default_factory=dict)
    source: str = "unknown"

    # Execution context
    priority: int = 5               # 1-10, higher = more urgent
    created_at: float = field(default_factory=time.time)
    timeout_sec: float = 5.0        # Max execution time

    # Relational context (for tracer tracking)
    parent_atom_id: Optional[str] = None    # What spawned this atom
    related_concepts: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)

    # Result (filled after execution)
    result: Optional[Any] = None
    error: Optional[str] = None
    executed_at: Optional[float] = None
    execution_time_ms: Optional[float] = None

    # Bindings created (for Association Cortex)
    bindings_created: List[Tuple[str, str, str]] = field(default_factory=list)  # (concept_a, concept_b, relation)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "atom_type": self.atom_type.value,
            "content": self.content,
            "source": self.source,
            "priority": self.priority,
            "created_at": self.created_at,
            "related_concepts": self.related_concepts,
            "tags": self.tags,
            "result": self.result,
            "error": self.error,
            "executed_at": self.executed_at,
            "execution_time_ms": self.execution_time_ms,
            "bindings_created": self.bindings_created,
        }


# =============================================================================
# ATOM RESULT - What comes back from worker execution
# =============================================================================

@dataclass
class AtomResult:
    """Result of executing a thought atom."""
    atom_id: str
    success: bool
    result: Any = None
    error: Optional[str] = None
    execution_time_ms: float = 0.0

    # Relationships discovered during execution
    discovered_concepts: List[str] = field(default_factory=list)
    bindings: List[Tuple[str, str, str]] = field(default_factory=list)

    # Child atoms spawned (for recursive processing)
    spawned_atoms: List[ThoughtAtom] = field(default_factory=list)


# =============================================================================
# WORKER - Executes atoms and tracks relationships
# =============================================================================

class AtomWorker:
    """
    A worker that executes thought atoms.

    Each worker:
    1. Pulls atoms from the queue
    2. Executes them with tracer tracking
    3. Discovers relationships between concepts
    4. Reports bindings to Association Cortex
    """

    def __init__(
        self,
        worker_id: str,
        atom_queue: queue.PriorityQueue,
        result_queue: queue.Queue,
        config: WorkerPoolConfig,
        tracer_pool=None,
        association_cortex=None,
    ):
        self.worker_id = worker_id
        self.atom_queue = atom_queue
        self.result_queue = result_queue
        self.config = config
        self.tracer_pool = tracer_pool
        self.association_cortex = association_cortex

        # State
        self._running = False
        self._atoms_processed = 0
        self._total_execution_time_ms = 0.0
        self._last_activity = time.time()

    def execute_atom(self, atom: ThoughtAtom, executor_fn: Optional[Callable] = None) -> AtomResult:
        """
        Execute a single thought atom.

        Args:
            atom: The atom to execute
            executor_fn: Optional custom executor function

        Returns:
            AtomResult with execution results and discovered relationships
        """
        start_time = time.time()
        result = AtomResult(atom_id=atom.id, success=False)

        try:
            # Start tracer if enabled
            tracer_id = None
            if self.config.enable_tracing and self.tracer_pool:
                tracer_id = self.tracer_pool.start_trace(
                    f"atom:{atom.id}",
                    metadata={
                        "atom_type": atom.atom_type.value,
                        "source": atom.source,
                        "concepts": atom.related_concepts,
                    }
                )

            # Execute the atom
            if executor_fn:
                atom_result = executor_fn(atom)
            else:
                atom_result = self._default_execute(atom)

            result.result = atom_result
            result.success = True

            # Extract discovered concepts from result
            if isinstance(atom_result, dict):
                result.discovered_concepts = atom_result.get("concepts", [])
                result.spawned_atoms = atom_result.get("spawned_atoms", [])

            # Create bindings from related concepts
            all_concepts = list(set(atom.related_concepts + result.discovered_concepts))
            if len(all_concepts) >= 2:
                # Bind each pair of concepts
                for i, concept_a in enumerate(all_concepts[:-1]):
                    for concept_b in all_concepts[i+1:]:
                        binding = (concept_a, concept_b, f"coactivate:{atom.atom_type.value}")
                        result.bindings.append(binding)

                        # Send to Association Cortex
                        if self.association_cortex:
                            try:
                                self.association_cortex.bind(concept_a, concept_b,
                                    rel=f"coactivate:{atom.atom_type.value}",
                                    weight=0.1)
                            except Exception:
                                pass

            # End tracer
            if tracer_id and self.tracer_pool:
                self.tracer_pool.end_trace(tracer_id, result={
                    "success": True,
                    "bindings": len(result.bindings),
                    "concepts": len(all_concepts),
                })

        except Exception as e:
            result.error = str(e)
            result.success = False

            if tracer_id and self.tracer_pool:
                self.tracer_pool.end_trace(tracer_id, error=str(e))

        # Record timing
        end_time = time.time()
        result.execution_time_ms = (end_time - start_time) * 1000

        # Update stats
        self._atoms_processed += 1
        self._total_execution_time_ms += result.execution_time_ms
        self._last_activity = end_time

        return result

    def _default_execute(self, atom: ThoughtAtom) -> Dict[str, Any]:
        """Default execution for atoms without custom executor."""
        # Simple processing based on atom type
        result = {
            "processed": True,
            "atom_type": atom.atom_type.value,
            "concepts": atom.related_concepts.copy(),
            "spawned_atoms": [],
        }

        # Type-specific processing
        if atom.atom_type == AtomType.INTEREST:
            # Interest atoms may spawn exploration atoms
            if atom.content.get("urgency", 0) > 0.6:
                child = ThoughtAtom(
                    atom_type=AtomType.PATTERN,
                    content={"explore": atom.content.get("content", "")},
                    source=f"interest:{atom.id}",
                    parent_atom_id=atom.id,
                    related_concepts=atom.related_concepts,
                )
                result["spawned_atoms"].append(child)

        elif atom.atom_type == AtomType.PATTERN:
            # Pattern detection adds pattern-related concepts
            result["concepts"].append(f"pattern:{atom.id[:6]}")

        elif atom.atom_type == AtomType.ASSOCIATION:
            # Association atoms strengthen bindings (already handled above)
            pass

        return result

    def get_stats(self) -> Dict[str, Any]:
        """Get worker statistics."""
        return {
            "worker_id": self.worker_id,
            "atoms_processed": self._atoms_processed,
            "total_execution_time_ms": self._total_execution_time_ms,
            "avg_execution_time_ms": (
                self._total_execution_time_ms / self._atoms_processed
                if self._atoms_processed > 0 else 0
            ),
            "last_activity": self._last_activity,
            "idle_seconds": time.time() - self._last_activity,
        }


# =============================================================================
# SYSTEM WORKER POOL FAIRY - The main pool manager
# =============================================================================

class SystemWorkerPoolFairy(Fairy):
    """
    System Worker Pool - Parallel Substrate Processing Engine.

    Manages a pool of workers that execute thought atoms in parallel,
    tracking relationships and feeding bindings to the Association Cortex.

    This is the bridge between:
    - Substrate layer (atoms, parallel)
    - Cognitive layer (chains, sequential)

    Fifth Ring Principle: Now a proper Fairy, heartbeat flows through postal system.
    """

    ACTOR_NAME = "SystemWorkerPoolFairy"
    ACTOR_PLANE = "P00"
    ACTOR_CHANNEL = "fairy.system_worker_pool"
    CRITICALITY = 10  # High criticality - manages all parallel processing

    def __init__(
        self,
        fabric: Optional["TensorFabric"] = None,
        config: Optional[WorkerPoolConfig] = None,
    ):
        # Initialize Fairy base class - Fifth Ring Principle compliant
        super().__init__(fabric=fabric)

        self.config = config or WorkerPoolConfig()

        # Thread pool for I/O-bound work (most fairy tasks)
        self._io_pool: Optional[ThreadPoolExecutor] = None

        # Queues
        self._atom_queue: queue.PriorityQueue = queue.PriorityQueue()
        self._result_queue: queue.Queue = queue.Queue()

        # Workers
        self._workers: Dict[str, AtomWorker] = {}

        # External references
        self._tracer_pool = None
        self._association_cortex = None
        self._collision_chamber = None

        # State
        self._running = False
        self._boot_time: Optional[float] = None
        self._dispatch_thread: Optional[threading.Thread] = None
        self._result_thread: Optional[threading.Thread] = None

        # Statistics
        self._stats = {
            "atoms_submitted": 0,
            "atoms_completed": 0,
            "atoms_failed": 0,
            "bindings_created": 0,
            "total_execution_time_ms": 0.0,
        }

        # Pending futures
        self._pending_futures: Dict[str, Future] = {}

        # Recent results for inspection
        self._recent_results: deque = deque(maxlen=100)

        # Lock for thread safety
        self._lock = threading.Lock()

    def on_boot(self) -> Dict[str, Any]:
        """Boot the worker pool."""
        if self._running:
            return {"ok": False, "error": "already_running"}

        self._boot_time = time.time()

        # Create thread pool
        self._io_pool = ThreadPoolExecutor(
            max_workers=self.config.io_pool_max,
            thread_name_prefix="atom_worker_"
        )

        # Create workers
        for i in range(self.config.io_pool_base):
            worker_id = f"worker_{i:02d}"
            self._workers[worker_id] = AtomWorker(
                worker_id=worker_id,
                atom_queue=self._atom_queue,
                result_queue=self._result_queue,
                config=self.config,
                tracer_pool=self._tracer_pool,
                association_cortex=self._association_cortex,
            )

        # Start dispatch thread
        self._running = True
        self._dispatch_thread = threading.Thread(
            target=self._dispatch_loop,
            daemon=True,
            name="atom_dispatcher"
        )
        self._dispatch_thread.start()

        # Start result processing thread
        self._result_thread = threading.Thread(
            target=self._result_loop,
            daemon=True,
            name="result_processor"
        )
        self._result_thread.start()

        # Heartbeat now handled by Fairy base class via postal system
        # No more HeartbeatMixin bypass - Fifth Ring Principle

        print(f"[{self.ACTOR_NAME}] Booted with {len(self._workers)} workers "
              f"(pool max: {self.config.io_pool_max})")

        return {
            "ok": True,
            "workers": len(self._workers),
            "pool_max": self.config.io_pool_max,
        }

    def on_shutdown(self) -> None:
        """Shutdown the worker pool gracefully."""
        print(f"[{self.ACTOR_NAME}] Shutting down...")

        self._running = False

        # Heartbeat cleanup handled by Fairy base class
        # No more HeartbeatMixin bypass - Fifth Ring Principle

        # Wait for threads to finish
        if self._dispatch_thread:
            self._dispatch_thread.join(timeout=2.0)
        if self._result_thread:
            self._result_thread.join(timeout=2.0)

        # Shutdown thread pool
        if self._io_pool:
            self._io_pool.shutdown(wait=True, cancel_futures=True)

        print(f"[{self.ACTOR_NAME}] Shutdown complete. "
              f"Processed {self._stats['atoms_completed']} atoms, "
              f"created {self._stats['bindings_created']} bindings.")

    # -------------------------------------------------------------------------
    # WIRING
    # -------------------------------------------------------------------------

    def wire_tracer_pool(self, tracer_pool) -> None:
        """Wire to TracerPool for relationship tracking."""
        self._tracer_pool = tracer_pool
        for worker in self._workers.values():
            worker.tracer_pool = tracer_pool
        print(f"[{self.ACTOR_NAME}] Wired to TracerPool")

    def wire_association_cortex(self, cortex) -> None:
        """Wire to Association Cortex for binding creation."""
        self._association_cortex = cortex
        for worker in self._workers.values():
            worker.association_cortex = cortex
        print(f"[{self.ACTOR_NAME}] Wired to Association Cortex")

    def wire_collision_chamber(self, chamber) -> None:
        """Wire to Collision Chamber to feed results."""
        self._collision_chamber = chamber
        print(f"[{self.ACTOR_NAME}] Wired to Collision Chamber")

    # -------------------------------------------------------------------------
    # ATOM SUBMISSION
    # -------------------------------------------------------------------------

    def submit_atom(
        self,
        atom_type: AtomType,
        content: Dict[str, Any],
        source: str = "unknown",
        priority: int = 5,
        related_concepts: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        executor_fn: Optional[Callable] = None,
    ) -> str:
        """
        Submit a thought atom for processing.

        Args:
            atom_type: Type of atom (interest, memory, association, etc.)
            content: The atom's content
            source: What created this atom
            priority: 1-10, higher = more urgent
            related_concepts: Concepts related to this atom
            tags: Additional tags
            executor_fn: Optional custom executor function

        Returns:
            atom_id: ID for tracking
        """
        atom = ThoughtAtom(
            atom_type=atom_type,
            content=content,
            source=source,
            priority=priority,
            related_concepts=related_concepts or [],
            tags=tags or [],
        )

        # Add to queue (priority queue uses tuple: (priority, timestamp, atom))
        # Negate priority so higher priority = lower number = processed first
        self._atom_queue.put((-atom.priority, atom.created_at, atom, executor_fn))

        with self._lock:
            self._stats["atoms_submitted"] += 1

        return atom.id

    def submit(self, fn: Callable, *args, **kwargs) -> Any:
        """
        Simple submit interface for backward compatibility.

        Wraps a function call in an atom and executes it.
        """
        if not self._io_pool:
            # Fallback to direct execution if pool not ready
            return fn(*args, **kwargs)

        future = self._io_pool.submit(fn, *args, **kwargs)
        return future.result(timeout=30.0)

    def submit_async(self, fn: Callable, *args, **kwargs) -> Future:
        """Submit a function for async execution, return Future."""
        if not self._io_pool:
            raise RuntimeError("Worker pool not running")
        return self._io_pool.submit(fn, *args, **kwargs)

    # -------------------------------------------------------------------------
    # DISPATCH LOOP - Pulls atoms from queue and executes
    # -------------------------------------------------------------------------

    def _dispatch_loop(self) -> None:
        """Main dispatch loop - pulls atoms and submits to workers."""
        while self._running:
            try:
                # Get atom from queue (with timeout to allow shutdown)
                try:
                    priority, timestamp, atom, executor_fn = self._atom_queue.get(timeout=0.5)
                except queue.Empty:
                    continue

                # Pick a worker (round-robin for now)
                worker_list = list(self._workers.values())
                if not worker_list:
                    continue

                worker = worker_list[self._stats["atoms_submitted"] % len(worker_list)]

                # Submit to thread pool
                if self._io_pool:
                    future = self._io_pool.submit(
                        worker.execute_atom,
                        atom,
                        executor_fn
                    )

                    # Track future
                    with self._lock:
                        self._pending_futures[atom.id] = future

                    # Add callback for result processing
                    future.add_done_callback(
                        lambda f, aid=atom.id: self._on_atom_complete(aid, f)
                    )

            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Dispatch error: {e}")

    def _on_atom_complete(self, atom_id: str, future: Future) -> None:
        """Callback when an atom completes."""
        try:
            result = future.result(timeout=1.0)
            self._result_queue.put(result)
        except Exception as e:
            # Create error result
            self._result_queue.put(AtomResult(
                atom_id=atom_id,
                success=False,
                error=str(e)
            ))

        # Remove from pending
        with self._lock:
            self._pending_futures.pop(atom_id, None)

    # -------------------------------------------------------------------------
    # RESULT LOOP - Processes completed atoms
    # -------------------------------------------------------------------------

    def _result_loop(self) -> None:
        """Process results from completed atoms."""
        while self._running:
            try:
                # Get result (with timeout)
                try:
                    result = self._result_queue.get(timeout=0.5)
                except queue.Empty:
                    continue

                with self._lock:
                    if result.success:
                        self._stats["atoms_completed"] += 1
                        self._stats["bindings_created"] += len(result.bindings)
                        self._stats["total_execution_time_ms"] += result.execution_time_ms
                    else:
                        self._stats["atoms_failed"] += 1

                    self._recent_results.append(result)

                # Feed successful results to collision chamber
                if result.success and self._collision_chamber and result.discovered_concepts:
                    try:
                        self._collision_chamber.receive_ingest(
                            content={
                                "atom_id": result.atom_id,
                                "concepts": result.discovered_concepts,
                                "bindings": len(result.bindings),
                                "type": "atom_result",
                            },
                            source="worker_pool",
                            importance="normal",
                        )
                    except Exception:
                        pass

                # Process spawned atoms
                for spawned in result.spawned_atoms:
                    self._atom_queue.put((
                        -spawned.priority,
                        spawned.created_at,
                        spawned,
                        None
                    ))

            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Result processing error: {e}")

    # -------------------------------------------------------------------------
    # FAIRY STATUS (for postal heartbeat system)
    # -------------------------------------------------------------------------

    def _get_fairy_status(self) -> Dict[str, Any]:
        """Custom status for postal heartbeat - Fifth Ring Principle compliant."""
        return {
            "workers": len(self._workers),
            "atoms_completed": self._stats.get("atoms_completed", 0),
            "bindings_created": self._stats.get("bindings_created", 0),
            "pending_atoms": self._atom_queue.qsize(),
            "running": self._running,
        }

    # -------------------------------------------------------------------------
    # STATUS
    # -------------------------------------------------------------------------

    def get_status(self) -> Dict[str, Any]:
        """Get pool status.

        FIX 2026-05-15 (Nous + Ace): Added flat top-level keys
        (io_pool_size, compute_pool_size, allocations, stats) for monitoring_tools.py
        compatibility, alongside the existing nested keys. Additive — doesn't break
        existing consumers. This consolidation lets us remove the duplicate
        `fairies/P00_Autonomic/nervous_system/hardware/system_worker_pool_fairy.py`
        (the "need-before-greed" allocator variant that had no real consumers).
        """
        with self._lock:
            worker_stats = [w.get_stats() for w in self._workers.values()]

            # Build allocations dict in monitoring_tools-expected shape from worker_stats
            # FIX 2026-05-15 (Nous + Ace, post-Skeptic-v30): AtomWorker.get_stats()
            # has no "busy" field; uses "idle_seconds" instead. Use idle_seconds < 1.0
            # as recently-active proxy (workers_active=1 when last activity within 1s).
            _allocations = {
                f"worker_{i:02d}": {
                    "workers_allocated": 1,  # each AtomWorker is its own slot
                    "workers_active": 1 if ws.get("idle_seconds", 999) < 1.0 else 0,
                    "tasks_queued": 0,
                    "tasks_completed": ws.get("atoms_processed", 0),
                }
                for i, ws in enumerate(worker_stats)
            }

            return {
                # ── Top-level keys for monitoring_tools.py (Fix 2026-05-15) ──
                "io_pool_size": self.config.io_pool_max,
                "compute_pool_size": self.config.compute_pool_max,
                "allocations": _allocations,
                # ── Original nested keys (preserved) ──
                "running": self._running,
                "uptime_sec": time.time() - self._boot_time if self._boot_time else 0,
                "workers": {
                    "count": len(self._workers),
                    "pool_max": self.config.io_pool_max,
                    "stats": worker_stats,
                },
                "queues": {
                    "pending_atoms": self._atom_queue.qsize(),
                    "pending_results": self._result_queue.qsize(),
                    "pending_futures": len(self._pending_futures),
                },
                "stats": self._stats.copy(),
                "throughput": {
                    "atoms_per_sec": (
                        self._stats["atoms_completed"] /
                        (time.time() - self._boot_time)
                        if self._boot_time and time.time() > self._boot_time else 0
                    ),
                    "avg_execution_ms": (
                        self._stats["total_execution_time_ms"] /
                        self._stats["atoms_completed"]
                        if self._stats["atoms_completed"] > 0 else 0
                    ),
                },
                "wiring": {
                    "tracer_pool": self._tracer_pool is not None,
                    "association_cortex": self._association_cortex is not None,
                    "collision_chamber": self._collision_chamber is not None,
                },
            }

    def get_recent_results(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent atom results."""
        with self._lock:
            results = list(self._recent_results)[-limit:]
            return [
                {
                    "atom_id": r.atom_id,
                    "success": r.success,
                    "error": r.error,
                    "execution_time_ms": r.execution_time_ms,
                    "discovered_concepts": r.discovered_concepts,
                    "bindings_count": len(r.bindings),
                }
                for r in results
            ]


# =============================================================================
# SINGLETON & FACTORY
# =============================================================================

_pool: Optional[SystemWorkerPoolFairy] = None
_pool_lock = threading.Lock()


def get_system_pool() -> SystemWorkerPoolFairy:
    """Get the system worker pool singleton."""
    global _pool
    with _pool_lock:
        if _pool is None:
            _pool = SystemWorkerPoolFairy()
        return _pool


def create_worker_pool(
    fabric: Optional["TensorFabric"] = None,
    config: Optional[WorkerPoolConfig] = None,
) -> SystemWorkerPoolFairy:
    """Create a new worker pool (replaces singleton)."""
    global _pool
    with _pool_lock:
        _pool = SystemWorkerPoolFairy(fabric=fabric, config=config)
        return _pool


# =============================================================================
# MCP TOOL FUNCTIONS
# =============================================================================

def tool_worker_pool_status() -> Dict[str, Any]:
    """Get worker pool status for MCP."""
    pool = get_system_pool()
    return pool.get_status()


def tool_worker_pool_submit_atom(
    atom_type: str,
    content: Dict[str, Any],
    source: str = "mcp",
    priority: int = 5,
    related_concepts: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Submit a thought atom via MCP."""
    pool = get_system_pool()

    # Map string to AtomType
    try:
        atype = AtomType(atom_type)
    except ValueError:
        atype = AtomType.INTEREST

    atom_id = pool.submit_atom(
        atom_type=atype,
        content=content,
        source=source,
        priority=priority,
        related_concepts=related_concepts,
    )

    return {"atom_id": atom_id, "queued": True}


def tool_worker_pool_recent() -> Dict[str, Any]:
    """Get recent atom results via MCP."""
    pool = get_system_pool()
    return {"recent_results": pool.get_recent_results(20)}
