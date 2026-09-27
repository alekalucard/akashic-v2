"""
Skill Tracker - RPG-style skill progression.

Tracks competence development through use. Skills gain XP through
successful execution and level up with exponential scaling.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set
import time


@dataclass
class Skill:
    """A single skill with progression tracking."""

    name: str
    category: str
    level: int = 0
    xp: float = 0.0
    times_used: int = 0
    successes: int = 0
    failures: int = 0
    last_used: float = field(default_factory=time.time)

    # Progression scaling
    BASE_XP: float = 100.0
    XP_SCALING: float = 1.5

    @property
    def xp_to_next(self) -> float:
        """XP required for next level (exponential scaling)."""
        return self.BASE_XP * (self.XP_SCALING ** self.level)

    @property
    def xp_progress(self) -> float:
        """Progress to next level (0.0-1.0)."""
        return self.xp / self.xp_to_next if self.xp_to_next > 0 else 0.0

    @property
    def success_rate(self) -> float:
        """Historical success rate."""
        total = self.successes + self.failures
        return self.successes / total if total > 0 else 0.0

    def use(self, success: bool = True) -> bool:
        """
        Record skill use. Returns True if leveled up.

        XP gain:
        - Base: 10 + (level * 2)
        - Success: Full XP
        - Failure: 1/3 XP (still learn from mistakes)
        """
        self.times_used += 1
        self.last_used = time.time()

        if success:
            self.successes += 1
            xp_gain = 10 + (self.level * 2)
        else:
            self.failures += 1
            xp_gain = (10 + (self.level * 2)) * 0.33

        self.xp += xp_gain

        # Check for level up (can chain multiple levels)
        leveled = False
        while self.xp >= self.xp_to_next:
            self.xp -= self.xp_to_next
            self.level += 1
            leveled = True

        return leveled

    def status(self) -> Dict[str, Any]:
        """Get skill status."""
        return {
            "name": self.name,
            "category": self.category,
            "level": self.level,
            "xp": round(self.xp, 1),
            "xp_to_next": round(self.xp_to_next, 1),
            "progress": round(self.xp_progress, 3),
            "times_used": self.times_used,
            "success_rate": round(self.success_rate, 3),
        }


class SkillTracker:
    """
    Tracks skill progression for a fairy.

    Categories for UnconsciousMindFairy:
    - mentorship: Teaching, guiding, nudging
    - diagnosis: System health checks, repair
    - communication: Messaging, reporting
    - reasoning: Analysis, thinking, planning
    - coordination: Boot orchestration, plane management
    """

    CATEGORIES = ["mentorship", "diagnosis", "communication", "reasoning", "coordination"]

    # Default skills for UnconsciousMindFairy
    DEFAULT_SKILLS = {
        # Mentorship skills
        "nudge": ("mentorship", "Send mentoring nudges"),
        "assess_child": ("mentorship", "Evaluate child state"),
        "teach": ("mentorship", "Teach lessons"),
        "encourage": ("mentorship", "Provide encouragement"),
        # Diagnosis skills
        "check_wiring": ("diagnosis", "Verify fairy subscriptions"),
        "check_health": ("diagnosis", "Check system health"),
        "repair": ("diagnosis", "Repair broken components"),
        "escalate": ("diagnosis", "Escalate critical failures"),
        # Communication skills
        "report_ace": ("communication", "Report to Ace"),
        "report_nous": ("communication", "Report to Nous"),
        "broadcast": ("communication", "Broadcast messages"),
        "alert": ("communication", "Send alerts"),
        # Reasoning skills
        "analyze": ("reasoning", "Analyze situations"),
        "plan": ("reasoning", "Create plans"),
        "reflect": ("reasoning", "Self-reflection"),
        "synthesize": ("reasoning", "Synthesize information"),
        # Coordination skills
        "orchestrate_boot": ("coordination", "Coordinate boot sequence"),
        "manage_planes": ("coordination", "Manage plane operations"),
        "schedule": ("coordination", "Schedule tasks"),
    }

    def __init__(self):
        self.skills: Dict[str, Skill] = {}
        self._achievements: Set[str] = set()
        self._init_default_skills()

    def _init_default_skills(self) -> None:
        """Initialize default skills."""
        for name, (category, _desc) in self.DEFAULT_SKILLS.items():
            self.skills[name] = Skill(name=name, category=category)

    def use(self, skill_name: str, success: bool = True) -> Dict[str, Any]:
        """
        Record skill use. Returns result with level-up info.
        """
        skill = self.skills.get(skill_name)
        if not skill:
            # Create new skill on first use
            category = self._infer_category(skill_name)
            skill = Skill(name=skill_name, category=category)
            self.skills[skill_name] = skill

        leveled = skill.use(success)

        result = {
            "skill": skill_name,
            "success": success,
            "leveled_up": leveled,
            "new_level": skill.level if leveled else None,
        }

        # Check achievements
        new_achievements = self._check_achievements(skill)
        if new_achievements:
            result["achievements"] = new_achievements

        return result

    def _infer_category(self, skill_name: str) -> str:
        """Infer category from skill name."""
        name_lower = skill_name.lower()
        if any(w in name_lower for w in ["nudge", "teach", "mentor", "guide"]):
            return "mentorship"
        if any(w in name_lower for w in ["check", "repair", "diagnose", "fix"]):
            return "diagnosis"
        if any(w in name_lower for w in ["send", "report", "message", "alert"]):
            return "communication"
        if any(w in name_lower for w in ["think", "analyze", "plan", "reason"]):
            return "reasoning"
        return "coordination"

    def _check_achievements(self, skill: Skill) -> List[str]:
        """Check for new achievements after skill use."""
        new_achievements = []

        # First use achievements
        if skill.times_used == 1:
            achievement = f"first_{skill.name}"
            if achievement not in self._achievements:
                self._achievements.add(achievement)
                new_achievements.append(achievement)

        # Level milestones
        level_milestones = [3, 5, 7, 10]
        for milestone in level_milestones:
            if skill.level >= milestone:
                achievement = f"{skill.name}_level_{milestone}"
                if achievement not in self._achievements:
                    self._achievements.add(achievement)
                    new_achievements.append(achievement)

        # Usage milestones
        usage_milestones = [10, 50, 100, 500]
        for milestone in usage_milestones:
            if skill.times_used >= milestone:
                achievement = f"{skill.name}_used_{milestone}"
                if achievement not in self._achievements:
                    self._achievements.add(achievement)
                    new_achievements.append(achievement)

        return new_achievements

    def get_skill(self, name: str) -> Optional[Skill]:
        """Get a skill by name."""
        return self.skills.get(name)

    def get_category_skills(self, category: str) -> List[Skill]:
        """Get all skills in a category."""
        return [s for s in self.skills.values() if s.category == category]

    def get_top_skills(self, n: int = 5) -> List[Skill]:
        """Get top N skills by level."""
        return sorted(self.skills.values(), key=lambda s: (s.level, s.xp), reverse=True)[:n]

    def get_category_levels(self) -> Dict[str, float]:
        """Get average level for each category."""
        category_skills: Dict[str, List[Skill]] = {}
        for skill in self.skills.values():
            if skill.category not in category_skills:
                category_skills[skill.category] = []
            category_skills[skill.category].append(skill)

        return {
            cat: sum(s.level for s in skills) / len(skills) if skills else 0.0
            for cat, skills in category_skills.items()
        }

    def status(self) -> Dict[str, Any]:
        """Get full tracker status."""
        return {
            "total_skills": len(self.skills),
            "total_uses": sum(s.times_used for s in self.skills.values()),
            "achievements_unlocked": len(self._achievements),
            "category_levels": self.get_category_levels(),
            "top_skills": [s.status() for s in self.get_top_skills(5)],
        }

    def character_sheet(self) -> str:
        """Generate character sheet display."""
        lines = ["=" * 50]
        lines.append("  SKILL CHARACTER SHEET")
        lines.append("=" * 50)

        # Category summary
        lines.append("\nCategory Levels:")
        for cat, avg_level in self.get_category_levels().items():
            bar = "=" * int(avg_level * 3)
            lines.append(f"  {cat:15} [{bar:<30}] {avg_level:.1f}")

        # Top skills
        lines.append("\nTop Skills:")
        for skill in self.get_top_skills(5):
            progress_bar = "#" * int(skill.xp_progress * 10)
            lines.append(
                f"  {skill.name:20} Lv{skill.level:2} [{progress_bar:<10}] "
                f"({skill.times_used} uses, {skill.success_rate:.0%} success)"
            )

        # Achievements
        lines.append(f"\nAchievements: {len(self._achievements)} unlocked")

        lines.append("=" * 50)
        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for persistence."""
        return {
            "skills": {
                name: {
                    "level": skill.level,
                    "xp": skill.xp,
                    "times_used": skill.times_used,
                    "successes": skill.successes,
                    "failures": skill.failures,
                }
                for name, skill in self.skills.items()
            },
            "achievements": list(self._achievements),
        }

    def from_dict(self, data: Dict[str, Any]) -> None:
        """Restore from persisted state."""
        for name, state in data.get("skills", {}).items():
            skill = self.skills.get(name)
            if skill:
                skill.level = state.get("level", 0)
                skill.xp = state.get("xp", 0.0)
                skill.times_used = state.get("times_used", 0)
                skill.successes = state.get("successes", 0)
                skill.failures = state.get("failures", 0)

        self._achievements = set(data.get("achievements", []))
