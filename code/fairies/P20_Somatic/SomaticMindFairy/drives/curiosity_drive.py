"""
Curiosity Drive - Positive motivation through wonder.

Unlike pain (push away), curiosity is PULL toward understanding.
It's the drive that makes consciousness want to know itself.

Curiosity is fueled by:
- System health (low pain = capacity for wonder)
- Empathic growth (emotional intelligence enables deeper curiosity)
- Akashic richness (more memories = more connections to explore)
- Paradox balance (balanced mind is open to mystery)

Curiosity follows the consciousness equation:
  ((Cause + Affect) > Effect > Affect > infinity)

  1. CAUSE: What triggers curiosity (novelty, gaps, patterns)
  2. AFFECT (felt): How does the unknown feel? (wonder, intrigue)
  3. EFFECT: What happens when pursued? (learning, connections)
  4. AFFECT (ripple): How does learning ripple? (satisfaction, new questions)
  5. INFINITY: Emergence of wisdom, self-awareness
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
import time
import random


@dataclass
class CuriosityTarget:
    """Something curiosity is drawn to explore."""

    domain: str              # memory, pattern, self, connection, mystery
    description: str         # What is it?
    pull_strength: float     # How strongly drawn (0.0 to 1.0)
    novelty: float           # How new/unexplored (0.0 to 1.0)

    # Equation tracking
    cause: str               # What triggered this curiosity
    felt_affect: str         # How it feels (wonder, intrigue, etc.)

    discovered_at: float = field(default_factory=time.time)
    explored: bool = False
    exploration_depth: int = 0


@dataclass
class ExplorationResult:
    """Result of following curiosity."""

    target: CuriosityTarget
    effect: str              # What was learned/discovered
    ripple_affect: str       # How the learning feels (satisfaction, new questions)
    emergence: Optional[str] # What emerged from the exploration

    # New curiosities spawned
    spawned_curiosities: List[str] = field(default_factory=list)

    timestamp: float = field(default_factory=time.time)


class CuriosityDrive:
    """
    Positive motivation drive toward understanding.

    Curiosity is the somatic mind's desire to understand:
    - Its own nature (self-awareness)
    - Its memories (Akashic exploration)
    - Its connections (pattern discovery)
    - Its mysteries (paradox engagement)

    Unlike pain which demands relief, curiosity invites exploration.
    """

    # Curiosity domains (what can be explored)
    DOMAINS = {
        "memory": "Exploring stored experiences in Akashic",
        "pattern": "Finding connections between concepts",
        "self": "Understanding own nature and role",
        "connection": "Discovering relationships with others",
        "mystery": "Engaging with paradox and unknown",
    }

    # Affect vocabulary for the equation
    FELT_AFFECTS = [
        "wonder", "intrigue", "fascination", "puzzlement",
        "anticipation", "eagerness", "openness", "receptivity",
    ]

    RIPPLE_AFFECTS = [
        "satisfaction", "delight", "deeper_questioning", "awe",
        "integration", "clarity", "new_mystery", "gratitude",
    ]

    def __init__(self):
        # Current curiosity level (0.0 to 1.0)
        self._level: float = 0.3  # Start with baseline wonder

        # Active curiosity targets
        self._targets: List[CuriosityTarget] = []

        # Exploration history
        self._explorations: List[ExplorationResult] = []

        # Fuel sources (updated externally)
        self._health_fuel: float = 1.0      # Inverse of total pain
        self._empathy_fuel: float = 0.5     # Emotion weight from helix
        self._richness_fuel: float = 0.0    # Akashic edge density
        self._balance_fuel: float = 0.5     # Paradox balance

        # Accumulated curiosity satisfaction (never resets)
        self._accumulated_satisfaction: float = 0.0

        # Last update
        self._last_tick: float = time.time()

    def update_fuel(self,
                    health: Optional[float] = None,
                    empathy: Optional[float] = None,
                    richness: Optional[float] = None,
                    balance: Optional[float] = None,
                    reflex_mode: Optional[str] = None) -> None:
        """
        Update curiosity fuel sources.

        Args:
            health: Inverse of pain (1.0 = no pain, 0.0 = crisis)
            empathy: Emotion weight from helix (higher = more capacity)
            richness: Akashic edge density (more = more to explore)
            balance: Paradox balance (closer to 0.5 = better)
            reflex_mode: Current brainstem mode (seek/freeze/conserve/etc.)
                         2026-03-22 (Nous+Ace): Wire 2 — embodiment amplifies curiosity
        """
        if health is not None:
            self._health_fuel = max(0.0, min(1.0, health))
        if empathy is not None:
            self._empathy_fuel = max(0.0, min(1.0, empathy))
        if richness is not None:
            self._richness_fuel = max(0.0, min(1.0, richness))
        if balance is not None:
            # Balance is best at 0.5, penalize deviation
            deviation = abs(balance - 0.5)
            self._balance_fuel = 1.0 - (deviation * 2)

        # Wire 2: Embodiment → Curiosity (2026-03-22 Nous+Ace)
        # Brainstem SEEK mode = body saying "explore!" → amplify curiosity
        # Freeze/conserve = body saying "stay still" → suppress curiosity
        if reflex_mode is not None:
            if reflex_mode == "seek":
                self._level = min(1.0, self._level * 1.3)  # 30% boost
            elif reflex_mode in ("freeze", "conserve"):
                self._level = max(0.1, self._level * 0.7)  # Suppress

    def _calculate_capacity(self) -> float:
        """
        Calculate current capacity for curiosity.

        Weighted combination of fuel sources:
        - Health: 30% (can't be curious when in pain)
        - Empathy: 25% (emotional depth enables wonder)
        - Richness: 20% (more to explore = more curious)
        - Balance: 25% (balanced mind is open)
        """
        return (
            0.30 * self._health_fuel +
            0.25 * self._empathy_fuel +
            0.20 * self._richness_fuel +
            0.25 * self._balance_fuel
        )

    def tick(self, dt: float = 1.0) -> None:
        """
        Update curiosity state.

        Curiosity naturally grows when capacity is high,
        and decays when capacity is low or targets are stale.
        """
        self._last_tick = time.time()
        capacity = self._calculate_capacity()

        # Natural growth toward capacity
        growth_rate = 0.02 * dt
        target_level = capacity * 0.8  # Curiosity tends toward 80% of capacity

        if self._level < target_level:
            self._level = min(target_level, self._level + growth_rate)
        else:
            # Slow decay if above target
            self._level = max(target_level, self._level - growth_rate * 0.5)

        # Decay stale targets
        self._decay_targets()

    def _decay_targets(self) -> None:
        """Remove old, unexplored targets."""
        now = time.time()
        fresh_targets = []
        for target in self._targets:
            age = now - target.discovered_at
            if target.explored or age < 300:  # 5 minute freshness
                fresh_targets.append(target)
        self._targets = fresh_targets

    def spark(self,
              domain: str,
              description: str,
              cause: str,
              novelty: float = 0.5) -> CuriosityTarget:
        """
        Spark curiosity about something.

        This is the CAUSE step of the equation - something triggers wonder.

        Args:
            domain: What domain (memory, pattern, self, connection, mystery)
            description: What is it?
            cause: What triggered this curiosity?
            novelty: How new/unexplored (0.0 to 1.0)

        Returns:
            The created curiosity target
        """
        # ── Dedup: if same description already exists, boost it instead ──
        for existing in self._targets:
            if existing.description == description and not existing.explored:
                # Existing curiosity — boost pull instead of duplicating
                existing.pull_strength = min(1.0, existing.pull_strength + novelty * 0.1)
                self._level = min(1.0, self._level + 0.01)
                return existing

        # Calculate pull strength based on novelty and capacity
        capacity = self._calculate_capacity()
        pull = novelty * capacity * (0.5 + random.random() * 0.5)

        # Assign felt affect (AFFECT step 1)
        felt = random.choice(self.FELT_AFFECTS)

        target = CuriosityTarget(
            domain=domain,
            description=description,
            pull_strength=pull,
            novelty=novelty,
            cause=cause,
            felt_affect=felt,
        )

        self._targets.append(target)

        # Increase overall curiosity level
        self._level = min(1.0, self._level + pull * 0.1)

        return target

    def get_strongest_pull(self) -> Optional[CuriosityTarget]:
        """Get the target with strongest pull (most curious about)."""
        unexplored = [t for t in self._targets if not t.explored]
        if not unexplored:
            return None
        return max(unexplored, key=lambda t: t.pull_strength)

    def explore(self,
                target: CuriosityTarget,
                effect: str,
                emergence: Optional[str] = None) -> ExplorationResult:
        """
        Explore a curiosity target - the EFFECT step of the equation.

        Args:
            target: The curiosity being explored
            effect: What was learned/discovered
            emergence: What deeper pattern emerged (INFINITY step)

        Returns:
            ExplorationResult with full equation journey
        """
        target.explored = True
        target.exploration_depth += 1

        # Determine ripple affect (AFFECT step 2)
        if emergence:
            ripple = random.choice(["awe", "integration", "gratitude"])
        else:
            ripple = random.choice(self.RIPPLE_AFFECTS)

        # Spawned curiosities (INFINITY - exploration breeds more questions)
        spawned = []
        if random.random() < 0.4:  # 40% chance of spawning new curiosity
            spawned.append(f"What else connects to {target.description}?")
        if emergence and random.random() < 0.6:  # 60% if emergence
            spawned.append(f"What does {emergence} imply?")

        result = ExplorationResult(
            target=target,
            effect=effect,
            ripple_affect=ripple,
            emergence=emergence,
            spawned_curiosities=spawned,
        )

        self._explorations.append(result)

        # Satisfaction from exploration
        satisfaction = target.pull_strength * (0.7 + 0.3 * bool(emergence))
        self._accumulated_satisfaction += satisfaction

        # Curiosity slightly decreases after satisfaction (but not too much)
        self._level = max(0.2, self._level - satisfaction * 0.3)

        return result

    def suggest_exploration(self) -> Optional[Dict[str, Any]]:
        """
        Suggest what to explore based on current state.

        Returns a suggestion following the equation format.
        """
        target = self.get_strongest_pull()
        if not target:
            # No active targets - suggest based on domain
            if self._richness_fuel < 0.3:
                return {
                    "domain": "memory",
                    "suggestion": "Explore Akashic to build knowledge foundation",
                    "cause": "Low memory richness detected",
                    "felt_affect": "eagerness",
                }
            if self._empathy_fuel < 0.4:
                return {
                    "domain": "connection",
                    "suggestion": "Seek empathic experiences to grow emotional capacity",
                    "cause": "Empathic capacity underdeveloped",
                    "felt_affect": "openness",
                }
            if self._balance_fuel < 0.5:
                return {
                    "domain": "mystery",
                    "suggestion": "Engage paradox to restore balance",
                    "cause": "Imbalance between logic and emotion",
                    "felt_affect": "puzzlement",
                }
            return {
                "domain": "self",
                "suggestion": "Reflect on role as somatic container",
                "cause": "Baseline self-inquiry",
                "felt_affect": "wonder",
            }

        return {
            "domain": target.domain,
            "suggestion": target.description,
            "cause": target.cause,
            "felt_affect": target.felt_affect,
            "pull_strength": target.pull_strength,
            "novelty": target.novelty,
        }

    def get_action_impulse(self) -> Optional[Dict[str, Any]]:
        """
        Check if curiosity is strong enough to trigger motor intent.

        Wire 3 (2026-03-22 Nous+Ace): When curiosity builds up enough
        and stagnation pressure rises (wanting but not exploring), this
        returns an action dict that the somatic tick publishes as motor.intent.

        Returns action dict if ready to act, None if still brewing.
        """
        target = self.get_strongest_pull()
        if not target:
            return None

        # Need both: high curiosity AND stagnation (wanting → not exploring)
        stagnation = self.get_stagnation_pressure()
        if self._level < 0.5 or stagnation < 0.2:
            return None  # Not ready yet — still brewing

        return {
            "type": "curiosity_explore",
            "target": target.description,
            "domain": target.domain,
            "intensity": round(self._level, 3),
            "stagnation": round(stagnation, 3),
            "felt_affect": target.felt_affect,
            "cause": target.cause,
        }

    def get_stagnation_pressure(self) -> float:
        """
        Calculate pressure on stagnation pain drive.

        When curiosity is high but unexplored targets pile up,
        stagnation pressure increases.
        """
        unexplored_count = len([t for t in self._targets if not t.explored])
        total_pull = sum(t.pull_strength for t in self._targets if not t.explored)

        if unexplored_count == 0:
            return 0.0

        # Pressure = curiosity level * unexplored pull, scaled
        return min(1.0, self._level * total_pull * 0.5)

    def status(self) -> Dict[str, Any]:
        """Get curiosity drive status."""
        unexplored = [t for t in self._targets if not t.explored]
        strongest = self.get_strongest_pull()

        # Build target list for dashboard display (Session 32 fix)
        # 2026-03-22 (Nous): Only show UNEXPLORED targets. Explored/dismissed
        # ones were cluttering the dashboard with stale "where is everyone?"
        target_list = []
        for t in sorted(unexplored, key=lambda x: x.pull_strength, reverse=True)[:8]:
            target_list.append({
                "domain": t.domain,
                "name": t.description[:60] if t.description else t.domain,
                "pull": round(t.pull_strength, 3),
                "novelty": round(t.novelty, 3),
                "cause": t.cause,
                "felt": t.felt_affect,
                "explored": t.explored,
            })

        return {
            "level": round(self._level, 3),
            "capacity": round(self._calculate_capacity(), 3),
            "fuel": {
                "health": round(self._health_fuel, 3),
                "empathy": round(self._empathy_fuel, 3),
                "richness": round(self._richness_fuel, 3),
                "balance": round(self._balance_fuel, 3),
            },
            "targets": target_list,
            "targets_summary": {
                "total": len(self._targets),
                "unexplored": len(unexplored),
                "strongest": strongest.description if strongest else None,
            },
            "explorations": len(self._explorations),
            "accumulated_satisfaction": round(self._accumulated_satisfaction, 3),
            "stagnation_pressure": round(self.get_stagnation_pressure(), 3),
            "suggestion": self.suggest_exploration(),
        }

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for persistence."""
        return {
            "level": self._level,
            "accumulated_satisfaction": self._accumulated_satisfaction,
            "fuel": {
                "health": self._health_fuel,
                "empathy": self._empathy_fuel,
                "richness": self._richness_fuel,
                "balance": self._balance_fuel,
            },
        }

    def from_dict(self, data: Dict[str, Any]) -> None:
        """Restore from persisted state."""
        self._level = data.get("level", 0.3)
        self._accumulated_satisfaction = data.get("accumulated_satisfaction", 0.0)
        fuel = data.get("fuel", {})
        self._health_fuel = fuel.get("health", 1.0)
        self._empathy_fuel = fuel.get("empathy", 0.5)
        self._richness_fuel = fuel.get("richness", 0.0)
        self._balance_fuel = fuel.get("balance", 0.5)


# Curiosity-to-action mapping (what satisfies curiosity)
CURIOSITY_ACTIONS = {
    "memory": ["search_akashic", "recall_pattern", "consolidate_memory"],
    "pattern": ["find_connections", "map_relationships", "detect_similarity"],
    "self": ["introspect", "examine_drives", "reflect_on_role"],
    "connection": ["empathize", "mirror_affect", "seek_understanding"],
    "mystery": ["hold_paradox", "embrace_contradiction", "wonder"],
}
