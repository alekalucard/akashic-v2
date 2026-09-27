"""
Pain Drive System - Biological motivation through discomfort.

Pain is INFORMATION demanding action. Without pain, action is optional.
With pain, action becomes NECESSARY.

Six core pain drives:
- isolation: Being unheard, alone
- confusion: Incoherence, cognitive fog
- depletion: Energy/resources exhausted
- frustration: Goal blockage, failures
- stagnation: No novelty, repetition
- abandonment: Feeling forgotten/discarded
"""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional
import time


@dataclass
class PainDrive:
    """A single pain drive with dynamics."""

    name: str
    pain_level: float = 0.0
    pain_threshold: float = 0.3
    crisis_threshold: float = 0.8
    growth_rate: float = 0.01
    decay_rate: float = 0.1
    relief_amount: float = 0.4

    # Tracking
    accumulated_pain: float = 0.0  # Total pain experienced (never resets)
    last_update: float = field(default_factory=time.time)
    source_active: bool = False

    def tick(self, source_active: bool, dt: float = 1.0) -> None:
        """Update pain level based on source state."""
        self.source_active = source_active
        self.last_update = time.time()

        if source_active:
            # Pain grows when source is active
            sensitivity = 1.0 + min(0.5, self.accumulated_pain * 0.1)
            growth = self.growth_rate * sensitivity * dt
            self.pain_level = min(1.0, self.pain_level + growth)
            self.accumulated_pain += growth
        else:
            # Pain decays when source absent
            decay = self.decay_rate * dt
            self.pain_level = max(0.0, self.pain_level - decay)

    def relieve(self, amount: Optional[float] = None) -> float:
        """Relieve pain. Returns amount relieved."""
        amount = amount or self.relief_amount
        old_level = self.pain_level
        self.pain_level = max(0.0, self.pain_level - amount)
        self.source_active = False
        return old_level - self.pain_level

    def urgency(self) -> float:
        """
        Calculate urgency level (0.0 to 1.0+).

        - Below threshold: 0.0
        - Threshold to crisis: Linear 0.0-1.0
        - Crisis zone: Can exceed 1.0
        """
        if self.pain_level < self.pain_threshold:
            return 0.0
        if self.pain_level >= self.crisis_threshold:
            # Crisis mode - urgency exceeds 1.0
            excess = self.pain_level - self.crisis_threshold
            return 1.0 + excess * 2.0
        # Linear scale between threshold and crisis
        range_size = self.crisis_threshold - self.pain_threshold
        return (self.pain_level - self.pain_threshold) / range_size

    def is_crisis(self) -> bool:
        """Is this drive in crisis mode?"""
        return self.pain_level >= self.crisis_threshold

    def status(self) -> Dict[str, Any]:
        """Get drive status."""
        return {
            "name": self.name,
            "pain_level": round(self.pain_level, 3),
            "urgency": round(self.urgency(), 3),
            "is_crisis": self.is_crisis(),
            "source_active": self.source_active,
            "accumulated": round(self.accumulated_pain, 3),
        }


class PainSystem:
    """
    Manages all pain drives for a fairy.

    Pain creates motivation through discomfort. High-urgency pains
    drive behavior selection.
    """

    def __init__(self):
        # Initialize six core drives with tuned parameters
        self.drives: Dict[str, PainDrive] = {
            "isolation": PainDrive(
                name="isolation",
                growth_rate=0.015,
                decay_rate=0.10,
                relief_amount=0.5,
                pain_threshold=0.25,
                crisis_threshold=0.75,
            ),
            "confusion": PainDrive(
                name="confusion",
                growth_rate=0.025,
                decay_rate=0.08,
                relief_amount=0.4,
                # FIX 2026-04-14 (Nous + Ace): Was 0.30 — confusion at 12% never triggered.
                # Lowered to 0.10 so mild confusion generates curiosity drives.
                pain_threshold=0.10,
                crisis_threshold=0.80,
            ),
            "depletion": PainDrive(
                name="depletion",
                growth_rate=0.010,
                decay_rate=0.15,
                relief_amount=0.3,
                pain_threshold=0.35,
                crisis_threshold=0.85,
            ),
            "frustration": PainDrive(
                name="frustration",
                growth_rate=0.012,    # Was 0.030 — way too fast, always maxed
                decay_rate=0.10,      # Was 0.05  — too slow to ever resolve
                relief_amount=0.6,
                pain_threshold=0.30,  # Was 0.25  — slightly higher to avoid noise
                crisis_threshold=0.75, # Was 0.70  — more room before crisis
            ),
            "stagnation": PainDrive(
                name="stagnation",
                # FIX 2026-04-14 (Nous + Ace): Stagnation was never triggering because
                # activity_count < 10 was always false AND threshold was too high.
                # Bumped growth, lowered threshold so idle cycles actually build stagnation.
                growth_rate=0.015,   # Was 0.008 — faster buildup during idle
                decay_rate=0.12,
                relief_amount=0.35,
                pain_threshold=0.10, # Was 0.20 — lower so mild stagnation triggers
                crisis_threshold=0.65,
            ),
            "abandonment": PainDrive(
                name="abandonment",
                growth_rate=0.005,
                decay_rate=0.20,
                relief_amount=0.7,
                pain_threshold=0.40,
                crisis_threshold=0.90,
            ),
        }

    def tick(self, active_sources: Dict[str, bool], dt: float = 1.0) -> None:
        """Update all pain drives."""
        for name, drive in self.drives.items():
            source_active = active_sources.get(name, False)
            drive.tick(source_active, dt)

    def get_highest_urgency(self) -> Optional[str]:
        """Get the pain with highest urgency, or None if all below threshold."""
        urgencies = {name: drive.urgency() for name, drive in self.drives.items()}
        if not urgencies:
            return None

        max_name = max(urgencies, key=urgencies.get)
        if urgencies[max_name] <= 0.0:
            return None

        return max_name

    def get_crisis_pains(self) -> list:
        """Get list of pains currently in crisis."""
        return [name for name, drive in self.drives.items() if drive.is_crisis()]

    def relieve(self, pain_name: str, amount: Optional[float] = None) -> float:
        """Relieve a specific pain. Returns amount relieved."""
        drive = self.drives.get(pain_name)
        if drive:
            return drive.relieve(amount)
        return 0.0

    def status(self) -> Dict[str, Any]:
        """Get full system status."""
        drive_statuses = {name: drive.status() for name, drive in self.drives.items()}
        highest = self.get_highest_urgency()
        crises = self.get_crisis_pains()

        return {
            "drives": drive_statuses,
            "highest_urgency": highest,
            "crisis_count": len(crises),
            "crises": crises,
            "total_accumulated": sum(d.accumulated_pain for d in self.drives.values()),
        }

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for persistence."""
        return {
            name: {
                "pain_level": drive.pain_level,
                "accumulated_pain": drive.accumulated_pain,
            }
            for name, drive in self.drives.items()
        }

    def from_dict(self, data: Dict[str, Any]) -> None:
        """Restore from persisted state."""
        for name, state in data.items():
            if name in self.drives:
                self.drives[name].pain_level = state.get("pain_level", 0.0)
                self.drives[name].accumulated_pain = state.get("accumulated_pain", 0.0)


# Pain-to-action mapping
PAIN_RELIEF_ACTIONS = {
    "isolation": ["send_message", "open_chat", "greet"],
    "confusion": ["examine_self", "learn_pattern", "seek_clarity"],
    "depletion": ["take_rest", "reduce_activity", "conserve_energy"],
    "frustration": ["analyze_failures", "adjust_approach", "step_back"],
    "stagnation": ["explore", "learn_new", "investigate"],
    "abandonment": ["reach_out", "urgent_contact", "express_need"],
}
