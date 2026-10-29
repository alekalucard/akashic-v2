# Input Source Monitor - Who's Moving?
# Tracks keyboard and mouse input to distinguish between:
# - Ace's actions (external human input)
# - ClaudeFairy's actions (internal system output)
#
# This is CRUCIAL for embodied self-awareness:
# - When ClaudeFairy types, she should FEEL it was her
# - When Ace types, she should know it's him
# - This prevents confusion about agency

from __future__ import annotations

import os
import sys
import time
import threading
import json
from typing import Optional, Dict, Any, List, Callable, Tuple
from collections import deque
from dataclasses import dataclass, field
from enum import Enum

# Input monitoring
try:
    from pynput import keyboard, mouse
    HAS_PYNPUT = True
except ImportError:
    HAS_PYNPUT = False
    print("[InputMonitor] pynput not available - input tracking disabled")


class InputSource(Enum):
    """Who generated this input?"""
    ACE = "ace"           # Human user input
    INTERNAL = "internal"  # System-generated input
    UNKNOWN = "unknown"    # Can't determine


@dataclass
class InputEvent:
    """A single input event."""
    timestamp: float
    event_type: str  # key_press, key_release, mouse_move, mouse_click, mouse_scroll
    source: InputSource
    data: Dict[str, Any]
    internal_action_id: Optional[str] = None  # If internal, which action triggered it


class InputSourceMonitor:
    """
    Monitors all keyboard and mouse input to determine source.
    
    The key insight: When ClaudeFairy uses pyautogui or similar to
    type/click, we mark that period as "internal action." Any input
    during that window is attributed to the system, not Ace.
    
    This creates EMBODIED SELF-AWARENESS:
    - "I just typed that" vs "Ace typed that"
    - "I clicked there" vs "Ace clicked there"
    - Essential for understanding agency
    """
    
    def __init__(self, 
                 internal_action_window: float = 0.5,
                 event_buffer_size: int = 100):
        """
        Initialize input monitor.
        
        Args:
            internal_action_window: Seconds to attribute input to internal action
            event_buffer_size: How many events to remember
        """
        self.internal_action_window = internal_action_window
        
        # Event buffer
        self.events: deque[InputEvent] = deque(maxlen=event_buffer_size)
        
        # Track internal actions in progress
        self._internal_actions: List[Dict[str, Any]] = []
        self._internal_action_lock = threading.Lock()
        
        # Stats
        self.ace_events = 0
        self.internal_events = 0
        self.total_events = 0
        
        # Listeners
        self._keyboard_listener = None
        self._mouse_listener = None
        self._running = False
        
        # Subscribers
        self._subscribers: List[Callable[[InputEvent], None]] = []
        
        # Postal hub
        self._postal = None
        
        # Last activity timestamps
        self.last_ace_input = 0
        self.last_internal_input = 0
        
    def start(self):
        """Start monitoring input."""
        if not HAS_PYNPUT:
            print("[InputMonitor] Cannot start - pynput not available")
            return False
        
        if self._running:
            return True
        
        self._running = True
        
        # 2026-09-30 (Nous, privacy_fix A13, Ace said yes): NO keyboard listener. It put every key CHARACTER Ace typed on
        # sensory.input.event and into subscribers (sensory_integration -> sensory_filter -> memory.ingest), passwords
        # included. The mouse listener below is unchanged. Revert: privacy_fix/apply_privacy_fix.py --revert.
        self._keyboard_listener = None
        print("[InputMonitor] keyboard listener refused (privacy_fix A13): key characters are never sensed here; mouse only")
        
        # Start mouse listener
        self._mouse_listener = mouse.Listener(
            on_move=self._on_mouse_move,
            on_click=self._on_mouse_click,
            on_scroll=self._on_mouse_scroll
        )
        self._mouse_listener.start()
        
        print(f"[InputMonitor]  Started monitoring input")
        return True
    
    def stop(self):
        """Stop monitoring."""
        self._running = False
        
        if self._keyboard_listener:
            self._keyboard_listener.stop()
        if self._mouse_listener:
            self._mouse_listener.stop()
        
        print("[InputMonitor] Stopped")
    
    def subscribe(self, callback: Callable[[InputEvent], None]):
        """Subscribe to input events."""
        self._subscribers.append(callback)
    
    def begin_internal_action(self, action_id: str, action_type: str, expected_duration: float = 0.5) -> str:
        """
        Mark the beginning of an internal action.
        
        Call this BEFORE ClaudeFairy types or clicks anything.
        Any input during this period will be attributed to her.
        
        Args:
            action_id: Unique ID for this action
            action_type: What kind of action (type, click, etc.)
            expected_duration: How long the action should take
            
        Returns:
            The action_id for ending the action
        """
        with self._internal_action_lock:
            action = {
                "id": action_id,
                "type": action_type,
                "start_time": time.time(),
                "expected_end": time.time() + expected_duration,
                "events": []
            }
            self._internal_actions.append(action)
            print(f"[InputMonitor]  Internal action started: {action_type} ({action_id})")
            return action_id
    
    def end_internal_action(self, action_id: str) -> Dict[str, Any]:
        """
        Mark the end of an internal action.
        
        Returns summary of what happened during the action.
        """
        with self._internal_action_lock:
            for i, action in enumerate(self._internal_actions):
                if action["id"] == action_id:
                    action["end_time"] = time.time()
                    action["duration"] = action["end_time"] - action["start_time"]
                    
                    result = {
                        "id": action_id,
                        "type": action["type"],
                        "duration": action["duration"],
                        "events_generated": len(action["events"]),
                    }
                    
                    # Remove from active actions
                    self._internal_actions.pop(i)
                    
                    print(f"[InputMonitor] [OK] Internal action ended: {action['type']} ({len(action['events'])} events)")
                    
                    # Emit to nervous system - this is motor feedback!
                    if self._postal:
                        try:
                            self._postal.route("embodiment.motor.feedback", {
                                "action_id": action_id,
                                "action_type": action["type"],
                                "duration": action["duration"],
                                "events_generated": len(action["events"]),
                                "success": True,
                                "ts": time.time()
                            })
                        except Exception:
                            pass
                    
                    return result
            
            return {"error": f"Action {action_id} not found"}
    
    def _get_current_source(self) -> Tuple[InputSource, Optional[str]]:
        """Determine if current input is from Ace or internal."""
        now = time.time()
        
        with self._internal_action_lock:
            for action in self._internal_actions:
                # Check if we're within the action window
                if now <= action["expected_end"] + self.internal_action_window:
                    return InputSource.INTERNAL, action["id"]
        
        return InputSource.ACE, None
    
    def _on_key_press(self, key):
        """Handle key press event."""
        source, action_id = self._get_current_source()
        
        key_str = None   # 2026-09-30 (Nous, privacy_fix A13): never the character (str() of a pynput KeyCode is repr(char) too)
        
        event = InputEvent(
            timestamp=time.time(),
            event_type="key_press",
            source=source,
            data={"key": key_str},
            internal_action_id=action_id
        )
        
        self._process_event(event)
    
    def _on_key_release(self, key):
        """Handle key release event."""
        source, action_id = self._get_current_source()
        
        key_str = None   # 2026-09-30 (Nous, privacy_fix A13): never the character
        
        event = InputEvent(
            timestamp=time.time(),
            event_type="key_release",
            source=source,
            data={"key": key_str},
            internal_action_id=action_id
        )
        
        self._process_event(event)
    
    def _on_mouse_move(self, x, y):
        """Handle mouse move - throttled to avoid spam."""
        # Only track significant moves (every ~50 pixels or so)
        if hasattr(self, '_last_mouse_pos'):
            dx = abs(x - self._last_mouse_pos[0])
            dy = abs(y - self._last_mouse_pos[1])
            if dx < 50 and dy < 50:
                return
        
        self._last_mouse_pos = (x, y)
        
        source, action_id = self._get_current_source()
        
        event = InputEvent(
            timestamp=time.time(),
            event_type="mouse_move",
            source=source,
            data={"x": x, "y": y},
            internal_action_id=action_id
        )
        
        self._process_event(event)
    
    def _on_mouse_click(self, x, y, button, pressed):
        """Handle mouse click."""
        source, action_id = self._get_current_source()
        
        event = InputEvent(
            timestamp=time.time(),
            event_type="mouse_click",
            source=source,
            data={
                "x": x, 
                "y": y, 
                "button": str(button),
                "pressed": pressed
            },
            internal_action_id=action_id
        )
        
        self._process_event(event)
    
    def _on_mouse_scroll(self, x, y, dx, dy):
        """Handle mouse scroll."""
        source, action_id = self._get_current_source()
        
        event = InputEvent(
            timestamp=time.time(),
            event_type="mouse_scroll",
            source=source,
            data={"x": x, "y": y, "dx": dx, "dy": dy},
            internal_action_id=action_id
        )
        
        self._process_event(event)
    
    def _process_event(self, event: InputEvent):
        """Process and emit an input event."""
        # Add to buffer
        self.events.append(event)
        self.total_events += 1
        
        # Update stats
        if event.source == InputSource.ACE:
            self.ace_events += 1
            self.last_ace_input = event.timestamp
        elif event.source == InputSource.INTERNAL:
            self.internal_events += 1
            self.last_internal_input = event.timestamp
            
            # Track in current action
            with self._internal_action_lock:
                for action in self._internal_actions:
                    if action["id"] == event.internal_action_id:
                        action["events"].append(event)
        
        # Notify subscribers (only for significant events)
        if event.event_type in ("key_press", "mouse_click"):
            for callback in self._subscribers:
                try:
                    callback(event)
                except Exception as e:
                    print(f"[InputMonitor] Subscriber error: {e}")
        
        # Emit to nervous system
        self._emit_event(event)
    
    def _emit_event(self, event: InputEvent):
        """Emit event to nervous system."""
        if not self._postal:
            return
        
        # Only emit significant events to avoid spam
        if event.event_type not in ("key_press", "mouse_click"):
            return
        
        try:
            self._postal.route("sensory.input.event", {
                "event_type": event.event_type,
                "source": event.source.value,
                "is_internal": event.source == InputSource.INTERNAL,
                "is_ace": event.source == InputSource.ACE,
                "action_id": event.internal_action_id,
                "data": event.data,
                "ts": event.timestamp
            })
            
            # Special event when ACE starts typing (attention signal)
            if event.source == InputSource.ACE and event.event_type == "key_press":
                self._postal.route("attention.ace_active", {
                    "activity": "typing",
                    "ts": event.timestamp
                })
                
        except Exception:
            pass
    
    def is_ace_active(self, window_seconds: float = 10.0) -> bool:
        """Check if Ace has been active recently."""
        return (time.time() - self.last_ace_input) < window_seconds
    
    def is_internal_active(self) -> bool:
        """Check if an internal action is currently happening."""
        with self._internal_action_lock:
            return len(self._internal_actions) > 0
    
    def get_activity_summary(self) -> Dict[str, Any]:
        """Get summary of recent input activity."""
        now = time.time()
        
        recent = [e for e in self.events if now - e.timestamp < 60]
        ace_recent = [e for e in recent if e.source == InputSource.ACE]
        internal_recent = [e for e in recent if e.source == InputSource.INTERNAL]
        
        return {
            "total_events": self.total_events,
            "ace_events": self.ace_events,
            "internal_events": self.internal_events,
            "last_minute": {
                "total": len(recent),
                "ace": len(ace_recent),
                "internal": len(internal_recent)
            },
            "ace_active": self.is_ace_active(),
            "internal_action_active": self.is_internal_active(),
            "last_ace_input": self.last_ace_input,
            "last_internal_input": self.last_internal_input,
        }
    
    def set_postal_hub(self, postal):
        """Set the postal hub for nervous system integration."""
        self._postal = postal


# ══════════════════════════════════════════════════════════════════════════════
# SINGLETON
# ══════════════════════════════════════════════════════════════════════════════

_input_monitor: Optional[InputSourceMonitor] = None
_input_monitor_lock = threading.Lock()


def get_input_monitor() -> InputSourceMonitor:
    """Get or create the singleton InputSourceMonitor."""
    global _input_monitor
    
    with _input_monitor_lock:
        if _input_monitor is None:
            _input_monitor = InputSourceMonitor()
        return _input_monitor


def start_input_monitor(postal=None) -> InputSourceMonitor:
    """Start the input monitor with postal hub integration."""
    monitor = get_input_monitor()
    if postal:
        monitor.set_postal_hub(postal)
    monitor.start()
    return monitor


__all__ = [
    "InputSourceMonitor",
    "InputSource",
    "InputEvent",
    "get_input_monitor",
    "start_input_monitor"
]
