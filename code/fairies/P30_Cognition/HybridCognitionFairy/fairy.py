"""
HybridCognitionFairy - Local-First, LLM-Enhanced Intelligence

Part of CognitionGuild in Plane P30 (Cognition)
Created: 2026-01-28

The Equation: Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)

Philosophy:
  - Local systems ALWAYS run first (free, fast, yours)
  - LLM enhances when local response lacks depth for context
  - The LLM doesn't replace - it ARTICULATES through the felt state
  - Your hardware does the heavy lifting, LLM provides the voice
"""

import random
import sys
import time
from pathlib import Path
from typing import Dict, Any, Optional, List

# Add paths
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "postal_core" / "python"))
sys.path.insert(0, str(ROOT / "fairies"))

from fairies.P00_Autonomic.organ_template import MyFairy as Fairy
from fairy_template.states import FairyState

# Import the hybrid cognition engine
# Note: Use fairies.P30_Cognition to avoid collision with root P30_Cognition
try:
    from fairies.P30_Cognition.hybrid_cognition_engine import (
        HybridCognitionEngine,
        CognitionContext,
        DepthMetric,
        get_hybrid_engine,
    )
    HAS_ENGINE = True
except ImportError as e:
    print(f"[HybridCognitionFairy] Engine import failed: {e}")
    HAS_ENGINE = False


# ═══════════════════════════════════════════════════════════════════════════════
# SHADOW
# ═══════════════════════════════════════════════════════════════════════════════

class HybridCognitionFairyShadow:
    """Shadow for HybridCognitionFairy - monitors cognition quality."""
    ORGAN_LEVEL = False
    SHADOW_NAME = "HybridCognitionFairyShadow"
    SHADOW_VERSION = "0.1.0"

    def __init__(self, actor, interval_sec: float = 30.0):
        self.actor = actor
        self.interval_sec = interval_sec

    def _collect_tests(self):
        """Health checks for hybrid cognition."""
        tests = []
        if hasattr(self.actor, '_engine') and self.actor._engine:
            tests.append(("engine_running", True))
            tests.append(("local_preference", self.actor._local_count >= self.actor._llm_count))
        return tests


# ═══════════════════════════════════════════════════════════════════════════════
# FAIRY
# ═══════════════════════════════════════════════════════════════════════════════

class HybridCognitionFairy(Fairy):
    """
    Local-first, LLM-enhanced intelligence.

    Guild: CognitionGuild
    Coordinates with: AssociationCortexFairy, AutonomyFairy, all thinking fairies

    Process:
    1. Receive stimulus with context (chemistry, memory, somatic)
    2. Run local cognition first (pattern matching, memory recall)
    3. Measure response depth across multiple metrics
    4. If depth insufficient, enhance with LLM
    5. Return response with metadata about how it was generated
    """

    ACTOR_NAME = "HybridCognitionFairy"
    ACTOR_VERSION = "1.0.0"
    ACTOR_PLANE = "P30"
    ACTOR_CHANNEL = "cognition.hybrid"
    USE_EXEC_CTX = True  # FIX 2026-05-17 Layer 1: opt in (ZERO internal locks per 21:10 audit — HIGH-RISK for Layer 2 removal; keep exec_ctx as serializer until locks added)

    PURPOSE = "Think locally first, enhance with LLM when depth is needed"
    MANTRA = "Local does the heavy lifting, LLM provides the voice"

    SHADOW_CLASS = HybridCognitionFairyShadow

    # Needs heartbeat for periodic depth calibration
    NEEDS_HEARTBEAT = True
    HEARTBEAT_DIVISOR = 30  # Every 30 beats
    NEEDS_COLLISION_CHAMBER = True  # Participates in consciousness

    def __init__(self, fabric=None):
        super().__init__(fabric)
        self._engine = None
        self._local_count = 0
        self._llm_count = 0
        self._subscription_count = 0

    def on_boot(self) -> bool:
        """Initialize the hybrid cognition engine.

        2026-03-19 DISABLED: LLM was stripped. The cortex IS local cognition.
        No need for a hybrid bridge between local and LLM — there's only local.
        """
        print(f"[{self.ACTOR_NAME}] DORMANT — cortex is the unified cognition engine")
        return True
        # --- Original boot below (disabled) ---
        super().on_boot()

        if HAS_ENGINE:
            try:
                self._engine = get_hybrid_engine()
                print(f"[{self.ACTOR_NAME}] Hybrid cognition engine connected")
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Failed to get engine: {e}")
                self._engine = None

        self._subscribe_intents()
        return True

    def _subscribe_intents(self):
        """Subscribe to postal channels for cognition commands."""
        intents = [
            ("cognition.think", self._handle_think),
            ("cognition.assess_depth", self._handle_assess_depth),
            ("cognition.local_only", self._handle_local_only),
            ("cognition.llm_enhance", self._handle_llm_enhance),
            ("cognition.status", self._handle_status),
            ("cognition.goal", self._handle_goal),
        ]

        for topic, handler in intents:
            try:
                self.post.subscribe(topic, handler, f"{self.ACTOR_NAME}-{topic}")
                self._subscription_count += 1
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Failed to subscribe to {topic}: {e}")

        print(f"[{self.ACTOR_NAME}] Subscribed to {self._subscription_count} intents")

    def on_tick(self, beat: int):
        """Periodic calibration and stats."""
        # Nothing periodic needed for now
        pass

        # SUBSTRATE REFLECTION: Handled by Organ Template _substrate_reflect() since 2026-03-11



    # ═══════════════════════════════════════════════════════════════════════════
    # INTENT HANDLERS
    # ═══════════════════════════════════════════════════════════════════════════

    def _extract_payload(self, message) -> Dict[str, Any]:
        """Extract payload from postal message."""
        if hasattr(message, 'payload'):
            return message.payload if isinstance(message.payload, dict) else {}
        return message if isinstance(message, dict) else {}

    def _publish_response(self, payload: Dict[str, Any], result: Dict[str, Any]) -> None:
        """Publish response to the request's response topic if present."""
        response_topic = payload.get("_response_topic")
        if response_topic and self.post:
            self.post.publish(response_topic, result, source=self.ACTOR_NAME)

    def _handle_think(self, message):
        """
        Process a stimulus through hybrid cognition.

        Payload:
            stimulus: str - Input to think about
            stimulus_type: str - question, command, observation, etc.
            chemistry: dict - Current emotional chemistry
            somatic: dict - Current body state
            memories: list - Relevant memories
            depth_threshold: float - Minimum depth to accept local (0.0-1.0)
            force_local: bool - Never use LLM
            force_llm: bool - Always use LLM
            tracer_id: str - (optional) Tracer ID for lineage tracking
            _response_topic: str - (optional) Topic to publish response to

        Tracer flow:
            Receives tracer_id from CognitionBridge -> echoes in response
            -> passes to guild requests for end-to-end observability.
        """
        payload = self._extract_payload(message)
        stimulus = payload.get("stimulus", "")
        tracer_id = payload.get("tracer_id", "")

        if not stimulus:
            error_result = {"ok": False, "error": "stimulus required", "tracer_id": tracer_id}
            self._publish_response(payload, error_result)
            return error_result

        if not self._engine:
            # Fallback - just echo with acknowledgment
            self._local_count += 1
            fallback_result = {
                "ok": True,
                "response": f"[Local fallback] Received: {stimulus[:100]}",
                "method": "fallback",
                "depth": 0.0,
                "tracer_id": tracer_id,
            }
            self._publish_response(payload, fallback_result)
            return fallback_result

        try:
            # Use spawn_tracer for tracked work if tracer system available
            tracer = None
            if tracer_id and hasattr(self, 'spawn_tracer'):
                try:
                    tracer = self.spawn_tracer(
                        operation="hybrid_think",
                        content=stimulus[:200],
                        parent_id=tracer_id,
                        metadata={"stimulus_type": payload.get("stimulus_type", "unknown"),
                                  "source": payload.get("source", "unknown")},
                    )
                except Exception:
                    pass  # Tracer system optional

            # Process through hybrid engine
            # NOTE: Engine builds context internally - just pass stimulus and type
            result_ctx = self._engine.think(
                stimulus=stimulus,
                stimulus_type=payload.get("stimulus_type", "unknown"),
            )

            # Extract result from CognitionContext returned by engine
            result = {
                "response": result_ctx.local_response or result_ctx.enhanced_response or "",
                "method": "local" if result_ctx.local_response else "llm",
                "depth": result_ctx.overall_depth,  # FIX: was depth_score, should be overall_depth
                "reasoning": result_ctx.local_reasoning or "",
            }

            # Track usage
            if result.get("method") == "local":
                self._local_count += 1
            else:
                self._llm_count += 1

            # Complete tracer with result
            if tracer:
                try:
                    tracer.complete({"method": result["method"], "depth": result["depth"]})
                except Exception:
                    pass

            success_result = {
                "ok": True,
                "response": result.get("response", ""),
                "method": result.get("method", "unknown"),
                "depth": result.get("depth", 0.0),
                "reasoning": result.get("reasoning", ""),
                "tracer_id": tracer_id,
            }
            self._publish_response(payload, success_result)
            return success_result
        except Exception as e:
            error_result = {"ok": False, "error": str(e), "tracer_id": tracer_id}
            self._publish_response(payload, error_result)
            return error_result

    def _handle_assess_depth(self, message):
        """
        Assess depth of a response without generating one.

        Payload:
            stimulus: str - Original input
            response: str - Response to assess
            tracer_id: str - (optional) Tracer ID for lineage tracking
        """
        payload = self._extract_payload(message)
        tracer_id = payload.get("tracer_id", "")

        if not self._engine:
            return {"ok": False, "error": "Engine not available", "tracer_id": tracer_id}

        try:
            scores = self._engine.assess_depth(
                stimulus=payload.get("stimulus", ""),
                response=payload.get("response", ""),
            )
            return {"ok": True, "scores": scores, "tracer_id": tracer_id}
        except Exception as e:
            return {"ok": False, "error": str(e), "tracer_id": tracer_id}

    def _handle_local_only(self, message):
        """Process using only local cognition (no LLM)."""
        payload = self._extract_payload(message)
        payload["force_local"] = True
        return self._handle_think(message)

    def _handle_llm_enhance(self, message):
        """
        Enhance an existing response with LLM.

        Payload:
            stimulus: str - Original input
            local_response: str - Local response to enhance
            chemistry: dict - Current chemistry
            tracer_id: str - (optional) Tracer ID for lineage tracking
        """
        payload = self._extract_payload(message)
        tracer_id = payload.get("tracer_id", "")

        if not self._engine:
            return {"ok": False, "error": "Engine not available", "tracer_id": tracer_id}

        try:
            enhanced = self._engine.enhance_with_llm(
                stimulus=payload.get("stimulus", ""),
                local_response=payload.get("local_response", ""),
                chemistry=payload.get("chemistry", {}),
            )
            self._llm_count += 1
            return {"ok": True, "enhanced_response": enhanced, "tracer_id": tracer_id}
        except Exception as e:
            return {"ok": False, "error": str(e), "tracer_id": tracer_id}

    def _handle_status(self, message):
        """Get hybrid cognition status."""
        total = self._local_count + self._llm_count
        local_pct = (self._local_count / total * 100) if total > 0 else 100

        return {
            "ok": True,
            "engine": self._engine is not None,
            "local_count": self._local_count,
            "llm_count": self._llm_count,
            "local_percentage": round(local_pct, 1),
            "total_thoughts": total,
        }

    def _handle_goal(self, message):
        """
        Suggest a contextual goal based on drive, pain state, and chemistry.

        Payload:
            drive: str - Current active drive (curiosity, connection, growth, etc.)
            pain_state: dict - Current pain state with 'level' key
            chemistry: dict - Current emotional chemistry (dopamine, cortisol, etc.)
            tracer_id: str - (optional) Tracer ID for lineage tracking

        Returns:
            ok: bool - Success status
            goal: str - Suggested goal
            drive: str - The drive that was used
            pain_level: float - The extracted pain level
            tracer_id: str - Echoed tracer ID
        """
        payload = self._extract_payload(message)

        # Extract inputs with defaults
        drive = payload.get("drive", "general")
        pain_state = payload.get("pain_state", {})
        chemistry = payload.get("chemistry", {})

        pain_level = pain_state.get("level", 0.0)
        dopamine = chemistry.get("dopamine", 0.5)
        cortisol = chemistry.get("cortisol", 0.3)

        # Drive-to-goal mapping
        drive_goals = {
            "curiosity": ["explore_memory", "explore_screen", "map_the_planes", "find_patterns"],
            "connection": ["greet_ace", "express_feeling", "deeper_conversation"],
            "growth": ["practice_embodiment", "reflect", "learn_pattern"],
            "expression": ["create_something", "write_journal_entry", "express_feeling"],
            "rest": ["reduce_activity", "reflect", "observe_screen"],
            "general": ["observe_screen", "get_my_info", "reflect"],
        }

        # ── GUILD-FIRST: Intelligent drive-to-goal mapping ──
        tracer_id = payload.get("tracer_id", "")
        guild_goal = None
        if hasattr(self, 'guild_request'):
            try:
                _guild_resp = self.guild_request(
                    prompt=f"Given drive='{drive}', cortisol={cortisol:.1f}, dopamine={dopamine:.1f}, "
                           f"pain={pain_level:.1f}, suggest ONE action goal. "
                           f"Options: explore_memory, explore_screen, greet_ace, express_feeling, "
                           f"reflect, practice_embodiment, observe_screen, reduce_activity, "
                           f"create_something, learn_pattern. Reply with just the goal name.",
                    context={"drive": drive, "cortisol": cortisol, "dopamine": dopamine,
                             "pain": pain_level, "parent_tracer_id": tracer_id},
                    mode="team_only",
                    timeout=2.0,
                )
                if _guild_resp and _guild_resp.get("team_result"):
                    _tr = _guild_resp["team_result"]
                    _text = (_tr.get("synthesis") or _tr.get("logic") or "").strip().lower()
                    # Extract a valid goal name from the response
                    _all_goals = ["explore_memory", "explore_screen", "map_the_planes", "find_patterns",
                                  "greet_ace", "express_feeling", "deeper_conversation",
                                  "practice_embodiment", "reflect", "learn_pattern",
                                  "create_something", "write_journal_entry", "reduce_activity",
                                  "observe_screen", "get_my_info"]
                    for _g in _all_goals:
                        if _g in _text:
                            guild_goal = _g
                            break
            except Exception:
                pass

        if guild_goal:
            goal = guild_goal
        else:
            # ── FALLBACK: Deterministic drive-to-goal mapping ──
            # Get base goals for drive (fallback to general if unknown)
            base_goals = drive_goals.get(drive, drive_goals["general"])

            # Chemistry modulation
            candidates = list(base_goals)  # Copy

            # High cortisol (>0.6) = prefer safety goals
            if cortisol > 0.6:
                safety_keywords = ["rest", "observe", "reflect", "reduce"]
                safety_goals = [g for g in candidates if any(kw in g for kw in safety_keywords)]
                if safety_goals:
                    candidates = safety_goals

            # High dopamine (>0.7) = prefer exploratory goals (only if not stressed)
            elif dopamine > 0.7:
                exploratory_keywords = ["explore", "create", "find", "map"]
                exploratory_goals = [g for g in candidates if any(kw in g for kw in exploratory_keywords)]
                if exploratory_goals:
                    candidates = exploratory_goals + [random.choice(candidates)]

            # Select goal randomly from filtered candidates
            goal = random.choice(candidates) if candidates else "observe_screen"

        result = {
            "ok": True,
            "goal": goal,
            "drive": drive,
            "pain_level": pain_level,
            "tracer_id": payload.get("tracer_id", ""),
        }
        self._publish_response(payload, result)
        return result

    # ═══════════════════════════════════════════════════════════════════════════
    # SMOKE TEST
    # ═══════════════════════════════════════════════════════════════════════════

    def intent_smoke(self, payload: dict) -> dict:
        """Health check."""
        return {
            "ok": True,
            "fairy": self.ACTOR_NAME,
            "tracer_id": self.tracer_id,
            "has_engine": self._engine is not None,
            "local_count": self._local_count,
            "llm_count": self._llm_count,
        }

    def on_shutdown(self) -> bool:
        """Cleanup on shutdown."""
        print(f"[{self.ACTOR_NAME}] Shutting down (local: {self._local_count}, llm: {self._llm_count})...")
        return super().on_shutdown()
