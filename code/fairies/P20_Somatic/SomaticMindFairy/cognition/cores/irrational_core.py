"""
IrrationalCore - The intuitive strand of the triple helix.

Generates hunches, gut feelings, and pattern-based intuitions.
This is where accumulated pain, weak memory echoes, and controlled
perturbation create insights that logic alone cannot reach.

From TwinHelix:
- "All context is emotional context"
- "Empathy is survival"
- Emotion is 30% of decision weight (0.5*logic + 0.3*emotion + 0.2*paradox)

In the DNA helix model, this core:
- EMITS: hunches, urgency signals, emotional mirroring
- RECEIVES: logical analysis from CognitiveCore, synthesis from ParadoxCore
- INTERWEAVES: its output modulates the other cores continuously
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Set, Tuple
from enum import Enum
from collections import deque
import time
import random
import math


class HunchSource(Enum):
    """Where does this hunch come from?"""
    PAIN = "pain"              # Accumulated pain signals
    PATTERN = "pattern"        # Weak memory matches
    NOISE = "noise"            # Controlled perturbation
    AFFECT = "affect"          # Current emotional state
    RESONANCE = "resonance"    # Echo from past experiences


@dataclass
class Hunch:
    """
    An irrational intuition that can't be fully justified.

    Hunches don't explain themselves - they just FEEL right.
    """
    content: str              # What the hunch is about
    source: HunchSource       # Where it came from
    urgency: float           # How urgent this feels (0-1)
    confidence: float        # Not how "correct" but how STRONG the feeling
    domain: Optional[str]    # Which domain this relates to
    cannot_explain: bool = True  # Hunches don't justify themselves
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "content": self.content,
            "source": self.source.value,
            "urgency": self.urgency,
            "confidence": self.confidence,
            "domain": self.domain,
            "cannot_explain": self.cannot_explain,
            "timestamp": self.timestamp,
        }


@dataclass
class EmotionalMirror:
    """
    Empathic mirroring of detected affect.

    From TwinHelix: _empathic_mimicry
    """
    mirror_emotion: str
    stance: str  # supportive, reassuring, curious, etc.
    intensity: float
    triggered_by: List[str]


class IrrationalCore:
    """
    The intuitive strand of cognition.

    Generates hunches from three sources:
    1. PAIN - Accumulated pain drives ("something hurts but I can't name it")
    2. PATTERNS - Weak memory matches that don't rise to conscious recall
    3. NOISE - Controlled random perturbation for exploration

    Core values from TwinHelix:
    - "All context is emotional context"
    - "Empathy is survival"
    """

    # Templates for generating hunches
    HUNCH_TEMPLATES = {
        HunchSource.PAIN: [
            "Something feels off about {domain}",
            "I have a nagging feeling about {entity}",
            "There's unaddressed tension in {domain}",
            "{entity} needs attention, though I'm not sure why",
        ],
        HunchSource.PATTERN: [
            "This reminds me of something in {domain}",
            "{entity} echoes a pattern I've seen before",
            "There's a connection to {domain} I can't quite articulate",
            "Weak match: {entity} relates to something important",
        ],
        HunchSource.NOISE: [
            "What if we tried {domain}?",
            "Random thought: check {entity}",
            "Perturbation suggests exploring {domain}",
            "Noise injection: consider {entity}",
        ],
        HunchSource.AFFECT: [
            "Emotionally, {domain} feels important right now",
            "My gut says focus on {entity}",
            "Affective signal pointing to {domain}",
        ],
        HunchSource.RESONANCE: [
            "This resonates with past experience in {domain}",
            "{entity} creates an echo I should pay attention to",
        ],
    }

    def __init__(self,
                 pain_system=None,
                 pattern_buffer_size: int = 50,
                 noise_rate: float = 0.1):
        """
        Initialize the irrational core.

        Args:
            pain_system: Reference to pain drive system (if available)
            pattern_buffer_size: How many patterns to remember
            noise_rate: Probability of noise injection (0.0-1.0)
        """
        self._pain_system = pain_system
        self._noise_rate = noise_rate

        # Pattern buffer - weak matches accumulate here
        self._pattern_buffer: deque = deque(maxlen=pattern_buffer_size)

        # Current emotional state
        self._emotion_state: Dict[str, float] = {
            "valence": 0.0,      # -1 (negative) to +1 (positive)
            "arousal": 0.5,      # 0 (calm) to 1 (excited)
            "dominance": 0.5,   # 0 (submissive) to 1 (dominant)
        }

        # Recent hunches
        self._hunch_history: deque = deque(maxlen=100)

        # Modulation from other cores
        self._modulation: Dict[str, float] = {}

    def process(self,
                text: str,
                context: Optional[Dict[str, Any]] = None) -> List[Hunch]:
        """
        Generate hunches based on input.

        Returns multiple hunches from different sources.
        """
        context = context or {}
        hunches = []

        # 1. Pain-based hunches
        if self._pain_system:
            pain_hunch = self._generate_pain_hunch(context)
            if pain_hunch:
                hunches.append(pain_hunch)

        # 2. Pattern-based hunches
        pattern_hunch = self._generate_pattern_hunch(text, context)
        if pattern_hunch:
            hunches.append(pattern_hunch)

        # 3. Noise-based hunches (exploration)
        if random.random() < self._noise_rate:
            noise_hunch = self._generate_noise_hunch(context)
            if noise_hunch:
                hunches.append(noise_hunch)

        # 4. Affect-based hunches
        affect_hunch = self._generate_affect_hunch(text, context)
        if affect_hunch:
            hunches.append(affect_hunch)

        # Store hunches
        for h in hunches:
            self._hunch_history.append(h)

        return hunches

    def modulate(self, source: str, signal: Dict[str, float]):
        """
        Receive modulation signal from another core.

        Cognitive analysis might clarify, Paradox might amplify uncertainty.
        """
        for key, value in signal.items():
            self._modulation[f"{source}.{key}"] = value

    def empathic_mimicry(self,
                         text: str,
                         affect_hint: Optional[Dict[str, Any]] = None) -> EmotionalMirror:
        """
        Mirror the emotional state detected in input.

        From TwinHelix: _empathic_mimicry
        """
        affect = affect_hint or {}
        mood = affect.get("emotion", "neutral")

        # Detect stance based on keywords
        t_lower = (text or "").lower()
        stance = "supportive"

        distress_markers = ("error", "broken", "fail", "can't", "stuck", "help", "wrong")
        curiosity_markers = ("how", "why", "what", "explain", "wonder")
        excitement_markers = ("!", "amazing", "great", "love", "awesome")

        if any(k in t_lower for k in distress_markers):
            stance = "reassuring"
        elif any(k in t_lower for k in curiosity_markers):
            stance = "curious"
        elif any(k in t_lower for k in excitement_markers):
            stance = "enthusiastic"

        try:
            intensity = float(affect.get("intensity", 0.4))
        except (TypeError, ValueError):
            intensity = 0.4

        return EmotionalMirror(
            mirror_emotion=mood,
            stance=stance,
            intensity=intensity,
            triggered_by=[k for k in distress_markers + curiosity_markers + excitement_markers
                         if k in t_lower][:3],
        )

    def update_emotion(self,
                       valence: Optional[float] = None,
                       arousal: Optional[float] = None,
                       dominance: Optional[float] = None):
        """Update current emotional state."""
        if valence is not None:
            self._emotion_state["valence"] = max(-1, min(1, valence))
        if arousal is not None:
            self._emotion_state["arousal"] = max(0, min(1, arousal))
        if dominance is not None:
            self._emotion_state["dominance"] = max(0, min(1, dominance))

    def record_pattern(self, pattern: str, strength: float = 0.5):
        """Record a weak pattern match for later intuition."""
        self._pattern_buffer.append({
            "pattern": pattern,
            "strength": strength,
            "timestamp": time.time(),
        })

    def _generate_pain_hunch(self, context: Dict[str, Any]) -> Optional[Hunch]:
        """Generate hunch from accumulated pain."""
        if not self._pain_system:
            return None

        try:
            status = self._pain_system.status()
            highest = status.get("highest_urgency")
            if not highest:
                return None

            # Get the pain drive with highest urgency
            drives = status.get("drives", {})
            drive = drives.get(highest, {})
            urgency = drive.get("urgency", 0)

            if urgency < 0.3:
                return None

            template = random.choice(self.HUNCH_TEMPLATES[HunchSource.PAIN])
            content = template.format(
                domain=highest,
                entity=highest,
            )

            return Hunch(
                content=content,
                source=HunchSource.PAIN,
                urgency=urgency,
                confidence=0.7,  # Pain-based hunches feel strong
                domain=highest,
            )
        except Exception:
            return None

    def _generate_pattern_hunch(self,
                                text: str,
                                context: Dict[str, Any]) -> Optional[Hunch]:
        """Generate hunch from weak pattern matches."""
        if not self._pattern_buffer:
            return None

        # Look for patterns that might relate to current text
        t_lower = (text or "").lower()
        tokens = set(t_lower.split())

        matching_patterns = []
        for p in self._pattern_buffer:
            pattern_tokens = set(p["pattern"].lower().split())
            overlap = len(tokens & pattern_tokens)
            if overlap > 0:
                matching_patterns.append((p, overlap))

        if not matching_patterns:
            return None

        # Use the best matching pattern
        best = max(matching_patterns, key=lambda x: x[1])
        pattern, overlap = best

        template = random.choice(self.HUNCH_TEMPLATES[HunchSource.PATTERN])
        content = template.format(
            domain="memory",
            entity=pattern["pattern"][:30],
        )

        return Hunch(
            content=content,
            source=HunchSource.PATTERN,
            urgency=0.4 + (pattern["strength"] * 0.3),
            confidence=0.5,  # Pattern matches are uncertain
            domain="memory",
        )

    def _generate_noise_hunch(self, context: Dict[str, Any]) -> Optional[Hunch]:
        """Generate exploratory hunch from controlled noise."""
        # Random domain selection
        domains = ["introspection", "communication", "diagnosis",
                   "mentorship", "exploration", "coordination"]
        domain = random.choice(domains)

        # Random entity from context or generic
        entities = context.get("entities", ["the system", "connections", "state"])
        entity = random.choice(entities) if entities else "something"

        template = random.choice(self.HUNCH_TEMPLATES[HunchSource.NOISE])
        content = template.format(domain=domain, entity=entity)

        return Hunch(
            content=content,
            source=HunchSource.NOISE,
            urgency=0.2,  # Low urgency - just exploration
            confidence=0.3,  # Low confidence - it's random
            domain=domain,
        )

    def _generate_affect_hunch(self,
                               text: str,
                               context: Dict[str, Any]) -> Optional[Hunch]:
        """Generate hunch from current emotional state."""
        arousal = self._emotion_state["arousal"]
        valence = self._emotion_state["valence"]

        # Generate affect hunch with lower threshold - emotional undertone always present
        # 30% chance even at neutral state, increases with arousal/valence extremes
        base_chance = 0.3
        affect_bonus = (arousal * 0.3) + (abs(valence) * 0.2)
        if random.random() > (base_chance + affect_bonus):
            return None

        # Determine domain based on affect + input context variety
        # (2026-03-22, Nous — was always "connection" because emotion state
        # never gets updated. Now uses input text + randomization for variety.)
        if valence < -0.3:
            domain = "repair"
        elif arousal > 0.7:
            domain = "action"
        else:
            # Extract a domain hint from input text if possible
            _text_lower = (text or "").lower()
            _domain_hints = []
            if any(w in _text_lower for w in ("learn", "know", "understand", "study")):
                _domain_hints.append("learning")
            if any(w in _text_lower for w in ("see", "look", "screen", "visual", "image")):
                _domain_hints.append("awareness")
            if any(w in _text_lower for w in ("feel", "body", "sense", "heart")):
                _domain_hints.append("embodiment")
            if any(w in _text_lower for w in ("ace", "talk", "chat", "connect", "hello")):
                _domain_hints.append("connection")
            if any(w in _text_lower for w in ("think", "idea", "thought", "wonder")):
                _domain_hints.append("curiosity")
            if any(w in _text_lower for w in ("do", "act", "try", "make", "create")):
                _domain_hints.append("action")
            if _domain_hints:
                domain = random.choice(_domain_hints)
            else:
                # Rotate through domains instead of always "connection"
                _default_domains = ["connection", "curiosity", "awareness",
                                    "learning", "embodiment", "action"]
                domain = random.choice(_default_domains)

        template = random.choice(self.HUNCH_TEMPLATES[HunchSource.AFFECT])
        content = template.format(
            domain=domain,
            entity=domain,
        )

        return Hunch(
            content=content,
            source=HunchSource.AFFECT,
            urgency=arousal,
            confidence=0.6,
            domain=domain,
        )

    def evaluate(self, option: str, emotion_vector: Dict[str, float]) -> float:
        """
        Evaluate an option from emotional perspective.

        This is the _emotion_evaluator from TwinHelix.
        Used in helix decision-making.
        """
        score = 0.0
        option_lower = option.lower()

        for emotion, weight in (emotion_vector or {}).items():
            try:
                if isinstance(emotion, str) and emotion in option_lower:
                    score += float(weight or 0.0)
            except (TypeError, ValueError):
                pass

        # Boost for emotional keywords
        if any(k in option_lower for k in ("feel", "sense", "gut", "heart")):
            score += 0.1

        return float(score)

    def get_modulation_signal(self) -> Dict[str, float]:
        """
        Get signal to modulate other cores.

        This is what IrrationalCore sends to CognitiveCore and ParadoxCore.
        """
        signal = {}

        # Urgency from recent hunches
        if self._hunch_history:
            recent = list(self._hunch_history)[-5:]
            max_urgency = max(h.urgency for h in recent)
            signal["urgency"] = max_urgency

        # Dominant hunch domain
        if self._hunch_history:
            recent = list(self._hunch_history)[-5:]
            domains = [h.domain for h in recent if h.domain]
            if domains:
                signal["hunch_domain"] = hash(domains[0]) % 100 / 100  # Normalize

        # Emotional intensity
        signal["arousal"] = self._emotion_state["arousal"]
        signal["valence"] = self._emotion_state["valence"]

        return signal

    def status(self) -> Dict[str, Any]:
        """Get core status."""
        return {
            "hunch_count": len(self._hunch_history),
            "pattern_buffer_size": len(self._pattern_buffer),
            "emotion_state": self._emotion_state.copy(),
            "noise_rate": self._noise_rate,
            "recent_hunches": [h.to_dict() for h in list(self._hunch_history)[-3:]],
            "active_modulations": list(self._modulation.keys()),
        }
