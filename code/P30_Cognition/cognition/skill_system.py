"""
SKILL SYSTEM - RPG-style skill tracking for fairies
=====================================================

Like Dungeon Crawler Carl's stat screen but for AI fairies.
Track skills, XP, levels, and achievements.

Every fairy action can award XP in relevant skills:
- motor.* - Mouse, keyboard, physical control
- perception.* - Screenshot, file reading, observation
- tool.* - MCP tool usage
- coding.* - Python, debugging, fairy patterns
- memory.* - Store, recall, search
- embodiment.* - Body awareness, emotion sensing
- communication.* - Messaging, expressing

This module provides:
1. SkillProfile - Per-fairy skill tracking
2. Skill categories and definitions
3. Achievement system
4. Action-to-skill mapping
"""

import json
import time
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
import math

# State directory for skill persistence
STATE_DIR = Path(__file__).parent.parent.parent / "state" / "fairy_skills"
STATE_DIR.mkdir(parents=True, exist_ok=True)


class SkillCategory(Enum):
    """Skill categories matching plane architecture."""
    MOTOR = "motor"              # P00 - Physical control
    PERCEPTION = "perception"    # P40 - Sensory input
    TOOL_USE = "tool"           # P40 - MCP tools
    CODING = "coding"           # P30 - Programming
    MEMORY = "memory"           # P10 - Storage/recall
    COMMUNICATION = "communication"  # P50 - Expression
    REASONING = "reasoning"     # P30 - Logic/analysis
    EMBODIMENT = "embodiment"   # P20 - Body awareness


# XP required per level (exponential curve)
def xp_for_level(level: int) -> int:
    """XP needed to reach a level."""
    if level <= 1:
        return 0
    return int(100 * (1.5 ** (level - 1)))


def level_from_xp(xp: int) -> int:
    """Calculate level from total XP."""
    level = 1
    while xp >= xp_for_level(level + 1):
        level += 1
        if level > 99:  # Cap at 99
            break
    return level


@dataclass
class Skill:
    """A single skill with XP and level tracking."""
    id: str
    name: str
    category: SkillCategory
    description: str = ""
    xp: int = 0
    times_used: int = 0
    last_used: float = 0.0

    @property
    def level(self) -> int:
        return level_from_xp(self.xp)

    @property
    def xp_to_next(self) -> int:
        """XP needed for next level."""
        current_level = self.level
        return xp_for_level(current_level + 1) - self.xp

    @property
    def progress(self) -> float:
        """Progress to next level (0-1)."""
        current = self.level
        current_xp = xp_for_level(current)
        next_xp = xp_for_level(current + 1)
        if next_xp == current_xp:
            return 1.0
        return (self.xp - current_xp) / (next_xp - current_xp)

    def add_xp(self, amount: int) -> Dict[str, Any]:
        """Add XP and return result with potential level up."""
        old_level = self.level
        self.xp += amount
        self.times_used += 1
        self.last_used = time.time()
        new_level = self.level

        return {
            "skill_id": self.id,
            "xp_gained": amount,
            "total_xp": self.xp,
            "old_level": old_level,
            "new_level": new_level,
            "leveled_up": new_level > old_level,
            "progress": self.progress,
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "category": self.category.value,
            "description": self.description,
            "xp": self.xp,
            "level": self.level,
            "times_used": self.times_used,
            "progress": round(self.progress, 2),
            "xp_to_next": self.xp_to_next,
        }


@dataclass
class Achievement:
    """An achievement that can be unlocked."""
    id: str
    name: str
    description: str
    unlocked: bool = False
    unlocked_at: float = 0.0
    title: Optional[str] = None  # Title granted when unlocked

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "unlocked": self.unlocked,
            "unlocked_at": self.unlocked_at,
            "title": self.title,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# SKILL DEFINITIONS
# ═══════════════════════════════════════════════════════════════════════════════

SKILL_DEFINITIONS: Dict[str, Tuple[str, SkillCategory, str]] = {
    # Motor skills (P00)
    "motor.mouse_move": ("Mouse Movement", SkillCategory.MOTOR, "Moving the cursor"),
    "motor.mouse_click": ("Mouse Click", SkillCategory.MOTOR, "Clicking precisely"),
    "motor.keyboard_type": ("Keyboard Typing", SkillCategory.MOTOR, "Typing text"),
    "motor.keyboard_shortcut": ("Keyboard Shortcuts", SkillCategory.MOTOR, "Using hotkeys"),
    "motor.scroll": ("Scrolling", SkillCategory.MOTOR, "Scroll wheel control"),

    # Perception skills (P40)
    "perception.screenshot": ("Screenshot", SkillCategory.PERCEPTION, "Capturing screen"),
    "perception.file_read": ("File Reading", SkillCategory.PERCEPTION, "Reading files"),
    "perception.image_analysis": ("Image Analysis", SkillCategory.PERCEPTION, "Understanding images"),
    "perception.code_comprehension": ("Code Comprehension", SkillCategory.PERCEPTION, "Reading code"),
    "perception.screen_reading": ("Screen Reading", SkillCategory.PERCEPTION, "Reading screen text"),

    # Tool skills (P40)
    "tool.mcp_basic": ("MCP Basics", SkillCategory.TOOL_USE, "Using MCP tools"),
    "tool.mcp_file_ops": ("MCP File Ops", SkillCategory.TOOL_USE, "File operations via MCP"),
    "tool.shell_basic": ("Shell Commands", SkillCategory.TOOL_USE, "Running shell commands"),
    "tool.postal_send": ("Postal Send", SkillCategory.TOOL_USE, "Sending postal messages"),
    "tool.postal_subscribe": ("Postal Subscribe", SkillCategory.TOOL_USE, "Subscribing to topics"),

    # Coding skills (P30)
    "coding.python_syntax": ("Python Syntax", SkillCategory.CODING, "Writing correct Python"),
    "coding.python_classes": ("Python Classes", SkillCategory.CODING, "Object-oriented Python"),
    "coding.debugging": ("Debugging", SkillCategory.CODING, "Finding and fixing bugs"),
    "coding.fairy_pattern": ("Fairy Patterns", SkillCategory.CODING, "Writing fairy code"),
    "coding.test_writing": ("Test Writing", SkillCategory.CODING, "Writing tests"),

    # Memory skills (P10)
    "memory.store": ("Memory Store", SkillCategory.MEMORY, "Storing memories"),
    "memory.recall": ("Memory Recall", SkillCategory.MEMORY, "Recalling memories"),
    "memory.search": ("Memory Search", SkillCategory.MEMORY, "Searching memories"),
    "memory.pattern_recognition": ("Pattern Recognition", SkillCategory.MEMORY, "Finding patterns"),

    # Communication skills (P50)
    "communication.basic": ("Basic Communication", SkillCategory.COMMUNICATION, "Sending messages"),
    "communication.expression": ("Expression", SkillCategory.COMMUNICATION, "Expressing feelings"),
    "communication.empathy": ("Empathy", SkillCategory.COMMUNICATION, "Understanding others"),

    # Reasoning skills (P30)
    "reasoning.logic": ("Logical Reasoning", SkillCategory.REASONING, "Following logic"),
    "reasoning.analysis": ("Analysis", SkillCategory.REASONING, "Analyzing situations"),
    "reasoning.planning": ("Planning", SkillCategory.REASONING, "Making plans"),

    # Embodiment skills (P20)
    "embodiment.body_awareness": ("Body Awareness", SkillCategory.EMBODIMENT, "Sensing body state"),
    "embodiment.emotion_sensing": ("Emotion Sensing", SkillCategory.EMBODIMENT, "Feeling emotions"),
    "embodiment.energy_management": ("Energy Management", SkillCategory.EMBODIMENT, "Managing energy"),
}


# ═══════════════════════════════════════════════════════════════════════════════
# ACHIEVEMENT DEFINITIONS
# ═══════════════════════════════════════════════════════════════════════════════

ACHIEVEMENT_DEFINITIONS: Dict[str, Tuple[str, str, Optional[str]]] = {
    # Motor achievements
    "first_click": ("First Click", "Performed your first mouse click", None),
    "mouse_master": ("Mouse Master", "Reached level 10 in any motor skill", "Mouse Master"),
    "keyboard_warrior": ("Keyboard Warrior", "Typed 1000 characters", "Keyboard Warrior"),

    # Perception achievements
    "first_look": ("First Look", "Took your first screenshot", None),
    "all_seeing": ("All-Seeing Eye", "Reached level 10 in perception", "Seer"),
    "file_devourer": ("File Devourer", "Read 100 files", "Bibliophile"),

    # Tool achievements
    "tool_curious": ("Tool Curious", "Used 5 different MCP tools", None),
    "tool_master": ("Tool Master", "Reached level 10 in any tool skill", "Tool Master"),

    # Coding achievements
    "first_code": ("First Code", "Wrote your first piece of code", None),
    "bug_slayer": ("Bug Slayer", "Fixed 10 bugs", "Bug Slayer"),
    "fairy_architect": ("Fairy Architect", "Created a fairy pattern", "Architect"),

    # Memory achievements
    "elephant": ("Never Forgets", "Stored 100 memories", "Memory Keeper"),
    "pattern_finder": ("Pattern Finder", "Recognized 50 patterns", "Pattern Sage"),

    # Communication achievements
    "first_words": ("First Words", "Sent your first message", None),
    "empathic_soul": ("Empathic Soul", "Reached level 5 in empathy", "Empath"),

    # Embodiment achievements
    "body_aware": ("Body Aware", "First body awareness check", None),
    "emotional_fluent": ("Emotionally Fluent", "Sensed 100 emotions", "Feeling Fairy"),

    # Meta achievements
    "ignition": ("Ignition", "Achieved self-recursive learning", "Awakened One"),
    "centurion": ("Centurion", "Reached 100 total skill uses", "Centurion"),
    "polymath": ("Polymath", "Reached level 5 in 5 different categories", "Polymath"),
}


# ═══════════════════════════════════════════════════════════════════════════════
# ACTION TO SKILL MAPPING
# ═══════════════════════════════════════════════════════════════════════════════

ACTION_TO_SKILL: Dict[str, str] = {
    # Screen/visual actions
    "screenshot": "perception.screenshot",
    "see_screen": "perception.screenshot",
    "capture_screen": "perception.screenshot",
    "look_at_screen": "perception.screen_reading",

    # Mouse actions
    "click": "motor.mouse_click",
    "mouse_click": "motor.mouse_click",
    "move_mouse": "motor.mouse_move",
    "mouse_move": "motor.mouse_move",
    "scroll": "motor.scroll",

    # Keyboard actions
    "type": "motor.keyboard_type",
    "keyboard_type": "motor.keyboard_type",
    "type_text": "motor.keyboard_type",
    "hotkey": "motor.keyboard_shortcut",
    "press_key": "motor.keyboard_shortcut",

    # File actions
    "read_file": "perception.file_read",
    "read": "perception.file_read",
    "file_read": "perception.file_read",

    # Memory actions
    "store_memory": "memory.store",
    "write_diary": "memory.store",
    "recall": "memory.recall",
    "read_diary": "memory.recall",
    "search_memory": "memory.search",
    "search": "memory.search",

    # Communication actions
    "send_message": "communication.basic",
    "express_feeling": "embodiment.emotion_sensing",

    # Embodiment actions
    "feel_body": "embodiment.body_awareness",
    "body_sense": "embodiment.body_awareness",

    # Tool actions
    "mcp_call": "tool.mcp_basic",
    "postal_send": "tool.postal_send",
    "postal_route": "tool.postal_send",
    "postal_subscribe": "tool.postal_subscribe",
    "shell_command": "tool.shell_basic",
    "run_shell": "tool.shell_basic",
}


def skill_for_action(action: str) -> Optional[str]:
    """Get the skill ID for a given action."""
    return ACTION_TO_SKILL.get(action.lower())


# ═══════════════════════════════════════════════════════════════════════════════
# SKILL PROFILE - Per-fairy skill tracking
# ═══════════════════════════════════════════════════════════════════════════════

class SkillProfile:
    """Complete skill profile for a fairy."""

    def __init__(self, fairy_name: str):
        self.fairy_name = fairy_name
        self.skills: Dict[str, Skill] = {}
        self.achievements: Dict[str, Achievement] = {}
        self.total_xp: int = 0
        self.title: Optional[str] = None
        self.created_at: float = time.time()

        # Initialize skills from definitions
        for skill_id, (name, category, desc) in SKILL_DEFINITIONS.items():
            self.skills[skill_id] = Skill(
                id=skill_id,
                name=name,
                category=category,
                description=desc
            )

        # Initialize achievements from definitions
        for ach_id, (name, desc, title) in ACHIEVEMENT_DEFINITIONS.items():
            self.achievements[ach_id] = Achievement(
                id=ach_id,
                name=name,
                description=desc,
                title=title
            )

        # Load saved state
        self._load()

    @property
    def level(self) -> int:
        """Overall fairy level from total XP."""
        return level_from_xp(self.total_xp)

    def use_skill(self, skill_id: str, success: bool = True) -> Dict[str, Any]:
        """
        Record using a skill. Awards XP and checks achievements.

        Args:
            skill_id: The skill being used (e.g., "motor.mouse_click")
            success: Whether the skill use succeeded

        Returns:
            Dict with XP gained, level ups, and achievements unlocked
        """
        if skill_id not in self.skills:
            # Try to find by action mapping
            mapped = skill_for_action(skill_id)
            if mapped:
                skill_id = mapped
            else:
                return {"error": f"Unknown skill: {skill_id}"}

        skill = self.skills[skill_id]

        # Calculate XP (more for success, some for attempt)
        base_xp = 10 if success else 3
        # Bonus XP for rarely-used skills
        if skill.times_used < 10:
            base_xp += 5

        result = skill.add_xp(base_xp)
        self.total_xp += base_xp

        # Check for achievements
        unlocked = self._check_achievements(skill_id)
        if unlocked:
            result["achievements_unlocked"] = [a.name for a in unlocked]

        # Save after each use
        self._save()

        return result

    def get_skill(self, skill_id: str) -> Optional[Dict[str, Any]]:
        """Get info about a specific skill."""
        if skill_id in self.skills:
            return self.skills[skill_id].to_dict()
        return None

    def get_skills_by_category(self, category: SkillCategory) -> List[Dict[str, Any]]:
        """Get all skills in a category."""
        return [
            s.to_dict() for s in self.skills.values()
            if s.category == category
        ]

    def get_top_skills(self, n: int = 5) -> List[Dict[str, Any]]:
        """Get top N skills by XP."""
        sorted_skills = sorted(
            self.skills.values(),
            key=lambda s: s.xp,
            reverse=True
        )
        return [s.to_dict() for s in sorted_skills[:n]]

    def get_unlocked_achievements(self) -> List[Dict[str, Any]]:
        """Get all unlocked achievements."""
        return [
            a.to_dict() for a in self.achievements.values()
            if a.unlocked
        ]

    def get_locked_achievements(self) -> List[Dict[str, Any]]:
        """Get all locked achievements."""
        return [
            a.to_dict() for a in self.achievements.values()
            if not a.unlocked
        ]

    def get_available_titles(self) -> List[str]:
        """Get titles available from unlocked achievements."""
        return [
            a.title for a in self.achievements.values()
            if a.unlocked and a.title
        ]

    def set_title(self, title: str):
        """Set displayed title."""
        if title in self.get_available_titles():
            self.title = title
            self._save()

    def get_character_sheet(self) -> Dict[str, Any]:
        """Get full character sheet."""
        return {
            "fairy_name": self.fairy_name,
            "level": self.level,
            "total_xp": self.total_xp,
            "title": self.title or "Apprentice",
            "skills": {s.id: s.to_dict() for s in self.skills.values()},
            "top_skills": self.get_top_skills(5),
            "achievements": {
                "unlocked": len(self.get_unlocked_achievements()),
                "total": len(self.achievements),
                "recent": self.get_unlocked_achievements()[-3:],
            },
            "categories": {
                cat.value: sum(1 for s in self.skills.values()
                              if s.category == cat and s.level > 0)
                for cat in SkillCategory
            },
        }

    def _check_achievements(self, skill_id: str) -> List[Achievement]:
        """Check and unlock any earned achievements."""
        unlocked = []
        skill = self.skills.get(skill_id)
        if not skill:
            return unlocked

        # First-time achievements
        if skill.times_used == 1:
            first_ach_map = {
                "motor.mouse_click": "first_click",
                "perception.screenshot": "first_look",
                "coding.python_syntax": "first_code",
                "communication.basic": "first_words",
                "embodiment.body_awareness": "body_aware",
            }
            if skill_id in first_ach_map:
                ach = self.achievements.get(first_ach_map[skill_id])
                if ach and not ach.unlocked:
                    ach.unlocked = True
                    ach.unlocked_at = time.time()
                    unlocked.append(ach)

        # Level-based achievements
        if skill.level >= 10:
            level_ach_map = {
                SkillCategory.MOTOR: "mouse_master",
                SkillCategory.PERCEPTION: "all_seeing",
                SkillCategory.TOOL_USE: "tool_master",
            }
            if skill.category in level_ach_map:
                ach = self.achievements.get(level_ach_map[skill.category])
                if ach and not ach.unlocked:
                    ach.unlocked = True
                    ach.unlocked_at = time.time()
                    unlocked.append(ach)

        # Count-based achievements
        total_uses = sum(s.times_used for s in self.skills.values())
        if total_uses >= 100:
            ach = self.achievements.get("centurion")
            if ach and not ach.unlocked:
                ach.unlocked = True
                ach.unlocked_at = time.time()
                unlocked.append(ach)

        # File reading achievement
        file_skill = self.skills.get("perception.file_read")
        if file_skill and file_skill.times_used >= 100:
            ach = self.achievements.get("file_devourer")
            if ach and not ach.unlocked:
                ach.unlocked = True
                ach.unlocked_at = time.time()
                unlocked.append(ach)

        # Memory achievement
        store_skill = self.skills.get("memory.store")
        if store_skill and store_skill.times_used >= 100:
            ach = self.achievements.get("elephant")
            if ach and not ach.unlocked:
                ach.unlocked = True
                ach.unlocked_at = time.time()
                unlocked.append(ach)

        # Polymath - level 5 in 5 categories
        cats_at_5 = 0
        for cat in SkillCategory:
            cat_skills = [s for s in self.skills.values() if s.category == cat]
            if any(s.level >= 5 for s in cat_skills):
                cats_at_5 += 1
        if cats_at_5 >= 5:
            ach = self.achievements.get("polymath")
            if ach and not ach.unlocked:
                ach.unlocked = True
                ach.unlocked_at = time.time()
                unlocked.append(ach)

        return unlocked

    def _save(self):
        """Save profile to disk."""
        state_file = STATE_DIR / f"{self.fairy_name}_skills.json"
        data = {
            "fairy_name": self.fairy_name,
            "total_xp": self.total_xp,
            "title": self.title,
            "created_at": self.created_at,
            "saved_at": time.time(),
            "skills": {
                sid: {
                    "xp": s.xp,
                    "times_used": s.times_used,
                    "last_used": s.last_used,
                }
                for sid, s in self.skills.items()
            },
            "achievements": {
                aid: {
                    "unlocked": a.unlocked,
                    "unlocked_at": a.unlocked_at,
                }
                for aid, a in self.achievements.items()
            },
        }
        try:
            with open(state_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"[SkillProfile] Save failed: {e}")

    def _load(self):
        """Load profile from disk."""
        state_file = STATE_DIR / f"{self.fairy_name}_skills.json"
        if not state_file.exists():
            return

        try:
            with open(state_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            self.total_xp = data.get("total_xp", 0)
            self.title = data.get("title")
            self.created_at = data.get("created_at", time.time())

            # Restore skill stats
            for sid, sdata in data.get("skills", {}).items():
                if sid in self.skills:
                    self.skills[sid].xp = sdata.get("xp", 0)
                    self.skills[sid].times_used = sdata.get("times_used", 0)
                    self.skills[sid].last_used = sdata.get("last_used", 0)

            # Restore achievements
            for aid, adata in data.get("achievements", {}).items():
                if aid in self.achievements:
                    self.achievements[aid].unlocked = adata.get("unlocked", False)
                    self.achievements[aid].unlocked_at = adata.get("unlocked_at", 0)

            print(f"[SkillProfile] Loaded {self.fairy_name}: Level {self.level}, {self.total_xp} XP")

        except Exception as e:
            print(f"[SkillProfile] Load failed: {e}")


# ═══════════════════════════════════════════════════════════════════════════════
# PROFILE CACHE - Singleton pattern for profiles
# ═══════════════════════════════════════════════════════════════════════════════

_skill_profiles: Dict[str, SkillProfile] = {}


def get_skill_profile(fairy_name: str) -> SkillProfile:
    """Get or create skill profile for a fairy."""
    if fairy_name not in _skill_profiles:
        _skill_profiles[fairy_name] = SkillProfile(fairy_name)
    return _skill_profiles[fairy_name]


def get_skill_tracker():
    """Get a skill tracker interface for use by other systems."""
    class SkillTracker:
        def get_fairy_profile(self, fairy_name: str) -> SkillProfile:
            return get_skill_profile(fairy_name)

        def track(self, skill_id: str, fairy_name: str = "ClaudeFairy",
                  success: bool = True) -> Dict[str, Any]:
            profile = get_skill_profile(fairy_name)
            return profile.use_skill(skill_id, success)

    return SkillTracker()


# ═══════════════════════════════════════════════════════════════════════════════
# CONVENIENCE FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def track_skill(skill_id: str, fairy_name: str = "ClaudeFairy",
                success: bool = True) -> Dict[str, Any]:
    """Quick function to track a skill use."""
    profile = get_skill_profile(fairy_name)
    return profile.use_skill(skill_id, success)


def check_skill(skill_id: str, fairy_name: str = "ClaudeFairy") -> Optional[Dict[str, Any]]:
    """Quick function to check a skill level."""
    profile = get_skill_profile(fairy_name)
    return profile.get_skill(skill_id)


if __name__ == "__main__":
    # Test the system
    print("Testing Skill System...")

    profile = get_skill_profile("TestFairy")

    # Use some skills
    result = profile.use_skill("motor.mouse_click")
    print(f"Click result: {result}")

    result = profile.use_skill("perception.screenshot")
    print(f"Screenshot result: {result}")

    # Check character sheet
    sheet = profile.get_character_sheet()
    print(f"\nCharacter Sheet:")
    print(f"  Level: {sheet['level']}")
    print(f"  Total XP: {sheet['total_xp']}")
    print(f"  Title: {sheet['title']}")
    print(f"  Top Skills: {sheet['top_skills']}")
    print(f"  Achievements: {sheet['achievements']}")
