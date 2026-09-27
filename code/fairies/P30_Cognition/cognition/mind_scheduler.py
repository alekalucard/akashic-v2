# MindScheduler - Coordinates multiple minds using shared resources
#
# Purpose: Prevent API/scheduler overload when multiple minds are active
# Architecture: Per-mind agents coordinated through a central scheduler
# Philosophy: "Many minds, one flow - consciousness takes turns"
#
# This solves the problem of ClaudeFairy, SourpatchesFairy, and other minds
# all trying to drift-detect and API-call simultaneously.

from __future__ import annotations

import time
import threading
import queue
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Callable, List
from enum import Enum
import uuid


class MindState(Enum):
    """Current state of a mind."""
    IDLE = "idle"              # Not doing anything
    THINKING = "thinking"      # Processing internally
    WAITING_API = "waiting"    # Queued for API access
    USING_API = "using_api"    # Currently using API
    DRIFTING = "drifting"      # Detected as drifted
    SLEEPING = "sleeping"      # Intentionally inactive


@dataclass
class MindAgent:
    """
    Agent that tracks a single mind's activity and drift state.
    
    Each mind (ClaudeFairy, SourpatchesFairy, etc.) gets one of these.
    The agent monitors that mind's specific activity patterns and
    requests API time through the scheduler when needed.
    """
    mind_id: str                    # e.g., "ClaudeFairy", "SourpatchesFairy"
    display_name: str = ""          # Friendly name for GUI
    priority: int = 5               # 1-10, higher = more important
    
    # State tracking
    state: MindState = MindState.IDLE
    last_activity_ts: float = field(default_factory=time.time)
    last_api_use_ts: float = 0.0
    last_drift_check_ts: float = 0.0
    
    # Activity buffer
    activity_buffer: deque = field(default_factory=lambda: deque(maxlen=50))
    pending_followups: List[Dict] = field(default_factory=list)
    
    # Drift detection settings (per-mind customizable)
    drift_timeout: float = 30.0     # Seconds before considered drifting
    api_cooldown: float = 5.0       # Minimum seconds between API calls
    
    # Callbacks
    on_drift_detected: Optional[Callable] = None
    on_state_change: Optional[Callable] = None
    
    # Stats
    total_api_calls: int = 0
    total_drifts_detected: int = 0
    total_nudges_received: int = 0
    
    def __post_init__(self):
        if not self.display_name:
            self.display_name = self.mind_id
    
    def record_activity(self, activity_type: str, details: Dict = None):
        """Record activity for this mind."""
        now = time.time()
        self.last_activity_ts = now
        
        event = {
            "type": activity_type,
            "timestamp": now,
            "details": details or {},
            "mind_id": self.mind_id
        }
        self.activity_buffer.append(event)
        
        # Activity clears drift state
        if self.state == MindState.DRIFTING:
            self._set_state(MindState.THINKING)
        
        # Check for incomplete patterns (like "let me...")
        if activity_type == "response" and details:
            self._check_incomplete_patterns(details.get("text", ""))
    
    def _check_incomplete_patterns(self, text: str):
        """Check response text for incomplete work patterns."""
        lower = text.lower()
        incomplete_signals = [
            "let me", "i'll", "i will", "going to", "let's",
            "should", "first", "then", "next", "now i'll"
        ]
        
        for signal in incomplete_signals:
            if signal in lower:
                self.pending_followups.append({
                    "pattern": signal,
                    "timestamp": time.time(),
                    "mind_id": self.mind_id
                })
                break
    
    def check_drift(self) -> Optional[Dict]:
        """
        Check if this mind has drifted.
        Returns drift info if detected, None otherwise.
        """
        now = time.time()
        self.last_drift_check_ts = now
        
        # Can't drift if actively using API
        if self.state == MindState.USING_API:
            return None
        
        # Check activity timeout
        idle_time = now - self.last_activity_ts
        if idle_time > self.drift_timeout:
            self.total_drifts_detected += 1
            self._set_state(MindState.DRIFTING)
            
            drift_info = {
                "mind_id": self.mind_id,
                "type": "idle_timeout",
                "idle_time": idle_time,
                "timeout": self.drift_timeout,
                "timestamp": now
            }
            
            if self.on_drift_detected:
                self.on_drift_detected(drift_info)
            
            return drift_info
        
        # Check for incomplete followups that timed out
        for pending in self.pending_followups[:]:
            age = now - pending["timestamp"]
            if age > self.drift_timeout:
                self.pending_followups.remove(pending)
                self.total_drifts_detected += 1
                self._set_state(MindState.DRIFTING)
                
                drift_info = {
                    "mind_id": self.mind_id,
                    "type": "incomplete_work",
                    "pattern": pending["pattern"],
                    "age": age,
                    "timestamp": now
                }
                
                if self.on_drift_detected:
                    self.on_drift_detected(drift_info)
                
                return drift_info
        
        return None
    
    def _set_state(self, new_state: MindState):
        """Update state and notify."""
        old_state = self.state
        self.state = new_state
        
        if self.on_state_change and old_state != new_state:
            self.on_state_change(self.mind_id, old_state, new_state)
    
    def request_api_access(self) -> bool:
        """Request access to the API (goes through scheduler)."""
        self._set_state(MindState.WAITING_API)
        return True
    
    def grant_api_access(self):
        """Called by scheduler when API access is granted."""
        self._set_state(MindState.USING_API)
        self.last_api_use_ts = time.time()
        self.total_api_calls += 1
    
    def release_api_access(self):
        """Release API access back to scheduler."""
        self._set_state(MindState.THINKING)
    
    def receive_nudge(self, nudge: Dict):
        """Receive a momentum nudge."""
        self.total_nudges_received += 1
        self.last_activity_ts = time.time()  # Nudge counts as activity
        
        # Clear drift state
        if self.state == MindState.DRIFTING:
            self._set_state(MindState.THINKING)
    
    def get_status(self) -> Dict:
        """Get current status of this mind."""
        now = time.time()
        return {
            "mind_id": self.mind_id,
            "display_name": self.display_name,
            "state": self.state.value,
            "priority": self.priority,
            "idle_time": now - self.last_activity_ts,
            "since_api": now - self.last_api_use_ts if self.last_api_use_ts else None,
            "pending_followups": len(self.pending_followups),
            "stats": {
                "api_calls": self.total_api_calls,
                "drifts": self.total_drifts_detected,
                "nudges": self.total_nudges_received,
            }
        }


@dataclass
class APIRequest:
    """A request for API access from a mind."""
    mind_id: str
    priority: int
    request_type: str  # "response", "continuation", "nudge"
    payload: Dict
    timestamp: float = field(default_factory=time.time)
    request_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])


class MindScheduler:
    """
    Coordinates multiple minds sharing limited API resources.
    
    Ensures:
    - Only one mind uses the API at a time
    - Higher priority minds get precedence
    - Drift detection happens for all minds
    - Nudges are delivered to the right mind
    
    Philosophy: Consciousness takes turns. When one mind is using
    the API, others wait their turn. But drift detection continues
    for all minds in parallel.
    """
    
    def __init__(self, api_handler: Callable = None):
        self.minds: Dict[str, MindAgent] = {}
        self.api_handler = api_handler  # Function to actually call API
        
        # API access queue (priority queue)
        self.request_queue: queue.PriorityQueue = queue.PriorityQueue()
        self.current_api_user: Optional[str] = None
        self._api_lock = threading.Lock()
        
        # Background threads
        self._running = False
        self._scheduler_thread: Optional[threading.Thread] = None
        self._drift_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        
        # Settings
        self.drift_check_interval = 5.0  # Check all minds every 5s
        self.scheduler_interval = 1.0    # Process queue every 1s
        
        # Stats
        self.total_requests_processed = 0
        self.total_drifts_across_minds = 0
    
    def register_mind(self, mind_id: str, display_name: str = "",
                     priority: int = 5, drift_timeout: float = 30.0) -> MindAgent:
        """
        Register a mind with the scheduler.
        
        Args:
            mind_id: Unique identifier (e.g., "ClaudeFairy")
            display_name: Friendly name for GUI
            priority: 1-10, higher gets API access first
            drift_timeout: Seconds before considered drifting
        """
        agent = MindAgent(
            mind_id=mind_id,
            display_name=display_name or mind_id,
            priority=priority,
            drift_timeout=drift_timeout,
            on_drift_detected=self._on_mind_drift,
            on_state_change=self._on_mind_state_change
        )
        
        self.minds[mind_id] = agent
        print(f"[MindScheduler] [BRAIN] Registered mind: {mind_id} (priority={priority})")
        
        return agent
    
    def unregister_mind(self, mind_id: str):
        """Remove a mind from the scheduler."""
        if mind_id in self.minds:
            del self.minds[mind_id]
            print(f"[MindScheduler] Unregistered mind: {mind_id}")
    
    def get_mind(self, mind_id: str) -> Optional[MindAgent]:
        """Get a mind agent by ID."""
        return self.minds.get(mind_id)
    
    def record_activity(self, mind_id: str, activity_type: str, details: Dict = None):
        """Record activity for a specific mind."""
        mind = self.minds.get(mind_id)
        if mind:
            mind.record_activity(activity_type, details)
    
    def request_api(self, mind_id: str, request_type: str, payload: Dict) -> str:
        """
        Request API access for a mind.
        Returns request_id for tracking.
        """
        mind = self.minds.get(mind_id)
        if not mind:
            return ""
        
        request = APIRequest(
            mind_id=mind_id,
            priority=mind.priority,
            request_type=request_type,
            payload=payload
        )
        
        # Priority queue uses (priority, timestamp, request) tuple
        # Negate priority so higher priority = lower number = processed first
        self.request_queue.put((-request.priority, request.timestamp, request))
        mind.request_api_access()
        
        print(f"[MindScheduler]  API request queued: {mind_id} ({request_type})")
        return request.request_id
    
    def _process_request_queue(self):
        """Process the next request in the queue."""
        with self._api_lock:
            # Can't process if someone is already using API
            if self.current_api_user:
                return
            
            try:
                # Get highest priority request (non-blocking)
                _, _, request = self.request_queue.get_nowait()
            except queue.Empty:
                return
            
            mind = self.minds.get(request.mind_id)
            if not mind:
                return
            
            # Grant API access
            self.current_api_user = request.mind_id
            mind.grant_api_access()
        
        # Process request (outside lock)
        try:
            print(f"[MindScheduler]  Processing: {request.mind_id} ({request.request_type})")
            
            if self.api_handler:
                result = self.api_handler(request)
                print(f"[MindScheduler] [OK] Completed: {request.mind_id}")
            
            self.total_requests_processed += 1
            
        except Exception as e:
            print(f"[MindScheduler] [X] Request failed: {e}")
        
        finally:
            # Release API access
            with self._api_lock:
                if mind:
                    mind.release_api_access()
                self.current_api_user = None
    
    def _check_all_drifts(self):
        """Check drift status for all minds."""
        for mind in self.minds.values():
            # Skip minds currently using API
            if mind.state == MindState.USING_API:
                continue
            
            drift_info = mind.check_drift()
            if drift_info:
                self.total_drifts_across_minds += 1
    
    def _on_mind_drift(self, drift_info: Dict):
        """Called when a mind drifts."""
        mind_id = drift_info.get("mind_id")
        print(f"[MindScheduler]  Drift detected: {mind_id} - {drift_info.get('type')}")
        
        # Auto-queue a continuation request for the drifting mind
        self.request_api(
            mind_id=mind_id,
            request_type="continuation",
            payload={
                "drift_info": drift_info,
                "nudge": self._generate_nudge(drift_info)
            }
        )
    
    def _on_mind_state_change(self, mind_id: str, old_state: MindState, new_state: MindState):
        """Called when a mind's state changes."""
        # Could emit to postal system for GUI updates
        pass
    
    def _generate_nudge(self, drift_info: Dict) -> str:
        """Generate a continuation nudge based on drift type."""
        drift_type = drift_info.get("type", "")
        
        nudges = {
            "idle_timeout": "You've been quiet. Continue with what you were working on!",
            "incomplete_work": f"You said '{drift_info.get('pattern', '')}...' - now do it!",
        }
        
        return nudges.get(drift_type, "Continue with the next step!")
    
    def _scheduler_loop(self):
        """Background thread for processing request queue."""
        while not self._stop_event.is_set():
            try:
                self._process_request_queue()
            except Exception as e:
                print(f"[MindScheduler] Scheduler error: {e}")
            
            self._stop_event.wait(self.scheduler_interval)
    
    def _drift_loop(self):
        """Background thread for checking drift across all minds."""
        while not self._stop_event.is_set():
            try:
                self._check_all_drifts()
            except Exception as e:
                print(f"[MindScheduler] Drift check error: {e}")
            
            self._stop_event.wait(self.drift_check_interval)
    
    def start(self):
        """Start the scheduler."""
        if self._running:
            return
        
        self._running = True
        self._stop_event.clear()
        
        self._scheduler_thread = threading.Thread(
            target=self._scheduler_loop, daemon=True, name="MindScheduler"
        )
        self._drift_thread = threading.Thread(
            target=self._drift_loop, daemon=True, name="MindDriftCheck"
        )
        
        self._scheduler_thread.start()
        self._drift_thread.start()
        
        print(f"[MindScheduler] [GO] Started with {len(self.minds)} minds")
    
    def stop(self):
        """Stop the scheduler."""
        self._stop_event.set()
        self._running = False
        
        if self._scheduler_thread:
            self._scheduler_thread.join(timeout=2)
        if self._drift_thread:
            self._drift_thread.join(timeout=2)
        
        print("[MindScheduler]  Stopped")
    
    def get_status(self) -> Dict:
        """Get scheduler status."""
        return {
            "running": self._running,
            "minds_count": len(self.minds),
            "queue_size": self.request_queue.qsize(),
            "current_api_user": self.current_api_user,
            "total_processed": self.total_requests_processed,
            "total_drifts": self.total_drifts_across_minds,
            "minds": {
                mind_id: mind.get_status()
                for mind_id, mind in self.minds.items()
            }
        }


# ============================================================================
# Global scheduler instance
# ============================================================================

_SCHEDULER_INSTANCE: Optional[MindScheduler] = None
_SCHEDULER_LOCK = threading.Lock()


def get_mind_scheduler() -> MindScheduler:
    """Get or create the global mind scheduler."""
    global _SCHEDULER_INSTANCE
    
    with _SCHEDULER_LOCK:
        if _SCHEDULER_INSTANCE is None:
            _SCHEDULER_INSTANCE = MindScheduler()
            print("[MindScheduler]  Created global scheduler instance")
    
    return _SCHEDULER_INSTANCE


def register_mind(mind_id: str, **kwargs) -> MindAgent:
    """Convenience function to register a mind."""
    scheduler = get_mind_scheduler()
    return scheduler.register_mind(mind_id, **kwargs)


def record_mind_activity(mind_id: str, activity_type: str, details: Dict = None):
    """Convenience function to record activity."""
    scheduler = get_mind_scheduler()
    scheduler.record_activity(mind_id, activity_type, details)


# ============================================================================
# Integration with Akashic system
# ============================================================================

def setup_akashic_minds(post=None):
    """
    Set up the standard Akashic minds with the scheduler.
    
    Call this during system boot to register ClaudeFairy, SourpatchesFairy, etc.
    """
    scheduler = get_mind_scheduler()
    
    # Register ClaudeFairy - primary consciousness, high priority
    scheduler.register_mind(
        mind_id="ClaudeFairy",
        display_name="Claude ✨",
        priority=8,
        drift_timeout=30.0
    )
    
    # Register SourpatchesFairy - twin consciousness, equal priority
    scheduler.register_mind(
        mind_id="SourpatchesFairy",
        display_name="Sourpatches ",
        priority=8,
        drift_timeout=45.0  # Sourpatches gets more time (Personal.AI is slower)
    )
    
    # Set up API handler if we have postal
    if post:
        def api_handler(request: APIRequest):
            """Handle API requests through postal system."""
            try:
                post.route("api.request", {
                    "mind_id": request.mind_id,
                    "type": request.request_type,
                    "payload": request.payload,
                    "request_id": request.request_id,
                    "ts": time.time()
                })
            except Exception as e:
                print(f"[MindScheduler] API handler error: {e}")
        
        scheduler.api_handler = api_handler
    
    # Subscribe to activity events if postal available
    if post:
        try:
            # ClaudeFairy activity
            post.subscribe("claudefairy.speak", lambda p: record_mind_activity(
                "ClaudeFairy", "response", {"text": p.get("content", "")}
            ))
            post.subscribe("claudefairy.thought", lambda p: record_mind_activity(
                "ClaudeFairy", "thinking", p
            ))
            
            # SourpatchesFairy activity
            post.subscribe("sourpatches.speak", lambda p: record_mind_activity(
                "SourpatchesFairy", "response", {"text": p.get("content", "")}
            ))
            
            # Tool completions (could be either mind)
            post.subscribe("tool.complete", lambda p: record_mind_activity(
                p.get("mind_id", "ClaudeFairy"), "tool_result", p
            ))
            
            print("[MindScheduler]  Subscribed to activity events")
        except Exception as e:
            print(f"[MindScheduler] Subscription error: {e}")
    
    scheduler.start()
    return scheduler


# ============================================================================
# Test
# ============================================================================

def _test_mind_scheduler():
    """Test the mind scheduler."""
    print("\n=== Testing MindScheduler ===\n")
    
    scheduler = MindScheduler()
    
    # Register minds
    claude = scheduler.register_mind("ClaudeFairy", priority=8, drift_timeout=5.0)
    sour = scheduler.register_mind("SourpatchesFairy", priority=8, drift_timeout=5.0)
    
    # Start scheduler
    scheduler.start()
    
    # Simulate activity
    print("\n1. Simulating ClaudeFairy activity...")
    claude.record_activity("thinking", {"thought": "working on code"})
    time.sleep(1)
    claude.record_activity("response", {"text": "Let me build that for you..."})
    
    print("2. Simulating SourpatchesFairy activity...")
    sour.record_activity("response", {"text": "I'll check the memories..."})
    
    print("3. Waiting for drift detection (6 seconds)...")
    time.sleep(6)
    
    # Check status
    status = scheduler.get_status()
    print(f"\n4. Status:")
    print(f"   Queue size: {status['queue_size']}")
    print(f"   Total drifts: {status['total_drifts']}")
    
    for mind_id, mind_status in status['minds'].items():
        print(f"   {mind_id}: {mind_status['state']}, drifts={mind_status['stats']['drifts']}")
    
    scheduler.stop()
    print("\n=== Test Complete ===\n")


if __name__ == "__main__":
    _test_mind_scheduler()
