"""
AdaptiveRegulator - Dynamic Self-Regulation for the Akashic System

The system should auto-regulate, not rely on static values. This module:

1. OBSERVES system state (tracer counts, fairy activity, decay rates)
2. ADJUSTS parameters dynamically based on health
3. LEARNS what works and what doesn't
4. STIMULATES idle components to prevent death cycles

Philosophy: Everything is dynamic. Nothing is static.
"""

from __future__ import annotations

import time
import threading
import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from collections import deque
from enum import Enum


class SystemHealth(Enum):
    """Overall system health state."""
    CRITICAL = "critical"   # Death cycle imminent
    STRESSED = "stressed"   # High load, needs relief
    HEALTHY = "healthy"     # Normal operation
    IDLE = "idle"           # Too quiet, needs stimulation
    THRIVING = "thriving"   # Peak performance


@dataclass
class ParameterHistory:
    """Track a parameter's value and effectiveness over time."""
    name: str
    current_value: float
    min_value: float
    max_value: float
    default_value: float

    # History of adjustments and outcomes
    history: List[Dict] = field(default_factory=list)

    # Running effectiveness score
    effectiveness_score: float = 0.5  # 0-1

    def adjust(self, new_value: float, reason: str):
        """Adjust parameter and record why."""
        old_value = self.current_value
        self.current_value = max(self.min_value, min(self.max_value, new_value))
        self.history.append({
            "ts": time.time(),
            "from": old_value,
            "to": self.current_value,
            "reason": reason,
        })
        # Keep only last 100 adjustments
        if len(self.history) > 100:
            self.history = self.history[-100:]

    def record_outcome(self, success: bool):
        """Record whether the current value is working."""
        # Exponential moving average
        alpha = 0.2
        outcome = 1.0 if success else 0.0
        self.effectiveness_score = alpha * outcome + (1 - alpha) * self.effectiveness_score


@dataclass
class FairyState:
    """Track a fairy's activity state."""
    name: str
    last_seen: float = 0.0
    last_output: float = 0.0
    message_count: int = 0
    is_idle: bool = False
    idle_since: float = 0.0
    stimulated_at: float = 0.0
    stimulation_count: int = 0


class AdaptiveRegulator:
    """
    Self-regulating system that adjusts parameters dynamically.

    Monitored Parameters:
    - tracer_ttl: How long tracers live
    - decay_rate: How fast tracers decay
    - promotion_threshold: Minimum priority for promotion
    - collision_interval: Time between collisions
    - stall_threshold: When to detect death cycle

    Monitored Fairies:
    - Tracks which fairies are idle
    - Injects stimulation when needed
    - Learns which stimulations work
    """

    # === SINGLETON ===
    _instance = None
    _lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> "AdaptiveRegulator":
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def __init__(self):
        # Prevent re-init
        if hasattr(self, '_initialized'):
            return
        self._initialized = True

        # === PARAMETERS TO REGULATE ===
        self._parameters: Dict[str, ParameterHistory] = {
            "tracer_ttl": ParameterHistory(
                name="tracer_ttl",
                current_value=300.0,
                min_value=60.0,
                max_value=900.0,
                default_value=300.0,
            ),
            "decay_rate": ParameterHistory(
                name="decay_rate",
                current_value=0.9,
                min_value=0.7,
                max_value=0.98,
                default_value=0.9,
            ),
            "promotion_threshold": ParameterHistory(
                name="promotion_threshold",
                current_value=0.3,
                min_value=0.1,
                max_value=0.6,
                default_value=0.3,
            ),
            "collision_interval": ParameterHistory(
                name="collision_interval",
                current_value=0.5,
                min_value=0.1,
                max_value=2.0,
                default_value=0.5,
            ),
            "stall_threshold": ParameterHistory(
                name="stall_threshold",
                current_value=60.0,
                min_value=30.0,
                max_value=180.0,
                default_value=60.0,
            ),
        }

        # === FAIRY TRACKING ===
        self._fairies: Dict[str, FairyState] = {}
        self._idle_threshold_sec = 120.0  # 2 minutes without output = idle

        # === SYSTEM METRICS ===
        self._metrics_history: deque = deque(maxlen=1000)
        self._last_health = SystemHealth.HEALTHY
        self._health_streak = 0  # How many cycles at current health

        # === LEARNING ===
        self._learned_adjustments: List[Dict] = []
        self._effective_patterns: Dict[str, float] = {}  # pattern -> effectiveness

        # === THREADING ===
        self._running = False
        self._thread = None
        self._postal = None

        # === PERSISTENCE ===
        self._state_file = Path(__file__).parent.parent.parent / "state" / "adaptive_regulator_state.json"
        self._load_state()

    def start(self, postal=None):
        """Start the regulation loop."""
        self._postal = postal
        self._running = True
        self._thread = threading.Thread(target=self._regulation_loop, daemon=True, name="AdaptiveRegulator")
        self._thread.start()
        print(f"[AdaptiveRegulator] Started dynamic regulation")

    def stop(self):
        """Stop the regulation loop."""
        self._running = False
        self._save_state()

    def get_parameter(self, name: str, default: float = 0.0) -> float:
        """
        Get the current value of a regulated parameter.

        This is how other components get dynamic values instead of static ones.
        If the parameter isn't tracked, returns the default.

        Args:
            name: Parameter name (tracer_ttl, decay_rate, promotion_threshold, etc.)
            default: Default value if parameter not found

        Returns:
            Current value of the parameter
        """
        if name in self._parameters:
            return self._parameters[name].current_value
        return default

    def record_outcome(self, parameter_name: str, success: bool):
        """
        Record whether a parameter's current value led to success.

        Call this after observing the outcome of using a parameter.
        Helps the regulator learn which values work.
        """
        if parameter_name in self._parameters:
            self._parameters[parameter_name].record_outcome(success)

    def _regulation_loop(self):
        """Main regulation loop - runs every 10 seconds."""
        while self._running:
            try:
                # 1. Observe current state
                metrics = self._observe_system()

                # 2. Assess health
                health = self._assess_health(metrics)

                # 3. Adjust parameters if needed
                self._adjust_parameters(health, metrics)

                # 4. Handle idle fairies
                self._handle_idle_fairies()

                # 5. Learn from outcomes
                self._learn_from_state(health, metrics)

                # 6. Save state periodically
                if int(time.time()) % 60 == 0:
                    self._save_state()

                time.sleep(10.0)
            except Exception as e:
                print(f"[AdaptiveRegulator] Error: {e}")
                time.sleep(5.0)

    def _observe_system(self) -> Dict[str, Any]:
        """Observe current system state."""
        metrics = {
            "ts": time.time(),
            "reflective_count": 0,
            "reasoning_count": 0,
            "recurring_count": 0,
            "promotion_rate": 0.0,
            "decay_rate_actual": 0.0,
            "idle_fairy_count": 0,
            "total_fairies": len(self._fairies),
        }

        # Try to get working memory stats
        try:
            from fairies.P30_Cognition.cognition.working_memory_hub_fairy import get_working_memory_hub
            hub = get_working_memory_hub()
            if hub:
                stats = hub.get_detailed_status()
                metrics["reflective_count"] = stats.get("reflective_count", 0)
                metrics["reasoning_count"] = stats.get("reasoning_count", 0)
                metrics["recurring_count"] = len(hub._recurring_pool) if hasattr(hub, '_recurring_pool') else 0

                # Calculate rates from stats
                total_received = stats.get("stats", {}).get("tracers_received", 0)
                total_promoted = stats.get("stats", {}).get("promoted_to_reasoning", 0)
                if total_received > 0:
                    metrics["promotion_rate"] = total_promoted / total_received
        except Exception:
            pass

        # Count idle fairies
        now = time.time()
        for fairy in self._fairies.values():
            if fairy.is_idle or (now - fairy.last_output > self._idle_threshold_sec):
                fairy.is_idle = True
                if fairy.idle_since == 0:
                    fairy.idle_since = now
                metrics["idle_fairy_count"] += 1

        self._metrics_history.append(metrics)
        return metrics

    def _assess_health(self, metrics: Dict) -> SystemHealth:
        """Assess overall system health."""
        reflective = metrics.get("reflective_count", 0)
        reasoning = metrics.get("reasoning_count", 0)
        recurring = metrics.get("recurring_count", 0)
        idle_count = metrics.get("idle_fairy_count", 0)
        total = metrics.get("total_fairies", 1)

        total_tracers = reflective + reasoning
        idle_ratio = idle_count / max(total, 1)

        # CRITICAL: No tracers and lots of idle fairies
        if total_tracers == 0 and recurring == 0:
            health = SystemHealth.CRITICAL
        # STRESSED: Too many tracers, system overloaded
        elif total_tracers > 50:
            health = SystemHealth.STRESSED
        # IDLE: Low activity
        elif total_tracers < 3 and idle_ratio > 0.5:
            health = SystemHealth.IDLE
        # THRIVING: Good balance
        elif 10 <= total_tracers <= 30 and idle_ratio < 0.3:
            health = SystemHealth.THRIVING
        else:
            health = SystemHealth.HEALTHY

        # Track health streak
        if health == self._last_health:
            self._health_streak += 1
        else:
            self._health_streak = 0
            self._last_health = health

        return health

    def _adjust_parameters(self, health: SystemHealth, metrics: Dict):
        """Adjust parameters based on health."""

        if health == SystemHealth.CRITICAL:
            # EMERGENCY: Maximize survival
            self._parameters["tracer_ttl"].adjust(
                self._parameters["tracer_ttl"].current_value * 1.5,
                "CRITICAL - extending TTL"
            )
            self._parameters["decay_rate"].adjust(
                min(0.98, self._parameters["decay_rate"].current_value + 0.05),
                "CRITICAL - slowing decay"
            )
            self._parameters["promotion_threshold"].adjust(
                max(0.1, self._parameters["promotion_threshold"].current_value - 0.1),
                "CRITICAL - lowering promotion bar"
            )

        elif health == SystemHealth.STRESSED:
            # Too much activity - let things decay faster
            self._parameters["decay_rate"].adjust(
                max(0.7, self._parameters["decay_rate"].current_value - 0.02),
                "STRESSED - speeding decay"
            )
            self._parameters["tracer_ttl"].adjust(
                max(60, self._parameters["tracer_ttl"].current_value * 0.9),
                "STRESSED - reducing TTL"
            )

        elif health == SystemHealth.IDLE:
            # Too quiet - stimulate
            self._parameters["tracer_ttl"].adjust(
                self._parameters["tracer_ttl"].current_value * 1.2,
                "IDLE - extending TTL"
            )
            self._parameters["stall_threshold"].adjust(
                max(30, self._parameters["stall_threshold"].current_value * 0.8),
                "IDLE - faster stall detection"
            )

        elif health == SystemHealth.THRIVING and self._health_streak > 5:
            # Stable - slowly return to defaults
            for param in self._parameters.values():
                if abs(param.current_value - param.default_value) > 0.01:
                    diff = param.default_value - param.current_value
                    param.adjust(
                        param.current_value + diff * 0.1,
                        "THRIVING - returning to default"
                    )

    def _handle_idle_fairies(self):
        """Stimulate idle fairies with daydreams/tasks."""
        if not self._postal:
            return

        now = time.time()

        for fairy in self._fairies.values():
            if not fairy.is_idle:
                continue

            # Don't over-stimulate
            if now - fairy.stimulated_at < 60:
                continue

            # Inject a daydream/task to wake them up
            self._stimulate_fairy(fairy)
            fairy.stimulated_at = now
            fairy.stimulation_count += 1

    def _stimulate_fairy(self, fairy: FairyState):
        """Inject stimulation for an idle fairy."""
        if not self._postal:
            return

        # Choose stimulation based on fairy type
        stimulation = {
            "type": "daydream",
            "target": fairy.name,
            "content": f"[STIMULATION] What are you thinking about, {fairy.name}?",
            "source": "AdaptiveRegulator",
            "priority": 0.5,
        }

        try:
            # Send to unconscious for processing
            self._postal.route("consciousness.stream", {
                "stream": "working",
                "type": "stimulation",
                "payload": stimulation,
                "source": "AdaptiveRegulator",
            })
            print(f"[AdaptiveRegulator] Stimulated idle fairy: {fairy.name}")
        except Exception as e:
            print(f"[AdaptiveRegulator] Stimulation failed: {e}")

    def _learn_from_state(self, health: SystemHealth, metrics: Dict):
        """Learn what adjustments work."""
        # If health improved, the recent adjustments were good
        # If health degraded, they were bad

        for param in self._parameters.values():
            if param.history:
                recent = param.history[-1]
                if time.time() - recent["ts"] < 30:  # Recent adjustment
                    # Was it effective?
                    success = health in (SystemHealth.HEALTHY, SystemHealth.THRIVING)
                    param.record_outcome(success)

                    # Record the learning
                    pattern = f"{param.name}:{recent['reason']}"
                    if pattern not in self._effective_patterns:
                        self._effective_patterns[pattern] = 0.5

                    alpha = 0.2
                    outcome = 1.0 if success else 0.0
                    self._effective_patterns[pattern] = (
                        alpha * outcome + (1 - alpha) * self._effective_patterns[pattern]
                    )

    # === EXTERNAL INTERFACE ===

    def observe_fairy(self, fairy_name: str, had_output: bool = False):
        """Called when a fairy does something."""
        now = time.time()

        if fairy_name not in self._fairies:
            self._fairies[fairy_name] = FairyState(name=fairy_name)

        fairy = self._fairies[fairy_name]
        fairy.last_seen = now
        fairy.message_count += 1

        if had_output:
            fairy.last_output = now
            fairy.is_idle = False
            fairy.idle_since = 0.0

    def get_parameter(self, name: str) -> float:
        """Get current value of a regulated parameter."""
        if name in self._parameters:
            return self._parameters[name].current_value
        return 0.0

    def get_status(self) -> Dict:
        """Get regulator status."""
        return {
            "health": self._last_health.value,
            "health_streak": self._health_streak,
            "parameters": {
                name: {
                    "value": p.current_value,
                    "effectiveness": p.effectiveness_score,
                    "adjustments": len(p.history),
                }
                for name, p in self._parameters.items()
            },
            "fairies": {
                name: {
                    "is_idle": f.is_idle,
                    "idle_sec": time.time() - f.idle_since if f.idle_since else 0,
                    "stimulations": f.stimulation_count,
                }
                for name, f in self._fairies.items()
                if f.is_idle
            },
            "effective_patterns": dict(sorted(
                self._effective_patterns.items(),
                key=lambda x: x[1],
                reverse=True
            )[:10]),
        }

    def manual_adjust(self, param_name: str, value: float, reason: str):
        """Manual parameter adjustment (from outside)."""
        if param_name in self._parameters:
            self._parameters[param_name].adjust(value, f"MANUAL: {reason}")
            self._learned_adjustments.append({
                "ts": time.time(),
                "param": param_name,
                "value": value,
                "reason": reason,
                "source": "manual",
            })

    # === PERSISTENCE ===

    def _save_state(self):
        """Save state to disk."""
        try:
            state = {
                "parameters": {
                    name: {
                        "current": p.current_value,
                        "effectiveness": p.effectiveness_score,
                        "history": p.history[-20:],  # Keep recent
                    }
                    for name, p in self._parameters.items()
                },
                "effective_patterns": self._effective_patterns,
                "learned_adjustments": self._learned_adjustments[-50:],
            }
            self._state_file.parent.mkdir(parents=True, exist_ok=True)
            self._state_file.write_text(json.dumps(state, indent=2))
        except Exception as e:
            print(f"[AdaptiveRegulator] Save failed: {e}")

    def _load_state(self):
        """Load state from disk."""
        try:
            if self._state_file.exists():
                state = json.loads(self._state_file.read_text())

                # Restore parameters
                for name, data in state.get("parameters", {}).items():
                    if name in self._parameters:
                        self._parameters[name].current_value = data.get("current", self._parameters[name].default_value)
                        self._parameters[name].effectiveness_score = data.get("effectiveness", 0.5)
                        self._parameters[name].history = data.get("history", [])

                # Restore patterns
                self._effective_patterns = state.get("effective_patterns", {})
                self._learned_adjustments = state.get("learned_adjustments", [])

                print(f"[AdaptiveRegulator] Loaded {len(self._effective_patterns)} learned patterns")
        except Exception as e:
            print(f"[AdaptiveRegulator] Load failed: {e}")


# === SINGLETON ACCESS ===

def get_adaptive_regulator() -> AdaptiveRegulator:
    """Get the adaptive regulator singleton."""
    return AdaptiveRegulator.get_instance()
