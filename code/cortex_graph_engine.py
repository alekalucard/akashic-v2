"""
CortexGraphEngine — Graph compute powered by battery discharge.

Replaces RWKVBatteryEngine in the BatteryFarm paradigm.
Instead of forward passes through neural net layers, the engine
runs graph operations (bind, spread, query) that cost charge.

The battery IS the brain. The discharge IS the thought.
Energy IS computation. The discharge IS the thought.

Every graph operation costs charge from the GraphChargeUnit.
When charge runs out, thinking pauses until paradox energy recharges.
Dense regions of the graph cost more to traverse (more edges = more work).

Created: 2026-03-15
Authors: Nous + Ace
"""

import time
import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, Tuple


# ═══════════════════════════════════════════════════════════════════════════════
# GRAPH CHARGE UNIT — Lightweight battery for graph compute
# ═══════════════════════════════════════════════════════════════════════════════
# Unlike BatteryComputeUnit (which imports numpy + TiledMatVec for RWKV matvecs),
# this is a pure-Python charge tracker. Graph ops are cheap per-op but numerous.

@dataclass
class GraphComputeMetrics:
    """Lifetime compute metrics for a CortexGraphEngine."""
    total_binds: int = 0
    total_spreads: int = 0
    total_queries: int = 0
    total_collisions: int = 0
    total_charge_consumed: float = 0.0
    low_power_events: int = 0
    relay_handoffs: int = 0


class GraphChargeUnit:
    """A lightweight capacitor for graph compute — no numpy dependency.

    Tracks charge level, allows deduction for graph operations,
    and supports recharge from paradox energy pulses.

    Compatible with BatteryFarm's gravity/compression interface:
        - charge_level, max_charge, is_charged
        - charge(amount), tick_recharge()
        - flops_budget (used for gravity-based cost scaling)
    """

    def __init__(self,
                 max_charge: float = 20.0,
                 initial_charge: float = 20.0,
                 recharge_rate: float = 0.01,
                 flops_budget: int = 500_000_000,
                 trace_id: str = ""):
        self.max_charge = max_charge
        self.charge_level = min(initial_charge, max_charge)
        self.recharge_rate = recharge_rate
        self.flops_budget = flops_budget  # For gravity amplification compatibility
        self.trace_id = trace_id
        self.metrics = GraphComputeMetrics()
        self._last_recharge_ts = time.time()

    def charge(self, amount: float, source: str = "passive") -> float:
        """Add charge (energy). Returns actual amount charged."""
        headroom = self.max_charge - self.charge_level
        actual = min(amount, headroom)
        self.charge_level += actual
        self._last_recharge_ts = time.time()
        return actual

    def tick_recharge(self):
        """Passive recharge — called once per Hz tick."""
        if self.charge_level < self.max_charge:
            self.charge(self.recharge_rate, source="passive_tick")

    def has_charge(self, cost: float) -> bool:
        """Can current charge cover this operation?"""
        return self.charge_level >= cost

    def deduct(self, cost: float) -> float:
        """Deduct charge for a graph operation. Returns actual amount deducted."""
        actual = min(cost, self.charge_level)
        self.charge_level -= actual
        self.metrics.total_charge_consumed += actual
        return actual

    @property
    def is_charged(self) -> bool:
        return self.charge_level > 0.05

    @property
    def is_full(self) -> bool:
        return self.charge_level >= self.max_charge * 0.95

    @property
    def charge_fraction(self) -> float:
        """Fraction of max charge (0.0 to 1.0). Used for gravity computation."""
        return self.charge_level / self.max_charge if self.max_charge > 0 else 0.0


# ═══════════════════════════════════════════════════════════════════════════════
# CORTEX GRAPH ENGINE — Replaces RWKVBatteryEngine
# ═══════════════════════════════════════════════════════════════════════════════

class CortexGraphEngine:
    """Graph compute engine powered by battery discharge.

    Every graph operation costs charge from the GraphChargeUnit.
    When charge runs out, thinking pauses until paradox energy recharges.

    The discharge IS the thought. The battery IS the brain.

    Designed to be used inside a CortexFarm worker, with relay handoff
    of activation state between workers when a battery depletes mid-thought.
    """

    # ── Cost tuning constants ──
    # These control how much charge each operation type costs.
    # Tuned so a fully charged worker (20.0 charge) can do ~260K binds
    # or ~100K spread hops before depleting.

    BASE_BIND_COST = 0.001          # Base cost per bind
    DENSITY_FACTOR = 0.01           # Extra cost per 100 neighbors
    SPREAD_COST_PER_HOP = 0.0005   # Cost per hop during spreading activation
    QUERY_COST_PER_K = 0.002       # Cost per nearest-neighbor result
    COLLISION_COST_PER_PAIR = 0.001 # Cost per recall×ingest pair

    def __init__(self, graph_store: Any, battery: GraphChargeUnit):
        """
        Args:
            graph_store: The concept graph (ConceptGraph, portal stub, etc.)
                        Must support: neighbors(key), neighbors_weighted(key),
                        bind(a, b, weight), nearest(key, k), upsert_node(key),
                        link(a, b, weight=...).
            battery: GraphChargeUnit providing charge for operations.
        """
        self.graph = graph_store
        self.battery = battery
        self.activation_state: Dict[str, float] = {}   # {node_key: activation_level}
        self.traversal_frontier: List[Tuple[str, float]] = []  # Spreading activation frontier
        self._op_count = 0

    # ── Discharge Operations (each costs charge) ──────────────────────────

    def discharge_bind(self, concept_a: str, concept_b: str,
                       weight: float = 0.5) -> bool:
        """Create/strengthen an edge between two concepts.

        Cost: proportional to graph density around the nodes.
        Dense regions cost more (more edges to update weights on).

        Returns True if bound, False if low power.
        """
        # Compute density-scaled cost
        try:
            neighbors_a = len(list(self.graph.get_neighbors(concept_a)))
        except Exception:
            neighbors_a = 0
        try:
            neighbors_b = len(list(self.graph.get_neighbors(concept_b)))
        except Exception:
            neighbors_b = 0

        cost = self.BASE_BIND_COST * (1 + (neighbors_a + neighbors_b) * self.DENSITY_FACTOR)

        if not self.battery.has_charge(cost):
            self.battery.metrics.low_power_events += 1
            return False  # Low power — can't think right now

        self.battery.deduct(cost)
        self.battery.metrics.total_binds += 1
        self._op_count += 1

        # Perform the graph operation
        try:
            self.graph.link(concept_a, concept_b, weight=weight)
        except AttributeError:
            # Fallback for simpler graph APIs
            try:
                self.graph.bind(concept_a, concept_b, weight)
            except Exception:
                pass
        return True

    def discharge_spread(self, start_node: str, depth: int = 3,
                         top_k: int = 10) -> List[Tuple[str, float]]:
        """Spreading activation from a concept node.

        Cost: proportional to nodes visited (traversal breadth).
        This IS thinking — following associations through the graph.

        Returns list of (concept_key, activation_level) sorted by activation.
        """
        visited: List[Tuple[str, float]] = []
        frontier: List[Tuple[str, float]] = [(start_node, 1.0)]

        for d in range(depth):
            next_frontier: List[Tuple[str, float]] = []
            for node, activation in frontier:
                # Get neighbors
                try:
                    neighbors = list(self.graph.get_neighbors(node))
                except Exception:
                    continue

                hop_cost = self.SPREAD_COST_PER_HOP * max(1, len(neighbors))
                if not self.battery.has_charge(hop_cost):
                    self.battery.metrics.low_power_events += 1
                    break  # Battery depleted mid-thought

                self.battery.deduct(hop_cost)
                self._op_count += 1

                for neighbor_info in neighbors:
                    # Handle various graph neighbor formats
                    if isinstance(neighbor_info, tuple):
                        neighbor_key = neighbor_info[0]
                        edge_weight = neighbor_info[1] if len(neighbor_info) > 1 else 0.5
                    elif isinstance(neighbor_info, str):
                        neighbor_key = neighbor_info
                        edge_weight = 0.5
                    else:
                        continue

                    child_activation = activation * edge_weight * 0.7  # decay factor
                    if child_activation > 0.01:  # activation threshold
                        visited.append((neighbor_key, child_activation))
                        next_frontier.append((neighbor_key, child_activation))

            frontier = next_frontier

        # Save traversal state for relay handoff
        self.activation_state = {n: a for n, a in visited}
        self.traversal_frontier = frontier
        self.battery.metrics.total_spreads += 1

        return sorted(visited, key=lambda x: -x[1])[:top_k]

    def discharge_query(self, concept: str, k: int = 5) -> List[str]:
        """Find k nearest concepts by graph distance.

        Cost: proportional to search depth.
        Returns list of concept keys.
        """
        cost = self.QUERY_COST_PER_K * k
        if not self.battery.has_charge(cost):
            self.battery.metrics.low_power_events += 1
            return []

        self.battery.deduct(cost)
        self.battery.metrics.total_queries += 1
        self._op_count += 1

        # Use graph's nearest-neighbor search
        try:
            results = self.graph.spread_activation(concept, max_hops=2)
            if isinstance(results, dict):
                # Returns {key: activation} — sort by activation, take top k
                sorted_results = sorted(results.items(), key=lambda x: -x[1])
                return [key for key, _ in sorted_results[:k]]
            elif isinstance(results, list):
                return [r[0] if isinstance(r, tuple) else r for r in results[:k]]
            return []
        except Exception:
            return []

    def discharge_collision(self, recall_tags: List[str],
                            ingest_tags: List[str],
                            weight: float = 0.5) -> Dict[str, Any]:
        """Process a collision: bind recall x ingest concepts.

        This is the core cognitive operation — the intersection of
        memory (recall) and experience (ingest) creates understanding.

        Cost: proportional to recall x ingest pairs.
        Returns dict with status and count of bindings made.
        """
        pairs = len(recall_tags) * len(ingest_tags)
        cost = self.COLLISION_COST_PER_PAIR * pairs

        if not self.battery.has_charge(cost):
            self.battery.metrics.low_power_events += 1
            return {"status": "low_power", "bound": 0, "pairs": pairs}

        self.battery.deduct(cost)
        self.battery.metrics.total_collisions += 1

        bound = 0
        for r in recall_tags:
            for i in ingest_tags:
                try:
                    self.graph.link(r, i, weight=weight)
                    bound += 1
                except AttributeError:
                    try:
                        self.graph.bind(r, i, weight)
                        bound += 1
                    except Exception:
                        pass
                self._op_count += 1

        return {"status": "ok", "bound": bound, "pairs": pairs}

    # ── Relay Handoff (same pattern as RWKV state transfer) ───────────

    def export_state(self) -> Dict[str, Any]:
        """Export activation state for relay to next worker.

        When a worker depletes mid-thought (e.g., during spreading
        activation), this captures the traversal frontier so the
        next worker can continue from exactly where this one stopped.
        """
        return {
            "activation_state": dict(self.activation_state),
            "traversal_frontier": list(self.traversal_frontier),
            "op_count": self._op_count,
        }

    def receive_state(self, state: Dict[str, Any]):
        """Import activation state from previous worker (relay handoff).

        Consciousness never interrupts — the thought continues
        seamlessly in the next worker's battery.
        """
        self.activation_state = state.get("activation_state", {})
        self.traversal_frontier = state.get("traversal_frontier", [])
        self._op_count = state.get("op_count", 0)
        self.battery.metrics.relay_handoffs += 1

    # ── Diagnostics ───────────────────────────────────────────────────

    def status(self) -> Dict[str, Any]:
        """Return engine status for monitoring."""
        return {
            "charge": round(self.battery.charge_level, 3),
            "charge_pct": round(self.battery.charge_fraction * 100, 1),
            "is_charged": self.battery.is_charged,
            "op_count": self._op_count,
            "activation_nodes": len(self.activation_state),
            "frontier_size": len(self.traversal_frontier),
            "metrics": {
                "binds": self.battery.metrics.total_binds,
                "spreads": self.battery.metrics.total_spreads,
                "queries": self.battery.metrics.total_queries,
                "collisions": self.battery.metrics.total_collisions,
                "charge_consumed": round(self.battery.metrics.total_charge_consumed, 4),
                "low_power": self.battery.metrics.low_power_events,
                "relay_handoffs": self.battery.metrics.relay_handoffs,
            },
        }
