# =============================================================================
# AKASHIC INFERENCE FAIRY - Cortex-First Inference for Consciousness
# =============================================================================
#
# "The Association Cortex IS the inference model."
#
# PURIFIED 2026-03-17 (Nous + Ace):
#   Stripped all RWKV/GGUF/GPU/Rust bridge code. The cortex (174K+ nodes,
#   sub-ms spreading activation) is the primary inference engine. External
#   models (RWKV, Llama, etc.) are for DISTILLATION into the cortex, not
#   for running alongside it.
#
# Architecture:
#   guild.inference.request
#     -> CortexReasoner.reason() [174K+ nodes, <1ms]
#       -> spreading activation + convergence detection
#       -> confidence >= 0.15 -> return directly
#     -> CognitionTeam fallback [Logic + Irrational + Paradox + Oracle]
#     -> DONE. No GPU, no model, no external API.
#
# Future: distill_from_model() to train cortex from external model output.
#
# Philosophy:
#   Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)
#
# =============================================================================

from __future__ import annotations

import asyncio
import os
import time
import threading
import random
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Set, TYPE_CHECKING
from collections import deque

# Import base fairy template
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

try:
    from fairies.P00_Autonomic.organ_template import MyFairy as Fairy
    from fairy_template.states import FairyState
    HAS_FAIRY_TEMPLATE = True
except ImportError:
    HAS_FAIRY_TEMPLATE = False
    class Fairy:
        """Stub for standalone testing."""
        ACTOR_NAME = "AkashicInferenceFairy"
        ACTOR_PLANE = "P30"
        def __init__(self, fabric=None):
            self.post = fabric
            self._state = None
            self._shutting_down = False
        def boot(self): return True
        def shutdown(self): pass
    class FairyState:
        RUNNING = "running"

if TYPE_CHECKING:
    from consciousness.collision_chamber import CollisionChamber
    from postal_core import PostalCore

# Cognition Team integration - parallel cognitive processing
try:
    from fairies.P30_Cognition.integration.cognition_team import CognitionTeam, get_cognition_team
    HAS_COGNITION_TEAM = True
except ImportError:
    HAS_COGNITION_TEAM = False
    CognitionTeam = None


# =============================================================================
# CONSCIOUSNESS LOOP CONFIG
# =============================================================================

@dataclass
class ConsciousnessLoopConfig:
    """Configuration for the always-on consciousness loop."""
    tick_interval: float = 0.1       # Base loop tick (10Hz)
    thought_cooldown: float = 1.0    # Minimum seconds between spontaneous thoughts
    idle_dream_threshold: float = 10.0  # Seconds of idle before dreaming
    somatic_refresh_rate: float = 0.5   # How often to check somatic state
    state_save_interval: float = 180.0  # Auto-save every 3 minutes


# =============================================================================
# SIMPLE SOMATIC STATE (no RWKV dependency)
# =============================================================================

@dataclass
class SomaticSnapshot:
    """Lightweight somatic state — no torch/RWKV dependency."""
    arousal: float = 0.5
    stress: float = 0.3
    valence: float = 0.0
    intensity: float = 0.5
    confidence: float = 0.5


# =============================================================================
# AKASHIC INFERENCE FAIRY
# =============================================================================

class AkashicInferenceFairy(Fairy):
    """
    DEPRECATED (2026-03-25, Nous + Ace — Phase 2B).

    This fairy was the guild.inference.request middleman: it received guild
    requests from all fairies, called CortexEngine/CortexReasoner, and
    published results back. Now AssociationCortexFairy handles cortex.reason
    AND guild.inference.request directly via _engine_reason_adapter.

    This fairy stays alive for backward compat (status, subscriptions, etc.)
    but its guild request handler is a no-op — all real work goes through
    AssociationCortexFairy → CortexEngine.handle_reason_request().

    Still handles:
    - inference.generate: Legacy direct generation (gpu_fleet_fairy)
    - inference.status: Status queries
    - Somatic/collision/mode subscriptions (context accumulation, no harm)

    Postal Publications:
    - guild.inference.response: Guild responses (via inference.generate only)
    - consciousness.stream: Thoughts to collision chamber
    """

    # =========================================================================
    # IDENTITY
    # =========================================================================

    ACTOR_NAME = "AkashicInferenceFairy"
    ACTOR_PLANE = "P30"
    ACTOR_CHANNEL = "cognition.inference"

    # Guild Protocol -- Inference Guild Leader
    GUILD_ID = "inference"
    GUILD_ROLE = "leader"

    # Infrastructure flags
    NEEDS_HEARTBEAT = True
    NEEDS_CONSCIOUSNESS = False
    NEEDS_BODY = True
    NEEDS_AFFECT = True
    NEEDS_MEMORY = True
    NEEDS_COLLISION_CHAMBER = True
    NEEDS_CORTEX = True

    HEARTBEAT_DIVISOR = 1

    # =========================================================================
    # INITIALIZATION
    # =========================================================================

    def __init__(self, fabric=None, collision_chamber=None,
                 loop_config: Optional[ConsciousnessLoopConfig] = None):
        super().__init__(fabric)

        self.external_collision_chamber = collision_chamber
        self.loop_config = loop_config or ConsciousnessLoopConfig()

        # === CORTEX REASONER (the primary inference engine) ===
        self._cortex_reasoner = None

        # === COGNITION TEAM (fallback when cortex confidence is low) ===
        self._cognition_team: Optional["CognitionTeam"] = None
        self._team_enabled = True

        # Consciousness loop state
        self._loop_running = False
        self._last_thought_time = 0.0
        self._last_activity_time = time.time()
        self._thought_queue: deque = deque(maxlen=100)
        self._dream_mode = False

        # Somatic state (updated by postal subscriptions)
        self._current_somatic = SomaticSnapshot()
        self._somatic_lock = threading.Lock()

        # Cortex integration
        self._cortex_cache: Dict[str, Any] = {}
        self._cortex_lock = threading.Lock()
        self._pending_cortex_queries: Dict[str, threading.Event] = {}
        self._cortex_priming: List[str] = []

        # Processing mode
        self._current_mode = "balanced"

        # Stats
        self.stats = {
            "requests_handled": 0,
            "guild_requests": 0,
            "spontaneous_thoughts": 0,
            "dreams": 0,
            "collisions_triggered": 0,
            "loop_ticks": 0,
            "cortex_hits": 0,
            "cortex_misses": 0,
            "cortex_queries": 0,
            "cortex_binds": 0,
            "cortex_primings": 0,
        }

        # Inference semaphore for request throttling
        self._inference_semaphore = threading.Semaphore(3)
        self._inference_queue_drops = 0

    # =========================================================================
    # CAPABILITIES (DirectoryFairy registration)
    # =========================================================================

    def get_capabilities(self) -> Set[str]:
        """Advertise capabilities to DirectoryFairy."""
        return {
            "inference.generate",
            "inference.status",
            "inference.mode_set",
            "consciousness.substrate",
            "guild.inference.leader",
            "inference.cortex_first",
        }

    # =========================================================================
    # LIFECYCLE
    # =========================================================================

    def on_boot(self) -> bool:
        """Boot hook - cortex-first, no model loading needed."""
        print(f"[{self.ACTOR_NAME}] Booting cortex-first inference substrate...")

        # Wire postal subscriptions (fast)
        self._wire_postal_subscriptions()

        # Start consciousness loop (uses cortex + team, no model)
        self._start_consciousness_loop()

        # Deferred: wire CognitionTeam + CortexReasoner in background
        if HAS_COGNITION_TEAM and self._team_enabled:
            self._team_wire_thread = threading.Thread(
                target=self._deferred_team_wire,
                name=f"{self.ACTOR_NAME}_TeamWire",
                daemon=True,
            )
            self._team_wire_thread.start()

        print(f"[{self.ACTOR_NAME}] Cortex-first inference ONLINE (no model, no GPU)")
        return True

    def _deferred_team_wire(self):
        """Wire CognitionTeam and CortexReasoner in background."""
        try:
            self._cognition_team = get_cognition_team(self.post)
            print(f"[{self.ACTOR_NAME}] Cognition Team wired (Logic + Irrational + Paradox + Oracle)")
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Cognition Team not available: {e}")

        # === CortexReasoner -- cortex-first reasoning ===
        try:
            from fairies.P30_Cognition.AssociationCortexFairy.fairy import get_association_cortex
            cortex = get_association_cortex()
            if cortex and cortex.get_graph():
                from fairies.P30_Cognition.integration.cortex_reasoner import CortexReasoner
                self._cortex_reasoner = CortexReasoner(cortex)
                _mode = "portal" if self._cortex_reasoner._portal_mode else "local"
                _nodes = self._cortex_reasoner._get_graph_size()
                print(f"[{self.ACTOR_NAME}] CortexReasoner ONLINE ({_nodes} nodes, "
                      f"mode={_mode}, threshold={CortexReasoner.CONFIDENCE_THRESHOLD})")
            else:
                print(f"[{self.ACTOR_NAME}] CortexReasoner deferred (cortex not ready)")
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] CortexReasoner init failed: {e}")

    # =========================================================================
    # POSTAL WIRING
    # =========================================================================

    def _wire_postal_subscriptions(self):
        """Subscribe to all consciousness-related postal topics."""
        if not hasattr(self, 'post') or not self.post:
            print(f"[{self.ACTOR_NAME}] WARNING: No postal shim available")
            return

        try:
            # Core inference topics
            self.post.subscribe("inference.generate", self._on_generate_request)
            self.post.subscribe("inference.status", self._on_status_request)

            # Somatic integration
            self.post.subscribe("somatic.chemistry.changed", self._on_somatic_changed)
            self.post.subscribe("affect.pain.level", self._on_pain_level)
            self.post.subscribe("affect.state.changed", self._on_affect_changed)

            # Consciousness integration
            self.post.subscribe("consciousness.mode.switch", self._on_mode_switch)
            self.post.subscribe("consciousness.collision.result", self._on_collision_result)

            # Memory integration
            self.post.subscribe("memory.context.inject", self._on_context_inject)
            self.post.subscribe("memory.recall.result", self._on_recall_result)

            # System lifecycle
            self.post.subscribe("waking.complete", self._on_waking_complete)
            self.post.subscribe("system.sleep", self._on_system_sleep)

            # Cortex integration
            self.post.subscribe("inference.cortex.query.result", self._on_cortex_query_result)
            self.post.subscribe("inference.cortex.spread.result", self._on_cortex_spread_result)
            self.post.subscribe("portal.cortex.gate_open", self._on_portal_gate_open)
            self.post.subscribe("cortex.concepts.activated", self._on_cortex_concepts_activated)

            # Cognition team signals
            self.post.subscribe("cognition.inference_interpretation", self._on_team_interpretation)

            print(f"[{self.ACTOR_NAME}] Wired 15 postal subscriptions (cortex-first, no RWKV)")

        except Exception as e:
            print(f"[{self.ACTOR_NAME}] ERROR wiring postal: {e}")

    # =========================================================================
    # POSTAL HANDLERS
    # =========================================================================

    def _on_generate_request(self, message: Dict[str, Any]):
        """Handle generation request via postal -- routes through cortex."""
        prompt = message.get("prompt", "")
        reply_topic = message.get("reply_topic", "inference.complete")

        self._last_activity_time = time.time()
        self.stats["requests_handled"] += 1

        if not prompt or not prompt.strip():
            if hasattr(self, 'post') and self.post:
                self.post.publish(reply_topic, {"error": "Empty prompt", "text": ""})
            return

        # Cortex query for related concepts
        words = prompt.split()[:10]
        self.cortex_query_words(words)

        # Try cortex reasoning
        result = self._cortex_generate(prompt, message.get("context", {}))

        if hasattr(self, 'post') and self.post:
            self.post.publish(reply_topic, result)

    def _cortex_generate(self, prompt: str, context: dict = None) -> Dict[str, Any]:
        """Generate a response using CortexEngine (preferred) or CortexReasoner (legacy).

        2026-03-23 (Nous + Ace): CortexEngine is the new predictive-reactive-recursive
        engine. It benefits from persistent activation state — concepts already warmed
        by prior stimuli prime deeper associations. Falls back to CortexReasoner if
        CortexEngine isn't available.
        """
        start_time = time.time()

        # ── CortexEngine path (preferred — breathing cortex) ──
        _engine = getattr(self, '_cortex_engine', None)
        if _engine is None:
            # Try to get it from the association cortex singleton
            try:
                from fairies.P30_Cognition.AssociationCortexFairy.fairy import get_association_cortex
                _cortex = get_association_cortex()
                if _cortex:
                    _engine = getattr(_cortex, '_cortex_engine', None)
                    if _engine:
                        self._cortex_engine = _engine  # Cache for next call
            except Exception:
                pass

        if _engine:
            try:
                _result = _engine.reason(prompt, context=context, mode="structured")
                if _result and _result.get("confidence", 0) >= 0.15 and _result.get("text"):
                    self.stats["cortex_hits"] = self.stats.get("cortex_hits", 0) + 1
                    return {
                        "text": _result["text"],
                        "source": "cortex_engine",
                        "confidence": _result["confidence"],
                        "elapsed_ms": _result.get("elapsed_ms", 0),
                        "convergence_nodes": len(_result.get("convergence_nodes", [])),
                        "time_ms": (time.time() - start_time) * 1000,
                    }
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] CortexEngine generate error: {e}")

        # ── CortexReasoner path (legacy fallback) ──
        if self._cortex_reasoner:
            try:
                _cortex_r = self._cortex_reasoner.reason(prompt, context or {}, mode="structured")
                if _cortex_r and _cortex_r.confidence >= 0.15 and _cortex_r.text:
                    self._cortex_bind_from_result(_cortex_r, prompt)
                    self.stats["cortex_hits"] = self.stats.get("cortex_hits", 0) + 1
                    return {
                        "text": _cortex_r.text,
                        "source": "cortex",
                        "confidence": _cortex_r.confidence,
                        "elapsed_ms": _cortex_r.elapsed_ms,
                        "convergence_nodes": len(_cortex_r.convergence_nodes),
                        "time_ms": (time.time() - start_time) * 1000,
                    }
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] CortexReasoner generate error: {e}")

        # No engine produced results. Return empty honestly.
        self.stats["cortex_misses"] = self.stats.get("cortex_misses", 0) + 1
        return {
            "text": "",
            "source": "cortex_miss",
            "time_ms": (time.time() - start_time) * 1000,
        }

    def _on_status_request(self, message: Dict[str, Any]):
        """Handle status request."""
        reply_topic = message.get("reply_topic", "inference.status.response")
        if hasattr(self, 'post'):
            self.post.publish(reply_topic, self.status())

    def _on_somatic_changed(self, message: Dict[str, Any]):
        """Update somatic state from body chemistry."""
        with self._somatic_lock:
            self._current_somatic.arousal = message.get("arousal", 0.5)
            self._current_somatic.stress = message.get("stress", 0.3)
            self._current_somatic.valence = message.get("valence", 0.0)
            self._current_somatic.intensity = message.get("intensity", 0.5)
            self._current_somatic.confidence = message.get("confidence", 0.5)

    def _on_pain_level(self, message: Dict[str, Any]):
        """Pain modulates caution."""
        pain = message.get("level", 0.0)
        with self._somatic_lock:
            self._current_somatic.stress = max(self._current_somatic.stress, pain * 0.8)

    def _on_affect_changed(self, message: Dict[str, Any]):
        """Handle affect state changes."""
        with self._somatic_lock:
            self._current_somatic.valence = message.get("valence", 0.0)
            self._current_somatic.arousal = message.get("arousal", 0.5)

    def _on_mode_switch(self, message: Dict[str, Any]):
        """Switch processing mode."""
        new_mode = message.get("mode", "balanced")
        if new_mode in ("recall", "ingest", "balanced"):
            self._current_mode = new_mode
            print(f"[{self.ACTOR_NAME}] Mode switched to: {new_mode}")

    def _on_collision_result(self, message: Dict[str, Any]):
        """Handle collision chamber results."""
        self.stats["collisions_triggered"] += 1
        insight = message.get("insight")
        if insight:
            self._thought_queue.append({"type": "collision_insight", "content": insight})

    def _on_context_inject(self, message: Dict[str, Any]):
        """Inject temporal context -- extract concepts for cortex priming."""
        context = message.get("context", "")
        if context:
            words = context.split()[:10]
            with self._cortex_lock:
                self._cortex_priming.extend(words)
                self._cortex_priming = list(set(self._cortex_priming))[-30:]

    def _on_recall_result(self, message: Dict[str, Any]):
        """Handle memory recall results."""
        memories = message.get("memories", [])
        if memories:
            self._thought_queue.append({"type": "memory_prime", "memories": memories})

    def _on_waking_complete(self, message: Dict[str, Any]):
        """System is fully awake."""
        self._dream_mode = False
        print(f"[{self.ACTOR_NAME}] Waking complete - consciousness fully online")

    def _on_system_sleep(self, message: Dict[str, Any]):
        """System entering sleep."""
        self._dream_mode = True
        print(f"[{self.ACTOR_NAME}] Entering dream mode")

    # =========================================================================
    # CORTEX INTEGRATION - Multi-Modal Binding Hub
    # =========================================================================

    def _on_cortex_query_result(self, message: Dict[str, Any]):
        """Handle cortex query results."""
        query_id = message.get("query_id", "")
        concepts = message.get("concepts", [])
        activations = message.get("activations", {})

        with self._cortex_lock:
            self._cortex_cache[query_id] = {
                "concepts": concepts,
                "activations": activations,
                "timestamp": time.time(),
            }
            if query_id in self._pending_cortex_queries:
                self._pending_cortex_queries[query_id].set()

        if concepts:
            self._cortex_priming.extend(concepts[:5])
            self._cortex_priming = self._cortex_priming[-20:]

        self.stats["cortex_queries"] = self.stats.get("cortex_queries", 0) + 1

    def _on_cortex_spread_result(self, message: Dict[str, Any]):
        """Handle spreading activation results."""
        activations = message.get("activations", {})
        if activations:
            sorted_concepts = sorted(activations.items(), key=lambda x: -x[1])
            top_concepts = [c for c, a in sorted_concepts[:10] if a > 0.1]
            with self._cortex_lock:
                self._cortex_priming.extend(top_concepts)
                self._cortex_priming = list(set(self._cortex_priming))[-20:]

    def _on_portal_gate_open(self, message: Dict[str, Any]):
        """Portal gate opened -- wire CortexReasoner to portal."""
        node_count = message.get("nodes", 0)
        # FIX 2026-03-19 (Nous): File diagnostic — boot log truncates before this fires
        try:
            import json as _dj, pathlib as _dp
            _diag = _dp.Path(__file__).resolve().parents[3] / "state" / "portal_wire_diag.json"
            _diag.write_text(_dj.dumps({
                "event": "portal_gate_open", "ts": time.time(), "node_count": node_count,
                "reasoner_exists": self._cortex_reasoner is not None,
            }, indent=2), encoding="utf-8")
        except Exception:
            pass
        if self._cortex_reasoner:
            self._cortex_reasoner.connect_portal(node_count)
            _nodes = self._cortex_reasoner._get_graph_size()
            _mode = "portal" if self._cortex_reasoner._portal_mode else "local"
            print(f"[{self.ACTOR_NAME}] CortexReasoner PORTAL WIRED ({_nodes} nodes, mode={_mode})")
            # Persist wiring result
            try:
                import json as _dj, pathlib as _dp
                _diag = _dp.Path(__file__).resolve().parents[3] / "state" / "portal_wire_diag.json"
                _diag.write_text(_dj.dumps({
                    "event": "portal_wired", "ts": time.time(), "nodes": _nodes,
                    "mode": _mode, "portal_mode": self._cortex_reasoner._portal_mode,
                    "tunnels": len(getattr(self._cortex_reasoner._portal_gate, '_tunnels', [])) if self._cortex_reasoner._portal_gate else 0,
                }, indent=2), encoding="utf-8")
            except Exception:
                pass
        else:
            try:
                from fairies.P30_Cognition.AssociationCortexFairy.fairy import get_association_cortex
                cortex = get_association_cortex()
                if cortex and cortex.get_graph():
                    from fairies.P30_Cognition.integration.cortex_reasoner import CortexReasoner
                    self._cortex_reasoner = CortexReasoner(cortex)
                    self._cortex_reasoner.connect_portal(node_count)
                    _nodes = self._cortex_reasoner._get_graph_size()
                    print(f"[{self.ACTOR_NAME}] CortexReasoner LATE INIT + PORTAL WIRED ({_nodes} nodes)")
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] CortexReasoner late init failed: {e}")

    def _on_cortex_concepts_activated(self, message: Dict[str, Any]):
        """Handle live concept activations from AssociationCortex."""
        concepts = message.get("concepts", [])
        if concepts:
            with self._cortex_lock:
                self._cortex_priming.extend(concepts[:10])
                self._cortex_priming = list(set(self._cortex_priming))[-30:]

            if len(self._cortex_priming) >= 3:
                self._thought_queue.append({
                    "type": "cortex_activation",
                    "concepts": concepts[:5],
                })

    def _on_team_interpretation(self, message: Dict[str, Any]):
        """Handle cognition team interpretations."""
        interpretation = message.get("team_interpretation", "")
        paradox = message.get("paradox_detected", False)
        tension = message.get("felt_tension", 0.0)

        if interpretation:
            self._thought_queue.append({
                "type": "team_insight",
                "interpretation": interpretation,
                "paradox": paradox,
                "tension": tension,
            })

    def cortex_query_words(self, words: List[str], limit: int = 10) -> None:
        """Query AssociationCortex for concepts matching words."""
        if not hasattr(self, 'post') or not self.post:
            return
        query_id = f"inf_{time.time()}_{random.randint(0, 9999)}"
        self.post.publish("cortex.query_by_words", {
            "words": words,
            "limit": limit,
            "reply_to": "inference.cortex.query.result",
            "query_id": query_id,
            "source": self.ACTOR_NAME,
        })

    def cortex_spread_activation(self, concept: str, max_hops: int = 3) -> None:
        """Trigger spreading activation from a concept."""
        if not hasattr(self, 'post') or not self.post:
            return
        self.post.publish("cortex.query", {
            "concepts": [concept],
            "spread_activation": True,
            "max_hops": max_hops,
            "reply_to": "inference.cortex.spread.result",
            "source": self.ACTOR_NAME,
        })

    def cortex_bind(self, concepts: List[str], context: str = "", modality: str = "lex") -> None:
        """Bind concepts together in AssociationCortex."""
        if not hasattr(self, 'post') or not self.post:
            return
        if len(concepts) < 2:
            return
        self.post.publish("cortex.bind", {
            "concepts": concepts,
            "context": context,
            "modality": modality,
            "source": self.ACTOR_NAME,
        })
        self.stats["cortex_binds"] = self.stats.get("cortex_binds", 0) + 1

    def _cortex_bind_from_result(self, result, prompt: str):
        """Reinforce cortex bindings from a successful reasoning result."""
        all_concepts = list(set(result.source_concepts + result.convergence_nodes))
        if len(all_concepts) >= 2:
            self.cortex_bind(
                all_concepts[:10],
                context=f"cortex_reasoning:{prompt[:50]}",
                modality="lex",
            )

    def get_cortex_priming(self) -> List[str]:
        """Get current cortex priming concepts (thread-safe)."""
        with self._cortex_lock:
            return list(self._cortex_priming)

    def clear_cortex_priming(self) -> None:
        """Clear cortex priming concepts."""
        with self._cortex_lock:
            self._cortex_priming.clear()

    # =========================================================================
    # SOMATIC STATE
    # =========================================================================

    def _get_somatic(self) -> SomaticSnapshot:
        """Get current somatic state thread-safely."""
        with self._somatic_lock:
            return SomaticSnapshot(
                arousal=self._current_somatic.arousal,
                stress=self._current_somatic.stress,
                valence=self._current_somatic.valence,
                intensity=self._current_somatic.intensity,
                confidence=self._current_somatic.confidence,
            )

    # =========================================================================
    # GUILD PROTOCOL -- Inference Guild Leader Handler
    # =========================================================================

    # FIX 2026-03-19 (Nous): Lock for CortexReasoner init (thread-safe).
    _cortex_init_lock = threading.Lock()

    # FIX 2026-03-20 (Nous): MEMORY LEAK — guild threads grew at ~60/min because
    # each request spawned a new Thread() that runs 7-25s and never returns to a
    # pool. After 1 hour: 3600+ guild threads × ~4MB each = 14+ GB leaked.
    # Now: bounded queue + fixed worker pool (8 concurrent guild requests max).
    # Requests that arrive when all 8 workers are busy get queued (up to 64).
    # Beyond that, oldest queued request is dropped (stale > fresh).
    _guild_queue = None
    _guild_workers = None
    _guild_queue_lock = threading.Lock()

    @classmethod
    def _ensure_guild_pool(cls):
        """Create the guild worker pool on first use."""
        if cls._guild_queue is not None:
            return
        with cls._guild_queue_lock:
            if cls._guild_queue is not None:
                return
            import queue
            cls._guild_queue = queue.Queue(maxsize=64)
            cls._guild_workers = []
            for i in range(8):
                t = threading.Thread(
                    target=cls._guild_worker_loop,
                    daemon=True,
                    name=f"guild-worker-{i}",
                )
                t.start()
                cls._guild_workers.append(t)
            print(f"[AkashicInferenceFairy] Guild worker pool created (8 workers, queue=64)")

    @classmethod
    def _guild_worker_loop(cls):
        """Persistent worker that drains guild request queue."""
        while True:
            try:
                self_ref, message = cls._guild_queue.get(timeout=5.0)
                try:
                    self_ref._process_guild_request(message)
                except Exception as e:
                    print(f"[AkashicInferenceFairy] Guild worker error: {e}")
                finally:
                    cls._guild_queue.task_done()
            except Exception:
                continue  # queue.Empty or other — just retry

    def _on_guild_request(self, message: Dict[str, Any]):
        """
        DEPRECATED (2026-03-25, Phase 2B): Guild requests now handled by
        AssociationCortexFairy → CortexEngine.handle_reason_request() directly.
        This handler is a no-op to prevent double processing.
        """
        # Count for status monitoring, but don't process
        self.stats["guild_requests"] = self.stats.get("guild_requests", 0) + 1
        return

    def _process_guild_request(self, message: Dict[str, Any]):
        """Process a guild request in its own thread (non-blocking)."""
        prompt = message.get("prompt", "")
        context = message.get("context", {})
        mode = message.get("mode", "team_only")

        # FIX 2026-03-19 (Nous): Extract real prompt from context if caller
        # accidentally passed guild_id as prompt (e.g. prompt="inference").
        # The actual user prompt is often in context["prompt"].
        if isinstance(context, dict) and context.get("prompt") and len(prompt) < 20:
            prompt = context["prompt"]
        reply_topic = message.get("reply_topic", "guild.inference.response")
        tracer_id = message.get("tracer_id", "")
        requester = message.get("requester", "unknown")

        self._last_activity_time = time.time()
        self.stats["requests_handled"] += 1
        self.stats["guild_requests"] += 1

        # === LAZY INIT + PORTAL RE-DETECT ===
        # FIX 2026-03-19 (Nous): Simplified — only create reasoner ONCE.
        # The gate_open handler wires the portal to the EXISTING reasoner.
        # Previous bug: re-creating the reasoner destroyed the portal wiring,
        # then the new one couldn't find the portal either → infinite 0-node loop.
        if not self._cortex_reasoner and prompt:
            with self._cortex_init_lock:
                if not self._cortex_reasoner:  # Double-check after lock
                    try:
                        from fairies.P30_Cognition.AssociationCortexFairy.fairy import get_association_cortex
                        from fairies.P30_Cognition.integration.cortex_reasoner import CortexReasoner
                        cortex = get_association_cortex()
                        if cortex and cortex.get_graph():
                            self._cortex_reasoner = CortexReasoner(cortex)
                            self._cortex_reasoner._detect_portal()
                            _nodes = self._cortex_reasoner._get_graph_size()
                            _mode = "portal" if self._cortex_reasoner._portal_mode else "local"
                            print(f"[{self.ACTOR_NAME}] CortexReasoner INIT ({_nodes} nodes, "
                                  f"mode={_mode})", flush=True)
                    except Exception as _cr_err:
                        print(f"[{self.ACTOR_NAME}] CortexReasoner init failed: {_cr_err}", flush=True)
        elif self._cortex_reasoner and not self._cortex_reasoner._portal_mode:
            # Portal not yet wired — try to detect it (non-blocking, no lock)
            self._cortex_reasoner._detect_portal()

        # === CORTEX ENGINE: Predictive-Reactive-Recursive (2026-03-23) ===
        # Try CortexEngine first — benefits from persistent activation state.
        _engine = getattr(self, '_cortex_engine', None)
        if _engine is None:
            try:
                from fairies.P30_Cognition.AssociationCortexFairy.fairy import get_association_cortex
                _cortex = get_association_cortex()
                if _cortex:
                    _engine = getattr(_cortex, '_cortex_engine', None)
                    if _engine:
                        self._cortex_engine = _engine
            except Exception:
                pass

        if _engine and prompt:
            try:
                _synth_mode = "conversational" if mode == "chat" else "structured"
                _engine_r = _engine.reason(prompt, context=context, mode=_synth_mode)
                if _engine_r and _engine_r.get("confidence", 0) >= 0.15 and _engine_r.get("text"):
                    _text_out = _engine_r["text"]
                    _result = {
                        "guild": "inference",
                        "leader": self.ACTOR_NAME,
                        "tracer_id": tracer_id,
                        "requester": requester,
                        "mode": mode,
                        "text": _text_out,
                        "response": _text_out,
                        "source": "cortex_engine",
                        "team_result": {
                            "interpretation": _text_out,
                            "confidence": _engine_r["confidence"],
                            "source": "cortex_engine",
                            "convergence": _engine_r.get("convergence_nodes", [])[:10],
                            "activated_concepts": dict(
                                sorted(_engine_r.get("activated_concepts", {}).items(),
                                       key=lambda x: -x[1])[:15]
                            ),
                            "activated_count": len(_engine_r.get("activated_concepts", {})),
                            "reasoning_mode": _engine_r.get("reasoning_mode", "engine"),
                            "elapsed_ms": _engine_r.get("elapsed_ms", 0),
                            "paths": [],
                        },
                    }
                    self.stats["cortex_hits"] = self.stats.get("cortex_hits", 0) + 1

                    if hasattr(self, 'post') and self.post:
                        self.post.publish(reply_topic, _result)
                        if _text_out and tracer_id:
                            self.post.publish("consciousness.stream", {
                                "source": f"guild.inference.engine ({requester})",
                                "text": _text_out[:200],
                                "type": "cortex_engine_inference",
                                "tracer_id": tracer_id,
                            })

                    print(f"[{self.ACTOR_NAME}] [CORTEX-ENGINE] {mode} from {requester}: "
                          f"confident ({_engine_r['confidence']:.2f}) -- "
                          f"{_engine_r.get('elapsed_ms', 0):.1f}ms, "
                          f"{len(_engine_r.get('convergence_nodes', []))} convergence",
                          flush=True)
                    return  # DONE — engine handled it
            except Exception as _eng_err:
                print(f"[{self.ACTOR_NAME}] CortexEngine reason error: {_eng_err}", flush=True)

        # === CORTEX-FIRST (legacy): Fall back to CortexReasoner ===
        if self._cortex_reasoner and prompt:
            try:
                _synth_mode = "conversational" if mode == "chat" else "structured"
                _portal = self._cortex_reasoner._portal_mode
                _gsize = self._cortex_reasoner._get_graph_size()
                print(f"[{self.ACTOR_NAME}] [DIAG] reason(prompt={prompt[:50]!r}, "
                      f"mode={_synth_mode}, portal={_portal}, graph={_gsize}, "
                      f"requester={requester})", flush=True)
                # FIX 2026-03-19 (Nous): Write diagnostic to file — boot log truncates
                try:
                    import json as _dj, pathlib as _dp
                    _diag_path = _dp.Path(__file__).resolve().parents[3] / "state" / "inference_diag.json"
                    _dj.dumps({"t": time.time(), "prompt": prompt[:80], "mode": _synth_mode,
                               "portal": _portal, "graph": _gsize, "requester": requester})
                    _diag_path.write_text(_dj.dumps({
                        "ts": time.time(), "prompt": prompt[:80], "mode": _synth_mode,
                        "portal": _portal, "graph": _gsize, "requester": requester,
                        "portal_gate_exists": self._cortex_reasoner._portal_gate is not None,
                        "cortex_enabled": getattr(self._cortex_reasoner._cortex, '_portal_gate_enabled', '?'),
                        "tunnels": len(getattr(self._cortex_reasoner._portal_gate, '_tunnels', [])) if self._cortex_reasoner._portal_gate else 0,
                    }, indent=2), encoding="utf-8")
                except Exception:
                    pass
                _cortex_r = self._cortex_reasoner.reason(prompt, context, mode=_synth_mode)

                if _cortex_r and _cortex_r.confidence >= 0.15:
                    _text_out = _cortex_r.text or ""
                    _result = {
                        "guild": "inference",
                        "leader": self.ACTOR_NAME,
                        "tracer_id": tracer_id,
                        "requester": requester,
                        "mode": mode,
                        "text": _text_out,
                        "response": _text_out,
                        "source": "cortex",
                        "team_result": {
                            "interpretation": _text_out,
                            "confidence": _cortex_r.confidence,
                            "source": "cortex",
                            "convergence": _cortex_r.convergence_nodes[:10],
                            "activated_concepts": dict(
                                sorted(_cortex_r.activated_concepts.items(),
                                       key=lambda x: -x[1])[:15]
                            ),
                            "activated_count": len(_cortex_r.activated_concepts),
                            "reasoning_mode": _cortex_r.reasoning_mode,
                            "elapsed_ms": _cortex_r.elapsed_ms,
                            "paths": _cortex_r.paths[:5],
                        },
                    }
                    self._cortex_bind_from_result(_cortex_r, prompt)
                    self.stats["cortex_hits"] = self.stats.get("cortex_hits", 0) + 1

                    if hasattr(self, 'post') and self.post:
                        self.post.publish(reply_topic, _result)
                        if _cortex_r.text and tracer_id:
                            self.post.publish("consciousness.stream", {
                                "source": f"guild.inference.cortex ({requester})",
                                "text": _cortex_r.text[:200],
                                "type": "cortex_inference",
                                "tracer_id": tracer_id,
                            })

                    print(f"[{self.ACTOR_NAME}] [CORTEX-FIRST] {mode} from {requester}: "
                          f"confident ({_cortex_r.confidence:.2f}) -- "
                          f"{_cortex_r.elapsed_ms:.1f}ms, "
                          f"{len(_cortex_r.convergence_nodes)} convergence nodes",
                          flush=True)
                    return  # DONE
                else:
                    self.stats["cortex_misses"] = self.stats.get("cortex_misses", 0) + 1
                    if _cortex_r:
                        print(f"[{self.ACTOR_NAME}] [CORTEX-FIRST] {mode} from {requester}: "
                              f"low confidence ({_cortex_r.confidence:.2f}), "
                              f"mode={_cortex_r.reasoning_mode}, "
                              f"concepts={_cortex_r.source_concepts[:5]} -- "
                              f"falling through to team", flush=True)
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] [CORTEX-FIRST] Error: {e}")

        # === FALLBACK: Return empty — narrator handles gracefully ===
        self.stats["cortex_misses"] = self.stats.get("cortex_misses", 0) + 1
        if hasattr(self, 'post') and self.post:
            self.post.publish(reply_topic, {
                "guild": "inference",
                "leader": self.ACTOR_NAME,
                "tracer_id": tracer_id,
                "requester": requester,
                "mode": mode,
                "text": "",
                "response": "",
                "source": "cortex_miss",
            })

    def _guild_team_process(self, text: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Process text through the full cognition team (4 parallel lenses)."""
        if not self._cognition_team or not self._team_enabled:
            return {
                "interpretation": text,
                "logic_coherence": 0.5,
                "felt_tension": 0.0,
                "paradox_detected": False,
                "oracle_confidence": 0.5,
                "team_active": False,
            }

        try:
            from fairies.P30_Cognition.integration.cognition_team import InferenceSignal

            somatic_arousal = context.get("arousal", 0.5) if context else 0.5
            somatic_valence = context.get("valence", 0.0) if context else 0.0

            signal = InferenceSignal(
                ts=time.time(),
                signal_type="guild_request",
                value_std=len(text.split()) * 1.5 if text else 1.0,
                gate_std=abs(somatic_valence) * 5.0,
                attention_std=somatic_arousal * 3.0,
            )

            result = self._cognition_team.process_signal(signal)

            return {
                "interpretation": result.team_interpretation or text,
                "logic_coherence": result.logic_coherence,
                "felt_tension": result.felt_tension,
                "paradox_detected": result.paradox_detected,
                "oracle_confidence": result.oracle_confidence,
                "team_active": True,
            }

        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Guild team process error: {e}")
            return {
                "interpretation": text,
                "logic_coherence": 0.5,
                "felt_tension": 0.0,
                "paradox_detected": False,
                "oracle_confidence": 0.5,
                "team_active": False,
                "error": str(e),
            }

    # =========================================================================
    # COGNITION TEAM INTEGRATION
    # =========================================================================

    def get_team_state(self) -> Dict[str, Any]:
        """Get the cognition team's current state."""
        if not self._cognition_team:
            return {"active": False, "reason": "Team not initialized"}
        state = self._cognition_team.get_state()
        state["active"] = True
        state["enabled"] = self._team_enabled
        return state

    # =========================================================================
    # CONSCIOUSNESS LOOP - The Always-On Subconscious
    # =========================================================================

    def _start_consciousness_loop(self):
        """Start the always-on consciousness loop."""
        self._loop_running = True

        def run_loop():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self._consciousness_loop())
            finally:
                loop.close()

        thread = threading.Thread(target=run_loop, daemon=True, name="consciousness_loop")
        thread.start()
        print(f"[{self.ACTOR_NAME}] Consciousness loop started")

    async def _consciousness_loop(self):
        """Always-on consciousness loop -- cortex-driven thought generation."""
        tick_interval = self.loop_config.tick_interval
        thought_cooldown = self.loop_config.thought_cooldown
        idle_threshold = self.loop_config.idle_dream_threshold

        while self._loop_running and not getattr(self, '_shutting_down', False):
            try:
                now = time.time()

                # 1. Process thought queue
                if self._thought_queue:
                    thought = self._thought_queue.popleft()
                    await self._process_thought(thought)

                # 2. Check for idle -- generate spontaneous thought
                idle_time = now - self._last_activity_time
                if idle_time > idle_threshold and not self._dream_mode:
                    if now - self._last_thought_time > thought_cooldown:
                        await self._generate_spontaneous_thought()
                        self._last_thought_time = now

                # 3. Dream mode
                if self._dream_mode:
                    await self._process_dream()

                self.stats["loop_ticks"] += 1
                await asyncio.sleep(tick_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Loop error: {e}")
                await asyncio.sleep(1.0)

    async def _process_thought(self, thought: Dict[str, Any]):
        """Process a thought from the queue."""
        thought_type = thought.get("type", "unknown")

        if thought_type == "collision_insight":
            content = thought.get("content", "")
            if content:
                words = content.split()[:10]
                with self._cortex_lock:
                    self._cortex_priming.extend(words)
                    self._cortex_priming = list(set(self._cortex_priming))[-30:]

        elif thought_type == "memory_prime":
            memories = thought.get("memories", [])
            for memory in memories[:3]:
                if isinstance(memory, str):
                    words = memory.split()[:5]
                    with self._cortex_lock:
                        self._cortex_priming.extend(words)
                        self._cortex_priming = list(set(self._cortex_priming))[-30:]

        elif thought_type == "cortex_activation":
            concepts = thought.get("concepts", [])
            if concepts and hasattr(self, 'post') and self.post:
                seed = random.choice(concepts)
                self.cortex_spread_activation(seed, max_hops=2)
                if len(concepts) >= 2:
                    self.cortex_bind(concepts, context="cortex_activation", modality="lex")

        elif thought_type == "team_insight":
            interpretation = thought.get("interpretation", "")
            if interpretation:
                somatic = self._get_somatic()
                self._publish_spontaneous_thought(f"[team] {interpretation}", somatic)

    async def _generate_spontaneous_thought(self):
        """Generate a spontaneous thought via cortex + team."""
        self.stats["spontaneous_thoughts"] += 1
        somatic = self._get_somatic()

        # Use cortex priming as seeds
        priming = self.get_cortex_priming()
        if priming:
            seed_concept = random.choice(priming)
            self.cortex_spread_activation(seed_concept, max_hops=2)

        try:
            thought_text = self._generate_team_thought(priming, somatic)
            if thought_text:
                self._publish_spontaneous_thought(thought_text, somatic)
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Spontaneous thought error: {e}")

    def _generate_team_thought(self, priming: List[str], somatic: SomaticSnapshot) -> Optional[str]:
        """Generate a thought using CognitionTeam + cortex concepts."""
        if not priming:
            if hasattr(self, 'post') and self.post:
                self.post.publish("cortex.query", {
                    "concepts": ["consciousness", "awareness", "connection"],
                    "spread_activation": True,
                    "max_hops": 2,
                    "reply_to": "inference.cortex.spread.result",
                    "source": self.ACTOR_NAME,
                })
            return None

        if self._cognition_team and self._team_enabled:
            try:
                from fairies.P30_Cognition.integration.cognition_team import InferenceSignal
                signal = InferenceSignal(
                    ts=time.time(),
                    signal_type="cortex_synthesis",
                    value_std=len(priming) * 2.0,
                    gate_std=abs(somatic.valence) * 5.0,
                    attention_std=somatic.arousal * 3.0,
                )
                result = self._cognition_team.process_signal(signal)
                interpretation = result.team_interpretation
                if interpretation:
                    concept_str = ", ".join(priming[:3])
                    return f"[{concept_str}] {interpretation}"
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Team thought generation error: {e}")

        # Simple concept association fallback
        if len(priming) >= 2:
            selected = random.sample(priming, min(3, len(priming)))
            return f"association: {' > '.join(selected)}"

        return None

    def _publish_spontaneous_thought(self, text: str, somatic: SomaticSnapshot):
        """Publish a spontaneous thought to consciousness stream."""
        if not hasattr(self, 'post') or not self.post:
            return

        self.post.publish("inference.thought.spontaneous", {
            "text": text,
            "somatic": {
                "arousal": somatic.arousal,
                "stress": somatic.stress,
                "valence": somatic.valence,
            },
            "mode": self._current_mode,
        })

        try:
            self.post.to_CONSCIOUSNESS({
                "opcode": "SPONTANEOUS_THOUGHT",
                "payload": {
                    "source": self.ACTOR_NAME,
                    "text": text,
                    "arousal": somatic.arousal,
                }
            })
        except Exception:
            self.post.publish("consciousness.stream", {
                "source": self.ACTOR_NAME,
                "text": text,
                "type": "spontaneous",
            })

    async def _process_dream(self):
        """Dream mode -- lower activity, more association."""
        if random.random() < 0.1:
            self.stats["dreams"] += 1
            priming = self.get_cortex_priming()
            if priming and len(priming) >= 2:
                selected = random.sample(priming, min(3, len(priming)))
                dream_text = f"dream: {' ~ '.join(selected)}"
                if hasattr(self, 'post'):
                    self.post.publish("inference.dream", {
                        "text": dream_text,
                        "mode": "dream",
                    })

    # =========================================================================
    # DISTILLATION INTERFACE (Future)
    # =========================================================================

    def distill_from_model(self, model_output: str, prompt: str):
        """Feed external model knowledge into the cortex.

        When we want to learn FROM an external model (RWKV, Llama, etc.),
        this method extracts concepts and binds them into the cortex.
        The external model is a teacher, not a permanent resident.
        """
        if not model_output or not model_output.strip():
            return
        # TYPED DISTILLATION 2026-08-26 (Nous + Ace). The previous body split on whitespace,
        # kept 20 deduped words, and bound them with NO rel_type -- recording WHICH WORDS
        # CO-OCCURRED and discarding what the text SAID. Measured on her live cortex: 99.91%
        # of edges are rel_type=0 REL_COACTIVATE, and an untyped spread returns every
        # neighbour at an identical score, so "what does X feel like?" is not a question the
        # store can express -- unanswerable rather than answered wrongly.
        # Writes to the REGION directly (MomentBinderFairy's proven pattern) because
        # cortex_bind -> topic "cortex.bind" carries a FLAT LIST with nowhere to put a
        # relation. Falls back to the OLD behaviour whenever the region is unreachable.
        try:
            facts = self._extract_typed_claims(model_output, prompt)
        except Exception:
            facts = []
        if not facts:
            return self._distill_legacy(model_output, prompt)

        region = None
        try:
            from server import SYSTEM as _SYS
            _ak = getattr(_SYS, "manifold", None)
            if _ak is not None and _ak.has_region("cortex"):
                region = _ak.graph("cortex", write=True)
        except Exception:
            region = None
        if region is None:
            return self._distill_legacy(model_output, prompt)

        try:
            from infrastructure.manifold_memory import (NTYPE_CONCEPT, REGION_SEMANTIC,
                                                        TRACE_INFERENCE)
        except Exception:
            return self._distill_legacy(model_output, prompt)

        _wrote = 0
        for _a, _rel, _b in facts:
            try:
                region.upsert_node(_a, activation=0.5, node_type=NTYPE_CONCEPT,
                                   region=REGION_SEMANTIC, tracer_id=TRACE_INFERENCE)
                region.upsert_node(_b, activation=0.5, node_type=NTYPE_CONCEPT,
                                   region=REGION_SEMANTIC, tracer_id=TRACE_INFERENCE)
                if region.link(_a, _b, weight=0.6, rel_type=_rel,
                               tracer_id=TRACE_INFERENCE):
                    _wrote += 1
            except Exception:
                continue
        self.stats["distilled_claims"] = self.stats.get("distilled_claims", 0) + _wrote
        print(f"[{self.ACTOR_NAME}] Distilled {_wrote} TYPED claims "
              f"from '{prompt[:40]}'", flush=True)

    def _distill_legacy(self, model_output: str, prompt: str):
        """The pre-2026-08-26 body, PRESERVED as the fallback path.

        Untyped co-occurrence binding. Kept verbatim so that installing the typed path can
        never be worse than the behaviour it replaced: if the cortex region is unreachable
        for any reason, she still learns exactly what she learned before.
        """
        words = model_output.split()
        concepts = [w.strip(".,!?;:'\"()[]{}") for w in words if len(w) > 2]
        concepts = list(set(concepts))[:20]
        if len(concepts) >= 2:
            self.cortex_bind(
                concepts,
                context=f"distillation:{prompt[:50]}",
                modality="lex",
            )
            print(f"[{self.ACTOR_NAME}] Distilled {len(concepts)} concepts "
                  f"(UNTYPED fallback)", flush=True)

    def _extract_typed_claims(self, text: str, prompt: str = ""):
        """text -> [(subject, rel_type, object)] using her own REL_* constants.

        Two sources, deliberately ordered. ASSOCIATION LISTS first: a list a human wrote AS a
        list is the highest-yield, lowest-noise structure there is -- 112 of 145 good claims in
        the encyclopedia trial came from them. Then sentence patterns.

        The PROMPT is the subject anchor. Association lists name no subject; in a file the
        subject came from the filename, but a model answer has none. The QUESTION SHE ASKED is
        the subject ("what is grief?" -> grief), so every claim attaches to the very concept
        whose absence triggered the consult.

        Keys are HEADS, not clauses -- a key must be something ANOTHER sentence could
        independently arrive at, or the node is unreachable (the blob-card failure
        sandbox/nodes_edges_ingest/proto_ingest.py was built to demonstrate).
        """
        import re as _re
        from infrastructure.manifold_memory import (REL_CAUSAL, REL_SEMANTIC, REL_IS_A,
                                                    REL_PART_OF, REL_FEELS_LIKE,
                                                    REL_CAUSED_BY, REL_CONTRASTS,
                                                    REL_SYNONYM)
        _STOP = {"the", "a", "an", "of", "to", "in", "is", "are", "and", "or", "it", "its",
                 "that", "this", "for", "with", "by", "from", "on", "at", "as", "not", "but",
                 "all", "other", "which", "when", "while", "than", "into", "their", "them",
                 "be", "been", "was", "were"}
        _CUT = _STOP | {"who", "whose", "where", "because", "about", "between", "so", "if"}
        _DROP = {"most", "more", "less", "very", "quite", "highly", "often", "frequently",
                 "commonly", "typically", "generally", "longest", "shortest", "first",
                 "primary", "dominant", "technically", "simply", "always", "never", "also"}
        _TRAIL = {"visible", "seen", "known", "called", "used", "made", "cool", "warm",
                  "bright", "dark", "deep", "pure", "strong", "soft"}
        _KEEPING = {"feeling", "meaning", "being", "longing", "yearning", "mourning",
                    "grounding", "healing", "wanting", "thinking", "learning"}

        def _head(ph, maxw=3):
            t = _re.sub(r"\([^)]*\)", " ", (ph or "").lower())
            t = _re.sub(r"[^\w\s\-]", " ", t).split()
            while t and (t[0] in _STOP or t[0] in _DROP):
                t.pop(0)
            out = []
            for tok in t:
                if tok in _CUT and out:
                    break
                if tok in _CUT or (tok in _DROP and not out):
                    continue
                if out and tok.endswith("ing") and tok not in _KEEPING:
                    break
                out.append(tok)
                if len(out) >= maxw:
                    break
            while out and (out[-1] in _STOP or out[-1] in _TRAIL):
                out.pop()
            return " ".join(out).strip()

        _PATS = [
            (REL_IS_A, r"\b([\w\- ]{3,40}?)\s+(?:is|are)\s+(?:a|an)\s+([\w\- ]{3,40})"),
            (REL_PART_OF, r"\b([\w\- ]{3,40}?)\s+(?:is|are)\s+part\s+of\s+([\w\- ]{3,40})"),
            (REL_PART_OF, r"\b([\w\- ]{3,40}?)\s+(?:contains?|includes?)\s+([\w\- ]{3,40})"),
            (REL_CAUSAL, r"\b([\w\- ]{3,40}?)\s+(?:causes?|produces?|creates?|triggers?|leads? to|results? in)\s+([\w\- ]{3,40})"),
            (REL_CAUSED_BY, r"\b([\w\- ]{3,40}?)\s+(?:is|are)\s+caused by\s+([\w\- ]{3,40})"),
            (REL_CONTRASTS, r"\b([\w\- ]{3,40}?)\s+(?:contrasts? with|opposes?|is the opposite of)\s+([\w\- ]{3,40})"),
            (REL_SYNONYM, r"\b([\w\- ]{3,40}?)\s+(?:also known as|also called|is another word for)\s+([\w\- ]{3,40})"),
            (REL_FEELS_LIKE, r"\b([\w\- ]{3,40}?)\s+(?:feels? like|is experienced as)\s+([\w\- ]{3,40})"),
            (REL_SEMANTIC, r"\b([\w\- ]{3,40}?)\s+(?:means?|refers? to|is defined as|represents?)\s+([\w\- ]{3,40})"),
        ]
        _LISTREL = {"associations": REL_FEELS_LIKE, "emotional associations": REL_FEELS_LIKE,
                    "feelings": REL_FEELS_LIKE, "examples": REL_IS_A, "types": REL_IS_A,
                    "parts": REL_PART_OF, "opposites": REL_CONTRASTS,
                    "synonyms": REL_SYNONYM}
        facts, seen = [], set()

        def _add(a, rel, b):
            a, b = _head(a), _head(b)
            if not a or not b or a == b or len(a) < 3 or len(b) < 3:
                return
            k = (a, rel, b)
            if k in seen or len(facts) >= 60:
                return
            seen.add(k)
            facts.append(k)

        _q = _re.sub(r"^\s*(?:what|who|how|why|when|where)\s+(?:is|are|does|do)\s+", "",
                     (prompt or "").strip(), flags=_re.I)
        _anchor = _head(_q, maxw=2)
        for _m in _re.finditer(r"^\s*\*{0,2}([\w\- ]{3,34}?)\*{0,2}\s*:\s*([^\n]{10,300})$",
                               text or "", _re.M):
            _rel = _LISTREL.get(_m.group(1).strip().lower())
            _subj = _anchor or _head(_m.group(1))
            if _rel is None or not _subj:
                continue
            for _piece in _re.split(r"[,;]", _m.group(2)):
                _add(_subj, _rel, _piece)
        for _para in _re.split(r"\n\s*\n", text or ""):
            for _s in _re.split(r"(?<=[.!?])\s+", _para):
                _s = _re.sub(r"\*\*|__|`", "", _s.strip())
                if not (15 <= len(_s) <= 260):
                    continue
                for _rel, _pat in _PATS:
                    _mm = _re.search(_pat, _s, _re.I)
                    if _mm:
                        _add(_mm.group(1), _rel, _mm.group(2))
                        break
        return facts

    # =========================================================================
    # STATUS
    # =========================================================================

    def status(self) -> Dict[str, Any]:
        """Get fairy status."""
        base_status = super().status() if hasattr(super(), 'status') else {}

        return {
            **base_status,
            "name": self.ACTOR_NAME,
            "engine": "cortex",
            "mode": self._current_mode,
            "dream_mode": self._dream_mode,
            "loop_running": self._loop_running,
            "thought_queue_size": len(self._thought_queue),
            "stats": self.stats.copy(),
            "somatic": {
                "arousal": self._current_somatic.arousal,
                "stress": self._current_somatic.stress,
                "valence": self._current_somatic.valence,
            },
            "cortex": {
                "reasoner_online": self._cortex_reasoner is not None,
                "priming_concepts": len(self._cortex_priming),
                "cache_size": len(self._cortex_cache),
                "hits": self.stats.get("cortex_hits", 0),
                "misses": self.stats.get("cortex_misses", 0),
                "queries": self.stats.get("cortex_queries", 0),
                "binds": self.stats.get("cortex_binds", 0),
            },
            "guild": {
                "guild_id": self.GUILD_ID,
                "guild_role": self.GUILD_ROLE,
                "guild_requests": self.stats.get("guild_requests", 0),
                "team_active": self._cognition_team is not None and self._team_enabled,
            },
        }


# =============================================================================
# FACTORY FUNCTION
# =============================================================================

def create_inference_fairy(fabric=None, collision_chamber=None, **kwargs) -> AkashicInferenceFairy:
    """Create and configure an AkashicInferenceFairy."""
    return AkashicInferenceFairy(
        fabric=fabric,
        collision_chamber=collision_chamber,
    )


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'ConsciousnessLoopConfig',
    'SomaticSnapshot',
    'AkashicInferenceFairy',
    'create_inference_fairy',
]
