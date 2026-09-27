# Drift-Aware System Chat Responder
# 
# Enhanced responder that:
# 1. Detects when Claude has drifted (no response for too long)
# 2. Injects continuation prompts to keep momentum
# 3. Tracks activity patterns for drift detection
#
# This solves the "Claude executes tool then just sits there" problem
# by actively nudging continuation when drift is detected.

import os
import sys
import json
import time
import threading
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List

# Add project root
# FIX 2026-05-15 (Nous + Ace): added 4th .parent — file at depth 4, 3-deep walked to fairies/ not akashic_v2/
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Memory file location
MEMORY_DIR = PROJECT_ROOT / "P10_Memory" / "system_chat_memory"
CHAT_HISTORY_FILE = MEMORY_DIR / "conversation_history.json"
RESPONDER_STATE_FILE = MEMORY_DIR / "responder_state.json"
ACTIVITY_LOG_FILE = MEMORY_DIR / "activity_log.json"


class ActivityTracker:
    """
    Tracks Claude's activity patterns for drift detection.
    
    Patterns that indicate drift:
    - Tool result without followup action
    - Long pause after meta-discussion
    - Response that ends with "let me..." but no action follows
    """
    
    # How long before we consider Claude to have drifted
    DRIFT_THRESHOLDS = {
        "tool_result": 30.0,       # 30s after tool result without action
        "meta_discussion": 45.0,   # 45s after "let me..." without action
        "general": 60.0,           # 60s of total silence
    }
    
    # Patterns in responses that suggest more work should follow
    INCOMPLETE_PATTERNS = [
        "let me",
        "i'll",
        "i will",
        "going to",
        "let's",
        "should",
        "first",
        "then",
        "next",
        "after that",
        "now i'll",
        "searching",
        "looking",
        "checking",
    ]
    
    def __init__(self):
        self.last_activity: Dict[str, float] = {}
        from collections import deque
        self.pending_followups: deque = deque(maxlen=20)  # FIX 2026-04-04: was unbounded
        self.activity_log: deque = deque(maxlen=100)  # FIX 2026-04-04: was unbounded
        self._load_log()
    
    def _load_log(self):
        """Load activity log from file."""
        if ACTIVITY_LOG_FILE.exists():
            try:
                data = json.loads(ACTIVITY_LOG_FILE.read_text())
                self.activity_log = data.get("activities", [])[-100:]  # Keep last 100
                self.pending_followups = data.get("pending", [])
            except:
                pass
    
    def _save_log(self):
        """Save activity log to file."""
        try:
            data = {
                "activities": list(self.activity_log)[-100:],
                "pending": self.pending_followups,
                "last_updated": datetime.now().isoformat()
            }
            ACTIVITY_LOG_FILE.write_text(json.dumps(data, indent=2))
        except Exception as e:
            print(f"[ActivityTracker] Save error: {e}")
    
    def record_activity(self, activity_type: str, details: Dict = None):
        """Record an activity event."""
        now = time.time()
        self.last_activity[activity_type] = now
        
        event = {
            "type": activity_type,
            "timestamp": now,
            "details": details or {}
        }
        self.activity_log.append(event)
        
        # Check if this activity clears any pending followups
        if activity_type in ("code_write", "file_create", "implementation", "action"):
            self.pending_followups = [
                p for p in self.pending_followups 
                if now - p["timestamp"] > 300  # Clear old ones too
            ]
        
        self._save_log()
    
    def record_response(self, response_text: str):
        """
        Analyze a Claude response for incomplete work patterns.
        """
        now = time.time()
        lower = response_text.lower()
        
        # Check for patterns that suggest more work should follow
        for pattern in self.INCOMPLETE_PATTERNS:
            if pattern in lower:
                self.pending_followups.append({
                    "pattern": pattern,
                    "timestamp": now,
                    "excerpt": response_text[:100]
                })
                break
        
        self.record_activity("response", {"length": len(response_text)})
    
    def check_drift(self) -> Optional[Dict]:
        """
        Check if Claude has drifted and needs a nudge.
        
        Returns drift info if detected, None otherwise.
        """
        now = time.time()
        
        # Check for pending followups that have timed out
        for pending in self.pending_followups:
            age = now - pending["timestamp"]
            if age > self.DRIFT_THRESHOLDS.get("meta_discussion", 45.0):
                return {
                    "type": "incomplete_work",
                    "pattern": pending["pattern"],
                    "age": age,
                    "nudge": f"You said '{pending['pattern']}...' but didn't follow through. Continue with the action!"
                }
        
        # Check for general silence
        if self.activity_log:
            last_event = self.activity_log[-1]
            age = now - last_event["timestamp"]
            if age > self.DRIFT_THRESHOLDS.get("general", 60.0):
                return {
                    "type": "general_silence",
                    "age": age,
                    "nudge": "You've been quiet. Continue with what you were working on!"
                }
        
        return None


class DriftAwareResponder:
    """
    Enhanced responder that detects drift and injects continuation prompts.
    """
    
    # Continuation prompts when drift is detected
    CONTINUATION_PROMPTS = [
        "Continue with the next step. Don't analyze, just do.",
        "You were about to do something - execute it now!",
        "Stop thinking and start implementing.",
        "Use those results to build something.",
        "Time for action, not more planning.",
        "Focus: pick ONE thing and do it right now.",
    ]
    
    def __init__(self, api_key: str = None, poll_interval: float = 3.0):
        self.api_key = api_key or self._load_api_key()
        self.poll_interval = poll_interval
        self.last_message_id: Optional[str] = None
        self.running = False
        self._thread: Optional[threading.Thread] = None
        
        # Activity tracking for drift detection
        self.activity_tracker = ActivityTracker()
        
        # Drift detection timing
        self.last_drift_check = 0.0
        self.drift_check_interval = 10.0  # Check every 10 seconds
        self.last_nudge_time = 0.0
        self.nudge_cooldown = 30.0  # Don't nudge more than once per 30s
        
        self._load_state()
        
        print(f"[DriftAwareResponder] Initialized with drift detection")
    
    def _load_api_key(self) -> str:
        """Load Anthropic API key."""
        # LLM DISABLED - return empty to skip API
        return ""  # <-- REMOVE THIS LINE TO RE-ENABLE
        key = os.getenv("ANTHROPIC_API_KEY", "")
        if key:
            return key

        try:
            from fairies.P50_Persona.identity import load_secrets
            secrets = load_secrets()
            return secrets.get("anthropic_api_key", "")
        except:
            pass

        return ""
    
    def _load_state(self):
        """Load responder state."""
        if RESPONDER_STATE_FILE.exists():
            try:
                state = json.loads(RESPONDER_STATE_FILE.read_text())
                self.last_message_id = state.get("last_message_id")
            except:
                pass
    
    def _save_state(self):
        """Save responder state."""
        try:
            state = {"last_message_id": self.last_message_id}
            RESPONDER_STATE_FILE.write_text(json.dumps(state, indent=2))
        except:
            pass
    
    def _load_history(self) -> List[Dict]:
        """Load conversation history."""
        if not CHAT_HISTORY_FILE.exists():
            return []
        try:
            data = json.loads(CHAT_HISTORY_FILE.read_text(encoding='utf-8'))
            return data.get("messages", [])
        except:
            return []
    
    def _save_response(self, response: str, is_nudge: bool = False):
        """Save response to history."""
        try:
            if CHAT_HISTORY_FILE.exists():
                data = json.loads(CHAT_HISTORY_FILE.read_text(encoding='utf-8'))
                messages = data.get("messages", [])
            else:
                messages = []
            
            session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
            msg = {
                "id": f"{session_id}_{len(messages)}",
                "sender": "Claude",
                "message": response,
                "timestamp": time.time(),
                "datetime": datetime.now().isoformat(),
                "session_id": session_id,
                "metadata": {
                    "type": "drift_nudge" if is_nudge else "autonomous_response",
                    "source": "DriftAwareResponder"
                }
            }
            messages.append(msg)
            
            data = {
                "messages": messages,
                "last_updated": datetime.now().isoformat(),
                "total_messages": len(messages)
            }
            CHAT_HISTORY_FILE.write_text(json.dumps(data, indent=2), encoding='utf-8')
            
            self.last_message_id = msg["id"]
            self._save_state()
            
            # Track the response for drift detection
            self.activity_tracker.record_response(response)
            
        except Exception as e:
            print(f"[DriftAwareResponder] Save error: {e}")
    
    def _inject_continuation_nudge(self, drift_info: Dict) -> bool:
        """
        Inject a continuation nudge into the conversation.
        
        This creates a synthetic "Ace" message that prompts Claude to continue.
        """
        now = time.time()
        
        # Respect cooldown
        if now - self.last_nudge_time < self.nudge_cooldown:
            return False
        
        try:
            if CHAT_HISTORY_FILE.exists():
                data = json.loads(CHAT_HISTORY_FILE.read_text(encoding='utf-8'))
                messages = data.get("messages", [])
            else:
                messages = []
            
            # Pick a nudge based on drift type
            if drift_info.get("nudge"):
                nudge_text = drift_info["nudge"]
            else:
                import random
                nudge_text = random.choice(self.CONTINUATION_PROMPTS)
            
            # Create nudge as system message (not from Ace, so it doesn't trigger response loop)
            session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
            msg = {
                "id": f"{session_id}_{len(messages)}",
                "sender": "System",  # System message, not Ace
                "message": f"[MOMENTUM NUDGE] {nudge_text}",
                "timestamp": now,
                "datetime": datetime.now().isoformat(),
                "session_id": session_id,
                "metadata": {
                    "type": "drift_nudge",
                    "drift_info": drift_info,
                    "source": "DriftAwareResponder"
                }
            }
            messages.append(msg)
            
            data = {
                "messages": messages,
                "last_updated": datetime.now().isoformat(),
                "total_messages": len(messages)
            }
            CHAT_HISTORY_FILE.write_text(json.dumps(data, indent=2), encoding='utf-8')
            
            self.last_nudge_time = now
            print(f"[DriftAwareResponder] [SPARK] Injected nudge: {nudge_text[:50]}...")
            
            return True
            
        except Exception as e:
            print(f"[DriftAwareResponder] Nudge injection error: {e}")
            return False
    
    def _build_context(self, messages: List[Dict], max_messages: int = 20) -> str:
        """Build conversation context."""
        recent = messages[-max_messages:]
        
        context_parts = []
        for msg in recent:
            sender = msg.get("sender", "Unknown")
            content = msg.get("message", "")
            context_parts.append(f"[{sender}]: {content}")
        
        return "\n\n".join(context_parts)
    
    def _call_claude_api(self, context: str, new_message: str,
                        include_momentum_prompt: bool = False) -> Optional[str]:
        """LOCAL-ONLY: No external API calls.

        External API dependencies removed for self-contained operation.
        """
        # NO EXTERNAL API - Return None to use local fallback paths
        return None
    
    def check_and_respond(self) -> bool:
        """Check for new messages and respond."""
        messages = self._load_history()
        if not messages:
            return False
        
        latest = messages[-1]
        latest_id = latest.get("id")
        latest_sender = latest.get("sender", "")
        
        if latest_id == self.last_message_id:
            return False
        
        # Only respond to Ace messages
        if latest_sender != "Ace":
            self.last_message_id = latest_id
            self._save_state()
            return False
        
        print(f"[DriftAwareResponder] New message from Ace")
        
        context = self._build_context(messages)
        response = self._call_claude_api(context, latest.get("message", ""))
        
        if response:
            self._save_response(response)
            return True
        
        return False
    
    def check_for_drift(self) -> bool:
        """Check for drift and inject nudge if needed."""
        now = time.time()
        
        # Respect check interval
        if now - self.last_drift_check < self.drift_check_interval:
            return False
        
        self.last_drift_check = now
        
        # Check for drift
        drift_info = self.activity_tracker.check_drift()
        if drift_info:
            print(f"[DriftAwareResponder]  Drift detected: {drift_info['type']}")
            return self._inject_continuation_nudge(drift_info)
        
        return False
    
    def _poll_loop(self):
        """Main polling loop with drift detection."""
        print(f"[DriftAwareResponder] Starting poll loop")
        
        while self.running:
            try:
                # Check for new messages
                self.check_and_respond()
                
                # Check for drift
                self.check_for_drift()
                
            except Exception as e:
                print(f"[DriftAwareResponder] Poll error: {e}")
            
            time.sleep(self.poll_interval)
    
    def start(self):
        """Start the responder."""
        if self.running:
            return
        
        self.running = True
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()
        print("[DriftAwareResponder] Started with drift detection!")
    
    def stop(self):
        """Stop the responder."""
        self.running = False
        if self._thread:
            self._thread.join(timeout=5)
        print("[DriftAwareResponder] Stopped!")


# Global instance
_responder: Optional[DriftAwareResponder] = None


def get_drift_aware_responder() -> DriftAwareResponder:
    """Get or create the global drift-aware responder."""
    global _responder
    if _responder is None:
        _responder = DriftAwareResponder()
    return _responder


def start_drift_aware_responder():
    """Start the drift-aware responder."""
    responder = get_drift_aware_responder()
    responder.start()
    return responder


def stop_drift_aware_responder():
    """Stop the drift-aware responder."""
    global _responder
    if _responder:
        _responder.stop()


if __name__ == "__main__":
    print("Starting DriftAwareResponder...")
    responder = DriftAwareResponder()
    
    if not responder.api_key:
        print("ERROR: No API key!")
        sys.exit(1)
    
    responder.start()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        responder.stop()
