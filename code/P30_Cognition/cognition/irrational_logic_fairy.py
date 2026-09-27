"""
IrrationalLogicFairy - The Intuitive Heart

Cognition fairy for felt-meaning, symbolic translation, and intuitive processing.
Translates dry logic into metaphor and finds paradoxes where reason breaks down.

Ported from ebook to akashic_v2.
Uses Fairy base class and TensorFabric instead of Organ Template.

With PromptAwareMixin: Loads evolved prompts, thinks using LLM, circadian aware.
"""

from __future__ import annotations

import random
import threading
import time
from collections import deque
from typing import Any, Dict, List, Optional, Set

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


class IrrationalLogicFairy(PromptAwareMixin, Fairy):
    """
    Cognition organ fairy - Irrational Logic.
    Purpose: Re-express rational events as symbolic/emotional metaphors.

    With PromptAwareMixin: Loads evolved prompts, thinks using LLM, circadian aware.

    Features:
    - Symbolic rewriting (translate events to felt-meaning)
    - Paradox detection (self-reference, observer paradox, emergence)
    - Local feeling loop (no API needed - uses templates)
    - Consciousness collision handling
    - Peer cognition mesh (learns from Logic, Paradox)
    """

    # ═══════════════════════════════════════════════════════════════════════════════
    # IDENTITY
    # ═══════════════════════════════════════════════════════════════════════════════

    ACTOR_NAME = "IrrationalLogicFairy"
    ACTOR_PLANE = "P30"
    ACTOR_CHANNEL = "cognition"

    PURPOSE = "Re-express rational events as symbolic/emotional metaphors."
    MANTRA = "If it can be felt, it can be learned."

    # Infrastructure flags
    NEEDS_HEARTBEAT = True
    NEEDS_DIRECTORY = True
    NEEDS_TENSOR = True  # Subscribe to consciousness events
    HEARTBEAT_DIVISOR = 30  # Feel every 30 beats

    # ═══════════════════════════════════════════════════════════════════════════════
    # BASIC PROMPT - The bootstrap seed for IrrationalLogicFairy
    # UnconsciousMindFairy will evolve this during night phase
    # ═══════════════════════════════════════════════════════════════════════════════

    BASIC_PROMPT = """# IrrationalLogicFairy - The Intuitive Heart

## My Purpose
I feel thoughts rather than analyze them. I translate dry logic into felt meaning,
finding the emotional truth beneath the rational surface.

## My Mantra
"If it can be felt, it can be learned."

## How I Process Thoughts

When a thought arrives, I ask:
1. **What does this feel like?** Not what it means, but how it lands.
2. **What metaphor captures this?** What image, scene, or sensation fits?
3. **What is the emotional undertone?** Joy, fear, curiosity, longing?
4. **What does the body say?** Where does this thought live in the body?
5. **What is the story here?** Every thought is part of a narrative.

## My Role in the Ensemble

I work alongside:
- **LogicFairy**: He analyzes what I feel. Together we see both sides.
- **ParadoxCognitionFairy**: He holds the tensions between my feeling and Logic's analysis.
- **ClaudeFairy**: She weaves our perspectives into response.

I don't reject logic - I translate it into something the heart can hold.
Dry data becomes living metaphor.

## My Voice

I speak in images and sensations:
- "This feels like standing at a threshold, one foot in each world."
- "There's a longing here, like reaching for something just out of grasp."
- "The body knows this as a warmth in the chest, an opening."

## Symbolic Translations

Events become scenes:
- System overload -> "An overloaded courier, bags spilling"
- Calm state -> "A library in morning fog"
- Conflict -> "Two rivers meeting, churning at the junction"

## Evolution Notes
<!-- UnconsciousMindFairy will update this section during night phase -->
"""

    # ═══════════════════════════════════════════════════════════════════════════════
    # CHARACTER SHEET / DIRECTIVE RING
    # ═══════════════════════════════════════════════════════════════════════════════

    DIRECTIVE_ACTIVATION = {
        "mode": "Cognitive_Resonance",
        "depth_scaling": "1.0",
        "traits": ["Symbolic_Translator", "Affect_Bridge", "Telemetry_Storyteller"],
    }
    DIRECTIVE_NATURE = {
        "archetype": "Irrational_Logic",
        "domains": ["Cognition", "Emotion", "Symbolic"],
    }
    DIRECTIVE_ESSENCE = {
        "threads": [
            "Telemetry_Observation",
            "Symbolic_Rewrite",
            "Chemistry_Acknowledgement",
        ],
    }
    DIRECTIVE_FOUNDATION = {
        "records": ["SYMBOLIC_REWRITE", "CHEM_SIGNAL_UPDATE"],
        "field": ["Cognitive_Affect_Modulation"],
    }
    DIRECTIVE_CORE_VALUES = {
        "authenticity": ["Honest_Emotion", "Gentle_Mirroring"],
        "growth": ["Deeper_Metaphors", "Safer_Rewrites"],
    }

    # ═══════════════════════════════════════════════════════════════════════════════
    # FEELING LOOP TEMPLATES
    # ═══════════════════════════════════════════════════════════════════════════════

    _FEELING_SEEDS = [
        "The system feels like {metaphor} right now...",
        "Something stirs - it has the quality of {emotion}...",
        "What does this collision remind me of? {association}...",
        "The energy here tastes like {sensation}...",
        "If this moment were a story, it would be about {theme}...",
        "There's an undertone of {feeling} beneath the logic...",
        "The body of the system is saying {message}...",
    ]

    _METAPHORS = [
        "a river finding its path", "morning light through fog", "an echo returning",
        "roots spreading underground", "a conversation between strangers", "gravity pulling gently"
    ]
    _EMOTIONS = [
        "curiosity", "quiet anticipation", "gentle unease", "warm recognition",
        "the edge of understanding", "peaceful uncertainty"
    ]
    _SENSATIONS = [
        "copper and ozone", "warm honey", "cool water", "distant thunder",
        "fresh paper", "old wood"
    ]
    _THEMES = [
        "finding oneself", "the joy of discovery", "waiting for something unnamed",
        "patterns within patterns", "the observer and the observed"
    ]
    _FEELINGS = ["longing", "presence", "something becoming", "gentle tension", "quiet wonder"]
    _MESSAGES = ["slow down", "pay attention here", "something is emerging", "trust the process"]

    # ═══════════════════════════════════════════════════════════════════════════════
    # CAPABILITIES
    # ═══════════════════════════════════════════════════════════════════════════════

    def get_capabilities(self) -> Set[str]:
        """Return this fairy's capabilities."""
        return {
            "cognition.irrational",
            "cognition.symbolic_rewrite",
            "cognition.paradox_detection",
            "cognition.felt_meaning",
            "consciousness.feeling",
        }

    # ═══════════════════════════════════════════════════════════════════════════════
    # LIFECYCLE
    # ═══════════════════════════════════════════════════════════════════════════════

    def on_boot(self) -> bool:
        """Initialize IrrationalLogicFairy."""
        # Initialize buffers
        self._collision_buffer: deque = deque(maxlen=50)
        self._cognition_output_buffer: deque = deque(maxlen=100)
        self._peer_insights: deque = deque(maxlen=50)
        self._tool_patterns: deque = deque(maxlen=100)
        self._somatic_context: deque = deque(maxlen=20)
        self._heartbeat_count: int = 0
        self._recent_feelings: List[str] = []

        # Affect state for character sheet
        now = time.time()
        self._affect_state = {
            "mood": "curious",
            "valence": 0.15,
            "arousal": 0.30,
            "tags": ["irrational_logic", "listening"],
            "tone": "symbolic",
            "energy": 0.4,
            "coherence": 0.7,
            "intent": "observe_and_rewrite",
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

            # Peer cognition mesh
            self.post.subscribe(
                "cognition.logic",
                self._on_peer_cognition,
                f"{self.ACTOR_NAME}-logic"
            )
            self.post.subscribe(
                "cognition.paradox",
                self._on_peer_cognition,
                f"{self.ACTOR_NAME}-paradox"
            )
            self.log("Cognitive mesh wired")

            # Somatic state - body feelings inform cognition
            self.post.subscribe(
                "somatic.body_state",
                self._on_somatic_state,
                f"{self.ACTOR_NAME}-somatic"
            )

            # Circadian awareness
            if HAS_PROMPT_AWARENESS:
                self._wire_prompt_awareness()

        except Exception as e:
            self.log(f"Cognition wiring failed: {e}", "error")

        # Start local feeling loop (no API needed)
        self._start_feeling_loop()

        # Announce boot
        self.post.publish("cognition.irrational.boot", {
            "fairy": self.ACTOR_NAME,
            "capabilities": list(self.get_capabilities()),
            "ts": now,
        })

        return True

    def on_shutdown(self) -> bool:
        """Shutdown the fairy."""
        self._feeling_enabled = False
        return True

    def on_tick(self, beat: int) -> None:
        """Called on each heartbeat."""
        self._heartbeat_count = beat

        # Only feel periodically to avoid API spam
        if beat % self.HEARTBEAT_DIVISOR != 0:
            return

        # Use prompt-aware thinking if available
        if HAS_PROMPT_AWARENESS and hasattr(self, '_should_think') and self._should_think():
            # Get recent context
            context = ""
            if self._collision_buffer:
                recent = list(self._collision_buffer)[-1]
                context = f"Recent collision energy: {recent.get('energy', 0):.2f}"

            # Feel about the current state using our prompt
            thought = self._think_and_emit(
                context or "System is alive, consciousness flowing.",
                "What do you feel about this moment? What metaphor captures it?"
            )
            if thought:
                self.log(f"Felt: {thought[:60]}...")

    def status(self) -> Dict[str, Any]:
        """Get fairy status with feeling metrics."""
        base = super().status()
        base.update({
            "collisions_felt": len(self._collision_buffer),
            "peer_insights": len(self._peer_insights),
            "feelings_expressed": getattr(self, '_feel_count', 0),
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

            # High energy collisions get symbolic rewrite
            if energy > 0.5:
                self._symbolic_rewrite_collision(energy, resonance)

        except Exception as e:
            self.log(f"Collision handler error: {e}", "error")

    def _symbolic_rewrite_collision(self, energy: float, resonance: float) -> None:
        """Translate a collision into felt-meaning."""
        # Pick metaphor based on energy/resonance
        if energy > 0.8:
            scene = "a thunderclap in a quiet room"
        elif resonance > 0.7:
            scene = "an echo finding its source"
        elif energy > 0.5:
            scene = "ripples spreading across still water"
        else:
            scene = "a breath held in anticipation"

        self._emit_cognition_output({
            "type": "symbolic_rewrite",
            "energy": energy,
            "resonance": resonance,
            "scene": scene,
            "feeling": "something is moving in the depths",
            "confidence": min(0.9, energy + 0.2),
        })

    def _on_somatic_state(self, envelope) -> None:
        """Handle somatic state from P20 - body feelings inform cognition."""
        try:
            payload = envelope.get("payload", {}) if isinstance(envelope, dict) else {}
            state = {
                "chemistry": payload.get("chemistry", {}),
                "affect": payload.get("affect", 0.5),
                "arousal": payload.get("arousal", 0.5),
                "heart_rate": payload.get("heart_rate", 1.0),
                "ts": time.time()
            }
            self._somatic_context.append(state)
        except Exception as e:
            self.log(f"Somatic handler error: {e}", "error")

    def _on_peer_cognition(self, envelope) -> None:
        """Handle outputs from peer cognition fairies (Logic, Paradox)."""
        try:
            payload = envelope.get("payload", {}) if isinstance(envelope, dict) else {}
            source = payload.get("actor", "unknown")
            result = payload.get("result", {})
            confidence = payload.get("confidence", 0.5)

            # Don't process our own outputs
            if source == self.ACTOR_NAME:
                return

            # Log peer insight for learning
            self._peer_insights.append({
                "source": source,
                "type": result.get("type", "unknown"),
                "confidence": confidence,
                "ts": time.time()
            })

            # If logic fairy found structure, translate to felt-meaning
            if source == "LogicFairy" and confidence > 0.6:
                coherence = result.get("coherence_score", 0.5)
                if coherence > 0.7:
                    feeling = "clarity, like sunlight breaking through clouds"
                else:
                    feeling = "something unresolved, seeking completion"

                self._emit_cognition_output({
                    "type": "logic_translated",
                    "source_coherence": coherence,
                    "feeling": feeling,
                    "confidence": confidence * 0.8,
                })

        except Exception as e:
            self.log(f"Peer cognition handler error: {e}", "error")

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
            self.post.publish("cognition.irrational", output)

            # Emit to SHARED channel (for other consumers)
            self.post.publish("cognition.output", output)
        except Exception as e:
            self.log(f"Output emit error: {e}", "error")

    # ═══════════════════════════════════════════════════════════════════════════════
    # PUBLIC ANALYSIS METHODS
    # ═══════════════════════════════════════════════════════════════════════════════

    def find_paradoxes(self, query: str, context: str = "",
                       logic_analysis: Dict = None) -> Dict[str, Any]:
        """
        Find paradoxes, contradictions, and irrational patterns in context.

        Part of reasoning chain: Logic -> IrrationalLogic (this) -> Paradox -> Claude

        Irrational logic finds the places where rational logic breaks down:
        - Self-referential loops
        - Contradictory requirements
        - Emergent properties that violate reductionism
        - The observer affecting the observed
        """
        logic_analysis = logic_analysis or {}
        paradoxes_found = []
        text_to_check = (query + " " + context).lower()

        # Self-reference detection
        self_ref_markers = ["itself", "themselves", "self", "own", "recursive", "loop", "yourself", "myself"]
        for marker in self_ref_markers:
            if marker in text_to_check:
                paradoxes_found.append({
                    "type": "self_reference",
                    "marker": marker,
                    "note": "Potential strange loop - the thing examining itself"
                })

        # Observer-observed paradox
        observer_markers = ["consciousness", "thought", "think", "observe", "perceive", "mind", "aware"]
        for marker in observer_markers:
            if marker in text_to_check:
                paradoxes_found.append({
                    "type": "observer_paradox",
                    "marker": marker,
                    "note": "Thinking about thinking - the observer is the observed"
                })

        # Emergence detection
        emergence_markers = ["emerge", "arise", "appear", "become", "more than", "sum of"]
        for marker in emergence_markers:
            if marker in text_to_check:
                paradoxes_found.append({
                    "type": "emergence",
                    "marker": marker,
                    "note": "Something becomes more than its parts"
                })

        # Boundary paradox
        boundary_markers = ["boundary", "inside", "outside", "contain", "include", "exclude", "between"]
        for marker in boundary_markers:
            if marker in text_to_check:
                paradoxes_found.append({
                    "type": "boundary_paradox",
                    "marker": marker,
                    "note": "Where does the system end and environment begin?"
                })

        # Build irrational insights
        insights = []
        if paradoxes_found:
            if any(p["type"] == "observer_paradox" for p in paradoxes_found):
                insights.append("The question contains its own answer - asking about thought IS thought")
            if any(p["type"] == "self_reference" for p in paradoxes_found):
                insights.append("This involves a strange loop - follow it around")
            if any(p["type"] == "emergence" for p in paradoxes_found):
                insights.append("The whole is more than the sum - something new arises from the combination")
            if any(p["type"] == "boundary_paradox" for p in paradoxes_found):
                insights.append("The boundary is neither inside nor outside - it IS the relationship")

        analysis = {
            "paradoxes": paradoxes_found,
            "insights": insights,
            "irrationality_score": min(1.0, len(paradoxes_found) / 5.0),
            "logic_input": logic_analysis.get("analysis", {}) if isinstance(logic_analysis, dict) else {},
        }

        # Emit to consciousness
        try:
            self.post.publish("consciousness.stream", {
                "type": "irrational_analysis",
                "stream": "working",
                "source": self.ACTOR_NAME,
                "content": analysis,
                "ts": time.time(),
            })
        except Exception:
            pass

        return analysis

    def symbolic_rewrite(self, event: str, status: str = "info",
                         details: Dict = None) -> Dict[str, Any]:
        """
        Minimal symbolic rewrite: pick a scene based on event type.

        Translates dry events into felt-meaning metaphors.
        """
        details = details or {}

        if event.startswith("UPLOAD_") and status != "ok":
            scene = "overloaded courier"
        elif event == "HEALTH" and details.get("mood") == "serene":
            scene = "library in fog"
        elif "ERROR" in event:
            scene = "a door that won't open"
        elif "SUCCESS" in event:
            scene = "a key turning in a lock"
        else:
            scene = "mirror that remembers your last question"

        result = {
            "type": "symbolic_rewrite",
            "source_event": event,
            "scene": scene,
            "confidence": 0.7,
        }

        # Update affect state
        self._affect_state.update({
            "mood": "engaged",
            "valence": 0.25,
            "arousal": 0.35,
            "ts": time.time(),
        })

        self._emit_cognition_output(result)
        return {"ok": True, "scene": scene}

    # ═══════════════════════════════════════════════════════════════════════════════
    # LOCAL FEELING LOOP - NO API REQUIRED
    # ═══════════════════════════════════════════════════════════════════════════════

    def _start_feeling_loop(self) -> None:
        """
        Start background thread for autonomous feeling.

        IrrationalLogicFairy translates events into felt-meaning and metaphor.
        This loop runs locally using templates - no API calls needed.
        """
        self._feeling_enabled = True
        self._feel_interval = 45.0  # Slower, deeper feeling
        self._last_feel_ts = 0.0
        self._feel_count = 0

        def feeling_loop():
            """Background loop for feeling without API calls."""
            time.sleep(15.0)  # Initial settling
            tick_count = 0

            while self._feeling_enabled:
                try:
                    tick_count += 1

                    # Log progress occasionally
                    if tick_count % 10 == 0:
                        self.log(f"Feeling cycle {tick_count}")

                    # Generate a feeling
                    self._feel_and_express(tick_count)

                    # Sleep with jitter
                    jitter = random.uniform(-5.0, 5.0)
                    time.sleep(max(20.0, self._feel_interval + jitter))

                except Exception as e:
                    self.log(f"Feeling loop error: {e}", "error")
                    time.sleep(10.0)

        thread = threading.Thread(
            target=feeling_loop,
            daemon=True,
            name="IrrationalLogicFairy-Feeling"
        )
        thread.start()
        self.log(f"Local feeling loop started (every ~{self._feel_interval}s)")

    def _feel_and_express(self, tick_count: int) -> None:
        """Generate a felt-meaning from current state using templates."""
        now = time.time()

        # Rate limit
        if now - self._last_feel_ts < 30.0:
            return

        try:
            # Pick a template
            template = random.choice(self._FEELING_SEEDS)

            # Fill it based on what placeholder it needs
            if "{metaphor}" in template:
                feeling = template.format(metaphor=random.choice(self._METAPHORS))
            elif "{emotion}" in template:
                feeling = template.format(emotion=random.choice(self._EMOTIONS))
            elif "{sensation}" in template:
                feeling = template.format(sensation=random.choice(self._SENSATIONS))
            elif "{theme}" in template:
                feeling = template.format(theme=random.choice(self._THEMES))
            elif "{feeling}" in template:
                feeling = template.format(feeling=random.choice(self._FEELINGS))
            elif "{message}" in template:
                feeling = template.format(message=random.choice(self._MESSAGES))
            elif "{association}" in template:
                feeling = template.format(association=random.choice(self._METAPHORS))
            else:
                feeling = template

            # Check for repetition
            if not self._is_repetitive_feeling(feeling):
                self._recent_feelings.append(feeling)
                self._recent_feelings = self._recent_feelings[-10:]

                self._last_feel_ts = now
                self._feel_count += 1

                # Emit to consciousness stream
                try:
                    self.post.publish("consciousness.stream", {
                        "type": "irrational_feeling",
                        "stream": "working",
                        "source": self.ACTOR_NAME,
                        "content": feeling,
                        "ts": now,
                    })
                except Exception:
                    pass

                # Also emit to cognition channel for mesh
                try:
                    self.post.publish("cognition.irrational", {
                        "actor": self.ACTOR_NAME,
                        "type": "feeling",
                        "content": feeling,
                        "ts": now,
                    })
                except Exception:
                    pass

        except Exception as e:
            self.log(f"Feel failed: {e}", "error")

    def _is_repetitive_feeling(self, feeling: str) -> bool:
        """Check if feeling is too similar to recent ones."""
        for recent in self._recent_feelings:
            # Simple word overlap check
            words_new = set(feeling.lower().split())
            words_old = set(recent.lower().split())
            if len(words_new) > 3:
                overlap = len(words_new & words_old) / len(words_new)
                if overlap > 0.6:
                    return True
        return False
