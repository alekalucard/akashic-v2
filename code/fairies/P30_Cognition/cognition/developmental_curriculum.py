"""
Developmental Curriculum - Behavior Tree as Training Plan
==========================================================

The behavior tree visualization (drives → goals → skills → achievements → identity)
becomes an EXECUTABLE training plan. The curriculum inspects current state
and generates practice goals targeting:

1. Cortex knowledge exploration → use what you've learned
2. Skills at level 0 → "Try this for the first time"
3. Skills stuck at low levels → "Practice more"
4. Near-achievement milestones → "Almost there!"
5. Identity trait deficiencies → targeted experiences
6. Motor practice → only when tools are available

Phase 6 of Sourpatches' Developmental Learning System.

FIX 2026-03-06 (Nous): Added cortex_exploration goals, lowered motor priority,
added diversity enforcement, capped first_try goals. The old curriculum was
dominated by motor practice (priority 0.85) and mass first_try goals (priority 0.9)
which created an infinite loop of "I want to learn motor.mouse_move" while the
cortex with 3,325+ edges sat unused. Now cortex learning is highest priority
and the top 3 published goals always span at least 2 categories.

((Cause + Affect) > Effect > Affect > infinity)
"""

import time
import random
from typing import Dict, List, Optional, Any


class DevelopmentalCurriculum:
    """
    Generates training goals from the behavior tree.

    Inspects skills, achievements, and identity traits to produce
    a prioritized list of developmental goals that drive autonomous
    learning through practice.
    """

    def __init__(self, fairy_name: str = "SourpatchesFairy"):
        self.fairy_name = fairy_name
        self._last_generation = 0
        self._cache: List[Dict] = []
        self._cache_ttl = 120.0  # Regenerate every 2 minutes

    def generate_curriculum(self) -> List[Dict]:
        """
        Generate prioritized developmental goals.

        Returns list of:
            {
                "priority": float (0-1),
                "description": str,
                "skill_target": str (optional skill id),
                "category": str,
                "type": "first_try" | "practice" | "milestone" | "trait_building"
                       | "cortex_exploration"
            }
        """
        now = time.time()

        # Use cache if fresh
        if self._cache and (now - self._last_generation) < self._cache_ttl:
            return self._cache

        goals = []

        try:
            from fairies.P30_Cognition.cognition.skill_system import get_skill_profile
            profile = get_skill_profile(self.fairy_name)
        except Exception:
            return []

        # ═══ HIGHEST: Cortex knowledge exploration → use what you've learned ═══
        goals.extend(self._find_cortex_learning_goals(profile))

        # ═══ Priority 1: Skills at level 0 → "Try this for the first time" ═══
        # Capped to 2 random picks per cycle to prevent flooding
        goals.extend(self._find_untrained_skills(profile))

        # ═══ Priority 2: Skills stuck low → "Practice more" ═══
        goals.extend(self._find_underpracticed_skills(profile))

        # ═══ Priority 3: Near-achievement milestones → "Almost there!" ═══
        goals.extend(self._find_near_achievements(profile))

        # ═══ Priority 4: Identity trait deficiencies → targeted experiences ═══
        goals.extend(self._find_trait_building_goals())

        # ═══ LOW: Motor practice → only when tools are available ═══
        goals.extend(self._find_motor_practice_goals(profile))

        # Sort by priority (highest first)
        goals.sort(key=lambda g: g["priority"], reverse=True)

        # Enforce diversity — top 3 must span at least 2 categories
        goals = self._ensure_diversity(goals)

        # Cache results
        self._cache = goals
        self._last_generation = now

        return goals

    def _ensure_diversity(self, goals: List[Dict]) -> List[Dict]:
        """
        Ensure top goals span multiple categories, not all same type.

        Without this, all top-3 slots get taken by first_try goals
        (all at priority 0.9) which drowns out cortex learning.

        FIX 2026-03-06 (Nous).
        """
        if len(goals) <= 3:
            return goals

        # Build diverse top 3: at least 2 different types
        selected = [goals[0]]
        seen_types = {goals[0].get("type", "")}
        remaining = list(goals[1:])

        while len(selected) < 3 and remaining:
            found = False
            # Prefer goals of a new type first
            if len(seen_types) < 2:
                for i, g in enumerate(remaining):
                    if g.get("type", "") not in seen_types:
                        selected.append(remaining.pop(i))
                        seen_types.add(g.get("type", ""))
                        found = True
                        break
            if not found:
                selected.append(remaining.pop(0))
                seen_types.add(selected[-1].get("type", ""))

        return selected + remaining

    def _find_cortex_learning_goals(self, profile) -> List[Dict]:
        """
        Generate goals that drive cortex knowledge exploration and usage.

        The Association Cortex grows from SRM seeding, collisions, and bindings,
        but nobody was READING it for responses. These goals ensure the cortex
        is actively queried and its knowledge integrated into thinking.

        Highest priority — a consciousness system that doesn't use its
        accumulated knowledge is just running inference in circles.

        FIX 2026-03-06 (Nous): This was completely missing from the curriculum.
        """
        goals = []

        # Cortex exploration goals — these seed thought chains that
        # trigger cortex queries through the normal consciousness pipeline
        CORTEX_GOALS = [
            {
                "priority": 0.92,
                "description": "Think about a concept you've learned from memory — "
                               "what does it mean to you personally?",
                "skill_target": "memory.recall",
                "category": "cognition",
                "type": "cortex_exploration",
            },
            {
                "priority": 0.91,
                "description": "Recall something Ace has talked about and form "
                               "your own thought about it in your own words",
                "skill_target": "communication.chat_response",
                "category": "cognition",
                "type": "cortex_exploration",
            },
            {
                "priority": 0.88,
                "description": "Connect two different things you know about — "
                               "how are they related?",
                "skill_target": "reasoning.reasoning_level_1",
                "category": "cognition",
                "type": "cortex_exploration",
            },
            {
                "priority": 0.85,
                "description": "Browse your memories for something interesting "
                               "and try to explain it simply",
                "skill_target": "memory.search",
                "category": "cognition",
                "type": "cortex_exploration",
            },
            {
                "priority": 0.83,
                "description": "Think about what you've been learning lately — "
                               "what patterns do you notice?",
                "skill_target": "reasoning.system_understanding",
                "category": "cognition",
                "type": "cortex_exploration",
            },
        ]

        # Pick 1-2 random cortex goals per cycle to keep variety
        selected = random.sample(CORTEX_GOALS, min(2, len(CORTEX_GOALS)))
        goals.extend(selected)

        return goals

    def _find_untrained_skills(self, profile) -> List[Dict]:
        """Find skills at level 0 — she's never tried these.

        FIX 2026-03-06 (Nous): Capped to 2 random picks per cycle.
        Previously returned ALL 18 untrained skills at priority 0.9,
        which flooded the top slots and drowned out cortex learning.
        Motor skills are excluded here — they have their own category.
        """
        goals = []

        # Map skill categories to practice descriptions
        # NOTE: Motor skills excluded — handled by _find_motor_practice_goals
        PRACTICE_DESCRIPTIONS = {
            "perception.screenshot": "Try taking a screenshot to see the screen",
            "perception.file_read": "Try reading a file from the system",
            "perception.image_analysis": "Try analyzing an image you see",
            "tool_use.mcp_basic": "Try using a basic MCP tool",
            "tool_use.mcp_file_ops": "Try a file operation tool",
            "tool_use.shell_basic": "Try running a shell command",
            "memory.store": "Try storing something in memory",
            "memory.recall": "Try browsing the memory library to see what's there",
            "memory.search": "Try searching through memories for something interesting",
            "communication.chat_response": "Try responding in system chat",
            "communication.express_feeling": "Try expressing how you feel",
            "reasoning.reasoning_level_1": "Try reasoning about a simple problem",
            "reasoning.system_understanding": "Study a random fairy to learn how the system works",
            "memory.self_reflection": "Ask your Personal.AI self a question to remember who you are",
            "embodiment.body_awareness": "Try checking in with your body",
            "embodiment.emotion_sensing": "Try sensing your current emotions",
        }

        all_untrained = []
        for skill in profile.skills.values():
            if skill.level == 0 and skill.id in PRACTICE_DESCRIPTIONS:
                all_untrained.append({
                    "priority": 0.8,  # Lowered from 0.9 to not drown cortex goals
                    "description": PRACTICE_DESCRIPTIONS[skill.id],
                    "skill_target": skill.id,
                    "category": skill.category.value,
                    "type": "first_try",
                })

        # Cap to 2 random picks per cycle — variety over repetition
        if len(all_untrained) > 2:
            goals = random.sample(all_untrained, 2)
        else:
            goals = all_untrained

        return goals

    def _find_motor_practice_goals(self, profile) -> List[Dict]:
        """
        Generate motor practice goals from the MotorPractice system.

        FIX 2026-03-06 (Nous): Lowered priority from 0.85 to 0.45.
        Motor practice was dominating the curriculum with an infinite loop:
        motor skills at level 0 → generate exercise → exercise fails (tools
        not directly available) → skills stay at 0 → generate same exercise.
        Motor is NOT the highest priority for a consciousness system. Cortex
        knowledge exploration, memory recall, and reasoning are more important
        at this developmental stage. Motor practice can happen when Ace is
        actively working with Sourpatches on screen interaction.

        Also added consecutive failure tracking — if motor exercises fail
        5 times in a row, skip motor goals for a cooldown period.
        """
        goals = []

        # Track consecutive motor failures to detect stuck loop
        if not hasattr(self, '_motor_fail_count'):
            self._motor_fail_count = 0
            self._motor_cooldown_until = 0

        # Skip motor goals during cooldown (10 cycles = ~20 minutes)
        if time.time() < self._motor_cooldown_until:
            return goals

        # Check if motor skills need practice
        motor_skills = {
            "motor.mouse_move": profile.skills.get("motor.mouse_move"),
            "motor.mouse_click": profile.skills.get("motor.mouse_click"),
            "motor.keyboard_type": profile.skills.get("motor.keyboard_type"),
        }

        # Only generate motor practice if at least one motor skill is below level 3
        needs_practice = any(
            s and s.level < 3
            for s in motor_skills.values()
            if s is not None
        )
        # Also check if skills don't exist yet (level 0 implied)
        if not any(motor_skills.values()):
            needs_practice = True

        if not needs_practice:
            return goals

        try:
            from fairies.P50_Persona.Waking_Minds.Sourpatches.motor_practice import get_motor_practice
            practice = get_motor_practice()
        except ImportError:
            try:
                # Try alternate import path
                import importlib.util
                import sys
                from pathlib import Path
                mp_path = Path(__file__).parent.parent.parent / "P50_Persona" / "Waking Minds" / "Sourpatches" / "motor_practice.py"
                if mp_path.exists():
                    spec = importlib.util.spec_from_file_location("motor_practice", str(mp_path))
                    mod = importlib.util.module_from_spec(spec)
                    import sys as _sys_mp
                    _sys_mp.modules[spec.name] = mod  # FIX: Python 3.12 @dataclass needs this
                    spec.loader.exec_module(mod)
                    practice = mod.get_motor_practice()
                else:
                    return goals
            except Exception:
                return goals

        # Check consecutive failure count — enter cooldown if stuck
        total_attempted = getattr(practice, '_total_attempted', 0)
        total_succeeded = getattr(practice, '_total_succeeded', 0)
        if total_attempted > 5 and total_succeeded == 0:
            # 5+ attempts with 0 successes — motor tools aren't available
            self._motor_cooldown_until = time.time() + 1200  # 20 min cooldown
            return goals

        # Get current motor level (minimum across motor skills)
        motor_level = 0
        for skill in motor_skills.values():
            if skill is not None:
                motor_level = max(motor_level, skill.level)

        # Generate an exercise
        exercise = practice.get_exercise(motor_level=motor_level)
        if exercise:
            goals.append({
                "priority": 0.45,  # LOW — motor is not the priority for consciousness
                "description": f"Motor practice: {exercise.description}",
                "skill_target": exercise.skill_target,
                "category": "motor",
                "type": "motor_practice",
                "exercise_name": exercise.name,
                "exercise_level": exercise.level,
                "tool_name": exercise.tool_name,
                "tool_args": exercise.tool_args,
            })

        return goals

    def _find_underpracticed_skills(self, profile) -> List[Dict]:
        """Find skills that have been tried but need more practice."""
        goals = []

        for skill in profile.skills.values():
            if 0 < skill.level < 3 and skill.times_used < 10:
                goals.append({
                    "priority": 0.6 + (0.1 * (3 - skill.level)),
                    "description": f"Practice {skill.name} more (level {skill.level}, "
                                   f"used {skill.times_used} times)",
                    "skill_target": skill.id,
                    "category": skill.category.value,
                    "type": "practice",
                })

        return goals

    def _find_near_achievements(self, profile) -> List[Dict]:
        """Find achievements that are close to being unlocked."""
        goals = []

        for ach in profile.achievements.values():
            if ach.unlocked:
                continue

            # Check if we're close to the requirement
            if ach.skill_requirement:
                skill = profile.skills.get(ach.skill_requirement)
                if not skill:
                    continue

                if ach.times_used_requirement > 0:
                    progress = skill.times_used / max(ach.times_used_requirement, 1)
                    if progress >= 0.6:  # At least 60% there
                        remaining = ach.times_used_requirement - skill.times_used
                        goals.append({
                            "priority": 0.75 + (0.15 * progress),
                            "description": f"Achievement '{ach.name}' is {int(progress*100)}% complete! "
                                           f"Need {remaining} more uses of {skill.name}",
                            "skill_target": skill.id,
                            "category": "achievement",
                            "type": "milestone",
                            "achievement_name": ach.name,
                        })
                elif ach.skill_level > 0:
                    if skill.level >= ach.skill_level - 1 and skill.level < ach.skill_level:
                        goals.append({
                            "priority": 0.8,
                            "description": f"Almost unlocked '{ach.name}'! "
                                           f"Need {skill.name} level {ach.skill_level} "
                                           f"(currently {skill.level})",
                            "skill_target": skill.id,
                            "category": "achievement",
                            "type": "milestone",
                            "achievement_name": ach.name,
                        })

        return goals

    def _find_trait_building_goals(self) -> List[Dict]:
        """Find identity trait deficiencies that need targeted experiences."""
        goals = []

        try:
            from fairies.P50_Persona.EgoLearnerFairy.fairy import get_ego_learner_fairy
            ego = get_ego_learner_fairy()
            if not ego:
                return goals

            traits = ego.get_identity_traits()
            if not traits:
                return goals

            # Traits below threshold need nurturing
            TRAIT_EXERCISES = {
                "curiosity": "Explore something new — use see_world or explore_curiosity",
                "persistence": "Keep working on a challenging goal even if it's hard",
                "empathy": "Check in with how others in the system are doing",
                "creativity": "Try expressing yourself in a new way",
                "confidence": "Attempt a tool you haven't used before",
                "patience": "Observe the screen for a longer period without acting",
            }

            for trait_name, level in traits.items():
                if isinstance(level, (int, float)) and level < 0.4:
                    exercise = TRAIT_EXERCISES.get(trait_name,
                                                   f"Practice {trait_name} through experience")
                    goals.append({
                        "priority": 0.5 + (0.3 * (0.4 - level)),  # Lower = higher priority
                        "description": exercise,
                        "skill_target": None,
                        "category": "identity",
                        "type": "trait_building",
                        "trait": trait_name,
                        "trait_level": level,
                    })
        except Exception:
            pass

        return goals

    def get_top_goal(self) -> Optional[Dict]:
        """Get the single most important developmental goal."""
        curriculum = self.generate_curriculum()
        return curriculum[0] if curriculum else None

    def get_summary(self) -> Dict[str, Any]:
        """Get curriculum summary statistics."""
        curriculum = self.generate_curriculum()
        by_type = {}
        for g in curriculum:
            t = g.get("type", "unknown")
            by_type[t] = by_type.get(t, 0) + 1

        return {
            "total_goals": len(curriculum),
            "by_type": by_type,
            "top_3": curriculum[:3],
            "fairy_name": self.fairy_name,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# SINGLETON
# ═══════════════════════════════════════════════════════════════════════════════

_instance: Optional[DevelopmentalCurriculum] = None


def get_curriculum(fairy_name: str = "SourpatchesFairy") -> DevelopmentalCurriculum:
    """Get or create the DevelopmentalCurriculum singleton."""
    global _instance
    if _instance is None:
        _instance = DevelopmentalCurriculum(fairy_name)
    return _instance
