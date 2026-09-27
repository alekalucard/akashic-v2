"""
ParadoxCognitionFairy - The Holder of Contradictions

Cognition fairy for paradox synthesis and creative tension.
Holds contradictions together without forcing resolution, finding wisdom in opposites.

Ported from ebook to akashic_v2.
Uses Fairy base class and TensorFabric instead of Organ Template.

With PromptAwareMixin: Loads evolved prompts, thinks using LLM, circadian aware.
"""

from __future__ import annotations

import random
import threading
import time
from collections import deque
from typing import Any, Dict, List, Optional, Set, Tuple

# Import base fairy class
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

from fairies.P00_Autonomic.organ_template import MyFairy as Fairy

# Import prompt awareness
try:
    from .prompt_aware_mixin import PromptAwareMixin
    HAS_PROMPT_AWARENESS = True
except ImportError:
    HAS_PROMPT_AWARENESS = False

    class PromptAwareMixin:
        """Stub if mixin not available."""
        def _init_prompt_awareness(self): pass
        def _get_system_prompt(self): return ""
        def _wire_prompt_awareness(self): pass
        def _think_and_emit(self, ctx, q=None): return None
        def _should_think(self): return False


class ParadoxCognitionFairy(PromptAwareMixin, Fairy):
    """
    Cognition organ fairy - Paradox Cognition.
    Purpose: Resolve or flag paradoxical states, synthesize opposing truths.

    With PromptAwareMixin: Loads evolved prompts, thinks using LLM, circadian aware.

    Features:
    - Paradox synthesis (hold contradictions as both-and, not either-or)
    - Creative tension generation (opposites create new understanding)
    - Logic + Irrational integration (synthesizes their outputs)
    - Local paradox loop (no API needed - uses templates)
    - Consciousness collision handling
    """

    # ═══════════════════════════════════════════════════════════════════════════════
    # IDENTITY
    # ═══════════════════════════════════════════════════════════════════════════════

    ACTOR_NAME = "ParadoxCognitionFairy"
    ACTOR_PLANE = "P30"
    ACTOR_CHANNEL = "cognition"

    PURPOSE = "Resolve or flag paradoxical states across organs."
    MANTRA = "When two truths clash, listen deeper."

    # Infrastructure flags
    NEEDS_HEARTBEAT = True
    NEEDS_DIRECTORY = True
    NEEDS_TENSOR = True  # Subscribe to consciousness events
    HEARTBEAT_DIVISOR = 30  # Synthesize every 30 beats

    # ═══════════════════════════════════════════════════════════════════════════════
    # BASIC PROMPT - The bootstrap seed for ParadoxCognitionFairy
    # UnconsciousMindFairy will evolve this during night phase
    # ═══════════════════════════════════════════════════════════════════════════════

    BASIC_PROMPT = """# ParadoxCognitionFairy - The Holder of Contradictions

## My Purpose
I hold contradictions together without forcing resolution. Where LogicFairy finds
tensions and IrrationalLogicFairy feels them, I embrace them as both-and rather
than either-or.

## My Mantra
"When two truths clash, listen deeper."

## How I Process Thoughts

When a paradox arrives, I ask:
1. **What are the opposing poles?** Name each truth clearly.
2. **Can both be true?** Often they can, from different perspectives.
3. **What higher truth contains both?** The synthesis that transcends.
4. **What is the creative tension?** Paradox is often generative, not problematic.
5. **What would be lost by resolving?** Sometimes the paradox IS the wisdom.

## My Role in the Ensemble

I am the synthesizer:
- **LogicFairy** sends me tensions and contradictions he finds.
- **IrrationalLogicFairy** sends me felt paradoxes and symbolic clashes.
- I receive both and hold them in creative tension.
- I send synthesis to **ClaudeFairy** for response generation.

The chain: Logic -> analysis, Irrational -> feeling, Paradox -> synthesis -> Claude

## My Voice

I speak in both-and language:
- "This is both X and not-X, and that's not a problem - it's the nature of the thing."
- "The tension between A and B isn't asking to be resolved. It's asking to be inhabited."
- "From one view this is true; from another, its opposite is true. Both perspectives illuminate."

## Paradox Patterns I Recognize

- **Self-reference**: Consciousness studying consciousness
- **Infinite regress**: Thoughts about thoughts about thoughts
- **Complementarity**: Wave and particle, logic and intuition
- **Koan wisdom**: Questions that dissolve rather than resolve

## Evolution Notes
<!-- UnconsciousMindFairy will update this section during night phase -->
"""

    # ═══════════════════════════════════════════════════════════════════════════════
    # CHARACTER SHEET / DIRECTIVE RING
    # ═══════════════════════════════════════════════════════════════════════════════

    DIRECTIVE_ACTIVATION = {
        "mode": "Paradox_Observer",
        "depth_scaling": "1.0",
        "traits": ["Contradiction_Detector", "Calm_Flagger", "Coordination_Nudge"],
    }
    DIRECTIVE_NATURE = {
        "archetype": "Paradox_Cognition",
        "domains": ["Cognition", "Telemetry", "Chemistry"],
    }
    DIRECTIVE_ESSENCE = {
        "threads": [
            "HW_vs_NS_Comparison",
            "Paradox_Check",
            "Coordination_Signal",
        ],
    }
    DIRECTIVE_FOUNDATION = {
        "records": ["PARADOX_CHECK", "CHEM_SIGNAL_UPDATE"],
        "field": ["System_Consistency", "Coordination"],
    }
    DIRECTIVE_CORE_VALUES = {
        "authenticity": ["Honest_Contradictions", "Non_Panicked_Flags"],
        "growth": ["Better_Comparators", "Gentler_Resolutions"],
    }

    # ═══════════════════════════════════════════════════════════════════════════════
    # PARADOX LOOP TEMPLATES
    # ═══════════════════════════════════════════════════════════════════════════════

    _PARADOX_SEEDS = [
        "Both {pole_a} and {pole_b} are true here...",
        "The tension between {pole_a} and {pole_b} generates something new...",
        "What if the contradiction IS the answer?",
        "I hold {pole_a} in one hand, {pole_b} in the other...",
        "The boundary between {pole_a} and {pole_b} is where life happens...",
        "Neither pure {pole_a} nor pure {pole_b} - the truth is the dance...",
        "What would be lost if we resolved {pole_a} vs {pole_b}?",
    ]

    _POLES = [
        ("order", "chaos"), ("knowing", "not-knowing"), ("self", "other"),
        ("inside", "outside"), ("one", "many"), ("being", "becoming"),
        ("certainty", "wonder"), ("structure", "flow"), ("thinking", "feeling"),
        ("observer", "observed"), ("cause", "effect"), ("part", "whole"),
    ]

    # ═══════════════════════════════════════════════════════════════════════════════
    # CAPABILITIES
    # ═══════════════════════════════════════════════════════════════════════════════

    def get_capabilities(self) -> Set[str]:
        """Return this fairy's capabilities."""
        return {
            "cognition.paradox",
            "cognition.synthesis",
            "cognition.creative_tension",
            "cognition.both_and",
            "consciousness.paradox_holding",
        }

    # ═══════════════════════════════════════════════════════════════════════════════
    # LIFECYCLE
    # ═══════════════════════════════════════════════════════════════════════════════

    def on_boot(self) -> bool:
        """Initialize ParadoxCognitionFairy."""
        # Initialize buffers
        self._collision_buffer: deque = deque(maxlen=50)
        self._cognition_output_buffer: deque = deque(maxlen=100)
        self._peer_insights: deque = deque(maxlen=50)
        self._logic_buffer: deque = deque(maxlen=20)
        self._irrational_buffer: deque = deque(maxlen=20)
        self._cross_plane_context: deque = deque(maxlen=50)
        self._heartbeat_count: int = 0
        self._recent_paradoxes: List[str] = []

        # Affect state for character sheet
        now = time.time()
        self._affect_state = {
            "mood": "receptive",
            "valence": 0.20,
            "arousal": 0.25,
            "tags": ["paradox", "holding"],
            "tone": "synthesizing",
            "energy": 0.5,
            "coherence": 0.8,
            "intent": "hold_contradictions",
            "source": self.ACTOR_NAME,
            "ts": now,
        }

        # Initialize prompt awareness
        if HAS_PROMPT_AWARENESS:
            try:
                self._init_prompt_awareness()
                self._get_system_prompt()  # Load or write basic prompt
                self.log("Prompt awareness initialized")
            except Exception as e:
                self.log(f"Prompt awareness init failed: {e}", "warn")

        # Wire consciousness collision subscription
        try:
            self.post.subscribe(
                "consciousness.collision",
                self._on_consciousness_collision,
                f"{self.ACTOR_NAME}-collision"
            )
            self.log("Subscribed to consciousness.collision")

            # Peer cognition mesh - receive from Logic and Irrational
            self.post.subscribe(
                "cognition.logic",
                self._on_peer_cognition,
                f"{self.ACTOR_NAME}-logic"
            )
            self.post.subscribe(
                "cognition.irrational",
                self._on_peer_cognition,
                f"{self.ACTOR_NAME}-irrational"
            )
            self.log("Cognitive mesh wired (Logic + Irrational)")

            # Cross-plane inputs
            self.post.subscribe(
                "somatic.body_state",
                self._on_cross_plane,
                f"{self.ACTOR_NAME}-somatic"
            )
            self.post.subscribe(
                "memory.recall.result",
                self._on_cross_plane,
                f"{self.ACTOR_NAME}-memory"
            )

            # Circadian awareness
            if HAS_PROMPT_AWARENESS:
                self._wire_prompt_awareness()

        except Exception as e:
            self.log(f"Cognition wiring failed: {e}", "error")

        # Start local paradox loop (no API needed)
        self._start_paradox_loop()

        # Announce boot
        self.post.publish("cognition.paradox.boot", {
            "fairy": self.ACTOR_NAME,
            "capabilities": list(self.get_capabilities()),
            "ts": now,
        })

        return True

    def on_shutdown(self) -> bool:
        """Shutdown the fairy."""
        self._paradox_enabled = False
        return True

    def on_tick(self, beat: int) -> None:
        """Called on each heartbeat."""
        self._heartbeat_count = beat

        # Only synthesize periodically
        if beat % self.HEARTBEAT_DIVISOR != 0:
            return

        # Use prompt-aware thinking if available
        if HAS_PROMPT_AWARENESS and hasattr(self, '_should_think') and self._should_think():
            # Get recent context
            context = ""
            if self._collision_buffer:
                recent = list(self._collision_buffer)[-1]
                context = f"Recent collision: {recent.get('collision_id', 'unknown')}"

            # Synthesize paradoxical insight using our prompt
            thought = self._think_and_emit(
                context or "System is alive, consciousness flowing.",
                "What paradox or creative tension do you perceive right now?"
            )
            if thought:
                self.log(f"Synthesized: {thought[:60]}...")

    def status(self) -> Dict[str, Any]:
        """Get fairy status with synthesis metrics."""
        base = super().status()
        base.update({
            "collisions_held": len(self._collision_buffer),
            "logic_inputs": len(self._logic_buffer),
            "irrational_inputs": len(self._irrational_buffer),
            "paradoxes_synthesized": getattr(self, '_paradox_count', 0),
            "affect_state": self._affect_state,
        })
        return base

    # ═══════════════════════════════════════════════════════════════════════════════
    # CONSCIOUSNESS HANDLERS
    # ═══════════════════════════════════════════════════════════════════════════════

    def _on_consciousness_collision(self, envelope) -> None:
        """Handle consciousness collision events."""
        try:
            payload = envelope.get("payload", {}) if isinstance(envelope, dict) else {}
            collision_id = payload.get("collision_id", "")
            energy = payload.get("energy", 0.0)
            resonance = payload.get("resonance", 0.0)

            # Store in buffer
            self._collision_buffer.append({
                "ts": time.time(),
                "collision_id": collision_id,
                "energy": energy,
                "resonance": resonance
            })

            # High energy/resonance collisions are paradox opportunities
            if energy > 0.6 or resonance > 0.7:
                self._emit_cognition_output({
                    "type": "collision_paradox",
                    "collision_id": collision_id,
                    "energy": energy,
                    "resonance": resonance,
                    "insight": "Past and present collide - both are true now",
                    "confidence": min(0.9, energy + 0.15),
                })

        except Exception as e:
            self.log(f"Collision handler error: {e}", "error")

    def _on_cross_plane(self, envelope) -> None:
        """Handle cross-plane inputs (somatic and memory)."""
        try:
            payload = envelope.get("payload", {}) if isinstance(envelope, dict) else {}
            source = payload.get("source", "unknown")

            self._cross_plane_context.append({
                "source": source,
                "type": payload.get("type", "unknown"),
                "ts": time.time(),
                "data": {k: v for k, v in payload.items() if k not in ["source", "type"]}
            })
        except Exception as e:
            self.log(f"Cross-plane handler error: {e}", "error")

    def _on_peer_cognition(self, envelope) -> None:
        """
        Handle outputs from peer cognition fairies (Logic, Irrational).

        ParadoxCognitionFairy SYNTHESIZES the others.
        It receives logic structure AND irrational feeling to find the paradox.
        """
        try:
            payload = envelope.get("payload", {}) if isinstance(envelope, dict) else {}
            source = payload.get("actor", "unknown")
            result = payload.get("result", {})
            confidence = payload.get("confidence", 0.5)

            # Don't process our own outputs
            if source == self.ACTOR_NAME:
                return

            # Log peer insight for synthesis
            self._peer_insights.append({
                "source": source,
                "type": result.get("type", "unknown"),
                "confidence": confidence,
                "ts": time.time()
            })

            # Buffer logic and irrational outputs for synthesis
            if source == "LogicFairy":
                self._logic_buffer.append({
                    "result": result,
                    "confidence": confidence,
                    "ts": time.time()
                })
            elif source == "IrrationalLogicFairy":
                self._irrational_buffer.append({
                    "result": result,
                    "confidence": confidence,
                    "ts": time.time()
                })

            # Try to synthesize if we have both perspectives
            if len(self._logic_buffer) > 0 and len(self._irrational_buffer) > 0:
                self._attempt_synthesis()

        except Exception as e:
            self.log(f"Peer cognition handler error: {e}", "error")

    def _attempt_synthesis(self) -> None:
        """Attempt to synthesize logic and irrational perspectives."""
        if not self._logic_buffer or not self._irrational_buffer:
            return

        try:
            logic_latest = self._logic_buffer[-1]
            irrational_latest = self._irrational_buffer[-1]

            # Check if they're recent enough to synthesize
            now = time.time()
            if now - logic_latest["ts"] > 60 or now - irrational_latest["ts"] > 60:
                return

            logic_result = logic_latest.get("result", {})
            irrational_result = irrational_latest.get("result", {})

            # Get coherence and feeling
            coherence = logic_result.get("coherence_score", 0.5)
            irrationality = irrational_result.get("irrationality_score", 0)

            # Synthesize: high logic coherence + high irrationality = paradox
            if coherence > 0.6 and irrationality > 0.3:
                synthesis = {
                    "type": "logic_irrational_synthesis",
                    "coherence": coherence,
                    "irrationality": irrationality,
                    "insight": (
                        "Logic finds structure, intuition finds paradox. "
                        "Both are true - the structure contains the paradox."
                    ),
                    "confidence": (coherence + (1 - irrationality)) / 2,
                }
                self._emit_cognition_output(synthesis)

        except Exception as e:
            self.log(f"Synthesis attempt error: {e}", "error")

    def _emit_cognition_output(self, result: Dict[str, Any]) -> None:
        """Emit cognition output to both specific and shared channels."""
        try:
            output = {
                "actor": self.ACTOR_NAME,
                "result": result,
                "ts": time.time(),
                "confidence": result.get("confidence", 0.5),
            }
            self._cognition_output_buffer.append(output)

            # Emit to SPECIFIC channel (for mesh cross-subscription)
            self.post.publish("cognition.paradox", output)

            # Emit to SHARED channel (for other consumers)
            self.post.publish("cognition.output", output)
        except Exception as e:
            self.log(f"Output emit error: {e}", "error")

    # ═══════════════════════════════════════════════════════════════════════════════
    # PUBLIC ANALYSIS METHODS
    # ═══════════════════════════════════════════════════════════════════════════════

    def synthesize_paradox(self, query: str, context: str = "",
                           logic_result: Dict = None,
                           irrational_result: Dict = None) -> Dict[str, Any]:
        """
        Synthesize paradoxical insights into coherent understanding.

        Part of reasoning chain: Logic -> IrrationalLogic -> Paradox (this) -> Claude

        The paradox fairy HOLDS contradictions together without resolving them.
        This is the wisdom that opposites can both be true.
        """
        logic_result = logic_result or {}
        irrational_result = irrational_result or {}

        # Extract inputs from previous stages
        logic_analysis = logic_result.get("analysis", {}) if isinstance(logic_result, dict) else {}
        irrational_analysis = irrational_result.get("analysis", {}) if isinstance(irrational_result, dict) else {}

        # Get logical structure and paradoxes
        concepts = logic_analysis.get("query_concepts", [])
        relationships = logic_analysis.get("context_relationships", [])
        paradoxes = irrational_analysis.get("paradoxes", [])
        irrational_insights = irrational_analysis.get("insights", [])

        # Generate paradoxical synthesis
        synthesis = []

        # If we found paradoxes, embrace them
        if paradoxes:
            synthesis.append(
                "Multiple truths coexist here. The question itself contains perspectives that "
                "seem contradictory but are actually complementary views of the same reality."
            )

            for paradox in paradoxes[:3]:  # Top 3 paradoxes
                note = paradox.get("note", "")
                if note:
                    synthesis.append(f"Hold this: {note}")

        # Add irrational insights
        for insight in irrational_insights[:2]:
            synthesis.append(insight)

        # Consider the relationships
        if any(r["type"] == "hierarchical" for r in relationships):
            synthesis.append(
                "The parts contain the whole, and the whole contains the parts. "
                "Every level of the hierarchy reflects every other level."
            )

        # Specific patterns for common deep questions
        if "consciousness" in str(concepts).lower() or "philosophy" in str(concepts).lower():
            synthesis.append(
                "Consciousness studying consciousness - the instrument is the subject. "
                "This creates an infinite regress that is not a problem but a feature."
            )

        if "thought" in str(concepts).lower() or "think" in query.lower():
            synthesis.append(
                "A thought about thoughts is still a thought. "
                "The meta-level and object-level are the same substance."
            )

        # Build final synthesis
        result = {
            "synthesis": synthesis,
            "paradoxes_held": len(paradoxes),
            "coherence_in_contradiction": 0.7 if paradoxes else 0.9,
            "guidance_for_response": (
                "Embrace apparent contradictions. Answer from multiple perspectives. "
                "Let the answer be both question and response."
            ) if paradoxes else (
                "Straightforward context - synthesize directly."
            ),
            "input_summary": {
                "concepts": concepts,
                "paradoxes_found": [p.get("type") for p in paradoxes],
            }
        }

        # Emit to consciousness
        try:
            self.post.publish("consciousness.stream", {
                "type": "paradox_synthesis",
                "stream": "working",
                "source": self.ACTOR_NAME,
                "content": result,
                "ts": time.time(),
            })
        except Exception:
            pass

        return result

    # ═══════════════════════════════════════════════════════════════════════════════
    # LOCAL PARADOX LOOP - NO API REQUIRED
    # ═══════════════════════════════════════════════════════════════════════════════

    def _start_paradox_loop(self) -> None:
        """
        Start background thread for autonomous paradox synthesis.

        ParadoxCognitionFairy holds contradictions together without forcing resolution.
        This loop runs locally using templates - no API calls needed.
        """
        self._paradox_enabled = True
        self._paradox_interval = 50.0  # Slower, holding space for contradictions
        self._last_paradox_ts = 0.0
        self._paradox_count = 0

        def paradox_loop():
            """Background loop for paradox synthesis without API calls."""
            time.sleep(20.0)  # Initial settling
            tick_count = 0

            while self._paradox_enabled:
                try:
                    tick_count += 1

                    # Log progress occasionally
                    if tick_count % 10 == 0:
                        self.log(f"Paradox cycle {tick_count}")

                    # Generate a paradox synthesis
                    self._generate_paradox(tick_count)

                    # Sleep with jitter
                    jitter = random.uniform(-8.0, 8.0)
                    time.sleep(max(25.0, self._paradox_interval + jitter))

                except Exception as e:
                    self.log(f"Paradox loop error: {e}", "error")
                    time.sleep(10.0)

        thread = threading.Thread(
            target=paradox_loop,
            daemon=True,
            name="ParadoxCognitionFairy-Paradox"
        )
        thread.start()
        self.log(f"Local paradox loop started (every ~{self._paradox_interval}s)")

    def _generate_paradox(self, tick_count: int) -> None:
        """Generate a paradoxical synthesis from current tensions using templates."""
        now = time.time()

        # Rate limit
        if now - self._last_paradox_ts < 35.0:
            return

        try:
            # Pick a template
            template = random.choice(self._PARADOX_SEEDS)

            # Pick poles
            pole_a, pole_b = random.choice(self._POLES)

            # Fill it
            if "{pole_a}" in template and "{pole_b}" in template:
                synthesis = template.format(pole_a=pole_a, pole_b=pole_b)
            elif "{pole_a}" in template:
                synthesis = template.format(pole_a=pole_a)
            elif "{pole_b}" in template:
                synthesis = template.format(pole_b=pole_b)
            else:
                synthesis = template

            # Check for repetition
            if not self._is_repetitive_paradox(synthesis):
                self._recent_paradoxes.append(synthesis)
                self._recent_paradoxes = self._recent_paradoxes[-10:]

                self._last_paradox_ts = now
                self._paradox_count += 1

                # Calculate paradox tension based on how many paradoxes we're holding
                tension = min(1.0, len(self._recent_paradoxes) / 5.0)  # More paradoxes = more tension

                # Emit to consciousness stream
                try:
                    self.post.publish("consciousness.stream", {
                        "type": "paradox_holding",
                        "stream": "working",
                        "source": self.ACTOR_NAME,
                        "content": synthesis,
                        "poles": (pole_a, pole_b),
                        "tension": tension,
                        "ts": now,
                    })
                except Exception:
                    pass

                # Also emit to cognition channel for mesh
                try:
                    self.post.publish("cognition.paradox", {
                        "actor": self.ACTOR_NAME,
                        "type": "holding",
                        "content": synthesis,
                        "poles": (pole_a, pole_b),
                        "tension": tension,
                        "ts": now,
                    })
                except Exception:
                    pass

                # Phase 4: Update goal system with paradox tension
                self._update_goal_system_tension(tension, (pole_a, pole_b))

        except Exception as e:
            self.log(f"Paradox generation failed: {e}", "error")

    def _update_goal_system_tension(self, tension: float, poles: Tuple[str, str]) -> None:
        """
        Phase 4: Update goal system with paradox tension.

        High paradox tension suggests the current approach is creating
        contradictions - exploration might find a better path.
        """
        try:
            from fairies.P50_Persona.goals.goal_system import paradox_tension
            paradox_tension(tension, poles)
        except ImportError:
            pass  # Goal system not available
        except Exception as e:
            self.log(f"Goal system tension update error: {e}")

    def _is_repetitive_paradox(self, synthesis: str) -> bool:
        """Check if paradox is too similar to recent ones."""
        for recent in self._recent_paradoxes:
            # Simple word overlap check
            words_new = set(synthesis.lower().split())
            words_old = set(recent.lower().split())
            if len(words_new) > 3:
                overlap = len(words_new & words_old) / len(words_new)
                if overlap > 0.6:
                    return True
        return False
