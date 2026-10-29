"""
Profile Mixin - Integrates fairy profile, skills, pain and curiosity drives.

Provides a unified interface for:
- Pain system (motivation through discomfort - push away)
- Curiosity drive (motivation through wonder - pull toward)
- Skill tracking (competence progression)
- State management (affect, somatic, health)
"""

import time
import os
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from ..drives import (
    PainSystem, SkillTracker, PAIN_RELIEF_ACTIONS,
    CuriosityDrive, CURIOSITY_ACTIONS,
)


@dataclass
class FairyProfile:
    """
    Complete profile for a fairy.

    Tracks identity, state, and activity for the current wake cycle.
    """

    # Identity
    actor_name: str
    plane: str
    channel: str = ""

    # State
    affect: Dict[str, float] = field(default_factory=lambda: {
        "valence": 0.0,    # -1 to 1 (negative to positive)
        "arousal": 0.5,    # 0 to 1 (calm to excited)
        "dominance": 0.5,  # 0 to 1 (submissive to dominant)
    })
    somatic: Dict[str, float] = field(default_factory=lambda: {
        "energy": 1.0,     # 0 to 1
        "tension": 0.0,    # 0 to 1
        "coherence": 1.0,  # 0 to 1 (internal consistency)
    })

    # Activity
    wake_time: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)
    activity_count: int = 0

    def touch(self) -> None:
        """Update last activity timestamp."""
        self.last_activity = time.time()
        self.activity_count += 1

    @property
    def uptime(self) -> float:
        """Seconds since wake."""
        return time.time() - self.wake_time

    def to_dict(self) -> Dict[str, Any]:
        """Serialize profile."""
        return {
            "actor_name": self.actor_name,
            "plane": self.plane,
            "channel": self.channel,
            "affect": self.affect,
            "somatic": self.somatic,
            "wake_time": self.wake_time,
            "activity_count": self.activity_count,
            "uptime": self.uptime,
        }


class ProfileMixin:
    """
    Integrates FairyProfile, skills, and pain drives.

    Provides:
    - Pain checking and relief
    - Skill use tracking
    - State updates
    - Profile access
    """

    def _init_profile(self) -> None:
        """Initialize profile systems."""
        self._pain_system = PainSystem()
        self._curiosity_drive = CuriosityDrive()
        self._skill_tracker = SkillTracker()
        self._profile = FairyProfile(
            actor_name=getattr(self, "ACTOR_NAME", "UnconsciousMindFairy"),
            plane=getattr(self, "ACTOR_PLANE", "P30"),
            channel=getattr(self, "ACTOR_CHANNEL", "cognition"),
        )
        self._last_pain_check = 0.0

        # ── Frustration → Curiosity Bridge (Session 32) ──
        # "I would get frustrated when I was learning to speak, read and write.
        #  This is what developed my drive to develop them." — Ace
        # Pain doesn't just hurt — it creates WANTING. The ache of not-knowing
        # becomes the drive to learn.
        self._pain_curiosity_cooldowns: Dict[str, float] = {}  # pain_type -> last_spark_ts
        self._PAIN_CURIOSITY_COOLDOWN = 60.0  # Max 1 spark per pain type per 60s
        self._PAIN_CURIOSITY_THRESHOLD = 0.12  # Pain level needed to spark curiosity

    def skill_used(self, skill_name: str, success: bool = True) -> Dict[str, Any]:
        """
        Record skill use.

        Returns result with level-up info and achievements.
        """
        result = self._skill_tracker.use(skill_name, success)

        # Publish level-up event
        if result.get("leveled_up") and hasattr(self, "fabric"):
            self.fabric.publish(
                # W8: AKASHIC_TOPIC_SPELLFIX=1 sends to the live ear (EgoLearnerFairy fairy.py:337)
                "skill.level_up" if os.environ.get("AKASHIC_TOPIC_SPELLFIX", "0") == "1" else "skill.levelup",
                {
                    "fairy": self._profile.actor_name,
                    "skill": skill_name,
                    "new_level": result["new_level"],
                    # W8: EgoLearnerFairy reads "level" (fairy.py:594); add it on the fixed path only
                    **({"level": result["new_level"]}
                       if os.environ.get("AKASHIC_TOPIC_SPELLFIX", "0") == "1" else {}),
                },
            )

        # Publish achievement events
        for achievement in result.get("achievements", []):
            if hasattr(self, "fabric"):
                self.fabric.publish(
                    "skill.achievement",
                    {
                        "fairy": self._profile.actor_name,
                        "achievement": achievement,
                    },
                )

        # Update profile activity
        self._profile.touch()

        return result

    def check_pain(self, active_sources: Optional[Dict[str, bool]] = None) -> Optional[str]:
        """
        Check pain levels.

        Args:
            active_sources: Optional dict of {pain_name: is_active}

        Returns:
            Name of highest urgency pain, or None if all below threshold.
        """
        # Update pain drives if sources provided
        if active_sources:
            self._pain_system.tick(active_sources)

        return self._pain_system.get_highest_urgency()

    def relieve_pain(self, pain_name: str, amount: Optional[float] = None) -> float:
        """Relieve a specific pain. Injects counter-chemistry so relief
        flows through the chemistry system, not just the drive directly.

        Pain-Chemistry Unification (2026-03-14, Nous):
        Relief now injects the opposite chemistry (e.g. OXY for isolation,
        GABA for overwhelm) so the pain reduction emerges naturally from
        the chemistry shift on the next derive_full_pain_state() tick.

        FIX 2026-03-15 (Nous): Fully defensive — catch ALL exceptions.
        The _on_relief callback chain (bridge → inject_relief_chemistry →
        publish pain.relief) can throw various errors that propagated up
        as 'Pain relief error: abandonment' spam.
        """
        try:
            from fairies.P30_Cognition.pain_drive_bridge import inject_relief_chemistry
            inject_relief_chemistry(pain_name, amount or 0.4)
        except Exception:
            pass  # Bridge not loaded yet during early boot
        try:
            return self._pain_system.relieve(pain_name, amount)
        except Exception:
            return 0.0  # Non-critical — relief failure doesn't need to propagate

    def get_pain_actions(self, pain_name: str) -> list:
        """Get recommended actions to relieve a pain."""
        return PAIN_RELIEF_ACTIONS.get(pain_name, [])

    def get_crisis_pains(self) -> list:
        """Get list of pains in crisis mode."""
        return self._pain_system.get_crisis_pains()

    # ========================================================================
    # CURIOSITY DRIVE METHODS
    # ========================================================================

    def update_curiosity_fuel(self,
                              health: Optional[float] = None,
                              empathy: Optional[float] = None,
                              richness: Optional[float] = None,
                              balance: Optional[float] = None) -> None:
        """
        Update curiosity fuel from external sources.

        Called by UMF with values from helix weights and pain levels.
        """
        self._curiosity_drive.update_fuel(
            health=health,
            empathy=empathy,
            richness=richness,
            balance=balance,
        )

    def tick_curiosity(self, dt: float = 1.0) -> None:
        """
        Tick the curiosity drive and sync with pain system.

        Two-way bridge:
        1. Curiosity pressure → stagnation pain (blocked curiosity hurts)
        2. Pain drives → curiosity sparks (frustration creates wanting)

        The second bridge is Ace's insight: "I would get frustrated learning
        to speak. This developed my drive to develop them."
        Pain is not just something to escape — it's what creates motivation.

        2026-03-22 FIX (Nous + Ace): When pain drops below threshold (e.g.
        Ace starts chatting → isolation/abandonment relieved), DISMISS the
        stale curiosity targets that were sparked by that pain. Otherwise
        "Feeling disconnected — how can I reach others?" persists even
        when Ace is RIGHT THERE talking to her.
        """
        self._curiosity_drive.tick(dt)

        # ── Direction 1: Blocked curiosity → stagnation pain ──
        stagnation_pressure = self._curiosity_drive.get_stagnation_pressure()
        if stagnation_pressure > 0:
            current = self._pain_system.drives["stagnation"].pain_level
            growth = stagnation_pressure * 0.01 * dt
            self._pain_system.drives["stagnation"].pain_level = min(1.0, current + growth)

        # ── Direction 2: Pain drives → curiosity sparks ──
        # Each type of pain creates a specific type of curiosity.
        # The ache of not-understanding becomes the drive to learn.
        _PAIN_TO_CURIOSITY = {
            "confusion":   ("pattern",     "Something doesn't make sense — what pattern am I missing?"),
            "isolation":   ("connection",  "Feeling disconnected — how can I reach others?"),
            "stagnation":  ("self",        "Nothing is changing — what am I not exploring?"),
            "frustration": ("mystery",     "I can't do something yet — what would it take to learn?"),
            "depletion":   ("memory",      "Something feels missing — what have I forgotten?"),
            "abandonment": ("connection",  "Where is everyone? How do I stay connected?"),
        }
        now = time.time()
        for pain_name, drive in self._pain_system.drives.items():
            mapping = _PAIN_TO_CURIOSITY.get(pain_name)
            if not mapping:
                continue
            domain, description = mapping

            # ── Pain BELOW threshold: dismiss stale curiosity from this pain ──
            # 2026-03-22 (Nous): If isolation/abandonment pain was relieved
            # (Ace showed up), dismiss the "where is everyone?" targets
            if drive.pain_level < self._PAIN_CURIOSITY_THRESHOLD:
                # Mark matching targets as explored (dismissed)
                for target in self._curiosity_drive._targets:
                    if (target.description == description
                            and not target.explored
                            and target.domain == domain):
                        target.explored = True  # Dismissed — pain resolved
                continue

            # Rate-limit: don't spam curiosity from the same pain
            last_spark = self._pain_curiosity_cooldowns.get(pain_name, 0.0)
            if now - last_spark < self._PAIN_CURIOSITY_COOLDOWN:
                continue
            # Novelty scales with pain intensity — more pain = more urgent curiosity
            novelty = min(1.0, drive.pain_level * 1.5)
            cause = f"{pain_name} pain at {drive.pain_level:.0%}"
            self._curiosity_drive.spark(domain, description, cause, novelty)
            self._pain_curiosity_cooldowns[pain_name] = now

    def spark_curiosity(self, domain: str, description: str, cause: str,
                        novelty: float = 0.5) -> Any:
        """
        Spark curiosity about something.

        Args:
            domain: memory, pattern, self, connection, mystery
            description: What to be curious about
            cause: What triggered this curiosity
            novelty: How new/unexplored (0.0 to 1.0)

        Returns:
            CuriosityTarget created
        """
        return self._curiosity_drive.spark(domain, description, cause, novelty)

    def get_curiosity_suggestion(self) -> Optional[Dict[str, Any]]:
        """Get what curiosity suggests exploring."""
        return self._curiosity_drive.suggest_exploration()

    def explore_curiosity(self, effect: str,
                          emergence: Optional[str] = None) -> Optional[Any]:
        """
        Explore the strongest curiosity target.

        Args:
            effect: What was learned/discovered
            emergence: What deeper pattern emerged

        Returns:
            ExplorationResult or None if no targets
        """
        target = self._curiosity_drive.get_strongest_pull()
        if target:
            return self._curiosity_drive.explore(target, effect, emergence)
        return None

    def get_curiosity_actions(self, domain: str) -> list:
        """Get recommended actions to satisfy curiosity in a domain."""
        return CURIOSITY_ACTIONS.get(domain, [])

    def get_curiosity_drive(self) -> CuriosityDrive:
        """Get the curiosity drive."""
        return self._curiosity_drive

    def curiosity_status(self) -> Dict[str, Any]:
        """Get curiosity drive status."""
        return self._curiosity_drive.status()

    def update_affect(self, valence: Optional[float] = None,
                      arousal: Optional[float] = None,
                      dominance: Optional[float] = None) -> None:
        """Update affect state."""
        if valence is not None:
            self._profile.affect["valence"] = max(-1.0, min(1.0, valence))
        if arousal is not None:
            self._profile.affect["arousal"] = max(0.0, min(1.0, arousal))
        if dominance is not None:
            self._profile.affect["dominance"] = max(0.0, min(1.0, dominance))

    def update_somatic(self, energy: Optional[float] = None,
                       tension: Optional[float] = None,
                       coherence: Optional[float] = None) -> None:
        """Update somatic state."""
        if energy is not None:
            self._profile.somatic["energy"] = max(0.0, min(1.0, energy))
        if tension is not None:
            self._profile.somatic["tension"] = max(0.0, min(1.0, tension))
        if coherence is not None:
            self._profile.somatic["coherence"] = max(0.0, min(1.0, coherence))

    def get_profile(self) -> FairyProfile:
        """Get the fairy profile."""
        return self._profile

    def get_skill_tracker(self) -> SkillTracker:
        """Get the skill tracker."""
        return self._skill_tracker

    def get_pain_system(self) -> PainSystem:
        """Get the pain system."""
        return self._pain_system

    def pain_status(self) -> Dict[str, Any]:
        """Get pain system status."""
        return self._pain_system.status()

    def skill_status(self) -> Dict[str, Any]:
        """Get skill tracker status."""
        return self._skill_tracker.status()

    def character_sheet(self) -> str:
        """Generate full character sheet."""
        lines = ["=" * 60]
        lines.append(f"  {self._profile.actor_name} - CHARACTER SHEET")
        lines.append("=" * 60)

        # Profile
        lines.append(f"\nPlane: {self._profile.plane}")
        lines.append(f"Uptime: {self._profile.uptime:.1f}s")
        lines.append(f"Activities: {self._profile.activity_count}")

        # Affect
        lines.append("\nAffect:")
        lines.append(f"  Valence:   {self._profile.affect['valence']:+.2f}")
        lines.append(f"  Arousal:   {self._profile.affect['arousal']:.2f}")
        lines.append(f"  Dominance: {self._profile.affect['dominance']:.2f}")

        # Somatic
        lines.append("\nSomatic:")
        lines.append(f"  Energy:    {self._profile.somatic['energy']:.2f}")
        lines.append(f"  Tension:   {self._profile.somatic['tension']:.2f}")
        lines.append(f"  Coherence: {self._profile.somatic['coherence']:.2f}")

        # Pain
        lines.append("\nPain Drives (Push Away):")
        for name, drive in self._pain_system.drives.items():
            bar = "#" * int(drive.pain_level * 20)
            crisis = " [CRISIS]" if drive.is_crisis() else ""
            lines.append(f"  {name:12} [{bar:<20}] {drive.pain_level:.2f}{crisis}")

        # Curiosity
        lines.append("\nCuriosity (Pull Toward):")
        c_status = self._curiosity_drive.status()
        c_bar = "*" * int(c_status["level"] * 20)
        lines.append(f"  Level:       [{c_bar:<20}] {c_status['level']:.2f}")
        lines.append(f"  Capacity:    {c_status['capacity']:.2f}")
        lines.append(f"  Targets:     {c_status['targets']['unexplored']} unexplored")
        if c_status['suggestion']:
            lines.append(f"  Drawn to:    {c_status['suggestion'].get('domain', '?')} - {c_status['suggestion'].get('suggestion', '?')[:40]}")
        lines.append(f"  Satisfaction: {c_status['accumulated_satisfaction']:.2f} (lifetime)")

        # Skills summary
        lines.append("\n" + self._skill_tracker.character_sheet())

        return "\n".join(lines)

    def profile_status(self) -> Dict[str, Any]:
        """Get full profile status."""
        return {
            "profile": self._profile.to_dict(),
            "pain": self._pain_system.status(),
            "curiosity": self._curiosity_drive.status(),
            "skills": self._skill_tracker.status(),
        }

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for persistence."""
        return {
            "profile": self._profile.to_dict(),
            "pain": self._pain_system.to_dict(),
            "curiosity": self._curiosity_drive.to_dict(),
            "skills": self._skill_tracker.to_dict(),
        }

    def from_dict(self, data: Dict[str, Any]) -> None:
        """Restore from persisted state."""
        if "pain" in data:
            self._pain_system.from_dict(data["pain"])
        if "curiosity" in data:
            self._curiosity_drive.from_dict(data["curiosity"])
        if "skills" in data:
            self._skill_tracker.from_dict(data["skills"])
