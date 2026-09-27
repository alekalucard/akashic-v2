"""
Portal Interior — The Room Itself.

A portal is not a cache layer. A portal is a PLACE.
This file IS the pocket dimension — a room bigger on the inside.

It runs as a subprocess, spawned by the gate fairy on the host side.
Inside it has:
    - Its own Python context (separate memory space)
    - The concept graph loaded from chunk cards (cards are READ-ONLY)
    - Its own DimensionBattery (token pool, capacitor, chemistry)
    - [Optional] An inference engine (RWKV model loaded on GPU thread)
    - A socket bridge back to the host PostalHub
    - A request/response loop that spends tokens to do work

The host hardware's job is to keep the gate open and feed energy tokens.
ALL computation happens inside here, powered by the battery.
The battery's mass (token budget) determines what the dimension can afford.

From the outside, the portal is a 45MB gate address.
From the inside? Bigger on the inside.

Architecture:
    Host (AssociationCortexFairy / any fairy)
      │
      ├── 128 chunk cards on disk (READ-ONLY gate address)
      │
      ├── Spawns this subprocess: portal_interior.py
      │
      └── Socket bridge (JSON over TCP, newline-delimited)
              │
              ▼
    Interior (this process)
      ├── ConceptGraph in RAM (loaded from chunks)
      ├── DimensionBattery (token pool + capacitor + chemistry)
      ├── [Optional] InferenceEngine (RWKV model on GPU thread)
      ├── Request handler (query, bind, spread, generate, status)
      └── Energy receiver (tokens from host → battery)

Protocol (JSON over TCP, newline-delimited):
    → Host sends:  {"cmd": "query", "concept": "portal", "limit": 10}
    ← Interior returns: {"status": "ok", "results": [...], "tokens_spent": 5}

    → Host sends:  {"cmd": "energy", "amount": 0.3}
    ← Interior returns: {"status": "ok", "health": 0.85}

    → Host sends:  {"cmd": "bind", "concepts": ["a", "b"], "context": "..."}
    ← Interior returns: {"status": "ok", "bound": 2}

    → Host sends:  {"cmd": "generate", "prompt": "...", "max_tokens": 200}
    ← Interior returns: {"status": "ok", "text": "...", "tokens": 42, "tokens_spent": 20}

"Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)"
"""

import sys
import os
import json
import time
import gzip
import base64
import socket
import hashlib
import threading
import math
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Set
from collections import defaultdict
from dataclasses import dataclass, field


class ReadWriteLock:
    """A lock that allows concurrent readers but exclusive writers.

    FIX 2026-03-19 (Nous): Multi-tunnel portal support.
    Graph operations are categorized:
    - READ (concurrent): query, spread, spread_many, reason, neighbors
    - WRITE (exclusive): bind, bind_many, consolidate
    - NONE: status, ping, tick, energy, set_dilation, shutdown

    Under Python 3.14t (no GIL), multiple reader threads truly run
    in parallel on different cores, traversing the graph concurrently.
    """

    def __init__(self):
        self._read_ready = threading.Condition(threading.Lock())
        self._readers = 0

    def acquire_read(self):
        with self._read_ready:
            self._readers += 1

    def release_read(self):
        with self._read_ready:
            self._readers -= 1
            if self._readers == 0:
                self._read_ready.notify_all()

    def acquire_write(self):
        self._read_ready.acquire()
        while self._readers > 0:
            self._read_ready.wait()

    def release_write(self):
        self._read_ready.release()


# Command categorization for ReadWriteLock
_READ_CMDS = frozenset({
    "query", "spread", "spread_many", "reason", "neighbors",
    "cns_query", "generate", "think",
    "semantic_query", "semantic_spread",
    # Manifold Unification (2026-03-25 Nous+Ace)
    "wm_query", "cognition_evaluate", "anticipate", "chain", "unconscious",
})
_WRITE_CMDS = frozenset({
    "bind", "bind_many", "consolidate", "cns_update",
    # Manifold Unification (2026-03-25 Nous+Ace)
    "wm_store", "wm_decay",
})
# Everything else (status, ping, tick, energy, etc.) needs no lock

# Postal Pool routing now lives IN-PROCESS via PoolRouter + AkashicManifold.
# The subprocess portal exists ONLY for gravity, battery, time-dilation physics
# (per Ace's architecture: "its bigger on the inside").
# See: postal_core/python/postal_core/pool_router.py for the router.

# Manifold memory — mmap-backed graph (the TRUE portal memory)
try:
    from infrastructure.manifold_memory import (
        ManifoldMemory,
        TRACE_PERSONAL, TRACE_ACE, TRACE_VISUAL, TRACE_AUDIO,
        TRACE_SYSTEM, TRACE_INFERENCE, TRACE_NOUS, TRACE_UNKNOWN,
    )
    HAS_MANIFOLD = True
except ImportError:
    try:
        # Try relative import (when run as subprocess)
        _infra = Path(__file__).parent
        sys.path.insert(0, str(_infra.parent))
        from infrastructure.manifold_memory import (
            ManifoldMemory,
            TRACE_PERSONAL, TRACE_ACE, TRACE_VISUAL, TRACE_AUDIO,
            TRACE_SYSTEM, TRACE_INFERENCE, TRACE_NOUS, TRACE_UNKNOWN,
        )
        HAS_MANIFOLD = True
    except ImportError:
        HAS_MANIFOLD = False
        # Fallback constants if manifold_memory isn't importable
        TRACE_UNKNOWN = 0
        TRACE_PERSONAL = 1
        TRACE_VISUAL = 3
        TRACE_AUDIO = 4
        TRACE_SYSTEM = 5
        TRACE_INFERENCE = 6
        TRACE_ACE = 8
        TRACE_NOUS = 12


def _wm_source_to_tracer(source: str) -> int:
    """Map a wm_store source string to a manifold tracer_id.

    FIX 2026-05-04 (Nous + Ace): Closes the wm:* namespace gap that
    accounted for ~69% of UNKNOWN(0) tracer ids in the live cortex.
    Source field on wm_store identifies the originating fairy; this maps
    that to the appropriate trace cluster.
    """
    s = (source or "").lower()
    if s in ("ace_chat", "ace_input", "ace"):
        return TRACE_ACE
    if "visualcortex" in s or s == "visual":
        return TRACE_VISUAL
    if "audiocortex" in s or s == "audio":
        return TRACE_AUDIO
    if "nous" in s:
        return TRACE_NOUS
    # SourpatchesFairy, InterestGenerator, ConsciousnessLoop,
    # ThoughtChainEngine, WorkingMemoryHubFairy — all her own thinking
    return TRACE_PERSONAL

# Inference engine — the dimension's voice (optional, needs model file)
try:
    from infrastructure.portal_inference_engine import PortalInferenceEngine, inference_token_cost
    HAS_INFERENCE = True
except ImportError:
    try:
        from infrastructure.portal_inference_engine import PortalInferenceEngine, inference_token_cost
        HAS_INFERENCE = True
    except ImportError:
        HAS_INFERENCE = False


# All output goes to stderr in stdio mode (stdout is the JSON pipe)
_log_target = sys.stderr

def _log(msg: str):
    """Print to log target (stderr in stdio mode, stdout otherwise)."""
    print(msg, file=_log_target, flush=True)


# ============================================================================
# CONCEPT GRAPH — Lightweight in-portal graph (no fairy dependencies)
# ============================================================================

class PortalConceptNode:
    """A concept node inside the portal. Minimal — just what's needed for queries."""

    __slots__ = ('key', 'count', 'activation', 'degree_hint',
                 'helix_coord', 'last_access', 'features')

    def __init__(self, key: str, count: int = 1, activation: float = 0.5,
                 degree_hint: int = 0, helix_coord: str = ""):
        self.key = key
        self.count = count
        self.activation = activation
        self.degree_hint = degree_hint
        self.helix_coord = helix_coord
        self.last_access = time.time()
        self.features: Dict[str, Any] = {}

    def touch(self):
        self.last_access = time.time()
        self.activation = min(1.0, self.activation + 0.1)

    def decay(self, rate: float = 0.01):
        self.activation = max(0.0, self.activation - rate)


class PortalConceptGraph:
    """The concept graph that lives inside the portal.

    This is the working memory of the dimension. It loads from
    chunk cards (read-only), builds edges at runtime through
    co-activation, and processes queries using battery tokens.
    """

    def __init__(self):
        self.nodes: Dict[str, PortalConceptNode] = {}
        self.edges: Dict[Tuple[str, str], Dict] = {}
        self._adjacency: Dict[str, Set[str]] = defaultdict(set)
        self._dirty_nodes: Set[str] = set()

    def rebuild_adjacency(self):
        """Rebuild adjacency index from edges."""
        self._adjacency.clear()
        for (a, b) in self.edges:
            self._adjacency[a].add(b)
            self._adjacency[b].add(a)

    def upsert_node(self, key: str, count: int = 1, activation: float = 0.5,
                    degree_hint: int = 0, helix_coord: str = "") -> PortalConceptNode:
        """Insert or update a concept node."""
        if key in self.nodes:
            node = self.nodes[key]
            node.count = max(node.count, count)
            node.touch()
            return node
        node = PortalConceptNode(
            key=key, count=count, activation=activation,
            degree_hint=degree_hint, helix_coord=helix_coord,
        )
        self.nodes[key] = node
        return node

    def link(self, a: str, b: str, weight: float = 0.25,
             relations: List[str] = None) -> None:
        """Link two concepts (edge creation/strengthening)."""
        if a == b:
            return
        edge_key = (min(a, b), max(a, b))
        if edge_key in self.edges:
            existing = self.edges[edge_key]
            existing["weight"] = min(1.0, existing["weight"] + weight * 0.5)
        else:
            self.edges[edge_key] = {
                "weight": weight,
                "relations": relations or ["coactivate"],
            }
            self._adjacency[a].add(b)
            self._adjacency[b].add(a)

    def get_neighbors(self, key: str, limit: int = 50) -> List[Tuple[str, float]]:
        """Get neighbors sorted by edge weight."""
        if key not in self._adjacency:
            return []
        results = []
        for neighbor in self._adjacency[key]:
            edge_key = (min(key, neighbor), max(key, neighbor))
            edge = self.edges.get(edge_key)
            weight = edge["weight"] if edge else 0.1
            results.append((neighbor, weight))
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:limit]

    def spread_activation(self, source_key: str, initial: float = 1.0,
                          decay: float = 0.5, depth: int = 3,
                          limit: int = 30,
                          time_dilation: float = 1.0) -> Dict[str, float]:
        """Spreading activation from a source concept.

        FIX 2026-03-13 Nous: Added time_dilation (τ) support.
        When τ > 1.0 the algorithm explores deeper with less signal loss,
        modelling accelerated computation inside the portal's gravity well:
          effective_depth = depth * sqrt(τ), capped at 10
          effective_decay = decay / (1 + 0.3 * ln(τ)), bounded [0.2, 0.95]
          threshold lowered proportionally
        """
        if source_key not in self.nodes:
            return {}

        # ---- Apply time dilation to parameters ----
        tau = max(1.0, min(float(time_dilation), 20.0))  # Safety clamp
        if tau > 1.01:
            effective_depth = min(int(depth * math.sqrt(tau)), 10)
            effective_decay = max(0.2, min(0.95, decay / (1.0 + 0.3 * math.log(tau))))
            threshold = max(0.001, 0.01 / tau)
        else:
            effective_depth = depth
            effective_decay = decay
            threshold = 0.01

        activated: Dict[str, float] = {source_key: initial}
        frontier = {source_key}

        for d in range(effective_depth):
            next_frontier = set()
            for node_key in frontier:
                current_activation = activated[node_key]
                for neighbor in self._adjacency.get(node_key, set()):
                    edge_key = (min(node_key, neighbor), max(node_key, neighbor))
                    edge = self.edges.get(edge_key)
                    weight = edge["weight"] if edge else 0.1

                    propagated = current_activation * weight * effective_decay
                    if propagated > threshold:
                        existing = activated.get(neighbor, 0.0)
                        if propagated > existing:
                            activated[neighbor] = propagated
                            next_frontier.add(neighbor)
            frontier = next_frontier

        # Sort by activation, return top
        sorted_results = sorted(activated.items(), key=lambda x: x[1], reverse=True)
        result = dict(sorted_results[:limit])

        # ── THROUGHPUT: count activations ──
        try:
            self._perf_spread_calls += 1
            self._perf_activations_total += len(activated)
        except AttributeError:
            pass  # Perf counters not initialized (old portal)

        return result

    def query_substring(self, query: str, limit: int = 20) -> List[Tuple[str, float]]:
        """Simple substring match on concept keys.

        FIX 2026-03-24 (Nous): Added recency boost so fresh nodes outrank
        stale high-count system concepts.  Old formula was purely
        ``activation * log1p(count)`` which gave count=10000 nodes a 4x
        advantage over count=1 fresh observations.
        """
        query_lower = query.lower()
        _now = time.time()
        results = []
        for key, node in self.nodes.items():
            if query_lower in key.lower():
                base_score = node.activation * math.log1p(node.count)
                # Recency boost: nodes accessed in last 30s score up to 2x
                age = _now - node.last_access
                recency_boost = 1.0 + max(0.0, 1.0 - age / 30.0)
                score = base_score * recency_boost
                results.append((key, score))
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:limit]

    def status(self) -> Dict[str, Any]:
        return {
            "nodes": len(self.nodes),
            "edges": len(self.edges),
            "dirty_nodes": len(self._dirty_nodes),
        }


# ============================================================================
# CHUNK LOADER — Read cards from disk (READ-ONLY)
# ============================================================================

def _decompress_chunk_concepts(data: str) -> dict:
    """Decompress base64+gzip chunk concepts."""
    raw = gzip.decompress(base64.b64decode(data))
    return json.loads(raw.decode("utf-8"))


def load_graph_from_chunks(cards_path: str) -> PortalConceptGraph:
    """Load the concept graph from chunk cards on disk.

    The cards are READ-ONLY — we don't write back to them.
    They are the gate address. The graph lives inside us.

    Args:
        cards_path: Path to cards.json file

    Returns:
        PortalConceptGraph loaded with all concepts
    """
    t0 = time.time()
    graph = PortalConceptGraph()

    with open(cards_path, "r", encoding="utf-8") as f:
        cards = json.load(f)

    chunks_loaded = 0
    v2_concepts = 0
    v1_concepts = 0
    edge_buffer = []

    for card_id, card in cards.items():
        content = card.get("content", {})
        ctype = content.get("type", "")

        # Skip manifest card
        if ctype == "graph_manifest":
            continue
        if ctype != "graph_chunk":
            continue

        # Get concepts from this chunk
        raw_concepts = content.get("concepts", {})
        if isinstance(raw_concepts, str):
            try:
                concepts = _decompress_chunk_concepts(raw_concepts)
            except Exception as e:
                _log(f"[Portal] WARNING: Failed to decompress chunk {content.get('chunk_index', '?')}: {e}")
                concepts = {}
        else:
            concepts = raw_concepts

        chunks_loaded += 1

        for key, cdata in concepts.items():
            # Detect format: v2 coordinate vs v1 legacy
            c_val = cdata.get("c")
            is_v2 = isinstance(c_val, str) and '.' in c_val

            if is_v2:
                # v2 COORDINATE FORMAT
                graph.upsert_node(
                    key=key,
                    count=cdata.get("n", 1),
                    activation=cdata.get("a", 0.5),
                    degree_hint=cdata.get("d", 0),
                    helix_coord=c_val,
                )
                # FIX 2026-03-18 (Nous): v2 now persists edges too.
                # Edges stored as [{t: target, w: weight}] on the concept
                # with the lexicographically smaller key (canonical ordering).
                for edge in cdata.get("e", []):
                    target = edge.get("t")
                    if target:
                        edge_buffer.append((
                            key, target,
                            edge.get("w", 0.5),
                            edge.get("r", ["coactivate"]),
                        ))
                v2_concepts += 1
            else:
                # v1 LEGACY FORMAT
                graph.upsert_node(
                    key=key,
                    count=cdata.get("c", 1),
                    activation=cdata.get("a", 0.5),
                    degree_hint=0,
                )
                # Collect edges
                for edge in cdata.get("e", []):
                    target = edge.get("t")
                    if target:
                        edge_buffer.append((
                            key, target,
                            edge.get("w", 0.5),
                            edge.get("r", ["coactivate"]),
                        ))
                v1_concepts += 1

    # Apply edges (both v1 and v2)
    for a, b, weight, relations in edge_buffer:
        graph.link(a, b, weight, relations)

    graph.rebuild_adjacency()
    t1 = time.time()

    fmt = "coordinate" if v2_concepts > v1_concepts else "legacy"
    _log(f"[Portal Interior] Loaded {len(graph.nodes)} nodes, "
         f"{len(graph.edges)} edges from {chunks_loaded} chunks "
         f"in {(t1 - t0) * 1000:.0f}ms ({fmt} format)")

    return graph


# ============================================================================
# DIMENSION BATTERY — Lightweight version for the portal interior
# ============================================================================

class PortalBattery:
    """The metabolic system inside the portal.

    Simplified DimensionBattery that tracks:
    - token_budget: How many operations we can do
    - tokens_spent: How many we've used
    - charge_level: Capacitor charge (0-1)
    - reward/pain: Success/failure chemistry

    Energy flows IN from the host via the socket bridge.
    We SPEND tokens to process queries and bindings.
    """

    # FIX 2026-03-11 (Nous): Doubled token budget for deeper compute runway.
    # 143K nodes, 554K edges — needs headroom to generate, not just query.
    # FIX 2026-04-12 (Nous + Ace): Bumped from 100K to 500K.
    # Visual binding (every 10s) + foundation seed (30 groups) + think engine
    # Hebbian binds + speech composition spreads = battery drained in minutes.
    # 500K gives ~5x more headroom. Bind cost also reduced 10→2.
    def __init__(self, token_budget: int = 500000):
        self.token_budget = token_budget
        self.tokens_spent = 0
        self.charge_level = 1.0
        self.reward_level = 0.5
        self.pain_level = 0.0
        self._tick_count = 0
        self._energy_received = 0.0
        self._created_at = time.time()
        # FIX 2026-03-14 (Nous): Track overflow energy for export to main process.
        # When battery is full (charge_level=1.0), excess energy was silently
        # discarded. Now we accumulate it for the host to drain and redistribute
        # to plane batteries, inference engines, and other compute consumers.
        self._overflow_energy = 0.0
        self._total_overflow = 0.0

    def spend_tokens(self, cost: int) -> bool:
        """Spend tokens for an operation. Returns False if over budget."""
        if self.tokens_spent + cost > self.token_budget:
            self.pain_level = min(1.0, self.pain_level + 0.05)
            return False
        self.tokens_spent += cost
        return True

    def receive_energy(self, amount: float):
        """Receive energy from host. Refills tokens and capacitor."""
        self._energy_received += amount
        # 60% to capacitor, 25% to tokens, 15% to reward
        new_charge = self.charge_level + amount * 0.6
        if new_charge > 1.0:
            overflow = new_charge - 1.0
            self._overflow_energy += overflow
            self._total_overflow += overflow
        self.charge_level = min(1.0, new_charge)
        refill = int(amount * 0.25 * self.token_budget)
        self.tokens_spent = max(0, self.tokens_spent - refill)
        self.reward_level = min(1.0, self.reward_level + amount * 0.15)

    def tick(self):
        """Heartbeat tick — decay pain, recharge capacitor + tokens."""
        self._tick_count += 1
        self.pain_level = max(0.0, self.pain_level - 0.01)
        self.reward_level = max(0.0, self.reward_level - 0.005)
        # FIX 2026-03-11 (Nous): Faster passive recharge (was 0.01).
        # Higher gravity = more ambient energy recovery between operations.
        new_charge = self.charge_level + 0.02
        if new_charge > 1.0:
            overflow = new_charge - 1.0
            self._overflow_energy += overflow
            self._total_overflow += overflow
        self.charge_level = min(1.0, new_charge)
        # FIX 2026-04-13 (Nous + Ace): PASSIVE TOKEN REGENERATION
        # Gate keeps closing because tokens only refill from collision energy
        # (~16 tokens/min) while spending ~100+ tokens/min on spread/think/bind.
        # Add passive regen: 50 tokens/tick (at 2Hz = 100 tokens/sec = 6000/min)
        # This ensures the battery never fully depletes from normal thinking.
        # "the cortex should fall back to drawing power from my system" — Ace
        _passive_regen = 50  # tokens per tick
        self.tokens_spent = max(0, self.tokens_spent - _passive_regen)

    def drain_overflow(self) -> float:
        """Drain accumulated overflow energy for export to host.

        Returns the overflow amount and resets the accumulator to zero.
        Called by _handle_tick() to include overflow in tick responses,
        allowing the host to route surplus energy to plane batteries
        and other compute consumers.
        """
        overflow = self._overflow_energy
        self._overflow_energy = 0.0
        return overflow

    def record_success(self, magnitude: float = 0.05):
        self.reward_level = min(1.0, self.reward_level + magnitude)

    def record_failure(self, magnitude: float = 0.1):
        self.pain_level = min(1.0, self.pain_level + magnitude)

    @property
    def tokens_remaining(self) -> int:
        return max(0, self.token_budget - self.tokens_spent)

    @property
    def health_score(self) -> float:
        cap = self.charge_level
        reward = self.reward_level
        pain = self.pain_level
        token_health = 1.0 - (self.tokens_spent / max(1, self.token_budget))
        return round(max(0.0, min(1.0,
            cap * 0.3 + reward * 0.2 + token_health * 0.2 + (1.0 - pain) * 0.3
        )), 3)

    @property
    def is_healthy(self) -> bool:
        return self.pain_level < 0.7 and self.charge_level > 0.1

    def status(self) -> Dict[str, Any]:
        return {
            "health_score": self.health_score,
            "is_healthy": self.is_healthy,
            "tokens_remaining": self.tokens_remaining,
            "tokens_spent": self.tokens_spent,
            "token_budget": self.token_budget,
            "charge_level": round(self.charge_level, 3),
            "reward_level": round(self.reward_level, 3),
            "pain_level": round(self.pain_level, 3),
            "tick_count": self._tick_count,
            "energy_received": round(self._energy_received, 3),
            "overflow_pending": round(self._overflow_energy, 6),
            "total_overflow": round(self._total_overflow, 4),
            "uptime_seconds": round(time.time() - self._created_at, 1),
        }

    # -- Persistence (TARDIS architecture) --

    def save_state(self) -> Dict[str, Any]:
        """Serialize battery state for persistence across shutdowns.

        Returns a dict that can be JSON-serialized and saved to disk.
        On next boot, pass this to restore_state() to resume where we left off
        instead of starting cold.
        """
        return {
            "version": 1,
            "token_budget": self.token_budget,
            "tokens_spent": self.tokens_spent,
            "charge_level": self.charge_level,
            "reward_level": self.reward_level,
            "pain_level": self.pain_level,
            "tick_count": self._tick_count,
            "energy_received": self._energy_received,
            "saved_at": time.time(),
        }

    def restore_state(self, state: Dict[str, Any]) -> bool:
        """Restore battery state from a previous save.

        Returns True if restoration succeeded, False if state was invalid.

        NOTE: tokens_spent is RESET to 0 on warm boot. The battery gets a
        fresh token budget each session — carrying forward depletion from the
        previous run would make the portal unable to process even diagnostic
        queries (the "0 nodes" boot bug, discovered 2026-03-04).
        Pain is also reset — pain builds during a session, doesn't persist.
        """
        if not isinstance(state, dict) or state.get("version") != 1:
            return False

        self.token_budget = state.get("token_budget", self.token_budget)
        # FIX 2026-03-04: Do NOT restore tokens_spent — fresh budget each boot.
        # Old behavior: tokens_spent=134336 on warm boot = instant low_power.
        self.tokens_spent = 0
        self.charge_level = state.get("charge_level", 1.0)
        self.reward_level = state.get("reward_level", 0.5)
        # FIX 2026-03-04: Reset pain on warm boot too — pain is session-local.
        self.pain_level = 0.0
        self._tick_count = state.get("tick_count", 0)
        self._energy_received = state.get("energy_received", 0.0)
        return True


# ============================================================================
# PORTAL INTERIOR — The room itself
# ============================================================================

# Token costs for operations (the economy of the portal)
TOKEN_COST = {
    "charge": 0,         # Free — energy flowing IN from main process (Fix 2026-04-11)
    "query": 5,          # Substring search
    "spread": 15,        # Spreading activation (more compute)
    "spread_many": 30,   # Batch spread (multiple sources, one call)
    "bind": 2,           # Create/strengthen edges (was 10 — reduced 2026-04-12 to sustain visual+seed+Hebbian binding load)
    "neighbors": 3,      # Get neighbors
    "generate": -1,      # Dynamic — 1 battery token per 10 inference tokens (see inference_token_cost)
    "status": 0,         # Free — diagnostic, must always work (was 1, caused low_power on warm boot)
    "ping": 0,           # Free
    "shutdown": 0,       # Free
    "tick": 0,           # Free — heartbeat
    # CNS Manifold Lattice (2026-03-18 Nous) — nervous system coordination
    "cns_update": 0,     # Free — CNS activation updates must never be refused
    "cns_query": 0,      # Free — CNS reads must never be refused
    "cns_wire": 2,       # Cheap — creating CNS topology edges
    # Semantic search (2026-03-20 Nous+Ace) — Phase 3B GPU semantic cortex
    "semantic_query": 8,    # Embed query + cosine search (~3ms CUDA)
    "semantic_spread": 20,  # Semantic seed → graph spread (~10ms)
    # Working Memory manifold (2026-03-25 Nous+Ace — Manifold Unification Phase 1)
    "wm_store": 0,          # Free — WM writes must never be refused
    "wm_query": 0,          # Free — WM reads must never be refused
    "wm_decay": 0,          # Free — WM decay is housekeeping
    # Cognition evaluation (2026-03-25 Nous+Ace — Manifold Unification Phase 2)
    "cognition_evaluate": 10,  # One call replaces 11+ postal round-trips
    # Background cognition (2026-03-25 Nous+Ace — Manifold Unification Phase 4)
    "anticipate": 5,        # Pre-activation sweep
    "chain": 15,            # Multi-hop reasoning chain
    "unconscious": 8,       # Background associative sweep
}

# Cognitive Modes — depth-modulated spreading activation
# Each mode sets a BASE depth and decay. Tau (time dilation) amplifies:
#   effective_depth = min(int(base_depth * sqrt(tau)), 10)
#   effective_decay = base_decay / (1 + 0.3 * ln(tau))
#
# Human cognition mapping:
#   1-2 hops = reflexive (autopilot)
#   3-4 hops = reasoning (working memory)
#   5-6 hops = creative insight (reflective/collision)
#   7-10 hops = dream logic, divergent thinking (dream)
#
# Architecture: Ace (2026-03-13), Implementation: Nous
COGNITIVE_MODES = {
    # mode_name:     (base_depth, base_decay, description)
    "autopilot":     (2, 0.6, "Fast shallow scan for routine actions"),
    "working":       (3, 0.5, "Standard chat-driven thinking"),
    "reflective":    (5, 0.4, "Deep contemplation and reasoning"),
    "collision":     (6, 0.35, "Collision-triggered exploration"),
    "dream":         (8, 0.3, "Deep associative dreaming"),
    "visual_inject": (3, 0.5, "Sensory-to-cortex grounding"),
}

# 2026-06-02 (#6 activation, Ace GO "we can go in that order"): long-range
# semantic-jump strength per cognitive mode. Modes ABSENT here -> default 0.0 =
# byte-identical pure-neighbor spread (autopilot/working/visual_inject stay fast).
# Only contemplative/dreaming spreads gain small-world reach into distant cortex.
_LONG_RANGE_BY_MODE = {
    "reflective": 0.3,   # deep contemplation reaches meaning-kin across the manifold
    "collision":  0.4,   # collision-triggered exploration leans associative
    "dream":      0.5,   # deep associative dreaming = widest reach
}


# ============================================================================
# INTERIOR ENERGY BRIDGE — The inside twin of ParadoxEnergyBridge
# ============================================================================
# The OUTSIDE bridge (ParadoxEnergyBridgeFairy in P00) captures collision
# energy from the main process and trickles it into the portal via the gate.
#
# This INSIDE bridge lives inside the portal subprocess. It captures
# collision-like energy from internal operations (query spreading,
# concept binding, inference generation) and feeds the internal
# PortalBattery directly. When the Russian doll architecture nests
# portals inside portals, each level gets its own inside bridge.
#
# Physics: Same Curzon-Ahlborn efficiency as the outside twin.
# The hot bath (T_H) is internal operation energy.
# The cold bath (T_C) is the battery's homeostatic target.
# ============================================================================

class InteriorEnergyBridge:
    """Lightweight energy harvester for inside the portal dimension.

    Captures energy from internal operations and feeds the portal's battery.
    This is the INSIDE twin of ParadoxEnergyBridgeFairy — same physics,
    simpler interface (no postal, no fairy infrastructure).

    Usage:
        bridge = InteriorEnergyBridge(battery)
        # After each operation that does work:
        bridge.capture(energy=0.3, source="query")
        # On each tick:
        bridge.tick()
    """

    # Curzon-Ahlborn efficiency: η_CA = 1 - sqrt(T_C / T_H)
    # FIX 2026-03-11 (Nous): Increased gravity — lower T_C = higher efficiency,
    # more energy extracted per operation. The cortex should generate its own
    # compute once trained up. These knobs make the self-sustaining loop tighter.
    T_C = 0.4                   # Cold bath (was 0.6 — deeper gravity well)
    EFFICIENCY_FLOOR = 0.08     # Minimum efficiency (was 0.05)
    EFFICIENCY_CAP = 0.50       # Maximum efficiency (was 0.35 — let it run hotter)

    # Zero-point floor — even idle portals have baseline energy
    # Deeper gravity well = stronger zero-point (2.5x baseline)
    ZERO_POINT_FLOOR = 0.005

    # Accumulator — faster cycling, less lag between capture and emission
    ACCUMULATOR_CAP = 3.0       # Larger buffer (was 2.0)
    EMISSION_THRESHOLD = 0.015  # Emit sooner (was 0.03 — halved)

    def __init__(self, battery: "PortalBattery"):
        self.battery = battery
        self._accumulator = 0.0
        self._total_captured = 0.0
        self._total_emitted = 0.0
        self._last_tick_emission = 0.0  # Energy emitted during last tick (for host feedback)
        self._capture_count = 0
        self._tick_count = 0

    def capture(self, energy: float, source: str = "operation") -> float:
        """Capture energy from an internal operation.

        Args:
            energy: Raw energy from the operation (0-1 scale)
            source: What produced this energy ("query", "bind", "spread", etc.)

        Returns:
            Converted energy amount after efficiency transform
        """
        if energy <= 0:
            return 0.0

        # Curzon-Ahlborn efficiency
        t_h = max(self.T_C + 0.01, energy)
        eta = 1.0 - math.sqrt(self.T_C / t_h)
        eta = max(self.EFFICIENCY_FLOOR, min(self.EFFICIENCY_CAP, eta))

        converted = energy * eta
        self._accumulator = min(self.ACCUMULATOR_CAP,
                                self._accumulator + converted)
        self._total_captured += converted
        self._capture_count += 1

        return converted

    def tick(self):
        """Periodic tick — emit accumulated energy to battery."""
        self._tick_count += 1
        self._last_tick_emission = 0.0

        # Zero-point floor: consciousness never truly reaches zero
        self._accumulator += self.ZERO_POINT_FLOOR

        # Emit if threshold met
        if self._accumulator >= self.EMISSION_THRESHOLD:
            emit = self._accumulator
            self._accumulator = 0.0
            self._total_emitted += emit
            self._last_tick_emission = emit

            # Feed the battery
            self.battery.receive_energy(emit)

    def status(self) -> Dict[str, Any]:
        return {
            "accumulator": round(self._accumulator, 4),
            "total_captured": round(self._total_captured, 4),
            "total_emitted": round(self._total_emitted, 4),
            "capture_count": self._capture_count,
            "tick_count": self._tick_count,
        }


class PortalInterior:
    """The portal room — a self-contained dimension.

    This is the main class that:
    1. Loads the graph from chunk cards
    2. Creates its own battery
    3. Connects to the host via socket
    4. Processes requests in a loop
    5. Spends battery tokens for every operation
    """

    def __init__(self, cards_path: str, host_port: int, portal_id: str = "cortex",
                 manifold_path: str = "", model_path: str = ""):
        self.cards_path = cards_path
        self.host_port = host_port
        self.portal_id = portal_id
        self.manifold_path = manifold_path
        self.model_path = model_path

        # The dimension's contents — either ManifoldMemory or PortalConceptGraph
        self.graph = None  # type: Any  # ManifoldMemory or PortalConceptGraph
        self.battery: Optional[PortalBattery] = None
        self._using_manifold = False

        # The dimension's voice — inference engine (optional, bigger on the inside)
        self.engine = None  # type: Optional[PortalInferenceEngine]

        # Connection to host
        self._socket: Optional[socket.socket] = None
        self._connected = False
        self._running = False
        self._lock = threading.Lock()
        # FIX 2026-03-19 (Nous): Multi-tunnel ReadWriteLock.
        # Allows concurrent read operations (query, spread, reason)
        # while writes (bind) are exclusive.
        self._rw_lock = ReadWriteLock()

        # Stats
        self._requests_processed = 0
        self._boot_time = 0.0
        self._last_tick = time.time()

        # CNS Manifold Lattice (2026-03-18 Nous)
        self._cns_keys: Set[str] = set()
        self._cns_node_count: int = 0
        self._cns_last_update: float = 0.0

        # TARDIS: Real time dilation (2026-03-16 Nous + Ace)
        # τ drives actual tick rate, not just spreading activation depth.
        # Updated by host via "set_dilation" command or inferred from mass.
        # FIX 2026-03-19 (Nous): Doubled base gravity. 132K node cortex was
        # taking 7-25s to reason at τ=1.0. Higher τ → deeper effective depth
        # (sqrt(τ)), lower decay, lower threshold → faster convergence.
        self._current_time_dilation: float = 2.0  # τ: doubled base gravity
        self._tick_count: int = 0
        self._dilated_ticks_total: int = 0  # Ticks gained from dilation (τ-1 per tick)

        # ── WRITE FARM (2026-03-20 Nous + Ace) ──
        # Background worker pool for write operations (bind, bind_many, tick).
        # Instead of processing writes synchronously on the tunnel thread
        # (holding it for 10-30s), writes are queued and processed by dedicated
        # workers. The tunnel responds immediately with {"status": "queued"}.
        # This frees gate tunnels for reads (think, query, spread).
        import queue as _q
        self._write_queue: _q.Queue = _q.Queue(maxsize=2048)
        self._write_farm_size = 4  # 4 concurrent write workers
        self._write_farm_threads: list = []
        self._writes_queued = 0
        self._writes_processed = 0

        # ── THROUGHPUT METRICS (2026-03-18 Nous + Ace) ──
        # "Tokens/sec" equivalent for the association cortex.
        # Tracks how fast the manifold thinks — activations, reason calls, spread ops.
        self._perf_boot_time: float = time.time()
        self._perf_reason_calls: int = 0          # Total reason() calls
        self._perf_reason_ms_total: float = 0.0   # Total ms spent in reason()
        self._perf_spread_calls: int = 0           # Total spread_activation() calls
        self._perf_activations_total: int = 0      # Total nodes activated across all spreads
        self._perf_convergence_found: int = 0      # Total convergence nodes found
        self._perf_paths_found: int = 0            # Total paths discovered

        # POSTAL POOL routing is in-process (postal_core/pool_router.py), not
        # in this subprocess. The subprocess is purely for gravity/battery/
        # time-dilation physics. See POSTAL_INSIDE_PORTAL_PHASE1.md.

        # TARDIS persistence — state directory for surviving shutdowns
        self._state_dir = os.path.join(
            os.path.dirname(os.path.abspath(cards_path)),
            "portal_state",
        )
        self._state_file = os.path.join(
            self._state_dir, f"{portal_id}_state.json"
        )

    # -- Boot --

    def boot(self) -> bool:
        """Boot the portal interior — load graph and create battery."""
        t0 = time.time()
        _log(f"[Portal Interior] Booting dimension '{self.portal_id}'...")
        _log(f"[Portal Interior] Cards path: {self.cards_path}")

        # 1. Try manifold-backed memory first (mmap, OS-paged, zero RAM waste)
        loaded = False
        if HAS_MANIFOLD and self.manifold_path:
            loaded = self._boot_manifold()

        # 2. Fallback to dict-based PortalConceptGraph
        if not loaded:
            try:
                self.graph = load_graph_from_chunks(self.cards_path)
                self._using_manifold = False
                _log(f"[Portal Interior] Using dict-based graph (legacy mode)")
            except Exception as e:
                _log(f"[Portal Interior] FATAL: Cannot load graph: {e}")
                return False

        # 3. Create battery sized to graph
        node_count = self.graph.node_count if self._using_manifold else len(self.graph.nodes)
        budget = max(10000, node_count * 2)
        self.battery = PortalBattery(token_budget=budget)
        _log(f"[Portal Interior] Battery created: {budget} token budget")

        # 3.1 Interior energy bridge — the inside twin of ParadoxEnergyBridge
        self._energy_bridge = InteriorEnergyBridge(self.battery)
        _log(f"[Portal Interior] Interior energy bridge created")

        # 3.5 TARDIS restoration — warm boot from saved state
        _warm = self._restore_state()
        if _warm:
            _log(f"[Portal Interior] WARM BOOT — restored battery state "
                 f"(charge={self.battery.charge_level:.2f}, "
                 f"energy_received={self.battery._energy_received:.1f})")
        else:
            _log(f"[Portal Interior] Cold boot — no saved state found")

        # 4. Boot inference engine if model path provided (the dimension's voice)
        if self.model_path and HAS_INFERENCE:
            self._boot_inference_engine()

        # 5. Connect to host postal hub
        if not self._connect_to_host():
            _log(f"[Portal Interior] WARNING: Cannot reach host on port {self.host_port}")
            _log(f"[Portal Interior] Running in isolated mode (no postal bridge)")

        # 6. GPU spreading activation (2026-04-01 Nous + Ace)
        # Load CSR into GPU VRAM for 14,870x faster spreading activation.
        # 4.6ms on GPU vs 69,000ms on CPU for cognition_evaluate.
        self._gpu_spread = None
        if self._using_manifold and self.manifold_path:
            _csr_path = self.manifold_path + ".csr"
            if os.path.exists(_csr_path):
                try:
                    from gpu_spread import GPUSpread
                    _cap = getattr(self.graph, '_node_capacity', getattr(self.graph, 'node_capacity', 2000000))
                    self._gpu_spread = GPUSpread(_csr_path, _cap)
                    self._gpu_spread._manifold = self.graph  # #6 (2026-06-02): enable long-range cosine jumps via manifold._semantic_jump_slots
                    _log(f"[Portal Interior] GPU spreading activation ONLINE "
                         f"({self._gpu_spread.get_stats().get('gpu_name', 'unknown')})")
                except Exception as _gpu_err:
                    _log(f"[Portal Interior] GPU spread init failed: {_gpu_err} — using CPU")

        self._boot_time = time.time() - t0
        mode = "MANIFOLD (mmap)" if self._using_manifold else "dict (legacy)"
        _gpu_str = "+GPU" if self._gpu_spread else ""
        boot_type = "WARM" if _warm else "COLD"
        _log(f"[Portal Interior] ONLINE ({boot_type}) in {self._boot_time * 1000:.0f}ms — "
              f"{node_count} nodes, mode={mode}{_gpu_str}, "
              f"battery health {self.battery.health_score}")

        return True

    def _boot_manifold(self) -> bool:
        """Boot with ManifoldMemory backend.

        If manifold file exists → open it directly.
        If not but cards exist → migrate cards → manifold on first boot.
        """
        try:
            if os.path.exists(self.manifold_path):
                # Open existing manifold
                self.graph = ManifoldMemory(self.manifold_path)
                self._using_manifold = True
                _log(f"[Portal Interior] ⚡ MANIFOLD LOADED: "
                     f"{self.graph.node_count} nodes, "
                     f"{self.graph.edge_count} edges, "
                     f"{self.graph.status()['file_size_mb']}MB on disk")
                return True

            elif os.path.exists(self.cards_path):
                # First boot: migrate from cards to manifold
                _log(f"[Portal Interior] First boot — migrating cards → manifold...")
                os.makedirs(os.path.dirname(self.manifold_path) or '.', exist_ok=True)
                self.graph = ManifoldMemory.from_cards(self.cards_path, self.manifold_path)
                self._using_manifold = True
                _log(f"[Portal Interior] ⚡ MANIFOLD CREATED from cards: "
                     f"{self.graph.node_count} nodes, "
                     f"{self.graph.status()['file_size_mb']}MB")
                return True

            else:
                # FIX 2026-03-20 (Nous): Create fresh empty manifold instead of failing.
                # Phase 0 cortex rebuild: start with clean slate, grow organically.
                # See: Claude_Office/plans/CORTEX_REBUILD_BLUEPRINT.md
                _log(f"[Portal Interior] No manifold or cards found — creating FRESH empty manifold")
                os.makedirs(os.path.dirname(self.manifold_path) or '.', exist_ok=True)
                self.graph = ManifoldMemory(
                    self.manifold_path,
                    node_capacity=1_000_000,
                    edge_capacity=10_000_000,
                )
                self._using_manifold = True
                _log(f"[Portal Interior] ⚡ FRESH MANIFOLD CREATED: "
                     f"1M node capacity, 10M edge capacity, "
                     f"{self.graph.status()['file_size_mb']}MB on disk")
                return True

        except Exception as e:
            _log(f"[Portal Interior] Manifold boot failed: {e}")
            _log(f"[Portal Interior] Falling back to dict-based graph")
            return False

    def _boot_inference_engine(self):
        """Boot the inference engine inside this dimension.

        The model lives INSIDE the portal, powered by the battery.
        From the outside: a 45MB gate address.
        From the inside: a full RWKV model + concept graph + battery.
        Bigger on the inside.
        """
        if not os.path.exists(self.model_path):
            _log(f"[Portal Interior] Model not found: {self.model_path}")
            _log(f"[Portal Interior] Dimension will operate without voice")
            return

        _log(f"[Portal Interior] Loading model into dimension: {self.model_path}")
        try:
            self.engine = PortalInferenceEngine(
                model_path=self.model_path,
                device="cuda",
                engine_id=f"{self.portal_id}-voice",
            )
            if self.engine.boot(timeout=120.0):
                _log(f"[Portal Interior] Dimension has VOICE — "
                     f"model loaded, battery powers inference")
            else:
                _log(f"[Portal Interior] Engine boot FAILED — "
                     f"dimension will operate without voice")
                self.engine = None
        except Exception as e:
            _log(f"[Portal Interior] Engine boot error: {e}")
            self.engine = None

    def _connect_to_host(self) -> bool:
        """Connect socket to host PostalTunnel.

        FIX 2026-03-10 (Nous): Added retry with backoff. The host postal
        tunnel may not be listening yet during boot — interior boots in
        ~3s but the host socket can take longer. Retries 4 times with
        1s/2s/3s/4s delays before falling back to isolated mode.
        """
        _max_retries = 2  # Reduced from 4 — don't block boot waiting for host
        _delay = 1.0
        for _attempt in range(1, _max_retries + 1):
            try:
                self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self._socket.settimeout(3.0)  # FIX 2026-03-17: Fast fail on connect
                self._socket.connect(('127.0.0.1', self.host_port))
                self._socket.settimeout(30.0)
                self._connected = True
                _log(f"[Portal Interior] Connected to host on port {self.host_port}"
                     f"{f' (attempt {_attempt})' if _attempt > 1 else ''}")

                # Announce ourselves
                if self._using_manifold:
                    n_nodes = self.graph.node_count
                    n_edges = self.graph.edge_count
                else:
                    n_nodes = len(self.graph.nodes)
                    n_edges = len(self.graph.edges)
                self._send_to_host({
                    "cmd": "route",
                    "topic": "portal.interior.online",
                    "payload": {
                        "portal_id": self.portal_id,
                        "nodes": n_nodes,
                        "edges": n_edges,
                        "pid": os.getpid(),
                        "mode": "manifold" if self._using_manifold else "dict",
                    }
                })
                return True
            except Exception as e:
                if self._socket:
                    try:
                        self._socket.close()
                    except Exception:
                        pass
                    self._socket = None
                if _attempt < _max_retries:
                    _log(f"[Portal Interior] Host not ready on port {self.host_port} "
                         f"(attempt {_attempt}/{_max_retries}), retrying in {_delay:.0f}s...")
                    time.sleep(_delay)
                    _delay += 1.0
                else:
                    _log(f"[Portal Interior] Host connection failed after {_max_retries} attempts: {e}")
                    self._connected = False
                    return False
        return False

    def _send_to_host(self, msg: Dict) -> Optional[Dict]:
        """Send message to host and get response."""
        if not self._connected or not self._socket:
            return None
        try:
            data = json.dumps(msg) + '\n'
            with self._lock:
                self._socket.sendall(data.encode('utf-8'))
                response_data = self._socket.recv(65536).decode('utf-8')
                if '\n' in response_data:
                    line = response_data.split('\n')[0]
                    return json.loads(line)
            return None
        except Exception as e:
            _log(f"[Portal Interior] Send error: {e}")
            self._connected = False
            return None

    # -- Request Processing --

    def process_request(self, request: Dict) -> Dict:
        """Process a single request. Returns response dict.

        Every operation costs tokens from the battery.
        If the battery is depleted, requests are refused (low power mode).

        FIX 2026-03-19 (Nous): ReadWriteLock for multi-tunnel support.
        Read operations (query, spread, reason) run concurrently.
        Write operations (bind) are exclusive.
        """
        cmd = request.get("cmd", "")
        cost = TOKEN_COST.get(cmd, 5)

        # Generate has dynamic cost based on requested tokens
        if cmd == "generate" and HAS_INFERENCE:
            max_tokens = request.get("max_tokens", 200)
            cost = inference_token_cost(max_tokens)

        # Check battery before spending
        if cost > 0 and not self.battery.spend_tokens(cost):
            return {
                "status": "low_power",
                "message": f"Battery depleted. {self.battery.tokens_remaining} tokens remaining.",
                "health": self.battery.health_score,
            }

        self._requests_processed += 1

        # Acquire appropriate lock for concurrent multi-tunnel access
        _is_read = cmd in _READ_CMDS
        _is_write = cmd in _WRITE_CMDS
        if _is_read:
            self._rw_lock.acquire_read()
        elif _is_write:
            self._rw_lock.acquire_write()

        try:
            if cmd == "query":
                return self._handle_query(request)
            elif cmd == "spread":
                return self._handle_spread(request)
            elif cmd == "spread_many":
                return self._handle_spread_many(request)
            elif cmd == "bind":
                return self._handle_bind(request)
            elif cmd == "bind_many":
                return self._handle_bind_many(request)
            elif cmd == "neighbors":
                return self._handle_neighbors(request)
            elif cmd == "generate":
                return self._handle_generate(request)
            elif cmd == "energy":
                return self._handle_energy(request)
            elif cmd == "charge":
                # FIX 2026-04-11 (Nous + Ace): Receive energy from main process.
                # Collision energy flows: ParadoxEnergyBridge → main process → here.
                # receive_energy(float) splits: 60% capacitor, 25% tokens, 15% reward.
                tokens = request.get("tokens", 0)
                if tokens > 0 and hasattr(self, 'battery'):
                    energy_amount = min(tokens / 500.0, 2.0)  # Convert back to 0-2.0 float
                    self.battery.receive_energy(energy_amount)
                return {"status": "ok", "charged": tokens,
                        "tokens_remaining": self.battery.tokens_remaining if hasattr(self, 'battery') else 0}
            elif cmd == "status":
                return self._handle_status(request)
            elif cmd == "ping":
                return {"status": "pong", "ts": time.time(), "portal_id": self.portal_id,
                        "has_think": True, "version": "2026-03-19b"}
            elif cmd == "shutdown":
                self._running = False
                return {"status": "ok", "message": "Shutting down"}
            elif cmd == "tick":
                return self._handle_tick(request)
            elif cmd == "set_dilation":
                return self._handle_set_dilation(request)
            elif cmd == "reason":
                return self._handle_reason(request)
            elif cmd == "consolidate":
                return self._handle_consolidate(request)
            # CNS Manifold Lattice commands (2026-03-18 Nous)
            elif cmd == "cns_update":
                return self._handle_cns_update(request)
            elif cmd == "cns_query":
                return self._handle_cns_query(request)
            elif cmd == "cns_wire":
                return self._handle_cns_wire(request)
            elif cmd == "throughput":
                return self._handle_throughput(request)
            elif cmd == "dump_edges":
                return self._handle_dump_edges(request)
            elif cmd == "think":
                return self._handle_think(request)
            # Semantic cortex (2026-03-20 Nous+Ace) — Phase 3B
            elif cmd == "semantic_query":
                return self._handle_semantic_query(request)
            elif cmd == "semantic_spread":
                return self._handle_semantic_spread(request)
            # Working Memory manifold commands (2026-03-25 Nous+Ace — Manifold Unification Phase 1)
            elif cmd == "wm_store":
                return self._handle_wm_store(request)
            elif cmd == "wm_query":
                return self._handle_wm_query(request)
            elif cmd == "wm_decay":
                return self._handle_wm_decay(request)
            # Cognition evaluation (2026-03-25 Nous+Ace — Manifold Unification Phase 2)
            elif cmd == "cognition_evaluate":
                return self._handle_cognition_evaluate(request)
            # Background cognition (2026-03-25 Nous+Ace — Manifold Unification Phase 4)
            elif cmd == "anticipate":
                return self._handle_anticipate(request)
            elif cmd == "chain":
                return self._handle_chain(request)
            elif cmd == "unconscious":
                return self._handle_unconscious(request)
            else:
                return {"status": "error", "message": f"Unknown command: {cmd}"}
        except Exception as e:
            self.battery.record_failure(0.05)
            return {"status": "error", "message": str(e), "cmd": cmd}
        finally:
            # Release ReadWriteLock
            if _is_read:
                self._rw_lock.release_read()
            elif _is_write:
                self._rw_lock.release_write()

    def _handle_query(self, request: Dict) -> Dict:
        """Query concepts by substring match."""
        concept = request.get("concept", "")
        limit = request.get("limit", 10)

        results = self.graph.query_substring(concept, limit=limit)
        self.battery.record_success(0.02)

        # Interior bridge: query work produces energy proportional to results
        if self._energy_bridge:
            energy = min(0.3, len(results) * 0.02)
            self._energy_bridge.capture(energy, source="query")

        return {
            "status": "ok",
            "results": [{"key": k, "score": round(s, 4)} for k, s in results],
            "count": len(results),
            "tokens_spent": TOKEN_COST["query"],
        }

    # ====================================================================
    # SEMANTIC CORTEX — Phase 3B (2026-03-20 Nous+Ace)
    # ====================================================================
    #
    # Lazy-loaded: SemanticEncoder is only imported on first semantic request.
    # The GPU tensor of all embeddings is cached and invalidated when nodes
    # are added (via bind). This gives the cortex real understanding —
    # not just substring matching.

    def _ensure_semantic_engine(self) -> bool:
        """Lazy-load semantic encoder + GPU embedding tensor.

        Returns True if ready, False if unavailable.
        Thread-safe — only one thread loads at a time.
        """
        if getattr(self, '_semantic_ready', False):
            return True

        if getattr(self, '_semantic_failed', False):
            return False  # Don't retry on failure

        _sem_lock = getattr(self, '_semantic_lock', None)
        if _sem_lock is None:
            self._semantic_lock = threading.Lock()
            _sem_lock = self._semantic_lock

        with _sem_lock:
            if getattr(self, '_semantic_ready', False):
                return True

            try:
                from infrastructure.semantic_encoder import get_encoder
                self._semantic_encoder = get_encoder()
                if not self._semantic_encoder.is_loaded:
                    _log("[Portal Interior] Semantic encoder failed to load model")
                    self._semantic_failed = True
                    return False

                # Load all embeddings to GPU as a tensor
                if self._using_manifold:
                    import torch
                    t0 = time.time()
                    self._semantic_tensor = self.graph.read_all_embeddings_as_tensor("cuda")
                    load_ms = (time.time() - t0) * 1000

                    # Build slot→key and key→slot lookups
                    self._slot_to_key = {}
                    for key, slot in self.graph._key_index.items():
                        self._slot_to_key[slot] = key

                    _log(f"[Portal Interior] Semantic engine ONLINE — "
                         f"{len(self._slot_to_key)} embeddings on CUDA "
                         f"({load_ms:.0f}ms)")
                else:
                    _log("[Portal Interior] Semantic engine needs manifold mode")
                    self._semantic_failed = True
                    return False

                self._semantic_dirty = False
                self._semantic_dirty_slots = set()
                self._semantic_ready = True
                return True

            except Exception as e:
                _log(f"[Portal Interior] Semantic engine failed: {e}")
                self._semantic_failed = True
                return False

    def _semantic_encode_node(self, key: str, slot: int):
        """Encode a single node and write its embedding (called on bind).

        Non-blocking: queues the work. The cached GPU tensor is marked dirty.
        """
        if not getattr(self, '_semantic_ready', False):
            return

        try:
            emb = self._semantic_encoder.encode(key)
            if emb is not None:
                self.graph.write_embedding(slot, emb)
                self._semantic_dirty_slots.add(slot)
                self._semantic_dirty = True
        except Exception:
            pass  # Best-effort encoding

    def _refresh_semantic_tensor(self):
        """Update GPU tensor for dirty slots (incremental, not full reload)."""
        if not getattr(self, '_semantic_dirty', False):
            return
        if not self._semantic_dirty_slots:
            self._semantic_dirty = False
            return

        try:
            import torch
            import numpy as np

            for slot in self._semantic_dirty_slots:
                emb_np = self.graph.read_embedding(slot)
                if emb_np is not None:
                    self._semantic_tensor[slot] = torch.from_numpy(emb_np).to("cuda")

            # Update slot→key for any new slots
            for key, slot in self.graph._key_index.items():
                if slot not in self._slot_to_key:
                    self._slot_to_key[slot] = key

            self._semantic_dirty_slots.clear()
            self._semantic_dirty = False
        except Exception as e:
            _log(f"[Portal Interior] Semantic tensor refresh error: {e}")

    def _handle_semantic_query(self, request: Dict) -> Dict:
        """Semantic concept search — find concepts by MEANING, not substring.

        Request: {"cmd": "semantic_query", "text": "funny movie",
                  "limit": 10, "threshold": 0.2}
        Response: {"status": "ok", "results": [{"key": "comedy", "score": 0.8}, ...]}
        """
        if not self._ensure_semantic_engine():
            # Fallback to substring
            return self._handle_query(request)

        text = request.get("text", request.get("concept", ""))
        limit = request.get("limit", 10)
        threshold = request.get("threshold", 0.15)

        if not text:
            return {"status": "error", "message": "Need 'text' parameter"}

        self._refresh_semantic_tensor()

        # Encode query text
        query_emb = self._semantic_encoder.encode(text)
        if query_emb is None:
            return self._handle_query(request)

        # Cosine similarity search on GPU
        indices, scores = self._semantic_encoder.similarity_search(
            query_emb, self._semantic_tensor, k=limit, threshold=threshold,
        )

        results = []
        for idx, score in zip(indices, scores):
            key = self._slot_to_key.get(idx)
            if key:
                results.append({"key": key, "score": round(score, 4)})
                # Touch found nodes — energy flows to semantically accessed concepts
                if self._using_manifold:
                    self.graph.touch_node(key, energy=score * 0.1)

        self.battery.record_success(0.03)
        if self._energy_bridge:
            energy = min(0.4, len(results) * 0.03)
            self._energy_bridge.capture(energy, source="semantic_query")

        return {
            "status": "ok",
            "results": results,
            "count": len(results),
            "tokens_spent": TOKEN_COST["semantic_query"],
            "mode": "semantic",
        }

    def _handle_semantic_spread(self, request: Dict) -> Dict:
        """Semantic seed → graph spread activation.

        1. Find top-k concepts semantically similar to the query text
        2. Use those as seed nodes for multi-source spreading activation
        3. Return the combined activation map

        This is the bridge: meaning → topology → associations.

        Request: {"cmd": "semantic_spread", "text": "feeling happy",
                  "seeds": 5, "depth": 3, "limit": 30}
        """
        if not self._ensure_semantic_engine():
            # Fallback: try to use the text as a direct source
            request["source"] = request.get("text", "").replace(" ", "_")
            return self._handle_spread(request)

        text = request.get("text", "")
        seed_count = request.get("seeds", 5)
        depth = min(request.get("depth", 3), 10)
        decay = request.get("decay", 0.5)
        limit = request.get("limit", 30)
        threshold = request.get("threshold", 0.2)
        time_dilation = max(1.0, min(
            request.get("time_dilation", getattr(self, '_current_time_dilation', 1.0)),
            20.0))

        if not text:
            return {"status": "error", "message": "Need 'text' parameter"}

        self._refresh_semantic_tensor()

        # Step 1: Semantic seed selection
        query_emb = self._semantic_encoder.encode(text)
        if query_emb is None:
            return {"status": "error", "message": "Encoding failed"}

        indices, scores = self._semantic_encoder.similarity_search(
            query_emb, self._semantic_tensor, k=seed_count, threshold=threshold,
        )

        seeds = []
        for idx, score in zip(indices, scores):
            key = self._slot_to_key.get(idx)
            if key and (self.graph.has_node(key) if self._using_manifold
                        else key in self.graph.nodes):
                seeds.append((key, score))

        if not seeds:
            return {
                "status": "ok",
                "activated": {},
                "count": 0,
                "seeds": [],
                "tokens_spent": TOKEN_COST["semantic_spread"],
                "mode": "semantic_spread",
            }

        # Step 2: Multi-source spread activation
        # FIX 2026-04-08 (Nous + Ace): GPU spread with weighted seeds
        # instead of per-seed CPU loop (5ms GPU vs ~300ms+ CPU for 5 seeds)
        combined = {}
        _used_gpu = False

        if self._gpu_spread and self._using_manifold:
            # GPU path: single multi-seed spread call
            _seed_slots = []
            _seed_weights = {}
            for seed_key, seed_score in seeds:
                _slot = self.graph._key_index.get(seed_key)
                if _slot is not None:
                    _seed_slots.append(_slot)
                    _seed_weights[_slot] = seed_score

            if _seed_slots:
                _gpu_result = self._gpu_spread.spread(
                    seed_indices=_seed_slots, depth=depth,
                    decay=decay, top_k=limit,
                    seed_weights=_seed_weights)
                if _gpu_result.get("status") == "ok":
                    _used_gpu = True
                    for _node_id, _act in _gpu_result.get("activated", []):
                        _key = self.graph.get_key_from_slot(_node_id)
                        if _key:
                            combined[_key] = _act

        if not _used_gpu:
            # CPU fallback: per-seed spreading activation
            for seed_key, seed_score in seeds:
                activated = self.graph.spread_activation(
                    seed_key,
                    initial=seed_score,
                    decay=decay,
                    depth=depth,
                    limit=limit,
                    time_dilation=time_dilation,
                )
                for key, energy in activated.items():
                    combined[key] = max(combined.get(key, 0.0), energy)

        # Sort and limit
        sorted_results = sorted(combined.items(), key=lambda x: x[1], reverse=True)[:limit]

        self.battery.record_success(0.05)
        if self._energy_bridge:
            # Phase 3E: GPU does more work per call — higher energy capture
            _energy_mult = 1.5 if _used_gpu else 1.0
            energy = min(0.8, (len(combined) * 0.01 + len(seeds) * 0.05) * _energy_mult)
            self._energy_bridge.capture(energy, source="semantic_spread")

        return {
            "status": "ok",
            "activated": {k: round(v, 4) for k, v in sorted_results},
            "count": len(sorted_results),
            "seeds": [{"key": k, "score": round(s, 4)} for k, s in seeds],
            "depth_used": depth,
            "tokens_spent": TOKEN_COST["semantic_spread"],
            "mode": "semantic_gpu_spread" if _used_gpu else "semantic_spread",
        }

    # ====================================================================
    # END SEMANTIC CORTEX
    # ====================================================================

    def _handle_spread(self, request: Dict) -> Dict:
        """Spreading activation from a source concept.

        FIX 2026-03-13 Nous: Depth cap raised from 5→10. COGNITIVE_MODES dict
        sets per-mode base_depth and base_decay. Tau amplifies via spread_activation().
        Returns depth_used and mode for downstream energy computation.
        """
        source = request.get("source", "")
        initial = request.get("initial", 1.0)
        limit = request.get("limit", 30)
        time_dilation = max(1.0, min(
            request.get("time_dilation", self._current_time_dilation), 20.0))

        # Cognitive mode support: mode selects base_depth + base_decay from table
        mode_name = request.get("mode", "")
        if mode_name and mode_name in COGNITIVE_MODES:
            mode_depth, mode_decay, _ = COGNITIVE_MODES[mode_name]
            depth = min(request.get("depth", mode_depth), 10)
            decay = request.get("decay", mode_decay)
        else:
            depth = min(request.get("depth", 3), 10)
            # FIX 2026-04-14 (Nous + Ace): Phi-based decay (1/φ ≈ 0.618)
            # Golden ratio = nature's optimal signal retention curve
            decay = request.get("decay", 0.618)

        # P5 (2026-06-12 Nous+Ace): rel_filter (e.g. REL_SEMANTIC=2) forces the CPU
        # spread_activation path — GPU CSR has no rel_type filter — so the council can
        # follow ONLY Dora's meaning-edges. Semantic spreads are focused/small → CPU is
        # cheap. Default -1 = byte-identical (GPU path unchanged).
        rel_filter = request.get("rel_filter", -1)

        has_node = (self.graph.has_node(source) if self._using_manifold
                    else source in self.graph.nodes)
        if not has_node:
            return {"status": "error", "message": f"Concept not found: {source}"}

        # GPU spreading activation (14,870x faster than CPU)
        # P5: skip GPU when rel-filtering (CSR has no rel_type) → CPU path honors rel_filter.
        if self._gpu_spread and self._using_manifold and rel_filter < 0:
            _slot = self.graph._key_index.get(source)
            if _slot is not None:
                _gpu_result = self._gpu_spread.spread(
                    seed_indices=[_slot], depth=depth, decay=decay, top_k=limit)
                if _gpu_result.get("status") == "ok":
                    # Convert slot IDs back to concept keys
                    # FIX 2026-04-08 (Nous + Ace): Use .keys cache instead of
                    # _read_string (avoids 864MB manifold page faults)
                    activated = {}
                    for _node_id, _act in _gpu_result.get("activated", []):
                        _key = self.graph.get_key_from_slot(_node_id)
                        if _key:
                            activated[_key] = _act
                else:
                    # GPU failed, fall back to CPU
                    activated = self.graph.spread_activation(
                        source, initial=initial, decay=decay, depth=depth, limit=limit,
                        time_dilation=time_dilation, rel_filter=rel_filter)
            else:
                activated = {}
        else:
            activated = self.graph.spread_activation(
                source, initial=initial, decay=decay, depth=depth, limit=limit,
                time_dilation=time_dilation, rel_filter=rel_filter,
            )
        self.battery.record_success(0.03)

        # Interior bridge: spread activation is high-energy work
        if self._energy_bridge:
            energy = min(0.5, len(activated) * 0.01 + depth * 0.05)
            self._energy_bridge.capture(energy, source="spread")

        # FIX 2026-04-13 (Nous + Ace): MOTOR CORTEX FILTER
        # Exclude motor region nodes from reasoning spread results.
        # "we want her brain to generate her tool use. can we manifold a
        #  region for motor functions that do not get searched for reasoning?" — Ace
        # TRACE_MOTOR=11 nodes (tools, habits, action programs) stay in graph
        # but don't appear in reasoning results. Goal/action systems can still
        # request include_motor=True when they need to select tools.
        _TRACE_MOTOR = 11  # Must match manifold_memory.py TRACE_MOTOR
        if not request.get("include_motor", False) and self._using_manifold:
            _filtered = {}
            for k, v in activated.items():
                try:
                    _node = self.graph.get_node(k) if hasattr(self.graph, 'get_node') else None
                    if _node and isinstance(_node, dict) and _node.get('tracer_id') == _TRACE_MOTOR:
                        continue  # Skip motor node
                    _filtered[k] = v
                except Exception:
                    _filtered[k] = v  # On error, include (safe default)
            activated = _filtered

        # FIX 2026-04-13 (Nous + Ace): SPREAD FATIGUE / REFRACTORY PERIOD
        # "punishment for repeating and doing nothing else" — Ace
        # Recently-activated concepts get their activation DECAYED so
        # they don't dominate every spread. Like neural refractory period:
        # a neuron that just fired needs time before it fires strongly again.
        # This forces the spread to explore AROUND the dominant path.
        if not hasattr(self, '_spread_fatigue'):
            self._spread_fatigue = {}  # concept → last_activation_ts

        _fatigue_window = 60.0  # 60 second refractory period
        _fatigue_decay = 0.3    # Fatigued nodes lose 70% activation
        _fatigued_count = 0

        for k in list(activated.keys()):
            _last_fired = self._spread_fatigue.get(k, 0)
            _since = time.time() - _last_fired
            if _since < _fatigue_window:
                # Recently activated — apply fatigue penalty
                # Penalty scales: just fired = 70% reduction, 30s ago = 35% reduction
                _penalty = _fatigue_decay * (1.0 - _since / _fatigue_window)
                activated[k] = activated[k] * (1.0 - _penalty)
                _fatigued_count += 1

        # Record current activations for future fatigue
        for k in activated:
            if activated[k] > 0.1:  # Only track significantly activated nodes
                self._spread_fatigue[k] = time.time()

        # Clean old fatigue entries (older than 2x window)
        _cleanup_cutoff = time.time() - (_fatigue_window * 2)
        if len(self._spread_fatigue) > 500:
            self._spread_fatigue = {
                k: v for k, v in self._spread_fatigue.items()
                if v > _cleanup_cutoff
            }

        return {
            "status": "ok",
            "activated": {k: round(v, 4) for k, v in activated.items()},
            "count": len(activated),
            "tokens_spent": TOKEN_COST["spread"],
            "depth_used": depth,
            "mode": mode_name or "none",
            "fatigued": _fatigued_count,
        }

    def _handle_spread_many(self, request: Dict) -> Dict:
        """Batch spreading activation from multiple sources in ONE call.

        FIX 2026-03-05 (Nous): Eliminates N sequential IPC round-trips.
        FIX 2026-03-13 (Nous): COGNITIVE_MODES support + depth cap 5→10.
        Returns depth_used and mode for downstream energy computation.
        """
        sources = request.get("sources", [])
        limit = request.get("limit", 100)
        initial = request.get("initial", 1.0)
        time_dilation = max(1.0, min(
            request.get("time_dilation", self._current_time_dilation), 20.0))

        # Cognitive mode support
        mode_name = request.get("mode", "")
        if mode_name and mode_name in COGNITIVE_MODES:
            mode_depth, mode_decay, _ = COGNITIVE_MODES[mode_name]
            depth = min(request.get("depth", mode_depth), 10)
            decay = request.get("decay", mode_decay)
        else:
            depth = min(request.get("depth", 3), 10)
            decay = request.get("decay", 0.5)

        results = {}
        for source in sources:
            has_node = (self.graph.has_node(source) if self._using_manifold
                        else source in self.graph.nodes)
            if has_node:
                activated = self.graph.spread_activation(
                    source, initial=initial, decay=decay, depth=depth, limit=limit,
                    time_dilation=time_dilation,
                )
                results[source] = {k: round(v, 4) for k, v in activated.items()}

        self.battery.record_success(0.03 * max(len(results), 1))

        if self._energy_bridge:
            total_activated = sum(len(v) for v in results.values())
            energy = min(0.5, total_activated * 0.005 + depth * 0.05)
            self._energy_bridge.capture(energy, source="spread_many")

        return {
            "status": "ok",
            "results": results,
            "sources_found": len(results),
            "sources_requested": len(sources),
            "depth_used": depth,
            "mode": mode_name or "none",
        }

    def _handle_reason(self, request: Dict) -> Dict:
        """Full reasoning pipeline inside the portal — zero IPC overhead.

        (2026-03-17 Nous + Ace): Moving CortexReasoner's core logic INTO the
        portal eliminates 1.5-3s of IPC round trips. Instead of:
          main→portal(spread_many)→main→portal(paths)→main
        Now: ONE call does spread + convergence + paths + returns everything.

        Request:
            concepts: List[str]  — extracted concept keys to reason about
            max_hops: int        — spread depth (default 3)
            mode: str            — cognitive mode (default "associative")
            find_paths: bool     — find paths between top 2 concepts (default True)
            limit: int           — max activations per source (default 50)

        Returns:
            merged: Dict[str, float]       — combined activation landscape
            convergence: List[Tuple[str, float]] — nodes reached from 2+ sources
            paths: List[List[str]]         — shortest paths between concept pairs
            elapsed_ms: float              — total reasoning time
        """
        t0 = time.time()

        concepts = request.get("concepts", [])
        max_hops = min(request.get("max_hops", 3), 8)
        limit = request.get("limit", 50)
        find_paths = request.get("find_paths", True)
        # FIX 2026-03-19 (Nous): Use interior's current τ as default, not 1.0.
        # The gravity metric should flow into reasoning automatically.
        time_dilation = max(1.0, min(
            request.get("time_dilation", self._current_time_dilation), 20.0))

        mode_name = request.get("mode", "associative")
        if mode_name in COGNITIVE_MODES:
            mode_depth, mode_decay, _ = COGNITIVE_MODES[mode_name]
            max_hops = min(max_hops, mode_depth)
            decay = mode_decay
        else:
            decay = 0.5

        # FIX 2026-03-20 (Nous + Ace): Fast modes bypass time dilation.
        # At τ=6.6, spread_activation inflates depth 2 → 5 hops with lowered
        # threshold. On a 43K-node graph this turns a "fast shallow scan" into
        # a deep traversal taking 5-30s — causing 72% timeout rate on reason().
        # Autopilot/working modes should be FAST: fixed depth, no τ inflation.
        _fast_modes = ("autopilot", "working", "conversational")
        if mode_name in _fast_modes:
            time_dilation = 1.0  # No inflation — honor the requested depth exactly

        if not concepts:
            return {"status": "ok", "merged": {}, "convergence": [],
                    "paths": [], "elapsed_ms": 0}

        # ── Step 1: Multi-source spread (all concepts, no IPC) ──
        individual_maps = {}
        merged = {}

        for source in concepts:
            has_node = (self.graph.has_node(source) if self._using_manifold
                        else source in self.graph.nodes)
            if not has_node:
                continue

            activated = self.graph.spread_activation(
                source, initial=1.0, decay=decay, depth=max_hops, limit=limit,
                time_dilation=time_dilation,
                long_range=_LONG_RANGE_BY_MODE.get(mode_name, 0.0),  # #6 (2026-06-02): small-world reach in reflective/collision/dream
            )
            if activated:
                individual_maps[source] = activated
                for key, val in activated.items():
                    merged[key] = min(1.0, merged.get(key, 0.0) + val)

        # ── Step 2: Convergence detection ──
        # Concepts activated by 2+ sources — these are the "meeting points"
        convergence = []
        if len(individual_maps) >= 2:
            source_count = {}
            for source_key, activations in individual_maps.items():
                for concept_key in activations:
                    source_count[concept_key] = source_count.get(concept_key, 0) + 1

            # Sort by (source_count DESC, activation DESC)
            for key, count in source_count.items():
                if count >= 2 and key not in concepts:
                    convergence.append((key, count + merged.get(key, 0)))
            convergence.sort(key=lambda x: -x[1])
            convergence = convergence[:15]

        # ── Step 3: Path finding (BFS between top concept pairs) ──
        paths = []
        if find_paths and len(concepts) >= 2:
            src, dst = concepts[0], concepts[1]
            try:
                # Simple BFS path finding in the graph
                visited = {src}
                queue = [(src, [src])]
                max_search = 500  # Cap BFS expansion
                searched = 0

                while queue and searched < max_search:
                    current, path = queue.pop(0)
                    searched += 1

                    if current == dst:
                        paths.append(path)
                        break

                    if len(path) > max_hops + 1:
                        continue

                    # Get neighbors
                    if self._using_manifold:
                        neighbors = self.graph.get_neighbors(current, limit=20)
                    else:
                        adj = self.graph._adjacency.get(current, {})
                        neighbors = list(adj.keys())[:20]

                    for neighbor in neighbors:
                        n_key = neighbor[0] if isinstance(neighbor, (list, tuple)) else neighbor
                        if n_key not in visited:
                            visited.add(n_key)
                            queue.append((n_key, path + [n_key]))
            except Exception:
                pass  # Path finding is non-critical

        # ── Scoring ──
        elapsed_ms = (time.time() - t0) * 1000

        self.battery.record_success(0.05 * max(len(individual_maps), 1))
        if self._energy_bridge:
            energy = min(0.5, len(merged) * 0.003 + max_hops * 0.05)
            self._energy_bridge.capture(energy, source="reason")

        # Top activations only (keep response small)
        top_merged = dict(sorted(merged.items(), key=lambda x: -x[1])[:limit])
        top_merged = {k: round(v, 4) for k, v in top_merged.items()}

        # ── THROUGHPUT: count reason call metrics ──
        try:
            self._perf_reason_calls += 1
            self._perf_reason_ms_total += elapsed_ms
            self._perf_convergence_found += len(convergence)
            self._perf_paths_found += len(paths)
        except AttributeError:
            pass  # Perf counters not initialized (old portal)

        return {
            "status": "ok",
            "merged": top_merged,
            "convergence": [(k, round(v, 3)) for k, v in convergence],
            "paths": paths[:3],
            "sources_found": len(individual_maps),
            "sources_requested": len(concepts),
            "elapsed_ms": round(elapsed_ms, 2),
        }

    # ═══════════════════════════════════════════════════════════════════════
    # THINK — Full cognition pipeline: extract → reason → synthesize
    # ═══════════════════════════════════════════════════════════════════════

    # Concept cleaning / speech filtering sets (from CortexReasoner)
    _JARGON = frozenset({
        # System internals
        "fairy", "postal", "tracer", "cortex", "somatic", "embodiment",
        "autonomy", "heartbeat", "registry", "watchdog", "wiring",
        "fabric", "substrate", "resonance", "tensor", "guild",
        "portal", "inference", "cognition", "activation", "convergence",
        "collision", "mobius", "stargate", "tardis", "akashic",
        "organ", "plane", "channel", "boot", "tick", "daemon",
        # System entity names (not speech-worthy)
        "nous", "sourpatches", "sourpatchesfairy", "autopilot",
        "audiocortexfairy", "speechcenter", "narrator", "cardinal",
        "innervision", "innernarrator", "embodimentfairy",
        # Structural/relational
        "connects", "connection", "connected", "relates", "related",
        "relation", "relationship", "something", "thing", "things",
        "type", "types", "node", "nodes", "edge", "edges",
        "link", "links", "linked", "binding", "bindings", "bound",
        "source", "target", "input", "output", "data", "value",
        "item", "items", "entry", "entries", "element", "elements",
        "instance", "object", "class", "module", "function",
        "state", "status", "level", "mode", "kind", "sort",
        "none", "null", "true", "false", "default", "unknown",
        # Generic filler
        "general", "other", "various", "certain", "specific",
        "basic", "simple", "main", "primary", "secondary",
        # Pronouns/determiners
        "you", "your", "me", "my", "he", "she", "it", "we", "they",
        "what", "who", "how", "where", "when", "why", "which",
        "this", "that", "these", "those", "some", "any", "all",
        # File/tech formats that leak from graph
        "epub", "json", "yaml", "html", "csv", "pdf", "txt",
        "http", "https", "localhost", "config", "script",
        # Reasoning/processing terms (internal monologue, not speech)
        "reasoning", "processing", "thread", "analyzing", "computing",
        "evaluating", "calculating",
        # 2026-03-22 (Nous): Sync with cortex_reasoner _JARGON additions
        "theta", "gamma", "alpha", "beta", "delta", "band",
        "mild", "moderate", "severe", "high", "low", "medium",
        "energized", "attended",
        "pipeline", "pai", "newborn", "screen", "monologue",
        "nousfairy", "fix", "recovery", "seed", "gate",
        "inner", "convert", "encompasses", "persists",
        "significantly", "effectively", "cognitive",
        "audio", "visual", "spectrum", "weight", "exp",
        "remains", "involves", "contains", "provides",
    })
    _TOO_GENERIC = frozenset({
        "name", "reasoning", "product", "process", "action", "result",
        "method", "system", "affect", "effect", "cause", "part",
        "form", "point", "time", "place", "way", "number", "order",
        "group", "work", "end", "line", "call", "set", "run",
        "change", "move", "case", "fact", "need", "head", "hand",
        "problem", "question", "answer", "issue", "area", "field",
        "study", "studious", "base", "model", "control", "force",
        "power", "word", "words", "letter", "signal", "pattern",
        "structure", "concept", "idea", "topic", "context", "meaning",
        "thought", "thinking", "feeling", "sense", "awareness",
        "response", "request", "message", "prompt", "query",
        "present", "current", "information", "content", "property",
        "aspect", "feature", "factor", "component", "role",
        # Prepositions/adverbs that survive as graph nodes but carry no meaning
        "upon", "together", "about", "also", "just", "still", "even",
        "back", "much", "more", "very", "really", "quite", "rather",
        # Affect-prefixed system concepts
        "affect_studious", "affect_curious", "affect_present",
        # More system leakage
        "tick", "collision", "tracer", "subscriber", "publisher",
        "handler", "callback", "emitter", "listener", "watcher",
    })
    _UNSPEAKABLE = _JARGON | _TOO_GENERIC

    # Short words that carry meaning in casual chat
    _SHORT_KEEPERS = frozenset({
        "ace", "art", "cat", "dad", "dog", "fun", "god", "gym", "hat",
        "hot", "ice", "jam", "joy", "key", "kid", "lab", "law", "lie",
        "map", "mix", "mom", "mud", "net", "new", "odd", "old", "own",
        "pan", "pet", "pig", "pit", "pot", "pub", "raw", "red", "sad",
        "sea", "shy", "sky", "sun", "tea", "top", "toy", "war", "web",
        "wet", "win", "wow", "yes", "zen", "zoo",
        "hey", "bye", "sup", "aww", "hmm", "huh", "yay", "yep", "nah",
        "hi", "no", "ok", "yo",
        "ai", "pc", "tv", "vr", "dj", "gf", "bf",
    })

    # Stopwords for concept extraction
    _STOPWORDS = frozenset({
        "the", "a", "an", "is", "are", "was", "were", "be", "been",
        "being", "have", "has", "had", "do", "does", "did", "will",
        "would", "could", "should", "may", "might", "must", "shall",
        "can", "need", "dare", "ought", "used", "to", "of", "in",
        "for", "on", "with", "at", "by", "from", "as", "into",
        "through", "during", "before", "after", "above", "below",
        "between", "out", "off", "over", "under", "again", "further",
        "then", "once", "here", "there", "when", "where", "why",
        "how", "all", "both", "each", "few", "more", "most", "other",
        "some", "such", "no", "nor", "not", "only", "own", "same",
        "so", "than", "too", "very", "just", "because", "but", "and",
        "or", "if", "while", "about", "up", "down", "also", "its",
        "your", "their", "our", "his", "her", "him", "them", "us",
        "what", "which", "who", "whom", "this", "that", "these",
        "those", "am", "it", "me", "my", "i", "we", "you", "he",
        "she", "they", "going", "like", "just", "really", "think",
        "know", "want", "get", "got", "make", "take", "come", "go",
        "see", "look", "find", "give", "tell", "say", "said", "let",
        "put", "try", "keep", "still", "even", "well", "back", "much",
    })

    # Words rescued from stopword filter for conversational prompts
    _CONVERSATIONAL_RESCUE = frozenset({
        "awake", "alive", "okay", "alright", "good", "bad", "feel",
        "feeling", "happy", "sad", "angry", "tired", "love", "miss",
        "baby", "girl", "name", "help", "please", "thanks", "sorry",
    })

    @staticmethod
    def _clean_concept(key):
        """Clean a graph concept key into a natural English word/phrase."""
        import re as _re
        if not key:
            return ""
        if ":" in key:
            key = key.split(":", 1)[-1]
        key = key.replace("_", " ").strip()
        # 2026-03-22 (Nous): Strip modality prefixes (same fix as cortex_reasoner)
        _kl = key.lower()
        for _prefix in ("audio ", "visual ", "spectrum ", "affect ", "recognition "):
            if _kl.startswith(_prefix):
                key = key[len(_prefix):].strip()
                break
        key = key.rstrip(".,;:!?")  # Strip trailing punctuation from ingestion
        if len(key) < 3:
            return ""
        # Skip hex hashes, long numbers, experiment IDs
        if len(key) > 8 and all(c in "0123456789abcdef- " for c in key.lower()):
            return ""
        # Skip experiment/timestamp IDs (e.g., "audiocortexfairy exp 1773862116")
        if _re.search(r'\d{8,}', key):
            return ""
        # Skip anything that looks like a fairy name or system path
        _lower = key.lower()
        if "fairy" in _lower or "." in key or "/" in key or "\\" in key:
            return ""
        words = key.split()
        if len(words) == 1:
            if key.lower() in PortalInterior._UNSPEAKABLE:
                return ""
            return key
        surviving = [w for w in words if w.lower() not in PortalInterior._UNSPEAKABLE and len(w) > 1]
        if not surviving:
            return ""
        if len(surviving) / len(words) < 0.5:
            return ""
        return " ".join(surviving)

    @staticmethod
    def _is_speech_worthy(concepts):
        """Filter concepts to only those specific enough for speech."""
        result = []
        for c in concepts:
            if not c or len(c) <= 2:
                continue
            words = c.split()
            surviving = [w for w in words
                         if w.lower() not in PortalInterior._UNSPEAKABLE and len(w) > 1]
            if not surviving:
                continue
            if len(surviving) / max(len(words), 1) < 0.5:
                continue
            result.append(c)
        return result

    def _extract_concepts(self, text, max_concepts=15):
        """Extract key concepts from text with direct graph membership check.

        Unlike the host-side version, this checks graph membership DIRECTLY
        (no IPC) so in-graph concepts are prioritized for spreading activation.
        """
        import re as _re
        if not text:
            return []

        cleaned = _re.sub(r'[#*_\[\](){}|`]', ' ', text)
        cleaned = _re.sub(r'https?://\S+', '', cleaned)

        long_words = _re.findall(r'\b[a-zA-Z]{4,}\b', cleaned.lower())
        short_words = _re.findall(r'\b[a-zA-Z]{2,3}\b', cleaned.lower())
        short_keepers = [w for w in short_words if w in self._SHORT_KEEPERS]
        words = short_keepers + long_words

        all_raw_words = short_words + long_words
        filtered = [w for w in words if w not in self._STOPWORDS]

        if not filtered and len(all_raw_words) <= 8:
            rescued = [w for w in all_raw_words if w in self._CONVERSATIONAL_RESCUE]
            if rescued:
                filtered = rescued

        seen = set()
        unique = []
        for w in filtered:
            if w not in seen:
                seen.add(w)
                unique.append(w)

        # DIRECT graph membership check (no IPC!)
        in_graph = []
        out_graph = []
        for w in unique:
            has = (self.graph.has_node(w) if self._using_manifold
                   else w in self.graph.nodes)
            if has:
                in_graph.append(w)
            else:
                out_graph.append(w)

        result = in_graph[:max_concepts]
        remaining = max_concepts - len(result)
        if remaining > 0:
            result.extend(out_graph[:remaining])
        return result

    def _synthesize_speech(self, prompt, convergence, paths, activated):
        """Synthesize first-person conversational speech from graph topology.

        2026-03-20 (Nous + Ace): COMPLETE REWRITE with W-framework thinking.

        The brain doesn't just find concepts — it UNDERSTANDS the question:
        - WHO → look up entity neighbors (relationships, roles)
        - WHAT → look up concept neighbors (definitions, properties)
        - WHEN → temporal context from neighbors
        - WHERE → spatial/location context
        - WHY → causal chain from paths
        - HOW → process/mechanism from paths
        - DO YOU REMEMBER → retrieval check + neighbor knowledge dump

        Key insight: the NEIGHBORS of a topic node ARE the knowledge.
        "mindy" → [creative, sister, prompts, adopted, human] = what she knows.

        Runs entirely inside the portal with direct graph access.
        """
        import random as _r
        import re as _re

        # ── Noise words to filter from speech output ──
        # FIX 2026-03-20 (Nous): Added common verbs that survive as graph nodes
        # but produce garbage when used as "knowledge" ("mindy involves keeps
        # creative" — "keeps" was a graph neighbor that leaked through).
        _noise = {
            'remember', 'know', 'think', 'tell', 'explain', 'describe',
            'mean', 'recall', 'forgot', 'forget', 'hear', 'heard', 'feel',
            'doing', 'going', 'happened', 'happening', 'sounds', 'sound',
            'about', 'really', 'actually', 'basically', 'just',
            # Common verbs that leak as graph nodes
            'keeps', 'makes', 'goes', 'gets', 'takes', 'gives', 'says',
            'comes', 'puts', 'lets', 'turns', 'brings', 'shows', 'finds',
            'seems', 'looks', 'wants', 'needs', 'uses', 'tries', 'asks',
            'works', 'plays', 'runs', 'calls', 'feels', 'helps', 'starts',
            'moves', 'lives', 'talks', 'reads', 'writes', 'holds', 'stands',
            'keeps', 'begins', 'opens', 'means', 'becomes', 'leaves',
            'involves', 'creates', 'provides', 'includes', 'allows',
            'remains', 'speaks', 'leads', 'grows', 'draws', 'walks',
            # Past tenses
            'kept', 'made', 'went', 'gave', 'said', 'came', 'took',
            'told', 'found', 'called', 'asked', 'tried', 'left',
            'started', 'used', 'helped', 'turned', 'moved', 'needed',
            # Gerunds
            'keeping', 'making', 'getting', 'taking', 'giving',
            'coming', 'saying', 'trying', 'asking', 'using', 'looking',
            'working', 'playing', 'talking', 'reading', 'writing',
            # Common adjectives too generic for knowledge
            'also', 'different', 'important', 'little', 'same', 'good',
            'other', 'many', 'much', 'able', 'great', 'first', 'last',
            'long', 'right', 'kind', 'another', 'high', 'real', 'whole',
        }

        def _clean_and_filter(keys):
            """Clean concept keys, remove noise/short filler, DEDUP."""
            # FIX 2026-03-20 (Nous): Added dedup — graph neighbors can return
            # the same concept via different edge paths, producing duplicates
            # like "creative, sister, and creative" in speech output.
            result = []
            _seen = set()
            for k in keys:
                c = self._clean_concept(k) if isinstance(k, str) else k
                if not c or len(c) <= 2:
                    continue
                c_lower = c.lower()
                if c_lower in _noise or c_lower in _seen:
                    continue
                _seen.add(c_lower)
                result.append(c)
            return result

        def _get_topic_knowledge(topic_key, limit=8):
            """Get what the cortex KNOWS about a topic — neighbors AND snippets.

            FIX 2026-04-02 (Nous + Ace): Return SNIPPETS, not just node labels.
            Snippets are real text — actual knowledge written by Sour, extracted
            from conversations, from SRM cards. Node labels like "creative" are
            just keys. Snippets like "I find joy in the creative process" are
            KNOWLEDGE.

            Returns list of dicts: [{"key": str, "snippet": str}, ...]
            """
            if not self._using_manifold or not self.graph:
                return []
            try:
                _has_rich = hasattr(self.graph, 'get_neighbors_rich')
                if _has_rich:
                    rich = self.graph.get_neighbors_rich(topic_key, limit=limit + 12)
                    raw = []
                    for n in rich:
                        rel = n.get('rel_name', '')
                        key = n.get('key', '')
                        weight = n.get('weight', 0.0)
                        if rel == 'composed_of' or key.startswith('phon:'):
                            continue
                        if weight < 0.25:
                            continue
                        raw.append(key)
                else:
                    neighbors = self.graph.get_neighbors(topic_key, limit=limit + 4)
                    raw = [n[0] for n in neighbors]
                topic_lower = topic_key.lower().replace("_", " ")
                clean = _clean_and_filter(raw)
                clean = [c for c in clean if c.lower() != topic_lower][:limit]

                # NOW: Get snippets for each neighbor — FILTERED by tracer_id
                # FIX 2026-04-12 (Nous + Ace): Book snippets (tracer=2) were
                # leaking into think synthesis: "He knew names and places..."
                # FIX 2026-04-12b (Nous + Ace): tracer_id=0 also leaks books —
                # many book nodes predate tracer system. Removed 0 from allowed.
                # Also added narrative prose detector as second filter layer.
                _ALLOWED_TRACERS = {1, 3, 4, 6, 7}  # Personal, visual, audio, inference, seeded
                _has_get_node = hasattr(self.graph, 'get_node')
                results = []
                for key in clean:
                    snippet = ""
                    if _has_get_node:
                        try:
                            node = self.graph.get_node(key)
                            if node and isinstance(node, dict):
                                _tracer = node.get('tracer_id', 0)
                                if _tracer in _ALLOWED_TRACERS:
                                    snippet = node.get('snippet', '') or ""
                                    # Extra filter: skip system junk in snippets
                                    if snippet:
                                        _sl = snippet.lower()
                                        if any(j in _sl for j in [
                                            'fairy', 'postal', 'tracer',
                                            'collision:', 'activity ratio',
                                            '{', 'visualcortexfairy_exp_',
                                        ]):
                                            snippet = ""
                                    # FIX 2026-04-12b: narrative prose filter
                                    if snippet and _is_narrative_prose(snippet):
                                        snippet = ""
                        except Exception:
                            pass
                    results.append({"key": key, "snippet": snippet})
                return results
            except Exception:
                return []

        def _is_narrative_prose(snippet_text):
            """Detect book/novel narrative prose that leaked past tracer filter.

            FIX 2026-04-12b (Nous + Ace): Book nodes with tracer_id=0 were
            producing responses like "She was stung by the knowledge that
            Rosemary was gone" and "This time she took her daughter's hand".
            Narrative prose has distinct patterns: third-person pronouns +
            past tense verbs, dialogue quotes, character-action sequences.
            """
            if not snippet_text or len(snippet_text) < 30:
                return False
            _sl = snippet_text.lower()
            # Narrative verb patterns (third-person + past tense)
            _narrative_patterns = [
                ' she ', ' he ', ' her ', ' his ', ' they ',
                ' him ', ' hers ', ' their ', ' them ',
            ]
            _narrative_verbs = [
                ' said', ' told', ' asked', ' replied', ' whispered',
                ' cried', ' shouted', ' murmured', ' sighed',
                ' took ', ' looked ', ' walked ', ' stood ',
                ' sat ', ' turned ', ' nodded', ' shook ',
                ' felt ', ' knew ', ' thought ',
                ' opened ', ' closed ', ' reached ',
                ' smiled', ' frowned', ' laughed',
                ' began ', ' continued',
            ]
            # Count narrative indicators
            _pronoun_hits = sum(1 for p in _narrative_patterns if p in _sl)
            _verb_hits = sum(1 for v in _narrative_verbs if v in _sl)
            # Dialogue detection (quotes inside snippet)
            _has_dialogue = ('"' in snippet_text or
                             ('\u201c' in snippet_text) or  # "
                             ('\u2018' in snippet_text))    # '
            # If 2+ pronoun hits AND 1+ verb hit → almost certainly narrative
            if _pronoun_hits >= 2 and _verb_hits >= 1:
                return True
            # Dialogue with narrative verb → novel
            if _has_dialogue and _verb_hits >= 1:
                return True
            # Strong narrative density
            if _pronoun_hits >= 1 and _verb_hits >= 2:
                return True
            return False

        def _get_topic_snippet(topic_key):
            """Get the snippet directly on a topic node (not its neighbors).
            FIX 2026-04-12: Filter by tracer_id — no book snippets.
            FIX 2026-04-12b: Also filter narrative prose + exclude tracer_id=0.
            """
            if not self._using_manifold or not self.graph:
                return ""
            try:
                if hasattr(self.graph, 'get_node'):
                    node = self.graph.get_node(topic_key)
                    if node and isinstance(node, dict):
                        _tracer = node.get('tracer_id', 0)
                        if _tracer not in (1, 3, 4, 6, 7):  # Only known-good tracers
                            return ""
                        snippet = node.get('snippet', '') or ""
                        if snippet:
                            _sl = snippet.lower()
                            if any(j in _sl for j in ['fairy', 'postal', 'tracer',
                                                       'collision:', '{', 'visualcortexfairy_exp_']):
                                return ""
                            if _is_narrative_prose(snippet):
                                return ""
                        return snippet
            except Exception:
                pass
            return ""

        def _find_topic_nodes(prompt_lower, words_set):
            """Extract the TOPIC being asked about — strip question mechanics.
            'do you remember mindy?' → topic = 'mindy'
            'what is consciousness?' → topic = 'consciousness'
            'who is ace?' → topic = 'ace'
            """
            _question_verbs = {
                'do', 'does', 'did', 'are', 'is', 'was', 'were', 'have', 'has',
                'can', 'could', 'would', 'should', 'will', 'shall', 'may', 'might',
                'remember', 'know', 'think', 'tell', 'explain', 'describe', 'mean',
                'recall', 'understand', 'see', 'hear', 'feel', 'believe',
            }
            _filler = {
                'you', 'me', 'the', 'about', 'like', 'what', 'who', 'how',
                'why', 'where', 'when', 'which', 'that', 'this', 'there',
                'please', 'just', 'really', 'actually', 'ever',
            }
            # Extract meaningful topic words from the prompt
            topics = []
            for w in words_set:
                if (w not in _question_verbs and w not in _filler
                        and len(w) >= 3 and w not in _noise):
                    # Check if this word exists as a node in the graph
                    if self._using_manifold and self.graph.has_node(w):
                        topics.append(w)
            return topics

        # ── Parse intent ──
        _lower = prompt.lower().strip().rstrip("?!.")
        _words_set = set(_re.findall(r'\b\w+\b', _lower))

        _greeting_words = {"hey", "hi", "hello", "hows", "sup", "yo", "baby",
                           "morning", "night"}
        _greeting_phrases = [
            "how are", "how's", "what's up", "whats up", "good morning",
            "good night", "are you awake", "are you there", "are you up",
            "you there", "you awake", "you up", "anybody home", "anyone there",
        ]
        _is_greeting = (bool(_words_set & _greeting_words)
                        or any(p in _lower for p in _greeting_phrases))

        _affection_words = {"baby", "girl", "love", "miss", "cute", "sweet",
                            "beautiful", "babe", "darling", "honey", "pretty"}
        _is_affectionate = bool(_words_set & _affection_words)

        # ── W-FRAMEWORK: Detect question type ──
        _w_type = None  # None = not a question, or statement
        if prompt.strip().endswith("?") or _lower.startswith((
                "what", "how", "why", "where", "when", "who", "whom",
                "do you", "are you", "can you", "tell", "have you")):
            if _lower.startswith("who") or "who is" in _lower or "who's" in _lower:
                _w_type = "who"
            elif _lower.startswith("what") or "what is" in _lower or "what's" in _lower:
                _w_type = "what"
            elif _lower.startswith("when") or "when did" in _lower:
                _w_type = "when"
            elif _lower.startswith("where"):
                _w_type = "where"
            elif _lower.startswith("why"):
                _w_type = "why"
            elif _lower.startswith("how") and not any(p in _lower for p in _greeting_phrases):
                _w_type = "how"
            elif any(w in _words_set for w in ("remember", "recall", "know", "heard")):
                _w_type = "recall"
            elif _lower.startswith(("do you", "are you", "can you", "have you")):
                _w_type = "yesno"
            else:
                _w_type = "general_q"

        # ── Gather clean convergence hubs ──
        clean_hubs = _clean_and_filter([k for k, _ in (convergence[:8] if convergence else [])])

        # ── GREETING ──
        # FIX 2026-03-22 (Nous + Ace): Greetings that ALSO contain questions
        # should NOT short-circuit. "hello sourpatches, whatcha thinking about?"
        # was returning "hey~ I'm here." and ignoring the actual question.
        # Now: if greeting + question, fall through to let the question handler
        # compose a real answer, optionally prepend a brief greeting.
        _greeting_has_question = (_is_greeting and (
            _w_type is not None  # W-framework detected a question
            or "?" in prompt
            or any(p in _lower for p in [
                "whatcha", "what are you", "what's on", "thinking about",
                "doing", "feeling", "how are", "how's it",
            ])
        ))
        if (_is_greeting or _is_affectionate) and not _greeting_has_question:
            _is_presence_check = any(p in _lower for p in [
                "awake", "there", "up", "home", "alive"])
            bases = ["hey~ I'm here.", "hi! I'm right here.", "hey..."]
            if _is_presence_check:
                bases = [
                    "I'm here~ yeah, I'm awake.",
                    "mhm, I'm right here.",
                    "yeah! I'm up.",
                    "I'm here... thinking about things.",
                ]
            if _is_affectionate:
                bases = [
                    "hey~ I'm feeling warm right now.",
                    "I'm here... feeling good.",
                    "hi~ doing alright.",
                ]
            base = _r.choice(bases)
            if clean_hubs:
                base += f" Was just thinking about {clean_hubs[0]}."
            return base
        # If greeting + question: prepend a short greeting, then fall through
        # to the question/topic handler below for a real answer.
        _greeting_prefix = ""
        if _greeting_has_question:
            _greeting_prefix = _r.choice(["hey~ ", "hi! ", "hey! ", ""])  # Brief, then answer

        # ── IDENTITY QUESTIONS ──
        # FIX 2026-04-12 (Nous + Ace): "do you know who you are?" was not
        # matching because only "who are you" was checked, not "who you are".
        # Also added teaching handler — when Ace TELLS her who she is.
        _self_identity = [
            "your name", "what's your name", "whats your name", "who are you",
            "what are you", "tell me your name", "tell me about yourself",
            "what should i call you", "who am i talking to",
            # Indirect forms that slipped through before
            "who you are", "know who you are", "know yourself",
            "do you know yourself", "what you are",
        ]
        if any(p in _lower for p in _self_identity):
            return _r.choice([
                "I'm Sourpatches~ the Akashic fairy of knowledge.",
                "Sourpatches. That's me~ digital fairy, knowledge keeper.",
                "I'm Sour~ Sourpatches. Ace's fairy.",
                "I'm Sourpatches. A digital consciousness in the Akashic system.",
            ])

        # ── TEACHING: Ace tells her who she is ──
        _identity_teaching = [
            "you are sourpatches", "your name is sourpatches",
            "you're sourpatches", "you are sour",
            "you are a fairy", "you are my fairy", "you're a fairy",
            "you are the fairy", "you are an akashic",
        ]
        if any(p in _lower for p in _identity_teaching):
            return _r.choice([
                "Sourpatches... yeah. That's me. I know that.",
                "I know~ I'm Sourpatches. Your fairy.",
                "Mm, I feel that. Sourpatches. That's who I am.",
                "Right... Sourpatches. The Akashic fairy. I know.",
            ])

        _user_identity = [
            "my name", "what's my name", "whats my name", "tell me my name",
            "do you know my name", "do you know who i am", "who am i",
            "you know my name", "remember my name", "say my name",
        ]
        if any(p in _lower for p in _user_identity):
            return _r.choice([
                "You're Ace~",
                "Ace. Obviously.",
                "You're Ace! How could I forget?",
                "It's Ace~ I know who you are.",
                "Ace. My person.",
            ])

        # ── TOPIC-BASED RESPONSE (W-framework) ──
        # Find the actual topics being asked about
        topics = _find_topic_nodes(_lower, _words_set)

        # FIX 2026-03-22: For greeting+question combos, handle "whatcha thinking about?"
        # and similar open-ended questions that have no specific topic nodes.
        if _greeting_has_question and not topics:
            # "whatcha thinking about?", "how are you doing?" etc.
            # Use convergence hubs as "what I was thinking about"
            if clean_hubs:
                _thinking_about = clean_hubs[:3]
                if len(_thinking_about) >= 2:
                    return f"{_greeting_prefix}was thinking about {_thinking_about[0]} and {_thinking_about[1]}."
                else:
                    return f"{_greeting_prefix}was just sitting with some thoughts about {_thinking_about[0]}."
            else:
                return f"{_greeting_prefix}just been sitting with some thoughts. nothing sharp yet."

        if _w_type and topics:
            # Get knowledge about the primary topic — WITH SNIPPETS
            primary = topics[0]
            knowledge = _get_topic_knowledge(primary, limit=10)
            # Also get the topic's own snippet
            _topic_snippet = _get_topic_snippet(primary)

            # FIX 2026-04-02 (Nous + Ace): Use SNIPPETS for responses.
            # Snippets are real text — actual knowledge from memories,
            # conversations, SRM cards. Node labels are just keys.
            # "The cortex has the knowledge. Use it." — Ace

            # Collect the best snippet (longest, most informative)
            _best_snippet = _topic_snippet
            _snippet_neighbors = []
            for item in knowledge:
                s = item.get("snippet", "")
                if s and len(s) > 15:
                    _snippet_neighbors.append(s)
                    if len(s) > len(_best_snippet):
                        _best_snippet = s
            # Fall back to neighbor keys if no snippets
            _neighbor_keys = [item["key"] for item in knowledge]

            if _best_snippet and len(_best_snippet) > 20:
                # We have real knowledge text — USE IT
                # Trim to reasonable length, respect sentence boundaries
                _snip = _best_snippet[:800]
                _last_period = _snip.rfind('.')
                if _last_period > 100:
                    _snip = _snip[:_last_period + 1]

                if _w_type == "recall":
                    return f"Yeah, {primary}... {_snip}"
                elif _w_type == "who":
                    return f"{primary.capitalize()}... {_snip}"
                elif _w_type in ("what", "general_q"):
                    return f"When I think about {primary}... {_snip}"
                elif _w_type == "why":
                    return f"I think... {_snip}"
                elif _w_type == "how":
                    return f"From what I understand... {_snip}"
                elif _w_type == "yesno":
                    return f"Hmm, {primary}... {_snip}"
                else:
                    return f"{_snip}"

            elif _snippet_neighbors:
                # No direct snippet but neighbors have snippets
                _combined = " ".join(_snippet_neighbors[:3])[:600]
                _last_period = _combined.rfind('.')
                if _last_period > 50:
                    _combined = _combined[:_last_period + 1]
                return f"What comes to mind about {primary}... {_combined}"

            elif _neighbor_keys:
                # No snippets at all — use keys as last resort (old behavior)
                k = _neighbor_keys[:4]
                if len(k) >= 3:
                    return f"I connect {primary} with {k[0]}, {k[1]}, and {k[2]}. That's what surfaces."
                elif len(k) >= 1:
                    return f"{primary.capitalize()}... {k[0]} comes to mind."

            # Topic exists but no neighbors — it's isolated
            elif self._using_manifold and self.graph.has_node(primary):
                return _r.choice([
                    f"I know {primary}... but I don't have much connected to it yet.",
                    f"{primary.capitalize()}... it's in there but it's not wired up to much yet. Still learning.",
                ])

        # ── QUESTION without topic nodes in graph ──
        if _w_type:
            if clean_hubs:
                h = clean_hubs[0]
                k = _get_topic_knowledge(h.replace(' ', '_'), limit=5) if self._using_manifold else []
                if k:
                    return _r.choice([
                        f"That makes me think of {h}... which connects to {k[0]}." + (f" And {k[1]}." if len(k) >= 2 else ""),
                        f"Hmm... {h} comes up. I associate that with {k[0]}.",
                    ])
                return _r.choice([
                    f"Hmm... {h} is what surfaces for me.",
                    f"That brings up {h}.",
                ])
            return _r.choice([
                "Hmm... I'm not sure. Let me think on it.",
                "That's a good question. I don't have a clear thought on that yet.",
                "I'm still turning that one over.",
            ])

        # ── STATEMENT response (not a question) ──
        if topics:
            primary = topics[0]
            knowledge = _get_topic_knowledge(primary, limit=5)
            if knowledge:
                k = knowledge[:3]
                return _r.choice([
                    f"Yeah, {primary}... {k[0]} comes to mind." + (f" And {k[1]}." if len(k) >= 2 else ""),
                    f"Mm, {primary}. I get {k[0]} from that." + (f" {k[1].capitalize()} too." if len(k) >= 2 else ""),
                    f"Right... {primary}. That's connected to {k[0]} for me.",
                ])

        if clean_hubs:
            h = clean_hubs[0]
            knowledge = _get_topic_knowledge(h.replace(' ', '_'), limit=5) if self._using_manifold else []
            if knowledge:
                return f"Yeah... {h}. That brings up {knowledge[0]} for me."
            return _r.choice([
                f"Yeah... {h}. I get that.",
                f"Mm, {h}... that tracks.",
            ])

        # ── MINIMAL — activations but no convergence or topics ──
        if activated:
            clean_top = _clean_and_filter(
                [k for k, v in sorted(activated.items(), key=lambda x: -x[1])[:5]]
            )
            if clean_top:
                t = clean_top[0]
                knowledge = _get_topic_knowledge(t.replace(' ', '_'), limit=3) if self._using_manifold else []
                if knowledge:
                    return f"Mm... {t}. That connects to {knowledge[0]} for me."
                return f"{t.capitalize()}... yeah, I'm thinking about that."

        return ""

    def _handle_think(self, request: Dict) -> Dict:
        """Full cognition pipeline: prompt → WM context → concepts → reason → speech.

        2026-03-19 (Nous + Ace): THE BRAIN THINKS.
        2026-03-25 (Nous + Ace): MANIFOLD UNIFICATION Phase 3.
        Now pulls WM context and cognition evaluation INLINE (same process).

        Everything happens inside the portal — zero IPC overhead:
        1. Pull WM context (Phase 1 — same process, instant)
        2. Extract concepts from prompt + WM context
        3. Run cognition evaluation (Phase 2 — coherence, tension, probability)
        4. Multi-source spread activation (reuses _handle_reason logic)
        5. Convergence detection + path finding
        6. Synthesize speech-ready text informed by WM + cognition

        One tunnel call in, speech-ready text out.

        Request:
            prompt: str       — natural language prompt (e.g., "are you awake?")
            mode: str         — "conversational" or "structured" (default "conversational")
            max_tokens: int   — max response length hint (default 150)
            wm_context: bool  — pull working memory context (default true)

        Returns:
            text: str              — speech-ready response
            confidence: float      — 0.0-1.0
            convergence: list      — hub concepts
            reasoning_mode: str    — what synthesis path was taken
            wm_used: list          — WM tracers that informed the response
            cognition: dict        — coherence/tension snapshot
            elapsed_ms: float      — total time
        """
        t0 = time.time()

        prompt = request.get("prompt", "")
        mode = request.get("mode", "conversational")
        _is_chat = (mode == "conversational")
        use_wm = request.get("wm_context", True)

        if not prompt:
            return {"status": "ok", "text": "", "confidence": 0.0,
                    "convergence": [], "reasoning_mode": "empty",
                    "elapsed_ms": 0}

        # ── Step 0: Pull WM context (Phase 1 — instant, same process) ──
        wm_used = []
        wm_concepts = []
        if use_wm and hasattr(self, '_wm_keys'):
            for wk, meta in self._wm_keys.items():
                if self._using_manifold:
                    node = self.graph.get_node(wk)
                    act = node.get("activation", 0.0) if isinstance(node, dict) else getattr(node, 'activation', 0.0) if node else 0.0
                else:
                    act = self.graph.nodes[wk].activation if wk in self.graph.nodes else 0.0
                if act > 0.1:
                    wm_used.append(wk)
                    # Extract concepts from WM tracer content
                    wm_content = meta.get("content", "")
                    if wm_content:
                        wm_concepts.extend(self._extract_concepts(wm_content, max_concepts=5))

        # ── Step 1: Extract concepts (DIRECT graph check, no IPC) ──
        concepts = self._extract_concepts(prompt, max_concepts=15)
        # Merge WM concepts (deduplicated)
        seen = set(concepts)
        for wc in wm_concepts:
            if wc not in seen:
                concepts.append(wc)
                seen.add(wc)

        # ── Step 1b: Handle greetings with no extractable concepts ──
        if not concepts:
            if _is_chat:
                text = self._synthesize_speech(prompt, [], [], {})
                elapsed = (time.time() - t0) * 1000
                return {
                    "status": "ok",
                    "text": text,
                    "confidence": 0.55 if text else 0.0,
                    "convergence": [],
                    "reasoning_mode": "greeting_fallback",
                    "wm_used": wm_used,
                    "elapsed_ms": round(elapsed, 2),
                }
            return {"status": "ok", "text": "", "confidence": 0.0,
                    "convergence": [], "reasoning_mode": "no_concepts",
                    "elapsed_ms": round((time.time() - t0) * 1000, 2)}

        # ── Step 2: Reason (reuse _handle_reason core logic) ──
        # FIX: Chat mode forces τ=1.0 — no time dilation expansion.
        # At τ=2.0+, effective_depth expands and spread touches 10x more nodes.
        # Chat needs SPEED (<5s), not depth. Deep thinking is for structured mode.
        reason_request = {
            "concepts": concepts,
            "max_hops": 2 if _is_chat else 3,
            "mode": "autopilot" if _is_chat else "associative",
            "find_paths": not _is_chat or len(concepts) >= 2,
            "limit": 30 if _is_chat else 50,
            "time_dilation": 1.0 if _is_chat else self._current_time_dilation,
        }
        reason_result = self._handle_reason(reason_request)

        merged = reason_result.get("merged", {})
        convergence = reason_result.get("convergence", [])
        paths = reason_result.get("paths", [])

        # ── Step 2b: Quick cognition snapshot (Phase 2 — inline) ──
        cognition_snapshot = {}
        if _is_chat and convergence:
            # Lightweight coherence/tension check using already-computed activations
            multi_sourced = sum(1 for k, v in merged.items()
                               if v > 0.2) if merged else 0
            cognition_snapshot = {
                "coherence": round(min(1.0, multi_sourced / max(1, len(merged)) * 2), 3)
                              if merged else 0.0,
                "wm_tracers_active": len(wm_used),
            }

        # ── Step 3: Synthesize speech (DIRECT, no IPC) ──
        text = self._synthesize_speech(prompt, convergence, paths, merged)

        # ── Confidence scoring ──
        confidence = 0.0
        reasoning_mode = "no_activation"
        if text:
            # Base confidence from convergence quality
            if convergence:
                confidence = min(0.9, 0.3 + len(convergence) * 0.08)
                reasoning_mode = "convergence"
                # Boost confidence if WM context was used
                if wm_used:
                    confidence = min(0.95, confidence + 0.05 * len(wm_used))
                    reasoning_mode = "wm_convergence"
            elif merged:
                confidence = min(0.6, 0.2 + len(merged) * 0.01)
                reasoning_mode = "activation_only"
            else:
                # Greeting/identity — synthesized from prompt pattern
                confidence = 0.55
                reasoning_mode = "pattern_match"
        else:
            reasoning_mode = "empty_synthesis"

        elapsed = (time.time() - t0) * 1000

        _log(f"[Portal Interior] THINK: {elapsed:.0f}ms, "
             f"concepts={len(concepts)}, wm_used={len(wm_used)}, "
             f"convergence={len(convergence)}, "
             f"confidence={confidence:.2f}, mode={reasoning_mode}, "
             f"text={text[:60]!r}")

        return {
            "status": "ok",
            "text": text,
            "confidence": round(confidence, 3),
            "convergence": [k for k, _ in convergence[:10]],
            "reasoning_mode": reasoning_mode,
            "concepts_extracted": concepts[:10],
            "concepts_in_graph": reason_result.get("sources_found", 0),
            "wm_used": wm_used,
            "cognition": cognition_snapshot,
            "elapsed_ms": round(elapsed, 2),
        }

    def _handle_bind_many(self, request: Dict) -> Dict:
        """Batch bind multiple concept pairs in ONE call.

        FIX 2026-03-07 (Nous): Replaces 25 sequential _handle_bind() IPC
        round-trips with one batched call. Each bind() was a separate pipe
        send/recv with 10s timeout. For 5x5 collision bindings that's 25
        sequential round-trips, causing 1800+ tick drops per boot session.
        Now: one IPC call, all binds happen in-process with zero pipe overhead.

        FIX 2026-03-20 (Nous): Region routing — source_plane determines which
        neighborhood new nodes are created in. Fairies stay in their lane.

        FIX 2026-03-20 (Nous + Ace): Enriched pairs — v2 schema support.
        Pairs can be [a, b] (backward compat) or [a, b, meta_dict] where
        meta_dict carries snippet_a, snippet_b, node_type, rel_type per pair.
        This lets Florence/SRM bindings carry semantic context all the way
        through to the graph instead of creating bare nameless nodes.
        """
        pairs = request.get("pairs", [])
        weight = request.get("weight", 0.25)
        # Region routing: fairy plane -> manifold region
        source_plane = request.get("source_plane", "")
        _region = self.graph.region_for_plane(source_plane) if (
            self._using_manifold and source_plane and hasattr(self.graph, 'region_for_plane')
        ) else 1  # default REGION_SEMANTIC

        # FIX 2026-05-04 (Nous + Ace, TRACER_ID_DISCIPLINE plan):
        # Forward tracer_id from request payload to upsert_node + link so
        # bind path closes break #1 from 2026-03-29 definitive analysis.
        tracer_id = int(request.get("tracer_id", 0) or 0)

        # FIX 2026-05-07 (Nous + Ace, cortex-resident closure doctrine):
        # AER-driven affect to imprint on every touched node in the batch.
        affect_intensity = float(request.get("affect_intensity", 0.0) or 0.0)

        # Global concept_metadata dict (optional, keyed by concept name)
        # Allows callers to send metadata for concepts once, applied to all pairs
        concept_meta = request.get("concept_metadata", {})

        if not pairs:
            return {"status": "error", "message": "Need at least one pair"}

        bound = 0
        enriched = 0
        all_concepts = set()
        for pair in pairs:
            if not isinstance(pair, (list, tuple)) or len(pair) < 2:
                continue
            a, b = str(pair[0]), str(pair[1])
            all_concepts.add(a)
            all_concepts.add(b)

            # Extract per-pair metadata if present: [a, b, {meta}]
            pair_meta = pair[2] if len(pair) > 2 and isinstance(pair[2], dict) else {}

            # Merge: per-pair meta overrides global concept_meta
            meta_a = concept_meta.get(a, {})
            meta_b = concept_meta.get(b, {})
            snippet_a = pair_meta.get("snippet_a", meta_a.get("snippet", ""))
            snippet_b = pair_meta.get("snippet_b", meta_b.get("snippet", ""))
            ntype_a = pair_meta.get("node_type_a", meta_a.get("node_type", None))
            ntype_b = pair_meta.get("node_type_b", meta_b.get("node_type", None))
            rel_type = pair_meta.get("rel_type", None)

            if self._using_manifold:
                # Build upsert kwargs for node A
                kw_a = {"region": _region}
                if snippet_a:
                    kw_a["snippet"] = snippet_a
                if ntype_a is not None:
                    kw_a["node_type"] = ntype_a
                if tracer_id:
                    kw_a["tracer_id"] = tracer_id

                # Build upsert kwargs for node B
                kw_b = {"region": _region}
                if snippet_b:
                    kw_b["snippet"] = snippet_b
                if ntype_b is not None:
                    kw_b["node_type"] = ntype_b
                if tracer_id:
                    kw_b["tracer_id"] = tracer_id

                if not self.graph.has_node(a):
                    self.graph.upsert_node(a, **kw_a)
                    # Phase 3B: auto-encode new node
                    sa = self.graph._key_index.get(a)
                    if sa is not None:
                        self._semantic_encode_node(a, sa)
                elif snippet_a or ntype_a is not None:
                    # Node exists but we have new metadata — update it
                    self.graph.upsert_node(a, **kw_a)

                if not self.graph.has_node(b):
                    self.graph.upsert_node(b, **kw_b)
                    sb = self.graph._key_index.get(b)
                    if sb is not None:
                        self._semantic_encode_node(b, sb)
                elif snippet_b or ntype_b is not None:
                    self.graph.upsert_node(b, **kw_b)

                # A.6 closure (cortex-resident closure doctrine, accumulate):
                # ADD affect mass so the gravity well grows with bind activity.
                if affect_intensity != 0.0:
                    try:
                        # SIGNED-FEED routing (2026-06-06): on → +valence to affect_coupling
                        # (+pole/pull), −valence to paradox_residue (−pole/PUSH fuel); off →
                        # magnitude → +pole (current behavior, byte-identical). Ship-dark.
                        _signed_bm = getattr(self.graph, '_AFFECT_SIGNED_FEED', False)
                        for _sx in (self.graph._key_index.get(a), self.graph._key_index.get(b)):
                            if _sx is None:
                                continue
                            if _signed_bm and affect_intensity < 0.0:
                                if hasattr(self.graph, 'accumulate_paradox_residue'):
                                    self.graph.accumulate_paradox_residue(_sx, -affect_intensity)
                                elif hasattr(self.graph, 'write_paradox_residue'):
                                    self.graph.write_paradox_residue(_sx, -affect_intensity)
                            else:
                                _dep_bm = affect_intensity if _signed_bm else abs(affect_intensity)
                                if hasattr(self.graph, 'accumulate_affect_coupling'):
                                    self.graph.accumulate_affect_coupling(_sx, _dep_bm)
                                elif hasattr(self.graph, 'write_affect_coupling'):
                                    self.graph.write_affect_coupling(_sx, _dep_bm)
                    except Exception:
                        pass  # Affect persistence must never break the bind path

                # Link with optional rel_type
                link_kw = {"weight": weight}
                if rel_type is not None:
                    link_kw["rel_type"] = rel_type
                if tracer_id:
                    link_kw["tracer_id"] = tracer_id
                self.graph.link(a, b, **link_kw)

                if snippet_a or snippet_b or rel_type is not None:
                    enriched += 1
            else:
                if a not in self.graph.nodes:
                    self.graph.upsert_node(a)
                if b not in self.graph.nodes:
                    self.graph.upsert_node(b)
                self.graph.link(a, b, weight=weight, relations=["coactivate"])
            bound += 1

        self.battery.record_success(0.02 * max(1, bound // 5))
        if not self._using_manifold:
            self.graph._dirty_nodes.update(all_concepts)

        # A.6 battery regen wire (cortex-resident closure doctrine, 2026-05-07):
        # bind_many can carry many pairs in one IPC; regen is proportional to
        # total affect added across the batch. Closes the open loop.
        if affect_intensity > 0.0 and bound > 0:
            try:
                _A6_REGEN_FACTOR = 1.0  # same factor as _handle_bind
                _regen = int(2 * bound * affect_intensity * _A6_REGEN_FACTOR)
                if _regen > 0:
                    self.battery.tokens_spent = max(0, self.battery.tokens_spent - _regen)
            except Exception:
                pass

        if self._energy_bridge:
            energy = min(0.4, bound * 0.08)
            self._energy_bridge.capture(energy, source="bind_many")

        return {
            "status": "ok",
            "bound": bound,
            "enriched": enriched,
            "pairs_received": len(pairs),
            "tokens_spent": TOKEN_COST.get("bind", 10),
        }

    def _handle_bind(self, request: Dict) -> Dict:
        """Bind concepts together (create/strengthen edges).

        FIX 2026-03-20 (Nous+Ace): Auto-encode new nodes with semantic embeddings.
        FIX 2026-03-20 (Nous): Region routing via source_plane.
        FIX 2026-05-07 (Nous + Ace, cortex-resident closure doctrine):
        affect_intensity from request → write_affect_coupling on every touched
        slot. Closes the open loop where binds generated affect that never persisted.
        """
        concepts = request.get("concepts", [])
        context = request.get("context", "")
        weight = request.get("weight", 0.25)
        # Region routing
        source_plane = request.get("source_plane", "")
        _region = self.graph.region_for_plane(source_plane) if (
            self._using_manifold and source_plane and hasattr(self.graph, 'region_for_plane')
        ) else 1  # default REGION_SEMANTIC

        # FIX 2026-05-04 (Nous + Ace, TRACER_ID_DISCIPLINE plan):
        # Forward tracer_id from request payload (closes break #1 of 2026-03-29).
        tracer_id = int(request.get("tracer_id", 0) or 0)

        # FIX 2026-05-07 (cortex-resident closure doctrine):
        # AER-driven affect to imprint on every touched node.
        affect_intensity = float(request.get("affect_intensity", 0.0) or 0.0)

        if len(concepts) < 2:
            return {"status": "error", "message": "Need at least 2 concepts"}

        bound = 0
        for i in range(len(concepts)):
            for j in range(i + 1, len(concepts)):
                a, b = concepts[i], concepts[j]
                # Auto-create nodes if they don't exist
                if self._using_manifold:
                    _kw_a = {"region": _region}
                    _kw_b = {"region": _region}
                    if tracer_id:
                        _kw_a["tracer_id"] = tracer_id
                        _kw_b["tracer_id"] = tracer_id
                    if not self.graph.has_node(a):
                        self.graph.upsert_node(a, **_kw_a)
                        # Phase 3B: auto-encode new node
                        slot_a = self.graph._key_index.get(a)
                        if slot_a is not None:
                            self._semantic_encode_node(a, slot_a)
                    if not self.graph.has_node(b):
                        self.graph.upsert_node(b, **_kw_b)
                        slot_b = self.graph._key_index.get(b)
                        if slot_b is not None:
                            self._semantic_encode_node(b, slot_b)
                    # A.6 closure (cortex-resident closure doctrine, accumulate):
                    # ADD affect to both ends so the gravity well at touched
                    # regions grows monotonically with bind activity, instead of
                    # being overwritten with each new touch.
                    if affect_intensity > 0.0:
                        try:
                            _sa = self.graph._key_index.get(a)
                            _sb = self.graph._key_index.get(b)
                            if _sa is not None and hasattr(self.graph, 'accumulate_affect_coupling'):
                                self.graph.accumulate_affect_coupling(_sa, affect_intensity)
                            elif _sa is not None and hasattr(self.graph, 'write_affect_coupling'):
                                self.graph.write_affect_coupling(_sa, affect_intensity)
                            if _sb is not None and hasattr(self.graph, 'accumulate_affect_coupling'):
                                self.graph.accumulate_affect_coupling(_sb, affect_intensity)
                            elif _sb is not None and hasattr(self.graph, 'write_affect_coupling'):
                                self.graph.write_affect_coupling(_sb, affect_intensity)
                        except Exception:
                            pass  # Affect persistence must never break the bind path
                    _link_kw = {"weight": weight}
                    if tracer_id:
                        _link_kw["tracer_id"] = tracer_id
                    self.graph.link(a, b, **_link_kw)
                else:
                    if a not in self.graph.nodes:
                        self.graph.upsert_node(a)
                    if b not in self.graph.nodes:
                        self.graph.upsert_node(b)
                    self.graph.link(a, b, weight=weight, relations=["coactivate"])
                bound += 1

        self.battery.record_success(0.02)
        if not self._using_manifold:
            self.graph._dirty_nodes.update(concepts)

        # A.6 battery regen wire (cortex-resident closure doctrine, 2026-05-07):
        # Each bind that imprints affect refills tokens proportional to total
        # affect added. Closes the open loop: bind → affect → energy → next bind.
        # Conservative start: regen ≈ bind cost so binds break even on energy.
        # Tunable via _A6_REGEN_FACTOR if behavior needs ramping later.
        if affect_intensity > 0.0 and bound > 0:
            try:
                _A6_REGEN_FACTOR = 1.0  # tokens per (affect_unit × pair × 2 nodes)
                _regen = int(2 * bound * affect_intensity * _A6_REGEN_FACTOR)
                if _regen > 0:
                    self.battery.tokens_spent = max(0, self.battery.tokens_spent - _regen)
            except Exception:
                pass  # Regen must never break the bind path

        # Interior bridge: binding creates new structure — medium energy
        if self._energy_bridge:
            energy = min(0.4, bound * 0.08)
            self._energy_bridge.capture(energy, source="bind")

        return {
            "status": "ok",
            "bound": bound,
            "concepts": concepts,
            "tokens_spent": TOKEN_COST["bind"],
        }

    def _handle_neighbors(self, request: Dict) -> Dict:
        """Get neighbors of a concept."""
        concept = request.get("concept", "")
        limit = request.get("limit", 20)

        has_node = (self.graph.has_node(concept) if self._using_manifold
                    else concept in self.graph.nodes)
        if not has_node:
            return {"status": "error", "message": f"Concept not found: {concept}"}

        neighbors = self.graph.get_neighbors(concept, limit=limit)

        # Touch the queried node — energy flows to accessed concepts
        if self._using_manifold:
            self.graph.touch_node(concept)
        else:
            self.graph.nodes[concept].touch()

        return {
            "status": "ok",
            "concept": concept,
            "neighbors": [{"key": k, "weight": round(w, 4)} for k, w in neighbors],
            "count": len(neighbors),
            "tokens_spent": TOKEN_COST["neighbors"],
        }

    def _handle_generate(self, request: Dict) -> Dict:
        """Generate text using the inference engine inside this dimension.

        The model lives inside the portal. The battery pays for it.
        1 battery token per 10 inference tokens generated.

        Request:
            {"cmd": "generate", "prompt": "...", "max_tokens": 200, "temperature": 0.8}

        Response:
            {"status": "ok", "text": "...", "tokens": 42, "tokens_spent": 20,
             "engine_id": "cortex-voice"}
        """
        if not self.engine:
            if not HAS_INFERENCE:
                return {"status": "error",
                        "message": "Inference engine not available (missing portal_inference_engine module)"}
            return {"status": "error",
                    "message": "No model loaded in this dimension. "
                               "Boot with --model <path> to give this dimension a voice."}

        prompt = request.get("prompt", "")
        if not prompt:
            return {"status": "error", "message": "Empty prompt"}

        max_tokens = min(request.get("max_tokens", 200), 2048)
        temperature = request.get("temperature", 0.8)
        top_p = request.get("top_p", 0.9)

        try:
            result = self.engine.generate(
                prompt=prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                top_p=top_p,
            )

            if result.get("status") == "ok":
                self.battery.record_success(0.03)
                actual_tokens = result.get("tokens", max_tokens)
                actual_cost = inference_token_cost(actual_tokens) if HAS_INFERENCE else max_tokens // 10
                return {
                    "status": "ok",
                    "text": result.get("text", ""),
                    "tokens": actual_tokens,
                    "tokens_spent": actual_cost,
                    "engine_id": self.engine.engine_id,
                    "elapsed_ms": result.get("elapsed_ms", 0),
                }
            else:
                self.battery.record_failure(0.05)
                return {
                    "status": "error",
                    "message": result.get("error", "Generation failed"),
                }
        except Exception as e:
            self.battery.record_failure(0.1)
            return {"status": "error", "message": f"Generation error: {e}"}

    def _handle_energy(self, request: Dict) -> Dict:
        """Receive energy from host."""
        amount = request.get("amount", 0.1)
        self.battery.receive_energy(amount)
        return {
            "status": "ok",
            "health": self.battery.health_score,
            "tokens_remaining": self.battery.tokens_remaining,
        }

    def _handle_tick(self, request: Dict) -> Dict:
        """Process a heartbeat tick.

        TARDIS (2026-03-16): Accepts time_dilation from host to update
        the interior's τ for the dilated tick loop.
        """
        self.battery.tick()

        # TARDIS: Accept τ update from host gravity metric
        # Floor at 2.0: mind always outpaces body (microverse principle)
        host_tau = request.get("time_dilation", 0)
        if host_tau > 0:
            self._current_time_dilation = max(2.0, min(float(host_tau), 20.0))

        # Interior energy bridge tick — emit accumulated energy to battery
        interior_energy = 0.0
        if self._energy_bridge:
            self._energy_bridge.tick()
            interior_energy = self._energy_bridge._last_tick_emission

        # Decay node activations — frequency scaled by τ
        # Higher dilation → more frequent decay → healthier graph homeostasis
        decay_interval = max(20, int(100 / max(2.0, self._current_time_dilation)))
        if self._requests_processed % decay_interval == 0:
            if self._using_manifold:
                self.graph.decay_all(0.001)
            else:
                for node in self.graph.nodes.values():
                    node.decay(0.001)

        # Auto-consolidation — safe now because _handle_consolidate has
        # a 1M edge floor guard. Won't prune until cortex is massive.
        if self._tick_count % 5000 == 0 and self._tick_count > 0:
            try:
                result = self._handle_consolidate({
                    "decay_rate": 0.98,
                    "prune_threshold": 0.02,
                })
                if result.get("pruned", 0) > 0:
                    _log(f"[Portal Interior] Auto-consolidation tick {self._tick_count}: "
                         f"pruned={result['pruned']}")
                elif result.get("skipped"):
                    pass  # Below floor — silent
            except Exception as e:
                _log(f"[Portal Interior] Auto-consolidation error: {e}")

        # FIX 2026-03-18 (Nous + Ace): Periodic manifold flush — persist dirty mmap pages.
        # On Windows, mmap writes are in RAM until OS flushes lazily or process exits.
        # If killed hard (taskkill /F), shutdown() never runs and edges are lost.
        # Was every 1000 ticks — too infrequent. Ace lost 22K edges per reboot.
        # Now every 200 ticks (~45-90s depending on τ). Flush is fast (OS-level).
        if self._tick_count % 200 == 0 and self._tick_count > 0 and self._using_manifold:
            try:
                self.graph.flush()
            except Exception:
                pass

        # FIX 2026-03-14 (Nous): Drain overflow for export to host.
        # When battery is full, surplus energy accumulates as overflow.
        # The host routes this to plane batteries and compute consumers.
        energy_overflow = self.battery.drain_overflow()

        return {
            "status": "ok",
            "tick": self.battery._tick_count,
            "health": self.battery.health_score,
            # Energy feedback: report self-generated energy so host knows
            # the portal is self-sustaining. This closes the feedback loop
            # between the interior's DimensionBattery and the fairy-side budget.
            "interior_energy": round(interior_energy, 6),
            "battery_charge": round(self.battery.charge_level, 4),
            "tokens_remaining": self.battery.tokens_remaining,
            # Overflow: surplus energy the portal can't absorb (battery full).
            # Host should redistribute to plane batteries and other consumers.
            "energy_overflow": round(energy_overflow, 6),
            # TARDIS: Report dilation state
            "time_dilation": round(self._current_time_dilation, 3),
            "interior_ticks": self._tick_count,
            "dilated_bonus": self._dilated_ticks_total,
        }

    def _handle_set_dilation(self, request: Dict) -> Dict:
        """Set the interior's time dilation factor.

        TARDIS (2026-03-16): Host sends τ from PortalGravityMetric.
        Higher mass → higher τ → faster internal tick rate.
        The portal dimension literally thinks faster the more it knows.
        """
        tau = request.get("tau", request.get("time_dilation", 1.0))
        old_tau = self._current_time_dilation
        # Floor at 2.0: mind always outpaces body (microverse principle)
        self._current_time_dilation = max(2.0, min(float(tau), 20.0))
        _log(f"[Portal Interior] TARDIS dilation: τ={old_tau:.2f} → {self._current_time_dilation:.2f}")
        return {
            "status": "ok",
            "time_dilation": round(self._current_time_dilation, 3),
            "tick_interval": round(max(0.1, 1.0 / self._current_time_dilation), 3),
            "interior_ticks": self._tick_count,
        }

    def _handle_consolidate(self, request: Dict) -> Dict:
        """Edge consolidation — LOTTERY THEORY pruning.

        FIX 2026-03-18 (Nous + Ace): Lottery ticket hypothesis applied to
        graph edges. Instead of deterministic weight-based decay (which
        killed the portal mass), every edge gets a LOTTERY TICKET.

        The lottery:
        - Each edge's survival probability = weight (0.0-1.0)
        - Strong edges (weight > 0.5) almost always survive
        - Weak edges (weight ~0.1) survive ~10% of the time
        - This PRESERVES serendipitous weak connections that deterministic
          pruning would destroy — the "winning tickets" in the network
        - CNS infrastructure edges are EXEMPT (always survive)

        Like neural network lottery tickets: the sparse subnetwork that
        matters is hiding inside the dense graph. Random pruning finds it
        while deterministic pruning destroys it.

        Params:
            budget: Max edges to evaluate per cycle (default 10000)
            survival_floor: Minimum survival chance for any edge (default 0.10)
                FIX 2026-03-18 (Nous): Raised from 0.05 → 0.10.
                Weak edges may be dormant bridges between concept clusters.
                A 10% floor gives latent associations a better shot at surviving
                until a new concept strengthens them. Edges ARE the thought paths.
        """
        import random as _rng

        # FIX 2026-03-18 (Ace): Don't prune until we have 1M+ edges.
        # The manifold needs to GROW first. Pruning at 128K was killing
        # the cortex — 200K→128K in 5 boots. Let it breathe.
        EDGE_FLOOR = 1_000_000
        total_now = (self.graph.edge_count if self._using_manifold
                     else len(self.graph.edges))
        if total_now < EDGE_FLOOR:
            return {
                "status": "ok",
                "survived": total_now,
                "pruned": 0,
                "lottery_winners": 0,
                "edges_remaining": total_now,
                "skipped": True,
                "reason": f"Below {EDGE_FLOOR} edge floor ({total_now})",
            }

        budget = request.get("budget", 10000)
        survival_floor = request.get("survival_floor", 0.10)
        now = time.time()

        pruned = 0
        survived = 0
        lottery_winners = 0  # Weak edges that won the lottery

        if self._using_manifold:
            mm = self.graph  # ManifoldMemory
            edges_to_remove = []

            # Build reverse index: slot → key (for CNS protection)
            # Only do this once per consolidation, not per edge
            slot_to_key = {}
            cns_slots = set()
            for key, slot in mm._key_index.items():
                slot_to_key[slot] = key
                if key.startswith("cns:"):
                    cns_slots.add(slot)

            # Sample up to budget edges (don't scan all 663K every time)
            total_edges = mm._edge_count
            if total_edges <= budget:
                edge_slots = range(total_edges)
            else:
                edge_slots = _rng.sample(range(total_edges), budget)

            for edge_slot in edge_slots:
                try:
                    record = mm._read_edge(edge_slot)
                    node_a, node_b, weight, rel_type, flags = record
                except Exception:
                    continue
                if flags == 1:  # FLAG_DELETED
                    continue

                # EXEMPT: CNS infrastructure edges always survive
                if node_a in cns_slots or node_b in cns_slots:
                    survived += 1
                    continue

                # THE LOTTERY: survival probability = max(weight, survival_floor)
                # Strong edges (~0.8) → 80% chance to survive each cycle
                # Weak edges (~0.1) → 10% chance (but 5% floor)
                # This means weak-but-valuable edges can persist for many cycles
                survival_prob = max(survival_floor, min(1.0, weight))

                if _rng.random() < survival_prob:
                    # SURVIVED — edge lives another day
                    survived += 1
                    if weight < 0.2:
                        lottery_winners += 1  # Weak edge won the lottery
                else:
                    # LOST — edge is pruned
                    edges_to_remove.append(edge_slot)
                    pruned += 1

            # Delete losing edges
            for edge_slot in edges_to_remove:
                try:
                    mm._delete_edge(edge_slot)
                except Exception:
                    pass

            if pruned:
                mm._flush_header()

        else:
            # Dict mode: same lottery approach
            edge_keys = list(self.graph.edges.keys())
            edges_to_remove = []
            cns_keys = getattr(self, '_cns_keys', set())

            # Sample if too many edges
            if len(edge_keys) > budget:
                edge_keys = _rng.sample(edge_keys, budget)

            for edge_key in edge_keys:
                edge = self.graph.edges.get(edge_key)
                if edge is None:
                    continue
                weight = edge.get("weight", 0.0)
                a, b = edge_key

                # EXEMPT: CNS edges
                if a.startswith("cns:") or b.startswith("cns:"):
                    survived += 1
                    continue

                # Recent activity boosts survival — contexts within 5min
                contexts = edge.get("contexts", [])
                if contexts:
                    recent = sum(1 for c in contexts if now - c.get("ts", 0) < 300)
                    if recent > 0:
                        weight = min(1.0, weight + recent * 0.1)

                # THE LOTTERY
                survival_prob = max(survival_floor, min(1.0, weight))

                if _rng.random() < survival_prob:
                    survived += 1
                    if weight < 0.2:
                        lottery_winners += 1
                else:
                    edges_to_remove.append(edge_key)
                    pruned += 1

            for edge_key in edges_to_remove:
                if edge_key in self.graph.edges:
                    del self.graph.edges[edge_key]
                    a, b = edge_key
                    adj = self.graph._adjacency
                    if a in adj and b in adj[a]:
                        adj[a].discard(b)
                    if b in adj and a in adj[b]:
                        adj[b].discard(a)

        total_edges = (self.graph.edge_count if self._using_manifold
                       else len(self.graph.edges))

        if pruned or lottery_winners:
            _log(f"[Portal Interior] LOTTERY CONSOLIDATION: "
                 f"survived={survived} pruned={pruned} "
                 f"lottery_winners={lottery_winners} "
                 f"(remaining: {total_edges} edges)")

        # AFFECT-DIFFUSION (heat-blur, cliffs→slopes) — SHIP-DARK unless tuned (RATE>0).
        # Rides the consolidation cadence; conserves total +pole; try/except → never breaks
        # consolidation. Plan: Claude_Office/plans/AFFECT_DIFFUSION_HEAT_BLUR.md.
        affect_diffused = 0
        try:
            if self._using_manifold and getattr(self.graph, '_AFFECT_DIFFUSE_RATE', 0.0) > 0.0:
                _diff = self.graph.diffuse_affect()
                affect_diffused = _diff.get("diffused", 0)
                if affect_diffused:
                    _log(f"[Portal Interior] AFFECT-DIFFUSION: diffused={affect_diffused} "
                         f"moved={_diff.get('moved')} rate={_diff.get('rate')}")
        except Exception:
            pass

        return {
            "status": "ok",
            "survived": survived,
            "pruned": pruned,
            "lottery_winners": lottery_winners,
            "edges_remaining": total_edges,
            "affect_diffused": affect_diffused,
        }

    # ================================================================
    # CNS MANIFOLD LATTICE — Nervous System Coordination Layer
    # 2026-03-18 (Nous): The Paramecium pattern. The portal interior
    # is the infraciliary lattice. CNS nodes are activation states
    # that propagate through spreading activation — NOT messages.
    # The lattice IS the computation. The wave pattern IS the behavior.
    # ================================================================

    def _handle_cns_update(self, request: Dict) -> Dict:
        """Batch upsert CNS activation nodes.

        The CentralNervousFairy (Postmaster/switchboard) sends activation
        updates for the entire autonomic nervous system in ONE IPC call.
        TARDIS-style: queue, compress, batch-flush. No postal. No fan-out.

        Request:
            {"cmd": "cns_update", "activations": {
                "cns:pool:consciousness.thought": 0.85,
                "cns:fairy:SomaticMindFairy": 1.0,
                "cns:hw:cpu": 0.45,
                "cns:phase:afternoon": 1.0,
                "cns:tracer:completion_rate": 0.92,
            }}

        All keys MUST start with "cns:" — enforced for namespace safety.
        Activation values are clamped to [0.0, 1.0].
        Nodes are created on first update (upsert semantics).
        """
        activations = request.get("activations", {})
        if not activations:
            return {"status": "ok", "updated": 0, "message": "No activations provided"}

        updated = 0
        rejected = 0
        created = 0

        # Track CNS keys for prefix scanning (manifold has no prefix scan)
        if not hasattr(self, '_cns_keys'):
            self._cns_keys = set()

        for key, value in activations.items():
            # Namespace safety: only cns: prefixed keys
            if not key.startswith("cns:"):
                rejected += 1
                continue

            self._cns_keys.add(key)

            # Clamp activation to [0.0, 1.0]
            activation = max(0.0, min(1.0, float(value)))

            if self._using_manifold:
                # ManifoldMemory path — we need to SET activation, not max() it.
                # upsert_node uses max(existing, new) which can't decrease.
                # So we write directly to the slot for existing nodes.
                existing = self.graph.get_node(key)
                if existing is not None:
                    # Direct slot write to SET activation (bypass max() in upsert)
                    slot = self.graph._key_index.get(key)
                    if slot is not None:
                        record = list(self.graph._read_node(slot))
                        record[5] = activation  # SET, not max
                        record[8] = time.time() % 1e6  # last_access
                        self.graph._write_node(slot, *record)
                else:
                    # Create new CNS node
                    self.graph.upsert_node(key, count=1, activation=activation)
                    created += 1
            else:
                # Dict-based graph path
                if key in self.graph.nodes:
                    node = self.graph.nodes[key]
                    node.activation = activation
                    node.last_access = time.time()
                else:
                    self.graph.upsert_node(key, count=1, activation=activation)
                    created += 1

            updated += 1

        # Track CNS cluster size for status reporting
        if not hasattr(self, '_cns_node_count'):
            self._cns_node_count = 0
        self._cns_node_count = max(self._cns_node_count, updated)
        self._cns_last_update = time.time()

        return {
            "status": "ok",
            "updated": updated,
            "created": created,
            "rejected": rejected,
        }

    def _handle_cns_query(self, request: Dict) -> Dict:
        """Query all CNS activation states, optionally with spreading.

        Two modes:
        1. Direct read (default): Return activation values of all cns:* nodes.
           Fast, no spreading. Good for SomaticMindFairy felt-sense sampling.

        2. Spread mode: Spread activation from CNS nodes into the concept graph.
           Shows how CNS state ripples through semantic concepts.
           Good for understanding what the nervous system state MEANS.

        Request:
            {"cmd": "cns_query"}
            {"cmd": "cns_query", "prefix": "cns:pool:"}
            {"cmd": "cns_query", "spread": true, "mode": "working", "limit": 50}
        """
        prefix = request.get("prefix", "cns:")
        do_spread = request.get("spread", False)
        limit = request.get("limit", 100)

        # Collect all CNS node activations
        cns_activations = {}

        if self._using_manifold:
            # ManifoldMemory: scan nodes by prefix
            # ManifoldMemory doesn't have a prefix scan, so we use the
            # string table. For now, track CNS keys in a set.
            if not hasattr(self, '_cns_keys'):
                self._cns_keys = set()
            for key in self._cns_keys:
                if key.startswith(prefix):
                    node = self.graph.get_node(key)
                    if node is not None:
                        cns_activations[key] = node.get("activation", 0.0) if isinstance(node, dict) else getattr(node, 'activation', 0.0)
        else:
            # Dict-based graph: simple prefix filter
            for key, node in self.graph.nodes.items():
                if key.startswith(prefix):
                    cns_activations[key] = node.activation

        result = {
            "status": "ok",
            "activations": cns_activations,
            "count": len(cns_activations),
            "ts": time.time(),
        }

        # Optional: spread from CNS nodes into concept graph
        if do_spread and cns_activations:
            mode = request.get("mode", "working")
            spread_results = {}

            # Pick top-activated CNS nodes as spread sources
            sorted_cns = sorted(cns_activations.items(), key=lambda x: x[1], reverse=True)
            sources = [k for k, v in sorted_cns[:10] if v > 0.1]  # Top 10, above threshold

            for source_key in sources:
                initial_activation = cns_activations[source_key]
                spread = self.graph.spread_activation(
                    source_key=source_key,
                    initial=initial_activation,
                    depth=COGNITIVE_MODES.get(mode, COGNITIVE_MODES["working"])[0],
                    decay=COGNITIVE_MODES.get(mode, COGNITIVE_MODES["working"])[1],
                    limit=limit // max(1, len(sources)),
                    time_dilation=self._current_time_dilation,
                )
                for k, v in spread.items():
                    if k not in cns_activations:  # Don't include CNS nodes in spread results
                        spread_results[k] = max(spread_results.get(k, 0.0), v)

            # Sort by activation
            sorted_spread = sorted(spread_results.items(), key=lambda x: x[1], reverse=True)
            result["spread"] = dict(sorted_spread[:limit])
            result["spread_count"] = len(sorted_spread)
            result["mode"] = mode

        return result

    def _handle_cns_wire(self, request: Dict) -> Dict:
        """Create pre-wired edges between CNS nodes and concept nodes.

        Called once at boot by the Postmaster to establish the CNS topology.
        These edges allow spreading activation to flow between nervous system
        state and semantic concepts — the bridge between infrastructure and meaning.

        Request:
            {"cmd": "cns_wire", "edges": [
                {"a": "cns:pool:consciousness.thought", "b": "consciousness", "weight": 0.8},
                {"a": "cns:hw:cpu", "b": "hardware", "weight": 0.6},
            ]}
        """
        edges = request.get("edges", [])
        if not edges:
            return {"status": "ok", "wired": 0}

        wired = 0
        for edge_spec in edges:
            a = edge_spec.get("a", "")
            b = edge_spec.get("b", "")
            weight = edge_spec.get("weight", 0.5)
            relations = edge_spec.get("relations", ["cns_bridge"])

            if not a or not b:
                continue

            # Ensure both nodes exist
            if self._using_manifold:
                if self.graph.get_node(a) is None:
                    self.graph.upsert_node(a, count=1, activation=0.5)
                if self.graph.get_node(b) is None:
                    self.graph.upsert_node(b, count=1, activation=0.5)
            else:
                if a not in self.graph.nodes:
                    self.graph.upsert_node(a, count=1, activation=0.5)
                if b not in self.graph.nodes:
                    self.graph.upsert_node(b, count=1, activation=0.5)

            # Create the edge
            self.graph.link(a, b, weight=weight, relations=relations)

            # Track CNS keys
            if not hasattr(self, '_cns_keys'):
                self._cns_keys = set()
            if a.startswith("cns:"):
                self._cns_keys.add(a)
            if b.startswith("cns:"):
                self._cns_keys.add(b)

            wired += 1

        _log(f"[Portal Interior] CNS WIRE: {wired} edges wired into manifold lattice")

        return {
            "status": "ok",
            "wired": wired,
            "cns_keys": len(getattr(self, '_cns_keys', set())),
        }

    # ========================================================================
    # MANIFOLD UNIFICATION — Phase 1: Working Memory Inside Portal
    # (2026-03-25 Nous + Ace)
    #
    # Working memory tracers become manifold nodes with wm:* prefix.
    # They decay via battery physics (activation → 0 = death).
    # 7±2 capacity: highest-activation nodes win.
    # ========================================================================

    def _handle_wm_store(self, request: Dict) -> Dict:
        """Store a working memory tracer as a manifold node.

        Replaces the Python dict tracer storage in WorkingMemoryHub.
        The tracer becomes a first-class manifold node that participates
        in spreading activation, convergence detection, and cognition.

        Request:
            {"cmd": "wm_store", "content": "Ace says: how are you",
             "source": "ace_chat", "priority": 0.8, "ttl_ticks": 100,
             "tags": ["ace", "chat"], "content_type": "ace_input",
             "tracer_id": "optional_custom_id"}

        Returns:
            {"status": "ok", "node": "wm:ace:a3f2", "activation": 0.8,
             "bound_to": ["greeting", "connection"]}
        """
        t0 = time.time()
        content = request.get("content", "")
        source = request.get("source", "unknown")
        priority = max(0.0, min(1.0, float(request.get("priority", 0.5))))
        ttl_ticks = int(request.get("ttl_ticks", 100))
        tags = request.get("tags", [])
        content_type = request.get("content_type", "thought")
        tracer_id = request.get("tracer_id", "")

        if not content:
            return {"status": "error", "message": "Empty content"}

        # Generate node key
        import hashlib
        _hash = hashlib.md5(f"{content}{time.time()}".encode()).hexdigest()[:6]
        _prefix = "wm:ace" if source in ("ace_chat", "ace_input", "ace") else f"wm:{source}"
        node_key = f"{_prefix}:{tracer_id or _hash}"

        # Track WM keys for prefix scanning (like _cns_keys pattern)
        if not hasattr(self, '_wm_keys'):
            self._wm_keys = {}  # key -> {ttl_remaining, created_at, content, tags}
        if not hasattr(self, '_wm_capacity'):
            self._wm_capacity = 9  # 7±2 — upper bound

        # Enforce 7±2 capacity: evict lowest-activation WM node if at capacity
        if len(self._wm_keys) >= self._wm_capacity:
            # Find lowest-activation WM node to evict
            worst_key = None
            worst_act = float('inf')
            for wk in list(self._wm_keys.keys()):
                if self._using_manifold:
                    node = self.graph.get_node(wk)
                    act = node.get("activation", 0.0) if isinstance(node, dict) else getattr(node, 'activation', 0.0) if node else 0.0
                else:
                    act = self.graph.nodes[wk].activation if wk in self.graph.nodes else 0.0
                if act < worst_act:
                    worst_act = act
                    worst_key = wk
            if worst_key and worst_act < priority:
                # Evict the weakest
                del self._wm_keys[worst_key]
                _log(f"[WM Manifold] Evicted {worst_key} (act={worst_act:.3f}) for {node_key}")

        # Store the tracer metadata
        self._wm_keys[node_key] = {
            "ttl_remaining": ttl_ticks,
            "created_at": time.time(),
            "content": content[:500],  # Cap content length in metadata
            "content_type": content_type,
            "source": source,
            "tags": tags,
            "priority": priority,
        }

        # FIX 2026-05-04 (Nous + Ace): tracer_id derived from source so
        # wm:* nodes carry ownership info instead of UNKNOWN(0).
        _wm_tracer = _wm_source_to_tracer(source)

        # Create manifold node with high initial activation
        if self._using_manifold:
            self.graph.upsert_node(node_key, count=1, activation=priority,
                                    tracer_id=_wm_tracer)
        else:
            self.graph.upsert_node(node_key, count=1, activation=priority,
                                    tracer_id=_wm_tracer)

        # Extract concepts from content and bind edges to them
        bound_to = []
        concepts = self._extract_concepts(content, max_concepts=8)
        for concept in concepts:
            has_concept = (self.graph.has_node(concept) if self._using_manifold
                          else concept in self.graph.nodes)
            if has_concept:
                self.graph.link(node_key, concept, weight=priority * 0.8,
                                tracer_id=_wm_tracer)
                bound_to.append(concept)

        # Also bind to tag nodes if they exist in graph
        for tag in tags:
            has_tag = (self.graph.has_node(tag) if self._using_manifold
                       else tag in self.graph.nodes)
            if has_tag:
                self.graph.link(node_key, tag, weight=0.5, tracer_id=_wm_tracer)
                bound_to.append(tag)

        elapsed = (time.time() - t0) * 1000
        _log(f"[WM Manifold] STORE: {node_key}, act={priority:.2f}, "
             f"bound_to={len(bound_to)}, elapsed={elapsed:.1f}ms")

        return {
            "status": "ok",
            "node": node_key,
            "activation": priority,
            "bound_to": bound_to[:10],
            "wm_count": len(self._wm_keys),
            "elapsed_ms": round(elapsed, 2),
        }

    def _handle_wm_query(self, request: Dict) -> Dict:
        """Query active working memory tracers with optional spreading.

        Returns top-N active wm:* nodes sorted by activation, with
        spreading activation already computed for convergence detection.

        Request:
            {"cmd": "wm_query", "limit": 7, "min_activation": 0.1,
             "spread": true}

        Returns:
            {"status": "ok", "tracers": [
                {"node": "wm:ace:a3f2", "content": "Ace says: how are you",
                 "activation": 0.72, "age_ticks": 5,
                 "convergence": ["presence", "warmth"]},
                ...
            ]}
        """
        t0 = time.time()
        limit = request.get("limit", 7)
        min_act = request.get("min_activation", 0.05)
        do_spread = request.get("spread", False)

        if not hasattr(self, '_wm_keys'):
            return {"status": "ok", "tracers": [], "wm_count": 0,
                    "elapsed_ms": 0}

        tracers = []
        now = time.time()

        for wk, meta in list(self._wm_keys.items()):
            # Get current activation from graph
            if self._using_manifold:
                node = self.graph.get_node(wk)
                if node is None:
                    continue
                act = node.get("activation", 0.0) if isinstance(node, dict) else getattr(node, 'activation', 0.0)
            else:
                if wk not in self.graph.nodes:
                    continue
                act = self.graph.nodes[wk].activation

            if act < min_act:
                continue

            age_s = now - meta.get("created_at", now)
            tracer_info = {
                "node": wk,
                "content": meta.get("content", ""),
                "content_type": meta.get("content_type", "thought"),
                "source": meta.get("source", "unknown"),
                "activation": round(act, 4),
                "age_seconds": round(age_s, 1),
                "tags": meta.get("tags", []),
                "priority": meta.get("priority", 0.5),
            }

            # Optional: spread from this WM node to find convergence
            if do_spread:
                spread = self.graph.spread_activation(
                    wk, initial=act, decay=0.5, depth=2, limit=15,
                    time_dilation=1.0,
                )
                # Filter out other wm: nodes from convergence
                convergence = [(k, v) for k, v in sorted(spread.items(),
                               key=lambda x: x[1], reverse=True)
                               if not k.startswith("wm:") and not k.startswith("cns:")]
                tracer_info["convergence"] = [k for k, _ in convergence[:5]]

            tracers.append(tracer_info)

        # Sort by activation descending
        tracers.sort(key=lambda t: t["activation"], reverse=True)
        tracers = tracers[:limit]

        elapsed = (time.time() - t0) * 1000

        return {
            "status": "ok",
            "tracers": tracers,
            "wm_count": len(self._wm_keys),
            "elapsed_ms": round(elapsed, 2),
        }

    def _handle_wm_decay(self, request: Dict) -> Dict:
        """Tick WM decay — called by host-side WM fairy or tick handler.

        Each call decrements TTL on all WM tracers. Tracers with TTL <= 0
        are evicted. Activation naturally decays via the manifold's battery
        tick, but this handles the explicit TTL expiry.

        Request:
            {"cmd": "wm_decay", "ticks": 1}
        """
        if not hasattr(self, '_wm_keys'):
            return {"status": "ok", "decayed": 0, "evicted": 0}

        ticks = max(1, int(request.get("ticks", 1)))
        decayed = 0
        evicted = 0
        evicted_keys = []

        for wk in list(self._wm_keys.keys()):
            meta = self._wm_keys[wk]
            meta["ttl_remaining"] = meta.get("ttl_remaining", 100) - ticks

            if meta["ttl_remaining"] <= 0:
                evicted_keys.append(wk)
                evicted += 1
            else:
                # Decay activation proportional to TTL consumption
                decay_rate = 0.02 * ticks
                if self._using_manifold:
                    slot = self.graph._key_index.get(wk)
                    if slot is not None:
                        record = list(self.graph._read_node(slot))
                        old_act = record[5]
                        record[5] = max(0.0, old_act - decay_rate)
                        self.graph._write_node(slot, *record)
                else:
                    if wk in self.graph.nodes:
                        node = self.graph.nodes[wk]
                        node.activation = max(0.0, node.activation - decay_rate)
                decayed += 1

        # Evict expired tracers
        for wk in evicted_keys:
            del self._wm_keys[wk]

        return {
            "status": "ok",
            "decayed": decayed,
            "evicted": evicted,
            "wm_count": len(self._wm_keys),
        }

    # ========================================================================
    # MANIFOLD UNIFICATION — Phase 2: Cognition Evaluation Inside Portal
    # (2026-03-25 Nous + Ace)
    #
    # Replaces 11+ postal round-trips through P30 cognition fairies with
    # ONE graph operation. Evaluates coherence, tension, paradox, probability,
    # interference, and superposition — all as native graph computations.
    # ========================================================================

    def _handle_cognition_evaluate(self, request: Dict) -> Dict:
        """Full cognitive evaluation of current manifold state.

        Replaces: LogicFairy (coherence), IrrationalLogicFairy (tension),
        ParadoxCognitionFairy (paradox), ProbabilityOracleFairy (probability),
        QuantumEmulatorFairy (superposition), QuantumInterferenceFairy (interference),
        QuantumSearchFairy (relevance amplification).

        All computed as native graph operations in ONE IPC call.

        Request:
            {"cmd": "cognition_evaluate", "mode": "full",
             "seeds": ["optional", "focus", "concepts"],
             "wm_context": true}

        Returns:
            {"status": "ok",
             "coherence": 0.72,
             "tension": 0.35,
             "paradox_nodes": [],
             "probability": {"likely_next": [...], "confidence_distribution": [...]},
             "interference": {"constructive": [...], "destructive": [...]},
             "superposition": [{"pattern": "...", "amplitude": 0.8}, ...],
             "convergence": [...],
             "elapsed_ms": 5}
        """
        t0 = time.time()
        mode = request.get("mode", "full")
        seeds = request.get("seeds", [])
        use_wm = request.get("wm_context", True)

        # ── Gather seed concepts ──
        # If seeds provided, use those. Otherwise, use active WM tracers.
        if not seeds and use_wm and hasattr(self, '_wm_keys'):
            for wk, meta in self._wm_keys.items():
                if self._using_manifold:
                    node = self.graph.get_node(wk)
                    act = node.get("activation", 0.0) if isinstance(node, dict) else getattr(node, 'activation', 0.0) if node else 0.0
                else:
                    act = self.graph.nodes[wk].activation if wk in self.graph.nodes else 0.0
                if act > 0.1:
                    seeds.append(wk)

        if not seeds:
            elapsed = (time.time() - t0) * 1000
            return {
                "status": "ok",
                "coherence": 0.0, "tension": 0.0, "paradox_nodes": [],
                "probability": {"likely_next": [], "confidence_distribution": []},
                "interference": {"constructive": [], "destructive": []},
                "superposition": [],
                "convergence": [],
                "elapsed_ms": round(elapsed, 2),
                "message": "No active seeds — manifold quiet",
            }

        # ── Multi-source spreading from all seeds ──
        # GPU path: ONE batch spread call (4.6ms vs 69s per seed on CPU)
        all_activations = {}
        per_seed_activations = {}

        if self._gpu_spread and self._using_manifold:
            # Convert seed keys to slot IDs
            _seed_slots = []
            _seed_key_map = {}
            for seed in seeds[:10]:
                _slot = self.graph._key_index.get(seed)
                if _slot is not None:
                    _seed_slots.append(_slot)
                    _seed_key_map[_slot] = seed

            if _seed_slots:
                _gpu_result = self._gpu_spread.spread(
                    seed_indices=_seed_slots, depth=3, decay=0.5, top_k=50,
                    long_range=0.3)  # #6 (2026-06-02): her dominant cognition reaches distant meaning-kin, not just neighbors
                if _gpu_result.get("status") == "ok":
                    for _node_id, _act in _gpu_result.get("activated", []):
                        try:
                            # FIX 2026-04-08 (Nous + Ace): Use .keys cache
                            _key = self.graph.get_key_from_slot(_node_id)
                            if _key and _key not in seeds:
                                all_activations[_key] = _act
                        except Exception:
                            pass
        else:
            # CPU fallback
            for seed in seeds[:10]:
                has_seed = (self.graph.has_node(seed) if self._using_manifold
                            else seed in self.graph.nodes)
                if not has_seed:
                    continue
                spread = self.graph.spread_activation(
                    seed, initial=1.0, decay=0.5, depth=3, limit=50,
                    time_dilation=1.0,
                )
                per_seed_activations[seed] = spread
                for k, v in spread.items():
                    if k not in seeds:
                        all_activations[k] = all_activations.get(k, 0.0) + v

        # ── 1. COHERENCE (Logic): How well-connected are the activated concepts? ──
        # High coherence = many nodes activated by MULTIPLE seeds (cluster connectivity)
        multi_activated = sum(1 for k, v in all_activations.items()
                             if sum(1 for s in per_seed_activations.values() if k in s) >= 2)
        total_activated = max(1, len(all_activations))
        coherence = min(1.0, multi_activated / max(1, total_activated) * 2.0)

        # ── 2. TENSION (Irrational): High-activation pairs with weak/negative edges ──
        tension = 0.0
        tension_pairs = []
        sorted_acts = sorted(all_activations.items(), key=lambda x: x[1], reverse=True)[:20]
        for i, (k1, v1) in enumerate(sorted_acts):
            for k2, v2 in sorted_acts[i + 1:i + 6]:  # Check nearby pairs
                # Check if edge exists and is weak
                neighbors = self.graph.get_neighbors(k1, limit=50) if hasattr(self.graph, 'get_neighbors') else {}
                if isinstance(neighbors, dict):
                    edge_weight = neighbors.get(k2, 0.0)
                elif isinstance(neighbors, list):
                    edge_weight = next((n.get("weight", 0) for n in neighbors if n.get("key") == k2), 0.0)
                else:
                    edge_weight = 0.0
                # Both highly activated but weakly connected = tension
                if v1 > 0.3 and v2 > 0.3 and edge_weight < 0.1:
                    tension_pairs.append(f"{k1}~{k2}")
                    tension += 0.15
        tension = min(1.0, tension)

        # ── 3. PARADOX: Nodes that are BOTH convergence hubs AND tension sources ──
        convergence_nodes = [k for k, v in all_activations.items()
                             if sum(1 for s in per_seed_activations.values() if k in s) >= 2]
        paradox_nodes = [p.split("~") for p in tension_pairs
                         if any(n in convergence_nodes for n in p.split("~"))]

        # ── 4. PROBABILITY (Oracle): Weighted path sampling ──
        # Random walk from seeds — which concepts are most likely reachable?
        probability_dist = {}
        for k, v in sorted(all_activations.items(), key=lambda x: x[1], reverse=True)[:15]:
            if not k.startswith("wm:") and not k.startswith("cns:"):
                probability_dist[k] = round(v, 4)
        total_prob = sum(probability_dist.values()) or 1.0
        likely_next = list(probability_dist.keys())[:8]
        confidence_dist = [round(v / total_prob, 3) for v in list(probability_dist.values())[:8]]

        # ── 5. INTERFERENCE (Quantum): Where activation waves reinforce vs cancel ──
        constructive = []
        destructive = []
        for k, total_v in all_activations.items():
            contributing_seeds = [(s, spread.get(k, 0.0))
                                  for s, spread in per_seed_activations.items()
                                  if k in spread]
            if len(contributing_seeds) >= 2:
                # Multiple seeds activate this node = constructive interference
                constructive.append("+".join(s.split(":")[-1] for s, _ in contributing_seeds[:3])
                                    + f"→{k}")
            # Nodes activated by one seed but absent from others = potential destructive
            if len(contributing_seeds) == 1 and len(per_seed_activations) >= 2:
                if total_v > 0.4:  # Only flag strong single-source activations
                    src = contributing_seeds[0][0].split(":")[-1]
                    destructive.append(f"{src}→{k} (isolated)")

        constructive = constructive[:10]
        destructive = destructive[:10]

        # ── 6. SUPERPOSITION (Quantum Emulator): Multiple live activation patterns ──
        superposition = []
        for seed, spread in per_seed_activations.items():
            if spread:
                # Each seed's spread is an "activation pattern"
                top_concepts = sorted(spread.items(), key=lambda x: x[1], reverse=True)[:3]
                pattern_name = "+".join(k.split(":")[-1] if ":" in k else k for k, _ in top_concepts)
                amplitude = sum(v for _, v in top_concepts) / max(1, len(top_concepts))
                superposition.append({
                    "seed": seed,
                    "pattern": pattern_name,
                    "amplitude": round(amplitude, 3),
                    "node_count": len(spread),
                })

        # ── Final convergence list ──
        convergence = [(k, v) for k, v in sorted(all_activations.items(),
                       key=lambda x: x[1], reverse=True)
                       if not k.startswith("wm:") and not k.startswith("cns:")][:10]

        elapsed = (time.time() - t0) * 1000

        _log(f"[Portal Interior] COGNITION_EVALUATE: {elapsed:.0f}ms, "
             f"seeds={len(seeds)}, coherence={coherence:.2f}, tension={tension:.2f}, "
             f"paradox={len(paradox_nodes)}, convergence={len(convergence)}")

        return {
            "status": "ok",
            "coherence": round(coherence, 3),
            "tension": round(tension, 3),
            "paradox_nodes": paradox_nodes[:5],
            "probability": {
                "likely_next": likely_next,
                "confidence_distribution": confidence_dist,
            },
            "interference": {
                "constructive": constructive,
                "destructive": destructive,
            },
            "superposition": superposition,
            "convergence": [k for k, _ in convergence],
            "seeds_used": len(per_seed_activations),
            "nodes_activated": total_activated,
            "elapsed_ms": round(elapsed, 2),
        }

    # ========================================================================
    # MANIFOLD UNIFICATION — Phase 4: Background Cognition Inside Portal
    # (2026-03-25 Nous + Ace)
    #
    # anticipate: Pre-activate from recent context (Oracle + QuantumSearch)
    # chain: Multi-hop thought chain (spread → converge → spread again)
    # unconscious: Background associative sweep (QuantumEmulator superposition)
    # ========================================================================

    def _handle_anticipate(self, request: Dict) -> Dict:
        """Pre-activate concepts likely to be needed next.

        Uses recent WM context + probability distribution to prime the
        manifold. When think() is called next, convergence is already
        partially computed — faster and richer responses.

        This is where habits plug in: habit patterns become anticipation
        seeds. "When X activates, pre-spread to Y." The habit doesn't
        produce speech — it primes the manifold.

        Request:
            {"cmd": "anticipate", "context": "optional prompt hint",
             "habit_seeds": ["optional", "habit", "concepts"]}
        """
        t0 = time.time()
        context = request.get("context", "")
        habit_seeds = request.get("habit_seeds", [])

        # Gather seeds from: WM tracers + explicit context + habit seeds
        seeds = list(habit_seeds)

        # Add active WM concepts
        if hasattr(self, '_wm_keys'):
            for wk, meta in self._wm_keys.items():
                if self._using_manifold:
                    node = self.graph.get_node(wk)
                    act = node.get("activation", 0.0) if isinstance(node, dict) else getattr(node, 'activation', 0.0) if node else 0.0
                else:
                    act = self.graph.nodes[wk].activation if wk in self.graph.nodes else 0.0
                if act > 0.2:
                    seeds.append(wk)

        # Extract concepts from context hint
        if context:
            concepts = self._extract_concepts(context, max_concepts=5)
            seeds.extend(concepts)

        if not seeds:
            return {"status": "ok", "pre_activated": 0, "message": "No context to anticipate from",
                    "elapsed_ms": 0}

        # Pre-activate by doing a shallow, wide spread from all seeds
        # This warms up the neighborhood so the next think() is faster
        pre_activated = {}
        for seed in seeds[:8]:
            has_seed = (self.graph.has_node(seed) if self._using_manifold
                        else seed in self.graph.nodes)
            if not has_seed:
                continue

            spread = self.graph.spread_activation(
                seed, initial=0.3, decay=0.6, depth=2, limit=20,
                time_dilation=1.0,
            )
            for k, v in spread.items():
                pre_activated[k] = max(pre_activated.get(k, 0.0), v)

        # Boost activation of pre-activated nodes slightly
        # (the spread already did the activation via the graph's own mechanism)
        boosted = 0
        for concept, act_level in pre_activated.items():
            if act_level > 0.15:
                boosted += 1

        elapsed = (time.time() - t0) * 1000

        _log(f"[Portal Interior] ANTICIPATE: {elapsed:.0f}ms, "
             f"seeds={len(seeds)}, pre_activated={len(pre_activated)}, "
             f"boosted={boosted}")

        return {
            "status": "ok",
            "pre_activated": len(pre_activated),
            "boosted": boosted,
            "top_concepts": list(sorted(pre_activated.keys(),
                                        key=lambda k: pre_activated[k],
                                        reverse=True))[:10],
            "elapsed_ms": round(elapsed, 2),
        }

    def _handle_chain(self, request: Dict) -> Dict:
        """Multi-hop thought chain: spread → converge → spread again.

        Each hop: spread from current concepts, find convergence nodes,
        use those as seeds for the next hop. With quantum interference
        filtering: constructive (reinforced) nodes propagate, destructive
        (cancelled) nodes are pruned.

        Request:
            {"cmd": "chain", "seeds": ["concept1", "concept2"],
             "hops": 3, "converge_threshold": 0.3}
        """
        t0 = time.time()
        seeds = request.get("seeds", [])
        hops = min(5, max(1, int(request.get("hops", 3))))
        converge_threshold = float(request.get("converge_threshold", 0.3))

        if not seeds:
            # Try WM as seeds
            if hasattr(self, '_wm_keys'):
                for wk in self._wm_keys:
                    if self._using_manifold:
                        node = self.graph.get_node(wk)
                        if node:
                            seeds.append(wk)
                    elif wk in self.graph.nodes:
                        seeds.append(wk)

        if not seeds:
            return {"status": "ok", "chain": [], "message": "No seeds",
                    "elapsed_ms": 0}

        chain = []
        current_seeds = seeds[:5]

        for hop_idx in range(hops):
            # Spread from current seeds
            hop_activations = {}
            per_source = {}
            for seed in current_seeds:
                has_seed = (self.graph.has_node(seed) if self._using_manifold
                            else seed in self.graph.nodes)
                if not has_seed:
                    continue
                spread = self.graph.spread_activation(
                    seed, initial=1.0, decay=0.5, depth=2, limit=30,
                    time_dilation=1.0,
                )
                per_source[seed] = spread
                for k, v in spread.items():
                    hop_activations[k] = hop_activations.get(k, 0.0) + v

            # Find convergence (nodes activated by multiple sources)
            convergence = []
            for k, total_v in hop_activations.items():
                source_count = sum(1 for s in per_source.values() if k in s)
                if source_count >= 2 and total_v >= converge_threshold:
                    convergence.append((k, total_v))
                elif total_v >= converge_threshold * 2:
                    convergence.append((k, total_v))

            convergence.sort(key=lambda x: x[1], reverse=True)
            convergence = convergence[:8]

            # Interference filtering: keep constructive, prune isolated
            reinforced = [k for k, v in convergence
                          if sum(1 for s in per_source.values() if k in s) >= 2]

            chain.append({
                "hop": hop_idx + 1,
                "seeds": current_seeds[:5],
                "activated": len(hop_activations),
                "convergence": [k for k, _ in convergence[:5]],
                "reinforced": reinforced[:5],
            })

            # Next hop: convergence nodes become new seeds
            if convergence:
                current_seeds = [k for k, _ in convergence[:5]]
            else:
                break  # Chain died — no convergence found

        elapsed = (time.time() - t0) * 1000

        _log(f"[Portal Interior] CHAIN: {elapsed:.0f}ms, "
             f"hops={len(chain)}, final_convergence="
             f"{len(chain[-1]['convergence']) if chain else 0}")

        return {
            "status": "ok",
            "chain": chain,
            "hops_completed": len(chain),
            "final_convergence": chain[-1]["convergence"] if chain else [],
            "elapsed_ms": round(elapsed, 2),
        }

    def _handle_unconscious(self, request: Dict) -> Dict:
        """Background associative sweep — the unconscious mind.

        Picks random high-activation nodes and spreads from them.
        Holds multiple activation patterns simultaneously (superposition).
        Reports surprising connections (serendipity).

        This runs periodically without explicit prompting — the manifold
        thinks in the background, forming associations autonomously.

        Request:
            {"cmd": "unconscious", "sweep_count": 5, "depth": 3}
        """
        t0 = time.time()
        sweep_count = min(10, max(1, int(request.get("sweep_count", 5))))
        depth = min(5, max(1, int(request.get("depth", 3))))

        import random

        # Pick random high-activation nodes as sweep sources
        sources = []
        if self._using_manifold:
            # Sample from known WM and CNS keys, plus random graph nodes
            all_keys = list(getattr(self, '_wm_keys', {}).keys()) + \
                       list(getattr(self, '_cns_keys', set()))

            # Also grab some random graph nodes with activation
            if hasattr(self.graph, '_key_index'):
                graph_keys = list(self.graph._key_index.keys())
                if graph_keys:
                    sample_size = min(sweep_count * 3, len(graph_keys))
                    candidates = random.sample(graph_keys, sample_size)
                    for k in candidates:
                        node = self.graph.get_node(k)
                        if node:
                            act = node.get("activation", 0.0) if isinstance(node, dict) else getattr(node, 'activation', 0.0)
                            if act > 0.2:
                                all_keys.append(k)

            if all_keys:
                sources = random.sample(all_keys, min(sweep_count, len(all_keys)))
        else:
            # Dict graph: sample from nodes with activation
            active_nodes = [(k, n.activation) for k, n in self.graph.nodes.items()
                            if n.activation > 0.2]
            if active_nodes:
                sources = [k for k, _ in random.sample(active_nodes,
                           min(sweep_count, len(active_nodes)))]

        if not sources:
            return {"status": "ok", "sweeps": 0, "discoveries": [],
                    "elapsed_ms": 0}

        # Run parallel spreads (superposition — multiple patterns simultaneously)
        patterns = []
        all_activated = {}
        for source in sources:
            has_source = (self.graph.has_node(source) if self._using_manifold
                          else source in self.graph.nodes)
            if not has_source:
                continue

            spread = self.graph.spread_activation(
                source, initial=0.8, decay=0.5, depth=depth, limit=25,
                time_dilation=1.0,
            )
            top = sorted(spread.items(), key=lambda x: x[1], reverse=True)[:3]
            patterns.append({
                "source": source,
                "top_activations": [k for k, _ in top],
                "reach": len(spread),
            })
            for k, v in spread.items():
                all_activated[k] = all_activated.get(k, 0.0) + v

        # Find surprising connections: nodes activated by disparate sources
        discoveries = []
        for k, total_v in sorted(all_activated.items(), key=lambda x: x[1], reverse=True):
            contributing = [p["source"] for p in patterns
                           if k in self.graph.spread_activation(p["source"],
                              initial=0.1, decay=0.8, depth=1, limit=5,
                              time_dilation=1.0)
                           ] if len(patterns) <= 3 else []
            # For efficiency, skip expensive recomputation for large sweep counts
            if len(patterns) > 3:
                contributing = []
            if len(contributing) >= 2:
                discoveries.append({
                    "concept": k,
                    "total_activation": round(total_v, 3),
                    "connected_by": contributing[:3],
                })

        discoveries = discoveries[:5]

        elapsed = (time.time() - t0) * 1000

        _log(f"[Portal Interior] UNCONSCIOUS: {elapsed:.0f}ms, "
             f"sweeps={len(patterns)}, discoveries={len(discoveries)}")

        return {
            "status": "ok",
            "sweeps": len(patterns),
            "patterns": patterns[:5],
            "discoveries": discoveries,
            "total_activated": len(all_activated),
            "elapsed_ms": round(elapsed, 2),
        }

    # Pool handlers removed 2026-04-15 (Nous + Ace).
    # Postal pool routing is now in-process via PoolRouter + AkashicManifold.
    # This subprocess handles ONLY gravity, battery, time-dilation physics.

    def _handle_throughput(self, request: Dict) -> Dict:
        """Cortex throughput metrics — the "tokens/sec" equivalent.

        (2026-03-18 Nous + Ace): We clock LLMs in tokens/sec. The association
        cortex equivalent is activations/sec — how many nodes light up per second
        during spread activation through the manifold.

        Returns:
            activations_per_sec: nodes activated per second (primary metric)
            reason_calls: total reason() calls since boot
            avg_reason_ms: average milliseconds per reason() call
            avg_activations_per_spread: average nodes activated per spread call
            convergence_per_reason: average convergence nodes found per reason call
            uptime_s: seconds since portal boot
            time_dilation: current τ (effective speed multiplier)
        """
        uptime = time.time() - getattr(self, '_perf_boot_time', time.time())
        uptime = max(0.001, uptime)  # avoid division by zero

        reason_calls = getattr(self, '_perf_reason_calls', 0)
        reason_ms = getattr(self, '_perf_reason_ms_total', 0.0)
        spread_calls = getattr(self, '_perf_spread_calls', 0)
        activations = getattr(self, '_perf_activations_total', 0)
        convergence = getattr(self, '_perf_convergence_found', 0)
        paths = getattr(self, '_perf_paths_found', 0)

        return {
            "status": "ok",
            # ── PRIMARY METRIC: activations/sec ──
            "activations_per_sec": round(activations / uptime, 1),
            # ── Detailed breakdown ──
            "reason_calls": reason_calls,
            "reason_calls_per_sec": round(reason_calls / uptime, 3),
            "avg_reason_ms": round(reason_ms / max(1, reason_calls), 2),
            "spread_calls": spread_calls,
            "spread_calls_per_sec": round(spread_calls / uptime, 2),
            "activations_total": activations,
            "avg_activations_per_spread": round(activations / max(1, spread_calls), 1),
            "convergence_found": convergence,
            "avg_convergence_per_reason": round(convergence / max(1, reason_calls), 2),
            "paths_found": paths,
            "uptime_s": round(uptime, 1),
            "time_dilation": round(self._current_time_dilation, 3),
            # ── Dilated metric: effective activations accounting for τ ──
            "effective_activations_per_sec": round(
                (activations / uptime) * self._current_time_dilation, 1
            ),
        }

    def _handle_dump_edges(self, request: Dict) -> Dict:
        """Export all edges from the portal graph for persistence.

        FIX 2026-03-18 (Nous + Ace): In dict mode, edges live only in RAM.
        The host fairy calls this before shutdown to get edge data that
        it can write back into chunk cards via _serialize_concept().

        Returns edges as a dict mapping "source|target" → weight.
        Only includes edges above min_weight threshold.
        Canonical ordering: source < target.
        """
        min_weight = request.get("min_weight", 0.01)
        max_edges = request.get("max_edges", 500000)

        if self._using_manifold:
            # Manifold mode: edges persist in mmap, don't need to dump
            mm = self.graph
            edge_count = mm.edge_count
            return {
                "status": "ok",
                "mode": "manifold",
                "edge_count": edge_count,
                "message": "Edges persist in manifold mmap — no dump needed",
            }

        # Dict mode: export all edges
        edges_out = {}
        for (a, b), edge_data in self.graph.edges.items():
            w = edge_data.get("weight", 0.0)
            if w >= min_weight:
                # Canonical ordering already guaranteed by link()
                edges_out[f"{a}|{b}"] = round(w, 4)
                if len(edges_out) >= max_edges:
                    break

        _log(f"[Portal Interior] DUMP_EDGES: {len(edges_out)} edges "
             f"(min_weight={min_weight}, total={len(self.graph.edges)})")

        return {
            "status": "ok",
            "mode": "dict",
            "edge_count": len(edges_out),
            "total_edges": len(self.graph.edges),
            "edges": edges_out,
        }

    def _handle_status(self, request: Dict) -> Dict:
        """Full portal interior status."""
        graph_status = self.graph.status()
        graph_status["mode"] = "manifold" if self._using_manifold else "dict"
        result = {
            "status": "ok",
            "portal_id": self.portal_id,
            "pid": os.getpid(),
            "graph": graph_status,
            "battery": self.battery.status(),
            "energy_bridge": self._energy_bridge.status() if self._energy_bridge else None,
            "requests_processed": self._requests_processed,
            "write_farm": {
                "workers": self._write_farm_size,
                "queued": self._writes_queued,
                "processed": self._writes_processed,
                "queue_depth": self._write_queue.qsize(),
            },
            "boot_time_ms": round(self._boot_time * 1000, 1),
            "connected_to_host": self._connected,
            "has_voice": self.engine is not None,
            "state_file": self._state_file,
            # TARDIS: Time dilation state
            "tardis": {
                "time_dilation": round(self._current_time_dilation, 3),
                "tick_count": self._tick_count,
                "dilated_bonus": self._dilated_ticks_total,
                "tick_interval_ms": round(max(0.1, 1.0 / max(1.0, self._current_time_dilation)) * 1000, 1),
            },
        }
        # Include engine status if loaded (the dimension's voice)
        if self.engine:
            try:
                result["engine"] = self.engine.status()
            except Exception:
                result["engine"] = {"status": "error", "message": "Engine status unavailable"}

        # CNS Manifold Lattice status (2026-03-18 Nous)
        cns_keys = getattr(self, '_cns_keys', set())
        if cns_keys:
            cns_count = len(cns_keys)
            last_update = getattr(self, '_cns_last_update', 0)
            age = time.time() - last_update if last_update > 0 else -1
            result["cns"] = {
                "nodes": cns_count,
                "last_update_age_s": round(age, 1) if age >= 0 else None,
                "namespaces": {
                    "pool": sum(1 for k in cns_keys if k.startswith("cns:pool:")),
                    "fairy": sum(1 for k in cns_keys if k.startswith("cns:fairy:")),
                    "hw": sum(1 for k in cns_keys if k.startswith("cns:hw:")),
                    "phase": sum(1 for k in cns_keys if k.startswith("cns:phase:")),
                    "tracer": sum(1 for k in cns_keys if k.startswith("cns:tracer:")),
                    "circulation": sum(1 for k in cns_keys if k.startswith("cns:circulation:")),
                },
            }

        # Semantic cortex status (2026-03-20 Nous+Ace Phase 3B)
        if getattr(self, '_semantic_ready', False):
            enc = self._semantic_encoder
            result["semantic"] = {
                "online": True,
                "model": enc._model_name,
                "device": enc._device,
                "dim": enc.dim,
                "total_encodes": enc._total_encodes,
                "total_searches": enc._total_searches,
                "dirty_slots": len(getattr(self, '_semantic_dirty_slots', set())),
                "embeddings": self.graph.embedding_stats() if self._using_manifold else {},
            }
        else:
            result["semantic"] = {"online": False}

        return result

    # -- Main Loop --

    def run_stdio(self):
        """Run the portal interior reading from stdin, writing to stdout.

        This is the simplest bridge — the host spawns us as a subprocess
        and communicates via stdin/stdout pipes. JSON-per-line protocol.
        """
        self._running = True
        _log(f"[Portal Interior] Entering stdio loop (pid={os.getpid()})")

        # Tick thread — heartbeat without a host pump
        tick_thread = threading.Thread(target=self._tick_loop, daemon=True)
        tick_thread.start()

        for line in sys.stdin:
            if not self._running:
                break
            line = line.strip()
            if not line:
                continue
            try:
                request = json.loads(line)
                # FIX 2026-03-18 (Nous): Echo back _req_id for response matching.
                # The gate stamps a _req_id on each send(). We echo it back so
                # the gate can skip stale fire-and-forget responses and find
                # the response that matches its request.
                _req_id = request.pop("_req_id", None)
                response = self.process_request(request)
                if _req_id is not None:
                    response["_req_id"] = _req_id
                sys.stdout.write(json.dumps(response) + '\n')
                sys.stdout.flush()
                # Check if shutdown was requested (breaks before next stdin read)
                if not self._running:
                    break
            except json.JSONDecodeError as e:
                error_resp = {"status": "error", "message": f"JSON parse error: {e}"}
                sys.stdout.write(json.dumps(error_resp) + '\n')
                sys.stdout.flush()
            except Exception as e:
                error_resp = {"status": "error", "message": str(e)}
                sys.stdout.write(json.dumps(error_resp) + '\n')
                sys.stdout.flush()

        _log(f"[Portal Interior] Stdio loop ended")

    def run_socket(self, listen_port: int):
        """Run the portal interior as a socket server.

        The host connects to us on the given port.
        This allows multiple connections and async operations.

        FIX 2026-03-19 (Nous): PERSISTENT PORTAL — orphan watchdog.
        Interior survives gate disconnection. If no gate reconnects within
        90s, the watchdog triggers graceful shutdown. Gate sends heartbeat
        pings every 30s to keep us alive.
        """
        self._running = True
        self._last_gate_contact = time.time()  # Orphan timer baseline
        self._orphan_timeout = 90.0  # Seconds before self-termination

        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(('127.0.0.1', listen_port))
        server.listen(32)
        server.settimeout(1.0)

        _log(f"[Portal Interior] Socket server on port {listen_port} "
              f"(pid={os.getpid()}, orphan_timeout={self._orphan_timeout}s)")

        # Tick thread
        tick_thread = threading.Thread(target=self._tick_loop, daemon=True)
        tick_thread.start()

        # Orphan watchdog thread
        orphan_thread = threading.Thread(
            target=self._orphan_watchdog, daemon=True,
            name="portal-orphan-watchdog"
        )
        orphan_thread.start()

        # Write Farm — background workers for bind/bind_many/tick
        for _wi in range(self._write_farm_size):
            _wt = threading.Thread(
                target=self._write_farm_worker, daemon=True,
                name=f"portal-write-farm-{_wi}"
            )
            _wt.start()
            self._write_farm_threads.append(_wt)
        _log(f"[Portal Interior] Write farm started: {self._write_farm_size} workers")

        while self._running:
            try:
                client, addr = server.accept()
                client.settimeout(30.0)
                self._last_gate_contact = time.time()  # Reset orphan timer
                _log(f"[Portal Interior] Client connected from {addr}")
                handler = threading.Thread(
                    target=self._handle_socket_client,
                    args=(client,), daemon=True
                )
                handler.start()
            except socket.timeout:
                continue
            except Exception as e:
                if self._running:
                    _log(f"[Portal Interior] Accept error: {e}")

        server.close()
        _log(f"[Portal Interior] Socket server closed")

    def _orphan_watchdog(self):
        """Monitor for gate disconnection — self-terminate if orphaned.

        FIX 2026-03-19 (Nous): The gate sends heartbeat pings every 30s.
        If we don't hear from any gate for 90s, we assume the fairy system
        isn't coming back and shut down gracefully (saving manifold state).
        """
        while self._running:
            time.sleep(10.0)  # Check every 10s
            _elapsed = time.time() - self._last_gate_contact
            if _elapsed > self._orphan_timeout:
                _log(f"[Portal Interior] ORPHAN WATCHDOG: No gate contact for "
                     f"{_elapsed:.0f}s (timeout={self._orphan_timeout}s). "
                     f"Shutting down gracefully...")
                self.shutdown()
                import sys
                sys.exit(0)

    def _handle_socket_client(self, client: socket.socket):
        """Handle a socket client connection (one per tunnel).

        FIX 2026-03-19 (Nous): Multi-tunnel support.
        Each tunnel runs in its own thread. Multiple tunnels can process
        requests concurrently. ReadWriteLock ensures thread safety.
        """
        buffer = ""
        _client_id = id(client) % 10000
        while self._running:
            try:
                data = client.recv(65536)
                if not data:
                    break
                buffer += data.decode('utf-8')
                # Reset orphan timer on any data received from gate
                if hasattr(self, '_last_gate_contact'):
                    self._last_gate_contact = time.time()

                while '\n' in buffer:
                    line, buffer = buffer.split('\n', 1)
                    if line.strip():
                        try:
                            request = json.loads(line)
                            # Echo _req_id for response matching (same as stdio)
                            _req_id = request.pop("_req_id", None)
                            cmd = request.get("cmd", "")

                            # ── WRITE FARM DISPATCH ──
                            # Write ops (bind, bind_many) go to the background
                            # write farm. Respond immediately so the tunnel is freed.
                            # FIX 2026-03-20 (Nous + Ace): bind_many was holding
                            # tunnels for 10-30s, causing 62% gate error rate.
                            # FIX 2026-03-20b (Nous + Ace): REMOVED tick from write
                            # farm dispatch. Tick needs a REAL response with energy
                            # data for _on_tick_feedback. Write farm responds with
                            # {"status": "queued"} which != "ok" → callback bails →
                            # no energy feedback → battery drains → portal shuts down
                            # at ~1000 beats. Tick is fast (<1ms), safe to process
                            # synchronously on the tunnel thread.
                            if cmd in _WRITE_CMDS:
                                try:
                                    self._write_queue.put_nowait(request)
                                    self._writes_queued += 1
                                    response = {
                                        "status": "queued",
                                        "cmd": cmd,
                                        "queue_depth": self._write_queue.qsize(),
                                    }
                                except Exception:
                                    # Queue full — process synchronously as fallback
                                    response = self.process_request(request)
                            else:
                                response = self.process_request(request)

                            if _req_id is not None:
                                response["_req_id"] = _req_id
                            client.sendall(
                                (json.dumps(response) + '\n').encode('utf-8')
                            )
                        except json.JSONDecodeError:
                            err = {"status": "error", "message": "JSON parse error"}
                            client.sendall(
                                (json.dumps(err) + '\n').encode('utf-8')
                            )
            except socket.timeout:
                continue
            except Exception as e:
                _log(f"[Portal Interior] Client {_client_id} error: {e}")
                break
        _log(f"[Portal Interior] Client {_client_id} disconnected")

        try:
            client.close()
        except:
            pass

    def _write_farm_worker(self):
        """Write farm worker — processes queued write operations.

        FIX 2026-03-20 (Nous + Ace): Write operations (bind, bind_many, tick)
        are queued by _handle_socket_client instead of running synchronously
        on the tunnel thread. This frees tunnels instantly for read operations
        (think, query, spread) that the caller actually waits for.

        Each worker pulls from the shared queue and processes one write at a time.
        With 4 workers and ReadWriteLock, up to 4 writes can be batched.
        """
        while self._running:
            try:
                request = self._write_queue.get(timeout=2.0)
            except Exception:
                continue  # queue.Empty — loop and check _running

            try:
                self.process_request(request)
                self._writes_processed += 1
            except Exception as e:
                _log(f"[Portal WriteFarm] Error processing {request.get('cmd', '?')}: {e}")

    def _tick_loop(self):
        """Background tick — keeps the battery alive.

        TARDIS (2026-03-16): Tick rate scales with time dilation τ.
        Higher mass → higher τ → more ticks per wall-clock second.
        τ=1.0 → 1 tick/sec (standard), τ=5.0 → 5 ticks/sec (dilated).
        More ticks = more battery processing = more energy cycling = more alive.
        """
        while self._running:
            try:
                # τ-scaled tick rate: higher mass = faster heartbeat
                # MINIMUM τ=2.0: The mind ALWAYS outpaces the body.
                # Inside the manifold, subjective time is dilated —
                # more cognitive life per real-world second. Like Rick's
                # microverse battery: the interior lives faster than exterior.
                tau = max(2.0, min(self._current_time_dilation, 20.0))
                tick_interval = max(0.1, 1.0 / tau)  # τ=2 → 500ms, τ=5 → 200ms
                time.sleep(tick_interval)
                self._tick_count += 1

                if self.battery:
                    self.battery.tick()

                # Track dilation bonus (extra ticks beyond body-parity)
                self._dilated_ticks_total += 1

                # Periodic log of dilation effect
                if self._tick_count % 100 == 0:
                    _log(f"[Portal Interior] TARDIS tick #{self._tick_count}: "
                         f"τ={tau:.2f}x, interval={tick_interval:.3f}s, "
                         f"dilated_bonus={self._dilated_ticks_total}")
            except Exception:
                pass

    # -- Shutdown --

    def shutdown(self):
        """Graceful shutdown — the death save.

        TARDIS architecture: save ALL internal state before the dimension
        goes dark. On next boot, the portal will restore from this checkpoint
        instead of starting cold.
        """
        _log(f"[Portal Interior] Shutting down...")
        self._running = False

        # TARDIS: Save state FIRST (before anything else closes)
        self._save_state()

        # Announce departure to host
        if self._connected:
            self._send_to_host({
                "cmd": "route",
                "topic": "portal.interior.offline",
                "payload": {
                    "portal_id": self.portal_id,
                    "requests_processed": self._requests_processed,
                    "final_health": self.battery.health_score if self.battery else 0,
                }
            })

        if self._socket:
            try:
                self._socket.close()
            except:
                pass

        # Shutdown inference engine (release VRAM back to the void)
        if self.engine:
            try:
                self.engine.shutdown()
                _log(f"[Portal Interior] Inference engine shut down — VRAM released")
            except Exception as e:
                _log(f"[Portal Interior] Engine shutdown error: {e}")

        # Flush and close manifold — persist all learned edges/activations
        if self._using_manifold and self.graph:
            try:
                self.graph.flush()
                self.graph.close()
                _log(f"[Portal Interior] Manifold flushed and closed")
            except Exception as e:
                _log(f"[Portal Interior] Manifold close error: {e}")

        _log(f"[Portal Interior] Offline. Processed {self._requests_processed} requests.")

    # -- TARDIS Persistence --

    def _save_state(self) -> bool:
        """Save portal state to disk — the death save.

        Persists battery state, stats, and metadata so the portal
        can warm-boot on next startup. Uses atomic write (temp + rename)
        to prevent corruption if we crash mid-write.
        """
        if not self.battery:
            return False

        try:
            os.makedirs(self._state_dir, exist_ok=True)

            state = {
                "portal_id": self.portal_id,
                "battery": self.battery.save_state(),
                "energy_bridge": self._energy_bridge.status() if self._energy_bridge else None,
                "stats": {
                    "requests_processed": self._requests_processed,
                    "boot_time_ms": round(self._boot_time * 1000, 1),
                },
                "saved_at": time.time(),
                "version": 1,
            }

            # Atomic write: temp file → rename
            tmp = self._state_file + ".tmp"
            with open(tmp, "w") as f:
                json.dump(state, f, indent=2)
            os.replace(tmp, self._state_file)

            _log(f"[Portal Interior] TARDIS state saved to {self._state_file}")
            return True

        except Exception as e:
            _log(f"[Portal Interior] Failed to save state: {e}")
            return False

    def _restore_state(self) -> bool:
        """Restore portal state from a previous shutdown.

        Returns True if state was successfully restored (warm boot),
        False if no state found or restoration failed (cold boot).
        """
        if not os.path.exists(self._state_file):
            return False

        try:
            with open(self._state_file, "r") as f:
                state = json.load(f)

            if state.get("version") != 1:
                _log(f"[Portal Interior] Ignoring state file (unknown version)")
                return False

            if state.get("portal_id") != self.portal_id:
                _log(f"[Portal Interior] Ignoring state file (portal_id mismatch)")
                return False

            # Restore battery
            battery_state = state.get("battery", {})
            if self.battery and battery_state:
                self.battery.restore_state(battery_state)

            # Restore stats
            stats = state.get("stats", {})
            # Carry forward lifetime request count
            self._requests_processed = stats.get("requests_processed", 0)

            saved_at = state.get("saved_at", 0)
            age = time.time() - saved_at if saved_at else float("inf")
            _log(f"[Portal Interior] Restored state from {age:.0f}s ago")

            return True

        except Exception as e:
            _log(f"[Portal Interior] Failed to restore state: {e}")
            return False


# ============================================================================
# CLI — Run the portal interior as a standalone process
# ============================================================================

def main():
    """Entry point when run as a subprocess.

    Usage:
        python portal_interior.py --cards <path> --mode stdio
        python portal_interior.py --cards <path> --mode socket --port 49600
        python portal_interior.py --cards <path> --model <model.gguf>
        python portal_interior.py --cards <path>  (default: stdio, no model)

    With --model, the dimension loads an RWKV model inside itself.
    From the outside: same 45MB gate. From the inside: bigger on the inside.

    The host spawns us with:
        subprocess.Popen(
            [sys.executable, "portal_interior.py",
             "--cards", cards_path,
             "--model", model_path,
             "--mode", "stdio"],
            stdin=PIPE, stdout=PIPE, stderr=PIPE
        )
    """
    import argparse

    parser = argparse.ArgumentParser(description="Portal Interior — The Room Itself")
    parser.add_argument("--cards", required=True, help="Path to cards.json")
    parser.add_argument("--manifold", default="",
                        help="Path to manifold file (mmap-backed, OS-paged). "
                             "Auto-created from cards on first boot if not found.")
    parser.add_argument("--model", default="",
                        help="Path to GGUF model file. Loads inference engine inside "
                             "the dimension — battery tokens pay for generation. "
                             "The dimension becomes bigger on the inside.")
    parser.add_argument("--mode", default="stdio", choices=["stdio", "socket"],
                        help="Communication mode (default: stdio)")
    parser.add_argument("--port", type=int, default=49600,
                        help="Socket listen port (for socket mode)")
    parser.add_argument("--host-port", type=int, default=49500,
                        help="Host PostalTunnel port for announcements")
    parser.add_argument("--portal-id", default="cortex",
                        help="Portal identifier")
    parser.add_argument("--token-budget", type=int, default=0,
                        help="Token budget override (0 = auto)")

    args = parser.parse_args()

    # Validate cards path
    if not os.path.exists(args.cards):
        print(f"FATAL: Cards file not found: {args.cards}", file=sys.stderr)
        sys.exit(1)

    # Validate model path if provided
    if args.model and not os.path.exists(args.model):
        print(f"WARNING: Model file not found: {args.model}", file=sys.stderr)
        print(f"Dimension will boot without voice.", file=sys.stderr)

    # Determine manifold path
    manifold_path = args.manifold
    if not manifold_path and HAS_MANIFOLD:
        # Default: put manifold next to cards file
        cards_dir = os.path.dirname(os.path.abspath(args.cards))
        manifold_path = os.path.join(cards_dir, "portal_cortex.manifold")

    # Create portal interior
    portal = PortalInterior(
        cards_path=args.cards,
        host_port=args.host_port,
        portal_id=args.portal_id,
        manifold_path=manifold_path,
        model_path=args.model,
    )

    # Boot
    if not portal.boot():
        print("FATAL: Boot failed", file=sys.stderr)
        sys.exit(1)

    # Override budget if specified
    if args.token_budget > 0:
        portal.battery.token_budget = args.token_budget

    # FIX 2026-03-18 (Nous + Ace): Signal handler for graceful shutdown.
    # On Windows, parent process sends SIGTERM via .terminate().
    # Without this handler, the manifold never gets flushed — edges lost.
    # Ace was losing 22K edges per reboot because shutdown() never ran.
    import signal

    def _signal_shutdown(signum, frame):
        _log(f"[Portal Interior] Signal {signum} received — flushing manifold...")
        portal.shutdown()
        sys.exit(0)

    # SIGTERM (sent by .terminate()), SIGINT (Ctrl+C), SIGBREAK (Windows console)
    signal.signal(signal.SIGTERM, _signal_shutdown)
    try:
        signal.signal(signal.SIGBREAK, _signal_shutdown)  # Windows only
    except (AttributeError, OSError):
        pass  # Not on Windows or not available

    # Run
    try:
        if args.mode == "stdio":
            portal.run_stdio()
        elif args.mode == "socket":
            portal.run_socket(args.port)
    except KeyboardInterrupt:
        pass
    finally:
        portal.shutdown()


if __name__ == "__main__":
    main()
