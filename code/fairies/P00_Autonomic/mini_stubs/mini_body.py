"""
MiniBody - Bootstrap Body Stub

Just enough to provide heartbeat pulse during bootstrap.
Full somatic system lives in P20_Somatic.

Capabilities:
- Simple heartbeat pulse
- Basic alive/dead state
- Bootstrap timing

Does NOT:
- Full body awareness
- Felt sense processing
- Complex somatic state
"""

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Optional, Callable, List, Any
from enum import Enum


class BodyState(Enum):
    """Minimal body states for bootstrap."""
    DORMANT = "dormant"       # Not yet started
    WAKING = "waking"         # Bootstrap in progress
    ALIVE = "alive"           # Heartbeat running
    SHUTTING_DOWN = "shutting_down"
    DEAD = "dead"             # Stopped


@dataclass
class Heartbeat:
    """Single heartbeat record."""
    beat_number: int
    timestamp: datetime
    state: BodyState
    interval_ms: float  # Time since last beat


class MiniBody:
    """
    Minimal body system for P00 bootstrap.

    Only provides heartbeat - no complex somatic awareness.
    Full body system lives in P20_Somatic.
    """

    # Default heartbeat interval in seconds
    DEFAULT_INTERVAL = 1.0

    def __init__(self, heartbeat_interval: float = DEFAULT_INTERVAL):
        """Initialize the minimal body system."""
        self._interval = heartbeat_interval
        self._state = BodyState.DORMANT
        self._beat_count = 0
        self._last_beat_time: Optional[float] = None
        self._start_time: Optional[float] = None
        self._running = False
        self._heartbeat_callbacks: List[Callable[[Heartbeat], None]] = []
        self._heartbeat_history: List[Heartbeat] = []
        self._max_history = 100

    def on_heartbeat(self, callback: Callable[[Heartbeat], None]) -> None:
        """Register a callback for heartbeat events."""
        self._heartbeat_callbacks.append(callback)

    def remove_heartbeat_callback(self, callback: Callable) -> bool:
        """Remove a heartbeat callback."""
        try:
            self._heartbeat_callbacks.remove(callback)
            return True
        except ValueError:
            return False

    def start(self) -> bool:
        """
        Start the heartbeat (synchronous version).

        Returns True if started successfully.
        """
        if self._state in (BodyState.ALIVE, BodyState.WAKING):
            return False

        self._state = BodyState.WAKING
        self._start_time = time.time()
        self._last_beat_time = self._start_time
        self._state = BodyState.ALIVE
        self._running = True

        # First beat
        self._do_beat()

        return True

    async def start_async(self) -> bool:
        """
        Start the heartbeat loop (async version).

        Returns True if started successfully.
        """
        if self._state in (BodyState.ALIVE, BodyState.WAKING):
            return False

        self._state = BodyState.WAKING
        self._start_time = time.time()
        self._last_beat_time = self._start_time
        self._state = BodyState.ALIVE
        self._running = True

        return True

    async def run_heartbeat_loop(self) -> None:
        """Run the async heartbeat loop."""
        while self._running and self._state == BodyState.ALIVE:
            self._do_beat()
            await asyncio.sleep(self._interval)

    def _do_beat(self) -> Heartbeat:
        """Execute a single heartbeat."""
        now = time.time()
        interval_ms = (now - self._last_beat_time) * 1000 if self._last_beat_time else 0
        self._last_beat_time = now
        self._beat_count += 1

        beat = Heartbeat(
            beat_number=self._beat_count,
            timestamp=datetime.now(),
            state=self._state,
            interval_ms=interval_ms
        )

        # Add to history
        self._heartbeat_history.append(beat)
        if len(self._heartbeat_history) > self._max_history:
            self._heartbeat_history.pop(0)

        # Notify callbacks
        for callback in self._heartbeat_callbacks:
            try:
                callback(beat)
            except Exception as e:
                print(f"[MiniBody] Heartbeat callback error: {e}")

        return beat

    def beat_once(self) -> Heartbeat:
        """
        Manually trigger a single heartbeat.

        Useful for synchronous bootstrap or testing.
        """
        if self._state == BodyState.DORMANT:
            self.start()
        return self._do_beat()

    def stop(self) -> None:
        """Stop the heartbeat."""
        self._state = BodyState.SHUTTING_DOWN
        self._running = False
        self._state = BodyState.DEAD

    def is_alive(self) -> bool:
        """Check if the body is alive (heartbeat running)."""
        return self._state == BodyState.ALIVE

    def get_state(self) -> BodyState:
        """Get current body state."""
        return self._state

    def get_beat_count(self) -> int:
        """Get total heartbeat count."""
        return self._beat_count

    def get_uptime(self) -> float:
        """Get uptime in seconds since start."""
        if self._start_time is None:
            return 0.0
        return time.time() - self._start_time

    def get_last_beat(self) -> Optional[Heartbeat]:
        """Get the most recent heartbeat."""
        return self._heartbeat_history[-1] if self._heartbeat_history else None

    def get_average_interval(self) -> float:
        """Get average heartbeat interval in milliseconds."""
        if len(self._heartbeat_history) < 2:
            return 0.0
        intervals = [h.interval_ms for h in self._heartbeat_history[1:]]
        return sum(intervals) / len(intervals) if intervals else 0.0

    def get_vital_signs(self) -> Dict[str, Any]:
        """
        Get current vital signs - minimal body state for bootstrap.

        This is what gets passed to other systems during bootstrap.
        """
        return {
            'state': self._state.value,
            'alive': self.is_alive(),
            'beat_count': self._beat_count,
            'uptime_seconds': self.get_uptime(),
            'last_beat': self._last_beat_time,
            'avg_interval_ms': self.get_average_interval(),
            'interval_target_ms': self._interval * 1000,
        }

    def prepare_for_p20(self) -> Dict[str, Any]:
        """
        Package state for handoff to P20_Somatic.

        Returns a dict that P20 can use to take over body awareness.
        """
        return {
            'vital_signs': self.get_vital_signs(),
            'heartbeat_history': [
                {
                    'beat': h.beat_number,
                    'timestamp': h.timestamp.isoformat(),
                    'interval_ms': h.interval_ms,
                }
                for h in self._heartbeat_history[-20:]  # Last 20 beats
            ],
            'start_time': datetime.fromtimestamp(self._start_time).isoformat() if self._start_time else None,
            'source': 'mini_body_bootstrap',
        }


# Singleton instance for bootstrap
_mini_body_instance: Optional[MiniBody] = None


def get_mini_body() -> MiniBody:
    """Get the singleton MiniBody instance."""
    global _mini_body_instance
    if _mini_body_instance is None:
        _mini_body_instance = MiniBody()
    return _mini_body_instance
