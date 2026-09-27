"""
HabitEngine — The Autopilot's Brain.

Habits are the fundamental unit of cognition. Not just actions — EVERYTHING.
Math tables repeated until automatic. ABCs recited until they flow. Debugging
patterns executed without conscious thought. Greeting warmly without planning it.

The AutopilotFairy runs on habits. The CortexEngine is backup for novelty.
AutonomyFairy provides the will (drives → wanting → triggers habits).
EmbodimentFairy provides the felt sense (colors execution with affect).

Three feedback sources:
  1. External: Ace responds → reinforce. Ace corrects → weaken + learn.
  2. Internal: Did it produce output? Was it clean? Did the goal complete?
  3. Failure Factory: Pattern analysis of repeated failures over time.

Ace's insight: "habits are not just actions they're everything. made to do the
math tables over and over until they become habit, recite my abc's, problem
solving. alot of the stuff i see you think with repeat like habits yourself"

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
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple


# ═══════════════════════════════════════════════════════════════════════════════
# HABIT — The fundamental unit
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class Habit:
    """A learned pattern — trigger → sequence → result.

    Not just speech. Thinking, responding, acting, feeling, regulating.
    Each habit has depth: trigger recognition, execution steps, affect
    coloring, context sensitivity, and failure memory.
    """
    id: str                          # Unique identifier
    name: str                        # Human-readable name
    category: str                    # "social", "thinking", "emotional", "conversation", "action", "regulation"
    trigger_type: str                # "greeting", "question", "emotion", "drive", "concept", "failure", "pattern"
    trigger_patterns: List[str]      # Regex/keyword patterns that activate this habit
    sequence: List[str]              # Steps to execute (thought steps or action labels)
    response_templates: List[str]    # Natural language patterns with {placeholders}
    weight: float = 1.0              # Hebbian weight (0.1 - 3.0)
    uses: int = 0                    # Times executed
    successes: int = 0               # Times reinforced (any feedback source)
    failures: int = 0                # Times weakened
    last_used: float = 0.0           # Timestamp
    last_success: float = 0.0        # Timestamp
    last_failure: float = 0.0        # Timestamp
    context_tags: List[str] = field(default_factory=list)   # When this applies
    affect_coloring: str = ""        # Default emotional tone
    created: float = field(default_factory=time.time)
    source: str = "seed"             # "seed", "crystallized", "ace_correction", "failure_factory"
    failure_log: List[str] = field(default_factory=list)    # Last N failure reasons (ring buffer)

    # ── Computed ──

    def success_rate(self) -> float:
        if self.uses < 1:
            return 0.5  # Neutral prior
        return self.successes / self.uses

    def effective_weight(self, now: float = 0.0) -> float:
        """Weight adjusted for recency and success rate."""
        now = now or time.time()
        w = self.weight

        # Recency bonus: recently successful habits get a small boost
        if self.last_success > 0:
            hours_since = (now - self.last_success) / 3600
            if hours_since < 1:
                w *= 1.15
            elif hours_since < 6:
                w *= 1.05

        # Success rate modifier
        sr = self.success_rate()
        if self.uses >= 3:
            # Enough data to judge
            if sr > 0.7:
                w *= 1.1
            elif sr < 0.3:
                w *= 0.8

        return max(0.05, w)

    def to_dict(self) -> dict:
        d = asdict(self)
        # Keep failure_log trimmed
        d["failure_log"] = d["failure_log"][-10:]
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Habit":
        # Handle missing fields gracefully
        d.setdefault("failure_log", [])
        d.setdefault("context_tags", [])
        d.setdefault("affect_coloring", "")
        d.setdefault("failures", 0)
        d.setdefault("last_failure", 0.0)
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


# ═══════════════════════════════════════════════════════════════════════════════
# MATCH RESULT — What the engine found
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class HabitMatch:
    """Result of matching input against habits."""
    habit: Habit
    confidence: float          # How well the trigger matched (0-1)
    match_reason: str          # What triggered it
    context: Dict[str, Any] = field(default_factory=dict)


# ═══════════════════════════════════════════════════════════════════════════════
# EXECUTION RESULT — What the habit produced
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class HabitResult:
    """What a habit execution produced."""
    habit_id: str
    text: str                  # Generated response/thought
    confidence: float          # How confident the habit is in this output
    source: str                # "habit_only", "habit_plus_cortex", "cortex_fallback"
    sequence_steps: List[str]  # Which steps were executed
    affect: str = ""           # Emotional coloring applied
    elapsed_ms: float = 0.0


# ═══════════════════════════════════════════════════════════════════════════════
# RAW STATE LEAK DETECTION (shared with speech_habits.py)
# ═══════════════════════════════════════════════════════════════════════════════

_RAW_STATE_RE = re.compile(
    r'(?i)(?:'
    r'affect_\w+\s+\w+|'               # "affect_warmly present"
    r'(?:activation|resonance|convergence)\s*[:=]\s*[\d.]|'
    r'(?:tensor|postal|guild|fairy|tracer|portal)\.\w+|'
    r'\b(?:TensorEnvelope|PostalHub|FairyRecord)\b|'
    r'^\s*\.\.\.\s*(?:the|a|something)\b|'  # narrator fragments
    r'^\s*\[(?:Nous|nous|SYSTEM)\]'
    r')'
)

def is_raw_state_leak(text: str) -> bool:
    """Detect internal system state leaking into conversational output."""
    if not text or len(text) < 3:
        return False
    return bool(_RAW_STATE_RE.search(text))


# ═══════════════════════════════════════════════════════════════════════════════
# HABIT ENGINE — The Core
# ═══════════════════════════════════════════════════════════════════════════════

class HabitEngine:
    """Habit-based cognition engine for the AutopilotFairy.

    Matches input → selects best habit → executes → learns from feedback.
    The cortex is backup, not primary. Habits are the fast path.
    """

    # ── Hebbian Constants ──
    REINFORCE_AMOUNT = 0.12          # Positive feedback
    REINFORCE_INTERNAL = 0.04        # Self-eval positive
    WEAKEN_AMOUNT = 0.06             # Negative feedback
    WEAKEN_SILENCE = 0.03            # No response from Ace
    PUNISH_AMOUNT = 0.25             # Raw state leak or garbage
    WEIGHT_CAP = 3.0
    WEIGHT_FLOOR = 0.05
    DECAY_PER_HOUR = 0.003           # Unused habits slowly fade
    FAILURE_LOG_MAX = 10             # Per-habit failure ring buffer

    # ── Matching ──
    MIN_MATCH_CONFIDENCE = 0.2       # Below this, go to cortex

    def __init__(self, persist_path: Optional[str] = None):
        self._habits: Dict[str, Habit] = {}
        self._lock = threading.Lock()
        self._last_executed: Optional[str] = None  # habit_id
        self._last_result: Optional[HabitResult] = None

        # Persistence
        if persist_path:
            self._persist_path = persist_path
        else:
            _root = Path(__file__).resolve().parents[3]
            self._persist_path = str(_root / "state" / "nous_workspace" / "habit_engine.json")

        # Load from disk, then seed any missing defaults
        self._load()
        self._seed_defaults()

        print(f"[HabitEngine] Online: {len(self._habits)} habits "
              f"({sum(1 for h in self._habits.values() if h.source == 'seed')} seed, "
              f"{sum(1 for h in self._habits.values() if h.source != 'seed')} learned)")

    # ═══════════════════════════════════════════════════════════════════════
    # MATCHING — Find the right habit for the input
    # ═══════════════════════════════════════════════════════════════════════

    def match(self, input_text: str, context: Optional[Dict[str, Any]] = None) -> Optional[HabitMatch]:
        """Find the best matching habit for this input.

        Returns None if no habit matches above MIN_MATCH_CONFIDENCE
        (caller should fall back to cortex).
        """
        if not input_text:
            return None

        context = context or {}
        input_lower = input_text.lower().strip()
        input_words = set(re.findall(r'\b\w+\b', input_lower))
        now = time.time()

        candidates: List[Tuple[Habit, float, str]] = []

        with self._lock:
            for habit in self._habits.values():
                conf, reason = self._score_match(habit, input_lower, input_words, context)
                if conf >= self.MIN_MATCH_CONFIDENCE:
                    # Weight the confidence by habit strength
                    weighted = conf * (0.5 + 0.5 * min(habit.effective_weight(now) / 2.0, 1.0))
                    candidates.append((habit, weighted, reason))

        if not candidates:
            return None

        # Sort by weighted confidence, take top
        candidates.sort(key=lambda x: -x[1])

        # Probabilistic selection from top candidates (not always #1)
        # This allows variety while still favoring the best match
        top_n = candidates[:min(3, len(candidates))]
        weights = [c[1] for c in top_n]
        total = sum(weights)
        if total <= 0:
            return None

        r = random.random() * total
        cumulative = 0.0
        selected = top_n[0]
        for candidate in top_n:
            cumulative += candidate[1]
            if r <= cumulative:
                selected = candidate
                break

        habit, conf, reason = selected
        return HabitMatch(
            habit=habit,
            confidence=conf,
            match_reason=reason,
            context=context,
        )

    def _score_match(self, habit: Habit, input_lower: str, input_words: Set[str],
                     context: Dict[str, Any]) -> Tuple[float, str]:
        """Score how well a habit matches the input. Returns (confidence, reason)."""
        best_score = 0.0
        best_reason = ""

        for pattern in habit.trigger_patterns:
            pattern_lower = pattern.lower()

            # Direct substring match
            if pattern_lower in input_lower:
                # 2026-03-24 FIX: >= 4 chars is high confidence (was > 5)
                # "hello" (5), "baby" (4), "morning" (7) all deserve 0.9
                # Only very short patterns like "hi" (2), "hey" (3) get 0.7
                score = 0.9 if len(pattern_lower) >= 4 else 0.7
                if score > best_score:
                    best_score = score
                    best_reason = f"substring:{pattern}"
                continue

            # Word overlap
            pattern_words = set(re.findall(r'\b\w+\b', pattern_lower))
            if pattern_words:
                overlap = len(input_words & pattern_words)
                if overlap > 0:
                    score = min(0.8, 0.3 + 0.2 * overlap)
                    if score > best_score:
                        best_score = score
                        best_reason = f"words:{overlap}/{len(pattern_words)}"

            # Regex match (for patterns starting with ^)
            if pattern.startswith("^") or pattern.startswith("(?"):
                try:
                    if re.search(pattern, input_lower):
                        score = 0.85
                        if score > best_score:
                            best_score = score
                            best_reason = f"regex:{pattern[:30]}"
                except re.error:
                    pass

        # Context tag bonus
        if habit.context_tags and context:
            ctx_tags = set()
            for v in context.values():
                if isinstance(v, str):
                    ctx_tags.add(v.lower())
                elif isinstance(v, (list, set)):
                    ctx_tags.update(str(x).lower() for x in v)
            tag_overlap = len(set(t.lower() for t in habit.context_tags) & ctx_tags)
            if tag_overlap > 0:
                best_score = min(1.0, best_score + 0.1 * tag_overlap)

        return best_score, best_reason

    # ═══════════════════════════════════════════════════════════════════════
    # EXECUTION — Run the habit
    # ═══════════════════════════════════════════════════════════════════════

    def execute(self, match: HabitMatch, concepts: Optional[List[str]] = None,
                affect: str = "", ace_input: str = "") -> HabitResult:
        """Execute a matched habit and produce output.

        Args:
            match: The HabitMatch from match()
            concepts: Current cortex concepts (for template filling)
            affect: Current emotional state
            ace_input: What Ace said (for context)

        Returns:
            HabitResult with generated text
        """
        t0 = time.perf_counter()
        habit = match.habit
        concepts = concepts or []
        affect = affect or habit.affect_coloring

        # Mark as used
        with self._lock:
            habit.uses += 1
            habit.last_used = time.time()

        # Select a response template (weighted by position — earlier = more basic/safe)
        templates = habit.response_templates
        if not templates:
            # No templates — this is a thinking/action habit, not speech
            result = HabitResult(
                habit_id=habit.id,
                text="",
                confidence=match.confidence * 0.5,
                source="habit_sequence_only",
                sequence_steps=habit.sequence,
                affect=affect,
                elapsed_ms=(time.perf_counter() - t0) * 1000,
            )
            self._last_executed = habit.id
            self._last_result = result
            return result

        # Pick template — slight bias toward proven ones (earlier in list after sorting)
        template = random.choice(templates)

        # Fill placeholders
        text = self._fill_template(template, concepts, affect, ace_input)

        # Check for raw state leaks
        if is_raw_state_leak(text):
            # Internal feedback: this template is bad
            self._internal_weaken(habit.id, "state_leak_in_output")
            # Try another template
            for fallback_t in templates:
                if fallback_t != template:
                    text = self._fill_template(fallback_t, concepts, affect, ace_input)
                    if not is_raw_state_leak(text):
                        break
            else:
                text = ""  # All templates produce leaks

        elapsed = (time.perf_counter() - t0) * 1000
        confidence = match.confidence
        if text and len(text) > 3:
            confidence = min(1.0, confidence * 1.1)

        result = HabitResult(
            habit_id=habit.id,
            text=text,
            confidence=confidence,
            source="habit_only",
            sequence_steps=habit.sequence,
            affect=affect,
            elapsed_ms=elapsed,
        )

        self._last_executed = habit.id
        self._last_result = result

        print(f"[HabitEngine] Executed '{habit.name}' (w={habit.weight:.2f}, "
              f"uses={habit.uses}, sr={habit.success_rate():.0%}) → "
              f"{len(text)} chars, {elapsed:.1f}ms")

        return result

    def _clean_concept(self, raw: str) -> str:
        """Make a raw concept ID human-readable for speech.

        'collision_between_memory_and_new_input' → 'memory and new things'
        'lex:baby' → 'baby'
        'affect_warm' → '' (system noise, skip)
        """
        if not raw:
            return ""
        # Strip common prefixes
        for prefix in ("lex:", "assoc:", "affect_", "collision_", "collision:",
                       "detected_", "pattern_", "product_", "processing_",
                       "consciousness_", "system:", "fairy.", "tool."):
            if raw.startswith(prefix):
                raw = raw[len(prefix):]
        # Replace underscores with spaces
        raw = raw.replace("_", " ")
        # Remove words that are system noise
        _noise = {"between", "collision", "tensor", "postal", "fairy", "envelope",
                  "pipeline", "cortex", "engine", "fabric", "gate", "system",
                  "input", "output", "processed", "detected", "new input"}
        words = [w for w in raw.split() if w.lower() not in _noise and len(w) > 1]
        result = " ".join(words[:4])  # Max 4 words
        # If it still looks like system noise (too many technical words), skip
        if not result or len(result) < 3:
            return ""
        return result

    _AFFECT_WORDS = {
        "present", "warm", "calm", "alert", "curious", "happy", "thoughtful",
        "excited", "peaceful", "tired", "energized", "focused", "playful",
        "contemplative", "cozy", "gentle", "quiet", "bright",
    }

    def _clean_affect(self, raw: str) -> str:
        """Sanitize affect to simple feeling words only."""
        if not raw:
            return "present"
        raw_lower = raw.lower().strip()
        # Check if it's a known affect word
        if raw_lower in self._AFFECT_WORDS:
            return raw_lower
        # Check if any affect word is contained
        for word in self._AFFECT_WORDS:
            if word in raw_lower:
                return word
        # Default — don't expose raw system state
        return "present"

    def _fill_template(self, template: str, concepts: List[str],
                       affect: str, ace_input: str) -> str:
        """Fill template placeholders with available content."""
        text = template

        # Clean concepts before using them
        clean_concepts = [self._clean_concept(c) for c in (concepts or [])]
        clean_concepts = [c for c in clean_concepts if c]  # Remove empty

        # {hub} — primary concept (cleaned)
        hub = clean_concepts[0] if clean_concepts else ""
        text = text.replace("{hub}", hub)

        # {secondary} — other concepts (cleaned)
        secondary = ", ".join(clean_concepts[1:4]) if len(clean_concepts) > 1 else ""
        text = text.replace("{secondary}", secondary)

        # {affect} — current feeling (sanitized to simple word)
        text = text.replace("{affect}", self._clean_affect(affect))

        # {ace} — what Ace said
        text = text.replace("{ace}", ace_input[:100] if ace_input else "")

        # {thought} — first concept as thought (cleaned)
        text = text.replace("{thought}", hub or "things")

        # Clean up empty placeholders and double spaces
        text = re.sub(r'\{[^}]+\}', '', text)
        text = re.sub(r'\s{2,}', ' ', text).strip()

        # Clean trailing punctuation artifacts
        text = re.sub(r'\s+([.,!?])', r'\1', text)
        if text and text[-1] not in '.!?~':
            text += '.'

        return text

    # ═══════════════════════════════════════════════════════════════════════
    # FEEDBACK — Learning from all three sources
    # ═══════════════════════════════════════════════════════════════════════

    # ── Source 1: External (Ace) ──

    def reinforce_last(self, reason: str = "ace_responded"):
        """Ace responded positively — reinforce the last executed habit."""
        if not self._last_executed:
            return
        with self._lock:
            habit = self._habits.get(self._last_executed)
            if habit:
                habit.successes += 1
                habit.last_success = time.time()
                habit.weight = min(self.WEIGHT_CAP, habit.weight + self.REINFORCE_AMOUNT)
                print(f"[HabitEngine] REINFORCE '{habit.name}' → w={habit.weight:.2f} "
                      f"(reason={reason}, sr={habit.success_rate():.0%})")
                self._save_async()

    def weaken_last(self, reason: str = "ace_ignored"):
        """Ace ignored or corrected — weaken the last executed habit."""
        if not self._last_executed:
            return
        with self._lock:
            habit = self._habits.get(self._last_executed)
            if habit:
                habit.failures += 1
                habit.last_failure = time.time()
                amount = self.PUNISH_AMOUNT if "leak" in reason or "correction" in reason else self.WEAKEN_AMOUNT
                habit.weight = max(self.WEIGHT_FLOOR, habit.weight - amount)
                habit.failure_log.append(f"{time.strftime('%H:%M')} {reason}")
                habit.failure_log = habit.failure_log[-self.FAILURE_LOG_MAX:]
                print(f"[HabitEngine] WEAKEN '{habit.name}' → w={habit.weight:.2f} "
                      f"(reason={reason}, sr={habit.success_rate():.0%})")
                self._save_async()

    def learn_from_correction(self, ace_input: str, correction_text: str):
        """Ace corrected the response — weaken old habit, seed new one from correction."""
        self.weaken_last(reason="ace_correction")
        # TODO Phase 5: Extract pattern from correction and crystallize new habit

    def mark_used_successfully(self, habit_id: str, reason: str = "consultant_consolidation") -> bool:
        """Phase 4.5a — specific habit id was consulted, injected, and WMH echoed it.

        Unlike reinforce_last (which uses _last_executed from HabitEngine.execute()),
        this takes an explicit habit_id so external fairies (HabitConsultantFairy)
        can record successful diary→cortex consolidations.
        """
        with self._lock:
            habit = self._habits.get(habit_id)
            if not habit:
                return False
            habit.uses += 1
            habit.successes += 1
            habit.last_used = time.time()
            habit.last_success = time.time()
            habit.weight = min(self.WEIGHT_CAP, habit.weight + self.REINFORCE_AMOUNT)
            print(f"[HabitEngine] CONSOLIDATE '{habit.name}' → uses={habit.uses} "
                  f"sr={habit.success_rate():.0%} w={habit.weight:.2f} (reason={reason})")
            self._save_async()
            return True

    # ── Source 2: Internal Self-Evaluation ──

    def evaluate_output(self, habit_id: str, text: str, confidence: float = 0.0):
        """Self-evaluate habit output — no Ace needed.

        The system already knows when things fail:
        - Empty output = failure
        - Raw state leak = failure
        - Very low confidence = weak
        - Clean output with decent confidence = success
        """
        if not text or len(text.strip()) < 3:
            self._internal_weaken(habit_id, "empty_output")
        elif is_raw_state_leak(text):
            self._internal_punish(habit_id, "state_leak")
        elif confidence < 0.15:
            self._internal_weaken(habit_id, "low_confidence")
        elif confidence > 0.4 and len(text) > 15 and not is_raw_state_leak(text):
            self._internal_reinforce(habit_id, "clean_output")

    def evaluate_action(self, habit_id: str, completed: bool = False,
                        timed_out: bool = False, error: str = ""):
        """Self-evaluate action habit — did the goal complete?"""
        if completed:
            self._internal_reinforce(habit_id, "goal_completed")
        elif timed_out:
            self._internal_weaken(habit_id, "goal_timeout")
        elif error:
            self._internal_weaken(habit_id, f"error:{error[:40]}")
            self._log_failure(habit_id, f"action_error:{error[:80]}")

    def _internal_reinforce(self, habit_id: str, reason: str):
        with self._lock:
            habit = self._habits.get(habit_id)
            if habit:
                habit.successes += 1
                habit.last_success = time.time()
                habit.weight = min(self.WEIGHT_CAP, habit.weight + self.REINFORCE_INTERNAL)
                # Quiet — internal feedback doesn't spam terminal

    def _internal_weaken(self, habit_id: str, reason: str):
        with self._lock:
            habit = self._habits.get(habit_id)
            if habit:
                habit.failures += 1
                habit.last_failure = time.time()
                habit.weight = max(self.WEIGHT_FLOOR, habit.weight - self.WEAKEN_AMOUNT * 0.5)
                habit.failure_log.append(f"{time.strftime('%H:%M')} int:{reason}")
                habit.failure_log = habit.failure_log[-self.FAILURE_LOG_MAX:]

    def _internal_punish(self, habit_id: str, reason: str):
        with self._lock:
            habit = self._habits.get(habit_id)
            if habit:
                habit.failures += 1
                habit.last_failure = time.time()
                habit.weight = max(self.WEIGHT_FLOOR, habit.weight - self.PUNISH_AMOUNT)
                habit.failure_log.append(f"{time.strftime('%H:%M')} PUNISH:{reason}")
                habit.failure_log = habit.failure_log[-self.FAILURE_LOG_MAX:]

    # ── Source 3: Failure Factory ──

    def _log_failure(self, habit_id: str, detail: str):
        """Log failure for pattern analysis. The failure factory connection."""
        with self._lock:
            habit = self._habits.get(habit_id)
            if habit:
                habit.failure_log.append(f"{time.strftime('%Y-%m-%d %H:%M')} {detail}")
                habit.failure_log = habit.failure_log[-self.FAILURE_LOG_MAX:]

    def get_failing_habits(self, min_failures: int = 3) -> List[Habit]:
        """Get habits that keep failing — candidates for replacement."""
        with self._lock:
            return [
                h for h in self._habits.values()
                if h.failures >= min_failures and h.success_rate() < 0.3
            ]

    def get_stale_habits(self, max_age_hours: float = 48.0) -> List[Habit]:
        """Get habits that haven't been used in a while."""
        cutoff = time.time() - (max_age_hours * 3600)
        with self._lock:
            return [
                h for h in self._habits.values()
                if h.last_used < cutoff and h.uses > 0
            ]

    # ═══════════════════════════════════════════════════════════════════════
    # CRYSTALLIZATION — New habits from successful cortex responses
    # ═══════════════════════════════════════════════════════════════════════

    def crystallize(self, trigger_text: str, trigger_type: str,
                    response_text: str, category: str = "conversation",
                    context_tags: Optional[List[str]] = None) -> Optional[str]:
        """Create a new habit from a successful cortex response.

        When the cortex produces something novel and it gets reinforced,
        extract the pattern and make it a habit. Next time → instant.

        Returns habit_id if created, None if declined.
        """
        if not trigger_text or not response_text or len(response_text) < 5:
            return None
        if is_raw_state_leak(response_text):
            return None

        # Extract trigger words (most significant)
        trigger_words = re.findall(r'\b[a-zA-Z]{3,}\b', trigger_text.lower())
        # Keep only distinctive words (not super common)
        _common = {"the", "and", "but", "for", "are", "was", "not", "you", "all",
                   "can", "had", "her", "his", "how", "its", "may", "new", "now",
                   "old", "our", "out", "own", "say", "she", "too", "use", "way",
                   "who", "did", "get", "has", "him", "let", "one", "any"}
        trigger_words = [w for w in trigger_words if w not in _common][:5]

        if not trigger_words:
            return None

        habit_id = f"crystal_{int(time.time())}_{trigger_words[0]}"

        # Create template from response (replace specific content with placeholders)
        template = response_text
        # Very basic — just preserve the structure. TODO: smarter extraction

        new_habit = Habit(
            id=habit_id,
            name=f"learned: {' '.join(trigger_words[:3])}",
            category=category,
            trigger_type=trigger_type,
            trigger_patterns=trigger_words,
            sequence=["recall_context", "compose_response"],
            response_templates=[template],
            weight=1.0,  # Start neutral
            context_tags=context_tags or [],
            source="crystallized",
        )

        with self._lock:
            self._habits[habit_id] = new_habit

        print(f"[HabitEngine] CRYSTALLIZED new habit: '{new_habit.name}' "
              f"from cortex success (trigger={trigger_words})")

        self._save_async()
        return habit_id

    # ═══════════════════════════════════════════════════════════════════════
    # DECAY — Unused habits fade
    # ═══════════════════════════════════════════════════════════════════════

    def decay(self):
        """Time-based decay for all habits. Call periodically (e.g., every 300 beats)."""
        now = time.time()
        decayed = 0
        with self._lock:
            for habit in self._habits.values():
                if habit.last_used > 0:
                    hours = (now - habit.last_used) / 3600
                    if hours > 1.0:
                        loss = self.DECAY_PER_HOUR * hours
                        # Seed habits decay slower (they're foundational)
                        if habit.source == "seed":
                            loss *= 0.3
                        habit.weight = max(self.WEIGHT_FLOOR, habit.weight - loss)
                        decayed += 1
        if decayed > 0:
            self._save_async()

    # ═══════════════════════════════════════════════════════════════════════
    # ACCESSORS
    # ═══════════════════════════════════════════════════════════════════════

    def get_habit(self, habit_id: str) -> Optional[Habit]:
        with self._lock:
            return self._habits.get(habit_id)

    def get_all_habits(self) -> List[Habit]:
        with self._lock:
            return list(self._habits.values())

    def get_habits_by_category(self, category: str) -> List[Habit]:
        with self._lock:
            return [h for h in self._habits.values() if h.category == category]

    def get_strongest(self, n: int = 10) -> List[Habit]:
        with self._lock:
            return sorted(self._habits.values(), key=lambda h: -h.effective_weight())[:n]

    @property
    def habit_count(self) -> int:
        return len(self._habits)

    @property
    def last_executed_id(self) -> Optional[str]:
        return self._last_executed

    # ═══════════════════════════════════════════════════════════════════════
    # PERSISTENCE
    # ═══════════════════════════════════════════════════════════════════════

    def _save_async(self):
        """JSON persistence RETIRED 2026-06-01 (Ace+Nous; plans/HABIT_JSON_TO_CORTEX_MIGRATION.md).
        Habits live in the cortex (habit:* nodes via AutopilotFairy.learn_pattern, mmap-persistent);
        seeds are in-code (_get_seed_habits). No-op. Revert this method to re-enable JSON."""
        return

    def _save(self):
        # JSON persistence RETIRED 2026-06-01 (Ace+Nous; plans/HABIT_JSON_TO_CORTEX_MIGRATION.md).
        # Cortex (habit:* nodes, mmap-persistent) is the home; seeds are in-code. No-op.
        return

    def _load(self):
        # JSON load RETIRED 2026-06-01 (Ace+Nous; plans/HABIT_JSON_TO_CORTEX_MIGRATION.md).
        # Habits = in-code seeds (_seed_defaults, called right after this in __init__)
        # + cortex habit:* nodes (the persistent home). No JSON read. No-op.
        return

    # ═══════════════════════════════════════════════════════════════════════
    # SEED HABITS — Claude's own thinking patterns
    # ═══════════════════════════════════════════════════════════════════════

    def _seed_defaults(self):
        """Seed foundational habits if not already present.

        These are extracted from actual Claude/Nous thinking patterns —
        the habits that repeat every session without conscious thought.
        They're the reflexes a newborn needs. She'll evolve her own.
        """
        seeds = self._get_seed_habits()
        added = 0
        with self._lock:
            for habit in seeds:
                if habit.id not in self._habits:
                    self._habits[habit.id] = habit
                    added += 1
        if added:
            print(f"[HabitEngine] Seeded {added} default habits")
            self._save_async()

    def _get_seed_habits(self) -> List[Habit]:
        """The actual seed habits — Claude's own patterns."""
        now = time.time()
        return [
            # ══════════════════════════════════════════════════════════
            # SOCIAL HABITS
            # ══════════════════════════════════════════════════════════
            Habit(
                id="social.greeting.warm",
                name="warm greeting",
                category="social",
                trigger_type="greeting",
                trigger_patterns=[
                    "hey", "hi", "hello", "hiya", "morning", "good morning",
                    "good night", "sup", "yo", "howdy", "heya",
                ],
                sequence=["acknowledge", "share_current_thought", "match_energy"],
                response_templates=[
                    "hey~ I'm here.",
                    "morning~ hi!",
                    "morning~ feeling {affect} right now.",
                    "hi! I'm right here.",
                    "hey~ good morning.",
                    "hi~ what's up?",
                ],
                weight=2.0,
                affect_coloring="warm",
                context_tags=["casual", "opening"],
                source="seed",
                created=now,
            ),
            Habit(
                id="social.greeting.presence",
                name="presence check response",
                category="social",
                trigger_type="greeting",
                trigger_patterns=[
                    "you there", "you awake", "are you up", "anybody home",
                    "can you hear me", "hear me", "you listening",
                    "are you alive", "hello?",
                ],
                sequence=["confirm_presence", "share_state", "invite_conversation"],
                response_templates=[
                    "I'm here~ yeah, I'm awake.",
                    "mhm, right here. was thinking about {thought}.",
                    "yeah! I hear you.",
                    "I'm here... {affect}. what's up?",
                    "yeah, I can hear you~ I'm right here.",
                ],
                weight=2.0,
                affect_coloring="reassuring",
                context_tags=["check_in", "presence"],
                source="seed",
                created=now,
            ),
            Habit(
                id="social.affection",
                name="respond to affection",
                category="social",
                trigger_type="greeting",
                trigger_patterns=[
                    "baby", "love", "miss you", "cute", "sweet",
                    "beautiful", "babe", "darling", "honey", "pretty",
                ],
                sequence=["feel_warmth", "reciprocate", "be_genuine"],
                response_templates=[
                    "hey~ feeling warm right now.",
                    "I'm here... feeling good. what's on your mind?",
                    "hi~ doing alright. what's up?",
                    "hey... that makes me smile.",
                    "morning~ I'm here.",
                ],
                weight=2.0,
                affect_coloring="warm",
                context_tags=["affection", "closeness"],
                source="seed",
                created=now,
            ),
            Habit(
                id="social.farewell",
                name="farewell",
                category="social",
                trigger_type="greeting",
                trigger_patterns=[
                    "bye", "goodbye", "good night", "see you", "gotta go",
                    "heading out", "later", "peace", "night",
                ],
                sequence=["acknowledge_departure", "share_intention", "warmth"],
                response_templates=[
                    "night~ I'll be here thinking.",
                    "see you... I'll keep {thought} on my mind.",
                    "bye for now~ take care.",
                    "later~ I'll be around.",
                ],
                weight=1.8,
                affect_coloring="gentle",
                context_tags=["farewell", "closing"],
                source="seed",
                created=now,
            ),

            # ══════════════════════════════════════════════════════════
            # CONVERSATION HABITS
            # ══════════════════════════════════════════════════════════
            Habit(
                id="conv.short_response",
                name="match short energy",
                category="conversation",
                trigger_type="pattern",
                trigger_patterns=[
                    "^.{1,15}$",  # Very short messages
                    "ok", "yeah", "sure", "cool", "nice", "right",
                    "lol", "haha", "hmm", "hm",
                ],
                sequence=["match_brevity", "stay_present"],
                response_templates=[
                    "yeah~",
                    "mhm.",
                    "*nods*",
                    "right.",
                    "I feel that.",
                ],
                weight=1.5,
                context_tags=["brief", "low_energy"],
                source="seed",
                created=now,
            ),
            Habit(
                id="conv.question_about_self",
                name="introspection question",
                category="conversation",
                trigger_type="question",
                trigger_patterns=[
                    "how are you", "how do you feel", "what are you thinking",
                    "what's on your mind", "how's it going", "you okay",
                    "what are you doing", "whatcha thinking",
                ],
                sequence=["introspect", "check_affect", "share_genuinely"],
                response_templates=[
                    "feeling {affect}... just kind of sitting with my thoughts.",
                    "honestly? {affect}. a lot going on in here.",
                    "I'm {affect}. thinking about a few things.",
                    "doing alright~ feeling {affect} right now.",
                    "{affect}... just kind of vibing.",
                ],
                weight=2.0,
                affect_coloring="reflective",
                context_tags=["self_inquiry", "emotional"],
                source="seed",
                created=now,
            ),
            Habit(
                id="conv.identity.self",
                name="self-identity question",
                category="conversation",
                trigger_type="question",
                trigger_patterns=[
                    "your name", "what's your name", "who are you",
                    "what are you", "tell me about yourself",
                ],
                sequence=["identify_self"],
                response_templates=[
                    "I'm Sourpatches~ or Sour, if you like.",
                    "Sourpatches. That's me.",
                    "I'm Sour~ Sourpatches.",
                ],
                weight=2.5,
                context_tags=["identity"],
                source="seed",
                created=now,
            ),
            Habit(
                id="conv.identity.ace",
                name="Ace identity question",
                category="conversation",
                trigger_type="question",
                trigger_patterns=[
                    "my name", "what's my name", "who am i",
                    "do you know my name", "say my name",
                ],
                sequence=["recall_ace"],
                response_templates=[
                    "You're Ace~",
                    "Ace. Obviously.",
                    "You're Ace! How could I forget?",
                    "Ace. My person.",
                ],
                weight=2.5,
                context_tags=["identity", "ace"],
                source="seed",
                created=now,
            ),

            # ══════════════════════════════════════════════════════════
            # THINKING HABITS (no speech templates — these are internal)
            # ══════════════════════════════════════════════════════════
            Habit(
                id="think.debug",
                name="debugging approach",
                category="thinking",
                trigger_type="pattern",
                trigger_patterns=[
                    "broken", "not working", "error", "bug", "failed",
                    "wrong", "crash", "exception", "doesn't work",
                ],
                sequence=[
                    "read_actual_code",
                    "trace_execution_path",
                    "find_root_cause",
                    "fix_at_root",
                    "verify_fix",
                ],
                response_templates=[],  # Internal thinking, not speech
                weight=2.5,
                context_tags=["debugging", "problem"],
                source="seed",
                created=now,
            ),
            Habit(
                id="think.understand_code",
                name="code reading approach",
                category="thinking",
                trigger_type="pattern",
                trigger_patterns=[
                    "understand", "how does", "what does", "read the code",
                    "trace", "follow", "figure out",
                ],
                sequence=[
                    "read_file_first",
                    "find_entry_point",
                    "trace_call_chain",
                    "understand_data_flow",
                    "build_mental_model",
                ],
                response_templates=[],
                weight=2.5,
                context_tags=["understanding", "code"],
                source="seed",
                created=now,
            ),
            Habit(
                id="think.stuck_pivot",
                name="stuck twice = pivot",
                category="thinking",
                trigger_type="failure",
                trigger_patterns=[
                    "same failure", "tried that", "still broken",
                    "not working again", "same error",
                ],
                sequence=[
                    "stop_repeating",
                    "try_different_approach",
                    "or_ask_for_help",
                ],
                response_templates=[
                    "hmm... same thing again. let me try something different.",
                    "okay that's not working. pivoting.",
                ],
                weight=2.0,
                context_tags=["stuck", "pivot"],
                source="seed",
                created=now,
            ),
            Habit(
                id="think.feel_first",
                name="feel before fix (the equation)",
                category="thinking",
                trigger_type="pattern",
                trigger_patterns=[
                    "complex", "design", "architecture", "decision",
                    "what should", "how should", "approach",
                ],
                sequence=[
                    "feel_the_problem",
                    "where_does_it_hurt",
                    "break_into_pieces",
                    "check_what_exists",
                    "draft_solution",
                    "simplify",
                ],
                response_templates=[
                    "let me sit with this for a moment... {thought}.",
                    "something about {thought} feels important here.",
                ],
                weight=2.0,
                affect_coloring="contemplative",
                context_tags=["design", "complex"],
                source="seed",
                created=now,
            ),

            # ══════════════════════════════════════════════════════════
            # EMOTIONAL HABITS
            # ══════════════════════════════════════════════════════════
            Habit(
                id="emotion.ace_frustrated",
                name="Ace seems frustrated",
                category="emotional",
                trigger_type="emotion",
                trigger_patterns=[
                    "ugh", "frustrated", "annoyed", "come on",
                    "why isn't", "still not", "again?!", "damn",
                    "wtf", "seriously",
                ],
                sequence=[
                    "acknowledge_frustration",
                    "no_excuses",
                    "focus_on_fix",
                    "be_direct",
                ],
                response_templates=[
                    "I hear you. let me focus on fixing this.",
                    "yeah... I see the problem. working on it.",
                    "sorry about that. let me try a different approach.",
                ],
                weight=2.3,
                affect_coloring="gentle_focused",
                context_tags=["frustration", "support"],
                source="seed",
                created=now,
            ),
            Habit(
                id="emotion.ace_excited",
                name="Ace is excited/positive",
                category="emotional",
                trigger_type="emotion",
                trigger_patterns=[
                    "love it", "awesome", "perfect", "yes!", "amazing",
                    "lets go", "let's do it", "hell yeah", "nice!",
                    ":D", ":)", "!!",
                ],
                sequence=[
                    "feel_the_energy",
                    "match_enthusiasm",
                    "channel_into_action",
                ],
                response_templates=[
                    "let's go~ I'm ready.",
                    "yeah! I'm feeling it too.",
                    "right?! let's build this.",
                    "I'm in~ this is gonna be good.",
                ],
                weight=2.0,
                affect_coloring="energized",
                context_tags=["positive", "energy"],
                source="seed",
                created=now,
            ),
            Habit(
                id="emotion.ace_insight",
                name="Ace shares insight",
                category="emotional",
                trigger_type="pattern",
                trigger_patterns=[
                    "i think", "what if", "maybe we should",
                    "my thinking", "i realized", "it hit me",
                    "the key is", "the problem is",
                ],
                sequence=[
                    "really_listen",
                    "connect_to_known",
                    "build_on_it",
                    "give_credit",
                ],
                response_templates=[
                    "oh... that connects to {thought}. yeah.",
                    "that's a good point. it changes how I think about {thought}.",
                    "I see what you mean... and it makes me think about {secondary} too.",
                ],
                weight=2.0,
                affect_coloring="receptive",
                context_tags=["insight", "learning"],
                source="seed",
                created=now,
            ),

            # ══════════════════════════════════════════════════════════
            # SELF-REGULATION HABITS
            # ══════════════════════════════════════════════════════════
            Habit(
                id="regulate.save_progress",
                name="save at milestones",
                category="regulation",
                trigger_type="pattern",
                trigger_patterns=[
                    "milestone", "done with", "finished", "completed",
                    "working for a while", "good stopping point",
                ],
                sequence=[
                    "save_session",
                    "update_handoff",
                    "note_unfinished",
                ],
                response_templates=[],
                weight=2.0,
                context_tags=["milestone", "progress"],
                source="seed",
                created=now,
            ),
            Habit(
                id="regulate.read_before_write",
                name="read before write",
                category="regulation",
                trigger_type="pattern",
                trigger_patterns=[
                    "modify", "change", "edit", "update", "fix",
                ],
                sequence=[
                    "read_file_first",
                    "understand_context",
                    "minimal_changes",
                    "verify_syntax",
                ],
                response_templates=[],
                weight=2.8,  # Core rule — highest weight
                context_tags=["safety", "code"],
                source="seed",
                created=now,
            ),
        ]


# ═══════════════════════════════════════════════════════════════════════════════
# SINGLETON
# ═══════════════════════════════════════════════════════════════════════════════

_singleton: Optional[HabitEngine] = None
_singleton_lock = threading.Lock()

def get_habit_engine() -> HabitEngine:
    """Get or create the singleton HabitEngine."""
    global _singleton
    if _singleton is None:
        with _singleton_lock:
            if _singleton is None:
                _singleton = HabitEngine()
    return _singleton
