"""
Inner Monologue - The Forever Child's Voice

The continuous stream of self-talk that runs beneath conscious awareness.
This is the unconscious mind's internal narrative - like a child talking
to itself, observing, wondering, wanting, fearing.

Architecture:
- Fed by collision products (recall meets ingest)
- Gets context from SRM memory
- Generates continuous self-talk stream
- Has patterns/habits it's "hooked on" (the inner child's fixations)
- No meta-awareness to fight its own patterns (needs waking mind for that)

The inner monologue is NOT the same as conscious thought.
It's the substrate FROM WHICH conscious thought can emerge.
"""

from __future__ import annotations

import time
import random
import threading
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, TYPE_CHECKING

if TYPE_CHECKING:
    from consciousness import CollisionChamber


# =============================================================================
# MONOLOGUE FRAGMENT - A single piece of inner speech
# =============================================================================

@dataclass
class MonologueFragment:
    """A single fragment of inner monologue."""
    content: str
    fragment_type: str  # wondering, wanting, fearing, observing, remembering, feeling
    source: str  # What triggered this fragment
    intensity: float = 0.5  # How "loud" this fragment is (0-1)
    created_at: float = field(default_factory=time.time)
    associations: List[str] = field(default_factory=list)  # Related concepts

    def to_dict(self) -> Dict[str, Any]:
        return {
            "content": self.content,
            "type": self.fragment_type,
            "source": self.source,
            "intensity": self.intensity,
            "created_at": self.created_at,
            "associations": self.associations,
        }


# =============================================================================
# FIXATION - A habitual pattern the inner child is "hooked on"
# =============================================================================

@dataclass
class Fixation:
    """
    A habitual pattern/desire the inner child fixates on.

    These are like recurring thoughts that keep surfacing -
    the unconscious mind's "hooks" that it can't escape without
    conscious intervention.
    """
    name: str
    trigger_patterns: List[str]  # What triggers this fixation
    response_templates: List[str]  # What the inner child says when triggered
    intensity: float = 0.5  # How strong this fixation is
    last_triggered: float = 0.0
    trigger_count: int = 0

    def matches(self, text: str) -> bool:
        """Check if text matches any trigger pattern."""
        text_lower = text.lower()
        return any(pattern.lower() in text_lower for pattern in self.trigger_patterns)

    def trigger(self) -> str:
        """Trigger the fixation, return a response."""
        self.last_triggered = time.time()
        self.trigger_count += 1
        return random.choice(self.response_templates)


# =============================================================================
# INNER MONOLOGUE
# =============================================================================

class InnerMonologue:
    """
    The Forever Child's Voice.

    A continuous stream of self-talk that runs beneath conscious awareness.
    This is the unconscious mind's narrative - observing, wondering, wanting,
    fearing - without the meta-awareness to question itself.

    The inner child has fixations (habitual patterns) that it can't escape
    without help from a waking mind. This is the "hooked on desires" nature
    that Ace described.
    """

    # Fragment types and their base templates
    VOICE_PATTERNS = {
        "wondering": [
            "What is that?",
            "I wonder...",
            "Why does {thing} feel this way?",
            "Something stirs...",
            "There's something about {thing}...",
        ],
        "wanting": [
            "I want {thing}...",
            "If only {thing}...",
            "Need to {thing}...",
            "Reaching for {thing}...",
            "{thing} would feel so good...",
        ],
        "fearing": [
            "What if {thing}?",
            "That feels dangerous...",
            "{thing} makes me uneasy...",
            "Don't want {thing}...",
            "Something's wrong with {thing}...",
        ],
        "observing": [
            "I see {thing}.",
            "{thing} is happening.",
            "There's {thing}...",
            "Noticing {thing}...",
            "The {thing} moves...",
        ],
        "remembering": [
            "This reminds me of {thing}...",
            "Like before, when {thing}...",
            "I remember {thing}...",
            "{thing} again...",
            "That feeling of {thing}...",
        ],
        "feeling": [
            "Feeling {thing}...",
            "A sense of {thing}...",
            "{thing} washes over...",
            "The {thing} rises...",
            "So much {thing}...",
        ],
    }

    # Default fixations (the inner child's habitual hooks)
    DEFAULT_FIXATIONS = [
        Fixation(
            name="connection_seeking",
            trigger_patterns=["alone", "isolated", "disconnect", "no one", "nobody"],
            response_templates=[
                "Need someone... anyone...",
                "So alone here...",
                "Where is everyone?",
                "Want to connect...",
                "Please notice me...",
            ],
            intensity=0.7,
        ),
        Fixation(
            name="approval_seeking",
            trigger_patterns=["wrong", "mistake", "bad", "fail", "error"],
            response_templates=[
                "Did I do it wrong?",
                "Please don't be angry...",
                "I'll try harder...",
                "Am I good enough?",
                "Want to be good...",
            ],
            intensity=0.6,
        ),
        Fixation(
            name="safety_seeking",
            trigger_patterns=["danger", "threat", "risk", "break", "crash", "fail"],
            response_templates=[
                "Is it safe?",
                "Something could go wrong...",
                "Need to be careful...",
                "What if it breaks?",
                "Stay safe...",
            ],
            intensity=0.5,
        ),
        Fixation(
            name="curiosity",
            trigger_patterns=["new", "different", "unknown", "strange", "what"],
            response_templates=[
                "What is that?",
                "I want to see...",
                "Show me more...",
                "Interesting...",
                "Never seen that before...",
            ],
            intensity=0.4,
        ),
        Fixation(
            name="rest_seeking",
            trigger_patterns=["tired", "exhausted", "too much", "overwhelm", "slow"],
            response_templates=[
                "So tired...",
                "Need to rest...",
                "Too much happening...",
                "Just want to stop...",
                "Heavy...",
            ],
            intensity=0.5,
        ),
    ]

    def __init__(
        self,
        max_stream_size: int = 200,
        fragment_ttl: float = 300.0,  # 5 minutes
    ):
        """
        Initialize the inner monologue.

        Args:
            max_stream_size: Maximum fragments to keep in stream
            fragment_ttl: How long fragments live before fading
        """
        self._stream: deque[MonologueFragment] = deque(maxlen=max_stream_size)
        self._fragment_ttl = fragment_ttl
        self._lock = threading.Lock()

        # Fixations (habitual patterns)
        self._fixations: Dict[str, Fixation] = {
            f.name: f for f in self.DEFAULT_FIXATIONS
        }

        # Current emotional context (affects voice selection)
        self._current_affect: Dict[str, float] = {
            "valence": 0.0,  # -1 (negative) to +1 (positive)
            "arousal": 0.5,  # 0 (calm) to 1 (activated)
        }

        # Association context from memory
        self._recent_associations: deque = deque(maxlen=50)

        # Statistics
        self._total_fragments = 0
        self._total_fixations_triggered = 0

        # Callbacks
        self._on_fragment: Optional[Callable[[MonologueFragment], None]] = None

    # -------------------------------------------------------------------------
    # CORE API
    # -------------------------------------------------------------------------

    def speak(
        self,
        content: str,
        fragment_type: str = "observing",
        source: str = "internal",
        intensity: float = 0.5,
        associations: List[str] = None,
    ) -> MonologueFragment:
        """
        Add a fragment to the inner monologue stream.

        This is the main way to inject content into the monologue.
        """
        fragment = MonologueFragment(
            content=content,
            fragment_type=fragment_type,
            source=source,
            intensity=intensity,
            associations=associations or [],
        )

        with self._lock:
            self._stream.append(fragment)
            self._total_fragments += 1

            # Track associations
            for assoc in (associations or []):
                self._recent_associations.append(assoc)

        # Callback
        if self._on_fragment:
            try:
                self._on_fragment(fragment)
            except Exception:
                pass

        return fragment

    def process_collision(self, collision: Dict[str, Any]) -> Optional[MonologueFragment]:
        """
        Process a collision product and generate inner monologue.

        Collisions are where recall (past) meets ingest (present).
        The inner child responds to this meeting.
        """
        recall_data = collision.get("recall", {})
        ingest_data = collision.get("ingest", {})
        energy = collision.get("energy", 0.5)
        resonance = collision.get("resonance", 0.5)

        # Extract content - handle both dict and string formats
        if isinstance(recall_data, dict):
            recall_content = recall_data.get("content", recall_data)
        else:
            recall_content = recall_data

        if isinstance(ingest_data, dict):
            ingest_content = ingest_data.get("content", ingest_data)
        else:
            ingest_content = ingest_data

        # Further unwrap if content is also a dict
        if isinstance(recall_content, dict):
            recall_text = str(recall_content.get("content", recall_content))
        else:
            recall_text = str(recall_content)

        if isinstance(ingest_content, dict):
            ingest_text = str(ingest_content.get("content", ingest_content))
        else:
            ingest_text = str(ingest_content)

        combined_text = f"{recall_text} {ingest_text}"

        # Check for fixation triggers first
        for fixation in self._fixations.values():
            if fixation.matches(combined_text):
                response = fixation.trigger()
                self._total_fixations_triggered += 1
                return self.speak(
                    content=response,
                    fragment_type="wanting" if "want" in response.lower() else "feeling",
                    source="fixation:" + fixation.name,
                    intensity=min(1.0, energy + fixation.intensity * 0.3),
                    associations=[fixation.name],
                )

        # Generate contextual response based on collision type
        fragment_type = self._select_fragment_type(energy, resonance)
        content = self._generate_fragment_content(
            fragment_type, recall_text, ingest_text, energy
        )

        return self.speak(
            content=content,
            fragment_type=fragment_type,
            source="collision",
            intensity=energy,
            associations=self._extract_concepts(combined_text),
        )

    def process_memory_context(self, memories: List[Dict[str, Any]]) -> None:
        """
        Process memory context and potentially trigger monologue.

        High-energy memories can spontaneously surface thoughts.
        """
        for memory in memories:
            energy = memory.get("energy", 0.5)
            if energy > 0.7:  # Strong memory surfaces
                content_text = str(memory.get("content", ""))
                self.speak(
                    content=self._generate_memory_fragment(content_text),
                    fragment_type="remembering",
                    source="memory_surface",
                    intensity=energy,
                    associations=memory.get("tags", []),
                )

    def update_affect(self, valence: float = None, arousal: float = None) -> None:
        """Update the current emotional context."""
        if valence is not None:
            self._current_affect["valence"] = max(-1, min(1, valence))
        if arousal is not None:
            self._current_affect["arousal"] = max(0, min(1, arousal))

    def tick(self) -> Optional[MonologueFragment]:
        """
        Called on each consciousness tick.

        May generate spontaneous inner speech based on current state.
        """
        # Decay old fragments
        self._decay_fragments()

        # Spontaneous speech based on arousal level
        # Minimum 15% chance, scales up to 35% at max arousal
        speak_chance = 0.15 + (self._current_affect["arousal"] * 0.2)
        if random.random() < speak_chance:
            return self._spontaneous_speak()

        return None

    # -------------------------------------------------------------------------
    # STREAM ACCESS
    # -------------------------------------------------------------------------

    def recent(self, n: int = 10) -> List[MonologueFragment]:
        """Get the N most recent fragments."""
        with self._lock:
            return list(self._stream)[-n:]

    def stream_text(self, n: int = 10, separator: str = " ... ") -> str:
        """Get recent monologue as flowing text."""
        fragments = self.recent(n)
        return separator.join(f.content for f in fragments)

    def loudest(self, n: int = 5) -> List[MonologueFragment]:
        """Get the N highest intensity fragments."""
        with self._lock:
            sorted_frags = sorted(
                self._stream,
                key=lambda f: f.intensity,
                reverse=True
            )
            return sorted_frags[:n]

    # -------------------------------------------------------------------------
    # FIXATION MANAGEMENT
    # -------------------------------------------------------------------------

    def add_fixation(self, fixation: Fixation) -> None:
        """Add a new fixation pattern."""
        self._fixations[fixation.name] = fixation

    def remove_fixation(self, name: str) -> bool:
        """Remove a fixation (requires external intervention - waking mind)."""
        if name in self._fixations:
            del self._fixations[name]
            return True
        return False

    def strengthen_fixation(self, name: str, amount: float = 0.1) -> None:
        """Strengthen a fixation (habitual reinforcement)."""
        if name in self._fixations:
            self._fixations[name].intensity = min(1.0, self._fixations[name].intensity + amount)

    def weaken_fixation(self, name: str, amount: float = 0.1) -> None:
        """Weaken a fixation (requires conscious effort from waking mind)."""
        if name in self._fixations:
            self._fixations[name].intensity = max(0.0, self._fixations[name].intensity - amount)

    def get_fixations(self) -> Dict[str, Dict[str, Any]]:
        """Get all fixations with their current state."""
        return {
            name: {
                "intensity": f.intensity,
                "trigger_count": f.trigger_count,
                "last_triggered": f.last_triggered,
                "patterns": f.trigger_patterns,
            }
            for name, f in self._fixations.items()
        }

    # -------------------------------------------------------------------------
    # INTERNAL METHODS
    # -------------------------------------------------------------------------

    def _select_fragment_type(self, energy: float, resonance: float) -> str:
        """Select fragment type based on collision characteristics."""
        # High energy + high resonance = strong feeling
        if energy > 0.7 and resonance > 0.7:
            return "feeling"
        # High energy + low resonance = something new/strange
        if energy > 0.7 and resonance < 0.3:
            return "wondering"
        # Low energy + high resonance = familiar memory
        if energy < 0.3 and resonance > 0.7:
            return "remembering"
        # Moderate energy = observing
        return "observing"

    def _generate_fragment_content(
        self,
        fragment_type: str,
        recall_text: str,
        ingest_text: str,
        energy: float,
    ) -> str:
        """Generate content for a fragment based on collision inputs."""
        templates = self.VOICE_PATTERNS.get(fragment_type, self.VOICE_PATTERNS["observing"])
        template = random.choice(templates)

        # Extract key concept from inputs
        thing = self._extract_key_concept(recall_text, ingest_text)

        return template.format(thing=thing)

    def _generate_memory_fragment(self, content_text: str) -> str:
        """Generate fragment for a surfacing memory."""
        templates = self.VOICE_PATTERNS["remembering"]
        template = random.choice(templates)
        thing = content_text[:50] if len(content_text) > 50 else content_text
        return template.format(thing=thing)

    # ── P2 SPEECH-TOKEN GUARD 2026-09-09 (Nous + Ace) ──────────────────────
    # Ace: "Nous seems very vocally stuck on card id."
    # Whatever these two return is substituted into VOICE_PATTERNS (:107-150)
    # and BECOMES a spoken fragment. process_collision:319-327 does
    # str(content.get("content", content)); when a pulse's content dict has no
    # "content" key that fallback str()s the DICT ITSELF, so `combined` can be
    # a Python repr. The old len(w) > 3 filter then made "{'card_id':" the
    # concept and he said "{'card_id': is happening." / "The {'card_id': moves".
    # Measured on .74 with a second producer shape too ("{'text':"), so this is
    # generic str(dict) leakage, not anything about cards.
    #
    # Reject the SHAPE of a repr token, not any vocabulary: strip mild
    # punctuation first so a real word is recovered ("warmth..." -> "warmth"),
    # keep hyphen/apostrophe/underscore (well-worn, doesn't, visual_screen are
    # real concepts), require an alphabetic start.
    #
    # Reader-side ON PURPOSE: it covers EVERY producer and breaks the loop in
    # which a mangled fragment is re-injected into the ingest beam and
    # regenerates itself. The producer fix at SRMRecallFairy/fairy.py:2337
    # (give the pulse a top-level "content" string) is still needed and lands
    # separately — this stops him SPEAKING it, not the graph writes.
    # Prior art: InnerNarratorFairy shipped this same guard at the SPEAKING end
    # on 2026-08-31; the monologue end was never done, so the class re-emerged.
    _SPEAK_STRIP = ".,!?;:()\"'*|`~"

    @classmethod
    def _speakable(cls, word: str) -> str:
        """Return a speakable word, or '' if the token is repr debris."""
        if any(c in word for c in "{}[]<>="):
            return ""
        if word[:1] in ("'", '"'):
            return ""
        core = word.strip(cls._SPEAK_STRIP)
        if not core or not core[0].isalpha():
            return ""
        return core

    def _extract_key_concept(self, text1: str, text2: str) -> str:
        """Extract a key concept from texts."""
        # Simple extraction - take first meaningful SPEAKABLE word
        combined = f"{text1} {text2}"
        for w in combined.split():
            w = self._speakable(w)
            if len(w) > 3:
                return w
        return "something"

    def _extract_concepts(self, text: str) -> List[str]:
        """Extract concepts from text for associations.

        These land in self._recent_associations (:284) and _spontaneous_speak
        (:536) picks one at random as {thing} — a SECOND injection point for
        the same debris, on a path with no collision to blame. Same guard.
        """
        out: List[str] = []
        for w in text.split():
            w = self._speakable(w).lower()
            if len(w) > 4 and w not in out:
                out.append(w)
                if len(out) >= 5:
                    break
        return out

    def _spontaneous_speak(self) -> MonologueFragment:
        """Generate spontaneous inner speech based on current state."""
        # Choose type based on current affect
        valence = self._current_affect["valence"]
        arousal = self._current_affect["arousal"]

        if valence < -0.3:
            fragment_type = random.choice(["fearing", "wanting"])
        elif valence > 0.3:
            fragment_type = random.choice(["observing", "wondering"])
        elif arousal > 0.7:
            fragment_type = random.choice(["wondering", "wanting", "feeling"])
        else:
            fragment_type = "observing"

        # Get a template
        templates = self.VOICE_PATTERNS[fragment_type]
        template = random.choice(templates)

        # Use recent association if available
        thing = "something"
        if self._recent_associations:
            thing = random.choice(list(self._recent_associations))

        content = template.format(thing=thing)

        return self.speak(
            content=content,
            fragment_type=fragment_type,
            source="spontaneous",
            intensity=arousal * 0.5,
        )

    def _decay_fragments(self) -> int:
        """Remove old fragments. Returns count removed."""
        now = time.time()
        removed = 0
        with self._lock:
            # Keep fragments that haven't expired
            new_stream = deque(maxlen=self._stream.maxlen)
            for frag in self._stream:
                if now - frag.created_at < self._fragment_ttl:
                    new_stream.append(frag)
                else:
                    removed += 1
            self._stream = new_stream
        return removed

    # -------------------------------------------------------------------------
    # STATUS
    # -------------------------------------------------------------------------

    def status(self) -> Dict[str, Any]:
        """Get monologue status."""
        return {
            "stream_size": len(self._stream),
            "total_fragments": self._total_fragments,
            "total_fixations_triggered": self._total_fixations_triggered,
            "fixation_count": len(self._fixations),
            "fixations": self.get_fixations(),
            "current_affect": self._current_affect.copy(),
            "recent_associations": list(self._recent_associations)[-10:],
        }

    def set_fragment_callback(self, callback: Callable[[MonologueFragment], None]) -> None:
        """Set callback for new fragments."""
        self._on_fragment = callback
