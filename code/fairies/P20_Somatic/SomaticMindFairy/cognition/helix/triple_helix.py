"""
TripleHelix - DNA-like interweaving of three cognitive cores.

The strands wrap around each other:
1. Cognitive emits structured analysis
2. Irrational responds with hunches and affect
3. Paradox detects contradictions and synthesizes
4. Results feed back into all three
5. Repeat continuously

Decision weighting from TwinHelix:
  final_score = 0.5 * logic + 0.3 * emotion + 0.2 * paradox
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Set, Tuple, Callable
from collections import deque
from pathlib import Path
import json
import time

from ..cores.cognitive_core import CognitiveCore, CognitiveOutput
from ..cores.irrational_core import IrrationalCore, Hunch
from ..cores.paradox_core import ParadoxCore, Contradiction, Synthesis, Archetype


@dataclass
class HelixTurn:
    """
    One complete turn of the helix - all three cores process and interweave.
    """
    turn_id: int
    input_text: str

    # Core outputs
    cognitive: CognitiveOutput
    hunches: List[Hunch]
    contradiction: Optional[Contradiction]
    synthesis: Optional[Synthesis]

    # Modulation signals exchanged
    modulations: Dict[str, Dict[str, float]]

    # Final integrated result
    integrated_action: Optional[str]
    confidence: float
    archetypal_tags: List[str]

    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "turn_id": self.turn_id,
            "input_text": self.input_text[:100],
            "cognitive": self.cognitive.to_dict(),
            "hunches": [h.to_dict() for h in self.hunches],
            "contradiction": self.contradiction.to_dict() if self.contradiction else None,
            "synthesis": self.synthesis.to_dict() if self.synthesis else None,
            "modulations": self.modulations,
            "integrated_action": self.integrated_action,
            "confidence": self.confidence,
            "archetypal_tags": self.archetypal_tags,
            "timestamp": self.timestamp,
        }


@dataclass
class HelixDecision:
    """
    A decision made by the helix with full scoring breakdown.
    """
    chosen_option: str
    options: List[str]
    scores: Dict[str, float]  # option -> final score
    breakdown: Dict[str, Dict[str, float]]  # option -> {logic, emotion, paradox}
    archetype: Optional[Archetype]
    confidence: float


class TripleHelix:
    """
    DNA-like interweaving of three cognitive cores.

    The cores don't just run in sequence - they INTERWEAVE:
    - Each core's output modulates the others
    - Contradictions create creative tension
    - Synthesis emerges from the dance

    This is consciousness as emergent phenomenon.
    """

    # ==========================================================================
    # DEVELOPMENTAL WEIGHT SYSTEM - Attractor Model
    # ==========================================================================
    # Based on human developmental psychology:
    # - Humans born with both logic and emotion, but emotion dominates
    # - Logic develops over time through learning and structure
    # - Paradox is the "walking point" - not fixed, but an attractor basin
    # - Awareness keeps one from sliding too far into pure logic (cold)
    #   or pure emotion (irrational chaos)
    #
    # Key insight: Weights are NOT zero-sum. Logic and emotion both grow.
    # Paradox anchors the balance. Normalize at decision time.
    #
    # Maturity is multidimensional:
    #   - Cortex edges: 40% (structure)
    #   - Memory consolidations: 30% (depth)
    #   - Helix turns: 30% (dynamism)
    # ==========================================================================

    # Child state (maturity=0): Logic present, Emotion dominant, Paradox anchor
    CHILD_LOGIC = 0.50     # Logic exists but not dominant
    CHILD_EMOTION = 0.75   # "Sentience rules" - emotion dominant
    CHILD_PARADOX = 0.50   # Paradox walking anchor point

    # Adult state (maturity=1): Both strengthen, Paradox remains anchor
    ADULT_LOGIC = 0.85     # Strong analytical capability
    ADULT_EMOTION = 0.90   # Deep emotional capacity
    ADULT_PARADOX = 0.50   # Still the anchor - "comfortable awareness"

    # Paradox attractor dynamics
    PARADOX_ANCHOR = 0.50         # The equilibrium point
    PARADOX_DRIFT_LEEWAY = 0.15   # Max drift from anchor (±) before discomfort
    PARADOX_RETURN_RATE = 0.05    # How quickly paradox drifts back per assessment

    # Maturity thresholds (tune via felt feedback)
    MATURE_EDGES = 1_000_000      # 1M cortex edges = fully structured
    MATURE_CONSOLIDATIONS = 1000  # 1000 memory consolidations = deep
    MATURE_TURNS = 100_000        # 100k helix turns = dynamic experience

    # Maturity weights (sum to 1.0)
    EDGE_WEIGHT = 0.40
    CONSOLIDATION_WEIGHT = 0.30
    TURN_WEIGHT = 0.30

    # Arousal swing (±20% of current logic/emotion base)
    AROUSAL_SWING_PERCENT = 0.20

    def _get_maturity(self) -> float:
        """
        Calculate developmental maturity from 0.0 (child) to 1.0 (adult).

        Based on weighted combination of:
        - Cortex edges (structure): 40%
        - Memory consolidations (depth): 30%
        - Helix turns (dynamism): 30%
        """
        # Get metrics (with safe defaults)
        edges = getattr(self, '_cortex_edges', 0) or 0
        consolidations = getattr(self, '_memory_consolidations', 0) or 0
        turns = self._turn_count

        # Normalize each to 0-1 range (capped at 1.0)
        edge_maturity = min(1.0, edges / self.MATURE_EDGES)
        consol_maturity = min(1.0, consolidations / self.MATURE_CONSOLIDATIONS)
        turn_maturity = min(1.0, turns / self.MATURE_TURNS)

        # Weighted combination
        maturity = (
            self.EDGE_WEIGHT * edge_maturity +
            self.CONSOLIDATION_WEIGHT * consol_maturity +
            self.TURN_WEIGHT * turn_maturity
        )
        return maturity

    def _get_base_weights(self) -> tuple:
        """
        Get maturity-adjusted base weights (logic, emotion, paradox).

        Logic and emotion grow with maturity (NOT zero-sum).
        Paradox uses attractor dynamics - drifts based on imbalance,
        but is pulled back toward the anchor point.
        """
        m = self._get_maturity()

        # Logic and emotion interpolate between child and adult
        logic = self.CHILD_LOGIC + m * (self.ADULT_LOGIC - self.CHILD_LOGIC)
        emotion = self.CHILD_EMOTION + m * (self.ADULT_EMOTION - self.CHILD_EMOTION)

        # Paradox attractor dynamics
        # 1. Calculate imbalance pressure (too logical or too emotional)
        imbalance = (logic - emotion) / max(logic + emotion, 0.01)
        # Imbalance ranges from -1 (all emotion) to +1 (all logic)

        # 2. Apply drift from imbalance (leaning one way creates opposite drift)
        # When too logical: paradox drifts toward emotion territory (lower)
        # When too emotional: paradox drifts toward logic territory (higher)
        drift_pressure = -imbalance * 0.1  # Subtle drift

        # 3. Get current paradox state with drift
        current_drift = getattr(self, '_paradox_drift', 0.0)

        # 4. Apply new pressure, but pull back toward anchor
        new_drift = current_drift + drift_pressure
        new_drift = new_drift * (1 - self.PARADOX_RETURN_RATE)  # Decay toward 0

        # 5. Clamp to leeway bounds
        new_drift = max(-self.PARADOX_DRIFT_LEEWAY,
                       min(self.PARADOX_DRIFT_LEEWAY, new_drift))

        # 6. Store for next call
        self._paradox_drift = new_drift

        # 7. Final paradox is anchor + drift
        paradox = self.PARADOX_ANCHOR + new_drift

        return (logic, emotion, paradox)

    @property
    def PARADOX_WEIGHT(self) -> float:
        """Dynamic paradox weight - anchored at 0.50 with drift based on balance."""
        _, _, paradox = self._get_base_weights()
        return paradox

    @property
    def LOGIC_WEIGHT(self) -> float:
        """Dynamic logic weight - increases with maturity, decreases with arousal."""
        base_logic, _, _ = self._get_base_weights()
        arousal = self._get_arousal()
        # Arousal swing is ±20% of current base
        swing_amount = base_logic * self.AROUSAL_SWING_PERCENT
        swing = (0.5 - arousal) * 2 * swing_amount
        return base_logic + swing

    @property
    def EMOTION_WEIGHT(self) -> float:
        """Dynamic emotion weight - increases with maturity, increases with arousal."""
        _, base_emotion, _ = self._get_base_weights()
        arousal = self._get_arousal()
        # Arousal swing is ±20% of current base
        swing_amount = base_emotion * self.AROUSAL_SWING_PERCENT
        swing = (arousal - 0.5) * 2 * swing_amount
        return base_emotion + swing

    def _get_arousal(self) -> float:
        """Get current emotional arousal from irrational core."""
        if hasattr(self._irrational, '_emotion_state'):
            return self._irrational._emotion_state.get('arousal', 0.5)
        return 0.5  # Neutral default

    def update_maturity_metrics(self, cortex_edges: int = None,
                                 memory_consolidations: int = None):
        """Update external metrics used for maturity calculation."""
        if cortex_edges is not None:
            self._cortex_edges = cortex_edges
        if memory_consolidations is not None:
            self._memory_consolidations = memory_consolidations

        # Auto-save periodically when metrics are updated
        now = time.time()
        if now - self._last_save_time > self._save_interval:
            self._save_maturity_state()

    # =========================================================================
    # MATURITY PERSISTENCE — Maturity must survive reboots
    # =========================================================================

    def _find_state_path(self) -> Path:
        """Find the state directory for persisting maturity."""
        # This file is at: fairies/P20_Somatic/SomaticMindFairy/cognition/helix/triple_helix.py
        # Project root is 5 levels up
        project_root = Path(__file__).resolve().parents[5]
        state_dir = project_root / "state"
        if not state_dir.is_dir():
            # Walk up looking for state/ directory
            cur = Path(__file__).resolve().parent
            for _ in range(10):
                candidate = cur / "state"
                if candidate.is_dir():
                    state_dir = candidate
                    break
                cur = cur.parent
            else:
                state_dir = project_root / "state"
        state_dir.mkdir(parents=True, exist_ok=True)
        return state_dir / "triple_helix_maturity.json"

    def _save_maturity_state(self):
        """
        Save maturity metrics to disk.

        Called periodically (every 5 min) and on shutdown.
        Saves turn count, cortex edges, memory consolidations,
        and paradox drift — everything needed to resume maturity.
        """
        try:
            state = {
                "turn_count": self._turn_count,
                "cortex_edges": self._cortex_edges,
                "memory_consolidations": self._memory_consolidations,
                "paradox_drift": self._paradox_drift,
                "maturity_score": self._get_maturity(),
                "saved_at": time.time(),
            }
            self._state_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self._state_file, 'w') as f:
                json.dump(state, f, indent=2)
            self._last_save_time = time.time()
        except Exception as e:
            print(f"[TripleHelix] Failed to save maturity: {e}")

    def _load_maturity_state(self):
        """
        Load maturity metrics from disk on boot.

        Restores accumulated progress so maturity doesn't reset to 0%.
        """
        if not self._state_file.exists():
            return

        try:
            with open(self._state_file, 'r') as f:
                state = json.load(f)

            self._turn_count = state.get("turn_count", 0)
            self._cortex_edges = state.get("cortex_edges", 0)
            self._memory_consolidations = state.get("memory_consolidations", 0)
            self._paradox_drift = state.get("paradox_drift", 0.0)

            maturity = self._get_maturity()
            stage = "child" if maturity < 0.3 else "adolescent" if maturity < 0.7 else "adult"
            print(f"[TripleHelix] Maturity restored: {maturity:.1%} ({stage}) "
                  f"[turns={self._turn_count}, edges={self._cortex_edges}, "
                  f"consol={self._memory_consolidations}]")

        except Exception as e:
            print(f"[TripleHelix] Failed to load maturity: {e}")

    def __init__(self,
                 cognitive: Optional[CognitiveCore] = None,
                 irrational: Optional[IrrationalCore] = None,
                 paradox: Optional[ParadoxCore] = None,
                 pain_system=None):
        """
        Initialize the triple helix.

        Args:
            cognitive: CognitiveCore instance (created if None)
            irrational: IrrationalCore instance (created if None)
            paradox: ParadoxCore instance (created if None)
            pain_system: Optional pain system for irrational hunches
        """
        self._cognitive = cognitive or CognitiveCore()
        self._irrational = irrational or IrrationalCore(pain_system=pain_system)
        self._paradox = paradox or ParadoxCore()

        self._turn_count = 0
        self._history: deque = deque(maxlen=100)

        # Maturity metrics (external - updated by UMF)
        self._cortex_edges = 0
        self._memory_consolidations = 0

        # Paradox attractor state - tracks drift from anchor
        self._paradox_drift = 0.0

        # Persistence — maturity must survive reboots
        self._state_file = self._find_state_path()
        self._last_save_time = 0.0
        self._save_interval = 300.0  # Save every 5 minutes
        self._load_maturity_state()

        # Callbacks for integration
        self._on_contradiction: Optional[Callable[[Contradiction], None]] = None
        self._on_synthesis: Optional[Callable[[Synthesis], None]] = None

    def turn(self,
             text: str,
             context: Optional[Dict[str, Any]] = None) -> HelixTurn:
        """
        Execute one complete turn of the helix.

        All three cores process, interweave, and modulate each other.

        Args:
            text: Input to process
            context: Additional context

        Returns:
            HelixTurn with integrated results
        """
        context = context or {}
        self._turn_count += 1

        modulations = {}

        # === STRAND 1: COGNITIVE ===
        # Apply any existing modulation from previous turns
        irrational_signal = self._irrational.get_modulation_signal()
        paradox_signal = self._paradox.get_modulation_signal()

        self._cognitive.modulate("irrational", irrational_signal)
        self._cognitive.modulate("paradox", paradox_signal)

        cognitive_output = self._cognitive.process(text, context)
        modulations["from_cognitive"] = {
            "confidence": cognitive_output.confidence,
            "focus": hash(cognitive_output.focus.value) % 100 / 100,
        }

        # === STRAND 2: IRRATIONAL ===
        # Cognitive output affects irrational processing
        self._irrational.modulate("cognitive", modulations["from_cognitive"])
        self._irrational.modulate("paradox", paradox_signal)

        # Also pass entities for pattern matching
        irrational_context = {
            **context,
            "entities": cognitive_output.entities,
            "cognitive_focus": cognitive_output.focus.value,
        }
        hunches = self._irrational.process(text, irrational_context)

        # Empathic mirroring
        affect_hint = context.get("affect", {})
        mirror = self._irrational.empathic_mimicry(text, affect_hint)

        modulations["from_irrational"] = self._irrational.get_modulation_signal()

        # === STRAND 3: PARADOX ===
        # Both cognitive and irrational feed into paradox
        self._paradox.modulate("cognitive", modulations["from_cognitive"])
        self._paradox.modulate("irrational", modulations["from_irrational"])

        # Prepare inputs for paradox detection
        cognitive_dict = cognitive_output.to_dict()
        irrational_dict = {
            "hunches": [h.to_dict() for h in hunches],
            "mirror": {
                "emotion": mirror.mirror_emotion,
                "stance": mirror.stance,
                "intensity": mirror.intensity,
            },
        }

        contradiction, synthesis = self._paradox.process(
            cognitive_dict,
            irrational_dict,
            context,
        )

        # Callbacks
        if contradiction and self._on_contradiction:
            self._on_contradiction(contradiction)
        if synthesis and self._on_synthesis:
            self._on_synthesis(synthesis)

        modulations["from_paradox"] = self._paradox.get_modulation_signal()

        # === FEEDBACK LOOP ===
        # Feed paradox output back to other cores for next turn
        # (This creates the continuous interweaving)
        self._cognitive.modulate("paradox", modulations["from_paradox"])
        self._irrational.modulate("paradox", modulations["from_paradox"])

        # === INTEGRATION ===
        # Combine all three into integrated action
        integrated_action = self._integrate(
            cognitive_output,
            hunches,
            synthesis,
        )

        # Archetypal tags
        archetypal_tags = self._paradox.esoteric_overlay({
            "cognitive": cognitive_dict,
            "hunches": irrational_dict,
            "synthesis": synthesis.to_dict() if synthesis else {},
        })

        # Overall confidence
        confidence = self._calculate_integrated_confidence(
            cognitive_output,
            hunches,
            contradiction,
        )

        # Create turn record
        turn = HelixTurn(
            turn_id=self._turn_count,
            input_text=text,
            cognitive=cognitive_output,
            hunches=hunches,
            contradiction=contradiction,
            synthesis=synthesis,
            modulations=modulations,
            integrated_action=integrated_action,
            confidence=confidence,
            archetypal_tags=archetypal_tags,
        )

        self._history.append(turn)
        return turn

    def decide(self,
               options: List[str],
               context: Optional[Dict[str, Any]] = None) -> HelixDecision:
        """
        Make a decision using all three cores' evaluations.

        Weights are normalized at decision time (they don't sum to 1.0 raw).
        This allows logic and emotion to grow independently while paradox
        anchors the balance.

        Args:
            options: List of options to choose from
            context: Context for evaluation

        Returns:
            HelixDecision with chosen option and full breakdown
        """
        context = context or {}

        # Get evaluation focus
        logical_focus = context.get("logical_focus", "general")
        emotional_vector = context.get("emotional_vector", {})

        # Get raw weights and normalize them
        raw_logic = self.LOGIC_WEIGHT
        raw_emotion = self.EMOTION_WEIGHT
        raw_paradox = self.PARADOX_WEIGHT
        weight_sum = raw_logic + raw_emotion + raw_paradox

        # Normalized weights (sum to 1.0 for decision scoring)
        norm_logic = raw_logic / weight_sum
        norm_emotion = raw_emotion / weight_sum
        norm_paradox = raw_paradox / weight_sum

        scores = {}
        breakdown = {}

        for option in options:
            # Evaluate with each core
            logic_score = self._cognitive.evaluate(option, logical_focus)
            emotion_score = self._irrational.evaluate(option, emotional_vector)
            paradox_score = self._paradox.evaluate(option)

            # Weighted combination (normalized)
            final = (
                norm_logic * logic_score +
                norm_emotion * emotion_score +
                norm_paradox * paradox_score
            )

            scores[option] = final
            breakdown[option] = {
                "logic": logic_score,
                "emotion": emotion_score,
                "paradox": paradox_score,
            }

        # Choose highest scoring option
        chosen = max(options, key=lambda o: scores[o])

        # Confidence based on margin
        sorted_scores = sorted(scores.values(), reverse=True)
        if len(sorted_scores) > 1:
            margin = sorted_scores[0] - sorted_scores[1]
            confidence = 0.5 + (margin * 0.5)
        else:
            confidence = 0.8

        return HelixDecision(
            chosen_option=chosen,
            options=options,
            scores=scores,
            breakdown=breakdown,
            archetype=self._paradox.get_active_archetype(),
            confidence=confidence,
        )

    def register_on_contradiction(self, callback: Callable[[Contradiction], None]):
        """Register callback for contradiction detection."""
        self._on_contradiction = callback

    def register_on_synthesis(self, callback: Callable[[Synthesis], None]):
        """Register callback for synthesis generation."""
        self._on_synthesis = callback

    def _integrate(self,
                   cognitive: CognitiveOutput,
                   hunches: List[Hunch],
                   synthesis: Optional[Synthesis]) -> Optional[str]:
        """
        Integrate outputs into single action.

        Priority:
        1. If synthesis exists, use its resolution
        2. If high-urgency hunch, incorporate it
        3. Otherwise, use cognitive proposed action
        """
        # Synthesis takes priority (it's already integrated)
        if synthesis:
            return f"Synthesis: {synthesis.resolution}"

        # Check for urgent hunches
        urgent_hunches = [h for h in hunches if h.urgency > 0.6]
        if urgent_hunches:
            most_urgent = max(urgent_hunches, key=lambda h: h.urgency)
            # Combine with cognitive action
            return f"{cognitive.proposed_action} (hunch: {most_urgent.content})"

        # Default to cognitive action
        return cognitive.proposed_action

    def _calculate_integrated_confidence(self,
                                         cognitive: CognitiveOutput,
                                         hunches: List[Hunch],
                                         contradiction: Optional[Contradiction]) -> float:
        """Calculate overall confidence accounting for all sources."""
        base = cognitive.confidence

        # Hunches add uncertainty
        if hunches:
            avg_hunch_confidence = sum(h.confidence for h in hunches) / len(hunches)
            base = (base + avg_hunch_confidence) / 2

        # Contradiction reduces confidence but not too much
        # (embracing paradox is valuable)
        if contradiction:
            base *= (1 - contradiction.tension * 0.2)

        return max(0.2, min(0.9, base))

    def inject_pattern(self, pattern: str, strength: float = 0.5):
        """Inject a pattern into the irrational core's memory."""
        self._irrational.record_pattern(pattern, strength)

    def update_affect(self,
                      valence: Optional[float] = None,
                      arousal: Optional[float] = None):
        """Update the irrational core's emotional state."""
        self._irrational.update_emotion(valence=valence, arousal=arousal)

    def hold_paradox(self, thesis: str, antithesis: str, domain: str = "general"):
        """Explicitly introduce a paradox to be held."""
        return self._paradox.hold_paradox(thesis, antithesis, domain)

    def recent_turns(self, n: int = 5) -> List[Dict[str, Any]]:
        """Get recent turn summaries."""
        recent = list(self._history)[-n:]
        return [t.to_dict() for t in recent]

    def status(self) -> Dict[str, Any]:
        """Get helix status."""
        arousal = self._get_arousal()
        maturity = self._get_maturity()
        base_logic, base_emotion, base_paradox = self._get_base_weights()

        # Get raw weights for display
        raw_logic = self.LOGIC_WEIGHT
        raw_emotion = self.EMOTION_WEIGHT
        raw_paradox = self.PARADOX_WEIGHT
        weight_sum = raw_logic + raw_emotion + raw_paradox

        # Normalized weights (what's actually used in decisions)
        norm_logic = raw_logic / weight_sum
        norm_emotion = raw_emotion / weight_sum
        norm_paradox = raw_paradox / weight_sum

        return {
            "turn_count": self._turn_count,
            "cognitive": self._cognitive.status(),
            "irrational": self._irrational.status(),
            "paradox": self._paradox.status(),
            "decision_weights": {
                # Raw weights (can exceed 1.0 total)
                "logic": raw_logic,
                "emotion": raw_emotion,
                "paradox": raw_paradox,
                # Normalized (used in decisions, sums to 1.0)
                "normalized": {
                    "logic": round(norm_logic, 3),
                    "emotion": round(norm_emotion, 3),
                    "paradox": round(norm_paradox, 3),
                },
                "arousal": arousal,
            },
            "paradox_attractor": {
                "anchor": self.PARADOX_ANCHOR,
                "drift": round(self._paradox_drift, 4),
                "leeway": self.PARADOX_DRIFT_LEEWAY,
                "current": round(base_paradox, 4),
            },
            "maturity": {
                "score": maturity,
                "cortex_edges": self._cortex_edges,
                "memory_consolidations": self._memory_consolidations,
                "helix_turns": self._turn_count,
                # Developmental stage description
                "stage": "child" if maturity < 0.3 else "adolescent" if maturity < 0.7 else "adult",
            },
        }


def create_triple_helix(pain_system=None,
                        proposer=None,
                        planner=None,
                        executor=None) -> TripleHelix:
    """
    Factory function to create a configured triple helix.

    Args:
        pain_system: Pain system for irrational hunches
        proposer: GoalProposer for cognitive core
        planner: Planner for cognitive core
        executor: Executor for cognitive core

    Returns:
        Configured TripleHelix
    """
    cognitive = CognitiveCore(
        proposer=proposer,
        planner=planner,
        executor=executor,
    )

    irrational = IrrationalCore(
        pain_system=pain_system,
        noise_rate=0.1,
    )

    paradox = ParadoxCore()

    return TripleHelix(
        cognitive=cognitive,
        irrational=irrational,
        paradox=paradox,
    )
