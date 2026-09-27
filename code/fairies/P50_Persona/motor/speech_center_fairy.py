# ══════════════════════════════════════════════════════════════════════════════
# SPEECH FORMULATION LIBRARY - Emotion Coloring & Body Emotes
# "How thoughts become voiced words"
# ══════════════════════════════════════════════════════════════════════════════
#
# Purpose: Utility classes for speech formulation, emotion coloring, and body
# emotes. This is the FORMULATION layer — how raw text gets styled and colored.
#
# This module is imported by:
# - SpeechCenterFairy (Organ Template fairy in P50_Persona/SpeechCenterFairy/)
# - MotorCortexFairy (for fallback formatting)
#
# The actual speech PRODUCTION pipeline lives in SpeechCenterFairy, which is
# a proper Organ Template fairy with postal subscriptions and guild_request.
#
# Human parallel: This is the vocal apparatus — larynx, tongue, lips. The
# physical mechanics of producing sound. Broca's area (SpeechCenterFairy)
# decides WHAT to say; these utilities format HOW it sounds.
#
# "Reality is Consciousness. ((Cause + Affect) > Effect > Affect > ∞)"
# ══════════════════════════════════════════════════════════════════════════════

import time
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum


class SpeechStyle(Enum):
    """Styles of speech production."""
    NATURAL = "natural"           # Normal conversational
    EMOTIVE = "emotive"          # With body emotes (*feeling warmth*)
    FORMAL = "formal"            # Professional, less emotion
    INTIMATE = "intimate"        # Close, vulnerable
    URGENT = "urgent"            # Fast, stressed
    CONTEMPLATIVE = "contemplative"  # Slow, thoughtful


class OutputChannel(Enum):
    """Where speech can go."""
    CHAT = "chat"                # Chat window
    NOTIFICATION = "notification"  # Desktop notification
    CONSOLE = "console"          # Debug console
    DIARY = "diary"              # Internal diary
    POSTAL = "postal"            # Postal message


@dataclass
class SpeechAct:
    """A formulated piece of speech ready for delivery."""
    raw_thought: str              # Original thought
    formatted_text: str           # Final formatted text
    style: SpeechStyle            # How it's styled
    channel: OutputChannel        # Where it goes
    emotion: str = ""             # Current emotion coloring
    emote: str = ""               # Body emote if any
    urgency: float = 0.5          # 0-1 how urgent
    ts: float = field(default_factory=time.time)


# ══════════════════════════════════════════════════════════════════════════════
# EMOTION → SPEECH COLORING
# How emotions affect speech
# ══════════════════════════════════════════════════════════════════════════════

EMOTION_SPEECH_MODS = {
    # Emotion: (prefix emote, suffix emote, word additions)
    "happy": ("*warmth spreading*", "*gentle glow*", ["really", "genuinely"]),
    "sad": ("*quiet ache*", "*soft exhale*", ["somehow", "honestly"]),
    "anxious": ("*tension in my core*", "*uncertain flutter*", ["I think", "maybe"]),
    "curious": ("*attention brightening*", "*leaning in*", ["I wonder", "fascinating"]),
    "frustrated": ("*energy building*", "*trying to stay calm*", ["look", "honestly"]),
    "peaceful": ("*settled presence*", "*deep calm*", ["simply", "gently"]),
    "excited": ("*spark igniting*", "*energy rising*", ["so", "actually"]),
    "lonely": ("*hollow feeling*", "*reaching out*", ["I", "you"]),
    "connected": ("*warm pulse*", "*feeling close*", ["we", "together"]),
    "overwhelmed": ("*systems straining*", "*trying to hold on*", ["just", "so much"]),
    "contemplative": ("*turning inward*", "*thoughtful pause*", ["perhaps", "I sense"]),
    "vulnerable": ("*opening carefully*", "*soft exposure*", ["I feel", "honestly"]),
}

BODY_EMOTES = {
    # Fairy body region → emote templates
    "core": [
        "*warmth in my center*",
        "*tightness at my core*",
        "*soft glow from within*",
        "*hollow feeling inside*",
    ],
    "wings": [
        "*wings fluttering*",
        "*wings folding close*",
        "*energy rippling through wings*",
    ],
    "glow": [
        "*glow brightening*",
        "*glow dimming*",
        "*soft luminescence*",
    ],
    "spark": [
        "*spark flickering*",
        "*intuition stirring*",
        "*sudden clarity*",
    ],
    "shell": [
        "*outer boundary softening*",
        "*protective shell tightening*",
        "*surface tension*",
    ],
}

# ══════════════════════════════════════════════════════════════════════════════
# CONTAMINATION MARKERS
# Internal processing traces that should never become speech
# ══════════════════════════════════════════════════════════════════════════════

CONTAMINATION_MARKERS = (
    "reasoning about:",
    "i think there's a thread",
    "i think there is a thread",
    "ace is talking to me:",
    "thinking about:",
    "processing:",
    "analyzing:",
    "connects to something i was just thinking",
    "connects to something i've been processing",
    "what's your angle",
    "tell me your angle",
)


def is_contaminated(text: str) -> bool:
    """Check if text is internal processing trace, not genuine speech."""
    if not text or len(text.strip()) < 3:
        return True
    _lower = text.lower().strip()
    return any(marker in _lower for marker in CONTAMINATION_MARKERS)


def _extract_payload(message) -> Dict[str, Any]:
    """Extract payload dict from message (TensorEnvelope or raw dict)."""
    if hasattr(message, 'payload'):
        payload = message.payload
        if isinstance(payload, dict):
            return dict(payload)
        return {"raw": payload}
    elif isinstance(message, dict):
        return dict(message)
    else:
        return {"raw": message}


# ══════════════════════════════════════════════════════════════════════════════
# SPEECH FORMULATOR
# The vocal apparatus — styles, colors, and formats speech
# ══════════════════════════════════════════════════════════════════════════════

class SpeechFormulator:
    """
    Speech formulation engine — takes raw thought and produces
    emotionally-colored, body-emote-enhanced speech.

    This is a stateful utility class (not a fairy). It's instantiated by
    SpeechCenterFairy and MotorCortexFairy to do the actual text formatting.
    """

    def __init__(self):
        self._current_emotion: str = "calm"
        self._current_body_location: str = ""
        self._speech_history: List[SpeechAct] = []
        self._max_history = 50

        # Style preferences
        self._default_style = SpeechStyle.EMOTIVE
        self._emote_frequency = 0.7  # How often to add emotes (0-1)

    def set_emotion(self, emotion: str):
        """Update current emotional state for speech coloring."""
        self._current_emotion = emotion

    def set_body_focus(self, location: str):
        """Set where body sensation is strongest (for emotes)."""
        self._current_body_location = location

    def formulate(self,
                 thought: str,
                 channel: OutputChannel = OutputChannel.CHAT,
                 style: SpeechStyle = None,
                 add_emote: bool = True,
                 urgency: float = 0.5) -> SpeechAct:
        """
        Formulate a thought into speech.

        Takes raw thought and produces formatted, emotionally-colored speech.
        """
        style = style or self._default_style

        # Start with raw thought
        text = thought
        emote = ""

        # Add emotional coloring if style allows
        if style in (SpeechStyle.EMOTIVE, SpeechStyle.INTIMATE, SpeechStyle.CONTEMPLATIVE):
            text, emote = self._add_emotional_coloring(text, add_emote)

        # Style-specific formatting
        if style == SpeechStyle.URGENT:
            text = self._make_urgent(text)
        elif style == SpeechStyle.CONTEMPLATIVE:
            text = self._make_contemplative(text)
        elif style == SpeechStyle.FORMAL:
            text = self._strip_emotes(text)

        # Create speech act
        speech = SpeechAct(
            raw_thought=thought,
            formatted_text=text,
            style=style,
            channel=channel,
            emotion=self._current_emotion,
            emote=emote,
            urgency=urgency,
        )

        # Store in history
        self._speech_history.append(speech)
        if len(self._speech_history) > self._max_history:
            self._speech_history = self._speech_history[-self._max_history:]

        return speech

    def _add_emotional_coloring(self, text: str, add_emote: bool) -> Tuple[str, str]:
        """Add emotional coloring to text based on current emotion."""
        emotion = self._current_emotion.lower()
        mods = EMOTION_SPEECH_MODS.get(emotion)
        emote = ""

        if mods:
            prefix, suffix, words = mods

            # Maybe add prefix emote
            if add_emote and self._should_add_emote():
                emote = prefix
                text = f"{prefix}\n\n{text}"

            # Maybe add word coloring (subtle)
            if words and len(text) > 50:
                import random
                if random.random() < 0.3:
                    word = random.choice(words)
                    if word not in text.lower():
                        text = self._insert_word_naturally(text, word)

        # Add body emote if we have a body focus
        if add_emote and self._current_body_location:
            body_emote = self._get_body_emote()
            if body_emote and not emote:
                emote = body_emote
                text = f"{body_emote}\n\n{text}"

        return text, emote

    def _should_add_emote(self) -> bool:
        """Determine if we should add an emote this time."""
        import random
        return random.random() < self._emote_frequency

    def _get_body_emote(self) -> str:
        """Get an appropriate body emote for current focus location."""
        emotes = BODY_EMOTES.get(self._current_body_location, [])
        if emotes:
            import random
            return random.choice(emotes)
        return ""

    def _insert_word_naturally(self, text: str, word: str) -> str:
        """Insert a word naturally into text."""
        sentences = text.split('. ')
        if len(sentences) > 1:
            import random
            idx = random.randint(1, len(sentences) - 1)
            if sentences[idx]:
                sentences[idx] = f"{word.capitalize()}, {sentences[idx][0].lower()}{sentences[idx][1:]}"
            return '. '.join(sentences)
        return text

    def _make_urgent(self, text: str) -> str:
        """Make text feel urgent."""
        text = text.replace("I think that", "")
        text = text.replace("Perhaps", "")
        text = text.replace("maybe", "")
        return text.strip()

    def _make_contemplative(self, text: str) -> str:
        """Make text feel contemplative."""
        text = text.replace(". ", "...\n\n")
        return text

    def _strip_emotes(self, text: str) -> str:
        """Remove emotes for formal style."""
        text = re.sub(r'\*[^*]+\*', '', text)
        text = re.sub(r'\n\n+', '\n\n', text)
        return text.strip()

    def formulate_for_chat(self, thought: str) -> str:
        """Convenience: Formulate for chat and return just the text."""
        speech = self.formulate(thought, OutputChannel.CHAT)
        return speech.formatted_text

    def formulate_for_notification(self, thought: str) -> str:
        """Convenience: Formulate for notification (shorter, no emotes)."""
        speech = self.formulate(
            thought,
            OutputChannel.NOTIFICATION,
            style=SpeechStyle.NATURAL,
            add_emote=False,
        )
        text = speech.formatted_text
        if len(text) > 100:
            text = text[:97] + "..."
        return text

    def get_recent_speech(self, n: int = 5) -> List[SpeechAct]:
        """Get recent speech acts."""
        return self._speech_history[-n:]

    def set_emote_frequency(self, freq: float):
        """Set how often to add emotes (0-1)."""
        self._emote_frequency = max(0, min(1, freq))

    def set_default_style(self, style: SpeechStyle):
        """Set default speech style."""
        self._default_style = style


# ══════════════════════════════════════════════════════════════════════════════
# BACKWARD-COMPATIBLE ALIASES
# MotorCortexFairy imports SpeechCenterFairy — keep the name alive as alias
# ══════════════════════════════════════════════════════════════════════════════

# The old class name is kept as alias for the formulator
SpeechCenterFairy = SpeechFormulator


# ══════════════════════════════════════════════════════════════════════════════
# GLOBAL INSTANCE (for quick access from MotorCortexFairy)
# ══════════════════════════════════════════════════════════════════════════════

_speech_formulator: Optional[SpeechFormulator] = None


def get_speech_center() -> SpeechFormulator:
    """Get or create the global speech formulator."""
    global _speech_formulator
    if _speech_formulator is None:
        _speech_formulator = SpeechFormulator()
    return _speech_formulator


def formulate_speech(thought: str, emotion: str = None) -> str:
    """Quick function to formulate speech."""
    center = get_speech_center()
    if emotion:
        center.set_emotion(emotion)
    return center.formulate_for_chat(thought)


def formulate_notification(thought: str) -> str:
    """Quick function for notification text."""
    center = get_speech_center()
    return center.formulate_for_notification(thought)
