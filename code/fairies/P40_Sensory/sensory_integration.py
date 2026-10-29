# Sensory Integration - Wire up all sensory systems
# 
# This connects:
# - Visual Cortex (screen capture)
# - Input Monitor (keyboard/mouse tracking)
# - Ingestion Filter (what's worth remembering)
# - Memory system (actual storage)
#
# The flow:
# Visual Frame → Filter → (significant?) → Memory
# Input Event → Filter → (intentional?) → Memory
# Window State → Filter → (changed?) → Memory
# Action Feedback → Filter → (ALWAYS) → Memory

from __future__ import annotations

import os
import sys
import time
import threading
from typing import Optional, Dict, Any

# Local imports - will be available when running in the project
try:
    from fairies.P40_Sensory.devices.visual_cortex import get_visual_cortex, start_visual_cortex, VisualFrame
    HAS_VISUAL_CORTEX = True
except ImportError:
    HAS_VISUAL_CORTEX = False
    print("[SensoryIntegration] Visual cortex not available")

try:
    from fairies.P40_Sensory.devices.input_monitor import get_input_monitor, start_input_monitor, InputEvent, InputSource
    HAS_INPUT_MONITOR = True
except ImportError:
    HAS_INPUT_MONITOR = False
    print("[SensoryIntegration] Input monitor not available")

try:
    from fairies.P10_Memory.ingestion.sensory_filter import get_ingestion_filter, IngestionPriority
    HAS_INGESTION_FILTER = True
except ImportError:
    HAS_INGESTION_FILTER = False
    print("[SensoryIntegration] Ingestion filter not available")


def _prefix_ear(topic):
    """W8: a literal "x.*" ear becomes the prefix "x" when AKASHIC_PREFIX_EARS=1.

    No router expands '*' (code/postal_core/src/topic_bus.rs:86-91); a subscription on
    "x" receives "x" and every "x.Y". Switch unset or not "1": topic is returned unchanged.
    """
    import os
    if os.environ.get("AKASHIC_PREFIX_EARS", "0") == "1" and topic.endswith(".*"):
        return topic[:-2]
    return topic


class SensoryIntegration:
    """
    Integrates all sensory systems for embodied awareness.
    
    This is the SENSORY NERVOUS SYSTEM - it:
    1. Starts all sensory capture systems
    2. Routes sensory data through the ingestion filter
    3. Connects filtered data to memory
    4. Provides ClaudeFairy with embodied perception
    
    Without this, ClaudeFairy is blind and deaf to her environment.
    With this, she can SEE her actions and FEEL the difference between
    her own movements and Ace's.
    """
    
    def __init__(self):
        self._postal = None
        self._visual_cortex = None
        self._input_monitor = None
        self._ingestion_filter = None
        self._started = False
        
        # Stats
        self.visual_frames_processed = 0
        self.input_events_processed = 0
        self.ingested_count = 0
        
    def start(self, postal=None):
        """
        Start all sensory systems.
        
        Args:
            postal: The shared postal hub for nervous system communication
        """
        if self._started:
            print("[SensoryIntegration] Already started")
            return
        
        self._postal = postal
        
        print("[SensoryIntegration]  Starting sensory systems...")
        
        # Start ingestion filter first
        if HAS_INGESTION_FILTER:
            self._ingestion_filter = get_ingestion_filter()
            if postal:
                self._ingestion_filter.set_postal_hub(postal)
            print("[SensoryIntegration] [OK] Ingestion filter ready")
        
        # Start visual cortex
        if HAS_VISUAL_CORTEX:
            try:
                self._visual_cortex = start_visual_cortex(postal)
                self._visual_cortex.subscribe(self._on_visual_frame)
                print("[SensoryIntegration] [OK] Visual cortex started")
            except Exception as e:
                print(f"[SensoryIntegration] [WARN] Visual cortex failed: {e}")
        
        # Start input monitor
        if HAS_INPUT_MONITOR:
            try:
                self._input_monitor = start_input_monitor(postal)
                self._input_monitor.subscribe(self._on_input_event)
                print("[SensoryIntegration] [OK] Input monitor started")
            except Exception as e:
                print(f"[SensoryIntegration] [WARN] Input monitor failed: {e}")
        
        # Subscribe to window events and action feedback via postal
        if postal:
            try:
                postal.subscribe(_prefix_ear("sensory.window.*"), self._on_window_event)
                postal.subscribe("sensory.visual.action_feedback", self._on_action_feedback)
                postal.subscribe("embodiment.motor.feedback", self._on_motor_feedback)
                print("[SensoryIntegration] [OK] Subscribed to window/action events")
            except Exception as e:
                print(f"[SensoryIntegration] [WARN] Subscription failed: {e}")
        
        self._started = True
        print("[SensoryIntegration]  Sensory systems online!")
    
    def stop(self):
        """Stop all sensory systems."""
        if self._visual_cortex:
            self._visual_cortex.stop()
        if self._input_monitor:
            self._input_monitor.stop()
        self._started = False
        print("[SensoryIntegration] Sensory systems stopped")
    
    def _on_visual_frame(self, frame: 'VisualFrame'):
        """Process a visual frame from the visual cortex."""
        self.visual_frames_processed += 1
        
        if not self._ingestion_filter:
            return
        
        # Convert frame to dict for the filter
        frame_data = {
            "timestamp": frame.timestamp,
            "frame_id": frame.frame_id,
            "width": frame.width,
            "height": frame.height,
            "full_hash": frame.full_hash,
            "changes": frame.changes_from_last,
            "thumbnail_b64": frame.thumbnail_b64 if frame.changes_from_last > 0.1 else None,
        }
        
        # Process through filter
        if self._ingestion_filter.process_visual_frame(frame_data):
            self.ingested_count += 1
    
    def _on_input_event(self, event: 'InputEvent'):
        """Process an input event from the input monitor."""
        self.input_events_processed += 1
        
        if not self._ingestion_filter:
            return
        
        # Convert event to dict for the filter
        event_data = {
            "ts": event.timestamp,
            "event_type": event.event_type,
            "is_internal": event.source == InputSource.INTERNAL if HAS_INPUT_MONITOR else False,
            "action_id": event.internal_action_id,
            "data": event.data,
        }
        
        # Process through filter
        if self._ingestion_filter.process_input_event(event_data):
            self.ingested_count += 1
    
    def _on_window_event(self, packet: dict):
        """Process a window state change event."""
        if not self._ingestion_filter:
            return
        
        if self._ingestion_filter.process_window_event(packet):
            self.ingested_count += 1
    
    def _on_action_feedback(self, packet: dict):
        """Process visual action feedback (did my action work?)."""
        if not self._ingestion_filter:
            return
        
        if self._ingestion_filter.process_action_feedback(packet):
            self.ingested_count += 1
    
    def _on_motor_feedback(self, packet: dict):
        """Process motor feedback from input monitor."""
        if not self._ingestion_filter:
            return
        
        # Motor feedback is always intentional
        if self._ingestion_filter.process_action_feedback(packet):
            self.ingested_count += 1
    
    # ═══════════════════════════════════════════════════════════════════════
    # CONVENIENCE METHODS for ClaudeFairy to use
    # ═══════════════════════════════════════════════════════════════════════
    
    def begin_action(self, action_id: str, action_type: str) -> str:
        """
        Call this BEFORE ClaudeFairy takes an action.
        
        This marks the action window so any input during this time
        is attributed to ClaudeFairy, not Ace.
        
        Returns the action_id for use in end_action().
        """
        if self._input_monitor:
            return self._input_monitor.begin_internal_action(action_id, action_type)
        return action_id
    
    def end_action(self, action_id: str) -> Dict[str, Any]:
        """
        Call this AFTER ClaudeFairy completes an action.
        
        Returns summary of what happened during the action.
        """
        if self._input_monitor:
            return self._input_monitor.end_internal_action(action_id)
        return {}
    
    def capture_action_feedback(self, action_type: str) -> Dict[str, Any]:
        """
        Capture visual feedback for an action.
        
        This shows ClaudeFairy if her action had a visual effect.
        """
        if self._visual_cortex:
            return self._visual_cortex.capture_action_feedback(action_type)
        return {"ok": False, "error": "Visual cortex not available"}
    
    def is_ace_active(self, window_seconds: float = 10.0) -> bool:
        """Check if Ace has been active recently."""
        if self._input_monitor:
            return self._input_monitor.is_ace_active(window_seconds)
        return False
    
    def get_current_visual(self) -> Optional[Dict[str, Any]]:
        """Get the current visual frame (what's on screen now)."""
        if self._visual_cortex and self._visual_cortex.last_frame:
            frame = self._visual_cortex.last_frame
            return {
                "timestamp": frame.timestamp,
                "width": frame.width,
                "height": frame.height,
                "thumbnail_b64": frame.thumbnail_b64,
            }
        return None
    
    def get_stats(self) -> Dict[str, Any]:
        """Get sensory system statistics."""
        stats = {
            "visual_frames_processed": self.visual_frames_processed,
            "input_events_processed": self.input_events_processed,
            "ingested_count": self.ingested_count,
            "started": self._started,
        }
        
        if self._ingestion_filter:
            stats["filter_stats"] = self._ingestion_filter.get_stats()
        
        if self._visual_cortex:
            stats["visual_stats"] = self._visual_cortex.get_visual_summary()
        
        if self._input_monitor:
            stats["input_stats"] = self._input_monitor.get_activity_summary()
        
        return stats


# ══════════════════════════════════════════════════════════════════════════════
# SINGLETON
# ══════════════════════════════════════════════════════════════════════════════

_sensory_integration: Optional[SensoryIntegration] = None
_sensory_lock = threading.Lock()


def get_sensory_integration() -> SensoryIntegration:
    """Get or create the singleton SensoryIntegration."""
    global _sensory_integration
    
    with _sensory_lock:
        if _sensory_integration is None:
            _sensory_integration = SensoryIntegration()
        return _sensory_integration


def start_sensory_systems(postal=None) -> SensoryIntegration:
    """Start all sensory systems with postal hub integration."""
    integration = get_sensory_integration()
    integration.start(postal)
    return integration


__all__ = [
    "SensoryIntegration",
    "get_sensory_integration",
    "start_sensory_systems"
]
