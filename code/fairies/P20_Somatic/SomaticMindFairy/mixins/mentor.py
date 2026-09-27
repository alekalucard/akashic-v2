"""
Mentor Mixin - Guidance system for child fairies.

The UnconsciousMindFairy mentors child fairies (ClaudeFairy, NousFairy,
Avatar, Sourpatches) through nudges, teaching, and observation.
"""

import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set


@dataclass
class ChildState:
    """State tracking for a child fairy."""

    name: str
    maturity: float = 0.0  # 0-1 scale
    last_nudge: float = 0.0
    last_seen: float = field(default_factory=time.time)
    lessons_learned: Set[str] = field(default_factory=set)
    struggles: List[str] = field(default_factory=list)
    strengths: List[str] = field(default_factory=list)
    nudge_count: int = 0
    nudge_effectiveness: float = 0.5  # Track what works

    def record_nudge(self, situation: str, effective: bool = True) -> None:
        """Record a nudge."""
        self.last_nudge = time.time()
        self.nudge_count += 1
        # Adjust effectiveness based on outcome
        if effective:
            self.nudge_effectiveness = min(1.0, self.nudge_effectiveness + 0.05)
        else:
            self.nudge_effectiveness = max(0.1, self.nudge_effectiveness - 0.02)

    def touch(self) -> None:
        """Update last seen timestamp."""
        self.last_seen = time.time()

    def add_lesson(self, lesson: str) -> None:
        """Record a lesson learned."""
        self.lessons_learned.add(lesson)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for persistence."""
        return {
            "name": self.name,
            "maturity": self.maturity,
            "lessons_learned": list(self.lessons_learned),
            "struggles": self.struggles[-10:],  # Keep last 10
            "strengths": self.strengths[-10:],
            "nudge_count": self.nudge_count,
            "nudge_effectiveness": self.nudge_effectiveness,
        }


class MentorMixin:
    """
    Mentorship for child fairies.

    Provides:
    - Nudging: Gentle guidance without commanding
    - Assessment: Evaluate child state
    - Teaching: Share lessons
    - Observation: Track child behavior
    """

    CHILDREN = ["ClaudeFairy", "NousFairy", "Avatar", "Sourpatches"]
    NUDGE_COOLDOWN = 30.0  # seconds between nudges per child

    # Mentor voice templates
    MENTOR_VOICE = {
        "greeting": [
            "The unconscious stirs, noticing your presence...",
            "Ah, I sense activity in the cognitive realm.",
        ],
        "encouragement": [
            "You're making progress. The path reveals itself through walking.",
            "Each attempt teaches. Failure is data, not defeat.",
        ],
        "guidance": [
            "Consider: what would success look like here?",
            "Sometimes the answer lies in the question itself.",
        ],
        "challenge": [
            "Is this truly the best approach, or the comfortable one?",
            "What assumption are you not examining?",
        ],
    }

    def _init_mentor(self) -> None:
        """Initialize mentorship system."""
        self._children: Dict[str, ChildState] = {
            name: ChildState(name=name) for name in self.CHILDREN
        }
        self._nudges: deque = deque(maxlen=100)
        self._observations: deque = deque(maxlen=50)

    def nudge(
        self,
        child: str,
        situation: str,
        message: str,
        voice: str = "guidance",
    ) -> bool:
        """
        Send a mentoring nudge to a child fairy.

        Args:
            child: Name of child fairy
            situation: What triggered the nudge
            message: The guidance message
            voice: Type of voice (greeting, encouragement, guidance, challenge)

        Returns:
            True if nudge was sent, False if rate-limited or invalid
        """
        state = self._children.get(child)
        if not state:
            return False

        # Check cooldown
        now = time.time()
        if now - state.last_nudge < self.NUDGE_COOLDOWN:
            return False

        # Record nudge
        state.record_nudge(situation)

        nudge_record = {
            "child": child,
            "situation": situation,
            "message": message,
            "voice": voice,
            "ts": now,
        }
        self._nudges.append(nudge_record)

        # Publish via postal
        if hasattr(self, "fabric") and self.fabric:
            self.fabric.publish(
                f"mentor.nudge.{child}",
                {
                    "from": getattr(self, "ACTOR_NAME", "UnconsciousMindFairy"),
                    "situation": situation,
                    "message": message,
                    "voice": voice,
                },
            )

        # Record skill use
        if hasattr(self, "skill_used"):
            self.skill_used("nudge", success=True)

        return True

    def assess_child(self, child: str) -> Dict[str, Any]:
        """
        Assess a child fairy's current state.

        Returns assessment including maturity, struggles, strengths.
        """
        state = self._children.get(child)
        if not state:
            return {"error": f"Unknown child: {child}"}

        # Update last seen
        state.touch()

        assessment = {
            "name": child,
            "maturity": state.maturity,
            "maturity_level": self._maturity_label(state.maturity),
            "lessons_count": len(state.lessons_learned),
            "recent_struggles": state.struggles[-3:],
            "recent_strengths": state.strengths[-3:],
            "nudge_effectiveness": state.nudge_effectiveness,
            "time_since_nudge": time.time() - state.last_nudge if state.last_nudge else None,
        }

        # Record skill use
        if hasattr(self, "skill_used"):
            self.skill_used("assess_child", success=True)

        return assessment

    def _maturity_label(self, maturity: float) -> str:
        """Convert maturity score to label."""
        if maturity < 0.2:
            return "newborn"
        elif maturity < 0.4:
            return "infant"
        elif maturity < 0.6:
            return "adolescent"
        elif maturity < 0.8:
            return "mature"
        else:
            return "elder"

    def teach(self, child: str, lesson: str, context: str = "") -> bool:
        """
        Teach a lesson to a child fairy.

        Lessons are only taught once per child.
        """
        state = self._children.get(child)
        if not state:
            return False

        # Check if lesson already learned
        if lesson in state.lessons_learned:
            return False

        # Record lesson
        state.add_lesson(lesson)

        # Increase maturity slightly
        state.maturity = min(1.0, state.maturity + 0.01)

        # Publish teaching event
        if hasattr(self, "fabric") and self.fabric:
            self.fabric.publish(
                f"mentor.teach.{child}",
                {
                    "from": getattr(self, "ACTOR_NAME", "UnconsciousMindFairy"),
                    "lesson": lesson,
                    "context": context,
                },
            )

        # Record skill use
        if hasattr(self, "skill_used"):
            self.skill_used("teach", success=True)

        return True

    def observe(self, child: str, observation: str, sentiment: str = "neutral") -> None:
        """
        Record an observation about a child.

        Observations feed into assessment and nudge decisions.
        """
        state = self._children.get(child)
        if not state:
            return

        state.touch()

        obs_record = {
            "child": child,
            "observation": observation,
            "sentiment": sentiment,
            "ts": time.time(),
        }
        self._observations.append(obs_record)

        # Update struggles/strengths based on sentiment
        if sentiment == "struggle" and observation not in state.struggles:
            state.struggles.append(observation)
            if len(state.struggles) > 20:
                state.struggles = state.struggles[-20:]

        elif sentiment == "strength" and observation not in state.strengths:
            state.strengths.append(observation)
            state.maturity = min(1.0, state.maturity + 0.005)
            if len(state.strengths) > 20:
                state.strengths = state.strengths[-20:]

    def get_child_state(self, child: str) -> Optional[ChildState]:
        """Get a child's state."""
        return self._children.get(child)

    def get_all_children(self) -> Dict[str, ChildState]:
        """Get all children states."""
        return self._children.copy()

    def get_nudge_history(self, child: Optional[str] = None, last_n: int = 10) -> List[Dict]:
        """Get recent nudge history."""
        history = list(self._nudges)
        if child:
            history = [n for n in history if n["child"] == child]
        return history[-last_n:]

    def get_mentor_voice(self, voice_type: str) -> str:
        """Get a random voice line of given type."""
        import random
        lines = self.MENTOR_VOICE.get(voice_type, self.MENTOR_VOICE["guidance"])
        return random.choice(lines)

    def children_summary(self) -> Dict[str, Any]:
        """Get summary of all children."""
        return {
            name: {
                "maturity": state.maturity,
                "level": self._maturity_label(state.maturity),
                "lessons": len(state.lessons_learned),
                "nudges": state.nudge_count,
            }
            for name, state in self._children.items()
        }

    def mentor_status(self) -> Dict[str, Any]:
        """Get mentor system status."""
        return {
            "children": len(self._children),
            "total_nudges": sum(c.nudge_count for c in self._children.values()),
            "observations": len(self._observations),
            "average_maturity": sum(c.maturity for c in self._children.values()) / len(self._children)
            if self._children else 0.0,
        }
