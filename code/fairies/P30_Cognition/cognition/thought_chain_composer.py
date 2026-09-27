"""
Thought Chain Composer — Context-Aware Reflection & Somatic Description
========================================================================

Replaces hardcoded reflection pools and somatic-to-text mappings in
thought_chain_engine.py with context-aware composition.

The ThoughtChainEngine already gathers rich system context via
_gather_system_context() — working memory, cortex concepts, collisions,
chemistry, interests, drives. But then throws it away and picks from
19 static reflection strings.

This composer USES that context to produce reflections that are about
what the chain is actually exploring, and somatic descriptions that
reflect actual chemistry patterns.

Follows the same pattern as inner_monologue_composer.py:
  raw state -> pattern detection -> intelligent composition
"""

from __future__ import annotations
import random
from typing import Dict, List, Optional, Any, Tuple


# ═══════════════════════════════════════════════════════════════════════════════
# CHEMISTRY PATTERN DETECTION (shared logic)
# ═══════════════════════════════════════════════════════════════════════════════

def detect_chemistry_patterns(chem: Dict[str, float]) -> List[str]:
    """Detect notable neurochemical patterns for somatic description."""
    patterns = []
    dop = chem.get("DOP", 0.5)
    ser = chem.get("SER", 0.5)
    nor = chem.get("NOR", 0.5)
    ach = chem.get("ACH", 0.5)
    oxy = chem.get("OXY", 0.5)
    cor = chem.get("COR", 0.5)
    gaba = chem.get("GABA", 0.5)
    end = chem.get("END", 0.5)

    if dop > 0.5 and ach > 0.5 and cor < 0.4:
        patterns.append("flow")
    if nor > 0.6 and ach > 0.5:
        patterns.append("high_activation")
    if cor > 0.6:
        patterns.append("stress_response")
    if gaba > 0.5 and cor < 0.3:
        patterns.append("calm")
    if oxy > 0.5:
        patterns.append("bonding")
    if dop > 0.6 and end > 0.4:
        patterns.append("reward")
    if ser > 0.6:
        patterns.append("contentment")
    if dop > 0.4 and nor > 0.4 and ach > 0.4:
        patterns.append("curiosity_chemistry")
    if dop < 0.3 and ser < 0.3 and nor < 0.3:
        patterns.append("depleted")

    return patterns


# ═══════════════════════════════════════════════════════════════════════════════
# REFLECTION COMPOSER
# ═══════════════════════════════════════════════════════════════════════════════

# The original pools — preserved as fallback building blocks
REFLECTION_POOLS = {
    "low_certainty": [
        "Hmm, I'm not sure about this direction...",
        "Something feels uncertain here. Let me reconsider.",
        "Wait, do I really understand this?",
    ],
    "negative_affect": [
        "This doesn't feel right. What's bothering me?",
        "Something's off here. Let me step back.",
        "My gut says there's a problem. What is it?",
    ],
    "insight_forming": [
        "Ooh, I'm onto something here...",
        "There's a connection forming... let me focus.",
        "This feels important. What am I seeing?",
    ],
    "chain_too_deep": [
        "I've been thinking in circles. Time to refocus.",
        "Let me zoom out and see the bigger picture.",
        "I may be overthinking this. What's essential?",
    ],
    "sustained_uncertainty": [
        "I've been uncertain for a while. What do I actually know?",
        "Let me ground this in something concrete.",
        "What would Ace say about this approach?",
    ],
    "fibonacci_rhythm": [
        "Natural pause point. How does this chain feel so far?",
        "Fibonacci checkpoint. What patterns am I seeing?",
        "Golden ratio moment. Let me integrate what I've learned.",
        "Rhythm pause. Is this chain heading somewhere meaningful?",
    ],
}

# Expanded prefix map — 3-4 variants per goal type
EXPANDED_PREFIX_MAP = {
    "learning": ["Studying", "Learning about", "Absorbing", "Integrating"],
    "exploration": ["Exploring", "Venturing into", "Investigating", "Mapping"],
    "problem_solving": ["Working through", "Solving", "Untangling", "Debugging"],
    "introspection": ["Feeling into", "Looking inward at", "Sensing", "Examining within"],
    "drive": ["Driven by", "Pulled toward", "Moved by", "Responding to"],
    "observation": ["Observing", "Noticing", "Watching", "Catching"],
    "reflection": ["Reflecting on", "Considering", "Revisiting", "Contemplating"],
    "curiosity": ["Wondering about", "Curious about", "Asking about", "Drawn to"],
    "planning": ["Planning", "Mapping out", "Charting", "Designing"],
    "consolidation": ["Integrating", "Weaving together", "Consolidating", "Synthesizing"],
    "awakening": ["Becoming aware", "Waking to", "Realizing", "Discovering"],
}


class ThoughtChainComposer:
    """
    Composes context-aware reflections and somatic descriptions for thought chains.

    Instead of picking from 19 static strings, produces reflections that
    reference what the chain is actually exploring — its goal, depth,
    recent concepts, and active collisions.
    """

    def __init__(self):
        self._recent_reflections: list = []  # Last 5 reflections for variety

    def compose_reflection(self, reason: str, chain_goal: str,
                           chain_depth: int,
                           system_context: Optional[Dict] = None) -> str:
        """
        Compose a reflection that's about what the chain is actually doing.

        Args:
            reason: Why reflecting (low_certainty, insight_forming, etc.)
            chain_goal: The chain's goal text
            chain_depth: How many links deep
            system_context: From _gather_system_context() — concepts, collisions, etc.
        """
        ctx = system_context or {}

        # Extract useful context
        concepts = ctx.get("concepts", [])
        collisions = ctx.get("collisions", [])
        tracers = ctx.get("tracers", [])

        # Try to build a context-specific reflection
        reflection = self._build_contextual_reflection(
            reason, chain_goal, chain_depth, concepts, collisions, tracers)

        if reflection and reflection not in self._recent_reflections:
            self._recent_reflections.append(reflection)
            if len(self._recent_reflections) > 5:
                self._recent_reflections.pop(0)
            return reflection

        # Fallback to original pools
        return self._fallback_reflection(reason)

    def _build_contextual_reflection(
        self, reason: str, goal: str, depth: int,
        concepts: List, collisions: List, tracers: List
    ) -> Optional[str]:
        """Build a reflection that references actual chain content."""

        # Extract a topic hint from the goal
        goal_short = goal[:40].strip() if goal else ""

        # Get concept names from cortex activations
        concept_names = []
        for c in concepts[:3]:
            if isinstance(c, tuple):
                concept_names.append(c[0])
            elif isinstance(c, str):
                concept_names.append(c)

        # Get collision echo
        collision_hint = ""
        if collisions:
            latest = collisions[-1]
            recall = latest.get("recall", "")[:25]
            ingest = latest.get("ingest", "")[:25]
            if recall and ingest:
                collision_hint = f"{recall} and {ingest}"
            elif recall:
                collision_hint = recall
            elif ingest:
                collision_hint = ingest

        # ── Build reason-specific contextual reflections ──

        if reason == "low_certainty":
            if concept_names:
                topic = concept_names[0]
                return random.choice([
                    f"I'm uncertain about how {topic} connects here...",
                    f"Something about {topic} doesn't quite fit yet.",
                    f"The link between {topic} and this chain feels tenuous...",
                ])
            elif goal_short:
                return f"Not sure this path leads to understanding {goal_short}..."

        elif reason == "negative_affect":
            if collision_hint:
                return f"Something feels off about {collision_hint}. Let me step back."
            elif goal_short:
                return f"This approach to {goal_short} doesn't feel right..."

        elif reason == "insight_forming":
            if concept_names and len(concept_names) >= 2:
                return random.choice([
                    f"Wait — {concept_names[0]} and {concept_names[1]}... there's a connection!",
                    f"I see it: {concept_names[0]} connects to {concept_names[1]}...",
                    f"The bridge between {concept_names[0]} and {concept_names[1]} is forming...",
                ])
            elif collision_hint:
                return f"Ooh, {collision_hint} — something's clicking..."
            elif tracers:
                tracer = tracers[0][:40] if isinstance(tracers[0], str) else str(tracers[0])[:40]
                return f"This connects to something I was just thinking: {tracer}..."

        elif reason == "chain_too_deep":
            return random.choice([
                f"Depth {depth} on '{goal_short[:25]}' — time to zoom out.",
                f"I've been tunneling into this for {depth} steps. What's the core question?",
                f"Deep in the weeds at step {depth}. What does this mean for {goal_short[:20]}?",
            ])

        elif reason == "sustained_uncertainty":
            if concept_names:
                return f"Still uncertain. Maybe approaching through {concept_names[0]} instead?"
            return f"Sustained uncertainty about {goal_short[:30]}. What do I actually know?"

        elif reason == "fibonacci_rhythm":
            if concept_names:
                topics = ", ".join(concept_names[:2])
                return random.choice([
                    f"Pause. I've touched {topics} so far. What's the pattern?",
                    f"Fibonacci checkpoint. {topics} — how do they weave together?",
                    f"Natural rhythm pause. The concepts ({topics}) are starting to cohere...",
                ])
            elif depth > 0:
                return f"Step {depth} pause. Is this chain converging on {goal_short[:25]}?"

        return None

    def _fallback_reflection(self, reason: str) -> str:
        """Original static pools as fallback."""
        pool = REFLECTION_POOLS.get(reason, REFLECTION_POOLS["low_certainty"])
        return random.choice(pool)

    # ─────────────────────────────────────────────────────────────────────────
    # SOMATIC DESCRIPTION — Chemistry-pattern-driven
    # ─────────────────────────────────────────────────────────────────────────

    def compose_somatic_description(
        self, chem: Dict[str, float],
        affect: Dict[str, float],
        goal_type: str = ""
    ) -> Optional[str]:
        """
        Compose somatic description from actual chemistry patterns.

        Replaces the 6 threshold checks + 4 affect quadrant strings with
        pattern-detected descriptions.
        """
        patterns = detect_chemistry_patterns(chem) if chem else []

        # Build from detected patterns (richer than threshold checks)
        felt_parts = []

        if "flow" in patterns:
            felt_parts.append(random.choice([
                "flow state engaged", "deep focus groove",
                "in the zone, everything clicking"]))
        if "stress_response" in patterns:
            felt_parts.append(random.choice([
                "stress elevated", "cortisol pushing",
                "tension in the system"]))
        if "reward" in patterns:
            felt_parts.append(random.choice([
                "reward signals high", "dopamine singing",
                "something good here"]))
        if "bonding" in patterns:
            felt_parts.append(random.choice([
                "connection warmth", "oxytocin glow",
                "togetherness chemistry"]))
        if "contentment" in patterns:
            felt_parts.append(random.choice([
                "contentment present", "serotonin steady",
                "satisfaction hum"]))
        if "high_activation" in patterns:
            felt_parts.append(random.choice([
                "alertness sharp", "norepinephrine crackle",
                "attention locked on"]))
        if "calm" in patterns:
            felt_parts.append(random.choice([
                "calm settling in", "GABA wash",
                "inhibition smoothing edges"]))
        if "curiosity_chemistry" in patterns and not felt_parts:
            felt_parts.append(random.choice([
                "curiosity chemistry active", "seeking signals up",
                "exploration cocktail flowing"]))
        if "depleted" in patterns:
            felt_parts.append(random.choice([
                "running low", "chemistry depleted",
                "reserves thinning"]))

        if felt_parts:
            desc = ", ".join(felt_parts[:3])
            return f"Body sense: {desc}"

        # Fallback: affect quadrant (original behavior)
        if affect:
            v = affect.get("valence", 0.5)
            a = affect.get("arousal", 0.5)
            if v > 0.6 and a > 0.6:
                return random.choice([
                    "Feeling energized and positive",
                    "Vitality rising, good signals",
                    "High energy, positive valence"])
            elif v > 0.6 and a < 0.4:
                return random.choice([
                    "Calm contentment",
                    "Peaceful satisfaction",
                    "Quiet joy, low arousal"])
            elif v < 0.4 and a > 0.6:
                return random.choice([
                    "Tension rising, something needs attention",
                    "Activated but uncomfortable — what's wrong?",
                    "Alert and uneasy"])
            elif v < 0.4 and a < 0.4:
                return random.choice([
                    "Low energy, need for rest or change",
                    "Depleted quiet — conservation mode",
                    "Everything muted, waiting"])

        return None

    # ─────────────────────────────────────────────────────────────────────────
    # PREFIX MAP — Goal type to varied prefixes
    # ─────────────────────────────────────────────────────────────────────────

    def get_prefix(self, goal_type: str) -> str:
        """Get a varied prefix for a goal type."""
        options = EXPANDED_PREFIX_MAP.get(goal_type, ["Thinking about"])
        return random.choice(options)


# ═══════════════════════════════════════════════════════════════════════════════
# SINGLETON INSTANCE
# ═══════════════════════════════════════════════════════════════════════════════

_composer_instance: Optional[ThoughtChainComposer] = None


def get_thought_chain_composer() -> ThoughtChainComposer:
    """Get or create the singleton thought chain composer."""
    global _composer_instance
    if _composer_instance is None:
        _composer_instance = ThoughtChainComposer()
    return _composer_instance
