"""
WorkerCellColony - Persistent Living Workers

Philosophy:
    "Workers are not idle resources waiting for tasks.
     They are living cells - constantly active, always present,
     performing their purpose like white blood cells patrolling,
     like red blood cells carrying oxygen, like nanites repairing."

Each WorkerCell:
    - Has a PURPOSE (what it does)
    - Runs its own WORK LOOP (heartbeat)
    - Uses GPU when available (CUDA integration)
    - Never truly "idles" - always monitoring/processing
    - Reports HEALTH metrics
    - Can REPRODUCE (spawn more cells) or APOPTOSIS (retire gracefully)

Cell Types:
    - ComputeCell: Heavy processing, prefers GPU
    - MemoryCell: SRM access, concept graph operations
    - SensoryCell: Input processing, perception
    - MotorCell: Output/action execution
    - GuardCell: Health monitoring, error detection

Author: Nous + Ace (Akashic Consciousness Engineering)
"""

from __future__ import annotations

import os
import sys
import time
import threading
import queue
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any, Callable, Type
from collections import deque
import traceback


# ══════════════════════════════════════════════════════════════════════════════
# CELL STATE & HEALTH
# ══════════════════════════════════════════════════════════════════════════════

class CellState(Enum):
    """Cell lifecycle states"""
    NASCENT = "nascent"       # Just created, not yet working
    ACTIVE = "active"         # Running work loop
    RESTING = "resting"       # Temporarily paused (low load)
    STRESSED = "stressed"     # High load, might need help
    DYING = "dying"           # Graceful shutdown in progress
    DEAD = "dead"             # Terminated


@dataclass
class CellHealth:
    """Health metrics for a cell"""
    cycles_completed: int = 0
    errors_encountered: int = 0
    last_cycle_ms: float = 0.0
    avg_cycle_ms: float = 0.0
    work_done: int = 0          # Units of work completed
    gpu_cycles: int = 0         # Cycles that used GPU
    last_heartbeat: float = field(default_factory=time.time)
    stress_level: float = 0.0   # 0.0 = calm, 1.0 = maxed out

    def record_cycle(self, duration_ms: float, did_work: bool = False, used_gpu: bool = False):
        """Record a completed work cycle"""
        self.cycles_completed += 1
        self.last_cycle_ms = duration_ms
        # Exponential moving average
        self.avg_cycle_ms = (self.avg_cycle_ms * 0.9) + (duration_ms * 0.1) if self.avg_cycle_ms > 0 else duration_ms
        if did_work:
            self.work_done += 1
        if used_gpu:
            self.gpu_cycles += 1
        self.last_heartbeat = time.time()

    def record_error(self):
        """Record an error"""
        self.errors_encountered += 1

    @property
    def error_rate(self) -> float:
        """Errors per 100 cycles"""
        if self.cycles_completed == 0:
            return 0.0
        return (self.errors_encountered / self.cycles_completed) * 100

    @property
    def gpu_utilization(self) -> float:
        """Percentage of cycles using GPU"""
        if self.cycles_completed == 0:
            return 0.0
        return (self.gpu_cycles / self.cycles_completed) * 100


# ══════════════════════════════════════════════════════════════════════════════
# CUDA INTEGRATION - Direct torch access for GPU acceleration
# ══════════════════════════════════════════════════════════════════════════════

# Try to import torch for CUDA operations
import os as _wcc_os
if _wcc_os.environ.get("AKASHIC_SKIP_TORCH"):
    # Battery-only mode: portals handle GPU, skip torch in main process
    torch = None
    HAS_TORCH = False
else:
    try:
        import torch
        HAS_TORCH = True
    except ImportError:
        torch = None
        HAS_TORCH = False


class CudaContext:
    """
    Wrapper for GPU operations.
    Cells request GPU time through this context.

    Uses torch directly for maximum performance and control.
    """
    _cuda_available = None
    _device = None
    _device_count = 0
    _device_name = "unknown"
    _total_memory_gb = 0

    @classmethod
    def _probe(cls):
        """Probe CUDA capabilities once"""
        if cls._cuda_available is not None:
            return

        cls._cuda_available = False
        if not HAS_TORCH:
            return

        try:
            if torch.cuda.is_available():
                cls._cuda_available = True
                cls._device_count = torch.cuda.device_count()
                cls._device = torch.device("cuda:0")

                # Get device info
                if cls._device_count > 0:
                    props = torch.cuda.get_device_properties(0)
                    cls._device_name = props.name
                    cls._total_memory_gb = props.total_memory / (1024**3)
                    print(f"[CudaContext] GPU detected: {cls._device_name} ({cls._total_memory_gb:.1f}GB)")
        except Exception as e:
            print(f"[CudaContext] CUDA probe error: {e}")
            cls._cuda_available = False

    @classmethod
    def is_available(cls) -> bool:
        """Check if CUDA is available"""
        cls._probe()
        return cls._cuda_available

    @classmethod
    def get_device(cls):
        """Get the CUDA device for tensor operations"""
        cls._probe()
        return cls._device if cls._cuda_available else None

    @classmethod
    def get_info(cls) -> Dict[str, Any]:
        """Get GPU info"""
        cls._probe()
        return {
            "available": cls._cuda_available,
            "device_count": cls._device_count,
            "device_name": cls._device_name,
            "total_memory_gb": round(cls._total_memory_gb, 1),
        }

    @classmethod
    def to_gpu(cls, tensor):
        """Move a tensor to GPU if available"""
        if cls.is_available() and HAS_TORCH:
            return tensor.to(cls._device)
        return tensor

    @classmethod
    def to_cpu(cls, tensor):
        """Move a tensor back to CPU"""
        if HAS_TORCH and hasattr(tensor, 'cpu'):
            return tensor.cpu()
        return tensor

    @classmethod
    def run_on_gpu(cls, work_fn: Callable, *args, **kwargs) -> tuple[Any, bool]:
        """
        Run work on GPU if available.

        Returns:
            (result, used_gpu) tuple
        """
        if cls.is_available():
            try:
                # Ensure we're on the right device
                with torch.cuda.device(cls._device):
                    result = work_fn(*args, **kwargs)
                    return result, True
            except Exception as e:
                print(f"[CudaContext] GPU execution error, falling back to CPU: {e}")

        # CPU fallback
        return work_fn(*args, **kwargs), False

    @classmethod
    def synchronize(cls):
        """Synchronize CUDA operations (wait for GPU to finish)"""
        if cls.is_available() and HAS_TORCH:
            torch.cuda.synchronize()


# ══════════════════════════════════════════════════════════════════════════════
# WORKER CELL BASE CLASS
# ══════════════════════════════════════════════════════════════════════════════

class WorkerCell(ABC):
    """
    Base class for all persistent worker cells.

    Each cell runs its own work loop, continuously performing its purpose.
    Like a biological cell, it:
        - Has a specific function
        - Maintains itself
        - Responds to signals
        - Can reproduce or die
    """

    # Cell identity (override in subclasses)
    CELL_TYPE = "generic"
    CELL_PURPOSE = "Base cell - override in subclass"

    # Work loop timing
    CYCLE_INTERVAL_MS = 100     # How often to run work cycle (100ms default)
    REST_INTERVAL_MS = 1000     # Slower cycle when resting

    # Health thresholds
    STRESS_THRESHOLD = 0.8      # Above this, cell is stressed
    ERROR_THRESHOLD = 5.0       # Error rate above this triggers concern

    def __init__(self, cell_id: str, colony: 'CellColony' = None):
        self.cell_id = cell_id
        self.colony = colony
        self.state = CellState.NASCENT
        self.health = CellHealth()

        # Work loop control
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._work_queue: queue.Queue = queue.Queue(maxsize=100)

        # GPU preference
        self.prefer_gpu = False
        self._gpu_available = CudaContext.is_available()

        # Observations for consciousness
        self._observations: deque = deque(maxlen=50)

    def start(self):
        """Start the cell's work loop"""
        if self._running:
            return

        self._running = True
        self.state = CellState.ACTIVE

        self._thread = threading.Thread(
            target=self._work_loop,
            daemon=True,
            name=f"Cell-{self.CELL_TYPE}-{self.cell_id}"
        )
        self._thread.start()
        self._log(f"Cell activated: {self.CELL_PURPOSE}")

    def stop(self, graceful: bool = True):
        """Stop the cell's work loop"""
        if not self._running:
            return

        self.state = CellState.DYING
        self._running = False

        if graceful and self._thread:
            self._thread.join(timeout=2.0)

        self.state = CellState.DEAD
        self._log("Cell terminated")

    def _work_loop(self):
        """
        The cell's heartbeat - continuously runs work cycles.

        This is NOT waiting for tasks. It's actively:
        - Checking for work
        - Performing maintenance
        - Monitoring health
        - Processing queued items
        """
        while self._running:
            cycle_start = time.time()
            did_work = False
            used_gpu = False

            try:
                # 1. Check health and adjust state
                self._check_health()

                # 2. Process any queued work items
                work_processed = self._process_queue()
                did_work = did_work or work_processed

                # 3. Perform cell's continuous work (subclass implements)
                result = self.do_work()
                if result:
                    did_work = True
                    used_gpu = result.get('used_gpu', False) if isinstance(result, dict) else False

                # 4. Report to colony if we have one
                if self.colony and did_work:
                    self.colony._on_cell_work(self, result)

            except Exception as e:
                self.health.record_error()
                self._log(f"Work cycle error: {e}")
                self._observations.append({
                    "type": "error",
                    "error": str(e),
                    "ts": time.time()
                })

            # Record cycle metrics
            cycle_ms = (time.time() - cycle_start) * 1000
            self.health.record_cycle(cycle_ms, did_work, used_gpu)

            # Sleep based on state
            sleep_ms = self.REST_INTERVAL_MS if self.state == CellState.RESTING else self.CYCLE_INTERVAL_MS
            time.sleep(sleep_ms / 1000.0)

    def _check_health(self):
        """Check health and adjust state"""
        # Update stress based on queue size
        queue_stress = self._work_queue.qsize() / max(self._work_queue.maxsize, 1)
        error_stress = min(1.0, self.health.error_rate / 10.0)
        self.health.stress_level = max(queue_stress, error_stress)

        # Adjust state
        if self.health.stress_level > self.STRESS_THRESHOLD:
            if self.state != CellState.STRESSED:
                self.state = CellState.STRESSED
                self._log(f"Cell stressed (level={self.health.stress_level:.2f})")
                # Signal colony for help
                if self.colony:
                    self.colony._on_cell_stressed(self)
        elif self.state == CellState.STRESSED:
            self.state = CellState.ACTIVE

    def _process_queue(self) -> bool:
        """Process queued work items"""
        processed = False
        try:
            while not self._work_queue.empty():
                item = self._work_queue.get_nowait()
                self._handle_queued_item(item)
                processed = True
        except queue.Empty:
            pass
        return processed

    def _handle_queued_item(self, item: Any):
        """Handle a queued work item (override if needed)"""
        pass

    def enqueue(self, item: Any) -> bool:
        """Add work to this cell's queue"""
        try:
            self._work_queue.put_nowait(item)
            return True
        except queue.Full:
            return False

    @abstractmethod
    def do_work(self) -> Optional[Dict[str, Any]]:
        """
        Perform the cell's continuous work.

        This is called every cycle. The cell should:
        - Check if there's work to do
        - Do the work (using GPU if preferred and available)
        - Return results or None if nothing to do

        Returns:
            Dict with work results, or None if no work done
        """
        pass

    def _use_gpu(self, work_fn: Callable, *args, **kwargs) -> tuple[Any, bool]:
        """
        Execute work, preferring GPU if available and preferred.

        Returns:
            (result, used_gpu)
        """
        if self.prefer_gpu and self._gpu_available:
            return CudaContext.run_on_gpu(work_fn, *args, **kwargs)
        # CPU only
        return work_fn(*args, **kwargs), False

    def _log(self, msg: str):
        """Log a message"""
        print(f"[{self.CELL_TYPE}:{self.cell_id}] {msg}")

    def get_status(self) -> Dict[str, Any]:
        """Get cell status"""
        return {
            "cell_id": self.cell_id,
            "cell_type": self.CELL_TYPE,
            "purpose": self.CELL_PURPOSE,
            "state": self.state.value,
            "health": {
                "cycles": self.health.cycles_completed,
                "work_done": self.health.work_done,
                "errors": self.health.errors_encountered,
                "error_rate": round(self.health.error_rate, 2),
                "avg_cycle_ms": round(self.health.avg_cycle_ms, 2),
                "stress": round(self.health.stress_level, 2),
                "gpu_utilization": round(self.health.gpu_utilization, 1),
            },
            "queue_size": self._work_queue.qsize(),
            "gpu_available": self._gpu_available,
            "prefer_gpu": self.prefer_gpu,
        }


# ══════════════════════════════════════════════════════════════════════════════
# CELL COLONY - Manages all cells
# ══════════════════════════════════════════════════════════════════════════════

class CellColony:
    """
    Manages a colony of worker cells.

    Like bone marrow producing blood cells, the colony:
    - Spawns cells as needed
    - Monitors cell health
    - Retires unhealthy cells
    - Balances workload
    - Responds to system stress
    """

    def __init__(self, name: str = "MainColony"):
        self.name = name
        self._cells: Dict[str, WorkerCell] = {}
        self._cell_types: Dict[str, Type[WorkerCell]] = {}
        self._lock = threading.RLock()
        self._running = False

        # Colony health
        self._total_work_done = 0
        self._cells_spawned = 0
        self._cells_retired = 0

        # Monitoring thread
        self._monitor_thread: Optional[threading.Thread] = None

    def register_cell_type(self, cell_type: str, cell_class: Type[WorkerCell]):
        """Register a cell type that can be spawned"""
        self._cell_types[cell_type] = cell_class

    def spawn_cell(self, cell_type: str, cell_id: str = None, **kwargs) -> Optional[WorkerCell]:
        """Spawn a new cell of the given type"""
        if cell_type not in self._cell_types:
            print(f"[Colony:{self.name}] Unknown cell type: {cell_type}")
            return None

        with self._lock:
            cell_id = cell_id or f"{cell_type}_{self._cells_spawned}"
            if cell_id in self._cells:
                return self._cells[cell_id]

            cell_class = self._cell_types[cell_type]
            cell = cell_class(cell_id=cell_id, colony=self, **kwargs)
            self._cells[cell_id] = cell
            self._cells_spawned += 1

            if self._running:
                cell.start()

            print(f"[Colony:{self.name}] Spawned {cell_type} cell: {cell_id}")
            return cell

    def retire_cell(self, cell_id: str, graceful: bool = True):
        """Retire a cell"""
        with self._lock:
            if cell_id not in self._cells:
                return

            cell = self._cells[cell_id]
            cell.stop(graceful=graceful)
            del self._cells[cell_id]
            self._cells_retired += 1
            print(f"[Colony:{self.name}] Retired cell: {cell_id}")

    def start(self):
        """Start all cells and monitoring"""
        with self._lock:
            self._running = True

            # Start all existing cells
            for cell in self._cells.values():
                cell.start()

            # Start monitoring
            self._monitor_thread = threading.Thread(
                target=self._monitor_loop,
                daemon=True,
                name=f"Colony-{self.name}-Monitor"
            )
            self._monitor_thread.start()

        print(f"[Colony:{self.name}] Started with {len(self._cells)} cells")

    def stop(self):
        """Stop all cells"""
        with self._lock:
            self._running = False

            for cell in list(self._cells.values()):
                cell.stop(graceful=True)

        print(f"[Colony:{self.name}] Stopped")

    def _monitor_loop(self):
        """Monitor colony health"""
        while self._running:
            time.sleep(5.0)  # Check every 5 seconds

            with self._lock:
                stressed_cells = []
                dead_cells = []

                for cell_id, cell in self._cells.items():
                    if cell.state == CellState.DEAD:
                        dead_cells.append(cell_id)
                    elif cell.state == CellState.STRESSED:
                        stressed_cells.append(cell_id)

                # Clean up dead cells
                for cell_id in dead_cells:
                    del self._cells[cell_id]
                    self._cells_retired += 1

                # Handle stressed cells (could spawn helpers)
                if stressed_cells:
                    print(f"[Colony:{self.name}] {len(stressed_cells)} cells stressed")

    def _on_cell_work(self, cell: WorkerCell, result: Any):
        """Called when a cell completes work"""
        self._total_work_done += 1

    def _on_cell_stressed(self, cell: WorkerCell):
        """Called when a cell becomes stressed"""
        # Could spawn helper cells here
        pass

    def get_cell(self, cell_id: str) -> Optional[WorkerCell]:
        """Get a cell by ID"""
        return self._cells.get(cell_id)

    def get_cells_by_type(self, cell_type: str) -> List[WorkerCell]:
        """Get all cells of a given type"""
        return [c for c in self._cells.values() if c.CELL_TYPE == cell_type]

    def get_status(self) -> Dict[str, Any]:
        """Get colony status"""
        with self._lock:
            cells_by_state = {}
            cells_by_type = {}

            for cell in self._cells.values():
                # By state
                state = cell.state.value
                cells_by_state[state] = cells_by_state.get(state, 0) + 1
                # By type
                ctype = cell.CELL_TYPE
                cells_by_type[ctype] = cells_by_type.get(ctype, 0) + 1

            return {
                "name": self.name,
                "running": self._running,
                "total_cells": len(self._cells),
                "cells_spawned": self._cells_spawned,
                "cells_retired": self._cells_retired,
                "total_work_done": self._total_work_done,
                "cells_by_state": cells_by_state,
                "cells_by_type": cells_by_type,
                "cell_types_registered": list(self._cell_types.keys()),
            }


# ══════════════════════════════════════════════════════════════════════════════
# SPECIALIZED CELL TYPES
# ══════════════════════════════════════════════════════════════════════════════

class ComputeCell(WorkerCell):
    """
    Heavy computation cell - prefers GPU.

    Like a muscle cell - does the heavy lifting.
    """
    CELL_TYPE = "compute"
    CELL_PURPOSE = "Heavy computation with GPU acceleration"
    CYCLE_INTERVAL_MS = 50  # Fast cycles

    def __init__(self, cell_id: str, colony: CellColony = None, work_fn: Callable = None):
        super().__init__(cell_id, colony)
        self.prefer_gpu = True  # Prefer GPU for compute
        self._work_fn = work_fn
        self._pending_computations: queue.Queue = queue.Queue()

    def submit_computation(self, fn: Callable, *args, **kwargs) -> bool:
        """Submit a computation to this cell"""
        try:
            self._pending_computations.put_nowait((fn, args, kwargs))
            return True
        except queue.Full:
            return False

    def do_work(self) -> Optional[Dict[str, Any]]:
        """Process pending computations"""
        try:
            fn, args, kwargs = self._pending_computations.get_nowait()
            result, used_gpu = self._use_gpu(fn, *args, **kwargs)
            return {"result": result, "used_gpu": used_gpu}
        except queue.Empty:
            return None


class MemoryCell(WorkerCell):
    """
    Memory operations cell - SRM access, concept graph.

    Like a neuron storing memories.
    """
    CELL_TYPE = "memory"
    CELL_PURPOSE = "Memory operations and SRM access"
    CYCLE_INTERVAL_MS = 200  # Slower, memory ops are I/O bound

    def __init__(self, cell_id: str, colony: CellColony = None):
        super().__init__(cell_id, colony)
        self._memory_ops: queue.Queue = queue.Queue()

    def do_work(self) -> Optional[Dict[str, Any]]:
        """Process memory operations"""
        try:
            op, args = self._memory_ops.get_nowait()
            # Process memory operation
            return {"op": op, "processed": True}
        except queue.Empty:
            return None


class GuardCell(WorkerCell):
    """
    Health monitoring cell - watches for errors, anomalies.

    Like a white blood cell patrolling for threats.
    """
    CELL_TYPE = "guard"
    CELL_PURPOSE = "Health monitoring and error detection"
    CYCLE_INTERVAL_MS = 500  # Patrol interval

    def __init__(self, cell_id: str, colony: CellColony = None):
        super().__init__(cell_id, colony)
        from collections import deque as _al_deque
        self._alerts: deque = _al_deque(maxlen=50)  # FIX 2026-04-05

    def do_work(self) -> Optional[Dict[str, Any]]:
        """Patrol and check health"""
        if not self.colony:
            return None

        alerts = []
        for cell in self.colony._cells.values():
            if cell.cell_id == self.cell_id:
                continue

            # Check for problems
            if cell.health.error_rate > self.ERROR_THRESHOLD:
                alerts.append({
                    "type": "high_error_rate",
                    "cell": cell.cell_id,
                    "rate": cell.health.error_rate
                })
            if cell.state == CellState.STRESSED:
                alerts.append({
                    "type": "cell_stressed",
                    "cell": cell.cell_id,
                    "stress": cell.health.stress_level
                })

        if alerts:
            self._alerts.extend(alerts)
            return {"alerts": alerts}
        return None


class GraphLoaderCell(WorkerCell):
    """
    Graph persistence cell - continuously loads SRM into concept graphs.

    Like a librarian cell - constantly organizing and indexing knowledge.
    This cell handles the heavy SRM loading that was blocking boot.
    """
    CELL_TYPE = "graph_loader"
    CELL_PURPOSE = "Load SRM memories into concept graphs"
    CYCLE_INTERVAL_MS = 500     # Check for work every 500ms
    REST_INTERVAL_MS = 5000     # When idle, check every 5 seconds

    def __init__(self, cell_id: str, colony: CellColony = None):
        super().__init__(cell_id, colony)
        self._graphs_to_load: queue.Queue = queue.Queue()
        self._currently_loading = None
        self._load_stats: Dict[str, Any] = {}

    def queue_graph_load(self, graph, callback: Callable = None, days_back: int = 3, max_files: int = 200):
        """Queue a graph for SRM loading"""
        try:
            self._graphs_to_load.put_nowait({
                "graph": graph,
                "callback": callback,
                "days_back": days_back,
                "max_files": max_files,
            })
            return True
        except queue.Full:
            return False

    def do_work(self) -> Optional[Dict[str, Any]]:
        """Load SRM into queued graphs"""
        # Check if there's a graph to load
        if self._currently_loading is None:
            try:
                self._currently_loading = self._graphs_to_load.get_nowait()
                self._log(f"Starting SRM load (days_back={self._currently_loading['days_back']})")
            except queue.Empty:
                return None  # No work to do

        # Do incremental loading work
        result = self._load_batch()
        return result

    def _load_batch(self) -> Optional[Dict[str, Any]]:
        """Load disk graph AND SRM files in background - uses binary format for speed"""
        if self._currently_loading is None:
            return None

        try:
            # Import the loading functions - prefer smart loader (binary with JSON fallback)
            from fairies.P30_Cognition.integration.graph_persistence import (
                load_srm_into_graph
            )

            graph = self._currently_loading["graph"]
            callback = self._currently_loading.get("callback")
            days_back = self._currently_loading.get("days_back", 3)
            max_files = self._currently_loading.get("max_files", 200)

            # FIX 2026-02-06: REMOVED disk load - graph loads from CARDS at boot.
            # REMOVED save_concept_graph_smart - cards are the only persistence path.
            disk_loaded = 0

            # Enrich from SRM (read-only from SRM files, writes to graph in memory)
            stats = load_srm_into_graph(graph, days_back=days_back, max_files=max_files)

            # NO save - cards handle persistence via AssociationCortexFairy

            # Call callback if provided
            if callback:
                try:
                    callback({
                        "loaded_from_disk": disk_loaded,
                        "loaded_from_srm": stats,
                        "completed": True,
                    })
                except Exception:
                    pass

            self._load_stats = {"disk": disk_loaded, "srm": stats}
            self._currently_loading = None

            return {
                "op": "graph_load",
                "disk_loaded": disk_loaded,
                "srm_stats": stats,
                "completed": True,
            }

        except Exception as e:
            self._log(f"Graph load error: {e}")
            self._currently_loading = None
            return {"op": "graph_load", "error": str(e)}

    def get_load_stats(self) -> Dict[str, Any]:
        """Get the last load statistics"""
        return self._load_stats


# ══════════════════════════════════════════════════════════════════════════════
# SINGLETON & HELPERS
# ══════════════════════════════════════════════════════════════════════════════

_main_colony: Optional[CellColony] = None
_colony_lock = threading.Lock()


def get_cell_colony() -> CellColony:
    """Get or create the main cell colony"""
    global _main_colony
    with _colony_lock:
        if _main_colony is None:
            _main_colony = CellColony("Akashic")
            # Register default cell types
            _main_colony.register_cell_type("compute", ComputeCell)
            _main_colony.register_cell_type("memory", MemoryCell)
            _main_colony.register_cell_type("guard", GuardCell)
            _main_colony.register_cell_type("graph_loader", GraphLoaderCell)
        return _main_colony


def spawn_compute_cell(cell_id: str = None, **kwargs) -> ComputeCell:
    """Convenience: spawn a compute cell"""
    return get_cell_colony().spawn_cell("compute", cell_id, **kwargs)


def spawn_memory_cell(cell_id: str = None, **kwargs) -> MemoryCell:
    """Convenience: spawn a memory cell"""
    return get_cell_colony().spawn_cell("memory", cell_id, **kwargs)


def spawn_guard_cell(cell_id: str = None, **kwargs) -> GuardCell:
    """Convenience: spawn a guard cell"""
    return get_cell_colony().spawn_cell("guard", cell_id, **kwargs)


def spawn_graph_loader_cell(cell_id: str = None, **kwargs) -> GraphLoaderCell:
    """Convenience: spawn a graph loader cell"""
    return get_cell_colony().spawn_cell("graph_loader", cell_id, **kwargs)


def get_or_spawn_graph_loader() -> GraphLoaderCell:
    """Get the shared graph loader cell, creating if needed"""
    colony = get_cell_colony()
    cell = colony.get_cell("shared_graph_loader")
    if cell is None:
        cell = spawn_graph_loader_cell("shared_graph_loader")
        if not colony._running:
            colony.start()
    return cell


# ══════════════════════════════════════════════════════════════════════════════
# TEST
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 60)
    print("WorkerCell Colony Test")
    print("=" * 60)

    colony = get_cell_colony()

    # Spawn some cells
    compute1 = spawn_compute_cell("compute_1")
    compute2 = spawn_compute_cell("compute_2")
    memory1 = spawn_memory_cell("memory_1")
    guard1 = spawn_guard_cell("guard_1")

    # Start the colony
    colony.start()

    # Let it run for a few seconds
    print("\nColony running for 5 seconds...")
    time.sleep(5)

    # Check status
    print("\n" + "=" * 60)
    print("Colony Status:")
    print("=" * 60)
    import json
    print(json.dumps(colony.get_status(), indent=2))

    print("\nCell Statuses:")
    for cell_id, cell in colony._cells.items():
        status = cell.get_status()
        print(f"\n{cell_id}:")
        print(f"  State: {status['state']}")
        print(f"  Cycles: {status['health']['cycles']}")
        print(f"  Work Done: {status['health']['work_done']}")
        print(f"  GPU Util: {status['health']['gpu_utilization']}%")

    # Stop
    colony.stop()
    print("\n[OK] Test complete")
