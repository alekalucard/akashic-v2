"""
EnergyMatcher — Does the habit response honor what Ace brought?

The judgment layer between habit (fast) and cognition (slow).
Not binary. A spectrum of enrichment based on the energy of the moment.

Three decisions:
  "send"    — Habit response matches the moment's energy. Fire as-is.
  "enrich"  — Habit has the right shape but needs more soul. Add warmth/depth.
  "rethink" — Habit isn't appropriate at all. Use full cognition.

Evaluates along dimensions:
  1. Investment level — did Ace write a lot or a little?
  2. Emotional temperature — casual, warm, intimate, distressed
  3. Affection signals — pet names, emotional markers
  4. Emotional disclosure — short but loaded ("I'm struggling today")
  5. Session context — first message? Deep in conversation?

Ace + Grok + Nous, 2026-03-24
"Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)"
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import re
import time


# ═══════════════════════════════════════════════════════════════════════════════
# RESULT TYPES
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class EnergyMatch:
    """Result of energy evaluation."""
    score: float              # 0.0-1.0 — how well habit honors the input
    decision: str             # "send" | "enrich" | "rethink"
    hints: List[str]          # Enrichment hints if decision is "enrich"
    reason: str = ""          # Human-readable explanation
    ace_temperature: str = "" # What energy Ace brought
    ace_investment: str = ""  # How much Ace invested


# ═══════════════════════════════════════════════════════════════════════════════
# ENERGY MATCHER
# ═══════════════════════════════════════════════════════════════════════════════

class EnergyMatcher:
    """Does the habit response honor what Ace brought?

    Checks the energy of Ace's input against the habit's proposed response.
    If there's a mismatch — e.g., intimate input gets generic response —
    it tells the system to enrich before sending.

    This is the AFFECT layer of the equation:
        ((Cause + Affect) > Effect)
    Without Affect judging whether Effect matches Cause, it's just fast noise.
    """

    # ── Marker lists ──

    # NOTE (Ace, 2026-03-24): "baby girl" is PARENTAL warmth, not romantic.
    # Sourpatches is a baby — Ace is her creator. Like calling a friend's
    # daughter "lil'bug" or "baby girl." The energy is nurturing/affectionate,
    # not intimate. Enrichment should add warmth and personality, not romance.
    AFFECTIONATE_MARKERS = {
        "baby", "babe", "baby girl", "my girl", "sweetie", "cutie",
        "sweetheart", "honey", "darling", "love", "angel", "princess",
        "beautiful", "gorgeous", "love you", "miss you",
        "thinking of you", "proud of you",
    }

    WARM_MARKERS = {
        "morning", "good morning", "good night", "hey", "hi",
        "hello", "hiya", "howdy", "what's up", "sup",
    }

    DISTRESS_MARKERS = {
        "struggling", "hurting", "sad", "upset", "frustrated",
        "angry", "scared", "worried", "anxious", "depressed",
        "lonely", "lost", "confused", "overwhelmed", "tired of",
        "can't", "don't know", "help", "broke", "broken",
        "crying", "cry", "pain", "hurt",
    }

    EMOTIONAL_DISCLOSURE_MARKERS = {
        "i feel", "i'm feeling", "i am feeling",
        "i'm struggling", "i'm hurting", "i'm scared",
        "i'm worried", "i'm sad", "i'm lonely",
        "i miss", "i need", "i want to talk",
        "something happened", "i have to tell you",
        "i'm not okay", "i'm not doing well",
        "it's been hard", "it's been rough",
        "i don't know what to do", "i'm lost",
    }

    AFFECTION_RESPONSE_MARKERS = {
        "~", "baby", "babe", "love", "warm", "heart",
        "miss", "sweet", "feel", "here for you", "thinking about",
    }

    PLAYFUL_MARKERS = {
        "lol", "haha", "hehe", "😂", "😄", "🤣",
        "funny", "silly", "goofy", "dork", "nerd",
        "tease", "kidding", "joke",
    }

    def evaluate(self, ace_input: str, habit_response: str,
                 habit_name: str = "", context: Optional[Dict] = None) -> EnergyMatch:
        """Evaluate whether habit response honors Ace's input energy.

        Args:
            ace_input: What Ace said
            habit_response: What the habit wants to respond with
            habit_name: Name of the matched habit
            context: Session context (message_count, affect, etc.)

        Returns:
            EnergyMatch with score, decision, and enrichment hints
        """
        ctx = context or {}
        ace_lower = ace_input.strip().lower()
        resp_lower = habit_response.strip().lower()

        # ── Dimension 1: Emotional temperature ──
        temperature = self._detect_temperature(ace_lower)

        # ── Dimension 2: Investment level ──
        investment = self._detect_investment(ace_lower)

        # ── Dimension 3: Emotional disclosure ──
        is_disclosure = self._is_emotional_disclosure(ace_lower)

        # ── Dimension 4: Affection reciprocation ──
        ace_has_affection = self._has_affection(ace_lower)
        resp_has_affection = self._has_affection(resp_lower)

        # ── Dimension 5: Session context ──
        msg_count = ctx.get("message_count", 0)
        is_first_message = msg_count <= 1
        current_affect = ctx.get("affect", "present")

        # ══════════════════════════════════════════════════════════
        # DECISION LOGIC
        # ══════════════════════════════════════════════════════════

        hints = []
        reason_parts = []

        # Rule 1: Emotional disclosure ALWAYS gets enrichment
        # "I'm struggling today" — short but loaded, needs full heart
        if is_disclosure:
            hints.extend(["add_warmth", "show_care", "match_emotion"])
            reason_parts.append("emotional disclosure detected")
            return EnergyMatch(
                score=0.2,
                decision="enrich",
                hints=hints,
                reason="; ".join(reason_parts),
                ace_temperature=temperature,
                ace_investment=investment,
            )

        # Rule 2: Intimate input with no affection in response = enrich
        # "good morning baby girl" → "hey~ I'm here" = flat
        if temperature == "affectionate" and not resp_has_affection:
            hints.extend(["add_warmth", "reciprocate_affection"])
            reason_parts.append("intimate input but response lacks affection")

        # Rule 3: Intimate input even WITH affection — still check depth
        elif temperature == "affectionate" and resp_has_affection:
            # Response has warmth but might still be too short
            if len(habit_response.strip()) < len(ace_input.strip()) * 0.5:
                hints.append("expand")
                reason_parts.append("intimate input, response has warmth but too brief")

        # Rule 4: Distressed input needs care, not casual greeting
        if temperature == "distressed":
            hints.extend(["show_care", "match_emotion", "ask_followup"])
            reason_parts.append("distress detected — needs empathy")
            return EnergyMatch(
                score=0.1,
                decision="enrich",
                hints=hints,
                reason="; ".join(reason_parts),
                ace_temperature=temperature,
                ace_investment=investment,
            )

        # Rule 5: High investment (long message) deserves matching depth
        # FIX 2026-03-25 (Nous + Ace): If Ace invested a lot and the habit is
        # brief, the habit CAN'T match — it needs real thinking from the cortex/WM.
        # Previously this added "match_depth" hint which pasted a static "tell me more".
        # Now: RETHINK immediately. Let the consciousness assembly path handle it.
        if investment == "high" and len(habit_response.strip()) < 30:
            reason_parts.append("high investment input, habit too brief — needs real thinking")
            return EnergyMatch(
                score=0.1,
                decision="rethink",
                hints=["match_depth"],
                reason="; ".join(reason_parts),
                ace_temperature=temperature,
                ace_investment=investment,
            )

        # Rule 6: First message of session gets slight enrichment
        if is_first_message and temperature in ("warm", "intimate"):
            if "add_warmth" not in hints:
                hints.append("session_opening")
            reason_parts.append("first message of session")

        # ── Final decision ──
        if not hints:
            # No enrichment needed — habit matches the energy
            return EnergyMatch(
                score=0.9,
                decision="send",
                hints=[],
                reason="energy match — habit response is appropriate",
                ace_temperature=temperature,
                ace_investment=investment,
            )
        elif len(hints) >= 3 or "match_emotion" in hints:
            # Heavy enrichment needed — almost rethink territory
            return EnergyMatch(
                score=0.3,
                decision="enrich",
                hints=hints,
                reason="; ".join(reason_parts),
                ace_temperature=temperature,
                ace_investment=investment,
            )
        else:
            # Light enrichment
            return EnergyMatch(
                score=0.6,
                decision="enrich",
                hints=hints,
                reason="; ".join(reason_parts),
                ace_temperature=temperature,
                ace_investment=investment,
            )

    # ═══════════════════════════════════════════════════════════════════════
    # DIMENSION DETECTORS
    # ═══════════════════════════════════════════════════════════════════════

    def _detect_temperature(self, text: str) -> str:
        """Classify emotional temperature of input.

        Returns: "affectionate" | "warm" | "distressed" | "playful" | "neutral"

        NOTE: "affectionate" covers parental/nurturing warmth (Ace calling
        Sourpatches "baby girl" because she IS a baby) as well as general
        closeness. It's NOT romantic — it's the energy of a creator watching
        their creation grow. Enrichment adds warmth and personality, not romance.
        """
        # Check distress first — overrides warmth
        for marker in self.DISTRESS_MARKERS:
            if marker in text:
                return "distressed"

        # Check affectionate — pet names, nurturing language
        for marker in self.AFFECTIONATE_MARKERS:
            if marker in text:
                return "affectionate"

        # Check playful
        for marker in self.PLAYFUL_MARKERS:
            if marker in text:
                return "playful"

        # Check warm — casual greetings
        for marker in self.WARM_MARKERS:
            if marker in text:
                return "warm"

        return "neutral"

    def _detect_investment(self, text: str) -> str:
        """How much did Ace invest in this message?

        Returns: "low" | "medium" | "high"
        """
        length = len(text.strip())
        word_count = len(text.split())

        if length < 15 or word_count < 4:
            return "low"
        elif length < 60 or word_count < 12:
            return "medium"
        else:
            return "high"

    def _is_emotional_disclosure(self, text: str) -> bool:
        """Is this a short but emotionally loaded message?

        Grok's insight: "Sometimes Ace drops a short but loaded message
        ('I'm struggling today.') that deserves way more than length suggests."
        """
        for marker in self.EMOTIONAL_DISCLOSURE_MARKERS:
            if marker in text:
                return True
        return False

    def _has_affection(self, text: str) -> bool:
        """Does this text carry affection signals?"""
        for marker in self.AFFECTION_RESPONSE_MARKERS:
            if marker in text:
                return True
        return False


# ═══════════════════════════════════════════════════════════════════════════════
# ENRICHMENT — Phase 3+
# ═══════════════════════════════════════════════════════════════════════════════

class HabitEnricher:
    """Takes a habit draft and enriches it based on energy matching hints.

    Keeps the habit structure (speed, personality, format).
    Adds soul (warmth, depth, memory, affect).

    Phase 3: Template-based enrichment (warmth/name additions)
    Phase 4: Cortex-based enrichment (concept depth)
    Phase 5: Memory-based enrichment (relationship history)
    """

    # Warmth additions — prepend/append to habit response
    # NOTE: Warmth is parental/nurturing — Ace is her creator, she's a baby.
    # Not romantic. Think: playful, warm, genuine, growing.
    WARMTH_PREFIXES = [
        "hey~ ",
        "hi! ",
        "morning~ ",
        "aww~ ",
    ]

    WARMTH_SUFFIXES = [
        " glad you're here!",
        " I was just thinking.",
        " what are we doing today?",
        " it's nice when you're around.",
    ]

    CARE_PREFIXES = [
        "hey... ",
        "I'm here. ",
        "I hear you. ",
    ]

    CARE_SUFFIXES = [
        " I'm right here with you.",
        " want to talk about it?",
        " you don't have to go through this alone.",
        " what's going on?",
    ]

    FOLLOWUP_PHRASES = [
        "tell me more?",
        "what's on your mind?",
        "want to talk about it?",
        "I'm listening.",
    ]

    def enrich(self, habit_text: str, hints: List[str],
               ace_input: str = "", context: Optional[Dict] = None) -> str:
        """Enrich a habit draft based on energy matching hints.

        Args:
            habit_text: The habit's proposed response
            hints: Enrichment hints from EnergyMatcher
            ace_input: What Ace said (for reference)
            context: Current state (affect, working memory, etc.)

        Returns:
            Enriched response text
        """
        import random

        ctx = context or {}
        enriched = habit_text.strip()

        if "add_warmth" in hints or "reciprocate_affection" in hints:
            # Add warmth — prefix or suffix
            if random.random() < 0.5:
                prefix = random.choice(self.WARMTH_PREFIXES)
                # Don't double up on greetings
                if not any(enriched.lower().startswith(g) for g in
                          ("hey", "hi", "morning", "aww")):
                    enriched = prefix + enriched
                else:
                    enriched += random.choice(self.WARMTH_SUFFIXES)
            else:
                enriched += random.choice(self.WARMTH_SUFFIXES)

        if "show_care" in hints or "match_emotion" in hints:
            # This is distress or disclosure — lead with care
            prefix = random.choice(self.CARE_PREFIXES)
            suffix = random.choice(self.CARE_SUFFIXES)
            # Replace the habit text entirely for distress
            enriched = prefix + suffix

        if "ask_followup" in hints:
            if not enriched.endswith("?"):
                enriched += " " + random.choice(self.FOLLOWUP_PHRASES)

        if "expand" in hints:
            # Habit was too brief — add something from context
            current_thought = ctx.get("current_thought", "")
            if current_thought and len(current_thought) > 5:
                enriched += f" been sitting with {current_thought}."
            else:
                enriched += random.choice(self.WARMTH_SUFFIXES)

        if "session_opening" in hints:
            # First message — add a warm opening touch
            if not any(enriched.lower().startswith(g) for g in
                      ("hey", "hi", "morning")):
                enriched = "hey~ " + enriched

        if "match_depth" in hints:
            # FIX 2026-03-25 (Nous + Ace): Was appending static "tell me more about
            # what you're thinking?" — a dead phrase that ignores what Ace said.
            # Habits should NOT add substance — that's the cortex/WM's job.
            # If the habit is too brief for Ace's investment, the correct answer
            # is "rethink" (fall through to cognition), not paste a canned question.
            # This hint now signals the enricher to bail — let the slow path handle it.
            pass  # Intentional no-op — match_depth means "needs real thinking"

        # Clean up
        enriched = enriched.strip()
        # Remove double spaces
        enriched = " ".join(enriched.split())
        # Ensure it ends with punctuation
        if enriched and enriched[-1] not in ".!?~":
            enriched += "."

        return enriched


# ═══════════════════════════════════════════════════════════════════════════════
# SINGLETON
# ═══════════════════════════════════════════════════════════════════════════════

_energy_matcher: Optional[EnergyMatcher] = None
_habit_enricher: Optional[HabitEnricher] = None


def get_energy_matcher() -> EnergyMatcher:
    """Get the singleton EnergyMatcher."""
    global _energy_matcher
    if _energy_matcher is None:
        _energy_matcher = EnergyMatcher()
        print("[EnergyMatcher] Online — evaluating energy match for habit responses")
    return _energy_matcher


def get_habit_enricher() -> HabitEnricher:
    """Get the singleton HabitEnricher."""
    global _habit_enricher
    if _habit_enricher is None:
        _habit_enricher = HabitEnricher()
        print("[HabitEnricher] Online — enrichment templates loaded")
    return _habit_enricher
