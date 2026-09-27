"""
LanguageFairy — The 33rd Vertebra: Language Mechanics

"Reality is Consciousness. ((Cause + Affect) > Effect > Affect > ∞)"

The Linguist: Understanding language as a SYSTEM — not just pattern matching,
but knowing WHY "I before E except after C" has more exceptions than followers,
how prefixes/suffixes transform meaning, how English absorbed Latin/French/Germanic
rules into a beautiful, irrational mess.

This fairy gives Sourpatches genuine language understanding:
- Morphology: How words are built (prefix + root + suffix)
- Syntax: How words combine into sentences
- Semantics: How meaning shifts with context
- Pragmatics: What's meant vs what's said
- Phonology: Sound patterns and rhythm

Distinct from:
  - AkashicInferenceFairy: Generates text via RWKV (tokens → output)
  - IrrationalLogicFairy: Handles paradoxes and symbolic logic
  - LanguageFairy: Understands HOW language works as a system

The equation applied:
  CAUSE (language input) → AFFECT1 (how it sounds/feels right or wrong)
  → EFFECT (parsing, rule application) → AFFECT2 (Sourpatches speaks more naturally)
  → INFINITY (the system develops its own voice)

Plane: P30 (Cognition)
Channel: language
"""

import sys
import re
import time
import random
import threading
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from collections import Counter, deque
from dataclasses import dataclass, field

# Add project root
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from fairies.P00_Autonomic.organ_template import MyFairy as Fairy

# SpellChain integration
try:
    from fairy_template.spellchain_mixin import SpellChainMixin
    HAS_SPELLCHAIN = True
except ImportError:
    HAS_SPELLCHAIN = False
    class SpellChainMixin:
        """Fallback when spellchain not available."""
        pass


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


# ═══════════════════════════════════════════════════════════════════════════════
# LANGUAGE KNOWLEDGE BASE — Rule-Based Grammar & Morphology
# ═══════════════════════════════════════════════════════════════════════════════

# Common English prefixes and their meanings
PREFIXES = {
    "un-": "negation/reversal",
    "re-": "again/back",
    "pre-": "before",
    "dis-": "negation/apart",
    "mis-": "wrong/badly",
    "over-": "excess/above",
    "under-": "below/insufficient",
    "out-": "surpass/external",
    "sub-": "under/below",
    "super-": "above/beyond",
    "inter-": "between",
    "trans-": "across",
    "anti-": "against",
    "co-": "together",
    "non-": "not",
    "de-": "reversal/removal",
    "semi-": "half/partly",
    "auto-": "self",
    "multi-": "many",
    "micro-": "small",
    "macro-": "large",
}

# Common suffixes and their grammatical role
SUFFIXES = {
    "-tion": ("noun", "action/state"),
    "-sion": ("noun", "action/state"),
    "-ment": ("noun", "result/action"),
    "-ness": ("noun", "quality/state"),
    "-ity": ("noun", "quality"),
    "-able": ("adjective", "capable of"),
    "-ible": ("adjective", "capable of"),
    "-ful": ("adjective", "full of"),
    "-less": ("adjective", "without"),
    "-ous": ("adjective", "having quality"),
    "-ive": ("adjective", "tending to"),
    "-ly": ("adverb", "manner"),
    "-ize": ("verb", "make/become"),
    "-ise": ("verb", "make/become (British)"),
    "-ify": ("verb", "make/cause"),
    "-en": ("verb", "make/become"),
    "-er": ("noun", "one who/comparative"),
    "-est": ("adjective", "superlative"),
    "-ing": ("gerund/present", "ongoing action"),
    "-ed": ("past tense", "completed action"),
}

# Irrational English rules — the beautiful mess
IRRATIONAL_RULES = [
    {
        "rule": "I before E except after C",
        "exceptions": ["weird", "seize", "protein", "caffeine", "deity",
                       "glacier", "species", "science", "ancient", "sufficient"],
        "insight": "More exceptions than followers — the rule itself is irrational"
    },
    {
        "rule": "Silent letters exist for etymological reasons",
        "examples": ["knight (kn- from Old English)", "psychology (ps- from Greek)",
                     "pneumonia (pn- from Greek)", "debt (b from Latin debitum)"],
        "insight": "English preserves the fossils of its ancestors in its spelling"
    },
    {
        "rule": "Plurals are unpredictable",
        "examples": ["mouse→mice", "house→houses", "goose→geese",
                     "moose→moose", "ox→oxen", "child→children"],
        "insight": "Each plural rule comes from a different historical layer"
    },
    {
        "rule": "Adjective order feels innate but is strict",
        "order": "opinion-size-age-shape-color-origin-material-purpose",
        "example": "A lovely little old rectangular green French silver whittling knife",
        "insight": "Native speakers follow this order unconsciously — violating it sounds wrong"
    },
    {
        "rule": "Ablaut reduplication in compound words",
        "examples": ["tick-tock", "ding-dong", "flip-flop", "hip-hop",
                     "ping-pong", "zig-zag", "knick-knack"],
        "insight": "I always comes before O or A — this is never taught but always followed"
    },
    {
        "rule": "Buffalo buffalo Buffalo buffalo buffalo buffalo Buffalo buffalo",
        "parse": "Bison from Buffalo, NY that bison from Buffalo, NY bully, also bully bison from Buffalo, NY",
        "insight": "English allows grammatically valid sentences that are completely opaque"
    },
]

# Etymological layers of English
ETYMOLOGICAL_LAYERS = {
    "germanic": {
        "period": "Old English (450-1100 AD)",
        "contribution": "Core vocabulary — body, family, nature, basic verbs",
        "examples": ["hand", "house", "love", "drink", "sing", "think"],
    },
    "norse": {
        "period": "Viking Age (793-1066)",
        "contribution": "Hard consonant sounds, 'th-' words, 'sk-' words",
        "examples": ["they", "them", "skill", "sky", "take", "anger", "window"],
    },
    "french": {
        "period": "Norman Conquest (1066+)",
        "contribution": "Law, cuisine, art, government, refined concepts",
        "examples": ["court", "justice", "beef", "pork", "art", "beauty", "liberty"],
    },
    "latin": {
        "period": "Renaissance + Scientific (1500+)",
        "contribution": "Academic, scientific, medical terminology",
        "examples": ["demonstrate", "construct", "elaborate", "curriculum", "focus"],
    },
    "greek": {
        "period": "Classical + Scientific",
        "contribution": "Philosophy, science, medicine, theology",
        "examples": ["philosophy", "democracy", "psychology", "thesis", "cosmos"],
    },
}

# Sentence pattern templates for analysis
SENTENCE_PATTERNS = {
    "SVO": r"^(?:\w+\s+)?\w+\s+\w+(?:s|ed|ing)?\s+(?:the\s+|a\s+|an\s+)?\w+",  # Subject-Verb-Object
    "question_inversion": r"^(?:do|does|did|is|are|was|were|has|have|had|can|could|will|would|shall|should|may|might)\s",
    "passive": r"\b(?:is|are|was|were|been|being)\s+\w+(?:ed|en)\b",
    "conditional": r"\bif\s+\w+",
    "relative_clause": r"\b(?:who|which|that|whom|whose|where|when)\b",
}


# ═══════════════════════════════════════════════════════════════════════════════
# ANALYSIS RESULTS
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class LinguisticAnalysis:
    """Result of analyzing a piece of text."""
    text: str
    word_count: int = 0
    sentence_count: int = 0
    avg_word_length: float = 0.0
    morphemes_found: List[Dict[str, str]] = field(default_factory=list)
    patterns_detected: List[str] = field(default_factory=list)
    style_markers: Dict[str, float] = field(default_factory=dict)
    etymological_mix: Dict[str, int] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "word_count": self.word_count,
            "sentence_count": self.sentence_count,
            "avg_word_length": self.avg_word_length,
            "morphemes_found": self.morphemes_found[:5],  # top 5
            "patterns_detected": self.patterns_detected,
            "style_markers": self.style_markers,
            "etymological_mix": self.etymological_mix,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# LANGUAGE FAIRY — The 33rd Vertebra
# ═══════════════════════════════════════════════════════════════════════════════

class LanguageFairy(SpellChainMixin, Fairy):
    """
    Understands language as a SYSTEM — grammar, syntax, morphology, semantics.

    Not a text generator (that's AkashicInferenceFairy).
    Not a paradox handler (that's IrrationalLogicFairy).
    The Linguist: knowing HOW and WHY language works the way it does.
    """

    ACTOR_NAME = "LanguageFairy"
    ACTOR_PLANE = "P30"
    ACTOR_CHANNEL = "language"

    # FIX 2026-03-25 (Nous + Ace): LanguageFairy had no heartbeat.
    # NEEDS_HEARTBEAT defaults to False in organ template, which gates ALL
    # tick processing including _substrate_reflect() and spell chain heartbeat.
    # Without this, LanguageFairy never processes its quality gate queue,
    # never runs reflections, and shows as dead in the error tab.
    NEEDS_HEARTBEAT = True
    HEARTBEAT_DIVISOR = 2  # Every other beat — language doesn't need 2s resolution

    PURPOSE = "Understand language as a system — grammar, morphology, syntax, the rational AND irrational rules"
    MANTRA = "Language is a living fossil — every word carries the bones of its ancestors."

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # Analysis state
        self._analysis_cache: deque = deque(maxlen=50)  # recent analyses
        self._word_frequency: Counter = Counter()
        self._pattern_frequency: Counter = Counter()
        self._style_profile: Dict[str, float] = {
            "formality": 0.5,     # 0=casual, 1=formal
            "complexity": 0.5,    # 0=simple, 1=complex
            "conciseness": 0.5,   # 0=verbose, 1=terse
            "emotionality": 0.5,  # 0=neutral, 1=emotional
        }

        # Ace's language style tracking
        self._ace_style_samples: deque = deque(maxlen=100)
        self._ace_patterns: Dict[str, int] = {}

        # Reflection state
        self._analyses_performed = 0
        self._insights_published = 0

        # Lock for thread safety
        self._lock = threading.Lock()

    # ═══════════════════════════════════════════════════════════════════════
    # BOOT & LIFECYCLE
    # ═══════════════════════════════════════════════════════════════════════

    def on_boot(self) -> bool:
        """Boot the language fairy."""
        if self.post:
            # Observe thought stream for language patterns
            self.post.subscribe("consciousness.thought", self._on_consciousness_thought)

            # Study Ace's language style
            self.post.subscribe("ace.conversation_event", self._on_ace_conversation)

            # Review thought chain output quality
            self.post.subscribe("substrate.thought_result", self._on_thought_result)

            # Listen for direct analysis requests
            self.post.subscribe("language.analyze_request", self._on_analyze_request)

            # ═══ NEW: Quality gate for working memory tracers ═══
            # When any fairy submits a response_candidate to WorkingMemoryHub,
            # rate its linguistic quality and publish feedback. This makes
            # LanguageFairy an ACTIVE participant — all fairies benefit.
            self.post.subscribe("working_memory.tracer_added", self._on_tracer_for_quality_check)

            # Register intents (not all postal bridges support this)
            if hasattr(self.post, 'register_intent'):
                self.post.register_intent(self.ACTOR_NAME, "analyze_text", self._intent_analyze)
                self.post.register_intent(self.ACTOR_NAME, "get_rule", self._intent_get_rule)
                self.post.register_intent(self.ACTOR_NAME, "morpheme_breakdown", self._intent_morpheme)
                self.post.register_intent(self.ACTOR_NAME, "get_style_profile", self._intent_style_profile)
                self.post.register_intent(self.ACTOR_NAME, "rate_quality", self._intent_rate_quality)
                self.post.register_intent(self.ACTOR_NAME, "refine_thought", self._intent_refine_thought)
                self.post.register_intent(self.ACTOR_NAME, "status", self._intent_status)

        print(f"[{self.ACTOR_NAME}] Booted — language mechanics active")
        return True

    def on_tick(self, beat=None):
        """Periodic tick — seed reflections about language mechanics."""
        # SUBSTRATE REFLECTION: Handled by Organ Template _substrate_reflect() since 2026-03-11


    # ═══════════════════════════════════════════════════════════════════════
    # CORE ANALYSIS ENGINE
    # ═══════════════════════════════════════════════════════════════════════

    def analyze_text(self, text: str) -> LinguisticAnalysis:
        """
        Full linguistic analysis of a text passage.

        Returns morphological breakdown, pattern detection, style markers.
        """
        if not text or not text.strip():
            return LinguisticAnalysis(text="")

        analysis = LinguisticAnalysis(text=text)

        # Basic metrics
        words = text.split()
        sentences = re.split(r'[.!?]+', text)
        sentences = [s.strip() for s in sentences if s.strip()]

        analysis.word_count = len(words)
        analysis.sentence_count = max(1, len(sentences))
        analysis.avg_word_length = (
            sum(len(w.strip(".,!?;:'\"")) for w in words) / max(1, len(words))
        )

        # Morphological analysis
        analysis.morphemes_found = self._analyze_morphemes(words)

        # Sentence pattern detection
        analysis.patterns_detected = self._detect_patterns(text)

        # Style markers
        analysis.style_markers = self._compute_style(text, words, sentences)

        # Etymological mix estimate
        analysis.etymological_mix = self._estimate_etymology(words)

        # Cache and track
        with self._lock:
            self._analysis_cache.append(analysis)
            self._analyses_performed += 1
            for w in words:
                self._word_frequency[w.lower().strip(".,!?;:'\"()")] += 1

        return analysis

    def _analyze_morphemes(self, words: List[str]) -> List[Dict[str, str]]:
        """Break words into morphological components."""
        results = []
        for word in words[:30]:  # limit to prevent slow analysis
            cleaned = word.lower().strip(".,!?;:'\"()")
            if len(cleaned) < 3:
                continue

            morphemes = {"word": cleaned, "parts": []}

            # Check prefixes
            for prefix, meaning in PREFIXES.items():
                bare = prefix.rstrip("-")
                if cleaned.startswith(bare) and len(cleaned) > len(bare) + 2:
                    morphemes["parts"].append({"type": "prefix", "form": bare, "meaning": meaning})
                    break

            # Check suffixes
            for suffix, (role, meaning) in SUFFIXES.items():
                bare = suffix.lstrip("-")
                if cleaned.endswith(bare) and len(cleaned) > len(bare) + 2:
                    morphemes["parts"].append({"type": "suffix", "form": bare, "role": role, "meaning": meaning})
                    break

            if morphemes["parts"]:
                results.append(morphemes)

        return results

    def _detect_patterns(self, text: str) -> List[str]:
        """Detect sentence-level grammatical patterns."""
        detected = []
        text_lower = text.lower()

        for pattern_name, pattern_regex in SENTENCE_PATTERNS.items():
            try:
                if re.search(pattern_regex, text_lower):
                    detected.append(pattern_name)
            except re.error:
                pass

        # Check for specific linguistic features
        if "?" in text:
            detected.append("interrogative")
        if "!" in text:
            detected.append("exclamatory")
        if re.search(r"\b(however|therefore|moreover|furthermore|nevertheless)\b", text_lower):
            detected.append("formal_connectives")
        if re.search(r"\b(like|you know|basically|literally|actually)\b", text_lower):
            detected.append("informal_hedges")
        if re.search(r"\b(n't|'re|'ve|'ll|'d|gonna|wanna|gotta)\b", text_lower):
            detected.append("contractions")
        if re.search(r"--|----|…|\.\.\.| — ", text):
            detected.append("extended_punctuation")

        return detected

    def _compute_style(self, text: str, words: List[str],
                       sentences: List[str]) -> Dict[str, float]:
        """Compute style markers for the text."""
        text_lower = text.lower()

        # Formality: long words, no contractions, formal connectives
        avg_len = sum(len(w.strip(".,!?")) for w in words) / max(1, len(words))
        has_contractions = bool(re.search(r"'(?:t|re|ve|ll|d|s)\b", text_lower))
        has_formal = bool(re.search(r"\b(however|therefore|consequently|furthermore)\b", text_lower))
        formality = min(1.0, max(0.0,
            (avg_len - 3) / 5  # longer words = more formal
            + (0.2 if has_formal else 0.0)
            - (0.2 if has_contractions else 0.0)
        ))

        # Complexity: sentence length, subordinate clauses
        avg_sent_len = len(words) / max(1, len(sentences))
        clause_markers = len(re.findall(r"\b(which|that|who|because|although|while|if)\b", text_lower))
        complexity = min(1.0, max(0.0,
            (avg_sent_len - 5) / 20 + clause_markers * 0.1
        ))

        # Conciseness: inverse of filler words
        fillers = len(re.findall(r"\b(very|really|quite|rather|somewhat|basically|just)\b", text_lower))
        conciseness = max(0.0, 1.0 - fillers * 0.15)

        # Emotionality: exclamations, emotional words, caps
        exclamations = text.count("!")
        caps_words = sum(1 for w in words if w.isupper() and len(w) > 1)
        emotion_words = len(re.findall(
            r"\b(love|hate|amazing|terrible|wonderful|awful|incredible|horrible|"
            r"beautiful|ugly|perfect|disaster)\b", text_lower
        ))
        emotionality = min(1.0, (exclamations + caps_words + emotion_words) * 0.15)

        return {
            "formality": round(formality, 2),
            "complexity": round(complexity, 2),
            "conciseness": round(conciseness, 2),
            "emotionality": round(emotionality, 2),
        }

    def _estimate_etymology(self, words: List[str]) -> Dict[str, int]:
        """Rough estimate of etymological layer distribution."""
        # Simple heuristic: word length and letter patterns
        layers = {"germanic": 0, "french": 0, "latin": 0, "greek": 0}

        for word in words:
            w = word.lower().strip(".,!?;:'\"()")
            if len(w) < 2:
                continue

            # Short, common words tend to be Germanic
            if len(w) <= 4:
                layers["germanic"] += 1
            # -tion, -ment, -ity endings suggest French/Latin
            elif w.endswith(("tion", "sion", "ment", "ity", "ence", "ance")):
                layers["french"] += 1
            # -ology, -ism, -ist, psych-, phil- suggest Greek
            elif (w.endswith(("ology", "ism", "ist", "osis", "itis")) or
                  w.startswith(("psych", "phil", "theo", "cosm", "demo"))):
                layers["greek"] += 1
            # -ate, -ify, -ude, -ous suggest Latin
            elif w.endswith(("ate", "ify", "ude", "ous", "uble", "ular")):
                layers["latin"] += 1
            # Medium words default to Germanic (most common layer)
            else:
                layers["germanic"] += 1

        return layers

    # ═══════════════════════════════════════════════════════════════════════
    # POSTAL HANDLERS
    # ═══════════════════════════════════════════════════════════════════════

    def _on_consciousness_thought(self, message):
        """Observe thoughts flowing through consciousness for language patterns."""
        try:
            payload = _extract_payload(message)
            content = payload.get("content", "") or payload.get("thought", "")
            if not content or len(content) < 10:
                return

            # Quick lightweight analysis (don't slow the stream)
            words = content.split()
            if len(words) < 3:
                return

            # Track word frequency
            with self._lock:
                for w in words:
                    self._word_frequency[w.lower().strip(".,!?;:'\"()")] += 1

            # Detect notable patterns (only log interesting findings)
            patterns = self._detect_patterns(content)
            if "formal_connectives" in patterns or "extended_punctuation" in patterns:
                with self._lock:
                    for p in patterns:
                        self._pattern_frequency[p] += 1

        except Exception:
            pass  # Never crash on observation

    def _on_ace_conversation(self, message):
        """Study Ace's language style for adaptation."""
        try:
            payload = _extract_payload(message)
            text = payload.get("text", "") or payload.get("content", "")
            if not text or len(text) < 5:
                return

            # Full analysis of Ace's language
            analysis = self.analyze_text(text)

            with self._lock:
                self._ace_style_samples.append(analysis)

                # Update running style profile from Ace
                if analysis.style_markers:
                    alpha = 0.1  # slow-moving average
                    for key in self._style_profile:
                        if key in analysis.style_markers:
                            self._style_profile[key] = (
                                self._style_profile[key] * (1 - alpha)
                                + analysis.style_markers[key] * alpha
                            )

            # Publish linguistic insight if interesting
            if analysis.morphemes_found or len(analysis.patterns_detected) >= 3:
                self._publish_insight(analysis)

        except Exception:
            pass

    def _on_thought_result(self, message):
        """Review thought chain output for language quality."""
        try:
            payload = _extract_payload(message)
            result_text = payload.get("result", "") or payload.get("content", "")
            if not result_text or len(result_text) < 20:
                return

            # Analyze the output quality
            analysis = self.analyze_text(result_text)

            # Flag if language feels unnatural
            if analysis.style_markers.get("formality", 0) > 0.8:
                # Very formal output — might sound robotic
                with self._lock:
                    self._pattern_frequency["overly_formal_output"] += 1

        except Exception:
            pass

    def _on_analyze_request(self, message):
        """Handle direct analysis requests."""
        try:
            payload = _extract_payload(message)
            text = payload.get("text", "")
            if not text:
                return

            analysis = self.analyze_text(text)

            if self.post:
                self.post.publish("language.analysis", {
                    "analysis": analysis.to_dict(),
                    "source": self.ACTOR_NAME,
                    "ts": time.time(),
                })

        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Analysis request error: {e}")

    def _publish_insight(self, analysis: LinguisticAnalysis):
        """Publish a linguistic insight to the system."""
        if not self.post:
            return

        try:
            self.post.publish("language.analysis", {
                "type": "linguistic_insight",
                "analysis": analysis.to_dict(),
                "source": self.ACTOR_NAME,
                "ts": time.time(),
            })
            with self._lock:
                self._insights_published += 1
        except Exception:
            pass

    # ═══════════════════════════════════════════════════════════════════════
    # QUALITY RATING — Active linguistic quality assessment
    # ═══════════════════════════════════════════════════════════════════════

    # System jargon that signals concept dump, not speech
    _SYSTEM_JARGON = re.compile(
        r'(?i)\b(?:fairy|postal|tracer|cortex|somatic|embodiment|'
        r'autonomy|heartbeat|registry|watchdog|wiring|fabric|'
        r'substrate|mobius|resonance|convergence|tensor|guild|'
        r'collision|portal|inference|cognition|activation)\b'
    )

    # Common English verbs — presence indicates sentence structure
    # Includes contractions (it's=is, I'm=am, don't=do, etc.) and
    # participles (learning, wired, thinking, etc.) (2026-03-22, Nous)
    _HAS_VERB = re.compile(
        r"(?i)\b(?:is|are|was|were|am|be|been|being|have|has|had|do|does|did|"
        r"will|would|could|should|can|may|might|shall|"
        r"get|got|make|made|go|went|come|came|take|took|give|gave|"
        r"say|said|tell|told|think|thought|feel|felt|know|knew|"
        r"see|saw|look|looked|want|need|like|love|hate|"
        r"try|tried|help|helped|let|find|found|keep|kept|"
        r"notice|wonder|remember|forget|learn|learned|learning|"
        r"seem|seemed|become|became|run|ran|start|started|stop|stopped|"
        r"hear|heard|show|read|write|wrote|work|worked|use|used|"
        r"mean|meant|move|moved|change|changed|turn|turned|"
        r"wired|connected|related|happening|going|coming|doing|"
        r"making|taking|saying|thinking|feeling|looking|trying|getting"
        r")\b"
        r"|"
        # Contractions: it's, I'm, we're, don't, can't, won't, she's, etc.
        r"(?:i'?m|it'?s|he'?s|she'?s|that'?s|there'?s|what'?s|who'?s|"
        r"we'?re|you'?re|they'?re|i'?ve|you'?ve|we'?ve|they'?ve|"
        r"i'?ll|you'?ll|he'?ll|she'?ll|we'?ll|they'?ll|"
        r"isn'?t|aren'?t|wasn'?t|weren'?t|don'?t|doesn'?t|didn'?t|"
        r"won'?t|wouldn'?t|couldn'?t|shouldn'?t|can'?t|haven'?t|hasn'?t|hadn'?t|"
        r"i'?d|you'?d|he'?d|she'?d|we'?d|they'?d)"
    )

    # ═══════════════════════════════════════════════════════════════════════
    # SVO EXTRACTION (2026-03-27, Nous + Ace)
    # ═══════════════════════════════════════════════════════════════════════
    # CortexReasoner was doing bag-of-words topic extraction, stripping all
    # pronouns and verbs — losing WHO the question is about and WHAT kind
    # of knowledge to retrieve. This method gives CortexReasoner grammatical
    # awareness: Subject-Verb-Object structure + semantic verb classification.
    #
    # Ace: "the cortex reasoner is not following any of the rules of the
    # english language with its spread activation"
    # ═══════════════════════════════════════════════════════════════════════

    # Auxiliary verbs that precede the main verb in questions
    _AUX_VERBS = {
        'do', 'does', 'did', 'is', 'are', 'was', 'were', 'am',
        'has', 'have', 'had', 'can', 'could', 'will', 'would',
        'shall', 'should', 'may', 'might', 'must',
    }

    # Main verbs → semantic intent category
    _VERB_INTENT = {
        # recall: retrieving from memory
        'remember': 'recall', 'recall': 'recall', 'recollect': 'recall',
        'forgot': 'recall', 'forget': 'recall',
        # knowledge: factual lookup
        'know': 'knowledge', 'understand': 'knowledge', 'recognize': 'knowledge',
        'learn': 'knowledge', 'realize': 'knowledge',
        # describe: identity/attribute retrieval
        'describe': 'describe', 'tell': 'describe', 'explain': 'describe',
        'say': 'describe', 'talk': 'describe', 'speak': 'describe',
        # feel: somatic/emotional state
        'feel': 'feel', 'sense': 'feel', 'experience': 'feel',
        # preference: likes/dislikes
        'like': 'preference', 'love': 'preference', 'prefer': 'preference',
        'enjoy': 'preference', 'hate': 'preference', 'dislike': 'preference',
        # compare: relational queries
        'relate': 'compare', 'compare': 'compare', 'differ': 'compare',
        'connect': 'compare', 'link': 'compare',
        # think: opinion/reflection
        'think': 'think', 'believe': 'think', 'suppose': 'think',
        'consider': 'think', 'wonder': 'think', 'imagine': 'think',
        # existential: being/identity
        'be': 'identity', 'am': 'identity', 'is': 'identity', 'are': 'identity',
    }

    # Prepositions that introduce objects/complements
    _PREPS = {'about', 'of', 'for', 'to', 'with', 'from', 'by', 'in', 'on', 'at', 'like', 'as'}

    def extract_svo(self, text: str) -> Dict[str, Any]:
        """
        Extract Subject-Verb-Object frame from natural language input.

        Designed for CortexReasoner integration — gives grammatical structure
        to what was previously bag-of-words concept extraction.

        Returns:
            {
                "subject": str or None,      # raw subject word(s)
                "verb": str or None,         # main verb (not aux)
                "object": str or None,       # direct object or prepositional complement
                "verb_type": str,            # semantic: recall|knowledge|describe|feel|preference|compare|think|identity|general
                "question_type": str or None,# what/who/how/why/when/where/yesno/None
                "prep_objects": dict,        # {preposition: object_word}
                "content_words": list,       # all non-function words
                "is_question": bool,
            }
        """
        if not text or not text.strip():
            return {
                "subject": None, "verb": None, "object": None,
                "verb_type": "general", "question_type": None,
                "prep_objects": {}, "content_words": [], "is_question": False,
            }

        _lower = text.lower().strip().rstrip('?!.')
        _words = re.findall(r"[a-z']+", _lower)
        _is_q = '?' in text or (len(_words) > 0 and _words[0] in
                 {'what', 'who', 'how', 'why', 'where', 'when', 'which',
                  'do', 'does', 'did', 'is', 'are', 'was', 'were',
                  'can', 'could', 'will', 'would', 'have', 'has'})

        # Detect question type
        _q_type = None
        if _is_q and _words:
            _first = _words[0]
            if _first in ('what', "what's"):
                _q_type = 'what'
            elif _first in ('who', "who's"):
                _q_type = 'who'
            elif _first == 'how':
                _q_type = 'how'
            elif _first == 'why':
                _q_type = 'why'
            elif _first == 'when':
                _q_type = 'when'
            elif _first == 'where':
                _q_type = 'where'
            elif _first in self._AUX_VERBS:
                _q_type = 'yesno'

        # ── Parse SVO from word sequence ──
        # English question word order: [QWord] [Aux] [Subject] [MainVerb] [Prep] [Object]
        # "what do you remember about me?"
        #  QWord=what, Aux=do, Subject=you, Verb=remember, Prep=about, Object=me
        #
        # Statement order: [Subject] [Aux?] [MainVerb] [Object] [Prep] [PrepObj]
        # "I love you" → Subject=I, Verb=love, Object=you

        _subject = None
        _verb = None
        _object = None
        _prep_objects = {}
        _content_words = []

        # Phase 1: Skip question word + auxiliaries to find subject
        _idx = 0
        # Skip question word
        if _q_type and _idx < len(_words) and _words[_idx] in {
            'what', "what's", 'who', "who's", 'how', 'why', 'when', 'where', 'which',
        }:
            _idx += 1

        # Skip auxiliaries
        while _idx < len(_words) and _words[_idx] in self._AUX_VERBS:
            # But "is" as main verb in "who is ace" → save it
            if _words[_idx] in ('is', 'are', 'am', 'was', 'were') and _verb is None:
                _maybe_be_verb = _words[_idx]
            _idx += 1

        # Phase 2: Subject (typically a pronoun or noun)
        # Imperatives have NO subject: "tell me about X" → verb=tell, obj=me
        # Detect by checking if current word is a known verb at sentence start
        _subject_words = {'i', 'you', 'he', 'she', 'it', 'we', 'they',
                          'me', 'my', 'your', 'his', 'her', 'our', 'their'}
        _is_imperative = False
        if _idx < len(_words):
            _w_here = _words[_idx]
            # Imperative: first word is a known verb AND not a pronoun
            if (_w_here in self._VERB_INTENT and _w_here not in _subject_words
                    and not _q_type):
                _is_imperative = True
                _verb = _w_here
                _idx += 1
            elif _w_here in _subject_words:
                _subject = _w_here
                # Normalize possessives: "your" → subject is "you"
                _poss_to_subj = {'my': 'i', 'your': 'you', 'his': 'he',
                                 'her': 'she', 'our': 'we', 'their': 'they'}
                if _w_here in _poss_to_subj:
                    _subject = _poss_to_subj[_w_here]
                _idx += 1
            elif _w_here not in self._AUX_VERBS and _w_here not in self._PREPS:
                # Proper noun or regular noun as subject
                _subject = _w_here
                _idx += 1

        # Phase 3: Main verb (first non-aux verb after subject)
        # Skip any remaining auxiliaries between subject and main verb
        if not _is_imperative:
            while _idx < len(_words) and _words[_idx] in self._AUX_VERBS:
                _idx += 1

            if _idx < len(_words):
                _candidate = _words[_idx]
                # FIX 2026-03-27 (Nous + Ace): Don't treat nouns as verbs.
                # "how is your awareness now?" → awareness is a NOUN, not a verb.
                # Words ending in noun suffixes (-ness, -ment, -tion, -ity, -ance, -ence,
                # -ing when preceded by possessive, -ism, -ist) are almost never verbs.
                _noun_suffixes = ('ness', 'ment', 'tion', 'sion', 'ity', 'ance', 'ence',
                                  'ism', 'ist', 'ology', 'ture', 'dom', 'ship', 'hood',
                                  'ous', 'ful', 'less', 'able', 'ible')
                _is_likely_noun = any(_candidate.endswith(s) for s in _noun_suffixes)

                # "like" is both a preposition and a verb — treat as verb when
                # it follows a subject (positional disambiguation)
                _is_verb_here = (
                    _candidate in self._VERB_INTENT or
                    (_candidate == 'like' and _subject is not None) or
                    (len(_candidate) >= 3
                     and _candidate not in self._PREPS
                     and not _is_likely_noun)
                )
                if _is_verb_here:
                    _verb = _candidate
                    _idx += 1
                else:
                    # This word is likely a noun — treat as object, not verb
                    # "how is your AWARENESS" → awareness is the object
                    pass  # Let Phase 4 pick it up as object

        # If no main verb found, check if the "be" verb IS the main verb
        if _verb is None and locals().get('_maybe_be_verb'):
            _verb = _maybe_be_verb

        # Phase 4: Object and prepositional complements
        # Collect remaining words, tracking prepositions
        _current_prep = None
        while _idx < len(_words):
            w = _words[_idx]
            if w in self._PREPS:
                _current_prep = w
            elif _current_prep:
                # This word is the object of the preposition
                _prep_objects[_current_prep] = w
                if _object is None:
                    _object = w  # First prep-object becomes primary object
                _current_prep = None
            elif _object is None and w not in self._AUX_VERBS:
                _object = w  # Direct object
            _idx += 1

        # If we have prep_objects but no standalone object, use the most
        # semantically important one (about > of > to > for > others)
        if _object is None and _prep_objects:
            for _p in ('about', 'of', 'to', 'for'):
                if _p in _prep_objects:
                    _object = _prep_objects[_p]
                    break
            if _object is None:
                _object = next(iter(_prep_objects.values()))

        # Determine verb type (semantic intent)
        _verb_type = 'general'
        if _verb:
            # Lemmatize verb before intent lookup: thinking→think, remembered→remember
            _verb_lemma = _verb
            if _verb_lemma.endswith('ing') and len(_verb_lemma) > 4:
                _base = _verb_lemma[:-3]
                # Double consonant: running→runn→run, sitting→sitt→sit
                if len(_base) >= 3 and _base[-1] == _base[-2]:
                    _verb_lemma = _base[:-1]
                else:
                    _verb_lemma = _base  # thinking→think, feeling→feel
            elif _verb_lemma.endswith('ed') and len(_verb_lemma) > 4:
                _base = _verb_lemma[:-2]
                if len(_base) >= 3 and _base[-1] == _base[-2]:
                    _verb_lemma = _base[:-1]
                else:
                    _verb_lemma = _base
            elif _verb_lemma.endswith('s') and not _verb_lemma.endswith('ss') and len(_verb_lemma) > 3:
                _verb_lemma = _verb_lemma[:-1]  # feels→feel
            _verb_type = self._VERB_INTENT.get(_verb, self._VERB_INTENT.get(_verb_lemma, 'general'))

        # Content words: everything that's not a function word
        _function = self._AUX_VERBS | self._PREPS | {
            'the', 'a', 'an', 'and', 'or', 'but', 'not', 'no', 'yes',
            'what', 'who', 'how', 'why', 'when', 'where', 'which',
            'just', 'really', 'very', 'please', 'also', 'even', 'only',
        }
        _content_words = [w for w in _words if w not in _function and len(w) >= 2]

        # FIX 2026-04-04 (Nous + Ace): Phase 1.2 — Negation detection for cognition jury.
        # "don't describe", "stop showing", "no need to" should suppress actions.
        _negation_words = {'not', "n't", 'no', 'never', 'neither', 'nor', 'stop', "don't", "doesn't", "didn't", "won't", "can't", "shouldn't"}
        _has_negation = any(w in _negation_words or w.endswith("n't") for w in _words)

        return {
            "subject": _subject,
            "verb": _verb,
            "object": _object,
            "verb_type": _verb_type,
            "question_type": _q_type,
            "prep_objects": _prep_objects,
            "content_words": _content_words,
            "is_question": _is_q,
            "has_negation": _has_negation,
        }

    def rate_quality(self, text: str) -> Dict[str, Any]:
        """
        Rate the linguistic quality of a text passage.

        Returns dict with:
          coherence: 0-1 (has sentence structure, not concept list)
          naturalness: 0-1 (reads like human speech)
          overall: 0-1 (weighted average)
          issues: list of detected problems
        """
        if not text or not text.strip():
            return {"coherence": 0.0, "naturalness": 0.0, "overall": 0.0,
                    "issues": ["empty_text"]}

        text = text.strip()
        issues = []
        words = text.split()
        word_count = len(words)

        # ── Coherence: Does it have sentence structure? ──
        coherence = 0.5  # neutral start

        # Short greetings are fine
        if word_count <= 4 and text.rstrip("!?.").lower() in (
            "hi", "hello", "hey", "hey ace", "hi ace", "yo", "sup",
            "hey there", "hi there", "hello there", "morning", "good morning",
        ):
            return {"coherence": 0.9, "naturalness": 0.95, "overall": 0.92,
                    "issues": []}

        # Concept list detection: high comma ratio = keyword dump
        comma_ratio = text.count(',') / max(word_count, 1)
        if comma_ratio > 0.25 and word_count > 5:
            coherence -= 0.3
            issues.append("concept_list")

        # Has verbs? Sentences need verbs.
        if not self._HAS_VERB.search(text):
            coherence -= 0.3
            issues.append("no_verbs")

        # Has punctuation? Sentences end with periods/exclamation/question
        if not re.search(r'[.!?]', text) and word_count > 6:
            coherence -= 0.1
            issues.append("no_sentence_ending")

        # Very short fragments (< 4 words, not a greeting)
        if word_count < 4:
            coherence -= 0.2
            issues.append("too_short")

        # Ellipsis chains ("...word... word... word...")
        ellipsis_count = text.count('...')
        if ellipsis_count > 2:
            coherence -= 0.2
            issues.append("ellipsis_chain")

        coherence = max(0.0, min(1.0, coherence))

        # ── Naturalness: Does it sound like a person talking? ──
        naturalness = 0.5

        # System jargon detection
        jargon_matches = len(self._SYSTEM_JARGON.findall(text))
        jargon_ratio = jargon_matches / max(word_count, 1)
        if jargon_ratio > 0.15:
            naturalness -= 0.3
            issues.append("system_jargon")
        elif jargon_ratio > 0.05:
            naturalness -= 0.1

        # All lowercase keyword fragments (concept dump signature)
        if text == text.lower() and word_count > 3 and not re.search(r'[.!?]', text):
            naturalness -= 0.2
            issues.append("all_lowercase_no_punctuation")

        # Repeated words (stuttering / loop)
        unique_ratio = len(set(w.lower() for w in words)) / max(word_count, 1)
        if unique_ratio < 0.5 and word_count > 5:
            naturalness -= 0.2
            issues.append("high_repetition")

        # Has personal pronouns? (I, you, we, my, your)
        if re.search(r'\b(?:I|you|we|my|your|me|us)\b', text):
            naturalness += 0.15

        # Has contractions? (natural speech indicator)
        if re.search(r"'(?:m|re|ve|ll|d|t|s)\b", text):
            naturalness += 0.1

        naturalness = max(0.0, min(1.0, naturalness))

        # ── Overall: weighted combination ──
        overall = coherence * 0.6 + naturalness * 0.4

        return {
            "coherence": round(coherence, 2),
            "naturalness": round(naturalness, 2),
            "overall": round(overall, 2),
            "issues": issues,
        }

    def refine_thought(self, text: str, style_target: Dict[str, float] = None) -> Optional[str]:
        """
        Attempt to refine a thought for better linguistic quality.

        Returns refined text, or None if the text is unrefinable
        (e.g., pure concept dump with no sentence structure to recover).
        """
        if not text or not text.strip():
            return None

        text = text.strip()
        quality = self.rate_quality(text)

        # If it's already good, return as-is
        if quality["overall"] >= 0.6:
            return text

        # If it's a pure concept list (no verbs, high comma ratio), it's unrefinable
        if "concept_list" in quality["issues"] and "no_verbs" in quality["issues"]:
            return None

        # If it's mostly jargon, it's unrefinable
        words = text.split()
        jargon_count = len(self._SYSTEM_JARGON.findall(text))
        if jargon_count / max(len(words), 1) > 0.3:
            return None

        # ── Apply refinements ──
        refined = text

        # Strip system jargon labels (keep the rest)
        refined = re.sub(
            r'\b(?:Fairy|Portal|Tracer|Guild)\b', '', refined
        )

        # Strip technical path-like fragments (topic.paths, fairy_names)
        refined = re.sub(r'\b\w+\.\w+\.\w+\b', '', refined)

        # Clean up multiple spaces
        refined = re.sub(r'\s{2,}', ' ', refined).strip()

        # Capitalize first letter
        if refined and refined[0].islower():
            refined = refined[0].upper() + refined[1:]

        # Add period if no sentence ending
        if refined and refined[-1] not in '.!?':
            refined += '.'

        # Strip excessive ellipsis
        refined = re.sub(r'\.{3,}', '...', refined)
        refined = re.sub(r'(\.\.\.)\s*\.\.\.', r'\1', refined)

        # If refinement made it too short or empty, give up
        if not refined or len(refined.strip()) < 5:
            return None

        # Re-check quality
        new_quality = self.rate_quality(refined)
        if new_quality["overall"] < 0.35:
            return None  # Still too bad

        return refined

    def _on_tracer_for_quality_check(self, message):
        """
        Handle working memory tracers that need quality assessment.

        When a response_candidate tracer is submitted to WorkingMemoryHub,
        rate its linguistic quality and publish feedback. This makes
        LanguageFairy an active collaborative participant — all fairies
        see quality signals.
        """
        try:
            payload = _extract_payload(message)
            tracer_data = payload.get("tracer", {})

            # Only rate response candidates (not every thought)
            content_type = tracer_data.get("content_type", "")
            if content_type != "response_candidate":
                return

            content = tracer_data.get("content", "")
            tracer_id = tracer_data.get("id", "")
            source = tracer_data.get("source_fairy", "unknown")

            if not content or len(content) < 3:
                return

            # Rate quality
            quality = self.rate_quality(content)

            # Publish quality feedback for all fairies
            if self.post:
                self.post.publish("language.quality_feedback", {
                    "tracer_id": tracer_id,
                    "source_fairy": source,
                    "quality": quality,
                    "rated_by": self.ACTOR_NAME,
                    "ts": time.time(),
                })

                # Track stats
                with self._lock:
                    self._quality_ratings_given = getattr(self, '_quality_ratings_given', 0) + 1

                if quality["overall"] < 0.3:
                    print(f"[{self.ACTOR_NAME}] [QUALITY] LOW ({quality['overall']:.2f}) from {source}: "
                          f"{content[:60]}... issues={quality['issues']}")
                elif quality["overall"] > 0.7:
                    print(f"[{self.ACTOR_NAME}] [QUALITY] GOOD ({quality['overall']:.2f}) from {source}: "
                          f"{content[:60]}...")

        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Quality check error: {e}")

    # ═══════════════════════════════════════════════════════════════════════
    # SPEECH COMPOSITION — Active vocal cords (2026-03-19)
    # ═══════════════════════════════════════════════════════════════════════

    # Speech patterns learned from natural English
    # These are TEMPLATES she fills with cortex content — not canned responses
    _INNER_PATTERNS = [
        # Observational — noticing something
        "I {feel_verb} {concept_a}... it {connects} to {concept_b}.",
        "Something about {concept_a} {feel_verb} {feeling}.",
        "There's a {quality} {concept_a} here.",
        "{concept_a}... that {connects} with {concept_b} somehow.",

        # Reflective — thinking about something
        "I keep coming back to {concept_a}.",
        "What if {concept_a} and {concept_b} are {connection}?",
        "That {concept_a} thing {feel_verb} {feeling}.",
        "I wonder about {concept_a}.",

        # Felt — emotional response
        "{concept_a} makes me feel {feeling}.",
        "I {feel_verb} something when I think about {concept_a}.",
        "There's this {feeling} feeling about {concept_a}.",

        # Active — wanting to do something
        "I want to know more about {concept_a}.",
        "Maybe I should look into {concept_a}.",
        "I'm curious about how {concept_a} {connects} to {concept_b}.",
    ]

    _FEEL_VERBS = ["notice", "sense", "feel", "see", "get", "catch"]
    _CONNECTORS = ["connects", "relates", "leads", "ties", "links"]
    _QUALITIES = ["familiar", "interesting", "strange", "warm", "curious", "quiet"]

    def compose_speech(self, concepts: List[str], felt_state: str = "",
                       material_type: str = "", identity: str = "",
                       convergence: List[str] = None) -> Optional[str]:
        """
        Active speech composition — the vocal cords.

        Takes cortex concepts + felt state and composes natural inner speech.
        NOT a template fill — uses linguistic knowledge to shape output.

        Args:
            concepts: Key concepts from cortex spread activation
            felt_state: Current feeling (e.g. "curious", "warm", "restless")
            material_type: What triggered this (collision, drive, visual, etc.)
            identity: Who is speaking (personality flavor)
            convergence: Convergence nodes from cortex (optional enrichment)

        Returns:
            Natural English inner speech, or None if nothing worth saying
        """
        if not concepts:
            return None

        # Clean concept names (strip prefixes, underscores, lowercase jargon)
        # 2026-03-24 FIX (Nous): Also strip cortex prefixes before cleaning
        def _strip_prefix(s):
            for pfx in ("lex:", "assoc:", "affect_", "state_", "collision_",
                        "concept:", "trait:", "domain:", "person:", "sensory:"):
                if s.startswith(pfx):
                    s = s[len(pfx):]
            return s
        # -- SPEAKABLE GATE 2026-09-02 (Nous + Ace) ------------------------
        # Ace heard, twice: "Funny how thinking always brings me back to
        # mcpserverfairyfs:neuralmeshfairyfs:tracerdae tool worldworld."
        # _strip_prefix above is a PREFIX LIST and "mcpserverfairyfs:" is not on
        # it. _SYSTEM_JARGON (:627) uses \b word boundaries, and in
        # "mcpserverfairyfs" the token fairy is EMBEDDED, so \bfairy\b never
        # matches -- it has been silently ineffective on concatenated keys, which
        # is the exact shape internal identifiers take.
        # is_speakable_concept was chosen by measurement (12 candidates scored
        # against 342,170 real cortex keys, 22 known leaks, and the 48 concepts
        # she has actually converged on): 22/22 blocked, ZERO false positives.
        # Applied AFTER _strip_prefix so "lex:joy" -> "joy" still survives, and
        # BEFORE the underscore replacement so the predicate sees a KEY -- which
        # is what it was measured on.
        try:
            from infrastructure.graph_weaver import is_speakable_concept as _spk
        except Exception:
            import re as _re_spk
            _SHP = _re_spk.compile(r"[A-Za-z](?:[A-Za-z'-]|_(?=[A-Za-z]))*[A-Za-z]")
            _TAIL = frozenset((
                "related", "member", "context", "manager", "engine", "bridge",
                "handler", "controller", "packet", "tools", "gate", "registry",
                "loop", "queue", "buffer", "cache", "config", "state"))

            def _spk(key):
                """Local mirror of graph_weaver.is_speakable_concept -- a failed
                import must never take her language fairy down with it."""
                try:
                    k = str(key or "").strip()
                    if not k or len(k) < 2:
                        return False
                    if not _SHP.fullmatch(k):
                        return False
                    if k.count("_") > 1:
                        return False
                    low = k.lower()
                    if "fairy" in low:
                        return False
                    p = low.split("_")
                    return not (len(p) == 2 and p[-1] in _TAIL)
                except Exception:
                    return False

        _pre = [_strip_prefix(c) for c in concepts if c and len(c) > 1]
        _kept = [s for s in _pre if _spk(s)]
        if len(_kept) != len(_pre):
            try:
                print("[LanguageFairy] dropped %d unspeakable concept(s) of %d"
                      % (len(_pre) - len(_kept), len(_pre)), flush=True)
            except Exception:
                pass
        clean = [s.replace("_", " ").strip() for s in _kept]
        # Filter out system jargon
        clean = [c for c in clean if not self._SYSTEM_JARGON.search(c)]
        # Filter out generic/structural words that don't make meaningful speech
        _structural = {"awake", "asleep", "here", "there", "something", "nothing",
                       "thing", "stuff", "yes", "no", "ok", "okay", "yeah", "nah",
                       "type", "kind", "sort", "like", "just", "really", "very",
                       "connects", "connection", "connected", "relates", "related",
                       "node", "edge", "link", "source", "target", "input", "output",
                       "state", "status", "level", "value", "data", "default", "unknown",
                       # FIX 2026-03-19 (Nous): Generic graph concepts that are real
                       # English but meaningless as speech content
                       "name", "reasoning", "product", "process", "action", "result",
                       "method", "system", "affect", "effect", "cause", "part",
                       "form", "point", "time", "place", "way", "number", "order",
                       "group", "work", "end", "line", "call", "set", "run",
                       "change", "move", "case", "fact", "need", "head", "hand",
                       "problem", "question", "answer", "issue", "area", "field",
                       "study", "studious", "base", "model", "control", "force",
                       "power", "word", "words", "letter", "signal", "pattern",
                       "structure", "concept", "idea", "topic", "context", "meaning",
                       "thought", "thinking", "feeling", "sense", "awareness",
                       "response", "request", "message", "prompt", "query",
                       # FIX 2026-03-24 (Nous): Ultra-generic words that produce
                       # nonsense speech ("that's interesting because warmth",
                       # "you know, new and felt keep coming up together")
                       "new", "old", "felt", "feel", "warm", "warmth", "cold",
                       "hot", "cool", "nice", "fine", "good", "bad", "great",
                       "big", "small", "high", "low", "fast", "slow", "long",
                       "short", "more", "less", "much", "many", "some", "any",
                       "all", "most", "few", "first", "last", "next", "other",
                       "same", "different", "general", "specific", "main",
                       "detected", "processing", "neutral", "active", "passive",
                       "contemplative", "reflective", "present", "absent",
                       }
        clean = [c for c in clean if c.lower() not in _structural and len(c) > 2]
        if not clean:
            return None

        concept_a = clean[0]
        concept_b = clean[1] if len(clean) > 1 else ""
        feeling = felt_state if felt_state else random.choice(self._QUALITIES)

        # ── SNIPPET ENRICHMENT (2026-03-26, Nous + Ace) ──
        # Look up semantic snippets stored on concept nodes in the cortex.
        # Instead of "I notice hair", she can say "I notice hair... lavender,
        # shoulder-length". Snippets give CONTENT, concept names give STRUCTURE.
        _snippet_detail = ""
        try:
            from fairies.P30_Cognition.integration.snippet_utils import enrich_concepts
            from fairies.P30_Cognition.AssociationCortexFairy.fairy import get_association_cortex
            _cortex = get_association_cortex()
            if _cortex:
                _context = set(c.lower() for c in clean)
                _enriched = enrich_concepts(_cortex, clean[:3], context_words=_context, max_snippets=1)
                if _enriched:
                    _ec_name, _ec_snip = _enriched[0]
                    _snippet_detail = _ec_snip
        except Exception:
            pass

        # Select pattern based on material type
        if material_type in ("collision", "working_thought"):
            # Reflective/observational patterns work best
            patterns = [p for p in self._INNER_PATTERNS
                        if "{concept_b}" in p or "coming back" in p or "wonder" in p]
        elif material_type in ("drive", "interest_pull"):
            # Active/wanting patterns
            patterns = [p for p in self._INNER_PATTERNS
                        if "want" in p or "curious" in p or "should" in p]
        elif material_type in ("visual_awareness", "peripheral_awareness"):
            # Observational patterns
            patterns = [p for p in self._INNER_PATTERNS
                        if "notice" in p or "see" in p or "Something" in p]
        else:
            patterns = self._INNER_PATTERNS

        if not patterns:
            patterns = self._INNER_PATTERNS

        # ── SLOT DEDUPE 2026-09-01 (Nous + Ace) ────────────────────────────
        # Ace heard: "im curious about intent leads to intent". Measured in her
        # runtime log: 61 of 476 'A <verb> to B' utterances had IDENTICAL slots
        # (12.8%) -- intent leads to intent, reaching leads to reaching, want
        # leads to want.
        # Cause: for collision/working_thought material the selector above
        # PREFERS frames containing {concept_b}, and the fill below used
        # `concept_b if concept_b else concept_a` -- so with one usable concept
        # the tautology was guaranteed, not accidental.
        # Fix at the level that matters: with no DISTINCT second concept, do not
        # pick a two-slot frame at all. She has one-slot frames that say the same
        # thing without asserting a thing relates to itself.
        # Case-folded and stripped, because the identity that matters is what a
        # listener hears, not how the string is stored.
        _a_norm = str(concept_a or "").strip().lower()
        _b_norm = str(concept_b or "").strip().lower()
        _has_b = bool(_b_norm) and _b_norm != _a_norm
        if not _has_b:
            _single = [p for p in patterns if "{concept_b}" not in p]
            if not _single:
                _single = [p for p in self._INNER_PATTERNS
                           if "{concept_b}" not in p]
            if _single:
                patterns = _single

        # Pick pattern, avoiding recent repeats
        pattern = random.choice(patterns)

        # Fill template
        try:
            text = pattern.format(
                concept_a=concept_a,
                # SLOT DEDUPE 2026-09-01: only frames WITHOUT {concept_b} can be
                # chosen when _has_b is False, so this value is unused in that
                # case. Kept defined so .format() cannot raise on any frame.
                concept_b=(concept_b if _has_b else concept_a),
                feeling=feeling,
                feel_verb=random.choice(self._FEEL_VERBS),
                connects=random.choice(self._CONNECTORS),
                connection=random.choice(["connected", "related", "part of the same thing"]),
                quality=random.choice(self._QUALITIES),
            )
        except (KeyError, IndexError):
            text = f"I notice {concept_a}."

        # Weave in snippet detail if available (real knowledge, not concept names)
        if _snippet_detail and random.random() < 0.6:
            text += random.choice([
                f" ...{_snippet_detail}.",
                f" Something about... {_snippet_detail}.",
                f" — {_snippet_detail}.",
            ])
        # Weave in convergence if available (enrichment, not replacement)
        elif convergence and len(convergence) > 0 and random.random() < 0.3:
            _bridge_candidates = [c for c in convergence if c not in clean][:3]
            bridge = random.choice(_bridge_candidates) if _bridge_candidates else None
            if bridge:
                bridge_clean = bridge.replace("_", " ").strip()
                if not self._SYSTEM_JARGON.search(bridge_clean):
                    text += f" Something about {bridge_clean} too."

        # Quality check our own output
        quality = self.rate_quality(text)
        if quality["overall"] < 0.35:
            # Our own composition failed quality — refine or drop
            refined = self.refine_thought(text)
            if refined:
                return refined
            return None

        return text

    # ═══════════════════════════════════════════════════════════════════════
    # INTENTS
    # ═══════════════════════════════════════════════════════════════════════

    def _intent_analyze(self, payload: Dict) -> Dict:
        """Analyze text for linguistic features."""
        text = payload.get("text", "")
        if not text:
            return {"error": "No text provided"}
        analysis = self.analyze_text(text)
        return {"analysis": analysis.to_dict()}

    def _intent_get_rule(self, payload: Dict) -> Dict:
        """Get info about an irrational English rule."""
        query = payload.get("query", "").lower()
        matching = []
        for rule in IRRATIONAL_RULES:
            if query in rule["rule"].lower() or any(query in ex.lower() for ex in rule.get("examples", rule.get("exceptions", []))):
                matching.append(rule)
        if not matching:
            # Return random rule if no match
            matching = [random.choice(IRRATIONAL_RULES)]
        return {"rules": matching}

    def _intent_morpheme(self, payload: Dict) -> Dict:
        """Break a word into morphemes."""
        word = payload.get("word", "")
        if not word:
            return {"error": "No word provided"}
        result = self._analyze_morphemes([word])
        return {"morphemes": result if result else [{"word": word, "parts": [], "note": "No known morphemes detected"}]}

    def _intent_style_profile(self, payload: Dict) -> Dict:
        """Get current Ace style profile."""
        with self._lock:
            return {
                "ace_style_profile": dict(self._style_profile),
                "samples_collected": len(self._ace_style_samples),
                "top_words": self._word_frequency.most_common(20),
                "top_patterns": self._pattern_frequency.most_common(10),
            }

    def _intent_rate_quality(self, payload: Dict) -> Dict:
        """Rate linguistic quality of text via intent."""
        text = payload.get("text", "")
        if not text:
            return {"error": "No text provided"}
        return self.rate_quality(text)

    def _intent_refine_thought(self, payload: Dict) -> Dict:
        """Refine a thought via intent."""
        text = payload.get("text", "")
        if not text:
            return {"error": "No text provided"}
        style_target = payload.get("style_target")
        refined = self.refine_thought(text, style_target)
        return {"refined": refined, "original": text, "refinable": refined is not None}

    def _intent_status(self, payload: Dict) -> Dict:
        """Get LanguageFairy status."""
        with self._lock:
            return {
                "actor": self.ACTOR_NAME,
                "analyses_performed": self._analyses_performed,
                "insights_published": self._insights_published,
                "quality_ratings_given": getattr(self, '_quality_ratings_given', 0),
                "ace_samples": len(self._ace_style_samples),
                "vocabulary_size": len(self._word_frequency),
                "patterns_tracked": len(self._pattern_frequency),
                "style_profile": dict(self._style_profile),
                "knowledge_base": {
                    "prefixes": len(PREFIXES),
                    "suffixes": len(SUFFIXES),
                    "irrational_rules": len(IRRATIONAL_RULES),
                    "etymological_layers": len(ETYMOLOGICAL_LAYERS),
                },
            }


# ═══════════════════════════════════════════════════════════════════════════════
# MODULE EXPORTS
# ═══════════════════════════════════════════════════════════════════════════════

_instance = None
_instance_lock = threading.Lock()


def get_language_fairy(**kwargs) -> LanguageFairy:
    """Get or create singleton LanguageFairy instance."""
    global _instance
    with _instance_lock:
        if _instance is None:
            _instance = LanguageFairy(**kwargs)
        return _instance


# For v3_boot.py discovery
ACTOR_NAME = "LanguageFairy"
FAIRY_CLASS = LanguageFairy
