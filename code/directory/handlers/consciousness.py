"""
Consciousness Handler - React to tensor fabric consciousness events.
"""

from typing import Any, Dict, List, Optional, Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from postal_core.tensor_fabric import TensorFabric, TensorEnvelope


class ConsciousnessHandler:
    """
    Handles consciousness events from the tensor fabric.

    Listens to:
    - consciousness.heartbeat - System consciousness pulse
    - consciousness.affect_change - Affect state changes

    Provides:
    - Affect anomaly detection
    - Resonance pattern detection
    - System state monitoring
    """

    # Thresholds for anomaly detection
    HIGH_AFFECT_THRESHOLD = 0.8
    LOW_AFFECT_THRESHOLD = 0.1
    RESONANCE_THRESHOLD = 0.9

    def __init__(self, fabric: Optional["TensorFabric"] = None):
        self.fabric = fabric
        self._affect_history: List[float] = []
        self._max_history = 100
        self._anomaly_callbacks: List[Callable[[str, Dict], None]] = []
        self._resonance_callbacks: List[Callable[[float, int, int], None]] = []

    def on_consciousness_heartbeat(self, envelope: "TensorEnvelope") -> Dict[str, Any]:
        """
        Handle consciousness heartbeat.

        This is called on each consciousness pulse from the system.
        """
        if not self.fabric:
            return {"ok": False, "error": "no_fabric"}

        # Get current affect
        mean_affect = self.fabric.mean_affect()
        self._affect_history.append(mean_affect)

        # Trim history
        if len(self._affect_history) > self._max_history:
            self._affect_history = self._affect_history[-self._max_history:]

        # Check for anomalies
        anomalies = self._check_anomalies(mean_affect)

        return {
            "ok": True,
            "time_index": self.fabric.time_index,
            "mean_affect": mean_affect,
            "anomalies": anomalies,
        }

    def _check_anomalies(self, current_affect: float) -> List[str]:
        """Check for affect anomalies."""
        anomalies = []

        # High affect
        if current_affect > self.HIGH_AFFECT_THRESHOLD:
            anomalies.append("high_affect")
            self._notify_anomaly("high_affect", {"value": current_affect})

        # Low affect (if we've had higher before)
        if current_affect < self.LOW_AFFECT_THRESHOLD and len(self._affect_history) > 10:
            avg = sum(self._affect_history[-10:]) / 10
            if avg > 0.3:  # Was higher, now crashed
                anomalies.append("affect_crash")
                self._notify_anomaly("affect_crash", {"current": current_affect, "recent_avg": avg})

        # Sudden change
        if len(self._affect_history) >= 2:
            prev = self._affect_history[-2]
            delta = abs(current_affect - prev)
            if delta > 0.5:
                anomalies.append("affect_spike")
                self._notify_anomaly("affect_spike", {"delta": delta, "from": prev, "to": current_affect})

        return anomalies

    def _notify_anomaly(self, anomaly_type: str, data: Dict) -> None:
        """Notify registered anomaly callbacks."""
        for callback in self._anomaly_callbacks:
            try:
                callback(anomaly_type, data)
            except:
                pass

    def on_anomaly(self, callback: Callable[[str, Dict], None]) -> None:
        """Register a callback for anomaly detection."""
        self._anomaly_callbacks.append(callback)

    def check_resonance(self, t1: int = 0, t2: int = 1) -> Optional[float]:
        """
        Check temporal resonance between time slices.

        High resonance (> 0.9) might indicate patterns or loops.
        """
        if not self.fabric:
            return None

        resonance = self.fabric.compute_resonance(t1, t2)

        # Check for high resonance (potential pattern)
        if resonance > self.RESONANCE_THRESHOLD:
            for callback in self._resonance_callbacks:
                try:
                    callback(resonance, t1, t2)
                except:
                    pass

        return resonance

    def on_resonance(self, callback: Callable[[float, int, int], None]) -> None:
        """Register a callback for resonance events."""
        self._resonance_callbacks.append(callback)

    def get_affect_state(self) -> Dict[str, Any]:
        """Get current affect state summary."""
        if not self.fabric:
            return {"error": "no_fabric"}

        current = self.fabric.mean_affect()
        history = self._affect_history[-10:] if self._affect_history else []

        return {
            "current": current,
            "recent_history": history,
            "avg_10": sum(history) / len(history) if history else 0,
            "time_index": self.fabric.time_index,
        }

    def get_tensor_snapshot(self) -> Dict[str, Any]:
        """Get a snapshot of the tensor state."""
        if not self.fabric:
            return {"error": "no_fabric"}

        return {
            "shape": self.fabric.shape.as_tuple(),
            "time_index": self.fabric.time_index,
            "mean_affect": self.fabric.mean_affect(),
            "tensor_updates": self.fabric._stats.get("tensor_updates", 0),
        }
