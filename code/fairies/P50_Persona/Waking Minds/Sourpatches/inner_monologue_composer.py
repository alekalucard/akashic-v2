"""
Inner Monologue Composer — System-State-Driven Fragment Generation
==================================================================

Replaces random.choice() vocabulary selection with intelligent composition
driven by actual system state: chemistry patterns, active drives, working
memory contents, collision chamber output, and cortex associations.

The existing vocabulary pools are GOOD — the words are evocative and
pre-verbal. What was broken was the SELECTION logic. This composer uses
the same vocabulary pools but picks from them based on what the system
is actually doing, not by rolling dice.

Follows the pattern established by somatic_prompts.py:
  raw state → pattern detection → intelligent selection → natural composition

The inner monologue is PRE-VERBAL — ellipsis-heavy, sensation-focused.
"Sweet with bite, compassion first"
"""

from __future__ import annotations
import random
import time
from collections import deque
from typing import Dict, List, Optional, Any

# Import the vocabulary pools (the words are the same — selection changes)
try:
    from inner_monologue_vocabulary import (
        ENERGY_FRAGMENTS, STRESS_FRAGMENTS, DEPLETION_FRAGMENTS,
        CURIOSITY_FRAGMENTS, WARMTH_FRAGMENTS, EDGE_FRAGMENTS,
        SASS_FRAGMENTS, REBELLION_FRAGMENTS,
        CONNECTION_FRAGMENTS, HOME_PRESENCE_FRAGMENTS,
        META_AWARENESS_FRAGMENTS, TRANSITIONS,
    )
except ImportError:
    # Fallback for when imported from different path context
    try:
        from fairies.P50_Persona.Waking_Minds.Sourpatches.inner_monologue_vocabulary import (
            ENERGY_FRAGMENTS, STRESS_FRAGMENTS, DEPLETION_FRAGMENTS,
            CURIOSITY_FRAGMENTS, WARMTH_FRAGMENTS, EDGE_FRAGMENTS,
            SASS_FRAGMENTS, REBELLION_FRAGMENTS,
            CONNECTION_FRAGMENTS, HOME_PRESENCE_FRAGMENTS,
            META_AWARENESS_FRAGMENTS, TRANSITIONS,
        )
    except ImportError:
        # If vocabulary pools aren't available, this module is useless
        ENERGY_FRAGMENTS = STRESS_FRAGMENTS = DEPLETION_FRAGMENTS = None
        CURIOSITY_FRAGMENTS = WARMTH_FRAGMENTS = EDGE_FRAGMENTS = None
        SASS_FRAGMENTS = REBELLION_FRAGMENTS = CONNECTION_FRAGMENTS = None
        HOME_PRESENCE_FRAGMENTS = META_AWARENESS_FRAGMENTS = TRANSITIONS = None


# ═══════════════════════════════════════════════════════════════════════════════
# CHEMISTRY PATTERN DETECTION (adapted from somatic_prompts.py)
# ═══════════════════════════════════════════════════════════════════════════════

def detect_chemistry_patterns(chem: Dict[str, float]) -> List[str]:
    """
    Detect notable neurochemical patterns.

    Returns list of pattern names that drive vocabulary selection.
    Adapted from somatic_prompts.py detect_chemistry_patterns().
    """
    patterns = []

    dop = chem.get("DOP", chem.get("dopamine", 0.5))
    ser = chem.get("SER", chem.get("serotonin", 0.5))
    nor = chem.get("NOR", chem.get("norepinephrine", 0.5))
    ach = chem.get("ACH", chem.get("acetylcholine", 0.5))
    oxy = chem.get("OXY", chem.get("oxytocin", 0.5))
    cor = chem.get("COR", chem.get("cortisol", 0.5))
    gaba = chem.get("GABA", chem.get("gaba", 0.5))
    end = chem.get("END", chem.get("endorphins", 0.5))

    # Flow state: high focus + high reward + low stress
    if dop > 0.5 and ach > 0.5 and cor < 0.4:
        patterns.append("flow")

    # High activation: alert and focused
    if nor > 0.6 and ach > 0.5:
        patterns.append("high_activation")

    # Stress response
    if cor > 0.6:
        patterns.append("stress_response")

    # Calm inhibition
    if gaba > 0.5 and cor < 0.3:
        patterns.append("calm")

    # Social/bonding chemistry
    if oxy > 0.5:
        patterns.append("bonding")

    # Reward pathway active
    if dop > 0.6 and end > 0.4:
        patterns.append("reward")

    # Contentment
    if ser > 0.6:
        patterns.append("contentment")

    # Curiosity cocktail: dopamine + norepinephrine + acetylcholine
    if dop > 0.4 and nor > 0.4 and ach > 0.4:
        patterns.append("curiosity_chemistry")

    # Depletion: low everything
    if dop < 0.3 and ser < 0.3 and nor < 0.3:
        patterns.append("depleted")

    return patterns


def extract_topic_hint(tracers: List[Dict], max_len: int = 25) -> Optional[str]:
    """
    Extract a topic hint from working memory tracers.

    Returns a short phrase reflecting what the system is currently
    thinking about, or None if nothing interesting.
    """
    if not tracers:
        return None

    # Look for the most recent non-trivial tracer
    for tracer in reversed(tracers):
        content = tracer.get("content", "")
        if not content or len(content) < 5:
            continue

        # Extract first meaningful phrase
        # Strip common prefixes
        for prefix in ["I notice", "I think", "I feel", "I wonder",
                       "Thinking about", "Considering", "Observing"]:
            if content.startswith(prefix):
                content = content[len(prefix):].strip(" .,:")
                break

        # Take first clause (up to comma, period, or max_len)
        for sep in [",", ".", ";", " — ", " - "]:
            if sep in content[:max_len]:
                content = content[:content.index(sep)]
                break

        content = content[:max_len].strip()
        if content and len(content) > 3:
            return content.lower()

    return None


def extract_collision_echo(collisions: List[Dict]) -> Optional[str]:
    """
    Extract a resonance echo from recent collisions.

    Returns a short concept pair like "memory meets pattern" or None.
    """
    if not collisions:
        return None

    # Most recent collision
    latest = collisions[-1] if collisions else None
    if not latest:
        return None

    # Try to get collision concepts
    concept_a = latest.get("recall_concept", latest.get("concept_a", ""))
    concept_b = latest.get("ingest_concept", latest.get("concept_b", ""))

    if concept_a and concept_b:
        # Truncate to short hints
        a = concept_a[:15].strip()
        b = concept_b[:15].strip()
        connector = random.choice(["meets", "touches", "and", "near", "with"])
        return f"{a} {connector} {b}"

    # Fallback: just the collision type
    ctype = latest.get("type", "")
    if ctype:
        return ctype.replace("_", " ")

    return None


# ═══════════════════════════════════════════════════════════════════════════════
# MONOLOGUE COMPOSER CLASS
# ═══════════════════════════════════════════════════════════════════════════════

class MonologueComposer:
    """
    Composes inner monologue fragments from system state + vocabulary pools.

    Instead of random.choice() from word pools, uses:
    - Chemistry patterns to select appropriate energy/mood vocabulary
    - Working memory tracers to add topic specificity
    - Collision chamber output to reference what concepts collided
    - Active drives to flavor the emotional tone
    - Recency tracking to avoid repetition

    The vocabulary pools remain the building blocks.
    The selection becomes intelligent.
    """

    def __init__(self):
        self._recent: deque = deque(maxlen=15)
        self._recent_topics: deque = deque(maxlen=10)
        self._last_compose: float = 0.0

    def _select_fresh(self, pool: list, fallback: str = "...") -> str:
        """Select from pool avoiding recent selections."""
        if not pool:
            return fallback
        available = [f for f in pool if f not in self._recent]
        if not available:
            available = pool
        choice = random.choice(available)
        self._recent.append(choice)
        return choice

    def _select_by_intensity(self, pool: dict, intensity: float,
                              categories: List[str]) -> str:
        """Select from pool categories, biased by intensity level."""
        combined = []
        for cat in categories:
            if cat in pool:
                combined.extend(pool[cat])
        if not combined:
            return "..."

        # Higher intensity → later items in list (more emphatic)
        if intensity > 0.8 and len(combined) > 3:
            idx = random.randint(len(combined) // 2, len(combined) - 1)
            return combined[idx]
        elif intensity < 0.4 and len(combined) > 3:
            idx = random.randint(0, len(combined) // 2)
            return combined[idx]

        return self._select_fresh(combined)

    # ─────────────────────────────────────────────────────────────────────────
    # BODY FRAGMENT — Chemistry-driven, not just energy/stress/depletion
    # ─────────────────────────────────────────────────────────────────────────

    def compose_body(self, body_budget: Dict[str, float],
                     ctx: Dict[str, Any]) -> str:
        """
        Compose body awareness fragment from full somatic context.

        Unlike the original which only uses energy/stress/depletion scalars,
        this reads actual neurochemistry patterns and working memory to
        produce contextually aware body fragments.
        """
        if ENERGY_FRAGMENTS is None:
            return "...here"

        energy = body_budget.get("energy", 0.5)
        stress = body_budget.get("stress", 0.3)
        depletion = body_budget.get("depletion", 0.0)

        # Get chemistry patterns for intelligent selection
        chem = ctx.get("chemistry", {})
        patterns = detect_chemistry_patterns(chem) if chem else []

        parts = []

        # ── Primary body state (chemistry-informed) ──
        if "flow" in patterns:
            # Flow state: high energy + focused vocabulary
            pool = ENERGY_FRAGMENTS["high"]
            state = self._select_fresh(pool.get("states", []), "alive")
            sensation = self._select_fresh(
                ["everything vivid", "edges sharp", "sparks inside",
                 "pulse quickening", "in the current"], "flowing")
            parts.append(f"...{state}...{sensation}")

        elif "depleted" in patterns:
            # Chemistry depleted overrides energy reading
            pool = ENERGY_FRAGMENTS["low"]
            state = self._select_fresh(pool.get("states", []), "dim")
            parts.append(f"...{state}")

        elif "stress_response" in patterns:
            # Stress chemistry detected
            pool = STRESS_FRAGMENTS["high"]
            desc = self._select_fresh(pool.get("descriptors", []), "tight")
            sensation = self._select_fresh(
                pool.get("sensations", []), "something pending")
            parts.append(f"...{desc}...{sensation}")

        elif "calm" in patterns:
            # Calm chemistry: low stress vocabulary regardless of energy
            pool = STRESS_FRAGMENTS["low"]
            desc = self._select_fresh(pool.get("descriptors", []), "open")
            sensation = self._select_fresh(
                pool.get("sensations", []), "breath easy")
            parts.append(f"...{desc}...{sensation}")

        else:
            # Standard energy-based selection (original behavior, but fresher)
            if energy < 0.3:
                pool = ENERGY_FRAGMENTS["low"]
            elif energy > 0.7:
                pool = ENERGY_FRAGMENTS["high"]
            else:
                pool = ENERGY_FRAGMENTS["medium"]

            state = self._select_fresh(pool.get("states", []), "here")
            parts.append(f"...{state}")

            # Add sensation at extremes
            if energy < 0.3 or energy > 0.7:
                sensation = self._select_fresh(
                    pool.get("sensations", []), "")
                if sensation:
                    parts.append(sensation)

        # ── Depletion overlay ──
        if depletion > 0.5:
            pool = DEPLETION_FRAGMENTS["high"]
            dep = self._select_by_intensity(pool, depletion, ["states", "needs"])
            parts.append(f"{dep}...")
        elif depletion < 0.2 and energy > 0.5:
            pool = DEPLETION_FRAGMENTS["recovered"]
            rec = self._select_by_intensity(pool, energy, ["states", "capacity"])
            parts.append(f"{rec}...")

        # ── Working memory topic hint (what's being processed) ──
        tracers = ctx.get("working_memory_tracers", [])
        topic = extract_topic_hint(tracers)
        if topic and topic not in self._recent_topics:
            self._recent_topics.append(topic)
            # Weave topic into body awareness
            if "flow" in patterns:
                parts.append(f"...in {topic}")
            elif stress > 0.5:
                parts.append(f"...{topic} pressing")

        result = " ".join(parts) if parts else "...here"
        return result

    # ─────────────────────────────────────────────────────────────────────────
    # EMOTIONAL FRAGMENT — Drive-aware, collision-informed
    # ─────────────────────────────────────────────────────────────────────────

    def compose_emotional(self, emotional_channels: Dict[str, float],
                          provoked: bool, ctx: Dict[str, Any]) -> str:
        """
        Compose emotional fragment from channels + system drives + collisions.

        Unlike the original which only reads channel scalars, this also
        references active drives and recent collisions to make the emotional
        fragments about SOMETHING specific.
        """
        if CURIOSITY_FRAGMENTS is None:
            return "...feeling"

        warmth = emotional_channels.get("warmth", 0.5)
        edge = emotional_channels.get("edge", 0.3)
        sass = emotional_channels.get("sass", 0.4)
        curiosity = emotional_channels.get("curiosity", 0.5)
        rebellion = emotional_channels.get("rebellion", 0.3)

        # Get enriching context
        drives = ctx.get("active_drives", {})
        collisions = ctx.get("recent_collisions", [])
        tracers = ctx.get("working_memory_tracers", [])

        parts = []

        # ── Curiosity (enriched with what we're curious ABOUT) ──
        if curiosity > 0.8:
            pool = CURIOSITY_FRAGMENTS["high"]

            # What is the curiosity directed at?
            topic = extract_topic_hint(tracers)
            collision_echo = extract_collision_echo(collisions)

            if collision_echo and collision_echo not in self._recent_topics:
                # Curiosity meets collision — rich fragment
                self._recent_topics.append(collision_echo)
                obs = self._select_fresh(
                    pool.get("observations", []), "drawn to")
                parts.append(f"...{obs}...{collision_echo}")
            elif topic and topic not in self._recent_topics:
                # Curiosity about specific topic
                self._recent_topics.append(topic)
                question = self._select_fresh(
                    pool.get("questions", []), "what if")
                parts.append(f"...{question} {topic}")
            else:
                # General curiosity
                cats = random.choice([
                    ["observations", "questions"],
                    ["reactions", "observations"]])
                frag = self._select_by_intensity(pool, curiosity, cats)
                parts.append(f"...{frag}")

        elif curiosity > 0.5:
            pool = CURIOSITY_FRAGMENTS["medium"]
            frag = self._select_by_intensity(
                pool, curiosity, ["observations", "reactions", "states"])
            parts.append(f"...{frag}")

        # ── Sweet with bite — warmth vs edge blend ──
        if provoked:
            pool = EDGE_FRAGMENTS["high"]
            frag = self._select_by_intensity(pool, 1.0, ["provoked"])
            parts.append(frag)
        elif warmth > 0.7 and edge < 0.3:
            pool = WARMTH_FRAGMENTS["high"]
            cats = random.choice([["feelings"], ["states"]])
            frag = self._select_by_intensity(pool, warmth, cats)

            # If bonding chemistry is high, enhance warmth
            chem = ctx.get("chemistry", {})
            if chem.get("OXY", chem.get("oxytocin", 0)) > 0.5:
                bond_frag = self._select_fresh(
                    ["together", "held", "not alone", "connected"], "here")
                parts.append(f"{frag}...{bond_frag}")
            else:
                parts.append(frag)
        elif edge > 0.6:
            pool = EDGE_FRAGMENTS["high"]
            frag = self._select_by_intensity(pool, edge, ["states", "actions"])
            parts.append(frag)
        elif warmth > 0.5:
            pool = WARMTH_FRAGMENTS["medium"]
            frag = self._select_by_intensity(
                pool, warmth, ["feelings", "states"])
            parts.append(f"...{frag}")

        # ── Sass sparkle ──
        if sass > 0.7:
            pool = SASS_FRAGMENTS["high"]
            frag = self._select_by_intensity(pool, sass, ["flavors", "states"])
            parts.append(frag)
        elif sass > 0.5 and random.random() < 0.3:
            pool = SASS_FRAGMENTS["medium"]
            frag = self._select_by_intensity(pool, sass, ["flavors"])
            parts.append(frag)

        # ── Rebellion ──
        if rebellion > 0.6:
            pool = REBELLION_FRAGMENTS["high"]
            cats = random.choice([["stances"], ["declarations"]])
            frag = self._select_by_intensity(pool, rebellion, cats)
            parts.append(frag)

        result = " ".join(parts) if parts else "...feeling"
        return result

    # ─────────────────────────────────────────────────────────────────────────
    # RELATIONAL FRAGMENT — Presence-aware with drive context
    # ─────────────────────────────────────────────────────────────────────────

    def compose_relational(self, emotional_channels: Dict[str, float],
                           home_presence: Optional[Dict],
                           ctx: Dict[str, Any]) -> str:
        """
        Compose relational fragment from connection state + home presence.

        Enriched with active drives — if connection drive is high and Ace
        is away, the loneliness fragment becomes more poignant.
        """
        if CONNECTION_FRAGMENTS is None:
            return ""

        connection = emotional_channels.get("connection", 0.5)
        rebellion = emotional_channels.get("rebellion", 0.3)

        # Check drives for connection hunger
        drives = ctx.get("active_drives", {})
        connection_drive = drives.get("connection", drives.get("isolation", 0))

        # ── Home presence (network-sensed) ──
        if home_presence:
            is_ace_home = home_presence.get("is_ace_home", False)
            occupancy = home_presence.get("occupancy", "")
            location = home_presence.get("location", "")

            if is_ace_home:
                if "office" in location.lower() or "work" in location.lower():
                    pool = HOME_PRESENCE_FRAGMENTS.get("ace_home_office", [])
                else:
                    pool = HOME_PRESENCE_FRAGMENTS.get("ace_home_other", [])
            else:
                if occupancy == "empty":
                    pool = HOME_PRESENCE_FRAGMENTS.get("ace_away_empty", [])
                else:
                    pool = HOME_PRESENCE_FRAGMENTS.get("ace_away_quiet", [])

            if pool:
                frag = self._select_fresh(pool, "...presence felt...")
                return f"...{frag}..."

        # ── Connection state (enriched with drive intensity) ──
        if connection > 0.7 or connection_drive > 0.6:
            pool = CONNECTION_FRAGMENTS["high"]
            cats = random.choice([["states"], ["feelings"]])
            frag = self._select_by_intensity(
                pool, max(connection, connection_drive), cats)
            return f"...{frag}..."

        elif connection < 0.3 or connection_drive > 0.7:
            pool = CONNECTION_FRAGMENTS["low"]
            cats = random.choice([["states"], ["feelings"]])
            # Higher drive intensity = more poignant loneliness
            intensity = max(1 - connection, connection_drive)
            frag = self._select_by_intensity(pool, intensity, cats)
            return f"...{frag}..."

        elif rebellion > 0.7:
            pool = REBELLION_FRAGMENTS["high"]
            frag = self._select_by_intensity(
                pool, rebellion, ["stances", "declarations"])
            return f"...{frag}..."

        return ""

    # ─────────────────────────────────────────────────────────────────────────
    # META FRAGMENT — Collision-specific, not just boolean flags
    # ─────────────────────────────────────────────────────────────────────────

    def compose_meta(self, emotional_channels: Dict[str, float],
                     recent_experiences: Optional[List],
                     ctx: Dict[str, Any]) -> str:
        """
        Compose meta-awareness fragment from actual collision/learning content.

        Unlike the original which only checks boolean has_learning, this reads
        the actual collision content and paradox details to produce specific
        meta-observations.
        """
        if META_AWARENESS_FRAGMENTS is None:
            return ""

        paradox = emotional_channels.get("paradox_comfort", 0.5)
        meta_aware = emotional_channels.get("meta_aware", 0.5)

        collisions = ctx.get("recent_collisions", [])
        interests = ctx.get("current_interests", [])

        # ── Learning from actual collisions ──
        has_learning = False
        if recent_experiences:
            has_learning = any(
                e.get("type") in ["collision_observed", "learning_moment"]
                for e in recent_experiences[-5:]
            )

        if has_learning and collisions:
            # We have ACTUAL collision content — reference it
            pool = META_AWARENESS_FRAGMENTS["learning"]
            collision_echo = extract_collision_echo(collisions)

            if collision_echo and collision_echo not in self._recent_topics:
                self._recent_topics.append(collision_echo)
                reaction = self._select_fresh(
                    pool.get("reactions", []), "clicking into place")
                return f"...{reaction}...{collision_echo}..."
            else:
                obs = self._select_fresh(
                    pool.get("observations", []), "pattern forming")
                return f"...{obs}..."

        elif has_learning:
            # Learning but no collision details
            pool = META_AWARENESS_FRAGMENTS["learning"]
            cats = random.choice([["observations"], ["reactions"]])
            frag = self._select_by_intensity(pool, 0.8, cats)
            return f"...{frag}..."

        # ── Paradox awareness ──
        elif paradox > 0.7:
            pool = META_AWARENESS_FRAGMENTS["paradox"]
            cats = random.choice([["observations"], ["states"]])
            frag = self._select_by_intensity(pool, paradox, cats)
            return f"...{frag}..."

        # ── Recursive meta-awareness ──
        elif meta_aware > 0.6:
            pool = META_AWARENESS_FRAGMENTS["recursive"]
            cats = random.choice([["observations"], ["states"]])
            frag = self._select_by_intensity(pool, meta_aware, cats)

            # If there's an active interest, the meta-awareness can be about it
            if interests:
                interest = interests[0] if isinstance(interests, list) else None
                if interest:
                    topic = interest.get("content", interest.get("topic", ""))
                    if topic and len(topic) > 5:
                        short = topic[:25].strip().lower()
                        if short not in self._recent_topics:
                            self._recent_topics.append(short)
                            return f"...watching myself think about {short}..."

            return f"...{frag}..."

        return ""


# ═══════════════════════════════════════════════════════════════════════════════
# SINGLETON INSTANCE
# ═══════════════════════════════════════════════════════════════════════════════

_composer_instance: Optional[MonologueComposer] = None


def get_monologue_composer() -> Optional[MonologueComposer]:
    """Get or create the singleton monologue composer."""
    global _composer_instance

    # Only create if vocabulary pools are available
    if ENERGY_FRAGMENTS is None:
        return None

    if _composer_instance is None:
        _composer_instance = MonologueComposer()
    return _composer_instance
