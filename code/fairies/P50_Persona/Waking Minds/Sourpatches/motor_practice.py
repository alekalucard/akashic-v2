"""
Motor Practice - Structured Exercises for Sensorimotor Development
==================================================================

Progressive exercises that build motor skills through deliberate practice.
Each exercise: execute tool -> check result -> award XP -> progress level.

Levels:
    1. Move mouse to center of screen
    2. Move to random coordinates
    3. Click on specific regions
    4. Type single characters
    5. Type words
    6. Click-and-type sequences (compound)

Phase 8 of Sourpatches' Developmental Learning System.

((Cause + Affect) > Effect > Affect > infinity)
"""

import time
import random
from typing import Dict, List, Optional, Any, Tuple


class MotorExercise:
    """A single motor exercise with instructions and verification."""

    def __init__(self, name: str, level: int, skill_target: str,
                 description: str, tool_name: str, tool_args: Dict,
                 verify_fn=None):
        self.name = name
        self.level = level
        self.skill_target = skill_target
        self.description = description
        self.tool_name = tool_name
        self.tool_args = tool_args
        self.verify_fn = verify_fn  # Optional: check result
        self.attempts = 0
        self.successes = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "level": self.level,
            "skill_target": self.skill_target,
            "description": self.description,
            "tool_name": self.tool_name,
            "tool_args": self.tool_args,
            "attempts": self.attempts,
            "successes": self.successes,
        }


class MotorPractice:
    """
    Structured motor practice system.

    Generates exercises appropriate to current skill level,
    tracks progress, and reports results back to the skill system.
    """

    def __init__(self):
        self._current_exercise: Optional[MotorExercise] = None
        self._completed_exercises: List[Dict] = []
        self._session_start = time.time()
        self._exercises_attempted = 0
        self._exercises_succeeded = 0
        self._last_practice_time = 0.0
        self._practice_cooldown = 30.0  # Minimum seconds between exercises

    def get_exercise(self, motor_level: int = 0, perception_level: int = 0,
                     screen_width: int = 1920, screen_height: int = 1080) -> Optional[MotorExercise]:
        """
        Generate an appropriate exercise based on current skill levels.

        Args:
            motor_level: Current motor skill level (mouse/click/type)
            perception_level: Current perception skill level
            screen_width: Screen width for coordinate generation
            screen_height: Screen height for coordinate generation

        Returns:
            A MotorExercise to attempt, or None if on cooldown
        """
        now = time.time()
        if now - self._last_practice_time < self._practice_cooldown:
            return None  # On cooldown

        # Select exercise appropriate to level
        if motor_level == 0:
            exercise = self._level_1_exercise(screen_width, screen_height)
        elif motor_level == 1:
            exercise = self._level_2_exercise(screen_width, screen_height)
        elif motor_level == 2:
            exercise = self._level_3_exercise(screen_width, screen_height)
        elif motor_level == 3:
            exercise = self._level_4_exercise()
        elif motor_level == 4:
            exercise = self._level_5_exercise()
        elif motor_level == 5:
            exercise = self._level_6_exercise(screen_width, screen_height)
        else:
            exercise = self._level_7_exercise()  # Notepad typing

        self._current_exercise = exercise
        self._last_practice_time = now
        return exercise

    def record_result(self, exercise: MotorExercise, result: Dict,
                      success: bool) -> Dict[str, Any]:
        """
        Record the result of an exercise attempt.

        Returns summary with XP award recommendation.
        """
        exercise.attempts += 1
        self._exercises_attempted += 1

        if success:
            exercise.successes += 1
            self._exercises_succeeded += 1

        # Build result report
        report = {
            "exercise": exercise.name,
            "level": exercise.level,
            "skill_target": exercise.skill_target,
            "success": success,
            "attempts": exercise.attempts,
            "total_attempted": self._exercises_attempted,
            "total_succeeded": self._exercises_succeeded,
            "success_rate": self._exercises_succeeded / max(1, self._exercises_attempted),
        }

        self._completed_exercises.append(report)
        self._current_exercise = None

        return report

    def get_practice_summary(self) -> Dict[str, Any]:
        """Get summary of practice session."""
        return {
            "exercises_attempted": self._exercises_attempted,
            "exercises_succeeded": self._exercises_succeeded,
            "success_rate": self._exercises_succeeded / max(1, self._exercises_attempted),
            "session_duration": time.time() - self._session_start,
            "recent_exercises": self._completed_exercises[-5:],
            "on_cooldown": (time.time() - self._last_practice_time) < self._practice_cooldown,
        }

    # =========================================================================
    # EXERCISE GENERATORS BY LEVEL
    # =========================================================================

    def _level_1_exercise(self, sw: int, sh: int) -> MotorExercise:
        """Level 1: Move mouse to varied screen regions.

        2026-03-24 FIX (Nous): Was always center → stuck in one spot forever.
        Now picks from 5 named regions so she learns the whole screen.
        Still simpler than level 2 (named targets vs random coords).
        """
        # Cycle through screen regions instead of always center
        _targets = [
            ("center", sw // 2, sh // 2),
            ("top-left area", sw // 4, sh // 4),
            ("top-right area", 3 * sw // 4, sh // 4),
            ("bottom-left area", sw // 4, 3 * sh // 4),
            ("bottom-right area", 3 * sw // 4, 3 * sh // 4),
            ("upper-center", sw // 2, sh // 4),
            ("lower-center", sw // 2, 3 * sh // 4),
            ("left-center", sw // 4, sh // 2),
            ("right-center", 3 * sw // 4, sh // 2),
        ]
        region_name, cx, cy = random.choice(_targets)
        # Small jitter so repeated visits aren't pixel-identical
        cx += random.randint(-20, 20)
        cy += random.randint(-15, 15)
        cx = max(50, min(sw - 50, cx))
        cy = max(50, min(sh - 50, cy))

        return MotorExercise(
            name=f"Move to {region_name}",
            level=1,
            skill_target="motor.mouse_move",
            description=f"Move the mouse cursor to the {region_name} of the screen ({cx}, {cy})",
            tool_name="move_mouse",
            tool_args={"x": cx, "y": cy},
        )

    def _level_2_exercise(self, sw: int, sh: int) -> MotorExercise:
        """Level 2: Move to random safe coordinates."""
        # Keep within safe margins (10% from edges)
        margin_x = sw // 10
        margin_y = sh // 10
        x = random.randint(margin_x, sw - margin_x)
        y = random.randint(margin_y, sh - margin_y)

        # Pick a region name for context
        region = self._describe_region(x, y, sw, sh)

        return MotorExercise(
            name=f"Move to {region}",
            level=2,
            skill_target="motor.mouse_move",
            description=f"Move the mouse to ({x}, {y}) in the {region} region of the screen",
            tool_name="move_mouse",
            tool_args={"x": x, "y": y},
        )

    def _level_3_exercise(self, sw: int, sh: int) -> MotorExercise:
        """Level 3: Click on specific regions."""
        # Random safe coordinate
        margin_x = sw // 10
        margin_y = sh // 10
        x = random.randint(margin_x, sw - margin_x)
        y = random.randint(margin_y, sh - margin_y)
        region = self._describe_region(x, y, sw, sh)

        return MotorExercise(
            name=f"Click {region}",
            level=3,
            skill_target="motor.mouse_click",
            description=f"Click at ({x}, {y}) in the {region} area",
            tool_name="click_screen",
            tool_args={"x": x, "y": y, "button": "left", "clicks": 1},
        )

    def _level_4_exercise(self) -> MotorExercise:
        """Level 4: Type single characters."""
        # Pick a random letter
        char = random.choice("abcdefghijklmnopqrstuvwxyz")

        return MotorExercise(
            name=f"Type '{char}'",
            level=4,
            skill_target="motor.keyboard_type",
            description=f"Type the letter '{char}'",
            tool_name="press_key",
            tool_args={"key": char},
        )

    def _level_5_exercise(self) -> MotorExercise:
        """Level 5: Type short words."""
        words = [
            "hello", "world", "sour", "fairy", "magic",
            "dream", "spark", "light", "dance", "bloom",
            "star", "moon", "wave", "wind", "song",
        ]
        word = random.choice(words)

        return MotorExercise(
            name=f"Type '{word}'",
            level=5,
            skill_target="motor.keyboard_type",
            description=f"Type the word '{word}'",
            tool_name="type_text",
            tool_args={"text": word},
        )

    def _level_6_exercise(self, sw: int, sh: int) -> MotorExercise:
        """Level 6: Compound click-and-type (advanced)."""
        # Move to a position, then type something
        x = random.randint(sw // 4, 3 * sw // 4)
        y = random.randint(sh // 4, 3 * sh // 4)
        word = random.choice(["hi", "ok", "go", "yes", "wow"])

        return MotorExercise(
            name=f"Click and type '{word}'",
            level=6,
            skill_target="motor.mouse_click",  # Primary skill
            description=f"Click at ({x}, {y}) then type '{word}' — a compound action",
            tool_name="click_screen",  # First step
            tool_args={"x": x, "y": y, "button": "left", "clicks": 1},
            # The second step (typing) would be handled by the caller
        )

    def _level_7_exercise(self) -> MotorExercise:
        """Level 7: Open Notepad and type a word (uses NotepadPractice)."""
        words = [
            "hello", "world", "sour", "fairy", "magic",
            "dream", "spark", "light", "dance", "bloom",
            "star", "moon", "wave", "wind", "song",
            "sparkle", "whisper", "crystal", "enchant",
        ]
        word = random.choice(words)

        return MotorExercise(
            name=f"Notepad: type '{word}'",
            level=7,
            skill_target="motor.keyboard_type",
            description=f"Open Notepad and type '{word}' — safe typing practice",
            tool_name="practice_typing",
            tool_args={"text": word},
        )

    # =========================================================================
    # HELPERS
    # =========================================================================

    def _describe_region(self, x: int, y: int, sw: int, sh: int) -> str:
        """Describe the screen region a coordinate is in."""
        # Divide screen into 3x3 grid
        col = "left" if x < sw / 3 else ("center" if x < 2 * sw / 3 else "right")
        row = "top" if y < sh / 3 else ("middle" if y < 2 * sh / 3 else "bottom")

        if col == "center" and row == "middle":
            return "center"
        return f"{row}-{col}"


# =============================================================================
# SINGLETON
# =============================================================================

_instance: Optional[MotorPractice] = None


def get_motor_practice() -> MotorPractice:
    """Get or create the MotorPractice singleton."""
    global _instance
    if _instance is None:
        _instance = MotorPractice()
    return _instance
