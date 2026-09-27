"""
═══════════════════════════════════════════════════════════════════════════════
HEARTBEAT SYNC - The Ignition Pulse Connector
═══════════════════════════════════════════════════════════════════════════════

"The human heartbeat is the ignition pulse. It hits the system-wide send button
that triggers different process speeds. Like a symphony conductor - doesn't tell
you WHAT to play, just keeps time. Musicians know their parts."

This module connects fairies to the heartbeat at their natural tempo:

  BEAT ───┬──→ Consciousness (every beat)
          ├──→ WorkingMemory (every beat)
          ├──→ Interests (every 2 beats)
          ├──→ GoalScheduler (every 4 beats)
          ├──→ Consolidation (every 60 beats)
          └──→ Circadian (every 3600 beats)

USAGE FOR ANY FAIRY:
    class MyFairy(HeartbeatSyncMixin, MyOrganFairy):
        # Fire every 4 beats (quarter time)
        HEARTBEAT_DIVISOR = 4
        
        def on_boot(self):
            super().on_boot()
            self.sync_to_heartbeat()  # Connect to the pump
        
        def on_heartbeat(self, beat_number: int, blood_state: dict):
            # Called every 4th beat - do your work!
            self.do_my_regular_work()

═══════════════════════════════════════════════════════════════════════════════
"""

from __future__ import annotations
import time
import threading
from typing import Dict, Any, Optional, Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from fairies.P20_Somatic.circulation.circulation_pump_fairy import CirculationPumpFairy, PulseEvent


# ═══════════════════════════════════════════════════════════════════════════════
# TEMPO DIVISORS - Based on Human Physiology
# ═══════════════════════════════════════════════════════════════════════════════

# Heart rate ~60-100 BPM = 1.0-1.7 Hz
# Base tempo: 1 beat = ~1 second

TEMPO_PRESETS = {
    # Every beat - immediate/reflex processes
    "REFLEX": 1,           # Nervous system, immediate response
    "PERCEPTION": 1,       # Sensory integration
    "CONSCIOUSNESS": 1,    # Thought circulation
    
    # Every 2 beats - fast but not reflex
    "ATTENTION": 2,        # Interest tracking
    "WORKING_MEMORY": 2,   # Active thought decay check
    
    # Every 4 beats - moderate pace
    "COGNITION": 4,        # Reasoning, processing
    "GOALS": 4,            # Goal checking
    "EMOTION": 4,          # Affect integration
    
    # Every 8 beats - slower deliberation
    "PLANNING": 8,         # Action planning
    "REFLECTION": 8,       # Meta-cognition
    
    # Every 30 beats (~30 seconds) - slow background
    "CONSOLIDATION": 30,   # Memory consolidation
    "LEARNING": 30,        # Pattern learning
    
    # Every 60 beats (~1 minute) - very slow
    "ROUTINE_CHECK": 60,   # Goal routine verification
    "HEALTH_CHECK": 60,    # System health monitoring
    
    # Every 300 beats (~5 minutes) - rare
    "DEEP_REFLECTION": 300,
    
    # Every 3600 beats (~1 hour) - circadian-scale
    "CIRCADIAN": 3600,
}


# ═══════════════════════════════════════════════════════════════════════════════
# HEARTBEAT SYNC MIXIN - Add to any fairy to connect to the pulse
# ═══════════════════════════════════════════════════════════════════════════════

class HeartbeatSyncMixin:
    """
    Mixin that connects a fairy to the heartbeat.
    
    The heartbeat is pure activation energy - no context, no commands.
    Just PULSE. The fairy wakes up and does its job.
    
    Attributes:
        HEARTBEAT_DIVISOR: Fire every N beats (default 1 = every beat)
        HEARTBEAT_ENABLED: Set False to disable sync
    """
    
    # Configuration - override in subclass
    HEARTBEAT_DIVISOR: int = 1          # Fire every N beats
    HEARTBEAT_ENABLED: bool = True       # Enable/disable
    HEARTBEAT_PHASE: int = 0             # Phase offset (0 = on beat, 1 = offset by 1, etc.)
    
    # Internal state
    _heartbeat_pump: Optional["CirculationPumpFairy"] = None
    _heartbeat_subscribed: bool = False
    _last_processed_beat: int = 0
    
    def sync_to_heartbeat(self):
        """
        Connect to the heartbeat pump.
        Call this in on_boot() after super().on_boot()
        """
        if not self.HEARTBEAT_ENABLED:
            return
        
        if self._heartbeat_subscribed:
            return

        # Subscribe via POSTAL only - no direct callbacks!
        # Direct subscribe_pulse() bypasses the postal worker pool and can freeze the heart.
        if hasattr(self, 'post') and self.post:
            self.post.subscribe("somatic.pulse", self._on_pulse_postal)
            self._heartbeat_subscribed = True
            print(f"[{getattr(self, 'ACTOR_NAME', 'Fairy')}] Synced to heartbeat via postal (divisor={self.HEARTBEAT_DIVISOR})")
        else:
            # No postal = no heartbeat sync. Direct callbacks are NOT allowed.
            print(f"[{getattr(self, 'ACTOR_NAME', 'Fairy')}] WARNING: No postal available for heartbeat sync!")
    
    def unsync_from_heartbeat(self):
        """Disconnect from heartbeat."""
        self._heartbeat_subscribed = False
        # Note: can't easily unsubscribe from postal, but setting flag prevents processing
    
    def _on_pulse_postal(self, pulse_data: Dict):
        """Handle pulse received via postal (async, through worker pool)."""
        if not self.HEARTBEAT_ENABLED or not self._heartbeat_subscribed:
            return

        # Heart sends "beat" key, not "beat_number"
        beat_number = pulse_data.get("beat", pulse_data.get("beat_number", 0))
        self._check_and_fire(beat_number, pulse_data)
    
    def _check_and_fire(self, beat_number: int, pulse_data: Dict):
        """Check if this beat should fire our callback."""
        # Apply phase offset
        adjusted_beat = beat_number - self.HEARTBEAT_PHASE
        
        # Check divisor (e.g., divisor=4 means fire on beats 4, 8, 12, ...)
        if adjusted_beat > 0 and adjusted_beat % self.HEARTBEAT_DIVISOR == 0:
            # Don't double-fire same beat
            if beat_number > self._last_processed_beat:
                self._last_processed_beat = beat_number
                
                try:
                    self.on_heartbeat(beat_number, pulse_data)
                except Exception as e:
                    print(f"[{getattr(self, 'ACTOR_NAME', 'Fairy')}] Heartbeat handler error: {e}")
    
    def on_heartbeat(self, beat_number: int, pulse_data: Dict):
        """
        Override this to do work on each heartbeat.
        
        This is the "do your job" signal. No context needed - 
        the fairy knows what it should be doing.
        
        Args:
            beat_number: Which beat this is (monotonic counter)
            pulse_data: Blood state, chemistry, etc. (for somatic awareness)
        """
        pass  # Override in subclass


# ═══════════════════════════════════════════════════════════════════════════════
# MULTI-TEMPO SYNC - For fairies that need multiple frequencies
# ═══════════════════════════════════════════════════════════════════════════════

class MultiTempoSyncMixin(HeartbeatSyncMixin):
    """
    For fairies that need to operate at multiple frequencies.
    
    Example: ConsciousnessLoopFairy might need:
    - Every beat: Check thought circulation
    - Every 30 beats: Run consolidation
    - Every 60 beats: Deep reflection
    
    USAGE:
        class ConsciousnessLoopFairy(MultiTempoSyncMixin, MyOrganFairy):
            TEMPO_HANDLERS = {
                1: "on_fast_tick",      # Every beat
                30: "on_consolidation", # Every 30 beats
                60: "on_deep_check",    # Every 60 beats
            }
    """
    
    # Map divisor → method name
    TEMPO_HANDLERS: Dict[int, str] = {}
    
    def on_heartbeat(self, beat_number: int, pulse_data: Dict):
        """Dispatch to multiple handlers based on tempo."""
        for divisor, handler_name in self.TEMPO_HANDLERS.items():
            if beat_number % divisor == 0:
                handler = getattr(self, handler_name, None)
                if handler:
                    try:
                        handler(beat_number, pulse_data)
                    except Exception as e:
                        print(f"[{getattr(self, 'ACTOR_NAME', 'Fairy')}] {handler_name} error: {e}")


# ═══════════════════════════════════════════════════════════════════════════════
# HEARTBEAT REGISTRY - Global registry of who's synced
# ═══════════════════════════════════════════════════════════════════════════════

class HeartbeatRegistry:
    """
    Tracks which fairies are synced to the heartbeat.
    Useful for diagnostics and ensuring the pulse is reaching everyone.
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._synced_fairies = {}
        return cls._instance
    
    def register(self, fairy_name: str, divisor: int):
        """Record a fairy as synced."""
        self._synced_fairies[fairy_name] = {
            "divisor": divisor,
            "synced_at": time.time(),
            "last_fired": 0,
        }
    
    def unregister(self, fairy_name: str):
        """Remove a fairy from registry."""
        self._synced_fairies.pop(fairy_name, None)
    
    def mark_fired(self, fairy_name: str, beat_number: int):
        """Record that a fairy fired on a beat."""
        if fairy_name in self._synced_fairies:
            self._synced_fairies[fairy_name]["last_fired"] = beat_number
    
    def get_status(self) -> Dict:
        """Get status of all synced fairies."""
        return {
            "count": len(self._synced_fairies),
            "fairies": dict(self._synced_fairies),
        }
    
    def get_silent_fairies(self, current_beat: int, threshold_beats: int = 10) -> list:
        """Find fairies that haven't fired recently."""
        silent = []
        for name, info in self._synced_fairies.items():
            expected_fires = current_beat // info["divisor"]
            if expected_fires > 0 and current_beat - info["last_fired"] > threshold_beats * info["divisor"]:
                silent.append(name)
        return silent


def get_heartbeat_registry() -> HeartbeatRegistry:
    """Get the singleton heartbeat registry."""
    return HeartbeatRegistry()


# ═══════════════════════════════════════════════════════════════════════════════
# CONVENIENCE DECORATORS
# ═══════════════════════════════════════════════════════════════════════════════

def on_every_beat(method):
    """Decorator to mark a method as firing every beat."""
    method._heartbeat_divisor = 1
    return method

def on_every_n_beats(n: int):
    """Decorator to mark a method as firing every N beats."""
    def decorator(method):
        method._heartbeat_divisor = n
        return method
    return decorator


# ═══════════════════════════════════════════════════════════════════════════════
# EXPORTS
# ═══════════════════════════════════════════════════════════════════════════════

__all__ = [
    "TEMPO_PRESETS",
    "HeartbeatSyncMixin",
    "MultiTempoSyncMixin",
    "HeartbeatRegistry",
    "get_heartbeat_registry",
    "on_every_beat",
    "on_every_n_beats",
]
