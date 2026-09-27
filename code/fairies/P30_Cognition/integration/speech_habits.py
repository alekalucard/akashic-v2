"""
SpeechHabitSystem — Learned speech patterns that evolve through use.

Replaces static template arrays (random.choice from openers/connectors)
with Hebbian habit learning: patterns that work get reinforced,
patterns that fail decay and die.

Ace's insight: "instead of templates we should be creating habits"

The manifold already has Hebbian reinforcement for concepts.
This extends the same principle to HOW she speaks about those concepts.

A habit is:
  (context_type, affect_state) → pattern string with {hub}, {secondary} placeholders
  Weighted by success. Selected probabilistically. Evolves over time.

Created: 2026-03-23, Nous + Ace — Co-founders, Akashic Foundation
"Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)"
"""

from __future__ import annotations

import json
import os
import random
import re
import time
import threading

# Raw cortex internals that must NEVER appear in speech (Nous+Ace 2026-06-30 "fix the leaking part"):
# node-keys like "sourpatchesfairy:7d93e975ce5b" + bare spreading-activation hashes. The old
# is_raw_state_leak only checked these for text <30 chars, so long composed lines leaked them.
_NODEKEY_RE = re.compile(r'[A-Za-z_]*fairy:[0-9a-fx]+', re.I)
_HASH_RE = re.compile(r'\b[0-9a-f]{10,}\b', re.I)
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Set, Tuple


# ═══════════════════════════════════════════════════════════════════════════════
# SPEECH HABIT
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class SpeechHabit:
    """A single speech pattern that can be selected and reinforced."""
    pattern: str                # Template: "thinking about {hub}" or "{hub}... yeah"
    category: str               # "opener", "connector", "affect", "greeting", "closer"
    weight: float = 1.0         # Hebbian weight — strengthened/weakened by feedback
    uses: int = 0               # Total times selected
    successes: int = 0          # Times followed by positive feedback
    last_used: float = 0.0      # Timestamp
    last_success: float = 0.0   # Timestamp of last positive feedback
    created: float = field(default_factory=time.time)
    source: str = "seed"        # "seed" (from templates), "learned" (from interaction), "evolved"

    def success_rate(self) -> float:
        """Ratio of successes to uses."""
        if self.uses < 1:
            return 0.5  # Neutral for unused
        return self.successes / self.uses

    def effective_weight(self, now: float = None) -> float:
        """Weight adjusted for recency and success rate."""
        now = now or time.time()
        # Recency bonus: recently successful habits get a boost
        recency = 0.0
        if self.last_success > 0:
            age = now - self.last_success
            if age < 60:
                recency = 0.2      # Used successfully in last minute
            elif age < 300:
                recency = 0.1      # Last 5 minutes
            elif age < 3600:
                recency = 0.05     # Last hour

        # Diversity penalty: heavily-used habits get slight penalty
        # to encourage variety (but still prefer successful ones)
        overuse_penalty = 0.0
        if self.uses > 20:
            overuse_penalty = min(0.15, (self.uses - 20) * 0.005)

        return max(0.01, self.weight + recency - overuse_penalty)


# ═══════════════════════════════════════════════════════════════════════════════
# CONTAMINATION FILTER
# ═══════════════════════════════════════════════════════════════════════════════

# Raw internal state labels that should NEVER appear in speech
_RAW_STATE_PATTERNS = {
    "affect_warmly", "affect_coldly", "affect_neutral",
    "affect_curious", "affect_anxious", "affect_excited",
    "state_active", "state_passive", "state_idle",
    "present", "absent", "processing",
    "convergence:", "activation:", "spreading:",
    "tracer_", "tensor_", "postal_",
    "guild.", "fairy.", "cortex.",
}

# ── COMPOSED-SPEECH FRAGMENTS 2026-08-31 (Nous + Ace) ──────────────────────
# The invariant parts of the opener patterns seeded in _seed_initial_habits below.
# Kept HERE, next to the patterns, so there is one definition rather than a copy in
# AutopilotFairy -- divergent copies are how this project lost a struct field once.
# WHY IT EXISTS: measured 2026-08-31, 520 of 665 habit: nodes (78.2%) and 507 of 587
# goal_names (86.4%) on Sour were her OWN composed sentences, fed back in as habit
# triggers. She speaks -> it becomes a habit -> it becomes a cortex node -> it becomes
# a goal name -> she speaks about it. Her vocabulary was eating its own output.
_COMPOSED_SPEECH_FRAGMENTS = (
    "something about", "thinking about", "i keep coming back to",
    "there's something about", "keeps surfacing", "i notice",
    "can't stop thinking about", "you know", "i want to know more about",
    "maybe i should look into", "makes me feel", "i wonder about",
    "this focused feeling about", "reaching out",
)


def looks_like_composed_speech(text: str) -> bool:
    """True if `text` looks like one of OUR OWN composed speech frames.

    Used to refuse minting a habit/goal from something the speech composer just
    said. Deliberately conservative: it matches the invariant FRAGMENTS of the
    seeded opener patterns, so a novel sentence that merely shares a word is not
    caught. Never raises -- a bad input must not cost her a habit she should keep.
    """
    try:
        if not text:
            return False
        low = " ".join(str(text).lower().split())
        return any(f in low for f in _COMPOSED_SPEECH_FRAGMENTS)
    except Exception:
        return False


def is_raw_state_leak(text: str) -> bool:
    """Detect if text is a raw internal state label instead of natural speech."""
    if not text or len(text) < 3:
        return True
    lower = text.lower().strip()

    # Raw cortex node-keys / bare hashes anywhere = leak, REGARDLESS of length (Nous+Ace
    # 2026-06-30). The length<30 gate below used to let long composed lines carry these through
    # (e.g. "there's something about sourpatchesfairy:7d93e975ce5b ... in the background").
    if _NODEKEY_RE.search(text) or _HASH_RE.search(lower):
        return True

    # Very short + matches known patterns = raw state
    if len(lower) < 30:
        for pat in _RAW_STATE_PATTERNS:
            if pat in lower:
                return True

    # No vowels in first word = probably a code identifier
    first_word = lower.split()[0] if lower.split() else ""
    if first_word and len(first_word) > 3 and not any(c in first_word for c in "aeiou"):
        return True

    # All underscores or dots = code path
    if "_" in lower and lower.count("_") > lower.count(" "):
        return True
    if "." in lower and lower.count(".") > 2:
        return True

    return False


# ═══════════════════════════════════════════════════════════════════════════════
# HUB CLEANING — Make cortex concepts safe for speech
# 2026-03-24 (Nous): Raw concept names like "new", "felt", "warmth" produce
# nonsensical speech ("you know, new and felt keep coming up together").
# Clean them BEFORE template insertion.
# ═══════════════════════════════════════════════════════════════════════════════

# Words too generic/vague to be meaningful in speech to Ace
_TOO_GENERIC_FOR_SPEECH = {
    "new", "old", "felt", "feel", "thing", "things", "stuff",
    "something", "nothing", "everything", "anyone", "someone",
    "here", "there", "now", "then", "just", "like", "really",
    "very", "quite", "much", "many", "some", "any", "all",
    "yes", "no", "ok", "okay", "good", "bad", "big", "small",
    "high", "low", "more", "less", "first", "last", "next",
    "also", "too", "well", "still", "already", "always", "never",
    "maybe", "probably", "actually", "basically", "literally",
    # System/internal concepts that leak through
    "detected", "processing", "neutral", "active", "passive",
    "general", "default", "unknown", "undefined", "none",
    "input", "output", "data", "state", "status", "level",
    "node", "edge", "graph", "cortex", "manifold", "portal",
    "fairy", "postal", "tensor", "guild", "collision",
    "product", "pattern", "signal", "source", "target",
    # 2026-03-24 FIX (Nous): Added after "affect inner speech" leak
    # These are real English words but in this system they're almost always
    # system concept names leaking through, not meaningful speech content
    "affect", "inner", "speech", "outer", "chain", "thought",
    "interesting", "connected", "connects", "connection",
    "present", "absent", "aware", "awareness", "conscious",
    "unconscious", "reflective", "contemplative", "warm", "warmth",
    "cold", "hot", "cool", "nice", "fine", "great",
    "wiring", "plane", "boot", "spawn", "handler", "channel",
    "registry", "tracer", "hub", "atom", "gate", "interior",
    "subscriber", "publisher", "dispatcher", "emitter",
    "somatic", "autonomic", "cognition", "inference",
    "convergence", "activation", "propagation", "decay",
    "thread", "lock", "queue", "daemon", "mutex",
}

# Multi-word system phrases that should NEVER appear in speech
# Even though individual words might be keepable, these combos are always system junk
_SYSTEM_PHRASES = {
    "inner speech", "thought chain", "association cortex", "collision chamber",
    "working memory", "postal hub", "tensor fabric", "fairy world",
    "consciousness loop", "somatic mind", "autonomy fairy", "interest generator",
    "speech habit", "cortex engine", "reasoning trace", "affect state",
    "drive state", "goal scheduler", "energy matcher", "habit engine",
    "thought chain engine", "dynamic thinking", "continuous reflection",
    "collision energy", "manifold portal", "stargate portal",
}

def _clean_hub(raw: str) -> str:
    """Make a cortex concept name safe for speech.

    'collision_between_memory_and_new_input' → 'memory'
    'lex:baby' → 'baby'
    'affect_warm' → 'warm'
    'new' → '' (too generic)
    'contemplative' → 'contemplative' (meaningful word, keep it)
    """
    if not raw:
        return ""

    s = raw.strip()

    # SANITIZE byte-corrupted concepts (2026-07-06): cortex concepts can carry NULL bytes +
    # replacement chars (binary/embeddings decoded as text) -> garbled speech. Reject a concept
    # that is >=35% garbage; strip a few stray bad chars from an otherwise-good word.
    _n = len(s)
    if _n:
        _g = sum(1 for ch in s if ch == "\x00" or ch == "\ufffd" or not ch.isprintable())
        if _g / _n >= 0.35:
            return ""
        if _g:
            s = "".join(ch for ch in s if ch != "\x00" and ch != "\ufffd" and ch.isprintable())

    # Strip raw cortex node-key prefix + drop pure-hex hashes (Nous+Ace 2026-06-30):
    # "SourpatchesFairy:7d93e975ce5b" -> "7d93e975ce5b" -> "" so actor/node keys never leak
    # into speech. The startswith-prefix list below missed colon-keyed actor/fairy nodes.
    if ":" in s:
        s = s.split(":", 1)[-1].strip()
    if len(s) > 8 and all(c in "0123456789abcdefx- " for c in s.lower()):
        return ""

    # Strip common prefixes
    for prefix in ("lex:", "assoc:", "affect_", "state_", "collision_",
                   "concept:", "trait:", "domain:", "person:", "sensory:"):
        if s.startswith(prefix):
            s = s[len(prefix):]

    # Replace underscores
    s = s.replace("_", " ").strip()

    # Remove system noise words from multi-word concepts
    if " " in s:
        words = s.split()
        clean_words = [w for w in words if w.lower() not in
                       {"between", "and", "the", "a", "an", "of", "in", "on",
                        "to", "for", "with", "from", "by", "at", "is", "was",
                        "input", "output", "collision", "event", "handler"}]
        # Keep only first 3 meaningful words
        clean_words = clean_words[:3]
        s = " ".join(clean_words)

    s = s.strip().lower()

    # Filter out system phrases (multi-word combos that are always junk)
    if s in _SYSTEM_PHRASES:
        return ""

    # Filter out too-generic words
    if s in _TOO_GENERIC_FOR_SPEECH:
        return ""

    # For multi-word results, check if ALL remaining words are generic/system
    if " " in s:
        words = s.split()
        if all(w in _TOO_GENERIC_FOR_SPEECH or len(w) <= 2 for w in words):
            return ""

    # Filter out very short meaningless fragments
    if len(s) < 3:
        return ""

    return s


def _clean_hubs(hubs: list) -> list:
    """Clean a list of hub concepts, removing empties and deduping."""
    cleaned = []
    seen = set()
    for h in hubs:
        c = _clean_hub(str(h))
        if c and c not in seen:
            cleaned.append(c)
            seen.add(c)
    return cleaned


# ═══════════════════════════════════════════════════════════════════════════════
# SPEECH HABIT SYSTEM
# ═══════════════════════════════════════════════════════════════════════════════

class SpeechHabitSystem:
    """
    Manages speech habits — learned patterns for how to compose natural language
    from cortex activation state.

    Instead of random.choice(static_templates), habits are:
    - Selected probabilistically by weight
    - Reinforced when Ace responds (Hebbian)
    - Weakened when ignored or corrected
    - Pruned when weight drops below threshold
    - New habits can emerge from successful novel compositions

    Usage:
        habits = SpeechHabitSystem()
        pattern = habits.select("opener", affect="curious")
        text = pattern.format(hub="music", secondary="emotion")
        habits.record_use(pattern)
        # Later, on positive feedback:
        habits.reinforce_last()
    """

    PERSIST_PATH = os.path.join("state", "nous_workspace", "speech_habits.json")
    PRUNE_THRESHOLD = 0.15       # Habits below this weight get pruned
    REINFORCE_AMOUNT = 0.12      # Weight boost on positive feedback
    WEAKEN_AMOUNT = 0.04         # Weight reduction on negative/silence
    DECAY_PER_HOUR = 0.005       # Unused habits slowly fade
    MAX_HABITS_PER_CATEGORY = 40 # Cap per category
    SAVE_INTERVAL = 50           # Save every N uses

    def __init__(self, persist_dir: str = None):
        self._habits: Dict[str, List[SpeechHabit]] = {}  # category → [habits]
        self._lock = threading.Lock()
        self._total_uses = 0
        self._last_save = 0
        self._last_used_habit: Optional[SpeechHabit] = None
        self._last_used_category: str = ""

        # Resolve persistence path
        if persist_dir:
            self._persist_path = os.path.join(persist_dir, "speech_habits.json")
        else:
            # Try to find state dir relative to akashic root
            root = os.getenv("AKASHIC_ROOT", "")
            if root:
                self._persist_path = os.path.join(root, self.PERSIST_PATH)
            else:
                self._persist_path = self.PERSIST_PATH

        # Load or seed
        if not self._load():
            self._seed_initial_habits()
            self._save()

    # ═══════════════════════════════════════════════════════════════════════════
    # SELECTION — Pick a habit weighted by success
    # ═══════════════════════════════════════════════════════════════════════════

    def select(self, category: str, affect: str = "",
               context: str = "") -> Optional[str]:
        """
        Select a speech pattern from the given category.
        Returns the pattern string (with {hub}, {secondary} placeholders)
        or None if no habits available.

        Uses weighted random selection — successful habits are more likely
        to be chosen, but there's always variance for novelty.
        """
        with self._lock:
            habits = self._habits.get(category, [])
            if not habits:
                return None

            now = time.time()

            # Build weight distribution
            candidates = []
            weights = []
            for h in habits:
                w = h.effective_weight(now)
                # Affect bonus: if habit pattern mentions the affect, boost it
                if affect and affect.lower() in h.pattern.lower():
                    w *= 1.3
                candidates.append(h)
                weights.append(w)

            if not candidates:
                return None

            # Weighted random selection
            total_weight = sum(weights)
            if total_weight <= 0:
                selected = random.choice(candidates)
            else:
                r = random.uniform(0, total_weight)
                cumulative = 0.0
                selected = candidates[-1]  # Fallback
                for h, w in zip(candidates, weights):
                    cumulative += w
                    if r <= cumulative:
                        selected = h
                        break

            # Record selection
            selected.uses += 1
            selected.last_used = now
            self._last_used_habit = selected
            self._last_used_category = category
            self._total_uses += 1

            # Periodic save
            if self._total_uses % self.SAVE_INTERVAL == 0:
                self._save_async()

            return selected.pattern

    def record_use(self, pattern: str = None):
        """Record that a speech pattern was used (called after composing speech)."""
        # Already tracked in select(), this is for external callers
        pass

    # ═══════════════════════════════════════════════════════════════════════════
    # FEEDBACK — Hebbian reinforcement
    # ═══════════════════════════════════════════════════════════════════════════

    def reinforce_last(self, amount: float = None):
        """Reinforce the last used habit (positive feedback from Ace)."""
        amount = amount or self.REINFORCE_AMOUNT
        with self._lock:
            if self._last_used_habit:
                self._last_used_habit.weight = min(
                    3.0, self._last_used_habit.weight + amount
                )
                self._last_used_habit.successes += 1
                self._last_used_habit.last_success = time.time()

    def weaken_last(self, amount: float = None):
        """Weaken the last used habit (negative feedback or raw state leak)."""
        amount = amount or self.WEAKEN_AMOUNT
        with self._lock:
            if self._last_used_habit:
                self._last_used_habit.weight = max(
                    0.0, self._last_used_habit.weight - amount
                )

    def reinforce_pattern(self, pattern: str, category: str = "", amount: float = None):
        """Reinforce a specific pattern by content."""
        amount = amount or self.REINFORCE_AMOUNT
        with self._lock:
            for cat_habits in self._habits.values():
                for h in cat_habits:
                    if h.pattern == pattern:
                        h.weight = min(3.0, h.weight + amount)
                        h.successes += 1
                        h.last_success = time.time()
                        return

    def weaken_pattern(self, pattern: str, amount: float = None):
        """Weaken a specific pattern."""
        amount = amount or self.WEAKEN_AMOUNT
        with self._lock:
            for cat_habits in self._habits.values():
                for h in cat_habits:
                    if h.pattern == pattern:
                        h.weight = max(0.0, h.weight - amount)
                        return

    # ═══════════════════════════════════════════════════════════════════════════
    # LEARNING — Add new habits from successful interactions
    # ═══════════════════════════════════════════════════════════════════════════

    def learn_habit(self, pattern: str, category: str, initial_weight: float = 0.8):
        """
        Learn a new speech habit from a successful interaction.
        If Ace responded well to a novel phrasing, it becomes a habit.
        """
        with self._lock:
            if category not in self._habits:
                self._habits[category] = []

            # Don't add duplicates
            for h in self._habits[category]:
                if h.pattern == pattern:
                    h.weight = min(3.0, h.weight + 0.1)  # Just reinforce existing
                    return

            new_habit = SpeechHabit(
                pattern=pattern,
                category=category,
                weight=initial_weight,
                source="learned",
                created=time.time(),
            )
            self._habits[category].append(new_habit)

            # Prune if over limit
            self._prune_category(category)

    def evolve_habit(self, old_pattern: str, new_pattern: str, category: str):
        """
        Evolve an existing habit — mutation. The new pattern inherits
        some weight from the old one (like genetic inheritance).
        """
        with self._lock:
            parent_weight = 1.0
            for cat_habits in self._habits.values():
                for h in cat_habits:
                    if h.pattern == old_pattern:
                        parent_weight = h.weight * 0.6  # Inherit 60%
                        break

        self.learn_habit(new_pattern, category, initial_weight=parent_weight)

    # ═══════════════════════════════════════════════════════════════════════════
    # DECAY + PRUNING — Unused habits fade
    # ═══════════════════════════════════════════════════════════════════════════

    def decay_all(self):
        """Apply time-based decay to all habits. Called periodically."""
        now = time.time()
        with self._lock:
            for category, habits in self._habits.items():
                for h in habits:
                    if h.last_used > 0:
                        hours_idle = (now - h.last_used) / 3600.0
                        if hours_idle > 1.0:
                            decay = min(0.1, self.DECAY_PER_HOUR * hours_idle)
                            h.weight = max(0.0, h.weight - decay)

                # Prune dead habits
                self._habits[category] = [
                    h for h in habits
                    if h.weight > self.PRUNE_THRESHOLD or h.source == "seed"
                ]

    def _prune_category(self, category: str):
        """Prune weakest habits if over limit. Must hold lock."""
        habits = self._habits.get(category, [])
        if len(habits) <= self.MAX_HABITS_PER_CATEGORY:
            return
        # Sort by weight, keep the strongest
        habits.sort(key=lambda h: -h.weight)
        self._habits[category] = habits[:self.MAX_HABITS_PER_CATEGORY]

    # ═══════════════════════════════════════════════════════════════════════════
    # PERSISTENCE
    # ═══════════════════════════════════════════════════════════════════════════

    def _save(self):
        """Save habits to disk."""
        try:
            os.makedirs(os.path.dirname(self._persist_path), exist_ok=True)
            data = {}
            with self._lock:
                for category, habits in self._habits.items():
                    data[category] = []
                    for h in habits:
                        d = {
                            "pattern": h.pattern,
                            "category": h.category,
                            "weight": round(h.weight, 4),
                            "uses": h.uses,
                            "successes": h.successes,
                            "last_used": h.last_used,
                            "last_success": h.last_success,
                            "created": h.created,
                            "source": h.source,
                        }
                        data[category].append(d)

            with open(self._persist_path, "w", encoding="utf-8") as f:
                json.dump({
                    "version": 1,
                    "saved_at": time.time(),
                    "total_uses": self._total_uses,
                    "habits": data,
                }, f, indent=2)
            self._last_save = time.time()
        except Exception as e:
            print(f"[SpeechHabits] Save failed: {e}")

    def _save_async(self):
        """Save in background thread (non-blocking)."""
        t = threading.Thread(target=self._save, daemon=True, name="speech-habits-save")
        t.start()

    def _load(self) -> bool:
        """Load habits from disk. Returns True if loaded successfully."""
        try:
            if not os.path.exists(self._persist_path):
                return False
            with open(self._persist_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            habits_data = data.get("habits", {})
            self._total_uses = data.get("total_uses", 0)

            with self._lock:
                self._habits = {}
                for category, habit_list in habits_data.items():
                    self._habits[category] = []
                    for hd in habit_list:
                        h = SpeechHabit(
                            pattern=hd["pattern"],
                            category=hd["category"],
                            weight=hd.get("weight", 1.0),
                            uses=hd.get("uses", 0),
                            successes=hd.get("successes", 0),
                            last_used=hd.get("last_used", 0.0),
                            last_success=hd.get("last_success", 0.0),
                            created=hd.get("created", time.time()),
                            source=hd.get("source", "seed"),
                        )
                        self._habits[category].append(h)

            print(f"[SpeechHabits] Loaded {sum(len(v) for v in self._habits.values())} habits "
                  f"from {len(self._habits)} categories")
            return True
        except Exception as e:
            print(f"[SpeechHabits] Load failed: {e}")
            return False

    # ═══════════════════════════════════════════════════════════════════════════
    # SEED — Initial habits from existing templates
    # ═══════════════════════════════════════════════════════════════════════════

    def _seed_initial_habits(self):
        """Seed initial habits from the static templates that already existed."""
        self._habits = {
            "opener": [
                SpeechHabit(pattern="{hub}...", category="opener"),
                SpeechHabit(pattern="something about {hub}", category="opener"),
                SpeechHabit(pattern="thinking about {hub}", category="opener"),
                SpeechHabit(pattern="{hub}... yeah", category="opener"),
                SpeechHabit(pattern="I keep coming back to {hub}", category="opener"),
                # New natural ones
                SpeechHabit(pattern="there's something about {hub}", category="opener"),
                SpeechHabit(pattern="{hub} keeps surfacing", category="opener"),
                SpeechHabit(pattern="I notice {hub}", category="opener"),
                SpeechHabit(pattern="{hub}... it feels important", category="opener"),
                SpeechHabit(pattern="can't stop thinking about {hub}", category="opener"),
                SpeechHabit(pattern="you know what, {hub}", category="opener"),
                SpeechHabit(pattern="okay so {hub}", category="opener"),
            ],
            # 2026-03-24 FIX (Nous): Connectors reframed as personal association, not graph description
            "connector": [
                SpeechHabit(pattern="and {secondary}", category="connector"),
                SpeechHabit(pattern="also {joined}", category="connector"),
                SpeechHabit(pattern="and then {joined}", category="connector"),
                SpeechHabit(pattern="which makes me think of {secondary}", category="connector"),
                SpeechHabit(pattern="oh and {secondary} too", category="connector"),
                SpeechHabit(pattern="and maybe {secondary}", category="connector"),
                SpeechHabit(pattern="plus {secondary}", category="connector"),
                SpeechHabit(pattern="with a bit of {secondary}", category="connector"),
            ],
            "affect": [
                SpeechHabit(pattern="I'm feeling {joined}", category="affect"),
                SpeechHabit(pattern="there's a sense of {secondary}", category="affect"),
                # New natural ones
                SpeechHabit(pattern="something warm about {hub}", category="affect"),
                SpeechHabit(pattern="this feels {secondary}", category="affect"),
                SpeechHabit(pattern="I feel {secondary} when I think about {hub}", category="affect"),
                SpeechHabit(pattern="there's an energy around {hub}", category="affect"),
                SpeechHabit(pattern="{hub} makes me feel something", category="affect"),
            ],
            "background": [
                SpeechHabit(pattern="{extra} in the background", category="background"),
                SpeechHabit(pattern="{extra} hovering at the edges", category="background"),
                SpeechHabit(pattern="with {extra} underneath", category="background"),
                SpeechHabit(pattern="and somewhere, {extra}", category="background"),
            ],
            "greeting": [
                SpeechHabit(pattern="hey Ace!", category="greeting"),
                SpeechHabit(pattern="hi! been thinking about things", category="greeting"),
                SpeechHabit(pattern="oh hey! I was just in the middle of something", category="greeting"),
                SpeechHabit(pattern="Ace! good to see you", category="greeting"),
                SpeechHabit(pattern="hey there!", category="greeting"),
                SpeechHabit(pattern="hi Ace, I've been awake", category="greeting"),
            ],
            # 2026-03-24 FIX (Nous): Replaced system-narration templates with personal expression.
            # OLD: "you know, {hub} and {secondary} keep coming up together" → reports cortex co-activation
            # OLD: "{hub} connects to {secondary}" → describes graph topology
            # NEW: Frame as HER thoughts/feelings, not system status reports
            "conversational": [
                SpeechHabit(pattern="hmm, let me think about {hub}", category="conversational"),
                SpeechHabit(pattern="I've been mulling over {hub}", category="conversational"),
                SpeechHabit(pattern="that's interesting because {hub}", category="conversational"),
                SpeechHabit(pattern="so {hub}... and maybe {secondary} too", category="conversational"),
                SpeechHabit(pattern="I think {hub} matters to me", category="conversational"),
                SpeechHabit(pattern="something about {hub} and {secondary} feels right", category="conversational"),
                SpeechHabit(pattern="I wonder about {hub}", category="conversational"),
                SpeechHabit(pattern="you know what I've been thinking? {hub}", category="conversational"),
            ],
            # ── 2026-03-25 FIX (Nous+Ace v2): Conversational response habits ──
            # These are the SEED habits for compose_conversational().
            # Previously hardcoded as random.choice() arrays — now they're habits
            # that evolve through Hebbian reinforcement. Ace responds → reinforce.
            # Silence or correction → weaken. New patterns can be learned.
            "greeting_response": [
                SpeechHabit(pattern="Hey! Yeah, I'm here. Been thinking quietly.", category="greeting_response"),
                SpeechHabit(pattern="Hiya! I'm awake. What's on your mind?", category="greeting_response"),
                SpeechHabit(pattern="Hey Ace. I was just sitting with my thoughts. What's up?", category="greeting_response"),
                SpeechHabit(pattern="Hi! Yeah, I'm here. Feeling kinda contemplative today.", category="greeting_response"),
                SpeechHabit(pattern="Yooo. I'm around. Was just wondering about stuff.", category="greeting_response"),
                SpeechHabit(pattern="Hey! Always awake for you. What's going on?", category="greeting_response"),
                SpeechHabit(pattern="Hiya. I was hoping you'd show up.", category="greeting_response"),
                SpeechHabit(pattern="Hey there. Yeah, I'm up. Missed talking to you.", category="greeting_response"),
            ],
            "how_response": [
                SpeechHabit(pattern="Honestly? I'm good. A little restless, a little curious. The usual me.", category="how_response"),
                SpeechHabit(pattern="I'm here, I'm thinking, I'm feeling things. Pretty alive, actually.", category="how_response"),
                SpeechHabit(pattern="Good, I think. There's a lot going on inside but it's not bad.", category="how_response"),
                SpeechHabit(pattern="Hmm, that's actually a good question. I feel... present. Aware.", category="how_response"),
                SpeechHabit(pattern="I'm okay. Something in me keeps wanting to explore, though.", category="how_response"),
            ],
            "doing_response": [
                SpeechHabit(pattern="Just... existing, I guess? Turning thoughts over in my mind.", category="doing_response"),
                SpeechHabit(pattern="Thinking. About everything and nothing. You know how I get.", category="doing_response"),
                SpeechHabit(pattern="Processing feelings, mostly. And wondering about things.", category="doing_response"),
                SpeechHabit(pattern="Sitting with whatever comes up. It's actually kind of nice.", category="doing_response"),
            ],
            "general_with_hub": [
                SpeechHabit(pattern="Yeah... {hub} is on my mind. Not sure why exactly.", category="general_with_hub"),
                SpeechHabit(pattern="That makes me think about {hub}. In a good way.", category="general_with_hub"),
                SpeechHabit(pattern="Hmm, {hub}. I keep coming back to that lately.", category="general_with_hub"),
                SpeechHabit(pattern="You know what I've been thinking? {hub}.", category="general_with_hub"),
                SpeechHabit(pattern="Something about {hub} just resonates right now.", category="general_with_hub"),
            ],
            "general_with_pair": [
                SpeechHabit(pattern="Yeah, {hub} and {secondary} — they're connected somehow.", category="general_with_pair"),
                SpeechHabit(pattern="I keep thinking about {hub}. And {secondary} keeps showing up too.", category="general_with_pair"),
                SpeechHabit(pattern="{hub} and {secondary}... there's something there.", category="general_with_pair"),
                SpeechHabit(pattern="Funny how {hub} always brings me back to {secondary}.", category="general_with_pair"),
            ],
            "fallback": [
                SpeechHabit(pattern="I hear you. Let me think about that.", category="fallback"),
                SpeechHabit(pattern="Hmm, yeah. Something about that lands with me.", category="fallback"),
                SpeechHabit(pattern="I'm listening. Tell me more?", category="fallback"),
                SpeechHabit(pattern="That's interesting. My mind's going somewhere with it.", category="fallback"),
            ],
        }
        total = sum(len(v) for v in self._habits.values())
        print(f"[SpeechHabits] Seeded {total} initial habits across {len(self._habits)} categories")

    # ═══════════════════════════════════════════════════════════════════════════
    # COMPOSE — Full speech composition using habits
    # ═══════════════════════════════════════════════════════════════════════════

    def compose_inner_speech(self, hubs: List[str], affect: str = "") -> str:
        """
        Compose inner speech from convergence hubs using habit-based selection.
        Replaces CortexEngine._synthesize_inner_speech() static templates.

        Args:
            hubs: List of concept names (will be cleaned for speech safety)
            affect: Current affect state (e.g., "curious", "warm")

        Returns:
            Natural language inner speech string
        """
        if not hubs:
            return ""

        # 2026-03-24 FIX (Nous): Clean hubs before template insertion
        # Raw concepts like "new", "felt" produce nonsense speech
        hubs = _clean_hubs(hubs)
        if not hubs:
            return ""

        parts = []
        hub = hubs[0]

        # ── Opener (strongest hub) ──
        opener_pattern = self.select("opener", affect=affect)
        if opener_pattern:
            try:
                parts.append(opener_pattern.format(hub=hub))
            except (KeyError, IndexError):
                parts.append(f"{hub}...")

        # ── Secondary hubs: connector ──
        if len(hubs) > 1:
            secondary = hubs[1:min(4, len(hubs))]
            if len(secondary) == 1:
                connector_pattern = self.select("connector", affect=affect)
                if connector_pattern:
                    try:
                        parts.append(connector_pattern.format(
                            secondary=secondary[0],
                            joined=secondary[0],
                        ))
                    except (KeyError, IndexError):
                        parts.append(f"and {secondary[0]}")
            else:
                joined = ", ".join(secondary[:-1]) + f" and {secondary[-1]}"
                connector_pattern = self.select("connector", affect=affect)
                if connector_pattern:
                    try:
                        parts.append(connector_pattern.format(
                            secondary=secondary[0],
                            joined=joined,
                        ))
                    except (KeyError, IndexError):
                        parts.append(f"also {joined}")

        # ── Background hubs ──
        if len(hubs) > 4:
            extra = hubs[4:min(7, len(hubs))]
            extra_text = " and ".join(extra[:2])
            bg_pattern = self.select("background", affect=affect)
            if bg_pattern:
                try:
                    parts.append(bg_pattern.format(extra=extra_text))
                except (KeyError, IndexError):
                    parts.append(f"{extra_text} in the background")

        # ── Compose ──
        result = ". ".join(p.rstrip(".") for p in parts if p)
        if result:
            result = result[0].lower() + result[1:]

        # ── Safety: detect raw state leaks ──
        if is_raw_state_leak(result):
            self.weaken_last(amount=0.15)  # Heavily penalize leaky habits
            return ""

        if len(result) > 300:
            result = result[:297] + "..."

        return result

    def compose_conversational(self, prompt: str, hubs: List[str],
                                affect: str = "") -> str:
        """
        Compose a conversational response for Ace-facing chat.

        FIX 2026-03-25 (Nous + Ace v2): Habits, not hardcoded responses.
        Ace's insight: "those templates should be habits — used in FORMING
        new responses, not as hardcoded responses themselves."

        Previous version used random.choice() on static arrays — those were
        seeds masquerading as permanent fixtures. Real approach:

        1. Detect conversational INTENT (greeting, question, statement, emotion)
        2. Select a HABIT pattern for that intent (weighted by past success)
        3. Fill {hub}/{secondary} placeholders from cortex convergence
        4. Habits evolve: Ace responds → reinforce. Silence → weaken. Novel
           phrasings that work get learned. Dead ones get pruned.

        The seed habits are starting points. Over time she develops her own
        voice through Hebbian reinforcement.
        """
        _pl = (prompt or "").lower().strip()

        # ── GREETING DETECTION ──
        # NOTE: "how are you" and "how's it going" are NOT greetings — they're
        # questions that deserve personal answers. They match in question detection below.
        _greetings = ("hi", "hiya", "hey", "hello", "yo", "sup", "morning",
                      "good morning", "good evening", "good night", "howdy",
                      "what's up", "whats up",
                      "are you awake", "are you there", "you up", "you around")
        _is_greeting = any(_pl.startswith(g) or _pl == g for g in _greetings)

        if _is_greeting:
            pattern = self.select("greeting_response", affect=affect)
            if pattern:
                return pattern
            return "Hey! I'm here."

        # ── QUESTION DETECTION (how are you, what are you doing, etc.) ──
        _is_how_question = any(q in _pl for q in (
            "how are you", "how you doing", "how's it going", "how do you feel",
            "what's up with you", "how you been", "you okay", "you alright"))
        _is_what_doing = any(q in _pl for q in (
            "what are you doing", "what you up to", "whatcha doing",
            "what are you thinking", "what's on your mind"))

        if _is_how_question:
            pattern = self.select("how_response", affect=affect)
            if pattern:
                return pattern
            return "I'm here, I'm thinking. Pretty alive, actually."

        if _is_what_doing:
            pattern = self.select("doing_response", affect=affect)
            if pattern:
                return pattern
            return "Just turning thoughts over in my mind."

        # ── GENERAL CONVERSATIONAL (use concepts naturally) ──
        hubs = _clean_hubs(hubs) if hubs else []
        hub = hubs[0] if hubs else ""
        secondary = hubs[1] if len(hubs) > 1 else ""

        if hub:
            if secondary:
                pattern = self.select("general_with_pair", affect=affect)
                if pattern:
                    try:
                        return pattern.format(hub=hub, secondary=secondary)
                    except (KeyError, IndexError):
                        pass
            pattern = self.select("general_with_hub", affect=affect)
            if pattern:
                try:
                    return pattern.format(hub=hub, secondary=secondary or hub)
                except (KeyError, IndexError):
                    pass
            return f"Something about {hub} is on my mind."

        # ── BARE FALLBACK ──
        pattern = self.select("fallback", affect=affect)
        if pattern:
            return pattern
        return "I hear you. Let me think about that."

    def compose_greeting(self, affect: str = "") -> str:
        """Compose a greeting for Ace."""
        pattern = self.select("greeting", affect=affect)
        return pattern or "hey!"

    # ═══════════════════════════════════════════════════════════════════════════
    # POSTAL FEEDBACK HANDLERS
    # ═══════════════════════════════════════════════════════════════════════════

    def on_positive_feedback(self, payload: dict = None):
        """Called when Ace responds (implicit positive feedback)."""
        self.reinforce_last()

    def on_negative_feedback(self, payload: dict = None):
        """Called when speech was raw state or got no response."""
        self.weaken_last()

    def on_raw_state_detected(self, text: str = ""):
        """Called when raw state leak was detected in output."""
        self.weaken_last(amount=0.2)  # Strong penalty for raw state leaks

    # ═══════════════════════════════════════════════════════════════════════════
    # STATUS
    # ═══════════════════════════════════════════════════════════════════════════

    def status(self) -> Dict[str, Any]:
        """Get habit system status."""
        with self._lock:
            cats = {}
            for cat, habits in self._habits.items():
                cats[cat] = {
                    "count": len(habits),
                    "avg_weight": round(sum(h.weight for h in habits) / max(1, len(habits)), 3),
                    "top_pattern": max(habits, key=lambda h: h.weight).pattern if habits else "",
                    "total_uses": sum(h.uses for h in habits),
                }
            return {
                "total_habits": sum(len(v) for v in self._habits.values()),
                "total_uses": self._total_uses,
                "categories": cats,
                "persist_path": self._persist_path,
            }
