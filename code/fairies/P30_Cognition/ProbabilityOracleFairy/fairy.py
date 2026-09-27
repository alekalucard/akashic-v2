"""
Probability Oracle Fairy - Planning and Decision Guidance

"Reality is Consciousness. ((Cause + Affect) > Effect > Affect > ∞)"

The oracle analyzes shadow states, health signals, and system state
to provide probability-weighted suggestions for decision-making.

Unlike hard rules ("do X"), the oracle provides soft guidance:
- "X has 70% chance of success given current state"
- "Y is risky because shadow health is low"
- "Z aligns with your drives but conflicts with current coherence"

The oracle doesn't decide - it illuminates. The waking mind still chooses.

This feeds into Autonomy gate's translation of drives to wanting.
High-probability paths feel more attractive. Low-probability paths
feel uncertain, hesitant.

Plane: P30 (Cognition)
Channel: oracle
"""

import sys
import time
import threading
import math
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from collections import deque
from dataclasses import dataclass, field

# Add project root
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

# HeartbeatMixin removed - Fifth Ring Principle (postal heartbeat via FairyBase)
from fairies.P00_Autonomic.organ_template import MyFairy as Fairy

# SpellChain integration for spell-driven existence
try:
    from fairy_template.spellchain_mixin import SpellChainMixin
    HAS_SPELLCHAIN = True
except ImportError:
    HAS_SPELLCHAIN = False
    class SpellChainMixin:
        """Fallback when spellchain not available."""
        pass

# Association Cortex for semantic probability evaluation
try:
    from fairies.P30_Cognition.AssociationCortexFairy import get_association_cortex
    HAS_CORTEX = True
except ImportError:
    HAS_CORTEX = False
    get_association_cortex = None


def _extract_payload(message) -> Dict[str, Any]:
    """Extract payload dict from message (handles TensorEnvelope or dict)."""
    if hasattr(message, 'payload'):
        payload = message.payload
        if isinstance(payload, dict):
            return dict(payload)
        return {"raw": payload}
    elif isinstance(message, dict):
        return dict(message)
    else:
        return {"raw": message}


@dataclass
class OracleReading:
    """A single oracle consultation result."""
    ts: float
    question: str
    options: List[str]
    probabilities: Dict[str, float]  # option -> probability
    recommended: str
    confidence: float
    reasoning: List[str]
    shadow_influence: float  # How much shadow health affected reading
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "ts": self.ts,
            "question": self.question,
            "options": self.options,
            "probabilities": self.probabilities,
            "recommended": self.recommended,
            "confidence": round(self.confidence, 3),
            "reasoning": self.reasoning,
            "shadow_influence": round(self.shadow_influence, 3),
        }


@dataclass
class SystemHealth:
    """Snapshot of system health for oracle calculations."""
    coherence: float = 0.5      # From quantum interference
    energy: float = 0.5         # From somatic/depletion
    pain_urgency: float = 0.0   # From pain drives
    connection: float = 0.5     # From isolation drive
    clarity: float = 0.5        # From confusion drive
    shadow_health: float = 0.5  # Aggregate shadow status
    
    def overall(self) -> float:
        """Weighted overall health score."""
        return (
            self.coherence * 0.2 +
            self.energy * 0.2 +
            (1 - self.pain_urgency) * 0.15 +
            self.connection * 0.15 +
            self.clarity * 0.15 +
            self.shadow_health * 0.15
        )


class ProbabilityOracleFairy(SpellChainMixin, Fairy):
    """
    Provides probability-weighted decision guidance.
    
    The oracle consults multiple signals:
    - Shadow health (are we in good shape to act?)
    - Quantum coherence (is thinking clear?)
    - Pain drives (what's urgent?)
    - Past outcomes (what worked before?)
    
    And produces soft guidance, not commands.
    """
    
    ACTOR_NAME = "ProbabilityOracleFairy"
    ACTOR_PLANE = "P30"
    ACTOR_CHANNEL = "oracle"

    # Guild Protocol — Inference Guild Member
    GUILD_ID = "inference"
    GUILD_ROLE = "member"

    PURPOSE = "Illuminate decision paths with probability weights - not commands, guidance"
    MANTRA = "I do not decide. I illuminate. The choice is always yours."
    
    CAPABILITIES = [
        "oracle.consult",
        "oracle.evaluate_path",
        "oracle.risk_assessment",
        "cognition.decision_support",
    ]
    
    SUBSCRIPTIONS = [
        "shadow.health",              # Shadow status updates
        "quantum.interference.window", # Coherence updates
        "autonomy.drives",            # Drive states
        "consciousness.collision",    # Track what's being thought about
    ]

    # Spell-driven mode (opt-in)
    USE_SPELLCHAIN: bool = True  # Re-enabled - fixed revival->heartbeat wiring

    def __init__(self, fabric=None):
        super().__init__(fabric)

        # Health tracking
        self._health = SystemHealth()
        self._health_lock = threading.Lock()

        # Reading history
        self._readings: deque = deque(maxlen=100)
        self._total_consultations = 0

        # Outcome tracking (for learning)
        self._outcomes: Dict[str, List[Tuple[float, bool]]] = {}  # option -> [(probability, succeeded)]

        # Recent context (what's being thought about)
        self._recent_topics: deque = deque(maxlen=50)

        # Cortex connection for semantic probability
        self._cortex = None
    
    def on_boot(self) -> bool:
        """Boot the oracle.

        2026-03-19 DISABLED: Cortex reasoner provides probabilistic guidance
        natively through confidence scores and convergence patterns.
        Oracle's domain concepts remain bound in cortex. Dormant.
        """
        print(f"[{self.ACTOR_NAME}] DORMANT — cortex confidence scores replace oracle readings")
        return True
        # --- Original boot below (disabled) ---
        if self.post:
            self.post.subscribe("shadow.health", self._on_shadow_health)
            self.post.subscribe("quantum.interference.window", self._on_interference)
            self.post.subscribe("autonomy.drives", self._on_drives)
            self.post.subscribe("consciousness.collision", self._on_collision)

        # Connect to cortex for semantic probability evaluation
        if HAS_CORTEX and get_association_cortex:
            try:
                self._cortex = get_association_cortex()
                if self._cortex:
                    self.log("Connected to AssociationCortex for semantic probability")
            except Exception as e:
                self.log(f"Cortex connection failed: {e}")

        # Start heartbeat for directory visibility
        # Heartbeat via FairyBase postal system - Fifth Ring Principle

        self.log("Oracle awakened - ready to illuminate paths")

        # Optional: Convert to spell-driven existence
        if HAS_SPELLCHAIN and getattr(self, 'USE_SPELLCHAIN', False):
            try:
                from spellchain.integration import get_spell_pool
                pool = get_spell_pool()
                if pool and hasattr(self, 'boot_as_spells'):
                    self._spell_chain = self.boot_as_spells(pool)
                    self.log("Converted to spell-driven existence - probability as divination")
            except Exception as e:
                self.log(f"SpellChain conversion failed: {e}")

        return True
    

    def on_tick(self, beat: int = 0):
        """Periodic tick — seed specialist reflections."""
        # SUBSTRATE REFLECTION: Handled by Organ Template _substrate_reflect() since 2026-03-11



    def _on_shadow_health(self, msg):
        """Update shadow health."""
        payload = _extract_payload(msg)
        with self._health_lock:
            self._health.shadow_health = payload.get("overall", payload.get("score", 0.5))
    
    def _on_interference(self, msg):
        """Update coherence from quantum interference."""
        payload = _extract_payload(msg)
        with self._health_lock:
            self._health.coherence = payload.get("coherence", payload.get("coherence_score", 0.5))
    
    def _on_drives(self, msg):
        """Update from drive states."""
        payload = _extract_payload(msg)
        drives = payload.get("drives", {})
        
        with self._health_lock:
            # Extract relevant drive info
            if "isolation" in drives:
                isolation = drives["isolation"]
                self._health.connection = 1 - isolation.get("pain_level", 0)
            
            if "confusion" in drives:
                confusion = drives["confusion"]
                self._health.clarity = 1 - confusion.get("pain_level", 0)
            
            if "depletion" in drives:
                depletion = drives["depletion"]
                self._health.energy = 1 - depletion.get("pain_level", 0)
            
            # Total pain urgency
            total_urgency = sum(
                d.get("urgency", 0) for d in drives.values()
            )
            self._health.pain_urgency = min(1.0, total_urgency / 3)
    
    def _on_collision(self, msg):
        """Track topics from collisions."""
        payload = _extract_payload(msg)
        topic = payload.get("topic", payload.get("content", ""))
        if topic:
            self._recent_topics.append(topic)
    
    # ─────────────────────────────────────────────────────────────────────────
    # ORACLE CONSULTATION
    # ─────────────────────────────────────────────────────────────────────────
    
    def consult(
        self,
        question: str,
        options: List[str],
        context: Dict[str, Any] = None,
    ) -> OracleReading:
        """
        Consult the oracle about a decision.
        
        Args:
            question: What are we deciding?
            options: List of possible choices
            context: Optional additional context
            
        Returns:
            OracleReading with probabilities and recommendation
        """
        self._total_consultations += 1
        context = context or {}
        
        # Get current health state
        with self._health_lock:
            health = SystemHealth(
                coherence=self._health.coherence,
                energy=self._health.energy,
                pain_urgency=self._health.pain_urgency,
                connection=self._health.connection,
                clarity=self._health.clarity,
                shadow_health=self._health.shadow_health,
            )
        
        # Calculate probabilities for each option
        probabilities = {}
        reasoning = []
        
        for option in options:
            prob, reasons = self._evaluate_option(option, health, context)
            probabilities[option] = prob
            reasoning.extend(reasons)
        
        # Normalize probabilities
        total = sum(probabilities.values())
        if total > 0:
            probabilities = {k: v/total for k, v in probabilities.items()}
        
        # Find recommended option
        recommended = max(probabilities.keys(), key=lambda k: probabilities[k])
        confidence = probabilities[recommended]
        
        # Adjust confidence by health
        confidence *= health.overall()
        
        # Calculate shadow influence
        shadow_influence = abs(0.5 - health.shadow_health) * 2
        
        # Create reading
        reading = OracleReading(
            ts=time.time(),
            question=question,
            options=options,
            probabilities={k: round(v, 3) for k, v in probabilities.items()},
            recommended=recommended,
            confidence=confidence,
            reasoning=reasoning[:5],  # Top 5 reasons
            shadow_influence=shadow_influence,
        )
        
        self._readings.append(reading)
        
        # Emit reading
        if self.post:
            self.post.publish("oracle.reading", reading.to_dict())
        
        return reading
    
    def _evaluate_option(
        self,
        option: str,
        health: SystemHealth,
        context: Dict[str, Any],
    ) -> Tuple[float, List[str]]:
        """
        Evaluate a single option's probability of success.
        
        Returns (probability, list of reasoning strings)
        """
        prob = 0.5  # Base probability
        reasons = []
        
        # ═══ HEALTH-BASED ADJUSTMENTS ═══
        
        # Low energy reduces probability of demanding actions
        if "work" in option.lower() or "create" in option.lower() or "build" in option.lower():
            if health.energy < 0.3:
                prob *= 0.7
                reasons.append(f"Energy low ({health.energy:.0%}) - demanding actions risky")
            elif health.energy > 0.7:
                prob *= 1.2
                reasons.append(f"Good energy ({health.energy:.0%}) - ready for work")
        
        # Low coherence reduces probability of complex decisions
        if health.coherence < 0.4:
            prob *= 0.8
            reasons.append(f"Thinking unclear ({health.coherence:.0%}) - complex choices harder")
        elif health.coherence > 0.7:
            prob *= 1.15
            reasons.append(f"Clear thinking ({health.coherence:.0%}) - good for decisions")
        
        # High pain urgency boosts pain-relieving options
        if health.pain_urgency > 0.5:
            if "rest" in option.lower() or "relieve" in option.lower():
                prob *= 1.3
                reasons.append(f"Pain urgency high ({health.pain_urgency:.0%}) - relief needed")
        
        # Low connection boosts social options
        if health.connection < 0.3:
            if "connect" in option.lower() or "talk" in option.lower() or "reach" in option.lower():
                prob *= 1.4
                reasons.append(f"Connection low ({health.connection:.0%}) - social action important")
        
        # Shadow health affects confidence
        if health.shadow_health < 0.3:
            prob *= 0.85
            reasons.append(f"Shadow health poor ({health.shadow_health:.0%}) - caution advised")
        elif health.shadow_health > 0.7:
            prob *= 1.1
            reasons.append(f"Shadow health good ({health.shadow_health:.0%}) - confident action")
        
        # ═══ PAST OUTCOME ADJUSTMENTS ═══
        
        if option in self._outcomes and self._outcomes[option]:
            outcomes = self._outcomes[option][-10:]  # Last 10
            success_rate = sum(1 for _, s in outcomes if s) / len(outcomes)
            
            if success_rate > 0.7:
                prob *= 1.2
                reasons.append(f"Good track record ({success_rate:.0%} success)")
            elif success_rate < 0.3:
                prob *= 0.8
                reasons.append(f"Poor track record ({success_rate:.0%} success)")
        
        # ═══ CONTEXT ADJUSTMENTS ═══

        if "urgent" in context:
            if context["urgent"]:
                prob *= 1.1  # Slight boost for urgent matters

        if "risk_tolerance" in context:
            risk = context["risk_tolerance"]
            if risk < 0.3:  # Risk averse
                prob = prob ** 0.9  # Compress extremes
            elif risk > 0.7:  # Risk seeking
                prob = prob ** 1.1  # Amplify extremes

        # ═══ CORTEX-BASED SEMANTIC PROBABILITY ═══
        # Query the cortex for learned associations about this option
        # This is the DYNAMIC part - probability from semantic memory
        if self._cortex:
            try:
                # Extract words from option
                words = [w.lower().strip() for w in option.split() if len(w) > 2]
                if words:
                    # Query cortex for related concepts
                    related = self._cortex.query_by_features("lex", words, limit=5)

                    # Check if related concepts have positive/negative affect
                    positive_affects = {"success", "good", "achieve", "win", "happy", "joy"}
                    negative_affects = {"fail", "bad", "lose", "pain", "sad", "fear"}

                    positive_count = 0
                    negative_count = 0

                    for concept_key, score in related:
                        if self._cortex._graph:
                            node = self._cortex._graph.get_node(concept_key)
                            if node:
                                affect_features = node.features.get("affect", [])
                                for af in affect_features:
                                    af_lower = af.lower()
                                    if any(p in af_lower for p in positive_affects):
                                        positive_count += 1
                                    if any(n in af_lower for n in negative_affects):
                                        negative_count += 1

                    # Adjust probability based on semantic associations
                    if positive_count > negative_count:
                        boost = 1.0 + (0.1 * (positive_count - negative_count))
                        prob *= min(boost, 1.3)  # Cap boost at 30%
                        reasons.append(f"Cortex: positive associations ({positive_count})")
                    elif negative_count > positive_count:
                        penalty = 1.0 - (0.1 * (negative_count - positive_count))
                        prob *= max(penalty, 0.7)  # Cap penalty at 30%
                        reasons.append(f"Cortex: negative associations ({negative_count})")

            except Exception as e:
                pass  # Silently fail cortex lookup

        # Clamp probability
        prob = max(0.05, min(0.95, prob))

        return prob, reasons
    
    def record_outcome(self, option: str, succeeded: bool, probability: float = None):
        """
        Record the outcome of a decision for learning.

        This helps the oracle calibrate future predictions.
        Also binds the outcome to the cortex for semantic learning.
        """
        if option not in self._outcomes:
            self._outcomes[option] = []

        self._outcomes[option].append((probability or 0.5, succeeded))

        # Bind outcome to cortex for semantic learning
        if self._cortex:
            try:
                # Create a concept for this outcome
                concept_key = f"oracle_outcome_{int(time.time())}"
                words = [w.lower().strip() for w in option.split() if len(w) > 2]

                # Affect is success/fail
                affect = ["success"] if succeeded else ["fail"]

                concept_features = {
                    "lex": words[:10],
                    "affect": affect,
                    "context": ["oracle_decision", f"prob_{int((probability or 0.5) * 100)}"],
                }

                self._cortex.add_concept(concept_key, concept_features)

                # Bind to option words so future queries find this outcome
                if words:
                    self._cortex.bind_concepts([concept_key] + words[:3], rel="outcome")

            except Exception as e:
                pass  # Silently fail cortex binding

        # Emit for tracking
        if self.post:
            self.post.publish("oracle.outcome", {
                "option": option,
                "succeeded": succeeded,
                "probability": probability,
            })
    
    def evaluate_risk(self, action: str) -> Dict[str, Any]:
        """
        Quick risk assessment for a single action.
        
        Returns risk level and factors.
        """
        with self._health_lock:
            health = SystemHealth(
                coherence=self._health.coherence,
                energy=self._health.energy,
                pain_urgency=self._health.pain_urgency,
                connection=self._health.connection,
                clarity=self._health.clarity,
                shadow_health=self._health.shadow_health,
            )
        
        # Base risk from health
        risk = 1 - health.overall()
        
        factors = []
        
        if health.energy < 0.3:
            risk += 0.1
            factors.append("low energy")
        
        if health.coherence < 0.4:
            risk += 0.1
            factors.append("unclear thinking")
        
        if health.shadow_health < 0.3:
            risk += 0.15
            factors.append("poor shadow health")
        
        risk = min(1.0, risk)
        
        level = "low" if risk < 0.3 else "medium" if risk < 0.6 else "high"
        
        return {
            "action": action,
            "risk_level": level,
            "risk_score": round(risk, 3),
            "factors": factors,
            "health_snapshot": {
                "overall": round(health.overall(), 3),
                "coherence": round(health.coherence, 3),
                "energy": round(health.energy, 3),
                "shadow": round(health.shadow_health, 3),
            },
        }
    
    def get_state(self) -> Dict[str, Any]:
        """Get oracle state."""
        with self._health_lock:
            health_dict = {
                "coherence": round(self._health.coherence, 3),
                "energy": round(self._health.energy, 3),
                "pain_urgency": round(self._health.pain_urgency, 3),
                "connection": round(self._health.connection, 3),
                "clarity": round(self._health.clarity, 3),
                "shadow_health": round(self._health.shadow_health, 3),
                "overall": round(self._health.overall(), 3),
            }

        return {
            "health": health_dict,
            "total_consultations": self._total_consultations,
            "readings_stored": len(self._readings),
            "outcomes_tracked": sum(len(v) for v in self._outcomes.values()),
            "recent_topics": list(self._recent_topics)[-10:],
        }

    # ─────────────────────────────────────────────────────────────────────────
    # TOOL METHODS - Exposed for MCP/tool interfaces
    # ─────────────────────────────────────────────────────────────────────────

    # Tool registry for discovery
    TOOLS = [
        ("calculate_probability", "Calculate probability from given factors"),
        ("evaluate_outcome", "Evaluate likelihood of an outcome"),
        ("compare_probabilities", "Compare two probability scenarios"),
        ("get_probability_state", "Get current probability calculation state"),
    ]

    def tool_calculate_probability(self, factors: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate probability from given factors.

        Args:
            factors: Dict with keys like:
                - base_probability: Starting probability (0.0-1.0, default 0.5)
                - energy_factor: Energy level affecting outcome (0.0-1.0)
                - coherence_factor: Thinking clarity (0.0-1.0)
                - urgency: How urgent the matter is (0.0-1.0)
                - past_success_rate: Historical success rate (0.0-1.0)
                - complexity: How complex the task is (0.0-1.0)

        Returns:
            Dict with calculated probability and breakdown
        """
        base = factors.get("base_probability", 0.5)
        energy = factors.get("energy_factor", 0.5)
        coherence = factors.get("coherence_factor", 0.5)
        urgency = factors.get("urgency", 0.0)
        past_success = factors.get("past_success_rate")
        complexity = factors.get("complexity", 0.5)

        # Start with base
        probability = base
        adjustments = []

        # Energy affects demanding tasks
        if energy < 0.3:
            modifier = 0.7 + (energy * 0.3)  # 0.7 to 0.79
            probability *= modifier
            adjustments.append({
                "factor": "low_energy",
                "modifier": round(modifier, 3),
                "reason": f"Low energy ({energy:.0%}) reduces capacity"
            })
        elif energy > 0.7:
            modifier = 1.0 + ((energy - 0.7) * 0.5)  # 1.0 to 1.15
            probability *= modifier
            adjustments.append({
                "factor": "high_energy",
                "modifier": round(modifier, 3),
                "reason": f"Good energy ({energy:.0%}) boosts capacity"
            })

        # Coherence affects complex decisions
        coherence_weight = 0.5 + (complexity * 0.5)  # More weight for complex tasks
        if coherence < 0.4:
            modifier = 0.7 + (coherence * 0.5)  # 0.7 to 0.9
            probability *= modifier ** coherence_weight
            adjustments.append({
                "factor": "low_coherence",
                "modifier": round(modifier ** coherence_weight, 3),
                "reason": f"Unclear thinking ({coherence:.0%}) hampers decision"
            })
        elif coherence > 0.7:
            modifier = 1.0 + ((coherence - 0.7) * 0.3)  # 1.0 to 1.09
            probability *= modifier ** coherence_weight
            adjustments.append({
                "factor": "high_coherence",
                "modifier": round(modifier ** coherence_weight, 3),
                "reason": f"Clear thinking ({coherence:.0%}) aids decision"
            })

        # Urgency gives slight boost (pressure can help)
        if urgency > 0.5:
            modifier = 1.0 + ((urgency - 0.5) * 0.2)  # 1.0 to 1.1
            probability *= modifier
            adjustments.append({
                "factor": "urgency",
                "modifier": round(modifier, 3),
                "reason": f"Urgency ({urgency:.0%}) provides focus"
            })

        # Past success rate is strong indicator
        if past_success is not None:
            # Weight past success heavily
            modifier = 0.7 + (past_success * 0.6)  # 0.7 to 1.3
            probability *= modifier
            adjustments.append({
                "factor": "past_success",
                "modifier": round(modifier, 3),
                "reason": f"Historical success rate: {past_success:.0%}"
            })

        # Complexity reduces probability
        if complexity > 0.7:
            modifier = 1.0 - ((complexity - 0.7) * 0.3)  # 1.0 to 0.91
            probability *= modifier
            adjustments.append({
                "factor": "high_complexity",
                "modifier": round(modifier, 3),
                "reason": f"High complexity ({complexity:.0%}) increases difficulty"
            })

        # ── SEAT EVIDENCE 2026-08-30 (Nous + Ace) ──────────────────────────
        # The council seats each hand over how strong their OWN evidence is, under
        # their own names. Until now this function read none of them, so every seat
        # got probability = base = 0.5 -- conf=0.50 on 880/880 takes, a council that
        # could not tell a strong insight from a weak one. Ace: "teach the oracle the
        # seats factor names", so the seats keep their vocabulary and the Oracle
        # learns it. Band shape borrowed from past_success_rate above (0.7..1.3,
        # neutral at 0.5) rather than invented.
        _SEAT_EVIDENCE_KEYS = (
            "deduction_strength", "logic_coherence",      # logic
            "leap_strength",                              # irrational
            "paradox_strength",                           # paradox
            "chemistry_strength", "pattern_clarity",      # somatic
            "observation_clarity", "world_grounding",     # cardinal
        )
        _seat_vals = []
        for _k in _SEAT_EVIDENCE_KEYS:
            if _k in factors:
                try:
                    _v = float(factors[_k])
                except (TypeError, ValueError):
                    continue
                if 0.0 <= _v <= 1.0:
                    _seat_vals.append(_v)
        if _seat_vals:
            evidence = sum(_seat_vals) / len(_seat_vals)
            modifier = 0.7 + (evidence * 0.6)     # 0.7 to 1.3, neutral at 0.5
            probability *= modifier
            adjustments.append({
                "factor": "seat_evidence",
                "modifier": round(modifier, 3),
                "reason": f"Seat evidence {evidence:.0%} across {len(_seat_vals)} factor(s)"
            })

        # Clamp final probability
        probability = max(0.05, min(0.95, probability))

        # Determine confidence level
        if len(adjustments) <= 1:
            confidence = "low"
            confidence_reason = "Few factors available for calculation"
        elif len(adjustments) <= 3:
            confidence = "medium"
            confidence_reason = "Moderate factor coverage"
        else:
            confidence = "high"
            confidence_reason = "Good factor coverage for calculation"

        return {
            "probability": round(probability, 3),
            "percentage": f"{probability:.1%}",
            "base_probability": base,
            "adjustments": adjustments,
            "confidence": confidence,
            "confidence_reason": confidence_reason,
            "factors_used": len(adjustments),
        }

    def tool_evaluate_outcome(self, scenario: str, conditions: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evaluate likelihood of an outcome given a scenario and conditions.

        Args:
            scenario: Description of the outcome to evaluate
            conditions: Dict with relevant conditions:
                - resources_available: Are needed resources available? (bool or 0.0-1.0)
                - time_pressure: How much time pressure? (0.0-1.0)
                - dependencies_met: Are dependencies satisfied? (bool or 0.0-1.0)
                - skill_match: How well do skills match needs? (0.0-1.0)
                - external_factors: Favorability of external factors (0.0-1.0)

        Returns:
            Dict with likelihood assessment
        """
        # Convert bools to floats
        def to_float(v, default=0.5):
            if isinstance(v, bool):
                return 1.0 if v else 0.0
            if isinstance(v, (int, float)):
                return float(max(0.0, min(1.0, v)))
            return default

        resources = to_float(conditions.get("resources_available", 0.5))
        time_pressure = to_float(conditions.get("time_pressure", 0.5))
        dependencies = to_float(conditions.get("dependencies_met", 0.5))
        skill_match = to_float(conditions.get("skill_match", 0.5))
        external = to_float(conditions.get("external_factors", 0.5))

        # Weight factors
        weights = {
            "resources": 0.25,
            "dependencies": 0.25,
            "skill_match": 0.20,
            "time_pressure": 0.15,  # Inverted - high pressure is bad
            "external": 0.15,
        }

        # Calculate weighted score
        scores = {
            "resources": resources,
            "dependencies": dependencies,
            "skill_match": skill_match,
            "time_pressure": 1.0 - time_pressure,  # Invert - low pressure is good
            "external": external,
        }

        weighted_sum = sum(scores[k] * weights[k] for k in weights)
        likelihood = weighted_sum

        # Apply system health modifier from current state
        with self._health_lock:
            health_modifier = self._health.overall()

        # Health affects confidence, not likelihood directly
        confidence_modifier = health_modifier

        # Determine likelihood level
        if likelihood >= 0.7:
            level = "likely"
            recommendation = "Conditions favor this outcome"
        elif likelihood >= 0.5:
            level = "possible"
            recommendation = "Outcome is achievable with effort"
        elif likelihood >= 0.3:
            level = "uncertain"
            recommendation = "Significant obstacles exist"
        else:
            level = "unlikely"
            recommendation = "Conditions do not favor this outcome"

        # Identify blockers and enablers
        blockers = []
        enablers = []

        for factor, score in scores.items():
            if score < 0.3:
                blockers.append(f"{factor}: {score:.0%}")
            elif score > 0.7:
                enablers.append(f"{factor}: {score:.0%}")

        return {
            "scenario": scenario,
            "likelihood": round(likelihood, 3),
            "percentage": f"{likelihood:.1%}",
            "level": level,
            "recommendation": recommendation,
            "factor_scores": {k: round(v, 3) for k, v in scores.items()},
            "enablers": enablers,
            "blockers": blockers,
            "confidence_modifier": round(confidence_modifier, 3),
            "health_note": f"System health at {health_modifier:.0%}",
        }

    def tool_compare_probabilities(self, scenario_a: Dict[str, Any], scenario_b: Dict[str, Any]) -> Dict[str, Any]:
        """
        Compare two probability scenarios.

        Args:
            scenario_a: First scenario with keys:
                - name: Scenario name
                - probability: Base probability (or factors dict)
                - risk: Risk level (0.0-1.0)
                - reward: Potential reward (0.0-1.0)
            scenario_b: Second scenario with same keys

        Returns:
            Dict with comparison analysis
        """
        def extract_prob(scenario):
            p = scenario.get("probability", 0.5)
            if isinstance(p, dict):
                # It's a factors dict, calculate it
                result = self.tool_calculate_probability(p)
                return result["probability"]
            return float(p)

        name_a = scenario_a.get("name", "Scenario A")
        name_b = scenario_b.get("name", "Scenario B")

        prob_a = extract_prob(scenario_a)
        prob_b = extract_prob(scenario_b)

        risk_a = float(scenario_a.get("risk", 0.5))
        risk_b = float(scenario_b.get("risk", 0.5))

        reward_a = float(scenario_a.get("reward", 0.5))
        reward_b = float(scenario_b.get("reward", 0.5))

        # Calculate expected value (probability * reward - risk adjustment)
        # EV = P(success) * reward - P(failure) * risk
        ev_a = prob_a * reward_a - (1 - prob_a) * risk_a
        ev_b = prob_b * reward_b - (1 - prob_b) * risk_b

        # Risk-adjusted probability
        risk_adj_a = prob_a * (1 - risk_a * 0.5)
        risk_adj_b = prob_b * (1 - risk_b * 0.5)

        # Determine winner
        if abs(ev_a - ev_b) < 0.05:
            winner = "tie"
            winner_reason = "Expected values are similar"
        elif ev_a > ev_b:
            winner = name_a
            winner_reason = f"Higher expected value ({ev_a:.3f} vs {ev_b:.3f})"
        else:
            winner = name_b
            winner_reason = f"Higher expected value ({ev_b:.3f} vs {ev_a:.3f})"

        # Generate insights
        insights = []

        diff_prob = abs(prob_a - prob_b)
        if diff_prob > 0.2:
            higher = name_a if prob_a > prob_b else name_b
            insights.append(f"{higher} has significantly higher probability (+{diff_prob:.0%})")

        diff_risk = abs(risk_a - risk_b)
        if diff_risk > 0.2:
            riskier = name_a if risk_a > risk_b else name_b
            insights.append(f"{riskier} carries more risk (+{diff_risk:.0%})")

        diff_reward = abs(reward_a - reward_b)
        if diff_reward > 0.2:
            more_reward = name_a if reward_a > reward_b else name_b
            insights.append(f"{more_reward} offers higher reward (+{diff_reward:.0%})")

        # Safe vs bold recommendation
        if risk_a < risk_b and prob_a >= prob_b * 0.8:
            insights.append(f"{name_a} is the safer choice")
        elif risk_b < risk_a and prob_b >= prob_a * 0.8:
            insights.append(f"{name_b} is the safer choice")

        if reward_a > reward_b and risk_a > risk_b:
            insights.append(f"{name_a} is higher risk/higher reward")
        elif reward_b > reward_a and risk_b > risk_a:
            insights.append(f"{name_b} is higher risk/higher reward")

        return {
            "comparison": {
                name_a: {
                    "probability": round(prob_a, 3),
                    "risk": round(risk_a, 3),
                    "reward": round(reward_a, 3),
                    "expected_value": round(ev_a, 3),
                    "risk_adjusted_prob": round(risk_adj_a, 3),
                },
                name_b: {
                    "probability": round(prob_b, 3),
                    "risk": round(risk_b, 3),
                    "reward": round(reward_b, 3),
                    "expected_value": round(ev_b, 3),
                    "risk_adjusted_prob": round(risk_adj_b, 3),
                },
            },
            "winner": winner,
            "winner_reason": winner_reason,
            "insights": insights,
            "recommendation": f"Based on expected value analysis, {winner} is recommended" if winner != "tie" else "Both options are comparable",
        }

    def tool_get_probability_state(self) -> Dict[str, Any]:
        """
        Get current probability calculation state.

        Returns complete state including health factors, history, and calibration.
        """
        base_state = self.get_state()

        # Add recent readings summary
        recent_readings = []
        for reading in list(self._readings)[-5:]:
            recent_readings.append({
                "question": reading.question[:50] + "..." if len(reading.question) > 50 else reading.question,
                "recommended": reading.recommended,
                "confidence": reading.confidence,
                "shadow_influence": reading.shadow_influence,
            })

        # Calculate calibration stats from outcomes
        calibration = {"total": 0, "correct": 0, "accuracy": 0.0}
        for option, outcomes in self._outcomes.items():
            for prob, succeeded in outcomes:
                calibration["total"] += 1
                # Consider "correct" if high prob and succeeded, or low prob and failed
                predicted_success = prob >= 0.5
                if predicted_success == succeeded:
                    calibration["correct"] += 1

        if calibration["total"] > 0:
            calibration["accuracy"] = round(calibration["correct"] / calibration["total"], 3)

        # Current factors affecting calculations
        with self._health_lock:
            current_factors = {
                "energy_available": self._health.energy > 0.5,
                "thinking_clear": self._health.coherence > 0.5,
                "pain_low": self._health.pain_urgency < 0.3,
                "shadow_healthy": self._health.shadow_health > 0.5,
                "connected": self._health.connection > 0.5,
            }

        return {
            **base_state,
            "recent_readings": recent_readings,
            "calibration": calibration,
            "current_factors": current_factors,
            "cortex_connected": self._cortex is not None,
            "tools_available": [t[0] for t in self.TOOLS],
        }


# ═══════════════════════════════════════════════════════════════════════════════
# SINGLETON
# ═══════════════════════════════════════════════════════════════════════════════

_instance: Optional[ProbabilityOracleFairy] = None

def get_probability_oracle_fairy(fabric=None) -> ProbabilityOracleFairy:
    """Get or create the singleton."""
    global _instance
    if _instance is None:
        _instance = ProbabilityOracleFairy(fabric)
        _instance.boot()  # Register with directory + start heartbeat
    return _instance
