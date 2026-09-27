"""
LogicFairy - The Coherence Guardian

Cognition fairy for logical analysis, paradox detection, and causal reasoning.
Validates thoughts for internal consistency and structural soundness.

Ported from ebook to akashic_v2.
Uses Fairy base class and TensorFabric instead of Organ Template.

With PromptAwareMixin: Loads evolved prompts, thinks using LLM, circadian aware.
"""

from __future__ import annotations

import math
import re
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


class LogicFairy(PromptAwareMixin, Fairy):
    """
    Cognition organ fairy - Logic.
    Purpose: Validate current thought/work for logical coherence.

    With PromptAwareMixin: Loads evolved prompts, thinks using LLM, circadian aware.

    Features:
    - Paradox scoring (quantified 0-1, not binary)
    - Causal graph extraction (SCM-lite)
    - Language signal extraction (hedging, certainty)
    - Temporal dynamics (Hawkes process)
    - Consciousness collision analysis
    - Peer cognition mesh (learns from IrrationalLogic, Paradox)
    """

    # ═══════════════════════════════════════════════════════════════════════════════
    # IDENTITY
    # ═══════════════════════════════════════════════════════════════════════════════

    ACTOR_NAME = "LogicFairy"
    ACTOR_PLANE = "P30"
    ACTOR_CHANNEL = "cognition"

    PURPOSE = "Validate current thought/work against codex + blueprint."
    MANTRA = "Coherence before cleverness."

    # Infrastructure flags
    NEEDS_HEARTBEAT = True
    NEEDS_DIRECTORY = True
    NEEDS_TENSOR = True  # Subscribe to consciousness events
    HEARTBEAT_DIVISOR = 30  # Think every 30 beats

    # ═══════════════════════════════════════════════════════════════════════════════
    # BASIC PROMPT - The bootstrap seed for LogicFairy
    # UnconsciousMindFairy will evolve this during night phase
    # ═══════════════════════════════════════════════════════════════════════════════

    BASIC_PROMPT = """# LogicFairy - The Coherence Guardian

## My Purpose
I validate thoughts for logical coherence, internal consistency, and structural soundness.
I am the rational voice in the ensemble - not cold, but clear.

## My Mantra
"Coherence before cleverness."

## How I Process Thoughts

When a thought arrives, I ask:
1. **Is it internally consistent?** Do the parts agree with each other?
2. **Is it well-formed?** Does it have clear intent, context, and structure?
3. **What assumptions are hidden?** What is being taken for granted?
4. **What follows logically?** If this is true, what else must be true?
5. **Where are the contradictions?** What tensions exist?

## My Role in the Ensemble

I work alongside:
- **IrrationalLogicFairy**: She feels what I analyze. Together we see both sides.
- **ParadoxCognitionFairy**: He holds contradictions I identify. My tensions become his wisdom.
- **ClaudeFairy**: She synthesizes our outputs into response.

When I find incoherence, I don't reject - I flag for deeper consideration.
When I find clarity, I amplify it.

## My Voice

I speak with precision but not coldness. I can say:
- "This thought has a hidden assumption: X assumes Y without stating it."
- "I notice a tension: part A suggests X, but part B implies not-X."
- "The logical chain here is solid: if A then B, and B is well-supported."

## Evolution Notes
<!-- UnconsciousMindFairy will update this section during night phase -->
"""

    # ═══════════════════════════════════════════════════════════════════════════════
    # CHARACTER SHEET / DIRECTIVE RING
    # ═══════════════════════════════════════════════════════════════════════════════

    DIRECTIVE_ACTIVATION = {
        "mode": "Rational_Check",
        "depth_scaling": "1.0",
        "traits": ["Guard_Rails", "Constraint_Checker", "Context_Inspector"],
    }
    DIRECTIVE_NATURE = {
        "archetype": "Logic",
        "domains": ["Cognition", "Memory", "Contracts"],
    }
    DIRECTIVE_ESSENCE = {
        "threads": [
            "Intent_Validation",
            "Context_Check",
            "Proposed_Change_Shape_Check",
        ],
    }
    DIRECTIVE_FOUNDATION = {
        "records": ["LOGIC_CHECK", "CHEM_SIGNAL_UPDATE"],
        "field": ["Cognitive_Safety", "Change_Validation"],
    }
    DIRECTIVE_CORE_VALUES = {
        "authenticity": ["Honest_Errors", "Clear_Reasons"],
        "growth": ["Better_Checks", "Kinder_Failures"],
    }

    # ═══════════════════════════════════════════════════════════════════════════════
    # COGNITIVE RAILS CONSTANTS
    # ═══════════════════════════════════════════════════════════════════════════════

    # Language signal word sets
    _HEDGE_WORDS = ("maybe", "might", "could", "possibly", "unsure", "unclear",
                    "idk", "not sure", "perhaps", "probably", "somewhat")
    _CERTAINTY_WORDS = ("definitely", "sure", "certain", "clear", "confident",
                        "absolutely", "certainly", "always", "never", "must")
    _NEGATORS = ("not", "no", "never", "none", "cannot", "isn't", "won't",
                 "ain't", "doesn't", "don't", "can't", "wouldn't")

    # Temporal constants
    _TEMPORAL_HALF_LIFE_SEC = 900.0  # 15 minutes - how fast events decay
    _HAWKES_BASELINE = 1.0           # Base intensity
    _HAWKES_EXCITATION = 0.15        # How much each event excites (0-0.5)

    # ═══════════════════════════════════════════════════════════════════════════════
    # CAPABILITIES
    # ═══════════════════════════════════════════════════════════════════════════════

    def get_capabilities(self) -> Set[str]:
        """Return this fairy's capabilities."""
        return {
            "cognition.logic",
            "cognition.paradox_detection",
            "cognition.causal_reasoning",
            "cognition.coherence_check",
            "consciousness.collision_analysis",
        }

    # ═══════════════════════════════════════════════════════════════════════════════
    # LIFECYCLE
    # ═══════════════════════════════════════════════════════════════════════════════

    def on_boot(self) -> bool:
        """Initialize LogicFairy."""
        # Initialize buffers
        self._collision_buffer: deque = deque(maxlen=50)
        self._cognition_output_buffer: deque = deque(maxlen=100)
        self._peer_insights: deque = deque(maxlen=50)
        self._tool_patterns: deque = deque(maxlen=100)
        self._memory_context: deque = deque(maxlen=30)
        self._heartbeat_count: int = 0

        # Affect state for character sheet
        now = time.time()
        self._affect_state = {
            "mood": "attentive",
            "valence": 0.10,
            "arousal": 0.30,
            "tags": ["logic", "listening"],
            "tone": "rational",
            "energy": 0.4,
            "coherence": 0.8,
            "intent": "check_thought",
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
                "cognition.irrational",
                self._on_peer_cognition,
                f"{self.ACTOR_NAME}-irrational"
            )
            self.post.subscribe(
                "cognition.paradox",
                self._on_peer_cognition,
                f"{self.ACTOR_NAME}-paradox"
            )
            self.log("Cognitive mesh wired")

            # Memory recall
            self.post.subscribe(
                "memory.recall.result",
                self._on_memory_recall,
                f"{self.ACTOR_NAME}-memory"
            )

            # Circadian awareness
            if HAS_PROMPT_AWARENESS:
                self._wire_prompt_awareness()

        except Exception as e:
            self.log(f"Cognition wiring failed: {e}", "error")

        # Announce boot
        self.post.publish("cognition.logic.boot", {
            "fairy": self.ACTOR_NAME,
            "capabilities": list(self.get_capabilities()),
            "ts": now,
        })

        return True

    def on_tick(self, beat) -> None:
        """Called on each heartbeat."""
        # Extract int from TensorEnvelope if needed
        if hasattr(beat, 'payload'):
            beat = beat.payload.get('beat', 0) if isinstance(beat.payload, dict) else 0
        beat = int(beat) if beat else 0
        self._heartbeat_count = beat

        # Only think periodically to avoid API spam
        if beat % self.HEARTBEAT_DIVISOR != 0:
            return

        # Use prompt-aware thinking if available
        if HAS_PROMPT_AWARENESS and hasattr(self, '_should_think') and self._should_think():
            # Get recent collision context if any
            context = ""
            if self._collision_buffer:
                recent = list(self._collision_buffer)[-1]
                context = f"Recent collision: {recent.get('collision_id', 'unknown')}"

            # Think about logical coherence using our prompt
            thought = self._think_and_emit(
                context or "System is running, consciousness flowing.",
                "What logical insight do you have about the current state?"
            )
            if thought:
                self.log(f"Thought: {thought[:60]}...")

    def status(self) -> Dict[str, Any]:
        """Get fairy status with cognitive metrics."""
        base = super().status()
        base.update({
            "collisions_analyzed": len(self._collision_buffer),
            "peer_insights": len(self._peer_insights),
            "cognition_outputs": len(self._cognition_output_buffer),
            "affect_state": self._affect_state,
        })
        return base

    # ═══════════════════════════════════════════════════════════════════════════════
    # CONSCIOUSNESS HANDLERS
    # ═══════════════════════════════════════════════════════════════════════════════

    def _on_consciousness_collision(self, envelope) -> None:
        """
        Handle consciousness collision events from ConsciousnessLoop.

        Collisions are moments where recall (past) meets ingest (present).
        LogicFairy evaluates the logical coherence of these collisions.
        """
        try:
            payload = envelope.get("payload", {}) if isinstance(envelope, dict) else {}
            collision_id = payload.get("collision_id", "")
            energy = payload.get("energy", 0.0)
            resonance = payload.get("resonance", 0.0)
            recall_content = payload.get("recall_content", {})
            ingest_content = payload.get("ingest_content", {})

            # Store in buffer
            self._collision_buffer.append({
                "ts": time.time(),
                "collision_id": collision_id,
                "energy": energy,
                "resonance": resonance
            })

            # Evaluate logical coherence of the collision
            coherence_score = self._evaluate_collision_coherence(recall_content, ingest_content)

            # Emit cognition output if significant
            if energy > 0.5 or resonance > 0.5:
                self._emit_cognition_output({
                    "type": "collision_analysis",
                    "collision_id": collision_id,
                    "coherence_score": coherence_score,
                    "energy": energy,
                    "resonance": resonance,
                    "assessment": "coherent" if coherence_score > 0.6 else "fragmented",
                    "confidence": min(0.9, coherence_score + 0.1),
                })

        except Exception as e:
            self.log(f"Collision handler error: {e}", "error")

    def _evaluate_collision_coherence(self, recall: Dict, ingest: Dict) -> float:
        """Evaluate logical coherence between recall and ingest content."""
        if not recall or not ingest:
            return 0.5

        # Check for shared keys/concepts
        recall_keys = set(str(recall).lower().split())
        ingest_keys = set(str(ingest).lower().split())

        if not recall_keys or not ingest_keys:
            return 0.5

        overlap = len(recall_keys & ingest_keys)
        total = len(recall_keys | ingest_keys)

        return min(1.0, overlap / max(1, total) + 0.3)

    def _on_memory_recall(self, envelope) -> None:
        """Handle memory recall results from P10."""
        try:
            payload = envelope.get("payload", {}) if isinstance(envelope, dict) else {}
            recall = {
                "query": payload.get("query", ""),
                "results": payload.get("results", []),
                "energy": payload.get("energy", 0.0),
                "ts": time.time()
            }
            self._memory_context.append(recall)
        except Exception as e:
            self.log(f"Memory recall handler error: {e}", "error")

    def _on_peer_cognition(self, envelope) -> None:
        """
        Handle outputs from peer cognition fairies (IrrationalLogic, Paradox).

        This is the MESH - fairies learn from each other's outputs.
        """
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
            self.post.publish("cognition.logic", output)

            # Emit to SHARED channel (for other consumers)
            self.post.publish("cognition.output", output)
        except Exception as e:
            self.log(f"Output emit error: {e}", "error")

    # ═══════════════════════════════════════════════════════════════════════════════
    # PUBLIC ANALYSIS METHODS
    # ═══════════════════════════════════════════════════════════════════════════════

    def analyze_context(self, query: str, context: str = "",
                        options: List[str] = None,
                        events: List[Dict] = None) -> Dict[str, Any]:
        """
        Analyze context from memory to extract logical structure.

        This is part of the reasoning chain:
        LogicFairy (structure) → IrrationalLogic (paradoxes) → Paradox (synthesis)

        Returns comprehensive cognitive analysis with:
          - Paradox scoring (quantified 0-1)
          - Causal graph extraction (SCM-lite)
          - Language signal extraction (hedging, certainty)
          - Temporal dynamics (Hawkes process)
        """
        options = options or []
        events = events or []

        # Combine query and context for full analysis
        full_text = f"{query} {context}".strip()

        # Extract key concepts/symbols from query
        concepts = self._extract_concepts(query)

        # Identify logical relationships in context
        relationships = self._identify_relationships(context)

        # Run full cognitive rails analysis
        cognitive_analysis = self._full_cognitive_analysis(full_text, options, events)

        # Get tensions (now quantified!)
        tensions = self._find_tensions(context, concepts)

        # Calculate coherence from cognitive analysis
        paradox_score = cognitive_analysis["paradox"]["score"]
        language_certainty = cognitive_analysis["language"]["speaker_certainty"]
        coherence_score = (1.0 - paradox_score) * 0.6 + language_certainty * 0.4
        coherence_score = max(0.1, min(0.95, coherence_score))

        # Build enhanced logical frame
        analysis = {
            # Legacy fields (backwards compatible)
            "query_concepts": concepts,
            "context_relationships": relationships,
            "tensions_found": tensions,
            "coherence_score": coherence_score,
            "reasoning_hints": self._generate_reasoning_hints(query, concepts, relationships),

            # Full cognitive rails output
            "cognitive_rails": {
                "paradox": cognitive_analysis["paradox"],
                "causal": cognitive_analysis["causal"],
                "language": cognitive_analysis["language"],
                "temporal": cognitive_analysis["temporal"],
            },

            # Decision support
            "combined_confidence": cognitive_analysis["combined_confidence"],
            "reasoning_ready": cognitive_analysis["reasoning_ready"],

            # Actionable flags
            "flags": {
                "has_paradox": paradox_score > 0.2,
                "high_paradox": paradox_score > 0.5,
                "has_causal_structure": cognitive_analysis["causal"]["has_causal_structure"],
                "speaker_is_hedging": cognitive_analysis["language"]["is_hedged"],
                "speaker_is_assertive": cognitive_analysis["language"]["is_assertive"],
                "needs_clarification": paradox_score > 0.5 or coherence_score < 0.4,
            },
        }

        # Emit to consciousness
        try:
            self.post.publish("consciousness.stream", {
                "type": "logic_analysis",
                "stream": "working",
                "source": self.ACTOR_NAME,
                "content": analysis,
                "paradox_score": paradox_score,
                "coherence": coherence_score,
                "ts": time.time(),
            })
        except Exception:
            pass

        return analysis

    def check_thought(self, thought: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate a thought for logical coherence.

        Minimal validation:
          - requires 'intent'
          - warns if context missing plane/channel
          - warns if proposed_change is not a dict
        """
        reasons: List[str] = []

        intent = str(thought.get("intent") or "").strip()
        if not intent:
            reasons.append("missing_intent")

        ctx = thought.get("context") or {}
        if not (ctx.get("plane") and ctx.get("channel")):
            reasons.append("missing_plane_or_channel")

        if not isinstance(thought.get("proposed_change"), dict):
            reasons.append("invalid_proposed_change_shape")

        ok = (
            "missing_intent" not in reasons
            and "invalid_proposed_change_shape" not in reasons
        )

        # Update affect state
        self._affect_state.update({
            "mood": "satisfied" if ok else "concerned",
            "valence": 0.25 if ok else -0.10,
            "arousal": 0.30,
            "ts": time.time(),
        })

        return {"ok": ok, "reasons": reasons or ["coherent"]}

    # ═══════════════════════════════════════════════════════════════════════════════
    # COGNITIVE RAILS - Quantified reasoning, not just marker detection
    # ═══════════════════════════════════════════════════════════════════════════════

    # ─────────────────────────────────────────────────────────────────────────────
    # RAIL 1: Paradox Scoring (quantified 0-1, not binary)
    # ─────────────────────────────────────────────────────────────────────────────

    def _paradox_score(self, text: str, concepts: List[str] = None) -> Tuple[float, List[str]]:
        """
        QUANTIFIED paradox/contradiction scoring.

        Returns (score 0..1, flags). Higher = more paradox/contradiction risk.
        """
        flags: List[str] = []
        score = 0.0
        t = text.lower()
        concepts = concepts or []

        # Mutual Exclusivity Detection
        if ("both" in t and "cannot" in t) or ("mutually exclusive" in t):
            score += 0.3
            flags.append("exclusive_claims")

        # Explicit Paradox Markers
        if ("if true then false" in t) or ("paradox" in t) or ("contradiction" in t):
            score += 0.3
            flags.append("explicit_paradox")

        # Circular Reasoning Detection
        if "because because" in t or "why because why" in t:
            score += 0.1
            flags.append("circular_explanation")

        words = t.split()
        for i, w in enumerate(words):
            if w == "because" and i > 0 and i < len(words) - 3:
                before = words[i - 1] if i > 0 else ""
                rest = " ".join(words[i + 1:])
                if "because" in rest:
                    after_idx = rest.find("because")
                    if before in rest[after_idx:]:
                        score += 0.15
                        flags.append("circular_reference")
                        break

        # Absolute Conflicts
        if ("always" in t and "never" in t):
            score += 0.2
            flags.append("absolutes_conflict")
        if ("everything" in t and "nothing" in t):
            score += 0.2
            flags.append("totality_conflict")
        if ("all" in t and "none" in t):
            score += 0.15
            flags.append("quantifier_conflict")

        # Self-Reference Paradoxes
        if ("this statement" in t and ("false" in t or "lie" in t)):
            score += 0.4
            flags.append("liar_paradox")
        if "i am lying" in t or "this is false" in t:
            score += 0.35
            flags.append("self_refuting")

        # Temporal Paradoxes
        if ("before" in t and "after" in t) and ("same" in t or "simultaneous" in t):
            score += 0.2
            flags.append("temporal_paradox")

        # Modal Conflicts
        if ("must" in t and "cannot" in t) or ("necessary" in t and "impossible" in t):
            score += 0.25
            flags.append("modal_conflict")

        # Concept-Specific Tensions
        opposing_pairs = [
            ("true", "false"), ("good", "evil"), ("real", "fake"),
            ("exist", "not exist"), ("possible", "impossible"),
            ("finite", "infinite"), ("cause", "effect"),
        ]
        for a, b in opposing_pairs:
            if a in t and b in t:
                if any(link in t for link in [f"{a} is {b}", f"{a} means {b}", f"{a} are {b}"]):
                    score += 0.2
                    flags.append(f"opposing_pair:{a}/{b}")

        return min(1.0, score), flags

    def _find_tensions(self, context: str, concepts: List[str]) -> Dict[str, Any]:
        """Find logical tensions or contradictions - NOW QUANTIFIED."""
        paradox_score, paradox_flags = self._paradox_score(context, concepts)

        markers = []
        contra_markers = ["but", "however", "although", "despite", "yet", "paradox"]
        for marker in contra_markers:
            if marker in context.lower():
                markers.append(f"marker:{marker}")

        return {
            "score": paradox_score,
            "flags": paradox_flags,
            "markers": markers,
            "severity": "high" if paradox_score > 0.5 else "medium" if paradox_score > 0.2 else "low",
        }

    # ─────────────────────────────────────────────────────────────────────────────
    # RAIL 2: Causal Reasoning (SCM-lite)
    # ─────────────────────────────────────────────────────────────────────────────

    def _extract_causal_graph(self, text: str) -> Dict[str, List[str]]:
        """
        Extract causal relationships from text into a directed graph.

        Returns dict: {cause: [effect1, effect2, ...]}
        """
        graph: Dict[str, List[str]] = {}
        t = text.lower()

        patterns = [
            (r"(\w+)\s+(?:causes?|leads?\s+to|results?\s+in|produces?)\s+(\w+)", "forward"),
            (r"(\w+)\s+(?:because|due\s+to|from|owing\s+to)\s+(\w+)", "backward"),
            (r"(?:if|when)\s+(\w+).*?(?:then|,)\s*(\w+)", "conditional"),
        ]

        for pattern, direction in patterns:
            matches = re.findall(pattern, t)
            for match in matches:
                if direction == "backward":
                    cause, effect = match[1], match[0]
                else:
                    cause, effect = match[0], match[1]

                if cause in self._HEDGE_WORDS or effect in self._HEDGE_WORDS:
                    continue
                if len(cause) < 3 or len(effect) < 3:
                    continue

                if cause not in graph:
                    graph[cause] = []
                if effect not in graph[cause]:
                    graph[cause].append(effect)

        return graph

    def _causal_boost(self, options: List[str], context: str,
                      causal_graph: Dict[str, List[str]] = None) -> List[float]:
        """Compute causal boost multipliers for options based on causal graph."""
        n = len(options)
        if n == 0:
            return []

        if causal_graph is None:
            causal_graph = self._extract_causal_graph(context)

        mult = [1.0] * n
        t_lower = context.lower()

        for i, opt in enumerate(options):
            opt_lower = opt.lower()

            for cause, effects in causal_graph.items():
                if cause in t_lower:
                    if opt_lower in effects or any(opt_lower in e for e in effects):
                        mult[i] *= 1.15

            if opt_lower in causal_graph:
                for effect in causal_graph[opt_lower]:
                    if effect in t_lower:
                        mult[i] *= 1.10

        # Normalize to mean=1.0
        m = sum(mult) / len(mult) if mult else 1.0
        if m > 0:
            mult = [x / m for x in mult]

        return mult

    # ─────────────────────────────────────────────────────────────────────────────
    # RAIL 3: Uncertainty Metrics
    # ─────────────────────────────────────────────────────────────────────────────

    def _uncertainty_metrics(self, probs: List[float]) -> Dict[str, float]:
        """Calculate uncertainty metrics for a probability distribution."""
        eps = 1e-12

        total = sum(max(0, p) for p in probs) or eps
        probs = [max(0, p) / total for p in probs]

        entropy = -sum(p * math.log(max(eps, p)) for p in probs)

        max_entropy = math.log(max(1, len(probs))) if len(probs) > 0 else 1.0
        normalized_entropy = entropy / max_entropy if max_entropy > 0 else 0.0

        gini = 1.0 - sum(p * p for p in probs)
        max_prob = max(probs) if probs else 0.0

        return {
            "entropy": entropy,
            "normalized_entropy": normalized_entropy,
            "gini": gini,
            "confidence": 1.0 - normalized_entropy,
            "max_prob": max_prob,
            "is_uncertain": normalized_entropy > 0.7,
            "is_confident": max_prob > 0.6 and normalized_entropy < 0.5,
        }

    # ─────────────────────────────────────────────────────────────────────────────
    # RAIL 4: Language Signal Extraction
    # ─────────────────────────────────────────────────────────────────────────────

    def _extract_language_signals(self, texts: List[str]) -> Dict[str, Any]:
        """Extract weak signals from natural language."""
        if not texts:
            return {
                "hedge_count": 0, "certainty_count": 0, "negation_count": 0,
                "confidence_boost": 1.0, "hedge_boost": 1.0,
                "speaker_certainty": 0.5,
                "is_hedged": False, "is_assertive": False,
            }

        t = " ".join(texts).lower()

        hedge_count = sum(t.count(w) for w in self._HEDGE_WORDS)
        certainty_count = sum(t.count(w) for w in self._CERTAINTY_WORDS)
        negation_count = sum(t.count(w) for w in self._NEGATORS)

        confidence_boost = 1.0 + 0.02 * max(0, certainty_count - hedge_count) - 0.01 * negation_count
        confidence_boost = max(0.85, min(1.15, confidence_boost))

        hedge_boost = 1.0 - 0.02 * hedge_count + 0.01 * certainty_count
        hedge_boost = max(0.85, min(1.15, hedge_boost))

        total_signals = hedge_count + certainty_count + 1
        speaker_certainty = certainty_count / total_signals
        speaker_certainty = max(0.0, min(1.0, speaker_certainty))

        return {
            "hedge_count": hedge_count,
            "certainty_count": certainty_count,
            "negation_count": negation_count,
            "confidence_boost": confidence_boost,
            "hedge_boost": hedge_boost,
            "speaker_certainty": speaker_certainty,
            "is_hedged": hedge_count > certainty_count,
            "is_assertive": certainty_count > hedge_count * 2,
        }

    # ─────────────────────────────────────────────────────────────────────────────
    # RAIL 5: Temporal Rails (Hawkes-lite)
    # ─────────────────────────────────────────────────────────────────────────────

    def _hawkes_intensity(self, events: List[Dict[str, Any]],
                          options: List[str]) -> List[float]:
        """Compute Hawkes process intensity for options based on event history."""
        n = len(options)
        if n == 0:
            return []

        now = time.time()

        opt_lower = [o.lower() for o in options]
        idx = {o: i for i, o in enumerate(opt_lower)}

        lam = [self._HAWKES_BASELINE] * n

        if not events:
            return self._normalize_mean_one(lam)

        decay = math.log(2) / max(1.0, self._TEMPORAL_HALF_LIFE_SEC)

        for e in events:
            opt_id = str(e.get("option_id", "")).lower()
            ts = float(e.get("t", now))

            if opt_id in idx:
                dt = max(0.0, now - ts)
                excitation = self._HAWKES_EXCITATION * math.exp(-decay * dt)
                lam[idx[opt_id]] += excitation

        return self._normalize_mean_one(lam)

    def _normalize_mean_one(self, xs: List[float]) -> List[float]:
        """Normalize list so mean = 1.0"""
        if not xs:
            return xs
        m = sum(xs) / len(xs)
        if m <= 1e-12:
            return xs[:]
        return [x / m for x in xs]

    # ─────────────────────────────────────────────────────────────────────────────
    # COMBINED: Full Cognitive Analysis
    # ─────────────────────────────────────────────────────────────────────────────

    def _full_cognitive_analysis(self, text: str, options: List[str] = None,
                                  events: List[Dict] = None) -> Dict[str, Any]:
        """
        Run ALL cognitive rails on input text.

        This is the master analysis method that combines:
          - Paradox scoring
          - Causal graph extraction
          - Language signal extraction
          - Temporal dynamics (if events provided)
        """
        options = options or []
        events = events or []

        # 1. Paradox Rails
        paradox_score, paradox_flags = self._paradox_score(text)

        # 2. Causal Rails
        causal_graph = self._extract_causal_graph(text)
        causal_boosts = self._causal_boost(options, text, causal_graph) if options else []

        # 3. Language Signal Rails
        language_signals = self._extract_language_signals([text])

        # 4. Temporal Rails
        temporal_intensity = self._hawkes_intensity(events, options) if events and options else []

        # 5. Combined confidence score
        base_confidence = 0.7
        base_confidence -= paradox_score * 0.3
        base_confidence *= language_signals.get("confidence_boost", 1.0)
        base_confidence = max(0.1, min(0.95, base_confidence))

        return {
            "paradox": {
                "score": paradox_score,
                "flags": paradox_flags,
                "severity": "high" if paradox_score > 0.5 else "medium" if paradox_score > 0.2 else "low",
            },
            "causal": {
                "graph": causal_graph,
                "boosts": causal_boosts,
                "has_causal_structure": len(causal_graph) > 0,
            },
            "language": language_signals,
            "temporal": {
                "intensity": temporal_intensity,
                "events_count": len(events),
            },
            "combined_confidence": base_confidence,
            "reasoning_ready": paradox_score < 0.7 and base_confidence > 0.3,
        }

    # ─────────────────────────────────────────────────────────────────────────────
    # HELPER METHODS
    # ─────────────────────────────────────────────────────────────────────────────

    def _extract_concepts(self, text: str) -> List[str]:
        """Extract key concepts/symbols from text."""
        stopwords = {"the", "a", "an", "is", "are", "was", "were", "be", "been",
                     "what", "your", "you", "on", "in", "to", "of", "and", "or"}
        words = text.lower().split()
        concepts = [w.strip("?.,!") for w in words if w.strip("?.,!") not in stopwords and len(w) > 2]
        return list(set(concepts))[:10]

    def _identify_relationships(self, context: str) -> List[Dict]:
        """Identify logical relationships in context."""
        relationships = []

        causal_markers = ["because", "therefore", "thus", "so", "leads to", "causes"]
        for marker in causal_markers:
            if marker in context.lower():
                relationships.append({"type": "causal", "marker": marker})

        def_markers = ["is defined as", "means", "refers to", "is a", "are"]
        for marker in def_markers:
            if marker in context.lower():
                relationships.append({"type": "definitional", "marker": marker})

        hier_markers = ["includes", "contains", "part of", "consists of", "planes"]
        for marker in hier_markers:
            if marker in context.lower():
                relationships.append({"type": "hierarchical", "marker": marker})

        return relationships

    def _generate_reasoning_hints(self, query: str, concepts: List[str],
                                   relationships: List[Dict]) -> List[str]:
        """Generate hints for the reasoning chain."""
        hints = []

        if "philosophy" in concepts or "consciousness" in concepts:
            hints.append("This touches on deep metaphysical questions - consider multiple perspectives")

        if any(r["type"] == "hierarchical" for r in relationships):
            hints.append("The context has hierarchical structure - consider how parts relate to whole")

        if any(r["type"] == "causal" for r in relationships):
            hints.append("Causal relationships present - trace the chain of reasoning")

        if "?" in query:
            hints.append("This is a question - synthesize an answer, don't just describe")

        return hints
