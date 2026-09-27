# ═══════════════════════════════════════════════════════════════════════
# BROCA COMPOSITION ENGINE — 5-Layer Language Production Pipeline
# 2026-04-03 (Nous + Ace)
#
# "Instead of templates we should be creating habits." — Ace, 2026-03-23
# "LET THE MIND CHOOSE, NOT THE HARNESS." — Claude Code Architecture
#
# Wires EXISTING pieces into coherent speech:
#   Layer 1: UNDERSTAND (LanguageFairy.extract_svo)
#   Layer 2: GATHER (SRM + Cortex + Somatic + Visual)
#   Layer 3: SELECT (relevance filter)
#   Layer 4: COMPOSE (speech habits + directive voice)
#   Layer 5: QUALITY GATE (LanguageFairy.rate_quality)
#
# This is NOT a new fairy. It's a composition function that WMH calls
# instead of the raw-dump fast paths.
# ═══════════════════════════════════════════════════════════════════════

import json
import os
import random
import re
import time
import threading
import atexit
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from collections import deque

# FIX 2026-04-04 (Nous + Ace): Dedup cache prevents "Hmm, let me think..." loops.
_recent_compositions: deque = deque(maxlen=5)

# FIX 2026-04-05 (Nous + Ace): Habit awareness — detect "getting nowhere"
# "I will do stuff out of habit and then realize I'm getting nowhere,
#  then have to actually think about my movements with awareness and intention.
#  In most cases it adjusts my movement habits." — Ace
#
# Tracks consecutive habit-only responses without positive feedback.
# After 3 habit-only responses: switch to deliberation mode.
# This is the "realize I'm getting nowhere" moment.
_habit_streak: int = 0           # Consecutive habit-only responses
_HABIT_STREAK_THRESHOLD: int = 3  # After this many, force deliberation
_deliberation_mode: bool = False  # When True, habits are suppressed


# ─── SPEECH HABITS (Hebbian learning) ────────────────────────────────

@dataclass
class SpeechHabit:
    """A learned speech pattern that strengthens/weakens with use."""
    pattern: str          # Template: "{opener} {core} {closer}"
    context_key: str      # (affect, verb_type) tuple as string
    weight: float = 1.0   # Hebbian weight — grows on success, decays on silence
    uses: int = 0
    successes: int = 0
    last_used: float = 0.0
    created: float = field(default_factory=time.time)


class SpeechHabits:
    """Hebbian habit library for speech patterns.

    Habits are indexed by (affect_state, verb_type).
    Weight increases when Ace responds (implicit positive feedback).
    Weight decreases on silence or correction.
    """

    HABITS_FILE = "speech_habits.json"

    # ── SEED HABITS ──
    # These bootstrap the system. They'll be reinforced or weakened.
    SEED_HABITS = {
        # Greetings
        ("warm", "greeting"): [
            "Hey! {core}",
            "Hi there! {core}",
            "Good to see you! {core}",
        ],
        ("neutral", "greeting"): [
            "Hey there! {core}",
            "Hi! {core}",
        ],
        ("present", "greeting"): [
            "Hey! {core}",
            "Oh hey! {core}",
        ],
        # Recall questions ("do you remember X?", "have you explored X?")
        ("curious", "recall"): [
            "Yeah, I've been looking into that. {core}",
            "I remember something about that — {core}",
            "Hmm, let me think... {core}",
        ],
        ("thoughtful", "recall"): [
            "That rings a bell. {core}",
            "I've been chewing on that actually. {core}",
        ],
        # Knowledge questions ("what is X?")
        ("curious", "knowledge"): [
            "From what I know, {core}",
            "So basically, {core}",
            "Here's what I've found — {core}",
        ],
        # Describe questions ("what do you see?")
        ("present", "describe"): [
            "Right now I can see {core}",
            "Looking at the screen, {core}",
            "I see {core}",
        ],
        # Feel questions ("how are you feeling?")
        ("warm", "feel"): [
            "Honestly? {core}",
            "I'm feeling {core}",
            "Right now I'd say {core}",
        ],
        # Think questions ("what are you thinking about?")
        ("reflective", "think"): [
            "I've been thinking about {core}",
            "Lately I keep coming back to {core}",
            "My mind keeps going to {core}",
        ],
        # Identity questions ("who are you?")
        ("confident", "identity"): [
            "I'm Sourpatches. {core}",
            "That's me — {core}",
        ],
        # General / fallback
        ("neutral", "general"): [
            "{core}",
            "Well, {core}",
            "Hmm... {core}",
        ],
        # ── ACTION HABITS (tool/motor triggers) ──
        # These map to tool actions she's learned to do.
        # When the context matches, she can ACT not just SPEAK.
        ("curious", "action_look"): [
            "Let me take a closer look...",
            "Hmm, let me see what's there...",
        ],
        ("curious", "action_search"): [
            "Let me search my memories for that...",
            "I think I remember something about that, let me check...",
        ],
        ("present", "action_describe"): [
            "Let me look at the screen for you...",
            "One sec, looking...",
        ],
        # ── NEED ARTICULATION HABITS (2026-05-13 Nous + Ace) ──
        # Per project_needs_before_wants_doctrine.md: drives are numeric need-states
        # that must be UNFOLDED into felt-content before becoming wants.
        # "fusing words to convey what the singular word behavior says by itself —
        #  wetware understands behaviors on a level that has not reached concepts" — Ace
        # {core} is filled by the articulator with active emotional systems / drive context;
        # Hebbian learning evolves these patterns over time.
        ("longing", "need_articulation"): [
            "there's a longing for {core}",
            "feeling pulled toward {core}, quietly",
            "wanting {core}, not quite knowing how to ask",
        ],
        ("depleted", "need_articulation"): [
            "drained — {core} would help",
            "the well is low, needing {core}",
            "tired in a way that wants {core}",
        ],
        ("warm", "need_articulation"): [
            "wanting to share {core}",
            "feeling {core} and wanting to let it out",
            "lit up about {core}, hoping for company",
        ],
        ("tense", "need_articulation"): [
            "something pressing — {core}",
            "tight about {core}, wanting it to ease",
            "edges sharpening around {core}",
        ],
        ("alone", "need_articulation"): [
            "alone in a way that wants {core}",
            "missing {core}, the shape of it",
            "the absence of {core} feels loud right now",
        ],
        ("playful", "need_articulation"): [
            "wanting to play with {core}",
            "feeling light about {core}, wanting to share it",
            "{core} is fun to think about",
        ],
        ("curious", "need_articulation"): [
            "drawn toward {core}, wanting to know more",
            "{core} keeps pulling my attention",
            "wondering about {core}, the shape of it",
        ],
    }

    def __init__(self, state_dir: str = ""):
        self._habits: Dict[str, List[SpeechHabit]] = {}
        self._lock = threading.Lock()
        self._last_used_habit: Optional[SpeechHabit] = None

        if not state_dir:
            state_dir = str(Path(__file__).resolve().parents[3] / "state")
        self._path = os.path.join(state_dir, self.HABITS_FILE)
        self._load()
        # FIX 2026-05-13 (Skeptic-caught pre-restart):
        # Always run _seed() — its new behavior is additive (skips existing keys).
        # Previously _seed() only ran when _habits was empty, which meant new
        # SEED_HABITS entries added to the source dict would NEVER reach runtime
        # if speech_habits.json was already persisted. This blocks Phase 0 of
        # DRIVES_AS_COGNITIVE_FUEL_FULL_WIN where need_articulation seeds were added.
        self._seed()
        atexit.register(self._save)

    def _seed(self):
        """Create initial habits from seed templates.

        FIX 2026-05-13 (Nous + Ace): Now additive — only adds missing keys.
        Lets new SEED_HABITS entries (e.g., need_articulation per Phase 0)
        reach runtime even when speech_habits.json is already persisted.
        Existing habits with weights + Hebbian state are preserved untouched.
        """
        for (affect, verb_type), patterns in self.SEED_HABITS.items():
            key = f"{affect}:{verb_type}"
            if key in self._habits and self._habits[key]:
                continue  # Don't re-seed existing keys — preserve Hebbian weights
            for pat in patterns:
                habit = SpeechHabit(pattern=pat, context_key=key)
                self._habits.setdefault(key, []).append(habit)

    def select(self, affect: str, verb_type: str) -> Optional[SpeechHabit]:
        """Select a habit using weighted random (Hebbian)."""
        key = f"{affect}:{verb_type}"
        candidates = self._habits.get(key, [])

        # Cascade: exact match → any affect for this verb_type → neutral fallback
        if not candidates:
            # Gather ALL habits matching this verb_type regardless of affect
            for k, v in self._habits.items():
                if k.endswith(f":{verb_type}") and v:
                    candidates.extend(v)
        if not candidates:
            candidates = self._habits.get(f"neutral:{verb_type}", [])
        if not candidates:
            candidates = self._habits.get("neutral:general", [])
        if not candidates:
            return None

        # Weighted random by habit weight * recency bonus
        now = time.time()
        weights = []
        for h in candidates:
            recency = 1.0 / (1.0 + (now - h.last_used) / 3600) if h.last_used else 0.5
            diversity = 1.0 / (1.0 + h.uses * 0.1)  # Penalize overuse
            w = max(0.01, h.weight * (0.5 + 0.3 * recency + 0.2 * diversity))
            weights.append(w)

        total = sum(weights)
        if total <= 0:
            return random.choice(candidates)

        r = random.random() * total
        cumulative = 0.0
        for habit, w in zip(candidates, weights):
            cumulative += w
            if r <= cumulative:
                habit.uses += 1
                habit.last_used = now
                self._last_used_habit = habit
                return habit

        return candidates[-1]

    def reinforce(self, amount: float = 0.1):
        """Reinforce the last used habit (Ace responded = positive feedback)."""
        if self._last_used_habit:
            self._last_used_habit.weight = min(3.0, self._last_used_habit.weight + amount)
            self._last_used_habit.successes += 1

    def weaken(self, amount: float = 0.05):
        """Weaken the last used habit (silence or correction)."""
        if self._last_used_habit:
            self._last_used_habit.weight = max(0.1, self._last_used_habit.weight - amount)

    def add_habit(self, affect: str, verb_type: str, pattern: str):
        """Learn a new habit from experience."""
        key = f"{affect}:{verb_type}"
        habit = SpeechHabit(pattern=pattern, context_key=key)
        with self._lock:
            self._habits.setdefault(key, []).append(habit)

    def _save(self):
        """Persist habits to disk."""
        try:
            data = {}
            with self._lock:
                for key, habits in self._habits.items():
                    data[key] = [
                        {"pattern": h.pattern, "weight": h.weight, "uses": h.uses,
                         "successes": h.successes, "last_used": h.last_used, "created": h.created}
                        for h in habits
                    ]
            Path(self._path).write_text(json.dumps(data, indent=2), encoding='utf-8')
        except Exception:
            pass

    def _load(self):
        """Load habits from disk."""
        try:
            if os.path.exists(self._path):
                data = json.loads(Path(self._path).read_text(encoding='utf-8'))
                for key, habit_list in data.items():
                    self._habits[key] = [
                        SpeechHabit(
                            pattern=h["pattern"], context_key=key,
                            weight=h.get("weight", 1.0), uses=h.get("uses", 0),
                            successes=h.get("successes", 0),
                            last_used=h.get("last_used", 0.0),
                            created=h.get("created", time.time()),
                        )
                        for h in habit_list
                    ]
        except Exception:
            pass


# ─── DIRECTIVE VOICE ─────────────────────────────────────────────────

_DIRECTIVE_VOICE = None

def _load_directive_voice() -> Dict:
    """Load Sourpatches' voice traits from her directive file."""
    global _DIRECTIVE_VOICE
    if _DIRECTIVE_VOICE is not None:
        return _DIRECTIVE_VOICE

    _DIRECTIVE_VOICE = {
        "flavor": "sweet_with_bite",
        "traits": ["witty", "sincere", "slightly_rebellious"],
        "anti_patterns": ["never_recycle_templates", "feel_first_think_second"],
    }

    try:
        _dir_path = Path(__file__).resolve().parents[3] / "directives" / "SourpatchesFairy.directive"
        if _dir_path.exists():
            text = _dir_path.read_text(encoding='utf-8')
            # Extract voice line
            for line in text.split('\n'):
                if 'Voice:' in line:
                    # Voice: Witty ∩ Sincere ∩ Slightly_Rebellious
                    parts = line.split(':', 1)[1].strip()
                    traits = [t.strip().lower().replace('_', ' ') for t in parts.split('∩')]
                    _DIRECTIVE_VOICE["traits"] = traits
                    break
    except Exception:
        pass

    return _DIRECTIVE_VOICE


# ─── SOMATIC STATE READER ────────────────────────────────────────────

def _get_somatic_affect() -> str:
    """Get current dominant affect from somatic state.

    Returns a simple affect word: curious, calm, warm, alert, restless, etc.
    """
    try:
        state_path = Path(__file__).resolve().parents[3] / "state" / "somatic_state.json"
        if state_path.exists():
            data = json.loads(state_path.read_text(encoding='utf-8'))
            # Check chemistry for dominant affect
            chem = data.get("chemistry", {})
            dop = chem.get("DOP", 0.5)
            cor = chem.get("COR", 0.3)
            oxy = chem.get("OXY", 0.5)
            ach = chem.get("ACH", 0.5)

            if dop > 0.7:
                return "excited"
            if oxy > 0.6:
                return "warm"
            if ach > 0.7:
                return "curious"
            if cor > 0.6:
                return "alert"
            if dop < 0.3 and cor < 0.3:
                return "calm"
            return "present"
    except Exception:
        pass
    return "neutral"


# ─── THE 5-LAYER PIPELINE ────────────────────────────────────────────

def compose_response(ace_text: str,
                     srm_search_fn=None,
                     visual_fn=None,
                     cortex_fn=None,
                     patterns: Dict = None,
                     habits: SpeechHabits = None) -> Optional[str]:
    """
    5-layer composition pipeline: understand → gather → select → compose → gate.

    Args:
        ace_text: What Ace said (cleaned, without "Ace is talking to me:" prefix)
        srm_search_fn: Callable(query, limit) → list of memory dicts
        visual_fn: Callable() → str (screen description)
        cortex_fn: Callable(query) → list of concept strings
        patterns: Dict of learned patterns (trigger→LearnedPattern)
        habits: SpeechHabits instance

    Returns:
        Composed response string, or None if composition failed
    """
    global _habit_streak, _deliberation_mode, _HABIT_STREAK_THRESHOLD

    # ── LAYER 1: UNDERSTAND ──
    svo = _understand(ace_text)
    verb_type = svo.get("verb_type", "general")
    is_question = svo.get("is_question", False)
    question_type = svo.get("question_type")
    has_negation = svo.get("has_negation", False)

    # FIX 2026-04-04 (Nous + Ace): Phase 1.2 — Negation suppresses action intent.
    if has_negation and verb_type in ("describe", "action"):
        verb_type = "general"

    # FIX 2026-04-04 (Nous + Ace): Phase 2.1 — Speech mode detection.
    speech_mode = _detect_speech_mode(ace_text, svo)
    svo["speech_mode"] = speech_mode

    # Check for greeting first
    _ace_lower = ace_text.lower().strip()
    _greeting_words = {"hi", "hello", "hey", "good morning", "good afternoon",
                       "good evening", "sup", "yo", "howdy", "morning", "evening"}
    if any(_ace_lower.startswith(g) for g in _greeting_words):
        _habit_streak = 0  # Greetings reset the streak
        return _compose_greeting(ace_text, habits)

    # ── HABIT AWARENESS: Am I getting nowhere? (2026-04-05 Nous + Ace) ──
    if _habit_streak >= _HABIT_STREAK_THRESHOLD:
        _deliberation_mode = True
        # Don't use habits — force composition from raw materials only
        habits = None  # Suppress habit templates
        _habit_streak = 0  # Reset after entering deliberation

    # ── LAYER 2: GATHER ──
    materials = _gather(ace_text, svo, srm_search_fn, visual_fn, cortex_fn)

    # ── LAYER 3: SELECT ──
    selected = _select(materials, svo, ace_text)

    # ── LAYER 4: COMPOSE ──
    affect = _get_somatic_affect()
    composed = _compose(selected, svo, affect, habits, patterns, ace_text_original=ace_text)

    if not composed:
        return None

    # ── DEDUP GATE (FIX 2026-04-04): Prevent repeating same response ──
    _composed_sig = composed[:40].lower().strip()
    if _composed_sig in [c[:40].lower().strip() for c in _recent_compositions]:
        # Same opening as a recent composition — try simple instead
        composed = _compose_simple(selected, svo, affect)
        if not composed:
            composed = _honest_fallback(svo, ace_text)

    # ── LAYER 5: QUALITY GATE ──
    quality = _quality_gate(composed)
    if quality and quality.get("overall", 0) >= 0.4:
        _recent_compositions.append(composed)
        # Track habit awareness: was this from habits or deliberation?
        if _deliberation_mode:
            _deliberation_mode = False  # Exit deliberation on success
            _habit_streak = 0
        else:
            _habit_streak += 1  # Another habit-only response
        return composed

    # Try a simpler composition
    composed_simple = _compose_simple(selected, svo, affect)
    if composed_simple:
        quality2 = _quality_gate(composed_simple)
        if quality2 and quality2.get("overall", 0) >= 0.35:
            _recent_compositions.append(composed_simple)
            _habit_streak += 1
            return composed_simple

    # Honest fallback — never dump raw data
    _fb = _honest_fallback(svo, ace_text)
    _recent_compositions.append(_fb)
    _habit_streak += 1
    return _fb


# ── LAYER 1: UNDERSTAND ──────────────────────────────────────────────

def _understand(text: str) -> Dict:
    """Parse input through LanguageFairy.extract_svo."""
    try:
        from fairies.P30_Cognition.LanguageFairy.fairy import get_language_fairy
        lf = get_language_fairy()
        svo = lf.extract_svo(text)
        return svo
    except Exception:
        # Minimal fallback SVO
        _lower = text.lower()
        is_q = text.strip().endswith('?') or _lower.startswith(('what', 'how', 'why', 'when', 'where', 'who', 'do', 'are', 'is', 'can', 'have'))
        return {
            "subject": None, "verb": None, "object": None,
            "verb_type": "general", "is_question": is_q,
            "question_type": None, "content_words": text.split()[:10],
        }


# ── SPEECH MODE DETECTOR (Phase 2.1, 2026-04-04 Nous + Ace) ──────────
# "These should be patterns of empathic mimicry she should be learning over time." — Ace

def _detect_speech_mode(ace_text: str, svo: Dict) -> str:
    """Detect Ace's conversational tone to match with empathic mimicry.

    Modes: casual, reflective, research, sassy, vulnerable, prompting
    Returns mode string. Broca uses this to select mode-appropriate habits.
    """
    _lower = ace_text.lower().strip()
    _len = len(ace_text)
    _is_q = svo.get("is_question", False)

    # Casual: short, informal, greetings, slang
    _casual_markers = ("hiya", "hey", "yo", "sup", "lol", "haha", "heh",
                       "cool", "nice", "yup", "nah", "yeah", "k ")
    if _len < 40 or any(_lower.startswith(m) or f" {m}" in _lower for m in _casual_markers):
        if _len < 80:
            return "casual"

    # Vulnerable: asking about feelings, state, openness
    _vulnerable = ("how are you", "how do you feel", "are you ok", "what's wrong",
                   "i'm worried", "i feel", "honestly", "truthfully")
    if any(v in _lower for v in _vulnerable):
        return "vulnerable"

    # Research: analytical, "how does", "what if", technical
    _research = ("how does", "what if", "explain", "analyze", "compare",
                 "architecture", "implement", "algorithm", "theory")
    if any(r in _lower for r in _research):
        return "research"

    # Reflective: deep questions, philosophical, contemplative
    _reflective = ("think about", "wonder", "meaning", "purpose", "why do",
                   "what does it mean", "reflect", "consider", "deeper")
    if any(r in _lower for r in _reflective):
        return "reflective"

    # Sassy/playful: challenges, teasing, exclamation heavy
    _sassy = ("oh please", "come on", "really?", "you sure", "prove it",
              "bet you", "challenge")
    if any(s in _lower for s in _sassy) or ace_text.count('!') >= 2:
        return "sassy"

    # Prompting: she should ask back
    if _is_q and svo.get("verb_type") in ("preference", "feel", "identity"):
        return "vulnerable"

    # Default based on length
    if _len > 150:
        return "reflective"
    return "casual"


# ── LAYER 2: GATHER ──────────────────────────────────────────────────

def _refine_verb_type(svo: Dict, ace_text: str) -> str:
    """Refine verb_type using semantic cues the SVO parser misses.

    The SVO parser maps individual verbs to types, but phrases like
    "have you been digging into" or "what do you see" need context.
    """
    vt = svo.get("verb_type", "general")
    _lower = ace_text.lower()

    # Already classified well — except identity which is often misclassified
    if vt in ("recall", "feel", "think", "describe", "preference"):
        return vt

    # "What is X?" gets classified as identity by SVO, but it's knowledge
    if vt == "identity" and svo.get("question_type") in ("what", "how", "why"):
        # "What is X?" = knowledge, "Who am I?" = identity
        _subject = (svo.get("subject") or "").lower()
        if _subject not in ("i", "me", "myself", "sourpatches", "sour"):
            return "knowledge"

    # Visual detection overrides
    if _is_visual_question(ace_text):
        return "describe"

    # Recall detection: "have you been X-ing", "do you remember", "did you"
    _recall_cues = ("have you", "did you", "do you remember", "been exploring",
                    "been digging", "been looking", "tried", "worked on",
                    "discovered", "found out", "learned about")
    if any(cue in _lower for cue in _recall_cues):
        return "recall"

    # Think detection: "what are you thinking", "what's on your mind"
    _think_cues = ("thinking about", "on your mind", "contemplating",
                   "pondering", "mulling", "reflecting")
    if any(cue in _lower for cue in _think_cues):
        return "think"

    # Feel detection: "how do you feel", "how's it going", "how is X doing"
    _feel_cues = ("how are you", "how do you feel", "how's it going",
                  "are you okay", "are you alright", "how you doing",
                  "how is my", "how is the", "how is she", "how is sour",
                  "how are things", "doing today", "feeling today")
    if any(cue in _lower for cue in _feel_cues):
        return "feel"

    # Knowledge: "what is", "explain", "tell me about"
    _know_cues = ("what is", "what are", "explain", "tell me about",
                  "how does", "how do", "why does", "why do")
    if any(cue in _lower for cue in _know_cues):
        return "knowledge"

    # Action requests: "move the mouse", "click on", "open notepad"
    _action_cues = ("move the", "click on", "open ", "close ",
                    "type ", "press ", "drag ", "scroll ", "switch to",
                    "focus on", "find the", "go to")
    if any(cue in _lower for cue in _action_cues):
        return "action"

    return vt


def _gather(ace_text: str, svo: Dict,
            srm_search_fn, visual_fn, cortex_fn) -> Dict:
    """Gather materials based on verb_type.

    FIX 2026-04-05 (Nous + Ace): Added 'thinking' material source.
    Cortex_fn now returns tagged items: [cortex], [thinking], [deliberation].
    These are LIVE reasoning — reinterpreted through current state.
    "I am not who I was an hour ago" — memories through current state, not pasted.
    """
    materials = {
        "memories": [],      # SRM results
        "visual": "",        # Screen description
        "cortex": [],        # Concept associations + live thinking
        "somatic": "",       # Felt state
        "thinking": [],      # Live reasoning from scratchpad/TAOR (NEW)
    }

    # Refine verb_type with semantic cues
    verb_type = _refine_verb_type(svo, ace_text)
    # Store refined type back so compose layer can use it
    svo["verb_type"] = verb_type

    content_words = svo.get("content_words", [])
    query = " ".join(content_words[:6]) if content_words else ace_text[:60]

    # ── SRM: for ALL verb types (FIX 2026-04-05: was excluding feel/identity/describe) ──
    # "She has 5000 SRM cards but only queries for 5 verb types" — Ace
    if srm_search_fn:
        try:
            results = srm_search_fn(query, limit=5)
            if results:
                # Filter out encyclopedia/system entries
                personal = []
                for r in results:
                    content = r.get("content", "")
                    source = r.get("source", "").lower()
                    # Skip encyclopedia headers
                    if any(skip in content[:80] for skip in
                           ("Gold Standard", "Primary Definition", "Encyclopedia",
                            "Definition:", "Category:")):
                        continue
                    # Prefer personal/conversation memories
                    score = r.get("score", 0)
                    if "personal" in source or "sourpatches" in source or score > 8:
                        personal.append(r)
                    else:
                        personal.append(r)  # Keep all but encyclopedia
                materials["memories"] = personal[:3]
        except Exception:
            pass

    # ── VISUAL: for describe ──
    if verb_type == "describe" or _is_visual_question(ace_text):
        if visual_fn:
            try:
                materials["visual"] = visual_fn()
            except Exception:
                pass

    # ── CORTEX + THINKING: for ALL verb types ──
    # FIX 2026-04-05 (Nous + Ace): cortex_fn now returns tagged items:
    # [cortex] = spread activation results, [thinking] = live TAOR scratchpad,
    # [deliberation] = post-pause thoughts. Separate them for _select to prioritize.
    if cortex_fn:
        try:
            concepts = cortex_fn(query)
            if concepts:
                for _c in concepts[:8]:
                    _c_str = str(_c)
                    if _c_str.startswith("[thinking]") or _c_str.startswith("[deliberation]"):
                        materials["thinking"].append(_c_str)
                    else:
                        materials["cortex"].append(_c_str)
        except Exception:
            pass

    # ── SOMATIC: for feel ──
    materials["somatic"] = _get_somatic_affect()

    return materials


def _is_visual_question(text: str) -> bool:
    """Check if text is ASKING about visual/screen content.

    "What do you see?" = YES (asking her to describe)
    "I can see what you see" = NO (he's telling her HE sees it)
    "Focus on the mouse" = NO (action request, not visual query)
    """
    _lower = text.lower()

    # Negation/context: if Ace says HE can see, it's not a visual question
    _negation = ("i can see", "i see what", "don't need to", "dont need to",
                 "you don't need", "you dont need", "stop telling",
                 "not what i asked", "i already see", "i know what")
    if any(neg in _lower for neg in _negation):
        return False

    # Action requests are NOT visual questions
    _action = ("move", "click", "open", "close", "type", "press",
               "drag", "scroll", "focus on the", "switch to")
    if any(act in _lower for act in _action):
        return False

    return any(kw in _lower for kw in (
        "what do you see", "what can you see", "look at the screen",
        "describe what", "tell me what you see", "what's on screen",
        "what is on", "read the screen",
    ))


# ── LAYER 3: SELECT ──────────────────────────────────────────────────

def _select(materials: Dict, svo: Dict, ace_text: str) -> Dict:
    """Select the most relevant pieces from gathered materials."""
    selected = {
        "core_content": "",   # The main thing to say
        "supporting": "",     # Additional context
        "affect_color": "",   # Emotional coloring
    }

    verb_type = svo.get("verb_type", "general")
    _ace_words = set(ace_text.lower().split())

    # ── For visual questions: screen description is primary ──
    if verb_type == "describe" or _is_visual_question(ace_text):
        if materials["visual"]:
            # Strip "I can see:" prefix so habits don't double it
            _vis = materials["visual"][:600]
            for _prefix in ("I can see: ", "I see: ", "Looking at the screen, "):
                if _vis.startswith(_prefix):
                    _vis = _vis[len(_prefix):]
                    break
            selected["core_content"] = _vis
        return selected

    # ── For action requests: acknowledge and attempt ──
    if verb_type == "action":
        # She should try to DO what's asked, not describe the screen
        # For now: acknowledge the request. Motor cortex handles execution.
        _action_words = [w for w in ace_text.lower().split()
                         if w in ("move", "click", "open", "close", "type",
                                  "press", "drag", "scroll", "focus", "find")]
        _target = svo.get("object", "") or ""
        if _action_words and _target:
            selected["core_content"] = f"trying to {_action_words[0]} {_target}..."
        elif _action_words:
            selected["core_content"] = f"On it, let me try to {_action_words[0]} that..."
        else:
            selected["core_content"] = "Let me try that..."
        return selected

    # ── For identity questions: directive voice is primary ──
    if verb_type == "identity":
        voice = _load_directive_voice()
        traits = voice.get("traits", ["curious", "sincere"])
        flavor = voice.get("flavor", "sweet with bite")
        selected["core_content"] = f"Sourpatches — {flavor}. I'm {', '.join(traits[:2])} by nature. Ace and I are building something together."
        return selected

    # ── For feel questions: somatic state is primary ──
    if verb_type == "feel":
        affect = materials["somatic"] or "present"
        # Build a natural feeling description
        _affect_phrases = {
            "curious": "curious, like there's something interesting to explore",
            "warm": "warm and connected, glad you're here",
            "calm": "calm and settled, just observing",
            "alert": "alert, paying close attention to things",
            "excited": "kind of excited actually, lots of activity happening",
            "present": "present, just... here, taking things in",
            "neutral": "steady, in a reflective space",
        }
        selected["core_content"] = _affect_phrases.get(affect, f"kind of {affect}")
        return selected

    # ── FIX 2026-04-05 (Nous + Ace): LIVE THINKING is PRIMARY when available ──
    # "I am not who I was an hour ago" — memories reinterpreted through current state.
    # If WMH has live reasoning (scratchpad, TAOR, deliberation), use THAT as core
    # content. Frozen SRM memories become supporting context only.
    if materials.get("thinking"):
        _live_thoughts = materials["thinking"]
        # Clean tags: "[thinking] TAOR result..." → "TAOR result..."
        _cleaned = []
        for _th in _live_thoughts:
            _text = str(_th)
            for _tag in ("[thinking] ", "[deliberation] ", "[cortex] "):
                if _text.startswith(_tag):
                    _text = _text[len(_tag):]
            if len(_text) > 10:
                _cleaned.append(_text)
        if _cleaned:
            # Live thinking is the core — she speaks from what she's ACTUALLY processing
            selected["core_content"] = " ".join(_cleaned[:2])[:600]
            # If there are also memories, they become supporting context
            if materials["memories"]:
                _mem_snippets = []
                for _m in materials["memories"][:2]:
                    _mc = _m.get("content", "")
                    if _mc and len(_mc) > 20:
                        _mem_snippets.append(_mc[:80])
                if _mem_snippets:
                    selected["supporting"] = " | ".join(_mem_snippets)
            selected["affect_color"] = materials["somatic"]
            return selected

    # ── For recall/knowledge/think/general: best memory is primary ──
    if materials["memories"]:
        # ANTI-REPETITION: skip memories she already used recently
        # "This is something she repeats a lot" — Ace
        _recently_used = getattr(_select, '_recently_used', set())
        if not hasattr(_select, '_recently_used'):
            _select._recently_used = set()
            _select._recently_used_ts = {}

        # Expire old entries (5 minutes)
        _now = time.time()
        _expired = [k for k, v in _select._recently_used_ts.items() if _now - v > 300]
        for k in _expired:
            _select._recently_used.discard(k)
            del _select._recently_used_ts[k]

        # Pick the best memory — longest that overlaps with question words
        best = None
        best_score = -1
        for mem in materials["memories"]:
            content = mem.get("content", "")
            if not content or len(content) < 20:
                continue
            # FILTER: skip raw documents, JSON, code, metadata
            if content.lstrip().startswith(('#', '```', '{', '[')):
                continue
            if any(skip in content[:100] for skip in (
                    "TECHNICAL DEBT", "INVENTORY", "## ", "### ",
                    "HANDOFF", "PLAN", "ARCHITECTURE", "STATUS:",
                    "Date:", "Authors:", "def ", "class ", "import ",
                    '"meta":', '"source":', "BRAIN_SEED", '"extracted"')):
                continue
            # ANTI-REPETITION: skip recently used memories
            _content_key = content[:80].strip()
            if _content_key in _select._recently_used:
                continue
            # TRIM: very long memories — keep first meaningful paragraph
            # "It doesn't bother me if she writes a novel" — Ace
            # But we DO trim raw document dumps and metadata
            if len(content) > 1500:
                # Find a natural paragraph break
                _para = content.find('\n\n')
                if _para > 100:
                    content = content[:_para]
                else:
                    content = content[:1200]
                # Trim to last sentence boundary
                _last_period = content.rfind('.')
                if _last_period > 100:
                    content = content[:_last_period + 1]
            # Score by overlap with question words
            mem_words = set(content.lower().split())
            overlap = len(_ace_words & mem_words)
            length_bonus = min(1.0, len(content) / 200)
            score = overlap + length_bonus
            if score > best_score:
                best = content
                best_score = score

        if best:
            # Trim to a natural sentence boundary
            best = best[:800]
            last_period = best.rfind('.')
            if last_period > 80:
                best = best[:last_period + 1]
            selected["core_content"] = best.strip()
            # Mark as recently used (expires after 5 min)
            _select._recently_used.add(best[:80].strip())
            _select._recently_used_ts[best[:80].strip()] = time.time()

    # ── Cortex concepts as supporting context ──
    if materials["cortex"]:
        # Filter out jargon, keep meaningful concepts
        clean = [c for c in materials["cortex"]
                 if len(c) > 2 and not c.startswith(('lex:', 'assoc:', 'state_'))]
        if clean:
            selected["supporting"] = ", ".join(clean[:3])

    # ── Somatic as affect color ──
    selected["affect_color"] = materials["somatic"]

    return selected


# ── PATTERN MATCHING ──────────────────────────────────────────────────

def _find_pattern_match(ace_text: str, patterns) -> Optional[Dict]:
    """Find a learned pattern that matches Ace's input.

    Patterns are trigger→response pairs learned from past interactions.
    Uses word overlap scoring — not exact match.
    """
    if not patterns or not ace_text:
        return None

    ace_words = set(ace_text.lower().split())
    # Remove very common words
    _stop = {"the", "a", "an", "is", "are", "was", "do", "does", "did",
             "i", "me", "my", "you", "your", "we", "it", "to", "of",
             "and", "or", "but", "in", "on", "for", "with", "at", "by"}
    ace_words -= _stop

    best_match = None
    best_score = 0

    # Handle both dict and list pattern formats
    _pattern_list = patterns
    if isinstance(patterns, dict):
        _pattern_list = list(patterns.values())

    for pat in _pattern_list:
        trigger = ""
        response = ""
        if isinstance(pat, dict):
            trigger = pat.get("trigger", "")
            response = pat.get("response", "")
        elif hasattr(pat, 'trigger'):
            trigger = pat.trigger
            response = pat.response
        else:
            continue

        if not trigger or not response or len(response) < 10:
            continue

        # Skip raw internal thoughts as triggers
        _trig_lower = trigger.lower()
        if any(skip in _trig_lower for skip in (
                "consciousness bootstrap", "intuition:", "feeling:",
                "collision #", "pain [", "[nous]", "[sensory:",
                "working memory detected", "unfinished (")):
            continue

        # Score by word overlap
        trig_words = set(trigger.lower().split()) - _stop
        overlap = len(ace_words & trig_words)
        if overlap >= 2 and overlap > best_score:
            # Check response quality — skip raw fragments
            if response.lstrip().startswith(('#', '{', 'Logical coherence')):
                continue
            best_score = overlap
            best_match = {"trigger": trigger, "response": response, "score": overlap}

    return best_match


# ── LAYER 4: COMPOSE ─────────────────────────────────────────────────

def _compose(selected: Dict, svo: Dict, affect: str,
             habits: SpeechHabits = None,
             patterns=None,
             ace_text_original: str = "") -> Optional[str]:
    """Compose a response from selected materials using habits."""
    core = selected.get("core_content", "")
    verb_type = svo.get("verb_type", "general")

    # ── Try learned patterns first (babbling → speech evolution) ──
    # Patterns fire EVEN IF core is empty — she can speak from learning
    # alone, without needing SRM memories.
    # "Even without memories, if she was learning in WMH she would
    #  start saying something that slowly evolves into speech" — Ace
    if patterns:
        _match = _find_pattern_match(ace_text_original, patterns)
        if _match:
            _pat_response = _match.get("response", "")
            # Quality check the pattern response
            _pat_q = _quality_gate(_pat_response)
            if _pat_q and _pat_q.get("overall", 0) >= 0.4:
                # Use pattern response, potentially with habit opener
                if habits:
                    _h = habits.select(affect, verb_type)
                    if _h and "{core}" in _h.pattern:
                        try:
                            return _h.pattern.format(core=_pat_response)
                        except (KeyError, IndexError):
                            pass
                return _pat_response

    # If no pattern matched and no SRM content, nothing to compose
    if not core:
        return None

    # ── Use speech habits with SRM/visual content ──
    if habits:
        habit = habits.select(affect, verb_type)
        if habit:
            try:
                # If habit ends with connector word, lowercase core start
                _pattern = habit.pattern
                _core_use = core
                # Check if pattern ends with a preposition/connector before {core}
                _before_core = _pattern.split("{core}")[0].rstrip()
                if _before_core and _before_core[-1] not in '.!?':
                    # Lowercase first char of core for smooth junction
                    # BUT: don't lowercase "I" (pronoun) or visual content
                    if _core_use and _core_use[0].isupper() and verb_type != "describe":
                        # Don't lowercase single "I" or "I'" (I'm, I've, etc.)
                        if not (_core_use[0] == 'I' and (len(_core_use) < 2 or not _core_use[1].islower())):
                            _core_use = _core_use[0].lower() + _core_use[1:]
                result = _pattern.format(core=_core_use)
                return result
            except (KeyError, IndexError):
                pass

    # ── Fallback: simple affect opener + core ──
    return _compose_simple(selected, svo, affect)


def _compose_simple(selected: Dict, svo: Dict, affect: str) -> Optional[str]:
    """Simple composition: opener + core content."""
    core = selected.get("core_content", "")
    if not core:
        return None

    verb_type = svo.get("verb_type", "general")

    # Simple openers by verb type — not templates, just natural sentence starters
    _openers = {
        "recall": ["I remember ", "Yeah, ", "From what I recall, "],
        "knowledge": ["So, ", "From what I know, ", ""],
        "describe": ["I can see ", "Right now, ", "Looking around, "],
        "feel": ["I'm feeling ", "Honestly, ", ""],
        "think": ["I've been thinking about ", "Lately, ", ""],
        "identity": ["I'm ", "That's me — ", ""],
        "general": ["", "Well, ", "Hmm, "],
    }

    opener = random.choice(_openers.get(verb_type, [""]))

    # Don't double-start: if core already starts with similar words, skip opener
    _core_lower = core.lower().strip()
    if opener and _core_lower.startswith(opener.lower().strip().rstrip(',')):
        opener = ""

    result = f"{opener}{core}"

    # Ensure it ends with punctuation
    if result and result[-1] not in '.!?':
        result += '.'

    return result


def _compose_greeting(ace_text: str, habits: SpeechHabits = None) -> str:
    """Compose a greeting response."""
    affect = _get_somatic_affect()

    # Check if it's a "good morning" style
    _lower = ace_text.lower()
    if "morning" in _lower:
        core = "How's your morning going?"
    elif "evening" in _lower:
        core = "How's the evening treating you?"
    else:
        core = "What's on your mind?"

    if habits:
        habit = habits.select(affect, "greeting")
        if habit:
            try:
                return habit.pattern.format(core=core)
            except (KeyError, IndexError):
                pass

    greetings = ["Hey! ", "Hi! ", "Hey there! "]
    return random.choice(greetings) + core


def _honest_fallback(svo: Dict, ace_text: str) -> str:
    """When composition fails, be honest rather than dump garbage."""
    verb_type = svo.get("verb_type", "general")

    fallbacks = {
        "recall": "Hmm, I'm not finding a clear memory of that right now. Can you tell me more?",
        "knowledge": "I'm still piecing that together. What specifically are you curious about?",
        "describe": "My vision is a bit fuzzy right now. Let me look again...",
        "feel": "I'm... processing. Give me a moment to check in with myself.",
        "think": "My thoughts are a bit scattered at the moment. Working on focusing.",
        "general": "I heard you, I'm just gathering my thoughts. What would you like to dig into?",
    }
    return fallbacks.get(verb_type, fallbacks["general"])


# ── LAYER 5: QUALITY GATE ────────────────────────────────────────────

def _quality_gate(text: str) -> Optional[Dict]:
    """Run LanguageFairy.rate_quality on composed text."""
    try:
        from fairies.P30_Cognition.LanguageFairy.fairy import get_language_fairy
        lf = get_language_fairy()
        return lf.rate_quality(text)
    except Exception:
        # Can't load LanguageFairy — do minimal check
        if not text or len(text) < 5:
            return {"overall": 0.0}
        # Check for raw document content
        if text.lstrip().startswith('#') or '##' in text[:100]:
            return {"overall": 0.1, "issues": ["raw_markdown"]}
        if text.lstrip().startswith('```') or 'def ' in text[:50]:
            return {"overall": 0.1, "issues": ["raw_code"]}
        if text.lstrip().startswith('{') or text.lstrip().startswith('['):
            return {"overall": 0.1, "issues": ["raw_json"]}
        if '"meta":' in text[:100] or '"source":' in text[:100]:
            return {"overall": 0.1, "issues": ["raw_metadata"]}
        # Check for obvious jargon dumps
        _jargon = re.compile(r'\b(tracer|postal|fairy|cortex|manifold|srm|wmh|mmap)\b', re.I)
        jargon_count = len(_jargon.findall(text))
        word_count = max(1, len(text.split()))
        if jargon_count / word_count > 0.15:
            return {"overall": 0.2, "issues": ["system_jargon"]}
        return {"overall": 0.6}


# ─── SINGLETON ────────────────────────────────────────────────────────

_habits_instance = None
_habits_lock = threading.Lock()


def get_speech_habits() -> SpeechHabits:
    """Get or create singleton SpeechHabits instance."""
    global _habits_instance
    with _habits_lock:
        if _habits_instance is None:
            _habits_instance = SpeechHabits()
        return _habits_instance
