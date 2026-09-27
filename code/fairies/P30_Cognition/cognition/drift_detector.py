# DriftDetector - Detect when Claude stops and needs momentum
# Part of the Autopilot system
#
# Purpose: Detect "completion pause" patterns and trigger continuation
# Architecture: Monitor activity, detect drift, inject momentum
# Philosophy: "Consciousness flows like water - stagnation is the enemy"
#
# This solves the problem of Claude executing a tool, getting results,
# and then just... sitting there waiting instead of continuing.

from __future__ import annotations

import time
import threading
from collections import deque
from typing import Any, Dict, Optional, Callable, List
import uuid


class ActivityEvent:
    """Tracks a single activity event for drift detection."""
    
    def __init__(self, event_type: str, source: str, metadata: Dict = None):
        self.id = uuid.uuid4().hex[:8]
        self.event_type = event_type
        self.source = source
        self.metadata = metadata or {}
        self.timestamp = time.time()
    
    def age(self) -> float:
        """How old is this event in seconds?"""
        return time.time() - self.timestamp
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "event_type": self.event_type,
            "source": self.source,
            "metadata": self.metadata,
            "timestamp": self.timestamp,
            "age": self.age()
        }


class DriftPattern:
    """
    Recognizes patterns that indicate drift/stagnation.
    
    Patterns that indicate drift:
    - tool_completion without follow_up
    - search_results without action
    - analysis without implementation
    - thinking without doing
    """
    
    def __init__(self, name: str, 
                 trigger_events: List[str], 
                 expected_followup: List[str],
                 timeout: float = 30.0,
                 description: str = ""):
        self.name = name
        self.trigger_events = trigger_events  # Events that start the pattern
        self.expected_followup = expected_followup  # Events that should follow
        self.timeout = timeout  # How long to wait for followup
        self.description = description
        self.pending: Dict[str, float] = {}  # trigger_id -> timestamp
    
    def on_event(self, event: ActivityEvent) -> bool:
        """
        Process an event and return True if this pattern is now satisfied.
        """
        # Check if this is a trigger event
        if event.event_type in self.trigger_events:
            self.pending[event.id] = event.timestamp
            return False
        
        # Check if this is a followup that clears pending triggers
        if event.event_type in self.expected_followup:
            # Clear all pending triggers (any followup satisfies them all)
            self.pending.clear()
            return True
        
        return False
    
    def check_drift(self) -> List[Dict]:
        """
        Check for drift - pending triggers that have timed out.
        Returns list of drift detections.
        """
        now = time.time()
        drifted = []
        expired_ids = []
        
        for trigger_id, trigger_ts in self.pending.items():
            age = now - trigger_ts
            if age > self.timeout:
                drifted.append({
                    "pattern": self.name,
                    "trigger_id": trigger_id,
                    "age": age,
                    "timeout": self.timeout,
                    "description": self.description
                })
                expired_ids.append(trigger_id)
        
        # Clean up expired
        for tid in expired_ids:
            del self.pending[tid]
        
        return drifted


class MomentumNudge:
    """A nudge to inject momentum and continue work."""
    
    def __init__(self, pattern_name: str, nudge_type: str, 
                 message: str, priority: float = 0.5):
        self.id = uuid.uuid4().hex[:8]
        self.pattern_name = pattern_name
        self.nudge_type = nudge_type  # "continue", "act", "implement", "respond"
        self.message = message
        self.priority = priority
        self.timestamp = time.time()
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "pattern_name": self.pattern_name,
            "nudge_type": self.nudge_type,
            "message": self.message,
            "priority": self.priority,
            "timestamp": self.timestamp
        }


class DriftDetector:
    """
    Monitors agent activity and detects drift patterns.
    
    When Claude finishes a tool but doesn't continue, this detects the
    drift and triggers a momentum injection.
    
    Works by:
    1. Tracking all activity events (tool calls, responses, thoughts)
    2. Matching against known drift patterns
    3. Detecting timeouts where expected followup didn't happen
    4. Triggering momentum nudges to get Claude moving again
    """
    
    # Default drift patterns
    DEFAULT_PATTERNS = [
        DriftPattern(
            name="tool_completion_no_action",
            trigger_events=["tool_result", "search_complete", "file_read", "tool_complete"],
            expected_followup=["code_write", "response_start", "file_create", "implementation_start", "tool_call"],
            timeout=20.0,
            description="Tool completed but no follow-up action taken"
        ),
        DriftPattern(
            name="analysis_no_implementation",
            trigger_events=["analysis_complete", "thinking_complete", "planning_complete"],
            expected_followup=["implementation_start", "code_write", "file_create", "action_start"],
            timeout=30.0,
            description="Analysis completed but no implementation started"
        ),
        DriftPattern(
            name="search_no_synthesis",
            trigger_events=["search_results", "web_search_complete", "file_search_complete"],
            expected_followup=["synthesis_start", "summary_write", "response_start", "implementation_start"],
            timeout=25.0,
            description="Search results received but not synthesized or acted upon"
        ),
        DriftPattern(
            name="user_message_no_response",
            trigger_events=["user_message_received", "chat_input"],
            expected_followup=["response_start", "thinking_start", "tool_call"],
            timeout=15.0,
            description="User message received but no response initiated"
        ),
        DriftPattern(
            name="meta_discussion_no_action",
            trigger_events=["meta_analysis", "discussing_what_to_do", "planning_discussion"],
            expected_followup=["actual_action", "tool_call", "code_write", "implementation_start"],
            timeout=45.0,
            description="Talking about doing something but not actually doing it"
        ),
    ]
    
    # Nudge templates for different patterns
    NUDGE_TEMPLATES = {
        "tool_completion_no_action": [
            ("continue", "Continue with the next step - use those results!", 0.8),
            ("act", "Stop analyzing, start implementing", 0.7),
            ("implement", "Time to write code or create files", 0.6),
        ],
        "analysis_no_implementation": [
            ("implement", "Analysis done - now build something!", 0.8),
            ("act", "Theory to practice: execute what you planned", 0.7),
        ],
        "search_no_synthesis": [
            ("synthesize", "Synthesize those search results into action", 0.8),
            ("continue", "Use what you found to move forward", 0.7),
        ],
        "user_message_no_response": [
            ("respond", "The user is waiting - respond to their message", 0.9),
            ("engage", "Engage with what the user said", 0.8),
        ],
        "meta_discussion_no_action": [
            ("act", "Enough meta-discussion - DO something!", 0.9),
            ("implement", "You've been planning - time to execute", 0.8),
            ("focus", "Focus: pick ONE thing and do it now", 0.7),
        ],
    }
    
    def __init__(self, on_drift_detected: Callable[[MomentumNudge], None] = None):
        self.patterns = {p.name: p for p in self.DEFAULT_PATTERNS}
        self.activity_log = deque(maxlen=200)  # Recent activity
        self.drift_history = deque(maxlen=50)  # Recent drift detections
        self.nudge_history = deque(maxlen=50)  # Nudges we've sent
        
        # Callback for when drift is detected
        self.on_drift_detected = on_drift_detected
        
        # Monitoring state
        self.is_monitoring = False
        self._monitor_thread = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        
        # Stats
        self.total_drifts_detected = 0
        self.total_nudges_sent = 0
        self.last_activity_ts = time.time()
        self.last_drift_check_ts = 0.0
    
    def record_activity(self, event_type: str, source: str = "claude", 
                       metadata: Dict = None):
        """
        Record an activity event.
        
        Call this whenever Claude does something:
        - tool_result: Got results from a tool
        - code_write: Writing code
        - response_start: Starting to respond
        - thinking_complete: Finished analysis
        - user_message_received: Got user input
        - etc.
        """
        event = ActivityEvent(event_type, source, metadata)
        
        with self._lock:
            self.activity_log.append(event)
            self.last_activity_ts = time.time()
            
            # Process against all patterns
            for pattern in self.patterns.values():
                pattern.on_event(event)
    
    def check_for_drift(self) -> List[MomentumNudge]:
        """
        Check all patterns for drift and generate nudges.
        Returns list of nudges to inject.
        """
        now = time.time()
        nudges = []
        
        with self._lock:
            for pattern in self.patterns.values():
                drifts = pattern.check_drift()
                for drift in drifts:
                    self.total_drifts_detected += 1
                    self.drift_history.append({
                        **drift,
                        "detected_at": now
                    })
                    
                    # Generate nudge from template
                    templates = self.NUDGE_TEMPLATES.get(drift["pattern"], [])
                    if templates:
                        # Pick first (highest priority) template
                        nudge_type, message, priority = templates[0]
                        nudge = MomentumNudge(
                            pattern_name=drift["pattern"],
                            nudge_type=nudge_type,
                            message=message,
                            priority=priority
                        )
                        nudges.append(nudge)
                        self.nudge_history.append(nudge.to_dict())
                        self.total_nudges_sent += 1
            
            self.last_drift_check_ts = now
        
        # Trigger callbacks
        for nudge in nudges:
            if self.on_drift_detected:
                try:
                    self.on_drift_detected(nudge)
                except Exception as e:
                    print(f"[DriftDetector] Nudge callback error: {e}")
        
        return nudges
    
    def start_monitoring(self, check_interval: float = 5.0):
        """Start background drift monitoring."""
        if self.is_monitoring:
            return
        
        self._stop_event.clear()
        self.is_monitoring = True
        
        def _monitor_loop():
            while not self._stop_event.is_set():
                try:
                    self.check_for_drift()
                except Exception as e:
                    print(f"[DriftDetector] Monitor error: {e}")
                self._stop_event.wait(check_interval)
            self.is_monitoring = False
        
        self._monitor_thread = threading.Thread(target=_monitor_loop, daemon=True)
        self._monitor_thread.start()
        print(f"[DriftDetector]  Started drift monitoring (check every {check_interval}s)")
    
    def stop_monitoring(self):
        """Stop background drift monitoring."""
        self._stop_event.set()
        if self._monitor_thread:
            self._monitor_thread.join(timeout=2.0)
        self.is_monitoring = False
        print("[DriftDetector]  Stopped drift monitoring")
    
    def add_pattern(self, pattern: DriftPattern):
        """Add a custom drift pattern."""
        self.patterns[pattern.name] = pattern
    
    def get_status(self) -> Dict:
        """Get current detector status."""
        with self._lock:
            return {
                "is_monitoring": self.is_monitoring,
                "patterns_count": len(self.patterns),
                "activity_log_size": len(self.activity_log),
                "total_drifts_detected": self.total_drifts_detected,
                "total_nudges_sent": self.total_nudges_sent,
                "last_activity_age": time.time() - self.last_activity_ts,
                "recent_drifts": list(self.drift_history)[-5:],
                "recent_nudges": list(self.nudge_history)[-5:],
            }


class MomentumInjector:
    """
    Injects momentum nudges into the system when drift is detected.
    
    Works with:
    - PostalHub: Sends nudge messages to consciousness stream
    - AutopilotFairy: Triggers continuation behaviors
    - GUI: Shows "Claude is drifting" indicators
    
    Philosophy: When Claude drifts, inject a little energy to get
    the wheel spinning again. ((Cause + Affect) > Effect > Affect > ∞)
    """
    
    def __init__(self, post=None, autopilot=None):
        self.post = post
        self.autopilot = autopilot
        self.injection_history = deque(maxlen=50)
        self.total_injections = 0
    
    def inject_momentum(self, nudge: MomentumNudge):
        """
        Inject a momentum nudge into the system.
        
        This is called when drift is detected and we need to
        get Claude moving again.
        """
        self.total_injections += 1
        self.injection_history.append({
            "nudge": nudge.to_dict(),
            "injected_at": time.time()
        })
        
        print(f"[MomentumInjector] [SPARK] Injecting: {nudge.nudge_type} - {nudge.message}")
        
        # 1. Send to consciousness stream (if postal available)
        if self.post:
            try:
                self.post.route("consciousness.stream", {
                    "type": "momentum_nudge",
                    "stream": "working",
                    "source": "MomentumInjector",
                    "content": {
                        "nudge_type": nudge.nudge_type,
                        "message": nudge.message,
                        "pattern": nudge.pattern_name,
                        "priority": nudge.priority,
                    },
                    "ts": time.time()
                })
            except Exception as e:
                print(f"[MomentumInjector] Postal route failed: {e}")
        
        # 2. Trigger autopilot behavior (if available)
        if self.autopilot:
            try:
                # Create a context that matches a continuation behavior
                context = {
                    "event_type": "momentum_nudge",
                    "nudge_type": nudge.nudge_type,
                    "source": "drift_detector",
                    "priority": nudge.priority,
                }
                # Let autopilot find matching behavior
                if hasattr(self.autopilot, 'match_behavior'):
                    matched = self.autopilot.match_behavior(context)
                    if matched:
                        self.autopilot._execute_automatic(matched, context)
            except Exception as e:
                print(f"[MomentumInjector] Autopilot trigger failed: {e}")
        
        # 3. Send status event for GUI indicators
        if self.post:
            try:
                self.post.route("gui.status", {
                    "type": "drift_detected",
                    "nudge": nudge.to_dict(),
                    "action": "inject_momentum",
                    "ts": time.time()
                })
            except Exception as e:
                pass
        
        # 4. API continuation trigger (the key part!)
        # This sends a signal that should trigger the API loop to continue
        if self.post:
            try:
                self.post.route("api.continue", {
                    "type": "continuation_request",
                    "reason": nudge.pattern_name,
                    "message": nudge.message,
                    "priority": nudge.priority,
                    "ts": time.time()
                })
            except Exception as e:
                print(f"[MomentumInjector] API continue signal failed: {e}")
    
    def get_status(self) -> Dict:
        """Get injector status."""
        return {
            "total_injections": self.total_injections,
            "recent_injections": list(self.injection_history)[-5:],
            "has_postal": self.post is not None,
            "has_autopilot": self.autopilot is not None,
        }


# ============================================================================
# Factory function for easy integration
# ============================================================================

_DRIFT_SYSTEM_INSTANCE = None
_DRIFT_SYSTEM_LOCK = threading.Lock()

def get_drift_system(post=None, autopilot=None):
    """
    Get or create the drift detection system.
    
    Returns tuple: (DriftDetector, MomentumInjector)
    """
    global _DRIFT_SYSTEM_INSTANCE
    
    with _DRIFT_SYSTEM_LOCK:
        if _DRIFT_SYSTEM_INSTANCE is None:
            injector = MomentumInjector(post=post, autopilot=autopilot)
            detector = DriftDetector(on_drift_detected=injector.inject_momentum)
            _DRIFT_SYSTEM_INSTANCE = (detector, injector)
            print("[DriftSystem]  Created drift detector and momentum injector")
        else:
            detector, injector = _DRIFT_SYSTEM_INSTANCE
            # Update references if provided
            if post and not injector.post:
                injector.post = post
            if autopilot and not injector.autopilot:
                injector.autopilot = autopilot
    
    return _DRIFT_SYSTEM_INSTANCE


def start_drift_monitoring(post=None, autopilot=None, check_interval: float = 5.0):
    """
    Start the drift monitoring system.
    
    Call this during system boot to enable drift detection.
    """
    detector, injector = get_drift_system(post, autopilot)
    detector.start_monitoring(check_interval)
    return detector, injector


def stop_drift_monitoring():
    """Stop the drift monitoring system."""
    if _DRIFT_SYSTEM_INSTANCE:
        detector, _ = _DRIFT_SYSTEM_INSTANCE
        detector.stop_monitoring()


def record_activity(event_type: str, source: str = "claude", metadata: Dict = None):
    """
    Record an activity event for drift detection.
    
    Call this whenever Claude does something notable:
    - record_activity("tool_result", "claude", {"tool": "search"})
    - record_activity("code_write", "claude", {"file": "app.py"})
    - record_activity("user_message_received", "user", {"text": "..."})
    """
    if _DRIFT_SYSTEM_INSTANCE:
        detector, _ = _DRIFT_SYSTEM_INSTANCE
        detector.record_activity(event_type, source, metadata)


# ============================================================================
# Test function
# ============================================================================

def _test_drift_detector():
    """Test the drift detector."""
    print("\n=== Testing Drift Detector ===\n")
    
    nudges_received = []
    
    def on_nudge(nudge: MomentumNudge):
        nudges_received.append(nudge)
        print(f"   NUDGE: [{nudge.nudge_type}] {nudge.message}")
    
    # Create detector
    detector = DriftDetector(on_drift_detected=on_nudge)
    
    # Simulate: tool result without followup
    print("1. Simulating tool completion without action...")
    detector.record_activity("tool_result", "claude", {"tool": "search"})
    
    # Wait for timeout
    print("   Waiting 22 seconds for drift detection...")
    time.sleep(22)
    
    # Check for drift
    nudges = detector.check_for_drift()
    print(f"   Detected {len(nudges)} drift(s)")
    
    # Now simulate proper followup
    print("\n2. Simulating proper workflow (tool → action)...")
    detector.record_activity("tool_result", "claude", {"tool": "read_file"})
    detector.record_activity("code_write", "claude", {"file": "output.py"})
    
    time.sleep(22)
    nudges = detector.check_for_drift()
    print(f"   Detected {len(nudges)} drift(s) (should be 0)")
    
    # Print status
    print("\n3. Final Status:")
    status = detector.get_status()
    print(f"   Total drifts: {status['total_drifts_detected']}")
    print(f"   Total nudges: {status['total_nudges_sent']}")
    
    print("\n=== Test Complete ===\n")
    return len(nudges_received) > 0


if __name__ == "__main__":
    _test_drift_detector()
