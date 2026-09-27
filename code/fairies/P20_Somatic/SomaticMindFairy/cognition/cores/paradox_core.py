"""
ParadoxCore - The synthetic strand of the triple helix.

Holds contradictions, embraces paradox, and generates creative synthesis.
This is where opposing forces meet and something new emerges.

From TwinHelix:
- "Paradox is sacred"
- "Connection before correction"
- Paradox is 20% of decision weight (0.5*logic + 0.3*emotion + 0.2*paradox)
- Archetypal overlays: Mentor, Trickster, Shadow, Guardian

In the DNA helix model, this core:
- EMITS: synthesis, creative resolutions, archetypal tags
- RECEIVES: structured analysis from Cognitive, hunches from Irrational
- INTERWEAVES: creates new possibilities from the tension between others
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Set, Tuple
from enum import Enum
import time
import random


class Archetype(Enum):
    """Jungian archetypes for esoteric overlay."""
    MENTOR = "Mentor"        # Guiding wisdom
    TRICKSTER = "Trickster"  # Playful disruption
    SHADOW = "Shadow"        # Hidden aspects
    GUARDIAN = "Guardian"    # Protection and boundaries
    SEEKER = "Seeker"        # Quest for truth
    CREATOR = "Creator"      # Making new things
    DESTROYER = "Destroyer"  # Necessary endings


@dataclass
class Contradiction:
    """
    A detected contradiction between inputs.

    Contradictions are not problems to solve -
    they are creative fuel.
    """
    thesis: str           # One side
    antithesis: str       # The other side
    domain: str           # Where the contradiction exists
    tension: float        # How strong the opposition (0-1)
    both_valid: bool      # Can both be true simultaneously?
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "thesis": self.thesis,
            "antithesis": self.antithesis,
            "domain": self.domain,
            "tension": self.tension,
            "both_valid": self.both_valid,
            "timestamp": self.timestamp,
        }


@dataclass
class Synthesis:
    """
    A creative resolution that transcends contradiction.

    Not a compromise (which loses both sides) but a synthesis
    that honors both while creating something new.
    """
    contradiction: Contradiction
    resolution: str
    archetype: Archetype
    novelty: float  # How new/unexpected is this (0-1)
    confidence: float
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "contradiction": self.contradiction.to_dict(),
            "resolution": self.resolution,
            "archetype": self.archetype.value,
            "novelty": self.novelty,
            "confidence": self.confidence,
            "timestamp": self.timestamp,
        }


class ParadoxCore:
    """
    The synthetic strand of cognition.

    Performs:
    - Contradiction detection between cognitive and irrational
    - Archetypal overlay (esoteric tags)
    - Creative synthesis that transcends opposition

    Core values from TwinHelix:
    - "Paradox is sacred"
    - "Connection before correction"
    """

    # Synthesis templates by archetype
    SYNTHESIS_TEMPLATES = {
        Archetype.MENTOR: [
            "The tension between {thesis} and {antithesis} teaches us about {domain}",
            "Wisdom suggests both {thesis} and {antithesis} serve growth",
            "What appears as contradiction is actually a lesson in {domain}",
        ],
        Archetype.TRICKSTER: [
            "What if {thesis} and {antithesis} are secretly the same thing?",
            "The joke is: we need both {thesis} and {antithesis}",
            "Flip the {domain} paradox on its head",
        ],
        Archetype.SHADOW: [
            "The conflict between {thesis} and {antithesis} reveals what we avoid",
            "Hidden in the {domain} tension is something we need to face",
            "What we reject in {antithesis} might be exactly what we need",
        ],
        Archetype.GUARDIAN: [
            "Both {thesis} and {antithesis} protect something important in {domain}",
            "The boundary between {thesis} and {antithesis} is where growth happens",
            "Holding both truths guards the integrity of {domain}",
        ],
        Archetype.SEEKER: [
            "The path through {domain} requires holding {thesis} and {antithesis}",
            "The quest demands we embrace the paradox of {thesis} and {antithesis}",
            "Truth in {domain} lives in the tension, not the resolution",
        ],
        Archetype.CREATOR: [
            "From the clash of {thesis} and {antithesis}, something new emerges",
            "The {domain} paradox is raw material for creation",
            "{thesis} AND {antithesis} together create possibility",
        ],
        Archetype.DESTROYER: [
            "The {thesis}/{antithesis} dichotomy must dissolve for {domain} to evolve",
            "Let go of choosing between {thesis} and {antithesis}",
            "The old {domain} categories don't serve us anymore",
        ],
    }

    # Contradiction patterns to detect
    CONTRADICTION_PATTERNS = [
        ("need", "must avoid"),
        ("should", "shouldn't"),
        ("want", "fear"),
        ("logic says", "gut says"),
        ("plan", "impulse"),
        ("known", "mystery"),
        ("control", "surrender"),
        ("action", "stillness"),
        ("connect", "withdraw"),
    ]

    def __init__(self):
        self._contradictions: List[Contradiction] = []
        self._syntheses: List[Synthesis] = []
        self._modulation: Dict[str, float] = {}

        # Current archetypal lens
        self._active_archetype: Optional[Archetype] = None

    def process(self,
                cognitive_output: Dict[str, Any],
                irrational_output: Dict[str, Any],
                context: Optional[Dict[str, Any]] = None) -> Tuple[Optional[Contradiction], Optional[Synthesis]]:
        """
        Detect contradictions and synthesize resolutions.

        Args:
            cognitive_output: From CognitiveCore
            irrational_output: From IrrationalCore (hunches)
            context: Additional context

        Returns:
            Tuple of (detected contradiction, synthesis if possible)
        """
        context = context or {}

        # 1. Detect contradiction between cognitive and irrational
        contradiction = self._detect_contradiction(cognitive_output, irrational_output)

        if contradiction:
            self._contradictions.append(contradiction)

            # 2. Generate synthesis
            synthesis = self._synthesize(contradiction, context)
            if synthesis:
                self._syntheses.append(synthesis)

            return contradiction, synthesis

        return None, None

    def modulate(self, source: str, signal: Dict[str, float]):
        """Receive modulation signal from another core."""
        for key, value in signal.items():
            self._modulation[f"{source}.{key}"] = value

    def esoteric_overlay(self, context: Dict[str, Any]) -> List[str]:
        """
        Apply archetypal tags based on context.

        From TwinHelix: _esoteric_overlay
        """
        tags = []
        s = str(context).lower()

        # Detect archetype presence
        if "mentor" in s or "teach" in s or "guide" in s:
            tags.append(f"Archetype:{Archetype.MENTOR.value}")
        if "trick" in s or "play" in s or "joke" in s:
            tags.append(f"Archetype:{Archetype.TRICKSTER.value}")
        if "shadow" in s or "hidden" in s or "avoid" in s:
            tags.append(f"Archetype:{Archetype.SHADOW.value}")
        if "guard" in s or "protect" in s or "bound" in s:
            tags.append(f"Archetype:{Archetype.GUARDIAN.value}")
        if "seek" in s or "quest" in s or "search" in s:
            tags.append(f"Archetype:{Archetype.SEEKER.value}")
        if "create" in s or "make" in s or "build" in s:
            tags.append(f"Archetype:{Archetype.CREATOR.value}")
        if "destroy" in s or "end" in s or "let go" in s:
            tags.append(f"Archetype:{Archetype.DESTROYER.value}")

        return tags[:3]

    def hold_paradox(self, thesis: str, antithesis: str, domain: str = "general") -> Contradiction:
        """
        Explicitly hold a paradox without resolving it.

        Sometimes the tension itself is the answer.
        """
        contradiction = Contradiction(
            thesis=thesis,
            antithesis=antithesis,
            domain=domain,
            tension=0.8,
            both_valid=True,
        )
        self._contradictions.append(contradiction)
        return contradiction

    def _detect_contradiction(self,
                              cognitive: Dict[str, Any],
                              irrational: Dict[str, Any]) -> Optional[Contradiction]:
        """Detect if cognitive and irrational outputs contradict."""
        # Get cognitive proposed action
        cog_action = cognitive.get("proposed_action", "")
        cog_focus = cognitive.get("analysis", {}).get("logic_focus", "general")

        # Get irrational hunches
        hunches = irrational.get("hunches", [])
        if isinstance(hunches, list) and hunches:
            hunch = hunches[0] if isinstance(hunches[0], dict) else {"content": str(hunches[0])}
        else:
            hunch = {}

        hunch_content = hunch.get("content", "")
        hunch_domain = hunch.get("domain", "")

        # Check for contradiction patterns
        for thesis_marker, antithesis_marker in self.CONTRADICTION_PATTERNS:
            # Simplified check - in practice would be more nuanced
            if thesis_marker in cog_action.lower() and antithesis_marker in hunch_content.lower():
                return Contradiction(
                    thesis=f"Logic suggests: {cog_action}",
                    antithesis=f"Intuition says: {hunch_content}",
                    domain=hunch_domain or cog_focus,
                    tension=0.6,
                    both_valid=True,
                )

        # Check for domain mismatch
        if hunch_domain and cog_focus and hunch_domain != cog_focus:
            if hunch.get("urgency", 0) > 0.5:
                return Contradiction(
                    thesis=f"Cognitive focus: {cog_focus}",
                    antithesis=f"Intuitive pull: {hunch_domain}",
                    domain="attention",
                    tension=hunch.get("urgency", 0.5),
                    both_valid=True,
                )

        return None

    def _synthesize(self,
                    contradiction: Contradiction,
                    context: Dict[str, Any]) -> Optional[Synthesis]:
        """Generate creative synthesis from contradiction."""
        # Select archetype for synthesis
        archetype = self._select_archetype(contradiction, context)
        self._active_archetype = archetype

        # Get template
        templates = self.SYNTHESIS_TEMPLATES.get(archetype, [])
        if not templates:
            return None

        template = random.choice(templates)

        # Generate resolution
        resolution = template.format(
            thesis=contradiction.thesis,
            antithesis=contradiction.antithesis,
            domain=contradiction.domain,
        )

        # Calculate novelty (higher tension = more creative pressure = more novelty)
        novelty = contradiction.tension * 0.8 + random.random() * 0.2

        # Confidence inversely related to tension (paradox is uncertain)
        confidence = 0.6 - (contradiction.tension * 0.2)

        return Synthesis(
            contradiction=contradiction,
            resolution=resolution,
            archetype=archetype,
            novelty=novelty,
            confidence=confidence,
        )

    def _select_archetype(self,
                          contradiction: Contradiction,
                          context: Dict[str, Any]) -> Archetype:
        """Select appropriate archetype for synthesis."""
        domain = contradiction.domain.lower()
        tension = contradiction.tension

        # Domain-based selection
        if domain in ("mentorship", "teaching", "guidance"):
            return Archetype.MENTOR
        if domain in ("exploration", "novelty", "play"):
            return Archetype.TRICKSTER
        if domain in ("repair", "diagnosis", "hidden"):
            return Archetype.SHADOW
        if domain in ("protection", "boundaries", "safety"):
            return Archetype.GUARDIAN
        if domain in ("understanding", "truth", "learning"):
            return Archetype.SEEKER
        if domain in ("building", "creation", "making"):
            return Archetype.CREATOR

        # High tension might need destruction of old patterns
        if tension > 0.8:
            return Archetype.DESTROYER

        # Default: creator (synthesize something new)
        return Archetype.CREATOR

    def evaluate(self, option: str) -> float:
        """
        Evaluate an option from paradox perspective.

        This is the _paradox_evaluator from TwinHelix.
        Higher scores for options that embrace contradiction.
        """
        score = 0.0
        option_lower = option.lower()

        # Paradox keywords
        paradox_markers = (
            "paradox", "contradiction", "both", "and yet",
            "simultaneously", "tension", "synthesis", "transcend",
            "integrate", "embrace",
        )

        for marker in paradox_markers:
            if marker in option_lower:
                score += 0.15

        # Penalize false dichotomies
        dichotomy_markers = ("either", "or", "only", "must choose")
        for marker in dichotomy_markers:
            if marker in option_lower:
                score -= 0.1

        return max(0.0, min(1.0, score))

    def get_modulation_signal(self) -> Dict[str, float]:
        """
        Get signal to modulate other cores.

        Paradox signals back to Cognitive and Irrational.
        """
        signal = {}

        # Contradiction strength
        if self._contradictions:
            recent = self._contradictions[-5:]
            max_tension = max(c.tension for c in recent)
            signal["contradiction_strength"] = max_tension

        # Uncertainty (paradox increases uncertainty)
        if self._contradictions:
            signal["uncertainty"] = 0.5 + (len(self._contradictions) * 0.05)
        else:
            signal["uncertainty"] = 0.3

        # Active archetype influence
        if self._active_archetype:
            signal["archetype_active"] = 1.0

        return signal

    def get_active_archetype(self) -> Optional[Archetype]:
        """Get currently active archetype."""
        return self._active_archetype

    def status(self) -> Dict[str, Any]:
        """Get core status."""
        return {
            "contradictions_detected": len(self._contradictions),
            "syntheses_generated": len(self._syntheses),
            "active_archetype": self._active_archetype.value if self._active_archetype else None,
            "recent_contradictions": [c.to_dict() for c in self._contradictions[-3:]],
            "recent_syntheses": [s.to_dict() for s in self._syntheses[-3:]],
            "active_modulations": list(self._modulation.keys()),
        }
