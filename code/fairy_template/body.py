"""
Fairy Body - Somatic and Affect State Management

Every fairy has a body. The body tracks:
- Energy (somatic)
- Coherence (clarity of thinking)
- Affect (emotional state)
- Circadian (time-of-day context)

"Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)"
"""

import threading
from typing import Any, Dict, Optional


class FairyBody:
    """
    Manages somatic and affect state for a fairy.

    Thread-safe state management for:
    - Energy and coherence (somatic state from postal)
    - Valence, arousal, and primary affect (emotional state)
    - Circadian phase (time-of-day context)
    - Sedation level (sleep state)

    Every fairy has a body. The body is NOT optional.
    """

    def __init__(self, fairy_name: str):
        """
        Initialize the fairy body.

        Args:
            fairy_name: Name of the owning fairy
        """
        self._lock = threading.Lock()

        # Identity
        self._fairy_name = fairy_name

        # Somatic state
        self._energy: float = 1.0      # 0.0 to 1.0
        self._coherence: float = 0.5   # 0.0 to 1.0

        # Affect state
        self._valence: float = 0.0     # -1.0 to +1.0
        self._arousal: float = 0.5     # 0.0 to 1.0
        self._primary_affect: str = "neutral"

        # Circadian state
        self._circadian_phase: str = "unknown"

        # Sedation state
        self._sedation_level: float = 0.0  # 0.0 to 1.0

    # =========================================================================
    # PROPERTIES - Read-only access to state
    # =========================================================================

    @property
    def fairy_name(self) -> str:
        """The name of the owning fairy."""
        return self._fairy_name

    @property
    def energy(self) -> float:
        """Current energy level (0.0 to 1.0)."""
        with self._lock:
            return self._energy

    @property
    def coherence(self) -> float:
        """Current coherence/clarity (0.0 to 1.0)."""
        with self._lock:
            return self._coherence

    @property
    def valence(self) -> float:
        """Current emotional valence (-1.0 to +1.0)."""
        with self._lock:
            return self._valence

    @property
    def arousal(self) -> float:
        """Current arousal/activation level (0.0 to 1.0)."""
        with self._lock:
            return self._arousal

    @property
    def primary_affect(self) -> str:
        """Current primary emotion name."""
        with self._lock:
            return self._primary_affect

    @property
    def circadian_phase(self) -> str:
        """Current time-of-day phase."""
        with self._lock:
            return self._circadian_phase

    @property
    def sedation_level(self) -> float:
        """Current sedation/sleep level (0.0 to 1.0)."""
        with self._lock:
            return self._sedation_level

    # =========================================================================
    # COMPUTED PROPERTIES
    # =========================================================================

    @property
    def is_depleted(self) -> bool:
        """True if energy is below 0.2."""
        with self._lock:
            return self._energy < 0.2

    @property
    def can_work(self) -> bool:
        """True if energy > 0.3 AND sedation < 0.7."""
        with self._lock:
            return self._energy > 0.3 and self._sedation_level < 0.7

    @property
    def affect(self) -> Dict[str, Any]:
        """Returns affect state as {valence, arousal, primary}."""
        with self._lock:
            return {
                "valence": self._valence,
                "arousal": self._arousal,
                "primary": self._primary_affect,
            }

    # =========================================================================
    # UPDATE METHODS
    # =========================================================================

    def update_somatic(self, state: Dict[str, Any]) -> None:
        """
        Update somatic state from postal message.

        Args:
            state: Dict with optional 'energy' and 'coherence' keys
        """
        with self._lock:
            if "energy" in state and state["energy"] is not None:
                self._energy = self._clamp(float(state["energy"]), 0.0, 1.0)
            if "coherence" in state and state["coherence"] is not None:
                self._coherence = self._clamp(float(state["coherence"]), 0.0, 1.0)

    def update_affect(self, state: Dict[str, Any]) -> None:
        """
        Update affect state from postal message.

        Args:
            state: Dict with optional 'valence', 'arousal', 'primary' keys
        """
        with self._lock:
            if "valence" in state and state["valence"] is not None:
                self._valence = self._clamp(float(state["valence"]), -1.0, 1.0)
            if "arousal" in state and state["arousal"] is not None:
                self._arousal = self._clamp(float(state["arousal"]), 0.0, 1.0)
            if "primary" in state and state["primary"] is not None:
                self._primary_affect = str(state["primary"])

    def update_circadian(self, phase: str) -> None:
        """
        Update circadian phase.

        Args:
            phase: The time-of-day phase name
        """
        with self._lock:
            self._circadian_phase = phase

    def update_sedation(self, level: float) -> None:
        """
        Update sedation level.

        Args:
            level: Sedation level (0.0 to 1.0)
        """
        with self._lock:
            self._sedation_level = self._clamp(level, 0.0, 1.0)

    # =========================================================================
    # SERIALIZATION
    # =========================================================================

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize all state to a dictionary.

        Returns:
            Dict with all state fields (copy, not internal state)
        """
        with self._lock:
            return {
                "fairy_name": self._fairy_name,
                "energy": self._energy,
                "coherence": self._coherence,
                "valence": self._valence,
                "arousal": self._arousal,
                "primary_affect": self._primary_affect,
                "circadian_phase": self._circadian_phase,
                "sedation_level": self._sedation_level,
            }

    # =========================================================================
    # PRIVATE HELPERS
    # =========================================================================

    @staticmethod
    def _clamp(value: float, min_val: float, max_val: float) -> float:
        """Clamp a value to a range."""
        return max(min_val, min(max_val, value))
