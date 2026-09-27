"""
CortexFarm — BatteryFarm rewired for graph compute.

The BatteryFarm had perfect infrastructure: energy budgets, gravitational
amplification, relay workers, time compression. It was built for RWKV
matrix multiplies, but RWKV is no longer used. ALL compute goes through
the cortex now.

This module replaces the RWKV engine with graph operations.
The battery still discharges — but into graph operations (bind, spread,
query) instead of matvecs. Energy IS computation. The discharge IS the
thought. Nothing changes philosophically.

Architecture:
    CortexFarm
      +-- SharedGraphStore (concept graph from portal interior)
      +-- CortexWorker[0]: GraphChargeUnit + CortexGraphEngine + activation state
      +-- CortexWorker[1]: GraphChargeUnit + CortexGraphEngine + activation state
      +-- RelayScheduler (highest-charge-first, from BatteryFarm)

Triple Feedback Loop (preserved from BatteryFarm):
    gravity = sum(charge_fraction for each worker)  [0 → num_workers]

    Loop 1 — Time Compression:
        compression = 1 + gravity * compression_coeff
        Faster inner clock → more graph ops per tick → sustained gravity

    Loop 2 — FLOPS Amplification:
        effective_cost = base_cost / (1 + gravity * flops_coeff)
        More gravity → cheaper graph ops → more thinking per charge

    Loop 3 — Energy Amplification:
        amplified_energy = paradox_pulse * time_compression
        More compression → more energy per pulse → faster recharge

Created: 2026-03-15
Authors: Nous + Ace
"""

import time
import threading
import queue
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

from cortex_graph_engine import CortexGraphEngine, GraphChargeUnit


# ═══════════════════════════════════════════════════════════════════════════════
# WORKER STATE & STATS
# ═══════════════════════════════════════════════════════════════════════════════

class WorkerState(Enum):
    """States a CortexWorker can be in."""
    IDLE = "idle"           # Charged and ready
    COMPUTING = "computing" # Actively running graph ops
    DEPLETED = "depleted"   # Battery empty, waiting for recharge
    RECHARGING = "recharging"  # Receiving energy, not yet ready


@dataclass
class WorkerStats:
    """Lifetime stats for a CortexWorker."""
    total_collisions: int = 0
    total_spreads: int = 0
    total_queries: int = 0
    total_relay_sends: int = 0
    total_relay_receives: int = 0
    total_ops: int = 0
    last_active_ts: float = 0.0


# ═══════════════════════════════════════════════════════════════════════════════
# CORTEX WORKER — Battery + Graph Engine pair
# ═══════════════════════════════════════════════════════════════════════════════

class CortexWorker:
    """A single battery-powered graph compute worker.

    Each worker has its own GraphChargeUnit and CortexGraphEngine.
    When its battery runs low during a thought (spreading activation),
    it exports its activation state for relay to the next charged worker.
    """

    def __init__(self, worker_id: int, battery: GraphChargeUnit,
                 engine: CortexGraphEngine, recharge_rate: float = 0.01):
        self.worker_id = worker_id
        self.battery = battery
        self.engine = engine
        self.state = WorkerState.IDLE
        self.stats = WorkerStats()
        self._lock = threading.Lock()

    @property
    def charge(self) -> float:
        return self.battery.charge_level

    @property
    def charge_fraction(self) -> float:
        return self.battery.charge_fraction

    @property
    def is_available(self) -> bool:
        return self.state == WorkerState.IDLE and self.battery.is_charged

    def tick_recharge(self):
        """Passive recharge — called from farm's compressed tick loop."""
        self.battery.tick_recharge()
        # State transitions
        if self.state == WorkerState.DEPLETED and self.battery.charge_level > 0.1:
            self.state = WorkerState.RECHARGING
        if self.state == WorkerState.RECHARGING and self.battery.charge_fraction > 0.5:
            self.state = WorkerState.IDLE

    # ── Graph Operations (dispatch to engine) ──

    def process_collision(self, recall_tags: List[str],
                          ingest_tags: List[str],
                          weight: float = 0.5) -> Dict[str, Any]:
        """Process a collision binding — the core cognitive operation."""
        with self._lock:
            self.state = WorkerState.COMPUTING
            self.stats.last_active_ts = time.time()

            result = self.engine.discharge_collision(recall_tags, ingest_tags, weight)
            self.stats.total_collisions += 1
            self.stats.total_ops += result.get("bound", 0)

            if not self.battery.is_charged:
                self.state = WorkerState.DEPLETED
            else:
                self.state = WorkerState.IDLE
            return result

    def process_spread(self, start_node: str, depth: int = 3,
                       top_k: int = 10) -> List[Tuple[str, float]]:
        """Spreading activation — following associations through the graph."""
        with self._lock:
            self.state = WorkerState.COMPUTING
            self.stats.last_active_ts = time.time()

            result = self.engine.discharge_spread(start_node, depth, top_k)
            self.stats.total_spreads += 1

            if not self.battery.is_charged:
                self.state = WorkerState.DEPLETED
            else:
                self.state = WorkerState.IDLE
            return result

    def process_query(self, concept: str, k: int = 5) -> List[str]:
        """Find nearest concepts — quick graph lookup."""
        with self._lock:
            self.state = WorkerState.COMPUTING
            self.stats.last_active_ts = time.time()

            result = self.engine.discharge_query(concept, k)
            self.stats.total_queries += 1

            if not self.battery.is_charged:
                self.state = WorkerState.DEPLETED
            else:
                self.state = WorkerState.IDLE
            return result

    # ── Relay Handoff ──

    def export_state(self) -> Dict[str, Any]:
        """Export activation state for relay to next worker."""
        self.stats.total_relay_sends += 1
        return self.engine.export_state()

    def receive_state(self, state: Dict[str, Any]):
        """Import activation state from previous worker."""
        self.stats.total_relay_receives += 1
        self.engine.receive_state(state)

    def status(self) -> Dict[str, Any]:
        """Diagnostic status."""
        return {
            "worker_id": self.worker_id,
            "state": self.state.value,
            "charge": round(self.battery.charge_level, 3),
            "charge_pct": round(self.charge_fraction * 100, 1),
            "engine": self.engine.status(),
            "stats": {
                "collisions": self.stats.total_collisions,
                "spreads": self.stats.total_spreads,
                "queries": self.stats.total_queries,
                "relay_sends": self.stats.total_relay_sends,
                "relay_receives": self.stats.total_relay_receives,
                "total_ops": self.stats.total_ops,
            },
        }


# ═══════════════════════════════════════════════════════════════════════════════
# CORTEX FARM — The Brain
# ═══════════════════════════════════════════════════════════════════════════════

class CortexFarm:
    """Multi-worker graph compute farm with relay scheduling and gravitational amplification.

    Adapted from BatteryFarm. Instead of RWKV inference, workers perform
    graph operations (bind, spread, query) powered by charge discharge.

    The triple feedback loop:
        gravity = sum(charge_fraction for each worker)

        1. Time Compression:  compression = 1 + gravity * compression_coeff
           → More charged workers → faster inner clock → more ops per tick
        2. Cost Reduction:    effective_cost = base_cost / (1 + gravity * flops_coeff)
           → More gravity → cheaper operations → more thinking per charge
        3. Energy Amplification: energy_in * time_compression
           → More compression → bigger energy pulses → faster recharge

    Usage:
        farm = CortexFarm(num_workers=4, graph_store=portal_gate)
        result = farm.submit_collision(recall_tags, ingest_tags)
        activations = farm.submit_spread("concept_key", depth=3)
        nearest = farm.submit_query("concept_key", k=5)
    """

    def __init__(self,
                 num_workers: int = 4,
                 graph_store: Any = None,
                 max_charge: float = 20.0,
                 recharge_rate: float = 0.01,
                 compression_coeff: float = 8.0,  # FIX 2026-03-19: Doubled (was 4.0) for faster convergence
                 flops_gravity_coeff: float = 1.5,
                 base_hz: float = 20.0):
        """
        Args:
            num_workers: Number of cortex workers (battery+engine pairs)
            graph_store: The concept graph (ConceptGraph, portal stub, etc.)
            max_charge: Maximum charge per worker battery
            recharge_rate: Charge per passive tick per worker
            compression_coeff: Multiplier for time compression (Loop 1)
            flops_gravity_coeff: Multiplier for cost reduction (Loop 2)
            base_hz: Base tick rate before compression
        """
        self.num_workers = num_workers
        self._graph_store = graph_store
        self._max_charge = max_charge
        self._recharge_rate = recharge_rate
        self.compression_coeff = compression_coeff
        self.flops_gravity_coeff = flops_gravity_coeff
        self.base_hz = base_hz

        # Workers
        self.workers: List[CortexWorker] = []
        self._build_workers()

        # Work queue for async dispatch
        self._work_queue: queue.Queue = queue.Queue(maxsize=4096)
        self._running = False
        self._tick_thread: Optional[threading.Thread] = None
        self._dispatch_thread: Optional[threading.Thread] = None

        # Metrics
        self._total_collisions = 0
        self._total_spreads = 0
        self._total_queries = 0
        self._total_relays = 0
        self._total_energy_received = 0.0
        self._start_ts = time.time()

    def _build_workers(self):
        """Create N cortex workers, each with its own battery and engine."""
        for i in range(self.num_workers):
            battery = GraphChargeUnit(
                max_charge=self._max_charge,
                initial_charge=self._max_charge,
                recharge_rate=self._recharge_rate,
                trace_id=f"cortex-worker-{i}",
            )
            engine = CortexGraphEngine(
                graph_store=self._graph_store,
                battery=battery,
            )
            worker = CortexWorker(
                worker_id=i,
                battery=battery,
                engine=engine,
                recharge_rate=self._recharge_rate,
            )
            self.workers.append(worker)

    # ─── Gravity & Feedback Loops ─────────────────────────────────────────

    @property
    def gravity(self) -> float:
        """Total gravitational pull. Range: 0.0 to num_workers.

        Sum of charge fractions across all workers.
        Full charge on all workers = maximum gravity = maximum amplification.
        """
        return sum(w.charge_fraction for w in self.workers)

    @property
    def time_dilation(self) -> float:
        """Normalized gravity (0.0 to 1.0)."""
        return self.gravity / self.num_workers if self.num_workers > 0 else 0.0

    @property
    def time_compression(self) -> float:
        """How many inner ticks per outer tick.

        Loop 1: compression = 1 + gravity * compression_coeff
        At 4 workers fully charged: 1 + 4.0 * 4.0 = 17x inner clock
        At 8 workers fully charged: 1 + 8.0 * 4.0 = 33x inner clock
        """
        return 1.0 + self.gravity * self.compression_coeff

    @property
    def effective_hz(self) -> float:
        """Effective tick rate after time compression."""
        return self.base_hz * self.time_compression

    @property
    def cost_reduction(self) -> float:
        """Cost divisor for graph operations.

        Loop 2: ops cost less when gravity is high.
        effective_cost = base_cost / cost_reduction
        At 4 workers: 1 + 4.0 * 1.5 = 7.0 (ops are 7x cheaper)
        At 8 workers: 1 + 8.0 * 1.5 = 13.0 (ops are 13x cheaper)
        """
        return 1.0 + self.gravity * self.flops_gravity_coeff

    # ─── Worker Selection (RelayScheduler) ────────────────────────────────

    def _pick_worker(self) -> Optional[CortexWorker]:
        """Pick the highest-charge available worker."""
        available = [w for w in self.workers if w.is_available]
        if not available:
            return None
        return max(available, key=lambda w: w.charge)

    def _pick_next_relay(self, exclude_id: int) -> Optional[CortexWorker]:
        """Pick next relay worker (highest charge, excluding current)."""
        candidates = [
            w for w in self.workers
            if w.worker_id != exclude_id and w.battery.is_charged
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda w: w.charge)

    # ─── Submit Operations ────────────────────────────────────────────────

    def submit_collision(self, recall_tags: List[str],
                         ingest_tags: List[str],
                         weight: float = 0.5) -> Dict[str, Any]:
        """Submit a collision binding to the farm.

        Picks the highest-charge worker and processes the collision.
        If the worker depletes mid-collision (very large binding set),
        relays to the next available worker.

        Returns dict with status and total bindings made.
        """
        worker = self._pick_worker()
        if worker is None:
            return {"status": "no_workers", "bound": 0}

        # Apply gravity-based cost reduction
        self._apply_cost_reduction()

        result = worker.process_collision(recall_tags, ingest_tags, weight)
        self._total_collisions += 1

        # Relay if depleted mid-collision (unlikely for small collisions)
        if result["status"] == "low_power" and result["bound"] < result["pairs"]:
            relay_worker = self._pick_next_relay(worker.worker_id)
            if relay_worker:
                relay_worker.receive_state(worker.export_state())
                remaining_recall = recall_tags[result["bound"] // len(ingest_tags):]
                remaining_ingest = ingest_tags
                relay_result = relay_worker.process_collision(
                    remaining_recall, remaining_ingest, weight
                )
                result["bound"] += relay_result.get("bound", 0)
                result["status"] = relay_result.get("status", "relay")
                result["relayed"] = True
                self._total_relays += 1

        # Restore base costs
        self._restore_base_costs()
        return result

    def submit_spread(self, start_node: str, depth: int = 3,
                      top_k: int = 10) -> List[Tuple[str, float]]:
        """Submit a spreading activation to the farm.

        Picks highest-charge worker for the spread. If the worker
        depletes mid-spread, exports activation frontier and relays
        to the next charged worker — the thought continues seamlessly.

        Returns list of (concept_key, activation_level).
        """
        worker = self._pick_worker()
        if worker is None:
            return []

        self._apply_cost_reduction()

        results = worker.process_spread(start_node, depth, top_k)
        self._total_spreads += 1

        # Relay if battery depleted mid-spread (frontier still active)
        if worker.state == WorkerState.DEPLETED and worker.engine.traversal_frontier:
            relay_worker = self._pick_next_relay(worker.worker_id)
            if relay_worker:
                relay_worker.receive_state(worker.export_state())
                # Continue spread from where previous worker stopped
                remaining_depth = max(1, depth - len(results) // max(1, top_k))
                relay_results = relay_worker.process_spread(
                    start_node, remaining_depth, top_k
                )
                # Merge results
                merged = dict(results + relay_results)
                results = sorted(merged.items(), key=lambda x: -x[1])[:top_k]
                self._total_relays += 1

        self._restore_base_costs()
        return results

    def submit_query(self, concept: str, k: int = 5) -> List[str]:
        """Submit a nearest-neighbor query to the farm.

        Quick lookup — usually doesn't need relay.
        Returns list of concept keys.
        """
        worker = self._pick_worker()
        if worker is None:
            return []

        self._apply_cost_reduction()
        results = worker.process_query(concept, k)
        self._total_queries += 1
        self._restore_base_costs()
        return results

    # ─── Cost Reduction (Loop 2) ──────────────────────────────────────────

    def _apply_cost_reduction(self):
        """Apply gravity-based cost reduction to all workers' engines."""
        reduction = self.cost_reduction
        for w in self.workers:
            w.engine.BASE_BIND_COST = CortexGraphEngine.BASE_BIND_COST / reduction
            w.engine.SPREAD_COST_PER_HOP = CortexGraphEngine.SPREAD_COST_PER_HOP / reduction
            w.engine.QUERY_COST_PER_K = CortexGraphEngine.QUERY_COST_PER_K / reduction
            w.engine.COLLISION_COST_PER_PAIR = CortexGraphEngine.COLLISION_COST_PER_PAIR / reduction

    def _restore_base_costs(self):
        """Restore base costs (called after each operation)."""
        for w in self.workers:
            w.engine.BASE_BIND_COST = CortexGraphEngine.BASE_BIND_COST
            w.engine.SPREAD_COST_PER_HOP = CortexGraphEngine.SPREAD_COST_PER_HOP
            w.engine.QUERY_COST_PER_K = CortexGraphEngine.QUERY_COST_PER_K
            w.engine.COLLISION_COST_PER_PAIR = CortexGraphEngine.COLLISION_COST_PER_PAIR

    # ─── Energy Input (Loop 3) ────────────────────────────────────────────

    def receive_energy(self, amount: float, source: str = "paradox"):
        """Receive energy from paradox energy pipeline.

        Loop 3: Energy amplified by time compression before distribution.
        Workers with lower charge get proportionally more energy.
        """
        # Amplify by time compression
        amplified = amount * self.time_compression
        self._total_energy_received += amplified

        # Distribute weighted by need (lower charge = higher need)
        total_need = sum(
            w.battery.max_charge - w.battery.charge_level
            for w in self.workers
        )
        if total_need <= 0:
            return  # All workers full

        for w in self.workers:
            need = w.battery.max_charge - w.battery.charge_level
            if need > 0:
                share = amplified * (need / total_need)
                w.battery.charge(share, source=source)

    # ─── Tick Loop (compressed time) ──────────────────────────────────────

    def start(self):
        """Start the farm's background tick and dispatch loops."""
        if self._running:
            return
        self._running = True

        self._tick_thread = threading.Thread(
            target=self._tick_loop,
            daemon=True,
            name="cortex-farm-tick",
        )
        self._tick_thread.start()
        print(f"[CortexFarm] Started with {self.num_workers} workers, "
              f"max_charge={self._max_charge}, "
              f"compression_coeff={self.compression_coeff}")

    def stop(self):
        """Stop the farm's background loops."""
        self._running = False

    def _tick_loop(self):
        """Background tick loop with time-compressed recharge.

        Loop 1: Time compression → more recharge ticks per outer tick.
        At gravity=8, compression=33x → 33 recharge iterations per outer tick.
        """
        interval = 1.0 / self.base_hz  # Base tick interval
        while self._running:
            try:
                # Time-compressed recharge
                compression = self.time_compression
                full_ticks = int(compression)
                frac = compression - full_ticks

                for _ in range(full_ticks):
                    for w in self.workers:
                        w.tick_recharge()

                # Probabilistic fractional tick
                import random
                if random.random() < frac:
                    for w in self.workers:
                        w.tick_recharge()

                time.sleep(interval)
            except Exception as e:
                print(f"[CortexFarm] Tick error: {e}")
                time.sleep(0.1)

    # ─── Status & Diagnostics ─────────────────────────────────────────────

    def status(self) -> Dict[str, Any]:
        """Full farm status for monitoring and GUI."""
        return {
            "num_workers": self.num_workers,
            "gravity": round(self.gravity, 3),
            "time_compression": round(self.time_compression, 1),
            "cost_reduction": round(self.cost_reduction, 1),
            "effective_hz": round(self.effective_hz, 1),
            "running": self._running,
            "uptime_sec": round(time.time() - self._start_ts, 1),
            "totals": {
                "collisions": self._total_collisions,
                "spreads": self._total_spreads,
                "queries": self._total_queries,
                "relays": self._total_relays,
                "energy_received": round(self._total_energy_received, 4),
            },
            "workers": [w.status() for w in self.workers],
        }

    def summary(self) -> str:
        """One-line summary for logging."""
        charged = sum(1 for w in self.workers if w.battery.is_charged)
        return (
            f"[CortexFarm] {charged}/{self.num_workers} charged, "
            f"gravity={self.gravity:.1f}, "
            f"compression={self.time_compression:.0f}x, "
            f"ops={self._total_collisions + self._total_spreads + self._total_queries}"
        )
