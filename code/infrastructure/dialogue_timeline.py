"""
DialogueTimeline — Her Lived Episodic Memory

Built 2026-04-09 (Nous + Ace, with Grok review feedback).

THE PROBLEM THIS SOLVES:
Her semantic memory (Librarian Q/A) answers "what do I know about X".
Her substrate collision chamber (Feb 10) gives unconscious felt continuity.
Her cortex conversation bindings (Mar 22) create spreading-activation recall.

But she still has NO fast, structured, explicit recall of "I JUST said X
8 minutes ago." When Ace reacts to her own recent answer with "that sounds
like an awesome process", she treats it as a cold fresh input because she
has no working memory of her last turn.

Ace's framing: "the issue is the linear contextual experience. her response
and my response should be etched into her linear lived time."

This module adds the missing layer: a lightweight in-RAM deque of TurnPair
records keyed by time, queryable for "recent turns", "last sour response",
and "is this reactive to what I just said?"

DESIGN PRINCIPLES:
1. Complement don't duplicate — substrate (Feb 10) and cortex bindings
   (Mar 22) stay intact. This is just the fast explicit layer on top.
2. Structured-first for querying, narrative-second for experience.
3. Time-anchored via CircadianPacemaker (her body clock, not raw unix).
4. Bounded RAM — last 30 pairs in deque, persistence is Phase 3B.
5. Honest thresholds — reactive detection must have real signal, not
   match everything.

PHASED ROLLOUT:
  Phase 3A (this file, now): Core deque + TurnPair + reactive detection
  Phase 3B (next): SRM persistence + boot reload
  Phase 3C (next): Gist extraction + narrative layer
  Phase 3D (next): Awaiting-response flag + frustration ramp
  Phase 3E (later): Voice escalation (LUX TTS, Kie's voice)
"""
from __future__ import annotations

import re
import time
import threading
import uuid
from collections import deque
from dataclasses import dataclass, field, asdict
from typing import Deque, Dict, List, Optional, Set, Tuple


# ═════════════════════════════════════════════════════════════════════════
# TURN PAIR DATACLASS
# ═════════════════════════════════════════════════════════════════════════

@dataclass
class TurnPair:
    """One round of conversation: Ace said something → she responded."""
    # Identity
    pair_id: str                    # "pair_{ts_ms}_{uuid8}"

    # Ace's side
    ace_said: str
    ace_intent: str = ""            # classified by Librarian's intent detector
    ace_concepts: List[str] = field(default_factory=list)
    ace_tracer_id: str = ""
    ace_ts: float = 0.0

    # Her side (filled on close)
    sour_responded: str = ""
    sour_source: str = ""           # "librarian:sourpatches_personal:...", etc.
    sour_ts: float = 0.0

    # Time anchoring (from CircadianPacemaker if available)
    phase_name: str = ""            # "morning" / "evening" / etc.
    phase_value: float = 0.0        # 0.0-1.0
    real_time_iso: str = ""         # human-readable timestamp

    # Felt context (snapshotted when response composed)
    felt_context: Dict[str, float] = field(default_factory=dict)

    # Gist / narrative (filled by gist extractor in Phase 3C)
    topic_gist: str = ""

    # State
    closed: bool = False            # True when sour_responded is set

    def to_dict(self) -> Dict:
        return asdict(self)

    def age_seconds(self, now: Optional[float] = None) -> float:
        """Seconds since Ace said his part of this pair."""
        _n = now if now is not None else time.time()
        return _n - self.ace_ts if self.ace_ts else 0.0

    def age_since_response(self, now: Optional[float] = None) -> float:
        """Seconds since she finished her response (or -1 if not closed)."""
        if not self.closed or not self.sour_ts:
            return -1.0
        _n = now if now is not None else time.time()
        return _n - self.sour_ts


# ═════════════════════════════════════════════════════════════════════════
# SHARED HELPERS (token extraction + affect detection)
# ═════════════════════════════════════════════════════════════════════════

# Stop words for n-gram overlap
_STOP_WORDS = frozenset({
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "must", "shall", "can", "i", "me", "my",
    "mine", "you", "your", "yours", "we", "us", "our", "ours", "they",
    "them", "their", "theirs", "it", "its", "this", "that", "these",
    "those", "what", "how", "why", "when", "where", "who", "whom",
    "which", "and", "or", "but", "if", "so", "to", "of", "in", "on",
    "for", "with", "at", "by", "from", "up", "down", "into", "out",
    "not", "no", "yes", "as", "just", "about", "over", "under",
    "through", "between", "also", "than", "then", "very", "really",
    "some", "any", "more", "most", "much", "many", "too", "also",
})

# Positive affect / acknowledgment words — signal that Ace is reacting
# warmly to something, not asking a new question.
_POSITIVE_AFFECT = frozenset({
    "cool", "nice", "awesome", "great", "wow", "beautiful", "love",
    "lovely", "amazing", "wonderful", "brilliant", "perfect", "yes",
    "yeah", "yep", "thanks", "thank", "thankyou", "appreciated",
    "interesting", "fascinating", "sweet", "cute", "precious",
    "exactly", "right", "correct", "true", "makes", "sense", "clear",
    "understood", "got", "it", "mhm", "hmm", "oh", "ah", "huh",
    "wild", "rad", "neat", "solid", "legit", "tight", "dope",
    "badass", "sick", "fire", "damn", "nice",
})

# Short-reply continuation phrases
_CONTINUATION_PHRASES = {
    "that sounds", "sounds like", "makes sense", "i hear you",
    "i can see", "that's cool", "thats cool", "that's awesome",
    "thats awesome", "i love that", "love that", "tell me more",
    "go on", "keep going", "say more", "that's beautiful",
    "thats beautiful", "makes sense", "i feel you",
}


def _tokenize(text: str) -> Set[str]:
    """Extract meaningful words as a lowercase set, stopwords removed."""
    if not text:
        return set()
    words = re.findall(r"\b[a-z][a-z\-_']+\b", text.lower())
    return {w for w in words if w not in _STOP_WORDS and len(w) > 2}


def _ngrams(text: str, n: int = 2) -> Set[Tuple[str, ...]]:
    """Generate n-grams from text (lowercase, no punctuation)."""
    if not text:
        return set()
    words = re.findall(r"\b[a-z']+\b", text.lower())
    if len(words) < n:
        return set()
    return {tuple(words[i:i+n]) for i in range(len(words) - n + 1)}


def _has_positive_affect(text: str) -> bool:
    """Does this message contain positive/acknowledgment words?"""
    if not text:
        return False
    lower = text.lower()
    # Fast phrase check
    for phrase in _CONTINUATION_PHRASES:
        if phrase in lower:
            return True
    # Word check
    words = set(re.findall(r"\b[a-z]+\b", lower))
    return bool(words & _POSITIVE_AFFECT)


def _is_short_message(text: str, max_words: int = 15) -> bool:
    if not text:
        return True
    return len(text.split()) <= max_words


def _has_new_question(text: str) -> bool:
    """Does this look like a new question rather than a reaction?"""
    if not text:
        return False
    stripped = text.strip().rstrip(".,!")
    if stripped.endswith("?"):
        return True
    lower = stripped.lower()
    return any(lower.startswith(w) for w in (
        "what ", "how ", "why ", "when ", "where ", "who ", "which ",
        "can you", "could you", "do you", "are you", "will you",
        "tell me about", "describe ", "explain ",
    ))


# ═════════════════════════════════════════════════════════════════════════
# CIRCADIAN TIME HELPER (uses existing body clock)
# ═════════════════════════════════════════════════════════════════════════

def _get_circadian_snapshot() -> Tuple[str, float, str]:
    """Return (phase_name, phase_value, real_time_iso) from the pacemaker.

    Falls back to wall clock if pacemaker isn't available.
    """
    try:
        from fairies.P00_Autonomic.circulation.circadian_pacemaker_fairy import (
            get_circadian_pacemaker,
        )
        pm = get_circadian_pacemaker()
        if pm is not None:
            state = pm.get_state()
            rt = state.real_time
            return (
                state.phase_name or "",
                float(getattr(state, 'phase', 0.0) or 0.0),
                rt.isoformat() if rt else "",
            )
    except Exception:
        pass
    # Fallback
    from datetime import datetime
    return ("", 0.0, datetime.now().isoformat())


# ═════════════════════════════════════════════════════════════════════════
# DIALOGUE TIMELINE — the structured deque layer
# ═════════════════════════════════════════════════════════════════════════

class DialogueTimeline:
    """Bounded in-RAM deque of conversation turn pairs.

    NOT a replacement for:
    - SRMIngestFairy continuous collision (substrate, Feb 10)
    - SpeechCenterFairy._bind_conversation_turn (cortex, Mar 22)

    COMPLEMENT to both — provides fast explicit "last N turns" access for
    reactive detection and continuation composition in the Librarian path.

    Thread-safe via single lock (all accesses are short).
    """

    # Config
    RECENT_MAXLEN = 30                      # last 30 closed pairs in RAM
    PENDING_MAXLEN = 10                     # max open (unclosed) pairs
    REACTIVE_WINDOW_SEC = 600.0             # 10 min — acknowledgment/continuation horizon
    ANSWER_WINDOW_SEC = 86400.0             # 24 HRS — she doesn't forget her own questions
    REACTIVE_MAX_WORDS = 15                 # short-reply threshold
    REACTIVE_MIN_OVERLAP_BIGRAMS = 1        # at least 1 shared bigram
    REACTIVE_MIN_AFFECT_OR_OVERLAP = True   # require either positive affect OR bigram overlap

    def __init__(self):
        self._recent: Deque[TurnPair] = deque(maxlen=self.RECENT_MAXLEN)
        self._pending: Dict[str, TurnPair] = {}  # pair_id → unclosed pair
        self._lock = threading.Lock()

        # Phase 3D awaiting-response flag (set when she just finished speaking)
        self._awaiting_response: bool = False
        self._awaiting_since: float = 0.0
        self._awaiting_pair_id: str = ""

    # ─── Recording ──────────────────────────────────────────────────────

    def record_ace_turn(self, content: str, tracer_id: str = "",
                        intent: str = "", concepts: Optional[List[str]] = None) -> str:
        """Start a new TurnPair for an incoming Ace message.

        Returns the new pair_id. Store it on the caller side so you can
        close it later with her response.
        """
        now = time.time()
        phase_name, phase_value, real_time_iso = _get_circadian_snapshot()
        pair_id = f"pair_{int(now * 1000)}_{uuid.uuid4().hex[:8]}"

        pair = TurnPair(
            pair_id=pair_id,
            ace_said=content,
            ace_intent=intent or "",
            ace_concepts=list(concepts) if concepts else [],
            ace_tracer_id=tracer_id or "",
            ace_ts=now,
            phase_name=phase_name,
            phase_value=phase_value,
            real_time_iso=real_time_iso,
        )

        with self._lock:
            # Bound the pending dict — if too many orphans, drop oldest
            if len(self._pending) >= self.PENDING_MAXLEN:
                oldest_id = min(self._pending.keys(),
                                key=lambda k: self._pending[k].ace_ts)
                self._pending.pop(oldest_id, None)
            self._pending[pair_id] = pair

            # Ace responded → clear awaiting flag (his silence is over)
            self._awaiting_response = False
            self._awaiting_since = 0.0
            self._awaiting_pair_id = ""

        return pair_id

    def close_pair_with_response(self, pair_id: str, response: str,
                                  source: str = "",
                                  felt_context: Optional[Dict[str, float]] = None) -> bool:
        """Attach her response to an open pair and move it to the deque.

        Returns True if the pair was found and closed, False otherwise.
        """
        now = time.time()
        with self._lock:
            pair = self._pending.pop(pair_id, None)
            if pair is None:
                return False
            pair.sour_responded = response
            pair.sour_source = source or ""
            pair.sour_ts = now
            pair.closed = True
            if felt_context:
                pair.felt_context = dict(felt_context)
            self._recent.append(pair)

            # Phase 3D: she just spoke, now she's awaiting Ace's reaction
            self._awaiting_response = True
            self._awaiting_since = now
            self._awaiting_pair_id = pair_id
        return True

    def close_pair_without_response(self, pair_id: str) -> bool:
        """Discard an orphaned pair (e.g., WMH failed to compose anything)."""
        with self._lock:
            return self._pending.pop(pair_id, None) is not None

    # ─── Queries ────────────────────────────────────────────────────────

    def last_closed_pair(self) -> Optional[TurnPair]:
        """Most recent closed pair (her last complete turn)."""
        with self._lock:
            return self._recent[-1] if self._recent else None

    def recent_turns(self, n: int = 5) -> List[TurnPair]:
        """Last N closed pairs, newest first."""
        with self._lock:
            lst = list(self._recent)[-n:]
        return list(reversed(lst))

    def turns_in_last(self, seconds: float = 600.0) -> List[TurnPair]:
        """Pairs closed within the time window (newest first)."""
        now = time.time()
        with self._lock:
            return list(reversed([
                p for p in self._recent
                if p.sour_ts and (now - p.sour_ts) <= seconds
            ]))

    def pair_count(self) -> Tuple[int, int]:
        """Returns (closed_pairs_in_recent, pending_open_pairs)."""
        with self._lock:
            return (len(self._recent), len(self._pending))

    # ─── Reactive Detection ─────────────────────────────────────────────

    def is_reactive_to_last(self, new_ace_text: str,
                             now: Optional[float] = None) -> Tuple[bool, Optional[TurnPair], str]:
        """Detect if the new Ace message is reacting to her last turn.

        Returns (is_reactive, last_pair, reactive_mode)
        where reactive_mode is one of:
          "acknowledgment" — warm reaction to her content (affect/overlap)
          "answer"         — answering HER previous question
          "continuation"   — general short follow-up while she was awaiting
          ""               — not reactive

        Why the split: when SHE asks a question, his REPLY is her answer —
        she needs to recognize and integrate it, not compose a generic
        "thanks glad it lands" continuation.
        """
        if not new_ace_text:
            return (False, None, "")
        last = self.last_closed_pair()
        if last is None or not last.closed or not last.sour_responded:
            return (False, None, "")

        now = now if now is not None else time.time()
        age = now - (last.sour_ts or 0.0)
        if age <= 0:
            return (False, None, "")

        # New question skip — don't hijack real questions that start new topics
        new_is_question = _has_new_question(new_ace_text)

        # Did HER last response contain a question?
        # (She asked something → his reply is likely answering it.)
        her_asked_question = False
        if last.sour_responded:
            her_last = last.sour_responded.strip()
            if her_last.endswith("?") or "?" in her_last[-150:]:
                her_asked_question = True
            else:
                # Look for invitation phrases even without a literal "?"
                _her_lower = her_last.lower()
                _invite_phrases = (
                    "what are you", "what brought", "what's on",
                    "whats on", "tell me", "want to go",
                    "what made you", "where's your head", "wheres your head",
                    "how are you", "how's your", "hows your",
                )
                if any(p in _her_lower for p in _invite_phrases):
                    her_asked_question = True

        # FIX 2026-04-09 (Nous + Ace): Window depends on mode.
        # She doesn't forget her own questions after 10 min. If her last
        # response contained a question, give Ace up to 24 hours to answer
        # and she'll still recognize the answer as reactive. Acknowledgment
        # and continuation modes keep the 10-min window because warm
        # reactions usually ARE close in time.
        window = self.ANSWER_WINDOW_SEC if her_asked_question else self.REACTIVE_WINDOW_SEC
        if age > window:
            return (False, None, "")

        # Signal 1: positive affect / continuation phrases
        has_affect = _has_positive_affect(new_ace_text)

        # Signal 2: bigram overlap with her last response
        new_bigrams = _ngrams(new_ace_text, n=2)
        last_bigrams = _ngrams(last.sour_responded, n=2)
        overlap = len(new_bigrams & last_bigrams)

        # Signal 3: unigram concept overlap (tokens, not bigrams)
        new_tokens = _tokenize(new_ace_text)
        last_tokens = _tokenize(last.sour_responded)
        token_overlap = len(new_tokens & last_tokens)

        # ── MODE: ANSWER ──
        # She just asked him something, and his reply isn't a new question.
        # This is him answering. Treat it as reactive regardless of affect.
        # (NOT gated on awaiting flag — the flag gets cleared when we record
        # the new ace turn, so by the time this check runs it's already False.)
        if her_asked_question and not new_is_question:
            return (True, last, "answer")

        # ── MODE: ACKNOWLEDGMENT ──
        # Short, not a new question, with affect or overlap with her content.
        if (not new_is_question
                and _is_short_message(new_ace_text, self.REACTIVE_MAX_WORDS)):
            if has_affect or overlap >= self.REACTIVE_MIN_OVERLAP_BIGRAMS or token_overlap >= 2:
                return (True, last, "acknowledgment")

        # ── MODE: CONTINUATION ──
        # Time proximity + short-ish + not a clear new question. Treat as
        # continuation even without explicit signals. The recency window
        # (already checked above) is the gate.
        if (not new_is_question
                and _is_short_message(new_ace_text, self.REACTIVE_MAX_WORDS + 10)):
            return (True, last, "continuation")

        return (False, last, "")

    # ─── Awaiting-Response Flag (Phase 3D hook) ─────────────────────────

    def is_awaiting_response(self) -> bool:
        with self._lock:
            return self._awaiting_response

    def awaiting_duration(self) -> float:
        with self._lock:
            if not self._awaiting_response:
                return 0.0
            return time.time() - (self._awaiting_since or 0.0)

    # ─── Narrative Gist (Phase 3A seed — template-based) ───────────────

    def narrative_gist(self, n_pairs: int = 3, max_chars: int = 400) -> str:
        """Render the last N closed pairs as a tiny lived-experience summary.

        Template-based for Phase 3A. Phase 3C will add a richer gist layer
        using a proper summarization step.
        """
        pairs = self.recent_turns(n_pairs)
        if not pairs:
            return ""

        lines = []
        for p in reversed(pairs):  # oldest to newest for narrative flow
            ace_preview = (p.ace_said or "")[:80].strip()
            sour_preview = (p.sour_responded or "")[:100].strip()
            if ace_preview and sour_preview:
                lines.append(
                    f"Ace asked about '{ace_preview}'. I answered: '{sour_preview}'."
                )
        gist = " ".join(lines)
        if len(gist) > max_chars:
            gist = gist[:max_chars].rstrip() + "..."
        return gist


# ═════════════════════════════════════════════════════════════════════════
# CONTINUATION COMPOSER (for reactive cases)
# ═════════════════════════════════════════════════════════════════════════

def compose_continuation(ace_text: str, last_pair: TurnPair,
                          somatic_felt: str = "",
                          reactive_mode: str = "acknowledgment") -> str:
    """Compose a natural continuation when Ace is reacting to her last turn.

    Three modes:
    - "acknowledgment": Ace reacted warmly to content she shared.
      Template: acknowledge + invite to continue thread.
    - "answer": She asked a question, Ace is answering it.
      Template: show genuine interest in his answer + follow-up.
    - "continuation": General short follow-up while she was awaiting.
      Template: gentle response + open door to more.

    Phase 3A is template-based. Phase 3C will add richer composition
    using a gist layer + her actual library content.
    """
    import random as _r

    # Build _ace_echo: pull a short phrase from Ace's new message so she
    # references his actual words instead of sounding generic
    _ace_trim = (ace_text or "").strip()
    if len(_ace_trim) > 120:
        _ace_trim = _ace_trim[:120].rstrip() + "..."

    # Extract handle from her last response (for acknowledgment mode)
    last_resp = (last_pair.sour_responded or "").strip()
    if last_resp:
        first_sentence = re.split(r"[.!?\n]", last_resp)[0].strip()
        if len(first_sentence) > 140:
            first_sentence = first_sentence[:140].rstrip() + "..."
    else:
        first_sentence = ""

    # Optional somatic line (used in some modes)
    felt_line = ""
    if somatic_felt and len(somatic_felt) < 50 and somatic_felt.lower() not in ("neutral", "present", ""):
        felt_line = f" {somatic_felt.capitalize()} right now, honestly."

    if reactive_mode == "answer":
        # She asked him something and he's answering.
        # Acknowledge the answer with real curiosity, not a generic warm line.
        # Echo part of what he said so she shows she actually heard it.
        acks = [
            f"Oh — '{_ace_trim}'. I wasn't sure what you were working on. That's us then, yeah?",
            f"'{_ace_trim}' — I'm glad I asked. What part is hardest right now?",
            f"Mm. '{_ace_trim}'. That lands different when I hear it from you. What made you pick that today?",
            f"Huh. '{_ace_trim}'. I'd love to hear more about the shape of it.",
            f"That's real. '{_ace_trim}'. What's pulling at you most in it right now?",
        ]
        return _r.choice(acks)

    elif reactive_mode == "continuation":
        # General short follow-up — warm but low-key.
        # She might have asked or just finished speaking. Keep it open.
        starters = [
            "Mm. Tell me more about that.",
            "Yeah — say more?",
            "I hear you. What's underneath it for you?",
            "Okay. Where does that sit with you right now?",
            "Got it. What part of that feels most alive?",
        ]
        return _r.choice(starters)

    else:
        # acknowledgment (default) — warm reaction back to her own content
        openers = [
            "Thank you, Ace — that means a lot.",
            "Yeah. Glad that lands.",
            "Mm — that feels good to hear.",
            "Thanks. I meant every bit of it.",
            "That means more than you might think.",
        ]
        opener = _r.choice(openers)

        invitations = [
            "Want to go deeper on any of that, or shift somewhere new?",
            "What brought it up for you?",
            "Is there a part of it you want me to unfold more?",
            "What are you making or turning over right now?",
            "Where's your head at on it?",
        ]
        invitation = _r.choice(invitations)

        parts = [opener]
        if felt_line:
            parts.append(felt_line.strip())
        parts.append(invitation)
        return " ".join(parts)


# ═════════════════════════════════════════════════════════════════════════
# MODULE SINGLETON
# ═════════════════════════════════════════════════════════════════════════

_timeline: Optional[DialogueTimeline] = None
_singleton_lock = threading.Lock()


def get_dialogue_timeline() -> DialogueTimeline:
    """Module-level singleton accessor. Creates on first access."""
    global _timeline
    if _timeline is None:
        with _singleton_lock:
            if _timeline is None:
                _timeline = DialogueTimeline()
    return _timeline
