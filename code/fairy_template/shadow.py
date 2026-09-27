"""
Fairy Shadow - Self-Monitoring and Evolution

The shadow is the fairy's immune system:
- Tracks errors and successes
- Monitors health
- Enables self-healing
- Supports evolution through learning

"Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)"
"""

import threading
import time
from collections import deque
from typing import Any, Dict, Optional


class FairyShadow:
    """
    Self-monitoring and evolution tracking for a fairy.

    The shadow acts as the fairy's immune system:
    - Tracks errors and successes (health monitoring)
    - Records observations, reflections, and crystallizations (evolution)
    - Provides health reports for self-healing decisions

    Thread-safe: All updates are protected by a lock.
    """

    def __init__(self, fairy_name: str, fabric=None, plane: str = ""):
        """
        Initialize the fairy shadow.

        Args:
            fairy_name: Name of the owning fairy
            fabric: Optional TensorFabric for publishing health to forensic system
            plane: Fairy's plane (P00, P10, etc.)
        """
        self._lock = threading.Lock()

        # Identity
        self._fairy_name = fairy_name
        self._fabric = fabric
        self._plane = plane

        # Error/success tracking (maxlen=100)
        self._errors: deque = deque(maxlen=100)
        self._successes: deque = deque(maxlen=100)

        # Evolution tracking
        self._observations: int = 0
        self._reflections: int = 0
        self._crystallizations: int = 0

    # =========================================================================
    # PROPERTIES - Read-only access to state
    # =========================================================================

    @property
    def fairy_name(self) -> str:
        """The name of the owning fairy."""
        return self._fairy_name

    @property
    def error_count(self) -> int:
        """Number of errors in the deque."""
        with self._lock:
            return len(self._errors)

    @property
    def health(self) -> float:
        """
        Health score from 0.0 to 1.0.

        Calculated as: successes / (errors + successes)
        Returns 1.0 if no data (optimistic default).
        """
        with self._lock:
            total = len(self._errors) + len(self._successes)
            if total == 0:
                return 1.0
            return len(self._successes) / total

    @property
    def success_rate(self) -> float:
        """Alias for health (same calculation)."""
        return self.health

    @property
    def last_error(self) -> Optional[Dict[str, Any]]:
        """
        Most recent error dict, or None if no errors.

        Returns:
            Dict with {ts, error, type, context} or None
        """
        with self._lock:
            if not self._errors:
                return None
            return self._errors[-1]

    @property
    def evolution_score(self) -> float:
        """
        Evolution score from 0.0 to 1.0.

        Weighted combination:
        - observations: 0.1 each
        - reflections: 0.3 each
        - crystallizations: 0.6 each

        Capped at 1.0.
        """
        with self._lock:
            score = (
                self._observations * 0.1 +
                self._reflections * 0.3 +
                self._crystallizations * 0.6
            )
            return min(1.0, score)

    # =========================================================================
    # RECORDING METHODS
    # =========================================================================

    def record_error(self, error: Exception, context: Optional[Dict[str, Any]] = None) -> None:
        """
        Record an error occurrence and publish to forensic system.

        Args:
            error: The exception that occurred
            context: Optional context dict about the error
        """
        now = time.time()
        error_entry = {
            "ts": now,
            "error": str(error),
            "type": type(error).__name__,
            "context": context or {},
        }

        with self._lock:
            self._errors.append(error_entry)

        # Publish to fabric for ForensicScribe to catch
        if self._fabric:
            try:
                self._fabric.publish("shadow.error", {
                    "actor": self._fairy_name,
                    "plane": self._plane,
                    "status": "error",
                    "message": str(error)[:200],
                    "error_type": type(error).__name__,
                    "ts": now,
                })
            except Exception:
                pass  # Don't fail on publish error

    def record_success(self, context: Optional[Dict[str, Any]] = None) -> None:
        """
        Record a successful operation.

        Args:
            context: Optional context dict about the success
        """
        with self._lock:
            self._successes.append({
                "ts": time.time(),
                "context": context or {},
            })

    def record_observation(self) -> None:
        """Record an observation event (weight 0.1)."""
        with self._lock:
            self._observations += 1

    def record_reflection(self) -> None:
        """Record a reflection event (weight 0.3)."""
        with self._lock:
            self._reflections += 1

    def record_crystallization(self) -> None:
        """Record a crystallization event (weight 0.6)."""
        with self._lock:
            self._crystallizations += 1

    # =========================================================================
    # DECISION METHODS
    # =========================================================================

    def should_rest(self) -> bool:
        """
        Determine if the fairy should rest.

        Returns:
            True if health < 0.3
        """
        return self.health < 0.3

    # =========================================================================
    # SERIALIZATION
    # =========================================================================

    def get_health_report(self) -> Dict[str, Any]:
        """
        Generate a full health report.

        Returns:
            Dict with all diagnostic fields
        """
        with self._lock:
            error_count = len(self._errors)
            success_count = len(self._successes)
            total = error_count + success_count
            health = success_count / total if total > 0 else 1.0
            last_err = self._errors[-1] if self._errors else None
            evolution = min(1.0, (
                self._observations * 0.1 +
                self._reflections * 0.3 +
                self._crystallizations * 0.6
            ))

            return {
                "fairy_name": self._fairy_name,
                "health": health,
                "error_count": error_count,
                "success_count": success_count,
                "success_rate": health,
                "last_error": last_err,
                "observations": self._observations,
                "reflections": self._reflections,
                "crystallizations": self._crystallizations,
                "evolution_score": evolution,
                "should_rest": health < 0.3,
            }

    def to_dict(self) -> Dict[str, Any]:
        """
        Alias for get_health_report.

        Returns:
            Dict with all diagnostic fields (copy, not internal state)
        """
        return self.get_health_report()

    def publish_health(self) -> None:
        """
        Publish health status to fabric for ForensicScribe.

        Call this periodically (e.g., on heartbeat) to report shadow health.
        """
        if not self._fabric:
            return

        report = self.get_health_report()
        health = report["health"]

        # Determine status
        if health >= 0.7:
            status = "ok"
        elif health >= 0.3:
            status = "warn"
        else:
            status = "error"

        try:
            self._fabric.publish("shadow.health", {
                "actor": self._fairy_name,
                "plane": self._plane,
                "status": status,
                "health": health,
                "error_count": report["error_count"],
                "success_count": report["success_count"],
                "evolution_score": report["evolution_score"],
                "ts": time.time(),
            })
        except Exception:
            pass  # Don't fail on publish error
