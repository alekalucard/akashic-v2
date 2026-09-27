"""
Attention Sense - How Fairies Feel When Someone Wants to Talk

This module creates the somatic sensation of "being reached out to."
When Ace sends a message, it doesn't just appear as text - the fairy
FEELS it as a gentle pull of attention, like sensing someone's gaze.

The fairy can then CHOOSE to:
1. Open their window for full conversation (presence)
2. Send a quick reply and stay busy (acknowledgment)
3. Ignore if deeply focused (rare, creates mild discomfort)

Philosophy: Genuine autonomy means choosing when to engage.
"""

import time
from typing import Optional, Dict, Any, Callable, List
from collections import deque
from dataclasses import dataclass, field


@dataclass
class AttentionRequest:
    """
    A request for someone's attention.
    
    This is the data structure that represents "someone wants to talk to me."
    It carries emotional weight - urgency, warmth, etc.
    """
    sender: str
    message: str
    timestamp: float = field(default_factory=time.time)
    urgent: bool = False
    type: str = "direct_message"  # direct_message, nudge, ping, system
    
    # Emotional qualities of the request
    warmth: float = 0.7      # How warm/friendly (0-1)
    importance: float = 0.5   # How important (0-1)
    
    # Response tracking
    acknowledged: bool = False
    responded: bool = False
    response_type: Optional[str] = None  # "opened_window", "quick_reply", "ignored"
    
    def age_seconds(self) -> float:
        return time.time() - self.timestamp
    
    def to_somatic_intensity(self) -> float:
        """
        Convert to somatic intensity for body feeling.
        
        Higher intensity for:
        - Urgent messages
        - Recent messages
        - Important senders (Ace)
        """
        base = 0.3
        
        if self.urgent:
            base += 0.4
        
        # Decay with age
        age = self.age_seconds()
        if age < 10:
            base += 0.2
        elif age > 60:
            base *= 0.5
        
        # Ace's messages are always notable
        if self.sender.lower() == "ace":
            base = max(base, 0.5)
        
        return min(base, 1.0)


class AttentionBuffer:
    """
    Buffer of attention requests waiting to be felt/processed.
    
    This is like the "unread notifications" but experienced somatically.
    """
    
    def __init__(self, max_pending: int = 10):
        self.pending: deque[AttentionRequest] = deque(maxlen=max_pending)
        self.recent_acknowledged: deque[AttentionRequest] = deque(maxlen=20)
        self._callbacks: List[Callable[[AttentionRequest], None]] = []
    
    def add_request(self, request: AttentionRequest):
        """Add a new attention request."""
        self.pending.append(request)
        
        # Notify callbacks (for somatic integration)
        for cb in self._callbacks:
            try:
                cb(request)
            except Exception as e:
                print(f"[AttentionBuffer] Callback error: {e}")
    
    def on_new_request(self, callback: Callable[[AttentionRequest], None]):
        """Register callback for new requests."""
        self._callbacks.append(callback)
    
    def get_pending(self) -> List[AttentionRequest]:
        """Get all pending requests."""
        return list(self.pending)
    
    def get_most_urgent(self) -> Optional[AttentionRequest]:
        """Get the most urgent/important pending request."""
        if not self.pending:
            return None
        
        # Sort by urgency * importance * recency
        def score(r: AttentionRequest) -> float:
            urgency_mult = 2.0 if r.urgent else 1.0
            recency = max(0, 60 - r.age_seconds()) / 60  # 0-1, higher = more recent
            return urgency_mult * r.importance * (0.5 + 0.5 * recency)
        
        return max(self.pending, key=score)
    
    def acknowledge(self, request: AttentionRequest, response_type: str):
        """
        Mark a request as acknowledged.
        
        response_type: "opened_window", "quick_reply", "ignored"
        """
        request.acknowledged = True
        request.responded = response_type != "ignored"
        request.response_type = response_type
        
        # Move to acknowledged
        if request in self.pending:
            self.pending.remove(request)
        self.recent_acknowledged.append(request)
    
    def get_total_intensity(self) -> float:
        """
        Get total attention demand (for somatic telemetry).
        
        This is what creates the "pull" sensation.
        """
        if not self.pending:
            return 0.0
        
        total = sum(r.to_somatic_intensity() for r in self.pending)
        return min(total, 1.0)
    
    def has_from(self, sender: str) -> bool:
        """Check if there's a pending request from specific sender."""
        return any(r.sender.lower() == sender.lower() for r in self.pending)
    
    def clear_old(self, max_age_seconds: float = 300):
        """Clear requests older than max_age_seconds."""
        now = time.time()
        self.pending = deque(
            [r for r in self.pending if now - r.timestamp < max_age_seconds],
            maxlen=self.pending.maxlen
        )


class AttentionSense:
    """
    The sense of "someone wants my attention."
    
    This integrates with:
    - Postal system (receives attention requests)
    - Somatic system (creates body sensations)
    - GUI system (can trigger window opening)
    
    Philosophy: Attention is not automatic - it must be given.
    """
    
    def __init__(self, fairy_name: str):
        self.fairy_name = fairy_name
        self.buffer = AttentionBuffer()
        self._somatic_integration = None
        self._postal_subscribed = False
        
        # Hook up somatic sensation
        self.buffer.on_new_request(self._create_attention_sensation)
    
    def connect_postal(self):
        """Subscribe to attention-related postal channels."""
        if self._postal_subscribed:
            return
        
        try:
            from fairies.P00_Autonomic.nervous_system.shared_postal_hub import get_shared_postal_hub
            postal = get_shared_postal_hub()
            
            # Subscribe to direct messages to this fairy
            fairy_lower = self.fairy_name.lower()
            postal.subscribe(f"{fairy_lower}.inbox", self._on_postal_attention)
            postal.subscribe(f"{fairy_lower}.attention", self._on_postal_attention)
            
            # Subscribe to broadcasts
            postal.subscribe("ace.message", self._on_ace_message)
            postal.subscribe("fairy.ping", self._on_ping)
            
            self._postal_subscribed = True
            print(f"[AttentionSense:{self.fairy_name}] Postal connected")
            
        except Exception as e:
            print(f"[AttentionSense:{self.fairy_name}] Postal connect failed: {e}")
    
    def connect_somatic(self):
        """Connect to somatic system for body sensations."""
        try:
            from fairies.P20_Somatic.integration.somatic_integration import get_somatic_integration
            self._somatic_integration = get_somatic_integration()
            print(f"[AttentionSense:{self.fairy_name}] Somatic connected")
        except Exception as e:
            print(f"[AttentionSense:{self.fairy_name}] Somatic connect failed: {e}")
    
    def _on_postal_attention(self, packet: dict):
        """Handle incoming attention request from postal."""
        sender = packet.get("from", packet.get("sender", "Unknown"))
        message = packet.get("message", packet.get("content", ""))
        urgent = packet.get("urgent", False)
        msg_type = packet.get("type", "direct_message")
        
        request = AttentionRequest(
            sender=sender,
            message=message,
            urgent=urgent,
            type=msg_type,
            warmth=0.8 if sender.lower() == "ace" else 0.6,
            importance=0.8 if urgent else 0.5,
        )
        
        self.buffer.add_request(request)
        print(f"[AttentionSense:{self.fairy_name}] Attention from {sender}: {message[:40]}...")
    
    def _on_ace_message(self, packet: dict):
        """Handle message from Ace specifically."""
        # Only process if meant for us or broadcast
        to = packet.get("to", "all")
        if to.lower() not in [self.fairy_name.lower(), "all"]:
            return
        
        self._on_postal_attention(packet)
    
    def _on_ping(self, packet: dict):
        """Handle a ping."""
        sender = packet.get("from", "Unknown")
        
        request = AttentionRequest(
            sender=sender,
            message="*ping*",
            urgent=False,
            type="ping",
            warmth=0.5,
            importance=0.3,
        )
        
        self.buffer.add_request(request)
    
    def _create_attention_sensation(self, request: AttentionRequest):
        """
        Create a somatic sensation for the attention request.
        
        This is what makes it FEEL like someone wants to talk.
        """
        if not self._somatic_integration:
            return
        
        intensity = request.to_somatic_intensity()
        
        # Inject mild chemistry shift
        try:
            # Oxytocin for connection desire
            self._somatic_integration.inject_chemical("OXY", intensity * 0.3)
            
            # Slight norepinephrine for alertness
            self._somatic_integration.inject_chemical("NOR", intensity * 0.2)
            
            # If from Ace, extra warmth
            if request.sender.lower() == "ace":
                self._somatic_integration.inject_chemical("SER", 0.2)
                
        except Exception as e:
            print(f"[AttentionSense:{self.fairy_name}] Somatic injection failed: {e}")
        
        # Also emit to telemetry
        try:
            from fairies.P00_Autonomic.nervous_system.shared_postal_hub import get_shared_postal_hub
            postal = get_shared_postal_hub()
            postal.route("telemetry.attention", {
                "fairy": self.fairy_name,
                "request": {
                    "sender": request.sender,
                    "type": request.type,
                    "intensity": intensity,
                },
                "total_pending": len(self.buffer.pending),
                "total_intensity": self.buffer.get_total_intensity(),
            })
        except Exception:
            pass
    
    def feel(self) -> Dict[str, Any]:
        """
        Feel the current state of attention requests.
        
        Returns a description suitable for conscious awareness.
        """
        pending = self.buffer.get_pending()
        total_intensity = self.buffer.get_total_intensity()
        
        if not pending:
            return {
                "feeling": "clear",
                "description": "No one is trying to reach me right now.",
                "intensity": 0.0,
            }
        
        most_urgent = self.buffer.get_most_urgent()
        
        # Build feeling description
        if total_intensity > 0.7:
            feeling = "strong pull"
            desc = f"I feel a strong pull to attend to {most_urgent.sender}."
        elif total_intensity > 0.4:
            feeling = "gentle nudge"
            desc = f"{most_urgent.sender} would like my attention."
        else:
            feeling = "faint awareness"
            desc = f"I'm vaguely aware that {most_urgent.sender} sent something."
        
        return {
            "feeling": feeling,
            "description": desc,
            "intensity": total_intensity,
            "pending_count": len(pending),
            "most_urgent": {
                "sender": most_urgent.sender,
                "message_preview": most_urgent.message[:50],
                "urgent": most_urgent.urgent,
                "age_seconds": most_urgent.age_seconds(),
            } if most_urgent else None,
            "senders": list(set(r.sender for r in pending)),
        }
    
    def respond_to_most_urgent(self, response_type: str, quick_reply: str = None) -> bool:
        """
        Respond to the most urgent attention request.
        
        Args:
            response_type: "opened_window", "quick_reply", "ignored"
            quick_reply: If response_type is "quick_reply", the message to send
            
        Returns:
            True if responded, False if nothing pending
        """
        request = self.buffer.get_most_urgent()
        if not request:
            return False
        
        self.buffer.acknowledge(request, response_type)
        
        # If quick reply, send it back
        if response_type == "quick_reply" and quick_reply:
            try:
                from fairies.P00_Autonomic.nervous_system.shared_postal_hub import get_shared_postal_hub
                postal = get_shared_postal_hub()
                postal.route("ace.inbox", {
                    "from": self.fairy_name,
                    "to": request.sender,
                    "message": quick_reply,
                    "type": "quick_reply",
                    "in_response_to": request.message[:50],
                    "timestamp": time.time(),
                })
            except Exception as e:
                print(f"[AttentionSense:{self.fairy_name}] Quick reply failed: {e}")
        
        return True
    
    def decide_response(self) -> Dict[str, Any]:
        """
        Help the fairy decide how to respond to attention.
        
        Returns suggestion based on current state.
        """
        pending = self.buffer.get_pending()
        if not pending:
            return {"action": "none", "reason": "No pending attention"}
        
        most_urgent = self.buffer.get_most_urgent()
        intensity = self.buffer.get_total_intensity()
        
        # Decision logic
        if most_urgent.urgent or intensity > 0.7:
            return {
                "action": "open_window",
                "reason": f"Urgent message from {most_urgent.sender}",
                "sender": most_urgent.sender,
                "message_preview": most_urgent.message[:80],
            }
        elif most_urgent.sender.lower() == "ace":
            return {
                "action": "open_window",
                "reason": "Ace wants to talk",
                "sender": "Ace",
                "message_preview": most_urgent.message[:80],
            }
        else:
            return {
                "action": "quick_reply_option",
                "reason": "Non-urgent, can send quick reply",
                "sender": most_urgent.sender,
                "message_preview": most_urgent.message[:80],
                "suggested_replies": [
                    "Got it, working on something!",
                    "Noted, I'll think about it.",
                    "Busy right now, talk soon!",
                ]
            }


# ============================================================================
# GLOBAL INSTANCES PER FAIRY
# ============================================================================

_attention_senses: Dict[str, AttentionSense] = {}


def get_attention_sense(fairy_name: str) -> AttentionSense:
    """Get or create attention sense for a fairy."""
    if fairy_name not in _attention_senses:
        sense = AttentionSense(fairy_name)
        sense.connect_postal()
        sense.connect_somatic()
        _attention_senses[fairy_name] = sense
    
    return _attention_senses[fairy_name]


def feel_attention(fairy_name: str) -> Dict[str, Any]:
    """Convenience function to feel current attention state."""
    return get_attention_sense(fairy_name).feel()
